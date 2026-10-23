<!-- src-sha1: 8d1c772149420abe245fd6a70c2b6615d2ab4fc5 -->
# WhatsApp Interop — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** interoperabilidade de chat com terceiros no Android (estilo DMA): controle de funcionalidade e flags AB, aviso de consentimento e opt-in, lista de integradores, domínios JID interop e tag binária de JID, descoberta de usuários (`w:interop` FetchUsers), IQ set `w:interop`, plaintext restrito `InteropMessage` e tipos de mensagem suportados, diferenças de criptografia e stanza, grupos interop (operações MEX, notificações, privacidade de adição), ping de alcançabilidade, bloqueio e denúncia, armazenamento, casos de erro, diferenças em relação aos chats nativos, comparação com o Baileys

---

## 1. O que é (tecnicamente)

O Interop permite que uma conta do WhatsApp troque mensagens 1:1 e mensagens de grupo com contas de outros aplicativos de mensagens ("integradores"). O cliente nunca fala com esses aplicativos. Ele fala com os servidores do WhatsApp, que expõem cada conta de terceiros como um JID sintético no domínio `interop` (grupos: `interop.g.us`). Todas as afirmações vêm de análise estática do APK decompilado; nada foi capturado na rede nem executado contra um servidor. Níveis: **found** = lido em código ou recursos, **inferred** = deduzido do código, **unknown** = não resolvido. Os nomes ofuscados mudam a cada build e foram re-resolvidos na 2.26.41.6 a partir de strings estáveis (`InteropOptInManager/`, `InteropChatMessageHandler/`, `IntegratorManager/`, `w:interop`, `integrator_display_name`, `xwa2_interop_*`).

Estado nesta build:

| Parte | Estado na 2.26.41.6 |
|------|--------------------|
| Código | **Presente e completo**: UI (10 activities mais fragments e diálogos), cliente IQ, operações MEX de grupo e privacidade, pipeline de recebimento estrito, armazenamento, handler de notificação |
| Chave no servidor | **Desligado por padrão**: a flag AB raiz **7495** tem padrão `false`; toda flag interop lida no código tem padrão `false` (seção 2) |
| Região | O texto do produto limita a usuários com número de telefone da Região Europeia; **nenhuma verificação de país no cliente foi encontrada** (aplicação inferida no servidor, via flag 7495 e a lista de integradores) |
| Integradores | **Nenhum embutido no código**: nenhum nome de integrador, nenhum id fixo de integrador no código, recursos ou assets; a lista vem do servidor (seção 4) |

| Entidade | Nome na 2.26.41.6 | Função |
|--------|----------------|------|
| Gate (`InteropRolloutManager`, nome inferido de um getter) | `C32001Oa` | `A01` elegível, `A02` elegível e primário, `A00` grupos, `A03` caixa de entrada unificada |
| Cliente IQ / builders / parsers | `DmaInteropRPCManager` (`com.whatsapp.infra.smax.generated.dmainterop.outgoing`); `C31107Dfz` (cases 20-23), `C31106Dfy`; `C214369Ee`, `C9EQ`, `C9EP`, `C214389Eg`, `A1J` | cinco RPCs `w:interop`, parse estrito de schema |
| Integradores | `C227409sQ` manager, `C23765ANa` store, `A3X` (`IntegratorInfo`), `InteropUiCache` = `SharedPreferencesOnSharedPreferenceChangeListenerC20390p5` (prefs `interop_ui`) | lista, estado de opt-in, cache de UI |
| JIDs | `C99O` usuário, `C41021lm` dispositivo, `C55529Oy6` grupo, `C9YC` parser; writer `C40411kn.A00`, reader `C24610wf` (tag 244) | seção 3 |
| Recebimento | `ENP` -> `C34471Exu` (`DecryptionCallbackInterop`) -> `C34720F4p` (`InteropChatMessageHandler`); `DTF` (plaintext de 9 campos), `EUQ` (`ParseInteropMessageParams`) | pipeline estrito |
| Registro de tipos | `C32718EOz`; `FBN` texto, `FBK` imagem, `FBL` vídeo, `FBJ` GIF, `FBH` áudio, `FBI` documento, `FBM` reação, `FBG` não suportado | protobuf <-> FMessage |
| Envio | `C33446EhE` (branch), `F6P` (`E2eMessageEncryptor`), `F6K` (`<meta>`) | saída |
| Grupos / privacidade | `InteropGroupsManager`, `C3R2`, `C3Rb` / `C3Qh` somente em smali; `C0WQ` (notificações); `InteropPrivacySettingsManager`, `C3Q4` / `C3Q1` / `C29664Cuh` | MEX |
| Opt-in | `C229349vm` (`InteropOptInManager`), `ARH`, `A4N`, `C224669lg` / `C24380wI` (aviso), `PaaInteropMigrator` | wizard, consentimento |
| Ping | `X.0xL` anônimo em `C1S0` (`InteropNotificationHandler`), id 270 em `AbstractC32331E9w` | notificação |
| Analytics | `AnonymousClass590` | WAM 6684, 7044, 7168, 6680 |

---

## 2. Controle de funcionalidade

### 2.1 Cadeia de gates (found, `C32001Oa`)

| Método | Condição | Usado para |
|--------|-----------|----------|
| `A01()` | conta não é uma conta dependente sob as regras de experiência por idade (`C14980fa.A00` -> `C08520Ne.A03()` -> `C08530Nf.A03()` false; tipo dependente `EnumC08540Ng.DEPENDENT`) **e** AB **7495** | tudo; pasta da lista de chats, badge, composição |
| `A02()` | `A01()` e não é companion (`AnonymousClass091.BRD()` false, ou seja, `registration_device_id` é 0) | opt-in manager, configurações, seleção de integradores, handler de notificação |
| `A00()` | `A01()` e AB **15732** | entrada "New group", etapa de privacidade de grupo |
| `A03()` | `A01()` e AB **11479** | etapa de caixa de entrada unificada e caixa combinada |

`InteropSettingsActivity.onResume` (chama `finish()`), `InteropOptInSelectIntegratorsActivity.onCreate`, `InteropOptInManager` e o handler de notificação `w:interop` verificam `A02()` novamente.

