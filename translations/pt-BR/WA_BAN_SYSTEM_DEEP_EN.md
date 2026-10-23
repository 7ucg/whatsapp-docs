<!-- src-sha1: 84ea5bd809c6118cf8363e58c56bee3ba607d23e -->
# WhatsApp Ban System — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-17
**Escopo:** Fluxo de banimento, ciclo de vida do WFAC, coleta de sinais de spam, protocolo GraphQL, sistema de apelação, marcação como suspeito, prevenção

---

## 1. Visão Geral da Arquitetura

```
                         [Server]
                             │
       ┌─────────────────────┴──────────────────────────────┐
       ▼                                                     ▼
XMPP login <failure reason=…>                   MEX GraphQL (pull-based)
(HandlerThreadC12340b0.A13 → C45351tB,            │
 handled in C0ZH.handleMessage)                   ├── BizIntegrityQuery ──► BizIntegritySignalsManager
  │                                               │        └─► wa_biz_integrity_signals (SQLite, wa.db)
  ├─ 403 perm-ban ─► HGB.startPermanentBanFlow    │              ├── is_banned (INT)   (stored; no reader found)
  │      └─► BanAppealActivity (userban.ui)       │              ├── is_suspicious (INT)
  ├─ 416 / 402+code 106|107|109 (underage/U13)    │              ├── trust_tier (TEXT)
  │      └─► WfacManager.startUnderageBanFlow     │              ├── dhash (TEXT, server-supplied, opaque)
  ├─ 402 otherwise ─► SpamWarningActivity         │              ├── is_meta_verified (new in 2.26.41.6 vs report)
  ├─ 405 ─► pref software_forced_expiration (`t`)      │              ├── fmx_business_holdout_group (TEXT, new)
  └─ 406 ─► pref underage_account_banned            │              └── integrity_tags (JSON)
                                                  │
                                                  └── ban-status fetch (xwa2_fetch_wa_users, token)
                                                           └─► WfacBanRepository ──► SharedPreferences
                                                                 ├── wfac_ban_state = "BANNED" | "CHECKPOINTED" | "UNBANNED"
                                                                 ├── wfac_ban_violation_type
                                                                 ├── wfac_ban_violation_reason
                                                                 ├── wfac_ban_violation_source
                                                                 ├── wfac_last_ban_status_fetch_timestamp_ms (new)
                                                                 └── wfac_ban_status_token

  Main.A5W() (2.26.26.4: `Main.A5D()`; reads wfac_ban_state at start, registration state 21, log "main/me/wfac ban")
      └─► WfacBanActivity (hard ban UI; now `com.whatsapp.waffle.wfac.ui`, JADX pkg `p191ui`; intent built by `HBC`)

  SpamWarningActivity (pre-ban warning)       ◄── XMPP <failure reason=402> (C0ZH, type 2)
  SuspiciousFmxBottomSheetFragment (info sheet, opened from the FMX card buttons, see 7.2)
  SMB soft-enforcement banner                 ◄── XMPP business notification `biz_integrity_warning_notification` (see 7.4)
```

**Achado crítico (corrigido na 2.26.41.6):** a sincronização do estado de banimento (WFAC) é **pull-based via MEX GraphQL**, mas os *eventos* de banimento e de aviso no momento da conexão chegam por XMPP no nó `<failure>` do login (reason 402/403/416/406, seção 8.1). O aviso de soft-enforcement de SMB é uma notificação de negócio XMPP. Nenhuma sinalização de banimento via `<stream:error>` foi encontrada (esse handler trata apenas `code` 515/516, `conflict type="device_removed"` e kicks por `ack`).

---

## 2. Ciclo de Vida do Estado de Banimento (WFAC)

### 2.1 Máquina de Quatro Estados

| Estado | Valor | Significado |
|--------|-------|-------------|
| `UNKNOWN_IN_CLIENT` | 0 | Sem cache local (também fallback para qualquer string não reconhecida) |
| `CHECKPOINTED` | 1 | Restrição leve, pode exigir verificação. A string do servidor `NO_APPEAL_OPENED` é mapeada para `CHECKPOINTED` por `AbstractC38371GmM.A00` (novo) |
| `BANNED` | 3 | Banimento definitivo, conta restrita, apelação possível |
| `UNBANNED` | 2 | Totalmente funcional |

### 2.2 SharedPreferences (MainPreferences)

```
wfac_ban_state              → "BANNED" | "CHECKPOINTED" | "UNBANNED" | "UNKNOWN_IN_CLIENT"
wfac_ban_status_token       → server token for status updates (must be non-empty)
wfac_ban_violation_type     → INT (violation category)
wfac_ban_violation_reason   → STRING
wfac_ban_violation_source   → INT (intent extra 0/1/2 kept, anything else -1; stored only for launch_source 2/3; default -1 via `HLK`; category names for 0/1/2 not found in 2.26.41.6, so the earlier SPAM/PHISHING/UNDERAGE mapping stays unverified)
wfac_last_ban_status_fetch_timestamp_ms → LONG (throttle, new)
```

Wrapper de prefs: `HLK` (o getter de estado faz o parse via `C36188FnW.A00`: string inválida lança "Invalid BanState"). ViewModel: `C36188FnW` (WfacBanViewModel).

### 2.3 Fluxo de Transição de Estado

```
Client connects
    │
    ▼
wfac_ban_status_token present? → NO → UNKNOWN_IN_CLIENT (no check)
    │ YES
    ▼
Registration state == 21? (fully registered)
    │ YES
    ▼
GraphQL: xwa2_fetch_wa_users (with token) (still present, `AWS`, `C46770Kc0`)
    │
    ▼
Throttle: skip if last fetch < 5000 ms ago (refreshInterval) or a fetch is in flight (generation counter); 60 s timeout runnable (new)
    │
    ▼
Response parsed by handler `C40191HfD` (obfuscated name 2.26.41.6; response class `C42252Ic7` / `C204538nH`)
    │
    ├── Stores via SharedPreferences: "wfac_ban_state" = state_string (stale generation responses discarded)
    ├── Error codes 1-4 logged separately; unknown → -1 (found, `C40191HfD`)
    └── Writers of `wfac_ban_state`: this handler (server string stored as is, `WfacBanRepository/storeBanState`), and `WfacBanActivity.onCreate` (launch_source 2/3 → "CHECKPOINTED"; launch_source 4 with `appeal_decision` "banned"/"unbanned" → "BANNED"/"UNBANNED"). No code path from `is_banned` (BizIntegrity) to `wfac_ban_state` was found.
```

### 2.4 Sequência de Reset do Banimento

Em apelação bem-sucedida ou liberação da conta (`WfacBanViewModel.A0x` / `C36188FnW`, resetRegistration):
1. Limpa: `wfac_ban_state`, `wfac_ban_status_token`, `wfac_ban_violation_*`, `wfac_last_ban_status_fetch_timestamp_ms`, `support_ban_appeal_user_banned_from_chat_disconnect` (novo)
2. Desconecta o usuário (finishAffinity)
3. Redireciona para a tela de login

---

## 3. BizIntegrityQuery — Protocolo GraphQL

### 3.1 Detalhes Técnicos

