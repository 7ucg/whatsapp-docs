<!-- src-sha1: 03dc5e8e2a1874ff243bbae88accc3b09b397b6f -->
# WhatsApp Consentimento de Patrocinador para Contas de Adolescentes — Full RE Report
**Versão:** 2.26.45.10 | **Data:** 2026-11-15
**Escopo:** o pacote `com.whatsapp.vpc.sponsor` — uma tela de revisão para um pai/responsável ("sponsor") sobre a conta WhatsApp de um menor ("teen"), seu modelo de navegação, o gate de verificação de idade do lado do sponsor, as três telas de resultado (aprovado/recusado/não-pode-revisar), a consequência `account_deletion_time_ms` ao recusar, o que é e o que não é alcançável ou rastreado no wire, e a distinção do sistema de supervisão parental do `WA_MANAGED_ACCOUNT.md`

---

## 1. O que é isto

Novo na `2.26.45.10` (ausente da linha de base `2.26.41.6`): quatro classes sob
`com.whatsapp.vpc.sponsor` implementando uma decisão de revisão única que um pai/responsável faz
sobre a conta WhatsApp de um menor — aprová-la, recusá-la, ou reportar incapacidade de revisá-la.
Isto é estruturalmente diferente do produto existente de supervisão parental do
`WA_MANAGED_ACCOUNT.md` (a seção 8 abaixo detalha a distinção); lê-se como o WhatsApp adotando o
mesmo padrão de segurança de conta de adolescente que a Meta já embarca para Instagram e Facebook:
um responsável deve aprovar a existência de uma conta de um menor, com uma consequência de exclusão
de conta em caso de recusa.

"VPC" não é expandido em nenhum lugar no cliente; "Verified Parent/guardian Consent" é a leitura
mais plausível dado o formato do recurso — **inferred**, não uma expansão de string encontrada.

| Entidade | Classe | Papel |
|---|---|---|
| Tela hospedeira | `VpcSponsorActivity` | não exportada, sem intent-filter — mecanismo de lançamento não resolvido (§6) |
| View model | `X/B18` | mantém os argumentos de lançamento obrigatórios, executa o age-gate, dirige a navegação |
| Dispatcher de nav/resultado | `X/CaB` | classe compartilhada (também sustenta a `ConsentFlowActivity` de verificação de idade não relacionada e a `WamoSubActivity`); o ramo que trata eventos de `VpcSponsorActivity` é o que este relatório rastreia |
| Resultado aprovado | `VpcSponsorApprovedFragment` | mostrado na aprovação |
| Resultado recusado | `VpcSponsorDeclinedFragment` | mostrado na recusa; exibe a contagem regressiva de exclusão |
| Resultado não-pode-revisar | `VpcSponsorCannotReviewFragment` | mostrado quando o sponsor não pôde ser verificado para revisar |

Todas as descobertas são análise estática do APK decompilado (decodificação smali via `apktool`;
nenhuma execução JADX de APK completo, conforme a prática de segurança deste repositório para
builds grandes). Nada aqui foi capturado no wire ou exercitado em runtime. Tiers de evidência:
**found** = lido diretamente no smali (uma string literal, campo, ou classe); **inferred** =
raciocinado a partir da estrutura do código sem um literal que o nomeie; **unknown** = não
resolvido nesta passagem.

As mesmas quatro classes existem, byte a byte inalteradas em formato de campo/string, em
`com.whatsapp.w4b` (WhatsApp Business) `2.26.45.7` — **found** pela presença da classe; não
re-rastreado independentemente, o rastreamento da build consumer abaixo é assumido como aplicável.

---

## 2. Modelo de navegação

A tela é dirigida por um tipo de destino sealed, `LX/CvW` (found pela presença da classe; a própria
interface não carrega nenhuma string de auto-nomeação), com sete implementações identificadas por
seus próprios literais `toString()` (found):

