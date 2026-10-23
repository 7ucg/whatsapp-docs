<!-- src-sha1: 84ea5bd809c6118cf8363e58c56bee3ba607d23e -->
# WhatsApp Sistema de Bloqueo — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-17
**Alcance:** Flujo de bloqueo, ciclo de vida de WFAC, recolección de señales de spam, protocolo GraphQL, sistema de apelación, marcado como sospechoso, prevención

---

## 1. Visión general de la arquitectura

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

**Hallazgo crítico (corregido en 2.26.41.6):** la sincronización del estado de bloqueo (WFAC) es **pull-based sobre MEX GraphQL**, pero los *eventos* de bloqueo y advertencia al momento de conectar llegan por XMPP en el nodo `<failure>` del login (reason 402/403/416/406, sección 8.1). La advertencia de soft-enforcement de SMB es una notificación de negocio XMPP. No se encontró señalización de bloqueo mediante `<stream:error>` (ese handler solo trata `code` 515/516, `conflict type="device_removed"` y expulsiones por `ack`).

---

## 2. Ciclo de vida del estado de bloqueo (WFAC)

### 2.1 Máquina de cuatro estados

| Estado | Valor | Significado |
|-------|-------|---------|
| `UNKNOWN_IN_CLIENT` | 0 | Sin caché local (también fallback para cualquier cadena no reconocida) |
| `CHECKPOINTED` | 1 | Restricción suave, puede requerir verificación. La cadena del servidor `NO_APPEAL_OPENED` se mapea a `CHECKPOINTED` mediante `AbstractC38371GmM.A00` (nuevo) |
| `BANNED` | 3 | Bloqueo duro, cuenta restringida, apelación posible |
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

Wrapper de prefs: `HLK` (el getter del estado parsea mediante `C36188FnW.A00`: una cadena inválida lanza "Invalid BanState"). ViewModel: `C36188FnW` (WfacBanViewModel).

### 2.3 Flujo de transición de estados

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

### 2.4 Secuencia de reinicio del bloqueo

Tras una apelación exitosa o la liberación de la cuenta (`WfacBanViewModel.A0x` / `C36188FnW`, resetRegistration):
1. Borra: `wfac_ban_state`, `wfac_ban_status_token`, `wfac_ban_violation_*`, `wfac_last_ban_status_fetch_timestamp_ms`, `support_ban_appeal_user_banned_from_chat_disconnect` (nuevo)
2. Cierra la sesión del usuario (finishAffinity)
3. Redirige a la pantalla de login

---

## 3. BizIntegrityQuery — Protocolo GraphQL

### 3.1 Detalles técnicos

| Parámetro | Valor |
|-----------|-------|
| Nombre de la query | `BizIntegrityQuery` |
| doc_id | `28596420510007620` (cambiado; era `25975613018777537`, rotado en 2.26.38.10, confirmado en el catálogo de persist-id de 2.26.41.6; client_doc_id `14769534217004148908396994706`) |
| Esquema | `whatsapp-android-mex` |
| Transporte | MEX HTTP/2 POST → `/mex/query` |
| Formato de JID | `<shortNum>@lid` (p. ej. `1910@lid`) |

### 3.2 Solicitud

2.26.41.6 (found, `BizIntegritySignalsGraphQLFetcher.A00`): objeto de entrada `input { query_input: [ {jid, privacy_token{tctoken, timestamp}?} ], telemetry{context:"INTERACTIVE"} }`, clase de resultado `C48528LIw`. `privacy_token` solo se agrega cuando coincide un gate (`MZ4.A00`) y existe un TC-token almacenado. Respuesta (found, `C51015Mjl`): raíz `xwa2_fetch_wa_users[]`, por usuario `integrity_signals_info` con `dhash`, `fb_linked_page_number_of_likes`, `ig_linked_age_number_of_followers` (sic, clave literal), `is_banned`, `is_suspicious`, `is_suspicious_start_chat`, `join_date_ms` (string, parseado a long), `phone_country_code`, `trust_tier` (enum `M5B`), `is_mv_subscribed` (almacenado como `is_meta_verified`), `meta_verified_info{mv_friction_eligibility}`, `integrity_tags[]{tag, pipeline_date_ms, dates_ms[]}`, `hide_safety_tools_for_business`, `fmx_business_holdout_group`. La lista de campos siguiente es la reconstrucción de 2.26.26.4 (inferred, no re-verificada; la forma de la variable de solicitud `$userJids` difiere de la forma de entrada de 2.26.41.6):

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

### 3.3 DTO de respuesta — `BizIntegritySignals` (`C51530MtC`; era C39833Hhl en 2.26.26.4)

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

(`C51222Mno` lista de `C51359MqA`; serialización en `LwI`, forma sin cambios)

```
IntegrityTagInfo {
  tag         → String
  pipelineDS  → Date (originally Long ms)
  taggedDates → List<Date>
}
```

**Formato JSON en la BD:**
```json
[
  {
    "tag": "automation_bulk_messaging",
    "pipelineDS": 1700000000000,
    "taggedDates": [1699000000000, 1699500000000]
  }
]
```

### 3.5 Eventos disparadores

| Disparador | Cadena de usecase |
|---------|---------------|
| Abrir un chat | `"START_CHAT_CONTEXT"` (disparador principal) |
| Después de enviar un mensaje | hook posterior al envío |
| Inicio de la app / login | scheduler en segundo plano |

### 3.6 Feature Flags

