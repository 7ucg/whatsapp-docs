<!-- src-sha1: b8a925dee480430088a421b7aba690bc2f641a5f -->
# WhatsApp Account Security — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-22
**Escopo:** verificação de número de telefone em uma conta existente (HTTP de registro `/v2/*`), métodos de segundo fator, PIN de verificação em duas etapas e e-mail de recuperação, senha da conta (envelope `#PWD_WA`, dependência do canonical user), código nativo OPAQUE / VOPRF e o que ele realmente atende, login e gerenciamento de passkey, dispositivos confiáveis, recuperação de conta (troca de nonce do canonical user), soft logout / login-back, operações w:mex (doc_ids, variáveis, raízes de resposta), feature flags, notas sobre Baileys

---

## 1. O que é (tecnicamente)

"Segurança da conta" no cliente Android não é um único subsistema. São cinco mecanismos independentes sobrepostos ao fluxo de registro por número de telefone. Todas as afirmações são análise estática do APK decompilado; nada foi capturado na rede. Nível: **found** = lido no código ou nos assets, **inferred** = deduzido do código, **unknown** = não resolvido. Os nomes ofuscados mudam a cada build e foram re-resolvidos na 2.26.41.6.

| Mecanismo | Onde é imposto | Credencial | Principais classes do cliente (2.26.41.6) |
|-----------|---------------|------------|-------------------------------------------|
| Verificação de telefone (OTP) | HTTP de registro, `/v2/exist` → `/v2/code` → `/v2/register` | SMS / voz / flash / dispositivo antigo / OTP por e-mail / silent auth | `K49` (`RegistrationHttpManager`), `KotlinRegistrationBridge`, `AbstractC45307Jps` |
| Segundo fator no registro | `/v2/register` com reason `security_code`, depois `VerifyTwoFactorAuth` | PIN de 6 dígitos, senha da conta, OTP por e-mail | `VerifyTwoFactorAuth`, `EnumC43759JAu`, `HOZ` |
| Verificação em duas etapas (PIN + e-mail) | IQ `urn:xmpp:whatsapp:account` `<2fa>` | PIN de 6 dígitos, e-mail de recuperação opcional | `C1DP` (`TwoFactorAuthManager`), `C1DT` (`TwoFactorXmppMethods`) |
| Senha da conta | w:mex (`whatsapp-android-mex`, `whatsapp-android-www`) | 8-20 caracteres, letra + dígito | `PasswordRepository`, `PasswordServerApiImpl`, `CanonicalPasswordService` |
| Passkey (WebAuthn) | `/v2/passkey_auth` no login; IQ `passkey` ou w:mex para gerenciamento | passkey da plataforma via Credential Manager | `PasskeyServerApiImpl`, `PasskeyCreateFlow`, `PasskeyVerifier`, `K15` |
| Dispositivo confiável | w:mex | registro no servidor com chave no `ANDROID_ID` em hash | `TrustedDevicesServerApiImpl`, `RegTrustedDeviceGraphQLHelper` |
| Soft logout / login-back | w:mex | nenhuma (flag de estado) | `LogoutManager`, `LogoutPushManager` |
| Recuperação de conta | w:mex, Meta canonical user | envelope RSA/AES de um segredo gerado pelo cliente | `AccountRecoveryManager` |

Dois pontos que definem todo o relatório:

- A máquina de estados OPAQUE em `libwhatsapp.so` está ligada à senha do **backup criptografado de ponta a ponta** (handlers `encb/*`), não à senha da conta (seção 6).
- A senha da conta, neste build, é criada e alterada por meio de `XfbWaCreatePasswordMutation` / `XfbWaChangePasswordMutation` com um envelope RSA/AES (`#PWD_WA:11`), e somente se o app possuir credenciais de canonical user da Meta (seção 5).

---

## 2. Transportes e catálogo de operações

### 2.1 Quatro transportes

| Transporte | Usado para | Evidência |
|-----------|------------|-----------|
| HTTPS `/v2/<name>` (stack de registro) | verificação de telefone, segundo fator no login, asserção de passkey, confirmação de dispositivo | found: constantes de path em `AbstractC45307Jps` (seção 3.1) |
| IQ `xmlns="urn:xmpp:whatsapp:account"` | definir / verificar / obter PIN e e-mail; OTP do e-mail da conta; username etc. | found |
| IQ `xmlns="passkey"` (smax ids 125, 126, 129) | start / finish / clear de passkey legado | found, controlado pelas flags 10452 / 10453 / 10461 |
| IQ `xmlns="w:mex"` | todas as operações GraphQL abaixo | found |

### 2.2 Envelope w:mex e origem do doc_id

As variáveis são enviadas como JSON. Quase toda mutation embrulha seus campos em um único objeto: o helper `AbstractC197058a0.A17(obj, vars)` guarda o objeto sob a chave `input` (found). Exceções: as duas mutations `Xfb*` de senha colocam `encrypted_password` sob `data` (found); `PasskeyDeleteMutation` também usa `input` (via `c16770ig.A00(obj, "input")`).

Os doc_ids não são literais no código. O cliente envia o nome da operação mais um nome de config (`whatsapp-android-mex`, `whatsapp-android-www`, `whatsapp-android-facebook-schema`); o id numérico é lido de `assets/whatsapp-android-{mex,www,facebook-schema}_client_persist_ids.json` (found). Todo doc_id abaixo foi lido desses assets na 2.26.41.6 e o nome da operação foi conferido contra um call site. Nenhum é `tested`.

### 2.3 Catálogo de operações (call sites presentes)

As variáveis ficam dentro de `input`, salvo indicação. "Root" é o nome do objeto de resposta lido pelo cliente.

