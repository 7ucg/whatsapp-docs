<!-- src-sha1: 42c77add3dafd5b90522b32d91692dff968b2f54 -->
# WhatsApp Canais & Newsletters — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-11-01
**Escopo:** domínio JID `@newsletter` e a nomenclatura interna "newsletter", seguir/deixar de seguir, criação de canal, papéis de admin e transferência, os seis campos de proto `newsletterAdmin*`/`newsletterFollower*`/`newsletterScheduledMessage`, metadados do canal (nome, descrição, foto, verificação, estado), reações em posts, contagem de visualizações/seguidores, fluxo de convite/revogação/aceite de admin, operações GraphQL/MEX de newsletter (doc_ids), armazenamento local, feature flags, casos de erro

---

## 1. O que é (tecnicamente)

Um "canal" é o nome voltado ao consumidor para o que o cliente chama internamente de **newsletter**: um JID de transmissão um-para-muitos com armazenamento server-side (sem E2E), um pequeno conjunto de papéis (owner/admin/subscriber/guest), e a maioria das operações de plano de controle trafegada via `w:mex` GraphQL em vez de IQs clássicos de XMPP. A entrega de conteúdo (busca de posts, busca de status, mensagens agendadas, assinatura de atualização em tempo real) ainda usa um namespace de IQ XMPP dedicado, `xmlns="newsletter"`. Todas as afirmações são análise estática do APK decompilado; nada foi capturado no tráfego. Camadas: **found** = lido no código, **inferred** = deduzido do código, **unknown** = não resolvido. Diferente da maioria dos reports obfuscados deste repositório, o pacote de newsletter visível ao cliente (`com.whatsapp.newsletter.*`, 122 arquivos) traz **nomes legíveis de classe e método** na 2.26.41.6; apenas a infraestrutura compartilhada (JID, proto de mensagem, construtores de IQ) é obfuscada e é re-resolvida aqui a partir de strings estáveis.

Fora do escopo: listas de transmissão clássicas e `status@broadcast` — ver [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md). Mecânica de busca de contato/dispositivo reutilizada por newsletters (não específica de newsletter) — ver [WA_USYNC.md](WA_USYNC.md).

| Entidade | Valor | Camada |
|--------|-------|------|
| Servidor JID | `newsletter` (ex.: `120363000000000000@newsletter`) | found |
| `Jid.getType()` | **21** | found |
| Criptografia | `EnumC14260eC.NON_E2EE` — o conteúdo do canal **não é criptografado ponta a ponta** | found |
| Classe de modelo local | `C2130898y` ("NewsletterInfo"), estende a linha genérica de chat `C14220e7` | found |
| Classe JID | `C1Y7` (`NewsletterJid`) | found |
| Link de convite | `https://whatsapp.com/channel/<invite_code>` | found |
| Tabela local do BD | `newsletter` (colunas incluem `membership`, `invite_code`, indexadas) | found |

| Componente | Nome na 2.26.41.6 | Papel |
|-----------|----------------|------|
| Parser de JID | `C0DL.A03` (switch em string do servidor), `C1Y7` (JID), `C1Y8` (companion/cache do JID) | valida id numérico, sem zero à esquerda, constrói/armazena em cache `C1Y7` |
| Predicados de JID | `C0DZ.A0a(jid)` = `getType()==21`; `C0DZ.A0M` inclui o tipo 21 no conjunto que também contém grupos (18), lista de transmissão (3), status (5) etc. | isNewsletter / conjunto com capacidade multi-destinatário |
| Modelo local | `C2130898y` | papel, verificação, mudo, configuração de reação, estado, contagens |
| Papéis | `C9U5` (enum local), `C9U4` (enum string de wire) | seção 4 |
| Job de metadados | `BaseMetadataNewsletterGraphqlJob`, `GetNewsletterAdminMetadataJob` | `NewsletterMetadata` / `NewsletterAdminMetadataQuery` |
| Job de atualização | `UpdateNewsletterGraphqlJob` | `NewsletterMetadataUpdate` |
| Job de criação/exclusão | sob `com.whatsapp.newsletter.editcreate`, `com.whatsapp.newsletter.delete` | `NewsletterCreate(Verified)` / `NewsletterDelete` |
| Busca de mensagens | `GetNewsletterMessagesJob`, `GetNewsletterMessagesUpdatesJob`, `GetNewsletterMyAddOnMessagesJob`, `SendNewsletterMessageJob`, `SendViewReceiptJob` | `com.whatsapp.newsletter.messages.job` |
| Busca de status (atualizações do canal) | `GetNewsletterStatusesJob`, `GetNewsletterStatusUpdatesJob`, `GetStatusMyAddOnsJob` | `com.whatsapp.newsletter.status.job` |
| Construtor de IQ | `C9EN` (construtores `xmlns="newsletter"`), `C9E2` (conjuntos de valores de view-role / nó filho) | seção 6 |
| Envio de convite de admin | `C9m6` (`UserActionsNewsletterMessaging`), `C213489Am` | seção 5.4 |
| Armazenamento de reação | `C12H`, `C23768ANd` → tabela `newsletter_message_reaction` | seção 7 |

