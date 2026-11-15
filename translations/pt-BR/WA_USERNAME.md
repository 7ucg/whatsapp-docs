<!-- src-sha1: 73855f4f8148d9b0ef853f43cef4adbe0cb996a5 -->
# WhatsApp Username — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-17
**Escopo:** verificação/definição/reserva/exclusão de username, chave de username (PIN), relação com LID, privacidade e visibilidade, operações GraphQL w:mex (doc_ids, variáveis, respostas), notificações, busca USync, regras de validação, feature flags, notas Baileys

---

## 1. O que é um username (tecnicamente)

Um username é um identificador do lado do servidor vinculado a uma conta, usado para que um contato possa ser alcançado sem expor o número de telefone. Todas as afirmações são análise estática do APK decompilado. Tier: **found** = lido em código ou assets, **inferred** = deduzido do código, **unknown** = não resolvido.

O recurso é construído sobre três camadas:

| Camada | Transporte | Usado para |
|-------|-----------|----------|
| Gerenciamento próprio | IQ `w:mex`, GraphQL persistido (config `whatsapp-android-mex`) | verificar, definir/reservar/excluir, obter, chave (PIN) definir/excluir, verificação múltipla |
| Busca de outros | USync (`xmlns="usync"`) e a variante MEX `UsyncQuery` | resolver `@username` (+ chave) para um LID, buscar o username de um JID conhecido |
| Push | Notificações MEX | `UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification` |
| Entre dispositivos | sincronização de app-state (`SyncActionValue`) | `username_chat_start_mode`, `lid_contact_action` (carrega `username`) |

| Entidade | Nome na 2.26.41.6 | Papel |
|--------|----------------|------|
| Gerenciador de username | `C122815Lj` | chamadas `UsernameGet`, `UsernameSet`, atualização de estado local, hook de rate-limit |
| Verificação de disponibilidade | `C67402tT` | chamada `UsernameCheck` + mapeamento de resposta |
| Verificação múltipla | `C76333Kg` | `UsernameCheckMulti`, blocos de 10 |
| API de chave | `MexUsernamePinProtocolApi` | `UsernamePinSet` (definir/excluir chave) |
| Estado local / prefs | `C5Q8` | `username_reservation_state`, `username_pin`, `is_username_revoked` |
| Enum de estado | `C4DU` | `UNSET`, `RESERVED`, `ACTIVATED`, `CREATED` |
| Modo de elegibilidade | `C224069kP.A00()` -> `C9SR` | `CREATION`, `RESERVATION`, `COMPANION_READ_ONLY`, `DISABLED` |
| Armazenamento de rate-limit | `C67942uO` | backoff após 429 / 503 / 529 |
| Validador local | `C82003fB.A04`, `C1187754z` | comprimento, charset, regras de ponto, regex |
| Validador de chave | `C1176550d` (+ `AbstractC111284pZ`) | formato de chave |
| VM de entrada de chave | `UsernamePinEntryViewModel` | submeter chave para um username de outra pessoa |
| Cliente USync | `C23638AId` (`querySyncUsernameWithErrorInfo`), `C18670m9` | construtor/parser de stanza usync clássico |
| USync MEX | `C229259vZ`, `O0F` | `UsyncQuery` com `include_username` |
| Handlers de notificação | `C49822Lvi`, `C49821Lvh`, anônimo `X.2YG` em `AbstractC20380p4` | definir/excluir/atualizar |

Nomenclatura: o nome voltado ao usuário do PIN é **chave de username** (strings "Username key", "Add a username key to control who can contact you"). O wire e o código dizem `pin`.

---

## 2. Operações MEX (doc_ids)

### 2.1 Onde os doc_ids vivem

doc_ids não são literais em `java_src`. O cliente envia o nome da operação (`"UsernameSet"`, ...) com o nome de config `"whatsapp-android-mex"` (found, `C16880is`). O id numérico é lido de `assets/whatsapp-android-mex_client_persist_ids.json`: `EnumC17010j7.WHATSAPP_ANDROID_MEX` mapeia para esse arquivo, `C17040jA.CMg(op)` retorna o campo `doc_id`, `AGb(op)` o campo `client_doc_id` (found). Qual dos dois acessores preenche o atributo `query_id` não foi rastreado até o fim (unknown); capturas anteriores na 2.26.26.4 mostram `query_id` igual a `doc_id`.

Os doc_ids abaixo são **found** no asset da 2.26.41.6:

| Operação | doc_id | Tipo | Ponto de chamada | Classe de resposta |
|-----------|--------|------|-----------|----------------|
| `UsernameCheck` | `26124072630599518` | query | `C67402tT.A00` | `C2IG` |
| `UsernameCheckMulti` | `27134626522840286` | query | `C76333Kg.A00` | `C2IE` |
| `UsernameGet` | `32618050064506055` | query | `C122815Lj.A02` | `C87173nz` |
| `UsernameSet` | `27108705368767936` | mutation | `C122815Lj.A00` | `C87183o0` |
| `UsernamePinSet` | `25529696019976770` | mutation | `MexUsernamePinProtocolApi.A00` | `C48557LJz` |
| `UsernameGetRecommendationsQuery` | `26077456248616957` | query | nenhum encontrado | unknown |
| `UsyncQuery` | `38635300486116501` | query | `C229259vZ.A01` | `C2IQ` |

