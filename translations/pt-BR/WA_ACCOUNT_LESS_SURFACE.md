<!-- src-sha1: 166366154a0dd7893ab70aa91166a96d5a2e788f -->
# WhatsApp Superfície sem Conta — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** o que o cliente Android expõe sem conta registrada ou antes de o registro ser concluído — componentes exportados no manifest (activities, aliases, services, receivers, providers), telas de pré-registro e roteamento por estado de registro, deep links e links web, endpoints HTTP e Graph não autenticados, tabela de hosts compilada no app, formulário de suporte deslogado, status de banimento e pontos de entrada de recurso, identificadores enviados antes do login, superfícies IPC de terceiros, o que permanece unknown

---

## 1. O que "sem conta" significa nesta build

Não existe um único "modo deslogado". Vários caminhos independentes rodam enquanto o cliente não possui JID de usuário, sessão de chat autenticada ou tem um registro inacabado. Cada caminho substitui a conta por uma credencial diferente. Todas as afirmações são análise estática do APK decompilado (`versionCode 264100600`, target SDK 36, min SDK 23). Nada foi observado na rede. Tiers: **found** = lido no código ou no manifest, **inferred** = deduzido do código, **unknown** = não resolvível estaticamente. Documentação defensiva: superfícies e controles são descritos, não exercitados.

Nomes ofuscados mudam a cada build e foram re-resolvidos a partir de strings estáveis na 2.26.41.6.

| Caminho | Credencial que substitui a conta | Transporte | Classes principais (2.26.41.6) |
|---------|----------------------------------|------------|--------------------------------|
| Registro por telefone | nenhuma até `/v2/register`; a requisição carrega o pacote de chaves estáticas Noise e ids do dispositivo | HTTPS `/v2/*` | `K49`, `KotlinRegistrationBridge`, `AbstractC45307Jps` |
| Log de funil pré-número | apenas phone id (`fdid`) | HTTPS `/v2/pre_pn_client_log` | `PrePnBaseFunnelLogger`, `K49` |
| AB props pré-chat | prefs `ab_key` / `ab_hash` | HTTPS `/v2/reg_onboard_abprop` | `K49.checkPreChatdABProps` |
| Status de banimento / recurso | token opaco armazenado no momento do banimento + app client token compilado | HTTPS Graph `graph.<domain>/graphql` | `AbstractC40195HfH`, `C37409GLo`, `C37604GYf`, `C37414GLt` |
| Formulário de suporte deslogado | nenhuma; email + texto livre + `anid` | HTTPS multipart POST | `LoggedOutContactFormActivity`, `C47328KmN` |
| Upload de crash / logs | app token compilado | HTTPS `crashlogs.whatsapp.net` | `C10V`, `C05640An` |
| Assets estáticos | nenhuma | HTTPS GET | `static.whatsapp.net/*` |
| Graph com credencial anônima (ACS / OHAI) | token ACS ou configuração de chave OHAI, sem JID | HTTPS `acs.whatsapp.com/graphql` | `C31991Nz`, `R5t`, `N5I` |
| Registro de companion | nenhuma; conexão Noise com JID nulo permitida apenas aqui | Noise | `HandlerThreadC12340b0` |
| Fallback de DNS embutido | nenhuma | tabela compilada | `AbstractC47101wK`, `C36881dC` |

Não coberto aqui, veja os relatórios vinculados: etapas de registro, métodos de OTP e motivos de falha ([WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) seção 3); tokens de atestação enviados no registro ([WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md)); máquina de estados de banimento e criptografia do recurso ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) seções 2, 10); login Noise e registro de companion ([WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)); telemetria WAM ([WA_WAM_ANALYTICS.md](WA_WAM_ANALYTICS.md)).

---

## 2. Manifest: componentes exportados

### 2.1 Contagens (found, `AndroidManifest.xml`, analisado sob `<application>`)

| Tipo | Declarados | Exportados (`true` explícito; nenhum depende do padrão implícito) |
|------|-----------:|-----------------------------------------------------------------:|
| `activity` | 828 | 22 |
| `activity-alias` | 33 | 29 (14 são aliases de launcher `AppIcon01..14` desabilitados) |
| `service` | 61 | 16 |
| `receiver` | 68 | 19 |
| `provider` | 19 | 11 |
| Total | 1009 | 97 |

Das 97 entradas exportadas: 20 estão `enabled="false"` (14 aliases de ícone, service de car-app, receiver ADM, activity e provider de migração iOS, dois receivers de intent UPI da Índia); 24 carregam `permission` / `readPermission`; 6 são protegidas por uma permissão `signature` definida pelo WhatsApp; 56 estão habilitadas sem permissão no manifest. Qualquer verificação além do manifest está no código (seção 9).

Permissões customizadas (found): `REGISTRATION`, `IDENTITY_VERIFICATION`, `MIGRATION_CONTENT_PROVIDER`, `BROADCAST`, `MAPS_RECEIVE`, `RECEIVE_ADM_MESSAGE`, `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` são `protectionLevel="signature"`. `com.whatsapp.sticker.READ` não tem `protectionLevel` (padrão normal).

### 2.2 Pontos de entrada que rodam sem conta

