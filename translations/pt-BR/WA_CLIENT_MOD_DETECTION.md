<!-- src-sha1: acf9c9e68ca59b17d45a787d66ae2550607b66cc -->
# WhatsApp Client Mod Detection — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-11-01
**Escopo:** Detecção client-side de clientes Android modificados/não-oficiais (repacks da família GB WhatsApp, módulos de hook Xposed/LSPosed como o WaEnhancer, APKs reassinados) — a única heurística dedicada a mods encontrada (`is_whatsapp_plus_user`), busca por artefatos de hook-frameworks (Xposed/Frida/Substrate), o que o client faz com a telemetria de assinatura/origem-de-instalação/root já catalogada em `WA_CLIENT_INTEGRITY.md`, o tratamento da UI de ban do WFAC para motivos de ban enviados pelo servidor, e a superfície de ataque que um módulo de hook de terceiros (WaEnhancer) é conhecido por atingir dentro do processo host

---

## 1. Visão geral

Este relatório tem escopo em **detecção de mod/tamper**, não em atestação de conta. Keystore attestation, Play Integrity, WASafe, o self-check de assinatura (WAM **6251**) e a flag de origem de instalação (WAM **10255**) estão totalmente documentados em [`WA_CLIENT_INTEGRITY.md`](WA_CLIENT_INTEGRITY.md); este relatório só declara o que eles contribuem para a detecção de mod e não repete seus mecanismos.

| Mecanismo | Detecta | Reportado como | Enforcement encontrado |
|-----------|---------|-------------|--------------------|
| `is_whatsapp_plus_user` (probe reflexivo de classe) | Um client de terceiros que empacota a biblioteca de crash-report ACRA | Campo de telemetria `wam_daily`; string `diagnostic` no contact-us (`nw-wap`) e no debug report (`NW-WAP-1`) | nenhum |
| Self-check de assinatura do app (`AbstractC38241gg` / `C27965CCj`) — ver relatório de integridade §5 | APK reassinado/repackaged (certificado de assinatura ≠ valor embutido do WhatsApp) | Atributo comum WAM **6251** | nenhum |
| Flag de origem de instalação (`CHH`) — ver relatório de integridade §5.4 | Instalação via sideload / não-Play | WAM **10255**, `install_source_official` | apenas roteamento de download de módulo, sem gate |
| Flags de root / emulador / custom-ROM (`C00L`, `Cdt`) — ver relatório de integridade §6 | Dispositivo com root ou emulado (um facilitador comum, não um sinal de mod em si) | `wam_daily` | nenhum |
| Strings de artefatos de hook-framework (Xposed, Frida, Substrate, LSPosed, TracerPid) | — | — | **não encontrado** nesta build (§3) |
| Checksum próprio de biblioteca nativa / dex | — | — | **não encontrado** nesta build (§3) |
| UI de ban do WFAC (`WfacBanActivity`) | — | exibe `ban_violation_type` / `ban_violation_source` / `ban_violation_reason` enviados pelo servidor | decisão do servidor, opaca para o client (§5) |

Nenhum caminho de código foi encontrado em qualquer lugar do client decompilado que recuse executar, degrade uma feature, ou bloqueie uma ação por causa de qualquer um dos itens acima. Todo mecanismo encontrado é **telemetria**, consistente com a conclusão já alcançada para integridade de conta.

---

## 2. A única heurística dedicada a mods: `is_whatsapp_plus_user`

### 2.1 O que ela verifica

Três sites independentes, cada um executando o **mesmo probe reflexivo** em vez de chamar um helper compartilhado:

```smali
; smali_classes7/X/Cdt.smali, method C4k (fills LX/0Fp; = wam_daily event)
const-string v0, "org.acra.ACRA"
invoke-static {v0}, Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;
; ClassNotFoundException -> false, success -> true
iput-object v0, p1, LX/0Fp;->A0W:Ljava/lang/Boolean;   ; -> wam_daily.is_whatsapp_plus_user
```

