<!-- src-sha1: 4762669c756eee4725aaf5af56633f2b59edd479 -->
# WhatsApp AB Props — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** AB props / feature flags no Android: ids numéricos de flag e tabelas de valores padrão tipadas, leitores tipados e opções de leitura, camada MobileConfig (Stable IDs, unit types, `params_map_v4_u*`, `MetaConfigFetchMutation`), IQ de sync de props (`xmlns="abt"`: hash, refresh, refresh_id, delta, expo keys, sampling weights), props em nível de grupo, props de pré-registro, experimentos no dispositivo (offline), armazenamento no dispositivo, registro de exposição, caminhos de override e debug, relação com os ids de flag citados em outros relatórios, catálogo de flags por área, comparação com o Baileys

---

## 1. O que é (tecnicamente)

AB props são as feature flags do cliente controladas pelo servidor. Cada flag é identificada apenas por um **config code** numérico (por exemplo `20548`); nenhum nome de flag existe no APK. O cliente embarca uma tabela de valores padrão tipada por código, pede overrides ao servidor por um IQ, armazena a resposta em SharedPreferences e a lê por uma única classe leitora abstrata. Uma segunda camada derivada da Meta (MobileConfig) roda ao lado e pode se tornar a fonte da verdade. Todas as afirmações vêm de análise estática do APK decompilado; nada foi capturado na rede. Tiers: **found** = lido em código ou dados, **inferred** = deduzido, **unknown** = não resolvido. Os nomes ofuscados são específicos de cada build e foram re-resolvidos na 2.26.41.6.

| Camada | Nome na 2.26.41.6 | Função |
|--------|-------------------|--------|
| Base do leitor | `C00D` (abstract) | acessores tipados, caches, exposição, chave de troca para MobileConfig |
| Store principal | `C08J` (`extends C00D`, prefs `ab-props`) | mantém os cinco mapas de padrões, lê todas as flags normais |
| Store pré-chatd | `C0D9` (prefs `ab-prechatd-props`) | flags obtidas por HTTP antes de a conta estar conectada |
| Store privado | `C0ER` (prefs `ab-private-abprop`) | valores de experimentos no dispositivo, mesmos padrões de `C08J` |
| Opções de leitura | `C00F` (`AbPropsOptions`) | modo de exposição + fixação no primeiro acesso |
| Descritores tipados | `C054909t` ABPropBoolean, `C055109v` ABPropInt, `C1OT` ABPropFloat, `C055009u` ABPropString, `C055209w` ABPropJson | id + padrão no ponto de chamada |
| Gerenciador de sync | `C0D2` (`ABPropsManager`) | armazenamento, hash, refresh, backup, atualização pré-chatd |
| Requisição / resposta | `C27646BzW` (requisição), `C28894Cgv` (resposta + erro) | `<iq xmlns="abt">` |
| Gatilho | ramo default de `RunnableC48591z1` (log `MessageHandler/maybeGetNewAbProps`), `C1S0` handler de `<... abprops/>` | quando um fetch é enviado |
| Props de grupo | `C41861nA` (`GroupAbPropsManager`), `C502324k` (gatilho), `C28900Ch1` (resposta) | valores por grupo |
| MobileConfig | `C053409d` (factory), `C054709r` (`InterfaceC054609q`), `C06510El` (tabela de Stable IDs), `C34081Wt` / `C34091Wu` (lambdas tipadas), `C06460Eg`, `C053809h` (tabela de overrides), `CQN` + `C29448CqB` (fetcher), `C41251mA` (coordenador de fetch) | engine com backend nativo, fetch via MEX |
| Exposição | `C42831om`, `BxP`, `C27952CBv`, evento WAM `C44051qo` (5504) | chaves de exposição |
| AB offline | `C24976ApB`, `C27629BzE`, `C60839RQl`, `ON0` / `ON1` / `C53973OMy`, `ConfigVariable` | atribuição local de experimentos |
| Observers | `C0NE` (3 callbacks), 46 implementadores, p. ex. `CY8` | reagem a valores alterados |

Pontos decisivos:

- O espaço de ids de flag é um único espaço numérico (id máximo **39140**, 21.424 ids com padrão). `C05Z.A00(n)`, `C1XG.A0I(n)`, os ints de tipo de IQ e os ids WAM são espaços numéricos diferentes (seção 12).
- Nomes nunca chegam ao cliente. Nem nas tabelas de padrões, nem na resposta de sync (apenas `config_code`), nem em um resource.
- Existem três caminhos de sync paralelos: o IQ `abt` (nível de usuário), o IQ `abt` com `group=` (nível de grupo) e o fetch MEX do MobileConfig (seção 4).

---

## 2. Modelo de flag

### 2.1 Tipos e tabelas de padrões (found, `C08J`)

Cinco mapas imutáveis são construídos no construtor de `C08J` (`buildKeepingLast`, então puts duplicados no decompile são inofensivos). As contagens são de ids únicos por mapa:

| Tipo | Mapa | Acessores em `C00D` | Ids | Exemplo |
|------|------|---------------------|-----|---------|
| bool | `A1A()` | `A15(id)`, `A18(ABPropBoolean)`, `A0E(...)` | 16.668 (1.237 com padrão `true`) | `9667` true |
| int | `A1C()` | `A0b(id)`, `A0f(ABPropInt)`, `A02(...)` | 3.530 | `996` 604800 |
| float | `A1B()` | `A0Z(id)`, `A0a(ABPropFloat)`, `A00(...)` | 177 | `31535` 0.0 |
| string | `A1E()` | `A0j(id)`, `A0n(ABPropString)`, `A08(...)` | 867 | `34350` regex |
| JSON | `A1D()` | `A0p(id)`, `A0r(ABPropJson)`, `A09(...)` | 182 | `21995` `{}` |

Nenhum id está em dois mapas. Leituras literais estáticas (`A15(n)`, `A0b(n)`, `A0j(n)`, `A0Z(n)`, `A0p(n)`): 16.355 pontos de chamada em `p000X` e `com`; leituras por descritor vêm além disso (pontos de construção: 492 ABPropBoolean, 482 deles distintos, 259 ABPropInt, 30 ABPropFloat, 66 ABPropString, 12 ABPropJson).

Resolução do padrão (found, `C00D.A0D`, `A01`):