Notas:
- `UsernameGetRecommendationsQuery`: o nome ocorre apenas no JSON do asset. Nenhuma classe em `java_src` o referencia por string (found). Variáveis e resposta são unknown.
- Os três nomes de notificação (`UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification`) não têm nenhuma entrada no asset de persist-id. São tipos de notificação, não requisições (ver 7).
- O asset tem `operation_name_hash`, `operation_text_hash` e `client_doc_id` por op. Exemplo `UsernameSet`: `client_doc_id` `427995565715419341100134328918` (found).

### 2.2 Envelope

Construído em `C19370nI` / `C19310nC` (found):

```xml
<iq to="[server jid]" xmlns="w:mex" type="get" id="...">
  <query query_id="DOC_ID">{"queryId":"DOC_ID","variables":{...}}</query>
</iq>
```

| Campo | Regra (código) |
|-------|-------------|
| `xmlns` | `w:mex` |
| `type` | `get` para toda operação, incluindo mutations |
| atributo `query_id` | definido apenas se tiver 1 a 20 chars |
| corpo | JSON `{"queryId": ..., "variables": {...}}`, 1 a 8448000 bytes |
| variáveis nulas | `C16770ig.A03(k, null)` e `A02(k, null)` pulam a chave, então um valor ausente significa que a chave não é enviada |

Stanzas de wire de sessões reais não são reproduzidas aqui; esta build foi analisada apenas estaticamente.

---

## 3. Operações em detalhe

### 3.1 UsernameCheck

Variáveis (found, `C67402tT.A00`):

| Variável | Tipo | Condição |
|----------|------|-----------|
| `username` | string | sempre |
| `include_suggestions` | bool | sempre (a UI passa `false` no caminho de verificação tipado `C64H` case 21) |
| `source` | string | apenas se não-nulo |
| `session_id` | string | apenas se não-nulo |

Mapeamento de `source` (`AbstractC78993Wd.A0U`): int 1 -> `FB`, 2 -> `IG`, 3 -> `USER_INPUT`, 4 -> `SUGGESTION`, outro -> null (não enviado).

Caminho de resposta (found, ramo padrão de `C77183Np`): `data.xwa2_username_check`

| Campo | Tipo | Uso |
|-------|------|-----|
| `result` | enum `EnumC59782gh` | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `INVALID`, `SUCCESS` |
| `suggestions` | list<string> | lido apenas quando `INVALID` |
| `rejection_reasons` | lista de `C4G8` | lido apenas quando `INVALID` |
| `suggestions_eligible` | bool | padrão `true` quando o campo é nulo |

Valores de `C4G8` (found): `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALREADY_TAKEN`, `REQUIRE_FB_ACCOUNT_LINKING`, `REQUIRE_FB_CONSUMER_ACCOUNT_LINKING`, `REQUIRE_IG_ACCOUNT_LINKING`, `REQUIRE_IG_CONSUMER_ACCOUNT_LINKING`.

Mapeamento: `SUCCESS` -> `C76283Kb` (disponível); `INVALID` -> `C76303Kd` (indisponível, carrega sugestões + motivos); `UNSET` -> nenhum dos ramos atribui um resultado (o callback recebe a variável anterior/nula; comportamento unknown). Backoff local ativo -> `C76293Kc` (erro com código de rate-limit das prefs, ver 5.3); o callback de falha da própria requisição não foi lido.

Os motivos de rejeição conduzem o texto de vinculação de conta ("This username matches an account on Facebook/Instagram. To use it ... add your accounts to Accounts Center", `C82003fB`). Em `C82003fB` qualquer motivo diferente de `UNSET` dispara o caminho de erro local com o código 40601 (`A08(40601L)`); uma lista vazia ou apenas `UNSET` mostra "Username isn't allowed." O fluxo de controle exato em torno do loop está apenas parcialmente decompilado (inferred).

### 3.2 UsernameCheckMulti

| Variável | Tipo | Notas |
|----------|------|-------|
| `usernames` | **list<string>** | array via `A00.A0B("usernames", list)`; o catálogo de doc_id a tipa como `str`, o código envia uma lista |

Loteamento (`C76333Kg.AG5`): a lista é dividida nos primeiros 10 e no restante; o restante é processado após um atraso da flag **29327** (padrão 60, unidade não resolvida). Lista vazia retorna um mapa vazio sem requisição.

Caminho de resposta `data.xwa2_username_check_multi.results[]` (found): cada item tem `username` e `response.result` (mesmo `EnumC59782gh`). Mapeamento: `SUCCESS` -> disponível, `INVALID` -> indisponível (sem sugestões, `suggestions_eligible=false`), qualquer outra coisa -> erro. Nomes ausentes do resultado são marcados como erro.

