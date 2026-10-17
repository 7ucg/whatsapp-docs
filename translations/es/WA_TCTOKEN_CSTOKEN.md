<!-- src-sha1: abf07b893763b0d9ab0f43cb7e9b4dab51809e14 -->
# WhatsApp TCToken y CSToken — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-17
**Alcance:** TCToken y CSToken — qué son, cómo funcionan, internos del APK de Android, implementación en Baileys

---

## 1. Resumen: ¿Qué son estos tokens?

| Token | Nombre completo | Quién lo emite | Cuándo se usa | Propósito |
|-------|-----------------|----------------|---------------|-----------|
| **tctoken** | Trusted Contact Token | Servidor de WA | Contacto cálido (relación existente) | Prueba que remitente y destinatario tuvieron contacto previo — atestación anti-spam |
| **cstoken** | Cold-Start Token (alternativa NCT) | Cliente (HMAC-SHA256, found en Java de Android) | Contacto frío (sin tctoken almacenado) | Señal anti-spam de respaldo cuando no existe tctoken |

**Regla central (found):** En el stanza de mensaje 1:1, `cstoken` solo se adjunta cuando el almacén no contiene un tctoken válido para el destinatario (`NctTokenMessageSendStanzaContributor/ skipped - tctoken present`). `tctoken` lo adjunta un contributor distinto (`PrivacyTokenMessageSendStanzaContributor`).

Ambos tokens son señales anti-spam. Lo que el servidor hace con ellos no es visible desde el cliente (inferred: límite de spam / chats nuevos, ver `NewChatMessageCappingAsyncInit` como disparador del salt).

Todos los tokens tienen nivel de evidencia **found** (lectura estática con JADX de 2.26.41.6) salvo que se marque inferred / not re-verified. Nada está tested en tiempo de ejecución.

---

## 2. TCToken (Trusted Contact Token)

### 2.1 Qué es

Un token binario emitido por el servidor que atestigua una relación de confianza entre dos JIDs. El servidor lo genera y lo distribuye. El cliente lo almacena y lo reenvía. Los bytes del token son opacos para el cliente (datos firmados / algoritmo: unknown).

### 2.2 Cómo se solicita / renueva

**Job:** `GeneratePrivacyTokenJob` — nombre del job `"generate-tc-token"`. No lleva un token: le pide al servidor que (re)emita uno (ver 2.4).

**Manager:** `PrivacyTokenSendManager` (`C230709y3`)

**Lógica de disparo (found):**
- Puntos de entrada `C230709y3.A01(C14080dr, UserJid)`, `A02(UserJid)`, `A04(UserJid)`; `A05` es un conjunto de deduplicación de tareas en curso (`A03` elimina de él).
- `A04`: basado en buckets. Feature flag **996** = longitud del bucket en segundos (<= 0 registra "Bad bucket configuration" y recurre a ahora − 15724800 s = 182 días). El job se omite si la marca de tiempo almacenada cae en el bucket actual o en uno posterior.
- La clave de SharedPrefs `"privacy_token_last_batch_time_sec"` (leída en `A04` y en `AHP`) registra la hora del último lote. El flag **4063** (int) es un desplazamiento de bucket que se usa junto con ella y con la marca de tiempo de emisión real.
- El flag **14303** (bool) selecciona cómo se normaliza el JID (`A00`): activado, `PrivacyTokenStore.A0L` (mapeo PN → LID); desactivado, LID → PN mediante el JID mapper. El flag **15491** (bool) desactiva de forma similar la doble búsqueda PN/LID en el store (`A02`, `A0Q`).

**Validación de frescura (found):**
```java
// C14820fK.A0Y(UserJid)  — token for sending
C9oI c9oI = A0M(userJid);
if (c9oI == null || c9oI.A00 < this.A04.A02()) return null;  // expired or missing
return c9oI.A01;
```
Compuerta de expiración `C14830fL` (TokenBucketValidity):
- `A02()` (tokens recibidos) = `A00(len=flag 865, validBuckets=flag 909)`
- `A01()` (validez de la marca de tiempo de envío) = `min(A00(flag 996, flag 997), A02())`
- `A00(len, n)` = `max((now/len − (n−1)) * len, now − 15724800)` (15724800 s = 182 días, límite inferior estricto).