### 2.2 Flags AB (found: id, padrão e pontos de chamada; nomes de uma tabela de nomes de build antiga, casados por id, **inferred**)

| Flag | Nome legado (inferred) | Padrão | Lida em | Controla |
|------|------------------------|---------|---------|----------|
| **7495** | `IS_USER_INTEROP_ELIGIBLE` | false | `C32001Oa.A01`, `C224669lg.A01`, `C230679y0` (badge), `RunnableC23952AUh` (Home), `C0Y5` | gate raiz; estado do badge da Home |
| **15732** | `INTEROP_GROUP_MESSAGING_ENABLED` | false | `C32001Oa.A00` | criação de grupo, etapa de privacidade de grupo |
| **11479** | `WA_INTEROP_UNIFIED_INBOX_ENABLED` | false | `C32001Oa.A03`; id também registrado em `C33251Ee2` | etapa do tipo de caixa de entrada, caixa combinada |
| **25512** | `INTEROP_CONTACT_MASTER_ENABLED` | false | `C0ZT`, `C51044MkK`, `C201508iH`, `C93z`, `InteropSelectChatTypeActivity` | entrada "New contact", contatos interop salvos, resolução de nomes |
| **5760** | `INTEROP_PROTOBUF_VALIDATION_ENABLED` | false | `ENP.A00` | encaminha JIDs interop ao pipeline estrito `InteropMessage` (8.1) |
| **38723** | sem nome | false | `EA0.A00` (descriptor) | distribuição de sender key dentro de grupos interop (string de log `interop_group_skdm_processing_enabled`) |
| **23701** | `DMA_INFLATE_VIEW_ONDEMAND_ANDROID` | true | `C1R9` | inflação sob demanda do cabeçalho interop da lista de chats |

Definidas com padrões mas sem leitor literal encontrado (uso unknown): **3953** `INTEROP_CLIENT_UX_ENABLED`, **5759** `INTEROP_BOOTSTRAP_ENABLED`, **6613** `INTEROP_WS8_ENABLED`, **18670** `INTEROP_ADD_GROUP_PARTICIPANT_CLIENT_ENABLED`, **20999**, **11518**, **13532**, **14070** (todas false); **22752**, **24016**, **24256**, **23652**, **24275**, **24098** (ajuste de UI `DMA_*`, todas true). A flag **11619** (`ENABLE_DMA_GROUP_JID`) não tem entrada nas tabelas de padrões. Mecanismo: WA_AB_PROPS.md.

### 2.3 Gates não AB (found)

- Aviso de consentimento **20240306** no estágio **160** (`C24380wI.A0D`): as configurações mostram a tela de configuração só quando aceito, senão a tela inicial de opt-in (5.1).
- Conta dependente (`C14980fa`): não elegível; `PaaInteropMigrator` sai dos grupos interop e reinicia o aviso (5.5).
- Dispositivo primário (`A02()`): companions não podem fazer opt-in nem configurar.

---

## 3. Identidade: JIDs e domínios

### 3.1 Domínios (found)

| Tipo | Classe | Tipo de JID | Formato | Validação |
|------|-------|----------|--------|------------|
| Usuário interop | `C99O` (`InteropUserJid`) | **22** | `{integrator}-{account}@interop` | um hífen (o último divide); integrator 1-3 dígitos, sem `0` à esquerda, parseado como int; account 1-15 dígitos, sem `0` à esquerda |
| Dispositivo interop | `C41021lm` | **23** | `{integrator}-{account}:{device}@interop` | o índice do dispositivo deve ser **0**, senão `C09B` ("Interop device JIDs must have device index 0") |
| Grupo interop | `C55529Oy6` (`GroupJid`) | **28** | `{gid}@interop.g.us` | gid 1-20 dígitos, primeiro dígito 1-9, sem `-` |

- `C0DZ.A0W` = tipo 22, `A0X` = 22 ou 23 (1:1), `A0V` = 28, `A0U` = `A0X` ou `A0V` (qualquer chat interop); usado em 128 classes. `C41021lm.getRawString()` sempre imprime `:0`. A factory (`UserJid.JID_FACTORY.A04(str, "interop")`, `C9YC.A00`) lança `C09B` ("Invalid interop JID: ...") em qualquer violação de regra.
- Ids de integrador em respostas IQ são limitados a 1-999 (igual à regra de 3 dígitos). Ids de grupo não têm a forma legada `creator-timestamp`; as operações MEX de grupo recebem o gid sem domínio (`InteropGroupsManager.A00` remove `@...`).

### 3.2 Token binário (found)

Tag **244** `JID_INTEROP` (writer `C40411kn.A00`, leitor de atributos `C24610wf`): string `user` (id da conta, ou gid para grupos) -> u16 **device** -> u16 **integrator** -> byte **domain**.

Byte de domínio: **0** = `interop`, **2** = `interop.g.us`; qualquer outro valor lança exceção ("invalid domain received for JID_INTEROP tuple"). Uma tupla de grupo deve ter device 0 e integrator 0 (senão "invalid interop group jid"). O reader renderiza o domínio 0 como `{integrator}-{user}[:{device}]@interop` (device omitido quando 0). A tag **245** (uma forma separada de JID interop em outros clientes) não tem handler nesta build (grep de `C24610wf` / `C40411kn`).

### 3.3 Mapeamento e exibição (found)

| Tópico | Fato |
|-------|------|
| LID / PN | `WaJidMapRepository/setJidMapping refused mapping for interop JID`; um JID interop é seu próprio endereço signal e id de chat |
| Nome | fonte de nome `INTEROP_NAME` (`C0Y7`), valor do campo `display_name` do contato (`c06290Dn.A07().A00.A0b`); o parser da stanza de mensagem lê `notify` e `display_name` em toda mensagem (`AbstractC33377Eg6.A02`); uso de `display_name` para push names interop inferido |
| Membros do grupo | o parse de participantes `w:g2` mantém o JID interop no registro do participante (`C23201A1a` -> `C228499uF.A00(c99o, ...)`), além de `display_name`, `lid`, `phone_number`, `join_time` |
| Dados de perfil | sem foto nem nome de perfil: "Profile name and photo are not available in third-party chats" (string); somente ícone do integrador (cache de 8 MiB `cache/interop_image_cache`, loader `interop_image_loader`) |

