<!-- src-sha1: 900bf74a45a7fabc6e7b8c42ef4df8074e676084 -->
# WhatsApp Grupos e Comunidades — Full RE Report
**Versão:** 2.26.41.6 (superfície de wire de aprovação de membresia/entrada verificada adicionalmente na 2.26.45.10, anotado inline) | **Data:** 2026-11-15
**Escopo:** Modelo estrutural de grupo vs. comunidade (grupo pai, subgrupos vinculados, subgrupo padrão, chat geral), endereçamento JID, superfície de wire legada `w:g2`/`w:gp2`, catálogo de operações GraphQL de grupo/comunidade do `whatsapp-android-mex`, fluxos de criação/convite/ação administrativa, links de convite, e aprovação de entrada em comunidade (`QueryMembershipApprovalRequests`, `GroupMembershipRequestUpdate`, o fallback legado `w:g2`, e a operação de submissão `JoinMembershipForm` inferida).

---

## 1. O que é

Uma **comunidade** do WhatsApp não é uma entidade endereçável distinta. É um **grupo** — mesmo espaço de JID, mesmo parser de nó `<group>`, mesma tabela `wa_group_admin_settings` — que desempenha o papel de **grupo pai** para um conjunto de **subgrupos vinculados**. Este relatório reúne o modelo de grupo/comunidade que de outra forma está espalhado por [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2 (classificação, endereçamento), [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) (tabelas do BD), [WA_REPORTING.md](WA_REPORTING.md) (a superfície `w:g2` de denúncia para admin) e [WA_POLLS.md](WA_POLLS.md) (variante de enquete do subgrupo padrão), e adiciona o catálogo de operações MEX de grupo/comunidade e a descoberta de aprovação de entrada em comunidade na 2.26.45.10.

### 1.1 Entidades

| Entidade | Endereçamento | Relação | Tier |
|--------|-----------|----------|------|
| Grupo | próprio JID `@g.us` | — | found |
| Comunidade | **mesmo** espaço de JID `@g.us` de um grupo; classificada, não tipada separadamente | é um grupo agindo como pai | found |
| Grupo pai | nó `<group>` tipo **1** (filho `parent` presente) | topo de uma comunidade | found |
| Subgrupo vinculado | nó `<group>` tipo **2** (filho `linked_parent jid`) | `linked_parent jid` aponta para o JID do pai | found |
| Subgrupo padrão | nó `<group>` tipo **3** (filho `default_sub_group`) | subgrupo auto-criado de uma comunidade; `group_type` **3** localmente, também o gatilho para `pollCreationMessageV2` (WA_POLLS §1) | found |
| Chat geral | nó `<group>` tipo **6** (filho `general_chat`) | chat estilo anúncio para toda a comunidade | found |
| Grupo normal | nó `<group>` tipo **0** | sem relação de comunidade | found |

Classificação e extração do JID pai: `C23201A1a.A01` (tipos 0/1/2/3/6 acima), `C23201A1a.A03` (lê o JID pai de `linked_parent jid`) — ambos `found` em [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.3, re-citados aqui em vez de re-derivados. `membership_approval_mode` de um subgrupo tem como padrão `parent/default_membership_approval_mode="request_required"`.

---

## 2. Modelo de endereçamento e participantes

Condensado de [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.1–2.2 (detalhe completo lá; campos específicos de histórico de grupo omitidos aqui):

- Nó `<group>`, caminho legado `C23201A1a.A0C` (compartilhado com notificações de grupo); existe um gêmeo MEX/SMAX (`AbstractC23204A1d`, `AN6`, `C23690AKd`).
- Atributos principais: `id`, `creation`, `subject`, `s_t`/`s_o`/`s_o_pn`, `creator`/`creator_pn` (os gêmeos `_pn` carregam o JID de telefone ao lado de um LID).
- `addressing_mode` (`lid` / `pn`) — armazenado em `wa_group_admin_settings.addressing_mode`; qualquer coisa diferente de `pn` é lida como `lid`.
- `<participant jid lid phone_number type display_name username join_time group_history_sent>` (`C23201A1a.A05`, `C23205A1e.A0J`). `type` é o atributo de papel por grupo que fica por trás do status de admin; `jid`/`lid`/`phone_number` carregam as duas formas de endereço dependendo de `addressing_mode`.

Não existe nenhuma chave separada estilo `community_jid` ou `newsletter_jid` em nenhum lugar do cliente — confirmado com evidência de código fresca em §11.3 abaixo, consistente com o modelo "comunidade é um grupo" do §1.

---

## 3. Protocolo de wire legado (`w:g2` / `w:gp2`)

Operações de grupo pré-MEX ainda rodam como IQs XMPP binários sob o namespace `w:g2`; `w:gp2` está listado como uma das variantes de push-stanza `notification` (inventários de namespace `Protocols/xml-stanzas`, `Protocols/xmpp-namespaces-android`, `found`). Exemplo concreto, recuperado estruturalmente (`found`, `WASmaxGroupsGetGroupInfoRPC`):

```
iq[id=<stanzaId>, to=<groupJid>, type="get", xmlns="w:g2"]
  query[request=<string>, phash=<string?>]
    add_request[admin=<userJid>, code=<string>, expiration=<int>]   (optional, min=0 max=1)
```

Variantes de resposta: `ClientError` / `ServerError` / `Success` (metadados completos do grupo: participantes, assunto, criação, descrição, configurações efêmeras). O mesmo namespace carrega operações de grupo não relacionadas documentadas em outro lugar deste repositório e não repetidas aqui:

- Denúncia para admin (`<iq to=groupJid type=set xmlns=w:g2><reports><report message_id=.../></reports></iq>`) e o toggle de denúncias ao admin (`allow_admin_reports`/`not_allow_admin_reports`) — [WA_REPORTING.md](WA_REPORTING.md) §9.
- O fallback legado de solicitações de aprovação de membresia — §11.2 abaixo.

---

## 4. Superfície GraphQL MEX

Catálogo de persisted-queries `whatsapp-android-mex`, `found in` o asset `whatsapp-android-mex_client_persist_ids.json` embarcado. Os valores de `doc_id` rotacionam a cada build do APK (95 rotações registradas entre 2.26.41.6 e 2.26.45.10, `Querys/graphql-diff-2.26.41.6-to-2.26.45.10.md` no brain) — as tabelas abaixo são o snapshot da 2.26.41.6.

### 4.1 Operações de grupo (21)

| Operação | doc_id (2.26.41.6) | Tipo |
|---|---|---|
| `AddParticipantsToGroupV2` | `28425601030437902` | Mutation |
| `AddParticipantsToGroupsV3` | `26857242513977310` | Mutation |
| `AddParticipantsToInteropGroup` | `25732168276369451` | Mutation |
| `AllowNonAdminGroupCreation` | `32024438593867697` | Query |
| `CreateGroup` | `38588807217433890` | Mutation |
| `GetPreRegGroupAddRequestsQuery` | `25018599251091282` | Query |
| `GroupMembershipRequestUpdate` | `29469157542702726` | Mutation |
| `GroupsCreateInteropGroup` | `25726817620301611` | Mutation |
| `GroupsStoreAndSendInvitesSMSMutation` | `27018112604523582` | Mutation |
| `GroupsStoreInvitesSMSMutation` | `25508574885415377` | Mutation |
| `JoinMembershipForm` | `28997137096573014` (new in 2.26.45.10 catalog only) | unknown |
| `LeaveInteropGroup` | `25346167795013271` | Query |
| `QueryBatchGetGroups` | `28340966318889583` | Query |
| `QueryGroupInfo` | `38342717635376065` | Query |
| `QueryGroupInfoByCode` | `27616410928049563` | Query |
| `QueryInteropGroupInfo` | `32734144032867938` | Query |
| `QueryLinkedGroupInfo` | `28221051120830416` | Query |
| `QueryMembershipApprovalRequests` | `28845604101745223` | Query |
| `QueryParticipatingGroups` | `28394594513526802` | Query |
| `QuerySuggestedGroups` | `26012055225051917` | Query |
| `SetGroupProperty` | `24688994337458819` | Mutation |
| `SetGroupResetInviteLink` | `24812851838367451` | Mutation |

### 4.2 Operações de comunidade (4)

| Operação | doc_id (2.26.41.6) | Tipo |
|---|---|---|
| `QueryCommunityParticipantCount` | `31981537024824321` | Query |
| `QuerySubgroupParticipantCount` | `24784259781196779` | Query |
| `QuerySubgroups` | `25554052094203120` | Query |
| `UpdateCommunityOwner` | `24781435194845316` | Mutation |

Não existe nenhuma operação com o nome `CreateCommunity` neste catálogo — `unknown` se a criação de comunidade é um wizard local no cliente que encadeia `CreateGroup` + chamadas de vinculação, ou uma promoção implícita do lado do servidor de um grupo a pai; não resolvido nesta passagem.

### 4.3 Variáveis recuperadas dos pontos de chamada do APK (`found`)

| Operação | Variáveis | Ponto de chamada |
|---|---|---|
| `CreateGroup` | `participants`, `subject`, `expiration_time_in_sec`, `trigger`, `member_add_mode`, `member_link_mode`, `member_share_group_history_mode`, `username`, `user_lid` | `X/C36500G6k.java` |
| `AddParticipantsToGroupV2` | `mode`, `user_lid`, `username`, `group_id`, `participants`, `add_participants_metadata`, `input` | `X/C08600aH.java` |
| `AddParticipantsToGroupsV3` | `mode`, `group_ids`, `participants`, `tctoken`, `privacy_token`, `add_participants_metadata` | `X/RunnableC24380AnV.java` |
| `QueryGroupInfo` | `group_jid`, `query_context`, `input` | `X/C08630aK.java` |
| `QueryGroupInfoByCode` | `invite_code`, `query_context`, `get`, `input` | `X/C08600aH.java` |
| `QueryLinkedGroupInfo` | `group_jid`, `sub_group_jid_hint`, `query_context`, `input` | `X/JOF.java` |
| `QueryBatchGetGroups` | `group_jid`, `query_context`, `groups`, `request_context` | `X/FGG.java` |
| `QueryParticipatingGroups` | `input` | `X/C16710ou.java` |
| `SetGroupProperty` | ver §9 | `X/A18.java`, `X/A19.java` |
| `SetGroupResetInviteLink` | `group_id`, `query_context`, `group_input`, `group_jid`, `max_use`, `seconds_for_expiry` | `X/C54392a5.java` |
| `AllowNonAdminGroupCreation` | `allow_non_admin_sub_group_creation` (bool) | `com/whatsapp/community/mex/AllowNonAdminSubGroupCreationGraphQlHandler.java` |
| `QuerySuggestedGroups` | `group_input` | `com/whatsapp/community/mex/GetSuggestedGroupsGraphQlHandler.java` |
| `QuerySubgroups` | `group_input` | `com/whatsapp/community/mex/GetSubgroupsGraphQlHandler.java` |
| `UpdateCommunityOwner` | `new_role`, `group_id`, `role_updates`, `user_jid` | `com/whatsapp/community/mex/TransferCommunityOwnershipGraphQlHandler.java` |
| `GroupsStoreAndSendInvitesSMSMutation` | `server_sent_sms`, `participants`, `entry_point`, `is_bundle_invite`, `participant`, `group_jid` | `com/whatsapp/invite/api/ServerSentGroupInviteMutationHelper.java`, `com/whatsapp/invite/ui/SMSPreviewGroupInviteBottomSheetFragment.java` |
| `GroupsStoreInvitesSMSMutation` | `partcipants` (sic), `group_jid` | `X/C67052zD.java` |
| `AddParticipantsToInteropGroup` | `gid`, `participants`, `jid`, `input` | `X/C3ZT.java` |
| `QueryInteropGroupInfo` | `gid`, `group_input` | `X/C3ZT.java` |

O restante (`GetPreRegGroupAddRequestsQuery`, `GroupsCreateInteropGroup`, `LeaveInteropGroup`, `QueryCommunityParticipantCount`, `QuerySubgroupParticipantCount`) não tem ponto de chamada estático recuperado: `unknown`, provavelmente enviando `{}`.

---

## 5. Criando um grupo

`CreateGroup` (§4.3) define `member_add_mode`, `member_link_mode`, `member_share_group_history_mode` no momento da criação — as mesmas três propriedades administrativas que `SetGroupProperty` edita depois (§9). `trigger` é uma tag string de ponto de entrada (`found`, conjunto exato de valores não enumerado nesta passagem).

---

## 6. Links de convite e convites

| Item | Detalhe | Tier |
|------|--------|------|
| Resetar/criar link de convite | `SetGroupResetInviteLink`: `group_id`, `group_jid`, `max_use`, `seconds_for_expiry` | found |
| Resolver um código de convite | `QueryGroupInfoByCode`: `invite_code` -> info do grupo | found |
| Convite por SMS (lote) | `GroupsStoreAndSendInvitesSMSMutation`: `participants`, `entry_point`, `is_bundle_invite`, `server_sent_sms` | found |
| Convite por SMS (apenas armazenar) | `GroupsStoreInvitesSMSMutation`: `group_jid`, participants | found |
| Lista de permissão/bloqueio | BD `wa_group_add_allow_list`, `wa_group_add_black_list` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) | found |
| Convites não-WhatsApp | BD `group_non_wa_invites` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) | found |

### 6.1 Forma de wire `groupInviteMessage`

`Message.groupInviteMessage`, campo **28**, tipo aninhado `Message.GroupInviteMessage` (encontrado em WAProto.proto):

| Campo | # | Tipo |
|-------|---|------|
| `groupJid` | 1 | string |
| `inviteCode` | 2 | string |
| `inviteExpiration` | 3 | int64 |
| `groupName` | 4 | string |
| `jpegThumbnail` | 5 | bytes |
| `caption` | 6 | string |
| `contextInfo` | 7 | ContextInfo |
| `groupType` | 8 | enum `GroupType` |

`GroupType`: `DEFAULT` = 0, `PARENT` = 1 — a própria mensagem de convite distingue um convite de grupo comum de um convite de comunidade (grupo pai), consistente com o modelo "comunidade é um grupo classificado" do §1. Existe um segundo tipo `GroupInviteMessage` de nível superior, não relacionado, em outro lugar no mesmo arquivo proto; esta tabela cobre apenas o `Message.GroupInviteMessage` aninhado usado pelo campo 28.

---

## 7. Participantes: adicionar, sugerir, enumerar

| Operação | Propósito (inferido do nome + variáveis) |
|---|---|
| `AddParticipantsToGroupV2` / `V3` | adicionar um ou mais usuários a um ou mais grupos |
| `QueryParticipatingGroups` | listar grupos nos quais o chamador está |
| `QueryBatchGetGroups` | busca de metadados em lote para um conjunto de JIDs de grupo |
| `QuerySuggestedGroups` | superfície de sugestões de comunidade/grupo; BD `member_suggested_groups_v2` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) |
| `QuerySubgroups` / `QuerySubgroupParticipantCount` / `QueryCommunityParticipantCount` | contagens em nível de comunidade sobre os subgrupos vinculados |