### 2.3 Almacenamiento

**Tablas de base de datos (`wa.db`), creadas por `C23627AHs` / `C23628AHt` (found):**

```sql
-- Incoming tokens (received from contacts)
CREATE TABLE wa_trusted_contacts (
  jid                         TEXT PRIMARY KEY,
  incoming_tc_token           BLOB,
  incoming_tc_token_timestamp LONG
);
CREATE INDEX incoming_tc_token_timestamp_index ON wa_trusted_contacts (incoming_tc_token_timestamp);

-- Outgoing token tracking
CREATE TABLE wa_trusted_contacts_send (
  jid                     TEXT PRIMARY KEY,
  sent_tc_token_timestamp LONG,
  real_issue_timestamp    LONG
);
CREATE INDEX sent_tc_token_timestamp_index ON wa_trusted_contacts_send (sent_tc_token_timestamp);
CREATE INDEX sent_real_issue_timestamp_index ON wa_trusted_contacts_send (real_issue_timestamp);
```
(Los tipos de columna de `jid` / clave primaria no se muestran en las dos clases de esquema leídas; la columna `jid` se usa como clave en todas las consultas. Los tipos DDL exactos son inferred.)

**Storage manager:** `PrivacyTokenStore` (`C14820fK`), acceso a la DB mediante `C14840fM`
- Caché en memoria: `C12420b9(10, "privacytokendatacache")`
- Métodos clave:
  - `A0P(UserJid, byte[], long)` — almacena el token recibido; solo sobrescribe si la nueva marca de tiempo es más reciente ("UPDATE_RECEIVED_TOKEN_IF_NEWER")
  - `A0Y(UserJid)` — bytes del token para enviar (null si expiró)
  - `A0M(UserJid)` — lee token + marca de tiempo
  - `A0O(UserJid)` / `A0N(UserJid)` — `(timestamp, real_issue_timestamp)` del lado de envío (en caché; `A0O` descarta entradas anteriores a `A04.A01()`)
  - `A0V(UserJid, long)` / `A0W(UserJid, long)` — actualizan la marca de tiempo de envío (`A0V` además deja `real_issue_timestamp` en null)
  - `A0X(UserJid, Integer)` — verificación de recencia de la emisión real usando los flags **865** y **3802** / **22012**
  - `A0U()` — puebla la caché (llamado desde `NewChatMessageCappingAsyncInit` en primer plano)

**Tipos de datos:** `C9oI` = `(A00=timestamp, A01=byte[] token)`; `C220519e9` = `(A00=sent timestamp, A01=Long real_issue_timestamp)`.

### 2.4 Stanzas XMPP

**Solicitud saliente (found, `GeneratePrivacyTokenJob.A0M`)** — enviada al JID del servidor (`C19380nJ.A00`), no al contacto. No lleva bytes de token; nombra al contacto, el tipo y la marca de tiempo almacenada:

```xml
<iq id="[id]" to="[server]" type="set" xmlns="privacy">
  <tokens>
    <token jid="[contact-jid]" type="trusted_contact" t="[stored-timestamp]"/>
  </tokens>
</iq>
```

Enviada mediante `A0W(callback, node, id, 299, 32000L)` (`C10140Tq`, `MessageClient`): timeout de **32,000 ms** (found). `299` es el entero de tipo de solicitud IQ: `A0A` lo registra como `MessageClient/sendIqWithCallbackInternal ... type=` y lo guarda junto con el callback pendiente (found). Es un id por tipo de solicitud compartido por muchos sitios de llamada IQ (la misma posición lleva valores como 1, 2, 14, 114, 237, 254, 264, 415), no un feature flag. El cliente no indica qué valor nombra qué solicitud. Reintento del job: `A0O` reintenta salvo que el código del nodo de error sea 4xx. El job aborta ("Token timestamp ... missing or too old to send") si no hay ninguna marca de tiempo de token almacenada que sea válida.

