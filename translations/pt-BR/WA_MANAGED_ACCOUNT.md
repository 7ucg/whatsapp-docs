<!-- src-sha1: 3f456309f1ce11a70a08dd912d84e40193c760ad -->
# WhatsApp Managed Account — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-11-01
**Escopo:** o sistema de supervisão parental visível ao cliente, conhecido como "managed account" (vínculo patrocinador/dependente, papéis, experiência etária, PIN, configurações de privacidade, desvínculo, operações w:mex, armazenamento local, feature flags); o conjunto separado e não relacionado de sinais para números comerciais operados por um Business Solution Provider via Cloud API (emissor do certificado de nome verificado, campos host-storage/actual-actors, UI de coexistência, tipo de conta multi-dispositivo hospedada); como distinguir os dois

---

## 1. O que "managed" significa neste cliente

Dois sistemas não relacionados na versão 2.26.41.6 usam uma linguagem que um leitor externo chamaria de "managed account" (conta gerenciada). Eles não compartilham código, proto nem esquema w:mex. Todas as afirmações são análise estática do APK decompilado; nada foi capturado na rede. Nível: **found** = lido no código ou nos assets, **inferred** = deduzido do código, **unknown** = não resolvido.

| Sistema | Nome(s) interno(s) no código | O que é "gerenciado" | Onde | Seção |
|---|---|---|---|---|
| Supervisão parental | `com.whatsapp.managedaccount.*`, `com.whatsapp.pma.*`, `com.whatsapp.pmta.*`; codenames internos **PAA**, **PMA**, **PMTA** (encontrados em nomes de pacote/classe/pref, nunca expandidos em strings) | a própria conta do WhatsApp de um menor ("dependente"), supervisionada por uma conta pai/responsável ("patrocinador") | `w:mex`, SQLite local/SharedPrefs | 2-8 |
| Delegação de número comercial a um provedor | nenhuma string "BSP" ou "tech provider" em nenhum lugar do cliente; a UI chama isso de "um serviço seguro da Meta" ou "outras empresas" | o número do WhatsApp de uma **empresa**, cujas mensagens são hospedadas/tratadas pela infraestrutura em nuvem da Meta e/ou por um provedor terceirizado em vez do próprio dispositivo da empresa | certificado de nome verificado (`w:biz`), tipo de conta multi-dispositivo "hosted" | 9 |

Os recursos de string `str2fc9`/`str3139` ("Managed account"), `str30ae`, `str3109`, `str439d`/`str439f` e a tela de configurações a que pertencem são **todos** do sistema parental (seção 2). Não existe nenhum rótulo "Managed account" em lugar nenhum do cliente para uma empresa operada por um BSP; esse caso é sinalizado puramente por campos de certificado e banners de chat/chamada (seção 9). Esta é a correção-chave a fazer antes de usar o termo: uma nota de reverse-engineering ou um ticket que diga "managed account" sobre um número de **empresa** está falando da seção 9, não de nada chamado `ManagedAccount*` no código.

---

## 2. Supervisão parental: papéis e relação de conta

### 2.1 Papéis

`EnumC08540Ng` (found), com um rótulo de debug por constante:

| Papel | Rótulo de debug | Quem |
|---|---|---|
| `NONE` | "None" | nenhuma relação de supervisão |
| `DEPENDENT` | "Dependent" | a própria conta do menor |
| `SPONSOR` | "Sponsor" | a conta do pai/responsável |
| `SPONSOR_ADMIN` | "Sponsor Admin" | um patrocinador com direitos elevados (os direitos extras exatos não foram rastreados) |

O papel do dispositivo atual é lido do estado local por `SharedPreferencesOnSharedPreferenceChangeListenerC08490Nb.A04()` e armazenado em cache por `C08530Nf` ("ManagedAccountStartupPreferences", nome inferido de sua tag de log `ManagedAccountStartupPreferences/...`).

### 2.2 A relação é conta-a-conta, não dispositivo-a-dispositivo