| Parâmetro | Valor |
|-----------|-------|
| Nome da query | `BizIntegrityQuery` |
| doc_id | `28596420510007620` (mudou; era `25975613018777537`, rotacionado na 2.26.38.10, confirmado no catálogo de persist-id da 2.26.41.6; client_doc_id `14769534217004148908396994706`) |
| Schema | `whatsapp-android-mex` |
| Transporte | MEX HTTP/2 POST → `/mex/query` |
| Formato do JID | `<shortNum>@lid` (p. ex. `1910@lid`) |

### 3.2 Requisição

2.26.41.6 (found, `BizIntegritySignalsGraphQLFetcher.A00`): objeto de entrada `input { query_input: [ {jid, privacy_token{tctoken, timestamp}?} ], telemetry{context:"INTERACTIVE"} }`, classe de resultado `C48528LIw`. `privacy_token` só é adicionado quando um gate (`MZ4.A00`) corresponde e existe um TC-token armazenado. Resposta (found, `C51015Mjl`): raiz `xwa2_fetch_wa_users[]`, por usuário `integrity_signals_info` com `dhash`, `fb_linked_page_number_of_likes`, `ig_linked_age_number_of_followers` (sic, chave literal), `is_banned`, `is_suspicious`, `is_suspicious_start_chat`, `join_date_ms` (string, convertida para long), `phone_country_code`, `trust_tier` (enum `M5B`), `is_mv_subscribed` (armazenado como `is_meta_verified`), `meta_verified_info{mv_friction_eligibility}`, `integrity_tags[]{tag, pipeline_date_ms, dates_ms[]}`, `hide_safety_tools_for_business`, `fmx_business_holdout_group`. A lista de campos abaixo é a reconstrução da 2.26.26.4 (inferred, não reverificada; o formato da variável de requisição `$userJids` difere do formato de entrada da 2.26.41.6):

```graphql
query BizIntegrityQuery($userJids: [ID!]!) {
  bizIntegrityQuery(jids: $userJids) {
    jid
    is_banned
    trust_tier
    is_suspicious
    is_suspicious_start_chat
    integrity_tags { tag, pipelineDS, taggedDates }
    dhash
    phone_country_code
    join_date_ms
    fb_linked_page_number_of_likes
    ig_linked_page_number_of_followers
    mv_friction_eligibility
    hide_safety_tools_for_business
    chat_row_id
    last_sync_ts
  }
}
```

### 3.3 DTO de Resposta — `BizIntegritySignals` (`C51530MtC`; era C39833Hhl na 2.26.26.4)

```
BizIntegritySignals(
  userJid, dhash, fbLinkedPageNumberOfLikes,
  igLinkedPageNumberOfFollowers, isBanned, isSuspicious,
  isSuspiciousStartChat, joinDateMs, phoneCountryCode,
  trustTier, isMetaVerified, mvFrictionEligibility, integrityTags,
  chatRowId, lastSyncTs, hideSafetyToolsForBusiness, fmxBusinessHoldoutGroup
)

Fields:
  integrityTags           → List of IntegrityTagInfo
  userJid                 → UserJid
  hideSafetyToolsForBiz   → Boolean
  isBanned                → Boolean  ← HARD BAN FLAG
  isSuspicious            → Boolean  ← SOFT ENFORCEMENT
  isSuspiciousStartChat   → Boolean
  isMetaVerified          → Boolean  (new)
  mvFrictionEligibility   → Boolean
  fmxBusinessHoldoutGroup → String   (new; stored as fmx_business_holdout_group, purpose unknown)
  chatRowId               → Long
  fbLinkedPageLikes       → Long (stored as REAL)
  igLinkedFollowers       → Long (stored as REAL)
  joinDateMs              → Long (stored as REAL)
  lastSyncTs              → Long
  dhash                   → String
  phoneCountryCode        → String
  trustTier               → String: "SUSPICIOUS" | "UNTIERED" | "TRUSTED"
```

### 3.4 DTO de IntegrityTags

(`C51222Mno` lista de `C51359MqA`; serialização em `LwI`, formato inalterado)

```
IntegrityTagInfo {
  tag         → String
  pipelineDS  → Date (originally Long ms)
  taggedDates → List<Date>
}
```

**Formato JSON no banco:**
```json
[
  {
    "tag": "automation_bulk_messaging",
    "pipelineDS": 1700000000000,
    "taggedDates": [1699000000000, 1699500000000]
  }
]
```

### 3.5 Eventos de Disparo

| Gatilho | String de usecase |
|---------|-------------------|
| Abrir um chat | `"START_CHAT_CONTEXT"` (gatilho principal) |
| Após enviar uma mensagem | hook pós-envio |
| Início do app / login | agendador em segundo plano |

### 3.6 Feature Flags

| ID da flag | Função |
|------------|--------|
| 11061 | Gatilho de detecção de conta suspeita (`N5r.A03`; presente; avaliado apenas para contatos cujo nível de nome verificado começa com `ent:`) |
| 11064 | Elegibilidade do sinal de confiança de início de chat (ligado/desligado) (`BizIntegritySignalsManager.A04`; presente; padrão false) |
| 11065 | TTL do cache do sinal de confiança em segundos (`C51855N0t.A00`; padrão 86400, encontrado em `C08J`) |
| 12709 | Elegibilidade para contatos cujo negócio tem `hostStorage == 2` (`C197628ax.A06`); padrão false (presente) |
| 16349 | Caminho de consulta forçada em `BizIntegritySignalsManager.A04` (presente; padrão false) |
| 19793 | Novo nesta tabela: `N5r.A02`, controla a reutilização de sinais armazenados em `C51855N0t.A02`; finalidade inferida pelo uso; padrão false |
| 12840 | Configuração JSON indexada por tipo de violação, padrão `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}` (`C08J`); consumidor não localizado; finalidade inferida pelos nomes das chaves (`max_dismiss_count`, `max_display_days`) e pelas strings de tipo usadas pelo banner de soft-enforcement de SMB (7.4) |
| 19893 | Registro de mensagem de sistema do cartão FMX (presente, `C198788cr`) |
| 26697 | BizIntegrity v2 (presente, `C34735F5e`) |
| 27269 | Contagem separada de mensagens recebidas/enviadas (presente) |
| 34166 | ID de injeção, não um feature flag (veja WA_AB_PROPS.md); usado pelo escritor de `start_chat_trust_signals` (`ContactInfoActivity`) |

Cache em memória em `BizIntegritySignalsManager.A02`: entradas válidas por 60000 ms (found).

---

## 4. Marcação como Suspeito — Quando, Por Quê, Como, Prevenção (reverificado na 2.26.41.6; itens que não puderam ser localizados estão marcados no próprio local)

> **Achado central:** para as flags de BizIntegrity (`is_suspicious`, `trust_tier`, `is_banned`) o cliente não calcula nada: elas são extraídas da resposta GraphQL (`C51015Mjl`) e apenas renderizadas. Nenhum limiar ou pontuação no lado do cliente foi encontrado para elas. Separadamente, um modelo on-device produz veredictos locais de golpe (`odml_scam_alert_*`, 6.6, 7.6). A requisição BizIntegrity carrega apenas os JIDs consultados, um privacy token opcional e um contexto de telemetria (3.2); que o cliente envie suas métricas locais para outro lugar não foi encontrado.

### 4.1 Quem decide?

