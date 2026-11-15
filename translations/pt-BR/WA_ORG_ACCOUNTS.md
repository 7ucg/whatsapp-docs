<!-- src-sha1: 5fa1223d0cb214989ef32453299c247d3ee92ecf -->
# WhatsApp Contas de Organização — Full RE Report
**Versão:** 2.26.45.10 | **Data:** 2026-11-15
**Escopo:** modelo de entidade de conta org (org_id, diretório de membros, taxonomia de member-tag/equipe), fluxo de entrada via link de convite, verificação de disponibilidade de nome de exibição, onboarding com gate de email (OTP), catálogo de operações `GraphQlOrgApi`/`OrgEmailCodeClient` (9 ops, `www` + `mex`), distinção de Managed Account e de delegação da WhatsApp Business API, notas de implementação Baileys/velowa

---

## 1. O que é uma conta org

Todas as afirmações são análise estática do APK decompilado. Tier: **found** = leitura literal de string/campo em um ponto de chamada, **inferred** = deduzido do formato do código sem uma sequência de chamada rastreada de ponta a ponta, **unknown** = não resolvido.

Um "org" (nome interno usado em todo o código, nunca expandido para "organization" em nenhuma string lida) é uma entidade de membresia com identidade própria, um diretório de membros ao qual se pode aderir, e um caminho de onboarding por link de convite mais OTP por email, totalmente separado do próprio registro por número de telefone da conta e dos outros dois sistemas de som "gerenciado" já presentes neste repositório (seção 7).

| Entidade | Nome interno | Campos (found) | Papel |
|---|---|---|---|
| Identidade org | `org_id` | `org_id`, `org_name`, `org_member_count`, `org_icon_url`/`org_icon_handle`/`org_icon_full_url`, `org_description` | a própria org, resolvida a partir de um link de convite |
| Link de convite | `link_token` | carregado de ponta a ponta do referrer/deep-link até a mutation final de entrada | credencial de entrada de uso único(?); vida útil exata `unknown` |
| Identidade do membro dentro da org | `display_name` (+ `display_last_name` opcional), `member_tag` | nome de exibição por membro sujeito à própria verificação de disponibilidade/política, independente do nome principal de perfil da conta | como um membro é mostrado dentro do diretório da org |
| Taxonomia de equipe/papel | `team`, `team_options`, `selected_team` | encontrados como campos de estado; semântica dos valores individuais de equipe não resolvida | agrupamento de membros dentro de uma org |
| Relação no diretório | `relationship` (`OrgDirectory`), único valor observado `"CONTACT"` | — | o único valor de filtro de relação visto; outros mapeamentos ordinal→string são `unknown` |

Todos esses nomes de campo são lidos literalmente como `const-string` imediatamente antes de uma chamada setter `GraphQlCallInput`/`LX/0jN` em `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali` e `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali` (2.26.45.10), mais a lista de campos do objeto de estado `OrgJoinViewModel` — tudo **found**. A ordem de passos que encadeia essas ops em um fluxo (seção 3) é **inferred** a partir de como os campos de estado se alinham, não de uma única sequência de chamada rastreada.

---

## 2. Catálogo de operações

9 operações em dois transportes, todas em `com.whatsapp.orgs`. 7 em `www` (`GraphQlOrgApi`, GraphQL de doc_id persistido via `Lcom/facebook/pando/TreeWithGraphQL`), 2 em `mex` (`OrgEmailCodeClient`). As variáveis são **found** a partir do ponto de chamada em cada linha abaixo.

| Op | Transporte | doc_id (2.26.45.10) | Tipo | Variáveis | Propósito |
|---|---|---|---|---|---|
| `OrgInvitePreview` | www | `29166886682947630` | Query | `link_token` | pré-visualizar org (nome/ícone/contagem de membros) antes de se comprometer a entrar |
| `OrgCheckDisplayName` | www | `28738875225734024` | Query | `display_name` | verificação de disponibilidade/política para o nome de exibição do membro dentro da org |
| `OrgCheckEmailEligibility` | www | `28705126895811065` | Query | `link_token`, `email` | se este email pode ser usado para este convite de org específico |
| `OrgSendEmailCode` | mex | `28659396457057459` | Mutation | `email` | enviar OTP por email |
| `OrgVerifyEmailCode` | mex | `29096159596657036` | Mutation | `email`, `code` | verificar OTP por email |
| `OrgJoin` | www | `29366364109633604` | Mutation | `link_token`, `email`, `org_display_name`, `member_tag`, `org_display_last_name` | submissão final de entrada |
| `OrgDirectory` | www | `28698253656512395` (rotacionado de `28049955604655823` na 2.26.41.6) | Query | `org_id`, `relationship` (apenas `"CONTACT"` observado), `first`, `after` | diretório de membros paginado, pós-entrada |
| `OrgMemberSearch` | www | `39884553687825642` (rotacionado de `28199835469697557`) | Query | `query`, `org_id`, `first`, `after` | busca dentro do diretório de membros |
| `OrgLeaveMutation` | www | `28491454287217875` | Mutation | `org_id` | saída da org, em qualquer momento após entrar |
| `OrgList` | www | `28999557569709709` (rotacionado de `27920891847589435`) | Query | `unknown` (nenhum ponto de chamada estático encontrado além do doc_id/rotação) | listar orgs às quais a conta pertence |