O dependente tem **seu próprio número de telefone e seu próprio registro completo no WhatsApp** (seu próprio dispositivo primário, seus próprios companheiros multi-dispositivo, se houver). O patrocinador, da mesma forma, é uma conta normal, registrada de forma independente. O que os conecta é um registro do lado do servidor, espelhado localmente como:

```
ManagedAccountConnection(
  connectionLid,      // C14080dr — the dependent's LID, found
  role,                // EnumC08540Ng, found
  linkTs,              // long, link creation time, found
  connectionPnJid,     // PhoneUserJid — the dependent's phone-number JID, found
  graduationState,      // C4DV, section 2.3
  ageExperience)        // EnumC96934Gf, section 2.3
```

(`AnonymousClass586`, found; campos confirmados por seu `toString`.) Não há QR de pareamento, assinatura ADV, nem troca de chave de companheiro em lugar nenhum deste pacote — compare com o protocolo real de dispositivo companheiro em `WA_LINKED_DEVICE_PAIRING.md` seção 5, que não tem relação. O ponto de entrada do onboarding é um deep link tratado por `ManagedAccountSponsorOnboardingViewModel` (pacote `managedaccount.deeplink`, found), não um fluxo baseado em escaneamento.

### 2.3 Experiência etária e graduação

`EnumC96934Gf` (found): `UNKNOWN`, `U13`, `U16_BR`, `U18_BR`, `U18`, `STANDARD` (o Brasil tem suas próprias faixas etárias). `A00()` deste enum retorna true para `U16_BR`, `U18_BR`, `U18` — os estados que o código trata como "próximos de sair da faixa etária."

`C4DV` (estado de graduação, found): `PRE_GRADUATION`, `GRADUATION`, `PRE_GRADUATION_IMMINENT`, `UNKNOWN`. `ManagedAccountGraduationManager` e seu caminho `triggerTeenGraduationEagerly` (found) retiram um dependente da supervisão conforme ele se aproxima/cruza um limiar de idade; `ManagedAccountPmtaSponsorGraduationNuxActivity` e `ManagedAccountSponsorGraduationNuxActivity` mostram o NUX do lado do patrocinador para essa transição.

`ManagedAccountLinkingRepository.A00` (found) refaz a busca da experiência etária em um conflito HTTP 409 da chamada de vínculo, ou seja, o servidor pode rejeitar o vínculo porque a experiência etária armazenada está obsoleta, e o cliente precisa reconsultar `WaAgeExperienceRepository` antes de tentar novamente.

---

## 3. Fluxo de vínculo e operações w:mex

### 3.1 Catálogo de operações

Todos os nove nomes de operação e valores de `doc_id` abaixo foram lidos diretamente de `assets/whatsapp-android-mex_client_persist_ids.json` nesta build (found) — não inferidos de um cliente terceirizado. O esquema das nove é `whatsapp-android-mex` (chave do asset: `whatsapp_mex`).

| Operação | doc_id | Ponto de chamada encontrado | Variáveis (nesta build) |
|---|---|---|---|
| `ManagedAccountInitiateLinkingQuery` | `26671873552498548` | `MexManagedAccountInitiateLinkingApi.A00` | `input:{"dummy": null}` — **nenhum `phone_number`** é enviado; uma suposição anterior de que essa chamada carrega o número do dependente não se sustenta neste ponto de chamada |
| `ManagedAccountQuery` | `27232244463035262` | `ManagedAccountStateSynchronizer.A01` | `input:{"unused": null}` — **nenhum `jid`**; a query é vinculada à sessão, não parametrizada por JID neste ponto de chamada |
| `ManagedAccountValidateLinkingQuery` | `35449808311284430` | referenciada (correspondência de nome nos assets); variáveis não rastreadas a um ponto de chamada nesta build | unknown |
| `ManagedAccountAcceptLinkingMutation` | `26708926155457677` | referenciada; variáveis não rastreadas | unknown |
| `ManagedAccountCompleteLinkingMutation` | `26866501363013203` | referenciada; variáveis não rastreadas | unknown |
| `ManagedAccountRevokeLinkingMutation` | `27435058196100677` | referenciada; variáveis não rastreadas | unknown |
| `ManagedAccountSyncActivities` | `26594352680227840` | referenciada; variáveis não rastreadas | unknown |
| `ManagedAccountUpdatePinMutation` | `27653949584193082` | referenciada; variáveis não rastreadas | unknown |
| `ManagedAccountGetSponsorAgeVerificationInfoQuery` | `26433623289634522` | referenciada; variáveis não rastreadas | unknown |