```java
// C1Z.java (contact-us diagnostics)
try { Class.forName("org.acra.ACRA"); sbA0m.append("nw-wap "); } catch (ClassNotFoundException unused) {}

// C10V.java (debug report builder)
try { Class.forName("org.acra.ACRA"); sb10.append("NW-WAP-1 "); } catch (ClassNotFoundException unused2) {}
```

| Item | Valor | Tier |
|------|-------|------|
| Verificação | `Class.forName("org.acra.ACRA")` tem sucesso (classe presente no classpath) | found |
| Nome do campo | `is_whatsapp_plus_user` (`LX/0Fp;->A0W`), evento `wam_daily` | found |
| Sinks | telemetria `wam_daily`; string `diagnostic` do contact-us (`nw-wap `); texto do debug-report (`NW-WAP-1 `) | found |
| Racional | ACRA (`org.acra`) é uma biblioteca de crash-reporting de terceiros; o WhatsApp oficial não a empacota. Historicamente empacotada por repacks da família "WhatsApp Plus" para sua própria telemetria de crash (`inferred`: o nome do campo é uma escolha de label do próprio WhatsApp, não um valor lido do mod) | found (probe) / inferred (significado do label) |
| Lacuna de decompilação | `Cdt.java` em si não decompilou (só existe o `CDT.java`, uma classe irmã); a verificação é lida a partir do smali | found |

### 2.2 O que ela NÃO faz

- Nenhuma allowlist/denylist de nomes de pacote de mods (`com.gbwhatsapp`, `com.yowhatsapp`, `com.fmwhatsapp`, `com.wmods.wppenhacer`, …) existe em nenhum lugar do client decompilado — nenhuma dessas strings ocorre em `java_src` ou `smali*`.
- O probe é uma única busca reflexiva de classe, não uma assinatura, hash, ou verificação de comportamento. Um mod que simplesmente não empacota `org.acra.ACRA` (ou faz shade/rename da classe) a derrota trivialmente; este relatório não afirma o contrário.
- Os três sinks são texto de diagnóstico/telemetria e um evento de analytics diário. Nenhum branch lendo `A0W`/`is_whatsapp_plus_user` foi encontrado que altere o comportamento do client.

---

## 3. Busca por artefatos de hook-framework e repack (não encontrados)

Buscado em toda a árvore decompilada (`java_src/`, todos `smali*/`) para 2.26.41.6:

| String(s) de ancoragem | Alvo | Resultado |
|-------------------|--------|--------|
| `Xposed`, `XposedBridge`, `de.robv`, `LSPosed` | Presença do hook framework Xposed/LSPosed | não encontrado |
| `frida`, `Frida`, `re.frida`, `frida-server`, porta `27042` | Servidor de instrumentação Frida | não encontrado (o único hit de substring `frida` está dentro de um literal de regex de public-suffix/TLD, não relacionado) |
| `substrate`, `Substrate` | Hook framework Cydia Substrate | não encontrado |
| `TracerPid` | detecção clássica de tracer via ptrace em `/proc/self/status` | não encontrado |
| `GBWhatsApp`, `gbwhatsapp`, `com.gbwhatsapp`, `FMWhatsApp`, `YoWhatsApp`, `OGWhatsApp`, `com.wmods.wppenhacer` | strings de pacotes de mod-clients nomeados | não encontrado |
| `modded`, `unofficial`, `tampered`, `fake whatsapp`, `clone app` | strings genéricas de prosa/log de detecção de mod | não encontrado |
| usos de `CRC32` (10 hits) | checksum próprio de dex/asset | todos em carregamento multidex (`dextricks`) ou empacotamento de zip de crash-report, nenhum é um self-check de tamper do app |
| `checkSignatures` (3 hits) | comparação de assinatura | todos são verificações de confiança IPC/caller (verificação de caller com mesma assinatura do `FileSharingHelper`, uma verificação de confiança de app companion do Pixel) não relacionadas a detectar um client WhatsApp modificado |
| `isDebuggerConnected` | anti-debug | só no detector de ANR (`SigquitBasedANRDetector`) e helpers de crash, não um gate de tamper (confirma `WA_CLIENT_INTEGRITY.md` §6.4) |
| `/proc/self/status` (4 hits, `KGi`/`KGw`/`KH8`/`KGp`) | — | leitores de estatísticas de memória (provavelmente coleta de `VmRSS` para diagnósticos); nenhuma parsing de `TracerPid` encontrada lá |

