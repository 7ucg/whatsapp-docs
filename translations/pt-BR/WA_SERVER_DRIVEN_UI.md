<!-- src-sha1: 193c35598b4e82f9c32a0c5d2cee4dbf2d708588 -->
# WhatsApp UI Orientada pelo Servidor — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** Telas e ações orientadas pelo servidor no Android: máquina de estados de ações Phoenix/FCS (IQ `xmlns="phoenix"`, tipos de estado, operadores de choice, registro de resources), telas Bloks (busca via GraphQL, doc ids e roteamento por app-id, payload JSON, function ids Lispy, namespaces de ações, component queries, caches), native flow messages (registro de botões NFM), WhatsApp Flows (bridge WebView, política de host do SecureWebView, JSON do flow), AI rich response e card FMX (o que não é orientado pelo servidor), scripts do navegador in-app (bridge iabjs e nonce), sandboxing e feature flags, relevância para o Baileys

---

## 1. O que é (tecnicamente)

O WhatsApp Android não tem um único motor de UI orientada pelo servidor. Existem quatro mecanismos independentes; cada um busca uma descrição em um servidor (ou a lê de uma mensagem) e aciona código nativo. Todas as afirmações vêm de análise estática do APK decompilado; nada foi capturado na rede. Tiers: **found** = lido no código ou nos dados, **inferred** = deduzido, **unknown** = não resolvido. Os nomes ofuscados mudam a cada build e foram re-resolvidos na 2.26.41.6.

| Mecanismo | Descreve | Portador | Renderizador / executor | Onde é usado |
|-----------|----------|----------|-------------------------|--------------|
| Phoenix (os nomes de classe dizem FCS "flow configuration service", tag de log FDS) | Controle de fluxo: estados `resource` / `choice` / `pass` / `succeed` / `subflow` | IQ `<iq xmlns="phoenix">` com filho `<fds>` | Máquina de estados `QKb`, handlers de resource (`AbstractC57917Pxu`) | Onboarding de pagamentos, address message, pesquisa de negócios, fluxos de cartão do Brasil |
| Bloks | Telas: árvore de componentes + scripts Lispy + component queries assíncronas | HTTPS GraphQL POST para `graph.<domain>/graphql` | Activities e fragments host Litho/RenderCore | Pagamentos, suporte, assinaturas, consentimento, vinculação do Accounts Center, minishops, pesquisas, consentimento de negócio do Meta AI |
| Native flow messages (NFM) | Botões em mensagens interativas (`nativeFlowInfo` name + JSON de params) | Mensagem (protobuf) | Despacho `C33370Efz` para cerca de 40 classes de ação | Botões CTA, `address_message`, `galaxy_message` (Flows) |
| Web app WhatsApp Flows | JSON de flow renderizado por um web app hospedado | HTTPS (`flows.whatsapp.net`) em um `SecureWebView` + um canal de mensagens `WhatsAppBridge` | `WaFlowsWebViewBottomsheetModalActivity` / `FlowsWebBottomSheetContainer` | Formulários de negócio (`galaxy_message`, flexible checkout) |

Pontos decisivos:

- Phoenix é a camada de controle, Bloks é a camada de visão. Um estado Phoenix `resource` com id `open_bloks_screen_graphql` abre uma tela Bloks; as ações Bloks `wa.action.phoenix.*` voltam para a máquina de estados (seção 3.5; ligação inferida a partir dos nomes).
- Bloks não é MEX nem IQ. É um POST GraphQL no estilo Meta (`doc_id` + `variables`) sobre HTTPS (found, `AbstractC40195HfH`). Phoenix é IQ. A classe de resultado da query do endpoint de Flows (`AnonymousClass456`) compartilha a base de parser de resposta do Bloks; seu transporte não foi resolvido (seção 4.5).
- O conteúdo do servidor não pode nomear código nativo arbitrário. Toda rota passa por um registro fixo: ids de resource Phoenix (15 no código), function ids Bloks (681 nomeados), nomes de botão NFM (39), métodos da bridge de Flows (30), allow-list de xmlns de IQ do Bloks (2 entradas).
- Nenhuma verificação de assinatura de payload foi encontrada para payloads Bloks ou Phoenix. `BloksTrustedPayload` (`verifiedRoot`) existe e tem zero referências (found, smali e Java).
- Não orientados pelo servidor: o card de confiança FMX (mensagem de sistema criada pelo cliente), a AI rich response (conjunto fixo de componentes protobuf), os três arquivos `assets/json/bloks_*_template.json` (scaffolds de loading/erro, não telas de produto).

Relatórios relacionados: AB props (IQ `abt`, ids de flags) em `WA_AB_PROPS.md`; AI rich response em `WA_META_AI.md` seção 6.3. Nenhum framework com nome Genie foi localizado (busca por strings; ausência não comprovada).

---

## 2. Máquina de estados de ações Phoenix

### 2.1 Componentes (found, nomes da 2.26.41.6)

| Papel | Classe | Notas |
|-------|--------|-------|
| Runtime | `QKb` | Tag de log `FcsStateMachine`; `A03` executa um estado, `A04` segue `next` ou desempilha, `A05` encerra |
| Gerenciador FDS | `C58392QJx` | Inicia uma config (`A08`), envia o IQ (`A07`), monta o mapa de estados a partir da resposta (`A01`) |
| Construtor de IQ | `C31107Dfz` (ctor com `C9E1`), `C9E1`, `C31085Dfd` | `xmlns="phoenix"` |
| Parsers de resposta | `F7J` (`<iq><fds>`), `F8I` (cases 17 a 20, 27, 28), `F7Y` resource, `F7Z` choice, `C34784F7b` pass, `C34783F7a` succeed, `C34785F7c` subflow, `C34786F7d` version_check | Parser genérico de esquema de atributos (`C197428ac`) |
| Estados parseados | `P2W` resource, `P2U` choice, `P2T` pass, `P2S` succeed, `P2V` subflow, `C31057DfB` version_check | Parte comum `P2Q`: `name`, `input_path`, `input_selector`, `next`, `result_selector`, `result_path` (`C33411Ege.A03`) |
| Estados de runtime | `C55819P7c` resource, `C55817P7a` choice, `C55818P7b` pass, `P7Z` succeed, `C55820P7d` subflow | Mapeamento em `C58392QJx.A01` |
| Base de resource | `AbstractC57917Pxu` | `A02()` = id do resource, `A04(...)` = executa com mapa de params, id padrão `throw_error` |
| Binding / registro | `C51E` (id + handler lazy), `InterfaceC148426Oz.CP3()`, união `C138515tp` | Registros: `C135435oi`, `C135425oh`, `C135415og`, `C53207NpW`..`C53211Npa` |
| Operadores / erros / callback | `RsJ` (28 operadores), `AbstractC56245PPq`; `Q6G` (`catch`); `C57560Pry` (`A00(error, result)`, `A01(result)`) | |

### 2.2 Busca: IQ (found, `C31107Dfz`, `C58392QJx.A07`)

```
<iq xmlns="phoenix" type="get|set" id="...">
  <fds config="<config name>" state="<start state>" parameters="<json>">
    <context ... parameters='{"session-id":"...","bloks-versioning-id":"13c6e3b8...(64 hex)"}'/>
  </fds>
</iq>
```