Consumidor: `UsernameAvailabilityCache` armazena `EnumC59192fk` (`UNKNOWN`, `AVAILABLE`, `UNAVAILABLE`) por nome. Propósito (prefetch para sugestões de username do Facebook / Instagram, string `foa_username_prefetch_cache`) é inferido.

### 3.3 UsernameSet (criar / alterar / reservar / excluir)

Variáveis (found, `C122815Lj.A00`):

| Variável | Tipo | Condição |
|----------|------|-----------|
| `username` | string | omitido quando nulo (**exclusão**) |
| `reserved` | bool | sempre enviado |
| `session_id` | string | apenas se não-vazio (`C1YW.A08`) |
| `source` | string | apenas se o int de source for não-nulo (ver 3.1) |
| `pin` | string | apenas se não-nulo |

`reserved` é computado, não constante (found). Argumento `z` (força) = true dá `false`. Caso contrário: estado atual `ACTIVATED` ou `CREATED` dá `false`; estado atual `RESERVED` ou modo de elegibilidade `RESERVATION` dá `true`; todos os outros casos dão `false`. Então `reserved:true` só é enviado para contas em modo de reserva ou que já possuem uma reserva.

Exclusão é um modo da mesma operação: `username == null` -> tag de log `delete`, senão `set` (também em `MexUsernamePinProtocolApi` para a chave). Com um username nulo a chave `username` não está nas variáveis (found).

Guarda do lado do cliente: antes de enviar, se o armazenamento de rate-limit reporta um backoff ativo, a chamada falha localmente com `username_creation_rate_limit_error_code` e o texto "rate limit expiration time not reached" (found, `C122815Lj.A03`).

Tratamento de sucesso (`C122815Lj.A01`, found):

| Condição | Estado local escrito (`username_reservation_state`) |
|-----------|----------------------------------------------------|
| username nulo ou vazio | `UNSET`, pref de chave limpa |
| `reserved` era true | `RESERVED` |
| flag de ativação | `ACTIVATED` |
| senão | `ACTIVATED` se o estado era `ACTIVATED` e o nome é igual ao nome armazenado, senão `CREATED` |
| int de `source` é 1 ou 2 | pref `username_set_via_account_linking` = (int == 2) |
| `pin` enviado | pref `username_pin` atualizada |
| flag teen | pref `is_teen_account` = true |

A escrita de pref é `Voip.REJECT_REASON_DECLINED`, que é a string vazia `""` nesta build (found).

Tratamento de erro (`C138725uA` case 2):

| Código estilo HTTP | Ação do cliente |
|----------------|---------------|
| 429, 503, 529 | backoff armazenado (5.3) |
| 304 | tratado como sucesso ("não modificado"), o estado local ainda é atualizado |
| sem conexão (`C213639Bb`) | resultado `C4BO` "no network" |
| outro | `C4BN(code, message)` |

### 3.4 UsernameGet

Variáveis: nenhuma (a chamada constrói um conjunto de variáveis vazio, found, `C122815Lj.A02`). Marcado `@Deprecated`, substituído por uma variante suspend.

Resposta (found, `C138815uJ` case 34): `data.xwa2_username_get.username_info`

| Campo | Uso |
|-------|-----|
| `username` | armazenado; string vazia se ausente |
| `state` | `C4FC`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `RESERVED` |
| `pin` | **a chave é retornada em texto claro e armazenada na pref `username_pin`**; string vazia se ausente |

Mapeamento de estado: `RESERVED` -> `C4DU.RESERVED`; `ACTIVE` -> `ACTIVATED` se o username armazenado for igual ao retornado e o estado local era `RESERVED` ou `ACTIVATED`, senão `CREATED`; estado nulo ou `username_info` nulo -> `UNSET`.

Caso de erro 404 do servidor limpa o username local, a chave e o estado (log `clearSelfUsernameData NOT_FOUND`).

Se a chamada é usada como heartbeat é unknown; a nota antiga "polling heartbeat" não é suportada pelo código desta build.

### 3.5 UsernamePinSet (chave de username)

Variáveis (found): `pin` (string), omitido quando nulo.

| Ação | Variáveis |
|--------|-----------|
| definir chave | `{"pin": "<key>"}` |
| excluir chave | `{}` (`A02` chama `A00(null)`) |

O nome da operação para ambos é `UsernamePinSet`; não existe nenhuma operação de verificação separada. A verificação de uma chave de outra pessoa é feita em USync (4). Não conectado: retorna `C213639Bb("UsernamePinSet")` sem requisição.

A chave também pode trafegar em `UsernameSet` (variável `pin`). `C81793ej.A0x` usa `UsernameSet` com o username existente e o novo `pin` quando um username já está armazenado localmente (`A00 != null`), e `UsernamePinSet` caso contrário (found).

A classe de resposta `C48557LJz` não tem nenhum acesso de campo nos arquivos lidos; o formato da resposta é unknown.

---

## 4. Busca de outros usuários

### 4.1 USync clássico por username (fluxo de chave)

