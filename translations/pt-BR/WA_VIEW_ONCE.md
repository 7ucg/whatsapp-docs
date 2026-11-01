<!-- src-sha1: b9a264b89fe2f15a6ff3587c9bc5a6b3a47e10c0 -->
# WhatsApp Visualização Única — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-11-01
**Escopo:** wrapper `viewOnceMessage` / `viewOnceMessageV2` / `viewOnceMessageV2Extension` vs. o campo inline `viewOnce` em `ImageMessage` / `VideoMessage` / `AudioMessage` / `ExtendedTextMessage`, o mecanismo genérico de desembrulho de wrapper de mensagem compartilhado com as mensagens temporárias, tipos de mensagem e a interface de marcador comum, enforcement no lado do cliente (bloqueio de screenshot/gravação de tela, restrição de reenvio/compartilhamento/salvamento, bloqueio de autovisualização pelo remetente, remoção de mídia citada), armazenamento local e máquina de estados (`message_view_once_media`, job de deleção), ciclo de vida da chave de mídia (ligada, não repetida), o caso de wire `unavailable[type="view_once"]` e os tokens de leitura/escrita entre dispositivos, feature flags, comparação com o Baileys

---

## 1. O que é

Visualização única é um atributo por mensagem, não um tipo de mensagem separado: qualquer imagem, vídeo, mensagem de voz ou (em builds recentes) texto pode ser marcado para que o cliente do destinatário apague a cópia local após a abertura única, e o cliente adicionalmente bloqueia screenshots/gravação de tela e esconde reenvio/compartilhamento/salvamento enquanto está aberto. Todas as afirmações são análise estática do APK decompilado; nada foi capturado na rede. Níveis: **found** = lido em código, **inferred** = deduzido do código, **unknown** = não resolvido. Os nomes foram resolvidos em 2.26.41.6 a partir de strings estáveis e tags de log (`AppDataManager/contributeMetaAppData`, `ConversationRowViewOnceMedia/`, `EphemeralUpdateRunnable/`, `ViewOnceMessageStore/`, ids de string da UI).

| Entidade | Nome em 2.26.41.6 | Papel |
|--------|-----------------|------|
| Mensagem wrapper (um campo, `message` **1**) | `BD2` | corpo de `viewOnceMessage` **37**, `viewOnceMessageV2` **55**, `viewOnceMessageV2Extension` **59** em `Message` (`C30628DTw`) |
| Flag inline por tipo de mídia | `ImageMessage.viewOnce` **25**, `VideoMessage.viewOnce` **20**, `AudioMessage.viewOnce` **21**, `ExtendedTextMessage.viewOnce` **30** | definido diretamente na mensagem de mídia/texto, sem wrapper |
| Switch inline-vs-wrapper | flag **8784** | ligado: apenas campo inline; desligado: wrapper + campo inline ambos definidos (6.3) |
| Handler de imagem de visualização única | `C34670F2r` ("FMessageViewOnceImageProtobuf") | constrói/lê `DdP`, tipo de mensagem **42** |
| Handler de vídeo de visualização única | `C34671F2s` ("FMessageViewOnceVideoProtobuf") | constrói/lê `C30972DdZ`, tipo de mensagem **43** |
| Handler de texto de visualização única | `F33` ("FMessageViewOnceTextProtobuf") | constrói/lê `C31208Dhd`, tipo de mensagem **78** |
| Handler de áudio de visualização única | `C34669F2q` ("FMessageViewOnceAudioProtobuf") | constrói/lê `C30963DdH`, tipo de mensagem **82** |
| Interface de marcador | `InterfaceC24513Ahd` | implementada pelas quatro classes FMessage acima; usada para controlar o comportamento de UI/menu genericamente |
| Tabela de estado local | `message_view_once_media` | colunas `message_row_id`, `state` |
| Acessor de estado | `C199158dT` ("ViewOnceMessageStore") | get/insert/update de `state` |
| Job de deleção | `EphemeralUpdateRunnable` (classe anônima em `C199218dZ`), job type **3** | "`ViewOnceMessageStore/getViewOnceMessagesToDelete`" |
| Helper de bloqueio de captura de tela | `C66572s0` | `window.addFlags(8192)` = `FLAG_SECURE` |
| Gate de visualização única para o visualizador de mídia | `C1ZB.A0O(i)` | `i == 42 \|\| i == 43` |
| Visualizador dedicado (texto/áudio) | `ViewOnceViewerActivity`, `ViewOnceTextFragment`, `ViewOnceAudioFragment` | Activity separada, sempre com `FLAG_SECURE` |
| Visualizador compartilhado (imagem/vídeo) | `MediaViewFragment` / `MediaViewMenu` | visualizador de mídia normal, `FLAG_SECURE` apenas quando `C1ZB.A0O` é verdadeiro |
| Bottom sheets educativos | `ViewOnceNuxBottomSheet`, `ViewOnceSecondaryNuxBottomSheet` | explicação única exibida para remetente/destinatário |
| Stripper de mídia citada | `F43` ("QuotedMediaCleanupSerializationPostProcessor") | remove os bytes de mídia de uma citação de uma mensagem de visualização única, flag **25572** |