| ID del flag | Función |
|---------|---------|
| 11061 | Disparador de detección de cuenta sospechosa (`N5r.A03`; presente; solo se evalúa para contactos cuyo nivel de nombre verificado comienza con `ent:`) |
| 11064 | Elegibilidad de la señal de confianza de inicio de chat (on/off) (`BizIntegritySignalsManager.A04`; presente; por defecto false) |
| 11065 | TTL de la caché de señales de confianza en segundos (`C51855N0t.A00`; por defecto 86400, found en `C08J`) |
| 12709 | Elegibilidad para contactos cuyo negocio tiene `hostStorage == 2` (`C197628ax.A06`); por defecto false (presente) |
| 16349 | Ruta de consulta forzada en `BizIntegritySignalsManager.A04` (presente; por defecto false) |
| 19793 | Nuevo en esta tabla: `N5r.A02`, controla la reutilización de señales almacenadas en `C51855N0t.A02`; propósito inferred por el uso; por defecto false |
| 12840 | Configuración JSON indexada por tipo de violación, por defecto `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}` (`C08J`); consumidor no localizado; propósito inferred a partir de los nombres de clave (`max_dismiss_count`, `max_display_days`) y de las cadenas de tipo usadas por el banner de soft-enforcement de SMB (7.4) |
| 19893 | Registro del mensaje de sistema de la tarjeta FMX (presente, `C198788cr`) |
| 26697 | BizIntegrity v2 (presente, `C34735F5e`) |
| 27269 | Conteo dividido de mensajes entrantes/salientes (presente) |
| 34166 | ID de inyección, no un feature flag (ver WA_AB_PROPS.md); usado por el escritor de `start_chat_trust_signals` (`ContactInfoActivity`) |

Caché en memoria en `BizIntegritySignalsManager.A02`: entradas válidas 60000 ms (found).

---

## 4. Marcado como sospechoso — Cuándo, por qué, cómo, prevención (re-verificado en 2.26.41.6; los elementos que no se pudieron localizar están marcados en el lugar)

> **Hallazgo central:** Para los flags de BizIntegrity (`is_suspicious`, `trust_tier`, `is_banned`) el cliente no calcula nada: se parsean de la respuesta GraphQL (`C51015Mjl`) y solo se renderizan. No se encontró ningún umbral ni puntuación del lado del cliente para ellos. Por separado, un modelo on-device produce veredictos locales de estafa (`odml_scam_alert_*`, 6.6, 7.6). La solicitud de BizIntegrity lleva solo los JIDs consultados, un token de privacidad opcional y un contexto de telemetría (3.2); que el cliente suba sus métricas locales a otro lugar no se encontró (not found).

### 4.1 ¿Quién decide?

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

No existe en el cliente ninguna flecha desde las métricas locales hacia la solicitud de BizIntegrity (3.2). Qué señales del lado del servidor producen el veredicto no es visible desde el APK (ML del lado del servidor es inferred). El cliente **no tiene umbral local** del tipo "más de X mensajes -> sospechoso" para los flags de BizIntegrity.

---

### 4.2 Jerarquía de Trust Tier (asignada por el servidor)

Found en el APK de WhatsApp como un enum compilado (`M5B` en 2.26.41.6; valores sin cambios):

| Tier | Significado | Efecto |
|------|---------|--------|
| `SUSPICIOUS` | Riesgo más alto — marcado activamente | Todas las advertencias activas, fricción en la UI, posible bloqueo de envío |
| `TIER_0` | Tier legítimo más bajo (cuentas nuevas) | Elegibilidad de fricción elevada |
| `TIER_1` | Usuario estándar | Normal |
| `TIER_2` | Confianza elevada | Menos fricción |
| `TIER_3` | Mayor confianza legítima | Fricción mínima |
| `UNTIERED` | Sin evaluación | No se aplica verificación |
| `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` | Desconocido | Fallback |

**Verificación a nivel de código** (`BizIntegritySignalsManager`):
```java
"SUSPICIOUS".equals(trustTier)  // → triggers UI flow
```

### 4.3 Señales alrededor del veredicto

El cliente no adjunta los datos siguientes a la solicitud de BizIntegrity (3.2). La tabla lista dónde aparece cada uno en el cliente; si el servidor lo evalúa es inferred. La columna "Risk weight" del informe anterior no tenía evidencia del lado del cliente y se elimina.

| Señal | Dónde aparece en el cliente (2.26.41.6) | Rol |
|--------|---------------------------------------------|------|
| `isCountryMismatch` | feature on-device (`integrityai.impl.InputFeatureProviderImpl`, flag 31535) | Entrada del modelo on-device, no de la solicitud |
| `mostRecentSenderScore` | feature on-device (flag 31536) | Igual |
| `dhash` | campo de respuesta, almacenado tal cual | Cadena opaca suministrada por el servidor; ningún código del cliente la compone (significado unknown; la lectura anterior del informe como "device fingerprint" es inferred) |
| `join_date_ms`, `phone_country_code` | campos de respuesta | Almacenados; sin umbral en el cliente |
| Conteos FB/IG | campos de respuesta (`fb_linked_page_number_of_likes`, `ig_linked_age_number_of_followers`) | Se muestran en la tarjeta FMX (7.5) |
| `integrity_tags` | campo de respuesta `{tag, pipeline_date_ms, dates_ms[]}` | Almacenado como JSON; los valores de tag son opacos para el cliente |
| Token de privacidad | campo de solicitud `privacy_token{tctoken, timestamp}` | Opcional, solo cuando coincide el gate `MZ4.A00` y hay un TC-token almacenado |
| Volumen de mensajes | conteo local (`N54`, 6.2) | Subida al servidor no encontrada |
| Límite de broadcast | flag 20278 por defecto `{"max_messages": 10000, "farthest_time_days": 30}` | Consumidor no localizado (6.3) |

`isCountryMismatch` y `mostRecentSenderScore` son las dos features de ML concretas encontradas en el cliente (`com.whatsapp.integrityai.impl.InputFeatureProviderImpl`, 2.26.41.6). El flag 31535 suministra isCountryMismatch, el 31536 mostRecentSenderScore (found).

---

### 4.4 ¿Cuándo se dispara la verificación GraphQL?

**Gate de elegibilidad** (found, `BizIntegritySignalsManager.A04`; el JID consultado es la contraparte del chat):
1. Feature flag **11064** habilitado (por defecto false)
2. El JID no es de los dos tipos excluidos (`AbstractC24760wu.A03/A04`: JIDs de bots y un JID de número de teléfono fijo)
3. Una de: el contacto es un negocio SMB (`N5r.A06`, el nivel de nombre verificado comienza con `smb:`), o el flag **12709** está activo y el negocio del contacto tiene `hostStorage == 2` (`C197628ax.A06`), o (llamada forzada, `A09`) el flag **16349** está activo y se cumple `N5r.A04/A06` (`A04` = `!A01 && !SMB && !ENT`; la semántica del helper `N5r.A01` no se resolvió, por lo que qué JIDs no de negocio admite esto sigue abierto)
4. Para la ruta no forzada: caché expirada o sin caché local (`C51855N0t`)