---

## 4. Integradores

### 4.1 Modelo (found)

Não existe nome de integrador, id fixo nem tabela de tipos de identificador no código, em `res/` ou em `assets/`; o servidor decide quais integradores existem, seus ids, nomes e capacidade de grupo. `A3X`: `A00` id, `A03` nome, `A02` status (`ONBOARDING`, `ACTIVE`, `REMOVED`), `A04` URL do ícone, `A05` optedIn, `A01` tipo de identificador (`USERNAME`, `PHONE`, `EMAIL`), `A06` supportsGroupMessaging. Integrador de um JID: `C99O.A00` -> `C227409sQ.A00` -> `A3X`.

### 4.2 Fetch (found, `C31107Dfz` case 20, parser `C214369Ee`)

Requisição `<iq type="get" xmlns="w:interop" to="s.whatsapp.net" id=".."><integrator fetch="all"/></iq>` (`to` = JID do servidor, classe `C19380nJ.A00`). Resultado: `<integrator_list opted_in="true"><integrator id status identifier_type name icon opted_in><features group_messaging/></integrator>...</integrator_list>` (nomes de atributos encontrados; a forma do nó `features` é inferida a partir do caminho `features/group_messaging`).

Mapa de atributos: `status` = `onboarding` / `active` / `removed`; `identifier_type` = `username` / `pn` / `email`; `features` -> `group_messaging` = `true` / `false`; `opted_in` padrão `true`. Limites do parser: 0-999 integradores, id 1-999; uma entrada sem `name` ou `icon` é descartada; status ou tipo de identificador desconhecido lança exceção. Erros de IQ: `bad-request` (400), `internal-server-error` (500) (`A1J.A02` / `A04`).

A corrotina de refresh (`C24110Aar` case 34, log `IntegratorManager/refreshIntegrators`) grava a tabela (5.6) e a pref `group_capable_integrators`. Gatilhos encontrados: abertura da tela de opt-in; o handler genérico `<ack error>` (`C13X`) apaga todas as linhas `integrator_display_name` quando uma mensagem interop 1:1 é rejeitada (`C24110Aar` case 35). Outros gatilhos não foram resolvidos.

---

## 5. Consentimento, opt-in, configurações

### 5.1 Aviso de consentimento (found)

O id de aviso **20240306** é uma divulgação de privacidade (`C24380wI`, classe `PrivacyDisclosureDataManager`). Estágio **160** = aceito (`A0D`); os estágios 105-399 contam como "elegível/exibido" (`A02`). `InteropOptInManager.A01` (`C229349vm`):

```
A02() false -> log "interop is not enabled, stop"
notice 20240306 != 160 -> render notice (C32411Pr.A05); ARH.onUserOptedIn sets has_previously_onboarded and continues; dismiss / deny / error stop
else -> InteropOptInSelectIntegratorsActivity(entryPoint)
```

O estágio **162** é gravado por `PaaInteropMigrator` (`C24380wI.A09(null, 20240306, 162, false)`); significado unknown (não é 160, então o aviso passa a contar como não aceito).

### 5.2 Wizard (found, `A4N`, `InteropOptInSelectIntegratorsActivity`)

```
Select integrators (list from table, header "Select the third-party apps you want people to message you from.")
   ▼
[AB 11479] Unified inbox option (COMBINED | SEPARATED) ──► else skip
   ▼
[AB 15732] Group privacy setting ("Who can add me to third-party groups") ──► else skip
   ▼
InteropOptInManager.A01: notice not accepted -> consent notice (5.1); accepted -> straight on
   ▼  onUserOptedIn
SetOptInIntegrators IQ (full list)
```

Se o aviso já foi aceito (edição a partir das configurações), a tela de seleção esconde seus botões de cancelar e continuar e `C201718ig.A00` salva diretamente (salvar ao alterar inferido); tipo de caixa de entrada e privacidade de grupo são linhas separadas do fragment de configuração. A etapa de privacidade de grupo é inferida como terminando em `A01` (log `BaseInteropOptInViewModel onOptInContinue`). Os pontos de entrada são um int (`entryPoint`) registrado no WAM (5.6).

### 5.3 SetOptInIntegrators (found, `C31107Dfz` case 23, parser `C9EP`)

```xml
<iq type="set" xmlns="w:interop" to="s.whatsapp.net" id=".."><opt_in_integrators><integrator_list>
  <integrator id="12"/> ...      <!-- 0..999 entries, the full desired state -->
</integrator_list></opt_in_integrators></iq>   <!-- result: integrator_list/integrator[@id], each with an optional error child -->
```

Tratamento no cliente (`C24113Aau` case 40): erros por integrador são coletados; a tabela é reescrita em uma transação (`opt_in_status` zerado para todos, depois definido para os solicitados menos os ids com falha). O opt-out não tem stanza própria: os diálogos de opt-out e o caminho "turn off" usam o mesmo set com uma lista menor (inferido pela ausência de qualquer outra stanza de opt-out; o caminho de lista vazia não foi rastreado).

Mapeamento de erros na UI (`InteropOptInSelectIntegratorsActivity.A0X`): códigos **500**, **810**, **800** -> "Apps can't be saved right now. Please try again later."; qualquer outro código ou nulo -> "Apps can't be saved right now."

### 5.4 Telas de configurações (found, `AndroidManifest.xml`)

Telas (todas em `AndroidManifest.xml`): `InteropSettingsActivity` com fragments Main / Optin / Config (landing quando o aviso não foi aceito, senão configuração; FAQ de ajuda `317021344671277`); `InteropOptInSelectIntegratorsActivity` (apps); `InteropUnifiedInboxOptionActivity` ("Manage inbox", COMBINED vs SEPARATED); `InteropGroupPrivacySettingUpdateActivity` e `...AddBlocklistPickerActivity` (9.4); `InteropReachNotificationSettingsActivity` ("Third-party chat requests", 6.3); `InteropOptOutDialogFragment` / `...IntegratorDialogFragment` ("Turn off third-party chats?"); `InteropConversationsActivity` (lista da pasta); `InteropComposeSelectIntegratorActivity`, `...EnterInfoActivity`, `InteropSelectChatTypeActivity` (novo chat / grupo / contato).