**Entrante (found, `C1S0` case 4888, handler `X.0vv`)** — registrado para el token de diccionario **234** (`"privacy_token"`, tabla `AbstractC32331E9w`):

```xml
<notification from="[contact-jid]" sender_lid="[lid]?" t="[t]">
  <tokens>
    <token type="trusted_contact" t="[unix-timestamp]">[binary-token-bytes]</token>
  </tokens>
</notification>
```
Solo se almacenan los hijos con `type="trusted_contact"`; si falta el contenido se lanza "required token element to contain data". La clave de almacenamiento es `sender_lid` si está presente, si no `from`. `t` recurre al `t` del padre. Búsqueda de la marca de tiempo mediante `A0P`, que ignora los tokens que no son más recientes.

**Adjunto saliente de tctoken (found)** — bytes del token `1..120` desde `PrivacyTokenStore.A0Y`:

| Dónde | Clase | Forma |
|-------|-------|-------|
| Stanza de mensaje 1:1 | `PrivacyTokenMessageSendStanzaContributor` (`F6I`) | hijo `<tctoken>[bytes]</tctoken>`; si falta pero se esperaba, registra `expected token, but missing` y reporta el motivo `C99E.A07`. El flag **20605** cambia al JID de usuario del dispositivo |
| Fanout multidispositivo | `AbstractC33466EhY.A01` | `<tctoken>` se agrega una vez por usuario dentro del primer nodo de dispositivo `<to jid=...>`; limitado por el flag **20605** (bool) y el flag **20606** (máx. de usuarios por stanza) |
| IQ de foto de perfil `w:profile:picture` | `C197098a4.A00` | hijo `<picture ...><tctoken>` |
| Suscripción de presencia | `HandlerThreadC21920sG` case 12 / `C18320lY.A07` | `<presence type="subscribe"><tctoken>` |

### 2.5 Integración con GraphQL

El token almacenado se adjunta como contexto adicional en varias entradas de GraphQL:

```java
// BizIntegritySignalsGraphQLFetcher / IntegrityFeaturesContextFetcher / C229259vZ / C23694AKh / C20L.A0M
node = GraphQlCallInput("tctoken", base64(token));   // string field
node.put("timestamp", String.valueOf(c9oI.A00));
query_input.put("privacy_token", node);
```

Campos: `tctoken` (token, codificado en Base64 / string), `timestamp`, anidados bajo `privacy_token`. Llamadores en 2.26.41.6: BizIntegritySignals, IntegrityFeaturesContext (`use_case INTEGRITY_FEATURES_CONTEXT`), `C229259vZ`, `C23694AKh`, `C20L`.

### 2.6 Definición proto

No está en un mensaje `JidGroupInfo`: no existe ninguna clase con ese nombre en 2.26.41.6. Los campos del token persistido están en el proto `Conversation` (`BD1`, `id` = 1, `messages` = 2) (found, constantes `*_FIELD_NUMBER`):

| Campo | Número | Tipo |
|-------|--------|------|
| `tcToken` | **21** | bytes |
| `tcTokenTimestamp` | **22** | int64 |
| `contactPrimaryIdentityKey` | **23** | bytes |
| `tcTokenSenderTimestamp` | **28** | int64 |

La afirmación de 2.26.26.4 `JidGroupInfo.tcToken = 8` / `contactPrimaryIdentityKey = 9` no se sostiene para esta build.

---

## 3. CSToken / NCT Token (Cold-Start Token)

### 3.1 Qué es

Un **HMAC calculado por el cliente** sobre la cadena del JID del destinatario, con una clave que es un salt de toda la cuenta (`nctSalt`). Es la alternativa cuando no existe tctoken.

**Fórmula (found, Android `AbstractC38971i1.A00(data, key)`):**
```
cstoken = HMAC-SHA256(key=nctSalt, data=utf8(recipientJid.toString()))
```
Salida: 32 bytes, sin procesar. El código solo verifica que la cadena no esté vacía (log: `NctTokenGenerator/ recipient LID is empty`), lo que sugiere que el destinatario es un LID (inferred). La forma exacta de entrada `<user>@lid` es una afirmación exclusiva de WA Web del informe de 2.26.26.4; no aplica a Android y no se puede comprobar desde el APK.