| Classe | `toString()` | O que faz |
|---|---|---|
| `X/CSM` | `"AgeCollectionScreen"` | desvia para o fluxo compartilhado de verificação de idade entre apps da Meta |
| `X/CSO` | `"ConsentNoticeScreen"` | o prompt real de aprovar/recusar — **não renderizado em lugar algum deste pacote**, ver §4 |
| `X/CSN` | `"ApprovedScreen"` | mostra `VpcSponsorApprovedFragment` |
| `X/CSS` | `"DeclinedScreen(accountDeletionTimeMs=...)"` | mostra `VpcSponsorDeclinedFragment`; carrega um timestamp de exclusão `long` |
| `X/CSR` | `"CannotReviewScreen(teenName=...)"` | mostra `VpcSponsorCannotReviewFragment`; carrega o nome de exibição do adolescente |
| `X/CSP` | `"ErrorExit"` | mostra a tag de diálogo `vpc_sponsor_error_exit_dialog`, finaliza a activity ao dispensar |
| `X/CSQ` | `"Exit"` | finaliza a activity imediatamente |

---

## 3. Argumentos de lançamento obrigatórios e o age-gate do sponsor

O construtor de `X/B18` (found) lê três chaves do estado salvo/argumentos de navegação da activity,
duas delas obrigatórias — um valor ausente lança `IllegalStateException("Required value was
null.")`:

| Chave | Tipo | Notas |
|---|---|---|
| `vpc_teen_name` | `String` | obrigatório; o nome de exibição do adolescente, posteriormente copiado para o bundle da tela não-pode-revisar como `teen_name` puro |
| `vpc_account_deletion_time_ms` | número boxed (`.longValue()`) | presença obrigatória, mas o valor lido aqui é **descartado** — confirmado lendo o bytecode do construtor, a local nunca é armazenada em um campo. O número que a tela de recusa realmente mostra vem de um campo `X/CSS.A00` separado, definido mais tarde, quando o resultado da revisão produz um destino `DeclinedScreen` |
| `navigation` | nullable, comparado contra `X/CSM.A00` | se presente e não `AgeCollectionScreen`, define o destino inicial diretamente (ex. um fluxo retomado/reiniciado) |

Se nenhum destino inicial é definido, `B18` chama
`Lcom/whatsapp/dobverification/ContextualAgeCollectionRepository;->A06()Ljava/lang/Boolean;` — um
booleano **nullable** (found):

- **`null`** → navega para `AgeCollectionScreen`. O dispatcher compartilhado `X/CaB` lança uma
  **tela de verificação de idade Bloks** para este estado — o mesmo caminho de código que a
  `ConsentFlowActivity` não relacionada usa para verificações de idade no momento do registro
  (linha de log `"ConsentFlowActivity/navigate/launch Bloks age verification screen"`, found na
  classe compartilhada, não específico do vpc, mas o ramo que o estado `AgeCollectionScreen` do
  vpc-sponsor alcança).
- **`true`** → navega para `ConsentNoticeScreen`.
- **`false`** → navega para `CannotReviewScreen(teenName)`.

A tela Bloks responde através de
`VpcSponsorActivity.onAgeCollectionResult(ContextualAgeCollectionUsecaseApi$CACResult)` (found,
assinatura exata), reexecutando a mesma decisão de três vias a partir do subtipo `CACResult` em vez
de um booleano simples: um resultado carregando um booleano reentra nos ramos `true`/`false` acima;
um resultado dispensado/bloqueado roteia para `Exit`; um resultado sem idade disponível ou falhado
roteia para `ErrorExit`.

**Interpretação (inferred, não nomeada no cliente):** o *sponsor* — não o adolescente — deve passar
pela verificação de idade compartilhada entre apps da Meta antes de ser mostrado o prompt de
aprovar/recusar. Um sponsor que não pode ou não vai completá-la nunca alcança a decisão de
consentimento real; ele é roteado para `CannotReviewScreen`, `Exit`, ou `ErrorExit` dependendo de
como a verificação de idade se resolveu.