### 5.5 Opt-out e migrator (found)

Com opt-out: os chats existentes ficam somente leitura (banner do composer "Third-party chats are turned off. You can't send messages in this chat, and you won't receive messages."). `PaaInteropMigrator` (`C0q`): executa quando a conta é uma conta dependente (`C20K.A1W` = restricted) **e** o aviso foi aceito; chama `LeaveInteropGroup` (`groups_to_leave`, códigos de resposta em {200, 400, 401, 403, 404, 405} contam como concluído), depois grava o estágio de aviso 162. A expansão de "PAA" é inferida (experiência por idade); o vínculo com conta dependente foi found.

### 5.6 Estado armazenado e analytics (found)

| Armazenamento | Chaves / schema |
|-------|---------------|
| prefs `interop_ui` | `unified_inbox_option` (UNKNOWN / COMBINED / SEPARATED), `who_can_add_me_to_interop_groups` (int), `who_can_add_me_to_interop_groups_hash`, `who_can_add_me_to_interop_groups_deny_list` (set), `optedInIntegratorNames` (set) + chaves de nome por id, `interop_reach_enabled` (padrão true), `interop_reach_integrators` (array de int), `interop_reach_notifs` (set de `id:name:display_name:t`), `suspended_interop_groups` (set de gids), `has_previously_onboarded`, `group_capable_integrators`; prefs `interop_badge_prefs`: `pref_interop_badge_disabled`, `pref_interop_badge_account_state`, `pref_interop_badge_third_party_chats_state` |
| tabela `integrator_display_name` | `integrator_id` INTEGER PK, `display_name` TEXT, `status` INTEGER, `icon_path` TEXT padrão `''`, `opt_in_status` INTEGER padrão 0, `identifier_type` INTEGER padrão 0, `group_messaging_supported` INTEGER; índice `integrator_opt_in_index` em `opt_in_status` |
| outras tabelas | `wa_block_list_interop` (índice único em `jid`); linhas de `wa_address_book` com `raw_contact_id = -5` e `jid LIKE '{id}-%@interop'` (`SAVED_INTEROP_CONTACTS`), não gravadas nos contatos do telefone |
| WAM | 6684 (entrega de banner), 7044 (fluxo de onboarding, id de sessão `InteropOnboardingSessionIdManager`), 7168 (ação do usuário), 6680 (caixa de entrada de terceiros); o evento 1158 carrega `interopContactsSize`, `interopContactsSizePerIntegrator` |

---

## 6. IQ set `w:interop`

Os cinco RPCs de `DmaInteropRPCManager` passam por `MessageClientSmaxWrapper`; todo IQ carrega `type`, `xmlns="w:interop"`, `to` = JID do servidor, `id`.

| Operação | Tipo | Corpo | Limite | Resultado |
|-----------|------|------|-------|--------|
| FetchIntegrators | get | `<integrator fetch="all"/>` | - | 4.2 |
| FetchUsers | get | `<users><user external_id integrator_id/></users>` | **1-20 usuários** | 7.2 |
| SetOptInIntegrators | set | `<opt_in_integrators><integrator_list><integrator id/>` | 0-999 | 5.3 |
| GetReachabilitySettings | get | `<reachability_settings/>` | - | 6.3 |
| SetReachabilitySettings | set | `<reachability_settings enabled="true\|false"><integrator id/>...` | 0-999 | resultado / erro |
| Block / unblock | set | `<blocklist><item action="block\|unblock" jid="{interop JID}"/></blocklist>` | - | resultado; erros `IQErrorBadRequest`, `IQErrorInternalServerError` |

### 6.1 Bloqueio e denúncia (found)

O bloqueio interop usa `xmlns="w:interop"` (`C31106Dfy`, helper `C9EF`, log `InteropBlocklistHelper/getInteropBlocklist/error code:`) e a tabela `wa_block_list_interop`. UI: "Blocked in third-party chats"; o diálogo de bloqueio diz que pessoas bloqueadas no WhatsApp ainda podem alcançar o usuário no aplicativo de terceiros. A denúncia de spam usa o fluxo genérico de spam (`spam_flow`, `C9E2`) com texto de diálogo por integrador. Roteamento de notificação: `AbstractC32331E9w` mapeia o xmlns `w:interop` para o handler id **270**; `EnumC32096E0u.NOTIFICATION_W_INTEROP` = `"w:interop"`.

### 6.2 Notificação de ping (found, `X.0xL` anônimo em `C1S0`)

`<notification xmlns="w:interop" t=".."><ping display_name=".."><X id=".." name=".."/></ping></notification>` (a tag `X` do primeiro filho de `ping` não é verificada pelo código).

Somente um primeiro filho chamado `ping` é aceito (senão log `unknown tag=`). Com `A02()` true, ele acrescenta `id:name:display_name:t` à pref `interop_reach_notifs`, publica uma notificação local no canal `critical_app_alerts@1` (corpo "Chatting with people on third-party apps is an optional WhatsApp feature in the European Region.", ação "Manage requests", receiver de dispensa `InteropNotificationDismissReceiver`) e registra o WAM 6684. O gatilho no servidor (alguém de um integrador tentou alcançar o usuário) é inferido do texto de configurações "Get notified when someone wants to message you from a third-party app."

### 6.3 Alcançabilidade (found)

As configurações são por **integrador** (filhos `<integrator id>`, limite 0-999), não por usuário. O padrão de `enabled` é `true` em `interop_reach_enabled`. Nenhum código de inscrição de presença para JIDs interop foi encontrado (inferido: a alcançabilidade o substitui).

---

## 7. Descoberta de usuários

### 7.1 FetchUsers (found, `C31107Dfz` case 21, parser `C9EQ`)

