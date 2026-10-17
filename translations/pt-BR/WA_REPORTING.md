<!-- src-sha1: 27b3b625c1ca67d873007881de02f13ba8cbf277 -->
# WhatsApp Reporting — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-17
**Escopo:** Denúncias de usuário/contato, grupo, canal, status, chamada e mensagem — stanzas SMAX `spam`, `spam_list`, tipos de denúncia, pontos de entrada `spam_flow`, reporting tokens, upload de conteúdo, UI de denúncia/bloqueio, denúncia aos admins, stanza de bloqueio e listas de motivos, erros do servidor, sinais de abuso no cliente, Baileys

---

## 1. O que é uma denúncia (tecnicamente)

Uma denúncia é um único IQ `set` para `s.whatsapp.net` no namespace `spam`. Ele carrega um nó `spam_list` (entidade denunciada, mensagens denunciadas, ponto de entrada, contexto de business discovery). O cliente reserializa as mensagens denunciadas como protobuf em texto puro e as envia junto com um reporting token e a chave que o verifica. O bloqueio é uma stanza separada (`blocklist`). A denúncia aos admins é uma terceira stanza, não relacionada (`w:g2`).

Todas as afirmações são análise estática do APK decompilado. Nível: **found** = lido no código, **inferred** = deduzido do código, **unknown** = não resolvido. Nada aqui foi capturado na rede.

| Entidade | Nome na 2.26.41.6 | Função |
|--------|----------------|------|
| Builder de IQ (multifuncional, `$t` seleciona o formato) | `C9EN` | constrói todo IQ de denúncia (tipos 0, 18-23) e muitos IQs não relacionados |
| Nó de motivo/ponto de entrada | `C9E2` | `spam_list` com `spam_flow`, `wi_trace_id`, `is_known_chat`, ... (`xmlns="spam"`) |
| Filho de configuração de grupo | `C9E1` | `allow_admin_reports` / `not_allow_admin_reports` |
| Wrapper de conteúdo | `C31080DfY` | `raw`, `content_validation`, `reporting_token`, `reporting_token_key` |
| Nós diversos | `C31084Dfc`, `C31085Dfd` | flags (`multicast`, `url_text`, ...), `biz_opt_out`, `reporting` |
| Serializador ("ReportRpcUtils") | `C33446EhE` | `getMessageMixin` / `getMessageRaw`, montagem do token |
| SMAX manager | `SpamRPCManager` | `A01`-`A06`, um por tipo de denúncia (nome do pacote não ofuscado) |
| Repo | `SpamReportRepo` | roteia por classe de JID, efeitos colaterais locais |
| Wrappers de RPC | `IndividualSpamReportRpc`, `GroupSpamReportRpc`, `NewsletterSpamReportRpc`, `StatusSpamReportRpc`, `ChannelStatusSpamReportRpc`, `EventSpamReportRpc` | pacote `com.whatsapp.reportinfra.rpc` |
| Whitelist de origem | `C9ZJ` | valida o ponto de entrada (78 valores) |
| UI | `ReportSpamDialogFragment` (+ `reportAsSpam$1`, `triggerExtraAction$2`, `ReportSpamDialogViewModel`) | diálogo de denúncia, bloqueio/saída opcional |
| Executor de bloqueio | `C227489sZ` → `C34631Yx` | IQ `blocklist` |
| Denúncia aos admins | `RtaXmppClient` | fila de denúncias `w:g2` |
| Token store | `C23070uA` | tabelas `reporting_info`, `reporting_info_content` |

Os nomes variam por build; todo nome ofuscado acima foi resolvido na 2.26.41.6 a partir de strings estáveis (`spam_list`, `spam_flow`, `reporting_token_key`, `GET_REPORTING_INFO_LIST`, `blocklist`).

---

## 2. Tipos de denúncia

### 2.1 Roteamento (found)

`SpamReportRepo.A02(contact, status, entryPoint, wiTraceId, messages, includeCallLogs)` ramifica pela classe do JID:

| JID denunciado | Classe RPC | `SpamRPCManager` | Builder `$t` | Classe de resposta | Rótulo de log |
|--------------|-----------|------------------|--------------|----------------|-----------|
| objeto de status selecionado (`AbstractC31014DeU` não nulo) em um JID de newsletter | `ChannelStatusSpamReportRpc` | `A02` | 23 | `C43535Iyq` | StatusReportV2 |
| usuário (PN, LID, interop) | `IndividualSpamReportRpc` | `A01` | 20 | `C43534Iyp` | IndividualReport |
| grupo | `GroupSpamReportRpc` | `A04` | 19 | `C43538Iyt` | GroupReport |
| objeto de status selecionado em qualquer outro JID, ou JID de status com lista de mensagens | `StatusSpamReportRpc` | `A05` | 22 | `C43533Iyo` | StatusReport |
| newsletter/canal | `NewsletterSpamReportRpc` | `A03` | 21 | `C43536Iyr` | NewsletterReport |
| id de evento (string) | `EventSpamReportRpc` | `A06` | 18 | `C43537Iys` | EventReport |
| qualquer outro | nenhuma | nenhum | nenhum | nenhuma | `SpamReportRepo: unrecognized jid` lançada, retornada como falha |
| chat de bot | nenhuma (ver 3.3) | nenhum | nenhum | nenhuma | `C214999If` |