| Operação | doc_id | Config | Variáveis | Root e campos lidos |
|----------|--------|--------|-----------|---------------------|
| `HasPasswordQuery` | `25379221318423478` | mex | nenhuma | `xwa2_has_password`: `has_password`, `upgrade_needed` |
| `DeletePasswordMutation` | `27247058691550586` | mex | nenhuma | `xwa2_delete_password`: `success`, `twofa_auto_disabled`; o erro 409 significa "precisa de e-mail" |
| `GetTwofaQuery` | `27608881388708005` | mex | `device_id` | `xwa2_get_twofa`: `twofa_enabled`, `twofa_methods[]{method,value,state}`, `is_device_trusted`, `latitude`, `longitude` |
| `SetTwofaMutation` | `28092515560345874` | mex | `twofa_enabled` (bool), `device_id` | `xwa2_set_twofa`: `success`, `twofa_already_enabled`, `is_device_trusted` |
| `WaPasswordEncryptionKeyQuery` | `27318258844468227` | www | nenhuma | `wa_password_encryption_key`: `public_key` (PEM), `key_id` |
| `XfbWaCreatePasswordMutation` | `36595298760118580` | www | `data.encrypted_password` (não está sob `input`) | `xfb_wa_create_password` (campos de sucesso / erro não resolvidos) |
| `XfbWaChangePasswordMutation` | `27534818572826036` | www | `data.encrypted_password` | `xfb_wa_change_password` |
| `AddTrustedDeviceMutation` | `24522952587403287` | mex | `device_id`, `device_name` | `xwa2_add_trusted_device.list_of_trusted_device[]` |
| `UntrustTrustedDeviceMutation` | `26574930682133620` | mex | `device_id`, `reason` (`"REREG"` na única chamada) | root não resolvido |
| `DeleteTrustedDeviceMutation` | `33867503889559538` | mex | `device_id` | `xwa2_delete_trusted_device` (bool) |
| `GetTrustedDevicesQuery` | `27391232653862770` | mex | `device_id` | `xwa2_get_trusted_devices.list_of_trusted_device[]`: `device_id`, `device_name`, `latitude`, `longitude`, `last_ts` |
| `WhatsappTrustedDeviceRegistration` | `27335489319457030` | facebook-schema | `client_mutation_id`, `payment_type="TRUST_BINDING"`, `platform_trust_token`, `actor_id` / `logging_id` / `product_id` nulos | trust binding de pagamentos (`RunnableC53437NtS`), não o dispositivo confiável do login |
| `RegistrationPasskeyStartRegisterMutation` | `25415371271434748` | mex | nenhuma | `xwa2_passkey_start_register.credential_create` (string) |
| `RegistrationPasskeyFinishRegisterMutation` | `24611221275218156` | mex | `credential`, `key_attestation` | `xwa2_passkey_finish_register` (bool) |
| `RegistrationPasskeyEnableMutation` | `25147880151540247` | mex | `credential` | `xwa2_passkey_enable` (bool) |
| `RegistrationPasskeyClear` | `25111972538494859` | mex | nenhuma | `xwa2_passkey_clear` (bool) |
| `RegistrationPasskeyUpdateClientEncryptionStatusMutation` | `24866837389649930` | mex | `credential`, `status` (true) | `xwa2_passkey_update_client_encryption_status` (bool) |
| `PasskeyListExistResponseQuery` | `26930537423220681` | mex | nenhuma | `xwa2_passkey_exist_v2`: `result`, `uuid`, `passkeys[]{credential,create_ts_s,used_ts_s,password_manager,aaguid,usecases,is_disabled}` |
| `PasskeyDeleteMutation` | `25225683640428243` | mex | `credential_ids` (lista) | `xwa2_passkey_delete.credential_ids` |
| `AccountLoginMutation` | `27298465499757127` | mex | `phone_number` (string JID bruta) | não lido |
| `AccountLogoutMutation` | `26863447609979194` | mex | `enabled_biometric` (bool), `phone_number` | não lido; timeout de 5 s no cliente |
| `WWWTriggerAcountRecovery` | `24896267680055094` | mex | `nonce_encryption_key` (PEM em base64), `use_case`, `registration_trace_id`, `request_id` | o nonce é entregue por notificação (seção 9) |
| `WWWExchangeNonceForAccessToken` | `25727187160203620` | mex | `nonce`, `use_case`, `encrypted_password`, `request_id`, `registration_trace_id` | access token |
| `WWWGetNonceForCompanionDevice` | `24635485196143064` | mex | `fbid`, `nonce_encryption_key`, `encrypted_password`, `request_id`, `registration_trace_id` | canonical user do companion |
| `RegAccountTransferVerifyTokenMutation` | `7580940708621318` | mex | `token` | verificação do OTP de transferência de conta, timeout de 60 s |
| `ValidateVerifierConfidence` | `25879669248324812` | mex | `authResponse` (base64) | ping de confiança do autoconf |
| `GetRegistrationUpsells` / `GetDynamicRegistrationUpsells` / `RegistrationDynamicUpsellShown` | `24265038133175291` / `32273353145641323` / `25435755019399064` | mex | shown: `input="PASSKEYS"` (string) | agendamento de upsell no registro |

### 2.4 Operações nos assets sem call site neste build

Pesquisadas por nome em `java_src` e smali; sem referência (found). Suas variáveis e respostas são desconhecidas.

| Operação | doc_id |
|----------|--------|
| `SetPasswordMutation` | `33855141324134176` |
| `CheckPasswordMutation` | `26881928138061632` |
| `PasskeyExistResponseQuery` | `25188064727509430` |
| `PasskeyRequestChallengeMutation` | `26311497405176139` |
| `PasskeyVerifyChallengeMutation` | `26876394218624479` |
| `RegistrationPasskeyDisableMutation` | `27775237998742831` |

Na 2.26.41.6, um login com passkey não usa as mutations de request / verify; usa `/v2/passkey_auth` (seção 7.1). As operações de passkey de pagamentos (`PaymentsPasskey*`) e do Brasil (`BrPasskey*`) são superfícies separadas e não são cobertas.

---

## 3. Verificação de número de telefone em uma conta existente

### 3.1 Stack de registro e endpoints

`K49` (`RegistrationHttpManager`) monta as requisições e interpreta os resultados. Existem duas stacks HTTP: a bridge Kotlin (`KotlinRegistrationBridge`, `RetryingHttpClient`) e um cliente nativo `wamsys` acessado via `AbstractC45509Jtc` e `JniBridge.jvidispatch*`. O seletor `K49.A0b` retorna true se a config 24762 ou a flag **24763** estiver definida (found); as tags de log terminam em `/kotlin` ou `/wamsys`.

Os paths são ofuscados com XOR 0x12 em `AbstractC45307Jps` e decodificam para (found):

| Path | Função Kotlin | Campos enviados (além dos campos de dispositivo / e2e) |
|------|---------------|--------------------------------------------------------|
| `/v2/exist` | `performSameDeviceCheck` / `checkIfExists` | `lg`, `cc`, `in`, `foa_backup_token`, `client_capabilities`, `advertising_id`, `context`, `id`, `backup_token` |
| `/v2/challenge` | `challengeRequest` | challenge de login; resposta `login`, `challenge`, `retry_after` |
| `/v2/code` | `generateAuthCode` | `token`, `method`, `context`, `advertising_id`, `clicked_education_link`, `manage_call_permission`, `call_log_permission`, `client_start_message` |
| `/v2/register` | `registerPhoneNumber` | `code`, `auth_response` (bytes), `method`, `context`, `advertising_id`, mais entradas de map como `security_code`, `reset`, `wipe_token`, `cred_token` |
| `/v2/security` | `verifySecurityCode` | `code`, `reset`, `wipe_token` (path legado, flag 26215 desligada) |
| `/v2/passkey_auth` | `passkeyAuth` | `lg`, `context`, `credential` (resultado da asserção) |
| `/v2/device_logout_send`, `/v2/device_logout_fetch` | `sendAccountDefenceDeviceConfirmation`, `fetchAccountDefenceDeviceConfirmation` | `token` |
| `/v2/wfs` | `wfsAuth` | autenticação Meta SSO ("WFS"), resposta `login`, `wa_ac_machine_id`, `lid` |
| `/v2/consent`, `/v2/client_log`, `/v2/pre_pn_client_log`, `/v2/autoconf`, `/v2/autoconf_verifier`, `/v2/invite_preview`, `/v2/reg_onboard_abprop` | consentimento, logs de funil, verificação silenciosa, AB props | não específicos de segurança |

