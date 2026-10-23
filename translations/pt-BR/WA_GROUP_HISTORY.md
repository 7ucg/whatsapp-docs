<!-- src-sha1: 0c8270cd51a33a8c9e23ceb0a6129e273e5cb070 -->
# WhatsApp Histórico de Grupo — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** compartilhamento de histórico de grupo no Android (mensagens recentes do grupo enviadas a novos membros): configuração de admin `member_share_group_history_mode`, elegibilidade de remetente e destinatário, fluxo de entrada por adição / aprovação e job pendente, seleção e limites de mensagens, `MessageHistoryBundle` (campo 70) e `MessageHistoryNotice` (campo 102), proto interno `GroupHistory`, criptografia e upload de mídia do bundle, validação e importação no destinatário, metadados do grupo (participantes, endereçamento LID vs PN, relações de comunidade), uso de sender-key, reporting tokens, HistorySync de dispositivos companheiros (`HistorySyncConfig`, tipos de sync, operações peer sob demanda), feature flags, Baileys

---

## 1. O que é (tecnicamente)

O compartilhamento de histórico de grupo permite que um membro do grupo (admin, ou qualquer membro se o admin permitir) envie um bundle de mensagens recentes do grupo para pessoas recém-adicionadas, para que o novato veja o contexto. É uma mensagem de grupo normal com criptografia de ponta a ponta cujo payload é um arquivo de mídia (um protobuf de entradas `WebMessageInfo`). **Não** é o HistorySync de dispositivos companheiros (seção 11), embora ambos compartilhem a palavra "history" e algumas capability flags.

Todas as afirmações vêm de análise estática do APK decompilado; nada foi capturado na rede. Níveis: **found** = lido no código ou em resources, **inferred** = deduzido do código, **unknown** = não resolvido. Os nomes ofuscados foram re-resolvidos na 2.26.41.6 a partir de strings estáveis (`FMessageGroupHistoryBundleProtobuf`, `GroupHistorySendPermissionChecker`, `PendingSendGroupHistoryJob`, `member_share_group_history_mode`, `Group History`).

| Entidade | Nome na 2.26.41.6 | Função |
|----------|-------------------|--------|
| Mensagem bundle | `C213539Ar` (`FMessageGroupHistoryBundle`), FMessage tipo **117** | mensagem de mídia externa, `Message.messageHistoryBundle` campo **70** |
| Mensagem notice | `C213519Ap` (`FMessageGroupHistoryNotice`), FMessage tipo **118** | linha "histórico foi enviado", `Message.messageHistoryNotice` campo **102** |
| Serializador / parser do bundle | `C34677F2y` (`FMessageGroupHistoryBundleProtobuf`) | construir e validar a mensagem externa |
| Serializador / parser do notice | `C34678F2z` (`FMessageGroupHistoryNoticeProtobuf`) | construir e validar o notice |
| Construtor do bundle | `C9mW.A00` (+ `C231239yy`, `FMessageGroupHistoryBundleFactory`) | selecionar, empacotar, gravar arquivo, criar a mensagem de mídia |
| Seleção de mensagens | `A0G` (`GroupHistoryMessageManager`) | SQL para contagem e linhas |
| Elegibilidade | `A1W` (`GroupHistorySendPermissionChecker`), `C230099x1` (gates) | verificações de remetente / destinatário / entry point |
| Job pendente | `PendingSendGroupHistoryJob`, `SendGroupHistoryJobRequirement` | job durável após a adição |
| Provedor de requisitos | `C197318aR` (`SendGroupHistoryRequirementProvider`) | eventos de adição / aprovação liberam o job |
| Destinatário | `GroupHistoryBundleProcessor`, `GroupHistoryBundleFileProcessor` | baixar, parsear, inserir |
| Validadores / inserter | `C33241Eds`, `C34360Ew7`, `C34361Ew8`, `C33413Egg` (`GroupHistoryMessageValidator` / `GroupHistoryMessageInserter`) | verificações por mensagem e inserção no DB |
| Linha de tipo de mídia | `C15530gU.A0F` | `group-history`, `GROUP_HISTORY`, HKDF info `Group History`, id **117** |
| UI de configurações | `com.whatsapp.grouphistory.setting.ui.*`, `GroupPermissionsActivity` (`C201678ic`) | diálogo de quantidade, toggle do rodapé, switch de permissão |

Existem duas mensagens distintas por compartilhamento: o **bundle** (carrega os dados, enviado ao grupo) e o **notice** (carrega apenas contagens e destinatários, enviado depois que o bundle saiu do dispositivo, seção 5.4).

---

## 2. Metadados e configurações do grupo

### 2.1 Nó de info do grupo (`<group>`, caminho XMPP legado `C23201A1a.A0C`)

Parseado pelo mesmo helper para queries `w:g2` e notificações de grupo; existe um gêmeo MEX/SMAX (`AbstractC23204A1d`, `AN6`, `C23690AKd`). Apenas campos relevantes aqui e para endereçamento:

| Atributo / filho | Tipo | Uso |
|------------------|------|-----|
| `id`, `creation`, `subject`, `s_t`, `s_o`, `s_o_pn`, `creator`, `creator_pn` | attrs | identidade; os gêmeos `_pn` carregam o JID de telefone ao lado de um LID |
| `addressing_mode` | `lid` ou `pn` | armazenado em `wa_group_admin_settings.addressing_mode`; qualquer valor diferente de `pn` é lido como `lid` (`AbstractC268510t`) |
| `<group_history/>` | filho vazio | presença booleana; armazenado como `history_enabled`; significado inferido (feature flag do grupo) |
| `<member_share_group_history_mode>` | texto | configuração de admin, 2.4 |
| `<member_add_mode>` | `all_member_add` / outro | `member_add_mode` 1 / 0 |
| `parent`, `default_sub_group`, `linked_parent jid`, `general_chat` | filhos | tipo do grupo, 2.3 |

### 2.2 Participantes e endereçamento (found)

`<participant jid lid phone_number type display_name username join_time group_history_sent>` (`C23201A1a.A05`, `C23205A1e.A0J`):

| Atributo | Uso para histórico de grupo |
|----------|-----------------------------|
| `jid` | participante, LID ou PN conforme `addressing_mode`; um JID PN com atributo `phone_number` é verificado quanto a divergência |
| `lid`, `phone_number` | a outra forma de endereço; armazenada via repositório de mapeamento de JID |
| `join_time` | long positivo (segundos, inferred); armazenado por participante; base para "entrou há tempo demais" |
| `group_history_sent` | `"true"` / `"false"`, Boolean; alimenta `group_participant_user.group_history_send_state` (mapeamento inferred, 3.2) |

