<!-- src-sha1: 5428e0461d6ea8f961256e4ead0fe3df30ea4164 -->
# WhatsApp Contorno de Censura — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** Fallbacks de conectividade do Android quando o chatd está bloqueado: WhatsApp Proxy configurado pelo usuário (UI de configurações, armazenamento, link de compartilhamento, uso por chatd e mídia), serviço de proxy controlado pelo servidor (túnel Psiphon, módulo Voltron, restrições de região e VPN, túnel SOCKS com cabeçalho PROXY v2), lista de IPs de fallback (`<ib><fbip>`, arquivo `fbips`), push de desbloqueio (`fbips`, `unblocking_props`, `psl`), cadeia de fallback de DNS, provedores de relay de registro e estratégias de nova tentativa, papéis de Tigon e DGW, rastreamento de estado da conexão e diagnósticos, interação com novas tentativas, feature flags, mecanismos ausentes, comparação com Baileys

---

## 1. O que está presente neste build

Todas as afirmações vêm de análise estática do APK decompilado; nada foi capturado na rede. Níveis: **found** = lido em código ou recursos, **inferred** = deduzido, **unknown** = não resolvido. Os nomes ofuscados são específicos de cada build e foram re-resolvidos na 2.26.41.6. Transporte do chatd, handshake, escada de hosts e backoff estão em [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) e não são repetidos aqui.

| Mecanismo | Estado | Pontos de entrada | Tier |
|-----------|--------|-------------------|------|
| WhatsApp Proxy (relay de chat e mídia configurado pelo usuário) | presente, UI do usuário, controlado por feature flag | `SettingsUserProxyActivity`, `SettingsSetupUserProxyActivity`, `C12660bX`, `C12690ba`, passo 12 da sequência do chatd | found |
| Serviço de proxy (túnel Psiphon, módulo Voltron `proxyservice`) | presente, controlado pelo servidor, sem UI do usuário | `C12760bh` (orquestrador), `C42448IfJ` / `S6G`, `ca.psiphon.PsiphonTunnel`, `ProxyServiceBroadcaster` | found; biblioteca nativa não está no APK |
| Lista de IPs de fallback | presente | `<ib><fbip>` em `C40581l4`, `C36821d6`, arquivo `fbips` | found |
| Tabela fixa de host para IP, escada de hosts | presente | `AbstractC47101wK` (18 nomes de host), `C37151de` | found |
| Cadeia de fallback de DNS (plataforma / MNS, UDP para 8.8.8.8 e 8.8.4.4, fixo no código) | presente | `C36881dC`, `QG1` | found |
| Push de desbloqueio (`nt` = `unblocking`) | presente | `CLl` parser, `C28139CLl`, `C28912ChD`, `C27946CBo` | found |
| Relay de registro (provedores de cloud function) e estratégias de nova tentativa | presente, somente registro | `res/raw/domain_fronting_providers.tsv`, `C45421Jrl`, `RetryingHttpClient` | found |
| Tigon / DGW como fallback do chatd | não presente | a configuração de fallback do DGW existe, mas é construída desabilitada | found |

Não presente neste build (found como ausência no Java decompilado, manifest e recursos; código nativo não inspecionado):

| Ausente | Evidência |
|---------|-----------|
| chatd sobre WebSocket, HTTP long-poll ou MQTT | nenhum literal `wss://` ou `/ws/chat` no Java; `mqtt` apenas em rótulos de analytics e de stream do DGW (ver seção 13 do relatório Noise) |
| `VpnService` do Android | nenhum service ou `BIND_VPN_SERVICE` no manifest; o Psiphon roda em modo de proxy local |
| Proxy SOCKS ou HTTP-CONNECT configurável pelo usuário para o chatd | o passo 12 constrói um socket direto para `host:chatPort`, sem handshake de proxy |
| Proxy do sistema (`http.proxyHost`, `https.proxyHost`) para o chatd | não é lido pela sequência nem pelo código de socket; lido apenas pelo Tigon e como guarda (seção 4.6) |
| Domain fronting ou relay para o chatd | a lista de provedores é consumida apenas pelo cliente de registro (seção 7) |
| Tor, Snowflake, outros pluggable transports | nenhum código ou recurso encontrado |

Pontos que determinam o restante do relatório:

- Existem dois mecanismos de proxy independentes que nunca rodam juntos: o proxy do usuário (passo 12, terminal) e o serviço de proxy Psiphon (túnel SOCKS que substitui as conexões diretas em um subconjunto de passos). Com um proxy do usuário definido, a configuração do serviço é ignorada (`ConnectionSequence/socketConfigForUserProxy/skipping socks proxy in favor of user proxy`).
- Com um proxy do usuário válido, a sequência tem exatamente um alvo. O passo 12 avança para 16 (esgotado); não há fallback para hosts diretos (found, `C37031dS.A0G`).
- `libgojni.so` é entregue dentro do módulo baixável. O APK contém apenas o manifest do módulo; a discagem do túnel, a seleção de protocolo e o comportamento anti-DPI são unknown.

---

## 2. Posição na sequência de conexão do chatd

Os números dos passos são os da seção 2.2 do relatório Noise. Fonte: `C37031dS.A0G`, `C37151de`, `C37061dV`.

| Condição | Efeito |
|----------|--------|
| Endereço de debug definido | somente o passo 1 |
| Proxy do usuário válido (habilitado, host válido, flag **2784**) | o passo 0 vai para 12, que é terminal; configuração Psiphon ignorada |
| Sem proxy do usuário, configuração Psiphon presente (`C37061dV.A00 != null`) | os passos 5, 8, 13 são mantidos; 6, 7, 9, 10, 11, 14, 15 são pulados (`ConnectionThread/Skipping sequence N due to active proxy`); 2, 3, 4 são pulados a menos que a flag **23630** esteja ativa |
| Sem proxy do usuário, sem configuração Psiphon | escada inalterada: 2, 3, 4, 5, 8, 9, [15], 13, 14, 6, 10, 7, 11 |