| Passo | Regra |
|-------|-------|
| 1 | valor em cache na memória para este processo |
| 2 | valor do servidor armazenado em prefs `ab-props` sob a chave `String.valueOf(id)` |
| 3 | padrão do mapa do tipo do id |
| 4 | padrão no ponto de chamada de um descritor ABPropX (somente quando o mapa não tem entrada) |
| 5 | nenhum: `IllegalArgumentException("Unknown BooleanField: <id>")` (int: `Unknown IntField`) |

Para todos os 482 descritores ABPropBoolean distintos, o id existe no mapa e o padrão de produção do descritor é igual ao padrão do mapa. `debugDefaultValue` de ABPropBoolean difere do padrão de produção em 182 deles, mas não é lido em lugar nenhum exceto em `equals` / `hashCode` / `toString` (smali: o campo `A02` é referenciado apenas dentro de `09t`; os acessores usam apenas o id e o padrão de produção). Não tem efeito em runtime neste build.

### 2.2 Parsing do valor ao armazenar (found, `C0D2.A00`)

| Mapa do id | Armazenado como | Parse |
|------------|-----------------|-------|
| bool | `putBoolean` | `Integer.parseInt(config_value) != 0` (forma no wire `"1"` / `"0"`) |
| int | `putInt` | `Integer.parseInt` |
| float | `putFloat` | `Float.parseFloat` |
| string | `putString` | como está |
| JSON | `putString` | validado com `new JSONObject(...)`; em caso de falha registra `ABPropsManager/invalid format for config; configCode=...` e a prop não é armazenada |
| id em nenhum mapa | `putString` | armazenado como string; uma leitura tipada desse id não tem padrão e lança exceção (2.1 passo 5) |

Diferente da tabela do WA Web (códigos desconhecidos descartados), o Android mantém códigos desconhecidos como strings (found).

### 2.3 Opções de leitura (found, `C00F` = `AbPropsOptions`)

| Constante | exposureOptions | firstAccessValue | Usado como |
|-----------|-----------------|------------------|------------|
| `A03` | WITH_EXPOSURE_LOGGING (1) | false | padrão para todas as leituras simples (`A15`, `A0b`, ...) |
| `A02` | WITH_EXPOSURE_LOGGING | true | `A19(...)`, `A16`, leituras de bootstrap do MobileConfig |
| `A06` / `A05` | WITHOUT_EXPOSURE_LOGGING (0) | false / true | `A00()` os deriva |
| `A04` | WITH_URGENT_EXPOSURE_LOGGING (2) | false | store pré-chatd quando a flag **24317** está ligada |

`firstAccessValue = true` fixa o primeiro valor lido no processo em `C00D.A07` (ConcurrentHashMap); leituras posteriores desse id retornam o valor fixado mesmo após um sync (found, `C00D.A0D`, `A0i`). Leituras simples usam o cache `A0P`, que `A0s()` limpa após cada sync.

### 2.4 Caminho de leitura e fonte da verdade (found, smali de `C00D.A07`; nomes das chaves inferidos pelo uso)

```
read(id)
  ├─ A14() true  (A0E && A0b && !A0S)  and A08 set  and MobileConfig context present
  │      └─► MobileConfig value via C34081Wt/C34091Wu  (Stable ID lookup, C054709r.B6F)
  └─ else
         ├─ legacy value: cache A0P ► prefs "ab-props" ► default map
         └─ if A0E && A0G (shadow): also read MobileConfig and compare (A0C)
```

| Campo | Fonte | Significado (inferred) |
|-------|-------|------------------------|
| `A0F` | pref `23048` (bool), somente `C08J` | MobileConfig inicializado para esta conta |
| `A0E` | `A0F` ou pref `27668` (int) > 0 | MobileConfig ativo (somente `C08J`; false para `C0D9`, `C0ER`) |
| `A0b` | pref `24896` | MobileConfig é a fonte da verdade |
| `A0S` | pref `25403`, relida em `A0s()` | override de volta ao caminho legado |
| `A0G` | pref `22646` | comparação shadow ligada |
| `A0c` | pref `38895` == 1 | cache por leitura `A0d` para valores do MobileConfig |
| `A08` | AtomicBoolean, definido em `C054709r.BN4` (init do MobileConfig) | MobileConfig pronto; só então o caminho do MobileConfig é tomado (found); resetado no construtor para false |

Todos os seis são AB props também, lidos direto do arquivo de prefs na construção (found). O modo shadow monta um registro de comparação `N25` e envia um evento de field-stats (`C56612Vl`, valor `mobile_config_inconsistent_value`) amostrado 1 em flag **22647** (padrão 10) (found). Quando o MobileConfig é a fonte e um id não tem Stable ID, a lambda tipada retorna `false` / `0` / `""` com fonte de valor `INVALID_SPECIFIER_MISSING_IN_WA_LOOKUP_MAP`, não o valor do mapa de padrões (found em `C34081Wt`; efeito nos 70 ids somente com padrão inferred).

---

## 3. Camada MobileConfig

### 3.1 Stable IDs (found, `C06510El.A0J`)

`long[39141]` indexado por config code, 21.380 entradas não zero. `C054709r.B6F(id)` retorna a entrada (0 = nenhuma). 21.354 ids existem tanto nos mapas de padrões quanto nesta tabela; 70 ids existem só nos padrões, 26 só nos Stable IDs.

| Bits | Campo | Evidência |
|------|-------|-----------|
| 0-15 | índice de slot | `C053809h.A00`: `j & 65535`; significado inferred |
| 32-47 | índice de config, `0..20780`, um por entrada na ordem dos ids | `C06460Eg.A00`: `(j >>> 32) & 65535`, `C053409d.A08(int)` |
| 48-53 | tipo de valor: 1 bool, 2 int, 3 string ou JSON, 4 float | tabulação cruzada com os mapas de padrões, sem exceção |
| 54-59 | unit type: 1 SESSIONLESS (564 ids), 2 SESSIONBASED (20.781), 6 GROUP (35) | tabulação cruzada; seção 3.2 |
| 60-63 | valor `2` sse o padrão bool é `true` | 1.231 de 1.231 ids; 6 ids com padrão true não têm Stable ID |

### 3.2 Unit types e `params_map_v4_u*` (found)