```
Local inputs on the device (found):             Server response (found, 3.3):
────────────────────────────────                ──────────────────────────────
• message counts (in/out/threads)               • trust_tier
  via N54 logger (6.2)                          • is_suspicious / is_suspicious_start_chat
• on-device features isCountryMismatch,         • is_banned (stored, no reader found)
  mostRecentSenderScore (6.6)                   • integrity_tags, dhash, join_date_ms,
• BizIntegrity request: jid(s) +                  phone_country_code, FB/IG counts,
  optional privacy_token (TC-token)               is_mv_subscribed, mv_friction_eligibility
```

Não existe no cliente nenhuma seta das métricas locais para a requisição BizIntegrity (3.2). Quais sinais do lado do servidor produzem o veredicto não é visível no APK (ML no servidor é inferred). O cliente **não tem limiar local** do tipo "mais de X mensagens -> suspeito" para as flags de BizIntegrity.

---

### 4.2 Hierarquia de Trust Tier (atribuída pelo servidor)

Encontrada no APK do WhatsApp como um enum compilado (`M5B` na 2.26.41.6; valores inalterados):

| Tier | Significado | Efeito |
|------|-------------|--------|
| `SUSPICIOUS` | Risco mais alto — sinalizado ativamente | Todos os avisos ativos, fricção na UI, possível bloqueio de envio |
| `TIER_0` | Menor tier legítimo (contas novas) | Elegibilidade elevada a fricção |
| `TIER_1` | Usuário padrão | Normal |
| `TIER_2` | Confiança elevada | Menos fricção |
| `TIER_3` | Maior confiança legítima | Fricção mínima |
| `UNTIERED` | Sem avaliação | Nenhuma verificação aplicada |
| `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` | Desconhecido | Fallback |

**Verificação no nível do código** (`BizIntegritySignalsManager`):
```java
"SUSPICIOUS".equals(trustTier)  // → triggers UI flow
```

### 4.3 Sinais em torno do veredicto

O cliente não anexa os pontos de dados abaixo à requisição BizIntegrity (3.2). A tabela lista onde cada um aparece no cliente; se o servidor o avalia é inferred. A coluna "Risk weight" do relatório anterior não tinha evidência no lado do cliente e foi removida.

| Sinal | Onde aparece no cliente (2.26.41.6) | Função |
|-------|--------------------------------------|--------|
| `isCountryMismatch` | feature on-device (`integrityai.impl.InputFeatureProviderImpl`, flag 31535) | Entrada do modelo on-device, não da requisição |
| `mostRecentSenderScore` | feature on-device (flag 31536) | Idem |
| `dhash` | campo da resposta, armazenado como está | String opaca fornecida pelo servidor; nenhum código do cliente a compõe (significado unknown; a leitura anterior do relatório como "device fingerprint" é inferred) |
| `join_date_ms`, `phone_country_code` | campos da resposta | Armazenados; sem limiar no cliente |
| Contagens de FB/IG | campos da resposta (`fb_linked_page_number_of_likes`, `ig_linked_age_number_of_followers`) | Mostradas no cartão FMX (7.5) |
| `integrity_tags` | campo da resposta `{tag, pipeline_date_ms, dates_ms[]}` | Armazenado como JSON; os valores das tags são opacos para o cliente |
| Privacy token | campo da requisição `privacy_token{tctoken, timestamp}` | Opcional, apenas quando o gate `MZ4.A00` corresponde e um TC-token está armazenado |
| Volume de mensagens | contagem local (`N54`, 6.2) | Envio ao servidor não encontrado |
| Limite de broadcast | flag 20278 padrão `{"max_messages": 10000, "farthest_time_days": 30}` | Consumidor não localizado (6.3) |

`isCountryMismatch` e `mostRecentSenderScore` são as duas features de ML concretas encontradas no cliente (`com.whatsapp.integrityai.impl.InputFeatureProviderImpl`, 2.26.41.6). A flag 31535 fornece isCountryMismatch, a 31536 mostRecentSenderScore (found).

---

### 4.4 Quando a verificação GraphQL é disparada?

**Gate de elegibilidade** (found, `BizIntegritySignalsManager.A04`; o JID consultado é a contraparte do chat):
1. Feature flag **11064** habilitada (padrão false)
2. O JID não é de um dos dois tipos excluídos (`AbstractC24760wu.A03/A04`: JIDs de bot e um JID de número de telefone fixo)
3. Uma das condições: o contato é um negócio SMB (`N5r.A06`, nível de nome verificado começa com `smb:`), ou a flag **12709** está ligada e o negócio do contato tem `hostStorage == 2` (`C197628ax.A06`), ou (chamada forçada, `A09`) a flag **16349** ligada e `N5r.A04/A06` verdadeiro (`A04` = `!A01 && !SMB && !ENT`; a semântica do helper `N5r.A01` não foi resolvida, então quais JIDs não comerciais isso admite continua em aberto)
4. No caminho não forçado: cache expirado ou sem cache local (`C51855N0t`)

Correção em relação ao relatório anterior: na 2.26.41.6 o gate regular não pula contas comerciais, ele as seleciona (SMB ou hospedadas); o caminho forçado (16349) pode admitir outros JIDs. O fluxo do JADX de `A04` está parcialmente reestruturado, então esta leitura vem do formato decompilado mais os corpos dos helpers, não de smali.

**TTL do cache:** Feature flag **11065** em segundos, padrão **86400 (24 horas)** (found, `C08J`)
```java
long timeout_ms = TimeUnit.SECONDS.toMillis(remoteConfigValue(11065));
if (current_time - lastSyncTs > timeout_ms) {   // C51855N0t.A00
    // cache expired -> new GraphQL call required
}
```

**Tamanho do lote:** não existe divisão em chunks de 975 JIDs no caminho de fetch do GraphQL (`BizIntegritySignalsManager.A03` repassa a lista de JIDs sem alterações). A constante 975 pertence ao processamento em lotes da contagem local de mensagens em SQL (6.2).

---

### 4.5 Valores conhecidos de integrity_tag

As strings `automation_bulk_messaging` e `spam` são encontradas em `C35896FgX` e `ViewOnClickListenerC39711HTl`, mas ali são comparadas com o `type` da notificação de soft-enforcement de SMB (`HAR.A07`, ver 7.4), não com `integrity_tags` da resposta BizIntegrity. Também aparecem como chave do padrão da flag 12840. O cliente não enumera de forma alguma os valores de `integrity_tags`; os blobs JSON são armazenados de forma opaca. `business_policy_violation` não está presente como string em lugar nenhum de java_src, smali, assets ou res da 2.26.41.6.

| Tag | Significado |
|-----|-------------|
| `automation_bulk_messaging` | Tipo de notificação de soft-enforcement (envio em massa/automatizado); não demonstrado como valor de `integrity_tags` |
| `spam` | Tipo de notificação de soft-enforcement (spam) |

---

### 4.6 O que leva concretamente a suspeito — inferred pelo código

Reverificado na 2.26.41.6: o cliente não contém lógica, limiar ou peso para nenhuma linha abaixo, e a requisição BizIntegrity não carrega nenhuma dessas métricas (3.2). A tabela inteira continua **inferred** (um palpite sobre o comportamento do servidor a partir de quais sinais existem no cliente). A linha "New account (< 24h)" não tem sustentação: não existe verificação de idade da conta no cliente (ver 4.9 D).