A tabela de skip é o packed switch no bytecode de `C37031dS.A0G` (passos 2 a 15 mapeados para manter / pular / depende de flag). O passo 8 constrói sua configuração a partir de um literal de IP sem a configuração de proxy; portanto, em uma execução com proxy ativo ele é mantido, mas presumivelmente conecta diretamente (inferred). Os passos 5 e 13 resolvem via `C37151de.A03`: com configuração Psiphon e sem proxy do usuário, a configuração de socket retornada carrega o `ProxyServiceConfig` (`C46661vS`) e um nome de host não resolvido, de modo que o DNS acontece na saída do túnel (`DNSResolutionMethod` 7 `SOCKS_PROXY`, código interno 8 em `C37181dh`).

Ordem do passo 0 quando não existe endereço de debug (found; o branch Java decompilado do passo 1 parece invertido, o bytecode confirma): proxy do usuário, depois entradas de override fornecidas pelo servidor (2), depois a string de host configurada (3), depois 5.

---

## 3. WhatsApp Proxy (configurado pelo usuário)

### 3.1 Entrada nas configurações e telas (found)

| Tela | Classe | Conteúdo |
|------|--------|----------|
| Configurações > Armazenamento e dados > Proxy | `SettingsUserProxyActivity` (manifest `com.whatsapp.settings.ui.proxy.*`, não exportada) | switch `Use proxy`, linha do host, linhas de status de chat e mídia, item de menu de compartilhamento, texto informativo (`Only use a proxy if you're unable to connect to WhatsApp. Your IP address may be visible to the proxy provider…`, link `whatsapp-proxy`) |
| Configurar proxy | `SettingsSetupUserProxyActivity` | entrada do host, `Ports (Optional)` com `Chat port` (padrão exibido como `Default` para 443), `Media port` (`Default` para 587), `Use TLS`, botão salvar |
| Entrada na busca das configurações | `C23869ARc` subclasse `C215199Jq` | chave `proxy` |
| Excluir | clique longo na linha do host (`ViewOnLongClickListenerC46012K9h`, `Delete Proxy?`), ação em `KZA` | limpa o host, redefine a porta de mídia 587 e TLS true, status 0, `proxy_enabled` false |

Validação: `K09.A01` (literal de IP), `K09.A02` (host com `:port` opcional, regex construída a partir de `JRQ.A02`); erros `Enter a valid host`, `Enter a valid port`. O parsing de IPv6 existe em `K09.A00`.

### 3.2 Armazenamento (found, `C12660bX`, `C12690ba`)

Arquivo SharedPreferences `user_proxy_setting_pref`.

| Chave | Tipo | Padrão | Uso |
|-------|------|--------|-----|
| `proxy_enabled` | bool | false | estado do switch; efetivo somente quando a flag **2784** está ativa (`C12690ba.A03`) |
| `proxy_ip_address` | string | nenhum | `host:chatPort` (`ProxySetting.A04`); porta extraída na leitura, padrão 443 |
| `proxy_media_port` | int | 587 | porta do relay de mídia |
| `proxy_use_tls` | bool | true | wrapper TLS para o socket de chat |
| `proxy_connection_status` | int | 0 | status do chat exibido na UI (seção 3.5) |
| `proxy_media_connection_status` | int | 0 | status da mídia exibido na UI |

`ProxySetting` (`C45598Jv6`) = `domain`, `ip`, `chatPort`, `mediaPort`, `useChatTls`; um host que é literal de IP vai para `ip`, caso contrário para `domain`. `C12660bX.A03()` o retorna somente quando habilitado, com a flag **2784** ativa e host ou IP válido; este é o objeto que a sequência de conexão recebe.

### 3.3 Link de compartilhamento e importação (found)

Compartilhar: o item de menu constrói `https://wa.me/proxy?host=<host>&chatPort=<n>&mediaPort=<n>&chatTLS=<true|false>` com assunto `WhatsApp Proxy` e texto `Connect to WhatsApp using proxy. <url>`.

Importar: `DeepLinkActivity` (tipo `DEEP_LINK_PROXY`, prefixo de log `PROXY:`) exige a flag **2784**, tem um motivo de rejeição `proxy_has_segments` (condição inferida pelo nome) e então inicia `SettingsSetupUserProxyActivity` com os extras `intent_host_name`, `intent_chat_port`, `intent_media_port`, `intent_use_tls`, `source=deeplink`.

| Query | Parse | Padrão |
|-------|-------|--------|
| `host` | string | nenhum |
| `chatPort` | int | 443 |
| `mediaPort` | int | 587 |
| `chatTLS` | ausente, `true` ou `1` resulta em true; qualquer outro valor, false | true |

A importação apenas pré-preenche a tela de configuração; salvar ainda exige o usuário (found). O handler de `DeepLinkActivity` foi lido a partir do bytecode (não é decompilado para Java).

### 3.4 Uso pelo chatd (found)

Passo 12 (`C37151de.A02` case 12): host = `domain` ou `ip`, porta = `chatPort`, bit TLS = `useChatTls`. O host passa pela cadeia normal de resolvers (seção 6). O handshake Noise então roda sobre esse socket (dentro de TLS quando `useChatTls`). Salvar o proxy ou alternar o switch chama `C11380Yq.A0C(...)` (reconexão forçada) e dispara `wam_user_proxy_set`.