Os corpos de resposta além dos wrappers genéricos de sucesso/erro não foram lidos para nenhuma das nove; o resultado de sucesso de `ManagedAccountInitiateLinkingQuery` (`C135065o7`, `toString()` literalmente `"PAA Initiate Linking Success"`, found) carrega duas strings e um int cujos nomes de campo não foram resolvidos — quase certamente um token/URL de deep link de vínculo e uma expiração, mas isso é inferido, não lido de um campo nomeado.

Existe um caminho separado, fora do mex: `C14E.java` (`PaaAcceptLinkingIBHandler`) analisa um stanza/notificação entrante contendo um atributo `sponsor_jid` (found) — esse é um push do servidor que dispara a UI, não a própria requisição de `AcceptLinkingMutation`.

### 3.2 Repetição em caso de falha de entrega

`MexManagedAccountInitiateLinkingApi.A01` repete a chamada de initiate até um número de tentativas fornecido pelo chamador em caso de erro código **471** ("delivery failure"), registrando `MexManagedAccountInitiateLinkingApi/requestSponsorLinkingMaterial delivery failure, retrying` (found).

---

## 4. Modelo de dispositivo/sessão

Não há **vínculo de dispositivo do tipo companheiro** entre patrocinador e dependente, e nenhum entre qualquer uma das contas e qualquer infraestrutura operada pelo WhatsApp. Cada lado é uma conta comum do WhatsApp, registrada de forma independente (próprio número de telefone, próprio dispositivo primário, próprios dispositivos vinculados opcionais sob o sistema multi-dispositivo normal descrito em `WA_LINKED_DEVICE_PAIRING.md`). A relação de supervisão é um registro do lado do servidor indexado pelo LID do dependente e pelo JID de número de telefone (seção 2.2), sincronizado para ambos os lados via `w:mex`, não uma nova sessão, pareamento ou identidade ADV.

Essa é uma diferença estrutural em relação ao caso BSP/Cloud API da seção 9, em que o "dispositivo" do número comercial não é um telefone de forma alguma — veja a seção 9.3 sobre como isso é representado no modelo multi-dispositivo existente.

---

## 5. Configurações e permissões

### 5.1 Tela de privacidade do lado do dependente

`DependentAccountPrivacyActivity` (found) agrupa as configurações em três seções via enum `C9SE`:

| Seção | Constante `C9SE` | Conteúdo |
|---|---|---|
| Visibilidade | `VISIBILITY` (0) | quem pode ver as informações do perfil do dependente |
| Contato | `CONTACT` (1) | quem pode entrar em contato com o dependente |
| Controle do patrocinador | `SPONSOR_CONTROL` (2) | configurações que o patrocinador, não o dependente, controla |

A tela leva aos "controles parentais" pela string `str2fc8`: *"Your account is managed by your parent or guardian. They can make changes in parental controls."* Existe um gate de pref local para um desses controles: `privacy_dependent_account_messages` (int, padrão `1`), lido por `C08520Ne.A06()` e consultado apenas quando a conta é um patrocinador (found) — ou seja, quem pode enviar mensagens ao dependente é algo que o app state do **patrocinador** controla, não um valor que o dependente define.

### 5.2 Controles do lado do patrocinador