| Item | Valor | Tier |
|------|-------|------|
| `type` | `get` ao iniciar (`A08`), `get` ou `set` para o resource `send_fds_iq` | found |
| Ints de tipo de IQ / timeout | 302 (get), 303 (set), 32000 ms | found |
| `state`, `parameters` | só escritos quando não vazios; `parameters` = JSON das entradas não nulas | found |
| `bloks-versioning-id` | string constante de 64 hex, mesmo valor em todo construtor de requisição Bloks (seção 3.2) | found |
| Aninhamento do nó de contexto | `<context>` carregando o JSON; aninhamento exato do nó interno não resolvido | unknown |

Resposta (found, `F7J`, `F8I`):

| Elemento | Conteúdo | Usado para |
|----------|----------|------------|
| `<fds>` attrs `state`, `parameters` | dica de início | parseado, não rastreado adiante |
| `<states start_at="...">` + `<state ...>`+ | o programa (seção 2.3) | init de `QKb`, log `initializeStateMachine num_states` |
| `<next_screens>` + `<screen is_entry_screen app_id bloks_server_params sources>` | telas Bloks a pré-carregar | `C58392QJx.A06` (preload) |
| `<screen_data parameters>` | blob de dados da tela | parseado |
| `<persist_data>` + `<data ...>` | valores que o host mantém | `C58392QJx.A02` (callback por chave) |

Um erro de IQ é devolvido ao chamador como `error` (`BtN`) e a entrada pendente do gerenciador é removida.

### 2.3 Tipos de estado (found)

O parser aceita a lista de discriminadores `FDSResourceState|FDSChoiceState|FDSSucceedState|FDSPassState|FDSSubflowState|FDSVersionCheckState` (`F8I` case 27). O atributo `type` é a string fixa da segunda coluna.

| Tipo | `type` | Atributos próprios | Comportamento em runtime |
|------|--------|--------------------|--------------------------|
| Resource | `resource` | `id` (id do resource), `parameters`, `merge`, `merge_param`, `catch` | Procura `id` no registro; id ausente gera o erro `ResourceNotFound`; executa o handler; resultado mesclado conforme `merge`; vai para `next` |
| Choice | `choice` | `default` (próximo estado de fallback), `catch`, filhos `<choice choice="{json}"/>`+ (uma chave de operador + `next`) | Avalia operadores sobre o JSON de entrada; o primeiro que casar vence, senão `default`; pelo menos um choice é obrigatório |
| Pass | `pass` | `parameters` | Reescreve dados e vai para `next`, sem handler |
| Succeed | `succeed` | nenhum | Sucesso terminal (`A05` sem erro) |
| Subflow | `subflow` | `launch_mode` (`child` ou `embedded`), `config`, `parameters`, `catch` | `child`: novo gerenciador e máquina de estados; `embedded`: busca outra config na mesma sessão (inferred a partir de `C55820P7d`) |
| Version check | `version_check` | `default`, filho `<choice>` | Parseado (`C31057DfB`) mas sem ramo em `C58392QJx.A01`; o estado é descartado (found); uma transição para ele falharia com `state not found for name` (inferred) |

O parser não tem estado `fail`; o manifest ainda lista `fail` (2.7).

Seletores e dados (found):

- `input_selector` padrão `"$"`; a string `"null"` o desativa (`C58392QJx.A01`). `result_selector` e a mesclagem de parâmetros passam por `AbstractC58328QFo`. Um motor estilo JSONPath é usado para `catch` (`Q2G`, expressões como `$.[i].error_equals`) (found); que os seletores usem o mesmo motor é inferred.
- Modos de `merge` em `QKb.A03`: `replace` (padrão), `merge`, `incremental_merge`, `wae_commerce_merge` (found).
- `catch` = array JSON de `{error_equals:[names], next:<state>}`; um `error_equals` vazio casa com tudo (found, `Q6G.A00`). Erros sem correspondência encerram a máquina com o erro (`A05`).
- Erros levantados pelo próprio interpretador: `ResourceNotFound`, `FailToResume`, `unsupportedComparisonTypes`, `comparingValuesWithDifferentTypes`, `genericChoiceStateError`; erro padrão do handler `NOT_CATCHABLE_ERROR` (`C5I7.A03`) (found).

### 2.4 Operadores de choice (found, `RsJ.A00`)

28 classes. O manifest lista 21; sete nomes legados existem só no código.

| Grupo | Nomes |
|-------|-------|
| Booleano | `and`, `or`, `not`, `booleanEquals` |
| Igualdade | `eq`, `neq`, `eq_any`, `neq_any`, `eq_path`, `neq_path`, `eq_any_path`, `neq_any_path`, `stringEquals` |
| Ordenação | `gt`, `gte`, `lt`, `lte`, `gt_path`, `gte_path`, `lt_path`, `lte_path`, `numericalEquals`, `numericalGreaterThan`, `numericalGreaterThanEqual`, `numericalLessThan`, `numericalLessThanEqual` |
| Outros | `isPresent`, `regex_match` (`variable` + `regex_match`) |

Cada operador é selecionado pela presença da chave no JSON do choice (`AbstractC56245PPq.A00`); uma `JSONException` pula para o próximo operador. As variantes `_path` comparam com um valor resolvido a partir de um path (inferred a partir do nome); a resolução exata não foi lida.

### 2.5 Registro de resources (found)

Registrados via `InterfaceC148426Oz.CP3()`; os ids são mantidos por suppliers `C05T.A00(n)`. Os registros `C53207NpW`..`C53211Npa` devolvem um conjunto apenas quando `L8E.A1T()` é true (`C18780mK.A03()` igual a `C21610rj.A0E`); o que esse predicado significa é unknown.

| Id do resource | Handler | Em `phoenix-features.json` | Comportamento |
|----------------|---------|----------------------------|---------------|
| `open_bloks_screen_graphql` | `C954246c` | sim | Abre uma tela Bloks; param `app_id` obrigatório (o cast falha caso contrário) |
| `open_bloks_screen` | `C954346d` | não | Igual, `fetch_channel` = `GRAPHQL` (usa `bloks_server_params`) ou `STATIC` (usa `fetch_channel_params.static_url`, define `should_load_bloks_through_cdn: true`); outros valores lançam exceção |
| `send_fds_iq` | anon em `AbstractC79003We` | sim | Params `config`, `type` (`GET`/`SET`), `state`, `parameters`; precisa de um gerenciador FDS vivo pelo job id; gerenciador ou config ausente registra um erro e falha com `NOT_CATCHABLE_ERROR` |
| `abprop_fetch` | anon em `AbstractC79003We` | não | Params `code` (int), `abprop_type` (`string`/`json`/`boolean`/`float`/`integer`), `default_value`; devolve `abprop_value` lido do store de AB; nenhuma allow-list em `code` observada |
| `client_dasl_query` | `C954746h` | sim | Precisa do param `query`, senão registra `No parameters` e falha; a query executa em um executor de background |
| `dismiss_bottom_sheet` | `C955346n` | sim | Fecha a sheet atual |
| `native_flow_call_manager` | `C954946j` | sim | Precisa de `phone_number`; reduz a dígitos e `+`; inicia `ACTION_DIAL` (`tel:`) com `FLAG_ACTIVITY_NEW_TASK` (apenas discador, sem ligação automática) |
| `request_permission` | `C955046k` | não | Requisição de permissão Android (ligação com `FcsRequestPermissionActivity` inferred) |
| `throw_error` | `C954446e` | não | Levanta o mapa `error`; busca a mensagem por `error_map_type` + `code` |
| `payment_encrypt_with_public_key` | `C31703Dr4` | sim | Params `data_value`, `data_type`, `key_scope`, `provider_name`, `network` (gated) |
| `br_verify_card_deeplink` | `C955446o` | sim | Envia um broadcast restrito a pacote `com.whatsapp.payments.phoenix.action.launch_activity_for_phoenix_result` com `app_to_app_partner_app_package`, `app_to_app_partner_intent_action`, `app_to_app_request_payload` (gated) |
| `br_verify_card_check_if_app_exists` | `C31702Dr3` | não | Gated |
| `native_br_compliance`, `native_br_p2m_checkout_address`, `native_card_encryption_resource` | `C955146l`, `C955246m`, anon | não | Pagamentos do Brasil, gated exceto o de cartão |

