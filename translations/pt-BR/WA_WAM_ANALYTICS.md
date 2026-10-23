<!-- src-sha1: c6955a2c041a57de36c902dfa247b0b65dc0b530 -->
# WhatsApp WAM Analytics — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** telemetria WAM ("WhatsApp Metrics") do Android — modelo de eventos (ids de evento, campos, canais REGULAR / REALTIME / PRIVATE / canal 3), pipeline de logging em Java, amostragem e pesos por evento, runtime nativo (`libwhatsapp.so`), atributos comuns, buffers em disco, formato wire do WAM, upload regular (IQ `w:stats`), upload privado (IQ de credencial + transporte separado), `wam_daily` e o cron diário, ids de private-stats e rotação, tratamento de privacidade, feature flags, famílias de eventos notáveis, comparação com Baileys, o que permanece desconhecido

---

## 1. O que é o WAM neste build

O WAM é um pipeline de métricas do lado do cliente: eventos tipados são criados em Java (ou convertidos a partir das estatísticas nativas de chamadas), amostrados, entregues a um runtime nativo que os serializa em buffers binários armazenados em `files/wam/`, e enviados ao servidor. É apenas telemetria de saída. Nada no protocolo de chat depende dele. Todas as afirmações vêm de análise estática do APK decompilado (`versionCode 264100600`), das strings nativas de `libwhatsapp.so` e do layout dos arquivos de buffer encontrados em um diretório de dados de app deste build. Tiers: **found** = lido no código ou em um arquivo de buffer, **inferred** = deduzido, **unknown** = não resolvível estaticamente. Os nomes ofuscados são específicos de cada build e foram re-resolvidos a partir de strings estáveis na 2.26.41.6 (strings de log, nomes de evento `wam_*`, valores de atributos de IQ).

| Entidade | Nome na 2.26.41.6 | Função |
|----------|-------------------|--------|
| Classe base de evento | `C0Fc` | `code`, `samplingRate`, `bufferChannel`, `psId`; `getFieldsMap()` abstrato (ids numéricos), `getFieldsMapForFalco()` (nomes), `getEventNameForFalco()`, `validate()` |
| Tupla de amostragem | `C036300x` | faixas de peso; `A00` é o peso usado pelo sampler |
| Resolvedor de amostragem | `C0Fg` + `C06580Fh` | override de peso por evento a partir do prefs `field-stats-events-sampling` |
| Logger (fachada do runtime WAM) | `C06650Fo` (`InterfaceC06640Fn`); `C40098Hdb` distribui para ele e para o logger Falco em Java `C40099Hdc` | `CNW` post, `CNI` post com amostragem, `CXW` flush, `CUj` reset, `CXZ` flush e espera (2500 ms); init em `RunnableC29323CoA` case 33 |
| Bridge JNI | `com.whatsapp.wamsys.JniBridge` | `jvidispatch*` Java para nativo, `jnidispatch*` nativo para Java |
| Atributos comuns | `C06590Fi` (`CYl(value, attrId, channel)`), init em `RunnableC29340CoR` case 0 | atributos globais por canal |
| Handler de AB-props | `C28894Cgv` | faz o parse de `<props>` incl. `event_code` / `sampling_weight` |
| Evento diário | `C0Fp` (`wam_daily`, id 1158) | estado do dispositivo e do app |
| Cron diário | `C28643Ccj` (`WamDailyEventDailyCron`), alarme em `BEL` (`DailyCronAction`) | monta e posta `C0Fp` |
| Evento de chamada | `com.whatsapp.fieldstats.events.WamCall` (id 462) | criado a partir das estatísticas nativas de chamada, postado por `C24895Anr` |
| Runtime nativo | `libwhatsapp.so` (`WAMRuntime`, `WAMBufferStore`, `WAMTransportRegular`, `WAMTransportPrivate`, `WAMPSIDProfile`) | buffers, ids, uploads |

Não é WAM, não confundir (ver 17): o logger shadow Falco do lado Java (`C40099Hdc`, `FFLogger`), o uploader de crash e logs marcado com `wam-event/<name>`, tokens ACS de outros projetos, e a palavra `fieldstats` usada pelas estatísticas nativas de chamada (`prepare_wa_call_fieldstats`).

Os sinais de integridade do cliente que viajam dentro do WAM (`is_rooted`, `is_genymotion`, `is_whatsapp_plus_user`, atributos 6251 e 10255) são descritos em [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) e apenas referenciados aqui.

---

## 2. Modelo de eventos

### 2.1 Classe de evento (`C0Fc`)

Todo evento é uma classe gerada; o construtor é `super(code, samplingTuple, bufferChannel, psId)`, p. ex. `wam_daily`: `super(1158, new C036300x(1, 1, 1, false), 0, -1)`, `getEventNameForFalco() = "wam_daily"`, `internalFalcoMigrationBatchNumber() = 12`.

| Membro | Significado | Tier |
|--------|-------------|------|
| `code` | id numérico do evento (1158 para `wam_daily`, 460 `wam_login`, 462 `wam_call`, 854 `wam_message_send`) | found |
| `samplingRate` | `C036300x(a, b, c, flag)` é armazenado como `A02=a, A01=b, A00=b, A03=c`; o sampler usa `A00 = b`. Padrão `C0Fc.DEFAULT_SAMPLING_RATE = (1, 20, 20)` | found |
| `bufferChannel` | 0..3, ver 2.2 | found |
| `psId` | `-1` = não privado; caso contrário, um hash de chave de private-stats, ver 2.3 | found |
| `getFieldsMap()` / `getFieldsMapForFalco()` | id numérico de campo para valor (passado ao nativo) / nome em snake_case para valor | found |
| `validate()` | lista de violações (`.nonnull` e regras semelhantes), ver 3.2 | found |
| `serialize(C3T8)` | o corpo é `throw new NullPointerException("serialize")`; a serialização é nativa | found |

Os campos usam tipos boxed do Java (`Boolean`, `Integer`, `Long`, `Double`, `String`). Enums e timers viajam como inteiros (inferred a partir do setter de atributo, que só aceita null / String / Integer / Long / Double / Boolean). `wam_daily` tem 218 slots numéricos e 205 slots nomeados (13 slots numéricos são somente null), idêntico à contagem anterior da 2.26.35.8.

### 2.2 Canais

