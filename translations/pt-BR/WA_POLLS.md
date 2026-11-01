<!-- src-sha1: 4123b5a528529c4f17625135c9cbbdbd63f1dc08 -->
# WhatsApp Polls — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-11-01
**Escopo:** família de mensagens de enquete (`pollCreationMessage` até `pollCreationMessageV6`, `pollCreationOptionImageMessage`, `pollAddOptionMessage`, `pollUpdateMessage`, `pollResultSnapshotMessage`/`V3`), histórico de versões e lógica de seleção no envio/recebimento, validação e limites de criação, vínculo de opção em enquete com imagem, modelo de seleção de voto e privacidade, múltipla escolha vs. escolha única, edição de enquete, snapshot de resultado no momento do reenvio, feature flags

---

## 1. O que é

Uma enquete é um sub-objeto de `Message` (`PollCreationMessage`, reutilizado sem alterações nos seis campos de nível superior versionados) que carrega uma pergunta, uma lista de opções, um limite de seleção e configurações opcionais de quiz/horário de término/visibilidade. Votos (`pollUpdateMessage`), opções adicionadas (`pollAddOptionMessage`) e edições (`secretEncryptedMessage`) são mensagens de acompanhamento separadas, vinculadas ao id da mensagem de criação e derivadas do secret por mensagem dela; essa criptografia (casos de uso do HKDF, AES-GCM, AAD, retry de identidade) está documentada em [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) e não é repetida aqui. Este relatório cobre a camada de tipo de mensagem: qual campo carrega o quê, como o cliente escolhe entre eles, validação e limites, e o que os handlers específicos de enquete fazem com os payloads decifrados. Todos os achados são análise estática do APK decompilado 2.26.41.6 (fontes Java em `java_src/`, além de `res/values/strings.xml`); nada foi capturado na rede. Níveis: **found** = lido no código/recursos, **inferred** = deduzido do código, **unknown** = não resolvido.

| Entidade | Campo em `Message` | Tipo proto | Papel |
|--------|--------------------|-----------|------|
| `pollCreationMessage` | **49** | `PollCreationMessage` (`DTM`) | slot de criação original |
| `pollCreationMessageV2` | **60** | `PollCreationMessage` | criação em um chat de subgrupo padrão de comunidade |
| `pollCreationMessageV3` | **64** | `PollCreationMessage` | slot de criação de enquete simples (padrão atual para enquetes comuns) |
| `pollCreationMessageV4` | **93** | `FutureProofMessage` (`BD2`) | wrapper de compatibilidade futura em volta de um `Message.pollCreationMessage` interno (campo 49) |
| `pollCreationMessageV5` | **111** | `PollCreationMessage` | slot de criação de quiz |
| `pollCreationMessageV6` | **119** | `PollCreationMessage` | slot de enquete estendida (horário de término / ocultar nomes de votantes / permitir adicionar opção) |
| `pollCreationOptionImageMessage` | **90** | `FutureProofMessage` | imagem de uma opção de enquete com imagem, vinculada à futura enquete via `messageAssociation` |
| `pollAddOptionMessage` | **121** | `PollAddOptionMessage` (`C30556DRc`) | adiciona uma opção a uma enquete existente |
| `pollUpdateMessage` | **50** | `PollUpdateMessage` (`DSG`) | voto (criptografado) ou metadados do voto |
| `pollResultSnapshotMessage` | **88** | `PollResultSnapshotMessage` (`DSF`) | snapshot estático de resultado, enquete reenviada para outro chat |
| `pollResultSnapshotMessageV3` | **115** | `PollResultSnapshotMessage` | igual, variante de quiz (contagens de votos zeradas) |

Números dos campos verificados diretamente contra `C30628DTw` (a classe proto de `Message`), que declara as onze constantes `POLL_*_FIELD_NUMBER` correspondentes à tabela acima.

---

## 2. `PollCreationMessage` (`DTM`)