O que o host do proxy faz com o stream não é visível no lado do cliente. Um relay WhatsApp Proxy que encaminha bytes brutos do chatd é inferred a partir da ausência de qualquer troca SOCKS ou CONNECT.

### 3.5 Outros consumidores (found)

| Consumidor | Comportamento |
|------------|---------------|
| Upload / download de mídia | a flag **4073** faz a authority de mídia ser `proxy-host:mediaPort`; health check em [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) |
| Rotas de upload WAM | o callback nativo `jnidispatchO(0)` retorna `https://<proxy-host>:<mediaPort>/deidentified_telemetry` quando a flag **4074** está ativa, mais os hosts de `media_conn` quando a flag **4020** está ativa (ver [WA_WAM_ANALYTICS.md](WA_WAM_ANALYTICS.md)) |
| UI de status | `C42103IXl.A00`: 1 `Connecting…`, 2 `Connected`, 3 `Couldn't connect to proxy`, 4 `Disconnected`, 5 `No network`, outro `Not Set`; status do chat alimentado pelo observer de conexão `C28890Cgr` |
| Rotas HTTP e Tigon do Psiphon | desabilitadas enquanto existe um proxy do usuário (`C17420jn.A01`, `C12790bk`: `User proxy is set, skipping`) |
| Telemetria | `WamUserProxySet {connectionSuccess, proxySet}` (`C43286IuN`) enviado quando o status passa a 2 (true) ou 3 / 4 (false) e nas mudanças de proxy |

---

## 4. Serviço de proxy (Psiphon)

### 4.1 Módulo e biblioteca (found)

| Item | Valor |
|------|-------|
| Entrega | módulo Voltron `proxyservice` mais splits por ABI `proxyservice.config.{arm64_v8a,armeabi_v7a,x86,x86_64}` em `assets/app_modules.json`; o manifest do módulo lista `assets/proxyservice/libs.txt`, `assets/proxyservice/voltron_meta_embedded_server_entries` e `lib/<abi>/libgojni.so` por split |
| Lado Java | `ca.psiphon.PsiphonTunnel` (biblioteca upstream, `loadLibrary("gojni")`, `Psi.start`, `importPushPayload`), service host `S6G` / `C42448IfJ`, orquestrador `C12760bh`, loader do módulo `C46743KbZ` |
| Modo | proxy HTTP e SOCKS local em `localhost`; sem `VpnService` |
| Carga da biblioteca | libs de split APK acrescentadas às fontes do SoLoader (`proxy_service/Added module SoSource`); a string de log nomeia `libproxyservice.so`, embora o manifest do módulo tenha apenas `libgojni.so` |

`libgojni.so` não está presente no APK (entregue com o módulo). Seus internos (conjunto de protocolos, discagem, como `AdditionalParameters` é usado) são unknown.

### 4.2 Recurso de configuração `res/raw/proxyservice_config.json` (found)

Inalterado desde a 2.26.34.4. Lido por `C42448IfJ.getPsiphonConfig`; o placeholder de formato `ClientVersion` é preenchido com o versionCode do app (`264100600`).

| Campo | Valor / uso |
|-------|-------------|
| `SponsorId`, `PropagationChannelId`, `ClientPlatform` | ids opacos de 16 hex; plataforma `meta` |
| `ServerEntrySignaturePublicKey`, `PushPayloadSignaturePublicKey`, `RemoteServerListSignaturePublicKey` | chaves base64 de 32 bytes, 32 bytes e 548 bytes (tamanho de RSA); papel de verificação inferido pelos nomes |
| `AdditionalParameters` | 5300 caracteres base64 (3975 bytes), opaco, não decodificado |
| `Emit*` (endereço do cliente, avisos de diagnóstico, parâmetros de rede), `DisableServerEntriesReporter` | todos true; alimentam `onClientAddress`, `onDiagnosticMessage` |
| `ConnectionWorkerPoolSize`, `EstablishTunnelTimeoutSeconds` | 30, 0 |
| `TransformHostNameProbability`, `TLSFragmentClientHelloProbability` | 0.9, 0.5 (parâmetros anti-DPI para o engine nativo; efeito inferido pelos nomes) |
| `EnableLightProxy`, `LightProxyLimitDestinationAddresses` | true; `g.whatsapp.net` e `g-fallback.whatsapp.net` nas portas 80, 443, 5222 |

Mudanças em runtime: um objeto JSON da flag **23879** (fonte de flags pré-login) ou **23846** (fonte regular) é mesclado chave por chave sobre o arquivo. O modo de importação PSL (`C42448IfJ.A03`) força `DisableTunnels=true`, `EnableLightProxy=false`. As entradas de servidor embutidas são lidas de `assets/proxyservice/voltron_meta_embedded_server_entries` (ou do zip do módulo) quando a flag **23730** / **23731** está ativa; formato: int32 big-endian com a contagem, depois contagem vezes (int32 de comprimento, bytes), cada entrada codificada em hex, uma por linha (`C45480Jst.A01`).

As duas fontes de flags são escolhidas por `C17280jY.A00`: nenhuma conta logada, ou AB props nunca atualizadas, seleciona o conjunto pré-login. O serviço foi portanto projetado para funcionar também antes do registro (inferred a partir do predicado).

### 4.3 Máquina de estados (found, `AbstractC17380jj`, `C12760bh.A0B`)