---

## 4. O prompt de aprovar/recusar não é renderizado por este pacote

Lendo o ramo `ConsentNoticeScreen` de `X/CaB` (found, bytecode exato): ao alcançar este estado, o
código reverifica o valor *atual* do `StateFlow` de navegação contra `ConsentNoticeScreen`
novamente — e se ainda corresponder, roteia imediatamente para `ErrorExit` em vez de renderizar
qualquer coisa. Nenhum fragment, activity, ou lançamento Bloks está conectado a este estado em
lugar algum em `com.whatsapp.vpc.sponsor` ou no ramo rastreado de `X/CaB`.

**Conclusão (inferred):** a UI real de aprovar/recusar sobre a qual o sponsor age não é código
nativo alcançável a partir deste pacote. A explicação mais consistente, dado que o age-gate também
é dirigido por Bloks, é uma tela Bloks renderizada do lado do servidor lançada *antes* de
`VpcSponsorActivity` iniciar, com esta activity apenas recebendo o **resultado** — aprovado,
recusado, ou não-pode-revisar — para exibir o fragment terminal correspondente. Nenhum nome de
operação GraphQL/MEX ou id de tela Bloks para a própria submissão de aprovar/recusar foi encontrado
nesta passagem. **Unknown.**

---

## 5. Telas de resultado terminal

| Tela | Lê | Mostra | Chamada de rede no próprio fragment |
|---|---|---|---|
| `VpcSponsorApprovedFragment` | nada dos próprios argumentos | imagem de cabeçalho, texto de título/corpo, um span clicável marcado `"manage"` dentro do corpo, um botão `"Done"` | nenhuma encontrada |
| `VpcSponsorDeclinedFragment` | `account_deletion_time_ms` (long, bundle de argumento do Fragment, definido a partir de `CSS.A00`) | imagem de cabeçalho, título, texto de corpo com o tempo de exclusão **formatado como uma string relativa/de duração** (via `LX/0Fg;->A05(LX/0Fc;J)Ljava/lang/String;`, não um timestamp puro), um botão `"Done"` | nenhuma encontrada |
| `VpcSponsorCannotReviewFragment` | `teen_name` (String, bundle de argumento do Fragment, definido a partir de `CSR.A00`) | imagem de cabeçalho, título interpolando o nome do adolescente, texto de corpo, um botão `"OK"` que dispensa | nenhuma encontrada |

**O que `account_deletion_time_ms` significa na prática:** a tela de recusa formata este valor
através de um formatador de duração relativa e o mostra como "tempo restante", ou seja, isto é
apresentado ao visualizador como uma **contagem regressiva**, não um aviso de que a exclusão já
aconteceu — found, a partir da chamada do formatador. Se a recusa realmente *agenda* a exclusão do
lado do servidor, versus a exclusão já estar em andamento no momento em que esta tela é renderizada,
é **unknown**: nenhum fragment neste pacote faz uma chamada de rede própria; o valor simplesmente
chega como um argumento de lançamento/navegação que a tela exibe.

Todo o texto do corpo para essas três telas (`str5e24`-`str5e2c` no `res/values/strings.xml` desta
build) é texto placeholder Lorem-ipsum literal — esta é uma build beta; o layout e o data-binding
são found, o texto final de lançamento é **unknown**.

---

## 6. Ponto de entrada — não resolvido

`VpcSponsorActivity` é declarada `android:exported="false"` sem nenhum `<intent-filter>` no
manifesto (found). Uma busca em todo o repositório pelas chaves de argumento de navegação literais
(`vpc_teen_name`, `vpc_account_deletion_time_ms`) e por qualquer construção de
`VpcSponsorActivity` fora de suas próprias quatro classes e das classes auxiliares compartilhadas
`X/CaB`/infraestrutura de nav não retorna **nenhum resultado em lugar algum na árvore smali
decodificada** — um resultado negativo, found.