**Correção ao enquadramento de uma nota de pesquisa anterior:** uma nota de análise estática anterior descreve o WaEnhancer como "exatamente o tipo de client modded/não-oficial que o sistema de integridade do app oficial tem como alvo", mas não afirma que o app oficial o detecta pelo nome — essa leitura é confirmada aqui: não há código de detecção específico para WaEnhancer, específico para GB, ou específico para Xposed em 2.26.41.6. O único sinal client-side que dispararia para uma instalação do WaEnhancer é o probe genérico de ACRA do `is_whatsapp_plus_user`, e só se o módulo (ou uma dependência empacotada) por acaso embarcar aquela classe — não verificado de nenhuma forma especificamente para o WaEnhancer (`unknown`).

Isso estende `WA_CLIENT_INTEGRITY.md` §6.4, que apontou o CRC de dex/asset como "não buscado exaustivamente" — agora foi buscado e ainda não encontrado.

---

## 4. Consequências server-side visíveis client-side

### 4.1 UI de ban do WFAC

`WfacBanActivity` (`com.whatsapp.waffle.wfac.p191ui`) lê três extras fornecidos pelo servidor e os renderiza; ela não computa um motivo:

```java
int violationType   = getIntent().getIntExtra("ban_violation_type", -1);
String violationReason = getIntent().getStringExtra("ban_violation_reason");
int violationSource  = getIntent().getIntExtra("ban_violation_source", -1);
```

| Item | Tier |
|------|------|
| `ban_violation_type` / `ban_violation_source` são inteiros opacos; nenhum enum que os resolva para causas nomeadas (ex.: "client modificado") foi encontrado client-side | found (absence) |
| `ban_violation_reason` é uma string de texto livre, presumivelmente templated pelo servidor | found |
| Nenhum caminho de código conecta qualquer um dos sinais de detecção de §1–§3 (`is_whatsapp_plus_user`, mismatch de assinatura, root, origem de instalação) a um valor `ban_violation_*` | found (absence) |

A máquina de estados de ban completa, a GraphQL (`BizIntegrityQuery`), os níveis de confiança (trust tiers), e as stanzas XMPP de falha estão em [`WA_BAN_SYSTEM_DEEP_EN.md`](WA_BAN_SYSTEM_DEEP_EN.md); este relatório não repete esse conteúdo. Se o servidor usa qualquer um dos itens de telemetria de §1 (mismatch de assinatura, `is_whatsapp_plus_user`, root) como input de ban é **unknown** — é server-side e não observável estaticamente, mesma conclusão de `WA_CLIENT_INTEGRITY.md` §13.

### 4.2 Bloqueio de feature

Nenhum branch client-side foi encontrado que desabilite uma feature com base nos sinais de §1. O único "bloqueio" observado em toda a superfície de integridade/mod é o throttling das próprias requisições de attestation/token (ab-props, documentado no relatório de integridade) — não uma resposta à detecção de um mod.

---

## 5. Superfície de ataque: o que um módulo de hook tem como alvo (WaEnhancer, `com.wmods.wppenhacer`)

Esta seção descreve o outro lado da fronteira — o que um módulo Xposed/LSPosed representativo faz hook dentro do processo host — para enquadrar o que a detecção client-side (em grande parte ausente) precisaria cobrir. Fonte da evidência: artefatos que uma instalação modificada pelo WaEnhancer deixou em um diretório `wa-data-root/` de teste capturado (`Protocols/waenhancer-mod/info.md`), não análise estática do próprio APK do WhatsApp. Tiers conforme registrados lá.

