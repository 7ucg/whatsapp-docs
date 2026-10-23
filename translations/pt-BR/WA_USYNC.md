<!-- src-sha1: 8e15828bcc50ba6f6a9c5388872afeef15451af0 -->
# WhatsApp USync — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** USync IQ (`xmlns="usync"`): modos, contextos e tipos de sync, estrutura dos stanzas de requisição e resposta, protocolos de consulta (contact, sidelist, status, text_status, picture, business, devices, disappearing_mode, lid, username), busca de contatos e descoberta de números de telefone, sync da lista de dispositivos, verificações de key-index e ADV, mapeamento de LID, enriquecimento com privacy token, MEX `UsyncQuery` e roteamento por protocolo, rate limits e backoff, gatilhos no cliente, feature flags, comparação com o Baileys

---

## 1. O que é (tecnicamente)

USync é a consulta em lote "quem é este usuário". Um IQ carrega uma lista de usuários e uma lista de protocolos (tipos de dados); o servidor responde por usuário e por protocolo. O mesmo formato de stanza atende quatro funções: upload e download da agenda de contatos, buscas unitárias de número de telefone, atualização de dados de perfil (status, foto, business, disappearing mode) e atualização da lista de dispositivos para o fan-out de mensagens. Todas as afirmações vêm de análise estática do APK decompilado; nada foi capturado na rede. Tiers: **found** = lido no código, **inferred** = deduzido, **unknown** = não resolvido. Os nomes ofuscados mudam a cada build e foram resolvidos novamente na 2.26.41.6.

| Camada | Nome na 2.26.41.6 | Função |
|--------|-------------------|--------|
| Builder / parser de stanza | `C18670m9` (log tag `UniSyncProtocolHelper`): `A06` build, `A07` send, `CFS` result, `Brt` iq error, `Bog` delivery failure | monta `<iq xmlns="usync">`, faz o parse do resultado `<usync>` |
| Modelo de requisição | `A05` (tipo + usuários + opções), `A0A` (builder por usuário), `C222649hm` (requisição por usuário), `C222589hg` (requisição pendente, uma por iq id) | o que perguntar |
| Tipo de sync | `EnumC21760rz` (30 valores), `EnumC21770s0` contexto, `EnumC21780s1` modo, `EnumC21790s3` escopo | origem dos atributos `mode` / `context` |
| Buscas unitárias | `C23638AId` (`ContactQuerySync`) | número de telefone, JID, username, LID para username |
| Sync em lote | `C18580m0` (`ContactSyncHelper`), callback anônimo `X.0m7` | sync multiprotocolo, escolha entre MEX e clássico, prefs de backoff |
| Pontos de entrada públicos | `C18230lP` (`ContactSyncMethods`), builder `C21810s5`, requisição `C21830s7`, conjunto de protocolos `C21820s6`, motivo `EnumC21800s4` (77 valores) | todas as funcionalidades chamam estes |
| Aplicador de resultado | `N27` (`contactsyncresultupdater`), `C51909N4g` (`ContactSyncDevicesUpdater`) | grava no DB, mapa de LID, dispositivos |
| Dispositivo / ADV | `C23310uY` (`DeviceSyncManager`), `SyncDevicesJob`, `C24230w2` (`DeviceADVInfoHandler`) | jobs de atualização de dispositivos, verificação de key-index |
| Enriquecimento de privacidade | `C223659jg` (`ProfilePrivacyEnrichmentFetcher`), `C197138a8`, `C197148a9` | tctoken e grupo em comum por usuário |
| Variante MEX | `C229259vZ` (`MexUsyncQueryHelper`), `M4I` (rota), `M5H` (bit de protocolo) | `UsyncQuery` e roteamento |
| Armazenamento de backoff | `C18800mM`, arquivo de prefs `contact_sync_prefs` | `*_sync_backoff`, `*_full_sync_wait` |

Pontos decisivos:

- O builder do Android emite dez filhos de consulta: `contact`, `sidelist`, `status`, `text_status`, `picture`, `business`, `devices`, `disappearing_mode`, `lid`, `username`. Ele **não** tem filho `bot` nem filho de feature (found, todas constantes string de `A06`). `reachability`, `linked_profiles`, `orgs` e `ddm` existem apenas na variante MEX (seção 8).
- O Android tem quatro modos e dez contextos (seção 2); toda requisição carrega `sid`, `index="0"`, `last="true"` nos pontos de entrada lidos.
- Os usuários vão em `<list>` (normal) ou `<side_list>` (contatos fora da agenda).
- Requisições de perfil carregam uma prova de privacidade por usuário (tctoken armazenado ou JID de grupo em comum), ver seção 7 e WA_TCTOKEN_CSTOKEN.md.
- Buscas por username estão em WA_USERNAME.md; este relatório registra apenas as partes compartilhadas do stanza.

---

## 2. Envelope do stanza

### 2.1 Requisição (found, `C18670m9.A06`)

```xml
<iq xmlns="usync" id="0AB1" type="get">                       <!-- `to` added by the sender, inferred -->
  <usync sid="sync_sid_query_<uuid>" index="0" last="true"
         mode="query" context="interactive" [allow_mutation="true"]>
    <query>                                                   <!-- protocol children, section 3 -->
      <contact [addressing_mode="lid"]/> <devices version="2"/> <picture type="preview" size="N"/> ...
    </query>
    <list>      <user jid="..." [common_gid="..."]> per-user children </user> ... </list>
    <side_list> <user jid="LID" pn_jid="PN"> ... </user> ... </side_list>
  </usync>
</iq>
```

| Parte | Regra (código) |
|-------|----------------|
| iq `id` | `C10140Tq.A0G()`: `"0"` + hex de um contador, volta a zero em 65536 (loga "iqId too large") |
| `sid` | `AbstractC43461pq.A00(prefix)` = prefix + `_` + UUID aleatório; prefixos `sync_sid_query`, `ContactSyncHelper/sync_sid_<scope>`, `..._mex_profile` |
| `index` / `last` | vêm da chamada: `A07` sempre passa `0` e `true` |
| `mode`, `context` | `EnumC21780s1.modeString`, `EnumC21770s0.contextString` do tipo de sync |
| `allow_mutation="true"` | definido quando `A05.A04` é true: construído para tipos full / delta quando `C11980aQ.A0G()` vale (significado não rastreado) |
| filho contact | presente quando alguma requisição pede contact (`A05.A03`) ou quando nenhum outro protocolo é pedido |
| contexto REGISTRATION | enviado por `C10140Tq.A0A(...)` em vez de `A06(...)` (found); diferença não rastreada |
| Opções de envio | argumento de timeout do iq 32000 ms (`ContactQuerySync`) ou 128000 ms (`ContactSyncHelper`); numérico `102` passado ao sender (significado unknown) |