| Código | Estado | Definido quando |
|--------|--------|-----------------|
| 0 / 1 / 2 | `uninitialized` / `not_in_region_allowlist` / `initializing` | inicial / região rejeitada (o motivo carrega a região) / início aceito |
| 3 / 4 | `disabled` / `downloading_module` | gate como `vpn_in_use` / download Voltron em andamento |
| 5 / 6 / 7 | `connecting` / `connected` / `disconnected` | `onConnecting` / `BmZ` (portas prontas) / `BpU` |
| 8 / 9 | `download_failed` / `library_load_failed` | falha de instalação do módulo / `UnsatisfiedLinkError` |
| 10 | `shutdown` | `A04(reason)`, por exemplo `country_check`, `has_external_connectivity` |

Enquanto o estado é 2, 4 ou 5, a pilha HTTP espera o proxy: `C17420jn.A05(true)` arma um latch cujo timeout é a flag **29362** (ms, padrão 0, somente quando logado).

### 4.4 Gatilhos de início e parada (found)

| Gatilho | Caminho |
|---------|---------|
| Cold start do message handler | o caso default de `C1W6` chama `C12760bh.A03(…, null)` |
| Retomada do app | `C18980me`, `C28912ChD` chamam `A0A()` (renotifica o túnel, ou reinicia quando parado) |
| Push de desbloqueio com `psl` | `C28912ChD.BIb`: `A03(…, C46772Kc2(psl))`; sem `psl`, apenas `A0A()` quando `C17280jY.A02()` (flags **28186** / **28189**) |

Gates de início em `A03`:

1. Região do dispositivo = país do SIM, senão país da rede, senão país do locale (`AbstractC16510i9`); deve estar na lista em minúsculas separada por vírgulas da flag **18724** (pré-login) / **18725** (`C17280jY.A03`). Caso contrário, estado 1.
2. Verificação de VPN (`C17280jY.A01`, as flags **24068** / **24067** a contornam): VPN ativa resulta em `vpn_in_use`, estado 3.
3. A flag **25452** decide a ordem: ativa, o gate de VPN e o prober rodam depois do download do módulo; inativa, antes.
4. Prober (flag **18875**, `Q53`): HTTP GET da URL na flag **18871** (timeout **18874**, tentativas **18873**, atraso **18872**) pela pilha normal. Qualquer resposta HTTP conta como sucesso (`KUI.CF3`): `Probe succeeded. Removing proxy from http and tigon`, `A0N` (conectividade externa) definido, proxy removido de HTTP e Tigon, a verificação de shutdown roda.
5. Timeout do marcador de início: flag **25850** segundos (anotação `init_timed_out`).

Condições de parada:

| Condição | Resultado |
|----------|-----------|
| Região do cliente reportada pelo Psiphon não permitida (flag **19067** ativa) | `country_check`, shutdown |
| Prober bem-sucedido (`A0N`) e uma boa sessão direta do chatd reportada (`A0O`), flag **19613** ativa | `has_external_connectivity`, shutdown |
| Boa sessão direta do chatd (`HandlerThreadC12340b0.A0e`: serviço ativo, sessão mais longa que a flag **19372** (padrão 5, unidade não resolvida), rota diferente de `SOCKS_PROXY`) | `C12760bh.A09()` mais `C37061dV.A00()`: serviço de proxy ignorado durante o tempo de vida do processo (`good_direct_chatd_session`) |
| Flag **19144** negativa no início | ignorado durante o tempo de vida do processo (`abprop_config`) |

### 4.5 Integração com o chatd (found)

`C37061dV` (`ConnectionProxyConfig`) transforma o estado do broadcaster no `ProxyServiceConfig` que a sequência usa.

| Campo | Fonte |
|-------|-------|
| `address` | `localhost` quando o túnel pesado ou o proxy leve está ativo, senão vazio |
| `port` | porta SOCKS (`ProxyServiceBroadcaster.A01(true)`: pesado, ou leve quando permitido) |
| `proxyServiceClientIP` | `onClientAddress` |
| `httpProxyHost`, `httpProxyPort` | `localhost` e a porta HTTP quando diferente de zero |
| `isLightProxy` | `isLightProxy()` (proxy leve ativo, túnel pesado não conectado) |

Regras:

- A configuração é descartada quando address ou port está vazio (`updateProxyServiceConfig`), ou quando a região reportada pelo Psiphon não é permitida (`dropping due to unsupported client region`).
- `C37061dV.A02` (chamado a cada início de conexão) retorna a configuração somente quando a região do dispositivo é permitida, nenhuma VPN está ativa, o serviço não está em shutdown e o ignore de tempo de vida do processo não está definido. Quando a flag **24645** está ativa, a configuração em cache é usada sem essas verificações.
- A thread de conexão pode bloquear por flag **19144** ms (`awaitProxyServiceConfig`) esperando a configuração antes do passo 5 quando ainda não existe configuração.
- Uma configuração alterada define o reset flag e, quando a flag **36306** está ativa, reconecta com o motivo `proxy_service_update`.

Socket (`C37031dS.A01` else-branch, classe `C48201yM` = `ConnectionSocketTunnel`):

```java
Socket s = new Socket(new Proxy(Proxy.Type.SOCKS, new InetSocketAddress(cfg.address, cfg.port)));
s.connect(InetSocketAddress.createUnresolved(host, port), 30000);   // g.whatsapp.net / g-fallback.whatsapp.net
c37861f7.A00(out, cfg.proxyServiceClientIP, port);                    // PROXY v2 header, skipped when flag 26334 is on
```