`assets/params_map_v4_u<N>.txt` é carregado por `N3E` com `N` = unit type do MobileConfig (`AbstractC24817AmY.A00`): 0 NULL_VALUE, 1 SESSIONLESS, 2 SESSIONBASED, 3 PAGEID, 4 ADMINID, 6 GROUP, 7 FAMILY_DEVICE_ID, 8 FRLID, 9 AD_ACCOUNT_ID, 10 WEARABLE_DEVICE_OWNER_ID. O sufixo é o unit type, não uma largura de valor. A biblioteca nativa traz a mesma format string `params_map_v4_u%d.txt` (`libmobileconfig-jni.so`).

| Arquivo | Unit | Entradas | Chave de versão | Ids dentro da faixa de código do WA |
|---------|------|----------|-----------------|-------------------------------------|
| `u1` | SESSIONLESS (utilizável antes do login) | 575 | 565 | 564 |
| `u2` | SESSIONBASED | 20.844 | 20785 | 20.781 |
| `u4` | ADMINID | 72 | 2 | 0 (ids 112607..121623) |
| `u6` | GROUP | 35 | 35 | 35 |

Entrada (8 bytes, dois u32 little-endian, layout do header como no arquivo: magic `v4`, verificação `0x7fff`, chave de versão, contagem, hash de 32 caracteres):

| Campo | Achado |
|-------|--------|
| `int2 >> 12` | o config code do WA: para `u1`/`u2`/`u6` coincide com a tabela de Stable IDs (564 / 20.781 / 35 acertos) e com os mapas de padrões; os 12 bits baixos são 0 em todas as entradas exceto algumas |
| 16 bits baixos de `int1` | máscara de tipo de valor: `0x881` bool, `0x1001` int, `0x1801` string/JSON, `0x2001` float (`u2`); o bit 15 está setado exatamente para padrões bool `true` (25 + 1.206 = 1.231) |
| `int1 >> 16` | número de slot corrente (inferred) |
| ids de `u4` | fora da faixa de código do WA; finalidade unknown |

Os 9 bits baixos de `int1` são apenas 1 ou 129; não são um id de parâmetro.

Os 35 ids GROUP (found): 18205, 23245, 23246, 23397, 23398, 24075, 26013, 26269, 26270, 26862, 27009, 27025, 27247, 28357, 28358, 29275, 30905, 30906, 31456, 32501, 33673, 34075, 34277, 34333, 35211, 35227, 35639, 35772, 36156, 36504, 36505, 37523, 37524, 38082, 38083. A flag **18205** é lida por grupo pelo `GroupAbPropsManager` (seção 4.7).

### 3.3 Fetch do MobileConfig via MEX (found, `CQN`, `C29448CqB`)

Mutation MEX `MetaConfigFetchMutation`, schema `whatsapp-android-www`, doc_id **28207206725568030**, campo raiz `xwa2_mobile_config_fetch`. Campos de input definidos em `CQN`: `api_version`, `fetch_type`, `unit_type`, `unit_id`, `device_id`, `query_hash`, `query_string`, `bln_queries`, `mc_debug_id`, `mobile_app_universe_type`; sempre null nos caminhos lidos: `batch_size`, `bln_li_hashes`, `bool_opt_policy`, `contact_point`. Log: `WAMobileConfigFetcher/fetchWwwConfigs/request unit_type=...`. Resposta: um blob de config entregue ao gerenciador nativo (`onComplete(true, blob)`), mais `ep_refresh_id` e `ab_key`. `ab_key` é armazenado como `mc_expo:sys:ab_key`.

`C41251mA` (`MobileConfigFetchCoordinatorImpl`) decide quando esse fetch roda após um fetch de AB props: o ABPropInt **36185** (padrão 0) seleciona a opção: valor 2 espera o retorno do offline (`waiting for offline resume`), qualquer outro valor faz fetch imediatamente; o valor 1 compara uma versão de fetch por unit armazenada com a versão de `abprops` (`C054709r.A01`), e uma requisição delta compara a versão do app do último handle com `2.26.41.6`. `C054709r.CpO` chama `updateConfigs`, log de callback `WAMobileConfigFetcher/updateConfigs() callback: succeeded=`; em caso de sucesso armazena `last_full_fetch_ms:<unit>:<key>`.

O stanza `<success>` do login também carrega `mc_ep_version` (versão de emergency-push do MobileConfig) ao lado de `props` e `abprops` (found, `HandlerThreadC12340b0`); consumidor não rastreado.

---

## 4. Sync de props

### 4.1 Requisição (found, `C27646BzW.A00(boolean force, boolean delta, int refreshId)`)

```xml
<iq to="s.whatsapp.net" type="get" id="..." xmlns="abt">
  <props protocol="1" hash="<stored config_hash | empty>" [refresh_id="<last_version>"]/>
</iq>
```

| Atributo | Regra |
|----------|-------|
| `protocol` | constante `1` |
| `hash` | `ab_props:sys:config_hash` armazenado; string vazia quando `force` ou `delta` está definido, ou nada está armazenado |
| `refresh_id` | somente quando `delta` está definido e `refreshId > 0`; valor = `ab_props:sys:last_version` armazenado |
| envio | `MessageClient.A0W(callback, node, id, 220, 32000L)`: int de tipo de requisição do IQ 220, timeout de 32.000 ms |

### 4.2 Resposta (found, `C28894Cgv.CFS`)

```xml
<iq type="result"><props ab_key="..." hash="..." refresh="86400" refresh_id="N" [delta_update="true"]>
  <prop config_code="20548" config_value="1" config_expo_key="..."/>     <!-- one per changed flag -->
  <prop event_code="1094" sampling_weight="N"/>                         <!-- event sampling, no config_code -->
</props><erid>...</erid></iq>
```