**Inferred:** nada neste cliente constrói estaticamente o `Intent` de lançamento. A explicação mais
plausível, consistente com como a navegação dirigida por push é conhecida por funcionar em outras
partes deste app, é uma ação de notificação dirigida pelo servidor que resolve a activity alvo e
seus extras a partir dos dados do payload de push em runtime, em vez de um ponto de chamada fixo —
mas nenhum dispatcher desse tipo foi identificado nesta passagem. **Unknown** como um sponsor é
realmente notificado e roteado para esta tela.

---

## 7. Superfície de rede

Nenhum nome de operação GraphQL/MEX, id de tela Bloks, ou `xmlns` de stanza binária foi encontrado
em lugar algum deste pacote para nenhuma etapa do fluxo: não para notificar um sponsor de que uma
revisão está pendente, não para o age-gate (Bloks inferido, nenhum id de tela capturado), não para a
própria submissão de aprovar/recusar (§4), não para o que quer que realmente dispare a contagem
regressiva de exclusão de conta na recusa. Tudo com formato de rede neste fluxo é inferido como
trafegando sobre Bloks em vez de uma query GraphQL/MEX nomeada e persistida — consistente com como o
resto do ferramental de verificação de idade entre apps da Meta funciona neste cliente — mas nenhuma
operação ou identificador de tela foi capturado para nenhuma parte disso.

---

## 8. Distinções importantes

### 8.1 vs. `WA_MANAGED_ACCOUNT.md` ("Managed account")

| `vpc.sponsor` (este relatório) | `managedaccount.*` / PAA / PMA / PMTA (`WA_MANAGED_ACCOUNT.md` §2-8) |
|---|---|
| Uma **decisão de revisão única**: aprovar, recusar, ou reportar incapacidade de revisar a conta de um menor específico | Um **relacionamento de supervisão contínuo** entre duas contas registradas independentemente |
| Nenhuma operação `w:mex` encontrada; Bloks inferido, nenhum id de op/tela capturado | Nove operações `w:mex` `ManagedAccount*` nomeadas com doc_ids, schema `whatsapp-android-mex` |
| Nenhum registro de relacionamento local encontrado neste pacote | Linha local `ManagedAccountConnection` (`connectionLid`, `role`, `linkTs`, `connectionPnJid`, ...) |
| Recusar produz uma consequência `account_deletion_time_ms` para a **própria conta do adolescente** | Desvincular (`ManagedAccountRevokeLinkingMutation`) termina a supervisão; nenhuma das contas é excluída |
| Sem enum de papéis; o sponsor é simplesmente "o revisor" | `EnumC08540Ng`: `NONE`/`DEPENDENT`/`SPONSOR`/`SPONSOR_ADMIN` |
| Ponto de entrada não resolvido; activity não exportada, sem deep link | O ponto de entrada é um deep link dentro do app (`ManagedAccountSponsorOnboardingViewModel`) |
| Não compartilha nenhuma classe, pacote, ou string com `managedaccount.*`/`pma.*`/`pmta.*` | — |

Nenhum código em nenhum dos dois pacotes referencia o outro por classe ou string. Se uma aprovação
`vpc.sponsor` posteriormente cria ou interage com um relacionamento `managedaccount.*` não foi
rastreado; **unknown**.

### 8.2 vs. criação de conta normal

O registro normal do WhatsApp (`WA_ACCOUNT_LESS_SURFACE.md` / o fluxo padrão de OTP por
SMS/email) não tem nenhuma etapa de revisão por responsável; uma conta se torna ativa uma vez que
seu próprio proprietário completa o registro. `vpc.sponsor` insere um gate de aprovação externo —
mantido por uma pessoa diferente, em um dispositivo diferente — entre algum gatilho (não resolvido,
§6) e a existência continuada da conta, com a recusa carregando uma consequência de exclusão. O que
especificamente faz uma conta ser roteada para este estado de revisão por responsável em primeiro
lugar (idade no registro, um sinal de idade no dispositivo, uma reclassificação posterior) não foi
encontrado neste pacote e é **unknown**.