| Capacidade | Mecanismo | Tier |
|------------|-----------|------|
| Entrega | Módulo Xposed/LSPosed executando **dentro** do processo `com.whatsapp` (não um app separado, não um repack) | found |
| Tratamento de obfuscação | "Unobfuscator" em runtime: resolve nomes de classe/método obfuscados do WhatsApp na inicialização do módulo e armazena em cache os handles resolvidos (`UnobfuscatorCache.xml`, `UnobfuscatorCacheStrings.xml`), com chave vinculada ao nome de versão do próprio WhatsApp, de modo que o cache invalida quando qualquer um dos dois lados atualiza | found |
| Ocultação de presença ("ghost mode") | Faz hook de métodos relacionados a presença; configuração armazenada em `WaGlobal.xml` (`ghostmode`) | found (artifact) |
| Anti-revoke / anti-read-receipt | Intercepta os caminhos de código de delete-for-everyone e read-receipt; mantém cópias-sombra em seus próprios stores (`com_waenhancer_message_history.db`, e um `MessageHistory.db` baseado em Room — o próprio WhatsApp não usa Room para armazenamento de mensagens) | found |
| Visibilidade do protocolo bruto | `StanzaLogger.logStanza(...)` escreve stanzas XMPP de envio/recebimento em um arquivo em texto plano (`wae_stanzas.txt`) — ou seja, o módulo capta o próprio caminho de envio/recebimento de stanza do client depois que a camada Noise/E2E já descriptografou | found |
| Registro de hooks | Logging de diagnóstico por execução registrando uma contagem de hooks (`devtrace_logs/*.jsonl`, `eventType:"hook_config_loaded"`, `payload.hookCount`) | found |
| Limite de escopo | Faz hook só da camada Java/UI; não parece substituir a cripto nativa ou o transporte Noise/chatd (store axolotl/Signal, prekeys pós-quânticas, keystore, nativos OHAI/OPAQUE/WAFFLE intocados) | inferred |

Lido junto com §3: o client oficial não tem código que enumere módulos Xposed/LSPosed carregados, escaneie sua própria memória de processo por trampolins de hook, ou verifique `TracerPid`/`/proc/self/maps` por bibliotecas injetadas. A única coisa entre essa superfície de ataque e a detecção é o único probe genérico de classe `is_whatsapp_plus_user` (§2), que tem como alvo uma biblioteca de crash-reporting, não um hook framework.

---

## 6. Casos de erro / armadilhas

| Sintoma | Causa | Observação |
|---------|-------|------|
| `is_whatsapp_plus_user = true` no `wam_daily` sem nenhum efeito adicional no client | `org.acra.ACRA` resolvível no classpath | apenas telemetria, por design |
| `diagnostic` contém `nw-wap` / `NW-WAP-1` no contact-us ou em debug reports | mesmo probe de ACRA, sink diferente | texto de fluxo de suporte, não um gate |
| Nenhum motivo na tela de ban do WFAC além de um código numérico | `ban_violation_type`/`ban_violation_source` não têm enum client-side | controlado pelo servidor, não pode ser resolvido estaticamente |
| Buscar por "Xposed"/"Frida" não retorna nada | correto — esta build não contém detecção de hook-framework | não é uma lacuna de decompilação para essas strings específicas (busca em toda a árvore) |
| Uma instalação do WaEnhancer altera o comportamento de mensagem/read-receipt sem nenhum log do lado do WhatsApp | O WaEnhancer faz hook da camada Java antes que a própria telemetria do WhatsApp possa observar a chamada original | esperado dado o escopo de §5 |

---

## 7. Distinções importantes