---

## 2. JID e domínio

### 2.1 Parsing (found, `C0DL.A03`)

```java
// X.0DL (C0DL)
public C1Y7 A03(String str, String str2) throws C09B {
    String strTrim = str.trim();
    if (strTrim.isEmpty() || "0".equals(strTrim) || strTrim.indexOf("0") == 0)
        throw new C09B("Identifier must be a valid number starting with non-zero");
    if (!"newsletter".equals(str2)) throw new C09B(...);
    // cache lookup/insert, returns C1Y7(str)
}
```

`C1Y7.getServer()` retorna a string literal `"newsletter"`; `getType()` retorna `21`. Mesma regra de id numérico sem zero à esquerda dos demais tipos de JID multi-participante (grupos, listas de transmissão — ver [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) §2.1). O roteador genérico de JID `C0DZ.A01` recai em `C1Y7.A03.A02(str)` como seu caso default quando a string não é um singleton conhecido, nem um `UserJid`, nem um `GroupJid` — ou seja, `@newsletter` é o domínio de fallback nesse parser (found).

### 2.2 Pertencimento ao conjunto de tipos (found, `C0DZ.java`)

```java
public static boolean A0a(Jid jid) { return jid != null && jid.getType() == 21; }   // isNewsletter
public static boolean A0M(Jid jid) {
    int type = jid.getType();
    return type==0||type==1||type==18||type==22||type==3||type==7||type==21||type==26||type==28;
}
```
`A0a` é o predicado dedicado de newsletter. `A0M` agrupa o tipo 21 junto com grupos (18/22), lista de transmissão (3), comunidade (7) e outros em um conjunto mais amplo "capaz de multi-participante" (propósito do agrupamento exato não totalmente rastreado; inferido como controle de mecanismos compartilhados de participante/sessão).

---

## 3. Seguir / deixar de seguir

Seguir **não** é uma subscrição de stanza; é uma mutação `w:mex`, e o papel local (`C9U5`) alterna entre `GUEST` e `SUBSCRIBED`.

| Operação | doc_id | Variáveis (found) |
|-----------|--------|--------------------|
| `NewsletterJoin` | `24658527423838739` | `entry_point`, `record`, `recipient_account_id`, `sessions`, `jid`, `fetch_and_validate_vname`, `call_offer`, `request_bottom_sheet_fragment` |
| `NewsletterLeave` | `25758579043742316` | formato idêntico ao de `NewsletterJoin` |

Ambas são construídas pela mesma classe, `X/RunnableC24381AnW.java` (found). O conjunto de variáveis compartilhado (`entry_point`, `call_offer`, `request_bottom_sheet_fragment`) sugere que join/leave reutilizam um wrapper genérico de mutação de "ação de chat" também usado para chamadas e ações disparadas por bottom sheet em outras partes do app (inferido).

Transições do papel local no objeto `C2130898y` ("NewsletterInfo"):

| Helper | Condição | Significado |
|--------|--------|---------|
| `A0p()` | `!muted && role==ADMIN` | é admin |
| `A0q()` | `!muted && (role==ADMIN \|\| role==OWNER)` | é admin ou owner |
| `A0r()` | `role==SUBSCRIBED` | está seguindo |
| `A0s()` | `role==GUEST` | não está seguindo (usado para forçar `fetch_viewer_metadata=true` ao atualizar metadados — found em `BaseMetadataNewsletterGraphqlJob`) |
| `A0u()` | `!muted && role==OWNER` | é owner |

String de erro na UI ao falhar o follow: `str1c0d` "Couldn't follow channel", `str1c0e` "Couldn't follow channel. Check your device's internet connection and try again." (found, `res/values/strings.xml`).

---

## 4. Papéis

Existem dois enums de papel paralelos: um enum persistido local e um enum string de wire usado em variáveis/respostas GraphQL.

### 4.1 Papel local (found, `C9U5`)

```java
GUEST=0 (A03), SUBSCRIBED=1 (A05), ADMIN=2 (A02), OWNER=3 (A04)
```
`C9U5.A00()` mapeia ordinal → um rank de prioridade: GUEST→4, SUBSCRIBED→3, ADMIN→2, OWNER→1 (menor = mais privilegiado; propósito — ordem de classificação para listas de admin — inferido).

### 4.2 Papel de wire (found, `C9U4`, `serverValue` = nome do enum)

```
UNSET_OR_UNRECOGNIZED_ENUM_VALUE, ADMIN, GUEST, OWNER, SUBSCRIBER
```
Usado como o valor do atributo `view_role` no nó filho `smax:any` de IQs XMPP de newsletter (seção 6) e como valor de `viewer_metadata.role` do GraphQL (seção 8).

### 4.3 Capacidades e transferência