---

## 2. Marcação no proto

### 2.1 Campo inline (found)

```text
ImageMessage.viewOnce         = 25  (bool)
VideoMessage.viewOnce         = 20  (bool)
AudioMessage.viewOnce         = 21  (bool)
ExtendedTextMessage.viewOnce  = 30  (bool, VIEW_ONCE_FIELD_NUMBER)
```

Cada um é um booleano simples na mensagem de mídia/texto normal; nenhum container separado é necessário para transportá-lo. Confirmado pela leitura das tabelas de campos geradas de `C30612DTg` (Image), `C30614DTi` (Video), `DTX` (Audio), `C30613DTh` (ExtendedText).

### 2.2 Mensagem wrapper (found)

`viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**) e `viewOnceMessageV2Extension` (**59**) em `Message` são todos tipados `BD2`, e `BD2` tem exatamente um campo, `message` **1**, ele próprio um `Message`. Os três nomes de campo decompilam para a classe idêntica — são a mesma forma de wrapper usada três vezes para três gerações de protocolo:

```java
public final class BD2 extends GeneratedMessageLite {
    public static final int MESSAGE_FIELD_NUMBER = 1;
    public C30628DTw message_;   // a full nested Message
}
```

### 2.3 Inline vs. wrapper: flag 8784 (found)

Cada handler por tipo (`C34670F2r` imagem, `C34671F2s` vídeo, `F33` texto, `C34669F2q` áudio) constrói a mesma coisa duas vezes e escolhe uma com base em uma flag:

```java
boolean zA15 = this.A00.A15(8784);
...
if (zA15) {
    dp5.A0R(c30612DTg);                 // inline viewOnce=true directly on the outer Message
    return;
}
dp5A0f.A0R(c30612DTg);                  // same media message, but inside the BD2 wrapper
BD2 bd2A0Q = ...;
c30628DTwA0j.viewOnceMessageV2_ = bd2A0Q;
```

Com a flag ligada, a 2.26.41.6 nunca emite um wrapper para uma mensagem de visualização única composta localmente; os handlers de recebimento `CM7` (receive) nas mesmas classes olham apenas o flag inline (`c30612DTg.bitField0_ & ... && c30612DTg.viewOnce_`), não os campos do wrapper — desembrulhar um wrapper até a forma inline é uma etapa genérica separada (2.4).

### 2.4 Desembrulho genérico do wrapper (found)

Uma tabela estática (`AbstractC33204EdH.A00`, 35 entradas) associa um predicado "tem este wrapper" a um extrator "obtenha o `Message` interno" para cada wrapper de compatibilidade futura que o cliente conhece, incluindo `ephemeralMessage` (wrapper de mensagens temporárias), `viewOnceMessage`, `viewOnceMessageV2`, `viewOnceMessageV2Extension`, `editedMessage`, `documentWithCaptionMessage`, `botInvokeMessage`, `groupStatusMessage`, e outros. `C34748F5r` (validação de native-flow/`<biz>`, `AbstractC33204EdH.A00`) percorre essa tabela recursivamente até a profundidade 10 para encontrar o conteúdo classificável independentemente de quantos wrappers o envolvem:

```java
for (EQR eqr : AbstractC33204EdH.A00) {
    if (hasWrapper(c30628DTw, eqr) &&
        A00(..., unwrap(c30628DTw, eqr), i + 1) != C02U.A00) {
        return result;
    }
}
```

`ephemeralMessage` e os três wrappers de visualização única são entradas-pares nessa tabela — estruturalmente o mesmo mecanismo, de modo que uma mensagem de visualização única pode em princípio estar aninhada dentro, ou ao lado, de um wrapper de mensagens temporárias (seção 7). Isso espelha o próprio `getFutureProofMessage()` do Baileys em `message-inspect.js`, que enumera o mesmo conjunto de nomes de campos de wrapper.

---

## 3. Tipos de mensagem e a interface de marcador

| Tipo | Classe de mídia | Handler | Fragment/Activity |
|------|-------------|---------|--------------------|
| **42** | `DdP` (imagem) | `C34670F2r` | `MediaViewFragment` (visualizador compartilhado de imagem/vídeo) |
| **43** | `C30972DdZ` (vídeo) | `C34671F2s` | `MediaViewFragment` |
| **78** | `C31208Dhd` (texto) | `F33` | `ViewOnceTextFragment` dentro de `ViewOnceViewerActivity` |
| **82** | `C30963DdH` (áudio/ptt) | `C34669F2q` | `ViewOnceAudioFragment` dentro de `ViewOnceViewerActivity` |

Todas as quatro classes implementam `InterfaceC24513Ahd`, o único marcador que o resto do cliente testa ("isto é uma mensagem de visualização única") em vez de repetir a verificação dos quatro tipos em todo lugar. `C1ZB.A0O(i)` (`i==42 || i==43`) é o teste mais restrito, apenas imagem/vídeo, usado onde o `MediaViewFragment` compartilhado precisa distinguir imagem/vídeo de visualização única de tudo mais que também renderiza.

O conjunto de tipos `{42,43,78,82}` recorre literalmente em diversos pontos de chamada independentes encontrados nesta build: o produtor de `<meta view_once="true">` (seção 6.1), a tabela de consulta de nome de tipo (`AbstractC32316E9h`: `"viewOnceImage"`=42, `"viewOnceVideo"`=43, `"viewOnceAudio"`=82), e os métodos helper `C1ZB` para controle de salvamento/exibição.

---

## 4. Enforcement no lado do cliente

### 4.1 Bloqueio de screenshot / gravação de tela (found)

`C66572s0.A00(Window)` é um helper de uma linha:

```java
public final void A00(Window window) {
    if (window != null) {
        window.addFlags(8192);   // WindowManager.LayoutParams.FLAG_SECURE
    }
}
```

`8192` (`0x2000`) é o valor numérico bruto de `FLAG_SECURE`; o código decompilado usa a constante numérica, não o nome simbólico, de modo que uma busca por texto por `FLAG_SECURE` não encontra nada — a constante precisa ser casada pelo valor. `FLAG_SECURE` escurece a janela em screenshots, na miniatura de apps recentes e durante gravação/transmissão de tela no nível do SO; não é uma detecção específica do WhatsApp, é a flag padrão de janela segura do Android.

Dois pontos de chamada:

| Ponto de chamada | Condição | Escopo |
|-----------|-----------|-------|
| `MediaViewFragment` (visualizador de mídia genérico) | `C1ZB.A0O(i)` ou seja `i==42 \|\| i==43` | aplicado apenas quando a mensagem exibida é imagem/vídeo de visualização única; caso contrário o visualizador de mídia normal não é protegido |
| `ViewOnceViewerActivity.onCreate` | incondicional | esta Activity só é lançada para texto (78) ou áudio (82) de visualização única, então toda instância dela é protegida |

Efeito líquido: abrir qualquer um dos quatro tipos de visualização única define `FLAG_SECURE` na janela hospedeira enquanto ela estiver aberta; fechar o visualizador (o fragment/activity sendo destruído) remove a janela, o que descarta a flag com ela. Nenhuma evidência de um mecanismo de *detecção* de screenshot (p.ex. um `FileObserver` em `Pictures/Screenshots` ou um content-observer do `MediaStore`) foi encontrada; a proteção é prevenção no nível do SO, não detecção posterior ao fato.

### 4.2 Sem reenvio / compartilhamento / salvamento (found)

`ViewOnceViewerActivity.onCreateOptionsMenu` constrói exatamente quatro entradas de menu — info, transcrever (apenas áudio), apagar, denunciar — e nenhuma outra; não há entrada de reenvio, compartilhamento, salvamento ou cópia nesse menu. No `MediaViewMenu` compartilhado (usado para imagem/vídeo de visualização única através do visualizador de mídia normal), diversas variáveis locais booleanas de visibilidade de menu são calculadas com uma exclusão explícita `instanceof InterfaceC24513Ahd`, por exemplo:

```java
if (i6 == 2 && !c36911dGA1I21.element && ... && !(abstractC34931a2 instanceof InterfaceC24513Ahd)) {
    z14 = !C0DZ.A0X(c0df);     // forward-related menu flag, left false (hidden) for view-once
}
...
z16 = abstractC34931a2 instanceof InterfaceC24513Ahd;
if (!z16) {
    z17 = !AbstractC24760wu.A07(c0df);   // another gated flag, defaults false for view-once
}
```

Como toda flag tem valor padrão `false` e só recebe um valor utilizável no ramo não-visualização-única, os itens de menu correspondentes permanecem escondidos para mensagens `InterfaceC24513Ahd`. A restrição é aplicada na camada de UI (construção do menu), não removendo a mídia subjacente do disco local antes de o visualizador abri-la.

### 4.3 Remetente não pode reabrir a própria mídia (found)

`DYM` (componente da linha de conversa para mídia de visualização única) afirma:

```java
C00K.A0C(false, "ConversationRowViewOnceMedia/senders can not view their own media");
```

no caminho que a linha de visualização única enviada por um remetente usaria para reabrir o conteúdo — ou seja, o invariante "um remetente nunca recebe um handler de abertura funcional para sua própria mensagem de visualização única" é aplicado como uma asserção rígida, não como uma ocultação condicional de UI.

### 4.4 Citar remove a mídia (found)

`F43` ("QuotedMediaCleanupSerializationPostProcessor", controlado pela flag **25572**) reescreve o `imageMessage` / `videoMessage` / `documentMessage` / `audioMessage` de uma mensagem citada antes de ele ser anexado como `contextInfo.quotedMessage` a uma *nova* mensagem saindo: copia os campos não relacionados ao conteúdo (mimetype, legenda, dimensões, miniatura, o próprio bit `viewOnce`), mas descarta `mediaKey`, `fileSha256`/`fileEncSha256` e `directPath`. Citar uma mensagem de visualização única, portanto, não pode contrabandear a chave de mídia original em uma resposta; a citação mostra apenas metadados.

### 4.5 Bottom sheets educativos (found)

`ViewOnceNuxBottomSheet` é exibido uma vez por papel (remetente/destinatário — rastreado pelas chaves do UXCam `ephemeral_view_once` / `ephemeral_view_once_receiver`) na primeira vez que cada lado envia/recebe uma mensagem de visualização única, com o texto vindo diretamente de `res/values/strings.xml`:

| Id de string | Texto |
|-----------|------|
| `str4e56` | "View once messages give you more privacy" |
| `str4e55` | "For added privacy, the recipient can't share, forward, copy, save, or take a screenshot of it." |
| `str4e68` / `str4e5d` / `str4e7b` | variantes por tipo: "This is a view once photo/message/video so it's more private" |
| `str4e69` / `str4e6a` / `str4e5c` | "Also, you can't share, forward, copy, save, or take a screenshot of it." |
| `str4e63` / `str4e64` | "View once photo, expired" / "View once photo, opened" (mesmo padrão para vídeo/áudio/texto) |

Os pares de string "expired"/"opened" por tipo (imagem, vídeo, áudio, texto) são a face visível ao usuário da coluna `state` local (seção 5).

---

## 5. Armazenamento local e máquina de estados

### 5.1 Tabela (found, `C199158dT`)

```sql
-- message_view_once_media(message_row_id, state)
SELECT state FROM message_view_once_media WHERE message_row_id = ?     -- GET_VIEW_ONCE_STATE_BY_MESSAGE_ROW_ID_SQL
UPDATE message_view_once_media SET state = ? WHERE message_row_id = ?  -- UPDATE_VIEW_ONCE_SQL
INSERT INTO message_view_once_media (message_row_id, state) VALUES (?, ?)  -- INSERT_VIEW_ONCE_SQL
```

Uma linha por mensagem de visualização única, independente das tabelas genéricas `message` e `message_media` (que ainda mantêm a contabilidade de linha/arquivo de mídia compartilhada com mensagens comuns).

### 5.2 Estados (found valores de linha, mapeamento de nome parcialmente inferido)

| Transição | Código | Gatilho |
|------------|------|---------|
| Linha criada | `A02` (`BDk()` na FMessage, valor na criação) | mensagem enviada/recebida; o valor inicial é o que a FMessage reporta — consistente com "0 = não aberta", mas nenhuma constante nomeada foi encontrada |
| Marcada como aberta | `A03`: `state = 1` | o status da mensagem (`B6u()`) atinge **8**, **9** ou **10** (códigos de status relacionados a download/leitura; nomes exatos não resolvidos) |
| Lida sem linha | fallback `i = 2` em `A01` | `GET_VIEW_ONCE_STATE...` não retorna linha; o código trata isso como se a mensagem já tivesse expirado |

Então **1** = "aberta" confirmada (ponto de chamada nomeado); **2** é o fallback de sem-registro/expirada; existe um valor inicial/"não aberta", mas não foi fixado a um literal nesta build.

### 5.3 Deleção (found)

A mesma classe `EphemeralUpdateRunnable` que expira mensagens temporárias (job type 0, tabela `message_ephemeral`) e os add-ons de segredo de mensagem (job type 4, tabela `message_add_on`) também executa o job type **3**, registrado em log como `ViewOnceMessageStore/getViewOnceMessagesToDelete`:

```sql
SELECT message.* FROM message_view_once_media AS view_once
  JOIN message AS message ON view_once.message_row_id = message._id
  JOIN message_media AS message_media ON message_media.message_row_id = message._id
