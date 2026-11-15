<!-- src-sha1: 349e8112a4dcc4567ce203cf21c4c37e5bb47173 -->
# WhatsApp App Empresarial — Full RE Report
**Versão:** 2.26.45.7 (Business) vs 2.26.45.10 (consumer) | **Data:** 2026-11-15
**Escopo:** diff estrutural do APK WhatsApp Business (`com.whatsapp.w4b`) contra o WhatsApp consumer (`com.whatsapp`) — raízes de pacote exclusivas do Business, a pilha React Native, diff de bibliotecas nativas, assimetria de catálogo doc_id GraphQL/MEX/`www`/`facebook-schema`, diff de permissões; distinção da WhatsApp Business API/Cloud API e da Managed Account

---

## 1. Visão geral

WhatsApp Business é um app separado (`com.whatsapp.w4b`), não um modo alternável dentro do WhatsApp consumer. Ele compartilha o núcleo do protocolo Signal, o transporte Noise, e a maior parte da UI de chat com o WhatsApp consumer, mas embarca seu próprio conjunto de pacotes para recursos exclusivos de empresas e inclui uma dependência — um runtime React Native completo — que o consumer não carrega de forma alguma.

Este relatório cobre apenas o **app em si**, comparado como APK contra o WhatsApp consumer. É um eixo diferente de dois outros conceitos adjacentes a "business" já documentados neste repositório:

| Conceito | O que é | Relatório |
|---|---|---|
| **App WhatsApp Business** (este relatório) | Um APK de cliente distinto (`com.whatsapp.w4b`) que uma empresa instala em um telefone, com sua própria UI para catálogo, etiquetas, mensagens de ausência, anúncios | aqui |
| **WhatsApp Business API / Cloud API** | Infraestrutura do lado do servidor que hospeda/retransmite as mensagens do número de uma empresa, usada no lugar de ou junto com o app Business; sinalizada em qualquer cliente apenas via campos de certificado de nome verificado (`host_storage`, `actual_actors`, prefixo de emissor `smb:`/`ent:`) e banners de coexistência `business_state_id` | `WA_MANAGED_ACCOUNT.md` §9 |
| **Managed Account** | A própria conta consumer de um menor, supervisionada por um pai/responsável (`ManagedAccount*`/PAA/PMA/PMTA); não relacionado a nenhum dos conceitos business, não existe rótulo "gerenciado" para o caso business | `WA_MANAGED_ACCOUNT.md` §1-8 |

Uma única empresa pode combinar os três: rodar o app Business em um dispositivo, delegar partes de seu tráfego a um provedor de Cloud API (coexistência), enquanto a conta do parceiro de chat é uma conta consumer comum. Ver §9 para como esses interagem.

Fonte de evidência: um diff estático de pacote/asset/manifesto entre `WA-Business_2.26.45.7.apk` e `WhatsApp_2.26.45.10.apk` (par beta atual no momento do diff, não uma comparação versão-a-versão). Nenhum decompile jadx de APK completo foi executado em nenhum dos dois lados (regra rígida de segurança); todas as descobertas abaixo são no nível de árvore smali do apktool, JSON de assets, e manifesto reconstruído. Os tiers seguem `found`/`inferred`/`unknown` conforme o contrato de evidência do brain.

---

## 2. Diff no nível de pacote — found

Comparando todo diretório sob `smali*/` em cada árvore apktool: o Business tem 4.281 diretórios de caminho de pacote únicos (15 árvores `smali_classesN`), o consumer tem 3.710 (14 árvores). 853 caminhos existem apenas no Business, 282 apenas no consumer. 45 raízes de pacote `com/whatsapp/*` de nível superior são exclusivas do Business (o próprio diretório raiz ausente no consumer, não apenas um subcaminho).

### 2.1 Raízes de pacote exclusivas do Business, por cluster de recurso