### 3.2 NctSalt — de dónde viene

El salt se genera localmente en el dispositivo primario y se distribuye a los companions mediante **App-State-Sync** y **HistorySync**.

**Generación (found, `NctSaltProvider` = `C67592to.A00()`):**
```java
byte[] salt = loadFromSharedPrefs();            // C2X8.A04()
if (salt == null) {
    if (companionDevice) return null;           // "skipped - companion device"
    salt = new byte[32]; SecureRandom.nextBytes(salt);
    C2X8.A03(salt);                             // persist
    putLong("nct_salt_last_sync_ts", 0L);
}
```
Almacenamiento `C2X8`: clave de SharedPrefs `"nct_salt"`, Base64 (`NO_WRAP`). Por tanto, el origen es un `SecureRandom` local en el primario (found), no generado por el servidor.

**Disparador (found, `NewChatMessageCappingAsyncInit` = `C2AE`)**: al pasar la app a primer plano / async-init:
- Flag **24915** (bool): habilita la creación y sincronización del salt NCT.
- Si `nct_salt_last_sync_ts == 0` o el flag **26897** (int, segundos) > 0 y el tiempo transcurrido >= ese intervalo: escribe el nuevo `nct_salt_last_sync_ts` y programa un push de SyncD (`C3MD` case 36 → `SyncdUpdateHelperImpl/syncNctSalt`).

**Mutación de sync (found, `NctSaltSyncMutation` = `C52032Bk`)**: transporta el salt como `byte[]` sin procesar, acción `EnumC24865AnN.A0x` (`"NctSaltSyncAction"`, clave `"nct_salt_sync"`), envuelta en el campo **80** de `SyncActionValue`. Se envía a los companions mediante `C12440bB.A0U/A0O`.

**Recepción en el companion (found, `NctSaltSyncMutationHandler` en `C0XG`)**: en un companion, `A0S` almacena el salt mediante `C2X8.A03` ("Received NCT salt from primary, storing"). Handler habilitado por el flag **25253** (bool).

**HistorySync (found, `CMP`)**: `HistorySync.nctSalt` (`C25838BCy.nctSalt_`, bit de presencia 512) se almacena mediante `C2X8.A03` ("stored NCT salt from history sync"). Número de campo **19** (`C25838BCy.NCT_SALT_FIELD_NUMBER`, found).

### 3.3 Campos proto

```protobuf
// NctSaltSyncAction (C49554LrH): single field "salt" (ByteString)
message NctSaltSyncAction {
  bytes salt = 1;               // found: the only field; size/serialise helpers are called with tag 1 (C49650Lsp case 28)
}

// SyncActionValue (C49639Lse)
message SyncActionValue {
  NctSaltSyncAction nctSaltSyncAction = 80;  // found: NAq.A03(C49554LrH.A00, nct_salt_sync_action, 80)
}

// HistorySync (C25838BCy)
message HistorySync {
  bytes nctSalt = 19;           // found: NCT_SALT_FIELD_NUMBER = 19
}
```

DB: la columna `"nct_salt"` está registrada en el esquema de `wa.db` (`C09E`, entrada `C33501Un("nct_salt", ...)`). El informe de 2.26.26.4 atribuía `nctSalt = 12` a `ConversationThreadInfo`; en 2.26.41.6 no existe ninguna clase con ese nombre ni ningún campo `nctSalt` fuera de HistorySync (`nctSalt_` solo está en `C25838BCy`, número 19; `Conversation` `BD1` no tiene campo de salt).

### 3.4 Cálculo del HMAC y stanza (Android vs Web)