WHERE message_media.file_size IS NOT NULL
  AND message_media.file_size IS NOT 0
  AND message.from_me = 0
  AND view_once.state IN (1, 2)
LIMIT ?
```
<sub>(lista de colunas simplificada; `GET_EXPIRED_VIEW_ONCE_MESSAGES_SQL`)</sub>

Lido literalmente: o job só busca mídia de visualização única *recebida* (`from_me = 0`) que ainda tem um arquivo no disco (`file_size` presente e diferente de zero) e cujo estado é `1` (aberta) ou `2` (o mesmo valor de fallback usado para "sem linha"/expirada). O job libera o arquivo de mídia local para linhas que casam com essa consulta; não apaga a própria linha da mensagem (a linha sobrevive, carregando o rótulo de UI "aberta"/"expirada" da seção 4.5). Mídia de visualização única **enviada** (`from_me = 1`) não é cobrida por essa consulta — consistente com o remetente nunca poder reabri-la (4.3), mas nenhuma limpeza correspondente para a própria cópia do remetente foi encontrada; sua retenção/deleção é **unknown**.

### 5.4 Ciclo de vida da chave de mídia/cripto (ligada, não repetida)

A mídia de visualização única usa o pipeline de mídia comum de ponta a ponta — a mesma tabela `MmsType`, a mesma derivação de chave HKDF-80, o mesmo envelope AES-CBC+HMAC, as mesmas URLs de upload/download; não há uma linha `MmsType` separada para "visualização única". Veja [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) seções 3-5 para a cripto, e a seção 12 desse relatório para as notas específicas de visualização única (asserção de não-visualização-pelo-remetente, tag de log de deleção de miniatura). Se o servidor deleta ou marca de forma independente o objeto enviado após o primeiro download é **unknown** a partir desta análise estática — a garantia do lado do cliente é a deleção do arquivo local na 5.3, não um contrato de servidor que o cliente possa observar.

---

## 6. "Visualização única indisponível" / sinalização entre dispositivos

### 6.1 Stanza `unavailable[type="view_once"]` (correção a uma nota de pesquisa anterior)

Uma nota de pesquisa anterior (2.26.35.2) rastreou o par literal de saída `view_once`/`true` até um método registrado em log como `AppDataManager/contributeMetaAppData` e deixou aberto se esse método construía um nó completo ou apenas contribuía com metadados. Na 2.26.41.6 a mesma tag de log (`"AppDataManager/contributeMetaAppData type="`) **não** é o produtor de `view_once`: ela pertence a um ramo diferente, não relacionado, do `F6K` (o construtor genérico do nó `<meta>`) que grava um atributo livre `appdata` para mensagens de bot/add-on (`FZF.AVN()`). O atributo `view_once` real nesta build é construído algumas linhas antes, no *mesmo* método `F6K`, independentemente dessa linha de log:

```java
if (c08j2.A15(11282) && (i == 42 || i == 43 || i == 82 || i == 78)) {
    EZV.A00(ezv, "view_once", "true");
}
```

Isso emite `<meta view_once="true">` como filho/atributo do nó `<meta>` da stanza `<message>` de saída (não o filho `<unavailable type="view_once">` que a nota de pesquisa e o Baileys/whatsmeow descrevem). Os dois podem ser verdadeiros ao mesmo tempo: `<meta view_once="true">` é o marcador da própria stanza do remetente de que esta mensagem é de visualização única; `<unavailable type="view_once">` é um nó *diferente*, observado apenas no lado de recebimento/Web quando nenhum texto cifrado foi distribuído para esse dispositivo. A análise estática do APK Android (que não tem papel de Web/dispositivo vinculado aqui) não pode mostrar qual lado monta esse segundo nó; este relatório não altera a conclusão anterior de confiança média-alta de que ele é produzido pelo servidor ou normalizado pelo servidor a partir do estado de distribuição do remetente. O Baileys corrobora o lado de recebimento com um literal *mais específico* do que o genérico: `src/Socket/messages-recv.js` verifica `unavailableType === 'view_once_unavailable_fanout'` (junto com `bot_unavailable_fanout`, `hosted_unavailable_fanout`) para decidir se pula uma requisição de reenvio de placeholder sob demanda, enquanto `src/Utils/decode-wa-message.js` casa separadamente o literal simples `attrs.type === 'view_once'` em um filho `<unavailable>` para definir `isViewOnce`/`StubType.VIEWED_ONCE`. Esses são dois caminhos de código diferentes para o que a nota de pesquisa anterior tratava como uma única string.

### 6.2 Tokens `view_once="read"`/`"write"` (token found, consumidor não resolvido)

Os literais `view_once_read` e `view_once_write` estão presentes na tabela de dicionário de stanza binária do cliente Android (`AbstractC40911lb`, a lista fixa de vocabulário de wire usada para codificação compacta por token) — o mesmo tipo de tabela que carrega `unavailable`, `enc`, `polltype`, etc. O `decode-wa-message.js` do Baileys lê um valor `attrs.view_once` igual a `'read'` ou `'write'` em atributos no nível `<enc>` e o armazena como `fullMessage.viewOnceType`. Em conjunto, isso é consistente com um sinal de sincronização "já aberto" por dispositivo próprio que viaja junto com o envelope da mensagem — plausivelmente como os outros dispositivos vinculados de um usuário descobrem que o conteúdo de visualização única já foi aberto em um dispositivo — mas nenhum ponto de chamada Android que *define* ou *consome* esse atributo foi localizado na 2.26.41.6; está registrado aqui como um token de wire found com consumidor Android não resolvido (**unknown**).

---

## 7. Interação com mensagens temporárias

Visualização única e mensagens temporárias (TTL de mensagem por conversa) são flags independentes e ortogonais que podem ambas ser definidas na mesma mensagem:

- Usam tabelas locais separadas: `message_ephemeral` (temporárias, indexada por `expire_timestamp`) vs. `message_view_once_media` (visualização única, indexada por `state`).
- Ambas são expiradas por jobs do *mesmo* worker `EphemeralUpdateRunnable` (job type 0 para temporárias, job type 3 para visualização única, job type 4 para add-ons de segredo de mensagem) — um caminho de agendamento/execução compartilhado, estado e SQL distintos por funcionalidade.
- No nível do proto, `ephemeralMessage` é uma entrada-par na mesma tabela genérica de desembrulho de wrapper que os três wrappers de visualização única (seção 2.4): uma mensagem pode estar embrulhada como `ephemeralMessage{message: viewOnceMessage{message: imageMessage{...}}}` ou no aninhamento inverso, e o desembrulho recursivo em `C34748F5r` e o `getFutureProofMessage()` do Baileys percorrem ambas as ordens.
- A deleção de mensagem temporária remove a mensagem inteira depois do TTL da conversa, independentemente de ter sido aberta; a deleção de visualização única remove apenas o *arquivo* de mídia depois que a mensagem foi aberta (ou cai no fallback de estado 2), e mantém a linha da mensagem (agora exibida como "aberta"/"expirada") no lugar. Uma foto de visualização única dentro de uma conversa com mensagens temporárias está, portanto, sujeita ao TTL da conversa além da própria regra de apagar-após-uma-abertura.

---

## 8. Feature flags (ids como lidos nos pontos de chamada; nomes não resolvidos)

| ID | Tipo | Controla |
|----|------|----------|
| **8784** | bool | enviar mídia de visualização única apenas com o campo inline (ligado) vs. campo inline + wrapper legado (desligado) |
| **11282** | bool | emitir `<meta view_once="true">` para os tipos de mensagem 42/43/78/82 |
| **25572** | bool | remover campos de mídia de uma mensagem de visualização única citada (`F43`) |

(As flags que controlam o pipeline de mídia compartilhado — HKDF, upload/download, retry — estão listadas em [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) seção 16 e não são repetidas aqui.)

---

## 9. Baileys (`baron-baileys-v2`, código lido, nada testado)

| Tópico | Baileys | Android 2.26.41.6 |
|-------|---------|---------------------|
| Marcação no lado do envio | sempre embrulha: `{ viewOnceMessage \| viewOnceMessageV2 \| viewOnceMessageV2Extension: { message } }` dependendo de uma opção `viewOnceVersion` (`src/Utils/messages.js`) | embrulha apenas quando a flag 8784 está desligada; o padrão (8784 ligada) define o campo inline `viewOnce` diretamente na mensagem de mídia/texto, sem wrapper |
| Wrapper também usado para não-mídia | `viewOnceMessage` é adicionalmente usado para futureproof de envios `buttonsMessage`/`templateMessage`/`listMessage`/`interactiveMessage` (`src/Socket/messages-send.js`, `requiresViewOnce`) — não relacionado à privacidade de autodestruição | o mesmo tipo de wrapper (`BD2`) é reaproveitado pela tabela de desembrulho genérica para `botInvokeMessage`, `editedMessage`, etc. — mesmo papel de "envelope genérico" confirmado independentemente (2.4) |
| Lista de desembrulho genérico | `getFutureProofMessage()` em `message-inspect.js`: `ephemeralMessage`, `viewOnceMessage`, `documentWithCaptionMessage`, `viewOnceMessageV2`, `viewOnceMessageV2Extension`, `editedMessage`, `groupMentionedMessage`, `botInvokeMessage`, ... | `AbstractC33204EdH.A00` (35 entradas) — mesmos nomes de campo de wrapper |
| Tratamento de recebimento de `unavailable` | duas verificações de literal distintas: `attrs.type === 'view_once'` (define `isViewOnce`) e `unavailableType === 'view_once_unavailable_fanout'` (pula reenvio de placeholder) | apenas o produtor `<meta view_once>` do lado do cliente (6.1); o próprio nó `<unavailable>` é do caminho de recebimento/lado Web, não rastreado aqui |
| Token de leitura/escrita `view_once` | decodifica `attrs.view_once === 'read' \| 'write'` em atributos `<enc>` para `viewOnceType` | tokens presentes no dicionário de wire do cliente; nenhum consumidor Android localizado (6.2) |
| Analytics | `WAM/constants.js`: `viewOnceMessagesSent` (16), `viewOnceMessagesReceived` (17), `viewOnceMessagesOpened` (18) | não rastreado neste relatório; veja [WA_WAM_ANALYTICS.md](./WA_WAM_ANALYTICS.md) para o mecanismo WAM em geral |
| Bloqueio de screenshot/reenvio | não implementado — o Baileys é uma biblioteca de backend sem UI, sem janela, sem menu para restringir | `FLAG_SECURE` + omissão de item de menu (4.1-4.2); não reproduzível fora de uma UI Android |
| Deleção local após abertura | não aplicável — o Baileys não tem máquina de estados persistente de visualizador de mídia; os chamadores são responsáveis pelo próprio armazenamento | `message_view_once_media.state` + job type 3 do `EphemeralUpdateRunnable` (5.1-5.3) |

---

## 10. Casos de erro / pegadinhas

| Sintoma | Causa | Nota |
|---------|-------|------|
| A mídia de visualização única desaparece quando o visualizador é reaberto | normal: `state` chegou a 1 (aberta) ou a linha estava ausente (fallback 2), e o job de deleção já liberou o arquivo | não é um bug; este é o comportamento pretendido de apagar-após-uma-abertura |
| A própria mídia de visualização única do remetente nunca abre a partir da linha de conversa | asserção rígida do `DYM` `senders can not view their own media` | por design, não um caminho de erro |
| A resposta citando uma mensagem de visualização única não mostra mídia | `F43` remove `mediaKey`/hashes/`directPath` da citação, mantendo apenas legenda/dimensões/miniatura/o bit `viewOnce` | esperado; a citação não pode ser usada para reextrair a mídia |
| O visualizador de imagem/vídeo de visualização única deixa passar screenshots em alguns builds mas não em outros | `FLAG_SECURE` só é aplicado via `C1ZB.A0O(i)` (tipos 42/43); qualquer regressão nesse gate (p.ex. um caminho de código que abre o visualizador compartilhado para um item de visualização única sem passar pela chamada controlada) derrubaria silenciosamente a proteção | localização do gate documentada em `MediaViewFragment` linha ~3120 (nesta build) |
| Um dispositivo vinculado mostra uma mensagem de visualização única como já aberta sem o usuário tê-la aberto ali | sincronização plausível entre dispositivos via tokens de wire `view_once="read"/"write"` (6.2) | mecanismo não confirmado no lado Android; registrado como unknown |

---

## 11. Distinções-chave

| Isto | Não isto |
|------|----------|
| campo booleano `viewOnce` em `ImageMessage`/`VideoMessage`/`AudioMessage`/`ExtendedTextMessage` | o wrapper legado `viewOnceMessage`/`viewOnceMessageV2`/`viewOnceMessageV2Extension` em torno da mesma mensagem |
| `viewOnceMessage` (`BD2`) usado para privacidade (autodestruição) | o mesmo tipo de wrapper `BD2` reaproveitado como envelope genérico de futureproofing para envios de botões/template/lista/interativo (Baileys) e para `botInvokeMessage`/`editedMessage` no Android |
| `message_view_once_media.state` (local, por mensagem, rastreamento de abertura/expiração) | `message_ephemeral.expire_timestamp` (local, por mensagem, TTL de conversa com mensagens temporárias) — tabelas independentes, jobs independentes, mesmo executor |
| `<meta view_once="true">` — classificador do lado do remetente na stanza de saída | `<unavailable type="view_once">` — um nó diferente visto no lado de recebimento/Web quando nenhum texto cifrado chegou a esse dispositivo |
| `FLAG_SECURE` na janela do visualizador (*prevenção* de screenshot/gravação) | um callback de *detecção* de screenshot — nenhum mecanismo desse tipo foi encontrado |
| Deleção do *arquivo* de mídia local depois da abertura | deleção da *linha* da mensagem — a linha sobrevive, rotulada "aberta"/"expirada" |
| Visualização única (a mídia é apagada após uma abertura) | mensagens temporárias (a mensagem inteira é removida depois de um TTL no nível da conversa) — ortogonais, podem se combinar |

---

## 12. Fluxo completo (foto de visualização única, chat 1:1)

```
[Sender]
   │ pick photo, mark "view once" in composer
   │ ImageMessage.viewOnce = true          (flag 8784 on: inline only)
   │ upload via normal media pipeline (WA_MEDIA_UPLOAD.md)
   │ flag 11282 on, type==42 → <meta view_once="true">
   ▼