`SponsorControlsHubActivity` (found) é o hub do patrocinador, listando dependentes (fragmento/tag de log `"sponsor-controls-dependents"`) com um adaptador de foto de contato por dependente. `SponsorControlsDependentInfoActivity` abre o detalhe de um dependente. `ManageNotificationsActivity` / `ManageNotificationsFragment` e `ActivityAlertsFragment` / `ManagedAccountDependentActivityAlertHandler` configuram e entregam **alertas de atividade** — notificações ao patrocinador sobre a atividade do dependente no app (`ManagedAccountSyncActivities`, seção 3.1, é a fonte de dados, controlada pela flag **31562** em `ManagedAccountAlertInfoActivity`, found).

### 5.3 PIN

`SponsorPinSetupFragment`, `SponsorPinConfirmFragment`, `ManagedAccountChangePinActivity`/`ManagedAccountChangePinFragment`/`ManagedAccountConfirmChangePinFragment` (found, pela presença das classes) implementam a criação e a alteração do PIN definido pelo patrocinador; a mutation é `ManagedAccountUpdatePinMutation` (seção 3.1; os nomes exatos dos campos `old_pin`/`new_pin` não foram confirmados nesta build — unknown). Uma sincronização do lado do dependente pode falhar especificamente por falta de PIN: `ManagedAccountStateSynchronizer` registra `"ManagedAccountStateSynchronizer/fetchAndSync missing sponsor PIN for child user"` e retorna um resultado de erro quando o tipo de servidor/resposta é `C135095oA` (found) — a sincronização de estado do dependente depende de o PIN do patrocinador estar definido.

### 5.4 Desvínculo

`ManagedAccountUnlinkAccountSettingsActivity` (found) exibe um dos vários textos de confirmação dependendo de flags carregadas nos argumentos do fragmento: `is_pmta` (uma subvariante "PMTA" distinta), `is_teen_dependent`, e se o dependente tem um push name — strings `str49cb`…`str49d3`, por exemplo *"Your account will no longer be managed by %1$s"* / *"...by your parent"*. `ManagedAccountRevokeLinkingMutation` (seção 3.1) é a operação de rede inferida como responsável por essa ação; a própria activity não foi rastreada chamando-a diretamente nesta passagem.

### 5.5 Gate de reautenticação

`ManagedAccountAuthInterstitialActivity` hospeda `PmaAuthInterstitialFragment` (pacote `com.whatsapp.pma.product.dependent.fragments`, found) e é iniciada com uma string `extra_auth_entry_point` — uma etapa de reautenticação que controla a entrada nas telas de managed account a partir de um determinado ponto de entrada. O mecanismo exato de autenticação (PIN do dispositivo, biometria, senha da conta) não foi rastreado.

### 5.6 Superfícies de debug

`ManagedAccountDebugConnectionActivity` e `ManagedAccountDebugPinAuthActivity` existem nesta build (found). Nada nesta passagem estabelece se são alcançáveis a partir da UI de release ou apenas de uma flag de build interna/debug (inferred: apenas debug, pela convenção de nomenclatura e pela ausência de qualquer caminho de lançamento descoberto a partir das telas de produção).

---

## 6. Armazenamento

| Armazenamento | Chaves/colunas | Conteúdo |
|---|---|---|
| Registro local de relação | `connectionLid`, `role`, `linkTs`, `connectionPnJid`, `graduationState`, `ageExperience` (seção 2.2) | uma linha por conexão patrocinador↔dependente |
| SharedPrefs | `paa_graduation_nux_pending`, `paa_sponsor_blocked`, `paa_nux_education_banner_dismissed`, `paa_nux_education_banner_start_timestamp`, `paa_review_privacy_settings_banner_dismissed_dependent_<lid>`, `privacy_dependent_account_messages` | estado de dispensa de NUX/banner, flag de bloqueio pelo patrocinador, o único gate de mensagens ao dependente confirmado |

Todas as chaves encontradas literalmente em `C08530Nf`, `ManagedAccountBannerManager`, `C08520Ne`.

---

## 7. Strings indicadoras na UI

