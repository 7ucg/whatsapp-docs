<!-- src-sha1: 1fe6d8278b8f0a0adfe50041466f968ec368a2e2 -->
# WhatsApp Payments — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-11-01
**Escopo:** tipos de mensagem de pagamento no chat (`sendPaymentMessage`, `requestPaymentMessage`, `declinePaymentRequestMessage`, `cancelPaymentRequestMessage`, pagamentos divididos, convite/lembrete de pagamento) e seus campos proto, arquitetura de cliente multi-rail (UPI da Índia, Pix do Brasil, México, Indonésia, rail genérico "UPR"), vinculação de VPA/conta bancária e fluxo de onboarding UPI, a camada embutida de credencial/PIN/vinculação de dispositivo da NPCI ("Common Library", CL), sincronização de status de transação, camadas de criptografia (E2E do chat vs. blob de credencial NPCI), operações GraphQL/MEX de pagamento (doc_ids), regras de auto-leitura de OTP da NPCI, feature flags, tratamento de recusa/código de erro

---

## 1. O que é (visão geral)

O WhatsApp Android envia um protocolo de pagamento no chat compartilhado (tipos de mensagem proto carregados dentro da `Message` E2E normal) mais vários *rails* de pagamento específicos por país, cada um com sua própria UI de onboarding, operações GraphQL e (no caso da Índia) uma biblioteca de credencial de terceiros embutida. Todos os achados são análise estática do APK decompilado; nada foi capturado no tráfego. Tiers: **found** = lido diretamente no código/assets, **inferred** = deduzido do código, **unknown** = não resolvido. Nomes obfuscados são por build e foram resolvidos em 2.26.41.6 a partir de strings estáveis (constantes `FIELD_NUMBER`, nomes de interface AIDL, catálogos de operação GraphQL, nomes de arquivo de asset).

| Camada | Nome/caminho em 2.26.41.6 | Papel |
|-------|------------------------|------|
| Protocolo de mensagem do chat | `DSJ` SendPaymentMessage, `C30605DSz` RequestPaymentMessage, `C30502DPa` DeclinePaymentRequestMessage, `DPZ` CancelPaymentRequestMessage, `DT0`/`C30535DQh` pagamento dividido, `C30586DSg` PaymentInviteMessage, `C43112IrN` PaymentReminderMessage, `DTS` PaymentInfo | campos na seção 2 |
| Pacotes de rail | `com.whatsapp.payments.{common,indiaupi,brazilpay,mexico,indonesia,globalorder,upr,dcp,remittances,split,paymentkey,productinfra,integrity,phoenix}` | um pacote por mercado/rail, seção 3 |
| Biblioteca de credencial UPI da Índia | `org.npci.upi.security.{services,pinactivitycomponent}` (`CLRemoteService`, `CLRemoteServiceImpl`, `BinderC48420LDc`, `GetCredential`) | "Common Library" (CL) embutida da NPCI, seção 6 |
| Auto-leitura de OTP | `assets/npci/npci_otp_rules.json`, consumidor `org.npci.upi.security.pinactivitycomponent.C0315u` | seção 10 |
| Catálogo GraphQL/MEX | `assets/whatsapp-android-www_client_persist_ids.json` (schema `whatsapp`), `whatsapp-android-mex_client_persist_ids.json` (schema `whatsapp_mex`) | doc_ids, seção 9 |
| Handler de push do servidor | `C24410wL` ("PaymentsMessageHandler", log tag `PaymentsMessageHandler`) | `<notification type="pay\|upi\|fbpay\|transaction\|account-recovery\|alert\|...">`, seção 8 |
| Objeto de transação | `F7F` (linha de transação local), `DTS` (wire/history-sync PaymentInfo), construído por `EKY.A00` | seção 8 |

Rails identificados a partir de nomes de pacote/classe (found): **UPI da Índia** (`indiaupi`), **Pix do Brasil** (`brazilpay`), **México** (`mexico`), **Indonésia** (`indonesia`), além de um pacote agnóstico de rail "**UPR**" (`upr` — onboarding, gestão de conta, bubble UI) e uma referência legada ao Meta Pay/Novi ainda presente em código de enum/notificação (`FBPAY`, `NOVI`), embora esses serviços estejam há muito tempo descontinuados — mantidos aqui apenas porque as strings literais ainda existem em 2.26.41.6. As evidências abaixo são marcadas **específicas de India/UPI** ou **gerais** por seção; não assuma que achados sobre UPI se aplicam a Pix/México/Indonésia.

---

## 2. Tipos de mensagem de pagamento e campos proto

### 2.1 Posicionamento em `Message` (found)

Todos os tipos de mensagem de pagamento são campos diretos da proto de nível superior `Message` (`C30628DTw`, mesma classe documentada em `WA_MESSAGE_SECRETS.md`). A maioria das submensagens de pagamento **não** expõe constantes `FIELD_NUMBER` públicas na própria `Message`; os números abaixo foram recuperados decodificando a string de message-info compactada (`GeneratedMessageLite`) da classe (uma codificação reproduzível de 2 ou 3 caracteres por campo: caractere do número do campo, caractere marcador de tipo, caractere de índice do has-bit; o índice do has-bit incrementa exatamente um por entrada ao longo da mensagem completa de ~150 campos, o que é uma forte verificação interna de consistência sobre a decodificação).

| Campo (Message) | Número | Tipo |
|---|---|---|
| `sendPaymentMessage` | **16** | `SendPaymentMessage` (`DSJ`) |
| `requestPaymentMessage` | **22** | `RequestPaymentMessage` (`C30605DSz`) |
| `declinePaymentRequestMessage` | **23** | `DeclinePaymentRequestMessage` (`C30502DPa`) |
| `cancelPaymentRequestMessage` | **24** | `CancelPaymentRequestMessage` (`DPZ`) |
| `paymentInviteMessage` | **44** | `PaymentInviteMessage` (`C30586DSg`) |
| `splitPaymentMessage` | não decodificado nesta passada | `SplitPaymentMessage` (`DT0`), `unknown` |
| `splitPaymentUpdateMessage` | não decodificado nesta passada | `SplitPaymentUpdateMessage` (`C30535DQh`), `unknown` |
| `paymentReminderMessage` | não decodificado nesta passada | `PaymentReminderMessage` (`C43112IrN`), `unknown` |

O classificador de stanza `<message type="pay">` (compartilhado com outros add-on types) está documentado em `WA_MESSAGE_SECRETS.md`, na seção sobre o seletor de tipo (`AbstractC30999De0.A02`); não re-derivado aqui.