| Ação | Operação GraphQL | doc_id |
|--------|-----------|--------|
| Convidar um usuário como admin | `NewsletterAdminInvite` | `26278681041745438` |
| Revogar um convite de admin pendente | `NewsletterAdminInviteRevoke` | `24369392486051948` |
| Aceitar um convite de admin | `NewsletterAcceptAdminInvite` | `24934958956134858` |
| Rebaixar um admin | `NewsletterAdminDemote` | `25054538847517281` |
| Transferir a titularidade | `NewsletterChangeOwner` | `24737692515842078` |
| Busca em lote de perfis de admin | `NewsletterAdminProfilesQuery` | `28089989690595314` |
| Atualização de perfil de admin (nome/foto) | `NewsletterAdminProfileUpdate` | `25959584293627630` |
| Metadados de admin (completos, campos exclusivos de admin) | `NewsletterAdminMetadataQuery` | `26882701001369256` |
| Gate de capacidades | `NewslettersAdminCapabilitiesQuery` | `27579307995002556` |

Enum de ação do fluxo de convite de admin (found, `EnumC215899Sc`, usado por `AdminInviteErrorDialog`): `NOT_SUPPORTED=0`, `INVITE=1`, `ACCEPT_INVITE=2`, `REVOKE=3`, `DISMISS=4`.

Strings de erro na UI (found): `str0095` "Couldn't accept the admin invite. Please try again.", `str106c`/`str2bed` "Couldn't transfer ownership. Please try again(.)/ later.", `str2300`/`str2abd` "Channel admin invite", `str22fb` "Invite %s as admin?", `str2bd8` "Invite as channel admin".

---

## 5. Convite de admin — mensagem cliente-a-cliente, não apenas GraphQL

A UX de convite de admin tem **dois** mecanismos separados que rodam ambos: uma mutação MEX (`NewsletterAdminInvite`, concessão server-side) e uma **mensagem 1:1** normal de ponta a ponta, carregando o payload do convite para o convidado, construída de forma independente do MEX.

### 5.1 Proto (found, confirma e expande o material inicial de `Messages/newsletterAdminInviteMessage`)

`Message.newsletterAdminInviteMessage` — campo **78** de `Message` (`C30628DTw`), tipo `NewsletterAdminInviteMessage` (obfuscado `C30596DSq` na 2.26.41.6; constantes JADX na própria classe, não o número do campo em `Message`, já que a constante do campo de convite de admin não estava no conjunto grepado — o campo 78 corresponde a uma referência anterior do WAProto.proto e é corroborado de forma independente por todos os demais campos abaixo, que resolvem exatamente como documentado):

| Campo | Número | Tipo |
|-------|--------|------|
| `newsletterJid` | **1** | string |
| `newsletterName` | **2** | string |
| `jpegThumbnail` | **3** | bytes |
| `caption` | **4** | string |
| `inviteExpiration` | **5** | int64 |
| `contextInfo` | **6** | `ContextInfo` |

Constantes de número de campo confirmadas `CAPTION_FIELD_NUMBER=4`, `CONTEXT_INFO_FIELD_NUMBER=6`, `INVITE_EXPIRATION_FIELD_NUMBER=5`, `JPEG_THUMBNAIL_FIELD_NUMBER=3`, `NEWSLETTER_JID_FIELD_NUMBER=1`, `NEWSLETTER_NAME_FIELD_NUMBER=2` lidas diretamente de `C30596DSq` (found) — corresponde exatamente a um mapa de campos anterior para esta versão.

### 5.2 Caminho de envio (found, `C9m6` = `UserActionsNewsletterMessaging`)

```java
public final void A00(Context context, C1Y7 c1y7, String name, String caption, HashMap userJidToExpiration) {
    byte[] thumbnail = A01(context, c1y7);           // JPEG of the channel picture, quality 80
    for (entry in userJidToExpiration) {
        C213489Am item = new C213489Am(..., 94, ...); // message-type tag 94
        item.A01 = c1y7;          // newsletterJid
        item.A03 = name;          // newsletterName
        item.A00 = entry.value;   // inviteExpiration
        item.A02 = caption;
        item.A0O(thumbnail, false);
        // enqueued as a normal E2E message to the invitee's UserJid
    }
}
```
Linha de log: `"UserActionsNewsletterMessaging/userActionSendNewsletterAdminInviteMessages"`. Uma mensagem é enviada por convidado, cada uma com seu próprio timestamp de expiração — ou seja, o convite é uma **mensagem E2E por destinatário**, enquanto a operação MEX `NewsletterAdminInvite` (server-side) é o registro de concessão autoritativo (relação inferida entre os dois caminhos; ambos presentes no código, ordem/dependência não rastreada).

### 5.3 Aceitar

O cliente do convidado chama `NewsletterAcceptAdminInvite` (MEX). Sua requisição já carrega o conjunto completo de variáveis de busca de metadados (`fetch_followers_count`, `fetch_state`, `fetch_verification`, `fetch_viewer_metadata`, …) — aceitar um convite e rebuscar os metadados do canal é uma única ida e volta (found, variáveis de `X/AbstractC23610Aaw.java`).

---

## 6. Outras mensagens de newsletter: convite de seguidor, perfil de admin, agendada

### 6.1 `newsletterFollowerInviteMessage` / `newsletterFollowerInviteMessageV2`