Corrección respecto al informe anterior: en 2.26.41.6 el gate regular no omite las cuentas de negocio, las selecciona (SMB o hosted); la ruta forzada (16349) puede admitir otros JIDs. El flujo JADX de `A04` está parcialmente reestructurado, por lo que esta lectura proviene de la forma decompilada más los cuerpos de los helpers, no de smali.

**TTL de la caché:** Feature flag **11065** en segundos, por defecto **86400 (24 horas)** (found, `C08J`)
```java
long timeout_ms = TimeUnit.SECONDS.toMillis(remoteConfigValue(11065));
if (current_time - lastSyncTs > timeout_ms) {   // C51855N0t.A00
    // cache expired -> new GraphQL call required
}
```

**Tamaño de lote:** no existe fragmentación en 975 JIDs en la ruta de fetch GraphQL (`BizIntegritySignalsManager.A03` pasa la lista de JIDs sin cambios). La constante 975 pertenece al procesamiento por lotes SQL local del conteo de mensajes (6.2).

---

### 4.5 Valores conocidos de integrity_tag

Las cadenas `automation_bulk_messaging` y `spam` se encuentran en `C35896FgX` y `ViewOnClickListenerC39711HTl`, pero allí se comparan con el `type` de la notificación de soft-enforcement de SMB (`HAR.A07`, ver 7.4), no con `integrity_tags` de la respuesta de BizIntegrity. También aparecen como clave del valor por defecto del flag 12840. El cliente no enumera en absoluto los valores de `integrity_tags`; los blobs JSON se almacenan opacos. `business_policy_violation` no está presente como cadena en ninguna parte de java_src, smali, assets o res de 2.26.41.6.

| Tag | Significado |
|-----|---------|
| `automation_bulk_messaging` | Tipo de notificación de soft-enforcement (envío masivo/automatizado); no se demostró que sea un valor de `integrity_tags` |
| `spam` | Tipo de notificación de soft-enforcement (spam) |

---

### 4.6 Qué lleva concretamente a sospechoso — inferred a partir del código

Re-verificado en 2.26.41.6: el cliente no contiene lógica, umbral ni peso para ninguna fila siguiente, y la solicitud de BizIntegrity no lleva ninguna de estas métricas (3.2). Toda la tabla sigue siendo **inferred** (una conjetura sobre el comportamiento del servidor a partir de qué señales existen en el cliente). La fila "New account (< 24h)" no tiene sustento: no existe ninguna verificación de antigüedad de cuenta en el cliente (ver 4.9 D).

| Comportamiento | Por qué es riesgoso | Peso |
|----------|---------------|--------|
| Salientes altos vs. entrantes (solo envío, sin respuestas) | Patrón de difusión masiva | Muy alto |
| País del teléfono ≠ país de la IP | `isCountryMismatch = 1.0` | Muy alto |
| Mismo dhash en varias cuentas | Disparador de bloqueo de dispositivo | Muy alto |
| Broadcast > 10,000 destinatarios / 30 días | Límite duro, marcado inmediato | Alto |
| `mostRecentSenderScore` alto (destinatarios que reportan) | Bucle de retroalimentación de ML | Alto |
| Cuenta nueva (< 24h, sin contactos) | Baja credibilidad (no se encontró verificación de antigüedad en el cliente) | Alto |
| Sin vínculo FB/IG + alta tasa de salida | Falta de prueba social | Medio |
| integrity_tags existentes | Efecto de violación previa | Medio–Alto |
| `is_reach_out = 1` + iniciar muchos chats desconocidos | Patrón de contacto en frío | Medio |

### 4.7 Códigos de motivo de SpamWarning (advertencia previa al bloqueo)

Sin cambios en 2.26.41.6 (`SpamWarningActivity`: motivo por defecto 100, expiración por defecto -1; switch sobre 101, 102, 103, 104, 106, el default cubre 105/otros).

Entregado mediante el intent extra `spam_warning_reason_key`, establecido desde el atributo `code` (>= 100) del `<failure reason="402">` del login XMPP junto con `expire`, `message`, `url` (found, `C0ZH.handleMessage` tipo 2; ver 8.1):

| Código | Disparador | ¿Cuenta regresiva? |
|------|---------|-----------|
| 101 | Actividad de spam detectada | Sí |
| 102 | Violación de reenvío | Sí |
| 103 | Spam de estados | Sí |
| 104 | Reenvío por bot | Sí |
| 105 | General / por defecto | Permanente si expiry = -1 |
| 106 | Otra violación | Sí |
| default | Violación desconocida | Permanente si expiry = -1, si no cuenta regresiva |

`expiry_in_seconds == -1` + en línea: cierre inmediato (el servidor levantó la advertencia).

### 4.8 Categorías de SpamFlow relevantes para el marcado como sospechoso

97 categorías en el APK (found: `C9E2`, arreglo de 96 entradas más `1_1_spam_banner_report` agregada al final, índices 0 a 96; el conteo anterior de 92 y los índices de la tabla quedan reemplazados). La lista se serializa por nombre dentro del nodo SMAX `spam_list` (atributo `spam_flow` por entrada, `wi_trace_id` opcional de 24 caracteres), por lo que el índice es solo la posición en el arreglo del cliente, no un valor de wire. Nuevas: `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_suspicious_banner_block/_trust`, `odml_scam_alert_fmx_card_block/_trust`, `biz_spam_banner_block`, `1_1_spam_banner_block`, `chat_fmx_card_block`, `group_spam_banner_report`, `left_group_spam_banner_report`. Las directamente ligadas al estado sospechoso:

| Índice | Categoría | Significado |
|-------|----------|---------|
| 23 | `chat_fmx_card_block_server_flagged_suspicious` | Marcado como sospechoso por el servidor → bloqueo FMX |
| 24 | `chat_fmx_card_block_suspicious` | Chat bloqueado por el flag de sospechoso |
| 27 | `chat_fmx_card_safety_tools_block_suspicious` | Herramientas de seguridad mostradas para sospechoso |
| 70 | `odml_scam_alert_bottom_sheet_block` | ML on-device de estafa → bloqueo |
| 71 | `odml_scam_alert_bottom_sheet_trust` | ML on-device de estafa → confiar |
| 76 | `one_to_one_spam_banner_block_server_flagged_suspicious` | Banner de spam 1:1 (marcado por el servidor) |
| 85 | `trust_question_bottomsheet_block_server_flagged_suspicious` | Aviso de confianza (marcado por el servidor) |
| 89 | `user_initiated_chat_suspicious_banner_block` | Banner de sospechoso al iniciar chat |
| 94 | `1_1_old_spam_banner_block` | Banner de spam heredado |
| 96 | `1_1_spam_banner_report` | Reporte de spam 1:1 |

### 4.9 Mecanismos de protección — lo que muestra el cliente

La lista anterior de "factores protectores" es una lectura de ML del lado del servidor que no tiene respaldo en el cliente. Lo que 2.26.41.6 realmente contiene:

#### A) Estado de negocio
No es una omisión. El gate de elegibilidad regular selecciona contactos SMB (y contactos con `hostStorage == 2` bajo el flag 12709), ver 4.4. El flag 2923 (antes: "non-business validation toggle") no se localizó: no existe ninguna verificación de flag con ese ID ni valor de config por defecto para él en java_src o smali de 2.26.41.6.

#### B) Meta Verified (mvFrictionEligibility)
Campo de respuesta `meta_verified_info.mv_friction_eligibility` (found, `C51015Mjl`), almacenado como `mv_friction_eligibility`. `is_mv_subscribed` se almacena por separado como `is_meta_verified`. La tarjeta FMX (`C94p`) lee el flag y, con el flag 15735 activo, agrega un enlace "learn more". Que esto resulte en umbrales de fricción más bajos no es visible en el cliente (inferred).

#### C) Cuentas sociales vinculadas (FB/IG)
`fb_linked_page_number_of_likes` e `ig_linked_age_number_of_followers` se parsean como enteros (`optInt`) y se muestran en la tarjeta FMX (7.5). Son conteos, no booleanos (found). Que el servidor los pondere como protectores es inferred.

#### D) Período de gracia por antigüedad de la cuenta
No encontrado. La única comparación similar a una edad es el TTL de la caché sobre `last_sync_ts` contra el flag 11065 (4.4). `join_date_ms` se almacena pero no existe lógica de ventana de gracia en el cliente.

#### E) Whitelist / lista de validación (flag 12709)
Cambiado: la verificación `C197628ax.A06(userJid)` es `hostStorage == 2` en el registro de nombre verificado del contacto (`AnonymousClass119`), una propiedad local, no una lista de preaprobación del lado del servidor. Hace al contacto elegible para la consulta; no retorna antes.

#### F) hideSafetyToolsForBusiness (campo de la respuesta)
Campo de respuesta `hide_safety_tools_for_business`, almacenado en `hide_safety_tools_for_business`. El efecto en la UI no se volvió a trazar; la afirmación anterior de que solo oculta la UI de advertencia y no cambia el estado de sospechoso no está verificada.

---

### 4.10 Prevención — lo que revela el código

Esta parte es un consejo derivado de los campos anteriores. El cliente no tiene lógica que confirme nada de esto; trate cada elemento como **inferred**, salvo donde esté marcado found.

**Conductual (inferred):**
- Mantener equilibrada la proporción saliente/entrante
- Evitar la discrepancia de país entre el número y la red (el cliente alimenta `isCountryMismatch` al modelo on-device, found; el uso en el servidor es inferred)
- Mantenerse por debajo de la config de broadcast del flag 20278 (10,000 mensajes / 30 días; consumidor no localizado)

**Calidad de la cuenta (inferred):**
- Los conteos de FB/IG vinculados y Meta Verified son mostrados o almacenados por el cliente (found); su efecto en el veredicto es inferred
- Una ventana de cuenta nueva (24h) y el blacklisting por dhash no están respaldados por ningún código del cliente (ver 4.9 D y 4.3)

**Técnico (found):**
- `privacy_token` (TC-token) se agrega a la solicitud de BizIntegrity solo cuando coincide el gate `MZ4.A00` y hay un TC-token almacenado

**Temporización (found):**
- Las señales en caché se reutilizan hasta que `last_sync_ts` sea más antiguo que el flag 11065 (por defecto 86400 s); el manager mantiene además una entrada en memoria de 60000 ms
- Las señales persisten en `wa_biz_integrity_signals` hasta que una nueva respuesta las sobrescribe

---

## 5. Bases de datos SQLite locales

### 5.1 `wa.db` — `wa_biz_integrity_signals`

2.26.41.6 (found, `C53116Nmn`, 17 columnas incl. `_id`): agrega `is_meta_verified` y `fmx_business_holdout_group`; `fb_linked_page_number_of_likes`, `ig_linked_page_number_of_followers`, `join_date_ms`, `last_sync_ts` son REAL, `mv_friction_eligibility` e `is_meta_verified` no tienen valor por defecto declarado. Índices únicos `biz_integrity_signals_jid_index`, `biz_integrity_signals_chat_row_id_index`; trigger `contact_bd_for_business_integrity_signals` (BEFORE DELETE ON wa_contacts). Store: `LwI` (etiquetas `QUERY_BIZ_INTEGRITY_SIGNALS_BY_JID` / `_BY_ROW_ID`, `BizIntegritySignalsStore/saveBusinessIntegritySignals`). El esquema siguiente es la versión de 2.26.26.4.

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

Escritor/lector: `LwI` (store), `BizIntegritySignalsManager.A06(UserJid)` lee el `ConcurrentHashMap` en memoria (found: `A06` lee el mapa en memoria, `A07` lo lee con carga perezosa desde la BD, `A0A` hace upsert y persiste; los nombres `A08`/`A01` de 2.26.26.4 ya no existen)

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