JIDs interop vêm apenas deste IQ; o USync não tem protocolo interop (WA_USYNC.md).

```xml
<iq type="get" xmlns="w:interop" to="s.whatsapp.net" id=".."><users>
  <user external_id="alice@example.org" integrator_id="12"/>          <!-- 1..20 -->
</users></iq>
<!-- result -->
<users>
  <user jid="12-105012705411308@interop" external_id=".." normalized_external_id=".." integrator_id="12"/>
  <user external_id=".." normalized_external_id=".." integrator_id="12"><error code="404" text="item-not-found"/></user>
</users>
```

Resultados por usuário: sucesso `user[@jid]` (`C9DG`, jid parseado como `C99O`); `item-not-found` código padrão **404** (`C9DH`); `forbidden` padrão **403** (`C9DF`); `internal-server-error` (`C9DE`).

Erros do IQ inteiro: `bad-request`, `internal-server-error`. Listas de resultado em `C9FA`: não encontrado, forbidden, erro de servidor, mapa resolvido `{(external_id, integrator) -> UserJid}`. Requisição e resposta rejeitam 0 ou mais de **20** usuários.

### 7.2 Entrada de identificador e contatos salvos (found, `InteropComposeEnterInfoActivity`)

| Tipo de identificador | UI | Valor enviado como `external_id` |
|-----------------|----|------------------------------|
| `USERNAME` | um campo ("Enter Username") | texto |
| `PHONE` | seletor de país + número | código do país e número concatenados (filtro por caractere, regra não rastreada) |
| `EMAIL` | um campo | texto |

Fluxo: escolher app (`InteropComposeSelectIntegratorActivity`, integradores com opt-in da tabela) -> tipo de chat (`InteropSelectChatTypeActivity`: "New chat", "New group" se AB 15732 e o integrador suporta grupos, "New contact" se AB 25512) -> informar id -> FetchUsers -> abrir o chat no JID retornado. Strings: "This user can't be found" (não encontrado), "This user is already a group member" (adição ao grupo), "Couldn't create the chat. Please try again.".

Com AB 25512, `ContactFormActivity.verifyInteropIdentifierAndSave` resolve o id via FetchUsers (`C24113Aau` case 41) e salva uma linha em `wa_address_book` (raw_contact_id -5); "Usernames and contacts added to third-party chats will not save to your phone."

---

## 8. Mensagens

### 8.1 Seleção de pipeline (found)

Descriptografia (`ENP.A00`): quando a AB **5760** está ligada e o JID do chat satisfaz `A0U` (interop 1:1 ou grupo interop), o ciphertext é tratado por `C34471Exu` (`DecryptionCallbackInterop`); caso contrário, rodam os callbacks regulares. Os tipos de ciphertext tratados por `ENP` são os comuns: **0** (`msg`), **1** (`pkmsg`), **2** (`skmsg`, sender key), **4** (caminho de bot, não interop). Portanto o interop usa as mesmas sessões Signal e sender keys dos chats nativos.

```
<message from="12-123[:0]@interop" ..><enc type=pkmsg|msg|skmsg v=2>...</enc></message>
   │  ENP.decryptMessage (Signal / sender key)
   ▼
C34471Exu.handlePlaintext
   │  remove padding (last byte = pad length; empty / zero / >= length fails, log DecryptUtil/removePadding)
   │  C33369Efy.A03(E0T.INTEROP_MESSAGE, ...)          ── message pipeline type "interop_message"
   ▼
C34720F4p (InteropChatMessageHandler)
   │  parse bytes as DTF (InteropMessage subset)
   │  unknown-field check -> failure 70
   │  C32718EOz.A00(EUQ) -> FMessage via type handlers; SKDM (group) processed if AB 38723
   ▼
store, receipt, notification
```

Relato de falhas: `C34720F4p.A00` retorna `C33063Eaz(reason)` e chama `A0Y(null, key, reason, 491)` no caminho do recibo; `C34471Exu` chama `C33369Efy.A07(.., 491, reason, ..)` para plaintext inválido. O literal **491** é comum a ambos (significado não resolvido).

### 8.2 Subconjunto de plaintext `InteropMessage` (found, `DTF`)

O plaintext **não** é o `Message` completo. `DTF` declara exatamente estes campos, numerados como no `Message` completo:

| Campo | Número | Tipo | Handler | Notas |
|-------|--------|------|---------|-------|
| `conversation` | **1** | string | `FBN` | texto simples |
| `senderKeyDistributionMessage` | **2** | message | `C34720F4p` | id do grupo + SKDM axolotl; o id do grupo deve ser igual ao do chat quando o chat é um grupo |
| `imageMessage` | **3** | message | `FBK` | |
| `extendedTextMessage` | **6** | message | `FBN` | campos de prévia de link |
| `documentMessage` | **7** | message | `FBI` | não quando o `type` da stanza é `medianotify` |
| `audioMessage` | **8** | message | `FBH` | mensagens de voz via `ptt` |
| `videoMessage` | **9** | message | `FBL` (sem `gifPlayback`) / `FBJ` (`gifPlayback`) | |
| `reactionMessage` | **46** | message | `FBM` | |
| `ptvMessage` | **66** | message | nenhum encontrado | aceito pelo schema e validado quanto a campos desconhecidos; não existe parser de FMessage no registro (recebimento de video-note não resolvido) |

A verificação de campos desconhecidos lê por reflexão a contagem de campos desconhecidos de `DTF` e das submensagens de imagem, vídeo, PTV, áudio, documento, texto estendido e reação; uma contagem igual ou maior que 1 retorna a falha **70**. Campos fora de `DTF` fazem, portanto, a mensagem falhar: por exemplo `messageContextInfo` (35), `protocolMessage` (12), sticker, contato, localização, enquete (inferido do schema; o efeito de um campo específico não foi exercitado).

### 8.3 Tipos de mensagem suportados e limites (found)