Nomes presentes só no manifest (sem entrada no registro nesta build): `error_response`, `native_flow_npci_common_library` (subárvore `mode.collect`), `native_p2m_lite_compliance`, `native_p2m_lite_hpp_checkout`, `open_bloks_screen_static`. `open_bloks_screen_static` não tem handler; o caminho STATIC vive dentro de `open_bloks_screen` como `fetch_channel`.

### 2.6 Pontos de lançamento (found)

`new C57778Pva(config, params, startState)` é construído em: `address_message` (`C31337Djk`, NFM), `biz_survey` (`C57417PpS`), `br_merchant_onboarding` (`C33140EcF`), `br_p2m_checkout_add_card`, `br_p2p_verify_card` (`C32703EOj`), e uma entrada por deep link que passa uma config nomeada pelo servidor com estado inicial `DeepLink` (`RunnableC46615KYo` case 18, referral `deeplink`). As strings `add_card_phoenix`, `verify_card_phoenix` existem; seu papel como nomes de config é inferred. O programa da config em si vem do servidor; nenhum é embarcado, exceto o manifest de capacidades.

### 2.7 Manifest de capacidades

`assets/versioning/phoenix-features.json` (1.218 B, idêntico à cópia da 2.26.34.4): `pass` de nível superior, `choice` (21 operadores), `resource` (12 ids mais `input_selector`, `parameters`, `result_selector`, `result_path`), `succeed`, `fail`. Seu uso em runtime não foi localizado (nenhuma referência de string encontrada); trate como uma lista de nomes. O código é a autoridade (2.4, 2.5).

---

## 3. Bloks

### 3.1 Superfícies host (found)

| Host | Papel |
|------|-------|
| `WaBloksActivity`, `WaBloksBottomSheetActivity`, `BloksCDSBottomSheetActivity`, `BloksCDSPreloadCDSBottomSheetActivity` | Tela cheia, bottom sheet, sheets CDS (design system) |
| `WaSqBloksActivity`, `WaBloksScreenQueryFragment` | Hosts de screen-query (tipos `screen_query` vs `legacy_screen`) |
| `WaFcsModalActivity`, `WaFcsBottomSheetModalActivity`, `WaFcsPreloadedBloksActivity`; `SurveyCanonicalBloksActivity` (+ sheet) | Telas hospedadas pelo Phoenix; pesquisas |
| Hosts de produto | `CommonBloksActivity`, `SupportBloksActivity`, `BrazilPayBloksActivity`, `ConsumerSubscriptionBloksActivity`, `DigitalCommerceDcpBloksActivity`, `CsatSurveyBloksActivity`, `AppointmentBloksHostActivity` (exported false), `WaBackupStorageBloksActivity` (exported false) |

Nenhuma activity de Bloks, Flows ou Phoenix declara intent filter; `targetSdkVersion` é 36, então activities sem `android:exported` não são exportadas (found, manifest). O Bloks também pode embutir um componente `WebView` (`AndroidBridge.updateSize`, ação `bk.action.WebViewWithOnChange`) (found).

### 3.2 Busca: GraphQL sobre HTTPS (found, `AbstractC40195HfH`, `C45J`)

| Item | Valor |
|------|-------|
| URL | `https://graph.<domain>/graphql<path>`; `<domain>` = pref `pref_graphql_domain`, padrão `whatsapp.com`; várias classes de requisição forçam `facebook.com`; `<path>` vazio, ou `/extensions` para a variante de Flows |
| Query string | `?_emp=1` anexado quando a AB prop **549** está ativa (padrão false) |
| Corpo | JSON `{"variables": "<json string>", "access_token": ..., "doc_id": <long>, "lang": ..., "Content-Type": "application/json"}` |
| Token | token por requisição se definido, senão uma string de token estática com escopo de app embutida no cliente (valor não reproduzido) |
| Headers | `X-FB-Friendly-Name: WABloksAppRootQuery-<app_id>`, `X-FB-Request-Analytics-Tags` |
| `variables` | `app_id`, chave de versão, `params` (string JSON), `bloks_theme_params` |
| Nome da chave de versão | `version`, `versioning_id` ou `bloks_version` conforme a classe de requisição; o valor é a mesma constante de 64 hex do Phoenix |
| Variante pré-consentimento (`C136975rF`) | adiciona `app_version`, `locale`, `df_token`, `enc_token`, `disclosure_id`, `is_paused`, `country_code`, `encrypted_rid` |
| Variante extensions (`C132735kG` case 2) | `extension_id` (= `flow_id` para versões 2, 3, 4 de flow message), `business_jid`, `screen_id`, `bloks_version` |
| Erros | `errors[].extensions.error_code` (padrão 417), `is_retryable`; `error.code` 3489039 dispara uma verificação de integridade e nova tentativa, 1675012 gera `Bad Request` (caminho pré-consentimento) |

Campos raiz da resposta (`AnonymousClass451.A05`): o payload é `data.<root>.payload` (uma string JSON).

| Doc id | Campo raiz | Usado por (found) |
|--------|------------|-------------------|
| 3651100555017197 | `whatsapp_bloks_getlayout` | rota padrão; minishops link/pdp/storefront |
| 3958953970834604 | `whatsapp_bloks_getprivatelayout` | padrão para `C5LX.A00()`; aviso de privacidade de minishops, prévia de produtos |
| 9404809712971896 | `whatsapp_bloks_getlayout` | famílias roteadas por regex (3.3) |
| 9943385105682204 | `whatsapp_bloks_getprivatelayout` | `logged_out.cxthelp.whatsapp` |
| 6019334944816363 | Layout de Flows (o campo raiz `whatsapp_galaxy_bloks_getflowlayout` existe em `AnonymousClass424`; ligação entre os dois inferred) | `com.bloks.www.whatsapp.galaxy.flow.v2`, `...commerce.galaxy_message`, `...commerce.extensions_message_v2` |
| 36103976949247233 | `wamo_bloks_get_layout` | superfícies WAMO |
| 9676557989071413 | não mapeado para um campo raiz | amostra/care de pagamentos, `novi.care.*`, consentimento `whatsapp.ai.biz.*` |

Os doc ids 26891716230495873 (pix playground) e 25865201793138751 aparecem nas tabelas de roteamento sem campo raiz resolvido.

### 3.3 Roteamento por app-id (found)