### 3.2 Etapas

| # | Etapa | Evidência |
|---|-------|-----------|
| 1 | `/v2/exist` retorna o estado da conta: quais métodos de OTP são elegíveis, tempos de espera, `second_factor_methods`, `is_device_trusted`, `passkey_auth_challenge`, `password_eligible`, estado de wipe | found (3.3) |
| 2 | Se `passkey_auth_challenge` estiver presente e não expirado, o login com passkey é oferecido (seção 7.1) | found |
| 3 | O usuário escolhe um método; `/v2/code` com `method` | found |
| 4 | O usuário digita o OTP; `/v2/register` com `code` e `method` | found |
| 5 | `status=ok` encerra o registro (`login`, `lid`, `ent_access_token`, `ent_canonical_fbid` são lidos do resultado). `status=fail` com um reason (3.5) | found |
| 6 | O reason `security_code` significa que a conta tem um segundo fator: `VerifyTwoFactorAuth` coleta PIN, senha ou OTP por e-mail e chama `/v2/register` novamente (3.6) | nome do reason found; navegação inferred |
| 7 | Após o sucesso: `RegisterName`, registro de dispositivo confiável (seção 8), upsell de passkey (seção 7.2) | found |

Uma "conta existente" não é uma API separada: o servidor responde `/v2/exist` e `/v2/register` para um número que já tem conta, com o mesmo vocabulário de status / reason. Campos como `possible_migration`, `need_chat_restore_pn_verify`, `acc_tr_eligible` (transferência de conta) e `wa_old_eligible` (verificar pelo telefone antigo) mostram que o servidor conduz os fluxos de conta existente pelas mesmas duas chamadas (campos found, significado inferred a partir dos nomes).

### 3.3 Campos de resposta de `/v2/exist` lidos pelo cliente

| Campo | Tipo | Uso |
|-------|------|-----|
| `status` (`ok`/`fail`), `reason` | string | resultado |
| `login`, `lid` | string | identificadores de conta devolvidos ao cliente (consumidor não rastreado) |
| `is_device_trusted` | bool | armazenado como `pref_is_device_trusted`; oculta o checkbox de dispositivo confiável |
| `second_factor_methods` | array de strings | armazenado como `pref_second_factor_methods`; os valores são strings de wire de `EnumC43759JAu` |
| `passkey_auth_challenge`, `passkey_credential` | string | challenge armazenado como `reg_passkey_auth_challenge` com timestamp; dica de id da credencial |
| `password_eligible` | int | elegibilidade ao upsell de senha |
| `sms_wait`, `voice_wait`, `wa_old_wait`, `email_otp_wait`, `send_sms_wait`, `silent_auth_wait`, `retry_after` | string | cooldowns por canal |
| `sms_length`, `voice_length`, `wa_old_length`, `email_otp_length` | int | tamanho esperado do código |
| `email_otp_eligible`, `wa_old_eligible`, `silent_auth_eligible`, `carrier_silent_auth_eligible`, `send_sms_eligible`, `acc_tr_eligible` | int | elegibilidade do método |
| `email`, `wa_old_device_name` | string | e-mail mascarado / rótulo do dispositivo antigo (mascaramento não verificado) |
| `reset_method`, `wipe_type`, `wipe_token`, `wipe_wait`, `wipe_expiry_time`, `server_time` | misto | fluxo de PIN esquecido (3.7) |
| `fallback_methods`, `recommended_method`, `num_visible_dbs_methods` | array / int | ordenação da UI |
| `ent_access_token`, `ent_canonical_fbid` (em `/v2/register`) | string | credenciais de canonical user da Meta |
| `violation_type`, `violated_policy`, `appeal_token`, `in_app_ban_appeal`, `version_upgrade`, `custom_block_screen` | misto | telas de banimento / atualização (ver relatório de ban) |

### 3.4 Métodos de OTP

A sheet de solicitação de código dirigida pelo servidor (`RequestServerDrivenOtpCodeBottomSheetFragment`, `C46760Kbq`) oferece estas strings de `method` (found): `sms`, `voice`, `flash`, `wa_old`, `email_otp`, `password`, `passkey`, `send_sms`. `silent_auth` e `account transfer` têm seus próprios campos de elegibilidade.

### 3.5 Motivos de falha de `/v2/register` (parser em `KotlinRegistrationBridge`)

| `reason` | Significado (found: nome; significado inferred) |
|----------|-------------------------------------------------|
| `incorrect` | código errado ou PIN errado |
| `security_code` | segundo fator necessário |
| `second_code`, `device_confirm_or_second_code` | segundo fator ou confirmação de dispositivo necessários |
| `too_many_guesses`, `guessed_too_fast` | limite de taxa de tentativas; `guess_wait` é retornado |
| `stale`, `mismatch`, `missing`, `format_wrong` | código expirado / não confere / ausente / malformado |
| `sms_required` | deve verificar por SMS |
| `blocked`, `not_allowed`, `limited_release` | banido, não permitido, gate de rollout |
| `temporarily_unavailable` | transitório |
| `challenge` | rodada de challenge necessária (`/v2/challenge`) |
| `reset_too_soon` | reset de PIN esquecido solicitado cedo demais |
| `consent`, `consent_parent_linking_already_registered` | telas de consentimento |

### 3.6 Métodos de segundo fator

`EnumC43759JAu` (found): `twofac_pin`, `password`, `email_otp`, `oauth_email`, `sms`, `voice`, `flash`, `wipe_full`, `wipe_offline`. Com a flag **28755**, a tela é dirigida por `second_factor_methods` ("2FA dinâmico", string de contexto `twofac_dynamic`), e "verificar de outra forma" abre `Dynamic2faMethodSelectionBottomSheet`.

`K49.A0o` (`verifySecurityCode`):