As listas de destinatários e remetentes nos metadados do bundle (seção 6.2) são strings JID. O job as normaliza para o modo de endereçamento do grupo antes do uso: `PendingSendGroupHistoryJob.A01` mapeia cada destinatário para seu **LID** quando o grupo é endereçado por LID (`C30194DBb.A05`), senão mapeia LID para PN (`C0YH.A0G` / `AbstractC197018Zw.A0Y`). Quando um participante é adicionado, o job aceita ambas as formas (`C0YH.A0J` retorna a contraparte) para casar com os conjuntos de requisitos. Qual forma vai na rede depende do modo do grupo (inferred do código de mapeamento).

### 2.3 Relações de comunidade e grupo pai

`C23201A1a.A01` classifica um nó de grupo: **0** normal, **1** pai de comunidade (`parent`), **2** subgrupo vinculado (`linked_parent`), **3** subgrupo padrão (`default_sub_group`), **6** general chat. `A03` lê o JID pai de `linked_parent jid`. O padrão de `membership_approval_mode` para subgrupos vem de `parent/default_membership_approval_mode="request_required"`.

Found: `A1W` verifica apenas o **tipo de JID** (tipos 1 e 2 passam por `C0DZ.A0l`: grupo `@g.us` e o grupo `@temp` `C99Q`), não o papel na comunidade. O destinatário aceita apenas o tipo 1 (`C0DZ.A0b`). Se um grupo pai / de avisos é excluído por gates do servidor ou de experimento por grupo (23245 / 30905 são por grupo) é unknown. Mensagens de comentário (comentários de avisos da comunidade) e filhos de associação viajam em listas separadas (6.1); o destinatário descarta um comentário ou filho cujo pai não está no bundle (`orphan_parent_not_in_bundle`, `invalid_comment`).

### 2.4 Configuração de admin `member_share_group_history_mode`

| Valor na rede | Enum (`EnumC216299Tq`) | Int local | Significado |
|---------------|------------------------|-----------|-------------|
| ausente / desconhecido | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` 0 | 0 | não definido |
| `admin_share` | `ADMIN_SHARE` 1 | 1 | apenas admins enviam histórico |
| `all_member_share` | `ALL_MEMBER_SHARE` 2 | 2 | qualquer membro pode enviar |
| `all_member_share_toggle_on` | `ALL_MEMBER_SHARE_TOGGLE_ON` 3 | 2 | igual a 2; variante vista em notificações (distinção inferred) |

Mapeamento: `AbstractC227759t3.A01(String)` (string para int), `A00(enum)` (enum para int, 2 e 3 para 2).

| Item | Detalhe (found) |
|------|-----------------|
| Definir | switch em `GroupPermissionsActivity` (`C201678ic.A04`): operação MEX `SetGroupProperty` (cliente `whatsapp-android-mex`, classe de input `C204518nF`) com `member_share_group_history_mode` = `ALL_MEMBER_SHARE` ou `ADMIN_SHARE`. O mesmo input também carrega `allow_admin_reports`, `allow_non_admin_sub_group_creation`, `announcement`, `hidden_group`, `locked`, `member_add_mode`, `member_link_mode`, `membership_approval_mode_enabled`, `participant_label_enabled`, `subject` |
| Notificação | filho `member_share_group_history_mode` da notificação de grupo (`w:gp2`, inferred) (`C22270sr`) chama `A0g(actor, group, mode int, ts)`: atualiza o modo armazenado e insere uma mensagem de sistema |
| Mensagem de sistema | "turned on / off recent history sharing for new members" em seis variantes (actor `%s`, "Recent history sharing was ...", "You ..."), cada uma com "Tap to change" ou "Tap to learn more" |
| History sync | `GroupShareGroupHistoryModeHistorySync` recria a mensagem de sistema para companheiros; `GroupChangeHistoryEnabledHistorySync` faz o mesmo para `history_enabled` |
| DB | `wa_group_admin_settings`: `share_group_history_setting_mode`, `group_history_toggle_mode`, `history_enabled`, `earliest_group_history_message_timestamp_ms` |

O significado de `group_history_toggle_mode` (int, separado do modo de compartilhamento) não foi resolvido; a coluna é lida para grupos em que é diferente de zero e `group_state = 0`. Texto da UI: "Admins can choose if members are allowed to send message history", "Admins control if history is sent", "When adding someone to the group, members have the choice to send up to 100 recent messages".

---

## 3. Elegibilidade

### 3.1 Remetente (`A1W.A03`, found)

| # | Condição | Senão |
|---|----------|-------|
| 1 | kill switch **35987** ligado (pré-requisitos do remetente) | `PREREQUISITES_DISABLED` |
| 2 | JID do grupo tipo 1 ou 2 | `GROUP_TYPE_NOT_ELIGIBLE` |
| 3 | linha de contato do grupo existe | `GROUP_NOT_FOUND` |
| 4 | estou no grupo, e sou admin / superadmin, ou (`require_membership_approval` = false e `member_add_mode` = 1 e modo de compartilhamento = 2) | `SENDER_NOT_ELIGIBLE` (o log lista os três valores) |
| 5 | existe ao menos uma mensagem compartilhável (contagem `A0G.A00` > 0) | `NO_SHAREABLE_MESSAGES` (também corrige o timestamp mais antigo armazenado, `A0A`) |
| 6 | gate por entry point `A1W.A02` (3.3) | `EXPERIMENT_DISABLED` |

Portanto, um membro comum só pode enviar em grupos onde qualquer um pode adicionar membros, nenhuma aprovação é necessária e o admin habilitou `all_member_share`.

### 3.2 Destinatário (por usuário adicionado, found)

| Verificação | Código de resultado |
|-------------|---------------------|
| o destinatário não é um bot (`AbstractC24760wu.A03`) | `RECEIVER_NOT_ELIGIBLE` |
| o contato do destinatário não está "no longer active" (`externalUserState`, `A07`) | `RECEIVER_INACTIVE` |
| existe linha de participante para (grupo, usuário) | `NOT_IN_GROUP` |
| `now - join_time` abaixo da flag **30333** (unidade não resolvida) e `group_history_send_state` é null ou 1 | `NOT_NEW_OR_ALREADY_SENT` |

`group_history_send_state` (coluna de `group_participant_user`, escrita por `C14850fN.A0R`): 1 = ainda elegível, 2 = já enviado (found a partir do ramo "already sent" e do caminho de cancelamento que redefine 2 para 1). O mapeamento do atributo de rede `group_history_sent` para o estado é inferred.

### 3.3 Gates (`C230099x1`, `A1W.A02`)

Cada gate é `flag global OR exposição por grupo` (`C41861nA.A04(group, id)`):

| Helper | Global | ID por grupo | Uso |
|--------|--------|--------------|-----|
| `A01` | **26451** | 30905 | entry point `AFTER_JOIN` |
| `A02` | **15313** | 23245 | enviar histórico durante a adição (`A1W.A0B`), também controla `onGroupParticipantsAdded` |
| `A03` | **29973** | 30906 | chamadores não rastreados |

Entry points (`C9SA`): `AFTER_JOIN`, `FROM_MENTION`, `FROM_CONTACT_MESSAGE`. `FROM_MENTION` e `FROM_CONTACT_MESSAGE` estão adicionalmente atrelados aos kill switches **35554** / **35555** e ao gate `A02`. A polaridade da verificação combinada não está resolvida (o fluxo do decompile está confuso em torno de `A1W.A09`).

---

## 4. Fluxo de entrada (lado do remetente)

### 4.1 Entry points da UI (found)

| Entrada | Classe | O que acontece |
|---------|--------|----------------|
| Seletor de adicionar membros | `VoipParticipantPickerFragment` + `GroupHistoryAddMembersSettingFooterView` | rodapé "Send message history to approved members" com um toggle e um link "recent messages"; tocar abre o diálogo de quantidade; o estado do toggle é lembrado (`is_group_history_toggled`) |
| Tela de aprovação de membros | `GroupMembershipApprovalRequestsFragment` (`C24002AWf`) | mesmo diálogo de quantidade antes de aprovar |
| Sheet pós-entrada | `GroupHistoryAfterJoinSendBottomSheetFragment` | "Send message history to %1$s?" (um ou dois nomes) |
| Menção / contato compartilhado | entry points `FROM_MENTION`, `FROM_CONTACT_MESSAGE` | apenas nomes; comportamento não rastreado |

Texto de confirmação no primeiro uso: "Group history messages are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them." (contador `group_history_confirmation_dialog_confirmed_times`).

### 4.2 Opções de quantidade (`C229129vL.A00(n)`, found)

`n` = contagem de `A0G.A00` (mensagens que cabem nos limites de 5.1).

| n | Opções |
|---|--------|
| 0 | nenhuma ("No message history to view") |
| 1..25 | uma opção, `n`, marcada como "all" ("Last %d (all)") |
| > 25 | `k = min(4, ceil(n/25))`, `step = max(25, n/k)`; opções `step`, `2*step`, ... até `k-1` passos, depois `n` (marcada como "all" sob uma condição de tamanho no último passo; comparação exata não resolvida) |

A lista é então invertida por `C0CG.A0Z` (inferred: maior primeiro); a primeira entrada vem pré-selecionada. Um aviso sobre mensagens fixadas ("All available pinned messages will be included") é sempre exibido.

### 4.3 IQ de adição e ligação de eventos (found)

```xml
<iq xmlns="w:g2" type="set" to="GROUP@g.us" id="…">
  <add>                                       <!-- optional transparency_acknowledged="true" -->
    <participant jid="USER"><privacy>bytes</privacy></participant>   <!-- privacy child optional -->
  </add>