### 2.1 Campos (found)

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `encKey` | **1** | bytes | presente no wire mas não usado pelos handlers lidos nesta passagem (votos usam o `messageSecret` por mensagem, não este campo; ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3) |
| `name` | **2** | string | pergunta da enquete, máx. 5000 caracteres, obrigatório |
| `options` | **3** | `Option` repetido | opções de resposta |
| `selectableOptionsCount` | **4** | uint32 | limite de seleção, obrigatório (§11) |
| `contextInfo` | **5** | `ContextInfo` | contexto padrão |
| `pollContentType` | **6** | enum `PollContentType` (`E25`) | `UNKNOWN`=0 (`A03`), `TEXT`=1 (`A02`), `IMAGE`=2 (`A01`) |
| `pollType` | **7** | enum `PollType` (`EnumC32108E1g`) | `POLL`=0 (`A01`), `QUIZ`=1 (`A02`) |
| `correctAnswer` | **8** | `Option` | opção de resposta correta do quiz, obrigatória quando `pollType=QUIZ` |
| `endTime` | **9** | int64 | timestamp de encerramento da enquete (ms) |
| `hideParticipantName` | **10** | bool | "Ocultar nomes dos votantes" (§10) |
| `allowAddOption` | **11** | bool | "Permitir que outros adicionem opções" (§6) |

`PollCreationMessage.Option` (`C30529DQb`): `optionName` **1** (string), `optionHash` **2** (string, populado apenas para opções de enquete com imagem, §5).

### 2.2 Representação local

O cliente armazena uma enquete já interpretada como `C13J` (variante de quiz com imagem `C13K`), com opções como objetos `C33283EeZ` que carregam o nome bruto (`A04`), um digest SHA-256 calculado localmente a partir do nome (`A02`, §9.1) e, para opções com imagem, o `optionHash` do wire (`A08`).

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