| Componente | Exportado | Filtro | Por que é alcançável no pré-registro |
|------------|-----------|--------|--------------------------------------|
| `com.whatsapp.Main` | sim | `MAIN` / `LAUNCHER`, `MULTIWINDOW_LAUNCHER` | launcher único; roteia por estado de registro (seção 3) |
| `com.whatsapp.home.ui.HomeActivity` + aliases `AcceptInviteLinkActivityDeepLink`, `EventDeepLink`, `HomeActivity` | sim | `chat.whatsapp.com`, `call.whatsapp.com`, `event.whatsapp.com`, `whatsapp://chat`, `call`, `event`, NFC `application/com.whatsapp.chat`, `.join` | nenhuma verificação de registro encontrada na própria `HomeActivity` (inferred: uma classe base redireciona, não resolvido) |
| `DeepLinkActivity` via 4 aliases | alias sim, alvo não | veja seção 4 | ponto de entrada de links |
| `com.whatsapp.deeplink.ui.TpalOAuthRedirectActivity` | sim | `www.whatsapp.com/oauth_account_linking/login_redirect`, `/oauth_account_linking_mobile/login_redirect`, `whatsapp://third_party_oauth` | receptor de redirect OAuth, `noHistory` |
| `com.whatsapp.cuif.ConsentActivity` | sim | `whatsapp://consent` | lê os extras `flow_name`, `source`, `extra_params`, `device_id`, `app_id`; comportamento no pré-registro não resolvido |
| `com.whatsapp.Conversation` | sim | `sms:` / `smsto:` `VIEW` / `SENDTO` | ponto de entrada do handler de SMS do sistema |
| `com.whatsapp.accountsync.ProfileActivity`, `CallContactLandingActivity` | sim | `content://com.android.contacts` MIME `vnd.com.whatsapp.profile`, `.voip.call`, `.video.call` | integração com o app de contatos; `CallContactLandingActivity` exige `CALL_PHONE` |
| `com.whatsapp.registration.ui.RegistrationCompletedReceiver` | sim, `REGISTRATION` signature | `com.whatsapp.SMBRegistrationCompleted` | sinal do app irmão |
| `com.whatsapp.registration.directmigration.MigrationProviderOrderedBroadcastReceiver`, `MigrationRequesterBroadcastReceiver` | sim, `REGISTRATION` signature | ações `initialMigrationInfoAction`, `recoveryTokenAction`, `setMigrationStateOnProviderSide`, `providerIsLoggedOutAction`, `providerAppMigrationSpaceNeededAction` | migração entre apps irmãos consumer / SMB no momento do registro |
| `MigrationContentProvider`, `DirectMigrationContentProvider` | sim, `readPermission` `MIGRATION_CONTENT_PROVIDER` (signature) | authorities `com.whatsapp.provider.MigrationContentProvider`, `.DirectMigrationContentProvider` | mesma migração |
| `com.whatsapp.registration.app.verifyphone.SMSRetrieverAppInactiveReceiver` | sim, permissão GMS `SEND` | `SMS_RETRIEVED` | resultado do SMS Retriever quando o app está inativo |
| `com.whatsapp.registration.core.accounttransfer.AccountTransferReceiver` | sim, sem permissão | `com.google.android.gms.auth.START_ACCOUNT_EXPORT` | o código exige keyguard seguro e uma verificação de feature antes de agir (found) |
| `com.whatsapp.phoneid.PhoneIdRequestReceiver` | sim, sem permissão | `com.facebook.GET_PHONE_ID` | retorna o phone id a um chamador confiável (seção 9.1) |
| `com.whatsapp.otpmessage.otp.OtpRequestedReceiver`, `OtpIdentityHashRequestedReceiver` | sim, sem permissão | `com.whatsapp.otp.OTP_REQUESTED`, `ID_HASH_REQUESTED` | handshake de autofill de OTP para outros apps (seção 9.3) |

### 2.3 Outras entradas exportadas (não relacionadas a registro, listadas por completude)

| Grupo | Componentes | Proteção |
|-------|-------------|----------|
| Conteúdo de terceiros | `Conversation` (handler de `sms:`), `ExternalShareAlias` (`SEND`, `SEND_MULTIPLE`, `*/*`), `ContactPicker` (`PICK`, `CREATE_SHORTCUT`), `SetAsProfilePhoto` (`ATTACH_DATA`) | nenhuma no manifest |
| Stickers | `SendStickerCommandActivity`, `AddThirdPartyStickerPackActivity` (+ alias), `StickerCommandProvider`, `WhitelistPackQueryContentProvider` | nenhuma no manifest |
| IPC da família Meta | `FamilyAppsCredentialsProvider`, `FamilyAppsUserValuesProvider`, `WaAccountsCenterService` (`com.whatsapp.wfl.OPERATION`), `QuickSendsContactsProvider`, `OrbitSsoProvider`, `OrbitMessagesProvider`, `OrbitCompanionLinkActivity`, `InstrumentationService`, `InstrumentationAuthActivity`, `WhatsAppBugReportingBridgeActivity` | verificações do chamador no código (seção 9) |
| Companions de dispositivo | `WearOsListenerService`, `GarminBindingServiceShim`, `IQGarminBindingService`, `TetheredService`, `WhatsAppCarAppService` (desabilitado) | nenhuma no manifest |
| Integração Google | `BackupNowService`, `BackupStateService`, `OsMigrationAppDataService` (`BACKUP`), `DeferredRestoreBroadcastReceiver` (`BACKUP`), `WakeUpService` (permissão de notificação de exposição) | parcial |

Também exportados: hooks de configurações (`SettingsNotifications`, `SettingsDataUsageActivity`, configure de widget `AppAuthenticationActivity`), landing de chamadas (`SystemDialerCallLandingActivity`, `VoiceMessagingActivity`), receivers de bibliotecas (`WidgetProvider`, `BootReceiver`, `AppUpdatedReceiver`, `ExternalMediaStateReceiver`, `WAFbnsPreloadReceiver`, `FirebaseInstanceIdReceiver`, entradas de work-manager e profile-install atrás de `BIND_JOB_SERVICE` / `DUMP`), entradas Pixel (`com.google.permission.besties.API`) e as entradas desabilitadas de UPI da Índia e migração iOS. `IdentityVerificationActivity` (NFC `application/com.whatsapp.identity.ui`) exige a permissão signature `IDENTITY_VERIFICATION`.

### 2.4 Componentes de pré-registro não exportados (found)

As 806 activities não exportadas incluem toda tela de registro (seção 3.2), `LoggedOutContactFormActivity`, `LoggedOutContactSuccessActivity`, `BanAppealActivity`, `WfacBanActivity`, `PrimaryLoginBackActivity`, `RemoveLoggedOutAccountsActivity`. Três receivers de alarme não exportados conduzem lembretes de registro: `RegRetryVerificationReceiver` (`com.whatsapp.alarm.REGISTRATION_RETRY`, `SMS_RECEIVED_WHILE_INACTIVE`), `OnboardingIncompleteReceiver` (`ONBOARDING_INCOMPLETE`), `EnterPhoneNumberNotificationReceiver` (`ENTER_PHONE_NUMBER`). Providers não exportados: `FileProvider`, `SecureFileProvider`, `MediaProvider`, `AccountSwitchingContentProvider`, `RestartAppContentProvider`, `InstrumentationProvider` (todos com `grantUriPermissions` quando declarado).

### 2.5 Flags da aplicação e política de rede (found)

| Item | Valor |
|------|-------|
| `debuggable` | `false` |
| `allowBackup` | `true`, mas `fullBackupContent` e `dataExtractionRules` (backup na nuvem e transferência de dispositivo) excluem todos os domínios; a entrada de transferência multiplataforma para iOS carrega apenas `bundleId` / `teamId` |
| `networkSecurityConfig` base | `cleartextTrafficPermitted="true"`; trust anchors `system` e `user` (`overridePins="true"` para CAs de usuário) |
| Cleartext negado | `whatsapp.com`, `whatsapp.net`, `wa.me`, `wl.co` (22 pins SHA-256, sem expiração), `facebook.com`, `instagram.com`, `jiomart.com`, `hatch-api.meta.ai` |
| Escopo dos pins | o conjunto de pins fica no domain-config de `whatsapp.com` / `whatsapp.net` / `wa.me` / `wl.co`; herda os trust anchors da base, então os pins não se aplicam a CAs instaladas pelo usuário (comportamento da plataforma para `overridePins`) |
| Hosts fora de qualquer domain-config | `gstatic.com` (chave reCAPTCHA) cai sob a config base (cleartext permitido; o código usa `https://`) |

---

## 3. Telas de pré-registro e roteamento por estado