| Item | Tratamento |
|------|------------|
| `config_code` + `config_value` | armazenamento tipado conforme 2.2, com chave `String.valueOf(code)` |
| `config_expo_key` | armazenado como `<code>_expo_key` quando não vazio e o valor foi armazenado (chave de exposição do experimento / grupo em que a conta está; formato da chave unknown) |
| `ab_key` | armazenado em `ab_props:sys:config_key`; definido como atributo WAM **4473** (ambos os canais) quando o MobileConfig não é a fonte |
| `hash` | hash de conteúdo do conjunto inteiro; armazenado em `ab_props:sys:config_hash`; uma resposta sem hash e sem `delta_update` não altera nenhum valor |
| `refresh` | segundos, padrão 86400; armazenado x 1000 ms em `ab_props:sys:refresh`, piso de 600.000 ms; não atualizado por um delta |
| `refresh_id` | versão do conjunto; armazenado em `ab_props:sys:last_version` (também após um delta) |
| `delta_update="true"` | mescla nos prefs existentes; hash, key, refresh e `last_refresh_time` ficam intactos |
| hash presente | prefs anteriores copiados para `ab-props-backup` (limpo antes) |
| atualização completa (hash presente, não delta) | store limpo (mantendo `refresh` e `last_exposure_keys`), todas as props escritas |
| `event_code` + `sampling_weight` | linhas sem `config_code`; reescritas nos prefs `field-stats-events-sampling` (chave = event code, valor = peso); o código **1094** também define `app_launch_event_sampling_weight` |
| `<erid>` | rid criptografado: com a flag **3664** ligada é limpo, com **6084** ligada e valor alterado é armazenado como `encrypted_rid` |

Após uma atualização completa bem-sucedida: `last_refresh_time` = agora (ms), `fetch_app_version` = `2.26.41.6`, contadores de erro zerados, observers notificados (4.8).

### 4.3 Gatilhos (found salvo indicação)

| Gatilho | Condição |
|---------|----------|
| login `<success abprops="N">` (também `props`, `mc_ep_version`) | versão `N` > `last_version` armazenada: requisição com `force` + `delta` + `refresh_id`; modo DELTA (log `versionMismatch`) |
| mesmo caminho | `last_refresh_time + refresh < now`, ou `now < last_refresh_time` (relógio voltou; ramo lido em smali, o decompile omite o else): requisição normal com o hash armazenado; modo FULL (log `AB Props too old`) |
| filho `<... abprops/>` recebido (roteado com os filhos `log` e `push-config`; pai `ib` inferred) | `forceFetchABPropsAndMobileConfig`: `A00(true, false, 0)` (hash vazio, completo) quando o envio de mensagens está pronto; depois MobileConfig `BMu` + `CpO` |
| registro | fetch pré-chatd (4.6); atribuição offline (6) |

### 4.4 Intervalo de refresh e erros (found)

| Item | Valor |
|------|-------|
| intervalo padrão | `ab_props:sys:refresh` padrão 86.400.000 ms |
| `refresh` do servidor | segundos, x 1000, piso de 600.000 ms |
| códigos de erro contados | 207, 304, 400-503 (`C28894Cgv.Brt`); outros códigos apenas registram `unknown error code` |
| contagem de retry | `fetch_attemp_count` +1 por erro; ao chegar a 3 `last_refresh_time` = agora e o contador zera, então a próxima tentativa espera um intervalo |
| último erro | `ab_props:sys:last_error_code`, limpo em caso de sucesso |
| falha de entrega (`Bog`) | no-op |

### 4.5 Leituras durante a janela de fetch

`<props>` pode chegar depois de as primeiras telas lerem flags. A primeira leitura de um id antes de existirem dados usa o padrão; com a fixação por `firstAccessValue` (2.3) o padrão fixado permanece pelo processo (found); as telas de registro esperam com timeout pelas props online (strings de log `RegisterPhoneViewModel/cancelOnlineAbPropsTimeout`, `OnlineAbpropsAsyncStatus`, found; espera exata unknown).

### 4.6 Props pré-chatd (found, `C44707Jfc`, `C43414Iwr`, `K49`, `C0D2.A08`)

Antes de a conta estar conectada, o cliente HTTP de registro chama `checkPreChatdABProps` (`reg-onboard-abprop-request`) com `ab_hash` (pref `pref_pre_chatd_ab_hash`). O resultado traz um novo hash, um array JSON `expConfigs` de `{config_code, config_value, config_expo_key}`, um `ab_key` e um atraso até o próximo fetch (`pref_pre_chatd_ab_next_fetch_time` = agora + atraso). `C0D2.A08` limpa o store pré-chatd (`A04`) e o reescreve com as mesmas regras de tipagem (2.2) nos prefs `ab-prechatd-props`. A exposição é mantida em `pref_expo_keys` (array JSON de `<expo_key>,<timestamp>`) e enviada pelo log do funil de registro (`abprop_exposure` / `ab_prechatd_exposure`, com `ab_key` de `pref_pre_chatd_ab_key`), não pelo WAM 5504. Leituras pré-chatd usam as opções `A04` (urgent) quando a flag **24317** está ligada, senão `A03`.

### 4.7 Props em nível de grupo (found, `C41861nA`, `C502324k`, `C28900Ch1`)

```xml
<iq to="s.whatsapp.net" type="get" xmlns="abt"><props group="<group jid>" hash="<cached | empty>"/></iq>
```

Mesmo tipo 220 e 32.000 ms que em 4.1. O array de atributos da requisição tem duas entradas: `group` e `hash` (smali). Gate: flag **16206** (master) e uma conversa de grupo sendo aberta (`COK` / `Bnc`); ignorado com `reason=cacheValid` até `_nextRefreshTimeInSeconds`, ou `reason=disabled`. Resposta: `hash`, `refresh` limitado a 600..604.800 s (padrão 86.400), `refresh_id`, `<prop config_code config_value config_expo_key>`, tipada pelos mesmos mapas de padrões (bool, int, float, senão string). Os ids estão no espaço de ids compartilhado; o unit type GROUP (3.2) marca os 35 ids destinados a isso, e a leitura de flag para um grupo é `A04(groupJid, id)`. As leituras retornam `null` quando o grupo não tem valor armazenado (o chamador então recorre a outro caminho, não rastreado). Chaves nos prefs de grupo (`groupAbProps`, nome inferred a partir de `C00E`): `<jid>_<id>_value`, `<jid>_<id>_exposureKey`, `<jid>_exposureKeysSet`, `<jid>_nextRefreshTimeInSeconds`, `<jid>_lastRefreshHash`. Sem tipo JSON para valores de grupo.

### 4.8 Observers (found)