### 2.2 SendPaymentMessage (`DSJ`, found)

| Campo | Número | Tipo | Uso |
|---|---|---|---|
| `noteMessage` | **2** | `Message` (`C30628DTw`) | a "nota" anexada a um pagamento é ela mesma uma `Message` completa (normalmente carrega apenas um `extendedTextMessage` ou sticker) |
| `requestMessageKey` | **3** | `MessageKey` (`BD5`) | presente quando este envio é uma resposta a um `requestPaymentMessage` anterior |
| `background` | **4** | `PaymentBackground` (`DTJ`) | seção 2.7 |
| `transactionData` | **5** | string | opaco; o valor padrão no código decompilado é uma constante de string vazia compartilhada, não um default real |

O número de campo 1 está não utilizado/reservado (sem constante `FIELD_NUMBER` para ele).

### 2.3 RequestPaymentMessage (`C30605DSz`, found)

| Campo | Número | Tipo | Uso |
|---|---|---|---|
| `currencyCodeIso4217` | **1** | string | código ISO 4217 |
| `amount1000` | **2** | int64 | valor × 1000 (ponto fixo, sem decimais no valor transmitido) |
| `requestFrom` | **3** | string | identificador do solicitante (string de JID observada nos call sites) |
| `noteMessage` | **4** | `Message` | mesmo padrão da 2.2 |
| `expiryTimestamp` | **5** | int64 | segundos unix |
| `amount` | **6** | `Money` (`C30561DRh`) | valor estruturado, seção 2.7 |
| `background` | **7** | `PaymentBackground` (`DTJ`) | seção 2.7 |

### 2.4 DeclinePaymentRequestMessage / CancelPaymentRequestMessage (found)

Ambas as mensagens são mínimas — um único campo referenciando a solicitação original:

| Classe | Campo | Número | Tipo |
|---|---|---|---|
| `DeclinePaymentRequestMessage` (`C30502DPa`) | `key` | **1** | `MessageKey` (`BD5`) |
| `CancelPaymentRequestMessage` (`DPZ`) | `key` | **1** | `MessageKey` (`BD5`) |

**Nenhuma das duas mensagens carrega um campo de motivo/código de erro.** Decline e cancel são no-ops de protocolo além de "esta solicitação (identificada por `key`) foi recusada/cancelada" — qualquer texto de motivo mostrado na UI é apenas local, não parte do payload transmitido (found: não existe um segundo campo em nenhuma das classes; ver seção 12).

### 2.5 Pagamentos divididos (found)

`SplitPaymentMessage` (`DT0`):

| Campo | Número | Tipo |
|---|---|---|
| `splitId` | **1** | string |
| `totalAmount` | **2** | `Money` |
| `description` | **3** | string |
| `requesterJid` | **4** | string |
| `participants` | **5** | repeated `SplitPaymentParticipant` (`C30558DRe`) |
| `createdAtMs` | **6** | int64 |
| `contextInfo` | **17** | tipo semelhante a `MessageContextInfo` (`C30617DTl`) |

`SplitPaymentUpdateMessage` (`C30535DQh`): `splitId` (**1**, string), `participantJid` (**2**, string) — um ping de status por participante, sem payload próprio de valor/status.

### 2.6 PaymentInviteMessage / PaymentReminderMessage (found)

`PaymentInviteMessage` (`C30586DSg`): `serviceType` (**1**, int/enum — ligado aos códigos de serviço `UPI`/`PIX`/`NOVI`/`FBPAY` vistos na seção 8), `expiryTimestamp` (**2**, int64), `incentiveEligible` (**3**, bool), `referralId` (**4**, string), `inviteType` (**5**, int/enum).

`PaymentReminderMessage` (`C43112IrN`):

| Campo | Número | Tipo |
|---|---|---|
| `reminderId` | **1** | string |
| `instanceId` | **2** | string |
| `description` | **3** | string |
| `frequency` | **4** | int/enum |
| `status` | **5** | int/enum |
| `payeeVpa` | **6** | string |
| `payeeJid` | **7** | string |
| `payerJid` | **8** | string |
| `amount` | **9** | `Money` |

`payeeVpa` (campo 6) é um **campo VPA literal no protocolo de transmissão** — confirmação direta a nível de proto de que endereços de pagamento virtual (VPA) do UPI viajam dentro de mensagens de chat, não só por canais laterais GraphQL.

### 2.7 Tipos de suporte (found)

| Tipo | Classe | Campos |
|---|---|---|
| `Money` | `C30561DRh` | `value` (**1**, int64), `offset` (**2**, int32 — deslocamento do ponto decimal), `currencyCode` (**3**, string) |
| `MessageKey` | `BD5` | `remoteJid` (**1**, string), `fromMe` (**2**, bool), `id` (**3**, string), `participant` (**4**, string) |
| `PaymentBackground` | `DTJ` | `id` (**1**, string), `fileLength` (**2**, int64), `width` (**3**, int32), `height` (**4**, int32), `mimetype` (**5**, string), `placeholderArgb` (**6**, int32), `textArgb` (**7**, int32), `subtextArgb` (**8**, int32), `mediaData` (**9**, `MediaData` `C30588DSi`), `type` (**10**, enum) |

### 2.8 PaymentInfo — objeto de status de transação (found)

`DTS` ("PaymentInfo") **não** é um tipo de mensagem de chat; é anexado ao `WebMessageInfo` (`C30626DTu`, o carrier de history-sync/companion documentado em `WA_MESSAGE_SECRETS.md`) como `paymentInfo_` e `quotedPaymentInfo_`. Representa o status conhecido atual de uma transação de pagamento, construído a partir da linha de transação local por `EKY.A00`:

| Campo | Número | Tipo | Nota |
|---|---|---|---|
| `currencyDeprecated` | **1** | enum | legado |
| `amount1000` | **2** | int64 | |
| `receiverJid` | **3** | string | |
| `status` | **4** | enum | status grosseiro |
| `transactionTimestamp` | **5** | int64 | |
| `requestMessageKey` | **6** | `MessageKey` | |
| `expiryTimestamp` | **7** | int64 | |
| `futureproofed` | **8** | bool | definido quando o objeto de transação local do remetente não tem moeda/valor resolvível (escape hatch de evolução de schema) |
| `currency` | **9** | string | |
| `txnStatus` | **10** | enum | status mais detalhado (nível NPCI), enum separada de `status` |
| `useNoviFiatFormat` | **11** | bool | flag legada de formato de exibição do Meta Pay/Novi |
| `primaryAmount` | **12** | `Money` | |
| `exchangeAmount` | **13** | `Money` | exibição cross-currency |