</iq>
```

Found lendo o builder (`C11410Yt`): nenhum atributo específico de histórico é adicionado à requisição de adição; a decisão sobre histórico é puramente local. Eventos que liberam o job pendente (`C197318aR`, timeout de 32 s para o próprio IQ):

| Evento | Handler | Efeito |
|--------|---------|--------|
| Histórico solicitado | `CCP(params, group, requestId, receivers, nonReceivers, approvedByMe)` | persiste `PendingSendGroupHistoryJob`; lembra a contagem escolhida em `A08[requestId]`; define `group_history_usage_activated` |
| IQ de adição respondido | `BfO(C222169gu)` | armazena o mapa de resultado por requisição |
| Participantes adicionados (notificação) | `BvD` (somente com o gate `A02`) | adiciona aos conjuntos "added by me" / "added by others" |
| Aprovação de membro respondida | `C05(group, user, requestId, approved)` | armazena o usuário aprovado (ou vazio) |

### 4.4 Job pendente (`PendingSendGroupHistoryJob`, found)

Campos: `permanentGroupRawJid`, `requestId`, `messageCount`, `lastMessageSortId`, `groupHistoryReceiverRawJids`, `groupHistoryNonReceiverRawJids`, `approvedByMeRawJids`, `jobScheduledServerTimeInMillis`, `expirationTimeInMins`. ID de job persistente `group-pending-send-group-history`, requisito `SendGroupHistoryJobRequirement` (todos os JIDs de destinatário devem ser parseáveis, senão `invalid group history receiver jid`).

| Etapa | Detalhe |
|-------|---------|
| Requisito atendido quando | o job expirou; ou o resultado de adição / aprovação para `requestId` chegou; ou um destinatário está no conjunto "added by others" e não foi aprovado por mim; ou um destinatário agora é participante (`A0r`) |
| Expiração | `scheduled + flag 19034` minutos; job expirado: cancelar, redefinir estado do participante 2 para 1 |
| Execução | dividir destinatários em já-entrados e restantes; os restantes vão para um **novo** job pendente (mesmo request id, não-destinatários filtrados); os destinatários já entrados recebem o bundle (`C9mW.A00`) |
| Destinatários bot | um destinatário bot TEE (`AbstractC197238aI.A00`) é tratado por um carimbo separado de history-share (`A04`, 5.5) |
| Proteção contra duplicata | mapa `C197318aR.A09` (grupo, usuário) para horário de envio; entradas mais antigas que `19034` minutos (mín. 5) são removidas |

---

## 5. Seleção, limites e empacotamento

### 5.1 Seleção de linhas (`A0G`, `AbstractC494421h.A00`, found)

```sql
SELECT … FROM available_message_view [ / with association join when 24033 ]
WHERE timestamp >= (scheduledTimeMs - flag18406 s)
  AND chat_row_id = ? AND sort_id <= ?                 -- anchor = last message at scheduling time
  AND view_mode IS NOT 1 AND view_mode IS NOT 3
  AND message_type IN (shareable types)                -- from the type registry, BUv()
  AND (association_type IS NULL OR association_type IN (supported))   -- only when 24033
  AND (from_me = 0 OR status NOT IN (-1,0,1,2,7,20,21,22))
  AND (expire_timestamp IS NULL OR expire_timestamp >= now OR keep_in_chat = 1)