| Comportamento | Por que é arriscado | Peso |
|---------------|---------------------|------|
| Alto volume de saída vs. entrada (só envia, sem respostas) | Padrão de abordagem em massa | Muito alto |
| País do telefone ≠ país do IP | `isCountryMismatch = 1.0` | Muito alto |
| Mesmo dhash em várias contas | Gatilho de banimento de dispositivo | Muito alto |
| Broadcast > 10,000 destinatários / 30 dias | Limite rígido, flag imediata | Alto |
| `mostRecentSenderScore` alto (destinatários denunciando) | Ciclo de feedback do ML | Alto |
| Conta nova (< 24h, sem contatos) | Baixa credibilidade (nenhuma verificação de idade no cliente encontrada) | Alto |
| Sem vínculo FB/IG + alta taxa de envio | Falta de prova social | Médio |
| integrity_tags existentes | Efeito de violação anterior | Médio–Alto |
| `is_reach_out = 1` + iniciar muitos chats desconhecidos | Padrão de contato frio | Médio |

### 4.7 Códigos de motivo do SpamWarning (aviso pré-banimento)

Inalterado na 2.26.41.6 (`SpamWarningActivity`: motivo padrão 100, expiração padrão -1; switch em 101, 102, 103, 104, 106, o default cobre 105/outros).

Entregue via intent extra `spam_warning_reason_key`, definido a partir do atributo `code` (>= 100) do `<failure reason="402">` do login XMPP junto com `expire`, `message`, `url` (found, `C0ZH.handleMessage` tipo 2; ver 8.1):

| Código | Gatilho | Contagem regressiva? |
|--------|---------|----------------------|
| 101 | Atividade de spam detectada | Sim |
| 102 | Violação de encaminhamento | Sim |
| 103 | Spam de status | Sim |
| 104 | Encaminhamento de bot | Sim |
| 105 | Geral / padrão | Permanente se expiração = -1 |
| 106 | Outra violação | Sim |
| default | Violação desconhecida | Permanente se expiração = -1, caso contrário contagem regressiva |

`expiry_in_seconds == -1` + online: finaliza imediatamente (o servidor suspendeu o aviso).

### 4.8 Categorias de SpamFlow relevantes para a marcação como suspeito

97 categorias no APK (found: `C9E2`, array de 96 entradas mais `1_1_spam_banner_report` acrescentada por último, índices 0 a 96; a contagem anterior de 92 e os índices da tabela foram substituídos). A lista é serializada por nome dentro do nó SMAX `spam_list` (atributo `spam_flow` por entrada, `wi_trace_id` opcional de 24 caracteres), então o índice é apenas a posição no array do cliente, não um valor da rede. Novas: `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_suspicious_banner_block/_trust`, `odml_scam_alert_fmx_card_block/_trust`, `biz_spam_banner_block`, `1_1_spam_banner_block`, `chat_fmx_card_block`, `group_spam_banner_report`, `left_group_spam_banner_report`. As diretamente ligadas ao estado suspeito:

| Índice | Categoria | Significado |
|--------|-----------|-------------|
| 23 | `chat_fmx_card_block_server_flagged_suspicious` | Suspeito sinalizado pelo servidor → bloqueio FMX |
| 24 | `chat_fmx_card_block_suspicious` | Chat bloqueado devido à flag de suspeito |
| 27 | `chat_fmx_card_safety_tools_block_suspicious` | Ferramentas de segurança mostradas para suspeito |
| 70 | `odml_scam_alert_bottom_sheet_block` | Golpe detectado por ML on-device → bloquear |
| 71 | `odml_scam_alert_bottom_sheet_trust` | Golpe detectado por ML on-device → confiar |
| 76 | `one_to_one_spam_banner_block_server_flagged_suspicious` | Banner de spam 1:1 (sinalizado pelo servidor) |
| 85 | `trust_question_bottomsheet_block_server_flagged_suspicious` | Prompt de confiança (sinalizado pelo servidor) |
| 89 | `user_initiated_chat_suspicious_banner_block` | Banner de suspeito no início do chat |
| 94 | `1_1_old_spam_banner_block` | Banner de spam legado |
| 96 | `1_1_spam_banner_report` | Denúncia de spam 1:1 |

### 4.9 Mecanismos de proteção — o que o cliente mostra

A lista anterior de "fatores de proteção" é uma leitura de ML no servidor sem sustentação no lado do cliente. O que a 2.26.41.6 realmente contém:

#### A) Status de negócio
Não é um skip. O gate regular de elegibilidade seleciona contatos SMB (e contatos com `hostStorage == 2` sob a flag 12709), ver 4.4. A flag 2923 (antes: "non-business validation toggle") não foi localizada: não existe verificação de flag com esse ID nem configuração padrão para ela em java_src ou smali da 2.26.41.6.

#### B) Meta Verified (mvFrictionEligibility)
Campo da resposta `meta_verified_info.mv_friction_eligibility` (found, `C51015Mjl`), armazenado como `mv_friction_eligibility`. `is_mv_subscribed` é armazenado separadamente como `is_meta_verified`. O cartão FMX (`C94p`) lê a flag e, com a flag 15735 ligada, adiciona um link "learn more". Que isso resulte em limiares de fricção menores não é visível no cliente (inferred).

#### C) Contas sociais vinculadas (FB/IG)
`fb_linked_page_number_of_likes` e `ig_linked_age_number_of_followers` são lidos como inteiros (`optInt`) e mostrados no cartão FMX (7.5). São contagens, não booleanos (found). Que o servidor as pondere como protetoras é inferred.

#### D) Período de carência pela idade da conta
Não encontrado. A única comparação semelhante a idade é o TTL do cache em `last_sync_ts` contra a flag 11065 (4.4). `join_date_ms` é armazenado, mas não existe lógica de janela de carência no cliente.

#### E) Whitelist / lista de validação (flag 12709)
Mudou: a verificação `C197628ax.A06(userJid)` é `hostStorage == 2` no registro de nome verificado do contato (`AnonymousClass119`), uma propriedade local, não uma lista de pré-aprovação no servidor. Ela torna o contato elegível para a consulta; não retorna cedo.

#### F) hideSafetyToolsForBusiness (campo da resposta)
Campo da resposta `hide_safety_tools_for_business`, armazenado em `hide_safety_tools_for_business`. O efeito na UI não foi rastreado novamente; a afirmação anterior de que ele apenas oculta a UI de aviso e não altera o status de suspeito não foi verificada.

---

### 4.10 Prevenção — o que o código revela

Esta parte é um conselho derivado dos campos acima. O cliente não tem lógica que confirme qualquer item; trate todos como **inferred**, exceto onde marcado como found.

**Comportamental (inferred):**
- Mantenha a proporção saída/entrada equilibrada
- Evite divergência de país entre o número e a rede (o cliente alimenta `isCountryMismatch` no modelo on-device, found; uso no servidor inferred)
- Fique abaixo da configuração de broadcast da flag 20278 (10,000 mensagens / 30 dias; consumidor não localizado)

**Qualidade da conta (inferred):**
- Contagens de FB/IG vinculados e Meta Verified são mostrados ou armazenados pelo cliente (found); seu efeito no veredicto é inferred
- Uma janela de conta nova (24h) e a lista negra de dhash não são sustentadas por nenhum código do cliente (ver 4.9 D e 4.3)