O atributo `<participant type=...>` (§2) carrega a flag de admin/papel por grupo, e `group_participant_user.rank` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §3.6) a persiste localmente — então o rank de admin existe como conceito, mas nenhuma operação MEX explícita de promover/rebaixar ou remover-participante foi encontrada neste catálogo (as 21/4 ops de grupo/comunidade acima são exaustivas para a 2.26.41.6). **Unknown**: se esse caminho ainda roda puramente como um IQ legado `w:g2` de lista de participantes (consistente com o próprio nome de `AddParticipantsToGroupV2` implicando a existência de um predecessor V1) ou sob algum nome de operação fora dos grupos de substring `group`/`community`; não resolvido nesta passagem.

---

## 8. Grupos interop (breve)

`AddParticipantsToInteropGroup`, `GroupsCreateInteropGroup`, `QueryInteropGroupInfo`, `LeaveInteropGroup` — um conjunto paralelo pequeno de operações de grupo para grupos em ponte ("interop") de terceiros. Fora do escopo aqui além de listá-los; ver [WA_INTEROP.md](WA_INTEROP.md) para o modelo de consentimento/ponte interop no qual se encaixam.

---

## 9. Configurações de admin — `SetGroupProperty`

**Variáveis** (`found`, `X/A18.java`, `X/A19.java`):

