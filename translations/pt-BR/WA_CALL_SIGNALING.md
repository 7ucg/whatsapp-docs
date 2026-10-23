<!-- src-sha1: 7c179c130d5822c6103aa9a9ae2e6751ec1b0bd8 -->
# WhatsApp Sinalização de Chamadas — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-24
**Escopo:** sinalização de chamadas de voz/vídeo no Android: envelope `<call>` e acks, stanzas de ação (offer, accept, preaccept, reject, terminate, transport, relaylatency, enc_rekey, mute_v2, group_info, group_update, lobby, link_*, waiting_room_*, bcall), payload do offer (audio / video / capability / encopt / net), chave da chamada e sua criptografia Signal, rekey (v2 / v3), derivação da chave de mídia, seleção de relay e transporte, ICE / STUN / DTLS / SRTP versus o caminho de mídia específico do WhatsApp, chamadas em grupo, links de chamada e chamadas agendadas, registro de chamadas e mensagens bcall, códigos de nack do offer, comportamento de reject e terminate, feature flags, comparação com o Baileys

---

## 1. O que é (tecnicamente)

A sinalização de chamadas é um conjunto de stanzas `<call>` na conexão chatd normal (ver [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Cada stanza carrega exatamente um filho de ação. A camada Java não monta nem interpreta stanzas de chamada: um motor VoIP nativo faz isso, e o Java apenas (a) embrulha os filhos de saída em `<call>`, (b) criptografa a chave da chamada com Signal para cada dispositivo, (c) entrega as stanzas de entrada ao motor, (d) reage aos eventos do motor. A mídia (tráfego tipo RTP para relays, ICE, DTLS, SRTP) não é sinalização e roda em sockets UDP/TCP pertencentes ao motor. Todas as afirmações vêm de análise estática; nada foi capturado na rede. Tiers: **found** = lido em Java ou em strings nativas, **inferred** = deduzido, **unknown** = não resolvido.

| Camada | Nome na 2.26.41.6 | Função |
|--------|-------------------|--------|
| Fachada JNI | `Voip` / `VoipNativeImpl` (`com.whatsapp.calling.voipcalling`) | 148 métodos nativos (`startCall`, `acceptCall`, `rejectCall`, `nativeHandleIncomingSignalingXmpp`, ...) |
| Hook de saída | `OutgoingSignalingHandler` implementa `SignalingXmppCallback.sendCallStanza(Jid, callId, VoipStanzaChildNode)` | do motor para o Java; tratamento por tag, criptografia da chave da chamada |
| Escritor do envelope | `CIX` (fila), `C27410BtV` (stanza de chamada), caso 206 da writer-thread em `HandlerThreadC21920sG` | monta `<call to id>` |
| Handler de entrada | `C40641lA` (`CallStanzaHandler`), `BQU` (stanza de chamada interpretada), `C83` (decrypt), `C28120CKj` / `RunnableC29343CoU` (despacho para o motor) | interpreta o envelope, decifra `<enc>`, alimenta o motor |
| Eventos do motor | `VoipEventCallback`, `VoiceServiceEventCallback` (116 callbacks) | do motor para UI / estado |
| Callback de cripto | `DefaultCryptoCallback`, `SignalIdentityCryptoCallback` (`CryptoCallback`) | HKDF / HMAC / aleatório / assinaturas Ed para o motor |
| Sinalização HTTP | `VoiceTeeHttpSignalingHandler` (`SignalingHttpCallback`) | portador de sinalização alternativo, requisição TEE |
| Motor nativo | `libwhatsapp.so` (extraída do arquivo superpack `libs.so`; exporta `Java_com_whatsapp_calling_voipcalling_Voip_*`) | serializadores / desserializadores de stanza, máquina de estados da chamada, transporte, mídia |

Pontos que definem o restante do relatório:

- A gramática das stanzas fica no código nativo: serializadores `serialize_*` (C/C++) e uma crate Rust `call_control` (caminhos-fonte `xplat/wa-voip/rust/call_control/src/stanza_deserializer/...` em suas strings de panic) para a interpretação de entrada. A biblioteca voip não pôde ser decompilada; toda afirmação nativa se apoia apenas em strings e nomes exportados (strings found, significado inferred).
- O Java é uma camada fina, e por isso o conjunto de tags visto no Java (10 tags em `sendCallStanza`) é muito menor que o conjunto que o motor entende (seção 4).
- A chave da chamada é gerada e usada pelo motor; o Java a criptografa com a sessão Signal pairwise comum (seção 6). O mesmo código HKDF de que o motor precisa é um callback Java (seção 7).
- O caminho de mídia específico do WhatsApp (relay allocate/bind, pacotes "WARP", SRTP hop-by-hop, SFrame para chamadas em grupo) é distinto do caminho ICE/DTLS estilo WebRTC, que existe como modo "web_p2p" (seção 8).

---

## 2. Interface Java / nativa

Callbacks registrados na inicialização (found): `SignalingXmppCallback.sendCallStanza(to, callId, node)` (motor para Java, um filho de chamada); `CryptoCallback` (`generateE2EKeysV2`, `getSecureSsrc`, `hkdfSha256`, `hmacSha256`, `generateRandomBytes`; `SignalIdentityCryptoCallback` acrescenta `signWithIdentityKey` com assinatura de 64 bytes e `verifySignature` com chave de 32 bytes); `SignalingHttpCallback` (`sendMsg(callId, bytes, requestType)`, `cancelMsg`; tipos voice session 0, codec avatar 1); `VoipEventCallback` (seção 13). `VoipStanzaChildNode` é a árvore visível via JNI (tag, atributos, filhos, dados); o Java a converte de e para o nó chatd, cuja codificação binária está descrita em [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) seção 8.

| Entrada JNI (found) | Alimentada por | Notas |
|---------------------|----------------|-------|
| `nativeParseXmppOffer(CallOfferInfo[], ...)` | `preprocess_call_offer` (`AbstractC24816AmW`) | interpreta um offer sem iniciar uma chamada; `CallOfferInfo`: callId, fromJid, groupJid, callLinkToken, isVideoCall, isAudioChat, isJoinableCall, isOfferExpired, isCallEnded, silenceReason, groupPhash, participantHash, callGroupInfo |
| `nativeHandleIncomingXmppOffer` | `C28120CKj` | inicia o tratamento da chamada de entrada |
| `nativeHandleIncomingSignalingXmpp` / `...Ack(from, type, errorCode, children, ..)` / `...Receipt` | `RunnableC29343CoU` (mensagem 192) | toda ação que não é offer, acks das próprias stanzas (retorno 70004 é registrado como ack corrompido), recibos de chamada |
| `peekIncomingOffer`, `handleIncomingTerminatePush` | caminho de push | decisão pré-toque, terminate entregue por push |
| `handleIncomingSignalingHttp(callId, bytes, ..)` | resposta HTTP TEE | portador alternativo (11.3) |

---

## 3. Envelope, acks, recibos

### 3.1 `<call>` de saída (found, `HandlerThreadC21920sG` caso 206)

```
<call to="<jid>" id="<stanza id>">
  <ACTION .../>                      exactly one child
</call>
```

`to` deve passar por `C0DZ.A0R` (usuário, dispositivo e alguns outros tipos de JID; caso contrário `C27410BtV` lança `CallStanza:Wrong jid type`). O id da stanza vem do gerador de ids compartilhado. Linha de log `WriterThread/write/call-stanza-<tag>`.

### 3.2 `<call>` de entrada (found, `C40641lA`)

| Atributo | Tratamento |
|----------|------------|
| `from` | deve ser um JID válido, senão `CallStanza from invalid jid`; um JID de usuário é mapeado para seu dispositivo primário |
| `id` | id da stanza, usado para o ack |
| `t` | segundos, multiplicados por 1000 |
| `e` | segundos inteiros, multiplicados por 1000 e passados ao motor junto com `t` (significado exato não resolvido; inferred: idade / expiração do offer como entrada) |
| `offline` | inteiro; a presença marca entrega a partir da fila offline |
| `notify`, `platform`, `version` | repassados (push name do chamador, plataforma, versão do app) |
| `participant` | JID do dispositivo do remetente em contextos de grupo; um valor malformado recorre a `from` |
| `sender_lid` | lido quando `from` é um JID de domínio LID |
| filho `call-creator` | JID de dispositivo (obrigatório para a lógica que não é offer) |
| filho `call-id` | obrigatório; exceto as tags `reminder` e `bcall_*`, que recebem um call id vazio |
| outros atributos | `caller_pn` (JID de dispositivo com número de telefone), `username`, `caller_country_code`; lidos apenas quando o criador é LID e a tag não é `offer` |

Se `to` e `call-creator` estiverem em domínios de endereço diferentes (um LID, um número de telefone), o cliente registra `CallStanzaHandler/call-mixed-domain/...` e reporta a métrica `CallMixedDomainStanza`, e então continua (found). Domínios mistos são tolerados, não rejeitados.

### 3.3 Acks

| Caso | Comportamento (found) |
|------|-----------------------|
| tag fora de {offer, accept, reject, enc_rekey, terminate} | o Java envia um ack imediatamente: `<ack class="call" type="<tag>" id to [participant]/>` (`AbstractC47181wT.A01`) |
| tag nesse conjunto | sem ack imediato do Java; o nó segue por um caminho separado de ack pendente (`C36591ch.A0G`); semântica não resolvida |
| ack de uma stanza própria | `nativeHandleIncomingSignalingXmppAck(from, type, errorCode, children, ...)`. Tipos de ack vistos no Java: offer (carrega dados de relay, seção 8), accept, link_join, link_query, lobby; o nativo também trata link_create, link_edit, remove, remove_user, heartbeat, screen_share, add_extension, remove_extension, relaylatency, estado de vídeo, waiting_room_* |
| ack de offer com erro 435 | ação extra agendada após o ack (finalidade não resolvida) |
| entrega de offer / accept | o Java aguarda o ack de entrega do chatd com timeout (flags 9257, 9431); no timeout a stanza é descartada e registrada como `Call stanza delivery timed out` |

### 3.4 Tokens de dicionário (found, `AbstractC40911lb`)

Byte único (`A00`): `call` 97, `call-id` 101, `call-creator` 68, `terminate` 208, `relaylatency` 70, `video` 86, `audio` 158, `capability` 177, `device-identity` 227, `privacy` 223, `te` 212, `te2` 198, `token` 194, `key` 155, `participant` 5, `user` 14, `remove` 172, `notify` 24, `registration` 170, `attribute_padding` 229, `relay_id` 130, `token_id` 143. Dicionário secundário 0 (`A01[0]`): `offer` 28, `accept` 97, `preaccept` 18, `transport` 44, `mute_v2` 253, `group_info` 170, `group_update` 99, `net` 103, `medium` 36, `encopt` 21, `keygen` 26, `voip_settings` 10, `relay` 116, `joinable` 75, `heartbeat` 6, `transaction-id` 62, `uuid` 132, `self_pid` 71, `peer_pid` 76, `metadata` 118, `uncompressed` 20, `rate` 29, `dec` 73, `screen_width` 5, `reason` 46. Secundário 1: `reject` 0, `enc_rekey` 205, `e` 235.

Fora de qualquer dicionário desta build (strings simples no fio): `lobby`, `flowcontrol`, `screen_share`, `link_*`, `peer_state`, `interruption`, `reminder`, `raise_hand`, `waiting_room_*`, `hbh_key`, `auth_token`, `lightweight`, `silence`, `scheduled-id`, `group-jid`, `link-token`, `caller_pn` e `enc`.

---

## 4. Taxonomia de ações

Tags de entrada que o desserializador nativo despacha (found, lista de strings em `call_control`): `offer`, `accept`, `preaccept`, `reject`, `terminate`, `transport`, `relaylatency`, `enc_rekey`, `notify`, `flowcontrol`, `interruption`, `group_update`, `mute_v2`, `screen_share`, `raise_hand`, `reconfigure_bot`, `user_action`, `ready`, `relay_info_update`, `tos`, `screen`, `switchable`, `add_extension`, `waiting_room_update`, mais `receipt`. Acks interpretados: offer, accept, estado de vídeo, relaylatency, link_create / edit / query / join, lobby, heartbeat, remove, remove_user, screen_share, add_extension, remove_extension, waiting_room toggle / admit / deny / leave.

| Tag | Direção (found) | Finalidade |
|-----|-----------------|------------|
| `offer` | saída / entrada | iniciar uma chamada (seção 5); na entrada: também offers de chamadas já encerradas com `is_call_ended` e `terminate_hint` |
| `preaccept` | saída / entrada | dispositivo do destinatário está tocando / pronto; estado do motor `PRE_ACCEPT_RECEIVED`, evento `preacceptReceived` |
| `accept` | saída / entrada | destinatário aceita; carrega parâmetros de mídia e um certificado (strings nativas `error parse voip params for accept`, `error parsing certificate for accept`) |
| `reject` | saída / entrada | destinatário recusa; strings de motivo na seção 14.2 |
| `terminate` | saída / entrada | encerrar a chamada; transaction id e `call_summary` (seção 14.3) |
| `transport` | saída / entrada | candidatos, credenciais ICE, certificado, saúde (seção 8.5) |
| `relaylatency` | saída / entrada | latências de relay medidas (seção 8.4); tem ack próprio |
| `enc_rekey` | saída / entrada | recompartilhamento da chave da chamada (seção 6.4) |
| `video` (estado) | saída / entrada | vídeo ligado / desligado / upgrade; valores `kVideoState*` (seção 13); o ack carrega informações de relay |
| `notify`, `peer_state`, `flowcontrol`, `interruption`, `ready`, `heartbeat` | saída / entrada | estado durante a chamada: avisos do peer, saúde da rede, controle de fluxo, interrupções, heartbeat de grupo |
| `mute_v2`, `raise_hand`, `user_action`, `tos`, `reconfigure_bot` | saída / entrada | pedido de mute em chamadas em grupo, levantar a mão, ações do usuário, TOS de chamada em grupo, reconfiguração de bot (atributo `req_id`) |
| `group_info`, `group_update` | entrada (filho de offer / ack / update) | roster (seção 9) |
| `lobby` | saída / entrada | consulta / estado do lobby da chamada em grupo; seu ack carrega group info |
| `screen`, `screen_share`, `switchable` | saída / entrada | estado do compartilhamento de tela; troca de dispositivo (`switch_info`, `root_call_id`, `root_call_creator`, `peer_active_device`) |
| `add_extension`, `remove_extension` | saída / entrada | adicionar um endpoint de mídia ("extension") a uma chamada (seção 9.4) |
| `remove`, `remove_user`, `cancel_offer` | saída | remover participantes; cancelar um offer para participantes escolhidos |
| `link_create`, `link_edit`, `link_query`, `link_join` | saída | links de chamada (seção 10) |
| `waiting_room_toggle`, `_admit`, `_deny`, `_leave`, `_update` | saída / entrada | sala de espera de chamada por link (seção 10.3) |
| `reminder`, `bcall_*` | entrada | lembretes do servidor; família de chamadas business (seção 11) |
| `dtmf`, `duration`, `connect_stat`, `group_call_duration`, `group_call_tos_accepted` | saída | serializadores presentes no motor |

Tags visíveis no Java em `sendCallStanza` (found): `offer`, `accept`, `reject`, `terminate`, `video`, `enc_rekey`, `lobby`, `link_join`, `link_query`, `link_create`; toda outra tag segue o caminho de envio padrão.

Tabela numérica de ids de mensagem (85 tipos), divisão por mecanismo (filho / ack / recibo / interno) e comprimentos fixos de cabeçalho: não encontrados nesta build. O motor expõe tags e serializadores por tag, não um enum de ids visível nas strings. Trate qualquer tabela de ids como unknown para Android.

---

## 5. Offer

### 5.1 Montagem e envio (found)

`startCall(...)` faz o motor emitir `sendCallStanza(peer, callId, offerNode)`. O Java:

1. `sendOfferStanza` armazena o id da stanza (`outgoingCallOfferKey`), espera enquanto houver um job de pre-key pendente para qualquer dispositivo de destino e então criptografa a chave da chamada por dispositivo em um worker (`getBulkEncryptedE2EKeys`, seção 6.1).
2. O resultado é escrito no formato novo (`<destination><to jid><enc/></to>...</destination>`, via `AbstractC33466EhY.A08`) ou no formato antigo (um único filho `<enc>`, válido para um só dispositivo; `cannot have multiple encrypted messages in old format!`).
3. Se algum dispositivo recebeu um `pkmsg`, `<device-identity>` (bytes de `adv_signed_identity` das preferências do companion) é anexado; isso só acontece quando o próprio dispositivo passa por `BRD()` (id de registro do dispositivo diferente de zero, ou seja, um companion; inferred).
4. `CIX.A02` enfileira a stanza `<call>`; a flag **9257** (ms) limita a espera pela entrega.
5. Após o envio, um IQ de ping da chamada é agendado (flag **30890**, atraso **30891** ms padrão 3000, tentativas **32651**); se a conexão estiver caída o cliente reconecta, a menos que a chamada já não esteja no estado `CALLING`.
6. Se os destinos não puderem ser criptografados, o offer é mantido como `pendingCallOfferStanza` e enviado depois (`maybeSendPendingOffer` quando um job de pre-key termina, `sendPendingCallOfferStanza` no terminate). `preSendTerminate` remove da fila de retry um offer sem ack antes de um terminate sair.

### 5.2 Filhos e atributos

| Elemento | Origem | Atributos / conteúdo |
|----------|--------|----------------------|
| `<offer>` | envio | `call-id`, `call-creator` (JID de dispositivo); recebimento: `caller_pn`, `username`, `caller_country_code`, `group-jid`, `scheduled-id`, `joinable`, `lightweight` (`1` = toque de grupo lightweight / somente áudio), `rering_ts`, `is_call_ended`, `type` |
| `<audio>` (repete) | envio | `enc` (codec), `rate` (taxa de amostragem); `enc` e `rate` são tokens de dicionário |
| `<video>` | envio | `enc`, `dec`, `device_orientation`, `screen_width`, `screen_height`; strings de valor vistas no motor: `h.264`, `vp8`, `vp8/h.264`; o atributo `fps` também aparece como string (atributo de vídeo inferred) |
| `<net>` | envio | `medium` (tipo de rede), depois `health_status` em transport |
| `<capability>` | envio | `ver` + máscara de bits opaca (`pjmedia_voip_capabilities_*`: versão, `bit_mask_length`); `vid_dec` por dispositivo é uma lista de strings dos codecs de vídeo decodificáveis (`vid_codec_capability_str_to_bitmask`) |
| `<encopt>` | envio | `keygen` = versão de geração de chave; o motor rejeita outros valores (`Unsupported keygen ver`); existem as versões 2 e 3 (seção 6.4) |
| `<destination>` / `<to jid>` / `<enc>` | envio | chave da chamada criptografada por dispositivo (seção 6.1); `<to>` pode carregar `peer_recipient_lid`, `peer_recipient_pn`, `peer_recipient_username`, `eph_setting` |
| `<tctoken>` | envio | dentro de `<to>`, no máximo uma vez por usuário, quando a flag **20605** está ligada e menos de **20606** usuários já carregam um; mesma família de token de [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `<device-identity>` | envio | bytes da identidade assinada ADV, ver 5.1 passo 3 |
| `<privacy>` | recebimento | token de privacidade (nome do token presente no dicionário); conteúdo não rastreado |
| `<relay>` | recebimento / ack | lista de relays (seção 8) |
| `<voip_settings>` | recebimento / ack | parâmetros do motor fornecidos pelo servidor; atributo `uncompressed`; payloads comprimidos rejeitados em um caminho (`unexpected compressed voip params`) e `zlib inflate` está linkado (formato de compressão inferred) |
| `<metadata>` | recebimento | atributos de bucket de teste A/B do peer (`peer_abtest_bucket`, `peer_abtest_bucket_id_list`) |
| `<silence reason>` | recebimento | o offer é silencioso (sem toque); `BQU.A02`; inteiros de motivo `kOfferSilenceReason*` (seção 13) |
| `<group_info>` | recebimento | roster de uma chamada em grupo (seção 9) |
| `<terminate_hint>` / `<call_summary>` | recebimento | um offer para uma chamada que já terminou (`is_call_ended=1`): `terminate_reason`, transaction id, resumo |
| `<link_info>`, `<waiting_room>`, `<bot>`, info de extension | recebimento | dados de link, sala de espera, bot e extension |

Os valores exatos em bytes de `<capability>` e dos códigos de `net medium` não foram recuperados desta build (uma máscara de 7 bytes `01 05 F7 09 E4 BB 13` é às vezes citada para clientes web; ela não está presente como literal contíguo na biblioteca Android, então trate o valor do Android como unknown). O motor embute os codecs que nomeia nas strings: Opus mais um codec próprio de baixo bitrate ("mlow", enquadrado em Opus), OpenH264, VP8, AV1 (`wzav1`) e HEVC via MediaCodec.

### 5.3 Caminho de recebimento (found)

1. `CallStanzaHandler` monta `BQU`; métrica `CallStanzaHandler/handleStanza tag=... callId=...`; a mensagem 192 é postada no dispatcher.
2. Para um offer, `preprocess_call_offer` executa `nativeParseXmppOffer`; retorno diferente de zero descarta a stanza. Offers expirados ou encerrados não tocam.
3. `C83.A00` decifra o `<enc>` (seção 6.2), então `nativeHandleIncomingXmppOffer` inicia a chamada; estado `RECEIVED_CALL`.
4. `peekIncomingOffer` (pré-verificação guiada por push) ignora offers silenciados, offers de grupo (`group_info` presente), offers com `is_call_ended=1`, offers 1:1 sem `<enc>` e offers enquanto o telefone está ocupado; a flag **4217** bit 1 habilita peeks de voz, bit 2 peeks de vídeo.
5. Um `terminate` posterior ou o push `handleIncomingTerminatePush` encerra um peek.

---

## 6. Chave da chamada e sua criptografia

### 6.1 Saída (found, `getBulkEncryptedE2EKeys`)

O motor entrega um mapa de JID de dispositivo para bytes brutos da chave da chamada. Para cada dispositivo sem job de pre-key pendente, o cliente monta um protobuf `Message` e o criptografa com Signal usando a sessão pairwise existente (`C83` / `CallableC29363Coo`):

| Campo de Message.Call | Número | Tipo | Definido quando |
|-----------------------|--------|------|-----------------|
| `callKey` | **1** | bytes | sempre (32 bytes brutos) |
| `conversionSource` / `conversionData` / `conversionDelaySeconds` | **2** / **3** / **4** | string / bytes / uint32 | dados CTWA presentes |
| `ctwaSignals` / `ctwaPayload` | **5** / **6** | string / bytes | dados CTWA presentes |
| `contextInfo` | **7** | ContextInfo | flag CTWA (`externalAdReply.adType` definido com um valor fixo) |
| `nativeFlowCallButtonPayload` | **8** | string | chamada iniciada de um botão native-flow |
| `deeplinkPayload` | **9** | string | chamada iniciada de um deeplink |
| `messageContextInfo` | **10** | MessageContextInfo | enriquecimento por peer feito por `AbstractC30999De0` (conteúdo não rastreado) |
| `callEntryPoint` | **11** | uint32 | flag **24935**, somente no fanout inicial (`i == 0`) |
| `callReason` | **12** | string | presente no proto, não definido neste caminho |

`Message.call` é o campo **10** de `Message` (`C30628DTw`), a classe `Message.Call` = `C25827BCl`. Para o offer inicial, a flag **520** adiciona contexto de atribuição de anúncio vindo do resolvedor CTWA (`C35832FfR`; inferred). Um fanout roda com `i == 0` para offers e `i == 1` para rekeys. A criptografia é bloqueante com um caminho de cancelamento; um bloqueio acima de 5000 ms registra `voip_e2e_encryption_blocked`.

Forma no fio de um dispositivo (found, `AbstractC33466EhY.A03/A09`): `<enc v="<version>" type="msg|pkmsg|skmsg|frskmsg|msmsg" [count="<retry>"] [mediatype] [session_type="pq"] [bucket]>CIPHERTEXT</enc>`. `session_type="pq"` marca uma sessão Signal pós-quântica; `count` é omitido quando 0. As chaves de chamada nunca são mensagens de sender key de grupo neste caminho (o tipo `skmsg` é aceito pelo helper, mas nenhum caminho de chamada o produz; inferred).

Dispositivos de extension (prefixo de usuário do JID `01`) usam `sendReKeyToExtension`: um prekey bundle armazenado antes é processado, a chave é criptografada como `pkmsg` com `v="2"` (found).

### 6.2 Entrada (found, `C83.A00`)

| Etapa | Detalhe |
|-------|---------|
| filhos lidos | `registration` (deve ter 4 bytes; registration id do Signal, usado para retry), `device-identity`, `enc` |
| duplicatas | um segundo `<enc>` é descartado (`duplicate <enc>`) |
| contagem de retry | `count` em `<enc>`; valor ausente aborta (`invalid retry count`) |
| tipo | `msg` 0 ou `pkmsg` 1 aceitos; outros números registram `unrecognized ciphertext type` |
| decrypt | decrypt Signal pairwise (mensagem pre-key processada com a identidade de dispositivo do remetente); payload interpretado como `Message`, `call.callKey` extraído; `ExternalAdReplyInfo.adType` de CAWC é registrado |
| resultado | `<enc>` substituído por um nó `<enc>` simples com os bytes da chave da chamada para o motor |
| falha | evento `rejectedDecryptionFailure`, `onPeerE2EDecryptionFailed` refaz a configuração da sessão (busca uma nova pre-key quando o registration id é igual e a base key se repete); o motivo de reject `enc` é enviado quando a chamada não pode ser decifrada |

A flag **24063** altera o caminho de session-type usado para ciphertexts do tipo hosted (inferred a partir da condição `c33281EeX.A04`).

### 6.3 Retry

`sendOfferRetryRequest(device)` faz o motor reenviar o offer (`resendOfferOnDecryptionFailure`); `sendPendingRekeyRequest` repete um pedido de rekey enquanto o byte de retry armazenado estiver entre 0..4. Portanto `count` varia de 0 a 4 (found, `sendPendingRekeyRequest`).

### 6.4 `enc_rekey`: três formatos

| Formato | Evidência | Conteúdo |
|---------|-----------|----------|
| v2 unicast | `sendReKeyStanza` (Java) | o motor emite `<enc_rekey call-id call-creator transaction-id><enc count=N>RAW KEY</enc></enc_rekey>`; o Java substitui o filho pelo `<enc>` criptografado com Signal para o dispositivo de destino (found) |
| v2 fanout | `sendReKeyFanoutStanza` | o destino é um grupo; filho `<destination><to jid><enc/></to>...`; cada entrada criptografada separadamente (found) |
| v3 | strings nativas `handle_enc_rekey_v3`, `make_and_send_rekey_v3`, `ext_rekey: ...` | o payload é um protobuf com `wa.voip.RekeyKeyEntry` repetido (tipo de chave + chave); chaves por tipo têm comprimento fixo (`key type %d has unexpected length`); selecionado quando keygen é 3; requer suporte a extension (`kCallExtensionMV1`); transição v3 para v2 registrada |

Regras visíveis nas strings: rekeys carregam um transaction id; ids antecipados, antigos ou iguais são ignorados (`ignore old rekey msg with transaction id`); em uma chamada um-para-um, `enc_rekey` de entrada é ignorado (`ignore rekey msg in one to one call`); `request_keys` pede ao criador ou a uma extension que reenvie as chaves (somente v3; `request_keys with unexpected keygen` é ignorado). Qual lado inicia um rekey em uma chamada em grupo, e o gatilho exato, não foram resolvidos.

---

## 7. Derivação da chave de mídia

### 7.1 Callbacks Java (found)

| Callback | Cálculo |
|----------|---------|
| `generateE2EKeysV2(callKey[32], out[46], info)` | HKDF-SHA256, salt = 32 bytes zero, IKM = chave da chamada, info = string UTF-8 `info` fornecida pelo motor, 46 bytes de saída (`E2E_EXTENDED_V2_KEY_LENGTH`) |
| `hkdfSha256(salt, ikm, info, out)` | HKDF-SHA256 genérico (primeiro argumento salt, segundo IKM, terceiro info; comprimento da saída = `out.length`) |
| `getSecureSsrc(ikm, info, salt[4], out[4])` | HKDF-SHA256 para 4 bytes (`SECURE_SSRC_LENGTH`) |
| `hmacSha256(key, data, out[32])` | HMAC-SHA256 |
| `generateRandomBytes(out)` | `SecureRandom` (fonte da chave de chamada de 32 bytes; inferred) |

### 7.2 Labels e contextos no motor (strings found, função inferred)

`e2e sframe key`, `hbh srtp key`, `uplink hbh srtcp key`, `downlink hbh srtcp key`, `warp auth key`; funções `derive_sframe_key`, `derive_hbh_srtp_key`, `derive_and_update_warp_mi_keys`, `derive_extension_per_media_key`; slots de chave `owner_e2e_key`, `extension_audio_key`, `extension_video_key`, `extension_appdata_key`.

| Chave | Origem (inferred) | Protege |
|-------|-------------------|---------|
| Material E2E SRTP | saída de `generateE2EKeysV2` (46 bytes), por participante | mídia entre endpoints (1:1) |
| Chave SFrame | label `e2e sframe key` | criptografia de frames em chamadas em grupo / SFU e no data channel hop-by-hop (`wa_sframe_encrypt`, `sframe_keyprovider_set_chainkey`) |
| SRTP / SRTCP hop-by-hop | `hbh_key` fornecida pelo relay (seção 8.2) com os labels `hbh ...` | somente o trecho cliente-relay |
| Chave WARP MI | label `warp auth key` | tag de integridade de mensagem dos pacotes WARP (`warp_mi_tag_len`) |

Os layouts de chave (qual dos 46 bytes é chave ou salt, por direção), o conteúdo da string `info` e as cadeias HKDF exatas para SFrame / hop-by-hop não foram recuperados: os chamadores estão em código nativo que não pôde ser decompilado. Um JID qualificado por dispositivo como `info` é plausível, mas não verificado (**unknown**).

---

## 8. Relay, transporte e caminho de mídia

### 8.1 O que o cliente recebe

Os dados de relay chegam no ack do offer (chamador; `error during parsing relay info`, `Failed to parse relay info in offer ack`), no próprio offer (destinatário), e depois em `relay_info_update` e no ack de uma mudança de estado `video` (found).

### 8.2 Gramática de `<relay>` (found, strings de `fill_relay_info`)

| Item | Nome | Notas |
|------|------|-------|
| atributos do relay | `uuid`, `self_participant_uuid`, `conn_id`, `medium`, `warp_mi_tag_len`, `prefer_relay`, `prefer_ipv6`, `peer_dl`, `smart_transport_signal`, `attribute_padding` | por conjunto de relays |
| tokens | lista de `<token>` (`token_id`), pelo menos um obrigatório (`relay_token_list.num_tokens < 1`) | credencial do relay; lista copiada para a requisição allocate |
| auth tokens | `<auth_token>` (`auth_token_id`) | usado no lugar de um token quando o id está no intervalo; caso contrário "falling back to relay token" |
| key | `<key>` | material de senha do relay |
| `hbh_key` | filho com bytes brutos ou base64 | fonte da chave hop-by-hop; o tamanho é verificado (`HBH Key of unexpected size`, "though warp_mi_tag_len = ...") |
| endpoints | `<te>` ou `<te2>` | nunca ambos (`can not receive both te and te2 endpoints`); bytes de endereço IPv4 ou IPv6 (`endpoint too short for an IPv6 address`); endereço vazio rejeitado |
| por endpoint | `relay_id`, `relay_name` (truncado se muito longo), `domain_name`, `latency`, `c2r_rtt`, `ul_bw`, `dl_bw`, `is_favored` | `latency` alimenta a escolha do relay |
| participantes | `<participant pid jid>` | mapeia os ids de participante usados em pacotes WARP / SFU |

As strings de log imprimem endereços de relay por meio de um placeholder `[MetaServiceIP]`, de modo que os endereços de relay são tratados como IPs de serviço.

### 8.3 Seleção de relay (strings found, lógica inferred)

1. O cliente faz bind nos relays oferecidos (`wa_transport_p2p_start_relay_binds`; requisições bind / alloc são estilo STUN, `wa_stun_*`, transaction ids `tid=0x...`; bind e unbind exigem message integrity).
2. A latência é medida por requisições de ping por relay (`Ping request sent to relay N`), um prober TCP (`wa_transport_tcp_prober_*`) e round trips de allocate; o melhor se torna o "elected relay" (`Elected relay idx=...`, `wa_transport_get_elected_relay_approximate_e2e_rtt`); um árbitro (`wa_transport_path_arbiter_*`) troca de caminho, e `prefer_relay` força o uso de relay.
3. Um endereço server reflexive aprendido da resposta allocate é registrado (`Server reflexive addr`).
4. Peer-to-peer é tentado em paralelo por pares de candidatos (`p2p add_cand_pair`, `e2e bind probe`); o relay permanece como fallback.

### 8.4 `relaylatency` (found)

Serializadores e handlers: `serialize_relay_latency`, `send_or_enqueue_relay_latency`, `handle_relay_latency`, `unpack_and_apply_relay_latency`, em lote (`prepare_batched_relay_latencies`), com interpretação de ack `relaylatency ack: call_id is empty / has invalid type`. A stanza reporta ao peer o RTT medido pelo remetente por índice de relay, e o peer o aplica (`apply_relay_latencies`, limiares `Ignored higher relay latency ...`). A latência é ignorada em offers de chamadas em grupo (`Skip relay latency at call offer in group calls`).

### 8.5 `transport` (strings found)

Atributos e filhos: `transport-message-type`, `p2p-cand-round` (um restart incrementa a rodada e limpa os candidatos remotos), `ice-ufrag`, `ice-pwd`, `<certificate algorithm fingerprint>` (`cert_algorithm`, `cert_fingerprint`), `health_status`, entradas de candidato (endereço, prioridade). A string `Web P2P: skipping type 13 send` mostra que o tipo de mensagem 13 pertence à troca ICE / DTLS do web-P2P. Os demais números de subtipo não foram recuperados (**unknown**).

### 8.6 Dois caminhos de mídia

| Aspecto | Caminho de relay do WhatsApp (padrão) | Caminho web-P2P |
|---------|----------------------------------------|-----------------|
| Configuração | relay allocate / bind (estilo STUN), tokens vindos da sinalização | credenciais ICE e fingerprint do certificado DTLS trocados em `transport`; `wa_ice_transport`, `CreateDtlsTransport` |
| Forma do pacote | pacotes WhatsApp com payload RTP ("WARP", tag de integridade `warp_mi`, piggyback, FEC, `warp_rtx`) | RTP sobre DTLS-SRTP |
| Chave de hop | `hbh_key` do relay (SRTP / SRTCP hop-by-hop, DTLS hop-by-hop até o relay `hbh_dtls_handshake_*`) | derivada de DTLS |
| E2E | E2E SRTP em 1:1, SFrame em grupo (SFU) | SRTP |
| Finalidade | chamadas normais entre apps | interop com o cliente web (`set_peer_is_web`, `handle_transport_web_p2p`); inferred |
| Stack TLS | mbedTLS linkada estaticamente (`mbedtls_ssl_*`, `mbedtls_gcm_*`, `mbedtls_hkdf`) | igual |

Chamadas em grupo usam um SFU com subscriptions (`RxSubscriptions`, `SenderSubscriptions`, protobufs `wa.voip.*` dentro do data channel) em vez de caminhos por peer; a estimativa de banda roda por caminho (`wa_warp_sfu_*`, "one side BWE").

---

## 9. Chamadas em grupo

### 9.1 `group_info` (found, strings de `shared_elements/group.rs`)

| Item | Nome | Notas |
|------|------|-------|
| atributos | `connected-limit`, `phash`, `transaction-id`, `media`, `joinable` | hash do roster e id de ordenação; `group_info has invalid connected_limit` |
| membros | `<user jid [user_pn push_name guest_name account_kind state ..]>` com filhos `<device jid ..>`, ou `<participant jid pid>`; `<bot jid>` | `<user>` e `<participant>` juntos é um erro |
| por usuário | `state`, `pid`, `capability` (`ver`), `rekey`, `terminated`, `connected`, `country_code`, `reason` | listas de dispositivos obrigatórias para usuários sem nack |
| extensions | `extension_creator`, `ext_creator_identity_key_sig`, `extension_id`, `hn_video`, `gen`, `cohost`, `scope` | dados de extension / co-host |

### 9.2 Comportamento

- Limite `Voip.kMaxSupportedGroupCallParticipants` = 64 (found); o motor encerra uma chamada cujo update excede o máximo.
- `group_update` e `terminate` de chamada em grupo carregam transaction ids; os obsoletos ou fora de ordem são ignorados; `kInitialGroupTransactionId` = -1 (found).
- O offer de grupo não carrega chave de chamada por dispositivo; as chaves são recompartilhadas por dispositivo com `enc_rekey` (inferred a partir de `sendReKeyFanoutStanza`).
- Ações de toque e roster: `invite`, `inviteToGroupCall`, `cancelInviteToGroupCall`, re-ring (`rering_ts`, `make_and_send_cancel_offer_for_participants`), `sendRaiseHand`, `sendMutePeerRequestInGroupCall`, `sendRemoveRequest`; `lobby` é a etapa de entrada em uma chamada em grupo em andamento (`joinOngoingCall`).
- Extensions: `add_extension` / `remove_extension` anexam um segundo endpoint de mídia a uma chamada (`wa_call_extension_jid_*`, chaves de owner e extension em 7.2, `kCallExtensionMV1`; o Java trata JIDs de extension com prefixo de usuário `01` de forma especial, 6.1). A classe do dispositivo não foi resolvida (inferred: um wearable pareado, o app inclui `libsmartglasses-bundle.so` e `Voip.sendWearableAttribution`).

---

## 10. Links de chamada, sala de espera, chamadas agendadas

### 10.1 Links (found)

| Item | Valor |
|------|-------|
| URL | `https://call.whatsapp.com/{voice|video}/{token}`; host no manifest `call.whatsapp.com` |
| comprimento do token | `Voip.kCallLinkTokenLength` = 22 |
| criar | `Voip.createCallLink(isVideo, eventStartTimeSec, waitingRoomEnabled)` (log `actionCreateCallLink` / `actionCreateCallLinkForEvent`); o nativo `wa_call_link_create_v2` rejeita um horário de início inválido |
| editar / prévia | `editCallLink(token, ..., startTime, int)`, `previewCallLink`, `queryCallLinkForLinkEdit`; stanzas `link_edit`, `link_query` |
| entrar | `joinCallLink` envia `link_join`; o ack `LinkJoinAck` carrega `call-creator`, `group_info`, `voip_settings`, info do link |
| estados do link | `kCallLinkState`: None 0, QuerySent 1, QueryAcked 2, JoinSent 3, JoinAcked 4 |
| `CallLinkInfo` | creatorJid, token, videoEnabled, eventStartTsSec, isGuestEligible, linkState, waitingRoomState, self |
| eventos de nack | `linkCreateNacked`, `linkQueryNacked`, `linkJoinNacked`, `linkEditNacked` com o código de erro do ack |

As stanzas de link são endereçadas a um JID de domínio de chamada (o parser de JID em Rust lista `callDomainJID` e `callJID`; o tipo de JID aceito por `C0DZ.A0R` que corresponde a ele não foi resolvido).

### 10.2 Chamadas de evento (agendadas)

Uma chamada de evento é um link de chamada criado com `eventStartTimeSec` diferente de zero (found). O offer de uma chamada agendada carrega `scheduled-id` (found no parser). `Message` carrega duas mensagens de chat:

| Campo de Message | Número | Tipo | Conteúdo (found) |
|------------------|--------|------|------------------|
| `scheduledCallCreationMessage` | **61** | ScheduledCallCreationMessage | `scheduledTimestampMs` 1, `callType` 2 (UNKNOWN 0, VOICE 1, VIDEO 2), `title` 3 |
| `scheduledCallEditMessage` | **65** | ScheduledCallEditMessage | `key` 1 (MessageKey), `editType` 2 (UNKNOWN 0, CANCEL 1) |

Apenas cancelar existe como edição. Armazenamento local (found): tabelas `message_scheduled_call` (`scheduled_timestamp_ms`, `call_type`, `title`), `message_add_on_scheduled_call_edit` (`creation_message_row_id`, ...), `message_system_scheduled_call_start` (`call_title`, `call_timestamp_ms`), `scheduled_calls` (`key_chat_row_id`, `key_id`, `scheduled_timestamp`, `is_upcoming`, `call_log_row_id`). O lembrete do lado do servidor (um filho de chamada `reminder`, `kServerReminder*` abaixo) e como a mensagem de criação se liga ao token do link de chamada não foram resolvidos.

### 10.3 Sala de espera

Stanzas `waiting_room_toggle` (`link-token`, `media`, `enabled`, variante de chamada ativa), `_admit`, `_deny`, `_leave`, `_update`; campos de usuário interpretados `jid`, `user_pn`, `push_name`, `guest_name`, `is_guest_eligible`, `state`. Java: `waitingRoomAdmit`, `waitingRoomAdmitAll`, `waitingRoomDeny`, `waitingRoomToggle`; eventos `waitingRoomAdmitAcked`, `waitingRoomDenyAcked`, `waitingRoomStateChanged`, `waitingRoomDenied`. `kServerReminder`: Legacy 0, LinkJoinedCreator 1, LinkJoinedJoiner 2, LinkConnectedCreator 3, LinkMissedCreator 4, LinkCreatorWaitingRoomJoined 5, LinkCreatorWaitingRoomMultipleJoined 6.

---

## 11. bcall, bot e portadores alternativos

### 11.1 Mensagem de chat `bcall` (found)

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `sessionId` | **1** | string | sessão de chamada business |
| `mediaType` | **2** | enum | UNKNOWN 0, AUDIO 1, VIDEO 2 |
| `masterKey` | **3** | bytes | obrigatório: chave ausente lança `bcall message doesn't have master key` |
| `caption` | **4** | string | opcional |

`Message.bcallMessage` = campo **72** (classe `DSA`); o handler `F2V` (`FMessageBCallProtobuf`) o mapeia para o tipo de mensagem 91 com session id, media type (0 unknown, 1 audio, 2 video), caption e bytes da master key. A `master key` é uma chave entregue dentro de uma mensagem de chat criptografada ponta a ponta; o que ela protege (inferred: a mídia de uma chamada business) não foi rastreado. Eventos do motor `bCallCreated(callId, key, ...)`, `bCallJoined`, `bCallEnded`, `bCallAudienceUpdated`, `bCallCreateFailed`; `CallState.BCALL_STARTING`; filhos `<call>` de entrada chamados `bcall_*` recebem um call id vazio (3.2). Existem as strings nativas `bcall_start`, `bcall_notify`.

### 11.2 Chamadas de bot e sinalização HTTP / TEE

Chamadas de bot: `CallInfo.isBotCall`, nós `<bot>` em `group_info`, `verifyIncomingBotIdentityKey`, `reconfigure_bot` (`req_id`), fluxo de TOS do bot (nack 488); o offer é mesclado com um construtor de payload em cache. Contexto: [WA_META_AI.md](WA_META_AI.md). Separadamente, `SignalingHttpCallback.sendMsg` permite ao motor trocar bytes de sinalização opacos via `TeeRequestHandler` em vez do chatd (`handle_http_tee_start_session_response`, `handle_http_create_extension_response`); tipos de requisição voice session e codec avatar. Elegibilidade e formato do payload são **unknown** (inferred: sessões de bot e avatar).

---

## 12. Registro e histórico de chamadas

### 12.1 `callLogMesssage` (campo **69** de Message, classe `C49434Loq`, found)

| Campo | Número | Tipo | Valores |
|-------|--------|------|---------|
| `isVideo` | **1** | bool | |
| `callOutcome` | **2** | enum | CONNECTED 0, MISSED 1, FAILED 2, REJECTED 3, ACCEPTED_ELSEWHERE 4, ONGOING 5, SILENCED_BY_DND 6, SILENCED_UNKNOWN_CALLER 7 |
| `durationSecs` | **3** | int64 | |
| `callType` | **4** | enum | REGULAR 0, SCHEDULED_CALL 1, VOICE_CHAT 2 |
| `participants` | **5** | `CallParticipant` repetido | `jid` 1 (string), `callOutcome` 2 (mesmo enum) |

Builder `C53129Nna` (found): o resultado do registro de chamadas do motor (`Voip.kCallLog*`) é mapeado como segue.

| Resultado `kCallLog` | `callOutcome` no fio |
|----------------------|----------------------|
| Canceled 1, Missed 2 | MISSED |
| Unavailable 3 | FAILED |
| Rejected 4 | REJECTED |
| Connected 5 | CONNECTED |
| AcceptedElsewhere 6, ScreenedElsewhere 9 | ACCEPTED_ELSEWHERE |
| Invalid 0, Failed 7, ConnectedLonely 8, outros | ONGOING (ramo padrão decompilado) |
| flag DND / flag de chamador desconhecido no registro | SILENCED_BY_DND / SILENCED_UNKNOWN_CALLER (verificado primeiro) |

Failed 7 mapeado para ONGOING parece errado, mas é o ramo padrão decompilado; trate como lido, não como comportamento verificado. Tipo de chamada: o tipo local 1 mapeia para SCHEDULED_CALL, 2 ou 3 para VOICE_CHAT, caso contrário REGULAR. Um tipo de chamada ausente lança `call log message missing call_type`.

### 12.2 Banco de dados local (found)

Tabelas: `call_log` (`jid_row_id`, `from_me`, `call_id`, `transaction_id`, `timestamp`, `video_call`, `duration`, `call_result`, `is_dnd_mode_on`, `bytes_transferred`, `group_jid_row_id`, `is_joinable_group_call`, `call_creator_device_jid_row_id`, `call_random_id`, `call_link_row_id`, `call_type`, `offer_silence_reason`, `scheduled_id`, `telecom_uuid`, `terminated_by_device_switch`), `call_log_participant_v2` (`call_log_row_id`, `jid_row_id`, `call_result`), `joinable_call_log` (`call_id`, `joinable_video_call`, `group_jid_row_id`, `phash_identifier`, `self_other_device_connected`, `is_lgc_add`), `message_call_log`, `call_unknown_caller`, `reminder`. Eventos de alimentação: `callEnding(CallLogInfo, ..)`, `update1to1CallLog`, `updateJoinableCallLog` (`kUpdateJoinableCallLogType` Create 1, Update 2, Delete 3).

---

## 13. Estados e constantes do motor (found, `Voip.java`, `CallState`)

| Grupo | Valores |
|-------|---------|
| `CallState` | NONE, CALLING, PRE_ACCEPT_RECEIVED, RECEIVED_CALL, ACCEPT_SENT, ACCEPT_RECEIVED, ACTIVE, ACTIVE_ELSEWHERE, REJOINING, LINK, CONNECTED_LONELY, PRECALLING, ENDING, BCALL_STARTING, SCREENING |
| `kCallLog*` | Invalid 0, Canceled 1, Missed 2, Unavailable 3, Rejected 4, Connected 5, AcceptedElsewhere 6, Failed 7, ConnectedLonely 8, ScreenedElsewhere 9 |
| `kCallEndReason*` | Unknown 0, Timeout 1, Self 2, RejectDoNotDisturb 3, RejectBlocked 4, MicPermissionDenied 5, CameraPermissionDenied 6 |
| `kFatalReason*` | Unknown 0, ParticipantAllocationFailure 1, CallSetupError 2, CallTxTimeout 3, CallRxTimeout 4, VideoStreamCreateError 5, VideoPortCreateFailed 6, NoSamplingRatesForAudioRecord 7, AudioInitError 8 |
| `kOfferSilenceReason*` | None 0, Privacy 2, Lightweight 3, ScreenSharing 4, AddedAsLinkCreator 9, AddedForDeviceSwitching 10, GroupChatAdd 11 |
| `kParticipant*` | Connected 1, Incoming 2, Ringing 3, Rejected 4, Terminated 5, TimedOut 6, CreatingCall 7, Invited 11 |
| `kVideoState*` | Disabled 0, Enabled 1, Paused 2, UpgradeRequest 3, UpgradeAccept 4, UpgradeReject 5, Stopped 6, UpgradeRejectByTimeout 7, UpgradeCancel 8, UpgradeCancelByTimeout 9, UnknownPeer 10, Xr2dCodecAvatarEnabled 12, Error 20 |
| `kStatus*` | Success 0, InvalidArgument 70004, Exists 70015, Ignored 70020, CallAlreadyStarted 670001, CallNotActive 670007, CallHasNoVideo 670018, GroupCallUserExists 670021, GroupCallPeerCodecMismatch 670033, GroupCallUserExistsNotInvited 670038, NotPermitted 670040, UserNotRemovable 670041, UserNotConnected 670042 |
| `kScreenShareVersion*` | Legacy 0, 1 a 4 |
| `kNetworkHealth*` | Measuring 0, NoNetwork 1, Poor 2, Average 3, Good 4 |

Os inteiros de `kCallEndReason` são o que a UI vê; as strings colocadas no fio para terminate não estão entre as strings da biblioteca (14.3).

---

## 14. Erros, reject, terminate

### 14.1 Códigos de nack do offer (found, `VoiceServiceEventCallback.callOfferNacked`)

Um ack de offer com erros chama `callOfferNacked(errors[])`. Um único erro 304 ou 400 é tratado como offer duplicado e ignorado. O nack é fatal quando a chamada está em `CALLING` / `CONNECTED_LONELY` e todos os destinatários (ou o próprio) receberam nack, ou o código é 432; caso contrário é por destinatário e não fatal.

| Código | Caminho fatal (ramo decompilado) | Caminho não fatal |
|--------|----------------------------------|-------------------|
| 401 | tela de não permitido (id de motivo 3) | |
| 403 | tela de não permitido, id específico de vídeo quando é vídeo | |
| 404 | não permitido id 16 | texto "contact unavailable" por destinatário |
| 405 | id 4 | |
| 406 | id 2 (áudio) / 11 (vídeo) | |
| 411 | id 11, ou 37 para lightweight | |
| 412 | id 10; group info atualizado em caso de divergência de membros | |
| 426 | id 1 (áudio) / 9 (vídeo) | |
| 427 | id 12, ou 36 para 1:1 lightweight | texto por destinatário; em grupos acima de 4 participantes um id alternativo |
| 428 | id 14 | texto por destinatário |
| 429 | somente evento de UI | |
| 431 | id 15 | texto "not available" |
| 432 | id 2; sempre fatal | |
| 435 | | texto por destinatário; após um ack de offer também dispara uma ação extra |
| 460 / 463 | vídeo 10 / áudio 2; 463 id 17 | |
| 488 | TOS do bot não aceito: abre o fluxo de TOS do bot | igual |
| 467, 468, 469 | | id 46 para múltiplos destinatários |
| 500, 502 | | texto "not available" |
| 538 | | id 35 |
| outro | id padrão (vídeo 8 / 0) | assertion `Unknown error code` |

O ramo fatal decompilado perdeu alguns returns, então os ids são apenas indicativos; a lista de códigos e a divisão fatal / não fatal são firmes. Os significados dos códigos além da reação do cliente são do lado do servidor (**unknown**). Após um nack de offer completo, o motor não envia nenhuma stanza de chamada exceto `terminate` (string found).

### 14.2 Motivos de reject (found, `Voip.REJECT_REASON_*`)

| String | Significado / reação do cliente |
|--------|---------------------------------|
| `` (vazio) | recusada |
| `busy` | destinatário ocupado; tom de ocupado, a chamada termina após um atraso |
| `unavailable` | constante definida; uso principal encontrado no código de presença / disponibilidade |
| `uncallable` | o peer não pode ser chamado; tela de não permitido |
| `tos` | o peer não aceitou o TOS; tela de não permitido |
| `enc` | falha ao decifrar a chave da chamada |
| `server_conf_corrupted` | configuração do servidor inutilizável |

`rejectCall(callId, reason, int)` e `rejectPendingCall` são os pontos de entrada; `callRejectReceived` consome os motivos de entrada. Os motivos de reject são mapeados para resultados locais da chamada (`reject_reason_to_call_result`, `set_call_term_reason_from_received_call_reject_reason`).

### 14.3 Terminate (strings found)

- `terminate` carrega um transaction id e um nó `call_summary` (estados dos usuários, duração); um offer para uma chamada encerrada carrega `terminate_hint` com `terminate_reason`, `call_summary` e um transaction id. Se o próprio `terminate` tem um atributo `terminate_reason` não foi resolvido.
- Terminate vindo de um dispositivo companion é ignorado pelo motor; o primário faz fanout de um terminate para peers multi-device (`fanout_terminate_if_peer_is_md`).
- Um terminate de troca de dispositivo no estado errado é ignorado; os resultados "handled elsewhere" são derivados do motivo (`get_handled_elsewhere_outcome_from_terminate_reason`) e resultados conflitantes para o mesmo call id são ignorados.
- RTCP BYE no caminho de mídia também encerra uma chamada (`rtcp_bye_terminate_delay`), assim como a remoção de extension pelo servidor (`extension terminated by server`).
- O Java envia `terminate` com retry (enfileirado entre reconexões) quando a flag **8003** está ligada e a chamada não é uma chamada de bot nem está em estado lonely; caso contrário sem retry (ramo parcialmente obscuro na saída decompilada).
- Os valores da string `reason` de terminate (e qualquer mapeamento a partir de `kCallEndReason`) não estão nas strings da biblioteca e não foram encontrados em outro lugar do APK (**unknown**).

---

## 15. Feature flags (ids como lidos nos pontos de chamada; nomes não resolvidos)

| ID | Tipo | Controla |
|----|------|----------|
| **9257** | long ms | timeout de entrega do offer; stanza descartada no timeout (`CIX.A02`) |
| **9431** | long ms | timeout de entrega do accept; também memoriza o id da stanza accept para que `preSendTerminate` possa cancelá-la |
| **9432** | bool | no timeout do accept, dispara uma reconexão |
| **8003** | bool | terminate com retry (14.3) |
| **15125** | bool | reportar a métrica `call_stanza_drop` |
| **30890** | bool | enviar ping de chamada de saída após o offer |
| **30891** | long ms | timeout do ping, padrão 3000 |
| **32651** | int | tentativas de ping, mínimo 1 |
| **31086** | bool | tracker de offer de saída |
| **24935** | bool | escrever `callEntryPoint` em `Message.call` |
| **520** | bool | adicionar contexto de atribuição de anúncio a `Message.call` (inferred) |
| **20605** / **20606** | bool / int | adicionar `<tctoken>` aos destinos da chamada; limite de usuários por stanza |
| **24063** | bool | seleção de session-type no decrypt para uma classe de ciphertext (inferred) |
| **4217** | máscara int | peek de offers de entrada: bit 1 voz, bit 2 vídeo |
| **3094** | máscara int | bit 8 = eventos de chamada assíncronos (`kFlagEnableCallEventAsync`); pareada com **9210** (bool) |
| **7481** | bool | estado de notificação de mute de chamadas em grupo para chamadas em grupo por link |
| **13630** / **13804** | int / bool | amostragem para uma métrica de decrypt (inferred) |

Os parâmetros do motor (`p->enable_sframe_tx`, `tp->web_p2p_bitmap`, `tp->enable_e2e_bind_probe_bitmap`, `options.wa_log_time_series`, ...) vêm do `voip_settings` do servidor e são lidos via `Voip.getVoipParam`; seus nomes são strings na biblioteca, seus valores são do lado do servidor.

---

## 16. Baileys (`baron-baileys-v2`, código lido, nada testado)

| Tópico | Baileys | Android |
|--------|---------|---------|
| Offer | `offerCall`: `call-id` aleatório de 32 hex, `call-creator` = id próprio, `<audio enc=opus rate=16000/8000>`, `<video enc=vp8 dec=vp8 ...>` (vídeo), `<net medium=3>`, `<capability ver=1>` 6 bytes `01 04 FF 83 CF 04`, `<encopt keygen=2>`, `<destination>` com `Message{call{callKey}}` criptografada com Signal, `count=0`, `device-identity` quando um pkmsg é produzido | mesmos elementos; o Android monta o offer no motor, bytes de capability desconhecidos (5.2) |
| Envelope | `<call id to>` para offer; reject / accept / terminate usam `from` + `to` sem `id` | `<call to id>` sempre (3.1) |
| accept | `<accept call-id call-creator count=0/>`, sem filhos | o accept do motor carrega parâmetros de mídia e um certificado (seção 4) |
| terminate | `reason="user-terminated"`, `count=0` | strings de motivo desconhecidas (14.3) |
| rekey | `<enc_rekey ...><enc v=2 type=msg/></enc_rekey>` | o formato v2 corresponde a 6.4; v3 ausente |
| Entrada | decifra `<enc>` (`unpadRandomMax16`, `Message.decode`), faz cache do offer, emite eventos de chamada; tags de mídia / relay apenas recebem ack | o Android decifra com o mesmo envelope e alimenta o motor |
| Links | `link_create media` (+ `event start_time`) para `@call`; `waiting_room_toggle`; `link_join token` | a gramática corresponde aos nomes encontrados aqui; tipo de JID de destino não resolvido |
| Status de terminate | mapeia as strings de `terminate reason` `Timeout`, `RejectDoNotDisturb`, `MicPermissionDenied`, `CameraPermissionDenied`, `RemoteBusy`, `RemoteOffline` | essas strings não estão na biblioteca; os nomes lembram `kCallEndReason` (vínculo **inferred**) |

O Baileys não tem relay allocation, nem WARP / SRTP / SFrame, nem motor, então consegue sinalizar e fazer tocar, mas não consegue transportar mídia. Se um offer sem os parâmetros completos do motor é aceito ou toca no peer não foi testado.

---

## 17. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|----------|
| `Wrong jid type` para uma stanza de chamada | `to` não é um JID de usuário / dispositivo / domínio de chamada | endereçar o JID do dispositivo ou do usuário |
| offer enviado `without enc`, o peer não toca | chave da chamada não criptografada (sem sessão, job de pre-key pendente) | construir as sessões primeiro; o Android mantém o offer pendente |
| `duplicate <enc>` / `invalid retry count` / `invalid registration` | `<enc>` malformado; `registration` não tem 4 bytes | um `<enc>` com `count`; `registration` somente em retry |
| nack de offer 304 / 400 | offer duplicado | ignorar |
| nack de offer 401 / 403 / 463 | chamador não tem permissão para chamar este peer | nenhuma no cliente |
| nack de offer 412 / 488 | participação no grupo diverge / TOS do bot não aceito | atualizar group info / aceitar o TOS do bot |
| reject `enc` | o destinatário não conseguiu decifrar a chave da chamada | reenviar o offer após reparar a sessão (`count` > 0) |
| `Unsupported keygen ver`, `can not receive both te and te2`, `num_tokens < 1` | `encopt`, endpoints de relay ou tokens inválidos | enviar keygen 2 ou 3, uma família de endpoint, pelo menos um token |
| `bcall message doesn't have master key` | `masterKey` ausente | incluí-la |
| `Call stanza delivery timed out` | sem ack do chatd dentro da flag 9257 / 9431 | stanza descartada; accept pode reconectar (flag 9432) |

---

## 18. Distinções-chave

| Não confundir | Com |
|---------------|-----|
| `Message.call` (campo 10, chave de chamada E2E dentro de uma mensagem Signal) | `callLogMesssage` (69, registro de resultado), `bcallMessage` (72, chave de sessão business) |
| `<enc>` em uma stanza de chamada (ciphertext Signal pairwise) | mensagens de sender key `skmsg` e criptografia de mídia |
| Chaves E2E SRTP / SFrame (derivadas da chave da chamada) | chaves hop-by-hop (derivadas da `hbh_key` do relay) |
| `<token>` / `<auth_token>` do relay (credenciais de alocação) | `<tctoken>` (token de privacidade dentro de `<to>`) |
| inteiros `kCallEndReason` (UI), `kCallLog*` (resultado do motor) | strings de motivo de terminate (fio, unknown), enum `callOutcome` (fio) |
| `CallLogMessage.CallType` REGULAR / SCHEDULED_CALL / VOICE_CHAT | `ScheduledCallCreationMessage.CallType` UNKNOWN / VOICE / VIDEO |
| `enc_rekey` v2 (filho `<enc>` Signal) | `enc_rekey` v3 (lista protobuf `RekeyKeyEntry`) |
| Caminho de relay do WhatsApp (WARP, SRTP hop-by-hop) | caminho web-P2P (ICE + DTLS-SRTP) |
| Chamada de evento (link com horário de início) | mensagens de chat de chamada agendada (61 / 65) |
| Sinalização via chatd | sinalização HTTP / TEE para sessões de bot e avatar |

---

## 19. Fluxo completo (chamada 1:1)

```
[Caller app]  startCall(callId, peer, video, ...)
     │
     ▼
[Native engine]  mints 32-byte callKey ; builds <offer> (audio, video, net, capability, encopt keygen)
     │  sendCallStanza(peer, callId, node)
     ▼
[OutgoingSignalingHandler]  per device: Message{call{callKey,...}} → Signal encrypt → <enc>
     │  <destination><to jid><enc/></to>…</destination> [tctoken] [device-identity if pkmsg]
     ▼
[CIX / writer]  <call to id><offer call-id call-creator>…</offer></call>     (delivery timeout, flag 9257)
     │
     ▼
[WA Server]  (not observed) enriches the offer: relay, voip_settings, metadata, privacy
     ├──────► [Caller]  offer ack: <relay> tokens, endpoints, hbh_key ; voip_settings ; or nack (14.1)
     ▼
[Callee]  <call from t e offline><offer/></call>
     │  CallStanzaHandler → nativeParseXmppOffer → C83 decrypt <enc> → callKey → ring (RECEIVED_CALL)
     ▼
[Callee]  preaccept ─► [Caller] PRE_ACCEPT_RECEIVED ;  accept (media params, certificate) ─► ACCEPT_RECEIVED
     │
     ▼
[Both engines]  relay allocate / bind with tokens ; transport / relaylatency / relay_info_update
     │  E2E keys from callKey (HKDF) ; hop-by-hop keys from hbh_key ; optional P2P pair or web_p2p DTLS
     ▼
[Media]  WARP packets via the elected relay or P2P ; ACTIVE ; in-call video, mute_v2, notify, heartbeat
     │
     ▼
[Either side]  terminate (transaction id, call_summary) ─► ack class="call" type="terminate"
     ▼
[Both]  callEnding(CallLogInfo) → call_log row / callLogMesssage ; teardown ; RTCP BYE
```

Diferenças da chamada em grupo: o offer carrega `group_info` e nenhuma chave por dispositivo; quem entra depois usa `lobby` / `link_join`; os rekeys trafegam como `enc_rekey` (fanout v2 ou v3) com transaction ids; a mídia passa por um SFU com SFrame.

---

## 20. Unknowns

| Item | Status |
|------|--------|
| Construtores / parsers nativos de stanza, strings `info` do HKDF, layouts de chave | biblioteca voip não decompilada; apenas strings |
| Bytes de capability, códigos de `net medium`, padrões de parâmetros de codec | não recuperados |
| Valores de `transport-message-type` além de 13 | não recuperados |
| Strings `reason` de terminate, mapeamento de reject para end-reason | não encontrados |
| Significado de `e` no envelope, ação secundária do erro 435 no ack do offer | não resolvido |
| Tabela numérica de 85 ids de mensagem | ausente nas strings desta build |
| Classe do dispositivo extension, gatilho do rekey v3, gatilho do rekey em grupo | não resolvido |
| Tipo de JID da chamada por link, vínculo da chamada agendada com o token | não resolvido |
| Payload e elegibilidade da sinalização TEE / HTTP | não resolvido |
| Comportamento do servidor (enriquecimento, semântica de nack, escolha de relay) | lado do servidor |
| Tráfego | nada capturado |