Confirmado na 2.26.41.6 exatamente como o material inicial afirma, e re-verificado de forma independente aqui: ambos os campos de `Message` existem (`NEWSLETTER_FOLLOWER_INVITE_MESSAGE_FIELD_NUMBER` = **108**, `NEWSLETTER_FOLLOWER_INVITE_MESSAGE_V2_FIELD_NUMBER` = **113**, ambos found como constantes nomeadas em `C30628DTw`), e **ambos mapeiam para o mesmo tipo de submensagem**, `C30585DSf`:

| Campo | Número | Tipo |
|-------|--------|------|
| `newsletterJid` | **1** | string |
| `newsletterName` | **2** | string |
| `jpegThumbnail` | **3** | bytes |
| `caption` | **4** | string |
| `contextInfo` | **5** | `ContextInfo` |

Por que existem dois números de campo para um único tipo ainda é **unknown** — nenhuma divisão comportamental foi encontrada na camada Java nesta passagem também (consistente com uma descoberta anterior).

### 6.2 `newsletterAdminProfileMessage` / `newsletterAdminProfileStatusMessage` / `newsletterScheduledMessage`

Todos os três confirmados presentes como constantes nomeadas em `C30628DTw` (`NEWSLETTER_ADMIN_PROFILE_MESSAGE_FIELD_NUMBER` = **116**, `NEWSLETTER_ADMIN_PROFILE_STATUS_MESSAGE_FIELD_NUMBER` = **126**, `NEWSLETTER_SCHEDULED_MESSAGE_FIELD_NUMBER` = **132**), e todos os três resolvem para o mesmo wrapper genérico de campo único, `BD2` (= `FutureProofMessage`):

```java
public final class BD2 { public C30628DTw message_; }   // field "message", number 1, type Message (recursive)
```

Nenhuma classe de renderização/validação específica de campo existe para nenhum dos três (found, corresponde a uma nota anterior para `newsletterAdminProfileMessage` e `newsletterScheduledMessage`). `newsletterScheduledMessage` tem uma superfície dedicada não-message: a tabela local `newsletter_scheduled_message` (`chat_row_id`, `scheduled_server_id`, com índice único) e o nó filho de IQ de wire `<scheduled_messages/>` (seção 6.3) — a *funcionalidade* de agendamento é real e rastreada; apenas o próprio campo de proto `Message.newsletterScheduledMessage` permanece um wrapper não expandido.

### 6.3 Tabelas locais relacionadas

`newsletter_scheduled_message`, `newsletter_admin_profile` (`chat_row_id`, `admin_profile_id`, `timestamp`) sustentam `NewsletterAdminProfilesQuery`/`NewsletterAdminProfileUpdate` e a UI de agendamento, respectivamente (found, `C0SG.java`, `C0S3.java`).

---

## 7. Posts do canal: busca, envio, reações, contagem de visualizações

### 7.1 Namespace de IQ XMPP `newsletter` (found, `C9EN`)

A busca de conteúdo e algumas ações de escrita usam um namespace de IQ dedicado, separado do MEX:

```xml
<iq xmlns="newsletter" type="get" to="<jid>@newsletter" id="…">
  <messages count="N">
    <smax:any type="jid" jid="<jid>@newsletter" view_role="admin|guest|owner|subscriber"/>
    <before count="N"/> <!-- or <after count="N"/> -->
  </messages>
</iq>
```

| Elemento filho | Construtor | Propósito |
|---------------|-------------|---------|
| `<messages count/>` + `<before>`/`<after>` | `C9EN(C9EB, C9E2, id, count)` | paginar posts do canal |
| `<message_updates count since/>` | `C9EN(C1Y7, C9E8, Long, id, count)` | sincronização delta de posts editados/excluídos |
| `<statuses count/>` | `C9EN(C9E9, C9E2, id, count)` | busca de status/atualização do canal |
| `<status_updates count since/>` | `C9EN(C1Y7, C9EA, Long, id, count)` | sincronização delta de posts de status |
| `<scheduled_messages count/>` | `C9EN(C1Y7, C31085Dfd, id, count)` | posts agendados pendentes |
| `<question_responses server_id count/>` (plano e `type="status"`) | `C9EN(...)` | respostas de enquete/pergunta em um post |
| `<my_question_responses server_id/>` | `C9EN(C1Y7, String, long)` | próprias respostas do chamador |
| `<my_addons type="status" limit jid/>` | `C9EN(C1Y7, String, int, long)` | próprias reações/add-ons do chamador |
| `<live_updates/>` (`type="set"`) | `C9EN(C1Y7, String)` | assinar push em tempo real para um canal |

O atributo `view_role` no `smax:any` carrega a string de papel `C9U4` do próprio chamador (admin/guest/owner/subscriber) em cada IQ de busca de conteúdo — o servidor parece filtrar o conteúdo da resposta (ex.: campos exclusivos de admin) por requisição, em vez de puramente pelo estado da sessão (inferido).

### 7.2 Envio (found, `SendNewsletterMessageJob`) e recibos de visualização

Postar em um canal reutiliza o pipeline de envio padrão (não detalhado mais aqui; o job envolve a maquinaria normal de stanza `<message>`). Visualizar um post é explícito e separado dos recibos de entrega/leitura:

```java
// com.whatsapp.newsletter.messages.job.SendViewReceiptJob
<receipt to="<jid>@newsletter" id="…" type="view">
  <list><item server_id="…"/> …</list>
</receipt>
```
Um recibo `view` agrupa vários ids de mensagem do servidor. Este é o mecanismo que alimenta a **contagem de visualizações** por post exibida na UI do canal (found; a contagem em si é agregada no servidor — o cliente só reporta, nunca lê uma contagem de volta por meio desse IQ).

### 7.3 Reações (found)

Reações em posts do canal são **agregadas, não atribuídas** no armazenamento local:

```sql
CREATE UNIQUE INDEX newsletter_message_reaction_index
  ON newsletter_message_reaction (message_row_id, reaction);
-- columns include: reaction, reaction_count
```
ou seja, uma linha por par `(message, emoji)` com uma contagem corrente, não uma linha por usuário que reagiu — correspondendo à UI do canal, que mostra uma contagem agregada por emoji em vez de uma lista de usuários que reagiram, como em chats comuns. `newsletter_my_reaction_orphan_message` (`chat_row_id`, `server_message_id`, com índice único) guarda a **própria** reação do chamador quando ela chega antes do post ao qual se destina, para ser reconciliada quando o post chegar.

Quem reagiu só é visível para admins, via uma query MEX dedicada:

| Operação | doc_id | Variáveis |
|-----------|--------|-----------|
| `NewsletterReactionSendersList` | `25219734117717032` | `server_id` |

A política de reação é configurável por canal (seção 8.2, `reaction_codes`): `ALL`, `BASIC`, `BLOCKLIST`, `NONE` (strings de wire, ver `C9U3`/`C9TA` abaixo).

### 7.4 Contagem de seguidores / visualizações em metadados

`thread_metadata.followers_count` é retornado como parte de `NewsletterMetadata` (seção 8.1). Também existe uma operação paginada dedicada:

| Operação | doc_id | Variáveis |
|-----------|--------|-----------|
| `NewsletterFollowers` | `25646542368289354` | `newsletter_id`, `count` |

Contagens de visualização por post não são retornadas por uma operação standalone documentada nesta passagem; são inferidas como residentes dentro dos metadados por mensagem retornados pelo IQ `messages`/`message_updates` (seção 7.1), que não foi mais expandido aqui (nome exato do campo unknown).

---

## 8. Metadados do canal (formato de resposta GraphQL)

### 8.1 Resposta `NewsletterMetadata` (found, cadeia `C208048tR → C208038tQ → C208028tP`, nó GraphQL `xwa2_newsletter`)

```
xwa2_newsletter {
  id
  refresh_after_interval_sec
  state { type }                                    // C9UA
  status_metadata { last_status_sent_time, last_status_server_id }
  thread_metadata {
    creation_time
    description { text, id }
    followers_count
    handle
    invite                                           // invite code / link token
    name { text, id }
    picture { direct_path, type, url, id }
    pinned_messages[]
    preview
    settings { reaction_codes { value } }            // C9U3
    verification                                     // EnumC216369Tx
    verification_source                              // EnumC216219Ti
    wamo_sub { plan_id }
  }
  viewer_metadata {
    role                                             // C9U4
    settings[]                                       // { type, value } = EnumC216349Tv / EnumC216359Tw
    wamo_sub_status                                  // EnumC216229Tj
  }
}
```

### 8.2 Enums (found)