| Não confundir | Fato |
|-----------------|------|
| `is_whatsapp_plus_user` vs. uma allowlist de mod-clients | um probe reflexivo para uma classe de biblioteca de terceiros; não existe lista de nomes de pacote de mod |
| Detecção de mod/tamper (este relatório) vs. atestação de conta (`WA_CLIENT_INTEGRITY.md`) | problemas diferentes: este relatório é sobre detectar um *binário/runtime de client modificado*; o relatório de integridade é sobre *atestar um dispositivo/chave genuíno* para o servidor — eles se sobrepõem só no fato de ambos serem telemetria, não enforcement |
| UI de ban do WFAC (`WfacBanActivity`) vs. lógica de decisão de ban | a activity renderiza códigos/strings fornecidos pelo servidor; ela não decide nem computa um motivo de ban |
| O tap `StanzaLogger` do WaEnhancer vs. quebrar a criptografia E2E | o módulo lê stanzas dentro do processo do client já descriptografado; ele não ataca a criptografia Signal/Noise em si |
| Telemetria de `safety-net-attestation` / assinatura / origem de instalação | esses existem e estão documentados em `WA_CLIENT_INTEGRITY.md`; este relatório não adiciona nenhum mecanismo novo para eles, só declara que nenhum deles bloqueia nada |
| "Não encontrado" neste relatório | significa ausente do Java/smali/strings decompilados desta build específica (2.26.41.6); não é uma afirmação sobre detecção server-side, que é inobservável estaticamente |

---

## 8. Fluxo de ponta a ponta

```
[Device boots WhatsApp, possibly under a hook module or with a bundled crash-reporter lib]
    │
    ▼
[Cdt.C4k / C1Z / C10V]  Class.forName("org.acra.ACRA")
    │  success ──► is_whatsapp_plus_user = true ─► wam_daily
    │  success ──► "nw-wap" / "NW-WAP-1" ─► contact-us / debug-report text
    │  (no further branch — nothing reacts to this value in the client)
    ▼
[AbstractC38241gg / C27965CCj]  signature self-check → WAM 6251   (see WA_CLIENT_INTEGRITY.md §5)
[CHH]                           install-source flag  → WAM 10255  (see WA_CLIENT_INTEGRITY.md §5.4)
[C00L / Cdt]                    root / emulator / custom-ROM     → wam_daily  (see WA_CLIENT_INTEGRITY.md §6)
    │
    ▼
[WA telemetry backend]  (server-side use of all of the above: unknown, not observable)
    │
    ▼
[If the server bans the account]
    │  ban_violation_type / ban_violation_source / ban_violation_reason sent as intent extras
    ▼
[WfacBanActivity]  displays the server's values verbatim — no client-side cause mapping
```

```
[Attack surface, other side of the boundary — not WhatsApp code]
[Xposed/LSPosed host process: com.whatsapp]
    │
    ▼
[WaEnhancer module loads] ─ Unobfuscator resolves WhatsApp's classes at runtime
    │
    ├─► hooks presence methods ──────► ghost mode (WaGlobal.xml)
    ├─► hooks delete/read-receipt ───► shadow stores (MessageHistory.db, com_waenhancer_message_history.db)
    └─► taps stanza send/receive ────► wae_stanzas.txt (post-decryption plaintext)
```

---

## 9. Incertezas

| Pergunta | Por que é desconhecida |
|----------|-------------|
| Se o servidor usa `is_whatsapp_plus_user`, mismatch de assinatura (6251), origem de instalação (10255) ou flags de root como inputs de ban/trust-score | server-side, nenhum tráfego observado |
| Se `org.acra.ACRA` está de fato presente em uma build atual do WaEnhancer/GB WhatsApp (ou seja, se a única heurística existente dispararia nele) | não verificado contra uma build de mod real nesta passagem |
| Mapeamento nomeado de motivo de ban para os valores de `ban_violation_type` / `ban_violation_source` | nenhum enum resolvido client-side; definido pelo servidor |
| Se algum código nativo (`libwhatsapp.so`, `libwasafe.so`) realiza detecção de hook/tamper além do que `WA_CLIENT_INTEGRITY.md` já encontrou ausente | bibliotecas nativas stripped não re-rastreadas exaustivamente para este relatório além da busca por strings em §3 |
| Tratamento server-side de uma visibilidade no estilo `wae_stanzas.txt` captada pelo WaEnhancer (ou seja, se o servidor pode distinguir um client com hook de um genuíno no nível de protocolo) | não observável estaticamente |