| `bufferChannel` | Eventos (parseados) | Nome (rótulos inferred; o Java usa ints simples) | Tier |
|-----------------|---------------------|------|------|
| 0 | 824 | REGULAR | found |
| 1 | 8 | REALTIME | found |
| 2 | 168 | PRIVATE (requer um id de private-stats, ver 2.3) | found |
| 3 | 8 | private-stats realtime anônimo, "RTPS" nas strings de log nativas (rótulo inferred) | found / inferred |

Total parseado: 1.008 classes de evento com ids distintos. O mapeamento é passado sem alterações ao nativo (argumento de canal 0..3 de `jvidispatchIIIIIOO`). Qualquer outro valor lança `IllegalArgumentException("Unsupported channel type")`.

Eventos REALTIME (ids): 2098 `wam_ui_action_real_time`, 5504 `wam_wefr_client_exposure`, 5278 `wam_android_test_realtime`, 6640 `wam_wefr_group_client_exposure`, 6088 `wam_restore_contacts_realtime_event`, 4290 `wam_wa_fs_chat_transfer`, 2872 `wam_xplatform_migration_export`, 6266 `wam_cac_client_event` (found).

Eventos do canal 3: 5164 `wam_wam_test_anonymous_realtime`, 7312 `wam_mm_signal_undisclosed`, 7352 `wam_mm_signal_realtime`, 6160 `wam_wamo_video_event`, 6158 `wam_wamo_ctwa_1pd_conversion`, 7956 `wam_wamo_promo_pog_impression`, 5712 `wam_wamo_promo_reporting_events`, 7350 `wam_wamo_alv2_link_click` (found). `C06650Fo.A01` descarta um evento do canal 3, a menos que seu código esteja em dois arrays fixos no código (`AbstractC38512Gog.A00` 3 ids, `A01` 5 ids). Esses 8 ids são exatamente os 8 eventos do canal 3, portanto neste build a verificação não descarta nada (inferred a partir dos conjuntos de ids).

### 2.3 Ids de private-stats (`psId`)

| `psId` (int) | String de chave no arquivo de perfil nativo | Rotação (dias) | Eventos | Tier |
|--------------|---------------------------------------------|----------------|---------|------|
| `-1` | nenhuma (não privado) | – | 832 (regular + realtime) | found |
| `0` | `none` (o global de buffer 6005 contém a string `none`) | – | 94 (86 privados + 8 do canal 3) | found; mapeamento "none" inferred |
| `113760892` | `default_ps_id` | nunca (`-1`) | 66 | found |
| `56300709` | `id_pre_metrics` | nunca (`-1`) | 1 (`wam_ps_app_launch`) | found |
| `248614979` | `id_ttl_daily` | 1 | 4 | found |
| `42196056` / `191000728` | `id_ttl_weekly` / `id_ttl_monthly` | 7 / 30 | 0 | found |
| `37887164` | `id_ttl_90_days` | 90 | 1 (`wam_clock_skew_difference_t`) | found |
| `152546501` | `group_exit_experience_id` | 30 | 4 | found |
| `216763284` | `group_safety_check_id` | 30 | 6 | found |

As strings de chave e os dias de rotação foram lidos nos oito arquivos `WAMMetadataPSIDProfile-*` (ver 6.3), as contagens de eventos a partir das classes de evento.

### 2.4 Pesos no catálogo

Peso efetivo do schema `A00` por evento (o evento é mantido com probabilidade 1/peso e o peso é armazenado junto com o evento):

| Peso | Eventos | Membros típicos |
|------|---------|-----------------|
| 1 (sempre) | 826 | `wam_daily`, `wam_registration_complete`, `wam_blocking_funnel` |
| 5 / 10 | 6 / 12 | `wam_message_send` (5), `wam_message_context_menu_actions` (10), `wam_ui_action_real_time` (10) |
| 20 | 135 | `wam_message_delete_actions`, `wam_message_high_retry_count`, todos os eventos em `DEFAULT_SAMPLING_RATE` (81) |
| 100 / 200 | 4 / 2 | `wam_login_stage_reliability` (100) |
| 1000 | 17 | `wam_message_stanza_receive`, `wam_call_stanza_receive`, `wam_status_stanza_receive`, `wam_iq_send`, `wam_push_latency`, `wam_db_perf` |
| 10000 | 4 | `wam_receipt_stanza_receive`, `wam_android_profilo_usage`, `wam_android_message_target_perf`, `wam_notification_highlight_result` |

O peso não é um feature switch: o servidor pode sobrescrevê-lo por evento (8.2). Um evento com peso constante no build não foi classificado em nenhuma faixa.

---

## 3. Pipeline de logging em Java

### 3.1 Caminho de post

`CNW` = `CNI(event, null, false)`: resolve o peso (8.1), executa a allowlist do canal 3 (`A01`), depois executa o runnable `X.1Fc` no executor do WAM (`C06600Fj.A01`):

| Etapa | Comportamento | Tier |
|-------|---------------|------|
| Latch do runtime | `C06650Fo.A0K` (`CountDownLatch`) bloqueia o executor até os atributos comuns serem inicializados ("wamruntime/initializeCommonAttributes: runtime initialized") | found |
| Validação | `event.validate()` roda apenas para os canais 0 e 1 (não para a classe de evento de validação `C40251kT`). Cada violação vira um `wam_wam_validation_error_event` (id 5560) com o código do evento ofensor, um valor de sessão aleatório e as partes da regra unidas por `;` | found |
| Modos do logger (`A04`) | `3`: para códigos em um conjunto configurado, escreve `traceIdInt` (64 bits aleatórios) no evento por reflection; `10`: para eventos que passam por `C06630Fm` (lote de migração Falco 1..16, fora de uma deny list), escreve `dedupKey` (64 bits aleatórios); `1` / `3`: adicionalmente postam um evento Falco (`_test$<name>` / `<name>_shadow`) | found |
| Dispatch | `jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fieldsMap)` após garantir que a biblioteca está carregada | found |
| Gatilho de upload de logs | A prop AB string **31314** contém `"code:N;code:M"`; se `Random.nextInt(N)==0` para o código postado, pede-se ao reporter de crash e logs que envie os logs do dispositivo com a tag `wam-event/<falco name>`. Isso envia logs, não o buffer do WAM | found |

`dedup_key` e `trace_id_int` são campos do schema do evento (presentes em `wam_login`, `wam_app_launch`, `wam_message_send`); são aleatórios por evento e não são identificadores de usuário (inferred a partir do gerador).