Construído em `C18670m9.A06` (o jadx falhou neste método, lido a partir do smali `X/0m9.smali`). Por entrada de requisição `C222649hm`: campo `A0C` = username, `A0D` = chave, `A05` = LID.

Atributos do nó filho contact (found no smali): `username` sempre; `lid` quando um LID é conhecido localmente; `pin` quando uma chave está definida. Os atributos extra são controlados pela flag **12402** (padrão `false`): quando a flag está desativada, apenas `username` é escrito (found). O nome do nó `contact` é inferido a partir do parser de resposta, que lê o filho `contact` e seu atributo `username` (`C18670m9` linhas ~969-975).

```xml
<iq xmlns="usync" to="[server]" type="get">
  <usync mode="query" context="interactive" sid="..." index="0" last="true">
    <list>
      <user><contact username="name" lid="LID" pin="KEY"/></user>
    </list>
    <query><contact/> ... </query>
  </usync>
</iq>
```

Ponto de entrada: `C23638AId.A0G(username, key)` (`querySyncUsernameWithErrorInfo`), chamado por `submitPinForUsername`. Tipo de sincronização `EnumC21760rz.A0J`, timeout de 32000 ms. O conjunto de atributos `contact`, `pin`, `username` está nos conjuntos de redação de log de `AbstractC40921lc` (found).

Pré-resolução local: `A0M.Aol(username)` busca `lid_row_id` na tabela `lid_display_name` onde `UPPER(username) = UPPER(?)`, linha mais nova primeiro (found, `C1S0`). O LID, se conhecido, vai no atributo `lid`.

### 4.2 Avaliação de resultado (entrada de chave)

`UsernamePinEntryViewModel$submitPinForUsername$1` (found):

| Resultado | Condição |
|---------|---------|
| chave correta | o `UserJid` resultante é um LID (`C14080dr`) |
| chave errada | o resultado não tem LID: log `[un-pin] incorrect PIN`, texto de erro "Wrong key entered" |
| sem rede | `C9qA` código 1 |
| erro genérico de infraestrutura | `C9qA` código 2 |
| rate limit do requisitante | `C225769os.A01` true: "Too many attempts made. Try later." |
| rate limit do requisitado | `C225769os.A00` true: "This account can't be reached with their key right now..." |

A verificação de rate-limit cacheada do lado do cliente roda primeiro quando a flag **16033** está ativa e a config JSON **21995** tem `enable_key_rate_limit` true (padrão true): `C30P.A00` contra o próprio LID e contra o username alvo. O username tem o `@` removido (`C0CX.A0i(username, '@')`).

Em caso de sucesso o resultado é um **LID**, o chat é então endereçado ao LID (inferido a partir da verificação `C14080dr`; a etapa de abertura do chat não foi rastreada).

### 4.3 Buscar o username de um LID conhecido

`C23638AId` (linha ~600-650) constrói um usync com `<list><user jid="LID"/></list><query><contact/><username/></query>`, modo/contexto de `EnumC21760rz.A0J` (found). O parser lê `username` como filho do resultado de `<usync>` (`C18670m9` linha 586, apenas quando a requisição o solicitou).

### 4.4 USync MEX (`UsyncQuery`)

`C229259vZ.A01` constrói `UsyncQuery` (doc_id acima). Partes relevantes (found):

| Variável | Uso |
|----------|-----|
| `query_input[]` | uma entrada por usuário: JID (`C493020r.A0C`), opcional `client_known_username` (apenas quando o username é solicitado e não-vazio) |
| `include_username` | bool, definido quando qualquer entrada solicita o username |
| `include_lid` | bool, solicita `lid_info` |
| `telemetry.context` | contexto USync em minúsculas |

Resposta por usuário: `jid`, `username_info`, `lid_info` (`O0F`). `username_info` é polimórfico por hash de tipo: um tipo valor contendo `username`, ou um tipo status com `status` de `EnumC216389Tz`: `EMPTY`, `NOT_ALLOWED`, `NO_CHANGE` (+ não definido). `NOT_ALLOWED` é logado como "username not allowed to be queried" e limpa o username armazenado; `NO_CHANGE` o mantém. `lid_info.lid_jid` carrega o LID.

Gate: `ContactSyncHelper` recusa o caminho MEX com o log "cantUseMex as username ab prop is off" a menos que a flag **8421** esteja ativa quando um username é solicitado (found; padrão `false`).

---

## 5. Validação, limites, erros

### 5.1 Formato de username (local)

Validador `C82003fB.A04` (found), verificações nesta ordem:

| Ordem | Verificação | Id de erro (`C02U`) | String de mensagem |
|-------|-------|-------------------|----------------|
| 1 | cada char em `[A-Za-z0-9_.]` | 2 | "must start with a letter and can only contain letters, digits, periods and underscores" |
| 2 | comprimento >= mín (flag **20494**, padrão 3) | 0 | "Use between %1$d-%2$d characters" |
| 3 | comprimento <= máx (flag **20459**, padrão 35) | 1 | mesma string |
| 4 | sem `.` inicial, sem `.` final, sem `..` | 3 | "can't start or end with a period or have 2 periods in a row" |
| 5 | pelo menos uma letra ASCII | 4 | "Choose a username with at least one letter" |
| 6 | regex (abaixo) | passa ou falha com 2 | n/a |