Outros formatos de `C9EN` que não são denúncias de spam: `$t=0` denúncia aos admins e `$t=1` alternância de configuração de grupo (seção 9), `$t=2` sugestões de subgrupos, `$t=24/25/26` nós `status`. O RPC de evento é chamado a partir de lambdas de coroutine (`AYs`, `Aaa`); a UI de origem é unknown (existem os pontos de entrada de evento `event_home_report` / `event_info_report`, então as denúncias de evento são inferred).

### 2.2 Denúncias de chamada são denúncias de usuário (found)

`SpamReportRepo.triggerReportCallNonSuspend` (origem `call_spam_dialog_report`) chama `IndividualSpamReportRpc.A00` sem `jid` denunciado, sem mensagens e com um item de chamada. O item de chamada (`C31082Dfa`):

```xml
<call from="<callerJid>" id="<callId>" to="<ownJid>">
  <call_info duration="<s>" terminator="<jid>" start_time="<ts>" adder="<jid>" creator="<jid>"
             terminate_reason="<enum>" reason="<enum>" mediatype="audio|video"/>
</call>
```

`terminate_reason` inclui `crash, detect_identity_change, ended_by_peer, ended_by_self, ended_by_user, reconnecting, timeout, unknown` e erros fatais de codec. A flag **36386** escolhe a forma do JID próprio em `to` (`CUC()` vs `Ask()`, LID vs PN inferred). Uma denúncia de usuário pela UI com `shouldIncludeCallLogsInReport` adiciona até 5 itens de call log (`C16430i1.A0B(jid, 5)`).

---

## 3. Fluxo do cliente

### 3.1 Diálogo

`ReportSpamDialogFragment` (bottom dialog). Args do fragment (found): `flow` (a string do ponto de entrada, vira `spam_flow`), `shouldDeleteChatOnBlock`, `notifyObservableDialogHost`, `upsellCheckboxActionDefault`, `shouldOpenHomeScreenAction`, `showLeaveCheckbox`. `ReportSpamDialogViewModel.initializeSpamDialog$1` carrega o estado do diálogo.

Ao confirmar, `reportAsSpam$1` executa:

1. Chat de bot: pula o RPC (3.3). Caso contrário, `SpamReportRepo.A02(...)` com a mensagem selecionada em uma lista de um elemento (ou nenhuma).
2. O sucesso carrega um report id opcional; o erro mostra o toast `str3bf8` (ou `C227489sZ.A00`, log `spamreportmanager/spam/report/no-network-cannot-report`). O WAM `wam_spam_report_perf` é preenchido (11.3).
3. Ação extra opcional `triggerExtraAction$2` (3.2), diálogo de conclusão vindo de `H2U` (10.2), gravações locais (3.3).

### 3.2 Somente denunciar vs denunciar + ação extra (found)

A checkbox mapeia para a string `report` (desmarcada) ou `report_block` (marcada), usada em analytics (`asd.BaC` vs `BaD`) e no toast pós-denúncia. A ação extra difere conforme o alvo:

| Alvo | Ação extra quando marcada |
|--------|--------------------------|
| usuário | bloqueio via `C227489sZ.A01` → IQ `blocklist` de `C34631Yx` (seção 8), motivo do bloqueio `null`, ponto de entrada = `flow`, `deleteChat` = arg `shouldDeleteChatOnBlock` |
| grupo | task de sair do grupo (`C98C` / `C9CI`, executada com o JID do grupo; semântica de saída inferred) |
| canal | oculta localmente o canal denunciado (`NewsletterReportCompletionListener`, flag **25218**), depois o fluxo de sair/deixar de seguir a newsletter |

O IQ de denúncia é enviado primeiro; o bloqueio/saída roda depois que o RPC retorna, independentemente do resultado (inferred a partir do fluxo de controle, sem checagem de sucesso antes de `triggerExtraAction$2`).

### 3.3 Chats de bot e efeitos locais (found)

Chats de bot pulam o `SpamReportRepo`: o cliente chama `BotMessageHelper/reportUgc` (`E1J.GENERIC`, `C27847C7h`) e trata como sucesso (`C214999If`); formato na rede unknown. Para os demais chats, `C24120Ab1` case 4 faz:

| Passo | Efeito |
|------|--------|
| nenhuma mensagem selecionada | coleta as últimas **5** mensagens do chat (`C14680f4.A01(..., 5, true)`; linhas de tipo system excluídas, sem filtro `from_me` nesta variante) como conteúdo denunciado |
| chat de usuário | log local `S3q.A0C(jid, localCode(flow), ...)`, `OptimisedDeliveryConversionLoggingController/handleUserReport`; a flag **20085** controla `H0J.A00(jid, ...)` (finalidade unknown) |
| após o RPC | `contacts.is_spam_reported = true` (`ContactManagerDatabase/updateIsReportedSpam`), `C31S.A01(...)`, sem checagem do resultado do RPC no fluxo visível |

---

## 4. Envelope da stanza e namespace

### 4.1 O nó de motivo é mesclado ao IQ (found)

Os RPCs não emitem dois `spam_list` irmãos. O `spam_list` principal (jid, mensagens) e o nó de motivo `C9E2` (um fragmento `<iq to="s.whatsapp.net" xmlns="spam"><spam_list .../></iq>`) são combinados com `C10340Uk.A04`, que mescla atributos e filhos de mesmo nome (valores de atributo conflitantes ou contagens de filhos conflitantes abortam a mesclagem). Resultado:

```xml
<iq type="set" id="<n..>" to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<reported>" spam_flow="<entry point>" wi_trace_id="<24 chars>">
    ...children...
  </spam_list>
</iq>
```

Evidência: os ctors de `C9EN` para 18-23 chamam `C9E2.A00(iq, reasonNode)` = `iq.A04(node)`; `C9E2` case 5 constrói `iq{to, xmlns="spam"} > spam_list{wi_trace_id, spam_flow}`; `C19380nJ.A00.getServer() = "s.whatsapp.net"`. O `id` do IQ vem de `MessageClientSmaxWrapper.A01()` (`n<hex counter>`, `C10140Tq.A0H`). Timeout de envio 32000 ms (`A0F(node, id, cont, type, 32000, ...)`); uma resposta nula (timeout/falha de entrega) vira `C216549Uq`.

Os tipos 0 e 1 definem `xmlns="w:g2"` e `to=<group>` literalmente; os tipos 18-23 constroem `<iq type="set">` e dependem da mesclagem para `to` e `xmlns`. O id de tipo passado ao sender é **98** (grupo, newsletter, evento) e **385** (denúncia aos admins).

### 4.2 Irmãos opcionais mesclados ao `spam_list`

| Nó/attr | Origem | Gate | Nível |
|-----------|--------|------|------|
| `spam_flow` | arg `flow` normalizado por `C9ZJ` | sempre | found |
| `wi_trace_id` (exatamente 24 chars) | `$wiTraceId` de `reportAsSpam$1` | opcional | found; origem do valor unknown |
| `is_known_chat` = `"true"`/`"false"` | `C33446EhE.A09` | flag **22256**; usuário: checagem de agenda de contatos, grupo: checagem de participação no grupo | found |
| filho `biz_opt_out` | `C33446EhE.A07` | existe registro de business discovery | found (ver 8.3) |

---

## 5. Stanzas por tipo

`from`/`to` de um item `<message>`: no caminho de usuário, o nó anônimo `C9E4` define `to=<jid>` quando a mensagem é de saída (`key.fromMe`) e `from=<jid>` caso contrário. As contagens são gates do builder (`AbstractC10350Ul.A07`).

### 5.1 Usuário (tipo 20)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<userJid>" spam_flow="chat" wi_trace_id="...">   <!-- jid: UserJid or interop jid (C99O) -->
    <message from|to="<userJid>" t id deleted_reason>              <!-- 0..210 items -->
      <raw v="2" local_message_type="<int>" mediatype="<enum>"><proto bytes></raw>
      <content_validation type="e2e_proto_message|mms_retry|plaintext_v3">
        <reporting_token v="<n>"><tag, min 6 bytes></reporting_token>
        <reporting_token_key><key, 16-32 bytes></reporting_token_key>
      </content_validation>
    </message>
    <call .../>                                                    <!-- 0..5 items, section 2.2 -->
    <extension_screen extension_id session_id t name entry_point>  <!-- 0..5, business Flows context (A0B), data child -->
    <biz_opt_out business_discovery_timestamp business_discovery_id business_discovery_entry_point/>
  </spam_list>
</iq>
```

O builder recebe três listas de itens com limites de 210 (mensagens), 5 (itens de chamada), 5 (itens de business-flow sem mensagem, `C33446EhE.A0B`: as últimas 5 entradas do store por business `messageless_flow_ids_per_business_<jid>`, nó `extension_screen`). O `jid` é validado apenas contra `UserJid` e `C99O`; sem `subject` neste caminho.

### 5.2 Grupo (tipo 19)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<groupJid>" source="<adderJid?>" subject="<group name>" spam_flow="group_info_report">
    <message from="<senderJid>" t id>...</message>     <!-- 0..210 -->
  </spam_list>
</iq>
```

- `source` é **o usuário que adicionou o denunciante ao grupo**, não o denunciante. É lido da mensagem de sistema local ("me joined") pelo SQL `GET_GROUP_ADDER_JID_SQL` (`C16100hT.A01`, `action_type` 12/124/144/127, `is_me_joined = 1`). Opcional. (found)
- `subject` é o nome de exibição do grupo vindo do registro de contato (`C06290Dn.A07().A00.A0b`; significado do campo inferred), string vazia `""` para grupos pai de comunidade ou quando não há registro (`Voip.REJECT_REASON_DECLINED` é `""`). Não é um motivo. Gate de comprimento 0..65536. (found)
- Uma quarta lista no ctor lança exceção (`getNode`) se não for vazia; o RPC passa uma lista vazia.

### 5.3 Newsletter (tipo 21) e post de status (tipo 22)

```xml
<spam_list jid="<newsletterJid>" subject="<channel name or ''>" spam_flow="newsletter_info_report">
  <message from="<newsletterJid>">...</message>        <!-- 0..65 -->
</spam_list>
<spam_list jid="<statusPosterJid>" spam_flow="status_post_report">
  <message from="<posterJid>">...</message>           <!-- 1..2 items, only the first selected status is passed -->
  <biz_opt_out .../>                                   <!-- optional -->
</spam_list>
```

O `subject` da newsletter = nome do canal (`C2130898y.A0j`), `""` se desconhecido (found). As denúncias de status usam suas próprias tabelas de token `status_reporting_info` / `status_reporting_content`.

### 5.4 Status de canal V2 (tipo 23)