**Técnico (found):**
- `privacy_token` (TC-token) é adicionado à requisição BizIntegrity apenas quando o gate `MZ4.A00` corresponde e um TC-token está armazenado

**Temporização (found):**
- Sinais em cache são reutilizados até que `last_sync_ts` seja mais antigo que a flag 11065 (padrão 86400 s); o manager mantém uma entrada adicional em memória de 60000 ms
- Os sinais persistem em `wa_biz_integrity_signals` até serem sobrescritos por uma nova resposta

---

## 5. Bancos de Dados SQLite Locais

### 5.1 `wa.db` — `wa_biz_integrity_signals`

2.26.41.6 (found, `C53116Nmn`, 17 colunas incl. `_id`): acrescenta `is_meta_verified` e `fmx_business_holdout_group`; `fb_linked_page_number_of_likes`, `ig_linked_page_number_of_followers`, `join_date_ms`, `last_sync_ts` são REAL, `mv_friction_eligibility` e `is_meta_verified` não têm padrão declarado. Índices únicos `biz_integrity_signals_jid_index`, `biz_integrity_signals_chat_row_id_index`; trigger `contact_bd_for_business_integrity_signals` (BEFORE DELETE ON wa_contacts). Store: `LwI` (rótulos `QUERY_BIZ_INTEGRITY_SIGNALS_BY_JID` / `_BY_ROW_ID`, `BizIntegritySignalsStore/saveBusinessIntegritySignals`). O schema abaixo é a versão da 2.26.26.4.

```sql
CREATE TABLE wa_biz_integrity_signals (
  jid                               TEXT PRIMARY KEY,
  join_date_ms                      LONG,
  trust_tier                        TEXT,     -- "SUSPICIOUS" | "TRUSTED" | ...
  is_suspicious                     INTEGER,  -- 0/1
  is_banned                         INTEGER,  -- 0/1
  dhash                             TEXT,     -- device fingerprint
  phone_country_code                TEXT,
  ig_linked_page_number_of_followers INTEGER,
  fb_linked_page_number_of_likes    INTEGER,
  is_meta_verified                  INTEGER,  -- new in 2.26.41.6
  mv_friction_eligibility           TEXT,
  integrity_tags                    TEXT,     -- JSON array
  chat_row_id                       LONG,
  last_sync_ts                      LONG,
  hide_safety_tools_for_business    INTEGER,  -- 0/1
  fmx_business_holdout_group        TEXT      -- new in 2.26.41.6
);
```

Escritor/leitor: `LwI` (store), `BizIntegritySignalsManager.A06(UserJid)` lê o `ConcurrentHashMap` em memória (found: `A06` lê o mapa em memória, `A07` o lê com carga lazy do banco, `A0A` faz upsert e persiste; os nomes `A08`/`A01` da 2.26.26.4 não existem mais)

### 5.2 `wa.db` — `start_chat_trust_signals`

```sql
CREATE TABLE start_chat_trust_signals (  -- schema `AI0`, columns unchanged (is_sender_suspicious, is_sender_new_account, created_ts); writer `C198788cr`
  jid                   TEXT PRIMARY KEY,  -- FK to wa_contacts
  is_sender_suspicious  INTEGER,           -- 0/1
  is_sender_new_account INTEGER,           -- 0/1
  created_ts            LONG
);

CREATE TRIGGER start_chat_trust_signals_contact_delete
  BEFORE DELETE ON wa_contacts
  BEGIN DELETE FROM start_chat_trust_signals WHERE jid = old.jid; END;
```

Leitor: `C57342Yp` (`SELECT * ... QUERY_START_CHAT_TRUST_SIGNALS_BY_JID`; era C2M7.A0K) → retorna a tupla `(is_sender_new_account, is_sender_suspicious)`

### 5.3 `msgstore.db` — `integrity_chat_info`

```sql
CREATE TABLE integrity_chat_info (
  chat_row_id                        LONG PRIMARY KEY,
  is_reach_out                       INTEGER,  -- 1 = unknown contact initiated
  is_eligible_for_link_friction_banner INTEGER
);
```

Rótulo da query: `"GET_INTEGRITY_CHAT_INFO"` (query em lote com `chat_row_id IN (...)`), store `C33O`, schema `C08970Ox` (índice `integrity_chat_info_chat_row_id_index`, trigger `chat_bd_for_integrity_chat_info_trigger` BEFORE DELETE ON chat). Inalterado.

### 5.4 `wa.db` — `wa_biz_integrity_chat_settings`

Encontrado na 2.26.41.6: schema `AHY` (colunas `jid`, `last_delivered_sort_id` LONG, `last_read_sort_id` LONG), índice único `biz_integrity_chat_settings_index` em `jid`, trigger `contact_bd_for_biz_integrity_chat_settings` (BEFORE DELETE ON wa_contacts). Função unknown.

---

## 6. Coleta de Sinais de Spam (Lado do Cliente)

(Reverificado na 2.26.41.6; itens que não puderam ser localizados estão marcados no próprio local.)

### 6.1 dhash

`dhash` é uma string na resposta BizIntegrity (`integrity_signals_info.dhash`), armazenada em texto simples em `wa_biz_integrity_signals.dhash`. Nenhum código do cliente a compõe: nenhuma entrada de modelo do dispositivo, SO, versão do app, número, fuso horário, Android ID ou build-fingerprint foi encontrada, e nada envia uma. A descrição anterior de "device fingerprint / lista negra no servidor" não é sustentada; o significado é unknown. Outras strings `dhash` no APK (lista de bloqueio, opt-out de negócio) são hashes de diretório sem relação.

---

### 6.2 Velocidade de mensagens

Found: `com.whatsapp.bizintegrity.logger.receiver.handler` (`C0236xdea74a22`, helper `N54`) conta mensagens localmente em um intervalo de tempo para uma lista de JIDs, com aliases SQL:
- `incoming_count`: mensagens com `from_me = 0`
- `incoming_threads_count`: `chat_row_id` únicos para mensagens recebidas
- `outgoing_count`: mensagens com `from_me = 1`
- `outgoing_threads_count`: `chat_row_id` únicos para mensagens enviadas
- Contagem de mensagens apagadas: `messages_count_after_privacy_token` (também `messages_count`, `outgoing_messages_count`) de `integrity_deleted_chat_message_count`

A feature flag 27269 controla se as mensagens recebidas/enviadas são contadas separadamente ou como um total combinado (found no mesmo handler).
Tamanho do lote: **975 JIDs** por chamada de processamento SQL (found: `C20H.A1A(list, 975)`, um chunk pelo limite de variáveis do SQLite, não um lote de rede).
Não localizado: agrupamento diário/por hora, taxa por contato; para onde as contagens vão depois de contadas não foi rastreado.

---

### 6.3 Limites de broadcast (contas comerciais)

Configuração de feature 20278: `{"max_messages": 10000, "farthest_time_days": 30}` (found como padrão em `C08J`/`C09W`).
- O limite de 10,000 mensagens por 30 dias é o padrão da configuração; o consumidor desse JSON (o código que o aplica antes de um envio, `renewal_date`, throttling por destinatário, classificação marketing vs. regular) não foi localizado: as strings de chave `max_messages`/`farthest_time_days` ocorrem apenas nas tabelas de padrões e `renewal_date` não ocorre em java_src.

---