### 3.2 Regras de validação

Em `C0Fp` (`wam_daily`), o campo `ai_widget_installed` é sempre reportado como violação porque nenhum membro Java o sustenta (regra `daily .nonnull`), e `default_after_read_enabled` quando seu membro é null. Consequência (inferred): todo evento diário no canal 0 também produz eventos de validação (id 5560).

### 3.3 Gatilhos de flush e ciclo de vida

| Gatilho | Chamada | Operação nativa | Tier |
|---------|---------|-----------------|------|
| Connection handler conectado | `C0A4.BvO` -> `CKt(0)` | `jvidispatchIIO(4, 0, ctx)` | found |
| Conectando / desconectado | `BvP`, `BvQ` -> `CKt(1)` | `jvidispatchIIO(4, 1, ctx)` | found |
| Processamento de mensagens offline concluído (`XmppStateManager/offlineProcessComplete`, também limpa `C0A2.A07`) | `BvR` -> `CXW(false)` somente com a prop AB **9654** | `jvidispatchIO(10, ctx)` (flush dos buffers ativos) | found |
| Flush explícito | `Bba()` -> `CXW(true)`; `CXZ()` faz flush e espera até 2500 ms | `jvidispatchIO(10, ctx)` | found |
| Fim de chamada | `C24895Anr.A02` posta `WamCall`, depois `Bba()` se a chamada estiver marcada ou com a prop AB **16047** | flush | found |
| Re-registro / remoção de conta | `C25100xS` ("RegistrationManager/reregister/rm-me") -> `CUj()` | `jvidispatchIO(12, ctx)` ("wamruntime/resetruntime") | found |

O argumento de estado 0/1 é o estado da conexão XMPP espelhado nos transportes nativos (string de log "wameta/transport/status - %d"). O significado de 0 = conectado é lido do mapeamento de callbacks, não do código nativo (inferred). Estados de `C0A2.A04`: 1 conectando, 2 conectado, 3 desconectado, 4 parado; `A07` é true desde a conexão até o processamento offline terminar, então `A0N()` significa "conectado e ainda drenando mensagens offline".

### 3.4 Superfície JNI

| Direção | Assinatura | Finalidade | Tier |
|---------|------------|------------|------|
| Java para nativo | `jvidispatchIOOOO(0, path, networkSession, ctx, config)` | inicializa o runtime (log "WAJContextInitWAMRuntime"), ver 4 | found |
| Java para nativo | `jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fields)` | registra evento | found |
| Java para nativo | `jvidispatchIIIOO(0, channel, attrId, String, ctx)` / `jvidispatchIIIO(4, channel, attrId, ctx)` / `jvidispatchIIIIO(1, channel, attrId, bool, ctx)` / `jvidispatchIIIDO` / variantes int, long | define atributo comum (null, string, boolean, double, integer) | found |
| Java para nativo | `jvidispatchIIO(4, state, ctx)` / `jvidispatchIO(10, ctx)` / `jvidispatchIO(12, ctx)` | estado da conexão / flush / reset | found |
| Java para nativo | `jvidispatchIOOOO(4, ctx, signedCredential, acsPublicKey, configId)` | resultado do IQ de credencial (tudo null em caso de falha) | found |
| Nativo para Java | `jnidispatchIO(6, byte[])` | envia um buffer regular como IQ `w:stats`, retorna 1 em `result` | found |
| Nativo para Java | `jnidispatchIO(7, byte[32])` | envia a requisição de credencial `privatestats` | found |

---

## 4. Inicialização do runtime

`RunnableC29323CoA` case 33 monta um mapa de configuração e chama o init nativo uma vez. O path é `<filesDir>/wam`.

| Chave de config | Prop AB | Tipo | Significado provável | Tier |
|-----------------|---------|------|----------------------|------|
| `platform_code` | – | int `2` | id da plataforma Android | found |
| `beacon_probability` | **6977** | int | probabilidade do status nativo de "beaconing" por evento (`WAMBeacon`) | found; significado inferred |
| `storage_size` | **9822** (x 1024) | long | limite de armazenamento de buffers (KiB para bytes); o nativo registra "no-enough-storage" e descarta eventos | found; unidade inferred |
| `buffer_timeout` | **12399** | int | timer de rotação de buffer | found; significado inferred |
| `throttling_percentage` / `throttling_exempt` | **9457** / **9456** | int / string | throttling de upload e lista de isenção | found; significado inferred, formato unknown |
| `enable_extra_logging` | **14310** | bool | logging nativo verboso | found |
| `enable_ps_upload_v2` | **15205** | bool (somente quando ativo) | "beginning upload v2 logic" nativo no transporte privado | found |
| `enable_aggregation` / `aggregation_config` | **11981** / **11982** | bool (somente quando ativo) / string | habilita `WAGAggregation` com suas regras | found; formato unknown |

A mesma chamada recebe um objeto `networkSession` criado por `C25810yb`; seu uso pelos wrappers HTTP nativos é inferred. Os valores padrão das props AB são entregues pelo servidor e não foram resolvidos.

---

## 5. Atributos comuns (globais)

Os atributos globais são escritos por `RunnableC29340CoR` case 0 via `C06590Fi.CYl(value, attrId, channel)` com os canais 0..3. Um helper define os quatro canais de uma vez; os demais definem apenas 0 e 1. Os canais privados (2, 3) recebem, portanto, um conjunto reduzido.