| Cluster | Raízes de pacote | Notas |
|---|---|---|
| Mensageria de ausência / saudação / resposta rápida | `businessaway`, `businessgreeting`, `businessquickreply`, `businessmissedcallfollowup` | recursos centrais de auto-resposta SMB |
| Etiquetas / agentes / atribuição de chat | `chatassignment`, `authagent`, `authagentfeaturecontrol`, `smbmultideviceagents`, `businesscontactmanager`, mais `lists/smb/labels` (subcaminho; a raiz `lists` é compartilhada) | assentos de agente e edição de etiqueta |
| Configuração de perfil / verificação | `businessregistration`, `protectedbusinessaccounts`, `metaverified` | |
| Catálogo/pedidos (lado de gerenciamento) | `ordermanagement` | a própria navegação/edição de catálogo (`catalog`, `businessproduct`, `businesscollection`) é **compartilhada** — ver §2.2 |
| Anúncios / integração Meta Ads | `ads4ads`, `adscreation`, `adcreationinterfaces` | ver §3 para o vínculo com React Native |
| Cobrança / assinaturas (tiers de API) | `metabilling`, `metabillingui`, `subscription`, `billingui` | |
| Coexistência app-para-API | `coexistence`, `connectedaccounts`, `linkedaccounts`, `dynamicaudience` | faz a ponte com o lado Cloud API, §9 |
| Agente business de Meta AI | `bizai`, `genai`, `maiba` | |
| Ferramentas business / compliance | `businesstools`, `businessinsights`, `rapidfeedbacksurvey`, `reportblocksharing`, `statistics`, `integrityenforcementsinfra`, `eligibilitychecker`, `googleeligibilityapi`, `smb`, `smbauth`, `waloginmbs`, `marketingmessage`, `marketingmessagemanagement`, `mediatemplates`, `bizdatasharing`, `bizgallerypicker`, `bizmedia` | |

### 2.2 Raízes compartilhadas com subpacotes exclusivos do Business

Algumas raízes existem em ambos os apps porque o consumer pode visualizar/consumir dados do lado business, mas os subpacotes de edição/gerenciamento são exclusivos do Business:

- `com/whatsapp/businessprofile/` — raiz compartilhada; `businessprofileaddress`, `businessprofilecategory`, `businessprofileedit` (+ `boostmedia`, `businessprofilecompleteness`), `businessvertical`, `businesscompliance/smb/...` são exclusivos do Business. O consumer mantém apenas os subpacotes de visualização de perfil do lado de leitura.
- `com/whatsapp/lists/` — raiz compartilhada (modelo de dados/UI de etiqueta, `labelitem` em ambos); o subpacote de **edição** de etiqueta `lists/smb/labels` é exclusivo do Business.
- `catalog`, `businessproduct` (+ `businessproductlist`), `businesscollection` — raízes compartilhadas, confirmadas presentes na árvore smali do consumer como a UI de **navegação** de catálogo/produto exibida ao visualizar um chat de empresa.

Formato geral: a visualização de catálogo/produto, a visualização de perfil business, e a exibição de etiquetas são compartilhadas; a edição de catálogo/perfil, a mensageria de ausência/saudação/resposta rápida, a edição de etiquetas, a autenticação de agente/multi-dispositivo, a criação de anúncios, e a coexistência com Cloud API são exclusivas do Business.

### 2.3 Pacotes exclusivos do consumer — found, não agrupados

282 caminhos existem apenas no consumer. Uma verificação pontual não revelou um cluster temático comparável em tamanho ao conjunto exclusivo do Business; a maioria são filhos aninhados de um número menor de raízes exclusivas do consumer. Não investigado em profundidade — listado como uma lacuna aberta em §8.

---

## 3. A pilha React Native — found, exclusivo do Business

Descoberta inesperada: o Business embarca uma pilha React Native completa ausente do consumer no nível de pacote, não apenas um módulo de recurso extra.

| Pacote | Business | Consumer |
|---|---|---|
| `com/facebook/react/*` (bridge, fabric, animated, devsupport, turbomodule, …) | 88 diretórios | 0 |
| `com/facebook/catalyst/*`, `com/facebook/fbreact/*` (módulos de bridge RN, i18n, safe-area) | presente | ausente |
| `com/facebook/hermes/*` | 3 diretórios | 1 diretório — apenas uma referência solta, sem nenhum `com/facebook/react` para formar par, ou seja, não é um runtime RN funcional |
| `com/caverock/androidsvg`, `com/crossapp/graphql/facebook/*` | presente | ausente |

Corroborado no nível de biblioteca nativa (§4): `libreactnative.so` (runtime RN), `libappmodules.so` (o carregador nativo do bundle JS do RN), e `libimagepipeline.so` (Fresco, o pipeline de imagem do RN) são arquivos `.so` exclusivos do Business.