Lector: `C57342Yp` (`SELECT * ... QUERY_START_CHAT_TRUST_SIGNALS_BY_JID`; era C2M7.A0K) → devuelve la tupla `(is_sender_new_account, is_sender_suspicious)`

### 5.3 `msgstore.db` — `integrity_chat_info`

```sql
CREATE TABLE integrity_chat_info (
  chat_row_id                        LONG PRIMARY KEY,
  is_reach_out                       INTEGER,  -- 1 = unknown contact initiated
  is_eligible_for_link_friction_banner INTEGER
);
```

Etiqueta de consulta: `"GET_INTEGRITY_CHAT_INFO"` (consulta por lotes con `chat_row_id IN (...)`), store `C33O`, esquema `C08970Ox` (índice `integrity_chat_info_chat_row_id_index`, trigger `chat_bd_for_integrity_chat_info_trigger` BEFORE DELETE ON chat). Sin cambios.

### 5.4 `wa.db` — `wa_biz_integrity_chat_settings`

Found en 2.26.41.6: esquema `AHY` (cols `jid`, `last_delivered_sort_id` LONG, `last_read_sort_id` LONG), índice único `biz_integrity_chat_settings_index` sobre `jid`, trigger `contact_bd_for_biz_integrity_chat_settings` (BEFORE DELETE ON wa_contacts). Rol unknown.

---

## 6. Recolección de señales de spam (del lado del cliente)

(Re-verificado en 2.26.41.6; los elementos que no se pudieron localizar están marcados en el lugar.)

### 6.1 dhash

`dhash` es una cadena en la respuesta de BizIntegrity (`integrity_signals_info.dhash`), almacenada en texto plano en `wa_biz_integrity_signals.dhash`. Ningún código del cliente la compone: no se encontró ninguna entrada de modelo de dispositivo, SO, versión de la app, número, zona horaria, Android ID ni build-fingerprint, y nada sube alguna. La descripción anterior de "device fingerprint / blacklist del lado del servidor" no está respaldada; el significado es unknown. Otras cadenas `dhash` en el APK (lista de bloqueo, opt-out de negocio) son hashes de directorio no relacionados.

---

### 6.2 Velocidad de mensajes

Found: `com.whatsapp.bizintegrity.logger.receiver.handler` (`C0236xdea74a22`, helper `N54`) cuenta mensajes localmente sobre un intervalo de tiempo para una lista de JIDs, con estos alias SQL:
- `incoming_count`: mensajes con `from_me = 0`
- `incoming_threads_count`: `chat_row_id` únicos de mensajes recibidos
- `outgoing_count`: mensajes con `from_me = 1`
- `outgoing_threads_count`: `chat_row_id` únicos de mensajes enviados
- Conteo de mensajes eliminados: `messages_count_after_privacy_token` (también `messages_count`, `outgoing_messages_count`) desde `integrity_deleted_chat_message_count`

El feature flag 27269 controla si los entrantes/salientes se cuentan por separado o como un total combinado (found en el mismo handler).
Tamaño de lote: **975 JIDs** por llamada de procesamiento SQL (found: `C20H.A1A(list, 975)`, un fragmento por el límite de variables de SQLite, no un lote de red).
No localizado: agrupación diaria/horaria, tasa por contacto; a dónde van los conteos después de contar no se trazó.

---

### 6.3 Límites de broadcast (cuentas de negocio)

Feature config 20278: `{"max_messages": 10000, "farthest_time_days": 30}` (found como valor por defecto en `C08J`/`C09W`).
- El límite de 10,000 mensajes por 30 días es el valor por defecto de la config; el consumidor de este JSON (el código que lo aplica antes de un envío, `renewal_date`, throttling por destinatario, clasificación marketing vs regular) no se localizó: las cadenas clave `max_messages`/`farthest_time_days` aparecen solo en las tablas de valores por defecto y `renewal_date` no aparece en java_src.

---

### 6.4 Aplicación de GAP (Global Abuse Prevention)

Found: `com.whatsapp.gapenforcement.triggers.GapEnforcementTrigger.A03` (`onMarketingMessageReceived`) se omite cuando el feature flag 14837 está desactivado, y almacena `LAST_MARKETING_MESSAGE_TIMESTAMP` en SharedPreferences (`C67902uK`) cuando llega un mensaje de marketing más reciente. El flag 25631 controla otra ruta de disparo. La expansión "Global Abuse Prevention" no está en el código (nombre no verificado).

Estado rastreado (`ChatDescription`, found):
- `isEnterpriseBusiness` (Boolean)
- `isMarketingMessageThread` (Boolean)
- `sortTimestamp` (Long)
- `chatJid` (UserJid)

---

### 6.5 WaFA (Federated Analytics)

Found: paquete `com.whatsapp.federatedanalytics.impl` (`WaFaConfigFetcher`, `WaFaReportScheduler`, `FaReportRunner`, `WaFaReportSubmitter`, `FaTeeConnection`, `FaTeeAcsRepository`, `FaAcsWarmer`). Los reportes pasan por una conexión TEE autenticada con ACS (headers `x-acs-token`, `x-acs-configid`, `x-acs-project-name`; obtención de clave pública OHAI). Próxima hora de ejecución en la pref `fa_next_report_run_timestamp`.
No localizado: el contenido de los reportes. La lista de métricas del informe anterior (adopción de features, crashes, latencia, RAM/almacenamiento/SO, geofencing, datos de sesión, tipo de conexión) no se encontró como código; el contenido de los reportes está dirigido por config, por lo que no se puede leer desde el cliente.

---

### 6.6 Extracción de features de ML (detección de estafas on-device)

Dos features concretas encontradas en el cliente decompilado:
- `isCountryMismatch` (float 0.0/1.0): país del remitente ≠ país del destinatario → **ALTO RIESGO**
- `mostRecentSenderScore` (float): puntuación de reputación de ML del remitente

