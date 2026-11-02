<!-- src-sha1: 5cbe81a4c1568d0ea9b8c065d2d8dc0fbf7e1afc -->
# WhatsApp Links de Chamada — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-11-02
**Escopo:** Links de chamada para convidados (`call.whatsapp.com/{voice|video}/{token}`): o handshake `link_query` / `link_join`, a sala de espera, o modelo de participante convidado / alocação de JID, e o material de relay e de chave entregue a um convidado na admissão. Este relatório cobre apenas a camada de link/sala-de-espera/convidado; a gramática genérica do envelope `<call>`, offer/accept/terminate, a chave da chamada, a lógica de seleção de relay e o caminho de mídia são cobertos em [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md) e apenas referenciados aqui, sem repetição.

---

## 1. O que é

Um link de chamada é um token que permite a um participante entrar em uma chamada sem ser convidado por JID. O servidor resolve o token para uma chamada em execução ou iniciável e, se a chamada tiver sala de espera, mantém quem entrou lá até ser admitido. Tudo nas seções 3 em diante, abaixo das tabelas de forma de stanza, é **tested**: lido de uma captura real de tráfego de um cliente entrando em sua própria chamada de teste via link, decifrada e decodificada pelo próprio cliente que entra (não interceptação de tráfego de terceiros). Dados estáticos da APK (**found**) corroboram as partes que a captura não mostra, principalmente a criação do link. O raciocínio do lado do servidor é **unknown** salvo indicação contrária.

| Entidade | Forma | Definido por | Tier |
|--------|------|--------|------|
| URL do link | `https://call.whatsapp.com/{voice\|video}/{token}` | o cliente monta o template em torno de um token | found |
| Token | 22 caracteres, alfanumérico de caixa mista (`Voip.kCallLinkTokenLength`=22) | o ponto de criação não tem parâmetro de token em Java; atribuição pelo servidor é a hipótese de trabalho | found (tamanho), inferred (origem) |
| Call-id | 32 caracteres hex (16 bytes), ex. `0076804DB4CA9D41EFCB547F08AE87BD` | servidor, retornado no ack de `link_join` | tested |
| `is_guest_eligible` | bool no link | o host escolhe na criação (`CallLinkInfo.isGuestEligible`) | found (campo), tested (valor na rede) |
| `waiting_room` `enabled` | bool no link | o host escolhe na criação (`Voip.createCallLink(..., waitingRoomEnabled)`) | found (campo), tested (valor na rede) |
| Participante convidado | uma entrada de roster com `account_kind="guest"` e JID alocado pelo servidor | servidor, na admissão | tested |
| JID do domínio call | domínio `call` sem user part antes de existir um call-id, `<call-id>@call` depois | servidor | tested |

---

## 2. Base de evidência

Duas entradas de convidado independentes foram capturadas de ponta a ponta, ambas a partir de uma conexão chatd já autenticada (a sessão que entra tem sua própria identidade na rede) que deliberadamente chama o caminho de link com um nome de exibição escolhido pelo próprio usuário e sem identidade divulgada, em vez de entrar com o JID da própria conta:

| | Link de vídeo | Link apenas-áudio |
|---|---|---|
| Token | `7vEdtKy61dqCtbWAQ59zuO` | `ENcQnTAwKj7lQOdOHVJPmQ` |
| Call-id | `0076804DB4CA9D41EFCB547F08AE87BD` | `00BC509C0194CE83E26FA85A0319FD9C` |
| Criador da chamada (host) | `48615137533978` dispositivo 24 | `21428363591910` dispositivo 0 |
| push_name do convidado enviado | `Baron als Gast ohne wa` | `Baron aus web testt` |

Ambas as sessões endereçam o host e o próprio criador do call-id com uma forma de JID `type=1, domainType=1` e sem atributo `server` explícito; em outros pontos das mesmas capturas, essa mesma forma aparece, para a mesma conta, com `server="lid"` explícito (ex. os acks de recibo de classe mensagem). Lidos em conjunto: a sinalização de chamada aqui roda sobre identidades LID, consistente com a nota do WA_CALL_SIGNALING.md §3.2 de que stanzas de chamada toleram um `to` LID contra um `call-creator` de domínio diferente.