| Attr id | Origem do valor | Canais | Tier |
|---------|-----------------|--------|------|
| 3 / 5 | MNC / MCC extraídos de `TelephonyManager.getNetworkOperator()` (5 ou 6 dígitos, somente GSM) | 0 1 2 3 | found |
| 11 / 1659 / 1657 | código de plataforma `2` / código de plataforma `2` / constante `3` | 0 1 2 3 | found |
| 13 / 15 / 17 / 21 | `Build.MODEL-Build.MANUFACTURER` / `Build.VERSION.RELEASE` (ignorado com a prop AB **12637**) / versão do app `2.26.41.6` / `true` (flag de beta inferred; fixo no código neste APK beta) | 0 1 2 3 | found |
| 287 / 289 / 495 | `Build.MANUFACTURER` / `Build.MODEL` / uma string de dispositivo (não resolvida) | 0 1 | found |
| 655 / 689 / 2617 | métricas de memória e classe do dispositivo (`C38271gj`, `IJJ.A02/1048576`, `C38261gi`) | 0 1 2 3 | found; nomes inferred |
| 4473 | chave de config AB (`ab_key` da última resposta `<props>`, redefinida a cada atualização AB) | 0 1 | found |
| 5029 | ids de exposição a experimentos AB unidos por vírgula (`BxP`); com a prop AB **31830**, um mapa mesclado de `ab-props` e `ab-private-abprop` | 0 1; também presente em um buffer privado (canal 2) | found |
| 6251 / 10255 | verificação de assinatura do app / flag de instalador Play | 6251: 0 1 2 3; 10255: 0 1 | found, ver [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) |
| 12017, 12027, 14507, 15265, 15611, 23, 707, 7335, 13293, 23043 | valores variados de estado do app (12027 boolean do objeto de estado da conta, 707 `primary_platform_name` somente quando 12027 é true, 13293 = prop AB **3664**, 15611 constante WASafe (ver [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md)), 7335 `true` depois que os init hooks rodaram) | principalmente 0 1; 13293 todos os quatro | found; significados inferred ou unknown |
| 47 | commit time, int32 em segundos, adicionado nativamente | todos | found (arquivo de buffer) |
| 6005 | valor do id de private-stats (string UUID ou `none`), adicionado nativamente | buffers privados | found (arquivo de buffer) |
| 2795, 105 / 6833 | adicionado nativamente, somente buffers regulares / valor de `C21730rv`, somente canais 2 e 3 | 0 / 2 3 | found; significados unknown |

Nenhum número de telefone, JID ou id de conta está entre os atributos comuns escritos pelo Java. O transporte regular é vinculado à conta pela conexão autenticada por onde é enviado (inferred, ver 9).

---

## 6. Armazenamento nativo

As strings de `libwhatsapp.so` (`WAMBufferStoreImpl`, `WAMPSIDProfileStoreImpl`, `WAMPrivateCredentialStoreImpl`, `WAMMetadataStoreImpl`) e os arquivos de um diretório de dados instalado da 2.26.41.6 concordam.

### 6.1 Diretório `files/wam/`

| Arquivo | Conteúdo | Tier |
|---------|----------|------|
| `wamt-a-<channel>-0-<seq>` | buffer ativo, 65.559 bytes (pré-alocado, preenchido com zeros); uma string nativa `wamt-o` sugere buffers rotacionados (inferred) | found |
| `wam-metadata` | contêiner `MTD` v4 com contadores por canal; a próxima sequência armazenada para o canal 0 é igual à maior sequência de arquivo mais um | found; layout inferred |
| `WAMMetadataPSIDProfile-<n>-<keyHash>` | um perfil de private-stats por hash de chave (8 arquivos vistos) | found |
| `WAMMetadataPrivateCredential-<n>` | credencial armazenada para o transporte privado (`signed_credential`, chave, config id; v2, ~120 bytes) | found; layout inferred |

O terceiro número no nome do arquivo é um id de stream (log "wameta/buffer/rotated stream id: %d, channel: %d, buffer sequenceNumber: %d"; sempre `0` na amostra), o último é a sequência do buffer.

### 6.2 Layout do arquivo de buffer

```
off  0   "WMT" 03                      container magic, version 3
off  4   u32 LE  used length           = (end of used data) - 31   (checked in 2 files)
off  8   u32 LE  ?                     counter, meaning unknown
off 12   u32 LE  event count           equals the number of event markers decoded
off 16   u32 LE  ?                     close to the used length (+4, +6, +31 in samples)
off 20   u32     ?                     check value (inferred), algorithm unknown
off 24   "WAM" 05                      WAM header: magic + protocol version 5
off 28   u8  0                         flag byte (0 in all samples)
off 29   u16 LE  buffer sequence       equals the number in the file name
off 31   u8  channel                   0 regular, 2 private in samples
off 32   TLV entries                   globals first, then events
```

Found para todo byte listado com um valor; os campos marcados com "?" são unknown.

### 6.3 Perfil de private-stats

`WAMMetadataPSIDProfile-<n>-<keyHash>` (78 a 90 bytes), layout lido nos oito arquivos:

```
u8 version(2) │ i32 LE keyHash │ i32 LE rotationDays │ u8 ? │ float64 LE (timestamp, inferred) │ u32 ? (1) │
u32 keyLen │ u32 uuidLen(36) │ key string (e.g. "id_ttl_daily") │ UUID string
```

Dias de rotação lidos nos arquivos: -1 (`default_ps_id`, `id_pre_metrics`), 1, 7, 30, 30, 30, 90 (ver 2.3). As strings nativas nomeiam as operações `WAMPSIDProfileRotatePSID`, "psid delegated rotation was not persisted" e verificações de corrupção (`invalid rotationInDays`). O UUID é o que vai no global 6005 dos buffers privados. Se a rotação é guiada pelo horário local ou pelo servidor é unknown.

---

## 7. Formato wire do WAM

Confirmado em buffers reais: um decoder escrito a partir do esquema de tags abaixo fez o parse dos globais e eventos de dois buffers (regular e privado) sem sobras.

### 7.1 Codificação de entrada

Cada entrada é `[tag][field id][payload]`.

| Parte | Codificação | Tier |
|-------|-------------|------|
| Nibble baixo da tag | papel: `0` global, `1` marcador de evento, `2` campo; OU `0x04` último-do-grupo; OU `0x08` o field id é `u16 LE` em vez de `u8` | found |
| Nibble alto da tag | tipo do valor: `0x00` null, `0x10` int 0, `0x20` int 1, `0x30` int8, `0x40` int16 LE, `0x50` int32 LE, `0x60` int64 LE, `0x70` float64 LE, `0x80` string (comprimento u8), `0x90` string (comprimento u16 LE), `0xA0` string (comprimento u32 LE) | found para int 0/1, int8, int16, int32, string u8 e u16 (todos decodificados a partir de buffers); os demais são inferred a partir do esquema e do encoder do Baileys |
| Inteiros, strings, ordem de bytes | menor forma de inteiro (0 e 1 ficam na tag); strings UTF-8; little-endian em todo lugar (o codec de stanza é big-endian) | found |

### 7.2 Marcador de evento