ORDER BY sort_id DESC LIMIT n
```

| Parâmetro | Fonte |
|-----------|-------|
| `n` | a query de contagem usa a flag **18405** como LIMIT; a query de envio usa a contagem escolhida pelo usuário |
| janela | flag **18406** (segundos) antes do horário de agendamento; o texto da UI promete "up to 100" mensagens |
| tipos compartilháveis | registro por tipo de FMessage (`C222979iT.A00`, `C1ZP.BUv()` true), com override por mensagem (`C30039D5b`); não enumerado aqui |
| mensagens próprias | somente as que saíram do dispositivo (`status` fora do conjunto pendente / falho `AbstractC494421h.A00`) |
| efêmeras | mensagens expiradas e não mantidas são puladas |

Se um sort id pós-entrada é conhecido (`C14650f0.A05`), a contagem ancora nele ("post-join query"); caso contrário, ancora na mensagem mais recente ("pre-join query").

### 5.2 Listas no bundle (found, `C9mW.A00`)

| Lista | Conteúdo | Limite |
|-------|----------|--------|
| `messages` | as linhas selecionadas (somente compartilháveis) | `n` |
| `uncountedAssociatedMessageLists` | filhos anexados a um pai selecionado (itens de álbum, enquetes, ...), agrupados por `(parent key, association type)`; somente com **24033** | não contados em `messageCount` |
| `commentMessages` | comentários em mensagens selecionadas (`C14780fG.A02(list, flag 6050, …)`) | flag **6050** (inferred como o teto) |
| `outOfWindowPinnedMessages` | mensagens fixadas mais antigas que a selecionada mais antiga; somente não-mídia; filtradas pelo conjunto compartilhável | todas as disponíveis (string de aviso); teto no destinatário flag **19811** (inferred) |

Tipos de associação (`C13O`, 21 valores): `FUTURE` 0 (também o fallback), `MEDIA_ALBUM` 1, `BOT_PLUGIN` 2, `EVENT_COVER_IMAGE` 3, `HD_VIDEO_DUAL_UPLOAD` 5, `STATUS_EXTERNAL_RESHARE` 6, `MEDIA_POLL` 7, `POLL_ADD_OPTION` 20, `STREAMED_HD_VIDEO_DUAL_UPLOAD` 22 e outros tipos de status / sticker / dual-upload.

### 5.3 Empacotamento (found)

1. O proto `GroupHistory` (6.1) é serializado em um arquivo com extensão `proto` (`File … A0Z(C15530gU.A0F, "proto")`); nenhuma etapa de compressão foi encontrada.
2. Uma nova FMessage do tipo 117 é criada no chat do grupo com o arquivo como mídia (`mimetype application/protobuf`) e entregue ao pipeline normal de envio de mensagens de mídia (upload e criptografia, seção 7).
3. Campos locais na FMessage: contagem de mensagens, timestamp mais antigo na janela (segundos), timestamp mais antigo no total (mín. com mensagens fixadas), destinatários, não-destinatários, tamanhos das listas de mensagens empacotadas, tamanho do arquivo, tempo de construção (telemetria).
4. Se **24741** está ligada e a mensagem não tem secret, um message secret novo é gerado para ela; em seguida os reporting tokens por mensagem original são calculados (seção 9).

### 5.4 Notice após o envio (found, `ANQ.C0M`)

Quando o bundle atinge o status **1** (ou **24** quando a flag **28787** está ligada) e o notice ainda não foi enviado (`A00 != 1`), o dispositivo cria um notice tipo 118 no mesmo grupo com as contagens, timestamps e destinatários do bundle e o envia (`C33166Ecf.A06`). Todo membro do grupo o recebe; os destinatários nomeados em `historyReceivers` o marcam adicionalmente (`AbstractC30028D4q.A1B`).

### 5.5 Compartilhamento de histórico com bot TEE (found, breve)

Para um destinatário bot, `C9mW.A01` carimba as mensagens selecionadas que carregam um message secret com uma prova (`AbstractC33322EfC.A02(sender, botJid, "TEE History Share", stanzaId, secret)`) e envia um notice cujo `botHistoryShareSyncMetadata` lista `(stanzaId, messageSecretProof)`. Veja o relatório Meta AI para o contexto de bots: [WA_META_AI.md](./WA_META_AI.md). O caminho de bot não faz upload de um bundle.

---

## 6. Formato na rede

### 6.1 Arquivo interno: `GroupHistory` (`DSN`)

| Campo | Número | Tipo | Conteúdo |
|-------|--------|------|----------|
| `messages` | **1** | repeated `WebMessageInfo` (`C30626DTu`) | mensagens contadas |
| `uncountedAssociatedMessageLists` | **2** | repeated `UncountedAssociatedMessageList` (`C30578DRy`) | `messages` **1** (repeated WebMessageInfo), `parentMessage` **2** (`MessageKey`, `BD5`), `associationType` **3** (enum `C13O`) |
| `commentMessages` | **3** | repeated `WebMessageInfo` | comentários |
| `outOfWindowPinnedMessages` | **4** | repeated `WebMessageInfo` | fixadas |

O destinatário parseia os mesmos bytes uma segunda vez como `GroupHistoryWithMessageBytes` (`C30576DRw`: os mesmos quatro números de campo; entradas `C30543DQp` com `key` **1** (`MessageKey`) e `message` **2** (bytes); listas de associação `DPH` lidas apenas como `messages` **1**). Essa variante mantém os bytes serializados originais por mensagem (usada para validação de reporting token e tratamento de secret, inferred).

### 6.2 Mensagem externa: `Message.messageHistoryBundle` (`DT6`, campo **70**)

| Campo | Número | Tipo | Valor / uso |
|-------|--------|------|-------------|
| `mimetype` | **1** | string | deve ser igual a `application/protobuf` |
| `fileSha256` | **2** | bytes | 32 bytes, hash do texto plano |
| `mediaKey` | **3** | bytes | media key |
| `fileEncSha256` | **4** | bytes | 32 bytes, hash do texto cifrado |
| `directPath` | **5** | string | caminho de upload; vazio é logado, não fatal no momento do parse |
| `mediaKeyTimestamp` | **6** | int64 | segundos |
| `contextInfo` | **7** | `ContextInfo` | padrão |
| `messageHistoryMetadata` | **8** | `MessageHistoryMetadata` (`C30583DSd`) | abaixo |

`MessageHistoryMetadata`:

| Campo | Número | Tipo | Regra no recebimento |
|-------|--------|------|----------------------|
| `historyReceivers` | **1** | repeated string | ao menos um; o usuário atual deve estar listado |
| `oldestMessageTimestampInWindow` | **2** | int64 | presente e > 0 |
| `messageCount` | **3** | int64 | presente e > 0 |
| `nonHistoryReceivers` | **4** | repeated string | opcional |
| `oldestMessageTimestampInBundle` | **5** | int64 | opcional (inclui fixadas) |

### 6.3 Notice: `Message.messageHistoryNotice` (`DRY`, campo **102**)

`contextInfo` **1**, `messageHistoryMetadata` **2** (mesmo tipo, obrigatório com regras de destinatários, timestamp e contagem), `botHistoryShareSyncMetadata` **3** (`C25765B9z`: `botJid` **1**, `historyShareMessages` **3** repeated `BA2` = `stanzaId` **1**, `messageSecretProof` **2**). O layout lite não tem campo **2** em `C25765B9z`; um cutoff existe apenas como estado local (`C213519Ap.A03`).

### 6.4 Nível de stanza (found)

| Item | Bundle (117) | Notice (118) |
|------|--------------|--------------|
| `type` da stanza | `media` | não específico de mídia |
| `<enc>` media type | `group_history` (`C30106D7q`; no conjunto permitido de enc media types `C9E2` / `C33474Ehg`) | nenhum |
| `<meta appdata="…">` | **não definido** (`C213539Ar` não implementa `FZF`) | `group_history` (`C213519Ap.AVN`; `F6K` o escreve) |
| verificação no destinatário | `A0O == "media"` e `A0J == "group_history"`, senão erro 11 | `appdata == group_history`, senão erro 76 |
| `<reporting>` | opcional, seção 9 | nenhum |

Ambas as verificações são puladas quando as flags de envelope `A0V` / `A0U` estão definidas (significado não resolvido). Um bundle que chega com media type `group_history` mas sem mensagem correspondente, e um appdata de notice em um tipo estranho, são rejeitados por `GroupHistoryBundleDeserializationValidator` / `GroupHistoryNoticeDeserializationValidator` (`F3b` / `F3c`).

### 6.5 Marcadores de `WebMessageInfo` (`C30626DTu`, found)

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `isGroupHistoryMessage` | **57** | bool | a mensagem foi importada de um bundle |
| `reportingTokenInfo` | **62** | message | reporting tag (veja o relatório Reporting) |
| `groupHistoryIndividualMessageInfo` | **74** | `C30549DQv` | `bundleMessageKey` **1** (`MessageKey`), `editedAfterReceivedAsHistory` **2** (bool) |
| `groupHistoryBundleInfo` | **75** | `C30548DQu` | `deprecatedMessageHistoryBundle` **1**, `processState` **2** (enum `EnumC32128E2a`) |

`processState`: `NOT_INJECTED` 0, `INJECTED` 1, `INJECTED_PARTIAL` 2, `INJECTION_FAILED` 3, `INJECTION_FAILED_NO_RETRY` 4, `DEDUPED` 5.

---

## 7. Criptografia e mídia

| Camada | Found |
|--------|-------|
| Transporte da mensagem | fan-out normal de grupo: a mensagem 117 é cifrada como qualquer mensagem de grupo (`skmsg` com sender-key por grupo mais a distribuição usual de sender-key aos dispositivos). Os fundamentos não são repetidos aqui; a forma da stanza `<enc>` está em [WA_CALL_SIGNALING.md](./WA_CALL_SIGNALING.md) na seção sobre `<enc>`. O estado de sender-key por dispositivo fica em `group_participant_device` (`sent_sender_key`, `sent_add_on_sender_key`, `sent_sender_key_bucket`) |
| Linha de mídia | `C15530gU.A0F`: tipo de upload `group-history`, tipo de arquivo `GROUP_HISTORY`, HKDF info `Group History`, id 117 |
| Chave / cifra | media key aleatória, HKDF-SHA256 com info `Group History`, AES-256-CBC, HMAC-SHA256 truncado em 10 bytes anexado, `fileSha256` / `fileEncSha256` no proto: o esquema genérico em [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) seção 6 (expansão de 80 bytes no Android); aplicado a este tipo pelo pipeline comum de envio (inferred, apenas a linha do tipo foi lida) |
| URL de upload | `https://<host>/mms/group-history/<hash>?…`; a composição `mms/<upload type>` é found para a tabela (seção 4 do relatório de mídia); o caminho literal para este tipo não foi capturado (inferred) |
| Download | download de mídia padrão usando `mediaKey`, `directPath`, hashes; texto de falha `GroupHistoryBundleProcessor/download failed for … with reason …` |
| Reuso de chave | a media key do bundle é independente das chaves de mensagem das mensagens contidas |