| Enum | Valores (strings de servidor onde aplicável) |
|------|---|
| `state.type` (`C9UA`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `DELETED`, `GEOSUSPENDED`, `NON_EXISTING`, `SUSPENDED` |
| `verification` (`EnumC216369Tx`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `UNVERIFIED`, `VERIFIED` |
| `verification_source` (`EnumC216219Ti`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `LEGACY_MANUAL_REVIEW`, `META_VERIFIED_SUBSCRIPTION` |
| `viewer_metadata.role` (`C9U4`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ADMIN`, `GUEST`, `OWNER`, `SUBSCRIBER` |
| `wamo_sub_status` (`EnumC216229Tj`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `INACTIVE` |
| `settings[].type` (`EnumC216349Tv`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `MUTE_ADMIN_ACTIVITY`, `MUTE_FOLLOWER_ACTIVITY` |
| `settings[].value` (`EnumC216359Tw`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `OFF`, `ON` |
| `reaction_codes.value` (`C9U3`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALL`, `BASIC`, `BLOCKLIST`, `NONE` |

Espelhos locais em `C2130898y` ("NewsletterInfo"): estado de verificação `EnumC216079Su` (`NOT_VERIFIED=0`, `VERIFIED=1`), fonte de verificação `C9T1` (`UNKNOWN_VERIFICATION_SOURCE=0`, `META_VERIFIED_SUBSCRIPTION=1`, `LEGACY_MANUAL_REVIEW=2`), estado de enforcement `C9T2` (`NOT_ENFORCED`, `SUSPENDED`, `GEOSUSPENDED` — gateado para leitura atrás da flag **3877** em `A0w`/`A0x`), estado local "ativo" `C9T3` (`NOT_SET`, `INACTIVE`, `ACTIVE`), progresso de migração/criação `C9T9` (`NOT_STARTED`, `IN_PROGRESS`, `FAILED`, `COMPLETED`), visibilidade de diretório `EnumC216039Sq` (`PUBLIC`, `PRIVATE`) e configuração local de reação `C9TA` (`DEFAULT=0`→wire `"BASIC"`, `ALL=1`→`"ALL"`, `NONE=2`→`"NONE"`, `BLOCKLIST=3`→`"BLOCKLIST"` — mapeamento lido de `UpdateNewsletterGraphqlJob.A0M`).

### 8.3 Atualização (found, `UpdateNewsletterGraphqlJob` → `NewsletterMetadataUpdate`)

```js
// GraphQl input built for doc_id 27150690864552229
updates: {
  description?: string,   // "" clears
  name?: string,
  picture?: base64,        // "" clears
  admin_profiles_enabled?: { settings: { admin_profiles_enabled, reaction_codes: { value: "ALL"|"BASIC"|"NONE"|"BLOCKLIST" } } }
}
newsletter_id: <jid>
fetch_image: true, fetch_preview: true, fetch_name: true,
fetch_viewer_metadata / fetch_state / fetch_verification / fetch_followers_count: <bool, usually mirrors viewer role>
```

### 8.4 Strings de UI de verificação (found)

`str136f` "New verified channel", `str2be2`/`str2be3` "Create verified channel"/icon, `str2c51` "Verified channels", `str2c78` "Your verified badge will be removed from this channel. Your Meta Verified subscription will remain active.", `str2ca9` "Sorry, you cannot change the name of a verified channel from the app. Please contact customer support for assistance." — ou seja, canais verificados têm um nome imutável com enforcement server-side (UX client-side apenas; o lado do enforcement é unknown).

---

## 9. Operações GraphQL / MEX de newsletter (doc_ids)

Todos os doc_ids abaixo foram re-verificados de forma independente para este build contra `assets/whatsapp-android-mex_client_persist_ids.json` dentro de `WhatsApp_2.26.41.6.apk` (found — doc_ids são entradas de asset estáticas, não obfuscadas, e estáveis na comparação de versões tentada aqui). Existem 46 operações `Newsletter*` nesse asset no total; as não detalhadas em outra parte deste report:

| Operação | doc_id | Propósito (inferido do nome/variáveis) |
|-----------|--------|------------------------------------------|
| `NewsletterCreate` | `27009199332109318` | criar um canal |
| `NewsletterCreateVerified` | `27777918425146464` | criar um canal pré-verificado (contas privilegiadas) |
| `NewsletterDelete` | `31838460859131915` | excluir um canal |
| `NewsletterUpdateVerification` | `27133493439664458` | solicitar/atualizar estado de verificação |
| `NewsletterHide` / `NewsletterUnhide` | `25033614912931367` / `24551592861177484` | alternância de visibilidade no diretório (local `EnumC216039Sq`) |
| `NewsletterFollowing` | `26856957210673444` | lista de canais que a conta segue |
| `NewsletterDirectoryList` / `Search` / `CategoryPreview` | `27480627564903390` / `27887355094203575` / `27432651036395658` | navegação pública no diretório |
| `NewsletterSimilar` / `NewsletterRecommended` | `36410329795280256` / `26638880912457992` | descoberta |
| `NewsletterInsights` | `24672564052397921` | analytics de owner/admin |
| `NewsletterPinMessages` / `NewsletterUnpinMessages` | `28521965914059511` / `37386851567568720` | gestão de post fixado (`message_ids`) |
| `NewsletterBlockUser` | `25106066249006236` | bloquear um seguidor |
| `NewsletterLogExposures` | `24606408825709914` | telemetria de impressão no diretório |
| `NewsletterLinkPreviewCheck` | `24188786150796507` | validar domínios de preview de link em posts |
| `NewsletterPollVoterList` | `24803802869271956` | votantes de enquete em um post (`jid`, `vote_hash`) |
| `NewsletterQuestionResponseStateUpdate` | `24896618076668076` | estado de moderação de Q&A |
| `NewsletterLabelAiContent` / `NewsletterLabelPaidPartnership` | `27470054215955630` / `26221505494211174` | rótulo por post de conteúdo gerado por IA / parceria paga |
| `NewsletterChangeWamoSub` / `Enable`/`DisableWamoSub` | `25201342542835866` / `25122474967344830` / `31916794074578680` | estado de assinatura de monetização do WhatsApp |
| `NewsletterUserReports` / `NewsletterCreateReportAppeal` | `27149305681394065` / `27792557363683798` | denúncia de abuso / recurso |
| `NewsletterEnforcements` / `NewsletterEnforcementAlertStates` | `27089116857425014` / `27640745535604048` | estado de enforcement/suspensão (pacote próprio `com.whatsapp.newsletterenforcements`) |
| `NewsletterUpdateUserSetting` | `24935528202764688` | preferência de UI por usuário (ex.: contagem de tooltip do seletor de contato) |
| `FetchNewsletterRankingFeatures` | `24742757908756088` | busca de sinal de ranking (diretório/recomendação) |

Todas são IQs `w:mex` (`type="get"`), schema `whatsapp_mex`, transporte confirmado pelo padrão de chamada compartilhado `C16880is`/`TreeWithGraphQL` visto em §5–8 (found). Formatos de resposta além do `NewsletterMetadata` da §8 não foram expandidos nesta passagem (unknown).

---

## 10. Armazenamento

| Tabela | Colunas-chave (found) |
|-------|----------------------|
| `newsletter` | `membership` (indexada), `invite_code` (indexada) |
| `newsletter_message` | única em `(chat_row_id, server_message_id)`; `is_autodelete_eligible` (indexada) |
| `newsletter_message_reaction` | única em `(message_row_id, reaction)`; `reaction`, `reaction_count` |
| `newsletter_my_reaction_orphan_message` | única em `(chat_row_id, server_message_id)` — própria reação do chamador chegando antes do post alvo |
| `newsletter_admin_profile` | única em `(chat_row_id, admin_profile_id)`; `timestamp` (indexada) |
| `newsletter_subscribers` | indexada em `(chat_row_id, type_of_fetch)` |
| `newsletter_scheduled_message` | única em `(chat_row_id, scheduled_server_id)` |
| `newsletter_interaction` | indexada em `timestamp_ms` e `(newsletter_jid_row_id, timestamp_ms)` |
| `newsletter_linked_account` | indexada em `chat_row_id` |
| `newsletter_pinned_message` | indexada em `(chat_row_id, pin_timestamp_ms)` |
| `newsletter_media_clear` | única em `(chat_row_id, media_type)` |

A infraestrutura de chat compartilhada (`chat`/`chat_view`, colunas centrais de `message`) é reutilizada como para qualquer chat tipado como `Jid`, igual a grupos/listas de transmissão (ver [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) §3.5) — não re-detalhada aqui.

---

## 11. Feature flags

IDs lidos nos call sites em `com.whatsapp.newsletter.*`; valores padrão não todos resolvidos nesta passagem (marcados onde conhecidos).

| ID | Controla |
|----|----------|
| **3877** | gateia a leitura dos helpers locais de estado de enforcement `A0w`/`A0x` (checagens de `SUSPENDED`/`GEOSUSPENDED`) em `C2130898y` |
| **1777** | seletor de país nos filtros do diretório |
| **5276** | visualização de identidade do canal durante a UI de migração newsletter→algo |
| **6445** | `ShareNewsletterInviteLinkActivity` |
| **6618** | `ViewNewsletterProfilePhoto` |
| **7237** | `NewsletterStatusView` |
| **9096** | `SendNewsletterMessageJob` |
| **12989** | `NewsletterDirectoryCategoriesActivity` |
| **15754** | marcador do perf-tracker "messages_fetch_end" em `GetNewsletterMessagesJob` |
| **17985** | `ForwardCounterAcsRepository` (contador de post encaminhado) |
| **19889** | `ForwardCounterApi` |
| **23797** | `NewsletterDescriptionView` |

Os valores padrão exatos e a extensão completa do comportamento gateado não foram rastreados além de "a classe só é alcançável quando a flag está ativa" (inferido do formato do call site); trate esta tabela como um mapa de onde procurar, não como padrões on/off confirmados (unknown para a maioria das linhas).

---

## 12. Casos de erro

| Sintoma | Causa | Correção / comportamento esperado |
|---------|-------|--------------------------|
| "Couldn't follow channel" (`str1c0d`/`str1c0e`) | `NewsletterJoin` falhou ou sem conectividade | tentar novamente; verificar conexão |
| "Couldn't accept the admin invite. Please try again." (`str0095`) | `NewsletterAcceptAdminInvite` falhou | tentar novamente |
| "Couldn't transfer ownership…" (`str106c`/`str2bed`) | `NewsletterChangeOwner` falhou | tentar novamente mais tarde |
| "Sorry, you cannot change the name of a verified channel from the app." (`str2ca9`) | canal é `VERIFIED`; nome imutável client-side | contatar o suporte (server-side; enforcement exato unknown) |
| Própria reação sem post correspondente ainda | stanza/evento de reação chegou antes da própria entrega do post | mantida em `newsletter_my_reaction_orphan_message` até o post chegar, depois reconciliada |
| `state.type` = `SUSPENDED`/`GEOSUSPENDED` | ação de enforcement contra o canal | a busca de conteúdo ainda retorna `state`; postagem/ações de admin presumivelmente bloqueadas server-side (gate exato unknown) |
| `state.type` = `DELETED`/`NON_EXISTING` | canal excluído ou nunca existiu | o cliente deve descartar a linha local `newsletter` (caminho de aplicação não rastreado) |
| Ação de convite de admin = `NOT_SUPPORTED` (`EnumC215899Sc`) | convite/aceite/revogação tentados em um contexto não suportado (ex.: papel, build) | diálogo de erro genérico, sem botão de repetir (`str5735`) |

---

## 13. Distinções-chave

| Não confundir | Diferença |
|----------------|------------|
| Newsletter (`@newsletter`, tipo 21) vs lista de transmissão (`@broadcast`, tipo 3) | newsletter: armazenada no servidor, não-E2E, modelo público de follow, papéis; lista de transmissão: fan-out E2E com sender-key apenas para contatos salvos — ver [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) |
| IQ `xmlns="newsletter"` vs operações GraphQL `Newsletter*` de `w:mex` | IQ = busca/paginação/assinatura de conteúdo (mensagens, status, agendadas, live-updates); MEX = metadados, papéis, diretório, moderação, monetização |
| `newsletterAdminInviteMessage` (mensagem E2E 1:1, campo 78) vs `NewsletterAdminInvite` (mutação MEX) | a mensagem é a notificação por destinatário com sua própria expiração; a operação MEX é a concessão server-side — ambas existem, relação inferida |
| `newsletterFollowerInviteMessage` (campo 108) vs `newsletterFollowerInviteMessageV2` (campo 113) | tipo de payload idêntico (`C30585DSf`); motivo da duplicação unknown |
| Papel local `C9U5` (GUEST/SUBSCRIBED/ADMIN/OWNER) vs papel de wire `C9U4` (…GUEST/ADMIN/OWNER/SUBSCRIBER) | os mesmos quatro papéis, ordem ordinal diferente e capitalização/ordem de string diferente — não presumir compatibilidade ordinal |
| Valor de wire `reaction_codes` (`ALL`/`BASIC`/`BLOCKLIST`/`NONE`, de `C9U3`) vs mapa ordinal-para-string local `C9TA` | o ordinal local 0 (`DEFAULT`) serializa para a string de wire `"BASIC"`, não `"DEFAULT"` |
| Armazenamento de reação por post (`newsletter_message_reaction`, contagem agregada) vs reações normais de mensagem | canais armazenam uma linha por par `(message, emoji)` com uma contagem, não uma linha por usuário que reagiu |

---

## 14. Fluxo completo

```
[Admin]  create channel
    │   NewsletterCreate / NewsletterCreateVerified (MEX) ──► [WA Server] allocates <id>@newsletter
    ▼
[Admin]  set name/description/picture, reaction policy
    │   UpdateNewsletterGraphqlJob ──► NewsletterMetadataUpdate (MEX)
    ▼
[Admin]  invite co-admin
    │   C9m6: per-recipient E2E message (newsletterAdminInviteMessage, field 78, own expiration)
    │   + NewsletterAdminInvite (MEX, server-side grant)
    ▼
[Invitee]  NewsletterAcceptAdminInvite (MEX) ──► role GUEST/SUBSCRIBED → ADMIN (C9U5)

[User]  discover channel (directory / shared link https://whatsapp.com/channel/<code>)
    ▼
[Client]  NewsletterJoin (MEX) ──► role → SUBSCRIBED
    ▼
[Client]  <iq xmlns="newsletter" type="get"><messages count view_role=subscriber/></iq>
    │◄── posts, paginated by before/after server_id
    ▼
[User]  views post ──► <receipt type="view"><list><item server_id/></list></receipt> (view count)
[User]  reacts ──► newsletter_message_reaction (aggregate count, own reaction may be orphaned until post lands)

[Admin]  moderates: NewsletterReactionSendersList (who reacted), NewsletterBlockUser,
         NewsletterPinMessages/Unpin, NewsletterUpdateVerification, NewsletterChangeOwner
    ▼
[Owner]  delete channel ──► NewsletterDelete (MEX)
```

---

## 15. Desconhecidos

| Item | Motivo |
|------|--------|
| Relação/ordem exata entre a mensagem E2E de convite de admin e a concessão MEX `NewsletterAdminInvite` | ambas existem no código; qual é autoritativa, ou se uma dispara a outra, não rastreado |
| Por que `newsletterFollowerInviteMessage` (108) e `…V2` (113) compartilham um único tipo de proto | nenhuma divisão comportamental encontrada na camada Java |
| Nome/localização exata do campo de contagem de visualizações por post na resposta de busca de mensagens | inferido como existente dentro do payload do IQ `messages`/`message_updates`; não expandido |
| Enforcement server-side do nome imutável em canais verificados | o cliente só mostra uma string de erro estática |
| Formato completo de resposta da maioria das operações MEX além de `NewsletterMetadata` | não lido nesta passagem |
| Valores padrão da maioria das feature flags na §11 | apenas alcançabilidade de classe, estado padrão não confirmado |
| Tráfego / comportamento do servidor em produção | nada capturado; apenas análise estática |

---

## 16. Baileys

Não coberto: `baron-baileys-v2` (o fork do Baileys usado como base de comparação nos demais reports deste repositório) não tem, no momento desta escrita, uma implementação confirmada e verificada contra este APK de newsletter/canal para comparar. Nenhum código do lado do Baileys foi inspecionado para este report; adicionar uma seção Baileys sem fatos verificados violaria as regras de evidência deste repositório. Se/quando `baron-baileys-v2` lançar suporte a newsletter, esta seção deve ser preenchida contra o JID (tipo 21, servidor `newsletter`), os IQs `xmlns="newsletter"` da §7.1, e os doc_ids MEX da §9.