### 2.2 Modos (found, `EnumC21780s1`)

| `mode` | Significado |
|--------|-------------|
| `full` | ressincronização completa do escopo |
| `delta` | apenas as mudanças desde o último sync |
| `query` | consulta dos usuários listados, sem mudança de estado |
| `download` | baixa o conjunto de contatos do lado do servidor |

### 2.3 Contextos (found, `EnumC21770s0`)

`metadata`, `registration`, `interactive`, `background`, `notification`, `message`, `add`, `voip`, `snapshot`, `wamo`.

### 2.4 Tipos de sync (found, `EnumC21760rz`)

Nome, código wire, contexto / modo / escopo. Os códigos 10-15 e 17-20 não são usados. Escopo `PB` = phone book, `SL` = side list, `MP` = consulta multiprotocolo. O código é logado e mantido nas métricas; o stanza carrega apenas contexto e modo.

| Nomes (código) | Contexto / modo | Escopo |
|----------------|-----------------|--------|
| `REGISTRATION_FULL` (0) | registration / full | PB+SL |
| `INTERACTIVE_FULL` (1), `INTERACTIVE_DELTA` (2) | interactive / full, delta | PB+SL |
| `BACKGROUND_FULL` (3), `BACKGROUND_DELTA` (4) | background / full, delta | PB+SL |
| `NOTIFICATION_CONTACT` (5) | notification / delta | PB |
| `INTERACTIVE_QUERY` (6), `ADD_QUERY` (9) | interactive / query, add / query | PB |
| `NOTIFICATION_SIDELIST` (7) | notification / query | SL |
| `INTERACTIVE_DELTA_SIDELIST` (8) | interactive / delta | SL |
| `BACKGROUND_QUERY_PICTURES` (16), `BACKGROUND_MULTI_PROTOCOL_QUERY` (21), `BACKGROUND_COMPANION_MULTI_PROTOCOL_QUERY` (22) | background / query | MP |
| `REGISTRATION_COMPANION_MULTI_PROTOCOL_QUERY` (23) | registration / query | MP |
| `INTERACTIVE_MULTI_PROTOCOL_QUERY` (24), `MESSAGE_MULTI_PROTOCOL_QUERY` (25), `VOIP_MULTI_PROTOCOL_QUERY` (26) | interactive, message, voip / query | MP |
| `NOTIFICATION_MULTI_PROTOCOL_QUERY` (27), `LID_MIGRATION_NOTIFICATION_MULTI_PROTOCOL_QUERY` (28) | notification / query | MP |
| `LID_MIGRATION_MESSAGE_MULTI_PROTOCOL_QUERY` (29), `WAMO_MULTI_PROTOCOL_QUERY` (38) | message, wamo / query | MP |
| `CONTACT_DONWLOAD` (30, sic) | background / download | PB |
| `CONTACT_FORCE_UPLOAD` (31) | metadata / delta | PB+SL |
| `CONTACT_UPLOAD` (32), `NATIVE_CONTACT_DELTA` (39) | background / delta | PB |
| `CONTACTS_PROVIDER_WHATSAPP_ACCOUNT_SYNC` (33) | background / full | PB |
| `CONTACT_UPLOAD_SNAPSHOT` (34), `CONTACT_DOWNLOAD_SNAPSHOT` (35), `CONTACT_FULL_SYNC_SNAPSHOT` (36) | snapshot / delta, download, full | PB, PB, PB+SL |
| `CONTACT_RESTORE_FULL_SYNC` (37) | background / full | agenda de contatos do WA |

Helpers: `A00()` = delta, `A01()` = full, `A02()` = full e registration. Apenas `BACKGROUND_QUERY_PICTURES` faz o tipo da consulta de foto ser `image`; todos os outros tipos pedem `preview`.

---

## 3. Protocolos de consulta

### 3.1 Visão geral (found)

| Protocolo | Filho de `<query>` | Filho de requisição por usuário | Filho de resposta (por usuário) | Notas |
|-----------|--------------------|---------------------------------|---------------------------------|-------|
| contact | `<contact/>` | `<contact>+digits</contact>`, `<contact username=.. lid=.. pin=../>`, `<contact type="delete"/>`, `<contact/>` vazio | `<contact type="in\|out\|invalid">text</contact>` | apenas em `<list>` |
| sidelist | `<sidelist [addressing_mode="lid"]/>` | `<sidelist type="delete"/>` | `<sidelist type=..>` em `<side_list>` | usuários fora da agenda |
| status | `<status/>` | `<status t="secs"/>` quando existe um horário em cache | `<status t code type>text</status>` | texto do Recado |
| text_status | `<text_status/>` | nenhum | `<text_status last_update_time ephemeral_duration_sec text><emoji content/></text_status>` | flag **5839** |
| picture | `<picture type="image\|preview" [size="N"]/>` | `<picture id="N"/>` id em cache | `<picture id direct_path hash/>` | enriquecido com privacidade |
| business | `<business><verified_name/><profile v="N"/></business>` | `<business><verified_name serial/><profile tag/></business>` | `<business pn_jid><verified_name verified_level host_storage actual_actors privacy_mode_ts>cert</verified_name>...</business>` | `v` = AB **471** & 0x3FFC (padrão 1140) |
| devices | `<devices version="2"/>` | `<devices device_hash ts expected_ts/>` | `<devices><device-list><device id key-index is_hosted/></device-list><key-index-list ts expected_ts>bytes</key-index-list></devices>` | seção 5 |
| disappearing_mode | `<disappearing_mode/>` | nenhum | `<disappearing_mode duration t ephemerality_disabled/>` | `ephemerality_disabled` lido apenas com a flag **21235** |
| lid | `<lid/>` | `<lid jid="LID"/>` quando o usuário PN tem um LID conhecido | `<lid val="LID"/>` | seção 6 |
| username | `<username/>` | `<username username="@known"/>` | `<username>text</username>` ou `contact@username` | ver WA_USERNAME.md |

Atributos por usuário em `<user>`: `jid` (PN ou LID), `pn_jid` (entradas de side list), `common_gid` (seção 7). Um usuário também pode conter um filho `<tctoken>` com os bytes do token armazenado. Nas respostas, `<user>` também tem `pn_jid` e `new_jid`; o parser usa `jid` e recorre a `pn_jid` quando `jid` está ausente.

### 3.2 Contact (found)