O destinatário sempre trabalha a partir da `mediaKey` do proto; um bundle cujos hashes não têm 32 bytes é rejeitado (`bogus sha-256 hash received`, erro 14).

---

## 8. Destinatário: validação e importação

### 8.1 Verificações no parse (`C34677F2y.CM7`, found)

| Verificação | Erro |
|-------------|------|
| o JID do chat é um grupo (`A0l`) | 11 `chatJid is not a group` |
| envelope `media` + enc media type `group_history` | 11 |
| `mimetype == application/protobuf` | 11 |
| `fileSha256`, `mediaKey`, `fileEncSha256`, `mediaKeyTimestamp`, metadados presentes | 11 |
| `historyReceivers` não vazio, timestamp da janela > 0, contagem > 0 | 11 |
| usuário atual em `historyReceivers` (não para mensagens próprias) | 11 `current user is not in history receivers list` |
| gate **15311** desligado | FMessage placeholder `C35281aa` com código **82** ("Update to the latest version of WhatsApp to see it") |
| comprimento dos hashes 32 | 14 |

Notice (`C34678F2z`): chat de grupo, appdata, metadados com destinatários / timestamp / contagem; gate **15722** desligado gera placeholder com código **10008**.

### 8.2 Processamento (`GroupHistoryBundleProcessor`, found salvo indicação)

1. Gatilho: mensagem adicionada (`C0G`) e novamente no estado de mídia 3 (`C0M`). Um candidato é um chat de grupo (tipo 1), não enviado por mim, estado 0 ou 5, comigo na lista de destinatários, e mais novo que a flag **25910** (unidade não resolvida; senão "Message history expired").
2. Dedupe (flag **30462**): se um bundle já foi processado para a mesma sessão de entrada, o novo é marcado como deduped (`deduped_bundle_for_join_session`), UI: "%1$s also sent you message history, which you already got from someone else".
3. Baixar a mídia; falha exibe "Couldn't download message history from %1$s".
4. Parsear o arquivo duas vezes (`DSN`, `DRw`); falha de parse: `protobuf_parse_failed`.
5. Encontrar a âncora: a mensagem de entrada no grupo mais recente ("failed to find latest group join message, adding messages before the first message in chat" quando não há); uma âncora antiga demais: `anchor_message_too_old`.
6. Validar e inserir cada mensagem (8.3); associar cada linha inserida ao bundle (`group_history_bundle_association`: `bundle_message_key_id`, `message_row_id`, `message_sort_id`); marcar `isGroupHistoryMessage`.
7. Fixadas fora da janela: teto (flag **19811**, inferred), aplicar o estado de fixação compartilhado (`applySharedPin`).
8. Aplicar carimbos pendentes de history share de bot (`BotHistoryShareHelper`), depois telemetria (`group_history_receiver_user_journey`).