Cabeçalho PROXY v2 (`C37861f7`, log `ProxyHeaderWriter`): assinatura de 12 bytes `0D 0A 0D 0A 00 0D 0A 51 55 49 54 0A`, `21`, família `11` (IPv4) ou `21` (IPv6), comprimento de 16 bits, endereço de origem (o IP do cliente, endereço zero quando não é parseável), endereço de destino zero, porta de origem 0, porta de destino = porta alvo, depois um TLV `E8 00 01 50`. O significado do TLV é unknown. Se o edge aceita ou exige o cabeçalho é inferred apenas pela sua presença.

Os registros de timing da conexão por tentativa usam os estágios `DNS`, `SOCKET`, `TLS` e as pilhas `PLATFORM`, `MNS`, `SOCKS_PROXY` (`C37811f2`, `EnumC37801f1`, `EnumC37821f3`).

### 4.6 Outros consumidores do proxy local (found)

| Consumidor | Classe | Comportamento |
|------------|--------|---------------|
| Pilha HTTP do WA | `C17420jn` (`WaHttpUrlConnectionWithProxyService`) | `Proxy(HTTP, localhost:httpPort)`; para hosts terminados em `.whatsapp.net`, `.whatsapp.com`, `.fbcdn.net`, `.facebook.com`, `.instagram.com`, `.cdninstagram.com`, `.fbsbx.com` adiciona `X-Forwarded-For: <client IP>` e `using-wa-proxy-service: 1` |
| Clientes Tigon (MNS) | `C12790bk` (`WATigonProxyObserver`) | `setInAppProxyHostAndPort`; pulado quando as flags **26734** / **26735** (Tigon) ou **19905** / **19906** (proxy WA) estão ativas, existe um proxy do usuário, `http.proxyHost` / `https.proxyHost` está definido, ou o probe já teve sucesso |
| VoIP | `CQO`, `JNIUtils.socksProxyPort` | `Voip.updateProxy(socksPort)` quando a flag **34525** permite (segundo gate **36980** em `Buh()`) |
| WebView | `C39826HXw` | regra `PROXY_OVERRIDE` para os domínios da flag **25539** |
| Log de informações de rede | `C12500bH` | `network_info_socks_proxy_active[...]`, `socks_proxy_connected` / `socks_proxy_disconnected` |

O Tigon também lê por conta própria as propriedades de proxy do sistema (`TigonHttpClientBase.setSystemProxyHostAndPort`) com uma chave de fallback direto; isso é independente do serviço.

### 4.7 Diagnósticos (found)

`C42448IfJ.onDiagnosticMessage` faz o parse de `ConnectedServer:{json}` em `candidate_number`, `protocol`, `client_replay_type` (`bootstrap`, `replay`, `non-replay`), `server_entry_source`. Marcadores 79499422 (início), 79496324 (conexão), 79501264 (prober, anotado com `has_vpn`, `has_system_http_proxy`).

---

## 5. Endpoints de fallback e push de desbloqueio

### 5.1 `<ib><fbip>` (found, `C40581l4`, `C36821d6.A02`)

`<ib><fbip>text</fbip></ib>`: o texto é dividido por `,`. Uma única entrada `CLEAR` exclui o arquivo. Cada entrada tem seis campos separados por `|`:

```
ip|port|ts|ttl|secure|override       exp = (ts + ttl) * 1000
```

| Campo | Uso |
|-------|-----|
| `ip`, `port` | endpoint; código de resolver 4 (`FALLBACK`) |
| `ts`, `ttl` | expiração em ms; entradas expiradas são removidas no carregamento |
| `secure` | bit de wrapper TLS para o endpoint |
| `override` | entradas true vão para o passo 2 (tentadas antes de `g.whatsapp.net`), entradas false para o passo 8 (depois de `:80`) |

Persistência: arquivo `fbips` no diretório de arquivos do app, JSON `{"fbips":[{"ip","port","exp","secure","override","resolver"}]}` (`C36821d6.A00`). Erros de carregamento são reportados como `fallback-manager/load-error`, `save-error`.

### 5.2 Tabela fixa (found)

`AbstractC47101wK`: 18 nomes de host (`e1` a `e16`, `g`, `v` sob `.whatsapp.net`, formas simples e com ponto final), cada um com vários endereços IPv4. Usada pelos passos 6 / 10 e pelo resolver fixo. A entrada `v.whatsapp.net` não é usada por nenhum resolver neste build (seu stub de resolver retorna null).

### 5.3 Push de desbloqueio (found)

Parsing do push (`CLl`, `PushPayloadParser/fromJSON`): valores de `nt` `pre_reg`, `post_reg`, `voip_call_offer_1on1`, `voip_call_offer_group`, `call_terminate`, `message`, `group_message`, `wfac_ban`, `unblocking`. Transportes registrados em log: `ADM`, `GCM`, `FBNS`. O payload é decifrado (`PushEncryptionHelper`, campos `payload`, `IV`, `tag`, chave de `push:push_pkey_data`; cifra inferred como AES-GCM pelos nomes dos campos).

`nt` = `unblocking` carrega (`UnblockingPushPayload`, `BQY`):

| Chave JSON | Campo | Tratamento |
|------------|-------|------------|
| `fbips` | `fbips` | dividido por `,`, passado para `C36821d6.A02` (mesmo formato de 5.1) |
| `unblocking_props` | `unblockingProps` | `version\|a\|b`; version acima de 0 é ignorada; dois mapas `id=value;id=value` parseados por `C27946CBo.A00`; `processPreChatdProps` aplica pares `config_code` / `config_value`, `processPostChatdProps` o segundo mapa (atribuição dos mapas às fases parcialmente inferred) |
| `psl` | `proxyServerList` | base64, importado no Psiphon com `importPushPayload` (`C46772Kc2`) |