**Inferred**, não confirmado: alguma superfície exclusiva do Business — mais plausivelmente a criação de anúncios (`adscreation/lwi/react/*` tem um subpacote `react` diretamente dentro de `lwi`), Meta-billing, ou onboarding de coexistência — é implementada como telas React Native embutidas em vez de UI Android nativa. Qual recurso específico usa a pilha RN não está confirmado apenas pelos nomes de pacote; precisaria de um decompile delimitado das classes `adscreation/lwi/react/activity`. Esta é a "dependência surpreendente" mais clara que resta: um app de mensageria para empresas embute um runtime JS de UI multiplataforma, aparentemente apenas para uma ou poucas telas (a criação de anúncios é a correspondência de nomenclatura mais forte).

---

## 4. Diff de biblioteca nativa — found

Comparado o `superpack_index.csv` (o manifesto de biblioteca do próprio contêiner SUPERPACK_OB) entre as saídas de reconstrução dos dois apps:

| | Contagem |
|---|---|
| Bibliotecas consumer indexadas | 84 |
| Bibliotecas Business indexadas | 89 |

**Exclusivas do Business (5):** `libappmodules.so`, `libimagepipeline.so`, `libreactnative.so`, `libwacomponents.so` (o nome sugere uma biblioteca de componentes-bridge RN de autoria do WhatsApp, não o RN padrão), `libzstddecoder.so` (provavelmente descompressão de bundle/asset do RN).

**Exclusivas do consumer:** nenhuma — todo nome de biblioteca do consumer também aparece no índice do Business.

As 6 bibliotecas decompiladas por device-oracle compartilhadas por ambos os apps (`libwhatsapp.so`, `libwhatsappmerged.so`, `libwasafe.so`, `libvoprf-ed25519.so`, `libohai.so`, `libcurve25519.so`) são idênticas entre os dois apps (mesmos tamanhos, mesmas contagens de símbolo/export) — o núcleo do protocolo Signal/atestação/integridade de cliente não é tocado pela build Business. A pilha React Native + Fresco é exclusiva do Business tanto no nível de pacote Java/Kotlin quanto no nível de biblioteca nativa — uma descoberta consistente em duas camadas.

---

## 5. Diff de catálogo doc_id GraphQL / MEX / `www` / `facebook-schema` — found

Cada app embarca seu próprio catálogo doc_id `assets/whatsapp-android-<schema>_client_persist_ids.json`, lido diretamente da árvore de assets decodificada pelo apktool (sem necessidade de decompile).

| Schema | Ops Business | Ops consumer | Exclusivo Business | Exclusivo consumer |
|---|---|---|---|---|
| `mex` | 242 | 242 | 0 | 0 — conjunto idêntico |
| `wamo` | 22 | 22 | 0 | 0 — conjunto idêntico |
| `www` | 237 | 244 | 4 | 11 |
| `facebook-schema` | 224 | 17 | 215 | 7 |

### 5.1 `mex` e `wamo` — idênticos entre os apps

Ambos os catálogos têm exatamente os mesmos nomes de operação em ambos os APKs (a diferença de conjunto é vazia, não apenas igual em contagem). O Business não carrega nenhuma superfície MEX/GraphQL específica do Business neste nível de schema — ele compartilha o catálogo do consumer por completo.

### 5.2 `www` — pequena assimetria

- Exclusivo do Business (4): `BPAccessTokenAndSessionCookiesMutation`, `CatkitTypeaheadProxy`, `WACreateEnforcementAppeal`, `WAGetEnforcementAppealStatus`.
- Exclusivo do consumer (11): `WaAutofillAcknowledgeWalletTerms`, `WaAutofillFetchContactData`, `WaAutofillFetchSettings`, `WaAutofillSaveContactData`, `WaAutofillUpdateNegativeInteraction`, `WaAutofillUpdateSaveCvv`, `WaCreateLabyrinthBackupMutation`, `WaDeleteLabyrinthAccountMutation`, `WaDeleteLabyrinthThreadsMutation`, `WaRotateLabyrinthEpochMutation`, `WaUploadLabyrinthMessagesMutation`.

O consumer carrega suas próprias ops de pagamentos pessoais/autofill (`WaAutofill*`) e de backup de chat E2E (`WaCreateLabyrinthBackupMutation` etc. — o sistema de backup de chat do WhatsApp, "Labyrinth" internamente) que o Business não tem; o Business carrega algumas ops de apelação de enforcement de conta e sessão/typeahead que o consumer não precisa.