| Condição | Wire |
|----------|------|
| flag 26215 desligada | legado: `/v2/security` com `code` (e `reset`, `wipe_token` ao resetar) |
| flag 26215 ligada, método não é `password` | `/v2/register` com `security_code` = segredo em texto puro no map da requisição, `method` |
| flag 26215 ligada, método `password` | a senha é primeiro criptografada por `HOZ.A08` em `#PWD_WA:11:<epoch>:<blob>` (seção 5.3); o blob é enviado na posição de `code` de `/v2/register`; se a criptografia falhar, o QPL reporta `PASSWORD_ENCRYPT_FAILED` |

A chave do envelope vem de `WaPasswordEncryptionKeyQuery` via `CanonicalPasswordService.A04(..., true)` (chamado a partir de `C47204KjV`, found). Qual campo exatamente carrega o blob no wire foi lido da ordem dos argumentos do construtor, não de uma requisição capturada (inferred).

### 3.7 PIN esquecido, wipe e reset por e-mail

`/v2/exist` ou `/v2/register` podem retornar `reset_method`, `wipe_type` (`offline` ou `full`), `wipe_wait` (segundos), `wipe_token`, `wipe_expiry_time`, `server_time` (found). `VerifyTwoFactorAuth.A03` mapeia esses valores em quatro estados (found): 0 não permitido, 1 em cooldown ("0_7 days, offline_info"), 2 `offline` ("7_30"), 3 `full` ("over 30"). A chamada de reset envia `reset=<mode>` e `wipe_token`; `wipe_full` e `wipe_offline` são métodos de segundo fator (3.6). O que o servidor apaga em um wipe `offline` vs `full` é desconhecido.

---

## 4. Verificação em duas etapas (PIN) e e-mail de recuperação

### 4.1 Estado do cliente

`C1DP` (`TwoFactorAuthManager`) guarda o PIN localmente (found): pref `two_factor_auth_code`, opcionalmente criptografado (`two_factor_auth_using_encryption`, descriptografado por `C1DP.A01` por meio de um helper de keystore). É usado para um prompt periódico "verifique seu PIN": intervalos de lembrete 6 h, 12 h, 1 d, 1 d, 3 d, 7 d (`C1DP.A0I`, prefs `two_factor_auth_nag_time`, `two_factor_auth_nag_interval`). Outras prefs: `two_factor_auth_email_set`, `two_factor_auth_dynamic_validated`, `two_factor_auth_last_code_correctness`, `pref_2fa_{sms,voice,flash,email_otp}_wait_time`.

### 4.2 Stanzas IQ (`xmlns="urn:xmpp:whatsapp:account"`, timeout de 32 s)

| Ação | Stanza | Resposta lida | Classe |
|------|--------|---------------|--------|
| Obter status (smax 114) | `type=get` `<2fa/>` | `<2fa>`: filho `code` presente significa PIN definido; filho `email` presente define `two_factor_auth_email_set` | `C1DT.A00`, `C28896Cgx` |
| Definir PIN / e-mail | `type=set` `<2fa><code>PIN</code><email>addr</email></2fa>` (cada filho opcional) | o sucesso grava prefs; código de erro + texto para os listeners | `C1DP.A07`, `C28899Ch0` |
| Verificar PIN | `type=get` `<2fa><code>PIN</code></2fa>` | `<2fa>` contendo `code` significa correto | caminho de `VerifyTwoFactorAuthCodeDialogFragment`, `HandlerC25225AtN` |

O PIN tem 6 dígitos (`SetCodeFragment`, verificação de tamanho `== 6`). Definir é o tipo 1, confirmar é o tipo 2. `Fetch2FAEmailStatusJob` relê o status (32 s) para ver se o e-mail foi verificado. Se o servidor retorna mais do que os filhos `code` / `email` é desconhecido.

### 4.3 OTP do e-mail da conta (separado de `<2fa><email>`)

`C31107Dfz` monta, `KRB` interpreta (prefixo de log `EmailVerificationXmppMethods`):

| Etapa | Stanza | Resposta |
|-------|--------|----------|
| solicitar OTP | `type=set` `<verify_email><lg/><lc/></verify_email>` (idioma / locale, 2-3 caracteres) | `verify_email.wait_time` |
| verificar OTP | `type=get` `<verify_email><code>NNNNNN</code></verify_email>` (6 caracteres) | `verify_email.code_match` (`true`/`false`), `wait_time` |

O endereço de e-mail em si não está nessas stanzas (definido antes, caminho não rastreado). Usado por `VerifyEmailActivity` e pelo segundo fator `email_otp`.

### 4.4 PIN versus senha versus GetTwofa

`GetTwofaQuery` retorna `twofa_methods[]{method,value,state}`. `PasswordUpsellEligibility` procura as strings `password` e `pin` nessa lista (found). `SetTwofaMutation` só é chamada depois que uma senha foi criada, em best effort, com o id de dispositivo em hash (seção 5.2); `twofa_auto_enabled` / `twofa_auto_disabled` são as flags de resultado. O PIN em si nunca é enviado via w:mex.

---

## 5. Senha da conta

### 5.1 Entidades

| Entidade | Papel |
|----------|-------|
| `PasswordRepository` | orquestração: `setPassword`, `getTwofa`, id do dispositivo (`computeDeviceId`) |
| `PasswordServerApiImpl` | `HasPasswordQuery`, `DeletePasswordMutation`, `GetTwofaQuery`, `SetTwofaMutation` |
| `CanonicalPasswordService` | busca da chave, `A03` criar, `A02` alterar (mutations `Xfb*`, schema `whatsapp-android-www`) |
| `HOZ` | criptografia do envelope (`A08` → `#PWD_WA:11`) |
| `PasswordCredentialManager` | salva a credencial no Android Credential Manager (`saveCredential`, ignorado sem um número E.164) |
| UI | `CreatePasswordActivity`, `ReplacePinWithPasswordActivity`, `PasswordUpgradeFragment`, `SettingsPassword`, `TrustThisDeviceActivity` |

### 5.2 Definir / alterar / excluir

`PasswordRepository.setPassword` primeiro precisa de credenciais canonical; sem elas, falha com "No canonical credentials available to set password" (found). Ou seja, a senha fica atrelada ao canonical user da Meta, não apenas ao número do WhatsApp.

```
setPassword(pw, isChange, enableTwofa)
  isChange  -> CanonicalPasswordService.A02  XfbWaChangePasswordMutation
  !isChange -> CanonicalPasswordService.A03  XfbWaCreatePasswordMutation
               then, if enableTwofa: GetTwofa/SetTwofa best effort (device_id = base64(SHA-256(ANDROID_ID)))
each: A04 = key fetch (WaPasswordEncryptionKeyQuery) + HOZ.A08 -> data.encrypted_password
```

`device_id` é `K2M.A01(android_id)` = Base64 (flag 2, sem wrap) do SHA-256 de `Settings.Secure.ANDROID_ID` (found). Excluir não envia variáveis; o código tipo HTTP 409 mapeia para um resultado "bloqueado, precisa de e-mail" (found). Regras locais em `CreatePasswordActivity`: tamanho de 8 a 20, pelo menos uma letra e um dígito, a confirmação deve coincidir (found).