| Forma | Condição | Notas |
|-------|----------|-------|
| `<contact>+15550001111</contact>` | busca por telefone | a string do número é repassada como o chamador a fornece; em buscas baseadas em JID, `C23638AId.A05` adiciona o prefixo `+` quando o JID é um JID de número de telefone e (`C11980aQ.A0M()` / AB **26739** está ligado, ou o tipo é `ADD_QUERY`) |
| `<contact>15550001111</contact>` | usuário PN com endereçamento LID (`C11980aQ.A0L()`, AB **14565**) | dígitos sem `+` |
| `<contact username="u" [lid=".."] [pin=".."]/>` | busca por username | `lid` / `pin` apenas com AB **12402**, caso contrário apenas `username` |
| `<contact type="delete"/>` | requisição marcada como excluída | remoção da agenda no sync de upload |
| `<contact/>` | usuário LID sem username | placeholder |
| consulta `<contact addressing_mode="lid"/>` | AB **14565** | sync de contatos com endereçamento LID |
| consulta `metadata_version="3"` | tipo delta e uma flag interna | a flag só é atribuída a partir de uma constante false no caminho lido, então provavelmente nunca é enviada (inferred) |

`type` da resposta: `in` = registrado (código interno 1), `out` = não registrado (2), `invalid` = número inválido (3); qualquer outro valor lança um erro de stream corrompido. O conteúdo de texto de cada `<contact>` é anexado a uma lista por usuário.

`<result><contact version refresh integrity snapshot_recovery>` no nível do resultado: `version` mantido no resultado, `refresh` em segundos alimenta a espera do full sync (seção 9), `integrity` é `pass` (padrão), `pending` ou `timelock` (interno 1 / 2 / 3), `snapshot_recovery` (`pending` / `pass`) é lido apenas com a flag **22410**.

### 3.3 Status e text status (found)

Tratamento do resultado de `<status>`: `type="fail"` com `code` 401 / 403 / 404 = oculto pela privacidade (estado interno 2); outro `fail` = falha (0); texto não vazio sem erro = definido (1, `t` * 1000 = horário de definição); vazio sem erro e flag de text-status desligada = nenhum (3). Os nomes dos estados são inferred.

Com a flag **5839** ligada, um filho `<text_status>` sobrescreve o estado 1 / 3: texto = `text`, emoji = `<emoji content>` (padrão "" quando ausente), horário de definição = `last_update_time` em segundos, expiração = horário de definição + `ephemeral_duration_sec` quando isso é maior que 0 (estado 3). Um status oculto (estado 2) é um nó de falha com 401 / 403 / 404, não uma string vazia.

### 3.4 Picture, business, disappearing mode (found)

| Protocolo | Detalhe da requisição | Parse da resposta |
|-----------|-----------------------|-------------------|
| picture | `type="preview"` mais `size` apenas quando AB `AbstractC36291cD.A06` é maior que 0 (limitado a 300); `id` por usuário apenas quando existe um id em cache | `id` (int, -1 quando não há `<picture>`), `direct_path`, `hash` |
| business | `profile v` = `C35756Fe7.A00()` = AB 471 & 16380; `serial` / `tag` por usuário apenas a partir da linha de business local | `pn_jid` (preenche o PN de um usuário LID e armazena o par LID-PN), `verified_name`: `verified_level`, `host_storage`, `actual_actors`, `privacy_mode_ts`, bytes do nó = certificado |

---

## 4. Busca de contatos e descoberta de números de telefone

### 4.1 Buscas unitárias (found, `C23638AId`)

| Método | Tipo | Monta | Resultado |
|--------|------|-------|-----------|
| `A0E(userJid, type, n)` | apenas `INTERACTIVE_QUERY` ou `ADD_QUERY` | JID do usuário + contact, status, picture, business, disappearing_mode, lid, username; devices se **5751**; text_status se **5839** | `C43621q7` |
| `A0C` / `A0A(type, n, number)` | os mesmos dois tipos | número de telefone como `<contact>`; mesmo conjunto (status apenas quando o chamador passa true) | `Pair(result, user)` |
| `A0B(type, n, number)` ("Lightweight") | qualquer | telefone + contact, lid; devices se **5751** | `Pair` |
| `A0D(type, numbers)` | qualquer | vários números: contact, status, picture, business, disappearing_mode, lid; text_status se **5839** | array de usuários |
| `A0F(lid)` | `INTERACTIVE_QUERY` | `<user jid=LID/>` + `<contact/><username/>` | username de um LID |
| `A0G(username, key)` | `INTERACTIVE_QUERY` | username (+ key) como `<contact>`; também status, picture, business, disappearing_mode, lid, username apenas se **33609** for false, text_status se **5839** | WA_USERNAME.md |

Guardas (found): verificação de rede (resultado `network_unavailable`), mapas de dedupe em andamento indexados por JID ou número (a segunda chamada retorna "skip too frequent query", sem janela de tempo), `sid` por chamada, espera de até 32000 ms, depois resultado de timeout. Com AB **14565** desligado, um JID LID com número de telefone conhecido é reescrito para esse número antes de a requisição ser montada (`AbstractC197018Zw.A0Y`; direção inferred a partir da etapa do prefixo `+` que vem a seguir).

### 4.2 Códigos de resultado (`C43621q7`, nomes inferred a partir do uso)

0 `A04` rede indisponível; 1 `A08` ignorado (nada a enviar ou frequente demais); 2 `A07` sucesso com mudanças (caminho de remoção de contato); 3 `A06` sucesso; 4 `A03` falha (resultado vazio, timeout, erro); 5 `A05` rate limited (erro de resultado 429); 6 `A02` exceção. `A01()` é true para 1, 2, 3. Uma `<list>` vazia com erro 429 do protocolo contact dá 5, qualquer outra lista vazia dá 4.

### 4.3 Quais funcionalidades chegam à agenda de contatos (found)

| Caminho | Entrada | Tipo | Protocolos (`C21820s6`) |
|---------|---------|------|-------------------------|
| Full sync em background (apenas primário) | `C18230lP.A0F(reason)` | `BACKGROUND_FULL` | tudo exceto orgs |
| Full sync forçado | helper `A01`, job periódico `RunnableC23953AUi` case 23 | `BACKGROUND_FULL`; companion: `BACKGROUND_COMPANION_MULTI_PROTOCOL_QUERY` | contact (`A0J`) ou side list (`A0K`); companion: tudo exceto contact / side list (`A0D`) |
| Force upload, delta upload, download | `A07(reason)`, `A0G(reason)`, `A0C()` | `CONTACT_FORCE_UPLOAD`, `CONTACT_UPLOAD`, `CONTACT_DONWLOAD` | contact + lid (`A0G`) |
| Contatos nativos alterados | `A0J(reason, jids)` | `NATIVE_CONTACT_DELTA` | tudo exceto orgs |
| Sync atrasado pós-registro | `A0L` (pref `registration_contact_sync_delayed`) | `CONTACTS_PROVIDER_WHATSAPP_ACCOUNT_SYNC` | contact + lid |
| Side contact na primeira exibição | `A0E(contact)` | primário: `INTERACTIVE_DELTA_SIDELIST`; companion: `INTERACTIVE_MULTI_PROTOCOL_QUERY` | tudo exceto orgs / tudo exceto contact, side list, orgs |