Uma tela é endereçada por `app_id` (um nome pontilhado, `com.bloks.www.*`). As tabelas de roteamento mapeiam um `app_id` para um descritor de query `C5LX(doc id, variante de request-factory)`: dez tabelas de conjuntos fixos (`InterfaceC148576Pp`: `C132235jS`..`C132335jc`) e tabelas de regex (`InterfaceC148726Qe`: `C132345jd`..`C132465jp`).

| Família | Padrão ou exemplo | Doc id |
|---------|-------------------|--------|
| Hub de pedidos / pagamentos | `orders_hub(\..+)*`, `fbpay_hub`, `payment.mft.wallet.fbpay_hub`, `(payment.)?mft.wallet.*`, `payment.(bloks.(commerce|ecp).checkout|fbpay.ecp).*` | 9404809712971896 |
| `gai` / `sna` / stickers de IA (significado da família inferred a partir dos nomes) | `bloks.nme.gai`, `wa.nme.gai`, `wa.sna`, `whatsapp.ai.stickers.*` | 9404809712971896 |
| Assinaturas | `dcp.subscriptions?(\..+)*` | 9404809712971896 |
| Suporte | `(csf|cxthelp)(\..+)+` | 9404809712971896 |
| Minishops | `minishops.link.app`, `.whatsapp.pdp`, `.storefront.wa` | 3651100555017197 |
| Consentimento de IA para negócios | `whatsapp.ai.biz.{learn_more,consent,assistant_consent,third_party_consent,meta_ai_consent}` | 9676557989071413 |
| Playground / debug | `wa.playground.payments.br.pix.*` (variante 9) ; `whatsapp.payments.phoenix.{debug,demo_*,multi_*}`, `payments.whatsapp.f2care`, `novi.care.*` (variante 10) | 26891716230495873 ; 9676557989071413 |

87 ids literais distintos `com.bloks.www.*` estão no código; o resto chega do servidor e é roteado pelas famílias de regex. Existem duas guardas de padrão em `AnonymousClass514`: ids `consent(...)` podem carregar `extra_params_json.whatsapp_bloks_networking_feature_override`; `payment.mft.security.*` com `ptt_use_case = WALLET` seleciona o helper de requisição `wallet_canonical` (found).

### 3.4 Formato do payload (found)

Parser JSON de streaming `AbstractC122255Jb`; o objeto de topo tem `payload` (string) e `layout.bloks_payload`.

| Chave de `bloks_payload` | Significado |
|--------------------------|-------------|
| `tree` | Componente raiz (seção abaixo); `action` no lugar de `tree` para payloads só de ação |
| `ft` | Tabela de funções: id para string de expressão |
| `data`, `values`, `templates`, `props` | Registros de dados (`id`, `type`, `data`, `scoped`), expressões de valor, templates, tabela de nomes de props |
| `embedded_payloads`, `hoisted_async_components` | Payloads aninhados por id |
| `referenced`, `referenced_external`, `referenced_embedded_payloads`, `referenced_templates`, `referenced_ft_entries`, `referenced_values`, `referenced_ct`, `ct` | Listas de dependências para payloads parciais/em streaming |
| `component_queries` | Component queries assíncronas (`id`, `app_id_expr`, `params`, `client_params`, `targets`, `cache_ttl_expr`, `disk_cache_enabled`, `is_scoped`) |
| `error_attribution` | `logging_id`, `source_map_id` |
| `depth`, `step_debugger_metadata.breakpoints` | Profundidade de streaming, debugger |

Codificação da árvore (`C5AN`): um nó é um objeto cuja única chave é um code point; esse code point é o id do componente (`AbstractC105654gT.A00` = `codePointAt(0)`); as chaves de atributo também são code points únicos (`!`=33 id, `#`=35 filho, `&`=38, `+`=43 para o componente shadow 13347). O mapa de id de componente para nome não está nos assets (unknown).

Function ids ("Lispy", `C122545Ki`): um nó de script é um array JSON cujo primeiro elemento é a função: `"#<name>"` nomeada, um nome pontilhado resolvido pela tabela de nomes `AbstractC111054pC.A01`, ou uma string base-36 parseada com `Integer.parseInt(s, 36)`. Constantes tipadas têm ids fixos: 17809 `bool.Const`, 18327 `f32.Const`, 18338 `f64.Const`, 19222 `i32.Const`, 19237 `i64.Const`. A tabela de nomes tem 681 entradas, ids 17293 a 26071.

Decodificado a partir dos templates embarcados (token base-36, id, nome na tabela; found): `e2a` 18226 `core.If`; `e25` 18221 `core.GetArg`; `e2f` 18231 `core.TakeLast`; `e1w` 18212 `core.Apply`; `dng` 17692 `bloks.GetParameter`; `dnt` 17705 `bloks.GetVariable2`; `f4g` 19600 `map.Get`; `f6m` 19678 `mins.CallRuntime`; `igq` 23930 `core.AsNonnull`; `fjm` 20146 `screen.callback.DidFetchSucceed`; `foz` 20339 `ttrc.MarkerStart` (todos sob `bk.action.`); `h9h` 22373 está listado com o nome literal `null`.

A forma de texto `\t(...)` em `ft` e em strings de expressão é uma serialização diferente; que ela usa os mesmos ids base-36 decorre de as decodificações acima serem coerentes (inferred). O parser de texto não foi lido.

Negociação de capacidades (inferred): o `bloks-versioning-id` de 64 hex é enviado em toda requisição; a tabela contém 50 nomes de capacidade `bk.versioning.*` (por exemplo `SupportsFunctionTables`, `TemplatePayloads`, `AsyncComponentBatchedWireProtocol`, `SupportsLispySignatureMinification`). Que o hash identifique esse conjunto de capacidades é inferred.

Assets embarcados (`assets/json/bloks_screen_template.json`, `bloks_bottomsheet_template.json`, `bloks_cds_base_screen_template.json`, 9.028 / 9.124 / 11.443 B, idênticos à 2.26.34.4): template raiz com uma `tree` de spinner, uma entrada de `component_queries` cujo alvo é `genScreenContent`, e um fallback de erro em `embedded_payloads` (`Something went wrong` / `Please try again later` em dois dos três). São scaffolds; as telas de produto vêm do resultado da query.

### 3.5 Namespaces de ações (found, `AbstractC111054pC`)