Os **nomes** das constantes da enum `status`/`txnStatus` são apagados pelo obfuscador no nível de bytecode javalite (restam apenas ordinais + classes `EnumVerifier`); o mapeamento ordinal→label é `unknown` nesta passada. `EKY.A00` lê a moeda/valor do objeto de transação local e, quando ausente, define `futureproofed=true` em vez de adivinhar — found no código (guard `f7fA00.A03 == 5 || !f7fA00.A0N()`).

---

## 3. Arquitetura de cliente multi-rail ("payment-common-library")

O código de pagamento é organizado como um pacote de UI/infraestrutura compartilhado mais um pacote por rail de mercado (found, pelo layout de pacotes sob `com.whatsapp.payments`):

| Pacote | Rail | Conteúdo (found) |
|---|---|---|
| `common` | compartilhado | `p144ui` (bottom sheets de pagamento genéricos, configurações, histórico de transações, seletores de método), `pin` (UI de entrada de PIN compartilhada entre rails), `paymentkeys`, `compliance`, `care` (CSAT), `qpl` (marcadores de logging de qualidade/performance) |
| `indiaupi` | UPI da Índia | onboarding, vinculação de banco/VPA, mandates, pagamento de contas, UPI Lite, QR, recuperação de conta — seção 4 |
| `brazilpay` | Pix do Brasil | gestão de chave Pix, cadastro biométrico/passkey, CPF |
| `mexico`, `indonesia` | rails locais | presentes como pacotes; não explorados além da existência nesta passada (detalhe `unknown`) |
| `upr` | agnóstico de rail | `nux` (onboarding), `accountmanagement`, `bubble` (sheet de opções de pagamento no chat), `shared` (seletores de instituição/tipo de conta) — mapeia para as operações GraphQL `GenUprPaymentConfig`/`GenUprPaymentConfigForViewer` (seção 9); a expansão de "UPR" não é explicitada em nenhuma string encontrada (`inferred`: "Universal/Unified Payment Rail") |
| `globalorder`, `remittances`, `split`, `paymentkey`, `productinfra`, `integrity`, `dcp`, `phoenix` | misto | presentes como pacotes; `integrity` contém um bottom sheet de "fricção" de pagamento (UI de risco/step-up), `dcp` e `phoenix` não tiveram arquivos resolvidos sob seus dois níveis superiores de diretório nesta passada (`unknown`) |

O transporte GraphQL cross-rail é envolvido por `PaymentsMexGraphQlClient$ApiEventCallBuilder` (`com.whatsapp.payments.indiaupi.common.graphql`, apesar do nome do pacote é o wrapper de chamada MEX compartilhado, found) — decora toda chamada MEX de pagamento com callbacks de início/sucesso/falha de logging QPL/evento (`FDA.BYz`) antes de delegar ao transporte subjacente `InterfaceC17070jD`. Esta é a correspondência mais próxima neste build de uma "biblioteca comum de pagamento" no nível do **cliente**: uma classe wrapper de chamada obfuscada, reutilizada pelos gerenciadores GraphQL do UPI da Índia (`IndiaUpiChangeMpinGraphqlManager`, `IndiaUpiCheckBalanceGraphqlManager`, `IndiaUpiEnrollIncentiveGraphqlManager`, etc. — found, mesmo pacote).

Separadamente, a Índia embarca uma biblioteca **de terceiros** embutida sob o pacote de propriedade da NPCI `org.npci.upi.security.*` (não `com.whatsapp.*`) — esta é a "CL" ("Common Library") referenciada pelos próprios assets `.properties` da NPCI (`version.properties`, `validation.properties`, `cl-*.properties`) e é coberta na seção 6. O vocabulário dos próprios assets NPCI (`salt`, `payInfo`, `controls`, `configuration`, `trust`, `keyXmlPayload`, `keyCode`) corresponde exatamente às strings de chave de bundle encontradas nas implementações `CLRemoteService.Acc`/`Acf` deste build (seção 6) — corroboração direta, neste build, de uma análise anterior apenas de assets. A expansão literal "Common Library" ainda não é explicitada em nenhuma string (`inferred`, agora corroborada pelos próprios nomes de classe `CLRemoteService`/`CLResultReceiver`/`CLRemoteServiceImpl`, o que é evidência nova desta passada).

---

## 4. Vinculação de VPA/conta bancária e onboarding UPI (específico da Índia)

Nomes de activity recuperados de `com.whatsapp.payments.indiaupi.*` (found, apenas existência e nomenclatura de classe — a ordem exata de navegação entre elas é `inferred` a partir da nomenclatura e NÃO rastreada via grafos de intent nesta passada):

| Etapa | Activity/Fragment |
|---|---|
| Entrada / proposta de valor | `IndiaUpiPaymentsValuePropsActivity`, `IndiaUpiPaymentsValuePropsBottomSheetActivity`, `IndiaUpiPaymentsTosActivity` |
| Verificação de SIM | `IndiaUpiSimPickerDialogFragment`, `IndiaUpiSimVerificationActivity` |
| Seleção de banco | `IndiaUpiBankPickerActivity` (pacote `onboarding`), `IndiaUpiBankAccountPickerActivity` |
| Verificação de identidade/cartão | `IndiaUpiDebitCardVerificationActivity`, `IndiaUpiAadhaarCardVerificationActivity`, `IndiaUpiDobPickerActivity` |
| Vinculação de dispositivo | `IndiaUpiDeviceBindStepActivity` (ver seção 6 para a criptografia por trás desta etapa) |
| Configuração de PIN | `IndiaUpiPinPrimerDialogFragment` / `...FullSheetActivity`, `IndiaUpiPinHandlerActivity`, `IndiaUpiPinSetUpCompletedActivity`, `IndiaUpiChangePinActivity`, `IndiaUpiForgotPinDialogFragment` |
| Conclusão | `IndiaUpiBankAccountAddedLandingActivity`, `IndiaUpiPaymentsAccountSetupActivity` |
| Mapeador de número para VPA | `IndiaUpiMapperValuePropsActivity` → `IndiaUpiMapperLinkActivity` → `IndiaUpiMapperPendingActivity` → `IndiaUpiMapperConfirmationActivity`; `IndiaUpiCreateCustomNumberActivity` para um número de celular não padrão |
| Resolução de contato VPA | `IndiaUpiVpaContactInfoActivity`, `IndiaUpiSendPaymentToVpaFragment` |