Conjuntos de protocolos (constantes de `C21820s6`, found): `A0S` username; `A0G` contact + lid; `A0P` status; `A0Q` text status; `A0O` picture; `A0F` business; `A0H` devices; `A0E` business + devices; `A0N` payment; `A0I` disappearing mode; `A0L` lid; `A0M` orgs; `A0D` tudo exceto contact, side list, orgs; `A0R` como `A0D` sem lid; `A0J` contact + conjunto `A0D`; `A0K` side list + conjunto `A0D`; `A0C` tudo exceto orgs. LID é implícito quando contact ou side list é sincronizado.

`C21830s7` (SyncRequest) persiste as opções como JSON: `sync_is_urgent`, `sync_only_if_changed`, `sync_only_if_registered`, `sync_clear_whatsapp_sync_data`, `sync_should_retry` e um booleano `sync_<protocol>` por protocolo (found); padrão do builder para retry int 5 (significado inferred).

### 4.4 Buscas acionadas por notificação (found)

O servidor envia um hash em vez de um número; o cliente o resolve e executa uma consulta.

| Handler de notificação | Payload | Sync | Protocolos |
|------------------------|---------|------|------------|
| `AnonymousClass145` (atualização de contato), `add` | até 2 filhos de hash do tipo `pn` (padrão) ou `lid`; apenas primário | `NOTIFICATION_CONTACT` | tudo exceto orgs |
| o mesmo, update | hash em base64 | `NOTIFICATION_SIDELIST` | status, picture, lid, username, text_status |
| `C1S0` notificação de status | atributo `hash` (base64) | `NOTIFICATION_SIDELIST` (motivo `NOTIFICATION_STATUS`) | apenas status |
| `C1S0` notificação de foto | atributo `hash` | `NOTIFICATION_SIDELIST` (motivo `NOTIFICATION_PICTURE`) | apenas picture |
| `AnonymousClass142` notificação de business (remoção sem jid com `hash`) | hash em base64 | `NOTIFICATION_SIDELIST` (motivo `NOTIFICATION_BUSINESS`) | conjunto business (constante não resolvida) |

O hash é comparado com usuários locais por `digest(user + "WA_ADD_NOTIF")` comparado byte a byte pelo prefixo (`AbstractC43461pq.A04`); o algoritmo de digest é escolhido pelo chamador (não rastreado). Um "forced sync" disparado pelo servidor (`RunnableC23951AUg`, motivo `SERVER_FORACE_SYNC`) executa `BACKGROUND_FULL` ou o tipo companion.

### 4.5 Sync de contatos via mutations MEX (found, não é USync)

Novo no build: o sync de contatos em Kotlin (`com.whatsapp.contact.sync.kmp`, `.handler`) usa mutations `w:mex` em vez do IQ usync. Config `whatsapp-android-mex`, doc_ids do asset persist-id.

| Operação | doc_id | Variáveis (found) | Resposta |
|----------|--------|-------------------|----------|
| `ContactsDeltaSyncMutation` | `28247314474869813` | `context` (`SEARCH`, `OSAB_IMPORT`, `EMAIL_IMPORT`, `QR_SCAN`), `primary_contacts_add[]`, `primary_contacts_remove[]` (`lid`, `modifier` = `BEST_EFFORT_DOWNGRADE_TO_WA_SIDE_CONTACT`, `normalized_phone`), `side_contacts_add[]` | `xwa2_contacts_delta_sync`: `results[]` {`client_cached_lid`, `failed`, `detail` (union: raw_pn / primary_normalized_phone / lid / phone_status; side_status; username_status; email_status; normalized_phone)}, `retry_after_seconds` |
| `PrimaryContactsFullSyncMutation` | `36963099086669113` | não lido | não lido |
| `SideContactsFullSyncMutation` | `26880700761604398` | `context`, `cursor`, `side_contacts[]` (`client_cached_lid`, `normalized_phone`) paginado | `results[]` como acima, `retry_after_seconds` |

O que decide entre este caminho e o caminho usync não foi encontrado (unknown). `retry_after_seconds` é o equivalente MEX do `backoff` do usync.

---

## 5. Sync da lista de dispositivos, key index, ADV

### 5.1 Requisição e resposta (found)

Requisição: filho de consulta `<devices version="2"/>`; por usuário `<devices device_hash="H" ts="T" expected_ts="E"/>`, enviado apenas quando existe um hash (`ts`, `expected_ts` apenas quando maiores que 0 e `expected_ts` maior que `ts`). Os valores vêm da linha local do dispositivo (`C15070fj.A07/A00/A04`).

Resposta por usuário: `<devices>` contém um `<error code text>` (o usuário recebe estado -1, log "parseUser/partial error") ou:

| Nó | Atributos | Convertido em |
|----|-----------|---------------|
| `<device-list><device .../>` | `id` (int), `key-index`, `is_hosted` | `DeviceJid(user, id)` -> key index; uma divergência entre o estado hosted do JID e `is_hosted` reporta `invalid-hosted-flag` |
| `<key-index-list ts expected_ts>` | `ts` (segundos), `expected_ts` (padrão 0), bytes de conteúdo | lista assinada de key-index, armazenada crua |

O `<devices>` no nível do resultado pode carregar `<error>` com backoff (seção 9). Rota MEX: `include_devices` mais `devices{hash, timestamp, expected_timestamp}`; rótulos de log do cliente para resultados descartados: `devices_dropped_status_error`, `devices_status_indeterminate`, `devices_hash_match_noop`, `devices_dropped_empty_without_hash`, `devices_dropped_no_jid`, `devices_dropped_stale_timestamp`, `devices_dropped_adv_proto_missing`, `devices_dropped_adv_verify_failed`, `devices_dropped_adv_data_update_failed`, `devices_outcome_unset`.

### 5.2 Verificações de atualização (found, `C51909N4g`, `C24230w2`)