Regex construída por `C1187754z.A02()` (found):

```
^(?!.*\.\.)(?=.*[a-zA-Z])[a-zA-Z0-9_][a-zA-Z0-9_.]{MIN-1,MAX-1}(?<![.])$
```

A capitalização não é normalizada pelo validador; a busca local `Aol` compara com `UPPER()`, então a correspondência é sem distinção de maiúsculas/minúsculas localmente (found). Se o servidor trata nomes sem distinção de maiúsculas/minúsculas é unknown. Underscore inicial é permitido pela regex; o texto da UI diz "start with a letter", que é mais restritivo que a regex (found, incompatibilidade).

A UI também rejeita links da web: "Enter only your username, not a web link" (string presente, verificação não rastreada).

### 5.2 Formato da chave de username

`C1176550d.A00` (found): a flag **34350** é uma string regex, padrão `^([0-9]{4}|[A-Z0-9]{6})$`. Se a string da flag estiver vazia, o fallback é exatamente quatro dígitos. Regex inválida loga `[un-pin] invalid username_key_regex` e aceita qualquer coisa. Flags de limite de comprimento **34347** (mín, 4) e **34348** (máx, 6) alimentam apenas o caminho de mensagem de erro em `UsernamePinEntryViewModel.A0w`. Regras do lado do servidor são unknown.

Então a nota antiga "PIN de 4 dígitos" está incompleta: o padrão embarcado aceita quatro dígitos ou seis alfanuméricos maiúsculos.

### 5.3 Rate limits e backoff

`C67942uO` (found), ativo apenas com a flag **28678** (padrão `false`):

| Item | Valor |
|------|-------|
| gatilho | erro 429, 503 ou 529 de `UsernameSet` |
| duração | string estilo `Retry-After` parseada como int segundos (`C23680AJt.A00`), senão a flag **28127** (padrão 30) segundos |
| armazenamento | prefs `username_creation_rate_limit_backoff_expiry` (ms), `username_creation_rate_limit_error_code` |
| efeito | `UsernameCheck`, `UsernameCheckMulti`, `UsernameSet` falham localmente até a expiração |

### 5.4 Código de erro para mensagem (`C82003fB.A02`, found)

| Código | Mensagem |
|------|---------|
| 400 | "Couldn't save your username. Try again." |
| 403, 404, 429 | "Couldn't complete your request. Try again." |
| 500, 529 | "We couldn't complete your request. Try again later." |
| 503 | "... Please try again later." |
| 406, 40601 | "This username is not available." |
| 40602 | "You can't make more changes to your username. Try again later." |
| 40603 | "You can't make changes to your username right now. Try again later." |
| outro | "We couldn't complete your request. Try again." |

40601 a 40603 estão no conjunto permitido `AbstractC111104pH.A01` (apenas 40603 mostrado no código lido). Sua semântica do lado do servidor é unknown além do texto do cliente.

---

## 6. Relação com LID

Tudo found salvo indicação.

| Fato | Evidência |
|------|----------|
| Buscas de username resolvem para um **LID**, não para um JID de telefone | teste de sucesso de chave `userJid instanceof C14080dr` (classe LID); `lid_info.lid_jid` no usync MEX |
| Mapa local username -> LID | tabela `lid_display_name` (colunas `username`, `lid_row_id`), query em `C1S0` |
| Notificações identificam o usuário por LID | handlers de definir/excluir fazem parse de `LidUserJid` (texto de erro "Failed to parse LidUserJid") |
| Notificação de exclusão pode carregar um JID de telefone | o handler verifica `isPnPresent`; com PN presente ele faz cast de um JID de PN e age, sem PN ele retorna |
| Ação de sincronização de contato | `ContactAction` tem `username` (6) ao lado de `lid_jid` (3), `pn_jid` (5); também `LidContactAction` (`lid_contact`, campo 61 de SyncActionValue) |
| Modo de início de chat | campo **59** de SyncActionValue `username_chat_start_mode`, enum `EnumC50053M6w`: `LID` = 1, `PN` = 2. Apenas o codec de sincronização foi encontrado; nenhum consumidor no código de UI (unknown) |
| String de recurso de companion | ao vincular um companion o primário adiciona `username_supported` (flag 4745 ou 20189), `username_reservation_only_mode` (apenas 20189), `username_account_linking_enabled` (flag 21199) à sua lista de recursos (`C25056AqU`) |

Inferred: um usuário que existe apenas como username é alcançável apenas através do LID até que o proprietário compartilhe o número de telefone; as strings "If you continue, your phone number will show in existing username chats and calls" (diálogo de exclusão) suportam isso mas o caminho de exposição do PN não foi rastreado.

---

## 7. Notificações

Handlers estendem `AbstractC23194A0r` e são registrados em `AbstractC20380p4` (found):