```xml
<spam_list jid="<newsletterJid>" spam_flow="...">
  <status server_id="<99..2147476647>" t="<1577865600..4102473600>">...</status>
</spam_list>
```

O status é identificado por `server_id` + timestamp, sem conteúdo enviado. O conteúdo do filho `status` (`InterfaceC35700FdB`) não foi resolvido.

### 5.5 Evento (tipo 18)

`<spam_list event_id="<1..64 chars>" spam_flow="..."/>`, sem `wi_trace_id` (caminho `C9E2(String)` de um argumento). Mensagem aos admins (tipo 0): seção 9.1.

---

## 6. Conteúdo denunciado e tokens

### 6.1 O que é enviado (found)

`C33446EhE.A0A(fmsg, entryPoint)` constrói um item de mensagem por mensagem denunciada:

| Parte | Detalhe |
|------|--------|
| attrs de `<message>` | `t` (timestamp da mensagem, 0..2^53), `id` (stanza id), jid `from`/`to`, `deleted_reason` = `view_once_opened` / `view_once_expired` |
| `<raw v="2" local_message_type mediatype>` | protobuf `Message` reserializado (`C30628DTw` com `MessageContextInfo` `C30624DTs`); `local_message_type` = int do tipo interno da mensagem |
| `<content_validation>` | token + chave (6.2) |
| flags meta | `<edit v="1">` (editada), `<multicast/>` (flag de broadcast 64), `<url_number/>` (flag 4), `<url_text/>` (flag 2), template id, `hsm` tid, `iab reported_link`, `original_sender` / `group_history_sender`, variantes de pagamento `futureproof`/`request`/`send` (`pay`), `reported_push_name` |
| filho `<reporting>` | flag **5718**: construído a partir das linhas `reporting_info` da mensagem (`C23070uA.A03`), até 1000 entradas (`C31085Dfd` case 28); schema por entrada não totalmente lido |
| portadores alternativos | `<plaintext>`, `<enc type=msg|pkmsg|skmsg|media|text>`, `<reporting_content>` (`C31084Dfc`, `C31081DfZ`) |

`mediatype` (33 valores, found): `audio, avatar_sticker, buttons_response, catalog, cataloglink, collection, contact, contact_array, document, genai_sticker, gif, image, invite, list, list_response, livelocation, location, native_flow_response, order, product, productlink, product_list, ptt, ptv, sticker, sticker_pack, system, unknown, url, user_created_sticker, vcard, video, 1p_sticker`.

Mensagens de template OTP: o placeholder `<code>` nos títulos de botão é substituído pelo código real antes da serialização (`AbstractC32303E8u.A00`). View-once: quando a mensagem é view-once e já foi aberta/expirou e a origem não é `media_viewer` / `view_once_viewer`, `A06` é true e o bloco de serialização é pulado. Se o item então carrega um `raw` vazio ou ausente, é inferred (declaração não inicializada no decompile).

Arquivos de mídia não são reenviados por esta stanza; a mensagem serializada carrega as referências de mídia (inferred; nenhuma chamada de upload encontrada). A stanza contém o proto em texto puro e a chave juntos, então o servidor pode ler o conteúdo: nós **found**, legibilidade **inferred**.

### 6.2 Reporting token e chave (found)

```xml
<content_validation type="e2e_proto_message">          <!-- "mms_retry" when the stored token row has retry mode 1 -->
  <reporting_token v="<int>"><tag, >=6 bytes></reporting_token>
  <reporting_token_key><key, 16..32 bytes></reporting_token_key>
</content_validation>
```

Montado em `C33446EhE.A03` a partir da linha armazenada (`C34539Ez0`): bytes do token (`A05`), versão (`A02`), stanza id (`A03`), chave (`A07`). Se a chave estiver ausente, é rederivada: `C33364Efs.A06(chat, sender, stanzaId, messageSecret)` → nativo `WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)` (use case id **5**; chats que não são de usuário passam por variantes de `JniBridge`). Se a chave e um token de 6 bytes estiverem ambos ausentes/zerados, o cliente registra `ReportingToken/MissingFkAtReport` e usa uma chave de 32 bytes toda zerada. Um token ausente retorna `null` (`ReportingToken is null`, o item fica sem `content_validation`).

### 6.3 Ciclo de vida do token (found, salvo indicação)

| Estágio | Detalhe |
|-------|--------|
| Mensagem de saída | builder `C35241aW.A00(token16, v)` → `<reporting><reporting_token v="<n>">16 bytes</reporting_token></reporting>`. Token = primeiros 16 bytes de `HMAC-SHA256(key, canonicalContent)` (`C35241aW.A04`, `AbstractC38971i1.A00`). `canonicalContent` = proto da mensagem com filtragem de campos dependente de versão (`A07`, remove subcampos selecionados do campo 35; leitura inferred). Chamadores do builder não rastreados |
| Compartilhamento de histórico de grupo | `F6C` (`GhsReportingTokenMessageSendStanzaContributor`): para mensagens de tipo 117, `<reporting>` com um filho por entrada (attr `id`, filho `<reporting_token v>`) |
| Mensagem de entrada | filho de stanza `<reporting validation_policy?><reporting_tag>BYTES</reporting_tag><reporting_token v>BYTES</reporting_token></reporting>` parseado por `C34764F6h` / `C1S0`, flag **5718**; tag e token são ambos opcionais, tag obrigatória |
| Armazenamento | tabelas `reporting_info` (`reporting_tag`, `stanza_id`, `is_message_add_on`, `send_timestamp`, `receive_flow`) e `reporting_info_content` (`reporting_token`, `reporting_token_content`, `reporting_token_version`, `reporting_token_key`); `message_conditional_reveal.reporting_token_info` (blob); `group_history_share_reporting_info`; `status_reporting_info` |
| Histórico | `WebMessageInfo.reportingTokenInfo` campo **62** = `ReportingTokenInfo` (`DR0`): `reportingTag` **1** bytes, `reportingTagTimestamp` **2** uint64; flag **6578** |
| Limpeza | linhas `reporting_info*` apagadas quando `receive_timestamp` é mais antigo que um corte (`FP7` case 6); valor do corte não resolvido |
| Nó de validação alternativo | `<reporting_validation><reporting_tag id ts_s participant>bytes</reporting_tag></reporting_validation>` (`C31081DfZ`) |