### 6.4 Enforcement GAP (Global Abuse Prevention)

Found: `com.whatsapp.gapenforcement.triggers.GapEnforcementTrigger.A03` (`onMarketingMessageReceived`) é ignorado quando a feature flag 14837 está desligada, e armazena `LAST_MARKETING_MESSAGE_TIMESTAMP` em SharedPreferences (`C67902uK`) quando chega uma mensagem de marketing mais nova. A flag 25631 controla outro caminho de gatilho. A expansão "Global Abuse Prevention" não está no código (nomenclatura não verificada).

Estado rastreado (`ChatDescription`, found):
- `isEnterpriseBusiness` (Boolean)
- `isMarketingMessageThread` (Boolean)
- `sortTimestamp` (Long)
- `chatJid` (UserJid)

---

### 6.5 WaFA (Federated Analytics)

Found: pacote `com.whatsapp.federatedanalytics.impl` (`WaFaConfigFetcher`, `WaFaReportScheduler`, `FaReportRunner`, `WaFaReportSubmitter`, `FaTeeConnection`, `FaTeeAcsRepository`, `FaAcsWarmer`). Os relatórios passam por uma conexão TEE autenticada com ACS (headers `x-acs-token`, `x-acs-configid`, `x-acs-project-name`; busca de chave pública OHAI). Próximo horário de execução na pref `fa_next_report_run_timestamp`.
Não localizado: o conteúdo dos relatórios. A lista de métricas do relatório anterior (adoção de features, crashes, latência, RAM/armazenamento/SO, geofencing, dados de sessão, tipo de conexão) não foi encontrada como código; o conteúdo do relatório é guiado por configuração, então não pode ser lido a partir do cliente.

---

### 6.6 Extração de features de ML (detecção de golpes on-device)

Duas features concretas encontradas no cliente decompilado:
- `isCountryMismatch` (float 0.0/1.0): país do remetente ≠ país do destinatário → **HIGH RISK**
- `mostRecentSenderScore` (float): pontuação de reputação de ML do remetente

As feature flags 31535/31536 controlam seus valores (found). Resultados enviados ao servidor para pontuação secundária de ML (inferred).

---

## 7. Componentes de UI: Suspeito, Avisos, Banimento

(Reverificado na 2.26.41.6: `SpamWarningActivity` agora em `com.whatsapp.userban.spamwarning`, `SuspiciousFmxBottomSheetFragment` em `com.whatsapp.fmx` mais a nova subclasse `SuspiciousSmbFmxBottomSheetFragment`. As condições de disparo de 7.2, 7.4 e 7.5 estão corrigidas abaixo.)

### 7.1 SpamWarningActivity

Parâmetros do intent:
- `spam_warning_reason_key` (int): código do motivo
- `expiry_in_seconds`: contagem regressiva (-1 = permanente)
- `spam_warning_message_key`: texto customizado
- `faq_url_key`: link de FAQ

Códigos de motivo:

| Código | Significado |
|--------|-------------|
| 100 | Aviso geral de spam |
| 101 | Atividade de spam detectada |
| 102 | Violação de encaminhamento |
| 103 | Spam de status |
| 104 | Encaminhamento de bot |
| 105 | Geral / permanente |
| 106 | Outras violações |

Se `expiry_in_seconds != -1` → temporizador de contagem regressiva exibido.
Se `-1` + online → finaliza imediatamente (o servidor suspendeu o aviso).

### 7.2 Suspicious FMX Bottom Sheet (`SuspiciousFmxBottomSheetFragment`)

Found: uma folha informativa (links "learn more" `about-blocking-reporting`, `examples-of-scams`), não um bloqueador guiado por estado. É aberta ao tocar em um botão de estado suspeito no cartão FMX (`C93z.setupSuspiciousButtons`, a variante SMB `C94p` abre `SuspiciousSmbFmxBottomSheetFragment`) e a partir de `C512928n` (variante SMB quando o contato é um negócio, `A0T()`), via helpers `AbstractC61092ir.A00` / `AbstractC61102is.A00`.

As quatro condições de disparo do relatório anterior (`is_suspicious == 1`, `is_suspicious_start_chat == 1`, `is_reach_out == 1`, `chat_fmx_card_block_suspicious == 1` como bloqueio de envio) não são sustentadas: o próprio fragmento não lê nenhuma delas, e `chat_fmx_card_block_suspicious` é um nome de categoria de SpamFlow (4.8), não uma flag armazenada. O que foi encontrado: o contexto de início de chat é mostrado quando `is_suspicious_start_chat` é verdadeiro (`StartChatContextUtils`), e o cartão FMX calcula `"SUSPICIOUS".equals(trust_tier)` (`C94p`).

---

### 7.3 UI de Banimento Definitivo do WFAC

| Classe | Função |
|--------|--------|
| `WfacBanActivity` | Ponto de entrada, informações do banimento + botão de apelação |
| `WfacBanInfoFragment` | Detalhes da violação + link de apelação |
| `WfacBanDecisionFragment` | Ação do usuário (apelação enviada) |
| `WfacUnbanDecisionFragment` | Confirmação pós-apelação |

Gatilho (mudou): `Main.A5D()` não existe mais; seu equivalente é `Main.A5W()`, que lê `wfac_ban_state` no início (switch em "UNBANNED" / "BANNED" / "CHECKPOINTED", estado de registro 21, log "main/me/wfac ban") e inicia `WfacBanActivity` por meio de `HBC`. Nenhum listener de mudança de SharedPreferences foi encontrado. `wfac_ban_state` é escrito pelo handler de fetch do status de banimento e por `WfacBanActivity.onCreate` (2.3). O caminho de falha de login (403) abre a antiga `com.whatsapp.userban.ui.BanAppealActivity` (`HBB`) em vez disso. 2.26.41.6: classes agora em `com.whatsapp.waffle.wfac.ui` (também `WfacBanBaseFragment`); activity aberta via helper de intent `HBC` e transição de tela `I1T` (`transitionToScreen`).

### 7.4 Soft Enforcement de SMB

Mudou: o gatilho não é `is_suspicious=true` + `integrity_tags` contendo `"business_policy_violation"` (essa string não existe na 2.26.41.6). É uma notificação de negócio XMPP (handler `AnonymousClass142`, id de notificação 202) com filho `biz_integrity_warning_notification > violation`:

| Atributo | Uso |
|----------|-----|
| `source` | origem da violação (obrigatório) |
| `type` | tipo de violação, p. ex. `automation_bulk_messaging`, `spam` (comparado em `C35896FgX`) |
| `severity` | p. ex. `"severe"` altera o texto do banner (`C35896FgX`, `WABIEnforcementEducationFragment`) |
| `policy_url` | destino do link (obrigatório) |
| `priority` | int >= 0 (obrigatório) |
| `status` | `active` (armazenado, contadores zerados) ou `inactive` (removido) |

O cliente monta uma `SMBSoftEnforcementNotification` (`HAR`) com `notificationType` fixo em `"warning"` e `bannerNotificationTimeStamp` = hora de recebimento, e persiste um array JSON na preferência `smb_soft_enforcement_banner-all-json-<notificationType>` (`C35894FgV`) com as chaves abaixo. Os contadores por notificação são preferências int `smb_soft_enforcement_banner-<notificationType>-<source>-<severity>-<type>-total_days|click_count|dismiss_count`.

