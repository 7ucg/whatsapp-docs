<!-- src-sha1: 287eecdda43f9253685bac27a2f3bea697aa3989 -->
# WhatsApp Enquetes — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-11-01
**Escopo:** família de mensagens de enquete (`pollCreationMessage` até `pollCreationMessageV6`, `pollCreationOptionImageMessage`, `pollAddOptionMessage`, `pollUpdateMessage`, `pollResultSnapshotMessage`/`V3`), histórico de versões e lógica de seleção de envio/recebimento, validação e limites de criação, vinculação de opção com imagem, modelo de seleção e privacidade de voto, multi-seleção vs. seleção única, edição de enquete, snapshot de resultado no momento do forward, feature flags

---

## 1. O que é

Uma enquete é um sub-objeto `Message` (`PollCreationMessage`, reutilizado sem alteração em seis campos de nível superior versionados) carregando uma pergunta, uma lista de opções, um limite de seleção, e configurações opcionais de quiz/tempo-final/visibilidade. Votos (`pollUpdateMessage`), opções adicionadas (`pollAddOptionMessage`) e edições (`secretEncryptedMessage`) são mensagens de acompanhamento separadas vinculadas ao id da mensagem de criação e com chave derivada de seu segredo por mensagem; essa criptografia (casos de uso HKDF, AES-GCM, AAD, retry de identidade) é coberta em [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) e não é repetida aqui. Este relatório cobre a camada de tipo de mensagem: qual campo carrega o quê, como o cliente escolhe entre eles, validação e limites, e o que os handlers específicos de enquete fazem com os payloads decriptados. Todas as descobertas são análise estática do APK decompilado 2.26.41.6 (fontes Java sob `java_src/`, mais `res/values/strings.xml`); nada foi capturado no wire. Tiers: **found** = lido em código/recursos, **inferred** = deduzido do código, **unknown** = não resolvido.

| Entidade | Campo em `Message` | Tipo proto | Papel |
|--------|--------------------|-----------|------|
| `pollCreationMessage` | **49** | `PollCreationMessage` (`DTM`) | slot de criação original |
| `pollCreationMessageV2` | **60** | `PollCreationMessage` | criação em um chat de subgrupo padrão de comunidade |
| `pollCreationMessageV3` | **64** | `PollCreationMessage` | slot de criação de enquete simples (padrão atual para enquetes comuns) |
| `pollCreationMessageV4` | **93** | `FutureProofMessage` (`BD2`) | wrapper de compatibilidade futura em torno de um `Message.pollCreationMessage` interno (campo 49) |
| `pollCreationMessageV5` | **111** | `PollCreationMessage` | slot de criação de quiz |
| `pollCreationMessageV6` | **119** | `PollCreationMessage` | slot de enquete estendida (tempo final / ocultar-nome-de-votante / permitir-adicionar-opção) |
| `pollCreationOptionImageMessage` | **90** | `FutureProofMessage` | uma imagem de opção de enquete com imagem, vinculada à futura enquete via `messageAssociation` |
| `pollAddOptionMessage` | **121** | `PollAddOptionMessage` (`C30556DRc`) | adiciona uma opção a uma enquete existente |
| `pollUpdateMessage` | **50** | `PollUpdateMessage` (`DSG`) | voto (criptografado) ou metadado de voto |
| `pollResultSnapshotMessage` | **88** | `PollResultSnapshotMessage` (`DSF`) | snapshot estático de resultado, enquete reenviada a outro chat |
| `pollResultSnapshotMessageV3` | **115** | `PollResultSnapshotMessage` | mesmo, variante quiz (contagens de voto zeradas) |

Números de campo verificados diretamente contra `C30628DTw` (a classe proto `Message`), que declara todas as onze constantes `POLL_*_FIELD_NUMBER` correspondendo à tabela acima.

---

## 2. `PollCreationMessage` (`DTM`)

### 2.1 Campos (found)

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `encKey` | **1** | bytes | presente no wire mas não usado pelos handlers lidos nesta passagem (votos usam o `messageSecret` por mensagem, não este campo; ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3) |
| `name` | **2** | string | pergunta da enquete, máx. 5000 chars, obrigatório |
| `options` | **3** | repeated `Option` | opções de resposta |
| `selectableOptionsCount` | **4** | uint32 | limite de seleção, obrigatório (§11) |
| `contextInfo` | **5** | `ContextInfo` | contexto padrão |
| `pollContentType` | **6** | enum `PollContentType` (`E25`) | `UNKNOWN`=0 (`A03`), `TEXT`=1 (`A02`), `IMAGE`=2 (`A01`) |
| `pollType` | **7** | enum `PollType` (`EnumC32108E1g`) | `POLL`=0 (`A01`), `QUIZ`=1 (`A02`) |
| `correctAnswer` | **8** | `Option` | opção de resposta correta do quiz, obrigatório quando `pollType=QUIZ` |
| `endTime` | **9** | int64 | timestamp de encerramento da enquete (ms) |
| `hideParticipantName` | **10** | bool | "Ocultar nomes dos votantes" (§10) |
| `allowAddOption` | **11** | bool | "Permitir que outros adicionem opções" (§6) |

