<!-- src-sha1: e4fe5d62fca781d0449295a5d549413929d95191 -->
# WhatsApp Listas de Transmissão — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** listas de transmissão clássicas e transmissões de status no Android: modelo de JID `@broadcast` (lista / status / localização), criação de lista, limites de membros e regras de destinatários, IQs `w:b` (obter listas, excluir lista, cota), app-state `business_broadcast_list`, migração para LID, armazenamento local, clone por destinatário na inserção, stanza de envio (fan-out de sender key, `phash`, `bucketing`, `<cap>`, configurações efêmeras por destinatário), agregação de ack e recibos, cota mensal de transmissão, banimentos por aviso de spam, GAP, publicação em `status@broadcast` (`SendE2eStatusJob`, partes, buckets manuais), modos de privacidade de status, amigos próximos e públicos personalizados, resposta / reação / menção / notificação de status, tabelas de status, feature flags, comparação com o Baileys

---

## 1. O que é (tecnicamente)

Existem três JIDs `broadcast` de servidor. Todos são JIDs "multi-participante" (`AbstractC20660pZ`, mesma base dos grupos) que compartilham um único pipeline de envio: o remetente cifra uma vez com uma sender key e entrega a chave a cada dispositivo destinatário par a par. Todas as afirmações são análise estática do APK decompilado; nada foi capturado na rede. Tier: **found** = lido no código, **inferred** = deduzido do código, **unknown** = não resolvido. Nada aqui é **tested**. Os nomes ofuscados foram re-resolvidos na 2.26.41.6 a partir de strings estáveis (`BroadcastListManager/…`, `BroadcastXmppMethods/…`, `StatusParticipantUserManager/…`, `SendE2eStatusJob/…`, nomes de tabelas e prefs).

| Entidade | Forma do JID | `Jid.getType()` | Classe | Papel |
|----------|--------------|-----------------|--------|-------|
| Lista de transmissão clássica | `<id>@broadcast` | 3 | `C99P` | lista do dispositivo primário, destinatários recebem cópias 1:1 |
| Transmissão de status | `status@broadcast` | 5 | `C199018dF` | publicações de status, público escolhido por publicação |
| Transmissão de localização | `location@broadcast` | 6 | `BOC` | existe no modelo de JID; uso não rastreado (localização em tempo real inferida pelo nome) |
| Pseudo-usuário do próprio status | `status_me` (local) | 11 | `C0Dh` | alias somente local, não é um JID de rede (papel inferido) |

Fora do escopo: newsletters (`SendNewsletterStatusJob` é um job separado), campanhas e insights do Business, broadcasts do SO Android.

| Componente | Nome na 2.26.41.6 | Papel |
|------------|-------------------|-------|
| Parser / helpers de JID | `C0DJ.A00` / `C0DZ.A0P`, `A0Q`, `A0h` | servidor `broadcast`: user `location` → `BOC`, `status` → `C199018dF`, senão `C99P`; helpers verdadeiros para qualquer broadcast (3, 5, 6) / lista (3) / status (5) |
| Alocador / gerenciador de listas | `C0YJ.A0E` / `A0K` (`BroadcastListManager`) | novo id de lista / adicionar e remover participantes |
| Filtro e migração LID | `C70552yj` (`BroadcastListLidMigrationHelper`), `C0UV` (tarefa de migração) | PN → LID |
| Gerenciador / store de participantes | `C22300su` (`A0j` adicionar, `A0k` remover), `C14850fN` (`ParticipantUserStore`) | compartilhado com grupos |
| IQs de lista | `C18240lQ` (`BroadcastXmppMethods`), `AKU` (handler de resultado), `BroadcastListQuotaProtocol` + `C9EN` | obter listas, excluir lista, cota |
| Cliente de cota | `C720733k` (repositório), `C2EX` (view model), `C74823Ej` (listener de mensagens) | limite mensal |
| Mutação de app-state | `C224469lG` (dispatch), `C26057BNq` (`BusinessBroadcastListMutation`) | `business_broadcast_list` |
| Clone na inserção | `C231399zG` (`BroadcastCloneOnInsertProcessor`), `AJO` | cópias locais por destinatário |
| Ack / recibos | `C22500tF`, `C22790ti` (`MainMessageStore`), `C269411e` (`MessageStatusStore`) | ack do servidor, divisão de recibos |
| Cifrador / jobs | `F6P` (`E2eMessageEncryptor`), `SendE2EMessageJob`, `SendE2eStatusJob` | sender key, SKDM, montagem do stanza |
| Verificador de entrada | `C34757F6a` (`CompanionSupportVerifier`) | descarta cópias de lista em companions |
| Público do status | `C11550Zh` (`StatusInfoStore`), `C182877r0` (distribution info), `C23140uH` (`StatusParticipantUserManager`), `C1889082i` (`StatusCustomListStore`), `C23340ub` (config de bucketing) | modos de privacidade, listas, buckets |
| Sync de privacidade do status | `C48386LBh` (`StatusPrivacySyncMutation`), `C49626LsR` (Wire `StatusPrivacyAction`), `M7H` (enum de modos) | ação de app-state 44 |

---

## 2. Modelo de JID

### 2.1 Parsing (found)