`pollCreationMessageV4` nunca é populado pelo caminho de envio lido nesta passagem; só aparece no recebimento (§3.3). A verificação de comunidade reutiliza o mesmo predicado `group_type == 3` do fallback de reação em texto puro em [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.2 (`C0GQ.A0A(chat) == 3`, definido a partir de `isDefaultSubgroup_`); por que uma enquete de subgrupo padrão ganha seu próprio slot versionado em vez de V3/V6 não é explicado no código lido aqui (inferred: ordenação histórica do rollout, já que o número de campo do V2 é o menor do conjunto estendido).

Então, na prática: **V3** é o slot atual para uma enquete comum de escolha única/múltipla sem extras, **V6** é o atual para uma enquete que usa horário de término, nomes de votantes ocultos ou adição de opção, **V5** é o atual para quizzes, e **V2** é uma variante específica de subgrupo de comunidade da mesma forma base. **V1** (o campo não versionado 49) e **V4** não são escolhidos pelo remetente nesta build.

### 3.2 `pollCreationMessageV4` = wrapper de compatibilidade futura (found, `F2N.CM7`)

O tipo proto do V4 é `FutureProofMessage` (`BD2`, campo único `message` = um `Message` interno). No recebimento, quando o slot V4 está populado, o cliente desempacota `BD2.message_` e lê o campo `pollCreationMessage` (49) *dessa* mensagem interna como o `PollCreationMessage` real. Este é um envelope de fallback genuíno, não um campo morto: um remetente que precisa emitir uma variante de enquete nova/indefinida pode envolver uma enquete básica (com a forma do campo 49) dentro do V4, de modo que clientes mais antigos — que entendem apenas o desempacotamento genérico de `FutureProofMessage`, não o slot mais novo — ainda renderizem uma enquete simples. Nenhum caminho de código nesta passagem popula o V4 no envio, então ele existe para compatibilidade entre versões de cliente para frente/para trás, não para algo que o próprio cliente 2.26.41.6 emita (inferred).

### 3.3 Seleção e downgrade no lado do recebimento (found, aproximado; o decompilador perdeu parte da estrutura dos branches)

`F2N.CM7` verifica os bitfields de `Message` na ordem V1 → V2 → V4 → V5 → V6 → fallback-V3 e interpreta o que estiver populado no mesmo validador (`F2N.A01`, §4). Três flags controlam a aceitação dos campos extras do V6 no recebimento; quando uma flag está desligada, a enquete é **rebaixada** (interpretada como o placeholder genérico de compatibilidade futura em vez de uma bolha de enquete) em vez de rejeitada diretamente:

| Campo extra | Flag | Efeito quando a flag está desligada |
|-------------|------|--------------------------|
| `endTime` | AB int **24884** (`receivingEnabled`) | registrado em log `poll downgraded to FMessageFuture (receiving disabled)`, não renderizado como enquete |
| `hideParticipantName` | AB int **24885** | downgrade (polaridade exata da verificação não totalmente resolvida a partir do fluxo de controle decompilado) |
| `allowAddOption` | AB int **25758** | downgrade |

O encadeamento exato dessas três condições não pôde ser totalmente reconstruído (o JADX reporta blocos duplicados/inalcançáveis em `F2N.CM7`); as flags de controle e o resultado de downgrade são found, a combinação booleana precisa é inferred.

### 3.4 Gate de conteúdo de imagem

`pollContentType = IMAGE` só é respeitado no caminho de interpretação V3/V5 quando o bit de `pollContentType` está definido; se estiver definido mas o valor não for `IMAGE`, a mensagem é rejeitada (`return null`, cai no parser genérico) em vez de ser silenciosamente tratada como texto.

---

## 4. Validação de criação (found, `F2N.A01`)

Validador único, compartilhado por todos os campos de criação versionados. Lança exceção, código de erro **11** salvo indicação contrária:

| Verificação | Regra | String de erro |
|-------|------|--------------|
| Nome presente | o bit de `name` deve estar definido | `poll_creation_missing_name` |
| Tamanho do nome | 1–5000 caracteres (a menos que um contexto de parse permissivo ignore isso, §4.1) | `poll_creation_invalid_name` |
| Resposta correta do quiz | se `pollType=QUIZ`, o bit de `correctAnswer` deve estar definido | `poll_creation_missing_correct_answer` |
| Opções presentes | ao menos uma opção, salvo quando o bypass de zero opções (§4.1) se aplica | `poll_creation_missing_options` |
| Contagem de opções (inferior) | ≥ 2 opções (0 sob o bypass) | `poll_creation_invalid_options_count` |
| Contagem de opções (superior) | ≤ `min(AB int 1408, 12)` — 12 é um teto rígido do cliente independente do valor do servidor | `poll_creation_invalid_options_count` |
| Tamanho do nome da opção | 1–2500 caracteres por opção | `poll_creation_invalid_option` |
| Nome da resposta correta | se quiz, `correctAnswer.optionName` deve ser não vazio | `poll_creation_missing_correct_answer_name` |
| Opções duplicadas | nomes das opções devem ser únicos | `poll_creation_duplicate_options` |
| Opções duplicadas após trim | sob a AB flag **25758**, nomes com espaços removidos também devem ser únicos | `poll_creation_duplicate_trimmed_options` |
| Resposta correta corresponde a uma opção | o nome da resposta correta do quiz deve ser igual ao nome de uma opção | `poll_creation_unmatched_correct_answer` |
| Contagem selecionável presente | o bit de `selectableOptionsCount` deve estar definido | `poll_creation_missing_selectable_options_count` |
| Faixa da contagem selecionável | `0 <= selectableOptionsCount <= options.size()` (ou `<= min(1408,12)` sob o bypass) | `poll_creation_invalid_selectable_options_count` |

### 4.1 Bypass permissivo / zero opções (found como caminho de código, semântica inferred)

Um booleano local (`z`) calculado a partir da AB bool **37909**, consultado apenas quando um contador interno de contexto de parse é igual a 1, relaxa a contagem mínima de opções para 0 e amplia o teto da contagem selecionável para o limite bruto `min(1408,12)` em vez de `options.size()`. O valor de contexto de parse a que isso corresponde (recebimento normal vs. algum outro caminho de ingestão, por exemplo history sync) não foi resolvido; isso fica registrado como found-mas-não-explicado, não como uma funcionalidade confirmada e visível ao usuário de "enquete sem opções".

### 4.2 Bypass de history-sync / nome permissivo

Uma flag de contexto separada (`c33371Eg0.A0W`) ignora tanto a verificação de tamanho do nome quanto (equivalentemente, em `F39`, §9) a verificação de tamanho do nome no snapshot de resultado, aceitando a string bruta sem checagem. Consistente com um caminho de parse de fonte confiável (por exemplo, reimportação local de histórico) em vez de um recebimento normal pela rede; não confirmado de forma independente.

---

## 5. Opções de enquete com imagem: `pollCreationOptionImageMessage`

### 5.1 Estrutura e vínculo (found)

`pollCreationOptionImageMessage` (campo 90) envolve uma `ImageMessage` enviada normalmente dentro de uma `FutureProofMessage` — a imagem **não** fica embutida em `PollCreationMessage.Option`. Cada imagem de opção é enviada como sua própria mensagem filha, associada à enquete (ainda não enviada) via `MessageContextInfo.messageAssociation`, tipo de associação `MEDIA_POLL = 6` (`AnonymousClass122.MEDIA_POLL`; este valor de enum é desta build — uma build anterior tinha esse valor em 7, o valor numérico não é estável entre versões e deve ser relido a cada release). O helper do lado de envio "MediaPollAssociationProvider" (em `C20M`) conta as linhas de `message_association` para o id de linha da enquete pai e tipo de associação `6`; quando a contagem atinge o número de opções, todas as imagens das opções são consideradas enviadas e o cliente prossegue para enviar a própria enquete com `pollContentType = IMAGE`.

### 5.2 Hash de opção para opções com imagem (inferred, herdado de uma build anterior, não re-derivado linha a linha na 2.26.41.6)

Para opções de texto simples, o campo `optionHash` do wire fica vazio; o único hash calculado para uma opção de texto simples é o digest local de busca `C13J.A00`:

```text
optionHash(text option) = Base64(SHA-256(UTF8(optionName)))
```

(confirmado diretamente na 2.26.41.6, §9.1 — este é o valor usado para casar seleções de voto, não o campo `optionHash` do proto). Para opções de **imagem**, o campo `optionHash` do proto é populado; um rastreamento de uma versão anterior da sequência de envio encontrou que ele combina o hash do nome da opção com o `fileSha256` da imagem enviada:

```text
nameHash   = lowerHex(SHA-256(UTF8(optionName)))
imageHash  = base64(imageMessage.fileSha256)
optionHash = lowerHex(SHA-256(UTF8(nameHash + imageHash)))
```

Essa fórmula não foi re-verificada contra o código da 2.26.41.6 nesta passagem (a classe que faz o cálculo não foi localizada); ela é mantida como inferred e deve ser reconferida antes de ser usada como base confiável.

---

## 6. `pollAddOptionMessage` (`C30556DRc`, campo 121)

### 6.1 Campos (found)

`pollCreationMessageKey` **1** (`MessageKey`), `addOption` **2** (`PollCreationMessage.Option`), `metadata` **3** (`PollUpdateMessageMetadata`, mesma forma da do voto, §7).

### 6.2 Envio (found, `F2L.ADr`)

Monta uma `Option` a partir do novo nome (e, para enquetes com imagem, do seu hash), vincula a chave da enquete de origem e — para chats 1:1, quando não é um contexto de edição — resolve a identidade do remetente através da fronteira LID/PN da mesma forma que a camada de message secret faz para outros add-ons (ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.1 passo 4). A opção em si *não* é criptografada por secret nesta camada como um `pollUpdateMessage` é: o payload de adição de opção viaja como um campo de mensagem normal; o que é envolvido em `secretEncryptedMessage` (tipo `POLL_ADD_OPTION`) é a tentativa de adição de opção como um todo, quando precisa trafegar pelo esquema de message secret (§8).

### 6.3 Validação no recebimento (found, `F2L.CM7`)

| Verificação | Erro |
|-------|------|
| Gate de feature: AB int **25758** deve ser não-zero | erro **10017** |
| `pollCreationMessageKey` presente | `poll_add_option_missing_poll_message_key` |
| `addOption` presente | `poll_add_option_missing_poll_option` |
| Nome da opção não vazio, ≤ 2500 caracteres | `poll_add_option_invalid_option` |

O objeto local resultante é criptografado por secret para transporte usando o caso de uso `Poll Add Option` (chamada confirmada ao helper de message secret com `AnonymousClass122.POLL_ADD_OPTION` como tag de associação). Opções adicionadas são rastreadas para correspondência com opções existentes da mesma forma que as opções de enquete com imagem (tipo de associação `POLL_ADD_OPTION = 18`).

---

## 7. `pollUpdateMessage` (voto e metadados do voto)

A criptografia completa (caso de uso HKDF `Poll Vote`, AAD, AES-GCM, retry de identidade LID/PN) está em [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3–§7; esta seção cobre apenas o que o handler de voto de enquete (`DUA`, estende `F2P`) faz com o texto decifrado.

### 7.1 Dois caminhos de envio/recebimento (found)

A AB bool **6772** escolhe entre:
- **ligada** (atual): um helper de criptografia compartilhado (`C33285Eeb`) monta o texto cifrado e a `MessageKey`; o voto é reenviado a partir de um par `(iv, payload)` previamente armazenado quando disponível, em vez de criptografar de novo.
- **desligada** (legado): um branch inline em `DUA` faz a mesma chamada HKDF/AES-GCM diretamente, derivando ele mesmo a identidade do destinatário (o próprio LID para votos na própria enquete do votante, senão o JID resolvido do destino do voto).

### 7.2 Payload do voto: `PollVoteMessage` (`DPF`)

Campo único `selectedOptions` **1**, bytes repetidos — cada entrada é um digest SHA-256 de 32 bytes do nome da opção (§9.1), não um índice. `MessageAddOnPollVoteUtils` (`AbstractC33199EdC`) valida a seleção decifrada:

| Verificação | Regra | Tag de log |
|-------|------|-----|
| Tamanho da seleção | ≤ 12 **e** ≤ `selectableOptionsCount` da enquete (quando > 0) | `poll_vote_invalid_options_count` |
| Formato do hash | cada hash selecionado decodifica para exatamente 32 bytes | `poll_vote_invalid_option_hashes` |
| Duplicatas | nenhum hash repetido em um mesmo voto | `poll_vote_duplicate_option_hashes` |
| Resolução | cada hash selecionado deve corresponder a um dos hashes de opção conhecidos (não removidos) da enquete | retorna um resultado de erro, sem correspondência -> voto rejeitado |

### 7.3 Horário de término e metadados (found, `DUA.A01`)

Um voto cujo `senderTimestampMs` seja posterior ao `endTime` da enquete é rejeitado (`poll_update_past_end_time`); sob a AB bool **2321**, um evento de voto rejeitado alimenta adicionalmente um contador de telemetria (`N0e`). O `metadata` do voto (`pollNameHash`, `lastEditStanzaId`) só é registrado no envio sob a AB bool **31593**; no recebimento, um bloco de metadados ausente/vazio é registrado em log como `"unstamped"` (não rejeitado só por isso), enquanto uma marcação *divergente* (verificada por `C32977EZa`) descarta o voto com `poll_update_tc_drop`. Esses metadados existem para que um cliente possa detectar que está votando contra uma enquete cujo histórico de edições ele ainda não acompanhou.

---

## 8. Edição de enquete (`secretEncryptedMessage`, `secretEncType = POLL_EDIT`)

Transportada dentro do wrapper genérico `secretEncryptedMessage` (campo 82), não de um carregador específico de enquete; ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §5/§7.4 para o envelope, o AAD e a tabela de códigos de erro (`poll_edit_message_stanza_invalid`, gate AB int **24886**, erro **10016**). A validação específica de enquete (`F3Y`, `SecretEncryptedMessageDeserializationValidator`) exige:

- que a mensagem interna seja do tipo FMessage 66 e seja uma enquete tanto antes quanto depois da edição;
- que `endTime`, `hideParticipantName`, `allowAddOption`, `selectableOptionsCount` e `pollType` sejam **inalterados** entre a enquete armazenada e a editada — apenas o texto da pergunta e/ou os textos das opções podem diferir;
- correspondência de opções: com uma flag por chat (`EOI.A01()`, id não resolvido) habilitada, as opções editadas são comparadas com um histórico de renomeações armazenado via correspondência sequencial (preservando a ordem), permitindo renomear opções no lugar; o comportamento exato do branch de comparação para o caso de não renomeação é inferred (o JADX novamente perde parte do fluxo de controle — a função cai, na forma decompilada, em `poll_edit_invalid_edits` nesse branch, o que é improvável que seja o comportamento real do cliente para uma edição no-op).

Uma string de toast `"Couldn't edit poll"` existe nos recursos, confirmando que a edição de enquete é voltada ao usuário nesta build, não apenas um caminho de protocolo reservado.

---

## 9. Internos da correspondência de voto

### 9.1 Hash da opção (found, `C13J.A00`)

```text
optionHash = Base64(SHA-256(UTF8(optionName)))
```

SHA-256 simples do texto visível da opção, sem material de chave. Este é o valor armazenado por opção local (`C33283EeZ.A02`) e o valor contra o qual as entradas de `selectedOptions` de um voto são comparadas. Qualquer aplicação que conheça o texto da opção pode calcular o mesmo hash — a privacidade de um voto vem inteiramente da criptografia por message secret do payload do voto (§7, e [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md)), não do fato de o hash ser imprevisível.

---

## 10. Modelo de privacidade / anonimato do voto

| Afirmação | Status |
|-------|--------|
| Votos são criptografados ponta a ponta por votante, por enquete (caso de uso HKDF `Poll Vote`) | found, [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3 |
| A opção selecionada é identificada por um hash de conteúdo, não por um índice | found, §9.1 |
| `hideParticipantName` ("Ocultar nomes dos votantes") suprime a exibição de quem votou, na UI | found (string `str2137`, campo 10 de `PollCreationMessage`) |
| `hideParticipantName` oculta o votante do servidor ou de outros clientes no nível de protocolo | **não suportado pelo código lido aqui** — o envelope `participant`/`from` (ou seja, a identidade do votante) é entregue e autenticado da mesma forma para todo add-on, independente dessa flag (ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §8); `hideParticipantName` é uma configuração apenas de exibição no objeto da enquete, não uma mudança de roteamento ou criptografia |
| O criador da enquete sempre pode determinar quem votou | inferred — nada no caminho de decifração do voto (§7, §9) depende de `hideParticipantName`; o cliente do criador decifra todo voto com a identidade do votante como modificador |

Em resumo: as enquetes do WhatsApp não são anônimas para o criador da enquete. "Ocultar nomes dos votantes" só controla se *outros participantes* (na lista "Votos da enquete") veem quem votou; não muda o que fica criptograficamente vinculado ao voto, e o servidor nunca conhece o conteúdo do voto de qualquer forma (a garantia E2E usual, não algo específico dessa flag).

---

## 11. Múltipla escolha vs. escolha única

`selectableOptionsCount` (campo 4) é o único mecanismo: um voto com mais seleções do que esse valor é rejeitado (§7.2). Não há um booleano separado de "é múltipla escolha" no wire — escolha única é simplesmente `selectableOptionsCount = 1`. A UI de criação expõe isso como um único alternador, **"Permitir múltiplas respostas"** (string `str425f`); quando desligado, infere-se que o cliente envia `selectableOptionsCount = 1`, quando ligado, infere-se que envia `selectableOptionsCount = options.size()` (a UI não parece expor um limite numérico arbitrário — inferred a partir da string de um único booleano, não confirmado de forma independente no código da UI de criação). O próprio protocolo permite qualquer valor `0..options.size()` (§4), então um valor de cliente diferente de 1 ou de "todas as opções" é possível ainda que a UI padrão não o ofereça. Quizzes são implicitamente de escolha única (uma resposta correta; string voltada ao votante `"Quiz • Selecione uma resposta correta"`, `str57a5`).

Os rótulos voltados ao votante confirmam os dois modos: `"Selecione uma"` (`str3865`) vs. `"Selecione uma ou mais"` (`str3866`).

---

## 12. `pollResultSnapshotMessage` / `V3`: snapshot no momento do reenvio

### 12.1 Finalidade (found, `F1A`)

Reenviar uma enquete ativa para outro chat **não** reenvia a enquete interativa. `F1A` (um dos vários conversores de "reenvio" que implementam a mesma interface de conversão usada em diferentes tipos de mensagem — o conversor irmão para tipos não suportados lança `"Cannot forward message of type: ..."`) converte a enquete ativa (`C13J`) em um objeto `Dd2`: texto da pergunta, nome de cada opção e **contagem local atual de votos**, e o tipo de enquete/quiz. Isso é então serializado como `pollResultSnapshotMessage` (enquete simples) ou `pollResultSnapshotMessageV3` (quiz) e renderizado com um view holder dedicado (`DWH`), distinto da bolha de enquete interativa.

### 12.2 Campos (found, `DSF`)

`name` **1** (string), `pollVotes` **2** (`PollVote` repetido — `optionName` **1**, `optionVoteCount` **2**), `contextInfo` **3**, `pollType` **4** (o mesmo enum `PollType` da criação).

### 12.3 Validação (found, `F39`)

Mesmo formato de verificações da criação: nome com 1–5000 caracteres, ao menos 2 opções, no máximo `min(AB 1408, 12)` opções, cada nome de opção com 1–2500 caracteres. Para a variante de **quiz** (`V3`), as contagens de votos são forçadas a 0 no envio — um snapshot de quiz reenviado nunca revela as contagens, apenas a pergunta e a lista de opções.

---

## 13. Resumo dos limites

| Item | Limite | Fonte |
|------|-------|--------|
| Tamanho do nome da pergunta/enquete | 1–5000 caracteres | `F2N.A01`, `F39.A00` |
| Tamanho do nome da opção | 1–2500 caracteres | `F2N.A01`, `F2L.CM7`, `F39.A00` |
| Contagem de opções (criação, snapshot) | 2–min(AB **1408**, 12) | `F2N.A01`, `F39.A00` |
| Opções selecionadas por voto | ≤ 12 e ≤ `selectableOptionsCount` | `AbstractC33199EdC.A02` |
| Faixa de `selectableOptionsCount` | 0–options.size() (0–12 sob o bypass permissivo, §4.1) | `F2N.A01` |
| Tamanho do hash de opção (entradas de voto) | exatamente 32 bytes | `AbstractC33199EdC` |

---

## 14. Feature flags (ids como lidos nos pontos de chamada; nomes não resolvidos)

| ID | Tipo | Controla |
|----|------|----------|
| **1408** | int | contagem máxima de opções de enquete configurada no servidor, teto rígido do cliente de 12 independentemente do valor |
| **24884** | bool | respeitar `endTime` no recebimento de uma enquete estendida (V5/V6); desligado -> rebaixada a um placeholder de compatibilidade futura |
| **24885** | int | controla a aceitação de `hideParticipantName` no recebimento (polaridade exata não resolvida) |
| **24886** | int | gate de recebimento da edição de enquete; 0 -> rejeitado, erro 10016 |
| **25758** | int (truthy) | gate de recebimento de adição de opção à enquete (erro 10017); também controla a rejeição de opções duplicadas após trim na criação |
| **31593** | bool | registra os metadados `pollNameHash`/`lastEditStanzaId` em um voto de saída |
| **6772** | bool | voto de enquete: helper de criptografia compartilhado (ligado) vs. caminho inline legado (desligado) |
| **37909** | bool | permite uma enquete com zero opções em um contexto de parse específico (não resolvido) |
| **2321** | bool | detalhe extra de telemetria registrado quando um voto é rejeitado por estar após o horário de término da enquete |

Flags da camada de message secret que também afetam enquetes (gate do caso de uso de edição **17811**, gates de geração, etc.) estão documentadas em [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §16 e não são repetidas aqui.

---

## 15. Baileys (apenas fatos confirmados)

[WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §17 já cobre as partes de uma implementação JavaScript (`baron-baileys-v2` 1.5.17) relevantes para enquetes, a partir da leitura de `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`:

- A derivação HKDF e as strings de caso de uso `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option` correspondem exatamente aos literais do cliente Android, incluindo o AAD `id\0modifier` do `Poll Vote`.
- O AAD, o retry de identidade (PN/LID) e o tratamento de secret ausente (recuar para a atualização bruta, não decifrada) correspondem ao comportamento do Android descrito neste relatório (§7) e em [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §7.2–§7.3.
- Nenhum caminho de criptografia no lado do envio para `pollUpdateMessage` (ou `encReactionMessage`, `encEventResponseMessage`, `encCommentMessage`) foi encontrado nos arquivos lidos — ou seja, essa implementação conseguia decifrar um voto recebido, mas os arquivos revisados não continham código para criptografar e enviar um.

Nada específico de enquete além do que já está declarado lá foi re-verificado de forma independente nesta passagem (nenhum código de criação de enquete, hash de opção ou edição de enquete do Baileys foi lido); nenhuma outra afirmação sobre o Baileys é feita aqui.

---

## 16. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|-----|
| `poll_creation_invalid_options_count` | menos de 2 ou mais de `min(1408,12)` opções | manter as opções dentro da faixa |
| `poll_creation_unmatched_correct_answer` | `correctAnswer.optionName` do quiz não é igual ao nome de nenhuma opção | definir a resposta correta com correspondência exata |
| Enquete silenciosamente não exibida (rebaixada) | `endTime`/`hideParticipantName`/`allowAddOption` definidos em uma enquete V6, mas a AB flag correspondente está desligada no destinatário | lado do remetente, não corrigível pelo conteúdo; lacuna de capacidade no destinatário |
| `poll_vote_invalid_options_count` | o voto seleciona mais opções do que `selectableOptionsCount`, ou mais de 12 | respeitar o limite da enquete |
| `poll_update_past_end_time` | timestamp do voto (ou da adição de opção / edição) posterior ao `endTime` | votar antes de a enquete fechar |
| `poll_update_tc_drop` | `pollNameHash`/`lastEditStanzaId` do voto não corresponde à visão do destinatário sobre a enquete | ressincronizar o histórico de edições da enquete antes de votar |
| erro **10017** na adição de opção | AB **25758** é zero no destinatário | lacuna de capacidade no destinatário |
| erro **10016** na edição de enquete | AB **24886** é zero no destinatário | lacuna de capacidade no destinatário |
| `poll_add_option_past_end_time` | opção adicionada depois do `endTime` | adicionar opções antes de a enquete fechar |

---

## 17. Distinções importantes

| Isto | Não isto |
|------|----------|
| `pollCreationMessage`/V2/V3/V5/V6 (tipo `PollCreationMessage`) | `pollCreationMessageV4` (`FutureProofMessage` envolvendo uma enquete básica interna) |
| `pollUpdateMessage` (voto, ou metadados do voto) | `secretEncryptedMessage` com `secretEncType=POLL_EDIT`/`POLL_ADD_OPTION` (edição de enquete / adição de opção) |
| `pollAddOptionMessage` (o payload da nova opção) | wrapper `secretEncryptedMessage` que o transporta no wire quando vinculado a message secret |
| `pollResultSnapshotMessage`/V3 (estático, reenviado) | a enquete interativa ativa (`pollCreationMessage*`) |
| Seleção de opção por hash SHA-256(nome) | seleção por índice — enquetes do WhatsApp nunca selecionam por posição |
| `hideParticipantName` (configuração de exibição na UI) | anonimato do remetente do voto (não existe; o criador sempre resolve o votante) |
| `selectableOptionsCount` (o único sinal de múltipla/única escolha) | um booleano separado de "é múltipla escolha" (não existe nenhum) |

---

## 18. Fluxo completo (criação, opção com imagem, voto, reenvio)

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

## 19. Pontos não resolvidos

| Item | Estado |
|------|-------|
| Polaridade exata da AB **24885** (aceitar/rebaixar `hideParticipantName`) | estrutura decompilada dos branches incompleta |
| Fórmula do hash de opção com imagem (`nameHash`+`imageHash`) para a 2.26.41.6 | herdada de uma build anterior, não re-derivada no código desta build |
| Id da AB flag atrás do alternador por chat de "renomeação ordenada de opção" usado na correspondência de edição de enquete (`EOI.A01()`) | id não resolvido |
| Branch de não renomeação da comparação de opções na edição de enquete | o decompilador perde parte do fluxo de controle; a forma decompilada literal sempre cai em `poll_edit_invalid_edits`, o que é improvável que seja o comportamento real para uma edição no-op |
| Valor de contexto de parse (`c33371Eg0.A00 == 1`) que habilita o bypass de zero opções (AB **37909**) | não identificado (history sync vs. outro caminho) |
| Se a UI de criação padrão pode enviar valores de `selectableOptionsCount` diferentes de 1 ou "todas as opções" | inferred a partir de uma única string de alternador booleano, não confirmado contra o código da UI |
| Estabilidade do valor numérico de `MEDIA_POLL` entre versões | encontrado como 6 na 2.26.41.6; uma build anterior usava um valor diferente, então não fixar esse valor entre versões |