| Aspecto | Android 2.26.41.6 | WA Web (solo Web, no aplica a Android; no se puede comprobar desde el APK) |
|---------|------------------|--------|
| Sync del salt (NctSaltSyncAction) | Implementado (campo 80) | Sí |
| Almacenamiento del salt | SharedPrefs `"nct_salt"` | IndexedDB `"WAWebNctSalt"` |
| Cálculo de HMAC-SHA256 | **Found en Java** (`AbstractC38971i1`, `javax.crypto.Mac`) | JavaScript |
| Inyección del token en el stanza | **Found en Java** (`NctTokenMessageSendStanzaContributor` = `F6G`) | nodo `<cstoken>` |

**Stanza contributor (found, `F6G.ASY`)**, en orden:
```
flag 24941 off                    → nothing
recipient not a 1:1 user JID      → skip ("not a 1:1 user JID")
flag 18639 on and recipient is GUEST_E2EE → skip ("guest recipient")
PrivacyTokenStore.A0Y(user) != null → skip ("tctoken present")
recipient string empty            → log "recipient LID is empty", fail
salt == null                      → log "no salt available", fail
else  <cstoken>[32 bytes]</cstoken> appended to the message stanza
```
Cualquier excepción se captura y se registra (`skipping cstoken due to ...`); el envío continúa.

```xml
<message ...>
  ...
  <cstoken>[32 raw bytes]</cstoken>
</message>
```

Flag **24941** (bool) = compuerta de envío de CSToken en Android; **18639** (bool) = exclusión de destinatarios guest.

---

## 4. Comparación de tokens

| | TCToken | CSToken |
|-|---------|---------|
| Emitido por | Servidor de WA | Cliente (HMAC) |
| Algoritmo | Definido por el servidor (binario opaco) | HMAC-SHA256 |
| Material de clave | Generado por el servidor | `nctSalt` (`SecureRandom` local, sincronizado vía App-State / HistorySync) |
| Datos firmados | No se conocen (opaco) | `utf8(recipient JID string)` (forma LID inferred) |
| Existe cuando | Hay contacto previo establecido, no expirado | Cuando existe el salt y no hay tctoken válido |
| Prioridad | Primero (gana tctoken) | Solo como respaldo |
| Stanza | hijo `<tctoken>` en mensaje / nodo `<to>` / IQ de foto / presencia; IQ de solicitud `xmlns="privacy"` al servidor | hijo `<cstoken>` en el mensaje |
| GraphQL | Enviado en varias consultas de integridad | No visto en GraphQL |
| Almacenamiento | `wa_trusted_contacts` (+ `_send`) en la DB | SharedPrefs `"nct_salt"` |
| Por destinatario | Sí (uno por JID) | No (un salt, calculado por destinatario) |

---

## 5. Implementación en Baileys

Todo lo de esta sección es guía de implementación (inferred a partir de los hechos del protocolo anteriores), no un artefacto decompilado. Las formas de los stanzas están ajustadas a 2.26.41.6; el TypeScript no está tested.

### 5.1 TCToken

**Recepción y almacenamiento:**
```ts
// Incoming tokens arrive as a notification, not an IQ set
// <notification from=jid [sender_lid=lid]><tokens><token type="trusted_contact" t=ts>bytes</token></tokens></notification>
sock.ws.on('CB:notification,type:privacy_token', async (node) => {
  const tokens = getBinaryNodeChild(node, 'tokens')
  if (!tokens) return
  for (const tk of getBinaryNodeChildren(tokens, 'token')) {
    if (tk.attrs.type !== 'trusted_contact') continue
    const jid = node.attrs.sender_lid || node.attrs.from
    const timestamp = parseInt(tk.attrs.t || node.attrs.t)
    if (tk.content) {
      await authState.keys.set({ 'tc-token': { [jid]: { token: Buffer.from(tk.content as Uint8Array), timestamp } } })
    }
  }
})
// Only overwrite when the new timestamp is newer (Android: UPDATE_RECEIVED_TOKEN_IF_NEWER)
```
(El valor del atributo `type` de la notificación usado en el nombre del evento es inferred; el handler de Android está indexado por el token de diccionario 234.)