### 5.3 Envelope `#PWD_WA:11` (`HOZ.A02` / `A08`)

```
epoch   = current time in seconds
aesKey  = random 32 B (AES-256)         iv = random 12 B
ct||tag = AES-GCM(aesKey, iv, utf8(secret))    // no AAD on this path
wrapped = RSA/ECB/PKCS1Padding(serverPublicKey, aesKey)
blob    = 0x01 | key_id(1 B) | iv(12) | len(wrapped) as uint16 LE | wrapped | tag(16) | ct
out     = "#PWD_WA:11:" + epoch + ":" + base64(blob, URL_SAFE | NO_WRAP | NO_PADDING)
```

`key_id` deve ser de 1 a 255 (`CanonicalPasswordService.A01`). A chave RSA é interpretada a partir do PEM como X.509 SPKI; o caminho PKCS1 não verifica o tamanho do módulo (o teste de ≥ 4096 bits existe apenas em `HOZ.A06`, uma variante OAEP diferente). O mesmo envelope é usado em três lugares (found): segundo fator no registro (3.6), criação / alteração canonical (5.2) e recuperação (`exchangeNonce`, seção 9, embrulhado no JSON `{version:1,timestamp,password}`).

Outras variantes em `HOZ` (não `#PWD_WA:11`): `A03` e `A06` usam RSA-OAEP-SHA-256 com IV zero e AAD (o caminho Waffle SSO escreve `#PWD_WAFFLE` em `C40069Hd8` / `C40090HdT`).

---

## 6. OPAQUE, VOPRF e o código criptográfico nativo

### 6.1 O que está presente

| Item | Onde | Nível |
|------|------|-------|
| `WESOpaqueClientRegistrationStartResult` (.rodata `0xaebae`), `...LoginStartResult` (`0xaebd5`), `...RegistrationFinishResult` (`0xaeda9`), `...LoginFinishResult` (`0xaedd1`), `...RegistrationState` (`0x115042`), `...LoginState` (`0x115072`) | strings de `libwhatsapp.so` | found |
| `OPAQUE_PBKDF2_SALT` (`0x17e129`), `VOPRF06-HashToGroup-` (`0x19465a`), `VOPRF06-Finalize-` (`0x19466f`) | strings de `libwhatsapp.so` | found |
| `org/whispersystems/curve25519/NativeVOPRFExtension` | mesma lib; a classe Java tem `nativeBlind`, `nativeUnBlind`, `nativePcdBlind` | found |
| `libvoprf-ed25519.so`, `libvoprf-ristretto.so` | libs separadas, exports apenas `JNI_OnLoad`; wrappers Java `com.facebook.privacy.acs.VoprfEd25519` / `VoprfRistretto` | found |

### 6.2 Funções que referenciam as strings (arm64, vaddr)

| Função | Tamanho | Conteúdo | Nível |
|--------|---------|----------|-------|
| `fcn.0075a1c0` | 644 B | referencia `VOPRF06-HashToGroup-`; init / update ×6 / finish de SHA-512 do mbedTLS, depois uma segunda passada de SHA-512 | found |
| `fcn.0075b550` | 712 B | referencia `VOPRF06-Finalize-` e `OPAQUE_PBKDF2_SALT`; SHA-512 sobre o transcript de finalização, depois `mbedtls_pkcs5_pbkdf2_hmac` | found |
| `fcn.0075a618`, `fcn.0075ad40` | - | ambas chamam `fcn.0075b550`, depois `mbedtls_hkdf_extract` + três `mbedtls_hkdf_expand` (md type `0xb`) | found |
| `fcn.0075a0d4` | - | chama `fcn.0075a1c0` | found |

Chamada PBKDF2 em `fcn.0075b550` (disassembly): tamanho da senha `0x40` (64 B, a saída do OPRF), tamanho do salt `0x12` = 18 = tamanho do label `OPAQUE_PBKDF2_SALT` e o buffer é inicializado a partir desse label, tamanho derivado `0x40`, contagem de iterações passada pelo chamador (não é constante nesta função), md type `0xb`. O md type `0xb` equivale a SHA-512 na numeração do mbedTLS 3.6 (inferred a partir do valor do enum e dos tamanhos de 64 bytes). Assim, a saída do OPRF alimenta PBKDF2-HMAC-SHA-512 com o label ASCII como salt (found para o formato da chamada, inferred para o hash).

Os papéis das funções (blind, finalize, registration-finish, login-finish) são inferred a partir do formato das chamadas. O grupo / ciphersuite (curva, id anexado aos prefixos `VOPRF06-`), os layouts de bytes de KE1 / KE2 / KE3, o conteúdo do envelope e a variante de AKE são **unknown**; o código nativo foi lido como disassembly das funções citadas, não decompilado.

### 6.3 Quem chama: backup criptografado, não a senha da conta

A entrada Java da máquina de estados é o protocolo de backup criptografado (prefixo de log `encb/`):

| Classe | Papel (found) |
|--------|---------------|
| `EncBackupViewModel` | cria `C61447Rhg` (handler de login) com a string da senha de backup do usuário |
| `AbstractC62498S8e` | envia os IQs `sendInitRegIq`, `sendBeginRegIq`, `sendFinishRegIq`, `sendInitLoginIq`, `finishLoginOnSuccess`, `sendDeleteAccountIq` (`EncryptedBackupProtocolHelper`) |
| `C62510S8q` (smali `X/S8q`) | handler de resposta; `jvidispatchOOO(0xb, password, ...)` retorna o estado de login (`Rtz`), `jvidispatchOO(0x20, state)` a próxima mensagem |
| `C62511S8r` | resposta do begin-login: verifica `l2` com `l2_sig` e `ed_pub` (Ed25519), lê `count`, `backoff`, `max_attempts`, depois `jvidispatchOIOOO(1, 100000L, state, ...)` |
| `RunnableC29321Co8` | finish-login: `jvidispatchOIOO(1, 100000L, state, ...)`, lê os campos do modelo, descriptografa a chave de backup com AES-GCM, monta o proto `C25803BBm` (`backupKeyData_`, `r3_`, `opaqueChallenge_`, `transcript_`) |

`100000` é passado às chamadas nativas de finish tanto no registro quanto no login (found). É provavelmente a contagem de iterações do PBKDF2 (inferred: a função nativa o recebe como parâmetro). Que esses índices de `jvidispatch` caiam no código `WESOpaque*` é inferred a partir dos argumentos (string de senha na entrada, objetos de estado entre chamadas, campos `l2` / `r3`) e da ausência de qualquer outro consumidor; nenhum símbolo Java nomeia OPAQUE. O código da senha da conta (seção 5) nunca os toca.