| Verificação | Comportamento |
|-------------|---------------|
| lista de key-index vazia | "update keyIndex is empty", sem atualização |
| `ts` da resposta mais antigo que o armazenado | "timestamp is less than existing one", descartado |
| retry de expected-ts obsoleto | ts da resposta abaixo do armazenado, `expected_ts` igual ao ts armazenado e valor armazenado mais antigo que a pref `adv_last_device_job_ts`: loga um erro de fetch do usync e emite o evento WAM `wam_adv_expected_ts_unavailable` (`C49716Ltt`), retorna true (efeito no chamador não rastreado) |
| informação de novo dispositivo | `C51909N4g.A00` limpa o expected ts armazenado quando o novo ts é pelo menos igual ao armazenado; tipo de conta derivado do conjunto de dispositivos (`C9U.A01`) |

### 5.3 Verificação do key-index assinado ADV (found, `C24230w2.A07`, `A04`)

| Etapa | Detalhe |
|-------|---------|
| Parse | bytes do key-index -> `ADVSignedKeyIndexList` (`C25786BAu`): `details` (**1**), `account_signature` (**2**), `account_signature_key` (**3**, opcional) |
| Chave pública | identidade do dispositivo primário a partir do identity store local; se o proto traz `account_signature_key` e ela difere da chave local, essa chave é usada e marcada `adv`; sem nenhuma das chaves: aviso "no primary identity" |
| Assinatura | verifica `account_signature` sobre `{0x06, 0x02} || details` com a chave escolhida (`AbstractC30195DBc.A08`); falha loga "fail to verify account signature" e emite um evento WAM (`C55912St`, 1 = chave local, 2 = chave adv) |
| Details | `details` -> `ADVKeyIndexList` (`BCB`): `raw_id` (**1**), `timestamp` (**2**), `current_index` (**3**), `valid_indexes` (**4**), `account_type` (**5**) |
| Correspondência de timestamp | `details.timestamp` deve ser igual ao atributo `ts`, caso contrário "advTimestampMismatch" + evento WAM `C2TD`, resultado rejeitado |
| Idade | se `ts` é mais antigo que `min(35, AB 730)` dias (padrão 35) e `valid_indexes` tem mais de 1 entrada: "advListTimestampInvalid", rejeitado |
| Raw id | `raw_id` diferente do armazenado: "incoming key-index not matching local state, resetting"; conta própria em um companion loga `device_self_invalid_index_list`; outros usuários: `C15070fj.A0G(user, "adv_key_index_list_validation_failed")` quando nenhuma lista nova foi parseada (efeito não rastreado) |
| Filtragem | `filterDeviceWithKeyIndexList` (`C24230w2.A08`) mantém um dispositivo quando ele é o primário, ou seu `key-index` é maior que 0 e está listado em `valid_indexes`; caso contrário é descartado com um evento WAM (`C55932Sv`, 1 quando o índice é 0). Um índice armazenado maior produz apenas um aviso |

### 5.4 Jobs de sync de dispositivos (found)

`DeviceSyncManager.A03(jids, type)` enfileira `SyncDevicesJob` (ignora usuários já em andamento; usuários pendentes sobrevivem a reinicializações na pref `pending_users_to_sync_device`). `syncType` seleciona o tipo de sync:

| `syncType` | Tipo de sync | Contexto | Chamado de (found) |
|------------|--------------|----------|--------------------|
| 0 / padrão | `INTERACTIVE_MULTI_PROTOCOL_QUERY` | interactive | — |
| 1 | `MESSAGE_MULTI_PROTOCOL_QUERY` | message | `SyncDevicesAndSendInvisibleMessageJob` (caminho de envio em grupo `C22300su`, tamanho do grupo entre AB 934 e AB 1946, um job por message key) |
| 2 | `NOTIFICATION_MULTI_PROTOCOL_QUERY` | notification | account sync dos próprios dispositivos (`C41431mS`) |
| 3 | `BACKGROUND_MULTI_PROTOCOL_QUERY` | background | mensagem ou status recebido cuja verificação de remetente ADV falhou (`DecryptMessageRunnable` / `StatusProcessingRunnable`, log `invalid adv sender`), divergências de metadados ADV (`C24230w2`), replay de usuários pendentes |
| 4 | `VOIP_MULTI_PROTOCOL_QUERY` | voip | setup de criptografia de chamada para um dispositivo não primário (`C1A`, log `voip/encryption/schedule usync`) |
| 5, 6 | `LID_MIGRATION_NOTIFICATION_MULTI_PROTOCOL_QUERY`, `LID_MIGRATION_MESSAGE_MULTI_PROTOCOL_QUERY` | notification, message | não rastreado |

Requisições somente de devices usam `C21820s6.A0H`. `handleADVMetadata` (`C24230w2.A0A`) também dispara uma atualização do tipo 3 quando os metadados ADV de uma mensagem recebida reportam um tipo de conta hosted que discorda do estado local (dispositivos limpos antes), ou um timestamp mais novo que o armazenado.

---

## 6. Mapeamento de LID

| Mecanismo | Detalhe (found) |
|-----------|-----------------|
| protocolo `lid` | consulta `<lid/>`; por usuário `<lid jid=known LID/>` apenas quando um usuário PN já tem um LID armazenado; resposta `<lid val="LID"/>` armazenada no resultado do usuário |
| Gravação do mapeamento | `N27.A03(users)`: LID = `new_jid` (se for um JID do tipo LID), senão o resultado `lid`, senão o `jid` do usuário se for um LID; PN = `pn_jid`, senão o `jid` do usuário se for um PN; os pares vão para o store de mapeamento LID-PN em um único lote |
| Business `pn_jid` | um usuário LID sem PN recebe o PN de `<business pn_jid>`; o par é armazenado |
| Side list | os usuários da requisição carregam `jid` = LID e `pn_jid` = PN quando o endereçamento LID está ligado (`C11940aM.A05`, resolvido via `C11500Zc.A00`, id da flag não rastreado); fallbacks logam `Sidelist: No LID provided`, `waContact_null`, `usernameLid_null` |
| Reparo de LID ausente | `MissingLidHandler` (`C32M`): `requestSyncDevicesAndLidIfMissingLids` espera 32000 ms por um `MESSAGE_MULTI_PROTOCOL_QUERY` com o protocolo lid antes de um ponto de entrada externo prosseguir |
| Observer de mapeamento | `ContactJidMapObserver` (`C0ZA`): quando um par LID-PN aparece e existe um contato deprecated, adiciona o contato substituto e enfileira um `BACKGROUND_DELTA` com motivo `LID_REQUEST` |

Por que o LID ausente importa: um contato apenas com PN não pode ser endereçado no envio LID-first; a consulta preenche o par sem um full sync (inferred a partir dos pontos de chamada).

---