Todas as 7 ops `www` ficam em uma classe, `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali`; ambas as ops `mex` em `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`. O namespace/schema das ops `www` é `whatsapp-android-www`; das ops `mex`, `whatsapp-android-mex`. `OrgDirectory`/`OrgList`/`OrgMemberSearch` já existiam antes da 2.26.45.10 (primeiro capturados contra a 2.26.41.6); seus doc_ids rotacionaram entre as duas builds (mesma classe, mesmos nomes de campo) — as outras 7 são novas na 2.26.45.10.

Operações de busca de suporte existem um pacote adiante, `com/whatsapp/work/publicidentity/` — não parte do próprio fluxo de entrada, mas a forma como o cliente de um contato descobre que alguém pertence a uma org antes mesmo de qualquer convite estar envolvido:

| Op | Transporte | doc_id | Variáveis | Propósito |
|---|---|---|---|---|
| `WorkPublicContactInfoQuery` | www | `29154186964216430` | `lids` (lista) | status de trabalho/conta business por contato, em lote (`CoalescingBatcher`, com debounce, máx. 100 chaves/rodada) |
| `WorkPublicOrgInfoQuery` | www | `28899689926378846` | `ids` (lista, ids de org) | info pública de org (`id`, `name`, 2 outros campos string opacos — `inferred`: logo/domínio) para orgs às quais um contato pertence |

---

## 3. Fluxo de entrada de ponta a ponta

Ordenação **inferred**, montada a partir dos nomes de campo de estado de `OrgJoinViewModel` (nenhuma sequência de chamada única rastreada cobre isso de ponta a ponta):

### 3.1 Entrada

O convite chega como um link token, seja por um referrer/deep-link (`OrgInviteReferrerOpener`, literal `org_invite_token_from_referrer` → se torna `link_token`) ou aberto diretamente (`OrgInviteLandingActivity`, com estados de falha `org_invite_landing_failure` / `org_invite_landing_already_in_org`).

### 3.2 Pré-visualização

`OrgInvitePreview(link_token)` retorna o suficiente para popular `org_name`, `org_member_count`, `org_icon_url`/`org_icon_handle`/`org_icon_full_url`, `org_description` antes que o usuário se comprometa com qualquer coisa.

### 3.3 Verificação de nome de exibição

`OrgJoinActivity`/`OrgJoinViewModel` coleta `display_name` (+ `display_last_name` opcional) e uma seleção de equipe (`team`/`team_options`/`selected_team`). `OrgCheckDisplayName(display_name)` é o gate de política/disponibilidade; em caso de rejeição, a continuação aninhada `OrgJoinViewModel$checkName$2` define `name_refusal` e/ou `last_name_refused` de forma independente — primeiro nome e sobrenome podem cada um ser rejeitados isoladamente.

### 3.4 Elegibilidade de email e OTP

`OrgCheckEmailEligibility(link_token, email)` verifica se um determinado email pode ser usado para este convite específico. `OrgSendEmailCode(email)` (mex) então envia o OTP; depois que o usuário o digita, `OrgVerifyEmailCode(email, code)` (mex) o verifica. A verificação pode exibir `username_pending_email` / `rejoin_after_username` / `username_screen_open` — a entrada pode ficar bloqueada atrás da própria configuração de username da conta principal, uma dependência do sistema do `WA_USERNAME.md` que de outra forma não tem relação com orgs.

### 3.5 Entrada

`OrgJoin(link_token, email, org_display_name, member_tag, org_display_last_name)` é a submissão final. O sucesso define `joined=true` e popula os campos da org (`org_id`, `org_name`, `org_member_count`, `org_icon_*`, `org_description`) no estado local.

### 3.6 Pós-entrada

`OrgDirectory(org_id, relationship="CONTACT", first, after)` busca o diretório de membros; `OrgMemberSearch(query, org_id, first, after)` busca dentro dele. `OrgLeaveMutation(org_id)` sai, em qualquer momento após entrar.