| Id da string | Texto | Onde é usada |
|---|---|---|
| `str2629` | "Create a parent-managed account" | entrada do onboarding |
| `str2fc9` / `str3139` | "Managed account" | selo/rótulo |
| `str30ae` | "Managed accounts can't see this message. Learn why" | conteúdo restrito |
| `str3109` | "This is a managed account. Learn more" | aviso no chat/perfil |
| `str3751` / `str3752` / `str3754` | mensagens de inelegibilidade ("isn't eligible for a parent-managed account", "Couldn't create parent-managed account") | falha no onboarding |
| `str439d` / `str439f` | "Settings for managed accounts" / "View activity and choose settings for managed accounts" | ponto de entrada das configurações |
| `str2fc8` | "Your account is managed by your parent or guardian..." | `DependentAccountPrivacyActivity` |
| `str49cb`-`str49d3` | variantes de confirmação de desvínculo | `ManagedAccountUnlinkAccountSettingsActivity` |

`ManagedAccountNotAvailableActivity` e `ManagedAccountAgeUnknownActivity` (found pelo nome da classe) sustentam mais dois estados — o recurso não estar disponível, e a idade da conta não estar determinada — o texto exato não foi resolvido.

---

## 8. Feature flags

| ID | Onde | Controla |
|---|---|---|
| **30174** | `C08520Ne.A02`, `ManagedAccountSponsorUpsellActivity` | elegibilidade de upsell para patrocinador |
| **31562** | `ManagedAccountAlertInfoActivity` | gate do recurso de alertas de atividade |
| **34268** | `C08520Ne.A01` | uma verificação de permissão adicional (papel não resolvido além do próprio gate) |
| **16763** | `C08520Ne.A04` | gate booleano não resolvido |
| **33355** | `C08520Ne.A05` | gate booleano não resolvido, condicionado ao dependente ou a uma interface secundária |

---

## 9. Números comerciais delegados a um provedor (Cloud API / BSP)

Este é o sistema que de fato corresponde a "uma conta comercial operada em nome de uma empresa por um provedor." Ele não compartilha classe, proto ou esquema w:mex com as seções 2-8. Nenhuma string nesta build diz "BSP," "tech provider," "Business Solution Provider," "on-premises API," ou "Cloud API" para o usuário; o sinal é estrutural.

### 9.1 Certificado de nome verificado: prefixo do emissor e `PrivacyMode`

O cliente armazena um registro local de certificado de nome verificado por JID comercial com colunas (found, `AbstractC218419al`): `verified_name`, `industry`, `city`, `country`, `verified_level`, `cert_blob`, `identity_unconfirmed_since`, `host_storage`, `actual_actors`, `privacy_mode_ts`. Esses três últimos campos são extraídos de um filho no estilo `<biz host_storage="" actual_actors="" privacy_mode_ts=""/>` de um stanza `w:biz` (found, múltiplos pontos de chamada, por exemplo `O0F.java`, `C18670m9.java`, `AbstractC24816AmW.java`) para `AnonymousClass118` ("`PrivacyMode`" segundo seu próprio `toString()`), cujos dois campos inteiros são:

| Campo | Valores vistos no código | Significado |
|---|---|---|
| `hostStorage` | 0 (padrão/não definido), 1, 2 | qual infraestrutura armazena/retransmite as mensagens da empresa; mapeamento **inferred** para os termos públicos da WhatsApp Business Platform: on-premises (auto-hospedado) vs. hospedado pela Meta (Cloud API) vs. um terceiro estado, dual/transitório — o cliente não tem constantes nomeadas para esses três valores |
| `actualActors` | 0 (padrão/não definido), 1, 2 | quem de fato opera a conta no dia a dia; mapeamento **inferred** para auto-operado vs. operado por um provedor — novamente sem constantes nomeadas neste cliente |

Um segundo sinal, encontrado de forma independente no mesmo wrapper de certificado (`AnonymousClass119.A02()`/`A03()`), lê a **string do emissor** do certificado (campo `A07`) e a classifica por prefixo (found, código exato):

```java
public boolean A01() { return this.A01 == 2; }        // hostStorage == 2
public boolean A02() { return this.A07 != null && this.A07.startsWith("ent:"); }
public boolean A03() { return this.A07 != null && this.A07.startsWith("smb:"); }
```