`C0NE` tem três callbacks: `BhX` antes de os novos valores serem escritos (evento 34), `Bfk` e `C2K` depois (eventos 33, 32). Exemplo `CY8` (`PQKeysUploadABPropsObserver`): guarda a flag **21198** em `BhX`; se ela passou de `true` para `false` em `Bfk`, registra `PQ_KEYS_UPLOAD_CODE changed from true to false, deleting all kyber prekeys` e enfileira `DeleteKyberPreKeysJob`. 46 classes implementam `C0NE` (contagem por grep).

---

## 5. Armazenamento no dispositivo

| Arquivo de prefs / chave | Conteúdo |
|--------------------------|----------|
| `ab-props` (`C08J`, `C0D2.A00`) | valor de `<id>`, `<id>_expo_key` e as chaves `ab_props:sys:*` abaixo |
| `ab_props:sys:config_hash`, `config_key`, `last_version`, `refresh`, `last_refresh_time`, `fetch_app_version`, `fetch_attemp_count`, `last_error_code` | estado do sync |
| `ab_props:sys:last_exposure_keys` (string set), `last_daily_expo_key_update` | estado de exposição |
| `ab_props:sys:private_experimentation_id` | id aleatório para experimentos no dispositivo (6) |
| `ab_offline_props:offline_exposure_strings`, `ab_offline_props:offline_exposure_hash_strings` | exposição de experimentos offline (em `ab-props`) |
| `ab-props-backup` | cópia do store anterior, reescrita a cada atualização completa |
| `ab-prechatd-props` | valores pré-chatd mais `pref_expo_keys` |
| `ab-private-abprop` | `last_read_time_ms` (atualizado no máximo a cada hora) e valores privados |
| `mc_expo:sys:ab_key`, `mc_expo:sys:last_exposure_keys`, `mc_expo:sys:last_exposure_keys_without_logging` | estado de exposição do lado MobileConfig |
| `field-stats-events-sampling` | event code para peso de amostragem |
| `groupAbProps` | valores de grupo (4.7) |
| `<dataDir>/mobileconfig/mc_overrides.json`, `id_name_mapping.json` | tabela de overrides do MobileConfig, mapa id-nome (nomes de arquivo encontrados em `C053409d`; ausentes do APK) |
| `pref_pre_chatd_ab_hash`, `pref_pre_chatd_ab_key`, `pref_pre_chatd_ab_next_fetch_time`, `pref_is_blocking_prechatd_exposure` | estado pré-chatd (prefs de registro) |

Todos os arquivos são abertos por `C00S.A05(name)` (um handle `SharedPreferences` no diretório de dados privado do app); não foi verificado se essa factory adiciona criptografia ou ofuscação (unknown).

---

## 6. Exposição, experimentos, grupos

### 6.1 Registro de exposição (found)

| Passo | Detalhe |
|-------|---------|
| 1 | uma leitura com registro de exposição (2.3) chama `A0B(options, this, "<id>_expo_key")` -> `A12` |
| 2 | expo key não vazia ainda ausente de `last_exposure_keys`: adicionada e persistida |
| 3 | store principal: `C42831om.A01` posta o evento WAM **5504** `WamWefrClientExposure` (`wam_wefr_client_exposure`), com debounce de pelo menos 1 s; `BxP` chama o runtime WAM (`C0D6.CYl(value, 5029, ...)`; "attribute" inferred pela forma da chamada) com as chaves unidas por vírgula (merge por fonte quando a flag **31830** está ligada) |
| 4 | após um sync completo, apenas as chaves que a nova resposta ainda traz permanecem no conjunto |
| 5 | reenvio diário: no callback de foreground `A0A0.BvR`, quando passaram mais de 24 h desde `last_daily_expo_key_update` (`sent_with_daily` = true) |
| 6 | pré-chatd: a thread de pulse `C27952CBv` envia o log do funil (4.6); o modo URGENT o aciona imediatamente |

Campos do WAM 5504 (nomes do Falco): `dedup_key`, `device_exp_id`, `exposure_key`, `from_metaconfig`, `sent_with_daily`. `device_exp_id` é uma string derivada do objeto de identidade do dispositivo (`C09E.A0J().A03()`); derivação não rastreada (unknown).

### 6.2 Ids de experimento e de grupo

| Id | Onde | Significado |
|----|------|-------------|
| `config_expo_key` | por `<prop>` | chave de exposição do braço do experimento; opaca para o cliente, apenas comparada e registrada |
| `ab_key` | atributo de `<props>` | chave do conjunto inteiro atribuído; atributo WAM 4473 |
| `refresh_id` | atributo de `<props>` | versão do conjunto; comparada com `abprops` do `<success>` do login |
| `hash` | atributo de `<props>` | hash de conteúdo usado para "sem mudança" |
| `private_experimentation_id` | local | id aleatório usado como unit para experimentos no dispositivo |
| `device_id`, `unit_id` | fetch MEX | identidade de unit do MobileConfig |

O targeting do lado do servidor (país, coorte, porcentagem) não é visível; o cliente vê apenas os valores resultantes (unknown).

### 6.3 Sampling weights (found)

As linhas `<prop event_code sampling_weight>` alimentam o logger de field-stats: por evento, um peso de amostragem 1 em N. O evento **1094** (app launch) é espelhado em `app_launch_event_sampling_weight`. A chave é um event code do WAM, não um id de flag.

---

## 7. Avaliação local, overrides, caminhos de debug

### 7.1 AB offline (found, `C24976ApB`, `C27629BzE`, `C60839RQl`)

Experimentos compilados no APK (`C60839RQl.A00`, lista de `ON0` -> `ON1` -> `C53973OMy` -> `ConfigVariable{id, name, value, type}`) são avaliados contra um mapa local de user-info e escritos no store `ab-props` com as mesmas regras de tipagem. As condições (árvore `RM2`) só podem usar as propriedades `platform`, `app_version`, `app_build`, `release_channel`, `os_version` (`C0ER.A0B`). Chaves de user-info: `device_id`, `app_build`, `release_channel`, `app_version`, `os_version`, `platform`, `country` (país do SIM), `private_experimentation_id`. Neste beta `app_build` e `release_channel` são a constante `beta`. Na atribuição, as chaves de sync (`config_hash`, `last_refresh_time`, `fetch_app_version`, `last_version`) são removidas para que o próximo fetch online seja completo, e um log crítico `abprops-offline-assigned-after-registration-verified` dispara quando a atribuição ocorre com `registration_state == 3`. As definições dos experimentos não são enumeradas aqui (unknown).