### 3.1 Roteamento de `Main` por estado de registro (found, smali de `Main.A5W`)

`Main` lê o estado de registro (`C0Gk.A02()`) e o objeto da própria conta armazenado. As tags de log são âncoras estáveis.

| Estado | Tag de log | Destino |
|-------:|------------|---------|
| 2 | `main/me/regname`, `main/no-me/regname` | etapa de registro de entrada de nome (`RegisterName`) |
| 21 | `main/me/wfac ban` | tela de banimento WFAC via `HBC.A00` (`WfacBanActivity`) |
| 24, 38 | `main/me/backup otp` | etapa de OTP de backup / verificação |
| 41 | `main/me/consent age ban` | tela de consentimento de idade |
| 45 | `main/me/paa onboarding`, `main/no-me/paa onboarding` | onboarding de conta dependente / gerenciada |
| 50 | `main/me/logged out, going to PrimaryLoginBackActivity` | tela de login-back |
| 51 | `main/me/pending login-back verification` | verificação de login-back (extra `login_back_verification`) |
| 56 | `main/me/username`, `main/no-me/username` | etapa de username |
| qualquer | `main/no-me/first-factor password` | ramo de senha de primeiro fator (sem objeto de conta própria) |
| qualquer | `main/invalid/registration state=` | log de estado inválido |

O mesmo método constrói intents (found) para `VerifyPhoneNumber`, `DeviceConfirmationRegistrationActivity`, `ExportMigrationDataExportedActivity`, `BanAppealActivity` (extra `launch_source`), `DeleteAccountConfirmation` e a entrada padrão `RegisterPhone`. Uma preferência `logged_out_phone_fallback_pending` retoma em `RegisterPhone` (`main/me/logged-out phone fallback resume`). Um token IDV mintado (`minted_idv_token`, `minted_idvtoken_expiry_time_secs`) é verificado, e um token expirado ou vazio reinicia o fluxo de remediação. Qual estado numérico corresponde a qual etapa no servidor é inferred a partir dos nomes das tags.

### 3.2 Telas de registro (found, todas não exportadas)

| Grupo | Activities (`com.whatsapp.registration.app.*` salvo indicação) |
|-------|-----------------------------------------------------------------|
| Entrada | `EULA` (tag `eula_screen` / `eula_with_language_selector`), `phonenumberentry.RegisterPhone`, `RegisterAsDependentActivity`, `RegTabletIntroActivity`, `RegTabletChooseOptionActivity` |
| Permissões | `RegPermissionsExplainerActivity`, `RegNotificationPermissionPrimerActivity` |
| Verificação | `verifyphone.VerifyPhoneNumber`, `sendsmstowa.SendSmsToWa`, `ManualSmsRequest`, `flashcall.PrimaryFlashCallEducationScreen`, `email.RegisterEmail`, `email.VerifyEmail`, `email.EmailEducationScreen`, `email.UnverifiedEmailSetupRegUpsellActivity`, `email.ConfirmEmailSetupRegUpsellActivity`, `backuptoken.BackupTokenEducationScreen`, `VerifyTwoFactorAuth` |
| Defesa da conta | `accountdefence.DeviceConfirmationRegistrationActivity`, `accountdefence.ui.OldDeviceSecureAccountActivity`, `OldDeviceSecureAccount2FaActivity`, `OldDeviceMoveAccountNoticeActivity` |
| Bloqueios | `parole.CustomRegistrationBlockActivity`, `downgrade.DowngradeFrictionActivity`, `com.whatsapp.userban.ui.BanAppealActivity` |
| Migração | `directmigration.RestoreFromConsumerDatabaseActivity`, `MigrationStartTransferActivity`, `RequestPermissionFromSisterAppActivity`, `com.whatsapp.migration.transfer.ui.*` |
| Nome / troca de número | `RegisterName`, `phonenumberentry.ChangeNumber*` |
| Modo companion | `com.whatsapp.companionmode.registration.ui.RegisterAsCompanionActivity`, `RegisterAsCompanionEnterNumberActivity`, `RegisterAsCompanionLinkCodeActivity`, `CompanionBootstrapActivity`, `CompanionPostLogoutActivity` |
| Deslogado | `logout.ui.PrimaryLoginBackActivity`, `RemoveLoggedOutAccountsActivity`, `loginfailure.LogoutMessageActivity` |
| Suporte | `inappsupport.ui.app.LoggedOutContactFormActivity`, `LoggedOutContactSuccessActivity` |

### 3.3 Seletores de idioma e país (found)

| Item | Detalhe |
|------|---------|
| Idioma | `LanguageSelectorBottomSheet` aberto a partir de `EULA` (evento de funil `language_selected`; métricas `language_selector_clicked_count`, `language_selector_time_spent` em `K49`); o `FullScreenLanguageSelectorActivity` do lado das configurações não é exportado |
| Nomes de países | 63 tabelas offline `assets/country_names_<lang>.tsv` (`ISO code<TAB>name`); nenhuma consulta de rede para o seletor encontrada |
| Preenchimento do número | `RegisterPhone` usa as dicas de número de telefone do Google (`RegisterPhone/launchGooglePNHints`) e um caminho "qual é o meu número" via SIM que exige permissão de telefone; extras de EULA `RegisterPhone.phone_number`, `country_code`, `auto_submit_after_prefill`, `one_click_from_eula` |
| Links legais em `EULA` | `https://www.whatsapp.com/legal/terms-of-service` ou `/terms`, `privacy-policy` ou `privacy-policies` (variante por config) |

---

## 4. Deep links e links web

### 4.1 Aliases de entrada (found)

| Alias | Alvo | Filtros |
|-------|------|---------|
| `TextAndDirectChatDeepLink` | `DeepLinkActivity` | `http(s)://api.whatsapp.com`, `wa.me`; `https://[www.]whatsapp.com` caminhos `/channel`, `/channel_status`, `/updates`, `/aimediainput`, `/aivoice`, `/dl`, `/privacy/disclosure`, `/wamo/status/link-{instagram,facebook}-in-house-ad`; schemes `whatsapp`, `whatsapp-smb`, `whatsapp-consumer`, `whatsapp-sheet` (listas de hosts, mais de 100 hosts) |
| `VerifyOtpDeepLink` | `DeepLinkActivity` | `http(s)://b.whatsapp.com`, `http(s)://v.whatsapp.com` |
| `FoaDeeplinkActivityAliasUniversalLink`, `FoaDeeplinkActivityAliasAppScheme` | `DeepLinkActivity` | sem filtro neste manifest (declarado para a biblioteca de deep links da família Meta) |
| `AcceptInviteLinkActivityDeepLink` | `HomeActivity` | `chat.whatsapp.com` |

`DeepLinkActivity` em si não é exportada; todo caminho externo passa por um alias. Todos os filtros com `autoVerify="true"` cobrem apenas hosts https. Vários filtros em `whatsapp`, `whatsapp-consumer`, `whatsapp-smb` carregam tanto `VIEW` quanto a ação customizada `com.whatsapp.DEEP_LINK_REDIRECT`, então o alias responde a um intent explícito com essa ação vindo de qualquer app (found: formato do filtro).