### 5.3 `facebook-schema` — a descoberta principal: 215 ops exclusivas do Business

É aqui que a superfície GraphQL realmente específica do Business vive — não em `mex`/`wamo`, que são byte-idênticos entre os dois apps. O Business carrega 224 ops neste schema contra as 17 do consumer; as 17 do consumer são ops de pagamento pessoal/nonce de comércio não relacionadas (`AcDcCreateCanonicalDigitalCommerceNonce`, `WaAutofillAddPayCreditCard`, `WaGetServerEncryptionKey`, etc.) que o Business não carrega.

As 215 ops exclusivas do Business, agrupadas por nome (agrupamento descritivo, derivado de análise estática, não uma taxonomia funcional confirmada):

| Cluster | Ops de exemplo |
|---|---|
| Base de conhecimento / resposta por IA / simulação ("coach") | `FetchAIAbilities`, `KnowledgeRepoFetchV2`, `UpdateAIKnowledge`, `DeleteAIKnowledge`, `CoachSimulationMessage`, `CoachSuggestedReply`, `StartSimulation`, `SubmitSimulationFeedback`, `FetchSuggestedReply`, `MarkSuggestedReplyUsed` |
| Agente business de Meta AI / MAIBA | `MAIBAOnboarding`, `MAIBACompleteParallelOnboarding`, `Maiba1pCalendarEvents`, `MaibaGetCurrentCatalog`, `MaibaDownloadLeadGenFlow`, `MetaAIBizAgentWAAIHome`, `MetaAIBizAgentWACoachingMutation` |
| Lead-gen / agendamentos | `CreateLeadGenFlow`, `GetLeadGenFlowLeads`, `UpdateLeadStages`, `CreateAppointmentFlow`, `GetAppointmentPrefill`, `GetDefaultAvailability` |
| Agente de autenticação / multi-agente SMB / login | `AuthAgentCompanyInfoQuery`, `AuthAgentFeaturePolicyQuery`, `AddSmbAgentAndCoexQr`, `SmbRegistrationInit`, `WALoginClaimAuthChallenge`, `WALoginConfirmAuthChallenge` |
| Coexistência app-para-Cloud-API | `CoexUnifiedOnboarding`, `CoexMultiAppEligiblity`, `CoexAppsAndServicesOffboardProduct`, `CoexCompanionPairingStatusCallback`, `CoexistenceQRCodeFetch` |
| Anúncios click-to-WhatsApp (CTWA) | `CTWACreateLookAlikeAudienceMutation`, `CTWAPreviousAdsRecommendationQuery`, `CtwaLinkedMediaQuery`, `CtwaNativeUploadAdMediaMutation` |
| Conta de anúncios / elegibilidade | `AdAccountEligibilityCheckerQuery`, `OnboardToWhatsAppAdAccount`, `WhatsAppBizFetchAdDefaults`, `WhatsAppBizGetEstimatedAdReach` |
| Gerenciamento de catálogo (lado de escrita) | `WhatsAppCatalogAddProduct`, `WhatsAppCatalogEditProduct`, `WhatsAppCatalogDeleteProduct`, `WhatsAppCatalogCreateCollections`, `WhatsAppCatalogProductVisibilityUpdate` |
| Transmissão de mensagem de marketing ("Pro") | `BusinessBroadcastProCampaignContent`, `BusinessBroadcastProCustomAudiencesQuery`, `BusinessBroadcastProInsights`, `WAMarketingMessagesCustomAudienceCreateMutation` |
| Gerenciador de contatos / perfis de cliente | `BizContactManagerProfiles`, `ContactManagerAccessState`, `WACustomerProfiles`, `UpsertWACustomerProfiles`, `DeleteWACustomerProfile` |
| Cobrança / assinatura (tiers cobrados pela Meta) | `FetchSubscriptionState`, `FetchSubscriptionStateV2`, `WaSmbMetaOneTierPaymentPrefetchTargetQuery`, `AcceptBizAiPaymentTerms` |
| Exportação de histórico de chat / integração 3P (GDrive) | `FetchChatHistoryExportStatus`, `GDriveGetFiles`, `UploadHistoricalMetadata`, `Disconnect3PPartners` |
| Conta IG/FB vinculada | `SetIGDisplayContactInfoMutation`, `WAFBPageProfileImportGet`, `WhatsAppBusinessLinkedAccountsQuery` |
| Infraestrutura de QE/feature-flag (lado business) | `CheckQEBool`, `WaFetchQEBool`, `WaFetchQEString`, `WhatsAppGraphQLCheckQE` |