Uma terceira captura, de uma sessão de navegador genuinamente sem conta (sem nenhum login prévio no WhatsApp, conduzida por um humano, nada automatizado), preenche parte dessa lacuna: mostra a etapa de registro que produz a identidade que as seções acima assumem já existir, e confirma que essa etapa roda sobre o transporte web ordinário, não um transporte separado. Ver §14–§15. O conteúdo decifrado da stanza de convidado dessa sessão (se é byte a byte idêntico às formas da §4) não foi capturado — o canal Noise o esconde de uma visão passiva de rede, assim como para qualquer outro cliente.

---

## 3. Criação do link (found, APK; não capturado na rede)

| Etapa | Classe / método | Detalhe |
|------|-----------------|--------|
| Pontos de entrada | `CreateCallLinkBottomSheet` (link independente), `EventCallLinkManager.createCallLink` (link vinculado a evento) | ambos convergem para um único manager |
| Manager | `CallLinkManager` (tag de log), despacha `actionCreateCallLink` / `actionCreateCallLinkForEvent` | |
| Chamada nativa | `Voip.createCallLink(isVideo, eventStartTimeSec, waitingRoomEnabled)` | apenas 3 parâmetros — sem token, sem argumento explícito de `media`/`guest` na assinatura Java |
| Montagem da stanza | nativo (`wa_call_link_create_v2`) | a própria IQ `link_create` é montada abaixo da fronteira JNI, como qualquer outra stanza de chamada (§2 do WA_CALL_SIGNALING.md) |
| Resultado | `CallLinkInfo` (creatorJid, token, videoEnabled, eventStartTsSec, isGuestEligible, linkState, waitingRoomState, self), populado por um callback nativo | o token é lido de volta, não fornecido |
| URL | `AbstractC227619sp.A01(token, isVideo)`: `Uri.Builder().scheme("https").authority("call.whatsapp.com").appendPath(isVideo?"video":"voice").appendPath(token)` | o cliente monta a URL de compartilhamento em torno do token que recebeu de volta |

Nenhum gerador `SecureRandom`/base62 aparece perto de `kCallLinkTokenLength` ou `createCallLink` em Java, e a biblioteca nativa não pôde ser decompilada. **Unknown**: se o token de 22 caracteres é gerado no lado do cliente e enviado em `link_create`, ou atribuído pelo servidor e retornado no ack — o ponto de chamada visível ao cliente não carrega argumento de token, o que favorece atribuição pelo servidor, mas isso é **inferred**, não provado. `connected-limit` (visto em `group_info`, §6) é retornado apenas pelo servidor; nenhum setter no lado do cliente foi encontrado. Nenhum limite de taxa no lado do cliente para criação de link foi encontrado.

---

## 4. Query e join (tested)

### 4.1 `link_query`

Enviado sem conteúdo adicional, antes de qualquer call-id ser conhecido, para o JID do domínio call sem user part (`to: {user: null, server: "call"}`):

```
<call to="@call" id="...">
  <link_query token="7vEdtKy61dqCtbWAQ59zuO" media="video"/>
</call>
```

Ack:

```
<ack from="@call" class="call" type="link_query" id="...">
  <link_query link_creator="<host jid>" media="video" token="...">
    <guest is_guest_eligible="1"/>
    <waiting_room enabled="1"/>
  </link_query>
</ack>
```

`link_creator` identifica o host; `is_guest_eligible` e `waiting_room enabled` são as configurações de criação do link (§3) ecoadas de volta. Ainda sem call-id — este ack apenas prévia o link.

### 4.2 `link_join`

Carrega o mesmo `token`/`media`, mais um `push_name` escolhido e os filhos de mídia no formato usual de offer:

```
<call to="@call" id="...">
  <link_join token="7vEdtKy61dqCtbWAQ59zuO" media="video" push_name="Baron als Gast ohne wa">
    <audio enc="opus" rate="16000"/>
    <video dec="H264" device_orientation="0"/>
    <net medium="2"/>
    <capability ver="1">...7 bytes...</capability>
  </link_join>
</call>
```

O `link_join` do link apenas-áudio (segunda captura) omite completamente o filho `<video>` — confirmado por comparação direta, não inferido:

```
<link_join token="ENcQnTAwKj7lQOdOHVJPmQ" media="audio" push_name="Baron aus web testt">
  <audio enc="opus" rate="16000"/>
  <net medium="2"/>
  <capability ver="1">...</capability>
</link_join>
```

`push_name` é um texto livre que o convidado escolhe para esta entrada; não é o nome de exibição do WhatsApp da conta (a conta que entra em ambas as capturas é uma sessão real já logada, mas o nome escolhido difere de seu nome de perfil normal — a identidade de convidado é só de apresentação nesta etapa). Os 7 bytes de `<capability>` observados (`01 05 F5 09 E0 BB 53` convidado em vídeo, `01 05 F7 09 E0 3B 53` host) são valores específicos da sessão, não uma máscara geral; o WA_CALL_SIGNALING.md §5.2 já marca os valores do byte de capability no Android como unknown em geral e isto não resolve essa questão.

Ack ao `link_join` já carrega um call-id — o servidor resolveu (ou iniciou) a chamada:

```
<ack from="@call" class="call" type="link_join" id="...">
  <waiting_room link-token="7vEdtKy61dqCtbWAQ59zuO" media="video"
                call-id="0076804DB4CA9D41EFCB547F08AE87BD"
                call-creator="<host jid>" enabled="1"/>
  <guest is_guest_eligible="1"/>
</ack>
```

### 4.3 Endereçamento do JID do domínio call (tested)

Isto resolve parte do WA_CALL_SIGNALING.md §10.1, que deixara o tipo do JID do domínio call não identificado:

1. `link_query` / `link_join` endereçam o domínio puro `call` — sem user part (`callDomainJID`).
2. No momento em que o ack de `link_join` retorna um `call-id`, o cliente passa a endereçar as demais stanzas em chamada (heartbeat da sala de espera, e depois mute/transport/relaylatency/video) para `<call-id>@call` — um JID qualificado por user part sob o mesmo domínio (`callJID`).
3. O próprio push de admissão do servidor (§5) chega depois com `from="<call-id>@call"`, confirmando o mesmo endereçamento no lado de entrada.

Então o call-id, uma vez conhecido, *é* o user-part do JID para tudo que vem depois — não uma chave de correlação separada carregada junto com o endereçamento.

---

## 5. Sala de espera (tested)

Enquanto espera, o convidado já entrado mas não admitido envia um heartbeat periódico para o JID do call-id:

```
<call to="<call-id>@call" id="...">
  <heartbeat call-id="0076804DB4CA9D41EFCB547F08AE87BD" call-creator="<host jid>" type="waiting_room"/>
</call>
```
confirmado imediatamente (`<ack ... type="heartbeat"/>`, sem conteúdo).

**Ressalva sobre a admissão**: esta captura é unilateral — mostra apenas a própria conexão do convidado. A ação do lado do host que admite um convidado em espera (`waitingRoomAdmit`, enviando uma stanza `waiting_room_toggle`/`_admit`, conforme WA_CALL_SIGNALING.md §10.3) roda na conexão do *host* e não foi observada aqui; este relatório mostra apenas o resultado dela. Em ambas as capturas, a admissão (§6) seguiu o único heartbeat visível em bem menos de um segundo — rápido o suficiente para ser **unknown** se isso reflete um host atento clicando em Admitir imediatamente, ou alguma condição de auto-admissão (ex. host já ativo na chamada); nenhuma evidência aqui distingue os dois casos.

---

## 6. Alocação de JID do convidado (tested)