Um marcador de evento tem papel `1` com o id do evento como field id. Seu valor é o peso de amostragem, armazenado positivo nos buffers: eventos com peso de schema 20 (`wam_secure_file_usage`, `wam_whatsapp_quick_promotion_client_eligibility_waterfall`) carregam 20, eventos com peso 1 carregam 1 (found). Os campos seguem com papel `2` (a flag de último campo `0x04` não foi verificada). Um bloco global (papel `0`) é escrito quando os atributos mudam, então os globais se repetem entre eventos (o commit time 47 é reescrito muitas vezes, found).

O payload do IQ tem de 4 a 126.976 bytes (9). Que ele seja igual ao buffer a partir do offset 24 (do header `WAM` em diante) não é demonstrado pelo código; é inferred a partir do layout e do fato de o Baileys enviar o mesmo header (15).

---

## 8. Amostragem e pesos por evento

### 8.1 Resolução (`C0Fg.A00`, simplificada)

```
override = prefs(code == 1094 ? "app_launch_event_sampling_weight" : "field-stats-events-sampling"[code], 0)
weight   = override != 0 ? override : schema.A00         // sampler becomes (|w|,|w|,|w|,|w|) for an override
keep     = random.nextInt(sampler.A00) == 0              // 1-in-N; null return = "(dropped)"
```

| Item | Valor | Tier |
|------|-------|------|
| Overrides locais | arquivo de prefs `field-stats-events-sampling` (chave = código do evento) e `app_launch_event_sampling_weight` (evento 1094); peso 1 é sempre mantido | found |
| Guarda nativa | "wameta/logger event weight exceeds max, dropped"; o limite é nativo | found; valor unknown |
| Amostragem por chamada | `WamCall`: o campo `logSampleRatio` (id 1120) do evento decide o peso, `new C036300x(i, i)` | found |

### 8.2 Entrega pelo servidor (resposta de AB props)

`C28894Cgv.CFS` trata o resultado de AB-props (nó `<props>`). Cada filho `<prop>` é uma config prop ou uma entrada de amostragem de evento:

```
<props ab_key hash refresh refresh_id delta_update>
  <prop config_code config_value config_expo_key/>    -> ab-props
  <prop event_code="854" sampling_weight="5"/>        -> field-stats-events-sampling
</props>
```

Quando `hash` não está vazio, os prefs de amostragem são limpos e reescritos a partir de todos os pares `event_code`/`sampling_weight`; a entrada 1094 também escreve `app_launch_event_sampling_weight` (e a remove quando ausente). Portanto o servidor controla os pesos por evento, e os pesos são enviados de volta com cada evento para que o servidor possa escalar as contagens (inferred a partir do campo que viaja com o evento; uso no servidor unknown).

O servidor, portanto, molda o WAM por meio de AB props, pesos de amostragem e da credencial privada; nada é empurrado no próprio IQ de upload (o IQ só recebe `result`).

---

## 9. Upload regular (`w:stats`)

O nativo chama `JniBridge.jnidispatchIO(6, bytes)`. O Java monta e envia:

```
<iq xmlns="w:stats" to="s.whatsapp.net" type="set" id="..">
  <add t="<unix seconds>">[binary: WAM buffer]</add>
</iq>
```

| Item | Valor | Tier |
|------|-------|------|
| Transporte | o stream de chat autenticado normal (`C10140Tq`), igual a qualquer IQ | found |
| `t`, limites, timeout | `t` = segundos unix atuais (adicionado apenas dentro de 1.577.865.600..4.102.473.600); payload verificado contra 4..126.976 bytes; timeout do IQ de 32.000 ms (espera síncrona) | found |
| Sucesso | atributo de resposta `type == "result"` -> contabilização `C0VI.A02(len, 32)`, retorna 1 | found |
| Falha | outro type ou interrupção -> log "FieldStatsXmppImpl/error sending fieldstats IQ", retorna 0 (o nativo decide os retries; "_WAMTransportManagerUploadFailedPermanently" existe) | found |
| Adiado durante uma chamada | retorna 0 com o log "WamJniBridge/upload postponed" se uma chamada estiver ativa, a menos que a prop AB **15507** esteja ligada, ou a chamada seja em grupo e a prop AB **468** esteja ligada | found (fluxo do decompilador, padrão da flag de grupo assumido como false) |
| Adiado durante o processamento offline | retorna 0 se `C0A2.A0N()` (conectado e mensagens offline ainda não drenadas) e a prop AB **9654** estiver ligada; com 9654 desligada o IQ é enviado | found |
| Vínculo com a conta / compressão | nenhum id de conta no payload, o servidor vê a sessão autenticada; sem compressão no caminho Java | inferred / found |

A mesma prop 9654 habilita o flush em `offlineProcessComplete` (3.3). Em conjunto: com 9654 ligada, os uploads esperam até a fila de mensagens offline ser drenada e um flush roda nesse momento (inferred a partir dos dois pontos de chamada; o timing de retry após uma tentativa adiada é nativo e unknown).

---

## 10. Upload privado

Os canais privados (2 e 3) não são enviados como `w:stats`. O `WAMTransportPrivate` nativo envia por um transporte HTTP separado (`WCIHTTPImpl`) com uma credencial anônima. Tudo abaixo vem de strings de log nativas e do handler de credencial em Java.

### 10.1 Requisição de credencial

```
<iq xmlns="privatestats" to="s.whatsapp.net" type="get" id="..">
  <sign_credential version="1">
    <blinded_credential>[32 bytes]</blinded_credential>
  </sign_credential>
</iq>
```

| Parte | Detalhe | Tier |
|-------|---------|------|
| Remetente | `JniBridge.jnidispatchIO(7, byte[32])`; o código de erro no tracker de IQ é 239, timeout de 32.000 ms | found |
| Resposta (`KRL.CFS`) | `<sign_credential t=..><signed_credential/><acs_public_key/><config_id/></sign_credential>`; os três arrays de bytes são entregues ao nativo com `jvidispatchIOOOO(4, ctx, ...)`; em caso de erro ou sem resposta o nativo recebe nulls | found |
| Telemetria | evento 2242 `wam_sign_credential` (canal regular) com status 3 = falha, 1 = sucesso, e tempo decorrido | found |
| Verificação e armazenamento | strings nativas "Invalid signature received from server", "fails validation" (o cliente valida a assinatura); armazenada em `WAMMetadataPrivateCredential-<n>`, renovada em 401 ("send failed, renew credentials") | found |
| Esquema | requisição cegada (blinded), resposta assinada, chave pública ACS: uma credencial anônima, de modo que a credencial não vincula os uploads privados à conta | inferred |