### 6.4 O outro VOPRF: tokens ACS da Meta

`NativeVOPRFExtension` e `libvoprf-ed25519.so` têm os consumidores Java `C1N9` (`ACSTokenProviderImpl`, prefixo de log `ACSToken/`) e `KYL`: fator de blinding, token blindado assinado, prova DLEQ, unblind, segredo compartilhado (strings found `blinding_factor_string`, `shared_secret_string`, `ACSToken/processSignedBlindedToken`). As operações correspondentes nos assets são `WaAcsGetConfig` (`27388182297440754`) e `WaAcsIssueCredentials` (`26645395115100537`); nenhum dos nomes aparece no código, portanto o transporte da requisição de token não foi rastreado. É um token de credencial anônima e não um login por senha.

### 6.5 O que isso significa para "login por senha"

| Afirmação | Status na 2.26.41.6 |
|-----------|---------------------|
| O login com a senha da conta usa OPAQUE | não suportado pelo código: a senha é enviada como envelope RSA/AES (`#PWD_WA:11`), nenhuma mensagem OPAQUE é construída nos caminhos lidos; `SetPasswordMutation` e `CheckPasswordMutation` não têm call site |
| Existe um cliente OPAQUE nativo | found |
| Ele atende a senha do backup criptografado | found (chamador Java), vínculo com os símbolos nativos inferred |
| O servidor guarda um verifier em vez da senha para a senha da conta | unknown |

Strings Java que parecem evidência de OPAQUE mas não têm relação (found): `opaqueChallenge_` (proto de bootstrap do backup acima), `opaquePayload_` (`C61318RfY`, frame de migração tethered), `OpaqueConfig` / `prefersOpaqueConfig` (config bitmap em `EnumC167127Ba`), `OpaqueKey(` (`C44715Jfl`, um wrapper de string), `KE1` (`X.KE1` é uma classe do Android Compose), `opaque_client_data` (coluna do history-sync).

---

## 7. Passkeys (WebAuthn)

### 7.1 Login no momento do registro

| Etapa | Evidência |
|-------|-----------|
| `/v2/exist` retorna `passkey_auth_challenge`; `K15.A03` o aceita enquanto for mais novo que `SignalCredentialStateController.MAX_RETRY_TIME` | found |
| `PasskeyVerifier.onPasskeyChallengeReceived` executa uma asserção de discoverable credential por `androidx.credentials` (`PasskeyLowLevelAndroidApiImpl.loginWithPasskey`); o estágio fica na pref `passkey_login_stage` | found |
| `K49.A0l` posta o resultado como `credential` em `/v2/passkey_auth` | found |
| Resposta: `status` (`ok`/`fail`), `reason` (`temporarily_unavailable`, `disabled`), `credential_create` (string), `login`, `cred_token` | found |
| `cred_token` é armazenado por número de telefone em `passkey_disabled_cred_token_map` e reenviado como `cred_token` em requisições posteriores quando a flag **25565** está ligada | found; finalidade (provar que uma passkey foi desativada) inferred |

Os resultados do lado do cliente são registrados como `passkey_client_login_{cancelled,nopasskey,ineligible,error,success}`. `prepareGetCredential` é usado apenas no Android 14+ (SDK 34) e na flag **21638** (found).

### 7.2 Criar e gerenciar

Upsell após a etapa de 2FA: `VerifyTwoFactorAuth.onCheckPasskeyUpsellAfter2FA` usa `PasskeyCreateEducationScreen` ou uma bottom sheet; a flag **20409** alterna entre o fluxo de controle e o caminho de quick-promotion (QP), e a flag **16591** adiciona uma verificação de elegibilidade (found).

| Operação | Gate MEX | Fallback IQ (`xmlns="passkey"`) |
|----------|----------|---------------------------------|
| start register | flag **10453** | smax 125, `type=get` |
| finish register | flag **10452** | smax 126, `type=set` |
| clear | flag **10461** | smax 129, `type=set` |
| list / exists, delete, enable, update encryption status | sempre MEX | nenhum |

O `credential_create` do start-register é armazenado em cache em `passkey_create_challenge`. O finish register envia `credential` e `key_attestation`; o payload de attestation só é montado se a flag **28809** estiver ligada (base64 da key attestation, `getKeyAttestationPayload`). A flag **8877** embrulha start / finish em um helper de retry / timeout (`C29707Cw7`, papel inferred). `PasskeyRandomizedDailyCronJob` e `PasskeyExistsCache` atualizam a lista de exists; a resposta de exists armazena `uuid` em `reg_passkey_exists_uuid`.

### 7.3 PRF e criptografia no cliente

`PasskeyPrfSecrets` usa o input PRF estático `WhatsAppPasskeyStaticPrfInputV1` e armazena uma root key derivada de PRF em `prf_derived_root_key.key` (label da chave de encapsulamento `prf_derived_root_key_file_encapsulation_key`). `RegistrationPasskeyUpdateClientEncryptionStatusMutation` informa ao servidor que a passkey é usada para criptografia no cliente. O consumidor é o fluxo de backup criptografado (`VerifyPasskeyFragment`, inferred a partir da localização da classe).

---

## 8. Dispositivos confiáveis

| Item | Valor |
|------|-------|
| `device_id` | `Base64(SHA-256(ANDROID_ID))` (sem wrap), `K2M.A01` |
| `device_name` | `<MANUFACTURER>-<MODEL>` (`HO4.A00`) |
| Checkbox | exibido em `VerifyPhoneNumber` e `VerifyTwoFactorAuth` quando a flag **30530** está ligada e `pref_is_device_trusted` é false; prefs `pref_trusted_device_checkbox_shown` / `_checked` |
| Conclusão do registro (`RegisterName`) | com opt-in: `AddTrustedDeviceMutation`; sem opt-in: `UntrustTrustedDeviceMutation` com `reason="REREG"` (`C29652Cu9`, found) |
| Configurações | `TrustedDevicesRepository` lista (`GetTrustedDevicesQuery`) e remove (`DeleteTrustedDeviceMutation`); `TrustThisDeviceActivity` |
| Efeito | `is_device_trusted` é retornado por `/v2/exist`, `/v2/register`, `GetTwofa` e `SetTwofa`; o cliente o usa para pular o checkbox. Que um dispositivo confiável pule o prompt de PIN / senha é inferred; nenhum código do cliente pula o segundo fator |

As entradas de `list_of_trusted_device[]` carregam `device_id`, `device_name`, `latitude`, `longitude`, `last_ts` (a localização do último uso é fornecida pelo servidor; como é derivada é desconhecido).

---

## 9. Recuperação de conta (Meta canonical user)

