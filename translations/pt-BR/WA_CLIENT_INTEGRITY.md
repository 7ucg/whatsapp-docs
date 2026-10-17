<!-- src-sha1: 4ca6293d8bc9da2aebc5db6f104c88b12dce1bd0 -->
# WhatsApp Client Integrity — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-17
**Escopo:** Integridade e atestação do cliente Android — Keystore key attestation ("blacknoise"), Play Integrity (API standard em Java e API classic nativa), biblioteca nativa de tokens WASafe, stanzas `integrity_payload` / `keystore_attestation`, parâmetro `gpia` do registro, autoverificação da assinatura do app, flag de origem da instalação, telemetria de root / emulador / cliente modificado (`wam_daily`), o que é bloqueado vs apenas reportado, o que permanece unknown

---

## 1. O que é "client integrity" nesta build

Não existe um gate único. O cliente produz várias provas e sinais independentes; todos são criados no dispositivo e enviados ao servidor. Nenhum código do lado do cliente foi encontrado que se recuse a rodar em um cliente modificado, com root ou reassinado. Todas as afirmações são análise estática do APK decompilado (`versionCode 264100600`). Níveis: **found** = lido no código, **inferred** = deduzido, **unknown** = não resolvível estaticamente.

Os nomes ofuscados são por build e foram resolvidos novamente a partir de strings estáveis na 2.26.41.6.

| Mecanismo | Produz | Enviado como | Uso no servidor |
|-----------|----------|---------|-----------|
| Keystore key attestation, tag de log interna `blacknoise` (`C25730yT`) | Cadeia de certificados DER de uma chave EC do `AndroidKeyStore` com attestation challenge | stanza `<ib><keystore_attestation>`; repasse ao nativo na hora do registro; caminhos de passkey e de pareamento de companion | unknown (não observável) |
| Play Integrity, API standard em Java (`C45007Jkc`) | Standard Integrity token (`gpia`) | parâmetro HTTP de registro `gpia`; token de pareamento de companion ("md-pairing") | unknown |
| Play Integrity, API classic nativa (`libwhatsapp.so`, `WAJIntegrityGpiaStatusRequest`) | Classic Integrity token via JNI | `<ib><integrity_payload>` (sink em Java found; ligação com o produtor nativo inferred) | unknown |
| WASafe (`libwasafe.so`, `libwasafedeps.so`) | Blob criptografado estilo ECIES de dados fornecidos pelo chamador, em base64 | sink unknown | unknown |
| Autoverificação da assinatura do app (`AbstractC38241gg`, `C27965CCj`) | valor 0/1 | atributo comum do WAM **6251** | unknown |
| Flag de origem da instalação (`CHH`) | boolean de instalador `com.android.vending` | atributos WAM `install_source_official`, **10255** | unknown |
| Flags de estado do dispositivo (`Cdt` → `C0Fp`) | `is_rooted`, `is_genymotion`, `is_monkeyrunner_running`, `is_using_custom_rom`, `is_whatsapp_plus_user` | evento WAM `wam_daily` | unknown |
| Diagnósticos de suporte (`C00L.A0F`) | tag "rted" | strings de contato com o suporte / relatório de debug | somente suporte |

Não são atestação de integridade, não confundir (ver 11): `com.whatsapp.integrityai` (detecção de golpes on-device), `bizintegritysignals`, UI de banimento WFAC (`com.whatsapp.waffle.wfac`), vinculação de contas (`com.whatsapp.waffle`).

| Entidade | Nome na 2.26.41.6 | Função |
|--------|----------------|------|
| Keystore attestation | `C25730yT` | par de chaves, cadeia de certificados, assinatura (alias `A00`/`A01`, `A02` gera, `A03` cadeia, `A07` assina) |
| Enum de modo de atestação | `C02U` | `C02U.A00` = dynamic, `C02U.A01` = static |
| Runnable de envio da stanza | `RunnableC48591z1` case 3 via `C41141ly` | envia `keystore_attestation` |
| Handler de conexão estabelecida | `A01` no handler de conexão (`smali/X/0Yq`) | agenda `sendKeystoreAttestation` |
| Trabalho na hora do registro | `C25810yb`, `KZ2` case 39, `K49.A0s` | atestação static para o nativo, tag `regtime_ka` |
| Pré-aquecimento do companion | `H1K` (atestação), `H1J` (Play Integrity) | cache de cadeia / token para o pareamento |
| Wrapper do Play Integrity | `C45007Jkc` | prepare + request da API standard |
| HTTP de registro | `K49` | adiciona `gpia` aos parâmetros da requisição |
| Ponte JNI | `com.whatsapp.wamsys.JniBridge` | `sendAttestationResult`, callbacks `jnidispatch*`, `wsafeplatform_context` |
| Gate de assinatura | `AbstractC38241gg` | janela de versão + SHA-1 do certificado de assinatura |
| Verificador de assinatura | `C27965CCj` | nome do pacote + SHA-256 do certificado de assinatura vs valores embutidos |
| Future da origem da instalação | `CHH` | `install_source_official` |
| Evento WAM diário | `C0Fp` (`getEventNameForFalco()` = `wam_daily`) | flags do dispositivo |
| Preenchedor de flags WAM | `Cdt` (smali) | preenche os booleanos de `C0Fp` |
| Helpers de root / emulador | `C00L` | `A0F` root, `A0C` emulador, `A0B` ROM customizada, `A0D` automação de testes |