Los feature flags 31535/31536 controlan sus valores (found). Resultados enviados al servidor para puntuación secundaria de ML (inferred).

---

## 7. Componentes de UI: sospechoso, advertencias, bloqueo

(Re-verificado en 2.26.41.6: `SpamWarningActivity` ahora `com.whatsapp.userban.spamwarning`, `SuspiciousFmxBottomSheetFragment` `com.whatsapp.fmx` más la nueva subclase `SuspiciousSmbFmxBottomSheetFragment`. Las condiciones de disparo de 7.2, 7.4 y 7.5 se corrigen más abajo.)

### 7.1 SpamWarningActivity

Parámetros del intent:
- `spam_warning_reason_key` (int): código de motivo
- `expiry_in_seconds`: cuenta regresiva (-1 = permanente)
- `spam_warning_message_key`: texto personalizado
- `faq_url_key`: enlace a FAQ

Códigos de motivo:

| Código | Significado |
|------|---------|
| 100 | Advertencia general de spam |
| 101 | Actividad de spam detectada |
| 102 | Violación de reenvío |
| 103 | Spam de estados |
| 104 | Reenvío por bot |
| 105 | General / permanente |
| 106 | Otras violaciones |

Si `expiry_in_seconds != -1` → se muestra el temporizador de cuenta regresiva.
Si `-1` + en línea → cierre inmediato (el servidor levantó la advertencia).

### 7.2 Suspicious FMX Bottom Sheet (`SuspiciousFmxBottomSheetFragment`)

Found: una hoja informativa (enlaces "learn more" `about-blocking-reporting`, `examples-of-scams`), no un bloqueador dirigido por estado. Se abre al tocar un botón de estado sospechoso en la tarjeta FMX (`C93z.setupSuspiciousButtons`, la variante SMB `C94p` abre `SuspiciousSmbFmxBottomSheetFragment`) y desde `C512928n` (variante SMB cuando el contacto es un negocio, `A0T()`), mediante los helpers `AbstractC61092ir.A00` / `AbstractC61102is.A00`.

Las cuatro condiciones de disparo del informe anterior (`is_suspicious == 1`, `is_suspicious_start_chat == 1`, `is_reach_out == 1`, `chat_fmx_card_block_suspicious == 1` como bloqueo de envío) no están respaldadas: el fragmento mismo no lee ninguna, y `chat_fmx_card_block_suspicious` es un nombre de categoría de SpamFlow (4.8), no un flag almacenado. Lo que se encontró: el contexto de inicio de chat se muestra cuando `is_suspicious_start_chat` es true (`StartChatContextUtils`), y la tarjeta FMX calcula `"SUSPICIOUS".equals(trust_tier)` (`C94p`).

---

### 7.3 UI de bloqueo duro WFAC

| Clase | Función |
|-------|---------|
| `WfacBanActivity` | Punto de entrada, información del bloqueo + botón de apelación |
| `WfacBanInfoFragment` | Detalles de la violación + enlace de apelación |
| `WfacBanDecisionFragment` | Acción del usuario (apelación enviada) |
| `WfacUnbanDecisionFragment` | Confirmación posterior a la apelación |

Disparador (cambiado): `Main.A5D()` ya no existe; su equivalente es `Main.A5W()`, que lee `wfac_ban_state` al inicio (switch sobre "UNBANNED" / "BANNED" / "CHECKPOINTED", estado de registro 21, log "main/me/wfac ban") e inicia `WfacBanActivity` mediante `HBC`. No se encontró ningún listener de cambios de SharedPreferences. `wfac_ban_state` es escrito por el handler del fetch del estado de bloqueo y por `WfacBanActivity.onCreate` (2.3). La ruta de fallo de login (403) abre en su lugar la antigua `com.whatsapp.userban.ui.BanAppealActivity` (`HBB`). 2.26.41.6: clases ahora en `com.whatsapp.waffle.wfac.ui` (también `WfacBanBaseFragment`); actividad abierta mediante el helper de intent `HBC` y la transición de pantalla `I1T` (`transitionToScreen`).

### 7.4 SMB Soft Enforcement

Cambiado: el disparador no es `is_suspicious=true` + `integrity_tags` que contenga `"business_policy_violation"` (esa cadena no existe en 2.26.41.6). Es una notificación de negocio XMPP (handler `AnonymousClass142`, notification id 202) con hijo `biz_integrity_warning_notification > violation`:

| Atributo | Uso |
|-----------|-----|
| `source` | origen de la violación (obligatorio) |
| `type` | tipo de violación, p. ej. `automation_bulk_messaging`, `spam` (comparado en `C35896FgX`) |
| `severity` | p. ej. `"severe"` cambia el texto del banner (`C35896FgX`, `WABIEnforcementEducationFragment`) |
| `policy_url` | destino del enlace (obligatorio) |
| `priority` | int >= 0 (obligatorio) |
| `status` | `active` (almacenado, contadores reiniciados) o `inactive` (eliminado) |

El cliente construye una `SMBSoftEnforcementNotification` (`HAR`) con `notificationType` fijo en `"warning"` y `bannerNotificationTimeStamp` = hora de recepción, y persiste un arreglo JSON bajo la preferencia `smb_soft_enforcement_banner-all-json-<notificationType>` (`C35894FgV`) con las claves siguientes. Los contadores por notificación son preferencias int `smb_soft_enforcement_banner-<notificationType>-<source>-<severity>-<type>-total_days|click_count|dismiss_count`.

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

El JSON del informe anterior (`notification_type: soft_enforcement`, `violation_type`, `education_url`, `action_required`) no está presente en el cliente. UI: `SMBSoftEnforcementEducationFragment`, `WABIEnforcementEducationFragment` en `com.whatsapp.banner.softenforcementsmb`.

---

### 7.5 Tarjeta FMX (Trust Signal Card)