"Mapper" aqui é o termo da própria NPCI para o serviço de diretório número de telefone↔VPA; as quatro activities `mapper.register.*` implementam esse sub-fluxo de registro específico (found: caminho de pacote `indiaupi.p148ui.mapper.register`).

Operações GraphQL relevantes para a vinculação com variáveis verificadas em call-site (found, de `com.whatsapp.payments.indiaupi.common.graphql.*` e classes `X/*` relacionadas; ver seção 9 para o catálogo completo):

| Operação | doc_id | Variáveis (found) |
|---|---|---|
| `GetUpiBankList` | `27764018976534565` | `account_type`, `provider_type`, `request` |
| `GetUpiAccounts` | `25691302307224710` | `bank_code`, `device_id`, `provider_type`, `account_type` |
| `GetUpiToken` | `25639185495767704` | `challenge`, `device_id`, `token_type`, `provider_type` |
| `GenCreatePaymentKey` | `24662763616751127` | `add_bank`, `account_holder_name`, `display_name`, `payment_method_type`, `payment_account`, … (superconjunto ruidoso, caller compartilhado entre várias ops — ver ressalva na seção 9) |
| `SetUpiChangeMpin` | `27149786891388216` | `credential_fbid`, `device_id`, `new_mpin`, `old_mpin`, `seq_no`, `upi_bank_info`, `vpa` |

---

## 5. Configuração/onboarding de pagamento (geral, cross-rail)

O pacote `upr` implementa uma shell de onboarding agnóstica de rail: `UprOnboardingActivity` → `UprOnboardingFragment` → `UprAccountTypePickerBottomSheet` → `AddPaymentMethodFragment` / `UprInstitutionPickerBottomSheet` (found, apenas nomes de classe; ordem do fluxo `inferred`). A gestão de conta após a configuração passa por `UprAccountManagementActivity`/`UprAccountManagementListFragment`, e o gatilho de pagamento no chat aparece via `UprPaymentOptionsBottomSheet`/`UprPaymentAccountDetailBottomSheet` (pacote "bubble" — o sheet flutuante de opções de pagamento aberto a partir de um chat).

A configuração server-side para essa shell é obtida via `GenUprPaymentConfig` (doc_id `26905963415743456`) e `GenUprPaymentConfigForViewer` (doc_id `37307071662269517`) — found no catálogo de doc_id, não verificado independentemente por call-site nesta passada (variáveis `unknown`).

---

## 6. "Common Library" (CL) da NPCI: credencial, PIN e vinculação de dispositivo (específico de India/UPI)

### 6.1 Arquitetura (found)

A entrada de PIN e o tratamento de credenciais bancárias do UPI da Índia são delegados a um serviço Android AIDL embutido, de propriedade da NPCI, totalmente separado do próprio código `com.whatsapp.*` do WhatsApp:

```
org.npci.upi.security.services.CLRemoteService      <- AIDL interface
org.npci.upi.security.services.CLResultReceiver     <- AIDL callback interface
org.npci.upi.security.pinactivitycomponent.CLRemoteServiceImpl  <- Android Service, binds the AIDL
org.npci.upi.security.pinactivitycomponent.BinderC48420LDc      <- Binder implementation of CLRemoteService
org.npci.upi.security.pinactivitycomponent.GetCredential        <- PIN-entry Activity launched by the binder
org.npci.upi.security.pinactivitycomponent.Keypad               <- on-screen keypad widget
```

Métodos de `CLRemoteService` (found, assinaturas de interface): `AQR(otpResultJson)`, `AZO(mode, nonce)` (desafio-resposta de vinculação de dispositivo, seção 6.2), `Acc(...)`/`Acf(...)` (inicia a activity de PIN com um bundle de credencial), `BBj(...)` (leitura de saldo), `BVz/CRh/CRi(...)` (validação de certificado/estado do dispositivo), `BW1()` (verificação de integridade do dispositivo).

### 6.2 Vinculação de dispositivo e troca de credenciais (found)

`BinderC48420LDc.AZO(mode, nonce)`:
- modo "initial": constrói `deviceId|randomHex|nonce`, criptografa com RSA contra um certificado NPCI embutido (`MYU.A00`), codifica em base64, retorna `"2.3-v1.8|" + ciphertext`. O prefixo `2.3-v1.8` é uma tag de versão de protocolo CL fixa no código (literal, found).
- modo subsequente: deriva uma chave AES do registro de credencial armazenado, criptografa com AES/GCM a mesma tripla `deviceId|randomHex|nonce` com um IV aleatório novo, retorna `ciphertext|iv` sob o mesmo prefixo de versão.

`BinderC48420LDc.Acc`/`Acf` constroem um `Bundle` com as chaves `keyCode`, `keyXmlPayload`, `controls`, `configuration`, `salt`, `payInfo`, `trust`, `languagePref` e iniciam a activity `GetCredential` com ele (found, chaves de string literais) — este é exatamente o vocabulário que uma análise anterior apenas de assets de `version.properties`/`validation.properties` inferiu que o esquema "CL" usaria (`salt`, `payInfo`); o código deste build confirma que essas são chaves de bundle reais em tempo de execução, não apenas placeholders de arquivo de asset.

`C51962N8y` (helper de criptografia usado em todo o binder):
- `A00`: gera um **par de chaves RSA-2048 dentro do Android KeyStore**, `CN=NPCI_CERT`, SHA-512/PSS, requer hardware seguro (`isInsideSecureHardware()`, lança exceção caso contrário) e (dependendo do SDK) autenticação do usuário dentro de uma janela de validade curta — esta é a chave de vinculação de dispositivo.
- `A03`/`A04`: AES/GCM-NoPadding, tag de 128 bits, chave e IV fornecidos explicitamente pelo chamador — criptografia/descriptografia no nível de sessão.
- `A02`: digest SHA-256 (hash do desafio).
- `A01`: descriptografa uma string no formato `ciphertext|iv` usando uma chave AES armazenada — pareado com o formato de saída do `AZO` acima.