A admissão chega como um push `group_update`/`group_info` comum vindo de `<call-id>@call`, com duas entradas `<user>` — host e convidado lado a lado:

| Campo | Entrada do host | Entrada do convidado |
|-------|-----------|--------------|
| `jid` | `48615137533978` (dispositivo 24 sob `<device>`) | `29554559176938` (dispositivo 0) |
| `type` | `admin` | *(ausente — sem papel elevado)* |
| `account_kind` | *(ausente)* | `guest` |
| `push_name` | *(ausente nesta entrada)* | `Baron als Gast ohne wa` — o nome enviado em `link_join` §4.2, copiado literalmente para o roster |
| `state` | `connected` | `connected` |
| `platform` do dispositivo | `web` | `web` |
| `pid` do dispositivo | `0` | `1` |

O JID do convidado (`29554559176938`) está na mesma classe de forma de endereço (`type=1`, `domainType=1`, isto é, estilo LID, §2) que o do host, alocado na hora pelo servidor para esta chamada — não é a identidade de conta da própria sessão que entrou. O `pid` do dispositivo (`1` para o convidado) corresponde ao `self_pid="1"` do bloco de relay na mesma stanza (§7) — o id de participante por dispositivo do roster e o próprio id de participante do relay são o mesmo número.

**Unknown**: se este JID de convidado é reutilizado entre entradas repetidas do mesmo link pelo mesmo navegador/sessão, por quanto tempo é mantido, ou se é visível para o host além de `push_name` e `account_kind`.

---

## 7. Entrega de relay e chave na admissão (tested)

A mesma stanza de admissão carrega um bloco `<relay>`, irmão de `<group_info>`, dando ao convidado tudo que precisa para alcançar a mídia sem mais round trips. Os campos correspondem à gramática do WA_CALL_SIGNALING.md §8.2; esta seção adiciona detalhe concreto no nível da rede que aquele relatório deixara aberto.

| Filho | Contagem observada | Notas |
|-------|-----------|-------|
| `<token id=N>` | 3 (ids 0, 1, 2) | binário bruto, 194 bytes cada |
| `<auth_token id=0>` | 1 | binário bruto, 70 bytes |
| `<key>` | 1 | 24 bytes na rede — mas esses 24 bytes são, em si, texto ASCII de uma string base64, que ao decodificar novamente dá uma chave bruta de 16 bytes |
| `<hbh_key>` | 1 | 40 bytes na rede — mesmo padrão: texto ASCII base64, decodificando para 30 bytes brutos |
| `<te2 relay_id auth_token_id token_id domain_name relay_name c2r_rtt>` | 6 (2 relays: `edgeray-ham3-1.wt.whatsapp.com`/`ham3c01`, `edgeray-ber1-1.wt.whatsapp.com`/`ber1c01`) | nenhum `<te>` presente — confirma a regra "nunca os dois juntos", esta chamada usou `te2` |
| atributos de relay | `attribute_padding`, `transaction-id`, `self_pid`, `uuid`, `participant_uuid` | `self_pid="1"` corresponde ao `pid` do próprio dispositivo do convidado em `group_info` (§6) |
| `<participant pid jid>` | não presente | o filho de mapeamento participant-id-para-JID da seção 8.2 não foi visto nesta captura de 2 partes; unknown se aparece só em chamadas de grupo maiores |

Apenas `<key>` e `<hbh_key>` carregam a forma de codificação dupla (nó binário contendo texto ASCII base64); `<token>` e `<auth_token>` são binário bruto simples, com uma única decodificação. O que essa camada dupla ganha em relação a enviar bytes brutos diretamente é **unknown** (um resquício de um transporte orientado a texto internamente, inferred).