## 7. Enriquecimento de privacidade (tctoken, grupo em comum)

`ProfilePrivacyEnrichmentFetcher` (`C223659jg.A00`, rótulo de log `ContactSyncHelper.privacyEnrichment`) percorre a lista de requisições antes do envio. Para cada usuário ele busca (a) o privacy token armazenado com seu timestamp (`C14820fK.A0M`, descartado quando mais antigo que `C14820fK.A04.A02()`), (b) quando não existe token válido, um JID de grupo compartilhado com o usuário (`C197178aC.A04` / busca em massa, requer LID próprio). Resultado `C197148a9{ token C9oI, commonGroup, flag }`.

| Saída | usync clássico | MEX `UsyncQuery` |
|-------|----------------|------------------|
| token | filho `<tctoken>token bytes</tctoken>` de `<user>` | `privacy_token{tctoken, timestamp}` |
| grupo em comum | atributo `common_gid="..."` em `<user>` | `common_group` |

Aplica-se apenas a requisições que pedem picture ou status (AB **9667**, padrão true), text status (**20798**, padrão false), devices (**29769**), contact (**29770**), lid (**29771**) (flags com padrão false exceto 9667). Sem token ou grupo em comum o servidor ainda pode responder, mas pode omitir picture ou status (inferred; regra do servidor unknown). A emissão de token e o `cstoken` estão em WA_TCTOKEN_CSTOKEN.md.

Relacionado: `PRIVACY_TOKEN_REFRESH` (`C735439k`) emite `BACKGROUND_QUERY_PICTURES` com o conjunto somente de picture `A0O` em lotes de 10 usuários (found); que o propósito seja renovar a associação do token é inferred a partir do nome do motivo.

---

## 8. MEX `UsyncQuery` e roteamento por protocolo

### 8.1 Operação (found, `C229259vZ.A01`)

Operação `w:mex` `UsyncQuery`, doc_id `38635300486116501` (asset persist-id), classe de resposta `C2IQ`. Envelope como em WA_USERNAME.md 2.2.

| Variável | Origem |
|----------|--------|
| `query_input[]` | por usuário: JID, `client_known_username`, `about_status{dhash}`, `picture{id}`, `business{serial, tag}`, `devices{hash, timestamp, expected_timestamp}`, `privacy_token{tctoken, timestamp}`, `common_group` |
| `telemetry.context` | string de contexto em minúsculas |
| `include_username`, `include_reachability`, `include_linked_profiles`, `include_lid`, `include_about_status`, `include_picture`, `include_biz`, `include_ddm`, `include_devices`, `include_orgs` | booleanos definidos quando algum usuário pede o protocolo |
| `picture_field_input` | `type` `IMAGE` ou `PREVIEW`, `preview_px` para previews |
| `business_input` | `include_profile`, `include_vname`, `profile_version` |

Não transportados via MEX: contact e text_status. Apenas MEX: reachability, linked profiles, orgs, ddm (disappearing mode). Os detalhes da resposta além de username e lid (WA_USERNAME.md) não foram lidos (unknown).

### 8.2 Quando MEX é usado (found, `C18580m0`)

1. AB **37780** (int, padrão 0) diferente de zero: roteamento por protocolo. 16 bits altos = máscara de bits roteada via usync clássico (`SMAX`), 16 bits baixos = máscara roteada via MEX; `DROP` caso contrário. Bits (`M5H`): status 4, picture 8, business 16, devices 32, disappearing_mode 128, username 512, text_status 1024, orgs 2048. Os bits de nível de requisição 1 (contact), 2 (`C70582ym.A07`, provavelmente side list, inferred) e 256 viajam como a máscara "identity". Um protocolo que a rota escolhida não consegue transportar é definido como `DROP`: text_status em MEX, orgs em SMAX. A linha de log é `ContactSyncHelper/read_route type=.. contacts=.. identity=..,.. failed=..`.
2. Caso contrário, com AB **33432** (padrão false): consulta clássica para a requisição principal, depois um "mex profile follow-up" (`..._mex_profile`) para devices, com um marcador de métricas anotado com `requested_users`, `is_delta_sync`, resultado `success`, `partial_success`, `no_result`, `timeout`, `exception`, `interrupted`.
3. Caso contrário, `A0F` decide por requisição: MEX é recusado quando a requisição tem contact ou text_status ("cantUseMex"), exige AB **9732** para business e AB **8421** para username; o restante pode ir via MEX (`C229259vZ`), com espera de 128000 ms.

Estado padrão deste build: 37780 = 0, 33432 = false, 9732 = false, 8421 = false, então o USync roda sobre o stanza clássico a menos que um override de AB do servidor mude isso.

---

## 9. Rate limits, erros, backoff

### 9.1 Formatos de erro (found)

| Onde | Formato | Parseado por |
|------|---------|--------------|
| iq error | `<iq type="error"><error code backoff/></iq>` | `Brt`: `code`, `backoff` segundos * 1000 limitado a 3600000 ms (-1 quando ausente); chama `BIz(type, sid, code, backoffMs)`, completa o future com null |
| delivery failure | callback de transporte | `Bog`: o future falha com `C216419Uc`; estado de sync por JID resetado (`C502424l.A01`) |
| erro de protocolo | `<result><PROTO><error code text backoff/></PROTO></result>` | `C18670m9.A01`: `backoff` segundos * 1000, padrão 7200 s, limite 3600000 ms (1 h); loga `connection/unisynciq/parse/<proto>/error` |
| sucesso de protocolo | `<PROTO refresh="n"/>` | `refresh` segundos * 1000 |
| parcial no nível do usuário | `<devices><error code text/></devices>` | estado -1, usuário mantido |
| erro MEX | erro GraphQL, campo de path `<proto>_info`, string de backoff opcional | `C229259vZ.A00`: backoff padrão **7200**, limite 3600000, sem conversão * 1000 neste caminho (unidades pouco claras, unknown) |
| username key | códigos `42901` (requestor) e `42902` (requestee) no resultado de contact | `C23638AId.A0G`, ver WA_USERNAME.md |

Códigos vistos na lógica do cliente: `429` (rate limit: resultado de sync 5), `503` (backoff global), `42901`, `42902`.

### 9.2 Armazenamento de backoff (found, arquivo de prefs `contact_sync_prefs`, `C18800mM`)