`BinderC48420LDc.BW1()` executa uma verificação de root/adulteração (tags de build, caminhos comuns do binário `su`, probe `which su`) **e** verifica se a chave RSA recém-gerada é backed por StrongBox/TEE; uma verificação falha faz `BW1()` retornar `false`, o que bloqueia o caminho de emissão de credencial a montante (found: valor booleano de retorno consumido pelos caminhos de lógica `CRh`/`CRi`, não rastreado independentemente até uma mensagem de UI).

### 6.3 O que isso significa para o conteúdo da mensagem

O MPIN do UPI em si nunca aparece em uma mensagem de chat nem nos campos proto da seção 2 deste relatório — é tratado inteiramente dentro da activity `GetCredential` e trocado com o banco emissor/switch da NPCI através da camada RSA/AES acima, produzindo um *blob de credencial* opaco que é o que eventualmente chega às variáveis GraphQL como `new_mpin`/`old_mpin`/`mpin` em `SetUpiChangeMpin`/`CheckUpiBalance` (seção 9). Que a string que uma variável GraphQL realmente carrega já esteja criptografada pela NPCI (em vez de texto plano do cliente protegido apenas por TLS) é **inferred** a partir do propósito do fluxo CL que a precede, não confirmado independentemente ao ler o conteúdo de bytes do call site GraphQL.

---

## 7. Camadas de criptografia: E2E do chat vs. blob de credencial NPCI

Duas camadas de criptografia independentes estão envolvidas em um pagamento, e não devem ser confundidas (seção 13):

| Camada | Protege | Mecanismo | Evidência |
|---|---|---|---|
| E2E da mensagem de chat | a proto `Message` inteira, incluindo todos os campos da seção 2 (valor, nota, VPA em `payeeVpa`, JIDs, referências `MessageKey`) | criptografia de sessão padrão do WhatsApp via protocolo Signal/Noise — fora do escopo deste relatório, ver outros relatórios de RE para essa camada | não re-derivado aqui |
| Blob de credencial/vinculação de dispositivo da NPCI | MPIN, desafio-resposta de vinculação de dispositivo, payloads de verificação de risco trocados com o banco emissor via NPCI | RSA-2048 (KeyStore, vinculado a TEE, `CN=NPCI_CERT`) para vinculação de dispositivo; AES/GCM-128 com IV explícito para dados de sessão; SHA-256 para hash de desafio | seção 6.2, found |

A segunda camada é **específica de India/UPI** e roda abaixo/antes da chamada GraphQL, nunca dentro da proto `Message` do chat. Não foi encontrada uma camada AES/RSA específica de pagamento para Pix do Brasil ou México nesta passada (`unknown` — não explorado).

---

## 8. Sincronização de status de transação

### 8.1 Objeto local e history sync (found)

`F7F` é o objeto de transação de pagamento em memória/local (obtido via `D8X.A00(c13g)` a partir da linha de mensagem genérica `C13G`). `EKY.A00` converte-o no `PaymentInfo` (`DTS`, seção 2.8) de nível de transmissão anexado a `WebMessageInfo.paymentInfo_`/`quotedPaymentInfo_` para exportação via history-sync/companion.

### 8.2 Atualizações de status enviadas pelo servidor (found, `C24410wL` "PaymentsMessageHandler")

O canal de push voltado ao cliente é uma stanza `<notification>` com um atributo `type` despachado por `PaymentsMessageHandler.A0A`. Valores de `type` observados e seu tratamento:

| `type` | Tratamento |
|---|---|
| `pay` (com `hash`) | hash base64 decodificado, enfileirado como refresh USync de side-list (conjunto de protocolo `EnumC21760rz.A0Q`, `C21820s6.A0N`) — reutiliza o mecanismo USync documentado em `WA_USYNC.md` em vez de carregar o próprio status |
| `transaction` | faz parse da transação via `C24880x6.A07`, registra `onPaymentTransactionStatusUpdate`, atualiza o `F7F` local, expõe uma string de erro de transação para qualquer UI conectada (`InterfaceC35566Fb1.BIp`), e (sob gating das flags **1746** + **5049**) pode construir um card "custom item" de resumo de pedido para um nudge educativo pós-pagamento |
| `upi` | `consumer_status{value,dhash}` → `onPaymentConsumerStatusUpdate` (ping de elegibilidade de consumidor específico da Índia, distinto do status de transação) |
| `fbpay` | ping legado de elegibilidade do Meta Pay, mesmo caminho de handler que `upi` com uma chave de mapa de oferta diferente |
| `account-recovery` | `service=UPI` ou `service=BR`; conduz os fluxos de recuperação de conta de India/Brasil, sob gating das flags **1644**/**2000** |
| `alert`, `step_up`, `merchant_status`, `merchant-update`, `account`, `kyc-state`, `invite`, `alias`, `age_verification_update`, `document_verification_status` | nudges de UI/atualizações de compliance diversos, não status de transação |

### 8.3 Controle de sincronização (found, strings de chave de preferência)

`payments_all_transactions_last_sync_time`, `payments_block_list_last_sync_time`, `payments_error_map_last_sync_time_millis` — existem sincronizações periódicas de lista completa e de mapa de erros (classes consumidoras não totalmente rastreadas nesta passada; `unknown` cadência).

---

## 9. Operações GraphQL/MEX de pagamento

### 9.1 Dois transportes, dois schemas (found)

| Schema | Transporte | Contagem (neste build) |
|---|---|---|
| `whatsapp` (catálogo `www`) | POST GraphQL de doc_id persistido, mecanismo de transporte em si `inferred` (não rastreado até um call site HTTP/IQ nesta passada) | 81 operações marcadas como pagamento |
| `whatsapp_mex` (catálogo `mex`) | IQ `w:mex` sobre a conexão de stanza existente (`xmlns="w:mex"`) | 1 operação marcada como pagamento: `PaymentsIsAccountRecoverable` (doc_id `27351347491148282`) |

Fonte: `assets/whatsapp-android-www_client_persist_ids.json` e `assets/whatsapp-android-mex_client_persist_ids.json`, ambos assets declarativos próprios lidos em tempo de execução (found, o tier mais forte além de uma captura de tráfego — os próprios valores de doc_id não são "tested", apenas confirmados presentes no asset enviado).

### 9.2 Operações representativas com variáveis verificadas em call-site (found)

| Operação | doc_id | Tipo | Variáveis |
|---|---|---|---|
| `GetUpiAccounts` | `25691302307224710` | Query | `bank_code`, `device_id`, `provider_type`, `account_type` |
| `CheckUpiBalance` | `37205951525662520` | Query | `credential_fbid`, `device_id`, `mpin`, `seq_no`, `upi_bank_info`, `vpa`, `cl_version`, `device_ssid`, `request` |
| `SetUpiChangeMpin` | `27149786891388216` | Mutation | `credential_fbid`, `device_id`, `new_mpin`, `old_mpin`, `seq_no`, `upi_bank_info`, `vpa` |
| `GetUpiBankList` | `27764018976534565` | Query | `account_type`, `provider_type`, `request` |
| `GetUpiToken` | `25639185495767704` | Query | `challenge`, `device_id`, `token_type`, `provider_type` |
| `UpiCreateMandate` / `UpiAcceptMandate` | `26775212245448044` / `26786867597629452` | Mutation | caller compartilhado (`C42562IuV`): `frequency_rule`, `mandate_no`, `purpose_code`, `recurrence_day`, `recurring_rule`, `ref_id`, `device_id`, `top_up_amount`, `provider_type`, `upi_banks`, `is_revocable`, … |
| `CreateEnrollment` | `34570903025891763` | Mutation | `participant_id`, `device_id` |
| `GenRaisePaymentComplaint` | `27569318002686860` | Query | `complaint_type`, `reason`, `transaction_ref_id`, `user_description` |
| `PaymentsIsAccountRecoverable` (MEX) | `27351347491148282` | Query | nenhuma encontrada (provavelmente `{}`) |

A presença da variável `mpin` em `CheckUpiBalance`, lida ao lado de `cl_version`, é consistente com a seção 6.3: o nome da variável isoladamente não prova que o conteúdo é pré-criptografado, mas ela viaja junto a uma string explícita de versão de protocolo CL, o que só faz sentido se o valor tiver se originado da troca CL.

**Ressalva (found como uma limitação, não um achado sobre o WhatsApp):** `GenCreatePaymentKey`, `RevokeEnrollment` e `BrSaveCPF` resolvem todas para as *mesmas* classes de caller compartilhadas (`C42325Iq9`/`C42327IqB`, `RunnableC42211IoJ`) no catálogo de origem, o que retorna todo literal de string próximo a esse caller como "variáveis" para as três ops — isso coleta em excesso (por exemplo, campos específicos do Pix como `pix_key` aparecem sob uma op com nome de UPI). Trate as longas listas de variáveis dessas três operações específicas como um superconjunto ruidoso, não um schema por operação confirmado.

As demais operações no catálogo de 81 entradas (lista completa: `UpiPauseMandate`, `UpiResumeMandate`, `UpiRevokeMandate`, `UpiRejectMandate`, `UpiExecuteMandate`, `GetUpiLiteDetails`, `GetUpiP2mConfig`, `GetUpiPurposeLimitingKey`, `GetUpiSmsContentAndVmn`, `PaymentReminderCreate/Get/Cancel/Stop`, `GetBillReceipt`, `GetBillerPlans`, Pix do Brasil (`GetPixInfo`, `GetPixBankList`, `GetMerchantPixInfo`, `CompletePixTransaction`, `GenPayWithPixPrecheck`), biométrico/passkey (`Br*Passkey*`, `BrAuthorizeBiometricPayment`), e as ops de assinatura/promoção `Wamo*`) estão catalogadas com seus doc_ids mas não foram re-verificadas individualmente contra um call site nesta passada — trate sua presença como `found` (são entradas literais no asset de 2.26.41.6) e seu formato exato de requisição como `unknown`, exceto as listadas acima.

---

## 10. Regras de auto-leitura de OTP da NPCI (específico de India/UPI)

`assets/npci/npci_otp_rules.json` (found, 5 regras) é consumido por `org.npci.upi.security.pinactivitycomponent.C0315u` para extrair automaticamente um OTP de 6 dígitos de um SMS bancário/NPCI recebido durante um fluxo UPI, puramente como conveniência de digitação — não gera, valida ou transmite o OTP. Todas as 5 regras compartilham `sender: ["[a-zA-Z]+"]` (código curto alfabético) e `otp: "\d{6}"`; apenas a frase de gatilho difere (`"is your OTP"`, `"OTP is"`, `"one time password is"`, `"is your one time password"`, `".*OTP for Aadhaar.*"`). O caller pode sobrescrever a regex de contagem de dígitos do OTP em tempo de execução (`\d{` + `i` + `}`) quando passa um length diferente de zero. Um corpo contendo `"Aadhaar"`/`"AADHAAR"` é cacheado sob a chave de SharedPreferences `otp_type_aadhaar`, caso contrário `otp_type_bank`.

Esse asset e a classe consumidora são inalterados em natureza em relação a uma análise anterior de `2.26.34.4`; não re-diferenciado byte a byte independentemente contra 2.26.41.6 nesta passada (continuidade `inferred`, não re-verificada).

---

## 11. Feature flags

IDs de AB-prop conforme lidos diretamente em `PaymentsMessageHandler` (`C24410wL`, call sites found) salvo indicação contrária. Nenhum ID de flag numérico foi encontrado controlando os campos proto da seção 2 em si (esses são incondicionais na transmissão); todas as flags encontradas nesta passada controlam o *tratamento* de pushes do servidor ou nudges de UI.

| Flag | Controla |
|---|---|
| **1458** | remove um alias de pagamento UPI cacheado localmente assim que o servidor reporta que ele foi `deregistered` |
| **1644** | elegibilidade de recuperação de conta UPI (`payments-enabled:account-recovery-enabled`) |
| **2000** | elegibilidade de recuperação de conta Pix do Brasil (gate equivalente para `service=BR`) |
| **1746** + **5049** (ambas necessárias) | card educativo "custom item"/resumo de pedido mostrado após um pagamento concluído (nudge educativo BIP) |
| **12214** | caminho de criação de usuário FB durante a recuperação de conta UPI (vs. chamada de recuperação direta) |
| **423** | rastreamento de convite usado em pagamentos, caminho mais antigo |
| **544** | rastreamento de convite usado em pagamentos, caminho adicional (verificado junto com 423 via OR) |
| **20869** | verificação de allow-list de PSP durante o tratamento de notificação de recuperação de conta; pref string pareada `32353` (lista de PSPs opt-in separada por vírgula, lida via uma AB prop de valor string, não uma flag numérica) |

Nenhum ID de feature flag foi encontrado controlando especificamente a sequência de activities de onboarding do UPI da Índia (seção 4) ou o caminho de vinculação de dispositivo CL da NPCI (seção 6) nesta passada — `unknown`, não rastreado além da classe de handler acima.

---

## 12. Códigos de erro/motivo de recusa

### 12.1 Recusa/cancelamento no protocolo (found)

Como estabelecido na seção 2.4, `declinePaymentRequestMessage`/`cancelPaymentRequestMessage` carregam **apenas** uma referência `MessageKey` à solicitação original — sem enum de motivo, sem campo de texto livre. Um cliente mostrando "recusado: fundos insuficientes" ou similar está fazendo isso a partir de estado **local** (a própria cópia de UI do remetente, ou um status `transaction`/`PaymentInfo` correlacionado posterior, seção 8), não a partir de algo que a própria mensagem de decline/cancel transmite.

### 12.2 Campos de status de PaymentInfo (existência found, mapeamento unknown)

`DTS.status_` (campo 4) e `DTS.txnStatus_` (campo 10) são campos de tipo enum separados (seção 2.8). Seu mapeamento ordinal→label não pôde ser recuperado apenas a partir do bytecode javalite (os nomes das constantes enum são apagados pela obfuscação das classes `Internal.EnumVerifier` deste build) — `unknown`. `futureproofed` (campo 8, bool) é um escape hatch deliberado definido quando o objeto local do remetente não tem valor/moeda resolvível, permitindo que um receptor em um cliente mais novo renderize um status que de outra forma não conseguiria parsear.

### 12.3 Mapa de erro enviado pelo servidor (chaves de pref found, consumidor não totalmente rastreado)

As chaves de preferência `payments_error_code`, `payments_error_text`, `payments_error_title`, `payments_error_map_tag`, `payments_error_map_last_sync_time_millis` indicam que códigos de erro são resolvidos contra um **mapa sincronizado pelo servidor** (código → título/texto), não uma enum fixa do lado do cliente ou tabela de strings. Isso significa que o texto de erro/recusa mostrado a um usuário pode mudar com o tempo/região sem uma atualização do app. A classe que realiza essa sincronização não foi identificada nesta passada (`unknown`).

### 12.4 Falhas da camada CL da NPCI (found, sem código estruturado)

`BinderC48420LDc.BW1()` (verificação de integridade do dispositivo), `CRH`/`CRh`/`CRi` (validação de certificado/estado do dispositivo) falham todos **silenciosamente** — retornam `false`/lançam exceção, sem código de erro exposto através da fronteira AIDL além do booleano. Qualquer mensagem visível ao usuário para uma falha na camada CL é, portanto, construída inteiramente do lado do WhatsApp a partir do resultado booleano, não a partir de um código fornecido pela NPCI (`inferred`, consistente com a forma da interface AIDL na seção 6.1 não ter métodos de retorno de código de erro).

---

## 13. Específico de India/UPI vs. geral — divisão explícita

| Achado | Escopo |
|---|---|
| Campos proto de `sendPaymentMessage`/`requestPaymentMessage`/`declinePaymentRequestMessage`/`cancelPaymentRequestMessage`/pagamento dividido/`PaymentInviteMessage`/`PaymentReminderMessage` (seção 2) | **geral** — mesmos campos proto de `Message` independentemente do rail; `payeeVpa` (seção 2.6) é o único nome de campo com sabor UPI, mas o campo em si está presente incondicionalmente no schema |
| Objeto de status de transação `PaymentInfo` (`DTS`) (seção 2.8, 8) | estrutura **geral**; `useNoviFiatFormat` e os códigos de serviço legados `FBPAY`/`NOVI`/`PIX`/`UPI` mostram que o mesmo objeto/caminho de notificação é compartilhado entre todos os rails |
| Pacotes de rail `indiaupi`, `brazilpay`, `mexico`, `indonesia`, `upr` (seção 3) | dividido explicitamente por pacote; `upr`/`common` são agnósticos de rail, o restante é de país único |
| Vinculação de VPA, fluxo de mapper UPI, activities de onboarding (seção 4) | **exclusivo de India/UPI** |
| Biblioteca "CL" de credencial/vinculação de dispositivo da NPCI, criptografia RSA/AES, auto-leitura de OTP (seções 6, 7, 10) | **exclusivo de India/UPI** — essa camada inteira está ausente para Pix/México/Indonésia no código explorado |
| Catálogo de doc_id GraphQL (seção 9) | misto — o próprio catálogo abrange UPI, Pix, biométrico/passkey (Brasil) e operações agnósticas de rail (`Wamo*`, `Gen*`) sob um único schema; o escopo de cada op segue seu próprio nome/prefixo (`Br*` = Brasil, `Upi*`/`GetUpi*`/`SetUpi*` = Índia) |
| Tipos de notificação do `PaymentsMessageHandler` (seção 8.2) | misto — tipos estilo `pay`/`transaction`/`alert`/`step_up`/`account` são genéricos; o tipo `upi` e os ramos `service=UPI` são específicos da Índia, os ramos `service=BR` são específicos do Brasil |

---

## 14. Nota sobre Baileys

Clientes estilo Baileys podem construir e parsear os tipos de mensagem da seção 2 (são campos protobuf simples na `Message` padrão) e podem, em princípio, chamar os doc_ids GraphQL `whatsapp`/`whatsapp_mex` com variáveis construídas manualmente. Eles **não conseguem** completar um pagamento UPI de forma significativa: a troca de MPIN/vinculação de dispositivo na seção 6 passa por um componente Android nativo embutido, assinado pela NPCI, vinculado a uma relação de confiança real com o backend do banco/NPCI (chave RSA backed por TEE, `CN=NPCI_CERT`) que não tem equivalente fora do app oficial. Um `sendPaymentMessage` do Baileys é, portanto, uma mensagem correta em termos de protocolo mas funcionalmente inerte, a menos que pareada com uma transação que foi de fato autorizada através do fluxo real da NPCI.

---

## 15. Casos de erro/pegadinhas

| Sintoma | Causa | Correção/nota |
|---|---|---|
| Mensagem de decline/cancel sem motivo visível na transmissão | design de protocolo (seção 2.4) — existe apenas uma referência de volta `MessageKey` | não espere um código de motivo da própria mensagem; correlacione com uma notificação `transaction` posterior ou estado local |
| Operação de credencial com gating de `BW1()` falha sem texto de erro | dispositivo sem StrongBox/TEE, ou está rooted | exposto apenas como falha booleana ao lado do WhatsApp; não pode ser distinguido de outras falhas de CL sem logging adicional |
| Variáveis GraphQL `mpin`/`new_mpin`/`old_mpin` parecem texto plano em um dump de call-site decompilado | são produzidas pela troca CL (seção 6.3), não digitadas diretamente na chamada GraphQL | não assuma transmissão de PIN em texto plano sem rastrear os bytes reais em tempo de execução — este relatório não afirma ter feito isso |
| `GenCreatePaymentKey`/`RevokeEnrollment`/`BrSaveCPF` mostram listas enormes de variáveis com sabor Pix | coleta em excesso por classe de caller compartilhada na extração do catálogo de doc_id (seção 9.2) | trate como ruidoso, verifique por campo antes de confiar |
| Valores enum de `txnStatus`/`status` não podem ser nomeados | `EnumVerifier` obfuscado apaga os nomes das constantes | requer correlação de string em tempo de execução (strings de recurso de UI mapeadas para ordinais), não feito nesta passada |

---

## 16. Distinções importantes

| Não confundir | Detalhe |
|---|---|
| E2E da mensagem de chat vs. blob de credencial NPCI (seção 7) | duas camadas de criptografia separadas; a segunda é exclusiva de India/UPI e fica totalmente fora da proto `Message` |
| `DTS` PaymentInfo vs. os quatro tipos de mensagem de pagamento do chat | `DTS` é um objeto de history-sync/status (`WebMessageInfo.paymentInfo_`), nunca uma mensagem de chat enviável isolada |
| `status` vs. `txnStatus` em `DTS` | duas enums independentes, granularidade diferente, ambas opacas no nível de ordinal neste build |
| Schema `www`/`whatsapp` vs. schema `mex`/`whatsapp_mex` de doc_ids | transporte diferente (POST GraphQL de doc_id persistido vs. IQ `w:mex`); quase todas as ops de pagamento estão do lado `www`/`whatsapp` neste build |
| Onboarding agnóstico de rail "UPR" vs. onboarding UPI da Índia | UPR (`com.whatsapp.payments.upr`) é uma shell genérica mais nova; as activities de onboarding específicas da Índia `indiaupi` (seção 4) são um fluxo separado, mais antigo e muito maior, ainda presente lado a lado em 2.26.41.6 |
| "Common Library" da NPCI (`org.npci.upi.*`) vs. o próprio código `com.whatsapp.payments.*` do WhatsApp | a primeira é um componente de terceiros embutido com sua própria superfície AIDL; o código do WhatsApp apenas a inicia e lê de volta uma string/bundle opaca |

---

## 17. Fluxo completo (UPI da Índia, caso de envio de dinheiro)

```
[Payer chat]                 [WhatsApp client]                    [NPCI CL component]            [NPCI / Issuer bank]
     │ tap "Pay"                    │                                      │                             │
     ▼                              ▼                                      │                             │
 open IndiaUpiSendPaymentActivity → IndiaUpiSendPaymentToVpaFragment       │                             │
     │                              │ amount/VPA/note entered              │                             │
     │                              ▼                                      │                             │
     │                     CLRemoteService.Acc(keyCode, keyXmlPayload,     │                             │
     │                       controls, configuration, salt, payInfo, …) ──►│                             │
     │                              │                                GetCredential activity (PIN pad)    │
     │                              │                                      │ user enters MPIN            │
     │                              │                             AZO(): RSA/AES challenge-response ────►│
     │                              │                                      │◄──── signed/verified ────── │
     │                              │◄──── opaque credential blob ─────────│                             │
     │                              │                                      │                             │
     │                     build RequestPaymentMessage / SendPaymentMessage (section 2)                  │
     │                              │ amount, note, requestMessageKey, background                        │
     │                              ▼                                                                     │
     │                     chat E2E encrypt, send as normal <message>                                    │
     │                              │                                                                     │
     │                     CheckUpiBalance / SetUpiChangeMpin / mandate GraphQL op ─────────────────────► │
     │                              │          (credential_fbid, device_id, mpin blob, vpa, seq_no)       │
     │                              │◄──────────────── result / error (section 12.3 error map) ────────── │
     ▼                              ▼                                                                     │
[Payee chat]            server pushes <notification type="transaction"> ──────────────────────────────── │
     │                              │  PaymentsMessageHandler.A0A updates local F7F,                      │
     │                              │  EKY.A00 builds PaymentInfo (DTS) for history sync                  │
     ▼                              ▼
 status shown in chat        transaction row updated, payments_all_transactions_last_sync_time bumped
```

---

## 18. Desconhecidos

| Tópico | Motivo |
|---|---|
| Números de campo de nível superior em `Message` para `splitPaymentMessage`, `splitPaymentUpdateMessage`, `paymentReminderMessage` | decodificação da string de info não levada longe o suficiente nesta passada; os próprios campos da submensagem (seção 2.5/2.6) não são afetados |
| Mapeamento de label das enums `DTS.status_`/`txnStatus_` | `EnumVerifier` obfuscado, nomes das constantes apagados |
| Mecanismo exato de transporte para chamadas GraphQL de doc_id persistido do schema `whatsapp` (`www`) | não rastreado até um call site HTTP/IQ nesta passada; marcado `inferred` ao longo do relatório |
| Classe(s) consumidora(s) do mapa de erro sincronizado pelo servidor `payments_error_map_*` | chaves de pref encontradas, classe de leitura/escrita não identificada |
| Conteúdo dos pacotes `mexico`/`indonesia`/`dcp`/`phoenix` | existência do pacote confirmada, conteúdo não explorado |
| Se as variáveis GraphQL `mpin`/`new_mpin`/`old_mpin` carregam um blob já criptografado pela NPCI ou se proteção adicional é aplicada apenas no nível de TLS | inferred a partir do propósito do fluxo CL, não confirmado por inspeção do conteúdo de bytes real em tempo de execução |
| IDs de feature flag (se houver) controlando a sequência de onboarding UPI da Índia ou o próprio caminho de vinculação de dispositivo CL | nenhum encontrado nas classes exploradas |
| Continuidade byte a byte de `npci_otp_rules.json` e dos assets `.properties` CL entre `2.26.34.4` (uma análise anterior) e `2.26.41.6` | não re-diferenciado; as classes consumidoras e o vocabulário de chave de bundle em tempo de execução foram re-confirmados independentemente em 2.26.41.6, os bytes do asset em si não foram |
| Comportamento real de tráfego/transação em tempo real | apenas análise estática, sem captura de tráfego, nenhuma transação real executada |