| Regra | Valor |
|-------|-------|
| Servidor | `broadcast` |
| User `status` / `location` | singletons `C199018dF` / `BOC` |
| Qualquer outro user | `C99P`: comprimento 1..20, primeiro caractere `1`..`9`, demais caracteres `0`..`9`, senão `C09B` é lançada |

A regra de ausência de zero à esquerda é lida do construtor de `C99P` (o smali compara com `0x31`/`0x39`, resto `0x30`..`0x39`). Uma lista não é `g.us`, mas reutiliza a maquinaria de participantes de grupo (3.5).

### 2.2 Alocação (found, `C0YJ.A0E`)

O id é `System.currentTimeMillis() / 1000` seguido de `@broadcast`, incrementado em um segundo enquanto existir localmente uma lista com esse id. A unicidade é verificada apenas contra a lista de chats local; nenhuma chamada ao servidor precede a alocação (não existe IQ de criação, 3.3). Se o servidor aceita um id arbitrário não é determinável estaticamente.

---

## 3. Ciclo de vida da lista

### 3.1 Criação (found, parcialmente inferred)

```
[Picker]  "New broadcast" (menu item hidden when BRD() = companion mode), max 256 selected
     ▼
createBroadcastList callback (C222519hZ):
     │   C0YJ.A0E()                                allocate <seconds>@broadcast
     │   A0K.A04(jid, users): C70552yj.A00 → LID filter ; C22300su.A0h → local participants ; contact entry (name "")
     ▼
compose flow opens; system message "You created broadcast list "X" with N recipients"
```

`A0K.A04` não emite IQ nem mutação de app-state (found). O primeiro evento visível ao servidor é o primeiro envio ao JID da lista (4.2); que o servidor derive o estado da lista a partir dele é inferred. A mesma alocação é reutilizada para convites a seguidores de newsletter (`userActionSendNewsletterFollowerInviteMessages`, found).

### 3.2 Limites de membros e regras de destinatários

| Regra | Valor | Tier |
|-------|-------|------|
| Máx. de destinatários | 256: `ContactPickerFragmentKt.A39` rejeita `selected.size() > 256` (`Broadcast to a maximum of %d people at a time`); limite do picker `min(256, groupLimit - 1)` | found |
| Origem dos destinatários | seletor de contatos; texto de permissão `To create a broadcast … allow WhatsApp access to your contacts`; contatos bloqueados: `To add to broadcast list, unblock %s` | found |
| O destinatário deve ter o remetente salvo | somente texto de UI (`Only contacts who have you in their address book will receive your broadcast messages.`); a aplicação da regra é no servidor | found (texto), unknown (aplicação) |
| Endereçamento LID | `A0K.A01` sempre retorna `lid`; participantes PN sem mapeamento LID são descartados (`lid-broadcast-filtered-participants`) | found |
| Mapeamento ausente no envio | `missing_pn_lid_mapping_for_broadcast`: clone ignorado, o cifrador lança `E39(device, 4)` | found |
| Conjunto de participantes vazio | `saveGroupParticipants/broadcast_would_be_cleared`; com a flag **30111** (padrão true) os participantes armazenados são mantidos | found |

### 3.3 IQs do servidor (found)

Apenas três IQs tocam listas. Não existe IQ de criação nem de edição.

```xml
<!-- restore: BroadcastXmppMethods/sendGetBroadcastLists -->
<iq to="s.whatsapp.net" xmlns="w:b" type="get" id="…"><lists/></iq>
<iq type="result"><lists>
  <list id="1760000000@broadcast" name="Family">
    <recipient jid="<lid>@lid" pn_jid="<pn>@s.whatsapp.net" username="…"/>   <!-- pn_jid, username read for LID recipients -->
  </list>
</lists></iq>

<!-- delete: sendDeleteBroadcastList -->
<iq to="s.whatsapp.net" xmlns="w:b" type="set" id="…"><delete><list id="1760000000@broadcast"/></delete></iq>

<!-- quota (5.1) -->
<iq to="s.whatsapp.net" xmlns="w:b" smax_id="143" type="get" id="…"/>
```

Os três usam timeout de 32 s. `AKU` (resultado de get) cria, para cada `<list>` sem chat ou entrada de contato local, o chat (`A0K.A00`, mensagem de sistema tipo 9) e uma entrada de contato, e armazena os mapas de `pn_jid` e `username`. A exclusão é enviada por `C18240lQ.A01` e seguida de um REMOVE de app-state (3.4).

Gatilho de restauração (found): `RegistrationInitializer/shouldrefreshlists` define a pref `refresh_broadcast_lists=true` e envia get-lists (junto com get-privacy-settings) após o registro; `MessageHandlerCallback/ready` repete enquanto a pref for true; `AKU` a limpa. O servidor, portanto, persiste as listas por conta (found por implicação). Como ele toma conhecimento de uma lista não é visível no lado do cliente (unknown, ver 3.1).

### 3.4 Mutação de app-state (found)