[Server]  relays the E2E-encrypted stanza; cannot read viewOnce (it's inside the ciphertext)
   │
   ▼
[Receiver]
   │ decrypt → ImageMessage.viewOnce == true, message type 42 (DdP)
   │ INSERT message_view_once_media(message_row_id, state=<initial>)
   │ thumbnail shown in the conversation row; sender-side row asserts "can not view own media"
   │
   ├── user taps to open ──► MediaViewFragment, C1ZB.A0O(42) == true
   │                          → window.addFlags(FLAG_SECURE)
   │                          → forward/share/save menu items hidden (InterfaceC24513Ahd)
   │                          → status reaches 8/9/10 → state = 1 ("opened")
   │                          → window closed, FLAG_SECURE drops with it
   │
   ▼
[EphemeralUpdateRunnable, job type 3]
   │ SELECT ... FROM message_view_once_media JOIN message_media
   │   WHERE from_me=0 AND file_size IS NOT NULL AND state IN (1,2)
   ▼
local media file deleted; row kept, UI shows "View once photo, opened"
```

---

## 13. Pontos não resolvidos

| Item | Estado |
|------|-------|
| Constantes nomeadas para `state` 0 (inicial) e o significado exato compartilhado entre 2 (fallback de sem-linha) e "expirada" | apenas 1 ("aberta") tem um ponto de chamada nomeado; o resto é inferido do valor de fallback e das strings de UI |
| Códigos de status 8/9/10 consumidos por `C199158dT.A03` para disparar "aberta" | não resolvidos a constantes nomeadas |
| Retenção/limpeza da **própria** cópia do remetente da mídia de visualização única enviada | o job de deleção só busca `from_me = 0`; nenhuma limpeza correspondente do lado do remetente foi encontrada |
| Deleção/marcação do lado do servidor do objeto enviado após o primeiro download | não pode ser observada a partir de análise estática do cliente |
| Construção do nó `<unavailable type="view_once">` (placeholder do cliente vs. construído pelo servidor) | não resolvido; carregado de pesquisa anterior, não resolvido de novo aqui |
| Consumidor Android dos tokens de wire `view_once="read"/"write"` | presença do token confirmada na tabela de dicionário; nenhum ponto de chamada localizado |
| Se `FLAG_SECURE` é aplicado em todo caminho de código que pode apresentar conteúdo de visualização única (p.ex. preview de notificação, widget, Wear) | apenas os caminhos de `MediaViewFragment` e `ViewOnceViewerActivity` foram verificados |