Um sender genérico separado `C1N8` usa o mesmo namespace com `<sign_credential version="2">` e `project_name` para outros projetos ACS (prefs `acs_token_*`); não é o caminho do WAM.

### 10.2 Upload

| Item | Detalhe | Tier |
|------|---------|------|
| Endpoints | logs nativos "url/received", "fetch_endpoints/custom_endpoints - got endpoints: %d", "invalid_ps_endpoint, ignoring"; nenhum literal de URL em Java nem em `libwhatsapp.so` | found; origem da lista unknown |
| Tratamento de falhas e timer | "try next endpoint", "have next credentials", "401, no more endpoints"; timer do transporte ("timer/started - interval: %.1f seconds") iniciado em "connection_ready", parado em "connection_unavailable" | found; intervalo unknown |
| Realtime privado | buffers por evento: "create_buffer/realtime/buffer-created ... event id", "sendsingleeventimpl/realtime" | found |
| Headers, framing do corpo, compressão | não visíveis | unknown |

O logger Falco `C40099Hdc` com modo 9 descarta de seu próprio caminho eventos com canal 2 ou 3 ou com um psId e os conta como `wa:dropped_private_stats` (found), portanto os eventos privados não são duplicados nesse logger (inferred).

---

## 11. `wam_daily` e eventos periódicos

Id de evento 1158, nome Falco `wam_daily`, canal 0, peso 1, 218 campos numéricos / 205 nomeados. Para os campos de root, emulador, custom-ROM e mod-client, ver [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md); aqui só se registra a infraestrutura.

### 11.1 Agendamento (found)

| Peça | Detalhe |
|------|---------|
| Alarme | `BEL.A01`: próxima meia-noite local + jitter aleatório `nextInt(AB prop 5529)` (unidade convertida por `C20D.A02`), ação `com.whatsapp.action.DAILY_CRON` |
| Catch-up | ação `com.whatsapp.action.DAILY_CATCHUP_CRON`, repetida a cada 15 minutos enquanto "last_daily_cron" não for de hoje |
| Guarda | ignora com "too frequent" se o cron já rodou hoje (pref `last_daily_cron`); ignora todos os crons enquanto uma transferência de chat está em andamento; crons que precisam do message store são ignorados quando ele não está pronto |
| Executor | itera um conjunto DI de crons `InterfaceC29983D2n` (`Bo5`); `C28643Ccj` (tag `WamDailyEventDailyCron`) roda somente quando `anonymousClass091.BS3()` (estado da conta, significado não resolvido) |

### 11.2 Preenchimento

`C28643Ccj.Bo5` cria `new C0Fp()`, chama `C4k(C0Fp)` em cada populator de um conjunto DI (28 arquivos definem um populator `C4k(C0Fp)`), depois `CNW(c0Fp)` com o peso padrão do schema. O populator de flags do dispositivo existe somente em smali neste build (`smali_classes7/X/Cdt.smali`; o decompilador falha nele) e lê e escreve o pref `last_daily_event` (ms de relógio de parede), atribuindo `time_delta_since_last_event`. O branch decompilado altera o delta apenas de 0 para 1, portanto nenhuma afirmação de unidade ou cadência é feita para esse campo. `last_daily_event` não é o agendador (o alarme em 11.1 é).

O mesmo cron emite um evento somente Falco `wam_daily_permission` (amostrado): status da permissão de contatos, permissão de galeria, concessões de câmera / gravação de áudio / localização aproximada e precisa, configuração de notificação do SO, tamanhos da agenda de endereços, contagens opcionais de threads (prop AB **25576**) e `profile_photo_is_set` (prop AB **34207**), `os_version` (found).

### 11.3 Outros eventos periódicos

Outros eventos de início do app e periódicos: 1094 `wam_app_launch` (peso sobrescrevível por `app_launch_event_sampling_weight`), 3300 `wam_ps_app_launch` (privado, `id_pre_metrics`), 3178 `wam_clock_skew_difference_t` (privado, `id_ttl_90_days`), a família `*_daily` (5798 `wam_reaction_daily`, 3680 `wam_polls_daily_stats`; gatilhos inferred).

---

## 12. Tratamento de privacidade

| Aspecto | Achado | Tier |
|---------|--------|------|
| Ids estáveis em lotes | nenhum JID ou número de telefone nos atributos comuns escritos pelo Java; `dedup_key` e `trace_id_int` são aleatórios por evento; o canal regular é autenticado pelo stream em que viaja | found / inferred |
| Ids de private-stats | UUID por chave em `WAMMetadataPSIDProfile-*`, global 6005 nos buffers privados; rotação de 1, 7, 30, 90 dias ou nunca | found |
| Credencial anônima | token cegado (blinded) assinado pelo servidor para uploads privados (10.1) | found; não vinculabilidade inferred |
| Ids com hash e em texto puro | existem campos de id com hash (`hashed_blocked_conversation_jids`, `hashed_reported_conversation_jids`, `message_key_hash`, `invited_user_hash`; função de hash não rastreada); também existem strings do tipo JID (`reported_jid`, `e2e_sender_jid`; hash antes do logging não rastreado) | found (nomes), unknown |
| Reset | remoção de conta e re-registro chamam o reset nativo (`jvidispatchIO(12)`); um reset dos perfis PSID por ele não é demonstrado | found / unknown |
| Opt-out do usuário | nenhuma configuração, string ou flag encontrada que desabilite o WAM; a única string semelhante a consentimento nos recursos diz respeito a diagnósticos de suporte. Pode existir uma configuração em caminhos de código não pesquisados | unknown |
| Controle do servidor | pesos por evento (8.2), AB props (13), configuração `throttling_*` e `beacon_probability` (4); os algoritmos são nativos | found; unknown |

---

## 13. Feature flags (AB props conforme lidas nos caminhos de código acima)

| Prop | Tipo | Controla |
|------|------|----------|
| **9654** | bool | flush na conclusão do processamento offline (3.3); upload adiado enquanto as mensagens offline estão sendo drenadas (9) |
| **15507** / **468** / **16047** | bool | upload não adiado durante uma chamada / durante uma chamada em grupo / flush após eventos de chamada |
| **6977**, **9822**, **12399**, **9457**, **9456**, **14310**, **15205**, **11981**, **11982** | misto | chaves de config de init do runtime (seção 4) |
| **31314** | string | taxa de gatilho de upload de logs `"code:N;..."` por código de evento |
| **5529** | int | jitter do cron diário |
| **12637** | bool | ignora os atributos de versão do SO, fabricante e correlatos (15, 287, 21, 12027, 707) |
| **31830** / **25576** / **34207** | bool | lista AB privada mesclada no atributo 5029 / campos opcionais de `wam_daily_permission` |
| **34494..34507, 35169, 35170** | – | array em `AbstractC38513Goh.A01` (16 ids, mesma contagem dos lotes de migração Falco 1..16); uso inferred |