| Campo | Tipo | Significado | Tier |
|-------|------|---------|------|
| `group_id` | str | grupo alvo | found |
| `subject` | str | nome do grupo | found |
| `description` | str | descrição do grupo | found |
| `previous_id` | str | marcador de concorrência otimista / valor anterior (inferido) | inferred |
| `member_add_mode` | str | quem pode adicionar membros (`all_member_add` / outro, reflete o filho legado `<member_add_mode>`, [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.1) | found |
| `member_link_mode` | str | modo de permissão de link de convite (inferido do nome) | inferred |
| `member_share_group_history_mode` | str | `ADMIN_SHARE` / `ALL_MEMBER_SHARE`, enum completo e mapeamento de mensagem de sistema em [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.4 — não repetido aqui | found |
| `membership_approval_mode_enabled` | bool | ativa/desativa o controle de solicitação de entrada para este grupo — ver §11 | found |
| `limit_sharing`, `limit_sharing_enabled`, `limit_sharing_trigger` | str/bool/str | toggle de limite de encaminhamento para este grupo (inferido: restrição de encaminhamento "limit sharing") | inferred |
| `input` | str | objeto wrapper/contexto (formato não resolvido) | unknown |

A contraparte de notificação do lado do servidor e a lista completa de colunas de `wa_group_admin_settings` (`restrict_mode`, `announcement_group`, `no_frequently_forwarded`, `ephemeral_duration`, `require_membership_approval`, `addressing_mode`, `allow_member_labels`, …) estão em [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4 — referenciadas, não duplicadas.

---

## 10. Estrutura específica de comunidade

| Item | Detalhe | Tier |
|------|--------|------|
| Enumeração de subgrupos | `QuerySubgroups` (`group_input`) | found |
| Contagens de subgrupo/comunidade | `QuerySubgroupParticipantCount`, `QueryCommunityParticipantCount` | found (ops existem), unknown (variáveis) |
| Busca de grupo vinculado | `QueryLinkedGroupInfo` (`group_jid`, `sub_group_jid_hint`) — resolve um subgrupo dado seu pai | found |
| Transferência de propriedade | `UpdateCommunityOwner` (`new_role`, `group_id`, `role_updates`, `user_jid`) | found |
| Toggle de criação de subgrupo não-admin | `AllowNonAdminGroupCreation` (`allow_non_admin_sub_group_creation` bool) | found |
| Variante de enquete do subgrupo padrão | `pollCreationMessageV2` é o slot de enquete usado quando o chat é um subgrupo padrão (`group_type == 3`) — [WA_POLLS.md](WA_POLLS.md) §1, §3.3 | found |
| Tabelas do BD | `subgroup_info`, `community_settings`, `group_relationship` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4) | found |

---

## 11. Aprovação de membresia e aprovação de entrada em comunidade

### 11.1 Grupos: controle de solicitação de entrada

`membership_approval_mode_enabled` (`SetGroupProperty`, §9) ativa a entrada controlada por admin para um grupo; `wa_group_admin_settings.require_membership_approval` é a flag persistida ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4). Para um **subgrupo** de uma comunidade, o padrão vem do pai: `parent/default_membership_approval_mode="request_required"` (§1.1, `C23201A1a`). O armazenamento de solicitações pendentes é dividido por quem pode aprovar: `group_membership_approval_requests` (visível ao admin) e `non_admin_group_membership_approval_requests`; `group_membership_form_questions` guarda perguntas configuradas pelo admin que quem entra deve responder, e `group_membership_count` rastreia contagens agregadas (todos `found`, [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4). `group_membership_form_questions` é a evidência concreta do lado do cliente de que existe um fluxo de formulário de membresia — diretamente relevante para o `JoinMembershipForm` abaixo.

### 11.2 Superfície de wire: caminho primário MEX + fallback legado

`com/whatsapp/group/data/GroupFetchAllMembershipApprovalRequestsJob` (`found`, smali da 2.26.45.10) implementa "buscar solicitações de entrada pendentes aguardando aprovação do admin" para um `groupJidRawString`, controlado em runtime por `LX/00E;->A0G(LX/00E;LX/00g;)Z` contra o flag id `LX/4WC;->A04` (lido via `LX/00U;->A03(0x10d4)`):

| Caminho | Condição | Mecanismo |
|------|-----------|-----------|
| MEX | flag ativa | `GraphQlCallInput` com `query_context="INTERACTIVE"` e o `GroupJid` alvo, operação **`QueryMembershipApprovalRequests`** no namespace `whatsapp-android-mex` |
| IQ binário legado | flag desativada (fallback `LX/0RD`) | `<iq type="get" xmlns="w:g2" to="<group_jid>" id="..."><membership_approval_requests/></iq>` |

O `doc_id` de `QueryMembershipApprovalRequests` rotaciona normalmente entre builds: `28845604101745223` (2.26.41.6) → `28584744077887639` (2.26.45.10). A mutation de aprovar/negar do admin, `GroupMembershipRequestUpdate`, é a contraparte (`29469157542702726` → `28746221238391491`, mesmo padrão de rotação normal); seu ponto de chamada não foi rastreado nesta passagem, mas é a única mutation de membresia de grupo do lado do admin no catálogo (§4.1).

`JoinMembershipForm` (doc_id `28997137096573014`) é genuinamente novo no catálogo da 2.26.45.10 — ausente na 2.26.41.6, não uma rotação de uma operação existente. Seu nome, combinado com a tabela `group_membership_form_questions` (§11.1), o torna o melhor candidato para a mutation do lado de submissão "responder às perguntas do formulário de membresia do admin e solicitar entrada" — mas seu ponto de chamada não foi rastreado nesta passagem. **Inferred**, não found, para seu papel exato e esquema.

### 11.3 Aprovação de entrada em comunidade especificamente (2.26.45.10, found)

Novo pacote `com/whatsapp/community/product/joinapproval/`, uma classe: `CommunityJoinApprovalNuxBottomSheet` — uma folha explicativa de UI local ("você vai precisar de aprovação do admin para entrar nesta comunidade"), não um ponto de chamada de rede em si.

- Construída por `LX/3IN;->C3f` com argumentos de bundle `"group_jid"` (o próprio JID da comunidade, lido como uma string de JID de grupo bruta) e `"community_name"`.
- Handler do botão primário `LX/3Ge;->C3f`, `pswitch_28`: lê o `GroupJid` armazenado, chama `LX/122;->A01(Context, GroupJid, Integer)Intent`, inicia via `LX/0KC;->A02`, dispensa a folha.

**Descoberta principal:** a comunidade é endereçada por `group_jid`, não por uma chave distinta estilo `community_jid`/`newsletter_jid` — confirmação direta de código, não apenas convenção de nomenclatura, do modelo "comunidade é um grupo" do §1/§2. Não existe nenhuma operação estilo `Community*ApprovalRequests` em nenhum lugar do catálogo; as solicitações de entrada pendentes de uma comunidade viajam exatamente pelo mesmo par MEX `QueryMembershipApprovalRequests` / `GroupMembershipRequestUpdate` (e o mesmo fallback legado `w:g2`) que um grupo comum usa, porque o job de aprovação de membresia só vê um `groupJidRawString`.

### 11.4 Veredito

| Alegação | Tier |
|-------|------|
| Comunidade endereçada por `group_jid`, mesmo caminho de código dos grupos | found |
| Listar solicitações pendentes: MEX `QueryMembershipApprovalRequests` | found |
| Aprovar/negar: MEX `GroupMembershipRequestUpdate` | found (op existe, catalogada); ponto de chamada não rastreado |
| Fallback legado: `<iq xmlns="w:g2"><membership_approval_requests/></iq>` | found |
| Feature gate selecionando MEX vs. legado | found (flag id, não seu estado de rollout atual) |
| Lado de submissão é `JoinMembershipForm` | inferred |
| Esquema/variáveis exatos de `JoinMembershipForm` | unknown |
| Lógica de aceitação/validação do lado do servidor | unknown (apenas análise estática, sem captura de tráfego) |

---

## 12. Referência cruzada de armazenamento local

As listas completas de colunas estão em [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md); esta é uma tabela de apontamento, não uma duplicata:

| Tabela | Papel |
|-------|------|
| `wa_group_admin_settings` | configurações de admin por grupo (modo de endereçamento, histórico, aprovação, limite de encaminhamento, ...) |
| `group_participant_user`, `group_past_participant_user`, `group_participant_device` | participantes atuais/passados, rank, estado de sender-key por dispositivo |
| `group_membership_approval_requests`, `non_admin_group_membership_approval_requests` | solicitações de entrada pendentes, divididas por visibilidade do aprovador |
| `group_membership_form_questions` | perguntas de formulário de membresia configuradas pelo admin (§11.1, §11.2) |
| `group_membership_count` | contagens agregadas |
| `subgroup_info`, `community_settings`, `group_relationship` | estrutura de comunidade/subgrupo |
| `member_suggested_groups_v2` | superfície de grupos sugeridos |
| `group_suspension_appeal` | estado de apelação de suspensão em nível de grupo |
| `group_non_wa_invites` | convites para contatos não-WhatsApp |
| `group_root_key_mapping` | mapeamento de raiz de sender-key |

---

## 13. Notas de implementação Baileys / velowa

Todas as ops MEX de grupo/comunidade usam o mesmo envelope IQ `w:mex` de toda outra persisted-query neste repositório (`Protocols/mex-graphql`, `graphql-invocation-guide.md`):

```js
const res = await sock.query({
  tag: 'iq', attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '<doc_id>' },
    content: Buffer.from(JSON.stringify({ queryId: '<doc_id>', variables })) }],
})
```

A busca de metadados/participantes de grupo legada permanece em `w:g2` e já está implementada pela maioria das bibliotecas WA Web (chamadas estilo `groupMetadata`, `groupQuery`); a aprovação de membresia precisa do IQ do §11.2 adicionado explicitamente — a maioria das bibliotecas não a consulta.

| Por que falha | Correção |
|---------------|-----|
| `doc_id` fixo para qualquer op de grupo/comunidade | `doc_id` rotaciona a cada build do APK (confirmado: 4 ops de grupo rotacionaram só entre 2.26.38.10 e 2.26.41.6); atualize a partir de uma extração de catálogo atual, não fixe |
| Assumir que aprovação de membresia é sempre `w:g2` legado | É controlado por feature flag; uma vez que a flag esteja ativa do lado do servidor para uma conta, solicitações pendentes só aparecem via MEX `QueryMembershipApprovalRequests` — implemente ambos os caminhos ou só MEX a partir de agora |
| Assumir que uma comunidade tem seu próprio tipo de JID | Não tem — endereçe-a com o próprio JID `@g.us` do grupo pai, igual a qualquer op de grupo |
| Tentar submeter programaticamente uma solicitação de entrada controlada | O esquema de `JoinMembershipForm` não está resolvido (apenas papel inferido); não implementável com confiança ainda |

---

## 14. Distinções importantes

- **Comunidade é um grupo classificado, não uma entidade separada.** Sem `community_jid`; o próprio JID da comunidade é um JID de grupo com nó tipo 1 (`parent`).
- **`member_share_group_history_mode`** (quem pode compartilhar histórico recente com novos membros, [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.4) não tem relação com **`membership_approval_mode_enabled`** (controle de solicitação de entrada, §9/§11) — ambos são campos de `SetGroupProperty` mas controlam funcionalidades diferentes.
- **Denúncia para admin via `w:g2`** ([WA_REPORTING.md](WA_REPORTING.md) §9) e **fallback de solicitações de aprovação de membresia via `w:g2`** (§11.2) compartilham um namespace mas são nós filhos não relacionados (`reports`/`allow_admin_reports` vs. `membership_approval_requests`).
- **`JoinMembershipForm`** é uma operação de submissão inferida, não confirmada — não a trate como found.
- **Promover/rebaixar/remover participante** não tem operação MEX identificada neste catálogo; trate como não resolvido, não como "roda só sobre `w:g2` legado" (suposição, não evidência).

---

## 15. Fluxo de aprovação de entrada em comunidade (como evidenciado atualmente)

```
[Member]                         [Client]                              [Server / whatsapp-android-mex]
   │ taps "Request to join"         │                                        │
   ├────────────────────────────────▶ CommunityJoinApprovalNuxBottomSheet    │
   │                                 │  (local explainer, group_jid+name)    │
   │ taps primary button             │                                        │
   ├────────────────────────────────▶ LX/3Ge;->C3f pswitch_28                │
   │                                 │  -> LX/122;->A01(ctx, GroupJid, int)  │
   │                                 │     Intent into group/community flow  │
   │                                 │  (submit side, inferred)              │
   │                                 ├───────────────────────────────────────▶ JoinMembershipForm (inferred)
   │                                 │                                        │
[Admin]                           [Client]                                 │
   │ opens pending-requests screen   │                                        │
   ├────────────────────────────────▶ GroupFetchAllMembershipApprovalRequestsJob
   │                                 │  flag on  ─▶ QueryMembershipApprovalRequests (MEX)
   │                                 │  flag off ─▶ <iq xmlns="w:g2"><membership_approval_requests/></iq>
   │                                 │                                        │
   │ approves / denies               │                                        │
   ├────────────────────────────────▶ GroupMembershipRequestUpdate (MEX) ────▶ server
```

---

## 16. Itens abertos / pegadinhas

- Variáveis/formato de resposta de `JoinMembershipForm`: unknown, não rastreado por ponto de chamada.
- Variáveis próprias de `GroupMembershipRequestUpdate`: não recuperadas de um ponto de chamada nesta passagem (apenas confirmado que a op existe).
- Promover/rebaixar/remover participante: nenhuma op MEX identificada; legado-apenas vs. ausente-do-catálogo não está resolvido.
- `CreateCommunity`: não existe tal op MEX; o caminho de criação de comunidade não está resolvido (encadeamento de wizard do cliente com `CreateGroup` + vinculação é a hipótese de trabalho, não confirmada).
- Todas as alegações em §11 além da existência da tabela do BD são análise estática; nada aqui foi testado em tráfego (conforme o contrato de evidência — nenhuma interação com servidor em produção foi realizada para este relatório).