### 7.2 Overrides do MobileConfig (found, efeito inferred)

`C053809h` carrega `mc_overrides.json` (`hasOverridesFile`, `boolOverrideForParam`, `intOverrideForParam`, `stringOverrideForParam`, `doubleOverrideForParam`, com chave no Stable ID de 64 bits empacotado), `C053409d.getOrCreateOverridesTable` o devolve ao engine. Os overrides se aplicam apenas ao caminho do MobileConfig, não ao caminho legado de prefs. Se o engine consulta a tabela em um build de release é unknown; sem evidência de teste em runtime.

### 7.3 Deep link `override-abprops` (found)

Host do manifest `whatsapp-consumer://override-abprops` (alias exportado de `DeepLinkActivity`). `IJB` o mapeia para o destination id 154. `DeepLinkActivity.A0w` faz o parse do segmento de path `bugbash` e dos parâmetros de query `feature_name`, `feature_id`, `category`, `min_app_version`, `ready_to_test_time` e `variants` (array JSON em base64 de `{label, abprops:[{abprop_key, abprop_value}]}`) em `BugBashSession` / `BugBashVariant`. Existe um motivo de erro `abprop_override_not_allowed`. Nenhum código que escreva `abprop_key` / `abprop_value` em algum store de props foi encontrado: `BugBashVariant` é referenciado apenas pelo parser e seu serializador, e `bugbash_session` é apenas lido (`C51723Mxj`). Condição de gate e caminho de aplicação são unknown.

### 7.4 Outros

| Caminho | Detalhe |
|---------|---------|
| ABPropBoolean `debugDefaultValue` | declarado (182 diferem), nunca lido (2.1) |
| UI de debug | `com.whatsapp.backup.debugscreen.BackupAbPropsUiState` (apenas nome de classe, tela de debug de backup) |
| Profiler por leitura | prefs `31165` (int) e `32010` (bool) alimentam `C00D.A0H/A0I/A0J` e uma classe contadora (`Pr8`); finalidade não resolvida |

---

## 8. Ids de flag citados em outros relatórios (verificados na 2.26.41.6)

Todo id foi procurado nos mapas de padrões e na tabela de Stable IDs. Os tipos são os tipos dos mapas.

| Relatório | Resultado |
|-----------|-----------|
| `WA_BAN_SYSTEM_DEEP_EN.md` | 11061, 11064, 11065 (int 86400), 12709, 16349, 19793, 19893, 26697, 27269, 14837, 25631 presentes, bool padrão false; 12840 e 20278 são mapas **JSON** (padrões coincidem); 31535 / 31536 são **float**, padrão 0.0. **34166 não é uma flag**: sem padrão, sem Stable ID; `ContactInfoActivity.A0K = C1XG.A0I(34166)` é um id de injeção (os vizinhos 34165, 34168, 34169 são do mesmo tipo). 2923 ausente (como reportado) |
| `WA_TCTOKEN_CSTOKEN.md` | todos os 16 ids presentes; padrões: 996 / 865 / 26897 = 604800, 997 / 909 = 4, 3802 / 22012 = 26, 4063 = 0, 20606 = 2000, todos os ids bool false. `299` é o int de tipo de requisição do IQ de privacy token, não uma flag |
| `WA_META_AI.md` | 25119, 26189, 27083, 37227, 37852, 37054 bool false; **26190 é JSON**, padrão `""` |
| `WA_USERNAME.md` | todos os 18 presentes com os padrões documentados; **34350 é uma entrada de mapa string** (regex), **21995 uma entrada de mapa JSON** |
| `WA_USYNC.md` | todos os 21 ids de flag presentes com os padrões documentados (730 = 35, 471 = 1140, 9667 / 33609 / 20988 = true) |

O mesmo espaço de códigos aparece no WA Web: para 11 nomes de prop conhecidos da tabela pública de props do WA Web, a entrada Android tem o mesmo código, tipo e padrão (p. ex. 22797 JSON `{}`, 32276 string `info_card, list_card`, 26270 int 1209600, 35639 int -1, 12539 bool true, 25071 / 1133 / 23245 / 28357 / 27009 / 6939 bool false) (found para o lado Android, inferred para "mesma prop"). Ids somente do Web (3042, 30590, 24037, 25322) não têm padrão no Android. 12 dos 16 ids de nível de grupo do Web são os ids GROUP do Android (3.2).

---

## 9. Nomes e categorias

| Tópico | Achado |
|--------|--------|
| Nomes | nenhuma tabela de nomes legíveis encontrada em dex ou assets (uma busca por dois nomes de flags legadas conhecidas só encontrou strings de log); `id_name_mapping.json` é apenas um nome de arquivo de runtime em `C053409d` |
| Nomes em logs | algumas strings de log reutilizam nomes: `PQ_KEYS_UPLOAD_CODE` (21198), `abprop_override_not_allowed`; nomes de builds antigos ou do WA Web são o único caminho para a semântica |
| Categorias | sem campo de categoria. A estrutura vem do unit type (SESSIONLESS 564, SESSIONBASED 20.781, GROUP 35) e do tipo de valor |
| Mais lidos | os ids literais mais lidos: **20548** (bool true, 511 pontos), **9970** (false, 312), **1107** (false, 151), **12267** (true, 147), **1600** (string `{"allowed_product_type":"none"}`, 146), **27008** (false, 104), **13989** (int 7, 87). Semântica não resolvida |

---

## 10. Catálogo de flags por área (padrões encontrados em `C08J`; uso lido dos outros relatórios e reverificado aqui)

### 10.1 Infraestrutura de sync e MobileConfig