| Item | Valor |
|------|-------|
| Ação | `BusinessBroadcastListAction`, nome de rede `business_broadcast_list` (`EnumC24865AnN.A0H`, ordinal 62), campo **69** de `SyncActionValue`, coleção `regular`, versão de API 7 |
| Índice | `["business_broadcast_list", "<list jid>"]` |
| Operação | SET ao adicionar, remover, renomear; REMOVE com `deleted=true`, participantes vazios, nome `""` na exclusão da lista (`A0T`, `syncBusinessBroadcastListRemoval`) |
| Gate | `C12440bB.A0b()` (syncd não bloqueado ou companion-dirty); os hooks de Business (`storeForBroadcast`, `onAudienceChanged`, `getCustomAudienceFbidForBroadcast`) estão ausentes neste APK |
| Chamadores | `A0K.A03` / `A05` (adicionar / remover), renomear em `BroadcastListChatInfoActivity`, `C24085AaS` (conjunto de participantes) |
| Lado de aplicação | nenhum handler referencia `EnumC24865AnN.A0H`; existem apenas o writer (`C26057BNq`) e o accessor do campo em `BD4`, então o comportamento de aplicação no consumidor é desconhecido |

| Campo | Número | Tipo | Valor / uso |
|-------|--------|------|-------------|
| `deleted` | **1** | bool | lista removida |
| `participants` | **2** | repeated `BroadcastListParticipant` | público (`lid_jid` **1** obrigatório, `pn_jid` **2**) |
| `list_name` | **3** | string | assunto |
| `label_ids` | **4** | repeated string | público por etiquetas (alternativa a participants, nunca ambos) |
| `audience_expression` | **5** | string | público dinâmico (Business) |
| `custom_audience_fbid` | **6** | string | somente Business |

Mesma coleção: `BusinessBroadcastCampaignAction` (81), `BusinessBroadcastInsightsAction` (82), `MarketingMessageBroadcastAction` (39); somente no enum `BusinessBroadcastAssociationAction` (59) e `BusinessBroadcastAction` (94). Fundamentos: [WA_APPSTATE_SYNC.md](WA_APPSTATE_SYNC.md).

### 3.5 Migração para LID, armazenamento, companions

`BroadcastListLidMigrationTask` (`C0UV`) converte cada lista de participantes PN para LID: um usync para os LIDs ausentes (falha registrada como `usync_failed`, a tarefa prossegue), depois `C70552yj.A03` remove os participantes PN e adiciona o conjunto LID em uma transação.

| Store | Conteúdo | Tier |
|-------|----------|------|
| `chat` / `chat_view`, `jid.type = 3`, `subject`, `created_timestamp`, `hidden` | o chat da lista (`C222989iV`) | found |
| `group_participant_user` (`group_jid_row_id`, `user_jid_row_id`, `rank`, `pending`, `label`, `add_timestamp`), `group_participant_device` | destinatários, compartilhado com grupos | found |
| `wa_group_admin_settings` (`jid`, `addressing_mode`, `group_state`) | modo de endereçamento por lista (a telemetria conta linhas `@broadcast`) | found |
| colunas de `message` `broadcast`, `recipient_count`, `participant_hash`, `key_id`, `chat_row_id`, `from_me` | mensagem da lista e dados de ack | found |
| `message_broadcast_ephemeral` (`message_row_id`, `shared_secret`) | segredo por mensagem para mensagens temporárias da lista | found |

Companions (found): os itens de menu `New broadcast` / `Broadcast lists` são adicionados somente quando `BRD()` é false; `C34757F6a` lança `E3A(415, "received peer broadcast message on companion-mode, dropping", 18)` para uma cópia de lista da própria conta que carrega `<participants>`; a ação 69 não tem handler de aplicação.

---

## 4. Envio para uma lista

### 4.1 Fan-out local (found, `C231399zG`)

```java
// A02(msg): msg.fromMe, not one of two excluded message classes, status 0 or 2 (or 4 with flag 26867)
msg.A0Z = true;                                   // message.broadcast = 1
for (recipient : msg.A0A())                       // recipient list stored on the FMessage
    normalized = lidMapper.A0C(recipient);        // null → missing_pn_lid_mapping_for_broadcast, skip
    store.add(cloneFactory.A00(msg, new C1ZA(normalized, msg.key.id, true)));   // own row in the recipient's 1:1 chat
```

| Propriedade | Valor |
|-------------|-------|
| Id da mensagem | idêntico para a mensagem da lista e todos os clones (`key_id` copiado, só o chat difere) |
| Contagens | `recipient_count` (`FMessage.A06`) na linha da lista; contagem de referências do arquivo de mídia aumentada pelo número de clones |
| Duplicatas | `SQLiteConstraintException` em uma chave de clone existente é registrada e ignorada |
| Mensagens temporárias | o clone assume a configuração por destinatário do mapa efêmero (chaveado pelo dispositivo primário do destinatário); linhas de expiração em `message_ephemeral` |

### 4.2 Formato de rede (found, parcialmente inferred)

Um stanza endereçado ao JID da lista (exemplo, valores de atributos ilustrativos). A cifragem reutiliza o caminho de grupo (`F6P` é tipado em `AbstractC20660pZ`): um ciphertext de sender key mais mensagens de distribuição de sender key por dispositivo. Os fundamentos de sender key e sessão não são repetidos aqui.

```xml
<message to="1760000000@broadcast" type="text" id="3EB0…" t="…" phash="2:AbCdEf==" addressing_mode="lid">
  <participants>
    <to jid="<recipient device jid>"><enc v="2" type="pkmsg|msg" …/></to>   <!-- SKDM wrapped pairwise -->
  </participants>
  <enc v="2" type="skmsg" …/>                                                <!-- message under the sender key -->
  <cap client_capping_ready="true|false"/>                                   <!-- flag 16656 only -->
</message>
```