### 4.2 Links que tratam estado de pré-registro (found)

| Link | Âncora do parser | Comportamento |
|------|------------------|---------------|
| `https://[www.]whatsapp.com/dl?wsu=<6 digits>` | `IJB.A01`: caminho `dl`, query `wsu` casando com `\d{6}`, log `DeepLinkHelper/parseUri/web signup uri`, código **193** | transferência de cadastro web; valor validado apenas por regex no cliente |
| `whatsapp://s/signup` (único segmento de caminho `signup`) | `IJB.A01` código **216**, protegido pelos ab-props **25005** ou **25801**; handler `handleInAppSignupDeepLink` exige scheme `whatsapp` e query `s` | cadastro in-app; registra via `ApiSignupFlowLogger` com `signup_id` (pareamento do host `s` inferred a partir do manifest) |
| `https://v.whatsapp.com/<code>`, `https://b.whatsapp.com/<code>` (último segmento do caminho) e `whatsapp://r?c=<code>` | ramo de registro de `DeepLinkActivity`, log `DeepLinkActivity/Registration deeplink/registration state:` | link de OTP por email. O estado 1 abre `RegisterPhone` com extra `tapped_sms_link`; o estado 2 abre `VerifyEmail` com `email_otp`, `entrypoint`, `session_id`, `challenge_flow=false` e reporta `email_otp_deeplink_redirect_to_register_name`; outros estados redirecionam para as configurações (`settings_verification_email_address_verified`, inferred). O código é repassado como extra; a verificação é no servidor (unknown) |
| `whatsapp://code-linking?auth=<nonce>` | código **77**, handler `maybeStartCodeLinkingFlow`, ab-prop **4560** (`ENABLE_CODE_LINKING_DEEP_LINK_CODE`), pref `adl_deep_link_nonce` com janela de 300000 (unidade inferred como ms) | fluxo de código de dispositivo vinculado; ignorado quando a flag está desligada ou o nonce é mais antigo que a janela |
| `whatsapp://help/<segment>` | código **62**; o ramo offline registra `DeepLinkActivity/help/no-connectivity` | artigo de ajuda |
| `whatsapp://support` | código **30** (extraído do parser; o handler registra `about/no-connectivity`) | tela de suporte / sobre, exige conectividade |

### 4.3 O gate de pré-registro

| Âncora | Achado | Tier |
|--------|--------|------|
| `DeepLinkActivity/deeplink not allowed before registration/` e motivo `not_allowed_before_registration` | presente; o enum de motivo mapeia o valor 0 para essa string; o produtor do motivo 0 para links comuns não foi isolado | found (strings), unknown (produtor) |
| Handlers por código | cada handler verifica o estado de registro por conta própria (chamadas `C0Gk.A0C()` / `A02()` nos corpos do switch) | found |
| Allowlist de códigos deslogados | não re-resolvida: `C02T` é um serial executor nesta build e `C02U` é uma classe compartilhada de constantes inteiras, então nomes de classe anteriores não se mapeiam | unknown |
| Resultado `JXK` (`code`, `source`, motivo) construído por `IJB`, `IJC`, `IJD`, `IJE` | saída do parser consumida por `DeepLinkActivity.A0w` | found |

Resolver conteúdo (um chat, um canal, um diretório) ainda exige uma conta: os handlers de convite de grupo e `wa.me/<phone>` usam a sessão autenticada (inferred a partir dos nomes dos handlers; não rastreado de ponta a ponta aqui).

---

## 5. Hosts e endpoints contatados sem conta

### 5.1 HTTP de registro (found)

16 caminhos, chave XOR 18 em `AbstractC45307Jps`, todos redecodificados na 2.26.41.6: `/v2/exist`, `/v2/code`, `/v2/register`, `/v2/security`, `/v2/challenge`, `/v2/passkey_auth`, `/v2/consent`, `/v2/client_log`, `/v2/pre_pn_client_log`, `/v2/autoconf`, `/v2/autoconf_verifier`, `/v2/invite_preview`, `/v2/reg_onboard_abprop`, `/v2/device_logout_send`, `/v2/device_logout_fetch`, `/v2/wfs`. Duas constantes adicionais decodificam para `ENC` e `H` (uso unknown). As listas de campos do primeiro grupo estão em [WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) seção 3.1. O host base `v.whatsapp.net` é o nome na tabela compilada (5.4); o código que junta host e caminho está nas stacks wamsys / Kotlin e não foi lido aqui (inferred).

O seletor `K49.A0b` escolhe a stack Kotlin (`KotlinRegistrationBridge`) ou a stack nativa `wamsys`; a stack nativa precisa fazer bootstrap primeiro (`ensureWamsysForRegBootstrapped`, erro `FAIL_TO_INITIALIZE_WAMSYS`).

### 5.2 Outros endpoints HTTPS (literal found, autenticação conforme indicado)

| Host / URL | Método | Autenticação no código | Chamador | Sem conta? |
|------------|--------|------------------------|----------|------------|
| `https://www.whatsapp.com/contact/noclient/verification/` | multipart POST | nenhuma | `C47328KmN` case 0 (formulário de suporte) | sim |
| `https://graph.<pref_graphql_domain>/graphql` (padrão `graph.whatsapp.com`) | POST JSON | app client token compilado no body `access_token` | `AbstractC40195HfH` e subclasses | sim (status de banimento / recurso) |
| `https://crashlogs.whatsapp.net/wa_clb_data`, `/wa_fls_upload_check`, `/wa_profilo_data`, `/whatson_logs_upload` | POST | app token compilado (o upload de log adiciona `access_token`, `type`, `from_jid`, `ticket_id`, `build_id`) | `C10V`, `C05640An`, `ExceptionsUploadService`, `ProfiloUploadService`, `CM8` | roda sem login; conteúdo de `from_jid` quando deslogado unknown |
| `https://acs.whatsapp.com/graphql` | POST | token ACS ou config OHAI (sem JID) | `C31991Nz`, `R5t` | sim (requisições de-identificadas) |
| `https://static.whatsapp.net/wa/static/{downloadable,network_resource,payments/*}`, `/sticker?...`, `/payments/background` | GET | nenhuma | loaders de assets da UI | sim |
| `https://mmg.whatsapp.net/proxygen/health`, base `https://mmg.whatsapp.net` (config 22436) | GET | nenhuma | mídia / health | sim |
| `https://www.gstatic.com/recaptcha/verify_key/orcas/prod/android/verify_key.txt` | GET | nenhuma | `C44464JbH` (usado por `RequestCodeRepository`, `VerifyCodeRepository`, `VerifyPhoneNumber`) | sim (captcha de registro) |
| `https://www.whatsapp.com/compliance/xfac/mint` | POST form | nenhuma vista | `CommonRemediationApi` (remediação de idade, `minted_idv_token`) | alcançável no pré-registro: unknown |
| `https://www.whatsapp.com/v1/auth/canonical/token/` | POST form `nonce`, `user_id`, `device_id`, `client_pub_key` | nenhuma | `CanonicalUserCompanionDeviceManager` | caminho de companion / conta vinculada, não pré-registro puro |
| `https://api.whatsapp.net/support/add_bug_attachment` | multipart POST | `Authorization: Bearer <token>` | `PostBugAttachmentUploader` (relato de bug in-app) | não (vinculado a token) |
| `https://graph.whatsapp.net/v2.2/maps_configs?...&access_token=` (padrão `graph.facebook.com`) | GET | app token na URL | config de mapa `N6n` | gatilho não é pré-registro (inferred) |
| `https://api.whatsapp.net/calendar/integrations/` | requisição | sessão | feature de calendário | não |