| Flag | Tipo | Padrão | Controla |
|------|------|--------|----------|
| **23048** | bool | false | MobileConfig inicializado (`A0F`) |
| **27668** | int | 0 | `AbstractC06100Cm.A0E`; > 0 ativa o MobileConfig (`A0E`) |
| **24896** | bool | false | MobileConfig é a fonte da verdade (inferred) |
| **25403** | bool | false | de volta à fonte legada (inferred) |
| **22646** | bool | false | comparação shadow |
| **22647** | int | 10 | amostragem do log shadow |
| **38895** | int | 0 | `== 1`: cache MobileConfig por leitura |
| **26524**, **28443**, **30441**, **30556** | bool | false | opções da factory do MobileConfig (`CbW`, `BMu`) |
| **26525** | int | 600 | opção da factory do MobileConfig (`CbW`), unidade não resolvida |
| **26640** | bool | false | parâmetro de init do MobileConfig (`BN4`) |
| **35778** / **36185** | int | 0 | fase de init / opção de timing do fetch (`C054709r.APn`, `C41251mA.A00`) |
| **24317** | bool (SESSIONLESS) | false | leituras pré-chatd usam exposição urgent |
| **31830** | bool | false | merge por fonte do atributo de exposição 5029 |
| **16206** | bool | false | gate master das props de grupo |
| **18205** | bool (GROUP) | false | leitura por grupo em `GroupAbPropsManager` |
| **3664** / **6084** | bool | false | limpar / definir `encrypted_rid` |
| **21198** | bool | false | `PQ_KEYS_UPLOAD`: upload de prekeys Kyber; `true` para `false` as exclui |

### 10.2 Ban e integridade (`WA_BAN_SYSTEM_DEEP_EN.md`)

11061, 11064, 11065 (int 86400), 12709, 16349, 19793, 19893, 26697, 27269, 14837, 25631 (bool false); 12840 (JSON `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}`); 20278 (JSON `{"max_messages": 10000, "farthest_time_days": 30}`); 31535 / 31536 (float 0.0).

### 10.3 Privacy token e cstoken (`WA_TCTOKEN_CSTOKEN.md`)

| Flag | Tipo | Padrão |
|------|------|--------|
| **996** / **997** | int | 604800 / 4 |
| **865** / **909** | int | 604800 / 4 |
| **4063** | int | 0 |
| **3802** / **22012** | int | 26 / 26 |
| **20605** / **14303** / **15491** | bool | false |
| **20606** | int | 2000 |
| **24915** / **24941** / **18639** / **25253** | bool | false |
| **26897** | int | 604800 |

### 10.4 Meta AI, username, USync

| Relatório | Flags (padrão) |
|-----------|----------------|
| `WA_META_AI.md` | **26189**, **27083**, **25119** (sem leitor), **37227**, **37852**, **37054**: bool false; **26190** JSON `""` |
| `WA_USERNAME.md` | **4745**, **20189**, **23817**, **21199**, **16033**, **8421**, **12402**, **28678**: bool false; **21995** JSON `{}`; **20494** 3, **20459** 35, **34347** 4, **34348** 6, **28127** 30, **29327** 60; **34350** string `^([0-9]{4}\|[A-Z0-9]{6})$` |
| `WA_USYNC.md` | **5751**, **5839**, **20798**, **29769**-**29771**, **9732**, **33432**, **14565**, **26739**, **31261**: bool false; **9667**, **33609**, **20988**: true; **730** 35, **471** 1140, **37780** 0 |

### 10.5 Nível de grupo (unit GROUP, 35 ids)

Bool false: 18205, 23245, 23246, 26013, 26269, 26862, 27009, 27025, 28357, 28358, 29275, 30905, 30906, 31456, 32501, 34075, 35211, 35772, 36156, 36504, 36505, 38082, 38083. Int: 26270 (1209600 s = 14 dias), 27247 (0), 23397 / 23398 / 24075 / 34277 / 34333 / 35227 / 35639 / 37523 / 37524 (-1). String: 33673 (`none`). Os nomes de 26270, 23245, 23246, 26269, 30905, 30906, 28357, 28358, 27009, 27025, 35639, 35772 vêm do WA Web (histórico de grupo e configurações de enquete; inferred).

---

## 11. Baileys (`baron-baileys-v2`, `src/Socket/chats.js`)

| Tópico | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| requisição de usuário | `fetchABProps(protocol='1', hash, refreshId)`: `<props protocol hash? refresh_id?>` em `xmlns="abt"` | mesma forma; `hash` sempre presente (vazio quando forçado), `refresh_id` apenas com delta |
| requisição de grupo | apenas `{ group }` | `group` + `hash` (array de 2 em smali) |
| chaves da resposta | `reduceBinaryNodeToDictionary(props, 'prop')`: dicionário `config_code` -> `config_value` | armazenamento tipado; `config_expo_key`, linhas `event_code`, `hash`, `refresh`, `refresh_id`, `delta_update` são todos usados |
| lookup | por nome de flag (`abProps['stella_interop_enabled']`) | apenas por código numérico |
| props legadas | `fetchProps`: `xmlns="w"` `<props protocol="2" hash>` props nomeadas | nenhum builder encontrado; os nomes aparecem apenas no dicionário de tokens de stanza (`AbstractC40911lb`) |
| refresh | nenhum (uma vez por conexão) | intervalo + checagem de versão + push |

| Sintoma | Causa | Correção |
|---------|-------|----------|
| `abProps['<name>']` é `undefined` | a resposta `abt` traz apenas `config_code` | usar o código como chave; o espaço de códigos é o da seção 8 |
| uma chave `undefined` aparece no dicionário | linhas `event_code` / `sampling_weight` não têm `config_code` | ignorar linhas sem `config_code` |
| valores desatualizados | sem tratamento de hash / refresh / `refresh_id`, sem delta | armazenar `hash`, `refresh`, `refresh_id`; enviar `hash` e `refresh_id` na próxima requisição |
| bool lido como string truthy | `config_value` é `"1"` / `"0"` | fazer parse por tipo (`!= 0`) |

---