---

## 9. Nota de alcançabilidade Baileys / velowa

Nada neste fluxo é alcançável para um cliente de terceiros apenas-wire. A própria decisão de
aprovar/recusar é inferida como uma tela Bloks renderizada do lado do servidor que o próprio cliente
first-party do sponsor renderiza (§4) — não uma mensagem, IQ, ou mutation GraphQL/MEX nomeada que a
velowa poderia enviar ou observar. O gate de verificação de idade do lado do sponsor (§3) também é
dirigido por Bloks. Nenhum doc_id, nome de operação MEX, ou `xmlns` de nó binário existe para
nenhuma parte deste fluxo nos catálogos desta build. Não há nada aqui para implementar; esta seção
existe para registrar isso explicitamente em vez de deixá-lo implícito.

---

## 10. Incertezas

| Tópico | Motivo |
|---|---|
| Expansão de "VPC" | nunca expandida no cliente; inferida como Verified Parent/guardian Consent |
| O que lança `VpcSponsorActivity` e define seus argumentos de navegação | nenhum ponto de chamada estático encontrado em lugar algum na árvore decodificada; não exportada, sem intent-filter |
| A própria submissão de aprovar/recusar (operação de rede, id de tela) | não implementada neste pacote; Bloks inferido, nenhum identificador capturado |
| Se a recusa agenda a exclusão do lado do servidor, ou a contagem regressiva é puramente informativa | nenhuma chamada de rede em `VpcSponsorDeclinedFragment`; a exclusão é assumida como já iniciada do lado do servidor no momento em que esta tela é renderizada |
| O que roteia a conta de um adolescente para a revisão do responsável em primeiro lugar | não rastreado; nenhuma condição de gatilho encontrada neste pacote |
| Relacionamento, se houver, com `managedaccount.*` | nenhuma referência cruzada encontrada em nenhuma direção |
| Texto final de lançamento de todas as strings de `vpc.sponsor` | esta build beta embarca texto placeholder Lorem-ipsum |
| Semântica exata dos estados null/true/false de `ContextualAgeCollectionRepository.A06()` além de "desconhecido/suficiente/insuficiente" | inferida apenas do fluxo de controle; nenhum nome de campo ou enum encontrado |
| Tráfego real | apenas análise estática; nada capturado ou exercitado em runtime |

---

## 11. Fluxo (até onde a evidência alcança)

```
[Server / push — mechanism unresolved]
   │
   ▼
[VpcSponsorActivity starts] (launch args: vpc_teen_name, vpc_account_deletion_time_ms, navigation)
   │
   ▼
ContextualAgeCollectionRepository.A06() : Boolean?
   │
   ├─ null  ──► [Bloks age-verification screen] ──► onAgeCollectionResult(CACResult)
   │                                                     │
   │                                     ┌───────────────┼───────────────────┐
   │                                     ▼               ▼                   ▼
   │                             boolean payload   dismissed/blocked   no-age / failed
   │                             (re-enter below)      Exit               ErrorExit
   │
   ├─ true  ──► ConsentNoticeScreen
   │                 │
   │                 ▼
   │      [approve/decline prompt — not native to this package; inferred Bloks, unknown op]
   │                 │
   │      ┌──────────┼──────────────────┐
   │      ▼          ▼                  ▼
   │  ApprovedScreen  DeclinedScreen      (re-check of current state == ConsentNoticeScreen
   │      │          (accountDeletionTimeMs)   with no result yet falls to ErrorExit)
   │      ▼                 ▼
   │  VpcSponsorApproved  VpcSponsorDeclined
   │  Fragment ("Done")   Fragment (countdown text, "Done")
   │
   └─ false ──► CannotReviewScreen(teenName) ──► VpcSponsorCannotReviewFragment ("OK")
```