```
[Invite link / referrer]
  │ OrgInviteReferrerOpener: org_invite_token_from_referrer -> link_token
  │ (or OrgInviteLandingActivity: org_invite_landing_failure / _already_in_org)
  ▼
[OrgInvitePreview(link_token)]
  │  org_name, org_member_count, org_icon_*, org_description
  ▼
[OrgJoinActivity / OrgJoinViewModel]
  │  org_join_offline, step, team/team_options/selected_team, display_name, display_last_name
  ▼
[OrgCheckDisplayName(display_name)]
  │  -> name_refusal / last_name_refused on rejection
  ▼
[OrgCheckEmailEligibility(link_token, email)]
  ▼
[OrgSendEmailCode(email)]           -- mex, OTP send
  ▼
[user enters code]
  ▼
[OrgVerifyEmailCode(email, code)]   -- mex, OTP verify
  │  -> username_pending_email / rejoin_after_username / username_screen_open
  ▼
[OrgJoin(link_token, email, org_display_name, member_tag, org_display_last_name)]
  │  -> joined=true, org_id/org_name/org_member_count/org_icon_*/org_description populated
  ▼
[OrgDirectory(org_id, relationship="CONTACT", first, after)]
[OrgMemberSearch(query, org_id, first, after)]
[OrgLeaveMutation(org_id)]
```

---

## 4. Distinções importantes — não confundir

Existem três conceitos de "estrutura de conta" não relacionados dentro/em torno deste cliente. Eles não compartilham código, proto, nem espaço de doc_id.

| | Contas Org (este relatório) | Managed Account (`WA_MANAGED_ACCOUNT.md`) | Delegação de Business API (BSP/Cloud API) |
|---|---|---|---|
| Identidade da entidade | `org_id`, diretório próprio | `ManagedAccountConnection`, indexado por `connectionLid`/`connectionPnJid` | campos de certificado de nome verificado (`host_storage`/`actual_actors`), nenhum novo id de entidade |
| Relação | entrada voluntária via link de convite, N membros por org | um patrocinador ↔ um dependente, um vínculo de supervisão | um número business operado pela Meta/um provedor via Cloud API |
| Onboarding | link de convite + OTP por email + verificação de disponibilidade de nome de exibição | deep link + vinculação iniciada pelo patrocinador (`ManagedAccountInitiateLinkingQuery` etc.) | provisionamento do lado do servidor na plataforma business da Meta; invisível para este cliente além de marcadores resultantes |
| Local no código | `com.whatsapp.orgs.*` | `com.whatsapp.managedaccount.*` / `pma.*` / `pmta.*` | nenhum pacote dedicado; sinalizado via campos de certificado `w:biz` e tipo de conta `HOSTED` multi-dispositivo |
| Transporte | GraphQL `whatsapp-android-www` + `whatsapp-android-mex` (OTP) | apenas `whatsapp-android-mex` | campos de stanza `w:biz`, nem sequer um protocolo de entrada/convite |
| Saída/desvinculação | `OrgLeaveMutation(org_id)` | `ManagedAccountRevokeLinkingMutation` | não aplicável — sem entrada/saída por conta; o próprio número é provisionado/desprovisionado do lado do servidor |
| Conceito de diretório | sim — `OrgDirectory`/`OrgMemberSearch`, delimitado por relação | não | não |

Nenhum dos três é uma renomeação ou evolução do outro: uma conta org não tem semântica de supervisão (sem estado de idade/graduação, sem PIN de patrocinador) e nenhuma semântica de certificado business (sem `host_storage`/`actual_actors`, sem verificação de prefixo de emissor); é um modelo simples e voluntário de membresia-com-diretório sobreposto a uma conta WhatsApp já registrada. A conclusão de nomenclatura de produto ("recurso próprio do WhatsApp de organizações para empresas/instituições") é **inferred** apenas a partir do formato dos campos (`org_id` + diretório de membros + verificação de disponibilidade de nome de exibição + verificação de domínio de email) — nenhum texto de marketing ou do próprio cliente foi lido nomeando o recurso.

---

## 5. Casos de erro

Nenhuma tabela de códigos de erro pôde ser construída a partir dos pontos de chamada desta build — nenhum literal de formato de resposta (nomes de campo de sucesso/falha, códigos de erro numéricos) foi encontrado para nenhuma das 9 ops nesta passagem. Os únicos sinais de rejeição lidos são os dois campos de estado booleanos em `OrgJoinViewModel$checkName$2`:

| Sintoma | Causa | Evidência |
|---|---|---|
| Nome de exibição rejeitado | falha de política/disponibilidade de `OrgCheckDisplayName` | `name_refusal` definido (found, campo de estado) |
| Sobrenome rejeitado independentemente do primeiro nome | mesma verificação, ramo específico de sobrenome | `last_name_refused` definido (found, campo de estado) |
| Entrada bloqueada pendente de configuração de username | sucesso de `OrgVerifyEmailCode` depende do próprio estado de username da conta | `username_pending_email`/`rejoin_after_username`/`username_screen_open` (found, campos de estado; condição exata do servidor `unknown`) |
| Convite aberto enquanto já é membro | curto-circuito da landing page | `org_invite_landing_already_in_org` (found, literal string) |
| Link de convite inválido/expirado | falha genérica de landing | `org_invite_landing_failure` (found, literal string; nenhum sub-motivo distinto encontrado) |

---

## 6. Notas de implementação Baileys / velowa

Todas as 9 ops são chamadas padrão de GraphQL/MEX de doc_id persistido nos mesmos namespaces `whatsapp-android-www`/`whatsapp-android-mex` que a velowa já implementa para outros recursos (username, grupos) — nenhum transporte novo, nenhuma camada de criptografia nativa específica para orgs foi encontrada.

| Pronto para o wire | Não pronto para o wire |
|---|---|
| Os 9 nomes de op + doc_ids + chaves de variáveis (seção 2) — suficiente para montar uma requisição | Nomes de campo de resposta são unknown para toda op exceto os quatro explicitamente lidos no estado de `OrgJoinViewModel` (seção 1); um cliente deve tratar todas as respostas como JSON opaco até que uma captura em produção confirme os formatos |
| Caminho de propagação de `link_token` (referrer → preview → join) | Controle exato dos passos — se o servidor impõe a ordenação da seção 3, ou se, por exemplo, `OrgCheckDisplayName`/`OrgCheckEmailEligibility` podem ser pulados — é `inferred`, não confirmado |
| Formato de paginação de `OrgDirectory`/`OrgMemberSearch` (`first`/`after`, padrão de cursor padrão) | Enum `relationship`: apenas `"CONTACT"` está confirmado; outros valores possíveis são `unknown`, então um cliente não deve assumir que é o único filtro válido |
| `OrgLeaveMutation(org_id)` — mutation de campo único, trivial de implementar | As variáveis de `OrgList` por completo (nenhum ponto de chamada encontrado — provavelmente envia `{}`, não confirmado) |
| `WorkPublicContactInfoQuery`/`WorkPublicOrgInfoQuery` para buscas somente leitura de "este contato está em uma org", independentes do fluxo de entrada | O próprio formato de URL/deep-link do link de convite (host, caminho, codificação do token) — não capturado nesta passagem |

Uma implementação velowa tentando este fluxo deveria esperar descobrir os formatos de resposta empiricamente contra uma conta em produção, a mesma ressalva já carregada pelos outros relatórios de transporte `inferred` deste repositório (ex. `WA_USERNAME.md`).

---

## 7. Incertezas

| Tópico | Motivo |
|---|---|
| Variáveis de `OrgList` | nenhum ponto de chamada estático encontrado além do doc_id + rotação; provavelmente `{}` mas não confirmado |
| Valores do enum `relationship` além de `"CONTACT"` | apenas um mapeamento ordinal→string observado (ordinal 0 → `"CONTACT"`); outros ramos não cobertos nesta passagem |
| Formatos de campo de resposta para todas as 9 ops | nenhum literal/nome de campo do lado da resposta encontrado em nenhum ponto de chamada; tudo além dos campos de estado de `OrgJoinViewModel` é opaco |
| Semântica de vida útil/uso único de `link_token` | não rastreada; assumida como uso único apenas pela convenção de nomenclatura |
| Imposição do lado do servidor da ordenação de passos da seção 3 | montada a partir do formato dos campos de estado, não de uma cadeia de chamada sequencial rastreada — um cliente pode conseguir reordenar ou pular passos; não testado |
| Conjuntos de valores de `member_tag`/`team` | os campos existem (`team_options`, `member_tag`) mas nenhum valor enumerado foi encontrado |
| Formato de URL do link de convite | não capturado nesta passagem |

---

## 8. Evidência

Análise estática do smali do WhatsApp Android 2.26.45.10, todos os literais e chaves de variáveis lidos como `const-string` imediatamente antes de sua chamada setter `GraphQlCallInput`/`LX/0jN`. Nenhum tráfego foi interceptado; todas as afirmações sobre transporte/formato de resposta são `inferred`. Fonte: `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali`, `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`, `com/whatsapp/orgs/ui/join/OrgJoinActivity.smali`, `OrgJoinViewModel.smali`, `OrgJoinViewModel$checkName$2.smali`, `com/whatsapp/orgs/ui/invite/OrgInviteReferrerOpener.smali`, `com/whatsapp/orgs/ui/invite/OrgInviteLandingActivity.smali`, `com/whatsapp/work/publicidentity/graphql/MexWorkIdentityTransport.smali`.