Quem emite o `reporting_tag` e como o servidor verifica o token: lado servidor, unknown. O pareamento (tag na stanza, token+chave na denúncia) é inferred.

---

## 7. Pontos de entrada `spam_flow`

97 valores (found, `C9E2` case 5, ordem = ordem do array). O arg `flow` passa por `C9ZJ.A00`, que aceita **78** deles e, caso contrário, lança `IllegalArgumentException("Invalid BlockSpamReportOrigin value")`. Todos os seis wrappers de RPC o chamam, e `SpamReportRepo.A02` captura a exceção e retorna uma falha (erro no cliente, nenhuma stanza enviada). Os 78 são um subconjunto estrito dos 97. Os 19 valores rejeitados: `account_info, account_info_report_as_guest_user, block_dialog, call_log, call_spam_dialog_block, channel_status_report, chat_fmx_card_report_as_guest_user, chat_list_context_menu_block, chat_list_swipe_delete_block_upsell, chat_list_swipe_delete_report_upsell, ent_client, frx, group_chatlist_swipe_leave_report_upsell, group_info, guest_call_participant_report, guest_call_report, overflow_menu, overflow_menu_community_report, payment_transaction_report`. Provavelmente são origens exclusivas de bloqueio ou de outros RPCs (inferred). `channel_status_report` está no enum mas é rejeitado por `C9ZJ`; qual flow o chamador de status de canal passa é unknown.

| Superfície | Valores |
|---------|--------|
| Chat / 1:1 | `chat`, `message_menu`, `overflow_menu`, `overflow_menu_report`, `overflow_menu_block`, `block_dialog`, `block_header_chat`, `chat_list_block`, `chat_list_context_menu_block`, `chat_list_noinsub_block`, `chat_list_swipe_delete_block_upsell`, `chat_list_swipe_delete_report_upsell`, `triggered_block`, `notification_block`, `missed_call_notification_block`, `feedback_not_interested_block`, `user_controls_stop_block`, `media_viewer`, `view_once_viewer`, `account_info`, `account_info_block`, `account_info_report`, `account_info_report_as_guest_user`, `album_media_menu_report`, `iab_menu_report`, `extension_menu_report`, `comment_actions_bottom_sheet`, `payment_transaction_report` |
| Banners de spam | `1_1_spam_banner_block`, `1_1_spam_banner_report`, `1_1_old_spam_banner_block`, `one_to_one_spam_banner_block_server_flagged_suspicious`, `user_initiated_chat_suspicious_banner_block`, `user_initiated_chat_suspicious_banner_safety_tools_block`, `user_initiated_chat_suspicious_banner_safety_tools_report`, `dependant_chat_request_banner_decline_report_upsell`, `dependant_unknown_conversation_trust_signals_block` |
| Cards de segurança FMX | `chat_fmx_card_block`, `chat_fmx_card_block_suspicious`, `chat_fmx_card_block_server_flagged_suspicious`, `chat_fmx_card_report_as_guest_user`, `chat_fmx_card_safety_tools_block`, `..._block_suspicious`, `..._report`, `..._report_suspicious`, `user_initiated_chat_fmx_card_safety_tools_block`, `..._report`, `trust_question_bottomsheet_block_server_flagged_suspicious` |
| Alertas de golpe on-device | `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_bottom_sheet_block`, `odml_scam_alert_bottom_sheet_trust`, `odml_scam_alert_fmx_card_block`, `odml_scam_alert_fmx_card_trust`, `odml_scam_alert_suspicious_banner_block`, `odml_scam_alert_suspicious_banner_trust` |
| Grupo | `group_info`, `group_info_report`, `group_info_leave_report_upsell`, `group_spam_banner_exit`, `group_spam_banner_exit_group_history`, `group_spam_banner_report`, `left_group_spam_banner_report`, `group_safety_check_bottom_sheet`, `group_fmx_card_leave`, `group_fmx_card_leave_non_suspicious`, `group_chatlist_leave_report_upsell`, `group_chatlist_swipe_leave_report_upsell`, `group_overflow_menu_leave_report_upsell`, `community_home`, `community_announcement_group_suspicious_banner_exit_dialog`, `community_home_suspicious_banner_exit_dialog`, `overflow_menu_community_report` |
| Chamadas | `call_log`, `call_log_block`, `call_detail_overflow_report`, `call_detail_safety_tools_block`, `call_detail_safety_tools_report`, `call_spam_dialog_block`, `call_spam_dialog_report`, `guest_call_report`, `guest_call_participant_report` |
| Canais / status / eventos | `newsletter_info_report`, `newsletter_question_response_report`, `channel_status_report`, `status_post_report`, `status_question_answer`, `wamo_channel_report`, `event_home_report`, `event_info_report` |
| Business | `biz_account_info_block`, `biz_block_header_chat`, `biz_block_list`, `biz_call_log_block`, `biz_overflow_menu_block`, `biz_spam_banner_block`, `ent_client`, `frx` |