Tokens compilados: existem duas formas no estilo Facebook, `WA|<app_id>|<secret>` no padrão do cliente Graph e `<app_id>|<secret>` no uploader de logs. Os valores não são reproduzidos aqui. Eles identificam o app, não um usuário.

### 5.3 Bootstrap de DNS e conectividade (found)

| Item | Detalhe |
|------|---------|
| Tabela compilada `AbstractC47101wK` | host para lista IPv4 / IPv6 de 18 nomes: `e1..e16`, `g`, `v` sob `.whatsapp.net` (cada um com um gêmeo com ponto final); não precisa de rede |
| `C36881dC` (DnsCache) | ordem de uso: resolver primário, resolver DNS MNS (`DnsCache/resolveViaMnsDns`, a string `v.whatsapp.net` é testada nesse ramo), resolver secundário, tabela hardcoded; consultas hardcoded falham com `no hardcoded ips found for <host>` quando a tabela não tem entrada e são puladas com `hardcoded dns resolver disabled` quando o bit de opção está desligado |
| Host de chat | a entrada `g.whatsapp.net` é lida diretamente (`C36881dC.A01`) |

O formato wire do resolver MNS vive em código nativo: unknown.

### 5.4 Caminhos REST que não existem (found negativo)

Nenhum fetch REST não autenticado para gating ou config (`/gk`, `/props`, `/config`) foi encontrado. A config de experimento pré-login chega, sim, via HTTP de registro: `/v2/reg_onboard_abprop` (`K49.checkPreChatdABProps`) envia `ab_hash` da pref `pref_pre_chatd_ab_hash`, `ab_exposure`/`ab_key` de `pref_pre_chatd_ab_key`, mais os campos de dispositivo da seção 7.

---

## 6. Formulário de suporte deslogado (found)

`LoggedOutContactFormActivity` (não exportada) é o único fluxo de suporte totalmente sem conta nesta build.

| Intent extra (prefixo `com.whatsapp.inappsupport.ui.app.LoggedOutContactFormActivity.`) | Uso |
|------|-----|
| `PhoneNumber`, `CountryCode` | número pré-preenchido; string vazia quando ausente |
| `From` | rótulo do ponto de entrada |
| `ServerStatus` | string de status passada pelo chamador (inferred: status do servidor de registro) |
| `IsRegistrationVerification` | booleano; em caso de sucesso uma chamada de acompanhamento é feita (alvo não resolvido) |
| `SupportUserContext` (`K8W`) | ponto de entrada e ids de CMS (`Entry point`, `Cms ids`) |

Campos do formulário: email (chips de sugestão `@gmail.com`, `@hotmail.com`, `@icloud.com`, `@outlook.com`, `@yahoo.com`), descrição, até 3 screenshots escolhidos do `MediaStore`.

Envio (`C47328KmN` case 0, tag `logged_out_contact_form`, argumento final 20 de significado não resolvido):

| Parte | Nome | Conteúdo |
|-------|------|----------|
| campo | `email` | email digitado |
| campo | `message` | descrição |
| campo | `platform` | literal `ANDROID` |
| campo | `phone_number` | número digitado |
| campo | `debug_info` | texto construído por `C10V.A08` (seção 7.3) |
| arquivo | `log_data` | `logs.tar.gz` do log do cliente (rotacionado e comprimido antes) |
| arquivos | `attachment_<n>` | screenshots recodificados para JPEG qualidade 80, limite de 2048 px, mantidos apenas quando de 10 MiB ou menos |
| extra | `skip_saga_copy=true`, `saga_copy=true`, `pn` | `pn` = código do país + número quando ambos não estão vazios |

Resultado: o status HTTP vai para um callback de resultado (`C46422KQg`); uma falha aparece como `Server error: <status>` ou `Network error`; o sucesso abre `LoggedOutContactSuccessActivity` (extra `...Email`). O mapeamento exato de status para sucesso não foi lido. A chamada é um POST HTTPS simples pelo cliente HTTP do app; não é uma chamada GraphQL. Um UUID `anid` aleatório (7.1) é gerado a cada envio.

---

## 7. Identificadores enviados antes do login

### 7.1 Tabela de identificadores

| Identificador | Onde | Fonte | Notas | Tier |
|---------------|------|-------|-------|------|
| `fdid` | `/v2/pre_pn_client_log`, requisições de registro | `C38141gV.Ax2()`: `UUID.randomUUID()` aleatório armazenado como `phoneid_id` + `phoneid_timestamp` nas prefs | persiste entre tentativas de registro; o mesmo id é retornado por `PhoneIdRequestReceiver` | found |
| `fid` | requisições de registro | `C47381wu.Ax2()`: prefs `phoneyid_id` + `phoneyid_timestamp`, enviado como `<id>|<timestamp>` apenas quando presente | id secundário de família; produtor do valor não rastreado | found (uso inferred) |
| `anid` | formulário de suporte | `C11J.A01()`: `UUID.randomUUID()` por chamada, também registrado como evento WAM | id aleatório por envio | found |
| `advertising_id` / `android_advertising_id` | `/v2/exist`, `/v2/code`, `/v2/register`; log de funil | advertising id do Google quando disponível | excluído da string de debug log do funnel logger | found |
| `authkey`, `e_ident`, `e_keytype`, `e_regid`, `e_skey_id`, `e_skey_val`, `e_skey_sig`, `e_pq_last_resort_{id,val,sig}` | requisições de registro | `C45446JsB`: chave estática Noise do cliente e pacote de chaves Signal | material público | found |
| `gpia` | requisições de registro | token padrão do Play Integrity, protegido por flag | veja [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) | found |
| `ab_key`, `ab_hash`, `ab_exposure` | `/v2/exist`, `/v2/pre_pn_client_log`, `/v2/reg_onboard_abprop` | prefs `pref_pre_chatd_ab_key` / `pref_pre_chatd_ab_hash` | bucket de experimento | found |
| `device_country` | log de funil | `TelephonyManager.getSimCountryIso()` em maiúsculas, `ZZ` quando ausente | | found |
| `access_token` (app) | Graph, upload de logs | constante compilada | identidade do app, não do usuário | found |
| `request_token` / `token` | status de banimento / recurso | pref `wfac_ban_status_token` (status) e o token de recurso armazenado | opaco, emitido pelo servidor no momento do banimento ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md)) | found |
| `from_jid` | upload de logs | JID da conta quando presente | conteúdo quando deslogado unknown | found (campo), unknown (valor) |
| `registration_trace_id`, `request_id`, `nonce_encryption_key` | mutation de recuperação de conta | `AccountRecoveryManager` (seção 8.2) | | found |