Importação de `psl`: túnel ativo, importado diretamente; túnel inativo, um objeto de túnel temporário inicia em modo de importação PSL (`DisableTunnels`), importa, para (`Cold-importing push payload`). Ignorado quando o estado é `not_in_region_allowlist`. A expansão de PSL como "push server list" é inferred a partir da chave e do campo `PushPayloadSignaturePublicKey`.

---

## 6. Cadeia de fallback de DNS (found)

`C36881dC.A03` primeiro consulta um cache (alimentado por `fbips`, entradas com expiração; controlado por uma flag), depois percorre quatro resolvers em ordem:

| # | Resolver | Código do resolver | Notas |
|---|----------|--------------------|-------|
| 0 | stub para `v.whatsapp.net` | nenhum | retorna null |
| 1 | DNS da plataforma / MNS (`DnsCache/resolveViaMnsDns`) | 5 / 6 / 7 | tenta uma vez mais (`primary dns resolver failed, retrying...`) |
| 2 | secundário: DNS UDP construído à mão para 8.8.8.8 e 8.8.4.4 porta 53 (`QG1`) | 1 `GOOGLE` | UDP simples, sem DoH nem DoT |
| 3 | tabela fixa | 2 `HARDCODED` | `no hardcoded ips found for <host>` quando ausente |

A flag **13545** (string) mascara resolvers: `secondary` desliga o fixo, `hardcoded` desliga o resolver UDP, `none` desliga ambos (lógica de bits em `C37151de.A01`). Erros `EPERM` são relançados quando uma chave controlada por flag está definida. Os códigos de resolver chegam a `ClientPayload.dnsSource` (seção 6.5 do relatório Noise).

---

## 7. Relay de registro (found)

Escopo: HTTP de registro (`RegistrationHttpManager` = `K49`, `KotlinRegistrationBridge`, `RetryingHttpClient`) para `https://v.whatsapp.net`. Não toca o chatd.

### 7.1 Lista de provedores

Recurso `res/raw/domain_fronting_providers.tsv`, colunas `name`, `url template`, `host`:

| Nome | Template | Host |
|------|----------|------|
| `amazon` | `https://y9yrsygcg6.execute-api.us-east-1.amazonaws.com/s/s?_={PATH}&{QS}` | `y9yrsygcg6.execute-api.us-east-1.amazonaws.com` |
| `google` | `https://us-central1-propane-fusion-170222.cloudfunctions.net/s?_={PATH}&{QS}` | `us-central1-propane-fusion-170222.cloudfunctions.net` |

`C45421Jrl` o carrega (linhas com menos de 3 tokens registram `domain-fronting-providers/load/bad-line`) e mantém três listas: alcançáveis (`A05`), não testados (`A06`), inalcançáveis (`A04`). `K49.A0K` as entrega a cada chamada de registro nessa ordem.

### 7.2 Probe

`EULA.onCreate` inicia o probe no máximo a cada 900000 ms (pulado quando `C06810Gk(930).A07()`, significado não resolvido): abre `https://v.whatsapp.net`; em `IOException` (`DomainFrontingManager/probe-regd/cant connect to regd`) embaralha os provedores e faz GET em cada template com `{PATH}=/` e `{QS}` vazio, timeout de conexão e leitura de 60 s, headers `Host` = host do provedor e o user agent do app. HTTP 200 move um provedor para a lista de alcançáveis, qualquer falha para a de inalcançáveis (`domainFrontingProvider/cant reach`).

### 7.3 Estratégias de tentativa (`RetryingHttpClient`, `C44407JaE`, `C44975Jk4`)

| Estratégia | Requisição | Estado na 2.26.41.6 |
|------------|------------|---------------------|
| `ORIGINAL` | URL normal | sempre a tentativa 1 |
| `HOST` | mesma URL com um IP dado | a lista está vazia neste build |
| `PROXY` | via um IP de proxy dado | a lista está vazia neste build |
| `DOMAIN_FRONTING` | template com `{PATH}` e `{QS}` substituídos pelo path original e query bruta; headers `Host` = host do provedor, `X-Forwarded-Host` = host original | até o tamanho da lista de provedores |

Ordem: ORIGINAL, entradas HOST, entradas PROXY, provedores; no máximo 4 tentativas. O host da URL e o header `Host` são iguais em ambos os templates, portanto isto é um relay por cloud function (requisição encaminhada pelo provedor para `X-Forwarded-Host`, inferred) e não SNI / Host fronting clássico.

Regra de nova tentativa: os códigos de resultado 2, 5, 7, 12 não são repetíveis (`non-retryable error`), qualquer outra falha continua (`failed attempt N ... reason`); os significados dos códigos não estão resolvidos. Atraso antes da tentativa `n` > 1:

```
delay = clamp(r * (n*n - 1) * 4 * 1000, 0, 60000) ms      // r from a random double, assumed uniform in [0,1)
```

`RetryingHttpClient/executePostWithRetry/applying backoff`, `all retries exhausted`. As flags de payload de attestation de endpoint por path estão em `AbstractC44143JQf` e não têm relação com relay.

---

## 8. Tigon e DGW

| Item | Estado | Tier |
|------|--------|------|
| Tigon HTTP (`TigonHttpClient`, clientes MNS) | cliente HTTP(S); recebe o proxy HTTP do Psiphon e as propriedades de proxy do sistema (seção 4.6); não é um transporte do chatd | found |
| Cliente DGW (`AbstractC20460pC`) | construído com o domínio `gateway.facebook.com`, configuração de fallback `null`, configuração de personalização `null` | found |
| `DGWFallbackConfig` | `isFallbackEnabled`, `fallbackDomain`, `numFailuresForFallback`, `fallbackReasons`, `isHardcodedIpFallbackEnabled`; null resulta em tudo desligado; o builder Java nunca o habilita, padrões nativos unknown | found / unknown |
| Usuários do DGW | somente `WaFalcoStreamingRegistration` (streaming de telemetria); ver seção 13 do relatório Noise | found |