`"ent:"` e `"smb:"` são os dois prefixos de emissor que este cliente distingue (found, strings literais). `smb:` corresponde a um certificado emitido para o app comum do WhatsApp Business, auto-operado; `ent:` corresponde a um certificado emitido para um caminho empresarial/integrado via API — este é o equivalente mais próximo, em nível de código e de primeira parte, de "conta comercial autogerenciada" vs. "conta comercial gerenciada por BSP/Cloud API" (o mapeamento dos prefixos para essas duas categorias do mundo real é **inferred** a partir dos próprios prefixos e de como são consumidos em `AbstractC198638cc.A00`, não de nenhuma string de documentação no próprio cliente).

`AbstractC198638cc.A00` combina a verificação do emissor e um booleano separado (`A09`, significado não resolvido — possivelmente "certificado ausente/revogado", consistente com o texto voltado ao usuário "no longer an official business account" na seção 9.2) em um código de "cliente" com 4 valores (found):

```java
public static final int A00(AnonymousClass119 c) {
    if (c != null) {
        if (c.A09) return 4;
        if (c.A03()) return 2;   // smb: issuer
        if (c.A02()) return 3;   // ent: issuer
    }
    return 1;                    // default / no certificate
}
```

### 9.2 Banners de coexistência e `business_state_id`

`C198628cb` ("`BusinessState`" segundo seu `toString()`) combina o `PrivacyMode` do certificado (9.1), o código de "cliente" de 4 valores, e um booleano `isVerified` em um único inteiro achatado que a UI chama de `business_state_id` (found, definido a partir de `c198628cb.A02()` em `EncryptionChangeDialogFragment` e lido da mesma forma em `PrivacyInfoBottomSheet`/`ContactInfoActivity`). A função de mapeamento casa 18 tuplas explícitas `(client, actualActors, hostStorage, flag)` com os ids **0-17**; a tabela completa não pôde ser reconstruída (o JADX reporta um erro de region-overflow nesse método específico, e vários ramos são mesclados pelo decompilador), mas o seguinte foi estabelecido diretamente a partir do código:

- o id **15** é alcançado sempre que o código "cliente" é igual a 4 (certificado ausente/revogado), independentemente dos outros campos.
- os ids **5, 6, 9, 10** são os únicos alcançáveis quando um método de gate lateral `A05()` (uma verificação não relacionada, tipo bloquear/silenciar, no chat) é verdadeiro, e também são alcançáveis pelo caminho normal quando `hostStorage == 2` — esses consistentemente acionam as strings simples *"This business uses a secure service from Meta to manage this chat/call"* (`str080d`/`str080f`/`str0c9c`/`str0f5a`, found, pontos de chamada verificados por id de recurso em `C23324A5w`/`ContactInfoActivity`).
- os ids **16** e **17** são os casos residuais (nem uma tupla conhecida, nem o id 15) e acionam a família de strings "multiple tools" / "no longer an official business account" (`str38ef`-`str38fb`, `str08b3`-`str08c7`): *"This business has chosen to use multiple tools to chat with its customers... Chats between only you and this business are managed by a secure service from Meta... this business is using the WhatsApp Business app"* — ou seja, o estado de **coexistência**, em que o número é alcançável tanto pelo app Business em um dispositivo quanto por um caminho hospedado via API ao mesmo tempo, controlado pelas flags **12729**, **18047**, **23933**, **7131**, **29343** (found, em `PrivacyInfoBottomSheet`/`ContactInfoActivity`, cada uma selecionando entre um par de strings mais antigo e um mais novo para o mesmo estado).

O resultado da IQ `remove-companion-device` no fluxo multi-dispositivo, não relacionado, pode conter um filho `coex_token` (`WA_LINKED_DEVICE_PAIRING.md` §7.1) — mesmo conceito de "coexistência", consumidor não rastreado desse lado também.

### 9.3 Modelo de dispositivo/sessão para um número hospedado por um provedor