| Prefixo | Contagem na tabela de ids | Exemplos |
|---------|---------------------------|----------|
| `bk.action.core/bool/num/i32/i64/f32/string/array/map/math` | 113 | `core.If`, `core.Let`, `core.While`, `array.Map`, `string.*` |
| `bk.action.mins.*` | 36 | `CallRuntime`, `PutByVal`, `Raise` (VM minscript) |
| `bk.action.bloks.*` | 61 | `OpenScreen`, `OpenBottomSheet`, `Inflate`, `FetchAsyncComponents`, `WriteLocalState`, `ReplaceChildren`, `WriteGlobalConsistencyStore` |
| `bk.action.cds.*`, `bk.callbacks.cds.*` | 13 + | `OpenCdsBottomSheet`, `PushCdsBottomSheet`, `UnwindToScreen` |
| `bk.action.animated/animation/timer/collection/textinput/text_input/video` | 58 | Comportamento de UI |
| `bk.action.qpl/ttrc/trace` | 14 / 11 / 2 | Marcadores de latência (`ttrc.MarkerStart`) |
| `bk.action.privacy.consent.*` | 10 | `OpenFlow`, `LaunchConsent`, `ShutdownExperience` |
| `bk.action.waffle.*`, `bk.fx.*`, `bk.waffle.*` | 37 / 11 / 2 | Vinculação do Accounts Center: `EncryptPassword`, `DeleteLocalUserCredentials`, `GetProfilePictureUrl`, `UnpauseWithNativeAuthBlob`, `PregenerateAndCacheRSAKeyPairs` |
| `bk.action.mft.*`, `bk.action.frontier.*`, `bk.action.apt.PleEncrypt`, `bk.action.commerce.GetPaymentToken`, `bk.action.payments.GetCreditCardMetaData` | 5 / 5 / 1 / 1 / 1 | Pagamentos: `ModularGeneratePTT`, `LaunchGooglePaySheet`, `IsLuhnCompliant` |
| `bk.action.navigation.OpenUrl`, `bk.fx.action.OpenURLInIAB`, `bk.action.acp.OpenUrlExternally`, `bk.action.OpenUniversalLink`, `bk.action.DeeplinkToOtherAppOrDirectToAppStore`, `bk.action.bloks.IsAppInstalled` | 6 | Navegação para fora do Bloks |
| `bk.action.io.clipboard.SetString`, `bk.action.RequestPermission`, `bk.action.media.LoadAlbums`, `bk.fx.action.media.OpenMediaPicker`, `bk.action.foa.media.OpenCamera` | 5 | Acesso ao dispositivo |
| `wa.action.*` | 75 | Ações host do WhatsApp (tabela abaixo) |
| `wa.callbacks.*` | 10 | `FormInputOnTextChange`, `CodeInputOnTextChange`, `DatePickerOnDateSet`, `CameraViewOnMediaCaptured`, `ListViewItemSelected` |
| `bk.versioning.*`, `wa.versioning.image.base64` | 50 / 1 | Nomes de capacidade |

`wa.action.*` notáveis (ids 22391 a 26071):

| Grupo | Nomes |
|-------|-------|
| Rede | `IQRequest`, `AsyncRequest`, `UploadMedia`, `UploadProfilePicture` |
| Bridge Phoenix | `phoenix.FdsIq`, `FdsIqV2`, `FcsReturnResult`, `FcsReturnResultV2`, `FcsReturnResumableData`, `statemachine.GoBack`, `GoBackV2` |
| Estado do app | `GetAbPropValue`, `GetAppType`, `GetIntentParameter`, `LoadScreenParam`, `SaveScreenParam`, `IsDarkModeEnabled` |
| Navegação | `OpenUrl`, `RouteToNativeScreen`, `RouteToNativeBenefitDetail(V2)`, `navigation.OpenChat`, `OpenContactInfo`, `OpenNativeActionSheet`, `FinishActivity(WithResult)`, `PopScreen` |
| Mensagens / commerce | `commerce.SendNFMReplyMessage`, `commerce.ActionWithCallback`, `share.Text`, `bonsai.SubmitFeedback`, `care.OpenContactSupport`, `care.OpenReportThisPayment` |
| Telemetria | `SendFieldStat(V2)`, `StartFieldStatTimer`, `GetFieldStatEventId`, `perf.TrackPerformance`, `novi.EncryptLogEvent(V2)` |
| Deeplink | `RegDeeplinkListener`, `DeregDeeplinkListener` |

Guarda encontrada na ação de IQ do Bloks (`C129575f5.A0Y`, log `IQRequestHelper/sendIQRequest: Invalid XMLNS`): apenas os xmlns `w:pay` e `urn:xmpp:whatsapp:account` passam (`C33327EfH.A02`); qualquer outro chama o callback `on_failure`. Scripts Bloks, portanto, só podem enviar IQs nesses dois namespaces (found). As implementações de handler da maioria dos outros ids `wa.action.*` não foram rastreadas (seu código é alcançado por id numérico).

### 3.6 Component queries e cache (found)

- Uma `component_query` busca um componente assíncrono por `app_id` pelo mesmo caminho GraphQL (gerenciador `C5L9`, tag de log `BloksComponentQueryManager`); `app_id_expr`, `params`, `client_params` e `cache_ttl_expr` são expressões Lispy avaliadas no cliente.
- Duas camadas de cache: um cache em memória (`cache_src: memory`, `cache_age`) e um cache em disco com chave por query (`BloksComponentQueryDiskCache`; classes `C5NA`, `C5NN`, `C136885r6`). Os registros em disco são serializados em Java (`ComponentQueryDiskCacheRecord`: `DiskCacheData{initialResponse, extensions}`, `responseTimestampMs`, `BloksComponentQueryResources`); os metadados ficam sob `__disk_metadata`; uma `Bloks_ACQ_ReadWriteThread` faz o I/O. `disk_cache_enabled` é um interruptor por query.
- As ações `bk.action.AsyncComponentCacheWrite`, `bloks.ClearCachedAsyncComponents`, `bloks.InvalidateCachedAsyncComponents` permitem que um payload gerencie o cache.
- Diretório, limite de tamanho e evicção do cache em disco: unknown. A desserialização Java de registros de cache influenciados pelo servidor ocorre apenas a partir do cache do próprio app (inferred a partir do caminho de código).

---

## 4. Native flow messages e WhatsApp Flows

### 4.1 Registro de botões NFM (found, `AbstractC30032D4u` case 442, classe `EYT`)

Uma mensagem interativa carrega botões com `nativeFlowInfo.name` e um JSON de params. Despacho: `C33370Efz.A05` procura o nome em um mapa (`C0VA`) de cerca de 40 subclasses de `AbstractC33168Ech`; nomes desconhecidos registram `can not recognize NFM action` e são descartados; uma ação pode ser desativada por gate (contadores `wa:nfm_dispatch_gate_blocked` / `_observed`).

| Conjunto | Nomes |
|----------|-------|
| Nomes de botão suportados (39) | `cta_catalog`, `review_and_pay`, `review_and_pay_v2`, `cta_call`, `cta_url`, `cta_copy`, `cta_pix_code_copy`, `offer_payment_account`, `form_message`, `open_webview`, `catalog_message`, `voice_call`, `video_call`, `landline_call`, `quick_reply`, `single_select`, `view_product`, `call_permission_request`, `cta_app_link`, `appointment`, `automated_greeting_message_view_catalog`, `send_location`, `order_status`, `booking_confirmation`, `booking_status`, `psi_nux_opt_in`, `psi_tos_opt_in`, `psi_opt_outs`, `account_authentication_request`, `request_contact_info`, `agent_api_key`, `otp`, `payment_reminder`, `cta_reminder`, `payment_request`, `api_signup`, `inapp_signup`, `split_payment`, `send_payment` |
| Segundo conjunto | `address_message`, `galaxy_message` (lançam flows; papel inferred a partir do uso) |
| Allow-list mista/quick-reply | `C33370Efz.A08`: `cta_url`, `cta_call`, `voice_call`, `video_call`, `cta_copy`, `menu_options`, `cta_reminder`, `view_product`, `cta_app_link`, `galaxy_message`, `otp`, `booking_*`, ... |