A escolha `*_suspicious` vs simples para os cards FMX é feita em `C230769yA.A05` a partir de `A0D(userJid)` (contato conhecido ou não); esse predicado é inferred como checagem de agenda de contatos. As variantes `server_flagged` são escolhidas pelo tipo de card; de onde vem a flag do servidor é unknown.

`wi_trace_id`: atributo opcional de 24 chars, repassado do chamador; seu gerador não foi encontrado (unknown). Também é um campo do WAM `wam_spam_report_perf` (11.3).

---

## 8. Bloqueio, motivos e contexto de business

### 8.1 IQ de bloqueio (found, área de `C34631Yx.A0M`)

```xml
<iq to="s.whatsapp.net" id="<id>" type="set" xmlns="blocklist">
  <item action="block|unblock" jid="<chat jid>" dhash="<list hash?>" pn_jid|username|display_name|unknown_identifier="...">
    <biz_opt_out first_message="true|false|none" reason="<code>" reason_description="<text>"
                 entry_point="<flow>" business_discovery_entry_point business_discovery_timestamp business_discovery_id/>
  </item>
  <entry_point source="<flow>"/>
</iq>
```

`biz_opt_out` e `entry_point` só são emitidos para `action="block"`. O `jid` é escolhido entre as formas PN e LID por uma checagem de configuração (ramo `zA02`; regra exata não totalmente lida); em um bloqueio, o identificador extra é um entre `pn_jid` / `username` / `display_name` / `unknown_identifier="true"`. Timeout 20000 ms. Pontos de entrada que começam com `odml_scam_alert_*` são reescritos para `1_1_spam_banner_block` (`odml_scam_alert_fmx_card_block` → `chat_fmx_card_block`). Chats PSA usam um IQ diferente (`xmlns="w:comms:chat"`, `<blocking action>`). Fetch: `type="get"`, `<item dhash>` opcional.

### 8.2 Motivos de bloqueio (found)

String hardcoded → int local em `AbstractC227579sl.A00`: `no_longer_needed`/`no_longer_interested` = 1, `no_sign_up` = 2, `spam` = 3, `offensive_messages` = 4, `otp_did_not_request` = 5, `scam_or_fraud` = 6, outro = 0. `RunnableC40792Hpk` mapeia as mesmas strings para um segundo conjunto de códigos. Esses ints alimentam chamadas de log locais; se chegam a um servidor é unknown.

Sheet de bloqueio de business (`C24126Ab7`): mapa de motivos do servidor se não estiver vazio, senão `no_longer_needed, no_sign_up, spam, scam_or_fraud, other`; chats de template OTP: `no_longer_interested, otp_did_not_request, other`.

### 8.3 Contexto de business discovery (found)

`C33446EhE.A07` lê o registro de business discovery do JID denunciado (store `LA8`): timestamp, id, ponto de entrada. Enum de ponto de entrada (18 + `unknown`): `biz_profile, broadcast_list_context_menu, catalog_link, click_to_chat_link, contact_card, contact_search, ctwa, global_search_new_chat, group_participant_list, message_short_link, other_qbm, otp_qbm, phone_number_hyperlink, product_link, promotional_qbm, qr_code, status, transactional_qbm`. É anexado tanto às denúncias (`biz_opt_out` sob `spam_list`) quanto aos bloqueios. Esses são os únicos sinais de como-este-chat-começou encontrados no cliente.

### 8.4 Listas de motivos de denúncia (found)

Somente anúncios de business têm uma lista selecionável. `ReportReasonListFragment` começa vazio e é preenchido a partir de `<iq xmlns="w:biz" type="get"><mobile_config name="biz_report_reasons" v="1" report_type="status_ad|business_user"/></iq>` (resposta `mobile_config` > `list` com `name`, `v`, `country`). Enum de fallback hardcoded (`EnumC37888GeT`): `scam_or_fraud`, `pretending_impersonation`, `illegal_dangerous`, `inappropriate_hateful_violent`, `dont_like_ad`. Quando o fallback é usado: inferred como lista do servidor indisponível. Não há seletor de motivo para denúncias comuns de usuário/grupo/mensagem; o único "motivo" na rede é `spam_flow`.

---

## 9. Denúncia aos admins do grupo

### 9.1 Envio e consulta (found, `RtaXmppClient`)

```xml
<!-- reportMessageToAdmin, type 0, smax 385 -->
<iq to="<groupJid>" type="set" xmlns="w:g2" id><reports><report message_id="<stanza id>"/></reports></iq>

<!-- getReportedMessages, admin side -->
<iq to="<groupJid>" type="get" xmlns="w:g2" id><reports/></iq>
<!-- response: report{message_id} > reporter{jid, timestamp} x1..19999 -->
```