## 12. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|----------|
| `ABPropsManager/onABPropError; unknown error code: N` | erro fora de 207 / 304 / 400-503 | nenhuma; contador não avança |
| 3 fetches com falha, sem retry por um dia | `fetch_attemp_count` chegou a 3, `last_refresh_time` = agora | esperar um intervalo ou um aumento de versão `abprops` no login |
| `AbPropProtocolHelper/onReceiveABProps failed to parse response` (`C49828Lvo`) | `<props>` malformado | exceção relançada, store intocado |
| `ABPropsManager/invalid format for config; configCode=N; value=V` | int/float não numérico ou JSON inválido | essa prop é ignorada |
| `IllegalArgumentException: Unknown BooleanField: N` | leitura tipada de um id sem padrão no mapa e sem padrão no descritor | adicionar padrão; `N` é um config code |
| leitura do MobileConfig retorna `false` / `0` / `""` | o id não tem Stable ID (`INVALID_SPECIFIER_MISSING_IN_WA_LOOKUP_MAP`) | ler pelo caminho legado |
| `WAMCEvaluation/invalid json format; key=N` | valor de flag JSON não parseável no caminho do MobileConfig | `JSONObject` vazio retornado |
| `GroupAbPropsClient/malformedResponse ... noPropsChild` / `parseFailed` | resposta de grupo sem `<props>` ou parse ruim | nenhum valor de grupo armazenado |
| `GroupAbProps/fetchSkip reason=cacheValid` / `disabled` | antes de `_nextRefreshTimeInSeconds` / flag 16206 desligada | nenhuma |
| `ABPreChatdProps/exception ... error add expo key` | JSON de `pref_expo_keys` corrompido | chave não adicionada |

---

## 13. Distinções-chave

| Não confundir | Detalhe |
|---------------|---------|
| config code vs id de injeção | `A15(20548)` é uma flag; `C05Z.A00(66)`, `C1XG.A0I(34166)`, `C00C.A02(61)` são ids de dependência |
| config code vs tipo de requisição do IQ | `A0W(..., 220, 32000L)` (220 aqui, 299 no IQ de privacy token) é um int de tipo de requisição |
| config code vs ids WAM | 5504 é um evento, 5029 e 4473 são atributos WAM, 1094 é um event code nas linhas de sampling |
| config code vs Stable ID | o código (<= 39140) indexa a tabela; o Stable ID é um specifier de 64 bits do MobileConfig |
| IQ `abt` vs props `w` vs tabela `props` do DB | `abt` = AB props numéricas; props `w` legadas = props nomeadas do servidor; a tabela SQL `props` = store chave-valor local |
| props de usuário vs props de grupo | mesmo espaço de ids, mesmos mapas; valores de grupo ficam em `groupAbProps`, com chave pelo jid do grupo, unit GROUP |
| `ab_key` vs `config_expo_key` vs `hash` vs `refresh_id` | chave do conjunto / chave de experimento por prop / hash de conteúdo / versão |
| `abprops` do login vs `<props refresh_id>` | versão atual do servidor vs a versão armazenada da última resposta |
| MEX `MetaConfigFetchMutation` vs `abt` | blob do MobileConfig vs props numéricas legadas; ambos rodam quando o MobileConfig está ativo |
| padrão de produção vs padrão de debug | apenas o padrão de produção é lido |
| fixação no primeiro acesso vs cache normal | valores fixados sobrevivem a syncs até o fim do processo |
| atribuição offline vs online | experimentos offline escrevem no mesmo store e depois forçam um fetch online completo |

---

## 14. Fluxo completo

```
[Server]            [Login]                 [C0D2 / C27646BzW]               [C08J reads]         [WAM]
   │ <success abprops=N props mc_ep_version>   │                                   │                 │
   ├──────────────────►│ N > last_version? or  │                                   │                 │
   │                   │ last_refresh+refresh<now                                  │                 │
   │                   ├──────────────────────►│ <iq xmlns=abt>                    │                 │
   │◄───────────────────────────────────────── │  <props protocol=1 hash [refresh_id]>             │
   │ <props ab_key hash refresh refresh_id [delta_update]>                          │                 │
   │   <prop config_code config_value config_expo_key/> ... <prop event_code sampling_weight/>      │
   ├──────────────────────────────────────────►│ typed store per id (bool/int/float/string/JSON)   │
   │                                           │ backup, hash, refresh, last_version, ab_key       │
   │                                           ├─ observers BhX ► write ► Bfk / C2K ──────────────►│
   │                                           │ A0s(): clear read cache                           │
   │                                           │                                   │                 │
   │ <ib><abprops/>  (force, empty hash) ─────►│                                   │                 │
   │                                           │                                   │                 │
   │                                      A15(id) / A0b(id) / A0j(id)...           │                 │
   │                                           │          cache ► prefs ► default map ► (descriptor)│
   │                                           │          MobileConfig path if A0E && A0b && !A0S   │
   │                                           │                                   ├ first read ────►│ 5504 exposure
   │                                           │                                   │ + 24 h resend   │ 5029, 4473
   │                                           │                                   │                 │
   │ MEX MetaConfigFetchMutation ◄─────────────┼── C41251mA (option 36185) ────────┤                 │
   │ xwa2_mobile_config_fetch {blob, ep_refresh_id, ab_key} ───► native MobileConfig, Stable IDs    │
   │                                           │                                   │                 │
   │ <iq xmlns=abt><props group hash> (group opened, flag 16206) ► groupAbProps ► A04(groupJid,id)   │
```

---

## 15. Unknowns

| Tópico | Motivo |
|--------|--------|
| Semântica das flags | sem nomes; semântica apenas onde um ponto de chamada ou outro relatório a resolve |
| Atribuição no servidor | targeting, porcentagens de rollout, definições de experimentos não estão no cliente |
| Stanza pai do filho de push `abprops` | handler registrado sob o message code 235; `ib` inferred |
| Ligação entre o `abprops` do login e o argumento de versão do gatilho | o gatilho recebe um `Integer`; o parse do login define um `AtomicReference`; conexão inferred |
| `mc_overrides.json` do MobileConfig em builds de release | o código da tabela existe; sem evidência de que seja consultada ou gravável pelo usuário do app |
| Gate e caminho de aplicação do `override-abprops` | o motivo `abprop_override_not_allowed` existe; nenhum escritor em um store de props encontrado |
| Derivação de `device_exp_id`, formato de `config_expo_key` | não rastreado |
| Bits 0-15 do Stable ID, entradas de unit `u4`, `int1 >> 16` | significado não resolvido |
| Prefs `31165`, `32010`, flag `35778`, valores `36185` 1 / 2 | parcialmente lidos (`Pr8`, coordenador) |
| Comportamento dos 70 ids somente com padrão sob MobileConfig | a lambda tipada retorna valores zero (found); efeito nas funcionalidades não rastreado |
| Semântica de delta no servidor | quais props um delta carrega |
| Tráfego real e valores servidos ao vivo | apenas análise estática |