As linhas importadas são colocadas antes da âncora de entrada, de modo que aparecem acima da linha "you were added" (inferred da lógica da âncora).

### 8.3 Validação por mensagem (`C33241Eds`, `C34360Ew7`, `C34361Ew8`, `C33413Egg`, found)

| Motivo de skip | Causa |
|----------------|-------|
| `invalid_jid` | `key.remoteJid` difere do chat do bundle |
| `non_hex_id` | `key.id` não é somente hex |
| `timestamp_too_old` | `messageTimestamp` não é mais novo que o limite inferior permitido (campos do log `msgTs`, `allowedTs`, `diff`; limite derivado de estado local, fórmula não resolvida) |
| `parse_failed`, `pin_not_parsed` | o proto da entrada não foi parseado |
| `not_shareable` | tipo de mensagem não permitido para importação |
| `no_local_copy` | fixação compartilhada cuja mensagem foi pulada e não existe localmente |
| `max_limit_reached` | teto atingido |
| `timestamp_after_anchor` | mensagem mais nova que a âncora de entrada |
| `already_exists`, `duplicate`, `expired` | já presente localmente, duplicada no arquivo, efêmera expirada e não mantida |
| `orphan_parent_not_in_bundle`, `invalid_comment` | comentário / filho de associação sem o pai no arquivo |
| `insert_exception`, `anchor_messages_failed`, `insert_messages_exception` | erros do DB local |

Além disso: uma mensagem precisa ter seu `messageSecret` preservado (logs `messageSecretLost`, `noMessageSecret`); a cópia local prevalece quando existe uma mensagem com conteúdo diferente (`keeping local …`).

Tabelas tocadas (found): `group_history_bundle_association` (`bundle_message_key_id`, `message_row_id`, `message_sort_id`), `group_history_share_reporting_info` (`stanza_id`, `reporting_tag`, `send_timestamp`, `added_timestamp`, `reporting_token`, `reporting_token_version`, `is_send`, `validation_policy`), `group_participant_user.group_history_send_state`, `wa_group_admin_settings` (2.4).

---

## 9. Reporting tokens (breve)

Seção da stanza para um bundle quando **24741** está ligada (`F6C`, `GhsReportingTokenMessageSendStanzaContributor`):

```xml
<reporting>
  <message id="ORIGINAL_STANZA_ID"><reporting_token v="N">16 bytes</reporting_token></message>
  …
</reporting>
```

A derivação e o armazenamento do token estão em [WA_REPORTING.md](./WA_REPORTING.md) (seção 6.2); parte da derivação da chave roda em código nativo, então os bytes exatos não são reproduzíveis apenas com Java. No recebimento, quando **5718** e **24742** estão ligadas, a ausência de token para uma mensagem importada gera a telemetria `GROUP_HISTORY_MESSAGE_MISSING_FROM_PUBLIC_STANZA` (e, com **13063**, uma linha de diagnóstico interna); a mensagem ainda é inserida nesse caminho (inferred do fluxo de controle). Se o servidor exige tokens: unknown.

---

## 10. HistorySync de dispositivos companheiros (relacionado, não é histórico de grupo)

Os fundamentos de pareamento e app-state estão em [WA_LINKED_DEVICE_PAIRING.md](./WA_LINKED_DEVICE_PAIRING.md) e [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md). Apenas o que se relaciona a dados de grupo:

### 10.1 `HistorySyncConfig` (`C44601rs`, o companheiro anuncia; números de campo do layout lite)

| Campo | # | Valor do companheiro (found) |
|-------|---|------------------------------|
| `fullSyncDaysLimit`, `fullSyncSizeMbLimit` | 1, 2 | flags **15284**, **15283** |
| `storageQuotaMb`, `initialSyncMaxMessagesPerChat` | 3, 20 | não definidos no ramo rastreado |
| `recentSyncDaysLimit` | 5 | 0 |
| `supportMessageAssociation`, `supportHostedGroupMsg`, `supportAddOnHistorySyncMigration` | 14, 11, 13 | true |
| `supportGroupHistory` | 15 | flag **20658** |
| `onDemandReady` / `completeOnDemandReady` | 16 / 18 | `!` flag **18953** / false |
| `thumbnailSyncDaysLimit` | 19 | flag **21217** |
| `supportHatchHistory` / lista de canais de bot | 22 / 23 | flag **26445** / ramo em **26614** |
| call log, histórico de bot e CAG, `supportNewsletter`, `supportInlineContacts`, ... | 4, 6-8, 12, 24-27 | true (os demais false) |

Os campos restantes (`supportBizHostedMsg` 9, `supportRecentSyncChunkMessageCountTuning` 10, `supportGuestChat` 17, `supportManusHistory` 21, `supportUniversalReachChat` 26, `supportOmittedConversationIndex` 27) não são detalhados aqui.

### 10.2 Tipos de sync e mensagens

| Mensagem | Campo | Conteúdo |
|----------|-------|----------|
| `HistorySync` (`C25838BCy`) | `syncType` **1**, `conversations` **2**, `statusV3Messages` **3**, `chunkOrder` **5**, `progress` **6**, `pushnames` **7**, `globalSettings` **8**, `threadIdUserSecret` **9**, `threadDsTimeframeOffset` **10**, `recentStickers` **11**, `pastParticipants` **12**, `callLogRecords` **13**, `aiWaitListState` **14**, `phoneNumberToLidMappings` **15**, `companionMetaNonce` **16**, `shareableChatIdentifierEncryptionKey` **17**, `accounts` **18**, `nctSalt` **19**, `inlineContacts` **20/21**, `omittedConversations` **23/24** | conversas de grupo viajam em `conversations`; `pastParticipants` (**12**) lista ex-membros do grupo |
| `HistorySyncNotification` (`C25834BCt`) | `fileSha256` **1**, `fileLength` **2**, `mediaKey` **3**, `fileEncSha256` **4**, `directPath` **5**, `syncType` **6**, `chunkOrder` **7**, `originalMessageId` **8**, `progress` **9**, `oldestMsgInChunkTimestampSec` **10**, `initialHistBootstrapInlinePayload` **11**, `peerDataRequestSessionId` **12**, `fullHistorySyncOnDemandRequestMetadata` **13**, `encHandle` **14**, `messageAccessStatus` **15** | chunk referenciado por mídia; o payload é `HistorySync` |