| Chave | Gravada quando | Valor |
|-------|----------------|-------|
| `contact_sync_backoff` | qualquer erro de iq / protocolo contact com backoff acima de 0 (`X.0m7.BIz`, `AO4.BIz`) | agora + backoff ms |
| `delta_sync_backoff` | o mesmo, modo delta e código 429 | agora + backoff |
| `global_backoff_time` | o mesmo, código 503 | agora + backoff |
| `sidelist_sync_backoff` | callback `AO2.BIz` de `ContactQuerySync` em **qualquer** erro com backoff acima de 0 | agora + backoff; o código 503 também define `global_backoff_time` (o nome da chave não corresponde ao escopo do sync; found) |
| `contact_full_sync_wait`, `status_full_sync_wait`, `sidelist_full_sync_wait` | atributo `refresh` do resultado do protocolo | ms; não definido = 86400000 (24 h) |
| `status_`, `picture_`, `business_`, `devices_`, `disappearing_mode_`, `lid_`, `username_`, `text_status_`, `reachability_` `sync_backoff` | backoff de erro do resultado por protocolo em `BJ0` | agora + backoff |
| `last_contact_full_sync`, `last_status_full_sync`, `last_sidelist_full_sync` | conclusão do full sync | timestamp |

`C18800mM.A02()` reseta para -1 as chaves contact, sidelist, status, picture, business, devices, delta, disappearing_mode, lid, reachability e global; `username_sync_backoff` e `text_status_sync_backoff` não estão nessa lista (found).

Leitores encontrados por busca de string: `reachability_sync_backoff` (`C18580m0`), `text_status_sync_backoff` (`C3MA`), as três chaves `*_full_sync_wait` e `last_*_full_sync` (job periódico: um full sync é devido quando `wait - now + last` é no máximo 1800000 ms, 30 min). Nenhum leitor de `contact_sync_backoff`, `delta_sync_backoff`, `global_backoff_time` ou das outras chaves por protocolo foi encontrado (unknown se a verificação monta a chave dinamicamente).

### 9.3 Limites locais (found)

Dedupe em andamento: um `querySyncJid` por JID, uma consulta de telefone por número. Timeouts: 32000 ms busca unitária, 128000 ms lote, 180 s para a espera do callback `C18230lP.A00` (sem limite quando `C11980aQ.A09`). Limite de backoff 3600000 ms. Lotes de renovação de privacy-token de 10 usuários. Limites de consulta por conta e por número no lado do servidor são unknown.

---

## 10. O que aciona o USync

Motivo = valor de `EnumC21800s4` (rótulo do cliente, usado para agendamento e métricas). Tipo = tipo de sync.

| Funcionalidade do cliente | Motivo | Tipo | Protocolos |
|---------------------------|--------|------|------------|
| Registro concluído | `REGISTRATION_FULL` (`C25100xS`, `CJ8`) | `REGISTRATION_FULL` (código 0) | conjunto contact (variante companion não rastreada) |
| Onboarding de contatos | `NC_ONBOARDING` | `A0G` delta upload (`CONTACT_UPLOAD`) | contact + lid |
| Agenda do dispositivo alterada (apenas primário) | `DEVICE_ADDRESS_BOOK_CHANGE` | delta urgente on-change (`C18230lP.A02`) | não rastreado |
| Full sync periódico e forçado | `PERIODIC_FORCE_SYNC`, `FORCE_SYNC` | `BACKGROUND_FULL` | contact / side list |
| Seletor de contatos aberto | `CONTACT_PICKER_FULL_SYNC`, `CONTACT_PICKER_USYNC_RETRY` | `INTERACTIVE_FULL` | não rastreado |
| Adicionar contato, nova conversa por número, deep link, conversa sem contato | existem motivos `*_CONTACT_ADD`; não ligados ao caminho de consulta | `ADD_QUERY` (`C9AA`) / `INTERACTIVE_QUERY` (`C9AQ`, `C9AY`, `AWR`, `A1P`) | ver 4.1 |
| Abrir uma conversa com usuário ou business não salvo | `CONVERSATION_SIDE_CONTACT`, `SIDELIST_REQUEST` | consulta de telefone (`INTERACTIVE_QUERY`) quando AB **20988** (padrão true), senão `INTERACTIVE_DELTA_SIDELIST` | ver 4.1 / 4.3 |
| Enviar mensagem para lista de transmissão | `LID_REQUEST` | `MESSAGE_MULTI_PROTOCOL_QUERY` | lid |
| Envio de mensagem em grupo (tamanho dentro de AB 934..1946) | `DEVICE_REQUEST` | `MESSAGE_MULTI_PROTOCOL_QUERY` | devices |
| Mensagem recebida com verificação de remetente ADV falha, divergência de metadados ADV | `DEVICE_REQUEST` | `BACKGROUND_MULTI_PROTOCOL_QUERY` | devices |
| Setup de criptografia de chamada | `DEVICE_REQUEST` | `VOIP_MULTI_PROTOCOL_QUERY` | devices |
| Sync da própria conta | `DEVICE_REQUEST` | `NOTIFICATION_MULTI_PROTOCOL_QUERY` | devices |
| Push do servidor: mudança de contact, status, picture, business, username | `NOTIFICATION_*`, `USERNAME_UPDATE_NOTIFICATION` | `NOTIFICATION_CONTACT` / `NOTIFICATION_SIDELIST` | por notificação |
| Atualização de disappearing-mode e text-status | `DM_FORCE_REFRESH`, `TEXT_STATUS_FORCE_REFRESH` | `BACKGROUND_MULTI_PROTOCOL_QUERY` (text status também `BACKGROUND_FULL`) | disappearing_mode / text_status |
| Troca de conta | `ACCOUNT_SWITCH_REFRESH` | `BACKGROUND_FULL` | não rastreado |
| Renovação de privacy token | `PRIVACY_TOKEN_REFRESH` | `BACKGROUND_QUERY_PICTURES` | picture |
| Mudança no mapeamento LID-PN | `LID_REQUEST` | `BACKGROUND_DELTA` | tudo exceto orgs |
| Conversa de business (mensagem adicionada, chamada) | `BUSINESS_CONTACT_CHAT` (`C0LX`, `RunnableC23932ATn`) | `BACKGROUND_MULTI_PROTOCOL_QUERY` / `VOIP_MULTI_PROTOCOL_QUERY` | não rastreado |

---

## 11. Feature flags

IDs de AB-prop como lidos nos pontos de chamada; padrões vindos das tabelas de config deste build. IDs de flag em negrito.