```json
[{
  "source": "...",
  "type": "automation_bulk_messaging",
  "severity": "severe",
  "notificationType": "warning",
  "policyUrl": "https://...",
  "status": "active",
  "bannerNotificationTimeStamp": 1700000000000,
  "priority": 1
}]
```

O JSON do relatório anterior (`notification_type: soft_enforcement`, `violation_type`, `education_url`, `action_required`) não está presente no cliente. UI: `SMBSoftEnforcementEducationFragment`, `WABIEnforcementEducationFragment` em `com.whatsapp.banner.softenforcementsmb`.

---

### 7.5 Cartão FMX (Cartão de Sinal de Confiança)

Found: uma mensagem de sistema do tipo 129 (`0x81`, `C57172Xr`) é criada em `C198788cr` ("Creating FMX card system message for chat", "ContactsProcessor/added contact info message"); a flag 19893 apenas controla ali um evento de analytics. A escrita assíncrona em `start_chat_trust_signals` é controlada por `C1P2.A01()` (flag não resolvida) e roda por `C65972r0`. O cartão (`C94p`) renderiza as contagens de curtidas do FB e de seguidores do IG e a flag de fricção do Meta Verified; `"SUSPICIOUS".equals(trust_tier)` seleciona a variante suspeita. A exibição da idade da conta e a condição de exibição de "contato comercial/desconhecido" não foram localizadas.

---

### 7.6 ODML Scam Alert (ML on-device)

Modelo de ML baixável via token ACS `"WA_ODML"` (encontrado em `OdmlModelDownloadClient`, `ODML_MODEL_DOWNLOAD`, id `27301080136160169`, TTL 345600 s = 4 dias; tamanho do cache 64 não localizado). Pode ser ativado/desativado pelo usuário via `ScamDetectionSettingsActivity`. O funil é rastreado via extras de intent de ID de sessão / origem / ponto de entrada.

---

## 8. XMPP e Stanzas (contexto de banimento)

(Reverificado na 2.26.41.6 lendo os handlers de login e de stream-error; a seção 8.1 está corrigida. Uma verificação anterior na 2.26.35.2 não viu push de banimento por XMPP; essa observação foi substituída pelo caminho de falha de login abaixo.)

### 8.1 O `<failure>` do login carrega banimentos e avisos

A afirmação anterior "bans come only via MEX GraphQL" está errada para eventos no momento da conexão. `HandlerThreadC12340b0.A13` lê o nó de resultado do login; para `<failure>` ele pega `reason` (int) e monta uma exceção `C45351tB` (found):

| `reason` | Tipo | Atributos lidos | Reação do cliente (`C0ZH.handleMessage`) |
|----------|------|-----------------|-------------------------------------------|
| 5xx | 4 | - | Erro do servidor, caminho de retry |
| 402 | 2 (padrão) | `code`, `expire`, `message`, `url`, `appeal_token`, `age_collection` | `SpamWarningActivity` com `spam_warning_reason_key` = `code` (>= 100), `expiry_in_seconds`, texto, url de FAQ |
| 402 + `appeal_token` + `code` 106 | 13 | idem | `ContextualAgeCollectionActivity` (extras `appealToken`, `expireTimeout`) |
| 402 + `appeal_token` + `code` 107 / `code` 109 | 14 / 15 | idem | Caminho "U13 Banned PAA Pending" (prefs de conta gerenciada, onboarding) |
| 403 | 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` | Banimento permanente: `HGB.startPermanentBanFlow` -> `BanAppealActivity` (após atraso da flag 19714 em ms) |
| 405 | 3 | `t` (segundos) | Escreve a pref `software_forced_expiration` |
| 406 | 5 | `code` | Pref `underage_account_banned` |
| 416 | 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` | `WfacManager.startUnderageBanFlow`; `violation_reason == "u13_checkpoint"` define `support_ban_appeal_user_banned_from_chat_disconnect` |
| outro | 0 | - | Logout (caminho "exception-password") |

Todos os tipos de falha também leem atributos opcionais de UI de logout: `logout_message_header`, `logout_message_subtext`, `logout_message_locale`, `logout_main_button_text`, `logout_main_button_url`, `logout_secondary_button_text`, `logout_secondary_button_url`. `location` é lido do nó para roteamento.

`<stream:error>` (interceptor de leitura companion, `C40601l6`): `code` 515 / 516, filho `conflict type="device_removed"` (deregister), filho `ack` (kick). Nenhum filho específico de banimento foi encontrado. `<presence type="unavailable">` e códigos de fechamento de WebSocket não foram examinados.

### 8.2 Tokens de erro XMPP (dicionário binário)

Dicionário `AbstractC40911lb` (byte único `A00`, byte duplo `A01`). Presença dos tokens da tabela anterior:

| String do token | No dicionário |
|-----------------|---------------|
| `stream:error` | yes |
| `conflict` | yes |
| `not-authorized` | yes |
| `item-not-found` | yes |
| `server-error` | yes |
| `401` | yes |
| `policy-violation` | not found |
| `403` | not found as a token (the `reason` value 403 is read as an int attribute) |

A coluna "Meaning" do relatório anterior (p. ex. `403` = "Forbidden (ban-related)") era inferred; apenas o significado de 403 agora é sustentado pelo tratamento de `<failure>` acima. Também no dicionário: `404`, `407`, `failure`, `locked`.

### 8.3 Respostas IQ para contas restritas

Não encontrado. Nem o namespace `urn:ietf:params:xml:ns:xmpp-stanzas` nem os textos "Account restricted" / "User banned" existem em java_src ou resources da 2.26.41.6, e nenhum token `forbidden` / `service-unavailable` está no dicionário. Os exemplos XML do relatório anterior não foram verificados e não devem ser considerados confiáveis (podem ser ilustrativos). O tratamento de erro por IQ (p. ex. parsers de `item-not-found`, `not-authorized` como `K3P`, `C23205A1e`) não foi rastreado para contas restritas.

---

## 9. Fluxo Completo de Dados (Ponta a Ponta)

(Reverificado na 2.26.41.6: doc_id `28596420510007620`, formato de entrada `query_input`, nomes de classe acima. As setas `isBanned` -> `wfac_ban_state` -> `Main.A5D()` do diagrama da 2.26.26.4 foram removidas porque não existe tal ligação no código; ver seções 1 e 2.3.)

```
[Open chat / send message]
           │
           ▼
  Check integrity_chat_info (is_reach_out?)
           │
           ▼
  Lookup start_chat_trust_signals (is_sender_suspicious? is_sender_new_account?)
           │
           ▼
  BizIntegritySignalsManager eligibility check — feature flag 11064
           │
    Flag active?
     YES │
         ▼
  BizIntegritySignalsGraphQLFetcher
    → HTTP/2 POST /mex/query
    → Variables: input{query_input:[{jid, privacy_token?}], telemetry{context:"INTERACTIVE"}}
    → doc_id: 28596420510007620
           │
           ▼
  Response → BizIntegritySignals DTO
           │
  wa_biz_integrity_signals (SQLite write, incl. is_banned, is_suspicious)
           │
    is_suspicious_start_chat? ──► start-chat context
    trust_tier == "SUSPICIOUS" ──► suspicious FMX card variant
           │                         └─► tap -> SuspiciousFmxBottomSheet (info only)
           ▼
  (is_banned: stored, no reader found)

  Separate path: XMPP login <failure reason=402|403|416> -> SpamWarningActivity /
  BanAppealActivity / WfacManager; WFAC state: Main.A5W -> WfacBanActivity
           │
           ▼
  [User submits appeal]
           │
           ▼
  Fetch purpose_public_keys (purpose_public_ek/ik/ik_sig, dummy ciphertext/nonce)
           │
           ▼
  Encrypt(form_data JSON {token, debug_info, description}, info "WA_INAPP_BAN_APPEALS", `C37414GLt`)
           │
           ▼
  Graph request to https://<host>.facebook.com/graphql by doc_id (section 10)
           │
           ▼
  Server review → wfac_ban_state update → WfacUnbanDecisionFragment
```