---

## 2. Keystore key attestation ("blacknoise")

### 2.1 Geração de chave (`C25730yT.A02`)

Tudo controlado pela ab-prop **1934** (`A06()`, padrão `true`).

| Item | Valor | Nível |
|------|-------|------|
| Keystore | `AndroidKeyStore` | found |
| Finalidade da chave | `4` (`PURPOSE_SIGN`), digests `SHA-256`, `SHA-512`, autenticação do usuário não exigida | found |
| Algoritmo | ab-prop **2076**, padrão `"EC"`; `"RSA"` adiciona padding `PKCS1` | found |
| Algoritmo de assinatura | ab-prop **2075**, padrão `"SHA256withECDSA"` | found |
| Base do alias | ab-prop **2074**, padrão `the_well_of_wishes_awaits_in_the_crypt_of_decay`; fallback hardcoded `my_personal_mini_pony` quando a prop é null | found |
| Alias | dynamic: `<base>[_<suffix>]`; static: `<base>_static[_<suffix>]`; suffix = UUID aleatório armazenado nas prefs `ka_key_store_dynamic_alias_suffix` / `ka_key_store_static_alias_suffix`, rotacionado quando uma regeneração encontra um suffix existente | found |
| Validade do certificado | agora + ab-prop **2079** segundos (padrão 86400) | found |
| Attestation challenge | definido apenas em SDK >= 24 | found |
| Device-properties attestation | `setDevicePropertiesAttestationIncluded(true)` em SDK >= 31; em `ProviderException` repete sem (log `blacknoise/disbabling device ids att`) | found |

Layout do attestation challenge (found):

```
challenge = BE64(unix_seconds) ‖ 0x1F ‖ nonce
nonce     = caller-supplied bytes, else SecureRandom(ab-prop 2078 bytes, default 32)
```

### 2.2 Renovação e throttle

| Pref / prop | Significado | Padrão | Nível |
|-------------|---------|---------|------|
| `ka_refresh_ts` + ab-prop **2079** | chave dynamic recriada quando mais antiga que isso | 86400 s | found |
| `ka_static_refresh_ts` + ab-prop **4878** | renovação da chave static | 600 s | found |
| `ka_retried_ts` + ab-prop **2427** | dynamic: regeneração tentada cedo demais -> log `regeneration attempted too soon, waiting` | 600 s | found |
| `A04()` | apaga ambos os aliases e zera todas as prefs `ka_*` | – | found |

### 2.3 Cadeia de certificados (`C25730yT.A03`)

`keyStore.getCertificateChain(alias)`, cada certificado com `getEncoded()` (DER), concatenados em ordem inversa (root primeiro, leaf por último) em um único array de bytes. Cadeia vazia registra `empty list of certificates found`. Falhas são reportadas ao error reporter como `attestation-creation`, `attestation-nocertchain`, `attestation-nosign` (found). O tempo é registrado como `att-gen` / `att-sign` (found).

### 2.4 Assinatura (`C25730yT.A07`)

`Signature.getInstance(prop 2075)` sobre um payload do chamador com a chave static. Entrada de chave ausente -> `attestation-nosign` "cannot sign payload, att pair missing". Chamadores de `A07` não foram encontrados no código decompilado (lacunas de decompile são possíveis); onde uma assinatura seria enviada é unknown.

### 2.5 Quatro consumidores da cadeia