### 7.2 Atributos de dispositivo nas requisições de registro (found, helpers de `K49` `A0O`, `A0Q`, `A0R`, `A0U`, `A0W`, `A0X`)

`network_radio_type`, `simnum` (`0` / `1`), `hasinrc` (arquivo `rc2` presente), `pid` (id do processo), `device_ram`, `sim_type`, `airplane_mode_type`, `cellular_strength` (nível de sinal, `5` por padrão), `roaming_type`, `preloads_app_manager_id`, `preloads_attribution`, `entrypoint` (`create_paa` ou `suma`), `tos_version` (`5`), `old_phone_number` (fluxo de troca de número). Chaves de métricas de telemetria na mesma classe (found, uso na requisição não confirmado): `network_operator_name`, `sim_operator_name`, `sim_state`, `read_phone_permission_granted`, `mistyped`, `c2dm_reg_id` (lido das prefs).

### 7.3 Conteúdo do log de funil (found, `PrePnBaseFunnelLogger$sendPrePNFunnelLog$1`)

Antes de existir um número, o cliente envia: `current_screen`, `previous_screen` (pref `pref_previous_screen`, padrão `unknown`), `action_taken`, `event_name`, `access_funnel_type=wa`, `app_campaign_download_source`, `is_add_account_flow`, `android_advertising_id`, `ab_key`, `device_country`, `fdid`, os atributos de dispositivo acima e `entrypoint`. Em fluxos de adicionar conta ou fallback deslogado, também envia `primary_logout_session_id` e `number_of_accounts`. O envio é pulado quando o bootstrap do wamsys falha.

### 7.4 `debug_info` do formulário de suporte (found, `C10V.A08`, o argumento JID é `null` nesta chamada)

Rótulos escritos no texto: `useragent`, `Socket Conn`, `Connection`, `Server`, `Datacenter`, `Sim`, `Free Space Built-In` / `Removable`, `Network metered` / `restricted`, `Data roaming`, `Tel roaming`, `Diagnostic Codes`, `ABprops hash state`, `Screen reader`, `Fingerprint eligible`, campos de status de backup, `Is Companion`, `Number of Accounts`, `Mobile Build Id`, `wfl_state`, `isMetaVerified`, `Mistyped` / `Mistyped Last6` / `L Distance` (comparação do número digitado com o número do SIM), além de identificadores da última chamada quando existe histórico de chamadas. O rótulo `entity id` só é escrito quando um JID é passado, o que não ocorre aqui.

---

## 8. Chamadas Graph e MEX sem sessão de usuário

### 8.1 Requisições Graph com app token (found)

A classe base `AbstractC40195HfH.CND` constrói `https://graph.<A0f()>/graphql` (`A0f()` = pref `pref_graphql_domain`, padrão `whatsapp.com`; as subclasses `GEV`, `GEX`, `GET`, `GEW`, `GEU` e a família de troca de conta Meta `C45F` mudam para `facebook.com` / `instagram.com`). Body JSON: variáveis da operação, `access_token` (token compilado quando a subclasse não passa nenhum), `doc_id`, `lang`, `Content-Type`. O header `X-FB-Request-Analytics-Tags` é adicionado quando ausente.

| Classe | doc_id | Variáveis | Finalidade |
|--------|-------:|-----------|------------|
| `C37604GYf` | **4276154569100535** | `app_id` (`dev.app.id`), `request_token` | poll de status de banimento WFAC (`WfacBanRepository/fetchBanStatus`, token da pref `wfac_ban_status_token`) |
| `C37409GLo` | **27883644401256929** ou **4276154569100535** (booleano) | idem | status de banimento via `HG2.A01` |
| `C37414GLt` | **38509456535312323** ou **5473316762755318** (booleano) | `app_id`, `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}`; plaintext `{token, debug_info, description}`, contexto `WA_INAPP_BAN_APPEALS` | envio de recurso de banimento (`C40191HfD`); detalhes em [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) seção 10 |
| `C37408GLn` | **5803265299734043** | `app_id`, `client_pub_key` | finalidade unknown (envia uma chave pública do cliente); chamador não rastreado |
| `C37601GYc`, `GYd`, `GYe` | `GYd` **25453433540999208**, `GYe` **25974020015520396** (`GYc` não carrega id na própria classe) | `caller_name` `fx_waffle_contextual_pause_account_match`, `wa_waffle_certs`, `fx_waffle_foa_unpause` | helpers de vinculação de contas Meta |
| `C37605GYg`, `GYh`, `GYi` | **26573478745654327**, **26742313962085910**, **27503298369362501**, **28331348373116386**, **25840634418966704** | header `IG-Set-Waffle-Graphql-Access-Token`, chave `ACCESS_TOKEN` | vinculação de contas Facebook / Instagram; é exigido um token de conta vinculada (inferred a partir dos nomes de header e chave) |
| `C37413GLs` | **7236799486398397** | `batches`, `device_model`, `device_os`, `device_os_version`, `event_time`, `is_employee`, `primary_locale` | lotes de eventos do cliente (inferred a partir dos nomes das variáveis) |

O doc_id 6960707423955525 (um id legado de mutation de recurso reportado para builds antigas) não ocorre na 2.26.41.6. Os nomes de operação das requisições de recurso e status não são carregados por essas classes (unknown).

Diferença em relação a [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) seção 10: para `C37414GLt`, `C37409GLo` e `C37604GYf` o host é `graph.<pref_graphql_domain>` (padrão `graph.whatsapp.com`); apenas as subclasses listadas acima o sobrescrevem para `facebook.com`.

### 8.2 Operações MEX com ponto de chamada em tempo de registro ou deslogado (found, schema `whatsapp-android-mex`)

doc_ids de `assets/whatsapp-android-mex_client_persist_ids.json` (e dos arquivos `www` / `wamo` quando indicado).