**Envío con tctoken:** adjunta los bytes almacenados como hijo `<tctoken>` del stanza del mensaje (1..120 bytes), no como un IQ aparte:
```ts
const stored = (await authState.keys.get('tc-token', [recipientJid]))[recipientJid]
if (stored && !isExpired(stored.timestamp)) {
  stanza.content.push({ tag: 'tctoken', attrs: {}, content: stored.token })
}
```

**Renovación (IQ de solicitud, forma found en Android):**
```ts
await sock.query({
  tag: 'iq',
  attrs: { type: 'set', xmlns: 'privacy', to: S_WHATSAPP_NET },
  content: [{ tag: 'tokens', attrs: {}, content: [{
    tag: 'token', attrs: { jid: contactJid, type: 'trusted_contact', t: String(storedTimestamp) }
  }]}]
})
```

### 5.2 CSToken

**Captura de nctSalt desde App-State-Sync:**
```ts
// SyncActionValue field 80 = nctSaltSyncAction
function onMutation(mutation: any) {
  const nctSaltAction = mutation?.syncAction?.value?.nctSaltSyncAction
  if (nctSaltAction?.salt) {
    authState.keys.set({ 'nct-salt': { default: Buffer.from(nctSaltAction.salt) } })
  }
}
```
Un cliente de dispositivo primario, en cambio, crearía por sí mismo 32 bytes aleatorios (como hace `NctSaltProvider`) y enviaría la mutación.

**Cálculo y adjunto del cstoken:**
```ts
import { createHmac } from 'crypto'

async function buildCsTokenNode(recipientJid: string, authState: AuthenticationState, tcTokenBuffer?: Buffer) {
  if (tcTokenBuffer?.length) return null          // tctoken takes priority
  const salt = (await authState.keys.get('nct-salt', ['default']))['default']
  if (!salt || !recipientJid) return null
  const cs = createHmac('sha256', salt).update(Buffer.from(recipientJid, 'utf8')).digest() // 32 bytes
  return { tag: 'cstoken', attrs: {}, content: cs }
}
```
`recipientJid` = la cadena que pasa Android (`Jid.toString()` del destinatario 1:1); usar la forma LID es inferred.

**Stanza resultante:**
```xml
<message to="..." type="text" ...>
  <enc .../>
  <cstoken><!-- 32 raw bytes --></cstoken>
</message>
```

### 5.3 Flujo completo de envío

```
relayMessage(jid, msg)
    │
    ▼
is 1:1 user JID? → NO → skip token attachment
    │ YES
    ▼
valid tc-token in store for this JID?
    │
    ├── YES → <tctoken> child in stanza, no cstoken
    │
    └── NO (cold contact)
            │
            ▼
        load nct-salt → missing → log "no salt" + skip
            │ salt available
            ▼
        cstoken = HMAC-SHA256(salt, utf8(recipient JID string))
        attach <cstoken> node to message stanza
```

### 5.4 Proto para NctSaltSyncAction (parche proto de Baileys)

Agrégalo a tu proto si aún no está presente:
```protobuf
message NctSaltSyncAction {
  bytes salt = 1;
}

// In SyncActionValue:
NctSaltSyncAction nctSaltSyncAction = 80;
```

---

## 6. Gating / Feature Flags

| Flag | Valor | Controla |
|------|-------|----------|
| **24915** | bool | Creación + sync del salt NCT habilitados (`C2AE`) |
| **26897** | int (segundos) | Intervalo mínimo entre re-sincronizaciones del salt |
| **24941** | bool | Contributor de stanza de CSToken activado/desactivado (`F6G`) |
| **18639** | bool | Omitir cstoken para destinatarios GUEST_E2EE |
| **25253** | bool | Habilita `NctSaltSyncMutationHandler` |
| **996** | int (segundos) | Longitud del bucket de tokens enviados (disparador del job, `C230709y3.A04`; también `C14830fL.A01`) |
| **997** | int | Cantidad de buckets válidos de tokens enviados (`C14830fL.A01`) |
| **865** / **909** | int | Longitud de bucket de tokens recibidos / cantidad de buckets válidos (`C14830fL.A02`) |
| **4063** | int | Desplazamiento de bucket en la verificación de re-emisión de `A04` |
| **3802** / **22012** | int | Cantidad de buckets válidos en `A0X` (recencia de emisión real) |
| **20605** | bool | tctoken en nodos `<to>` por dispositivo; selección del JID de usuario del dispositivo en `F6I` |
| **20606** | int | Máx. de usuarios que llevan `<tctoken>` por stanza de fanout |
| **14303** / **15491** | bool | Comportamiento de normalización PN/LID en manager / store |
| `wa_nct_token_send_enabled` | AB-prop (Web) | Compuerta de envío de CSToken exclusiva de WA Web; no aplica a Android (cadena ausente del APK; la compuerta de Android es el flag 24941) |