| # | Gatilho | Modo | Nonce | Sink | Nível |
|---|---------|------|-------|------|------|
| 1 | Servidor conectado (`handleConnected` no handler de conexão, nome do job `sendKeystoreAttestation`) | dynamic (`C02U.A00`) | chave pública static do cliente (Noise) (`C25710yR.A0H()`) | `<ib><keystore_attestation>chain</keystore_attestation></ib>` via `C10140Tq.A0X(node, 6)` | found |
| 2 | Registro (`K49.A0s`, job `regtime_ka`, runnable `KZ2` case 39) | static (`C02U.A01`) | chave pública static do cliente | `JniBridge.jvidispatchIOO(1, ctx, chain)` para o nativo, com retry/backoff (ab-props **2863** 1000 ms, **2864** 5 tentativas); `K49.A0s` espera até a ab-prop **4696** (1880 ms) quando solicitado | found (uso no nativo unknown) |
| 3 | Início do registro de companion (`C0YS` `startcompanionreg` -> `H1K.A00`) | dynamic | chave pública static do cliente | em cache em `H1K` (campo `A02`), renovado por helper estilo `KeyAttestationLifetimeManager`; controlado pelas ab-props **6430** (padrão `true`), **7217** (bucket), intervalo **6431** (600000 ms), tentativas **6433**/**6434** | found (cache); consumidor dos bytes em cache não resolvido: unknown |
| 4 | API de servidor de passkey (`I16` case 18, `PasskeyServerApiImpl`) | dynamic | bytes fornecidos pelo servidor | devolvido ao chamador do passkey | found (o que o chamador faz é unknown) |

Gate da stanza para #1: `A06()` e ab-prop **1935** (padrão `true`), e no máximo uma vez a cada ab-prop **2067** segundos (padrão 86400), armazenado na pref `ka_stanza_sent_ts`. Uma cadeia null registra `blacknoise: got null attestation chain in custom stanza` e não envia nada (found).

Formato da stanza (found):

```
<ib>
  <keystore_attestation>[binary: DER certs, root first]</keystore_attestation>
</ib>
```

`keystore_attestation` também é um dictionary token (segundo dicionário, `AbstractC40911lb.A01[0]`), portanto é codificado como token na rede (found).

Vínculo: como o nonce em #1 a #3 é a própria chave pública static Noise do cliente, a extensão de challenge da cadeia de certificados carrega a identity key, ligando a chave de hardware à chave static da conta (inferred a partir da escolha do nonce; verificação no servidor unknown).

---

## 3. Play Integrity

### 3.1 API standard em Java (`C45007Jkc`)

| Item | Valor | Nível |
|------|-------|------|
| API | `IntegrityManagerFactory.createStandard` -> `StandardIntegrityManager` | found |
| Número do cloud project | `293955441834` (`PrepareIntegrityTokenRequest.setCloudProjectNumber`) | found |
| Prepare (`A00(callback, tag)`) | rotulado por tag; ignorado se já existe um token provider; recusa sem rede; máx. 5 prepares por 60 s (pref `pref_gpia_prepare_call_count_in_last_interval`) | found |
| Request (`A01(callback, nonce, tag)`) | `StandardIntegrityTokenRequest.setRequestHash(nonce)`; falha com 1003 se não há provider | found |
| Códigos de erro internos (`JCX`) | 1001 sem rede, 1002 prepares demais, 1003 não preparado, 1004 timeout (`C47238Kk7`), 1005 sem chave static (`Kmc`) | found |
| Eventos do error reporter (`GKY`) | `ka_at_md_generate_attestation`, `gpia_at_md_prepare`, `gpia_at_md_generate_attestation` | found |

Pontos de chamada do prepare (found): `RegisterPhone` (tag `register_phone`), `VerifyPhoneNumber` (tag `verify_phone`), pareamento de companion (tag `md-pairing`, `H1J`), mais um caminho de retry em `C41354Hz3`.

### 3.2 Parâmetro HTTP de registro `gpia`

`K49.A0V` adiciona um campo ao mapa da requisição HTTP de registro:

```java
if (!flag(3753)) return;               // default false
nonce = Base64(static_public_key, NO_PADDING|NO_WRAP);   // C47343Kmc case 48
token = request(nonce, tag="reg");     // timeout ab-prop 4263, default 1800
map.put("gpia", token);
```

| Item | Valor | Nível |
|------|-------|------|
| Gate | ab-prop **3753**, padrão `false` | found |
| Nonce | base64 (flags 3) da chave pública static do cliente (`C25710yR.A0H()`); chave null -> erro 1005 | found |
| Adicionado em | `checkIfExists` (dois caminhos de código), `verifySecurityCode` | found |
| Outras requisições (pedido de código, register final) | `A0V` não é chamado ali no código decompilado | found (ausência no decompile) |
| Métrica de tempo | `gpia-param-prepare` | found |

O padrão `false` significa que o parâmetro só é enviado quando o servidor habilita a prop 3753. Se o servidor de registro o exige: unknown.

### 3.3 Token de pareamento de companion

`H1J` (controlado por `A07(...)`, prop **7006** padrão `false`, intervalo **7007** = 21600000 ms) faz o prepare ("md-pairing") e `I16` case 3 solicita um token com nonce = base64(chave pública static, flags 3), timeout prop **7010** (1000 ms). Falhas registradas como `gpia_at_md_prepare` / `gpia_at_md_generate_attestation`. O consumidor do token não está resolvido (unknown).

### 3.4 API classic nativa e `integrity_payload`

Strings em `libwhatsapp.so` (found): `WAJIntegrityGpiaStatusRequest`, `WAJIntegrityGpiaStatusRequestAttributes`, `_WAJIntegrityTriggerGPIAWithRequestAttributes`, `_WAJIntegritySendResponseOrRetry`, `_WCAAPIGenerateGPIAParamOnMain`, e assinaturas JNI de `IntegrityManagerFactory.create(Context)`, `IntegrityTokenRequest.Builder` (`setNonce`, `setCloudProjectNumber`), `IntegrityManager.requestIntegrityToken`. O código nativo, portanto, conduz o Play Integrity (requisição classic) por conta própria via JNI.

Sink em Java (found):

```java
// JniBridge.jnidispatch... case 3  (callback "sendAttestationResult")
node = <ib><integrity_payload>{string}</integrity_payload></ib>   // C10140Tq.A0X(node, 194)
metric type "safety-net-attestation", result "success"/"failed"
```

A string de tipo de métrica `safety-net-attestation` é um rótulo legado; nenhuma API SafetyNet é usada (ver 10). A afirmação "o `WAJIntegrityGpiaStatusRequest` nativo produz a string `integrity_payload`" é **inferred** a partir dos nomes; a cadeia de chamadas dentro do código nativo stripped não foi rastreada. O que dispara uma requisição de status nativa (agenda do cliente vs pedido do servidor) é unknown.

O nativo lê ab-props por `jnidispatchIII(feature, kind)`; IDs mapeados (found): kind 0: 12->13178, 13->13456, 15->22925, 16->24048; kind 1: 13->13455. `jnidispatchO(1)` retorna a string da ab-prop **10266** (padrão vazio). A finalidade dessas props é unknown.

### 3.5 Outros usuários do Play Integrity

| Classe | Uso | Nível |
|-------|-----|------|
| família `JK4`, `KM0` | SDK reCAPTCHA Enterprise (`recaptcha.net`) com seu próprio `StandardIntegrityManager`; o resultado vai no parâmetro HTTP `recaptcha` (`K49.A0Z`) quando presente | found |
| `KLL`, `KLN`, `C42885In8`… | implementação de integridade do Play Core embutida (código de biblioteca) | found |

---

## 4. Biblioteca nativa WASafe

### 4.1 Lado Java

| Hook | Comportamento | Nível |
|------|-----------|------|
| `jnidispatchI(4)` | carrega `libwasafe.so` (`"wasafe"`), registra `WCAAPIEnsureSafeLibraryLoaded libwasafe.so load failed` em `UnsatisfiedLinkError` | found |
| `jnidispatchI(5)` | retorna a pref `runtime_override` do SharedPreferences `wsafeplatform_context`, senão a constante `1090327562` | found |
| Atributo WAM **15611** | a mesma constante, gravada como string `1090327562` nos atributos comuns | found |

O significado de `1090327562` é unknown (candidato: valor de runtime / tipo de detecção do WASafe, não verificado).

### 4.2 `libwasafe.so` (14480 bytes, arm64, stripped)

Exports: `WASafeSignalsCreate`, `WASafeSignalsConfigure`, `WASafeSignalsPrepare`, `WASafeSignalsGetBase64EncodedData`, `WASafeSignalsRelease`, `WASafeStatus`. Imports: libc (`stat`, `rand`, `srand`, `gettimeofday`, `malloc`…) e `WASafeDepsCrypto*` de `libwasafedeps.so`.

| Função | Comportamento decompilado | Nível |
|----------|---------------------|------|
| `WASafeSignalsConfigure(x)` | armazena `x` (tipo de detecção) em um global, zera um segundo global | found |
| `WASafeSignalsPrepare()` | grava a constante de status `0x1092` em um global; nenhum outro trabalho | found |
| `WASafeSignalsGetBase64EncodedData()` | passa os dados/comprimento do contexto por encrypt+base64 (`sub_6a00`) e retorna `{ptr, len}` | found |

Esta build da `libwasafe.so` não contém coleta de sinais: sem strings de root, debugger, hook, emulador ou caminhos de arquivo, e o único import de filesystem é `stat`. A `libwhatsapp.so` também contém uma string `WASafeSignalsStub` e `WAIntegrityPrepareSafeSignals(WASafeDetectionType)` com tags de log `safesignals/prepare` e `safesignals/generate` (found). De onde vêm os dados que são criptografados é unknown.

### 4.3 `libwasafedeps.so`

Exporta `WASafeDepsCryptoInputCreate`, `...SetServerPublicKey`, `...SetData`, `...EncryptBase64`, `...ResultGetData/GetLength/Release`; importa mbedtls (`ctr_drbg`, `entropy`, `gcm_setkey`, `gcm_crypt_and_tag`). Estrutura (found a partir de imports e nomes): chave efêmera aleatória, segredo compartilhado com uma chave pública do servidor, AES-GCM, base64. A curva exata e o KDF não foram redecompilados para esta build; uma construção Curve25519 ECDH + AES-GCM é **inferred**. Valor e rotação da chave pública do servidor: unknown.

---

## 5. Autoverificação da assinatura do app e origem da instalação

### 5.1 Gate (`AbstractC38241gg.A00`)

```java
long vc = versionCode;
if (vc < 264100600 || vc > 264100608) return 0;          // outside window
sha1 = Base64(SHA-1(signatures[0]), 11);
return "OKD31QX-GP7GT780Psqq8xDb15k".equals(sha1) ? 1 : 0;
```

A janela de versão começa no `versionCode` desta build (264100600). O resultado fica em cache em um static.

### 5.2 Verificador (`C27965CCj.A00(pkg, certBytes)`)

| Passo | Comportamento | Nível |
|------|-----------|------|
| 1 | Nome do pacote mascarado por XOR com uma chave de 5 bytes e comparado com dois arrays de bytes embutidos que decodificam para `com.whatsapp` e `com.whatsapp.w4b` | found |
| 2 | Se o pacote não é nenhum dos dois: retorna `true` imediatamente | found |
| 3 | Senão SHA-256 dos bytes do certificado, mascarado por XOR e comparado com dois valores embutidos de 32 bytes; correspondência -> `false`, divergência -> `true` | found |

O decompile deste método falhou; os passos foram lidos do dump de instruções.

### 5.3 Consumidor

Dentro do `initializeCommonAttributes` do WAM (runnable `RunnableC29340CoR`):

```java
long r = AbstractC38241gg.A00(ctx);          // 1 only when version window + SHA-1 match
if (r == 1) r = verifier(pkg, cert) ? 0 : 1;
common attribute 6251 = r;                   // 1 = both checks passed, 0 = otherwise
```

Portanto **6251 = 1** significa "o certificado de assinatura corresponde aos valores embutidos do WhatsApp" (found); 0 significa divergência ou build fora da janela (found). O valor só é reportado em telemetria. Nada no cliente reage a ele (nenhum caminho de código encontrado que leia o resultado para bloquear ou degradar). Uso no servidor: unknown.

### 5.4 Origem da instalação

`getInstallSourceInfo().getInstallingPackageName()` (SDK >= 30, senão `getInstallerPackageName`) comparado com `com.android.vending` (`C18970md`, `RunnableC29340CoR`): armazenado no future `CHH.A01`. Reportado como atributo WAM **10255** e como `install_source_official` em conjuntos de atributos de logging (`HO4`, `C08650Nr`, `AbstractC35718FdU`). Também o campo `install_source` de `C0Fp` (`wam_daily`). Usos separados da mesma comparação selecionam o instalador de módulos Voltron (`AbstractC12860bs`) (found). O resultado é telemetria mais roteamento de download de módulos; nenhuma imposição encontrada.

---

## 6. Sinais de root, emulador e cliente modificado

### 6.1 Flags de dispositivo do `wam_daily`

`C0Fp` é o evento `wam_daily` (`getEventNameForFalco()`); seus campos abaixo são preenchidos em `Cdt` (smali). Reportados, não impostos (found).

| Campo | Origem | Nível |
|-------|--------|------|
| `is_rooted` | `C00L.A0F(telephony helper)` | found |
| `is_using_custom_rom` | `C00L.A0B()` (strings de kernel/fabricante/display: cyanogen, debug, Darky, XDAndroid, MIUI…) | found |
| `is_whatsapp_plus_user` | `Class.forName("org.acra.ACRA")` tem sucesso (classe ausente deste APK; tipicamente embutida por clientes de terceiros) | found (checagem); "tipicamente embutida" inferred |
| `is_genymotion` | sonda de pacote para a região `com.genymotion.superuser` em `Cdt`; condição exata parcialmente rastreada | found (sonda), lógica inferred |
| `is_monkeyrunner_running` | origem não resolvida | unknown |
| `google_play_services_available`, `google_play_services_version`, `install_source` | presentes no mesmo evento | found |

### 6.2 Heurística de root em `C00L.A0F`

Static em cache. True quando qualquer um destes: `Build.TAGS` contém `test-keys`; `/system/app/Superuser.apk` existe; executável `su` em `/system/bin/su` ou `/system/xbin/su` (`canExecute`), com log extra `app/dly`; product/model/manufacturer semelhante a emulador (`sdk`) ou sem SIM/telefonia (a flag `z` só é usada no sufixo do log, found). Helpers relacionados: `A0C` emulador (brand/device `generic`, `goldfish`, `ranchu`, `google_sdk`, `Emulator`, `Android SDK built for x86`, `Genymotion`), `A0D` automação de testes (system property `fb.running_sapienz`).

### 6.3 Onde `A0F` é consumido

| Consumidor | Uso | Nível |
|----------|-----|------|
| builder de relatório de debug `C10V` | acrescenta `DC-RTED` (root) e `DC-BACRM` (ROM customizada) ao texto de diagnóstico | found |
| mapa de diagnósticos de contato `C1Z` | chave `diagnostic` = `rted ` (e `nw-wap ` se `org.acra.ACRA` está presente) | found |
| `C28049CFz` (estado do fluxo de verificação) | contexto de contato `register-phone-rtd` na tela de número de telefone | found |
| `Cdt` | `wam_daily.is_rooted` | found |
| `KH2` (crash reporter `lacrima`) | `ExtraDeviceInfoCollector` grava a flag de root (`test-keys`, `Superuser.apk`, `su` no `PATH`) nos relatórios de crash | found |

Nenhum desses bloqueia o registro ou as mensagens (found: nenhum ramo encerra o fluxo com base nesses booleanos). Se o servidor pondera as flags do `wam_daily`: unknown.

### 6.4 Não encontrado

| Checagem | Resultado |
|-------|--------|
| Strings de Magisk, Xposed (`de.robv`), Substrate, Frida no código do WhatsApp (`libwhatsapp.so`, Java) | não encontrado |
| `ro.kernel.qemu`, autoverificação de `FLAG_DEBUGGABLE` | não encontrado |
| Lista de pacotes banidos para clientes mod nomeados (GB, FM, Plus) | não encontrado |
| Autoverificação de CRC de dex / assets | não encontrado nesta passada (não pesquisado exaustivamente) |
| Checagem de chave com respaldo em hardware (`KeyInfo.isInsideSecureHardware`) no código de atestação próprio do WhatsApp | não encontrado (apenas em classes de biblioteca `BinderC48420LDc`, `C51962N8y`) |
| `FetchIntegritySignals`, `IntegrityChallengeResponse`, `relax_integrity_constraints_for_bb_wa_tenured_accounts` | não encontrados em nenhum lugar do APK (Java, smali, assets, nativo) |
| API `SafetyNet` | não encontrada |

`isDebuggerConnected` aparece apenas no detector de ANR (`SigquitBasedANRDetector`) e em helpers de crash.

---

## 7. Feature flags e ab-props

| ID | Valor / padrão | Controla |
|----|-----------------|----------|
| **1934** | `true` | gate mestre do blacknoise (`C25730yT.A06`) |
| **1935** | `true` | enviar a stanza `keystore_attestation` após conectar |
| **2067** | 86400 | segundos mínimos entre envios da stanza |
| **2074** | `the_well_of_wishes_awaits_in_the_crypt_of_decay` | base do alias da chave |
| **2075** | `SHA256withECDSA` | algoritmo de assinatura |
| **2076** | `EC` | algoritmo da chave |
| **2078** | 32 | comprimento do nonce aleatório |
| **2079** | 86400 | validade do certificado e segundos de renovação dynamic |
| **2427** | 600 | segundos mínimos entre regenerações dynamic |
| **4878** | 600 | segundos de renovação static |
| **2863** / **2864** | 1000 / 5 | base de backoff (ms) / tentativas na hora do registro |
| **4696** | 1880 | espera do registro pela atestação (ms) |
| **3753** | `false` | parâmetro de registro `gpia` |
| **4263** | 1800 | timeout da requisição `gpia` |
| **6430** | `true` | pré-aquecimento da atestação do companion (`H1K`) |
| **6431** | 600000 | idade do cache da atestação do companion (ms) |
| **6433** / **6434** | 5 / 1000 | tentativas / timeout do lifetime-manager da atestação do companion |
| **7217** | 1 | módulo do bucket da atestação do companion |
| **7006** | `false` | pré-aquecimento do Play Integrity do companion (`H1J`) |
| **7007** | 21600000 | idade do cache do token do companion (ms) |
| **7009** / **7010** | 5 / 1000 | tentativas / timeout do Play Integrity do companion |
| **10266** | string vazia | string entregue ao nativo via `jnidispatchO(1)` |
| **26215** | `false` | caminho alternativo de verifySecurityCode em `K49` (não específico de integridade) |

Os padrões são os valores compilados; o servidor pode sobrescrever as ab-props (found: tabela de props; valores do servidor unknown).

---

## 8. Casos de erro

| Sintoma | Causa | Correção / nota |
|---------|-------|-----------|
| Sem stanza `keystore_attestation` | prop 1934 ou 1935 false; enviada nos últimos 2067 s; cadeia null | por design |
| relatório de erro `attestation-creation` | falha na geração da chave (`ProviderException`, sem TEE) | nova tentativa depois, limitada por 2427 |
| `attestation-nocertchain` | `getCertificateChain` falhou ou veio vazia | – |
| `attestation-nosign` | `A07` chamado sem a entrada da chave static | – |
| `blacknoise/regeneration attempted too soon, waiting` | `ka_retried_ts` dentro de 600 s | aguardar |
| `blacknoise: not boostrapped for reg` | `C25810yb.A00` false na hora do registro | atestação ignorada para aquele registro |
| Play Integrity 1001 / 1002 / 1003 / 1004 / 1005 | sem rede / > 5 prepares por 60 s / não preparado / timeout / sem chave static | códigos internos (`JCX`) |
| `gpia` ausente na requisição de registro | prop 3753 false ou a requisição falhou (resultado null colocado como vazio) | ver 3.2 |
| `libwasafe.so load failed` | `UnsatisfiedLinkError` | apenas registrado em log |
| Atributo de assinatura 6251 = 0 | APK reassinado, certificado diferente ou build fora de `264100600..264100608` | apenas telemetria |

---

## 9. Baileys / clientes de protocolo

| Item | Afirmação | Nível |
|------|-----------|------|
| Checagens no lado do app | Um cliente puramente de protocolo nunca executa nenhum dos códigos acima | found (por definição) |
| Stanzas `keystore_attestation` / `integrity_payload` | Um cliente que as omite simplesmente não as envia; se o servidor rejeita, limita ou marca essas contas: unknown | unknown |
| Parâmetro de registro `gpia` | Opcional por padrão (prop 3753 `false`); imposição no servidor por região/conta: unknown | unknown |
| Forjar atestação | A cadeia deve ter raiz em hardware/raízes do Google e carregar o challenge; não há segredo do cliente a copiar, a validação fica no servidor | inferred |
| Risco conhecido | A política do servidor depende de dados que este relatório não consegue observar (comportamento, idade da conta) | unknown |

Correção: nenhuma derivável estaticamente. Enviar valores fabricados não é sustentado por nenhuma evidência encontrada aqui.

---

## 10. Distinções principais

| Não confundir | Fato |
|----------------|------|
| string de métrica `safety-net-attestation` vs SafetyNet | apenas rótulo; o payload vem do Play Integrity; não existe API SafetyNet no código |
| `keystore_attestation` vs `integrity_payload` | stanzas diferentes: cadeia de certificados DER (bytes) vs string de token do Play Integrity; produtores diferentes (Java/Keystore vs nativo/Play) |
| `gpia` em Java (API standard, request hash) vs GPIA classic nativo | APIs e sinks diferentes (parâmetro HTTP vs `<ib>`); construção do nonce da variante nativa não rastreada |
| Atestação static vs dynamic | alias static `..._static` (registro), alias dynamic (pós-conexão, companion, passkey) |
| Nonce | chave pública static do cliente em três consumidores; bytes do servidor no consumidor de passkey |
| `blacknoise` vs WASafe | Keystore attestation (Java) vs biblioteca nativa de blob criptografado |
| WASafe vs "signals" | a `libwasafe.so` desta build não coleta nada; o nome sugere sinais, o código não |
| 6251 vs 10255 | correspondência de assinatura vs instalador Play |
| `is_whatsapp_plus_user` vs uma allowlist de clientes mod | uma única sonda reflexiva de classe; não existe allowlist |
| `integrityai`, `bizintegritysignals` | recursos de segurança de conteúdo / business (detecção de golpes, UI de sinais de business), não atestação do cliente |
| WFAC / `waffle` | UI de banimento e vinculação de contas, não um componente de atestação |
| Reporte vs imposição | todos os resultados de root, emulador, assinatura e instalador encontrados são telemetria ou texto de suporte |

---

## 11. Componentes relacionados que não são atestação do cliente

| Componente | Fatos | Nível |
|-----------|-------|------|
| `com.whatsapp.integrityai` | `IntegrityAiOrchestrator`, `ScamDetectorImpl`, download de modelos (`IntegrityAiModelDownloadCoordinator`, tier do dispositivo), UI de opt-in `ScamDetectionSettingsActivity`; tag do store de resultados `IntegrityAi/ScamDetectionResultStore`; um classificador nativo chamado `kaleidoscope` não foi reverificado nesta build | found (estrutura); parte nativa unknown |
| `com.whatsapp.bizintegritysignals` | fetcher GraphQL e manager para sinais de integridade de business exibidos na UI | found |
| `com.whatsapp.waffle.wfac` | UI de decisão de banimento (`WfacBanActivity`, `WfacBanDecisionFragment`, `WfacUnbanDecisionFragment`) | found |
| `com.whatsapp.waffle.accountlinking` e irmãos | vinculação de contas, SSO, crossposting, verificação de idade | found |

---

## 12. Fluxo ponta a ponta

```
[Registration screens: RegisterPhone / VerifyPhoneNumber]
    │  C45007Jkc.A00  prepareIntegrityToken (cloud project 293955441834, tag register_phone / verify_phone)
    │  K49.A0s  "regtime_ka": C25730yT.A03(static)  nonce = static pubkey
    │      └── JniBridge.jvidispatchIOO(1, ctx, chain)  ──►  [native wamsys]  (use unknown)
    ▼
[K49 HTTP: exist / verifySecurityCode]
    │  if ab-prop 3753:  gpia = standard-API token, requestHash = b64(static pubkey)
    ▼
[WA registration server]  (validation not observed)

[Connected session]
    │  handleConnected ─► job "sendKeystoreAttestation"
    │  ab-props 1934 && 1935, once per 86400 s
    │  C25730yT.A03(dynamic, nonce = static pubkey) ─ AndroidKeyStore EC key, challenge = ts ‖ 0x1F ‖ nonce
    ▼
<ib><keystore_attestation>DER chain, root first</keystore_attestation></ib>
    ▼
[WA server]  (use unknown)

[Native libwhatsapp]  WAJIntegrityGpiaStatusRequest ─► classic IntegrityManager via JNI   (inferred link)
    │  JniBridge callback sendAttestationResult
    ▼
<ib><integrity_payload>token</integrity_payload></ib>   (node code 194)
    ▼
[WA server]  (use unknown)

[Companion pairing]
    │  C0YS startcompanionreg ─► H1K (chain cache) + H1J (GPIA token, tag md-pairing)
    ▼  consumer of cached bytes/token: unknown

[Telemetry, daily and common attributes]
    │  6251 signature match, 10255 Play installer, 15611 wasafe constant
    │  wam_daily: is_rooted, is_genymotion, is_using_custom_rom, is_whatsapp_plus_user, install_source
    ▼
[WA server]  (use unknown)
```

---

## 13. Unknowns

| Pergunta | Por que é unknown |
|----------|-------------|
| Validação e imposição de qualquer token no servidor | lado servidor, nenhum tráfego observado |
| O que dispara o `WAJIntegrityGpiaStatusRequest` nativo e como o nonce é construído | código nativo stripped não rastreado (decompiler para a biblioteca grande indisponível aqui) |
| De onde vêm os dados de entrada do WASafe e o que significa `1090327562` | nenhum produtor encontrado nos nativos stripped |
| Uso nativo dos bytes de atestação da hora do registro | apenas a entrada JNI (`jvidispatchIOO(1)`) é visível |
| Consumidores da cadeia em cache de `H1K` e do token de `H1J` | pontos de chamada não resolvidos no código decompilado |
| Significado da ab-prop 10266 e dos IDs de feature de `jnidispatchIII` | apenas valores |
| Origem de `is_monkeyrunner_running`, condição exata de `is_genymotion` | não rastreado |
| Chamadores de `C25730yT.A07` (assinatura) | nenhum encontrado; lacunas de decompile possíveis |
| Se existe alguma imposição para as flags de telemetria | nenhum ramo no cliente encontrado; servidor unknown |