| Operação | doc_id | Ponto de chamada |
|----------|-------:|------------------|
| `GetAutoConfConfidenceChallenge` | 25578301865133112 | `C40175Het`, `C40196HfI` (ping de confiança do autoconf) |
| `ValidateVerifierConfidence` | 25879669248324812 | `C40196HfI`, `C40197HfJ` |
| `FetchReachoutTimelockQuery` | 25627902213558773 | `RunnableC23952AUh` |
| `RemoveAccountReachoutTimelock` | 25040013452293167 | não rastreado |
| `UserCountryCodeGet` | 25292528387076991 | `MexUserCountryCodeRepository` |
| `MobileConfigFetchQuery` | 29248978061376279 | não rastreado |
| `SubmitAge`, `GetAgeExperience`, `SetAgeExperienceMutation` | 26049558371296621, 26567868986241476, 26051006311231325 | fluxos de idade |
| `TosSetResult` | 25225843213776555 | aceite dos termos |
| `GetWaOldResponse` | 25784374561179853 | verificar via telefone antigo |
| `WWWTriggerAcountRecovery` | 24896267680055094 | `AccountRecoveryManager` (variáveis `nonce_encryption_key`, `use_case`, `registration_trace_id`, `request_id`) |
| `WWWCreateUser`, `WWWDeleteUser`, `WWWGetCertificates` | 8548056818544135, 7989555047767245, 25094190163544446 | vinculação de contas |
| `OhaiKeyConfigQuery` | 25069818679280758 | `N5I` (bootstrap ACS / OHAI) |
| `CreateEnforcementAppeal` | 26933630359642347 | cliente de enforcement de newsletter |
| `NewsletterCreateReportAppeal` (mex), `CreateGroupSuspensionAppealMutation` (www), `WamoReportPromoAppealV2Mutation` (wamo) | 27792557363683798, 25646047815072526, 26867425009592691 | operações de recurso (vinculadas à conta; presentes nos assets) |

MEX é enviado como um IQ `xmlns="w:mex"` com `<query query_id=...>` (`C19370nI`) pela conexão de chat (`WAChatdGraphQLClient`). Se essas operações rodam em uma sessão sem conta não está estabelecido: veja 8.3.

### 8.3 Conexão de chat sem JID (found)

`ConnectionThread.connect` (`HandlerThreadC12340b0`) lê o próprio JID; quando é nulo, prossegue apenas se a flag de registro de companion (`C06830Gm.A02()`) for true; caso contrário lê uma segunda fonte de JID (`Ash()`), e se esta também for nula registra `ConnectionThread/connect/ignored/jid null and not in companion reg` e retorna. O registro do telefone primário, portanto, não usa uma conexão de chat com JID nulo (consistente com [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) seção 6.4). O significado da segunda fonte é inferred (um JID armazenado ou de registro pendente, não resolvido). Qual sessão carrega as chamadas MEX em tempo de registro de 8.2 é unknown.

### 8.4 Requisições de-identificadas (found)

`PandoGraphQLRequest.requireAcsToken()` e `requireOhaiConfig()` são lidos por `C6GN`; uma requisição marcada `@deidentified` sem token ACS ou config OHAI lança exceção (`Request was marked with @deidentified, but no ... was provided`). Campos de `AcsOhaiConfig`: nome do projeto, doc id, `graphQlUrl=https://acs.whatsapp.com/graphql`, surface, `tokenTtlSeconds`, `acsTokenMaxRedeemCount`. Quais operações carregam a flag está codificado nos assets `*_pando_flatbuffer_data.bin`: unknown.

---

## 9. Superfícies IPC exportadas com verificações no código

Todas as entradas são exportadas sem permissão no manifest, salvo indicação. Esta seção lista os controles encontrados no código, não um veredito sobre sua robustez.

### 9.1 `PhoneIdRequestReceiver` (`com.facebook.GET_PHONE_ID`)

Um broadcast ordenado. O receiver lê um extra `PendingIntent` `auth` dos extras do resultado e obtém `getCreatorPackage()`. Um pacote é confiável quando o hash do seu certificado de assinatura está em um conjunto de permissão hardcoded (`AbstractC28130CKz.A04`, SHA-1 de certificados de assinatura, valores não reproduzidos; um segundo conjunto SHA-256 é usado em `CHA.A02`). Um chamador confiável recebe o phone id e seu timestamp como resultado do broadcast (`setResult(-1, id, {timestamp})`); um caminho alternativo retorna o id secundário quando a flag **3651** permite. O fluxo de controle decompilado em torno da variável de confiança é parcial, então a precedência exata é inferred.

### 9.2 Providers da família de apps (found)

| Componente | Controles encontrados |
|------------|-----------------------|
| `FamilyAppsCredentialsProvider` | `getCallingPackage()`; mapa de handlers por seleção; UID do chamador resolvido para um certificado e verificado contra o conjunto confiável do handler (`C45775Jyk.A01`); elegibilidade do link-manager (`WfalManager.A00`); feature flags; o estado do link deve estar no conjunto elegível do handler; retorna um cursor de 3 colunas (prova de autenticação, bundle, TTL) das prefs `pref_foa_nta_ipc_bundle_auth_proof`, `pref_foa_nta_ipc_bundle`, `foa_nta_ipc_bundle_ttl`; erros para cache expirado ou ausente. Expansão de "NTA" unknown |
| `FamilyAppsUserValuesProvider` | uma seleção `foa_wo_wa_link_eligibility_values`, `getCallingPackage()` lido |
| `WaAccountsCenterService` | ação `com.whatsapp.wfl.OPERATION`; o corpo da classe é um stub na decompilação (verificações unknown) |
| `QuickSendsContactsProvider` | etapas de validação de `getCallingPackage()` registradas (`validation_start` / `validation_end`); serve arquivos de foto criptografados `.enc` e colunas de contato (`obfuscated_chat_id`, `display_name`, `profile_photo_uri`, `photo_key`) |
| `OrbitSsoProvider` (`com.whatsapp.orbit.v2.sso`) | gate por feature flag; o pacote chamador deve estar em uma allow-list (`AbstractC62035Rsx.A00`, caso contrário `SecurityException ... is not allowlisted`); uma verificação de pré-condição (`BS3()`) antes de qualquer método; métodos `get_profile` (retorna `display_name`, `phone_number`, `avatar_uri`, `avatar_mime_type`), `get_accounts`, `get_nonce`, `get_token`; caminho de arquivo `avatar` somente leitura. A allow-list é casada por nome de pacote em `A01()`; verificação de certificado, se houver, não está nesse método (unknown). O que `BS3()` testa é inferred como estado de login |
| `OrbitMessagesProvider` (`com.whatsapp.orbitmessages`) | arquivos abrem apenas com modo `r`, último segmento `media`, valores `media_handle` com prefixo `v1.` decifrados com AES-GCM; verificações do chamador não localizadas (unknown) |
| `OrbitCompanionLinkActivity` | lê `getCallingPackage()` e o extra `qr_data`; timers de hold / consentimento; retorna apenas o resultado (`return_result_only`) via `CompanionHelloConfirmationActivity` |
| `InstrumentationService`, `InstrumentationAuthActivity`, `WhatsAppBugReportingBridgeActivity` | não analisados |

### 9.3 Handshake de OTP (`OtpRequestedReceiver`)