| Atributo | Origem | Notas |
|----------|--------|-------|
| `to`, `type`, `id`, `t` | JID do chat (`C33150EcP.A07`), `AbstractC30999De0.A02`, `C1ZA.A01`, `originalTimestamp` | `to` é o JID da lista (inferred a partir do builder compartilhado); `t` somente quando diferente de zero |
| `phash` | `groupParticipantHash` | 4.3 |
| `bucketing` | `eva.A05` | `primcomp` quando a flag **28183** e a contagem de participantes ≥ **28185** (512); listas (≤ 256) ficam sem definição na prática (inferred) |
| `addressing_mode` | `lid` | omitido para JIDs de tipo 28 |
| `participant`, `recipient`, `recipient_pn`, `peer_recipient_pn`, `peer_recipient_username` | campos do job | envios peer / retry / DSM |
| `edit`, `expiration`, `device_fanout="false"`, `privacy_sensitive="1"` | campos do job | opcionais |

Os filhos vêm de contribuidores (`InterfaceC35538FaZ.ASY`, `processStanzaNodeParamsUsingNewFramework`). `F69` adiciona `<cap client_capping_ready="…"/>` para chats de lista quando a flag **16656** está ligada; o valor é a flag **13537**.

| Etapa | Detalhe | Tier |
|-------|---------|------|
| Dispositivos destinatários | conjunto do gerenciador de participantes menos os tipos de dispositivo 26 / 27 (`F6P.A07`, dispositivos hospedados inferidos); para chats de lista, `AxolotlMultiDeviceSessionRequirement` adiciona os próprios dispositivos companion (`BPE`: próprio user, não primário) ao conjunto-alvo de SKDM | found / inferred |
| Nome da sender key | (endereço do próprio dispositivo, string `groupId` `A0J`); `A0J` é escrito em `SenderKeyDistributionMessage.groupId`; status `-1002` de `encryptForGroup` = sender key inválida, rotacionada | found |
| Blobs efêmeros por destinatário | `F6P.A0A` (`buildBroadcastListEphemeralSettings`): para cada dispositivo destinatário ausente do mapa pairwise (companions próprios ignorados) monta `EphemeralSetting(expiration or afterReadDuration, timestamp)` e o cifra nativamente com o `shared_secret` da mensagem (`JniBridge.jvidispatchOOOOOOO`); configuração ausente lança `E39(device, 4)`. Finalidade (timers por destinatário dentro de um único stanza) inferida | found / inferred |
| Dispositivos próprios | mensagem envolta em `DeviceSentMessage` com `destinationJid = list` e `phash` dos dispositivos destinatários (`C33284Eea.A01`) | found |
| Tamanho | `BoundedStanzaSizeException` → `stanza-too-large` / `large payload` | found |

### 4.3 `phash` (found, `AbstractC44221r5`)

`<version>:` + base64 (`NO_WRAP`, padding mantido) dos primeiros 6 bytes do SHA-256 sobre os dispositivos destinatários ordenados. A versão `2:` faz hash de strings `user.0:device@server` (flag **16731** false, padrão); a versão `3:` faz hash das strings brutas do dispositivo (flag **16731** true). Usado em stanzas de grupo, lista e status.

### 4.4 Ack e recibos (found)

| Evento | Tratamento |
|--------|------------|
| Ack do servidor | `C22500tF` → `C22790ti.A04`: para chats de lista (não status) atualiza `message` onde `chat_row_id IN (list chat, every clone chat) AND from_me = 1 AND key_id = ?` com `status`, `receipt_server_timestamp`, `recipient_count`; recorre a uma varredura por `timestamp/from_me/key_id` (`UPDATE_RCV_BROADCAST_SERVER_SQL`, log `message-table-scan`) quando a lista de destinatários é menor que `recipient_count` |
| Recibo do destinatário | `MessageStatusStore.splitStatusUpdateReceipts`: um recibo para a chave da lista é mapeado ao clone `(normalized recipient, same id, fromMe)` e aplicado ao clone (`broadcast-individual`) e à mensagem múltipla; rebaixamentos de status descartados (`broadcast-statusdowngrade`); clone desconhecido registra `nosuchmessage for broadcast` |

A regra de status resumido da linha da lista e o que o telefone do destinatário exibe não estão resolvidos (unknown).

---

## 5. Limites e controles de abuso

### 5.1 Cota mensal de transmissão (found, caminho de consumidor)

```
iq get xmlns=w:b smax_id=143
  → <limits is_heavy_sender="true|false" messages_left="N" total_limit="M"/>
    <timeframe start_ts_s="…" reset_ts_s="…" end_ts_s="…"/>
```

Verificações de faixa do cliente: `messages_left` 0..300, `total_limit` 1..300, timestamps 2020-01-01..2100-01-01. Códigos de IQ de erro mapeiam para resultados do cliente `400` → 3, `401` → 4, `403` → 5, `500` → 1, outros → 0, sem conexão ou falha de entrega → 2 (`consumer_broadcast_capping_iq_error_response`).