| Tipo | Regras aplicadas no recebimento (motivo da falha) |
|------|--------------------------------------------|
| Texto, vídeo | `conversation` ou `extendedTextMessage.text`, truncado em **65536** caracteres; prévia de link somente se `matchedText` for uma URL válida contida no texto; título e descrição truncados em 65536; tipo de prévia mapeado para 0, 1, 4, 5, 6, 7; vídeo e GIF compartilham o parser de mídia `C33395EgO.A05` (`gifPlayback` escolhe `FBJ`) |
| Imagem | `mediaKey` obrigatória (16); `fileLength` >= 0 (13); `fileSha256` 32 bytes (14); `fileEncSha256` 32 bytes se definido (14); mime **somente `image/jpeg` ou `image/png`** (17); `directPath`, largura, altura copiados; tripla de thumbnail (direct path, sha, enc sha) opcional; scans progressivos aceitos quando há 2-20 comprimentos de scan e o comprimento de `scansSidecar` / 10 é igual à contagem e a soma cabe em um int |
| Áudio | `mediaKey` obrigatória (16); `fileLength` > 0 (13); hashes de 32 bytes (14); mime deve ser um tipo de áudio conhecido (17); flag `ptt`; `waveform` mantido somente se tiver 1-192 bytes; `backgroundArgb`; `seconds` |
| Documento | `mediaKey` obrigatória (16); `fileLength` >= 0 (13); hashes de 32 bytes (14); `title` truncado em 65536; thumbnail JPEG mantido se passar na verificação de tamanho |
| Reação | `key.id` e `key.remoteJid` não vazios; `text` junto com uma versão de edição diferente de zero é rejeitado (warning `edit version and text message are both set`); `senderTimestampMs` mantido; uma stanza com `type="reaction"` deve produzir uma mensagem de reação (senão falha **76**) |
| Resposta / citação | `ContextInfo` com `stanzaId`, `participant`, mensagem citada (parseada como `DTF` novamente, `ContextInfoProtobufInterop`), `quotedType`; no lado do envio `InteropContextInfoBuilder` serializa a mensagem citada recursivamente |

Não aceitos (fora dos 9 campos): stickers, contatos, localizações, enquetes, eventos, templates, view-once. O seletor de anexos esconde as entradas de contato, localização, enquete, evento, status de grupo, imagine, pagamento, pix e remessa para chats interop (verificações `A0L`, `A0M`, `A0P`, `A0Q`, `A0R`, `A0T`, `A0U`, `A0X` de `ConversationAttachmentContentView`); documento, câmera, galeria e áudio não são controlados por verificações interop (inferido que permanecem). Mensagens temporárias não são suportadas ("disappearing messages are not supported in third-party chats", também excluídas da configuração de timer padrão). Os bytes de mídia trafegam pelo caminho normal de mídia do WhatsApp (chave, hashes e `directPath` na mensagem; valor de analytics de origem de download 15 = `interop`).

### 8.4 Lado do envio (found)

| Etapa | Comportamento |
|------|-----------|
| Serializer | `C33446EhE`: JID de chat do tipo 22/23 (`A0X`) usa o serializer interop (`C32718EOz.A01` com `ADs` por tipo, logs `buildE2eInteropMessage`); outros chats usam o builder regular, então **grupos** interop (tipo 28) usam o builder regular |
| Classe FMessage não suportada | handler `FBG` -> lança `E3G` 70 antes do envio; classe errada para um handler -> `E3G` 0 |
| Verificações de imagem | mime `image/jpeg` ou `image/png`, senão `E3G` 17 (`null` vira `image/jpeg`); hash diferente de 32 bytes `E3G` 14; media key ausente `E3G` 16; os contribuidores de stanza `F6B`, `F6G`, `F6I`, `F68`, `F69`, `F6H`, `F6M`, `F6X` não têm branch interop (anexo não resolvido) |
| Encryptor (`F6P`) | para chats interop (`A0U`) o encryptor pula `C33284Eea.A02` (adiciona metadados da lista de dispositivos via `AbstractC30999De0.A03`, inferido) e pula `paddingBytes` (tamanho vindo da AB 1723) |
| `<meta>` (`F6K`) | `content_type="add_on"` é pulado para chats interop |
| Reporting token (`F6L`) | pulado quando o alvo é um JID de dispositivo interop |
| Lista de dispositivos / ADV | o índice de dispositivo interop é sempre 0; `DeviceADVInfoHandler` tem uma verificação interop na entrada (`C24230w2`, saída antecipada inferida); nenhum fan-out multi-dispositivo é possível (inferido: um dispositivo por contato) |

Outras diferenças em relação às mensagens nativas: chats interop usam o tipo de pipeline `interop_message` (`E0T`) em vez dos tipos de texto / mídia / reação; valor de tipo de chat WAM 5 no evento de decrypt (`AbstractC33424Egr`) e 6 no evento `FNR` (nativo 3 / 1); add-ons de message secret (votos de enquete, reações criptografadas, ver WA_MESSAGE_SECRETS.md) não estão entre os 9 campos, então não podem chegar a chats interop (inferido).

---

## 9. Grupos interop

### 9.1 Modelo (found)

Um grupo é `{gid}@interop.g.us` (tipo 28). Os membros são contas do WhatsApp (adicionadas como JIDs de usuário **LID**; found no caminho de adição, o caminho de criação inferido como igual) e JIDs interop. Os metadados do grupo vêm do MEX em vez de `w:g2`: `C11410Yt.A0F` chama `GroupXmppMethods/sendGetInteropGroupInfo` para o tipo 28. O estado é `UNSET`, `ACTIVE`, `SUSPENDED`; gids suspensos são mantidos na pref `suspended_interop_groups`. Banners do composer: grupo suspenso "You can't send messages to this group because all third-party members have left."; com opt-out ou removido "... because you're no longer a member."

### 9.2 Operações MEX (found; doc ids de `assets/whatsapp-android-mex_client_persist_ids.json`)