A lista completa dos 215 nomes é reproduzível a partir dos arquivos de asset dos dois apps citados acima; não reproduzida literalmente aqui. Os **valores** de doc_id de `www`/`facebook-schema` (não apenas os nomes das ops) não foram comparados — um nome de op compartilhado poderia em princípio ainda carregar um doc_id diferente entre os dois apps; não verificado.

---

## 6. Diff de permissões — found

Do inventário de manifesto de cada app:

| | Exclusivo Business | Exclusivo consumer |
|---|---|---|
| Permissão | `com.whatsapp.permission.MIGRATION_CONTENT_PROVIDER` | `android.permission.RECEIVE_SMS` |

Ambos os apps adicionalmente solicitam permissões próprias de auto-broadcast/mapas de pacote sob seus respectivos nomes de pacote (`com.whatsapp.w4b.*` vs `com.whatsapp.*`) — são equivalentes um do outro com o nome de pacote mascarado, não funcionalmente novos, e não contados acima.

O Business não solicita recebimento de SMS. **Inferred**, não confirmado pelo código: consistente com contas Business se registrando mais frequentemente via um caminho Cloud/Business API em vez de depender de leitura automática de SMS no dispositivo para OTP — mas esse raciocínio não é verificado contra nenhum código de fluxo de registro nesta passagem.

---

## 7. Nota Baileys / velowa

Quase nada da superfície deste relatório é alcançável a partir de um cliente WhatsApp Web comum (velowa ou qualquer implementação do protocolo Noise/multi-dispositivo):

- Os catálogos `mex`/`wamo` são **idênticos** aos do consumer — nada específico do Business para adicionar aí; qualquer cliente WA Web já tem os mesmos doc_ids.
- As 215 ops `facebook-schema` (§5.3) são a superfície GraphQL realmente específica do Business, mas são fluxos conduzidos pela **UI do app** Business (edição de catálogo, criação de anúncios, coaching/MAIBA, onboarding de coexistência, autenticação de agente) com gate pelo próprio estado de conta do app Business e, em vários clusters, inteiramente pelo lado do servidor da WhatsApp Business API/Cloud API (coexistência, cobrança, contas de anúncio). Um cliente WA Web falando o protocolo multi-dispositivo comum não tem caminho para a maioria disso — não são de forma alguma recursos de protocolo de wire, são chamadas REST/GraphQL que a própria UI do app Business faz contra o backend da plataforma business da Meta.
- A superfície React Native de criação de anúncios (§3) é apenas UI do app Android (telas JS embutidas renderizadas por `libreactnative.so`); nada nela trafega no protocolo de wire do chat.
- A única área com qualquer relevância para o protocolo multi-dispositivo é a coexistência (`coexistence`/`connectedaccounts`/`linkedaccounts`), cuja representação de dispositivo/sessão é coberta pela documentação já existente em `WA_MANAGED_ACCOUNT.md` §9.3 e `WA_LINKED_DEVICE_PAIRING.md` (tipo de conta `HOSTED`, device id 99, `platformType` 23/25-27) — essa parte já é tão longe quanto uma visão apenas do lado cliente pode ir.

Resumo: este relatório é útil para entender o que o APK Business *contém*, não como fonte de nova superfície de protocolo de wire para a velowa.

---

## 8. O que este relatório NÃO verificou