| Notificação | Handler | Comportamento |
|--------------|---------|-----------|
| `UsernameSetNotification` | `C49822Lvi` | payload `xwa2_notify_username_on_change`: lê o LID (hash de campo 107143) e o username; armazena via `InterfaceC11470Yz.BNU(lid, username)`; se o contato existe e é do tipo correspondente, atualiza o contato (`C12440bB.A0W`) |
| `UsernameDeleteNotification` | `C49821Lvh` | payload `xwa2_notify_username_delete`: lê o LID e o PN (hash -983979708); com PN presente executa a atualização de exclusão (`C53594Nzh`) |
| `UsernameUpdateNotification` | anônimo `X.2YG` | lê um hash base64 do payload, constrói uma requisição USync com motivo `USERNAME_UPDATE_NOTIFICATION` e `EnumC21760rz.A0Q` (contexto `NOTIFICATION_SIDELIST`, modo `query`; ver WA_USYNC.md), log `usync triggered for hash` |

Texto mostrado ao usuário: "Your username has changed", "WhatsApp has assigned you a new username (%1$s)", ou seja, o servidor pode reatribuir um username (revogação, pref `is_username_revoked`, `revocation_banner_dismissed_<username>`).

---

## 8. Feature flags

Os IDs de flag são ids de AB-prop lidos através de `C08J` (padrões das tabelas de `C08J`). Todos os padrões abaixo foram lidos desta build.

| Flag | Tipo | Padrão | Controla |
|------|------|---------|----------|
| **4745** | bool | false | primário: criação de username (modo `CREATION`); também divulgado como `username_supported` |
| **20189** | bool | false | primário: modo apenas-reserva (`RESERVATION`); `username_supported` |
| **23817** | bool | false | companion: recursos de username em geral (senão `DISABLED`) |
| **21199** | bool | false | vinculação de conta (FB / IG) ativada, divulgada como `username_account_linking_enabled` |
| **16033** | bool | false | gate mestre para recursos de chave (`C79343Xx.A00`): rate-limit de chave, upsell de chave, visualização de username WABI |
| **21995** | JSON | `{}` | `enable_key_rate_limit`, `enable_key_upsell_flows`, `enable_wabi_username_view` (todos padrão true quando a chave JSON está ausente) |
| **8421** | bool | false | permite o `UsyncQuery` MEX para requisições de username |
| **12402** | bool | false | adiciona os atributos `lid` e `pin` ao nó `contact` do usync |
| **20494** / **20459** | int | 3 / 35 | comprimento mín. / máx. do username |
| **34350** | string | `^([0-9]{4}\|[A-Z0-9]{6})$` | regex da chave |
| **34347** / **34348** | int | 4 / 6 | limites de comprimento da chave (mensagem de erro) |
| **28678** | bool | false | ativa o armazenamento de backoff de rate-limit |
| **28127** | int | 30 | segundos de backoff padrão |
| **29327** | int | 60 | atraso antes do segundo lote de `UsernameCheckMulti` |

Elegibilidade de companion (`C224069kP.A00`, leitura no nível de bytecode):

```
companion (identity of the A02 check inferred from the "open WhatsApp on your primary device" strings):
  23817 off, or pref username_reservation_creation_supported_on_primary false  -> DISABLED
  pref username_account_linking_enabled_on_primary true                         -> COMPANION_READ_ONLY
  state RESERVED                                                                -> COMPANION_READ_ONLY
  state not UNSET                                                               -> CREATION
  state UNSET and pref username_reservation_only_mode_on_primary true           -> COMPANION_READ_ONLY
  state UNSET otherwise                                                         -> CREATION
primary:
  4745 on -> CREATION;  else 20189 on -> RESERVATION;  else DISABLED
```

As três prefs `*_on_primary` são lidas apenas aqui; onde são escritas não foi encontrado (unknown).

---

## 9. Privacidade e visibilidade

| Aspecto | Descoberta | Tier |
|--------|---------|------|
| Propósito | "Keep your phone number private with a username"; pessoas que não têm o número salvo veem o username em vez disso | found (strings) |
| Primeiro contato | com uma chave definida, pessoas "com quem você não interagiu" devem digitar a chave antes de contatar o username | found (strings) |
| Compartilhamento de chave | a ação de compartilhar username pode incluir a chave (pref `username_share_include_pin`, migrada em `C138535tr`); strings "Share your username and key" | found |
| Onde o número é ocultado | admins de comunidade e de canal veem o número a menos que um username esteja definido; seguidores de canal não veem nenhum dos dois | found (strings) |
| Telemetria de grupo / thread | campos `has_username`, `has_username_pin`, `is_username_thread` na telemetria de envio de mensagem (`DZ1`, `RQG`) | found |
| Chave em repouso | a própria chave é retornada por `UsernameGet` e armazenada em prefs em texto claro `username_pin` | found |
| Chats de terceiros | "Usernames and contacts added to third-party chats will not save to your phone" | found (string) |
| Business | "This username is only available on WhatsApp Business" aparece como texto de rejeição | found (string) |
| Quem pode consultar | o status `NOT_ALLOWED` do usync MEX mostra que o servidor pode recusar a divulgação de username por requisitante | found (enum), regra unknown |
| Menores | pref `is_teen_account`; textos para o pai "Your child created the username ..." | found |