Todos os valores são atribuídos pelo servidor; os padrões não foram resolvidos.

---

## 14. Famílias de eventos notáveis

Os nomes são nomes Falco; ids e canais vêm das classes de evento. As listas de campos são os campos nomeados de `getFieldsMapForFalco()`.

### 14.1 Mensagens

| Evento | id | Canal / peso | Campos notáveis |
|--------|----|--------------|-----------------|
| `wam_message_send` | 854 | 0 / 5 | 89 campos: `message_send_result`, `message_send_t`, `message_type_str`, `e2e_ciphertext_type`, `e2e_ciphertext_version`, `is_pq`, `is_lid`, `retry_count`, `resend_count`, `message_is_forward`, `message_is_fanout`, `message_distribution_type`, `participant_count`, `device_count`, `message_key_hash`, `is_view_once`, efemeridade, edição/revogação, campos de bot e de IA privada |
| `wam_message_receive` | 450 | 0 / 20 | 58 campos: `message_receive_t0..t2`, `message_queue_time`, `message_is_offline`, `offline_count`, `stanza_process_count`, `padding_bytes_size`, `message_addressing_mode`, `server_addressing_mode`, `session_scope`, campos de sticker e de cartão de contato |
| `wam_e2e_message_send` / `_recv` | 476 / 478 | 0 / 20 | `e2e_successful`, `e2e_failure_reason`, `e2e_destination`, `group_encryption_state`, `enc_retry_count`, `pq_receive_gate_state` |
| `wam_e2e_message_decrypt_fail_sender` | 3524 | privado (ps `none`) | `e2e_sender_jid`, `e2e_failure_reason`, `retry_count` |

### 14.2 Chamadas

`WamCall` (id 462, canal 0) é criado a partir das estatísticas nativas (`ConvertFieldStats`, "can not construct com/whatsapp/fieldstats/events/WamCall") e tem aproximadamente 1.700 campos nomeados (1.716 sites `put` no mapa Falco). `WamJoinableCall` é o id 2572. A amostragem é `logSampleRatio` (campo 1120), e o evento sofre flush no fim da chamada (3.3). Outros eventos de chamada: 2582 `wam_call_stanza_receive` (peso 1000), 3452 `wam_call_critical_events`, 4568 `wam_call_user_journey`. A sinalização de chamadas em si está em [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md).

### 14.3 Login e registro

| Evento | id | Campos |
|--------|----|--------|
| `wam_login` | 460 | `login_result`, `login_t`, `connection_origin`, `connection_t`, `login_dns_resolver`, `login_ip_source`, `login_port`, `login_resolved_pop`, `login_socket_provider`, `noise_protocol_version`, `retry_count`, `server_error_code`, `passive`, `long_connect`, `network_is_vpn`, `android_keystore_state`, `pending_acks_count`, `unprocessed_message_count` (30 slots); ver [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) |
| `wam_reg_init` / `wam_registration_complete` | 2046 / 1342 | tempos de init (`contacts_sync_t`, `groups_init_t`, `total_t`); 30 campos incl. `registration_t`, `addressbook_size`, `contacts_permission_authorization_status`, `device_identifier`, `google_account_list_hashed_reg`, `invited_user_hash`, `is_new_jid`, campos de foto de perfil e de permissões |
| `wam_account_encryption_attestation` | 8164 | o nome sugere o resultado de uma attestation (inferred); ver [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) |

### 14.4 Spam, denúncia, bloqueio

Os fluxos estão em [WA_REPORTING.md](WA_REPORTING.md) e [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) (`wam_wfacp_ban_action`, id 5028); lado WAM:

| Evento | id | Canal | Campos |
|--------|----|-------|--------|
| `wam_spam_report_perf` | 6310 | 0 | `report_spam_flow`, `report_status`, `report_attempt_count`, `report_duration_ms`, `report_error_code` |
| `wam_report_conversation_context` | 4608 | 0 | `reported_jid`, `spam_flow`, `estimated_num_messages_sent/received`, `is_chat_maybe_suspicious`, `is_in_addressbook`, `first_entry_point`, `num_call_msgs_to_report` |
| `wam_blocking_funnel` / `wam_reporting_funnel` | 4920 / 4924 | 0 | `block_flow_action`, `hashed_blocked_conversation_jids`, `hashed_reported_conversation_jids` |
| `wam_reporting_token_validation_failure` | 5466 | 0 | `reporting_token_validation_failure_reason`, `reporting_token_version`, `is_part_of_group_history` |
| `wam_reporting_token_validation_failure_sender`, `wam_reporting_token_additional_client_validation` | 6094, 6702 | 2 (`default_ps_id`) | variantes do lado do remetente |
| `wam_message_template_blocks` | 3002 | 2 (`default_ps_id`) | motivos de bloqueio de template de negócio |

### 14.5 Experimentos

`wam_wefr_client_exposure` (id 5504, realtime) registra a exposição com `exposure_key`, `device_exp_id`, `user_lid`, `guest_id`, `is_canonical_ent_present`, `sent_with_daily`. Ele carrega um campo de LID do usuário (found; uso no servidor unknown). `wam_ui_action_real_time` (2098, peso 10) carrega apenas `chatd_internet_connectivity` e `dedup_key`.

---

## 15. Baileys (`baron-baileys-v2`, comparado com seu código-fonte)

O Baileys envia buffers WAM com o mesmo IQ do cliente Android.