Um filho `<voip_settings uncompressed="1">`, também irmão de `<group_info>`/`<relay>`, carrega um blob JSON de parâmetros do motor (não comprimido nesta captura, consistente com a nota do WA_CALL_SIGNALING.md §5.2 de que payloads comprimidos são rejeitados em pelo menos um caminho). Dentro dele, sob o objeto `fs` (feature-switch): `"guest_calling_logging_enabled": "true"` — a única chave específica de convidado encontrada em um documento de configuração genérico de ~32 KB (`aec`, `bwe`, `decode`, `encode`, `sfu`, `rc`, ... — todos ajustes genéricos do motor de mídia, sem relação com entrada de convidado). Os eventos de telemetria enviados pelo cliente que entra em torno desta chamada usam de forma independente a string de categoria `guest_calling` (vista nos próprios blobs `w:stats`/WAM do cliente), correspondendo à nomenclatura da chave de configuração.

Dois irmãos inofensivos, `<uploadfieldstat/>` e `<userrate interval="0"/>`, viajam junto na mesma stanza; sem conteúdo específico de convidado.

O cliente envia imediatamente um `<ack class="call" type="group_update">` simples para este push (sem conteúdo) — tratamento ordinário conforme WA_CALL_SIGNALING.md §3.3 (group_update não está no conjunto de tags sem ack imediato).

---

## 8. Tráfego pós-admissão (tested, breve)

Uma vez admitido, o tráfego é indistinguível de uma chamada normal no mesmo JID de call-id: `mute_v2` (o host muta o convidado imediatamente após a admissão nesta captura), `transport` (`transport-message-type="4"`, um filho `<net medium="2" protocol="0"/>`), `relaylatency` (ambas as direções, cada uma carregando um `<te latency relay_name>` referenciando os nomes de relay da §7), e mudanças de estado de `video` (`state="6"`, isto é, `Stopped` conforme a tabela `kVideoState*` do WA_CALL_SIGNALING.md §13, repetido três vezes em rápida sucessão durante a configuração). Nada disso é específico de link; ver WA_CALL_SIGNALING.md §§8, 13 para a semântica geral.

---

## 9. Link de vídeo vs. apenas-áudio — diferenças observadas (tested)

| Aspecto | Link de vídeo | Link apenas-áudio |
|--------|-----------|------------------|
| Atributo `media` de `link_query`/`link_join` | `video` | `audio` |
| Filhos de `link_join` | `<audio>`, `<video>`, `<net>`, `<capability>` | `<audio>`, `<net>`, `<capability>` — `<video>` omitido |
| `media` do ack de `waiting_room` | `video` | `audio` |
| Mecânica de sala de espera / elegibilidade de convidado | idêntica | idêntica |

Nenhuma outra diferença de protocolo foi observada entre os dois; o tipo de mídia é carregado de ponta a ponta como um atributo simples, não uma família de stanza diferente.

---

## 10. Diferenças de uma chamada normal 1:1 ou em grupo

| Aspecto | Chamada normal 1:1 / em grupo (WA_CALL_SIGNALING.md) | Entrada de convidado via link (este relatório) |
|--------|------------------------------------------------|-------------------------------|
| Stanza de entrada | `offer` para um JID de peer/grupo conhecido | `link_query` depois `link_join` para o domínio puro `call` |
| Chave da chamada | `Message.call.callKey` criptografado por Signal, por dispositivo, no offer | não observada na admissão desta captura; o convidado recebe material de relay/chave (§7) diretamente, não uma chave de chamada embrulhada em Signal — consistente com um convidado não ter sessão Signal pairwise com o host |
| Identidade de chamador/chamado | ambos os lados são JIDs conhecidos antes da chamada começar | a identidade real do lado que entra não é exposta no roster; o servidor aloca um JID novo e o rotula `account_kind="guest"` |
| Admissão | nenhuma — offer/accept é o único portão | sala de espera opcional: `waiting_room enabled`, mantido até um admit (não observado, do lado do host) |
| Entrega do roster | `group_info` dentro do offer ou uma atualização posterior | push `group_update`/`group_info` de `<call-id>@call`, agrupado com `<relay>` e `<voip_settings>` na mesma stanza |
| Endereçamento de JID | JID de peer/grupo durante toda a chamada | domínio puro `call` até existir um call-id, depois `<call-id>@call` |