Tipos de sync: `INITIAL_BOOTSTRAP` 0, `INITIAL_STATUS_V3` 1, `FULL` 2, `RECENT` 3, `PUSH_NAME` 4, `NON_BLOCKING_DATA` 5, `ON_DEMAND` 6, e no enum de 9 valores (`EnumC26456Bdr`) também `NO_HISTORY` 7 e `MESSAGE_ACCESS_STATUS` 8 (`EnumC26449Bdk` é a variante de 7 valores).

### 10.3 Operações peer data sob demanda (`EnumC26460Bdv`, found)

| Operação | Id | Campo de requisição (`C25823BCh`) | Campo de resposta (`C25828BCm`) |
|----------|----|-----------------------------------|---------------------------------|
| `HISTORY_SYNC_ON_DEMAND` | 3 | `historySyncOnDemandRequest` **4** (`BCR`: `chatJid` **1**, `oldestMsgId` **2**, `oldestMsgFromMe` **3**, `onDemandMsgCount` **4**, `oldestMsgTimestampMs` **5**, `accountLid` **6**, `supportInlineResponse` **7**) | nenhum definido; o histórico chega como `HistorySyncNotification` (inferred) |
| `FULL_HISTORY_SYNC_ON_DEMAND` | 6 | `fullHistorySyncOnDemandRequest` **6** (`BBB`: `requestMetadata` **1** `BBA`, `historySyncConfig` **2**, `fullHistorySyncOnDemandConfig` **3** `C156516k5`: `historyFromTimestamp` **1**, `historyDurationDays` **2**) | `fullHistorySyncOnDemandRequestResponse` **6** |
| `PLACEHOLDER_MESSAGE_RESEND` | 4 | **5** | **4** |
| `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` | 8 | **7** | **8** |

O primário mantém uma linha por sync em `msg_history_sync` (`device_id`, `sync_type`, `last_processed_msg_row_id`, `oldest_msg_row_id`, `sent_msgs_count`, `chunk_order`, `sent_bytes`, `last_chunk_timestamp`, `status`, `peer_msg_row_id`, `oldest_message_to_sync_row_id`, `session_id`, `size_limit_bytes`, `full_history_on_demand_request_id`, …). Tetos do lado do servidor para tamanho de chunk e contagem de mensagens não são visíveis no código do cliente lido aqui (unknown). Não existe operação sob demanda específica para o histórico compartilhado de um grupo.

### 10.4 Histórico de grupo em companheiros

| Item | Found |
|------|-------|
| Capability | `supportGroupHistory` (flag **20658**) em `companion-props`; armazenada no primário como `support_group_history` (relatório de pareamento, seção 6.2); consumidor não rastreado |
| Entrega do bundle | o bundle é uma mensagem de grupo normal, então todo dispositivo de um destinatário o recebe; strings para dispositivos vinculados ("Open WhatsApp on your phone and visit this group to see it") sugerem um placeholder ali (inferred) |
| Construção do sync no primário | `BuildHistorySyncParams` (`C33151EcQ`) carrega `supportGroupHistory`, `pullGroupHistoryUncountedChildren`, `maxCommentsToAdd`, `supportMessageAssociation`; consumidores não rastreados |
| Mensagens de sistema | mudanças de modo de compartilhamento, history-enabled, modo de adição / link / aprovação de membros são reconstruídas para companheiros pelas classes `Group*HistorySync` |

---

## 11. Feature flags e limites

IDs de flag em negrito; os valores são entregues pelo servidor, os padrões compilados não foram resolvidos (o texto da UI diz "up to 100" mensagens).

| Flag | Tipo | Controla | Nível |
|------|------|----------|-------|
| **35987** | bool | kill switch de pré-requisitos do remetente | found |
| **15313** / 23245 | bool / grupo | gate `A02`, enviar histórico durante a adição | found |
| **26451** / 30905 | bool / grupo | gate `A01`, entry point `AFTER_JOIN` | found |
| **29973** / 30906 | bool / grupo | gate `A03` | found (uso unknown) |
| **35554**, **35555** | bool | `FROM_MENTION`, `FROM_CONTACT_MESSAGE` | polaridade inferred |
| **18405** | int | LIMIT da query de contagem (teto do tamanho da oferta) | found |
| **18406** | int, s | janela retroativa antes do horário de agendamento | found |
| **19034** | int, min | expiração do job pendente, poda do dedupe (mín. 5) | found |
| **30333** | long | tempo máximo desde a entrada para um destinatário | found (unidade não resolvida) |
| **24033** | bool | listas de associação e filtro de associação | found |
| **6050** | int | teto de coleta de comentários | inferred |
| **24741** | bool | construir reporting tokens no envio | found |
| **28787** | bool | gatilho do notice no status 24 em vez de 1 | found |
| **20658** | bool | o companheiro anuncia `supportGroupHistory` | found |
| **15311** | bool | recebimento: bundle aceito (desligado: placeholder 82) | found |
| **15722** | bool | recebimento: notice aceito (desligado: placeholder 10008) | found |
| **30462** | bool | recebimento: dedupe por sessão de entrada | found |
| **25910** | long | recebimento: janela de frescor de um bundle | found (unidade não resolvida) |
| **19811** | int | recebimento: teto de fixadas fora da janela | inferred |
| **24034** / **25037** | bool / int | recebimento: processamento de filhos de associação e seu parâmetro int | inferred |
| **26039** | bool | gate do inserter (três locais) | found (uso unknown) |
| **5718** + **24742** | bool | recebimento: validação de reporting token | found |
| **13063** | bool | linha de diagnóstico interna em caso de token ausente | found |

---

## 12. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|----------|
| Sem opção "send history" | remetente não elegível (3.1), grupo sem consistência LID / PN, ou sem mensagens compartilháveis | o admin habilita `all_member_share`, modo de adição de membros `all_member_add`, sem aprovação; ou enviar como admin |
| O destinatário vê "Update to the latest version" | gate 15311 / 15722 desligado ou tipo desconhecido | nenhuma no cliente |
| Bundle rejeitado, erro 11 | MIME errado, tipo de envelope, media type, campo ausente, eu fora de `historyReceivers` | construir conforme a seção 6 |
| Bundle rejeitado, erro 14 | hash não tem 32 bytes | corrigir os hashes |
| Notice rejeitado, erro 11 / 76 | appdata diferente de `group_history` (parse, 11); appdata de notice em outro tipo (validador, 76) | definir `appdata=group_history` apenas no tipo 118 |
| Mensagens faltando após a importação | motivos de skip em 8.3 (`timestamp_too_old`, `not_shareable`, `invalid_jid`) | as keys devem ser ids hex do mesmo grupo |
| "Couldn't download message history" | download da mídia falhou (`directPath` expirado, key divergente) | tentar de novo; reenviar |
| O job nunca roda | evento de adição ou aprovação não visto, destinatários nunca se tornaram participantes, job expirado (19034) | adicionar de novo e reenviar |