Um número comercial totalmente hospedado pela Meta (o caso Cloud API, sem nenhum dispositivo físico) é representado dentro do sistema multi-dispositivo **existente**, não em um novo:

- o tipo de conta `HOSTED` (`EnumC32116E1o`, valor 1) e o id de dispositivo **99** são reservados para esse caso (`WA_LINKED_DEVICE_PAIRING.md` §5.1, §9.2).
- a enumeração `companion-props.platformType` que o primário armazena para seus próprios dispositivos vinculados inclui o valor **23 = `CLOUD_API`** (`WA_LINKED_DEVICE_PAIRING.md` §6.2), junto com **27 = `BUSINESS_BACK_OFFICE`** e **25/26 = `WAIL`/`WASS`** — todos tipos de plataforma de infraestrutura comercial dentro do mesmo enum de telefones/desktops/web comuns.
- a build do consumidor descrita neste relatório **se recusa** ativamente a parear um dispositivo hospedado a partir do lado primário (código de erro local **-10**, `WA_LINKED_DEVICE_PAIRING.md` §3.2) — o provisionamento hosted/Cloud API não é algo que este cliente inicia; ele apenas observa o tipo de conta resultante e os marcadores de plataforma em contas que já o possuem.

Nenhum pareamento, assinatura ADV, ou fluxo de chave de companheiro para a própria relação BSP/Cloud API foi encontrado em nenhum lugar deste APK; a máquina de canonical user/senha da segurança da conta (`WA_ACCOUNT_SECURITY.md`) e a máquina de identidade multi-dispositivo são ambas não relacionadas a como um BSP passa a operar um número — esse provisionamento acontece inteiramente do lado do servidor/na plataforma comercial da Meta e não deixa rastro neste cliente além dos marcadores acima.

### 9.4 Telemetria

O evento de log `wam_ts_navigation` (`C1EO`, found) carrega três booleanos de contexto comercial independentes por navegação registrada: `is_cloudapi`, `is_onpremises`, `is_smb`, além de `is_canonical_ent_present` e `is_meta_ai_thread`. `ChatDescription` (`com.whatsapp.gapenforcement.dto`) carrega separadamente `isEnterpriseBusiness`. Nenhuma das duas classes expõe como esses booleanos são calculados além do que as seções 9.1/9.2 já descrevem; são apenas de reporte e não controlam nenhum comportamento visível ao usuário nos arquivos lidos.

---

## 10. Distinções-chave

| A | B |
|---|---|
| "Managed account" (`ManagedAccount*`, PAA/PMA/PMTA) — a **própria conta de um menor**, supervisionada por um pai/responsável | um número comercial **operado por um provedor** via Cloud API — nenhuma string "managed account" em lugar nenhum para este caso |
| Vínculo patrocinador/dependente: duas contas do WhatsApp independentes, normalmente registradas, sem pareamento de dispositivo | número comercial hospedado: uma conta, `accountType=HOSTED`, id de dispositivo 99, nenhum dispositivo companheiro |
| Operações `w:mex` `ManagedAccount*`, esquema `whatsapp-android-mex` (seção 3.1) | campos de certificado de nome verificado via `w:biz` (`host_storage`, `actual_actors`) — stanza diferente, esquema diferente |
| Banners de coexistência de `business_state_id` (app Business autogerenciado **e** hospedado via API ao mesmo tempo) | uma empresa puramente autogerenciada (app comum do WhatsApp Business em seu próprio dispositivo, prefixo de emissor `smb:`) |
| Flag de telemetria `is_smb` (pequena/média empresa usando o app Business) | flags de telemetria `is_cloudapi` / `is_onpremises` (hospedagem do lado da API) |
| `ManagedAccountRevokeLinkingMutation` (encerra a supervisão parental) | `remove-companion-device` (não relacionado: remove um dispositivo vinculado; veja `WA_LINKED_DEVICE_PAIRING.md` §7) |

---

## 11. Fluxos completos

### 11.1 Supervisão parental: vinculando um dependente