Found: se crea un mensaje de sistema de tipo 129 (`0x81`, `C57172Xr`) en `C198788cr` ("Creating FMX card system message for chat", "ContactsProcessor/added contact info message"); el flag 19893 solo controla allí un evento de analytics. La escritura asíncrona en `start_chat_trust_signals` está controlada por `C1P2.A01()` (flag no resuelto) y se ejecuta mediante `C65972r0`. La tarjeta (`C94p`) renderiza los conteos de likes de FB y seguidores de IG y el flag de fricción de Meta Verified; `"SUSPICIOUS".equals(trust_tier)` selecciona la variante sospechosa. La visualización de la antigüedad de la cuenta y la condición de visualización de "contacto de negocio/desconocido" no se localizaron.

---

### 7.6 ODML Scam Alert (ML on-device)

Modelo de ML descargable mediante el token ACS `"WA_ODML"` (found en `OdmlModelDownloadClient`, `ODML_MODEL_DOWNLOAD`, id `27301080136160169`, TTL 345600 s = 4 días; tamaño de caché 64 no localizado). Activable por el usuario mediante `ScamDetectionSettingsActivity`. El embudo se rastrea mediante intent extras de ID de sesión / origen / punto de entrada.

---

## 8. XMPP y stanzas (contexto de bloqueo)

(Re-verificado en 2.26.41.6 leyendo los handlers de login y de stream-error; la sección 8.1 está corregida. Una verificación anterior en 2.26.35.2 no vio ningún push de bloqueo por XMPP; esa observación queda reemplazada por la ruta de fallo de login siguiente.)

### 8.1 El `<failure>` del login lleva bloqueos y advertencias

La afirmación anterior "los bloqueos llegan solo por MEX GraphQL" es incorrecta para eventos al momento de conectar. `HandlerThreadC12340b0.A13` lee el nodo de resultado del login; para `<failure>` toma `reason` (int) y construye una excepción `C45351tB` (found):

| `reason` | Tipo | Atributos leídos | Reacción del cliente (`C0ZH.handleMessage`) |
|----------|------|-----------------|-----------------------------------------|
| 5xx | 4 | - | Error del servidor, ruta de reintento |
| 402 | 2 (default) | `code`, `expire`, `message`, `url`, `appeal_token`, `age_collection` | `SpamWarningActivity` con `spam_warning_reason_key` = `code` (>= 100), `expiry_in_seconds`, texto, url de FAQ |
| 402 + `appeal_token` + `code` 106 | 13 | igual | `ContextualAgeCollectionActivity` (extras `appealToken`, `expireTimeout`) |
| 402 + `appeal_token` + `code` 107 / `code` 109 | 14 / 15 | igual | Ruta "U13 Banned PAA Pending" (prefs de cuenta administrada, onboarding) |
| 403 | 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` | Bloqueo permanente: `HGB.startPermanentBanFlow` -> `BanAppealActivity` (tras el retraso en ms del flag 19714) |
| 405 | 3 | `t` (segundos) | Escribe la pref `software_forced_expiration` |
| 406 | 5 | `code` | Pref `underage_account_banned` |
| 416 | 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` | `WfacManager.startUnderageBanFlow`; `violation_reason == "u13_checkpoint"` establece `support_ban_appeal_user_banned_from_chat_disconnect` |
| otro | 0 | - | Logout (ruta "exception-password") |

Todos los tipos de failure también leen atributos opcionales de la UI de logout: `logout_message_header`, `logout_message_subtext`, `logout_message_locale`, `logout_main_button_text`, `logout_main_button_url`, `logout_secondary_button_text`, `logout_secondary_button_url`. `location` se lee del nodo para el enrutamiento.

`<stream:error>` (interceptor de lectura acompañante, `C40601l6`): `code` 515 / 516, hijo `conflict type="device_removed"` (deregister), hijo `ack` (kick). No se encontró ningún hijo específico de bloqueo. `<presence type="unavailable">` y los códigos de cierre de WebSocket no se examinaron.

### 8.2 Tokens de error XMPP (diccionario binario)

Diccionario `AbstractC40911lb` (un byte `A00`, dos bytes `A01`). Presencia de los tokens de la tabla anterior:

| Cadena del token | En el diccionario |
|-------------|---------------|
| `stream:error` | sí |
| `conflict` | sí |
| `not-authorized` | sí |
| `item-not-found` | sí |
| `server-error` | sí |
| `401` | sí |
| `policy-violation` | no encontrado |
| `403` | no encontrado como token (el valor `reason` 403 se lee como atributo int) |

La columna "Meaning" del informe anterior (p. ej. `403` = "Forbidden (ban-related)") era inferred; solo el significado de 403 está ahora respaldado por el manejo de `<failure>` de arriba. También en el diccionario: `404`, `407`, `failure`, `locked`.

### 8.3 Respuestas IQ para cuentas restringidas

No encontrado. Ni el namespace `urn:ietf:params:xml:ns:xmpp-stanzas` ni los textos "Account restricted" / "User banned" existen en java_src o recursos de 2.26.41.6, y no hay tokens `forbidden` / `service-unavailable` en el diccionario. Los ejemplos XML del informe anterior no están verificados y no se debe confiar en ellos (pueden ser ilustrativos). El manejo de errores por IQ (p. ej. parsers de `item-not-found`, `not-authorized` como `K3P`, `C23205A1e`) no se trazó para cuentas restringidas.

---

## 9. Flujo de datos completo (End-to-End)

(Re-verificado en 2.26.41.6: doc_id `28596420510007620`, forma de entrada `query_input`, nombres de clase arriba. Las flechas `isBanned` -> `wfac_ban_state` -> `Main.A5D()` del diagrama de 2.26.26.4 se eliminan porque no existe tal vínculo en el código; ver secciones 1 y 2.3.)

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

## 10. Solicitud de apelación (2.26.41.6)