Nenhum conteúdo, token ou `spam_flow` é enviado; apenas o id da mensagem. Os erros só registram em log `Rta::<op>/onError: <code>` ou `/onDeliveryFailure: Network Failure`.

### 9.2 Alternância de denúncia por membros (found)

`$t=1`: `<iq to="<groupJid>" type="set" xmlns="w:g2"><allow_admin_reports/></iq>` (habilitar) ou `<not_allow_admin_reports/>` (desabilitar), smax 384. Os nós são filhos diretos do IQ, não embrulhados em um nó `group`. O builder aceita até quatro nós de configuração irmãos em um IQ.

---

## 10. Resposta do servidor e diálogos de conclusão

### 10.1 Resposta (found)

Sucesso (`type=result`): filho `report` com atributo `id` (máx. 20 chars) → `C213959Ch.A01` → devolvido à UI como o report id. Erros (`<error code text>`), por classe de resposta:

| Código | Nome | Individual | Grupo | Newsletter | Status | Status V2 | Evento |
|------|------|------------|-------|------------|--------|-----------|-------|
| 400 | `bad-request` | x | x | x | x | x | x |
| 403 | `forbidden` | x | | | x | x | |
| 429 | `rate-overlimit` | x | | | x | x | |
| 500 | `internal-server-error` | x | x | x | x | x | x |
| 501 | `feature-not-implemented` | x | x | | | | x |
| 548 | `report-token-validation-fail` | x | x | | x | | x |

### 10.2 Diálogos de conclusão

`H2U` decide a partir do report id e dos gates, e então `C5BD` constrói o fragment (`arg_report_id`, `arg_is_ad_report`):

| Gate | Diálogo |
|------|--------|
| flag **25818**, chat de usuário, mensagem presente | `NciiCompletionDialogFragment` |
| flag **6145** | `DsaCompletionDialogFragment` (UE) |
| flag **14249** | `UkOsaCompletionDialogFragment` |
| flags **12987** / **12990** | `AustraliaOsaCompletionDialogFragment` |

Todos, exceto NCII, exigem um report id não nulo; sem id, sem diálogo.

---

## 11. Sinais de abuso no cliente

### 11.1 O que o cliente envia além do conteúdo (found)

Pontos de entrada com `*_server_flagged_suspicious` significam que o card foi exibido para um chat marcado por um sinal diferente da checagem local de contato; como o cliente descobre essa flag é unknown. Enviados nas denúncias: `is_known_chat`, `biz_opt_out` (como o chat de business começou), itens de chamada (duração, quem encerrou, terminate reason), contexto `extension_screen` dos Flows de business, `source` (quem me adicionou ao grupo), `reported_push_name`, flags de encaminhamento/broadcast/URL em cada mensagem, flag de editada, estado view-once, ponto de entrada, `wi_trace_id` opcional.

### 11.2 Detecção de golpes on-device (found, escopo limitado)

`com.whatsapp.integrityai` executa um conjunto de modelos baixado (`scam_detection`) no dispositivo via ExecuTorch (`ScamDetectorImpl`, `EmbeddingProviderImpl`, `InputFeatureProviderImpl`; features `mostRecentSenderScore`, `isCountryMismatch`). Os resultados acionam banners/sheets de aviso e os pontos de entrada `odml_scam_alert_*` acima. Um registro JSON local de varredura (`outcome`, `inputs`, `model_info`, `verification`) é gravado em um `FileStash` quando `integrity_warning_report_enabled` (`C57375Pog`). Nenhum upload desse registro foi encontrado (unknown). É independente da stanza de denúncia `spam`.

### 11.3 Telemetria (found)

WAM `wam_spam_report_perf` (`C97R`, id 6310): `dedup_key`, `report_attempt_count`, `report_duration_ms`, `report_error_code`, `report_spam_flow`, `report_status`, `wi_trace_id`. Mapeamento do código de erro em `reportAsSpam$1`: cancelamento -4, timeout/sem resposta -1, outra exceção -3, erro de protocolo = código de erro do IQ.

---

## 12. Baileys

O pacote `baron-baileys-v2` não tem API de denúncia. Os formatos abaixo vêm dos nós found e não foram tested.

```ts
// report to group admins (smallest, no token needed)
await sock.query({
  tag: 'iq',
  attrs: { to: groupJid, type: 'set', xmlns: 'w:g2' },
  content: [{ tag: 'reports', attrs: {}, content: [
    { tag: 'report', attrs: { message_id: stanzaId } } ] }]
})
```

Os formatos de denúncia de usuário/grupo/canal seguem a seção 5 (um único `spam_list` mesclado, `xmlns: 'spam'`, `to: 's.whatsapp.net'`).

| Por que falha (tudo inferred) | Causa | Correção |
|--------------|-------|-----|
| erro 548 ou no-op silencioso | sem reporting token/chave válidos: o Baileys descarta o filho `<reporting>` das mensagens de entrada e nunca deriva a chave | parsear `reporting_tag`/`reporting_token` no recebimento, armazenar por mensagem, derivar a chave de `messageSecret` (use case 5) no momento da denúncia |
| 400 | `jid` de classe errada (deve ser user/interop para o tipo 20), contagem de itens acima dos limites, `spam_flow` de tipo errado | usar as strings de `spam_flow` da seção 7; ficar abaixo de 210 / 5 itens |
| IQ rejeitado | dois `spam_list` irmãos (motivo enviado como segundo nó) em vez de um nó mesclado | enviar um `spam_list` com todos os atributos |