| Mecanismo | Detalhe |
|-----------|---------|
| Cache | prefs `broadcast_quota_messages_left`, `_message_limit`, `_last_timestamp_fetched_ms`, `_heavy_sender`, `_start_timestamp`, `_end_timestamp`, `_reset_timestamp` |
| Atualização | quando o tempo desde a última busca excede a flag **13818** minutos (padrão 1440) ou agora ≥ `reset_ts_s` (combinação truncada no decompile, OR inferred) |
| Decremento / incremento | `C74823Ej`: por mensagem de lista adicionada marcada como `broadcast` e fora de um conjunto de tipos de mensagem isentos (`C2EX.A00`), por mensagem e não por destinatário; incrementado de volta na exclusão de mensagens de lista não enviadas, limitado a `total_limit` |
| Bloqueio pré-envio | predicado em `C20M`: chat de lista e flags **16585** e **13537** e `messages_left == 0` → envio recusado, bottom sheet `You've reached the broadcast limit for this month` |
| UI / telemetria | `Send up to %d broadcasts per month`, sheet de onboarding para heavy senders (`CappingBroadcastManager`); `wam_broadcast_list` (`blLimit`, `currentBlSends`, `numBlLists`, `broadcastListSize`) |

O valor do limite é fornecido pelo servidor; apenas a verificação de faixa está no cliente. Os hooks do lado Business (`isSmbPremiumBroadcastCappingEnabled`) são stubs neste APK.

### 5.2 Banimentos por aviso de spam (found)

`SpamWarningActivity` recebe um código do servidor (`spam_warning_reason_key`), `expiry_in_seconds`, texto opcional do servidor e URL de FAQ. Códigos: **101** mensagens a pessoas que não têm o remetente na agenda, **102** bloqueios em excesso, **103** grupos com pessoas que não têm o remetente salvo, **104** mesma mensagem para pessoas demais, **106** mensagens demais para uma lista de transmissão; os demais exibem o banimento genérico por termos de serviço. Caminho de entrega e o restante da superfície de banimento: [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md). Os limiares são do lado do servidor (unknown).

### 5.3 Config 20278 e GAP

- A config **20278** existe apenas como string padrão `{"max_messages": 10000, "farthest_time_days": 30}` em duas tabelas de padrões. Não há outra referência a `max_messages` / `farthest_time_days` no código de consumidor, portanto nenhum leitor foi encontrado. Não é o limite de lista do consumidor (5.1); seu uso é desconhecido (padrão do lado Business).
- GAP (`com.whatsapp.gapenforcement`, flag **14837**, padrão false) é do lado de recebimento: `GapEnforcementTrigger.onMarketingMessageReceived` e `RulesManager` avaliam regras de inbox para threads de mensagens de marketing (`parseMaxMmThreadsInTopInboxSize`, `parseNoConsecutiveInTopInboxSize`, `parseMinNUpdatedP`) e registram resultados de acurácia; não roda em companions e não limita envios a partir de listas. A expansão do acrônimo não está no APK (unknown).

---

## 6. status@broadcast

### 6.1 Pipeline de envio (found)

`SendE2eStatusJob` tem um tipo (`EnumC32060Dzj`): `STATUS` 0 (a publicação, tabela `status`), `STATUS_ADD_ON` 1 (reações e outros add-ons, `status_add_on`), `STATUS_NOTIFY` 2 (notificações de resposta / recompartilhamento / menção, `status_notify`). O stanza usa o builder de atributos de 4.2 mais contribuidores de `<meta>` (exemplo, valores de atributos ilustrativos):

```xml
<message to="status@broadcast" type="media" id="3EB0…" phash="2:…" bucketing="manual" addressing_mode="lid">
  <participants><to jid="<device>"><enc v="2" type="pkmsg|msg"/></to>…</participants>
  <enc v="2" type="skmsg" bucket="f1"/>                      <!-- one per bucket when bucketed -->
  <meta status_setting="contacts" session_scope="status"/>
</message>
```

| Atributo | Valores aceitos (conjuntos de valores do stanza, `C9E2`) |
|----------|----------------------------------------------------------|
| `status_setting` | `allowlist`, `closefriends`, `contacts`, `customlist`, `denylist` |
| `content_type` | `add_on`, `status_notify` |
| `message_association_type` | `av1_video_dual_upload`, `hd_image_dual_upload`, `hd_video_dual_upload`, `hevc_video_dual_upload` |
| `interaction_type` | `question`, `question_reshare` (com `parent_server_id`, `response_server_id`) |
| `bucketing` | `manual`, `primcomp`, `threebuckets` (`threebuckets` apenas no conjunto de valores) |

| Item | Detalhe |
|------|---------|
| Timeout de ack | 300000 ms (`no ack within 300000ms`) |
| Partes | públicos grandes são divididos: `status_send_part` (`status_row_id`, `part_code`, `is_first_part`, `device_count`, `state`, `sent_timestamp`, `ack_timestamp`, `error_code`, `stanza_devices_hash`); rastreamento de dispositivos em `status_receipt_device` (`uuid`, `receipt_device_jid`, `receipt_device_timestamp`, `primary_device_version`, `part_code`) |
| Status de grupo | `buildGroupStatus called with non-PermanentGroupJid`; `is_group_status`; campos de Message 92 / 96 / 103 |
| Falhas de montagem | `StatusStanzaBuildFailureReason`: `MISSING_RETRY_CIPHERTEXT`, `TARGETS_UNRESOLVABLE`, `PART_ATTEMPT_PERSISTENCE_FAILED`, `CANONICAL_ACK_PENDING`, `EMPTY_FANOUT`, `NON_CURRENT_BATCH`, `MISSING_SENDER_KEY_CIPHERTEXT`, `UNKNOWN` |
| Falhas do job | `encryption_limit`, `out_of_memory`, `payload_too_large`, `stanza_error`, `stanza_too_large` (tratada quando a flag **29113** está ligada), `unrecoverable_error` |