As strings nativas (`distribgw_tigon_tunnel`, `DGW_MQTTBYPASS`, rótulos de throttling e zero-rating) descrevem os internos do DGW. Nada liga o DGW à recuperação de um chatd bloqueado (inferred a partir da ausência).

---

## 9. Rastreamento de estado da conexão e diagnósticos

| Item | Onde | Conteúdo |
|------|------|----------|
| Persistência da sequência | prefs `connection_sequence_state`, `connection_sequence_attempts`, `last_successful_connection_step`, `_host`, `_port` | ponto de retomada, passo HISTORY (relatório Noise 2.2) |
| Registros por tentativa | `C37811f2` | estágio `DNS` / `SOCKET` / `TLS`, pilha `PLATFORM` / `MNS` / `SOCKS_PROXY`, timing, erro |
| Payload | `ClientPayload.dnsSource`, `connectAttemptCount` | resolver ou rota que produziu o socket |
| Serviço de proxy | `C12760bh.A06()`, `A08()` | código de estado (4.3); `A08()` retorna `both`, `heavy`, `light` ou null |
| Proxy do usuário | status de `user_proxy_setting_pref`, `wam_user_proxy_set` | UI e analytics |
| Log de informações de rede | `C12500bH` | `network_info_is_vpn`, `_is_airplane`, `_is_data_saver`, `_is_cellular_enabled`, `_socks_proxy_active`, `socks_proxy_connected` / `_disconnected` |
| Tags de log | `proxy_service/`, `ConnectionProxyConfig/`, `WaConnectivityProber/`, `WATigonProxyObserver/`, `ConnectionThread/Skipping sequence` | gates e mudanças de estado |

---

## 10. Interação entre nova tentativa e backoff

O backoff em si (unidades Fibonacci, limite de 15 minutos, alarmes) está na seção 10 do relatório Noise. Este recurso acrescenta:

| Interação | Efeito |
|-----------|--------|
| Proxy do usuário salvo, alternado, excluído | reconexão forçada (`C11380Yq.A0C(...)`) |
| Mudanças na configuração do serviço de proxy | reset da sequência; reconexão `proxy_service_update` quando a flag **36306** está ativa |
| Proxy do usuário definido | sequência de um passo; toda tentativa falha retorna ao backoff de conexão completa |
| Espera de configuração / espera de HTTP | a thread de conexão bloqueia até flag **19144** ms antes do passo 5; a pilha HTTP até flag **29362** ms enquanto o serviço inicia |
| Registro | limite próprio de 4 tentativas e atraso quadrático (seção 7.3), não compartilhado com o chatd |

---

## 11. Feature flags (ids como lidos no código; os valores são do lado do servidor)

| Id | Tipo | Controla |
|----|------|----------|
| **2784** | bool | recurso de proxy do usuário (estado habilitado, deep link) |
| **4020**, **4073**, **4074** | bool | hosts de media_conn para o nativo; mídia via proxy do usuário; rota de telemetria via proxy do usuário |
| **18875** | bool | prober de conectividade |
| **18871**-**18874** | string, ints | URL do probe, atraso, tentativas, timeout |
| **18724**, **18725** | string | regiões permitidas (fonte pré-login / regular) |
| **19067** | bool | nova verificação de região ao conectar |
| **19613** | bool | shutdown ao haver conectividade externa |
| **19144** | int | espera de configuração em ms; negativo ignora o serviço no processo |
| **19372** | int | limiar de boa sessão (padrão 5) |
| **19905**, **19906**, **26734**, **26735** | bool | desabilitam o proxy WA para HTTP / Tigon (pré-login / regular) |
| **23630** | bool | passos 2-4 permitidos sob proxy (declarada ativa por padrão, inferred) |
| **23730**, **23731** | bool | entradas de servidor embutidas (pré-login / regular) |
| **23846**, **23879** | JSON | override da configuração Psiphon (regular / pré-login) |
| **24067**, **24068** | bool | permitem o serviço enquanto uma VPN está ativa |
| **24645** | bool | usa a configuração do serviço em cache sem gates |
| **25452** | bool | ordem do gate de VPN e do prober em relação ao download do módulo |
| **25539** | string | allowlist de domínios de proxy do WebView |
| **25850** | int | timeout do marcador de início em segundos |
| **26334** | bool | pula o cabeçalho PROXY v2 |
| **28186**, **28189** | bool | retomam o serviço em push sem `psl` |
| **29362** | int | espera do HTTP pelo proxy em ms |
| **34525**, **36980** | bool | passam a porta SOCKS ao VoIP |
| **36306** | bool | reconectar na atualização do serviço de proxy |
| **13545** | string | máscara de resolvers de DNS |

As flags da escada do chatd e de keepalive (**20801**, **22916**, **30712**, **33512**, **7831**-**7834**, **15103**) estão na seção 12 do relatório Noise.

---

## 12. Baileys (`baron-baileys-v2`, verificado contra seu código-fonte)

| Aspecto | Baileys | Android 2.26.41.6 |
|---------|---------|-------------------|
| Transporte | WebSocket `ws` para `wss://web.whatsapp.com/ws/chat` (`waWebSocketUrl`) | TCP Noise bruto |
| Proxy | `config.agent` passado a `new WebSocket(url, { agent })`; uploads usam `fetchAgent` | relay WhatsApp Proxy, túnel Psiphon |
| Hosts de fallback | uma URL configurável | escada de `g`, `g-fallback`, `eN`, portas 443 / 5222 / 80 |
| `<ib><fbip>`, push de desbloqueio | não tratados | tratados |