La semántica de los flags se lee del uso; los valores reales del servidor son unknown.

---

## 7. Casos de error y qué vigilar

| Síntoma | Causa | Solución |
|---------|-------|----------|
| No se adjunta cstoken, envío normal | tctoken presente, flag 24941 desactivado, destinatario guest, o no 1:1 | Esperado (cadenas de log de Android en 3.4) |
| Log de Android `NctTokenGenerator/ no salt available` | No hay salt en SharedPrefs y el dispositivo es un companion (no puede crearlo) | Esperar NctSaltSyncAction / HistorySync |
| Log de Android `recipient LID is empty` | Se pasó una cadena de JID vacía al generador | Asegurar que el JID del destinatario esté resuelto |
| Error `463` del servidor tras enviar | Formato de cadena LID incorrecto | (2.26.26.4, not re-verified; no hay handler de 463 en las rutas de message-send, `F6G`, `AbstractC38971i1` ni del job de privacy-token de 2.26.41.6. La única rama de 463 a nivel de app encontrada es el `onError` de create-group en `NewGroup`, sin relación) |
| Falla `GeneratePrivacyTokenJob` | Un 4xx del servidor no se reintenta; otros errores se reintentan | Volver a solicitar cuando cambie el bucket |
| Token almacenado ignorado | Más antiguo que `C14830fL.A02()` o bucket expirado | Esperar una nueva notificación `privacy_token` |

---

## 8. Distinciones clave

- **tctoken** ≠ **privacy_token** a nivel de nombres: `privacy_token` es el campo anidado de GraphQL, el token de diccionario XMPP (234) y el namespace `xmlns="privacy"`; `tctoken` es el nombre del hijo del stanza, el campo string de GraphQL y el campo proto. Es el mismo token subyacente en contextos distintos.
- **ACSToken** — Android tiene un objeto de configuración de ACS-token (`C31991Nz`: `docId`, `graphQlUrl` = `https://acs.whatsapp.com/graphql`, `surface`, `tokenTtlSeconds`, `acsTokenMaxRedeemCount`) y `hasAcsToken()` en una interfaz relacionada (found). La descripción "Privacy Pass blind tokens for Status/Channels crediting" y el nombre `WAACSTokenUtils` son afirmaciones exclusivas de WA Web de 2.26.26.4 (no aplican a Android, no verificadas). No se encontró vínculo con la ruta de envío de tctoken/cstoken.
- **counter_abuse_token** — Metadatos de Server-ACK en móvil (cadena presente en 2.26.41.6: `C37961fH`, `C13X`, columna de DB en `C09550Rf`). No es un token construido por el remitente.
- **nctSalt** es de toda la cuenta (el mismo salt para todos los destinatarios). La diferenciación por destinatario ocurre en la entrada del HMAC (cadena del JID del destinatario).
- El IQ `xmlns="privacy"` es una **solicitud al servidor** que lleva solo `jid`/`type`/`t`, no un transporte para los bytes del token; los bytes del token viajan en hijos `<tctoken>` y llegan mediante notificación.

---

## 9. Cambios respecto a 2.26.26.4