```
[Sponsor]                                  [Server]                         [Dependent]
   │ deep link / in-app entry                  │                                 │
   ▼                                            │                                 │
ManagedAccountInitiateLinkingQuery (no vars) ──►│
   │◄── linking material (token/URL, expiry)    │
   │  share with dependent (deep link / code)   │
   │                                            │                                 │
   │                                            │◄── dependent opens link ───────│
   │                                            │   ManagedAccountValidateLinkingQuery {linking_token, sponsor_jid} (assets; call site not traced)
   │                                            │   ManagedAccountAcceptLinkingMutation {linking_token} (assets; call site not traced)
   │◄── notification: sponsor_jid (PaaAcceptLinkingIBHandler) ────────────────────│
   │                                            │   ManagedAccountCompleteLinkingMutation {linking_token} (assets; call site not traced)
   ▼                                            │                                 ▼
local ManagedAccountConnection row created on both sides (role=SPONSOR / DEPENDENT, connectionLid, connectionPnJid, linkTs)
   │                                            │                                 │
   ▼                                            │                                 ▼
periodic ManagedAccountQuery (no vars) + ManagedAccountSyncActivities ──────────► sponsor controls hub / activity alerts
```

### 11.2 Número comercial delegado a um provedor: o que o cliente do par vê

```
[Peer opens a chat/profile/call with the business number]
   │
   ▼
local verified-name cert for that JID: host_storage, actual_actors, privacy_mode_ts, issuer (smb:/ent:)
   │
   ▼
C198628cb.A02() → business_state_id (0-17)
   │
   ├─ id 15 (certificate missing/revoked)          → "no longer an official business account" (str08b3 family)
   ├─ ids 5/6/9/10 (hostStorage==2, or chat-gated)  → "uses a secure service from Meta to manage this chat/call" (str080d/f family)
   └─ ids 16/17 (coexistence residual states)       → "uses multiple tools... Business app AND a secure service from Meta" (str38ef-fb family)
```

---

## 12. Incógnitas

| Tópico | Motivo |
|---|---|
| Tabela completa tupla→`business_state_id` (todos os 18 valores) | erro de region-overflow do decompilador em `C198628cb.A02()`; vários ramos mesclados |
| Significado numérico exato de `hostStorage`/`actualActors` além do proxy de prefixo de emissor `smb:`/`ent:` | nenhuma constante nomeada neste cliente; o mapeamento para os termos on-premises/Cloud API/BSP é inferido da terminologia pública da Business Platform, não lido do código |
| Variáveis/campos de resposta de `ManagedAccountValidateLinkingQuery`, `AcceptLinkingMutation`, `CompleteLinkingMutation`, `RevokeLinkingMutation`, `SyncActivities`, `UpdatePinMutation`, `GetSponsorAgeVerificationInfoQuery` | doc_ids confirmados nos assets; nenhum ponto de chamada com nomes de variáveis encontrado nesta build |
| Significado do booleano `A09` que alimenta o código "cliente" 4 | consumido apenas como gate; sem nome ou comentário |
| Direitos extras de `SPONSOR_ADMIN` em relação a `SPONSOR` | o papel existe; comportamento diferenciado não rastreado |
| Expansão dos codenames PAA / PMA / PMTA | nunca explicitada em strings ou comentários; apenas contexto de uso |
| Alcançabilidade de `ManagedAccountDebugConnectionActivity`/`DebugPinAuthActivity` a partir de builds de release | o nome sugere apenas debug; nenhum caminho de lançamento encontrado em nenhum dos sentidos |
| Provisionamento do lado do servidor de um número hospedado via Cloud API (seção 9.3) | inteiramente do lado do servidor; este cliente nunca o inicia e apenas observa os marcadores resultantes |
| Se algum código do cliente consegue distinguir "operado diretamente pela Meta" de "operado por um BSP terceirizado via Cloud API da Meta" | ambos parecem colapsar nos mesmos sinais de `hostStorage`/`actualActors`/tipo de plataforma; nenhum campo identificador de BSP separado foi encontrado |
| Tráfego real | apenas análise estática |