`AccountRecoveryManager` não recupera chats do WhatsApp nem a conta do número de telefone. Ele recria as credenciais de canonical user da Meta de uma conta vinculada ao FB (found).

| Etapa | Detalhe |
|-------|---------|
| Gatilho | `maybeRecoverAccount`: sem canonical user, ou credenciais inválidas; variante diferida controlada pela flag **16017** |
| Chave do cliente | gera um par de chaves, envia a chave pública (PEM, base64) como `nonce_encryption_key` em `WWWTriggerAcountRecovery` com `use_case`, `registration_trace_id`, `request_id` |
| Nonce | chega por notificação; o timeout produz "Account Recovery Failed due to Nonce notification timeout" |
| Troca | `WWWExchangeNonceForAccessToken` com `nonce`, `use_case`, `request_id`, `registration_trace_id`, `encrypted_password` = envelope `#PWD_WA:11` de um segredo aleatório do cliente dentro do JSON `{version:1,timestamp,password}` |
| Companion | `WWWGetNonceForCompanionDevice`, `WWWTradeNonceForAccessTokens` fazem o mesmo para dispositivos vinculados (`CompanionCanonicalUserNonceManager`, `CompanionCanonicalUserAccessTokenJob`) |
| Relacionadas | `WWWValidateCanonicalUser`, `WWWCanonicalUserValid`, `WWWAppGenerateCanonicalNonce` (call sites existem; campos não lidos) |

A grafia `Acount` é do próprio WhatsApp. Qual é o algoritmo da chave de criptografia do nonce (o par vem de `N6T.A02`) não está resolvido.

---

## 10. Login e logout

`LogoutManager` implementa um soft logout (multi-conta) e o caminho de login-back (found).

| Ação | Wire | Notas |
|------|------|-------|
| Logout | `AccountLogoutMutation` `{phone_number, enabled_biometric}` | `enabled_biometric` vem de uma configuração de biometria; timeout de 5 s, depois o logout prossegue localmente ("timed out, proceeding with logout") |
| Push | `LogoutPushManager` desativa / reativa o push GCM (`"re-enable"` ao reverter) | found |
| Local | `markCurrentAccountLoggedOut`, `removeLoggedOutAccountWithCleanup`, `deleteGmsBackupState`, UI opcional de exclusão de chats (`DeleteChatsOnLogoutDialog`, `LoggedOutChatsFragmentDialog`) | found |
| Login back | `AccountLoginMutation` `{phone_number}`, depois `loginBack` → `actionReconnect`; espera até 7 s pela conexão | `PrimaryLoginBackActivity` |

É uma flag de estado no lado do servidor de uma configuração multi-conta, não o login por número de telefone da seção 3 e não a remoção de um dispositivo vinculado. A flag **28385** é lida em `LogoutManager` (papel não resolvido).

---

## 11. Feature flags

Os IDs estão em negrito. Tipos: B = AB prop booleana, C = config. Os nomes não estão no cliente; o papel é o que o código faz com a flag.

| ID | Onde | Controla |
|----|------|----------|
| **24762** (C) / **24763** (B) | `K49.A0b` | stack de registro Kotlin em vez do `wamsys` nativo |
| **26215** | `K49` verify / reset security code | segundo fator do registro via `/v2/register`, habilita o envelope de senha; desligada = `/v2/security` legado |
| **25565** | `K49.A0M` | enviar o `cred_token` armazenado |
| **28755** | `VerifyTwoFactorAuth` | seleção dinâmica do método de 2FA a partir de `second_factor_methods` |
| **30530** | `VerifyPhoneNumber`, `VerifyTwoFactorAuth` | checkbox de dispositivo confiável |
| **20409** | `VerifyTwoFactorAuth` | upsell de passkey via QP pós-2FA vs controle |
| **16591** | `VerifyTwoFactorAuth` | verificação de elegibilidade de passkey antes do upsell |
| **21638** | `PasskeyAndroidApi` | `prepareGetCredential` (Android 14+) |
| **10452** / **10453** / **10461** | `PasskeyServerApiImpl` | MEX em vez de IQ para finish / start / clear |
| **28809** | `PasskeyServerApiImpl` | payload de key attestation |
| **8877**, **31281** | `PasskeyCreateFlow` | wrapper de retry; caminho alternativo de passkey de pagamentos (papéis inferred) |
| **5156** | `SetCodeFragment` | oferecer "adicionar e-mail" após definir o PIN |
| **5711** | `TwoFactorAuthActivity`, `SetCodeFragment` | apenas layout (oculta o indicador de página) |
| **16017** | `AccountRecoveryManager` | processamento diferido do nonce |
| **28385** | `LogoutManager` | não resolvido |

---

## 12. Casos de erro

| Sintoma | Causa | Correção / nota |
|---------|-------|-----------------|
| `/v2/register` reason `security_code` ou `second_code` | a conta tem um segundo fator | enviar PIN / senha / OTP por e-mail via `/v2/register` (3.6) |
| `PASSWORD_ENCRYPT_FAILED` (QPL) | falha na busca da chave, `key_id` fora de 1-255, ou exceção de crypto (logs `encryptRegistrationPassword/*`) | tentar novamente; o cliente aborta a tentativa |
| `reset_too_soon` | reset de PIN esquecido antes de `wipe_wait` decorrer | aguardar; estado 1 da UI |
| `too_many_guesses` / `guessed_too_fast` | limite de tentativas de PIN ou OTP | aguardar `guess_wait` |
| `No canonical credentials available to set password` | sem Meta canonical user no dispositivo | concluir antes a configuração do canonical user |
| Falha ao criar / alterar a senha | payload `xfb_wa_*` sem sucesso; código de erro mapeado por `CanonicalPasswordService.A00` | enum de erro da UI `EnumC49982M3j` |
| `DeletePassword` 409 | e-mail da conta necessário antes da remoção | adicionar o e-mail primeiro |
| `Account Recovery Failed due to Nonce notification timeout` | notificação não recebida | repetir o gatilho |
| `...passwordPublicKeyStr is null` / `passwordKeyIdStr is null` | certificado de criptografia ausente na troca de recuperação | tentar novamente |
| `LogoutManager/callLogoutApi/timed out` | sem resposta em 5 s | o logout continua localmente |
| Passkey: `NoCredentialException`, `NotAllowedError`, GMS antigo demais, Play services ausente | falhas do Credential Manager | recorre a outros métodos |

---

## 13. Distinções-chave