| Lacuna | Motivo | Acompanhamento necessário |
|---|---|---|
| Diff de schema proto/wire entre os dois apps | `unknown`, não inferred-same. O estágio proto do pipeline de reconstrução não rodou para nenhuma das duas builds (`protoc_ok=False` em ambos os lados); a extração proto mais profunda usada em outro lugar nesta passagem de atualização de versão (1089 mensagens, `protoc` exit 0) rodou apenas contra o decompile jadx pré-existente do consumer — não existe decompile equivalente para `com.whatsapp.w4b` neste workspace. Produzir um exigiria uma execução jadx de APK completo, proibida pela regra rígida de segurança desta sessão (travou a máquina de análise anteriormente). Ausência de evidência não é evidência de ausência. | Uma extração jadx de classe única ou DEX único delimitada apenas às classes de mensagem/proto (não um decompile de APK completo) |
| Qual(is) recurso(s) renderiza(m) através da pilha React Native exclusiva do Business | Apenas correlação de nome de pacote/biblioteca (`adscreation/lwi/react/*` é a correspondência de nomenclatura mais forte, mas não confirmada) | Decompile delimitado das classes `com/whatsapp/adscreation/lwi/react/*` |
| Cluster de pacotes exclusivos do consumer (282 caminhos) | Não agrupado tematicamente nesta passagem — prioridade menor dado o enquadramento da tarefa na superfície exclusiva do Business | Uma passagem dedicada sobre o diff de 282 caminhos |
| **Valores** de doc_id de `www`/`facebook-schema` | Apenas **nomes** de op foram comparados; um nome compartilhado poderia carregar um doc_id diferente por app | Diff no nível de valor de ambos os JSONs de asset |
| Lista completa de 215 ops/variáveis/formatos de resposta de `facebook-schema` | O agrupamento é apenas por palavra-chave do nome; nenhuma recuperação de ponto de chamada ou campo de resposta foi tentada | Rastreamento de ponto de chamada direcionado por cluster, como feito para as ops MEX de outros relatórios |

---

## 9. Distinções importantes

| A | B |
|---|---|
| **App** WhatsApp Business (`com.whatsapp.w4b`) — um APK distinto com seu próprio conjunto de pacotes, este relatório | WhatsApp Business **API / Cloud API** — hospedagem/retransmissão do lado do servidor das mensagens do número de uma empresa; nenhum APK de cliente dedicado, sinalizado em qualquer cliente via campos de certificado de nome verificado (`WA_MANAGED_ACCOUNT.md` §9) |
| Pacotes `coexistence`/`connectedaccounts`/`linkedaccounts` do app Business — a própria UI do app para fazer a ponte com um provedor de Cloud API | Banners de coexistência `business_state_id` vistos pelo cliente de um **parceiro** (consumer ou Business) quando um número business roda tanto o app quanto a API ao mesmo tempo (`WA_MANAGED_ACCOUNT.md` §9.2) |
| Managed Account (`ManagedAccount*`, PAA/PMA/PMTA) — a própria conta **consumer** de um menor sob supervisão parental | App Business — a conta de uma empresa, conceito totalmente não relacionado, sem sobreposição de código/schema |
| Catálogos doc_id `mex`/`wamo` — conjuntos de nomes de op byte-idênticos em ambos os apps | Catálogo doc_id `facebook-schema` — 215 ops existem apenas no Business; é aqui que a superfície GraphQL específica do Business realmente vive |
| **Visualização** de catálogo/perfil/etiqueta — raízes de pacote compartilhadas, presentes também no consumer (então um usuário consumer pode navegar o catálogo de uma empresa) | **Edição** de catálogo/perfil/etiqueta — raízes de pacote exclusivas do Business (o lado de escrita que apenas a própria empresa pode alcançar) |

---

## 10. Resumo

Confirma o formato esperado de entrada — catálogo, perfil business/verificação, etiquetas, resposta rápida/saudação/mensageria de ausência, cluster de autenticação de agente/multi-dispositivo em código exclusivo do Business, com a metade de visualização/exibição de cada um compartilhada com o consumer — e adiciona duas descobertas não previstas:

1. **`facebook-schema` é onde a superfície GraphQL realmente específica do Business vive** (215 ops exclusivas do Business: coach de IA/base de conhecimento, MAIBA, lead-gen, auth-agent, coexistência, anúncios CTWA, ops de escrita de catálogo, transmissão de marketing, cobrança), não os catálogos principais `mex`/`wamo`, que são conjuntos de nomes de op byte-idênticos entre os dois apps.
2. **O Business embarca uma pilha React Native + Fresco completa** (`com.facebook.react.*`, `libreactnative.so`, `libimagepipeline.so`, `libwacomponents.so`) totalmente ausente do consumer, tanto no nível de pacote quanto no nível de biblioteca nativa — mais plausivelmente sustentando telas de criação de anúncios, mas a fronteira exata do recurso não está confirmada sem um decompile delimitado.

O diff de schema proto/wire não pôde ser feito nesta passagem (§8) e é registrado como unknown, não inferred-same.