- `address_message` inicia a config Phoenix `address_message` (`C31337Djk`, found).
- `galaxy_message` abre o WhatsApp Flows (4.2).
- As respostas de flow são armazenadas em `message_ui_elements_reply` (`flow_id`, `element_type` 8) e `interactive_message_bloks_widget` (found, SQL).

### 4.2 Params e lançamento de `galaxy_message` (found, `C31338Djl`, `C31337Djk`)

| Chave no JSON de params | Uso |
|-------------------------|-----|
| `flow_id` | deve casar com `\d+` para a ação Flows v2 |
| `flow_token`, `flow_cta` | obrigatórios com `flow_id` (caminho Flows v2) |
| `flow_message_version` | `2`, `3`, `4` selecionam as variáveis de extensão da query Bloks |
| `flow_action` (`navigate` padrão, `data_exchange`), `flow_action_payload` (objeto) | primeira tela / canal de dados |
| `mode` | `draft` marca um flow rascunho (`is_draft`) |
| `form_type` | roteia para `FlexCheckoutNativeFormActivity` (flexible checkout) |
| `flow_token_signature`, `www_proxy_secret` | repassados à página apenas quando a AB prop **14825** está ativa |

O JID do negócio remetente vem do chat (`FlowsV2Action`); sem ele o lançamento é abortado (`cannot launch flow without business jid`). Existem dois renderizadores: o web app (4.3) e um caminho Bloks (`com.bloks.www.whatsapp.galaxy.flow.v2`, seção 3.2). Qual deles uma dada mensagem usa não foi resolvido; as AB props **22787** (activity separada vs bottom sheet) e **14222** são lidas no caminho web.

### 4.3 Web app de Flows (found)

| Item | Valor |
|------|-------|
| URLs base (AB props string) | **7153** `https://flows.whatsapp.net/flows` (preload, `C35814Ff9`), **6060** mesmo padrão (busca do JSON do flow `EP6`: base + `/json/` + flow id, inferred a partir da ordem do builder), **7125** `.../flows/cache_management/` (limpador de cache `C39066GzF`, intervalo **7126** = 1382400), **16723** `.../flows-app/catalog` (catálogo) |
| Host | `SecureWebView` (`com.facebook.secure.securewebview`): acesso a arquivo e content desativado; carregamento permitido apenas se o esquema for `https` E o host for igual ao host da URL de lançamento ou um subdomínio dele (`GAP.A00`, `H26`, combinados com AND em `GAL`); caso contrário registra `Uri is blocked` |
| URL de lançamento | vem do bundle (`url`, padrão `about:blank`); a base é uma AB prop, então o servidor pode movê-la; a política de host segue a URL de lançamento (consequência inferred) |
| Preload | `FlowsWebPreloader` carrega AB **7153** em uma WebView oculta (`setCacheMode(2)`); a versão do cache de service worker é rastreada via `flows_service_workers_cache_version` |
| Injeção na página | tag `meta` com viewport, `layoutDirection`, `locale`, `timeZone`, `supportedStyles` |
| Bridge | `window.WhatsAppBridge.invoke(method, data, cb)`; o nativo cria um `MessageChannel` e posta `init-port` com a porta 1 (`HQD`); as mensagens são JSON `{method, data, callbackID}`; respostas `{callbackID, responseData}` |
| Vínculo de origem | O script da bridge é injetado com `evaluateJavascript` em qualquer coisa que a WebView mostre; a porta é postada para o alvo `Uri.EMPTY`; o controle depende da política de URL do SecureWebView (inferred) |
| JSON do flow | `flow_json` buscado por `EP6.A01` (HTTP GET, armazenado em disco como string serializada, chave `<id>_<id2>`), somente quando a AB **8552** está ativa; `FlowsWebViewDataRepository` monta o bundle (`flow_json`, `flow_action_payload`, `creation_source`, ids de sessão) |
| Chave pública | `WAExtensionsGetPublicKey` devolve a chave pública do endpoint obtida por uma chamada GraphQL de metadados (erros `extensions-metadata-graphql-*`, modo `required` ou `optional`); o uso para criptografar dados é feito no lado da página (inferred) |

Métodos da bridge tratados nativamente (30; `C41342Hyk`, `FlowsWebBottomSheetContainer.CKc`):

| Grupo | Métodos |
|-------|---------|
| Sessão | `WAExtensionsGetFlowData`, `WAExtensionsDataChannelExchange`, `WAExtensionsNavigate`, `WAExtensionsComplete`, `WAExtensionsClose`, `WAExtensionsGetPublicKey`, `WAExtensionsGetClientAbProps` |
| UI | `WAFlowsShowNativeInputDialogComponent`, `WAExtensionsConfigureNavBar`, `WAFlowsMediaSelect`, `WAFlowsMediaRetry`, `WAFlowsMediaDelete`, `WAFlowsCopyText`, `WAFlowsOpenURL`, `WAExtensionsLearnMore`, `WAExtensionsContextualHelp` |
| Negócio | `WAExtensionsSpamReport`, `WAExtensionsReportItem`, `WAFlowsDownloadResponse`, `WAFlowsMarketingDisclosureState`, `WAFlowsMarketingDisclosureUserAction` |
| Carrinho | `WAFlowsStoreShoppingFlowContext`, `WAFlowsGetCart`, `WAFlowsSetCartItem`, `WAFlowsClearCart` |
| Telemetria | `WAMLogger`, `WAQPLLogger.start`, `.end`, `.annotate`, `.point` |

Notas de tratamento: `WAFlowsOpenURL` inicia `ACTION_VIEW` apenas para URLs `https`, senão um snackbar; `WAExtensionsGetClientAbProps` devolve qualquer AB prop por código e tipo (`bool`, `int`, `float`, `string`, `json`) sem allow-list observada (`C37367GJs`); métodos desconhecidos vão para um handler padrão (`GJW`); entrada que falha no parse gera `extensions-bridge-api-input-parse-error`.

### 4.4 Conclusão do flow

`WAExtensionsComplete` encerra a sessão e o cliente envia uma mensagem de resposta de native-flow (colunas `native_flow_response_*`; os params carregam `wa_flow_response_params`, `flow_creation_source`, `response_message`) (found pelos nomes; caminho de envio não rastreado).

### 4.5 Query do endpoint de Flows

A classe de resultado `AnonymousClass456` lê a raiz `whatsapp_galaxy_forward_flow_data_response` ou `xwa_flows_make_flow_endpoint_request` e um `status_code`: 200 ok, 421 e 504 mapeados para resultados distintos, os demais falha genérica (found). Se isso roda sobre MEX ou sobre a stack GraphQL HTTPS é unknown (a base do parser é compartilhada com o Bloks).

---

## 5. Superfícies que não são UI descrita pelo servidor

### 5.1 AI rich response (carregada na mensagem, componentes fixos)

Protobuf `richResponseMessage` (ver `WA_META_AI.md` seção 6.3). Enum de tipo de sub-mensagem `EnumC32139E2l` (found): `AI_RICH_RESPONSE_UNKNOWN` 0, `GRID_IMAGE` 1, `TEXT` 2, `INLINE_IMAGE` 3, `TABLE` 4, `CODE` 5, `DYNAMIC` 6, `MAP` 7, `LATEX` 8, `CONTENT_ITEMS` 9; classes de destaque de código (`KEYWORD`, `STRING`, `NUMBER`, `METHOD`, `COMMENT`, `DEFAULT`); metadados dinâmicos `IMAGE`, `GIF`. O cliente renderiza um conjunto fixo; as ações são download / encaminhamento de arquivo (`UnifiedResponseActionHandlerFactory`). Sem linguagem de script, sem DSL de ações.