### 6.2 Público: modos de privacidade (found)

O público é resolvido no remetente e expandido para dispositivos destinatários explícitos; o atributo `status_setting` apenas rotula o modo. Estado local: `C11550Zh` (prefs `status_distribution`, `status_distribution_modes`, `status_white_list`, `status_black_list`).

| Modo local | Nome | `status_setting` | `M7H` de rede (app-state) |
|------------|------|------------------|---------------------------|
| 0 | My contacts | `contacts` | `CONTACTS` 2 |
| 1 | Only share with | `allowlist` | `ALLOW_LIST` 0 |
| 2 | My contacts except | `denylist` | `DENY_LIST` 1 |
| 3 | fallback não definido de `C182877r0.A01()`; recusado pela mutação de sync (`StatusPrivacySyncMutation invalid status setting`) | | |
| 4 | público personalizado / amigos próximos | `customlist` / `closefriends` (inferred) | `CUSTOM_LIST` 4 (`CLOSE_FRIENDS` 3 existe no enum, não é produzido) |

Mapeamento local para rede (found, `C48386LBh.A04`): 1 → 0, 2 → 1, 4 → 4, senão 2. Os nomes de modo de 0..2 também são registrados pelo job de envio como `contacts` / `allowlist` / `denylist`.

As listas de privacidade do servidor usam o IQ `privacy`, categoria `status` (nome da categoria de `AboutStatusPrivacyActivity`):

```xml
<iq to="s.whatsapp.net" xmlns="privacy" type="get" id="…">
  <privacy addressing_mode="lid"><list name="status" value="contact_allowlist|contact_blacklist" dhash="…"/></privacy>
</iq>
<iq xmlns="privacy" type="set"><privacy><category name="status" value="contacts|contact_blacklist|contact_allowlist"/></privacy></iq>
```

(`AbstractC230749y7.A02`, `C228009tS`, `C18260lS.A0P`; get é MEX / SMAX / shadow conforme a flag **23463**, set via MEX quando **23639**, senão SMAX.)

### 6.3 Públicos personalizados e amigos próximos (found)

Strings de UI: `New: Close friends`, `People you include see a purple ring on your status`, `Create audience`, `Choose name & emoji`.

| Item | Valor |
|------|-------|
| Tabela `status_privacy_custom_list` | `row_id` (PK), `list_id` (unique), `name`, `emoji`, `is_selected` (padrão 0), `member_jids`, `source_group_jids`, `allow_list_selected`; mantida tanto no message store quanto no status store (`*_MSGSTORE_DB`, `*_STATUS_DB`) |
| App-state | `status_privacy` (ordinal 38, `regular_high`, campo **44**); `StatusPrivacyAction`: `mode` **1**, `user_jid` **2**, `shareToFB` **3**, `shareToIG` **4**, `custom_lists` **5**, `modes` **6**; `StatusCustomList`: `list_id` **1**, `name` **2**, `emoji` **3**, `is_selected` **4**, `user_jid` **5** |
| Registro por publicação | `status_message_info`: `status_distribution_mode`, `selected_audience_list`, `audience_type`, `status_audience_custom_list_name`, `_emoji` |
| Validação | `StatusParticipantUserManager/validateAudience` (inclui uma verificação `HAS_STATUS_AUDIENCE` sobre `wa_contacts`), `StatusEmptyAudienceGuard` nos composers |

Relacionado: `userStatusMute` (ordinal 23, campo 29, `muted`). Múltiplos modos simultâneos exigem a flag **28731**, o custom-list store **27031** (ambas padrão false; os helpers de status-config `A0F` / `A0I` também controlam isso, não resolvido).

### 6.4 Buckets manuais de sender key (found)

| Item | Detalhe |
|------|---------|
| Tabela `manual_user_group_bucket` | `row_id`, `user_jid_row_id`, `multi_participant_jid_row_id`, `status_audience`, `bucket`; índice único em user + group |
| Nomes de público / prefixos de bucket | `contacts` → `c`, `close_friends` → `f`, `allow_list` → `a`, `close_friends:<id>` → prefixo derivado; outros nomes lançam `Unknown manual SKB audience name` |
| Store / planejamento | `ManualBucketStore/assignUsersToBuckets`, `deleteRowsForBuckets`, `getHoldersByBucketForGroup`; `ManualBucketingUtils/planSend`, `trimToEncBudget`; `SenderKeyBucketingRollback/cleanupBucketedState` |
| Flags | **28184** + limite de rollout **34545** (0 = todos) habilitam o bucketing manual para status (`C23340ub.A01`) |

### 6.5 Resposta, reação, menção, notificação (found)