| Aspecto | Baileys (`src/Socket/socket.js`, `src/WAM/encode.js`) | Android 2.26.41.6 | Tier |
|---------|--------------------------------------------------------|-------------------|------|
| Stanza de upload | `<iq to=s.whatsapp.net xmlns="w:stats" type="set"><add t=…>buffer</add></iq>` | igual | found both |
| Header | `"WAM"`, byte de versão 5, byte 4 = `1`, sequência `u16 BE` em 5, canal `0` em 7 | `"WAM"`, versão 5, byte 4 = `0`, sequência `u16 LE` em 29, canal em 31 (no arquivo com um contêiner `WMT` na frente) | found both |
| Codificação de valores | `0/1` na tag, int8, int16/int32 LE, float64 LE, strings com comprimento u8/u16 LE/u32 LE, flag de id largo `0x08` | mesmos bits | found both |
| Peso do evento | escrito como `-weight` | armazenado positivo nos arquivos de buffer | found both |
| Canais, flush | somente regular; flush a cada 30 s e após o login, falhas apenas registradas em log | 0..3; rotação e transportes nativos | found |

A diferença na ordem de bytes da sequência e no sinal do peso não é um erro comprovado por este relatório: os arquivos em disco do Android não precisam ser iguais aos bytes que o transporte nativo envia, e o parser do servidor não foi observado. Nada nos caminhos de código de chat lidos aqui espera pelo estado do WAM; se o servidor reage a um upload ausente ou incomum é unknown (19).

---

## 16. Casos de erro

| Sintoma | Causa | Correção / nota |
|---------|-------|-----------------|
| Evento ausente nos buffers | sorteio do peso falhou (1-in-N), allowlist do canal 3, limite de armazenamento, "weight exceeds max" nativo, "have to drop event" | verificar o peso em 2.4 e as AB props em 8.2, 4 |
| Evento diário produz eventos de validação | a regra `ai_widget_installed` falha para todo `wam_daily` (3.2) | esperado neste build |
| "WamJniBridge/upload postponed" | chamada ativa sem 15507 / 468, ou fila offline ainda sendo drenada com 9654 | transitório; o nativo tenta novamente (inferred) |
| "FieldStatsXmppImpl/error sending fieldstats IQ" | erro de IQ, timeout (32 s) ou interrupção | retry nativo / caminho de falha permanente |
| "Cannot log before WAM runtime is initialized" / "after ... terminated" | ordem do ciclo de vida nativo | o Java espera em `A0K`; terminate é um estado nativo |
| Upload privado falha com 401 | credencial rejeitada | renovar via IQ `privatestats` (10.1) |

---

## 17. Distinções-chave

| Par | Diferença |
|-----|-----------|
| WAM vs Falco | os eventos WAM passam pelo runtime nativo e pelos buffers; o logger Falco em Java (`C40099Hdc`, `FFLogger`) é um caminho paralelo que reutiliza as mesmas classes de evento pelo nome Falco. O lote de migração Falco 1..16 é por evento (`internalFalcoMigrationBatchNumber`) |
| Peso do evento vs feature flag | peso = amostragem 1-in-N e um multiplicador enviado com o evento; as flags apenas controlam o comportamento do transporte |
| Upload regular vs privado | regular = IQ `w:stats` no stream de chat; privado = transporte HTTP separado com uma credencial cegada (blinded) |
| `psId` vs global 6005 | `psId` é um hash de chave estático na classe do evento; 6005 é um UUID rotativo escrito nativamente nos buffers privados |
| Field id vs global id | os espaços numéricos se sobrepõem (47 é um global; o campo 47 de um evento é diferente); o papel da tag desambigua |
| `wam-event/<name>` vs upload WAM | o primeiro envia logs do dispositivo pelo reporter de crash, o segundo envia buffers de métricas |
| Buffer em disco vs payload wire | o arquivo tem um contêiner `WMT` e padding; o layout do payload do IQ é inferred |

---

## 18. Fluxo completo

```
[App code / native call stats]  new Event(...) / ConvertFieldStats -> WamCall
    ▼
[C06650Fo.CNW / CNI]  weight = override (prefs) or schema A00, keep 1-in-N ; validate (ch 0,1) -> event 5560
    ▼
[WAM executor]  jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fields)
    ▼
[libwhatsapp.so WAMRuntime]  encode TLV (LE), add globals (47 commit time, 6005 psId UUID, common attrs)
    ▼
[files/wam/wamt-a-<channel>-0-<seq>]  "WMT" container + "WAM" 5 header, 64 KiB
    │  rotate (buffer_timeout) / flush (offline-complete with 9654, Bba, call end, CXZ)
    ├── channel 0, 1 ─────────────────────────────┬── channel 2, 3 ───────────────────────────────┐
    ▼                                             ▼                                              
jnidispatchIO(6, bytes)                       jnidispatchIO(7, 32 bytes blinded token)
    │  postponed in calls / offline drain          │  <iq xmlns="privatestats" type="get">
    ▼                                             ▼
<iq xmlns="w:stats" type="set"><add t=..>     [WA server] signed_credential, acs_public_key, config_id
  bytes</add></iq>  on the chat stream              │  stored, renewed on 401
    ▼                                             ▼
[WA server] type="result" -> return 1         HTTP upload, endpoint list source unknown -> [private-stats backend]

[WA server] <props> response: event_code -> sampling_weight, config_code -> AB props  ──►  prefs (8.2)
[DailyCronAction alarm: next local midnight + jitter(5529)] -> C28643Ccj populates C0Fp (wam_daily 1158) -> CNW (same path, channel 0)
```

---

## 19. Desconhecidos

| Pergunta | Por que é unknown |
|----------|-------------------|
| Bytes exatos do payload de upload versus o arquivo de buffer | transporte nativo não desmontado; apenas os limites do IQ foram vistos |
| Compressão e framing de header dos uploads privados, origem da lista de endpoints | nenhum literal em Java nem nas strings; caminho HTTP nativo não rastreado |
| Intervalo de rotação nativo, agenda de retry, máximo de peso, regras de descarte, algoritmo de beaconing | código nativo stripped, sem decompilador para a biblioteca grande usada aqui |
| Significado dos atributos 495, 6833, 2795, 105 e de vários atributos de flag; campos `WMT` nos offsets 8, 16, 20; campos `MTD` | origens não resolvidas, apenas valores |
| Se algum comportamento do servidor depende de WAM ausente ou incomum | lado do servidor |
| Hash dos campos `*_jid`; existência de um opt-out visível ao usuário | não rastreado por evento / não encontrado (ausência não é prova) |
| Timing de retry nativo, gatilho de rotação de PSID (horário do cliente ou instrução do servidor), padrões das AB props | lógica nativa não rastreada; os padrões vêm da config do servidor |
| Gatilho de crons diários além de `wam_daily` | apenas o registro de crons e o cron de `wam_daily` foram lidos |