### 5.2 Card FMX

O card FMX (`LE7`, factory de view-model `fmxViewModelFactory`, tag de avatar `fmx-card-v2`) é criado pelo cliente como uma mensagem de sistema (`C198788cr`: `Creating FMX card system message for chat`); contadores como `fmxBizEnterpriseSenders`, `fmxMissingLidMapping`, `fmxSuspiciousBottomSheetCacheMiss` mostram que ele é acionado por sinais locais. Se o servidor fornece algum texto do card é unknown. Trate como UI nativa.

### 5.3 Scripts do navegador in-app (iabjs)

`res/raw/iabjs_*` tem 15 scripts na 2.26.41.6 (quatro a mais que o conjunto da 2.26.34.4): `autofill_execute_callback`, `autofill_language_detect`, `autofill_payment_detection`, `otp_autofill` são novos. Host `WaInAppBrowsingActivity` (exported false).

| Item | Valor (found) |
|------|---------------|
| Objeto bridge | `iabjs_unified_bridge`: `addWebMessageListener(name, allowedOrigins, listener, jsWorld)` no mundo JS isolado `iab_js` quando suportado (`HJY.A05`); fallback `addJavascriptInterface("iabjs_unified_bridge")` (`RunnableC40709HoJ`) |
| Lado da página | `window.__call_iabjs_unified_bridge(method, nonce, payload)` posta `{method, payload, nonce}`; o nonce é substituído em `window.__iabjs_unified_bridge_nonce="%s"` na injeção |
| Verificação nativa | `C39590HNn`: o `nonce` do JSON deve ser igual ao nonce armazenado do handler (gerado uma vez por handler por `AbstractC48382LBd.A00().toString()`, semelhante a UUID, inferred); divergência registra `invalid_nonce` e descarta a chamada; o método `iabjs_register_proxy` registra o mundo; outros métodos vão para listeners indexados por (mundo, método) |
| Novo nesta build | `iabjs_autofill_payment_detection` classifica campos em `cc-number`, `cc-exp`, `cc-exp-month`, `cc-exp-year`, `cc-csc`, `cc-name` por `autocomplete` ou regex de name/id/placeholder; `iabjs_otp_autofill` preenche `input[autocomplete="one-time-code"]`; `iabjs_autofill_language_detect` envia `languageDetermined` |
| Conjunto de origens permitidas | `Set` fornecido pelo chamador; conteúdo não rastreado (unknown) |
| Fallback legado | `addJavascriptInterface` não tem filtro por origem (comportamento da plataforma, inferred) |

Oito dos 11 scripts mais antigos são byte a byte idênticos às cópias da 2.26.34.4; `detect_login_forms`, `navigation_performance_logger_android`, `iabjs_bridge_init` mudaram (453 B vs 433 B para o bridge init).

---

## 6. Resumo de sandboxing e segurança

| Controle | Onde | Tier |
|----------|------|------|
| Ids de resource Phoenix fixos no código; id desconhecido gera `ResourceNotFound` | `QKb.A03` | found |
| Operadores Phoenix fixos (28); operador sem correspondência é pulado | `RsJ`, `AbstractC56245PPq` | found |
| Ação de IQ do Bloks limitada aos xmlns `w:pay`, `urn:xmpp:whatsapp:account` | `C33327EfH.A02` | found |
| Function ids Bloks fixos (681 nomeados) | `AbstractC111054pC`, `C122545Ki` | found |
| Nomes NFM fixos (39 + 2); desconhecidos descartados | `AbstractC30032D4u`, `C33370Efz` | found |
| Host de Flows: apenas https + host de lançamento (ou subdomínio), sem acesso a file/content | `SecureWebView`, `GAP`, `H26` | found |
| Bridge de Flows: lista fixa de métodos; `WAFlowsOpenURL` apenas https | `FlowsWebBottomSheetContainer` | found |
| iabjs: verificação de nonce, mundo isolado, conjunto de origens | `C39590HNn`, `HJY` | found |
| Broadcast `br_verify_card_deeplink` do Phoenix restrito ao próprio pacote | `C955446o` | found |
| Todas as activities de Bloks, Flows, Phoenix sem intent filters; targetSdk 36 | manifest | found |
| Verificação de assinatura ou hash do conteúdo Bloks/Phoenix | nenhuma localizada; `BloksTrustedPayload` sem referência | found (ausência nos caminhos pesquisados) |
| O servidor pode ler AB props por código (`abprop_fetch`, `WAExtensionsGetClientAbProps`) | nenhuma allow-list observada | found |
| Confiança no transporte (TLS pinning, tratamento de token para requisições graph) | não analisado | unknown |

Consequência (inferred): a confiança repousa no transporte e nos registros acima; um programa do lado do servidor comprometido ou malicioso fica limitado a esses registros, mas os registros incluem helpers de criptografia de pagamento, tratamento de credenciais do Accounts Center, `ACTION_DIAL`, abertura de URL e leituras de AB.

---

## 7. Cache e preload

Component queries do Bloks: memória + disco, TTL por `cache_ttl_expr` (3.6). Phoenix: os `next_screens` listados pelo servidor são pré-carregados em `WaFcsPreloadedBloksActivity`; entradas `persist_data` vão para listeners por chave (found). Flows web: WebView de preload, versão de cache de service worker, limpador agendado (AB 7125/7126), cache em disco do JSON do flow, marcador de ban de metadados `extensions_metadata_banned_<id>_<id>` nas prefs (found).

---

## 8. Feature flags (padrões de `C08J`; significados a partir do ponto de leitura)

| ID | Tipo | Padrão | Lido em | Efeito |
|----|------|--------|---------|--------|
| **549** | bool | false | `AbstractC40195HfH.A03` | Anexa `?_emp=1` à URL GraphQL (a menos que `C0GD.A02()`) |
| **7153** | string | `https://flows.whatsapp.net/flows` | `C35814Ff9` | URL de preload de Flows |
| **6060** | string | igual | `EP6`, `C33350Efe` | Base de Flows para `/json/<id>` |
| **7125** | string | `.../flows/cache_management/` | `C39066GzF` | URL do limpador de cache de Flows |
| **7126** | int | 1382400 | `C39066GzF` | Intervalo/ativação do limpador (unidade desconhecida; > 0 ativa) |
| **8552** | bool | false | `FlowsWebViewDataRepository.A07` | Busca o JSON do flow nativamente e o passa para a página |
| **14825** | bool | false | `FlowsWebViewDataRepository.A06` | Passa `www_proxy_secret` e `flow_token_signature` |
| **22787** | bool | false | `C31338Djl` | Flows em activity separada vs bottom sheet |
| **24781** | bool | false | `FlowsWebBottomSheetContainer` | Sem ela, uma sheet restaurada se fecha sozinha |
| **14222** | bool | false | `C31338Djl` | Gate no caminho de lançamento de Flows (efeito exato desconhecido) |
| **5333**, **1319** | bool | false / false | variante de Flows de `C45J` | Ambas ativas: erros de layout de Flows reportados como `extensions-layout-unexpected-error` |