| Interação | Mecanismo |
|-----------|-----------|
| Resposta | mensagem 1:1 normal citando o status (`status_reply`: `status_row_id`, `ref_id`, `reply_timestamp`); `Message.statusQuotedMessage` (campo **109**) para respostas a perguntas |
| Reação / add-on | tipo de job `STATUS_ADD_ON`; `status_add_on` (`status_row_id`, `type`, `uuid`, `sender_user_jid`, `state`, `sender_timestamp`, `is_revoked`, `content_proto`, `secret`); gates por publicação `cannot_receive_reactions`, `can_receive_multi_reactions` |
| Menção | `status_message_info.is_mentioned`, `status_mentions`, `status_mention_source`; `Message.statusMentionMessage` (campo **87**) é um wrapper de campo único (`message` **1**) desempacotado como `viewOnceMessage` (`C35228FOg`); demais semânticas inferidas |
| Notificação | `Message.statusNotificationMessage` (campo **98**): `responseMessageKey` **1**, `originalMessageKey` **2**, `type` **3** (1 add yours, 2 reshare, 3 question-answer reshare, 4 group status reply); armazenado em `status_notify` |
| Campos relacionados | `groupStatusMentionMessage` **92**, `groupStatusMessage` **96**, `groupStatusMessageV2` **103**, `statusQuestionAnswerMessage` **105**, `statusStickerInteractionMessage` **110** |

### 6.6 Armazenamento de status (found)

| Tabela | Colunas-chave |
|--------|---------------|
| `status` (status store) | `uuid`, `sender_user_jid`, `status_info_row_id`, `type`, `timestamp`, `server_receipt_timestamp`, `state`, `secret`, `content_proto`, `origin`, `flags`, `audience_type`, `stanza_xml`, `batch_state` |
| `status` (message store, resumo legado), `status_info` | `jid_row_id` / `chat_jid`, `unseen_count` / `unread_count`, `total_count`, `unread_count_close_friends` |
| `status_message_info` | `message_row_id`, `status_distribution_mode` (3 quando não definido), gates de menção / reação / recompartilhamento, `is_group_status`, `ranking_version`, colunas de público (6.3) |
| `status_send_part`, `status_receipt_device`, `manual_user_group_bucket` | estado de envio (6.1, 6.4) |

As duas tabelas chamadas `status` têm colunas disjuntas e vivem em bancos de dados diferentes (inferred a partir dos rótulos `MSGSTORE_DB` / `STATUS_DB`). Outras tabelas (`status_media_link`, `status_seen_receipt`, `status_ranking*`, `status_interactions*`) são listadas apenas pelo nome.

---

## 7. Feature flags

Ids como lidos nos pontos de chamada; padrões das tabelas de padrões compiladas.

| ID | Padrão | Controla |
|----|--------|----------|
| **13537** | false | capping de transmissão do consumidor: home de listas, busca / decremento de cota, valor de `client_capping_ready` |
| **16585** | true | bloquear envios de lista quando `messages_left == 0` |
| **16656** | false | adiciona `<cap client_capping_ready/>` aos stanzas de lista |
| **13818** | 1440 | intervalo de atualização da cota (minutos) |
| **15515** | true | helper de UI de capping (`C33z.A08`, com 13537) |
| **19790** | false | quando true, o clone na inserção ignora o mapeamento de mensagem citada |
| **26867** | true | ramo do clone na inserção para mensagens enviadas com status 4 (significado não resolvido) |
| **30111** | true | manter participantes de lista armazenados quando um save os esvaziaria |
| **16731** | false | variante de `phash` `3:` em vez de `2:` |
| **28183** / **28184** | false / false | bucketing `primcomp` mestre / bucketing manual de status |
| **28185** / **28199** / **34545** | 512 / 2 / 0 | limiar de participantes do bucketing / segundo int (não resolvido) / limite de rollout |
| **28731** / **27031** | false / false | múltiplos modos de status / custom list store |
| **29113** | false | tratamento de stanza-too-large para status |
| **23463** / **23639** / **23874** | 0 / false / false | protocolo de get de privacidade (1 MEX, 2 shadow, senão SMAX) / set de privacidade via MEX / caminho de busca da lista de privacidade |
| **14837** | false | GAP enforcement |
| **20278** (string) | `{"max_messages": 10000, "farthest_time_days": 30}` | limite padrão de transmissão Business, sem leitor no consumidor |

---

## 8. Baileys (`baron-baileys-v2`, verificado contra o código-fonte)

| Área | Implementação | Veredito contra a 2.26.41.6 |
|------|---------------|-----------------------------|
| Envio de status | `messages-send.js`: `isStatus`, `statusJidList` anexado à lista de participantes, `<meta status_setting session_scope="status">` | confere com 6.1 / 6.2; `statusPrivacy` não é validado (válidos: `allowlist`, `closefriends`, `contacts`, `customlist`, `denylist`) |
| Escala de público | `statusJidList` explícito, sem buckets, sem atributo `bucketing` | públicos grandes atingem os limites de stanza (6.1) |
| Excluir lista | `deleteBroadcastList`: `w:b` set, `<delete><list id/></delete>` | confere com 3.3 |
| Cota | `fetchBroadcastListQuota`: `xmlns="w:biz"` com filho `<broadcast_list_quota/>` | a requisição não confere (`w:b`, `smax_id=143`, sem filho); o parsing da resposta confere |
| Obter listas / app-state / envio de lista | não implementado / `businessBroadcastListAction` emitido como `settings.update` / `isJidBroadcast` apenas para decodificação | ver abaixo |