Regras de visibilidade impostas pelo servidor (quem pode resolver um username, rate limits de chave, reatribuição) são unknown a partir do cliente.

### 9a. Controles de audiência de compartilhamento de número de telefone (novo na 2.26.45.10, found)

Um pacote `com.whatsapp.pnsharing` separado controla quem pode ver o número de telefone da conta, independente das próprias regras de visibilidade do username em 9. Duas novas operações `whatsapp-android-mex`, ambas `found` a partir de literais `const-string` simples no smali (sem necessidade de decompile, `PnSharingAudienceUpdater.smali` / `PnSharingListFetcher.smali` / `PnSharingListUpdater.smali`):

| Operação | doc_id | Tipo |
|-----------|--------|------|
| `UsernamePhoneNumberPrivacyUpdateMutation` | `28835748819379698` | mutation |
| `UsernamePhoneNumberPrivacyGetQuery` | `29264643203229836` | query |

A configuração de audiência é um dos 4 valores do enum compartilhado, não específico de pnsharing, `LX/BWW` (13 membros no total, apenas estes 4 alcançáveis a partir deste caminho de chamada):

| ordinal | membro de `LX/BWW` | valor de `setting` |
|---|---|---|
| 0 | `A02` | `ALL` |
| 1 | `A07` | `MYCONTACTS` |
| 2 | `A08` | `MYCONTACTSEXCEPT` |
| 3 | `A09` | `NONE` |

**`UsernamePhoneNumberPrivacyUpdateMutation` é incremental, não substituição completa.** Dois pontos de chamada a alimentam:

- `PnSharingAudienceUpdater.A00` — apenas alteração da configuração de nível superior, sem entradas de lista.
- `PnSharingListUpdater.A01` — adicionar/remover por entrada em uma das três listas de audiência.

Campos de nível superior (found):

| Campo | Tipo | Significado |
|-------|------|-----------|
| `setting` | string | `ALL` / `MYCONTACTS` / `MYCONTACTSEXCEPT` / `NONE`, ver tabela acima |
| `input` | objeto | payload aninhado, ver abaixo |

Campos de `input` (found, aninhados sob `allow_list` / `contact_exclude_list` / `deny_list` dependendo de qual das 3 configurações não-`MYCONTACTS` está ativa — `MYCONTACTS` não envia nenhuma chave de lista):

| Campo | Tipo | Significado |
|-------|------|-----------|
| `dhash` | string | hash de conteúdo da lista de audiência, usado para invalidação de cache / detecção de conflito (string de log "...changed since it was read" ao lado) |
| `entries` | lista de objetos | entradas incrementais ADD/DEL, não uma substituição de lista completa |

Campos de item de `entries[]` (found, construídos por `PnSharingListUpdater.A00(Integer, Integer)`):

| Campo | Tipo | Significado |
|-------|------|-----------|
| `entry_type` | string | `USER` ou `GROUP` |
| `operation` | string | `ADD` ou `DEL` |
| `group_jid` | string, nullable | definido apenas quando `entry_type=GROUP` |
| `pn_jid` | string, nullable | definido quando a entrada é um número de telefone puro (`PhoneUserJid`) |
| `user_jid` | string, nullable | definido quando a entrada é um `Jid` de contato resolvido |
| `username` | string, nullable | o campo existe no schema mas nenhum ponto de chamada observado o popula; propósito `inferred`: pareamento de um número de telefone ainda-não-contato com um nome de exibição, consistente com exceções estilo `UsernameSet` — `unknown` se algum chamador de fato o define |

Exatamente um de `group_jid` / `pn_jid` / `user_jid` é preenchido por entrada (found); os outros dois ficam nulos.

`UsernamePhoneNumberPrivacyGetQuery` é a contraparte do lado de leitura (found, `PnSharingListFetcher.smali`): uma única ida e volta em lote que busca as 3 listas de audiência de uma vez, cada uma indexada por seu próprio `dhash` (hash cacheado localmente, ou a string literal `"none"` se ausente) para validação de cache.

**doc_id não resolvido:** o catálogo de persisted-query também lista `PnSharingPhoneNumberFetch` (doc_id `29229648029980096`, tipo query). Fazer grep na árvore smali decodificada completa da 2.26.45.10 (todos os shards, não apenas `com/whatsapp/pnsharing/`) por este literal não retorna nenhum ponto de chamada — apenas o asset embarcado `whatsapp-android-mex_client_persist_ids.json` o referencia. O que a chama e o que ela envia são **unknown**. Candidata provável apenas pelo nome (**inferred**, não mais que isso): uma busca de visibilidade de número de telefone por contato/por grupo, ou seja, a contraparte de item único da query em lote de 3 listas acima — não confirmado.

---

## 10. Notas Baileys

O envelope em 2.2 é genérico; um cliente Baileys pode construí-lo. Isto é **inferred**, não testado aqui.