Espera um extra `PendingIntent` `_ci_` (identidade do chamador) e um UUID `request_id` opcional (verificado por regex). Registra o pacote criador contra um valor gerado, registra um evento WAM e, quando a flag **6617** está ligada ou o pacote está na lista da config **7050**, responde com um broadcast `com.whatsapp.otp.OTP_HANDSHAKE_CONFIRMATION` a esse pacote carregando o `request_id`. Um `PendingIntent` ausente é rejeitado (`PendingIntent missing from handshake Intent`). Nenhuma verificação de registro foi encontrada neste receiver.

### 9.4 `AccountTransferReceiver`

Age apenas em `com.google.android.gms.auth.START_ACCOUNT_EXPORT`, apenas quando o dispositivo tem keyguard seguro e uma verificação de capacidade passa (`AbstractC21360rJ.A01`). A exportação em si roda em um executor em background (`C05X.A02(...).CVx`); conteúdo unknown.

---

## 10. Visualização de banimento e pontos de entrada de recurso

| Entrada | Mecanismo | Evidência |
|---------|-----------|-----------|
| Cold start em estado WFAC | `Main` estado 21 inicia `WfacBanActivity` via `HBC.A00` | found (3.1) |
| `BanAppealActivity` | não exportada; iniciada por `Main` (extra `launch_source`) e pelo fluxo de banimento permanente | found |
| Poll de status de banimento | Graph, `wfac_ban_status_token`, throttle de 5 s pref `wfac_last_ban_status_fetch_timestamp_ms` | found ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) 2.2) |
| Envio de recurso | Graph com `user_request` criptografado (8.1) | found |
| Resposta de registro | `/v2/register` campos `violation_type`, `violated_policy`, `appeal_token`, `in_app_ban_appeal`, `custom_block_screen`, `version_upgrade` | found ([WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) 3.3) |
| Contatar suporte | `LoggedOutContactFormActivity` (seção 6), flag `IsRegistrationVerification` para erros de registro | found |
| Deep links | `whatsapp://support`, `whatsapp://help`, `v.whatsapp.com` / `b.whatsapp.com` | found (4.2) |

A identidade por usuário do caminho de recurso é o token opaco emitido pelo servidor, não um número de telefone nem um id de dispositivo (os nomes de campo do token acima; derivação unknown).

---

## 11. Casos de erro e armadilhas

| Sintoma | Causa | Notas |
|---------|-------|-------|
| `ConnectionThread/connect/ignored/jid null and not in companion reg` | sem JID e não é registro de companion | normal antes do registro; o registro usa HTTPS |
| `FAIL_TO_INITIALIZE_WAMSYS` | bootstrap da stack nativa falhou (`ensureWamsysForRegBootstrapped`) | o HTTP de registro e o log de funil pré-número são pulados |
| `DeepLinkActivity/deeplink not allowed before registration/` | código de link bloqueado pelo gate | allowlist não resolvida (4.3) |
| `Request was marked with @deidentified, but no ...` | config ACS / OHAI ausente | requisição não enviada |

---

## 12. Distinções-chave

| Não confundir | Fato |
|---------------|------|
| Exportado vs alcançável sem conta | 97 entradas exportadas; a maioria não faz nada útil até existir uma conta registrada; apenas as entradas em 2.2 e 4.2 têm tratamento de estado de registro |
| App token vs user token | o `WA|<app_id>|<secret>` compilado identifica o app; chamadas de banimento adicionam um request token opaco, não uma sessão de usuário |
| `fdid` vs advertising id | `fdid` é um UUID gerado pelo app que sobrevive ao re-registro; advertising id é o valor do Google |
| Formulário de suporte deslogado vs suporte in-app | o formulário faz POST para `www.whatsapp.com/contact/noclient/verification/` com campos digitados; o suporte in-app usa a sessão (não analisado) |
| HTTP de registro vs conexão de chat | o registro é HTTPS `/v2/*`; uma conexão de chat com JID nulo é apenas para registro de companion |

---

## 13. Fluxo completo

```
[App launch / link tap]
    │  Main (only launcher)  or  DeepLinkActivity alias (wa.me, whatsapp.com/dl, v|b.whatsapp.com, whatsapp://...)
    ▼
[Main.A5W]  registration state ──► 2 regname │ 21 WFAC ban │ 41 age consent │ 45 PAA │ 50/51 login-back │ 56 username
    │  default
    ▼
[EULA]  language bottom sheet, ToS / privacy links
    │        └── /v2/pre_pn_client_log  (fdid, screens, device attrs, advertising id)   [ab_key via /v2/reg_onboard_abprop]
    ▼
[RegisterPhone]  hints / SIM number / country names (offline)
    │  /v2/exist  (fdid, fid, authkey, e_* key bundle, device attrs, gpia?)
    ▼
[VerifyPhoneNumber]  reCAPTCHA key GET (gstatic) ── /v2/code ── /v2/register
    │                        │
    │                        ├── ok  ──► RegisterName ──► account exists (leaves this report)
    │                        └── fail: violation_type / appeal_token / custom_block_screen
    │                                      │
    │                                      ▼
    │                         [WfacBanActivity / BanAppealActivity]
    │                                 Graph POST graph.whatsapp.com/graphql
    │                                 doc 4276154569100535 | 27883644401256929  (status, request_token)
    │                                 doc 38509456535312323 | 5473316762755318  (appeal, encrypted)
    ▼
[Help needed]
    LoggedOutContactFormActivity ──► POST www.whatsapp.com/contact/noclient/verification/
                                      email, message, platform=ANDROID, phone_number, debug_info, logs.tar.gz, <=3 JPEG
    ▼
[Background, any state]
    crashlogs.whatsapp.net uploads  │  static.whatsapp.net assets  │  acs.whatsapp.com (ACS/OHAI)
    DNS: system ► MNS ► secondary ► compiled table (e1..e16, g, v)
```

---

## 14. Unknowns

| Pergunta | Por que é unknown |
|----------|-------------------|
| Quais códigos de link são permitidos antes do registro | classe da allowlist não re-resolvida; os handlers verificam o estado individualmente, apenas quatro rastreados |
| Produtor do motivo 0 (`not_allowed_before_registration`) | não isolado no grande switch de `DeepLinkActivity` |
| Junção de host e caminho para `/v2/*`, constantes `ENC`, `H` | builders de requisição wamsys / Kotlin não lidos |
| Qual sessão carrega as operações MEX em tempo de registro | a conexão com JID nulo é recusada fora do registro de companion; a fonte `Ash()` não está resolvida |
| Conteúdo de `from_jid` em uploads de logs enquanto deslogado | `AbstractC05620Al.A0G` é abstrato |
| Validação no servidor de tokens, códigos, payloads de recurso | lado do servidor |
| Operações que carregam `@deidentified` | em `*_pando_flatbuffer_data.bin`, sem schema |
| Significado de "NTA", do produtor do id secundário `phoneyid_id`, de `c2dm_reg_id` como campo de requisição | apenas nomes |
| Se `HomeActivity` pode ser lançada sem registro e o que ela faz | gate da classe base não resolvido |