Os ids de flag usam o espaço numérico de `WA_AB_PROPS.md`.

---

## 9. Baileys (`baron-baileys-v2`)

Um cliente Baileys não tem renderizador, então Bloks e Flows web estão fora de alcance. O que ele pode tocar é a parte carregada em mensagens e, em princípio, o IQ.

| Objetivo | O que funciona | Por que pode falhar | Correção |
|----------|----------------|---------------------|----------|
| Enviar um botão de Flow | `interactiveMessage.nativeFlowMessage.buttons[]` com `name: 'galaxy_message'` e `buttonParamsJson` contendo as chaves de 4.2 (`flow_message_version`, `flow_id`, `flow_token`, `flow_cta`, `flow_action`, `flow_action_payload`) | O receptor precisa de contexto de JID de negócio, `flow_id` numérico, `flow_token`, `flow_cta`; remetentes usuário (não negócio) provavelmente não serão atendidos (inferred) | Enviar de uma conta registrada como negócio; manter `flow_id` numérico |
| Usar um nome de botão desconhecido | nenhum | `C33370Efz` descarta nomes fora dos 39 + 2 | Usar um nome de 4.1 |
| Buscar um programa Phoenix | `<iq xmlns="phoenix" type="get"><fds config=... /></iq>` | O servidor decide pelo estado da conta/app; conteúdo da resposta nunca capturado | Não tentado; tratar como unknown |
| Ler uma tela Bloks | não aplicável | Precisa do token graph, doc id e `bloks-versioning-id`; sem caminho no Baileys | Fora de escopo |

---

## 10. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|----------|
| `ResourceNotFound` e o flow termina | o estado `resource` nomeia um id fora do registro (ou um id gated do Brasil em uma build que não corresponde) | Usar ids de 2.5 |
| `state not found for name: <x>` | `next` aponta para um estado ausente, ou para um estado `version_check` (descartado por `C58392QJx.A01`) | Declarar o alvo como um tipo suportado |
| `unsupportedComparisonTypes` / `comparingValuesWithDifferentTypes` | Operador aplicado a tipos errados | Casar os tipos; usar `catch`; `NOT_CATCHABLE_ERROR` não pode ser capturado |
| `FdsIqResource/execute: can't find FdsManager from the job_id` | `send_fds_iq` fora de uma sessão viva | Executar dentro da sessão que o iniciou |
| Bloks `Invalid XMLNS` | `wa.action.IQRequest` com um xmlns fora da allow-list | Apenas `w:pay`, `urn:xmpp:whatsapp:account` |
| `FcsScreenOpenerBloksDelegate: app_id is not present` | `open_bloks_screen*` sem `app_id` | Passar `app_id` |
| `error.code` 3489039 | Verificação de integridade exigida (busca pré-consentimento) | O cliente tenta de novo após a verificação |
| Página de Flows em branco, log `Uri is blocked` | A navegação saiu do host de lançamento ou usou esquema não https | Manter o conteúdo no host de lançamento |
| `extensions-bridge-api-input-parse-error` | A mensagem da bridge não é JSON válido no formato esperado | Enviar `{method, data, callbackID}` |
| iabjs `invalid_nonce` | Nonce errado ou ausente | Usar o `__iabjs_unified_bridge_nonce` injetado |

---

## 11. Distinções-chave

| Não confundir | Diferença |
|---------------|-----------|
| Phoenix vs Bloks | Phoenix = fluxo de controle sobre IQ; Bloks = telas sobre GraphQL; eles se encontram em `open_bloks_screen*` e `wa.action.phoenix.*` |
| FCS vs FDS | Ambos aparecem: `flowconfigurationservice` (pacote, `FcsStateMachine`) e `FDS` (gerenciador de IQ, `<fds>`, log `FDSManage`); a expansão de "FDS" não está no código |
| Manifest vs código | `phoenix-features.json` lista 12 ids de resource e 21 operadores; o código tem 15 ids de resource e 28 operadores; o código vence |
| `open_bloks_screen_static` vs `open_bloks_screen` + `fetch_channel=STATIC` | Apenas o segundo tem handler |
| Chaves da árvore Bloks vs opcodes | As chaves da árvore são code points de componente; as cabeças de script são function ids (base-36) |
| Flows web vs Flows Bloks | Dois renderizadores para `galaxy_message`: WebView (`flows.whatsapp.net`) e `com.bloks.www.whatsapp.galaxy.flow.v2` |
| GraphQL do Bloks vs MEX | O Bloks posta em `graph.<domain>/graphql` com `doc_id`; MEX é a camada de query transportada por XMPP usada em outros lugares |
| Nonce do iabjs vs bridge de Flows | O iabjs usa um nonce por handler no envelope; a bridge de Flows não tem nonce, depende do handshake de porta e da política de URL |
| Rich response vs Bloks | Rich response é um conjunto protobuf fixo; Bloks é uma árvore programável |

---

## 12. Fluxo completo

```
[Server]                                          [WhatsApp client]
   │  message: interactive nativeFlowInfo name        │
   ├─────────────────────────────────────────────────►│ C33370Efz: name in registry? gated?
   │        address_message              galaxy_message│
   │             ▼                              ▼      │
   │  Phoenix start C58392QJx.A08       Flows launch C31338Djl: SecureWebView (https, launch host)
   │  IQ <iq xmlns="phoenix"><fds config>      + MessageChannel init-port, or Bloks galaxy.flow.v2
   │◄────────────────────────────────────────────────┤
   │  <fds><states start_at><state type=..>           │
   ├─────────────────────────────────────────────────►│ QKb.A03 loop: resource | choice(28 ops) | pass | subflow | succeed
   │                                                  │ resource -> registry: open_bloks_screen_graphql, send_fds_iq, abprop_fetch, ...
   │  POST graph.<domain>/graphql {doc_id, variables{app_id, versioning id, params}}  (route by app_id: C5LX)
   │◄────────────────────────────────────────────────┤
   │  layout.bloks_payload {tree, ft, component_queries, ...}
   ├─────────────────────────────────────────────────►│ AbstractC122255Jb: tree (code-point keys) + Lispy (base-36 ids)
   │                                                  │ user action -> bk.* / wa.* function id
   │◄── IQ (w:pay | urn:xmpp:whatsapp:account only) ──┤ wa.action.IQRequest
   │                                                  │ wa.action.phoenix.FdsIq / FcsReturnResult -> back into QKb (next / catch / end)
   │◄── WAExtensionsComplete -> native-flow response ─┤
```

---

## 13. Incógnitas

| Item | Status |
|------|--------|
| Expansão de "FDS"; significado do gate `L8E.A1T()` | unknown |
| Mapa de code point de componente para nome; nomes Lispy além dos 681 listados; parser da forma de texto | unknown |
| Código do handler da maioria dos ids `wa.action.*` / `bk.action.*` (alcançados por id numérico) | unknown |
| Conteúdo real do servidor: nenhum programa Phoenix ou tela Bloks foi capturado | unknown (apenas estático) |
| Transporte de `xwa_flows_make_flow_endpoint_request`; renderizador que um `galaxy_message` usa; efeito da AB **14222** | unknown |
| Local, tamanho e evicção do cache em disco; conjunto de origens permitidas do iabjs; integridade do lado do servidor além do TLS | unknown |
| Se existe um framework estilo Genie em outra build | unknown |