| A | B |
|---|---|
| Código nativo OPAQUE (senha do backup criptografado, IQs HSM `encb/*`) | senha da conta (`XfbWa*` + `#PWD_WA:11`) |
| `libvoprf-*.so` + `NativeVOPRFExtension` (tokens anônimos ACS) | máquina de estados OPAQUE (`WESOpaque*`) |
| PIN (IQ `<2fa>`, 6 dígitos) | senha (w:mex, 8-20 caracteres) |
| `<2fa><email>` (e-mail de recuperação para reset de PIN) | fluxo de OTP `<verify_email>` e segundo fator `email_otp` |
| `SetTwofaMutation` (flag por id de dispositivo após a senha) | IQ de definição de PIN |
| Dispositivo confiável (login, `AddTrustedDeviceMutation`) | `WhatsappTrustedDeviceRegistration` (trust binding de pagamentos) |
| `AccountLogoutMutation` (soft logout) | desvincular um companion (`remove-companion-device`) e logout por ban |
| `WWWTriggerAcountRecovery` (credenciais de canonical user) | wipe de PIN esquecido (`wipe_*`, `/v2/security`) |
| `#PWD_WA:11` (WhatsApp) | `#PWD_WAFFLE` (Waffle SSO) |
| Ops de `PasskeyServerApiImpl` (passkeys da conta) | `PaymentsPasskey*`, `BrPasskey*` |
| `/v2/passkey_auth` (asserção de login) | `PasskeyRequestChallengeMutation` / `PasskeyVerifyChallengeMutation` (sem call site) |

---

## 14. Baileys (`baron-baileys-v2`)

Comparado com `src/Socket/privacy.js` e `src/Socket/registration.js`.

| Item | APK 2.26.41.6 | Baileys | Resultado |
|------|---------------|---------|-----------|
| doc_ids de dispositivos confiáveis, login, logout, senhas, passkeys | assets | mesmos números | confere |
| `accountLogin` / `accountLogout` | `input{phone_number}` / `input{phone_number, enabled_biometric}` | igual | confere |
| `getTrustedDevices` | `input{device_id}` sempre enviado | `{}` | difere; comportamento do servidor sem `device_id` desconhecido |
| reason padrão de `untrustTrustedDevice` | `"REREG"` na única chamada | `'USER_INITIATED'` | difere, outros reasons desconhecidos |
| ops de passkey | variáveis `credential`, `key_attestation`, `credential_ids`; roots `xwa2_passkey_*` | nenhuma implementada nos arquivos lidos | usar os formatos do APK |
| `SetPassword` / `CheckPassword` | sem call site | apenas doc_ids | não verificado, não confiar |
| criptografia `#PWD_WA:11` | seção 5.3 | ausente na árvore `src` lida | implementar a partir da seção 5.3 |

Por que um cliente standalone falha nesses caminhos (inferred, nada testado): os endpoints de registro esperam os campos de requisição protegidos por e2e que o app monta (`C45446JsB`); as chamadas de senha e recuperação precisam de credenciais de canonical user; a asserção de passkey precisa de um autenticador de plataforma.

---

## 15. Fluxos completos

### 15.1 Verificar um número que já tem conta

```
[User]            [Client]                                   [Server]
  │ enter number    │                                           │
  ▼                 ▼                                           │
            POST /v2/exist ───────────────────────────────────►│
                    │◄── methods, waits, second_factor_methods, │
                    │    passkey_auth_challenge, is_device_trusted
  passkey? ─yes──►  Credential Manager assertion                │
                    POST /v2/passkey_auth {credential} ────────►│
                    │◄── status, login, cred_token              │
  no                ▼                                           │
            POST /v2/code {method} ─────────────────────────────►│  OTP sent (sms/voice/flash/wa_old/email_otp)
  type OTP ──►  POST /v2/register {code, method} ───────────────►│
                    │◄── ok | fail(reason)                      │
   reason=security_code / second_code                           │
  PIN / password ─► POST /v2/register {security_code | #PWD_WA blob, method}
                    │◄── ok (login, lid, ent_access_token)      │
                    ▼                                           │
        optional: AddTrustedDeviceMutation | UntrustTrustedDeviceMutation(REREG)
        optional: passkey upsell -> StartRegister -> Credential Manager -> FinishRegister
  forgot PIN ─────► reset=<mode>, wipe_token (after wipe_wait) ─►│
```

### 15.2 Definir um PIN e e-mail de recuperação

```
[Client]  IQ get <2fa/> ───────────────► [Server]  <2fa>[<code/>][<email/>]
[Client]  IQ set <2fa><code>NNNNNN</code><email>x</email></2fa> ──► ok | error(code,text)
[Client]  Fetch2FAEmailStatusJob: IQ get <2fa/> until <email> present
[Client]  IQ get <2fa><code>NNNNNN</code></2fa> ──► <2fa><code/></2fa> = correct   (periodic reminder)
```

### 15.3 Criar uma senha da conta

```
[Client]  canonical credentials present? ── no ─► fail
[Client]  WaPasswordEncryptionKeyQuery ──► public_key (PEM), key_id (1..255)
[Client]  HOZ.A08: AES-GCM + RSA-PKCS1 wrap -> "#PWD_WA:11:<epoch>:<blob>"
[Client]  XfbWaCreatePasswordMutation {data:{encrypted_password}} ──► success
[Client]  (best effort) GetTwofaQuery / SetTwofaMutation {input:{twofa_enabled:true, device_id}}
```

---

## 16. Unknowns

| Tópico | Motivo |
|--------|--------|
| Ciphersuite do OPAQUE (grupo, id após `VOPRF06-`), layouts de KE1 / KE2 / KE3 e do envelope, variante de AKE | nativo, lido apenas como disassembly de 4 funções |
| Vínculo dos índices `jvidispatch` do backup criptografado com o código `WESOpaque*` | por formato dos argumentos, não por símbolo |
| Contagem de iterações do PBKDF2 para o KSF do OPAQUE | passada como parâmetro; `100000` é o literal passado pelos chamadores Java |
| Se algum caminho envia uma senha via OPAQUE para a senha da conta | nenhum caminho assim encontrado; wrappers escondidos atrás de dispatch numérico não podem ser excluídos |
| Respostas de `XfbWa*`, `AccountLogin`, `AccountLogout`, `UntrustTrustedDevice` | root e campos não lidos |
| Operações sem call site (2.4) | variáveis e respostas desconhecidas |
| Campo exato que carrega o blob `#PWD_WA` em `/v2/register` | derivado da ordem do construtor |
| Significado dos campos `login`, `lid` retornados por `/v2/exist` e `/v2/passkey_auth` | consumidores não rastreados |
| Efeito de `wipe_full` / `wipe_offline` no servidor | o cliente mostra apenas texto |
| Se um dispositivo confiável pula o segundo fator | lado do servidor; sem lógica de skip no cliente |
| Algoritmo do par de chaves de recuperação (`N6T.A02`) | não lido |
| Papéis das flags 8877, 31281, 28385 | apenas gates |
| Tráfego real | apenas análise estática |