A chave de chamada por dispositivo ausente para o convidado (linha 2) é a diferença mais significativa e é **tested** apenas como uma ausência nesta captura — não confirmada como regra de protocolo; é também consistente com a nota do WA_CALL_SIGNALING.md §9.2 de que offers de grupo não carregam chave por dispositivo e chaves são reenviadas fora de banda (`enc_rekey`). Se um convidado algum dia recebe um `enc_rekey` não foi observado em nenhuma das duas janelas de captura usadas aqui.

---

## 11. Casos de erro / pegadinhas

| Sintoma | Causa | Correção / nota |
|---------|-------|-----------|
| Ack de `link_query` sem `call-id` | o link ainda não foi resolvido para uma chamada em execução/iniciável | normal para uma prévia simples; o call-id só chega no ack de `link_join` |
| Convidado travado após o ack de `link_join`, só troca heartbeats | sala de espera habilitada e o host ainda não admitiu | ação do lado do host necessária; não visível a partir da conexão do convidado |
| `link_join` carrega um filho `<video>` para um link apenas-áudio | bug do cliente — as duas capturas mostram que este filho precisa estar totalmente ausente para `media="audio"` | omitir `<video>` para entradas apenas-áudio |
| O próprio JID da conta do convidado aparece no roster da chamada em vez de um JID de convidado novo | caminho de entrada errado (`offer`/entrada em grupo comum em vez de `link_join`) | usar `link_query`→`link_join` para obter o tratamento `account_kind="guest"` |
| Convidado não recebe chave de chamada mas recebe material de relay/chave | esperado para este caminho (§10) — o convidado não recebe uma chave embrulhada em Signal como um chamado normal | não tratar como falha de decriptação |

---

## 12. Distinções importantes

| Não confundir | Com |
|-----------------|------|
| **Token** do link de chamada (22 caracteres, voltado para a URL) | **Call-id** (32 caracteres hex, voltado para o protocolo, aparece só depois de `link_join`) |
| JID do domínio call puro (pré-call-id) | `<call-id>@call` (pós-call-id) — ambos são "o JID do domínio call" em estágios diferentes, não dois endereços não relacionados |
| `is_guest_eligible` (configuração do link: *qualquer um* pode entrar neste link como convidado) | `waiting_room enabled` (configuração do link: convidados são mantidos para admissão) — flags independentes, ambas ecoadas nos mesmos acks |
| `push_name` do convidado em `link_join` (texto livre, escolhido a cada entrada) | o nome de perfil do WhatsApp da própria conta que entra (não é o que acaba no roster para uma entrada de convidado) |
| Bytes de `<key>` / `<hbh_key>` na rede (nó binário contendo texto ASCII base64, precisa de decodificação dupla) | Bytes de `<token>` / `<auth_token>` na rede (binário bruto simples, decodificação única) |
| Alocação de JID de convidado (lado do servidor, na admissão, por chamada) | JIDs LID/PN normais (nível de conta, persistentes) |

---

## 13. Fluxo completo (entrada de convidado, a partir da captura)

```
[Guest client]  already has a chatd session (own identity, not used for the call)
     │  <call to="@call"><link_query token media/></call>
     ▼
[WA Server]  resolves the token
     │  ack: link_creator, media, token, <guest is_guest_eligible/>, <waiting_room enabled/>
     ▼
[Guest client]  <call to="@call"><link_join token media push_name><audio/>[<video/>]<net/><capability/></link_join></call>
     ▼
[WA Server]  starts/resolves the call
     │  ack: <waiting_room link-token media call-id call-creator enabled/>, <guest is_guest_eligible/>
     ▼
[Guest client]  learns call-id → addresses it as <call-id>@call from now on
     │  <call to="<call-id>@call"><heartbeat call-id call-creator type="waiting_room"/></call>  (repeats)
     ▼
[Host, out of band — not in this capture]  taps Admit (waiting_room_toggle/_admit)
     ▼
[WA Server]  <call from="<call-id>@call"><group_update><group_info ...>
                 <user host .../><user account_kind="guest" push_name jid=<allocated> .../>
              </group_info>
              <relay token×N auth_token key hbh_key te2×N/>
              <voip_settings uncompressed fs.guest_calling_logging_enabled=true/>
              </group_update></call>
     │  ack: <ack class="call" type="group_update"/>
     ▼
[Both]  ordinary call traffic on <call-id>@call: mute_v2, transport, relaylatency, video state
              (see WA_CALL_SIGNALING.md §§8, 13 for generic semantics)
```