| Operação | doc_id | Campo raiz | Entrada | Saída / notas |
|-----------|--------|-----------|-------|----------------|
| `GroupsCreateInteropGroup` | `25726817620301611` | `xwa2_interop_group_create` | `input.participants[{jid}]` | `group`: `gid`, `creation_time`, `creator_v2`, `display_name`, `participants_v2`; nenhum assunto enviado |
| `LeaveInteropGroup` | `25346167795013271` | `xwa2_interop_group_leave` | `input.groups_to_leave[{gid}]` | `response_code` por grupo; {200, 400, 401, 403, 404, 405} tratados como finais |
| `AddParticipantsToInteropGroup` | `25732168276369451` | `xwa2_interop_add_participants_to_group` | `input.gid`, `input.participants[{jid}]` | membros do WhatsApp são mapeados de PN para LID primeiro; LID `null` aborta a chamada |
| `QueryInteropGroupInfo` | `32734144032867938` | `xwa2_interop_group_query_by_id` | `group_input.gid` | `state`, `gid`, `creation_time`, `creator_v2`, `participants_v2` |
| `InteropPrivacySettingsQuery` | `24849123668112654` | `xwa2_fetch_wa_users` -> `interop_privacy_settings` | `interop_privacy_settings_query_input{feature, dhash}` para o próprio LID | `settings_data`, `dhash`, `denied_contacts[{jid}]` |
| `InteropPrivacySettingsUpdate` | `25421856497452763` | `xwa2_interop_privacy_setting_update` | `feature`, `setting` | `success` |
| `InteropPrivacySettingWithContactListUpdate` | `24913399124998598` | `xwa2_interop_privacy_setting_with_contact_list_update` | `contact_list_type`, `contacts`, `dhash` (`none` se ausente), `feature`, `setting` | `success` |

Erros de criação e adição aparecem como "This group couldn't be created" / "Make sure everyone you add to this group has third-party chats turned on." / "A group with these members already exists." (strings found). Criar um grupo exige pelo menos um usuário do integrador escolhido ("To create this third-party group, you need to select at least one %1$s user.").

### 9.3 Notificações MEX (found, `C0WQ`)

| Notificação | Handler | Efeito |
|--------------|---------|--------|
| `NotificationInteropGroupCreateUpdate` | branch de `AbstractC23194A0r` (log `CreateInteropGroupNotificationHandler/`) | cria o grupo local a partir de `gid`, criador e participantes |
| `NotificationInteropGroupParticipantsUpdate` (`Xwa2NotifyInteropGroupOnParticipantChange`) | `A0B` | adiciona participantes com source `general_chat_auto_add`, remove participantes que saíram; retorna cedo (`no updates needed to gid=`) quando `C22300su.A15()` é false |
| `NotificationInteropGroupPropertyUpdate` | `A0C` | `state` ACTIVE ou SUSPENDED -> `suspended_interop_groups` |

### 9.4 Quem pode me adicionar (found, feature `GROUPADD`)