| Flag | Tipo | Padrão | Controla |
|------|------|--------|----------|
| **5751** | bool | false | pedir devices em consultas de contact e de número de telefone |
| **5839** | bool | false | protocolo text_status (requisição e parse) |
| **9667** | bool | true | enriquecimento de privacidade para requisições de picture / status |
| **20798** | bool | false | enriquecimento de privacidade para text_status |
| **29769**, **29770**, **29771** | bool | false | enriquecimento de privacidade para requisições de devices, contact, lid |
| **9732** | bool | false | business via MEX |
| **8421** | bool | false | username via MEX |
| **37780** | int | 0 | máscaras de roteamento de protocolo (16 altos SMAX, 16 baixos MEX) |
| **33432** | bool | false | divide consulta clássica + follow-up de perfil via MEX |
| **12402** | bool | false | `lid` e `pin` no `contact` de username |
| **14565** | bool | false | `addressing_mode="lid"` em contact, texto de PN somente com dígitos |
| **26739** | bool | false | prefixo `+` em números de telefone |
| **471** | int | 1140 | `profile v` de business (mascarado com 0x3FFC) |
| **730** | int | 35 | idade máxima do key-index ADV em dias (limitado a 35) |
| **31261** | bool | false | adiciona o `@username` conhecido por usuário (`C223639je`) |
| **33609** | bool | true | quando true, a busca de key-entry omite `<username/>` |
| **20988** | bool | true | consulta de telefone em vez de sync de side list em uma conversa de business não salvo |

---

## 12. Baileys (`baron-baileys-v2`, comparado com seu `src/WAUSync` e `Socket/socket.js`)

| Tópico | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| envelope | `iq to=s.whatsapp.net type=get xmlns=usync` + `usync{context, mode, sid, last="true", index="0"}` | mesmos atributos; `to` implícito |
| modos | `query` (padrão), `delta` | também `full`, `download` |
| contextos | `interactive` (padrão), `background`, `message`; `voip` aparece em sua regra de backoff | mais `registration`, `notification`, `add`, `voip`, `metadata`, `snapshot`, `wamo` |
| protocolos | adiciona `bot`, `feature`, `sidelist` como filho de consulta | sem filho `bot` / `feature`; usuários de sidelist vão em `<side_list>` |
| contact | `<contact>phone</contact>`, username com `pin` / `lid`, `type` | telefone com `+`, `type="delete"`, username |
| status oculto | `code="401"` em `<status>` resulta em `''` | `type="fail"` com 401 / 403 / 404 |
| prova de privacidade | `<tctoken>` apenas sob o protocolo status, quando o usuário carrega um token | `<tctoken>` para picture / status / outros e `common_gid` |
| backoff | `error backoff` segundos * 1000, sem limite | limitado a 1 h |

| Sintoma (inferred) | Causa | Correção |
|--------------------|-------|----------|
| picture / status ausentes para não contatos | sem tctoken, sem `common_gid` | anexar o `<tctoken>` armazenado ou um JID de grupo compartilhado por usuário |
| lista de dispositivos rejeitada | verificações de `ts` / `raw_id` do key-index da seção 5.3 | verificar que `ts` é igual ao `details.timestamp` assinado |
| backoff ignorado | o Baileys usa o valor do servidor sem limite | limitar a 1 h, esperar por protocolo |

---

## 13. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|----------|
| `ContactQuerySync/querySyncJid: rate-limit-error` | erro 429 no resultado de contact, lista vazia | esperar o `backoff` retornado, reduzir a taxa de consultas |
| `connection/unisynciq/parse/<proto>/error` | nó de erro por protocolo | armazenar o `backoff` apenas para esse protocolo |
| `handleSyncContactError ... code=503` | sobrecarga do servidor | backoff global, tentar de novo mais tarde |
| `sidelist-jid-absent-from-response` | o servidor omitiu um usuário de side list requisitado | o cliente marca o usuário como sincronizado para evitar um loop |
| `contactsyncDevicesupdater/update/verifyADVSignedKeyIndexList fail` | falha na verificação de assinatura, proto ou timestamp | linha do dispositivo não atualizada, atualização enfileirada |

---

## 14. Distinções importantes

| Não confundir | Detalhe |
|---------------|---------|
| tipo de sync vs motivo | o tipo (`EnumC21760rz`) escolhe modo, contexto, escopo; o motivo (`EnumC21800s4`) é apenas um rótulo para agendamento e métricas |
| `list` vs `side_list` | usuários da agenda vs usuários fora da agenda (side contacts) |
| usync vs MEX `UsyncQuery` vs mutations MEX de contact | três transportes para dados relacionados; flags de roteamento em 8.2 e 4.5 |
| resultado `<devices>` vs key index assinado | a lista de dispositivos não é confiável até a lista assinada ser verificada (5.3) |
| `refresh` vs `backoff` | `refresh` = por quanto tempo um bom resultado pode ser reutilizado, `backoff` = por quanto tempo ficar longe após um erro |

---

## 15. Fluxo completo

```
[Feature]         [ContactSyncMethods]            [UniSync builder / MEX]                [Server]
  │ trigger (10)         │                                  │                               │
  ▼                      ▼                                  │                               │
 reason + type ──► SyncRequest (protocol set, users)        │                               │
                         │ enrich: tctoken / common_gid (7) │                               │
                         │ route per protocol (8)           ▼                               │
                         └──► classic: <iq xmlns=usync><usync sid index last mode context> ─►│
                         └──► MEX: w:mex UsyncQuery {query_input, include_*} ───────────────►│
                                                            │◄── <usync><result> per protocol│
                                                            │     <list> <side_list>         │
                                                            ▼                               │
                    parse: contact in/out, status, picture, business,                       │
                           devices + key-index-list, lid val, username                      │
                                  │                                                         │
        ┌─────────────────────────┼─────────────────────────┐                               │
        ▼                         ▼                         ▼                               │
 devices: verify ADV sig,   LID/PN pairs ──► mapping   result errors: 429 / 503 / backoff   │
 ts, raw_id, valid_indexes  store (N27.A03)            ──► prefs; refresh ──► full_sync_wait │
        │ ok                                                                                │
        ▼                                                                                   │
 device rows updated ──► message fan-out, call setup, side-list chats use the new data      │
```

---

## 16. Unknowns

| Tópico | Motivo |
|--------|--------|
| atributo `to` do iq | adicionado pelo sender; sender não rastreado |
| Diferença de `C10140Tq.A0A` (registration) vs `A06` | não rastreado |
| Regras do servidor para taxa de consultas, limites por número, quais protocolos um requisitante pode ler | o cliente vê apenas códigos de erro |
| Leitores de `contact_sync_backoff`, `global_backoff_time`, `delta_sync_backoff` | nenhum leitor por string encontrado |
| Unidades do backoff MEX | sem `* 1000` em `C229259vZ.A00` |
| Qual rota vence em produção | todas as flags de rota têm padrão desligado neste build; valores de AB do servidor unknown |
| Tráfego real | apenas análise estática |