---

## 14. Registro do convidado (cliente web, tested)

Uma sessão de navegador genuinamente sem conta — sem nenhum login prévio no WhatsApp — registra uma identidade descartável antes mesmo de enviar `link_query`. Evidência: uma captura CDP de uma sessão conduzida por um humano abrindo um link de chamada real em um navegador; nada no fluxo abaixo foi automatizado ou roteirizado além do ponto de abrir a página e digitar um nome.

```
GET https://v.whatsapp.net/v2/guest_reg?...
```

| Parâmetro | Exemplo | Significado |
|-------|---------|---------|
| `mcc` / `mnc` | `310` / `999` | códigos de operadora fictícios |
| `lc` / `lg` | locale (ex. `DE`/`DE`) | locale da interface |
| `device_id` | uuid | id de dispositivo gerado pelo navegador |
| `access_session_id` | uuid | id da sessão |
| `authkey` | base64, 32 bytes | chave pública estática Curve25519 do Noise |
| `e_regid` | base64, 4 bytes | id de registro |
| `e_keytype` | base64, 1 byte | `0x05` = Curve25519 |
| `e_ident` | base64, 32 bytes | chave pública de identidade Signal |
| `e_skey_id` / `e_skey_val` / `e_skey_sig` | — | id da signed-prekey, chave pública (32 B), assinatura (64 B) |
| `os_name` / `os_version` / `browser` / `browser_version` | fatos de UA | fingerprint do cliente |
| `web_build_version` | ex. `2.3000.1052682108` | build do cliente |
| `guest_type` | `guest_calling` | marca isto como um registro de convidado de link de chamada |
| `invite_code` | o token do link | em qual link o convidado está entrando |
| `guest_name` | texto livre | o nome de exibição que o convidado digitou |
| `id` | 20 bytes brutos | ocupa o espaço que um número de telefone preenche no registro normal |
| `backup_token` | 20 bytes brutos | igual a `id` nesta captura |

A resposta (200, corpo não capturado) devolve as credenciais com as quais o convidado faz login. Estruturalmente, este é o **mesmo pacote de registro** (regid, chave de identidade, signed prekey, assinatura) do registro normal do WhatsApp — `guest_type`/`invite_code`/`guest_name` são os únicos acréscimos específicos de convidado, e `guest_reg` é um endpoint distinto do caminho normal `/v2/reg` (**found**, hostnames/caminhos distintos observados; não verificado cruzadamente com o próprio código de registro do Android aqui — ver a nota de escopo de `WA_MOBILE_REGISTRATION` se esse tópico for coberto em outro lugar).

Uma entrada de allow-list de CSP para um provedor de desafio anti-automação estava presente na página, e o código de bootstrap do convidado referencia um conceito de captcha/desafio, mas nenhum token de desafio foi exigido ou enviado nesta sessão de baixo volume, conduzida por humano (**tested**: ausente aqui; **unknown**: em quais condições ele é acionado — uma gate de anti-abuso baseada em risco é a hipótese de trabalho, não confirmada). Este relatório não investiga esse controle mais a fundo; fazê-lo significaria sondar um mecanismo anti-abuso, o que está fora do escopo aqui.

Evidência do lado do cliente de que este é um caminho de código distinto e consciente de convidado (found, subconjunto representativo de muitos nomes de módulo semelhantes vistos): um módulo de tratamento de nome de participante e um módulo de mensageria/persistência de job específico de convidado, distintos dos equivalentes do cliente de chat normal, além de um módulo literalmente nomeado para "esta UI de chamada está rodando para um convidado".