`PollCreationMessage.Option` (`C30529DQb`): `optionName` **1** (string), `optionHash` **2** (string, populado apenas para opções de enquete com imagem, §5).

### 2.2 Representação local

O cliente armazena uma enquete parseada como `C13J` (variante quiz com imagem `C13K`), com opções como objetos `C33283EeZ` carregando o nome bruto (`A04`), um digest SHA-256 do nome computado localmente (`A02`, §9.1) e, para opções com imagem, o `optionHash` do wire (`A08`).

---

## 3. Histórico de versões

### 3.1 Qual campo é usado para enviar (found, `F2N.A00`/`A02`)

```text
pollType == QUIZ (correct answer set)              -> pollCreationMessageV5
chat is a community default-subgroup (group_type 3) -> pollCreationMessageV2
else:
  hideParticipantName / endTime / allowAddOption set -> pollCreationMessageV6
  none of those set                                   -> pollCreationMessageV3
```

`pollCreationMessageV4` nunca é populado pelo caminho de envio lido nesta passagem; ele só aparece no recebimento (§3.3). A verificação de comunidade reutiliza o mesmo predicado `group_type == 3` do fallback de reação em texto puro em [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.2 (`C0GQ.A0A(chat) == 3`, definido a partir de `isDefaultSubgroup_`); por que uma enquete de subgrupo padrão recebe seu próprio slot versionado em vez de V3/V6 não é explicado no código lido aqui (inferred: ordenação histórica de rollout, já que o número de campo de V2 é o mais baixo do conjunto estendido).

Então na prática: **V3** é o slot atual para uma enquete comum de múltipla/única escolha sem extras, **V6** é o atual para uma enquete usando tempo final, nomes de votante ocultos ou adicionar-opção, **V5** é o atual para quizzes, e **V2** é uma variante específica de subgrupo de comunidade da mesma forma base. **V1** (o campo não versionado 49) e **V4** não são escolhidos pelo remetente nesta build.

### 3.2 `pollCreationMessageV4` = wrapper de compatibilidade futura (found, `F2N.CM7`)

O tipo proto de V4 é `FutureProofMessage` (`BD2`, campo único `message` = um `Message` interno). No recebimento, quando o slot V4 está populado, o cliente desembrulha `BD2.message_` e lê o próprio campo `pollCreationMessage` (49) *dessa* mensagem interna como o `PollCreationMessage` real. Este é um envelope de fallback genuíno, não um campo morto: um remetente que precisa emitir uma variante de enquete mais nova/indefinida pode embrulhar uma enquete básica (com formato de campo-49) dentro de V4 para que clientes mais antigos — que só entendem o desembrulho genérico de `FutureProofMessage`, não o slot mais novo — ainda renderizem uma enquete simples. Nenhum caminho de código nesta passagem popula V4 no envio, então isso existe para compatibilidade futura/retroativa entre versões de cliente, não para algo que o próprio cliente 2.26.41.6 emita (inferred).

### 3.3 Seleção no recebimento e downgrade (found, aproximado; o decompiler perdeu parte da estrutura de ramo)

`F2N.CM7` verifica os bitfields de `Message` na ordem V1 → V2 → V4 → V5 → V6 → fallback-V3 e faz o parse de qualquer campo versionado populado para o mesmo validador (`F2N.A01`, §4). Três flags controlam a aceitação dos campos extra de V6 no recebimento; quando uma flag está desativada a enquete é **rebaixada** (parseada como o placeholder genérico de compatibilidade futura em vez de uma bolha de enquete) em vez de rejeitada completamente:

| Campo extra | Gate | Efeito quando o gate está desativado |
|-------------|------|--------------------------|
| `endTime` | AB int **24884** (`receivingEnabled`) | logado `poll downgraded to FMessageFuture (receiving disabled)`, não renderizado como enquete |
| `hideParticipantName` | AB int **24885** | downgrade (polaridade exata da verificação não totalmente resolvida a partir do fluxo de controle decompilado) |
| `allowAddOption` | AB int **25758** | downgrade |

O aninhamento exato dessas três condições não pôde ser totalmente reconstruído (o JADX reporta blocos duplicados/inalcançáveis em `F2N.CM7`); as flags de gate e o resultado de downgrade são found, a combinação booleana precisa é inferred.

### 3.4 Gate de conteúdo de imagem

`pollContentType = IMAGE` só é respeitado no caminho de parse V3/V5 quando o bit para `pollContentType` está definido; se estiver definido mas o valor não for `IMAGE`, a mensagem é rejeitada (`return null`, cai no parser genérico) em vez de silenciosamente tratada como texto.

---

## 4. Validação de criação (found, `F2N.A01`)

Validador único compartilhado por todos os campos de criação versionados. Lança exceção, código de erro **11** salvo indicação:

| Verificação | Regra | String de erro |
|-------|------|--------------|
| Nome presente | o bit de `name` deve estar definido | `poll_creation_missing_name` |
| Comprimento do nome | 1–5000 chars (salvo se um contexto de parse permissivo contornar isso, §4.1) | `poll_creation_invalid_name` |
| Resposta correta do quiz | se `pollType=QUIZ`, o bit de `correctAnswer` deve estar definido | `poll_creation_missing_correct_answer` |
| Opções presentes | pelo menos uma opção, salvo se o bypass de zero opções (§4.1) se aplicar | `poll_creation_missing_options` |
| Contagem de opções (inferior) | ≥ 2 opções (0 sob o bypass) | `poll_creation_invalid_options_count` |
| Contagem de opções (superior) | ≤ `min(AB int 1408, 12)` — 12 é um teto rígido do cliente independente do valor do servidor | `poll_creation_invalid_options_count` |
| Comprimento do nome da opção | 1–2500 chars por opção | `poll_creation_invalid_option` |
| Nome da resposta correta | se quiz, `correctAnswer.optionName` deve ser não-vazio | `poll_creation_missing_correct_answer_name` |
| Opções duplicadas | nomes de opção devem ser únicos | `poll_creation_duplicate_options` |
| Opções duplicadas com trim | sob a flag AB **25758**, nomes com espaços removidos também devem ser únicos | `poll_creation_duplicate_trimmed_options` |
| Resposta correta corresponde a uma opção | o nome da resposta correta do quiz deve ser igual ao nome de uma das opções | `poll_creation_unmatched_correct_answer` |
| Contagem selecionável presente | o bit de `selectableOptionsCount` deve estar definido | `poll_creation_missing_selectable_options_count` |
| Intervalo da contagem selecionável | `0 <= selectableOptionsCount <= options.size()` (ou `<= min(1408,12)` sob o bypass) | `poll_creation_invalid_selectable_options_count` |

### 4.1 Bypass de zero-opção / permissivo (caminho de código found, semântica inferred)

Um booleano local (`z`) computado a partir da flag AB booleana **37909**, consultado apenas quando um contador de contexto de parse interno é igual a 1, relaxa a contagem mínima de opções para 0 e amplia o teto da contagem selecionável para o limite bruto `min(1408,12)` em vez de `options.size()`. O valor de contexto de parse ao qual isso corresponde (recebimento normal vs. algum outro caminho de ingestão, ex. sincronização de histórico) não foi resolvido; isto é registrado como found-mas-não-explicado em vez de um recurso confirmado e visível ao usuário de "enquete sem opções".

### 4.2 Bypass de nome permissivo / sincronização de histórico

Uma flag de contexto separada (`c33371Eg0.A0W`) ignora tanto a verificação de comprimento de nome quanto (equivalentemente, em `F39`, §9) a verificação de comprimento de nome do snapshot de resultado, aceitando a string bruta sem verificação. Consistente com um caminho de parse de fonte confiável (ex. re-importação local de histórico) em vez de um recebimento de rede normal; não confirmado independentemente.

---

## 5. Opções de enquete com imagem: `pollCreationOptionImageMessage`

### 5.1 Estrutura e vinculação (found)

`pollCreationOptionImageMessage` (campo 90) embrulha um `ImageMessage` enviado comumente dentro de um `FutureProofMessage` — a imagem **não** é embutida em `PollCreationMessage.Option`. Cada imagem de opção é enviada como sua própria mensagem filha, associada à enquete (ainda não enviada) via `MessageContextInfo.messageAssociation`, tipo de associação `MEDIA_POLL = 6` (`AnonymousClass122.MEDIA_POLL`; este é o valor de enum desta build — uma build anterior o tinha em 7, o valor numérico não é estável entre versões e deve ser relido a cada release). O helper do lado de envio "MediaPollAssociationProvider" (em `C20M`) conta linhas de `message_association` para o id de linha da enquete pai e tipo de associação `6`; quando a contagem alcança a contagem de opções, todas as imagens de opção são consideradas enviadas e o cliente procede a enviar a própria enquete com `pollContentType = IMAGE`.

### 5.2 Hash de opção para opções com imagem (inferred, carregado de uma build anterior, não re-derivado linha a linha na 2.26.41.6)

Para opções de texto simples o campo `optionHash` do wire é deixado vazio; o único hash computado para uma opção de texto simples é o digest de busca local `C13J.A00`:

```text
optionHash(text option) = Base64(SHA-256(UTF8(optionName)))
```

(confirmado diretamente na 2.26.41.6, §9.1 — este é o hash usado para corresponder seleções de voto, não o campo proto `optionHash`). Para opções de **imagem** o campo proto `optionHash` é populado; um rastreamento de versão anterior da sequência de envio descobriu que ele combina o hash do nome da opção com o `fileSha256` da imagem enviada:

```text
nameHash   = lowerHex(SHA-256(UTF8(optionName)))
imageHash  = base64(imageMessage.fileSha256)
optionHash = lowerHex(SHA-256(UTF8(nameHash + imageHash)))
```

Esta fórmula não foi re-verificada contra o código da 2.26.41.6 nesta passagem (a classe que computa não foi localizada); ela é carregada como inferred e deve ser reverificada antes de ser usada com confiança.

---

## 6. `pollAddOptionMessage` (`C30556DRc`, campo 121)

### 6.1 Campos (found)

`pollCreationMessageKey` **1** (`MessageKey`), `addOption` **2** (`PollCreationMessage.Option`), `metadata` **3** (`PollUpdateMessageMetadata`, mesmo formato do voto, §7).

### 6.2 Envio (found, `F2L.ADr`)

Constrói um `Option` a partir do novo nome (e, para enquetes com imagem, seu hash), anexa a chave da enquete de origem, e — para chats 1:1, quando não é um contexto de edição — resolve a identidade do remetente através da fronteira LID/PN da mesma forma que a camada de segredo de mensagem faz para outros add-ons (ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.1 etapa 4). A opção *não* é em si criptografada com segredo nesta camada como um `pollUpdateMessage` é: o payload de adicionar-opção trafega como um campo de mensagem normal; o que é embrulhado em `secretEncryptedMessage` (tipo `POLL_ADD_OPTION`) é a tentativa de adicionar-opção como um todo quando ela precisa trafegar pelo esquema de segredo de mensagem (§8).

### 6.3 Validação no recebimento (found, `F2L.CM7`)

| Verificação | Erro |
|-------|-------|
| Feature gate: AB int **25758** deve ser não-zero | erro **10017** |
| `pollCreationMessageKey` presente | `poll_add_option_missing_poll_message_key` |
| `addOption` presente | `poll_add_option_missing_poll_option` |
| Nome da opção não-vazio, ≤ 2500 chars | `poll_add_option_invalid_option` |

O objeto local resultante é criptografado com segredo para transporte usando o caso de uso `Poll Add Option` (chamada confirmada ao helper de segredo de mensagem com `AnonymousClass122.POLL_ADD_OPTION` como a tag de associação). Opções adicionadas são rastreadas para correspondência com opções existentes da mesma forma que opções de enquete com imagem (tipo de associação `POLL_ADD_OPTION = 18`).

---

## 7. `pollUpdateMessage` (voto e metadado de voto)

A criptografia completa (caso de uso HKDF `Poll Vote`, AAD, AES-GCM, retry de identidade LID/PN) está em [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3–§7; esta seção cobre apenas o que o handler de voto de enquete (`DUA`, estende `F2P`) faz com o texto plano.

### 7.1 Dois caminhos de envio/recebimento (found)

A flag AB booleana **6772** seleciona entre:
- **ativa** (atual): um helper de criptografia compartilhado (`C33285Eeb`) constrói o texto cifrado e o `MessageKey`; o voto é retentado a partir de um par `(iv, payload)` armazenado anteriormente quando presente, em vez de recriptografar.
- **desativada** (legado): um ramo inline em `DUA` faz a mesma chamada HKDF/AES-GCM diretamente, derivando a identidade de remetente alvo ela mesma (próprio LID para votos na própria enquete do votante, senão o JID resolvido do alvo do voto).

### 7.2 Payload de voto: `PollVoteMessage` (`DPF`)

Campo único `selectedOptions` **1**, bytes repetidos — cada entrada é um digest SHA-256 de 32 bytes do nome da opção (§9.1), não um índice. `MessageAddOnPollVoteUtils` (`AbstractC33199EdC`) valida a seleção decriptada:

| Verificação | Regra | Tag de log |
|-------|------|---------|
| Tamanho da seleção | ≤ 12 **e** ≤ o `selectableOptionsCount` da enquete (quando > 0) | `poll_vote_invalid_options_count` |
| Formato do hash | cada hash selecionado decodifica para exatamente 32 bytes | `poll_vote_invalid_option_hashes` |
| Duplicatas | nenhum hash repetido em um voto | `poll_vote_duplicate_option_hashes` |
| Resolução | todo hash selecionado deve corresponder a um dos hashes de opção conhecidos (não removidos) da enquete | retorna um resultado de erro, sem correspondência -> voto rejeitado |

### 7.3 Tempo final e metadados (found, `DUA.A01`)

Um voto cujo `senderTimestampMs` é posterior ao `endTime` da enquete é rejeitado (`poll_update_past_end_time`); sob a flag AB booleana **2321** um evento de voto rejeitado adicionalmente alimenta um contador de telemetria (`N0e`). O `metadata` do voto (`pollNameHash`, `lastEditStanzaId`) é marcado no envio apenas sob a flag AB booleana **31593**; no recebimento, um bloco de metadado ausente/vazio é logado `"unstamped"` (não rejeitado por si só) enquanto uma marca *incompatível* (verificada por `C32977EZa`) descarta o voto com `poll_update_tc_drop`. Esse metadado existe para que um cliente possa detectar que está votando contra uma enquete cujo histórico de edição ainda não alcançou.

---

## 8. Edição de enquete (`secretEncryptedMessage`, `secretEncType = POLL_EDIT`)

Carregada dentro do wrapper genérico `secretEncryptedMessage` (campo 82), não um transportador específico de enquete; ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §5/§7.4 para o envelope, AAD, e a tabela de código de erro (`poll_edit_message_stanza_invalid`, gate AB int **24886**, erro **10016**). A validação específica de enquete (`F3Y`, `SecretEncryptedMessageDeserializationValidator`) exige:

- a mensagem interna é FMessage tipo 66 e é uma enquete tanto antes quanto depois da edição;
- `endTime`, `hideParticipantName`, `allowAddOption`, `selectableOptionsCount` e `pollType` são **inalterados** entre a enquete armazenada e a editada — apenas o texto da pergunta e/ou os textos das opções podem diferir;
- correspondência de opção: com uma flag por chat (`EOI.A01()`, id não resolvido) ativa, opções editadas são comparadas contra um histórico de renomeação armazenado via correspondência sequencial (preservando a ordem), permitindo que opções sejam renomeadas no lugar; o comportamento exato do ramo de comparação sem renomeação é inferred (o JADX novamente perde parte do fluxo de controle — a função cai para `poll_edit_invalid_edits` nesse ramo na forma decompilada, o que é improvável de ser o comportamento real do cliente para uma edição no-op).

Uma string de toast `"Couldn't edit poll"` existe nos recursos, confirmando que a edição de enquete é voltada ao usuário nesta build, não apenas um caminho de protocolo reservado.

### 8.1 UI de edição de enquete (novo na 2.26.45.10) — operação de wire não resolvida

Um novo pacote `com.whatsapp.polls.ui.edit` embarca `PollEditActivity` mais diálogos de
suporte (`PollEditDiscardChangesDialog`, `PollEditSendFailedDialog`,
`PollOptionRemoveConfirmationDialog`), permitindo que um remetente renomeie uma enquete já
enviada ou adicione/remova opções dela. Found e unknown, a partir de rastreamento estático
de smali (sem decompile além da leitura do smali existente):

- **Found:** `PollEditActivity` é sustentada por um estado de edição mantido em
  `SavedStateHandle` (view model `LX/8kp`, payload de edição `LX/A4G`: nome/id, string do
  nome da enquete, linhas de opção atuais, um `Set<Long>` de ids de linha removidos). Linhas
  de opção (`LX/JZ8`) não carregam nenhuma flag de remoção — uma opção está simplesmente
  ausente da lista final comparada contra o estado de enquete ao vivo
  (`LX/8kp;->A03(LX/A4G;LX/9ei;LX/8kp;)LX/9oc;`). A remoção de opção é controlada por uma
  verificação de rollout escalonado, `LX/Ihb;->getPollRemoveOptionRollout()LX/1yG;` — um
  gate de recurso do lado do cliente, não evidência de uma nova operação de wire.
- **Found:** o diff de schema proto entre 2.26.41.6 e 2.26.45.10 contém **zero**
  alterações relacionadas a enquete — nenhum campo novo ou renomeado para renomear ou
  remover opção aparece em lugar algum no schema extraído para esta versão.
- **Inferred:** adicionar uma opção a partir desta UI muito provavelmente ainda trafega
  pelo `pollAddOptionMessage` existente (§6, campo 121) — a affordance de "adicionar linha"
  da UI corresponde ao formato dessa mensagem e nenhum primitivo substituto de
  adicionar-opção foi introduzido. Não confirmado pelo rastreamento do handler de salvar.
- **Unknown:** renomear e remover opção não têm nenhum primitivo de wire confirmado. Duas
  candidatas não confirmadas, nenhuma mais provável que a outra na evidência atual: (1) uma
  substituição completa de enquete via `Message.editedMessage` (`FutureProofMessage`
  embrulhando um `pollCreationMessage` novo), ou (2) reutilização do campo `vote`
  criptografado opaco de `pollUpdateMessage` (`PollEncValue`, §7) para uma atualização não
  relacionada a voto. A chamada de rede real do botão de salvar fica atrás de um dispatcher
  `View.OnClickListener` compartilhado, mesclado por R8 (`LX/A50`) cujo ramo `switch`
  relevante não pôde ser isolado apenas a partir do smali — este é o bloqueador específico,
  não uma escolha de escopo.

Isto é deixado aberto em vez de resolvido para um melhor palpite; reverificar uma vez que
um diff de proto contra uma versão posterior mostre um campo novo, ou uma vez que o ramo de
dispatch `LX/A50` seja rastreado.

---

## 9. Internos de correspondência de voto

### 9.1 Hash de opção (found, `C13J.A00`)

```text
optionHash = Base64(SHA-256(UTF8(optionName)))
```

SHA-256 simples do texto visível da opção, sem material de chave. Este é o valor armazenado por opção local (`C33283EeZ.A02`) e o valor contra o qual as entradas `selectedOptions` de um voto são comparadas. Qualquer aplicação que conheça o texto da opção pode computar o mesmo hash — a privacidade de um voto vem inteiramente da criptografia de segredo de mensagem do payload do voto (§7, e [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md)), não do hash ser não-adivinhável.

---

## 10. Modelo de privacidade / anonimato de voto

| Alegação | Status |
|-------|--------|
| Votos são criptografados ponta a ponta por votante, por enquete (caso de uso HKDF `Poll Vote`) | found, [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3 |
| A opção selecionada é identificada por um hash de conteúdo, não um índice | found, §9.1 |
| `hideParticipantName` ("Ocultar nomes dos votantes") suprime a exibição de quem votou, na UI | found (string `str2137`, campo 10 de `PollCreationMessage`) |
| `hideParticipantName` oculta o votante do servidor ou de outros clientes no nível do protocolo | **não suportado pelo código lido aqui** — o envelope `participant`/`from` (ou seja, a identidade do votante) é entregue e autenticado da mesma forma para todo add-on independentemente desta flag (ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §8); `hideParticipantName` é uma configuração apenas de exibição no objeto da enquete, não uma mudança de roteamento ou criptografia |
| O criador da enquete pode sempre determinar quem votou | inferred — nada no caminho de decriptação de voto (§7, §9) depende de `hideParticipantName`; o cliente do criador decripta todo voto com a identidade do votante como modificador |

Em resumo: as enquetes do WhatsApp não são anônimas para o criador da enquete. "Ocultar nomes dos votantes" só controla se *outros participantes* (na lista "Votos da enquete") veem quem votou; não muda o que é vinculado criptograficamente ao voto, e o servidor nunca aprende o conteúdo do voto de qualquer forma (a garantia E2E usual, não algo específico desta flag).

---

## 11. Multi-seleção vs. seleção única

`selectableOptionsCount` (campo 4) é o único mecanismo: um voto com mais seleções do que esse valor é rejeitado (§7.2). Não existe nenhum booleano separado de "é multi-seleção" no wire — seleção única é simplesmente `selectableOptionsCount = 1`. A UI de criação expõe isso como um único toggle, **"Permitir múltiplas respostas"** (string `str425f`); quando desativado o cliente é inferido a enviar `selectableOptionsCount = 1`, quando ativado é inferido a enviar `selectableOptionsCount = options.size()` (a UI não parece expor um limite numérico arbitrário — inferido da string de booleano único, não confirmado independentemente no código da UI de criação). O próprio protocolo permite qualquer valor `0..options.size()` (§4), então um valor do lado do cliente diferente de 1 ou "todas as opções" é possível mesmo que a UI padrão não o ofereça. Quizzes são implicitamente de seleção única (uma resposta correta; string voltada ao votante `"Quiz • Select one correct answer"`, `str57a5`).

Rótulos voltados ao votante confirmam os dois modos: `"Select one"` (`str3865`) vs. `"Select one or more"` (`str3866`).

---

## 12. `pollResultSnapshotMessage` / `V3`: snapshot no momento do forward

### 12.1 Propósito (found, `F1A`)

Reenviar uma enquete ativa para outro chat **não** reenvia a enquete interativa. `F1A` (um de vários conversores de "forward" que todos implementam a mesma interface de conversão usada entre tipos de mensagem — o conversor irmão para tipos não suportados lança `"Cannot forward message of type: ..."`) converte a enquete ativa (`C13J`) em um objeto `Dd2`: texto da pergunta, nome de cada opção e **contagem de voto local atual**, e o tipo enquete/quiz. Isso é então serializado como `pollResultSnapshotMessage` (enquete simples) ou `pollResultSnapshotMessageV3` (quiz) e renderizado com um view holder dedicado (`DWH`), distinto da bolha de enquete interativa.

### 12.2 Campos (found, `DSF`)

`name` **1** (string), `pollVotes` **2** (repeated `PollVote` — `optionName` **1**, `optionVoteCount` **2**), `contextInfo` **3**, `pollType` **4** (mesmo enum `PollType` da criação).

### 12.3 Validação (found, `F39`)

Mesmo formato de verificações da criação: nome de 1–5000 chars, pelo menos 2 opções, no máximo `min(AB 1408, 12)` opções, cada nome de opção de 1–2500 chars. Para a variante **quiz** (`V3`), as contagens de voto são forçadas a 0 no envio — um snapshot de quiz reenviado nunca divulga as totalizações, apenas a pergunta e a lista de opções.

---

## 13. Resumo de limites

| Item | Limite | Fonte |
|------|-------|--------|
| Comprimento do nome da enquete/pergunta | 1–5000 chars | `F2N.A01`, `F39.A00` |
| Comprimento do nome da opção | 1–2500 chars | `F2N.A01`, `F2L.CM7`, `F39.A00` |
| Contagem de opções (criação, snapshot) | 2–min(AB **1408**, 12) | `F2N.A01`, `F39.A00` |
| Opções selecionadas por voto | ≤ 12 e ≤ `selectableOptionsCount` | `AbstractC33199EdC.A02` |
| Intervalo de `selectableOptionsCount` | 0–options.size() (0–12 sob o bypass permissivo, §4.1) | `F2N.A01` |
| Tamanho do hash de opção (entradas de voto) | exatamente 32 bytes | `AbstractC33199EdC` |

---

## 14. Feature flags (ids como lidos nos pontos de chamada; nomes não resolvidos)

| ID | Tipo | Controla |
|----|------|----------|
| **1408** | int | contagem máxima de opção de enquete configurada pelo servidor, teto rígido do cliente 12 independentemente do valor |
| **24884** | bool | respeitar `endTime` no recebimento de uma enquete estendida (V5/V6); desativado -> rebaixada para um placeholder de compatibilidade futura |
| **24885** | int | controla a aceitação de `hideParticipantName` no recebimento (polaridade exata não resolvida) |
| **24886** | int | gate de recebimento de edição de enquete; 0 -> rejeitado, erro 10016 |
| **25758** | int (truthy) | gate de recebimento de adicionar-opção de enquete (erro 10017); também controla a rejeição de opção duplicada com trim na criação |
| **31593** | bool | marcar o metadado `pollNameHash`/`lastEditStanzaId` em um voto de saída |
| **6772** | bool | voto de enquete: helper de criptografia compartilhado (ativo) vs. caminho inline legado (desativado) |
| **37909** | bool | permite uma enquete com zero opções em um contexto de parse específico (não resolvido) |
| **2321** | bool | detalhe extra de telemetria logado quando um voto é rejeitado por estar após o tempo final da enquete |

Flags da camada de segredo de mensagem que também afetam enquetes (gate de caso de uso de edição **17811**, gates de geração, etc.) estão documentadas em [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §16 e não repetidas aqui.

---

## 15. Baileys (apenas fatos confirmados)

[WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §17 já cobre as partes de uma implementação JavaScript (`baron-baileys-v2` 1.5.17) relevantes para enquetes, a partir da leitura de `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`:

- A derivação HKDF e as strings de caso de uso `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option` correspondem exatamente aos literais do cliente Android, incluindo o AAD `id\0modifier` para `Poll Vote`.
- O AAD, o retry de identidade (PN/LID), e o tratamento de segredo ausente (recorrer à atualização bruta, não decriptada) correspondem ao comportamento do Android descrito neste relatório (§7) e em [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §7.2–§7.3.
- Nenhum caminho de criptografia do lado de envio para `pollUpdateMessage` (ou `encReactionMessage`, `encEventResponseMessage`, `encCommentMessage`) foi encontrado nos arquivos lidos — ou seja, essa implementação conseguia decriptar um voto entrante mas os arquivos revisados não continham código para criptografar e enviar um.

Nada específico de enquete além do que já é afirmado lá foi re-verificado independentemente nesta passagem (nenhum código de criação de enquete, hash de opção, ou edição de enquete do Baileys foi lido); nenhuma afirmação adicional sobre o Baileys é feita aqui.

---

## 16. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|-----|
| `poll_creation_invalid_options_count` | menos de 2 ou mais de `min(1408,12)` opções | manter opções dentro do intervalo |
| `poll_creation_unmatched_correct_answer` | `correctAnswer.optionName` do quiz não é igual ao nome de nenhuma opção | definir a resposta correta como uma correspondência exata |
| Enquete silenciosamente não mostrada (rebaixada) | `endTime`/`hideParticipantName`/`allowAddOption` definidos em uma enquete V6 mas a flag AB correspondente está desativada no receptor | lado do remetente, não corrigível pelo conteúdo; lacuna de capacidade do receptor |
| `poll_vote_invalid_options_count` | voto seleciona mais opções do que `selectableOptionsCount`, ou mais de 12 | respeitar o limite da enquete |
| `poll_update_past_end_time` | timestamp do voto (ou adicionar opção / editar) posterior a `endTime` | votar antes que a enquete seja encerrada |
| `poll_update_tc_drop` | `pollNameHash`/`lastEditStanzaId` do voto não corresponde à visão do receptor sobre a enquete | resincronizar o histórico de edição da enquete antes de votar |
| erro **10017** em adicionar-opção | AB **25758** é zero no receptor | lacuna de capacidade do receptor |
| erro **10016** em editar enquete | AB **24886** é zero no receptor | lacuna de capacidade do receptor |
| `poll_add_option_past_end_time` | opção adicionada após `endTime` | adicionar opções antes que a enquete seja encerrada |

---

## 17. Distinções importantes

| Isto | Não isto |
|------|----------|
| `pollCreationMessage`/V2/V3/V5/V6 (tipo `PollCreationMessage`) | `pollCreationMessageV4` (`FutureProofMessage` embrulhando uma enquete básica interna) |
| `pollUpdateMessage` (voto, ou metadado de voto) | `secretEncryptedMessage` com `secretEncType=POLL_EDIT`/`POLL_ADD_OPTION` (edição de enquete / adicionar opção) |
| `pollAddOptionMessage` (o payload de nova opção) | wrapper `secretEncryptedMessage` que o carrega pelo wire quando vinculado a segredo de mensagem |
| `pollResultSnapshotMessage`/V3 (estático, reenviado) | a enquete interativa ativa (`pollCreationMessage*`) |
| Seleção de opção por hash SHA-256(nome) | seleção por índice — enquetes do WhatsApp nunca selecionam por posição |
| `hideParticipantName` (configuração de exibição na UI) | anonimato do remetente do voto (não existe; o criador sempre resolve o votante) |
| `selectableOptionsCount` (o único sinal de multi/seleção-única) | um booleano separado de "é multi-seleção" (não existe nenhum) |

---

## 18. Fluxo completo (criação, opção com imagem, voto, forward)

```
[Creator]                                          [Server]                     [Participant]
   │ build PollCreationMessage                        │                              │
   │  (quiz? -> V5; community subgroup? -> V2;         │                              │
   │   extras(endTime/hide/addOpt)? -> V6; else V3)    │                              │
   │ [image poll]                                      │                              │
   │  send N × pollCreationOptionImageMessage           │                              │
   │   (messageAssociation MEDIA_POLL=6, parent key)───▶───────────────────────────▶ received,
   │  wait for all fileSha256                           │                              associated
   │  compute optionHash per option                     │                              │
   │ send pollCreationMessage* ─────────────────────────▶──────────────────────────▶ store poll,
   │                                                    │                              secret
   │                                                    │        select option(s)     │
   │                                                    │        hash = SHA256(name)  │
   │                                                    │        key = HKDF(secret,   │
   │                                                    │          pollId‖creator‖    │
   │                                                    │          voter‖"Poll Vote") │
   │                                                    │        pollUpdateMessage    │
   │◀────────────────────────────────────────────────────◀ {key, vote{ct,iv}, ts} ────│
   │ validate: end time, selection count/hash shape     │                              │
   │ decrypt, resolve hash -> known option              │                              │
   │ apply vote                                         │                              │
   │                                                    │                              │
   │ [user forwards the poll elsewhere]                 │                              │
   │ convert live poll -> Dd2 (name, per-option count)  │                              │
   │ quiz? zero the counts                              │                              │
   │ send pollResultSnapshotMessage[/V3] ───────────────▶──────────────────────────▶ static bubble,
   │                                                    │                              not interactive
```

---

## 19. Incertezas

| Item | Estado |
|------|--------|
| Polaridade exata da AB **24885** (aceitar/rebaixar hideParticipantName) | estrutura de ramo decompilada incompleta |
| Fórmula de hash de opção com imagem (`nameHash`+`imageHash`) para 2.26.41.6 | carregada de uma build anterior, não re-derivada no código desta build |
| Id de flag AB atrás do toggle de "renomeação de opção ordenada" por chat usado na correspondência de edição de enquete (`EOI.A01()`) | id não resolvido |
| Ramo sem renomeação da comparação de opção de edição de enquete | o decompiler perde parte do fluxo de controle; a forma decompilada literal sempre cai para `poll_edit_invalid_edits`, o que é improvável de ser o comportamento real para uma edição no-op |
| Valor de contexto de parse (`c33371Eg0.A00 == 1`) que ativa o bypass de zero-opção (AB **37909**) | não identificado (sincronização de histórico vs. outro caminho) |
| Se a UI de criação padrão pode enviar valores de `selectableOptionsCount` diferentes de 1 ou "todas as opções" | inferido de uma única string de toggle booleano, não confirmado contra o código da UI |
| Estabilidade do valor numérico de associação `MEDIA_POLL` entre versões | found como 6 na 2.26.41.6; uma build anterior usava um valor diferente, então não fixar seu valor entre versões |