| Elemento | 2.26.26.4 | 2.26.41.6 |
|----------|-----------|-----------|
| Send manager | `C73O` | `C230709y3` (puntos de entrada A01/A02/A04 más conjunto en curso A05) |
| Token store / caché | `C07730Zd` / `C07760Zg` | `C14820fK` / `C12420b9` "privacytokendatacache" |
| Tipo de dato del token | `C151666s4` | `C9oI` (token+ts); nuevo `C220519e9` (sent ts + real_issue ts) |
| Compuerta de expiración | `C07740Ze.A02()` | `C14830fL.A02()` (flags 865/909; límite de 182 días); lado de envío A01 (996/997) |
| Nombres de tabla / columna | `wa_trusted_contacts(_send)` | sin cambios; más 3 índices found |
| Flag 996 / 24915 / 26897 | listados | sin cambios; se encontraron muchos flags nuevos (ver 6) |
| Claves de SharedPrefs | `privacy_token_last_batch_time_sec`, `nct_salt`, `nct_salt_last_sync_ts` | sin cambios |
| Forma del IQ tc saliente | `<trusted_contact jid type t><token>bytes</token></trusted_contact>` al destinatario | `<tokens><token jid type="trusted_contact" t/></tokens>` al servidor, sin bytes de token (informe corregido a partir del código) |
| Timeout del IQ / int de tipo | 32,000 ms / 299 | sin cambios; 299 es un id de tipo de solicitud IQ, no un flag |
| Diccionario `privacy_token` | 234 | 234 (handler registrado en 234) |
| Token entrante | no documentado | handler de notificación `X.0vv` (`C1S0` case 4888), se prefiere `sender_lid` |
| tctoken en el stanza de mensaje | no documentado | hijo `<tctoken>` mediante `F6I`; también fanout `<to>` (`AbstractC33466EhY`), IQ de foto, presencia |
| tctoken en GraphQL | Solo BizIntegrity | también IntegrityFeaturesContext, `C229259vZ`, `C23694AKh`, `C20L` |
| HMAC de CSToken en Android | no encontrado (quizás nativo) | found en Java: `AbstractC38971i1` + `F6G`; clave salt, datos = cadena del JID del destinatario |
| Inyección de `<cstoken>` de CSToken en Android | no encontrada | found: `NctTokenMessageSendStanzaContributor` (`F6G`), compuertas flags 24941 / 18639 |
| Salt provider | `C57682i2` (redacción "server-generated") | `C67592to`: `SecureRandom` local de 32 bytes solo en el primario, los companions lo omiten |
| Mutación de sync del salt | `C177317vA` | `C52032Bk` (acción `nct_salt_sync`); handler `C0XG`, flag 25253 |
| Disparador del salt | `C37511mA` | `C2AE` (`NewChatMessageCappingAsyncInit`) |
| Salt en HistorySync | no documentado | `HistorySync.nctSalt` (`C25838BCy`) almacenado por `CMP` |
| `nctSalt = 12` en `ConversationThreadInfo` | afirmado | no encontrado; `nctSalt_` existe en HistorySync |
| Campo 80 de SyncActionValue | `C8MG`/`C8HG` | `C49639Lse` / `C49554LrH`, campo 80 confirmado |
| `JidGroupInfo.tcToken = 8`, `contactPrimaryIdentityKey = 9` | afirmado | no existe `JidGroupInfo`; `Conversation` (`BD1`): `tcToken` 21, `tcTokenTimestamp` 22, `contactPrimaryIdentityKey` 23, `tcTokenSenderTimestamp` 28 |
| Número de `NctSaltSyncAction.salt` | no indicado | 1 (único campo) |
| Número de `HistorySync.nctSalt` | no indicado | 19 |
| Int de tipo IQ `299` | "flag 299" | id de tipo de solicitud IQ pasado a `MessageClient`, no un flag |
| `wa_nct_token_send_enabled`, columna de WA Web | afirmado | Solo Web, no aplica a Android; la compuerta de Android es el flag 24941 |
| `463` | afirmado | ningún sitio de código en la ruta de envío; sin verificar |
| ACSToken | "string not found" | clase de configuración ACS `C31991Nz` found (`acs.whatsapp.com/graphql`); la descripción de Privacy Pass es solo Web/sin verificar |