Found en `C37414GLt`: el JSON `variables` de la solicitud lleva `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}` y `app_id` (`"dev.app.id"`); el texto plano antes del cifrado es `{token, debug_info, description}`; etiqueta de contexto `"WA_INAPP_BAN_APPEALS"` (info de derivación de clave). Transporte (found, `AbstractC40195HfH`): un POST simple de Facebook Graph a `https://<host>.facebook.com/graphql` con `doc_id` y un campo `access_token`, no MEX. `C37414GLt` pasa el `doc_id` **38509456535312323** cuando `hg3.A04.A00()` es true, de lo contrario **5473316762755318**. El nombre de operación `submitBanAppeal` no aparece como cadena en java_src, smali, assets o res de 2.26.41.6, y ninguno de los doc_id está en el catálogo de queries del proyecto, por lo que el nombre no está verificado. Antes del envío, `C40191HfD` parsea una primera respuesta con `data.purpose_public_keys{purpose_public_ek, purpose_public_ik, purpose_public_ik_sig, purpose_dummy_ciphertext, purpose_dummy_nonce}` que suministra el material de claves para el cifrado.

---

## 11. Cambios respecto a 2.26.26.4

| Elemento | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| doc_id de BizIntegrityQuery | `25975613018777537` | `28596420510007620` (rotado 2.26.38.10) |
| Forma de la solicitud | lista `$userJids` (reconstruida) | `input{query_input[{jid, privacy_token{tctoken,timestamp}}], telemetry{context}}` |
| Clase DTO | `C39833Hhl` | `C51530MtC` (17 campos: + `isMetaVerified`, `fmxBusinessHoldoutGroup`) |
| `wa_biz_integrity_signals` | 14 cols | + `is_meta_verified`, `fmx_business_holdout_group`; conteos REAL |
| Store / manager | `BizIntegritySignalsManager.A08/A01` | store `LwI`, esquema `C53116Nmn`, manager A02 caché en memoria de 60 s |
| Lector de start_chat_trust_signals | `C2M7.A0K` | `C57342Yp` |
| Enum de trust tier | no registrado, 7 valores | `M5B`, los mismos 7 valores |
| Paquete de UI WFAC | `com.whatsapp.waffle.wfac` (plano) | `com.whatsapp.waffle.wfac.ui` (+ `WfacBanBaseFragment`) |
| Prefs de WFAC | 5 claves | + `wfac_last_ban_status_fetch_timestamp_ms` (throttle de refresco de 5 s), `support_ban_appeal_user_banned_from_chat_disconnect` borrada al reiniciar |
| Parseo del estado de bloqueo | 4 estados | igual; `NO_APPEAL_OPENED` mapeado a `CHECKPOINTED` |
| Flags | 11061/11064/11065/12709/16349/19893/26697/27269 | todos presentes; + 19793 (N5r.A02) |
| Códigos de SpamWarning 100-106 | sí | sin cambios |
| integrity_tags | `automation_bulk_messaging`, `spam` | sin cambios |
| SpamFlow | 92 categorías | 97; agregadas `odml_scam_alert_*`, `biz_spam_banner_block`, otras |
| Features de ML | `isCountryMismatch`, `mostRecentSenderScore` (31535/31536) | sin cambios, en `integrityai.impl.InputFeatureProviderImpl` |
| Límite de broadcast 20278 | 10000 / 30 días | sin cambios |
| Eventos de bloqueo/advertencia al conectar | "no XMPP ban signalling" | `<failure>` del login XMPP: reason 402 (SpamWarning / U13), 403 (perm ban -> `BanAppealActivity`), 405, 406, 416 (WFAC underage); `C45351tB`, `C0ZH` |
| `Main.A5D()` | reacciona al cambio de `wfac_ban_state` | eliminado; `Main.A5W()` lee el estado al inicio (reg state 21) y abre `WfacBanActivity` mediante `HBC` |
| Escritores de `wfac_ban_state` | no registrado | handler del fetch del estado de bloqueo `C40191HfD`; `WfacBanActivity.onCreate` (CHECKPOINTED / BANNED / UNBANNED según el origen de lanzamiento); sin vínculo desde `is_banned` |
| Elegibilidad de BizIntegrity | "business accounts skip the check" | selecciona contactos SMB (nivel `smb:`) o `hostStorage == 2` (12709); ruta forzada 16349; sin fragmentación en 975 JIDs en el fetch |
| Lote de 975 | lote GraphQL | fragmento SQL local del conteo de mensajes (`N54`) |
| Flag 12709 | whitelist del lado del servidor | verificación local `hostStorage == 2` |
| Flag 2923, gracia de 24h por antigüedad de cuenta, composición de `dhash` | afirmado | no encontrado en 2.26.41.6 |
| Valores de `integrity_tags` | `automation_bulk_messaging`, `spam` | esas cadenas son valores de `type` de la notificación de soft-enforcement de SMB, no de `integrity_tags` |
| SMB soft enforcement | tag `business_policy_violation` + JSON `notification_type`/`education_url` | XMPP `biz_integrity_warning_notification > violation{source,type,severity,policy_url,priority,status}`; claves JSON almacenadas `source,type,severity,notificationType,policyUrl,status,bannerNotificationTimeStamp,priority`; flag 12840 |
| Índices/conteo de SpamFlow | 92, p. ej. `odml_scam_alert_bottom_sheet_block` = 65 | 97 entradas (`C9E2`), mismos nombres en índices desplazados (70, 71, 76, 85, 89, 94, 96) |
| `SuspiciousFmxBottomSheetFragment` | abierto por 4 condiciones de datos | hoja informativa abierta desde botones de la tarjeta FMX / `C512928n` |
| Solicitud de apelación | mutación MEX `submitBanAppeal` | Graph `https://<host>.facebook.com/graphql` por doc_id 38509456535312323 / 5473316762755318, precedido por un fetch de `purpose_public_keys`; nombre de operación no encontrado |
| `wa_biz_integrity_chat_settings` | no localizada | encontrada (`AHY`) |
| Tokens de error XMPP | tokens `policy-violation`, `403` | no están en el diccionario; `forbidden`/`service-unavailable` y los textos de 8.3 ausentes |

Aún abierto en 2.26.41.6: nombres de categoría detrás de `wfac_ban_violation_source` 0/1/2; consumidor del flag 20278 y del flag 12840; semántica del helper `N5r.A01`; contenido de los reportes de WaFA; manejo de errores por IQ para cuentas restringidas (8.3); visualización de la antigüedad de la cuenta en la tarjeta FMX; flag detrás de `C1P2.A01()`.