| Sintoma | Causa | Correção |
|---------|-------|----------|
| envio para lista clássica descartado ou rejeitado | listas são estado do dispositivo primário: companions ocultam o recurso, descartam cópias de lista da própria conta com `participants` (415), não existe IQ de criação | não direcionar a JIDs de lista a partir de um companion; enviar mensagens 1:1 por destinatário ou usar `status@broadcast` com `statusJidList` |
| destinatários não resolvidos | não há consulta de membros de listas em companions; participantes são endereçados por LID e filtrados por mapeamento | resolver os LIDs via usync primeiro |
| erros na requisição de cota | namespace errado | `xmlns="w:b"`, `smax_id` 143, `type="get"`, `to="s.whatsapp.net"` |

Envios 1:1 separados são compatíveis no transporte, mas não são uma lista clássica (sem chat de lista, id compartilhado ou cota).

---

## 9. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|----------|
| `missing_pn_lid_mapping_for_broadcast`, `lid-broadcast-filtered-participants` | o PN do destinatário não tem mapeamento LID | obter LIDs (usync) antes de adicionar ou enviar |
| 415 `received peer broadcast message on companion-mode` | cópia de lista com `participants` em um companion | esperado, companions não processam envios de lista |
| envio bloqueado, sheet de limite | `messages_left == 0` com 13537 e 16585 | aguardar `reset_ts_s`, excluir mensagens de lista não enviadas |
| código de banimento 106 | mensagens demais para uma lista de transmissão | aguardar `expiry_in_seconds` |
| `broadcast_would_be_cleared` | save de participantes com conjunto vazio | a flag 30111 mantém os participantes |
| `EMPTY_FANOUT` | o público resolveu para zero dispositivos | corrigir o público, `StatusEmptyAudienceGuard` deveria bloquear antes |
| `stanza_too_large`, `payload_too_large` | dispositivos ou payload demais | partes / buckets (6.1, 6.4), flag 29113 |

---

## 10. Distinções-chave

| Não confundir | Diferença |
|---------------|-----------|
| Lista (tipo 3) vs `status@broadcast` (tipo 5) | lista: destinatários armazenados, clones por destinatário, cota mensal; status: público por publicação, sem clones, tabelas próprias |
| Lista vs grupo | mesmo store de participantes e caminho de sender key; a lista é somente do primário, destinatários não são membros e veem chats 1:1 |
| Listas `w:b` do servidor vs ação de app-state 69 | `w:b` restaura listas após o registro; a ação 69 é escrita para sync e não tem handler de aplicação no consumidor |
| Cota (`w:b` smax 143, ≤ 300) vs config 20278 (10.000 / 30 dias) | a cota é fornecida pelo servidor e aplicada pela UI; 20278 não tem leitor no consumidor |
| Cota vs código de banimento 106 vs GAP | limite brando com UI / banimento temporário emitido pelo servidor / regras de inbox do lado de recebimento |
| IQ `privacy` vs públicos personalizados | o IQ guarda três modos do servidor; listas personalizadas e amigos próximos são locais mais a ação de app-state 44 |

---

## 11. Fluxo completo

```
[User]  New broadcast → select ≤ 256 contacts
     ▼
[Client]  C0YJ.A0E → <seconds>@broadcast ; A0K.A04 → LID filter, group_participant_user rows
     │     send → message.broadcast = 1 ; C231399zG clones into each recipient chat (same key id)
     │     quota gate: 13537 + 16585, messages_left > 0
     ▼
[SendE2EMessageJob]  F6P: skmsg + SKDM per device (pkmsg/msg) + ephemeral blobs ; DSM to own devices (phash)
     ▼
<message to="<id>@broadcast" phash id><participants>…</participants><enc type="skmsg"/><cap/></message>
     ▼
[WA Server]  (not observed) fan-out, ack
     ▼
ack → C22500tF updates list row + all clones ; receipts → splitStatusUpdateReceipts ; quota decremented on add

[User]  status: choose audience (contacts / allow / deny / close friends / custom)
     ▼
[Client]  validateAudience → StatusEmptyAudienceGuard ; users → LID → devices ; buckets c / f / a when 28184 on
     ▼
[SendE2eStatusJob]  type STATUS ; status_send_part rows ; sender key per bucket
     ▼
<message to="status@broadcast" phash bucketing><participants>…</participants><enc type="skmsg" bucket/><meta status_setting session_scope/></message>
     ▼
[WA Server]  (not observed) ack within 300 s ; viewers reply / react
     ▼
status_add_on / status_notify / status_reply rows ; status_receipt_device bookkeeping
```

---

## 12. Incógnitas

| Item | Status |
|------|--------|
| Como o servidor registra uma lista (existem apenas os IQs get / delete / quota) | registro no momento do envio inferido |
| Regra do servidor de que destinatários devem ter o remetente salvo; valores de tamanho da lista e cota | lado do servidor (somente texto de UI e verificações de faixa) |
| Comportamento de aplicação no consumidor da ação de app-state 69 | nenhum handler encontrado |
| O que os destinatários recebem de uma mensagem de lista; regra de recibo resumido da linha da lista | não visível a partir do remetente |
| Combinação de atualização da cota, conjunto de tipos de mensagem isentos | decompile truncado / não rastreado |
| Modo de status local 3, `threebuckets`, flags 28199, 26867, 15515, status-config `A0F` / `A0I` | não resolvido |
| Uso de `location@broadcast`; expansão de "GAP" | não rastreado / não está no APK |
| Tráfego | nada capturado |