```ts
const variables = { username: 'name', include_suggestions: false, source: 'USER_INPUT', session_id: uuid }
await sock.query({
  tag: 'iq',
  attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '26124072630599518' },
    content: Buffer.from(JSON.stringify({ queryId: '26124072630599518', variables })) }]
})
```

| Risco | Motivo |
|------|--------|
| Deriva de doc_id | os ids pertencem ao asset desta build; outras builds podem diferir (unknown) |
| `session_id` | o código o envia quando presente; se o servidor exige o mesmo valor para verificação e definição é unknown |
| Atributos de chave | `lid` / `pin` em `contact` estão atrás da flag 12402; o servidor pode ignorá-los para clientes sem a flag (unknown) |
| Regras locais | comprimento, charset e regras de ponto são do lado do cliente; as regras do servidor são unknown |

---

## 11. Distinções importantes

| Não confundir | Diferença |
|----------------|------------|
| Chave de username vs. PIN de conta / 2FA | A chave de username (`pin` em `UsernamePinSet`, pref `username_pin`) controla o primeiro contato via username. Não está relacionada ao 2FA de registro |
| Variável `reserved` vs. `UsernamePinSet` | `reserved` pertence a `UsernameSet` e marca uma reserva; a chave tem sua própria op |
| Estado `RESERVED` | `C4DU.RESERVED` local / `state=RESERVED` do servidor é um nome retido ainda não usável; `ACTIVATED` e `CREATED` são usáveis |
| Exclusão | não existe nenhuma op de exclusão; `UsernameSet` sem `username` exclui; a exclusão de chave é `UsernamePinSet` com `{}` |
| Resultado de verificação `INVALID` | cobre já-usado, vinculação-necessária e problemas de formato; o detalhe está em `rejection_reasons` |
| Username vs. LID | username é um identificador; a identidade de endereçamento é o LID |
| Ints de `source` | 1 `FB`, 2 `IG`, 3 `USER_INPUT`, 4 `SUGGESTION`; não são os mesmos ints que os ids de erro `C02U` |
| doc_id vs. `client_doc_id` | ambos estão no asset; os ids capturados são iguais a `doc_id` |
| Notificações vs. ops | os três tipos `Username*Notification` são handlers de push, não requisições |
| Rótulos de outros repositórios | `25975613018777537` está ausente do asset de persist-id desta build; `25741205615468935` é `GetTextStatusList` nesta build. Nenhum dos dois é uma operação de username aqui |

---

## 12. Fluxo de ponta a ponta

```
[User]                [Client]                              [Server]
  │ type name           │                                      │
  ▼                     │                                      │
 local validate ────────┤ charset, 3..35, dots, regex (5.1)    │
  │ ok                  ▼                                      │
  │              UsernameCheck {username, include_suggestions,  │
  │                             source, session_id}  ─────────►│
  │                     │◄──── xwa2_username_check {result,    │
  │                     │       suggestions, rejection_reasons}│
  │ SUCCESS             │                                      │
  ▼                     ▼                                      │
 confirm ─────────► UsernameSet {username, reserved,           │
                      session_id, source, [pin]} ─────────────►│
                        │◄──── ok | 304 | 40601..40603 | 429/503/529
                        ▼                                      │
                  write prefs: state, username_pin             │
                  429/503/529 -> backoff (flag 28678)          │
                                                               │
 [Owner sets key] ► UsernamePinSet {pin} | {} (delete) ───────►│

 [Other user, first contact]
  │ enter @name + key
  ▼
 validate key (flag 34350) ► usync contact{username,[lid],[pin]} ──►[Server]
                        │◄──── user jid (LID) | no LID | rate-limit flags
                        ▼
              LID  = open chat addressed to the LID
              none = "Wrong key entered"
              limit = "Too many attempts" / "can't be reached"

 [Server push]
   UsernameSetNotification (lid, username)  -> update local map
   UsernameDeleteNotification (lid, pn)     -> update contact
   UsernameUpdateNotification (hash)        -> usync delta
```

---

## 13. Incertezas

| Tópico | Motivo |
|-------|--------|
| Acessor exato que alimenta `query_id` | consumidor de `doc_id` vs. `client_doc_id` não rastreado até o construtor do IQ |
| Formato de resposta de `UsernamePinSet`, `UsernameSet` | as classes de resposta não têm nenhum acesso de campo no código lido |
| `UsernameGetRecommendationsQuery` | nenhum ponto de chamada, nenhuma variável |
| Regras de username e chave do lado do servidor | o cliente só valida localmente |
| Significado de 40601-40603 no servidor | apenas strings do cliente encontradas |
| Origem das prefs `*_on_primary` | nenhum escritor encontrado |
| Efeito de `username_chat_start_mode` | nenhum consumidor encontrado |
| Padrão de uso de `UsernameGet` (heartbeat) | não suportado pelo código lido |
| Etapa de abertura de chat após uma chave correta | não rastreada além da verificação de LID |
| Tráfego real | apenas análise estática |