```ts
const sock = makeWASocket({ agent: new SocksProxyAgent(proxyUrl), fetchAgent: new SocksProxyAgent(proxyUrl) })
```

| Por que falha | Causa | Correção |
|---------------|-------|----------|
| Um host de WhatsApp Proxy do Android rejeita o Baileys | o relay fala TCP Noise bruto na porta de chat (inferred); o Baileys envia um upgrade WebSocket | usar um proxy HTTP ou SOCKS que alcance `web.whatsapp.com` |
| Sem recuperação após um bloqueio | sem tratamento de `fbip`, sem canal de push | fornecer um novo `agent` ou URL |

---

## 13. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|----------|
| `Couldn't connect to proxy` | host do proxy do usuário inalcançável ou configuração TLS errada | verificar host, `Chat port`, `Use TLS`; a sequência não tem fallback direto |
| `Enter a valid host` / `Enter a valid port` | validação em `K09` | corrigir a entrada |
| O link de proxy não faz nada | flag **2784** desativada, ou segmentos de path extras (`proxy_has_segments`) | nada no lado do cliente |
| `proxy_service/Proxy service detected user region not in region allowlist.` | região reportada pelo Psiphon rejeitada pela lista da flag **18724** / **18725** | nada no lado do cliente |
| Estado `disabled`, motivo `vpn_in_use` | VPN ativa, flags **24067** / **24068** desativadas | desativar a VPN ou a flag |
| `RetryingHttpClient/executePostWithRetry/all retries exhausted` | todas as tentativas falharam | aguardar; o limite é 4 |

---

## 14. Distinções importantes

| Não confundir | Detalhe |
|---------------|---------|
| Proxy do usuário vs serviço de proxy | proxy do usuário = host escolhido, passo 12, terminal, link de compartilhamento; serviço de proxy = túnel SOCKS Psiphon controlado pelo servidor para os passos 5 e 13; um exclui o outro |
| `C48201yM` vs passo 12 | `C48201yM` é o socket de túnel SOCKS do serviço de proxy; o passo 12 é o proxy do usuário e usa um socket simples ou TLS |
| Proxy leve vs túnel pesado | o proxy leve é limitado aos seis destinos `g` / `g-fallback` listados; o túnel pesado é a sessão Psiphon completa |
| `fbip` vs push `fbips` vs `fallback_*` | `<ib><fbip>` e o push `fbips` fornecem IPs de fallback do chatd; `fallback_hostname` / `fallback_ip*` são atributos de `media_conn` (seção 16 do relatório Noise) |
| Relay de registro vs chatd | a lista de provedores nunca alimenta a sequência de chat |
| WhatsApp Proxy vs proxy do sistema | o proxy do sistema não é lido para o chatd |

---

## 15. Fluxo completo

```
[Operator]  push nt=unblocking {fbips, unblocking_props, psl}   or   <ib><fbip>...</fbip></ib>
     │  fbips file updated ; props applied ; psl imported (temporary tunnel if inactive)
     ▼
[Client]  C12760bh gates: region (SIM > network > locale), no VPN, flags ; Voltron proxyservice download
     │  PsiphonTunnel.startTunneling(embedded entries) ─► localhost SOCKS + HTTP ports ─► state 6
     ▼
[ProxyServiceBroadcaster]  C37061dV builds ProxyServiceConfig ─► sequence reset ("proxy_service_update")
     │
     ├── user proxy set ─► step 12 only: host:chatPort (+TLS) ─► Noise ─► end (no direct fallback)
     ▼
[ConnectionThread]  steps 5, 13 (2-4 if flag 23630) ─► SOCKS CONNECT g / g-fallback (unresolved host)
     │  PROXY v2 header (client IP) ─► Noise handshake (Noise report section 4)
     ▼
[Server]  login success; session > threshold and route != SOCKS_PROXY ─► proxy ignored for the process
     ▼
[Failure]  timeout / socket error ─► next step ─► exhausted ─► Fibonacci backoff (Noise report section 10)

[Registration]  v.whatsapp.net ─► ORIGINAL ─► relay providers (Host + X-Forwarded-Host) ─► <= 4 attempts
```

---

## 16. Unknowns

| Item | Status |
|------|--------|
| Qualquer comportamento na rede (túnel, aceitação de PROXY v2, resposta do relay, encaminhamento do WhatsApp Proxy) | nada capturado; nenhum item é `tested` |
| Internos de `libgojni.so`, protocolos, `AdditionalParameters`, conteúdo das entradas embutidas | módulo nativo não está no APK |
| Conteúdo da lista de regiões permitidas, URL do probe, todos os valores de flags | do lado do servidor |
| Significado do TLV `E8 00 01 50` no cabeçalho PROXY v2 | unknown |
| Mapeamento dos dois mapas de `unblocking_props` para as fases pré e pós chatd, cifra do push | parcialmente inferred |
| Unidade da flag **19372**, significado dos códigos na nova tentativa de registro (2, 5, 7, 12), predicado por trás de `C06810Gk(930).A07()` | não resolvido |
| Roteamento de entrada de `wa.me/proxy` antes de `DeepLinkActivity` (os filtros do manifest cobrem `wa.me`) | não rastreado além da activity |
| Se a configuração de fallback do DGW no lado Java permanece desligada no nativo, e qualquer fallback somente nativo | unknown |
| Comportamento das entradas do passo 8 dentro de uma execução com Psiphon ativo | inferred direto |