Enum de configuração `C9U8`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALL`, `MYCONTACTS`, `MYCONTACTSEXCEPT`, `MYCONTACTS_AND_ENABLED_INTEROP_INTEGRATORS`, `NONE`. A variante com lista de contatos carrega a lista de negação (`contact_list_type`, `contacts`). Texto: "You can only be added to third-party chats by people who either use or have selected the same messaging app." A configuração é armazenada por LID próprio e cacheada com `dhash`; a aplicação é no servidor (inferido), o cliente apenas apresenta a configuração.

---

## 10. Lista de chats, modelo de thread, UI

| Item | Fato (found) |
|------|--------------|
| Thread | um chat por JID interop (1:1) ou por gid; armazenado nas tabelas normais de chat; sem tabela de thread separada |
| Pasta | `InteropConversationsActivity` / `Fragment`; view de cabeçalho `InteropView` na lista de chats (`C31071Ju`, log `ChatListInteropChatsDelegate/`); exibida quando elegível e aviso aceito, ou quando já existem chats interop; oculta quando a caixa de entrada é COMBINED |
| Modo de caixa de entrada | SEPARATED: pasta dentro da caixa principal ou do menu "More"; COMBINED: chats interop listados na aba Chats (chip de filtro `interop` nos filtros de chat, `THIRD_PARTY_FILTER`) |
| Linha / busca | rótulo com nome do integrador e badge de ícone no avatar; chats de terceiros não são incluídos nos resultados de busca |
| Banner / badge | "You're messaging someone outside of WhatsApp. Third-party apps may have different security."; badge da Home de `pref_interop_badge_*`, controlado pela AB 7495 (`C230679y0`) |

---

## 11. Baileys (`baron-baileys-v2` 1.5.17, `src/Socket/interop.js`, `WABinary/decode.js`, fonte lida, nada testado)

| Tópico | Baileys | Android 2.26.41.6 |
|-------|---------|-------------------|
| Integradores | `12` (BirdyChat, email) e `13` (Haiket, pn) embutidos | nenhum no cliente; lista do servidor |
| Consulta em lote | `INTEROP_BATCH_MAX = 256` | **20** (builder da requisição e parser da resposta) |
| Opt-out | `<opt_out_integrators><integrator_list>` | nenhum nó assim; IQ de opt-in com lista menor |
| Reachability set | `<reachability_settings enabled><user external_id integrator_id/>` | filhos `<integrator id/>` |
| Consentimento | IQ `tos` `trackable id=20240306 result=105`, depois `160` | aviso 20240306 estágio 160 = aceito (found); forma na rede do IQ do aviso não rastreada |
| JID binário | o reader da tupla 244 lança exceção a menos que domain = 0; tag 245 tratada | tag 244 com domain 0 **e** 2 (grupos); sem tag 245 |
| Notificações | `type="interop"` com `stella_interop_enabled`, `peer_device_presence`, `ig_profile`, fbid | o handler `w:interop` id 270 trata somente `ping` |
| Envio / recebimento | texto simples como `conversation`, reporting token pulado; comentário em `Defaults/index.js`: recebimento interop não implementado | serializer restrito aos 9 campos; parser estrito `InteropMessage`; ids MEX de grupo e notificações idênticos em escopo |

Por que falha (inferido do código comparado acima):

| Sintoma | Causa | Correção |
|---------|-------|-----|
| Erro de decode em JID de grupo interop | o reader de tupla rejeita o byte de domínio 2 | aceitar o domínio 2 -> `{gid}@interop.g.us`, exigir device e integrator 0 |
| O peer descarta a mensagem com falha de campo desconhecido | qualquer campo fora dos 9 (por exemplo `messageContextInfo` com um `messageSecret`, `protocolMessage`) falha se o peer executa o mesmo parse estrito (inferido; envios interop do Baileys não foram rastreados para esses campos) | montar o `Message` somente com os campos 1, 2, 3, 6, 7, 8, 9, 46 (e 66) |
| O opt-out não tem efeito | `opt_out_integrators` não existe no cliente | enviar SetOptInIntegrators com os ids restantes |
| Nada chega em sessões companion | contatos interop têm somente device 0 | manter o interop na sessão primária |

---

## 12. Casos de erro

| Sintoma | Causa | Onde |
|---------|-------|-------|
| Telas interop fecham imediatamente ou nunca aparecem | `C32001Oa.A02()` false: flag 7495 desligada, conta dependente ou dispositivo companion | 2.1 |
| "Apps can't be saved right now" | falha de SetOptInIntegrators; os códigos 500 / 810 / 800 recebem o texto "try again later" | 5.3 |
| "This user can't be found" | FetchUsers `item-not-found` (404) | 7.1 |
| Exceção de JID interop inválido | integrator fora de 1-3 dígitos / `0` à esquerda, account fora de 1-15 dígitos, índice de dispositivo diferente de 0 | 3.1 |
| Grupo não criado / composer desabilitado | erro MEX de criação ou conjunto de membros duplicado / opt-out, grupo suspenso, não é mais membro | 9.1, 9.2 |
| Mensagem recebida descartada, motivo 70 / 13 / 14 / 16 / 17 / 76 / 26 | campo desconhecido ou tipo sem handler / tamanho inválido / tamanho de hash inválido / media key ausente / mime inválido / tipo de reação divergente / exceção de parse | 8.2, 8.3 |
| SKDM de grupo ignorado | AB 38723 desligada (log `sender key distribution message skipped`) | 8.1 |
| Nomes de integrador ausentes após erro de envio | o ack de erro apagou `integrator_display_name` | 4.2 |

---

## 13. Distinções-chave

| Não confundir | Fato |
|----------------|------|
| `w:interop` vs USync | a descoberta de contatos é FetchUsers em `w:interop` (máx. 20), não um protocolo USync |
| `@interop` / `@interop.g.us` / `@g.us` | usuário e dispositivo, grupo, grupo nativo; um JID interop nunca é mapeado para LID ou PN |
| `InteropMessage` vs `Message` | o recebimento aceita 9 campos; o envio omite contexto e padding para interop |
| token de privacidade `trusted_contact` | job genérico de privacy-token (WA_TCTOKEN_CSTOKEN.md); nenhum código específico de interop foi encontrado nesta build |
| "interop" do UPI | `IndiaUpiInterOpHybridActivity`, `IndiaUpiInteropSendToUpiActivity`, flags de nota de pagamento `isInterop` são funcionalidades de pagamentos, sem relação |
| "interop" de Compose / EXIF | `androidx.compose.ui.viewinterop`, `InteroperabilityIFDPointer` são bibliotecas |
| Elegível vs com opt-in vs consentimento | flag 7495 = elegível; `opted_in` por integrador vem do servidor; consentimento = aviso 20240306 estágio 160 |

---

## 14. Fluxo completo

```
[User]              [Client]                                   [WA server]              [Integrator app]
  │ Settings > Third-party chats
  ├──────────────────► A02(): flag 7495, primary, not dependent
  │                    notice 20240306 != 160 ──► show ──► accept ──► stage 160
  │ apps (+ inbox type, + group privacy)
  ├──────────────────► SetOptInIntegrators ─────────────────► opted_in list; table rewritten
  │ New chat > app > id
  ├──────────────────► FetchUsers (1..20) ──────────────────► jid 12-<account>@interop / 404 / 403 / 500
  │ send text / image / video / audio / doc / reaction
  ├──────────────────► restricted Message (no context, no padding), Signal encrypt, device 0
  │                    <message to=..@interop> ─────────────► bridge (inferred) ───► [Integrator app]
  │                    <message from=..@interop><enc/> ◄──────────────────────────── reply
  │                    ENP -> DecryptionCallbackInterop -> DTF parse (unknown field -> 70) -> FBx -> FMessage
  │ ◄──────────────── chat row, notification
  │                    <notification xmlns=w:interop><ping/> ◄─ server (trigger inferred)
  │ ◄──────────────── local notification "Manage requests"; reachability per integrator
  │ New group (flag 15732)
  ├──────────────────► GroupsCreateInteropGroup (LID + interop JIDs) ──► gid@interop.g.us
  │                    MEX notifications: create / participants / property; SUSPENDED -> composer blocked
```

---

## 15. Incógnitas

| Tópico | Estado |
|-------|-------|
| Forma na rede do IQ do aviso de consentimento | não rastreada; somente os estágios 160 (aceito) e 162 (gravado pelo migrator) são conhecidos |
| Bridge no servidor, entrega ao integrador, tratamento de chaves nesse lado | não visível no cliente; o cliente usa sessões Signal e sender keys comuns |
| Mudança de identidade / safety number para contatos interop | não rastreado |
| Chamadas, enquetes, edições, revogações, mudança de identidade / safety number para chats interop | nenhum caminho de código interop encontrado (nenhuma string interop no código de chamadas); não rastreado |
| Recebimento de PTV (`ptvMessage`) | campo aceito, nenhum parser encontrado |
| Literal 491 no caminho de falha; códigos de erro 810 / 800; gatilhos de FetchIntegrators além da tela de opt-in | não resolvido |
| Leitores das flags 3953, 5759, 6613, 18670, 20999, 11518, 13532, 14070 | sem leitor literal; podem ser lidas por descriptors |
| Confirmações de leitura para contatos interop | `ClientPayload.interopData` (campo **38**, `C38671hT`: `accountId` 1, `token` 2, `enableReadReceipts` 3) existe no schema; nada nesta build o preenche |
| Se o servidor aplica a regra da Região Europeia | somente texto de UI; sem verificação no cliente |