Tanto `wi_trace_id` quanto `is_known_chat` são opcionais no builder; se o servidor aceita denúncias com tokens fabricados é unknown.

---

## 13. Casos de erro

| Sintoma | Causa | Nível |
|---------|-------|------|
| toast `str3bf8`, nada enviado | `C9ZJ` rejeitou o valor de `flow` (`Invalid BlockSpamReportOrigin value`) | found |
| falha `unrecognized jid` | o JID do chat não é user/group/status/newsletter | found |
| denúncia "falha" sem toast | erro 548 do servidor: `C9ZI.A00` retorna o mesmo objeto de resultado não-erro do caminho de bot | found |
| toast genérico de falha | 400/403/429/500/501, ou timeout (32 s) → `C216549Uq` | found |
| conteúdo da denúncia ausente | view-once aberta/expirada e origem não é um viewer; mensagem sem token armazenado | found / inferred |
| estado local diz denunciado, servidor rejeitou | `is_spam_reported` gravado após o RPC sem checagem visível do resultado | found (fluxo), inferred (consequência) |

---

## 14. Distinções principais

| Não confundir | Com |
|----------------|------------------|
| `spam_list@source` | o denunciante. É o usuário que adicionou o denunciante ao grupo |
| `spam_list@subject` (grupo, canal) | um motivo. É o nome do grupo/canal |
| `spam_flow` | um motivo de denúncia. É a superfície de UI que disparou a denúncia (97 valores) |
| denúncia (xmlns `spam`) | bloqueio (xmlns `blocklist`), denúncia aos admins (xmlns `w:g2`), opt-out de marketing (xmlns `optoutlist`, `C31105Dfx`, não analisado mais a fundo) |
| dois nós `spam_list` | um `spam_list` mesclado (atributos e filhos combinados) |
| spam de chamada | spam de evento. Denúncias de chamada são o tipo 20 com um item `call`; o tipo 18 é `event_id` |
| `reporting_tag` (emitido pelo servidor, armazenado no recebimento) | `reporting_token` (HMAC de 16 bytes, enviado com mensagens de saída e enviado nas denúncias) e `reporting_token_key` (derivada, enviada) |
| denúncia aos admins | denúncia ao WhatsApp. A denúncia aos admins envia só `message_id`; sem conteúdo, sem token |
| `wi_trace_id` (trace id enviado pelo cliente) | o report id, que o servidor devolve em `<report id>` |
| `report_block` | um valor de rede. É uma string de analytics/toast do cliente; o bloqueio é um IQ próprio |
| alternância `allow_admin_reports` (`$t=1`) | mensagem de denúncia aos admins (`$t=0`) |

---

## 15. Fluxo ponta a ponta

```
[User]                  [Client]                                        [WhatsApp server]
  │ Report / Block+Report    │                                               │
  ├────────────────────────▶│ ReportSpamDialogFragment(flow = spam_flow)     │
  │ confirm (+block/leave)   │ reportAsSpam$1                                │
  │                          │  bot chat ──▶ BotMessageHelper/reportUgc      │
  │                          │ SpamReportRepo.A02: route by JID class        │
  │                          │  C9ZJ(flow) ──✗ IllegalArgumentException      │
  │                          │  no message ──▶ last 5 messages from DB       │
  │                          │ serialize msgs (EhE) + token + key,           │
  │                          │ is_known_chat, biz_opt_out, call items        │
  │                          │ C9EN + C9E2 merged into ONE spam_list         │
  │                          │ ── iq set xmlns=spam to=s.whatsapp.net ─────▶│
  │                          │                                   verify token│
  │                          │◀── result <report id> | error 400/403/429/    │
  │                          │    500/501/548 (548 treated as success)       │
  │                          │ WAM wam_spam_report_perf                      │
  │                          │ contacts.is_spam_reported = 1                 │
  │                          │ extra action:                                 │
  │                          │  user ── iq set xmlns=blocklist (block) ────▶│
  │                          │  group ─ leave   channel ─ hide + exit        │
  │◀─ completion dialog (DSA / UK OSA / AU OSA / NCII; needs report id)      │
  │                                                                          │
  │ member: iq set xmlns=w:g2 to=group reports>report{message_id} ──────────▶│
  │ admin : iq get xmlns=w:g2 to=group <reports/> ◀── report > reporter      │
```

---

## 16. Unknown

| Item | Motivo |
|------|--------|
| Verificação de token no servidor, emissão do `reporting_tag`, como `server_flagged` é decidido | lógica do servidor, não está no APK |
| Origem do `wi_trace_id` | gerador não localizado no decompile |
| Gatilho de UI da denúncia de evento, formato na rede da denúncia de chat de bot | apenas chamadores em lambda (`AYs`, `Aaa`) / `reportUgc` não rastreado além de `C33437Eh4` |
| String de flow que o chamador da denúncia de status de canal passa | `channel_status_report` é rejeitado por `C9ZJ` |
| Corte da limpeza de `reporting_info*` | chamador de `FP7` case 6 não rastreado |
| Upload do registro local de varredura de golpes | nenhum consumidor encontrado |
| Schema por entrada do filho `reporting` por mensagem e finalidade da chamada da flag 20085 | construído a partir de linhas do DB, lógica do consumidor não lida |
| Aceitação real de qualquer stanza da seção 12 | nenhum tráfego foi capturado |