## 15. Transporte Noise para uma sessão de convidado (tested)

A identidade de convidado registrada faz login sobre o **mesmo** transporte já documentado em [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md): um WebSocket com prefixo de tamanho para `wss://web.whatsapp.com/ws/chat` (porta alternativa observada `5222`), o prólogo `WA` + versão, e a mesma sequência de mensagens Noise XX (ClientHello → ServerHello com cadeia de certificado → ClientFinish criptografado carregando a chave estática/de identidade → o primeiro `ClientPayload` criptografado). Nada no framing do handshake difere para um convidado; isto confirma de forma independente, a partir de uma segunda plataforma de cliente (um navegador, não o app Android cobertos em outras partes deste projeto), que convidados de link de chamada são clientes Noise XX ordinários, não um protocolo leve paralelo.

Um fato em nível de proto que isto adiciona: `ClientPayload` já define um campo `AccountType` (`DEFAULT = 0`, `GUEST = 1`) no esquema de proto compartilhado do WhatsApp. O [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) encontrou esse campo presente, mas nunca escrito no Android (nenhum caminho de código o define — o Android nunca é um convidado). Uma sessão de convidado no navegador é o cliente que de fato o define: `accountType = GUEST` é a única diferença de `ClientPayload` entre um convidado e um login normal de cliente, além de a identidade vir de `guest_reg` (§14) em vez do registro normal por telefone e não carregar nenhum dado de pareamento de dispositivo.

O detalhe mais fino, por função (o código exato que monta um `ClientPayload` de convidado, e o corpo da resposta de `guest_reg`) está em bundles de script carregados de forma lazy e vinculados à sessão, que expiram com a página; obtê-lo exige uma nova captura ao vivo com acesso ao código-fonte do script, não uma busca estática. O que já foi estabelecido acima — o transporte é Noise XX sem modificação, o pacote de identidade é um pacote de registro normal, e o único campo marcado é `accountType = GUEST` — não depende de recuperar esse código-fonte.

---

## 16. Desconhecidos

| Item | Status |
|------|--------|
| Local de geração do token (gerado pelo cliente vs. atribuído pelo servidor) | o ponto de chamada de `createCallLink` não carrega argumento de token (found); a origem real é nativa (unknown) |
| Se uma sessão de navegador genuinamente sem conta produz a mesma sequência de stanzas decifradas | parcialmente resolvido (§14–§15): a sessão se registra via `guest_reg` e faz login sobre o mesmo transporte Noise XX com `ClientPayload.accountType = GUEST`; o conteúdo decifrado de `link_query`/`link_join` em si não foi capturado para essa sessão |
| Forma na rede da ação de admit do lado do host (`waiting_room_toggle`/`_admit`) | não está nesta captura (unilateral); descrita apenas a partir dos dados estáticos do WA_CALL_SIGNALING.md §10.3 |
| Por que a admissão seguiu o único heartbeat observado tão rápido | host atento vs. condição de auto-admissão — não distinguível a partir desta evidência |
| Tempo de vida / reutilização do JID de convidado entre entradas repetidas | não observado |
| Se um convidado algum dia recebe `enc_rekey` ou qualquer chave de chamada embrulhada em Signal | não observado em nenhuma das duas janelas de captura |
| Mapeamento `<participant pid jid>` sob `<relay>` | não presente nesta captura de 2 partes; unknown se chamadas em grupo com convidados o usam |
| Propósito da codificação dupla em base64 em `<key>`/`<hbh_key>` vs. `<token>`/`<auth_token>` bruto | unknown |
| `connected-limit` como limite configurável pelo cliente vs. sempre atribuído pelo servidor | nenhum setter do lado do cliente encontrado (found: apenas retornado pelo servidor) |
| Limites de taxa / controles de abuso na criação de link ou entrada de convidados | nada encontrado do lado do cliente; comportamento do servidor unknown |
</content>