---

## 13. Distinções-chave

| Não confundir | Com |
|---------------|-----|
| Bundle de histórico de grupo (tipo 117, `application/protobuf`, `group-history`) | notificação HistorySync de companheiro (`HistorySyncNotification`, `md-msg-hist`) |
| Bundle (dados, sem appdata) | notice (contagens e destinatários, `appdata=group_history`) |
| `member_share_group_history_mode` (quem pode enviar) | `group_history_toggle_mode` / `history_enabled` (significado não resolvido) |
| `historyReceivers` (recebem os dados) | `nonHistoryReceivers` (adicionados, não recebem) |
| `oldestMessageTimestampInWindow` (**2**) | `oldestMessageTimestampInBundle` (**5**, inclui fixadas fora da janela) |
| contagem de `messages` (`messageCount`) | filhos de associação e comentários não contados |
| `supportGroupHistory` em `HistorySyncConfig` (capability do dispositivo) | a configuração de admin |

---

## 14. Baileys (`baron-baileys-v2` 1.5.17)

Apenas fatos lidos em `src/Utils/group-history.js`, `src/Socket/groups.js`, `src/Socket/messages-recv.js`, `src/Socket/aigroups.js`, `src/Utils/validate-connection.js`, `WAProto/index.js`. Nada foi testado contra um servidor; nenhuma falha é afirmada.

| Tópico | Baileys | Android |
|--------|---------|---------|
| Proto | `GroupHistory`, `GroupHistoryWithMessageBytes`, `GroupHistoryBundleInfo`, `GroupHistoryIndividualMessageInfo`, `Message.messageHistoryBundle`, `messageHistoryNotice`, `HistorySyncConfig.supportGroupHistory` presentes em `WAProto` | 6 |
| Decoder | `decodeGroupHistory` tenta `zlib.inflateSync`, recua para bytes brutos; modo opcional `GroupHistoryWithMessageBytes`; `processGroupHistory` normaliza as quatro listas | nenhuma compressão encontrada no Android; protobuf bruto lido |
| Recebimento do bundle | nenhum código trata `messageHistoryBundle` (download de mídia, validação, inserção) | seção 8 |
| Envio do bundle | nenhum | seção 5 |
| Capability de companheiro | `supportGroupHistory: true` no `HistorySyncConfig` anunciado | flag 20658 |
| Configuração do grupo | `member_share_group_history_mode` lido dos metadados do grupo; `groupSetProperty(jid, property, value)` via MEX; a notificação mex `NotificationGroupMemberShareGroupHistoryModePropertyUpdate` emite `groups.update { memberShareHistoryMode }` | 2.4 |
| `aiGroupCreate` | aceita `memberShareGroupHistoryMode` (padrão `all_member_share`) mas não o coloca na stanza de criação no código lido | não se aplica |
| Atributos de participante | `group_history_sent`, `join_time` não parseados | 2.2 |
| Endereçamento | `addressing_mode` lido do nó do grupo, padrão `lid` ao enviar | 2.2 |

Consequência limitada ao que foi lido: um cliente Baileys que anuncia `supportGroupHistory` não consegue importar um bundle recebido, porque não existe consumidor no código-fonte. Um remetente deve seguir as seções 5 a 7 (envio pós-adição, tipo `media` com enc media type `group_history`, media type `group-history` com HKDF info `Group History`, notice com appdata); se o servidor aceita um bundle sem tokens `<reporting>` é unknown.

---

## 15. Fluxo completo

```
[Admin]  switch "Send message history" ─► MEX SetGroupProperty member_share_group_history_mode=ALL_MEMBER_SHARE|ADMIN_SHARE
     │
     ▼
[WA Server]  w:gp2 notification member_share_group_history_mode ─► all members: store mode, system message

[Sender]  add members (picker / approval screen / post-join sheet)
     │   A1W.A09: gate 35987, group type, sender (admin or all_member_share + all_member_add + no approval),
     │            receiver (join age, send_state), shareable messages
     │   A0G.A00 count ─► amount options (<=25 one option, else up to 4)
     ▼
iq set w:g2 <add><participant jid/></add>          (no history attribute)
     │
     ▼
[WA Server]  result ─► BfO / C05 / BvD events ─► PendingSendGroupHistoryJob requirement met
     │
     ▼
[Sender]  A0M: split joined / remaining (remaining re-queued) ─► C9mW.A00
     │   rows: timestamp >= scheduled - 18406 s, sort_id <= anchor, LIMIT n
     │   + association lists (24033) + comments (6050) + out-of-window pins
     │   GroupHistory proto ─► file ─► FMessage 117, mimetype application/protobuf
     ▼
upload  /mms/group-history  (HKDF info "Group History", AES-CBC + HMAC-10)       [WA_MEDIA_UPLOAD]
     │
     ▼
group message  type=media, enc mediatype=group_history, Message.messageHistoryBundle(70)
     │          metadata: receivers, nonReceivers, oldest ts (window / bundle), count
     │          optional <reporting><message id><reporting_token v/></message></reporting> (24741)
     ▼
[Receivers' devices]  C34677F2y checks (group, media, MIME, hashes, me in historyReceivers, gate 15311)
     │   download + decrypt ─► parse DSN / DRw ─► dedupe (30462) ─► anchor = join message
     │   validate each WebMessageInfo (jid, hex id, timestamp, type) ─► insert before anchor
     │   group_history_bundle_association, isGroupHistoryMessage=57
     ▼
[Sender]  bundle status 1 (24 with 28787) ─► notice type 118, appdata group_history, same metadata
     │
     ▼
[All members]  system row "<name> sent message history that starts on <date>"
```

---

## 16. Unknowns

| Item | Status |
|------|--------|
| Regras de aceitação do servidor, retenção, tetos de tamanho, exigência de reporting token | lado do servidor, não observado |
| Valores padrão de 18405, 18406, 19034, 25910, 30333 | entregues pelo servidor, padrões não resolvidos |
| Limite inferior exato de `timestamp_too_old` e unidade de 25910 / 30333 | não resolvido |
| Polaridade de `A1W.A02` por entry point; uso do gate `A03` e da flag 26039 | decompile confuso / não rastreado |
| Significado da coluna `group_history_toggle_mode` e do filho `<group_history/>` | nomes encontrados, semântica apenas inferred |
| Lista de tipos de mensagem compartilháveis (registro `BUv()`) | não enumerada |
| Renderização de um bundle no companheiro; consumidor de `support_group_history` no primário | não rastreado |
| Parte nativa da derivação da chave do reporting token | nativa, não lida |
| Tráfego | nada capturado; todos os fluxos vêm do código |