---

## 10. Requisição de Apelação (2.26.41.6)

Found em `C37414GLt`: o JSON `variables` da requisição carrega `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}` e `app_id` (`"dev.app.id"`); o texto simples antes da cifragem é `{token, debug_info, description}`; rótulo de contexto `"WA_INAPP_BAN_APPEALS"` (info de derivação de chave). Transporte (found, `AbstractC40195HfH`): um POST simples do Facebook Graph para `https://<host>.facebook.com/graphql` com `doc_id` e um campo `access_token`, não MEX. `C37414GLt` passa o `doc_id` **38509456535312323** quando `hg3.A04.A00()` é verdadeiro, caso contrário **5473316762755318**. O nome da operação `submitBanAppeal` não ocorre como string em java_src, smali, assets ou res da 2.26.41.6, e nenhum dos doc_ids está no catálogo de queries do projeto, então o nome não foi verificado. Antes do envio, `C40191HfD` interpreta uma primeira resposta com `data.purpose_public_keys{purpose_public_ek, purpose_public_ik, purpose_public_ik_sig, purpose_dummy_ciphertext, purpose_dummy_nonce}` que fornece o material de chave para a cifragem.

---

## 11. Mudanças em relação à 2.26.26.4

| Item | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| doc_id do BizIntegrityQuery | `25975613018777537` | `28596420510007620` (rotacionado na 2.26.38.10) |
| Formato da requisição | lista `$userJids` (reconstruída) | `input{query_input[{jid, privacy_token{tctoken,timestamp}}], telemetry{context}}` |
| Classe do DTO | `C39833Hhl` | `C51530MtC` (17 campos: + `isMetaVerified`, `fmxBusinessHoldoutGroup`) |
| `wa_biz_integrity_signals` | 14 colunas | + `is_meta_verified`, `fmx_business_holdout_group`; contagens REAL |
| Store / manager | `BizIntegritySignalsManager.A08/A01` | store `LwI`, schema `C53116Nmn`, manager A02 cache de memória de 60 s |
| leitor de start_chat_trust_signals | `C2M7.A0K` | `C57342Yp` |
| Enum de trust tier | não registrado, 7 valores | `M5B`, os mesmos 7 valores |
| Pacote de UI do WFAC | `com.whatsapp.waffle.wfac` (plano) | `com.whatsapp.waffle.wfac.ui` (+ `WfacBanBaseFragment`) |
| Prefs do WFAC | 5 chaves | + `wfac_last_ban_status_fetch_timestamp_ms` (throttle de refresh de 5 s), `support_ban_appeal_user_banned_from_chat_disconnect` limpa no reset |
| Parse do estado de banimento | 4 estados | igual; `NO_APPEAL_OPENED` mapeado para `CHECKPOINTED` |
| Flags | 11061/11064/11065/12709/16349/19893/26697/27269 | todas presentes; + 19793 (N5r.A02) |
| Códigos SpamWarning 100-106 | sim | inalterado |
| integrity_tags | `automation_bulk_messaging`, `spam` | inalterado |
| SpamFlow | 92 categorias | 97; `odml_scam_alert_*`, `biz_spam_banner_block`, outras adicionadas |
| Features de ML | `isCountryMismatch`, `mostRecentSenderScore` (31535/31536) | inalterado, em `integrityai.impl.InputFeatureProviderImpl` |
| Limite de broadcast 20278 | 10000 / 30 dias | inalterado |
| Eventos de banimento/aviso no momento da conexão | "no XMPP ban signalling" | `<failure>` do login XMPP: reason 402 (SpamWarning / U13), 403 (perm ban -> `BanAppealActivity`), 405, 406, 416 (WFAC underage); `C45351tB`, `C0ZH` |
| `Main.A5D()` | reage à mudança de `wfac_ban_state` | removido; `Main.A5W()` lê o estado no início (reg state 21) e abre `WfacBanActivity` via `HBC` |
| escritores de `wfac_ban_state` | não registrado | handler de fetch do status de banimento `C40191HfD`; `WfacBanActivity.onCreate` (CHECKPOINTED / BANNED / UNBANNED por origem de lançamento); sem ligação a partir de `is_banned` |
| Elegibilidade do BizIntegrity | "business accounts skip the check" | seleciona contatos SMB (nível `smb:`) ou `hostStorage == 2` (12709); caminho forçado 16349; sem divisão em chunks de 975 JIDs no fetch |
| lote de 975 | lote do GraphQL | chunk local de contagem de mensagens em SQL (`N54`) |
| Flag 12709 | whitelist no servidor | verificação local de `hostStorage == 2` |
| Flag 2923, carência de 24h pela idade da conta, composição do `dhash` | alegados | não encontrados na 2.26.41.6 |
| valores de `integrity_tags` | `automation_bulk_messaging`, `spam` | essas strings são valores de `type` da notificação de soft-enforcement de SMB, não de `integrity_tags` |
| Soft enforcement de SMB | tag `business_policy_violation` + JSON `notification_type`/`education_url` | XMPP `biz_integrity_warning_notification > violation{source,type,severity,policy_url,priority,status}`; chaves JSON armazenadas `source,type,severity,notificationType,policyUrl,status,bannerNotificationTimeStamp,priority`; flag 12840 |
| Índices/contagem do SpamFlow | 92, p. ex. `odml_scam_alert_bottom_sheet_block` = 65 | 97 entradas (`C9E2`), mesmos nomes em índices deslocados (70, 71, 76, 85, 89, 94, 96) |
| `SuspiciousFmxBottomSheetFragment` | aberto por 4 condições de dados | folha informativa aberta a partir de botões do cartão FMX / `C512928n` |
| Requisição de apelação | mutation MEX `submitBanAppeal` | Graph `https://<host>.facebook.com/graphql` por doc_id 38509456535312323 / 5473316762755318, precedida por um fetch de `purpose_public_keys`; nome da operação não encontrado |
| `wa_biz_integrity_chat_settings` | não localizada | encontrada (`AHY`) |
| Tokens de erro XMPP | tokens `policy-violation`, `403` | não estão no dicionário; `forbidden`/`service-unavailable` e os textos de 8.3 ausentes |

Ainda em aberto na 2.26.41.6: nomes de categoria por trás de `wfac_ban_violation_source` 0/1/2; consumidor da flag 20278 e da flag 12840; semântica do helper `N5r.A01`; conteúdo dos relatórios WaFA; tratamento de erro por IQ para contas restritas (8.3); exibição da idade da conta no cartão FMX; flag por trás de `C1P2.A01()`.
