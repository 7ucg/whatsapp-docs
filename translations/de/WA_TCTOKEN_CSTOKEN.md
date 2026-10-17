<!-- src-sha1: abf07b893763b0d9ab0f43cb7e9b4dab51809e14 -->
# WhatsApp TCToken & CSToken — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-17
**Umfang:** TCToken und CSToken — was sie sind, wie sie funktionieren, Android-APK-Interna, Baileys-Implementierung

---

## 1. Überblick: Was sind diese Tokens?

| Token | Voller Name | Wer stellt ihn aus | Wann verwendet | Zweck |
|-------|-----------|--------------|-----------|---------|
| **tctoken** | Trusted Contact Token | WA-Server | Warmer Kontakt (bestehende Beziehung) | Belegt, dass Sender und Empfänger bereits Kontakt hatten — Anti-Spam-Attestierung |
| **cstoken** | Cold-Start Token (NCT-Fallback) | Client (HMAC-SHA256, found in Android-Java) | Kalter Kontakt (kein gespeicherter tctoken) | Fallback-Anti-Spam-Signal, wenn kein tctoken existiert |

**Kernregel (found):** In der 1:1-Message-Stanza wird `cstoken` nur angehängt, wenn der Store keinen gültigen tctoken für den Empfänger enthält (`NctTokenMessageSendStanzaContributor/ skipped - tctoken present`). `tctoken` wird von einem separaten Contributor angehängt (`PrivacyTokenMessageSendStanzaContributor`).

Beide Tokens sind Anti-Spam-Signale. Was der Server mit ihnen macht, ist vom Client aus nicht sichtbar (inferred: Spam- / Neuchat-Capping, siehe `NewChatMessageCappingAsyncInit` als Salt-Trigger).

Alle Tokens haben die Evidenzstufe **found** (statische JADX-Analyse von 2.26.41.6), sofern nicht als inferred / not re-verified markiert. Nichts ist zur Laufzeit tested.

---

## 2. TCToken (Trusted Contact Token)

### 2.1 Was er ist

Ein vom Server ausgestellter binärer Token, der eine vertrauenswürdige Beziehung zwischen zwei JIDs attestiert. Der Server erzeugt und verteilt ihn. Der Client speichert und sendet ihn erneut. Die Token-Bytes sind für den Client opak (signierte Daten / Algorithmus: unknown).

### 2.2 Wie er angefordert / erneuert wird

**Job:** `GeneratePrivacyTokenJob` — Jobname `"generate-tc-token"`. Er trägt keinen Token: Er fordert den Server auf, einen (neu) auszustellen (siehe 2.4).

**Manager:** `PrivacyTokenSendManager` (`C230709y3`)

**Trigger-Logik (found):**
- Einstiegspunkte `C230709y3.A01(C14080dr, UserJid)`, `A02(UserJid)`, `A04(UserJid)`; `A05` ist ein In-Flight-Dedup-Set (`A03` entfernt daraus).
- `A04`: bucket-basiert. Feature-Flag **996** = Bucket-Länge in Sekunden (<= 0 loggt "Bad bucket configuration" und fällt auf now − 15724800 s = 182 Tage zurück). Der Job wird übersprungen, wenn der gespeicherte Timestamp im aktuellen Bucket oder später liegt.
- SharedPrefs-Key `"privacy_token_last_batch_time_sec"` (gelesen in `A04` und in `AHP`) verfolgt die letzte Batch-Zeit. Flag **4063** (int) ist ein Bucket-Offset, der zusammen damit und mit dem real-issue-Timestamp verwendet wird.
- Flag **14303** (bool) bestimmt, wie die JID normalisiert wird (`A00`): wenn an, `PrivacyTokenStore.A0L` (PN → LID-Mapping); wenn aus, LID → PN über den JID-Mapper. Flag **15491** (bool) deaktiviert analog den PN/LID-Doppel-Lookup im Store (`A02`, `A0Q`).

**Frische-Validierung (found):**
```java
// C14820fK.A0Y(UserJid)  — token for sending
C9oI c9oI = A0M(userJid);
if (c9oI == null || c9oI.A00 < this.A04.A02()) return null;  // expired or missing
return c9oI.A01;
```
Ablauf-Gate `C14830fL` (TokenBucketValidity):
- `A02()` (empfangene Tokens) = `A00(len=flag 865, validBuckets=flag 909)`
- `A01()` (Gültigkeit des gesendeten Timestamps) = `min(A00(flag 996, flag 997), A02())`
- `A00(len, n)` = `max((now/len − (n−1)) * len, now − 15724800)` (15724800 s = 182 Tage harte Untergrenze).

### 2.3 Speicherung

**Datenbanktabellen (`wa.db`), erzeugt von `C23627AHs` / `C23628AHt` (found):**

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
(Die Spaltentypen für `jid` / Primary Key sind in den beiden gelesenen Schema-Klassen nicht sichtbar; die Spalte `jid` wird in allen Queries als Key verwendet. Die genauen DDL-Typen sind inferred.)

**Storage-Manager:** `PrivacyTokenStore` (`C14820fK`), DB-Zugriff über `C14840fM`
- In-Memory-Cache: `C12420b9(10, "privacytokendatacache")`
- Wichtige Methoden:
  - `A0P(UserJid, byte[], long)` — empfangenen Token speichern; überschreibt nur, wenn der neue Timestamp neuer ist ("UPDATE_RECEIVED_TOKEN_IF_NEWER")
  - `A0Y(UserJid)` — Token-Bytes zum Senden (null, wenn abgelaufen)
  - `A0M(UserJid)` — Token + Timestamp lesen
  - `A0O(UserJid)` / `A0N(UserJid)` — sendeseitig `(timestamp, real_issue_timestamp)` (gecacht; `A0O` verwirft Einträge, die älter als `A04.A01()` sind)
  - `A0V(UserJid, long)` / `A0W(UserJid, long)` — gesendeten Timestamp aktualisieren (`A0V` setzt zusätzlich `real_issue_timestamp` auf null)
  - `A0X(UserJid, Integer)` — real-issue-Aktualitätsprüfung mit den Flags **865** und **3802** / **22012**
  - `A0U()` — Cache befüllen (aufgerufen von `NewChatMessageCappingAsyncInit` im Foreground)

**Datentypen:** `C9oI` = `(A00=timestamp, A01=byte[] token)`; `C220519e9` = `(A00=sent timestamp, A01=Long real_issue_timestamp)`.

### 2.4 XMPP-Stanzas

**Ausgehende Anfrage (found, `GeneratePrivacyTokenJob.A0M`)** — wird an die Server-JID (`C19380nJ.A00`) gesendet, nicht an den Kontakt. Sie trägt keine Token-Bytes; sie nennt den Kontakt, den Typ und den gespeicherten Timestamp:

```xml
<iq id="[id]" to="[server]" type="set" xmlns="privacy">
  <tokens>
    <token jid="[contact-jid]" type="trusted_contact" t="[stored-timestamp]"/>
  </tokens>
</iq>
```

Gesendet über `A0W(callback, node, id, 299, 32000L)` (`C10140Tq`, `MessageClient`): Timeout **32,000 ms** (found). `299` ist der IQ-Request-Type-Int: `A0A` loggt ihn als `MessageClient/sendIqWithCallbackInternal ... type=` und speichert ihn mit dem ausstehenden Callback (found). Es ist eine Kennung pro Request-Art, die von vielen IQ-Aufrufstellen geteilt wird (derselbe Slot trägt Werte wie 1, 2, 14, 114, 237, 254, 264, 415), kein Feature-Flag. Welcher Wert welche Anfrage benennt, ist im Client nicht aufgelistet. Job-Retry: `A0O` wiederholt, sofern der Fehlerknoten-Code nicht 4xx ist. Der Job bricht ab ("Token timestamp ... missing or too old to send"), wenn kein gültiger gespeicherter Token-Timestamp vorhanden ist.

**Eingehend (found, `C1S0` case 4888, Handler `X.0vv`)** — registriert für Dictionary-Token **234** (`"privacy_token"`, Tabelle `AbstractC32331E9w`):

```xml
<notification from="[contact-jid]" sender_lid="[lid]?" t="[t]">
  <tokens>
    <token type="trusted_contact" t="[unix-timestamp]">[binary-token-bytes]</token>
  </tokens>
</notification>
```
Nur Kinder mit `type="trusted_contact"` werden gespeichert; fehlender Inhalt wirft "required token element to contain data". Store-Key ist `sender_lid`, falls vorhanden, sonst `from`. `t` fällt auf das `t` des Elternelements zurück. Timestamp-Lookup über `A0P`, das nicht-neuere Tokens ignoriert.

**Ausgehender tctoken-Anhang (found)** — Token-Bytes `1..120` aus `PrivacyTokenStore.A0Y`:

| Wo | Klasse | Form |
|-------|-------|-------|
| 1:1-Message-Stanza | `PrivacyTokenMessageSendStanzaContributor` (`F6I`) | `<tctoken>[bytes]</tctoken>`-Child; fehlt er, obwohl erwartet, loggt `expected token, but missing` und meldet Grund `C99E.A07`. Flag **20605** schaltet auf die User-JID des Geräts um |
| Multi-Device-Fanout | `AbstractC33466EhY.A01` | `<tctoken>` einmal pro User im ersten `<to jid=...>`-Device-Node angehängt; begrenzt durch Flag **20605** (bool) und Flag **20606** (max. User pro Stanza) |
| Profilbild-IQ `w:profile:picture` | `C197098a4.A00` | `<picture ...><tctoken>`-Child |
| Presence-Subscribe | `HandlerThreadC21920sG` case 12 / `C18320lY.A07` | `<presence type="subscribe"><tctoken>` |

### 2.5 GraphQL-Integration

Der gespeicherte Token wird in mehreren GraphQL-Inputs als zusätzlicher Kontext angehängt:

```java
// BizIntegritySignalsGraphQLFetcher / IntegrityFeaturesContextFetcher / C229259vZ / C23694AKh / C20L.A0M
node = GraphQlCallInput("tctoken", base64(token));   // string field
node.put("timestamp", String.valueOf(c9oI.A00));
query_input.put("privacy_token", node);
```

Felder: `tctoken` (Token, Base64 / String-kodiert), `timestamp`, verschachtelt unter `privacy_token`. Aufrufer in 2.26.41.6: BizIntegritySignals, IntegrityFeaturesContext (`use_case INTEGRITY_FEATURES_CONTEXT`), `C229259vZ`, `C23694AKh`, `C20L`.

### 2.6 Proto-Definition

Nicht in einer `JidGroupInfo`-Message: Eine Klasse dieses Namens existiert in 2.26.41.6 nicht. Die persistierten Token-Felder liegen im `Conversation`-Proto (`BD1`, `id` = 1, `messages` = 2) (found, `*_FIELD_NUMBER`-Konstanten):

| Feld | Nummer | Typ |
|-------|--------|------|
| `tcToken` | **21** | bytes |
| `tcTokenTimestamp` | **22** | int64 |
| `contactPrimaryIdentityKey` | **23** | bytes |
| `tcTokenSenderTimestamp` | **28** | int64 |

Die Behauptung aus 2.26.26.4 `JidGroupInfo.tcToken = 8` / `contactPrimaryIdentityKey = 9` gilt für diesen Build nicht.

---

## 3. CSToken / NCT-Token (Cold-Start Token)

### 3.1 Was er ist

Ein **clientseitig berechneter HMAC** über den Recipient-JID-String, mit einem accountweiten Salt (`nctSalt`) als Schlüssel. Er ist der Fallback, wenn kein tctoken existiert.

**Formel (found, Android `AbstractC38971i1.A00(data, key)`):**
```
cstoken = HMAC-SHA256(key=nctSalt, data=utf8(recipientJid.toString()))
```
Ausgabe: 32 Bytes, raw. Der Code prüft nur, dass der String nicht leer ist (Log: `NctTokenGenerator/ recipient LID is empty`), was darauf hindeutet, dass der Empfänger eine LID ist (inferred). Die genaue Eingabeform `<user>@lid` ist eine WA-Web-only-Aussage aus dem 2.26.26.4-Report; sie ist auf Android nicht anwendbar und aus dem APK nicht prüfbar.

### 3.2 NctSalt — woher er kommt

Der Salt wird lokal auf dem Primärgerät erzeugt und über **App-State-Sync** und **HistorySync** an Companions verteilt.

**Erzeugung (found, `NctSaltProvider` = `C67592to.A00()`):**
```java
byte[] salt = loadFromSharedPrefs();            // C2X8.A04()
if (salt == null) {
    if (companionDevice) return null;           // "skipped - companion device"
    salt = new byte[32]; SecureRandom.nextBytes(salt);
    C2X8.A03(salt);                             // persist
    putLong("nct_salt_last_sync_ts", 0L);
}
```
Speicherung `C2X8`: SharedPrefs-Key `"nct_salt"`, Base64 (`NO_WRAP`). Der Ursprung ist also lokales `SecureRandom` auf dem Primärgerät (found), nicht serverseitig erzeugt.

**Trigger (found, `NewChatMessageCappingAsyncInit` = `C2AE`)**: bei App-Foreground / Async-Init:
- Flag **24915** (bool): aktiviert NCT-Salt-Erzeugung und -Sync.
- Wenn `nct_salt_last_sync_ts == 0` oder Flag **26897** (int, Sekunden) > 0 und das Intervall verstrichen ist: neuen `nct_salt_last_sync_ts` schreiben und einen SyncD-Push einplanen (`C3MD` case 36 → `SyncdUpdateHelperImpl/syncNctSalt`).

**Sync-Mutation (found, `NctSaltSyncMutation` = `C52032Bk`)**: trägt den rohen `byte[]`-Salt, Action `EnumC24865AnN.A0x` (`"NctSaltSyncAction"`, Key `"nct_salt_sync"`), eingewickelt in `SyncActionValue`-Feld **80**. Über `C12440bB.A0U/A0O` an Companions gepusht.

**Empfang auf dem Companion (found, `NctSaltSyncMutationHandler` in `C0XG`)**: auf einem Companion speichert `A0S` den Salt über `C2X8.A03` ("Received NCT salt from primary, storing"). Handler aktiviert durch Flag **25253** (bool).

**HistorySync (found, `CMP`)**: `HistorySync.nctSalt` (`C25838BCy.nctSalt_`, Presence-Bit 512) wird über `C2X8.A03` gespeichert ("stored NCT salt from history sync"). Feldnummer **19** (`C25838BCy.NCT_SALT_FIELD_NUMBER`, found).

### 3.3 Proto-Felder

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

DB: Spalte `"nct_salt"` im `wa.db`-Schema registriert (`C09E`, Eintrag `C33501Un("nct_salt", ...)`). Der 2.26.26.4-Report ordnete `nctSalt = 12` `ConversationThreadInfo` zu; in 2.26.41.6 existieren weder eine Klasse dieses Namens noch ein `nctSalt`-Feld außerhalb von HistorySync (`nctSalt_` nur in `C25838BCy`, Nummer 19; `Conversation` `BD1` hat kein Salt-Feld).

### 3.4 HMAC-Berechnung und Stanza (Android vs. Web)

| Aspekt | Android 2.26.41.6 | WA Web (Web-only, not applicable to Android; not checkable from the APK) |
|--------|------------------|--------|
| Salt-Sync (NctSaltSyncAction) | Implementiert (Feld 80) | Ja |
| Salt-Speicherung | SharedPrefs `"nct_salt"` | IndexedDB `"WAWebNctSalt"` |
| HMAC-SHA256-Berechnung | **Found in Java** (`AbstractC38971i1`, `javax.crypto.Mac`) | JavaScript |
| Token-Injektion in die Stanza | **Found in Java** (`NctTokenMessageSendStanzaContributor` = `F6G`) | `<cstoken>`-Node |

**Stanza-Contributor (found, `F6G.ASY`)**, der Reihe nach:
```
flag 24941 off                    → nothing
recipient not a 1:1 user JID      → skip ("not a 1:1 user JID")
flag 18639 on and recipient is GUEST_E2EE → skip ("guest recipient")
PrivacyTokenStore.A0Y(user) != null → skip ("tctoken present")
recipient string empty            → log "recipient LID is empty", fail
salt == null                      → log "no salt available", fail
else  <cstoken>[32 bytes]</cstoken> appended to the message stanza
```
Jede Exception wird abgefangen und geloggt (`skipping cstoken due to ...`); der Versand läuft weiter.

```xml
<message ...>
  ...
  <cstoken>[32 raw bytes]</cstoken>
</message>
```

Flag **24941** (bool) = CSToken-Send-Gate auf Android; **18639** (bool) = Ausschluss von Guest-Empfängern.

---

## 4. Token-Vergleich

| | TCToken | CSToken |
|-|---------|---------|
| Ausgestellt von | WA-Server | Client (HMAC) |
| Algorithmus | Server-definiert (opakes Binary) | HMAC-SHA256 |
| Schlüsselmaterial | Server-erzeugt | `nctSalt` (lokales `SecureRandom`, synchronisiert über App-State / HistorySync) |
| Signierte Daten | Nicht bekannt (opak) | `utf8(recipient JID string)` (LID-Form inferred) |
| Existiert, wenn | Vorheriger Kontakt hergestellt, nicht abgelaufen | Wenn Salt existiert und kein gültiger tctoken |
| Priorität | Zuerst (tctoken gewinnt) | Nur Fallback |
| Stanza | `<tctoken>`-Child in Message / `<to>`-Node / Picture-IQ / Presence; Request-IQ `xmlns="privacy"` an den Server | `<cstoken>`-Child in Message |
| GraphQL | In mehreren Integrity-Queries gesendet | In GraphQL nicht gesehen |
| Speicherung | `wa_trusted_contacts` (+ `_send`) in der DB | SharedPrefs `"nct_salt"` |
| Pro Empfänger | Ja (einer pro JID) | Nein (ein Salt, pro Empfänger berechnet) |

---

## 5. Baileys-Implementierung

Alles in diesem Abschnitt ist Implementierungshilfe (inferred aus den obigen Protokollfakten), kein dekompiliertes Artefakt. Die Stanza-Formen sind auf 2.26.41.6 angepasst; das TypeScript ist untested.

### 5.1 TCToken

**Empfangen und Speichern:**
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
(Der im Event-Namen verwendete Wert des Notification-Attributs `type` ist inferred; der Android-Handler ist auf Dictionary-Token 234 gekeyt.)

**Senden mit tctoken:** die gespeicherten Bytes als `<tctoken>`-Child der Message-Stanza anhängen (1..120 Bytes), nicht als separates IQ:
```ts
const stored = (await authState.keys.get('tc-token', [recipientJid]))[recipientJid]
if (stored && !isExpired(stored.timestamp)) {
  stanza.content.push({ tag: 'tctoken', attrs: {}, content: stored.token })
}
```

**Erneuern (Request-IQ, Form auf Android found):**
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

**nctSalt aus App-State-Sync erfassen:**
```ts
// SyncActionValue field 80 = nctSaltSyncAction
function onMutation(mutation: any) {
  const nctSaltAction = mutation?.syncAction?.value?.nctSaltSyncAction
  if (nctSaltAction?.salt) {
    authState.keys.set({ 'nct-salt': { default: Buffer.from(nctSaltAction.salt) } })
  }
}
```
Ein Primärgerät-Client würde stattdessen selbst 32 Zufallsbytes erzeugen (wie es `NctSaltProvider` tut) und die Mutation pushen.

**cstoken berechnen und anhängen:**
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
`recipientJid` = der String, den Android übergibt (`Jid.toString()` des 1:1-Empfängers); die Verwendung der LID-Form ist inferred.

**Resultierende Stanza:**
```xml
<message to="..." type="text" ...>
  <enc .../>
  <cstoken><!-- 32 raw bytes --></cstoken>
</message>
```

### 5.3 Vollständiger Send-Flow

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

### 5.4 Proto für NctSaltSyncAction (Baileys-Proto-Patch)

Zum eigenen Proto hinzufügen, falls noch nicht vorhanden:
```protobuf
message NctSaltSyncAction {
  bytes salt = 1;
}

// In SyncActionValue:
NctSaltSyncAction nctSaltSyncAction = 80;
```

---

## 6. Gating / Feature-Flags

| Flag | Wert | Steuert |
|------|-------|---------|
| **24915** | bool | NCT-Salt-Erzeugung + -Sync aktiviert (`C2AE`) |
| **26897** | int (Sekunden) | Min. Intervall zwischen Salt-Re-Syncs |
| **24941** | bool | CSToken-Stanza-Contributor an/aus (`F6G`) |
| **18639** | bool | cstoken für GUEST_E2EE-Empfänger überspringen |
| **25253** | bool | Aktiviert `NctSaltSyncMutationHandler` |
| **996** | int (Sekunden) | Bucket-Länge für gesendete Tokens (Job-Trigger, `C230709y3.A04`; auch `C14830fL.A01`) |
| **997** | int | Anzahl gültiger Buckets für gesendete Tokens (`C14830fL.A01`) |
| **865** / **909** | int | Bucket-Länge / Anzahl gültiger Buckets für empfangene Tokens (`C14830fL.A02`) |
| **4063** | int | Bucket-Offset in der `A04`-Re-Issue-Prüfung |
| **3802** / **22012** | int | Anzahl gültiger Buckets in `A0X` (real-issue-Aktualität) |
| **20605** | bool | tctoken in `<to>`-Nodes pro Gerät; Auswahl der Device-User-JID in `F6I` |
| **20606** | int | Max. User, die `<tctoken>` pro Fanout-Stanza tragen |
| **14303** / **15491** | bool | PN/LID-Normalisierungsverhalten in Manager / Store |
| `wa_nct_token_send_enabled` | AB-prop (Web) | WA-Web-only CSToken-Send-Gate; auf Android nicht anwendbar (String im APK nicht vorhanden; das Android-Gate ist Flag 24941) |

Die Flag-Semantik ist aus der Verwendung gelesen; Live-Werte vom Server sind unknown.

---

## 7. Fehlerfälle und worauf zu achten ist

| Symptom | Ursache | Behebung |
|---------|-------|-----|
| Kein cstoken angehängt, normaler Versand | tctoken vorhanden, Flag 24941 aus, Guest-Empfänger oder nicht 1:1 | Erwartet (Android-Log-Strings in 3.4) |
| Android-Log `NctTokenGenerator/ no salt available` | Kein Salt in SharedPrefs und Gerät ist Companion (kann keinen erzeugen) | Auf NctSaltSyncAction / HistorySync warten |
| Android-Log `recipient LID is empty` | Leerer JID-String an den Generator übergeben | Sicherstellen, dass die Recipient-JID aufgelöst ist |
| Server-Fehler `463` nach dem Senden | LID-String-Format falsch | (2.26.26.4, not re-verified; no 463 handler in the message-send, `F6G`, `AbstractC38971i1` or privacy-token job paths of 2.26.41.6. The only app-level 463 branch found is the create-group `onError` in `NewGroup`, unrelated) |
| `GeneratePrivacyTokenJob` schlägt fehl | 4xx vom Server wird nicht wiederholt; andere Fehler werden wiederholt | Erneut anfordern, nachdem der Bucket gewechselt hat |
| Gespeicherter Token wird ignoriert | Älter als `C14830fL.A02()` oder Bucket abgelaufen | Auf neue `privacy_token`-Notification warten |

---

## 8. Wichtige Unterscheidungen

- **tctoken** ≠ **privacy_token** auf Namensebene: `privacy_token` ist das verschachtelte GraphQL-Feld, das XMPP-Dictionary-Token (234) und der Namespace `xmlns="privacy"`; `tctoken` ist der Name des Stanza-Childs, das GraphQL-String-Feld und das Proto-Feld. Derselbe zugrunde liegende Token in unterschiedlichen Kontexten.
- **ACSToken** — Android hat ein ACS-Token-Config-Objekt (`C31991Nz`: `docId`, `graphQlUrl` = `https://acs.whatsapp.com/graphql`, `surface`, `tokenTtlSeconds`, `acsTokenMaxRedeemCount`) und `hasAcsToken()` auf einem verwandten Interface (found). Die Beschreibung "Privacy Pass blind tokens for Status/Channels crediting" und der Name `WAACSTokenUtils` sind WA-Web-only-Behauptungen aus 2.26.26.4 (auf Android nicht anwendbar, nicht verifiziert). Keine Verbindung zum tctoken/cstoken-Sendepfad gefunden.
- **counter_abuse_token** — Server-ACK-Metadaten auf Mobile (String in 2.26.41.6 vorhanden: `C37961fH`, `C13X`, DB-Spalte in `C09550Rf`). Kein vom Sender konstruierter Token.
- **nctSalt** ist accountweit (derselbe Salt für alle Empfänger). Die Differenzierung pro Empfänger erfolgt in der HMAC-Eingabe (Recipient-JID-String).
- Das `xmlns="privacy"`-IQ ist eine **Anfrage an den Server**, die nur `jid`/`type`/`t` trägt, kein Transportweg für die Token-Bytes; Token-Bytes reisen in `<tctoken>`-Children und kommen per Notification an.

---

## 9. Änderungen ggü. 2.26.26.4

| Punkt | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| Send-Manager | `C73O` | `C230709y3` (Einstiegspunkte A01/A02/A04 plus In-Flight-Set A05) |
| Token-Store / Cache | `C07730Zd` / `C07760Zg` | `C14820fK` / `C12420b9` "privacytokendatacache" |
| Token-Datentyp | `C151666s4` | `C9oI` (token+ts); neu `C220519e9` (sent ts + real_issue ts) |
| Ablauf-Gate | `C07740Ze.A02()` | `C14830fL.A02()` (Flags 865/909; 182-Tage-Untergrenze); Sendeseite A01 (996/997) |
| Tabellen- / Spaltennamen | `wa_trusted_contacts(_send)` | unverändert; plus 3 Indizes found |
| Flag 996 / 24915 / 26897 | aufgelistet | unverändert; viele neue Flags found (siehe 6) |
| SharedPrefs-Keys | `privacy_token_last_batch_time_sec`, `nct_salt`, `nct_salt_last_sync_ts` | unverändert |
| Form des ausgehenden tc-IQ | `<trusted_contact jid type t><token>bytes</token></trusted_contact>` an den Empfänger | `<tokens><token jid type="trusted_contact" t/></tokens>` an den Server, keine Token-Bytes (Report anhand des Codes korrigiert) |
| IQ-Timeout / Type-Int | 32,000 ms / 299 | unverändert; 299 ist eine IQ-Request-Type-ID, kein Flag |
| Dictionary `privacy_token` | 234 | 234 (Handler bei 234 registriert) |
| Eingehender Token | nicht dokumentiert | Notification-Handler `X.0vv` (`C1S0` case 4888), `sender_lid` bevorzugt |
| tctoken in der Message-Stanza | nicht dokumentiert | `<tctoken>`-Child über `F6I`; auch Fanout-`<to>` (`AbstractC33466EhY`), Picture-IQ, Presence |
| GraphQL-tctoken | nur BizIntegrity | zusätzlich IntegrityFeaturesContext, `C229259vZ`, `C23694AKh`, `C20L` |
| CSToken-HMAC auf Android | nicht gefunden (evtl. nativ) | in Java found: `AbstractC38971i1` + `F6G`; Key Salt, Daten = Recipient-JID-String |
| CSToken-`<cstoken>`-Injektion auf Android | nicht gefunden | found: `NctTokenMessageSendStanzaContributor` (`F6G`), Gates Flags 24941 / 18639 |
| Salt-Provider | `C57682i2` (Formulierung "server-generated") | `C67592to`: lokales `SecureRandom` mit 32 Bytes nur auf dem Primärgerät, Companions überspringen |
| Salt-Sync-Mutation | `C177317vA` | `C52032Bk` (Action `nct_salt_sync`); Handler `C0XG`, Flag 25253 |
| Salt-Trigger | `C37511mA` | `C2AE` (`NewChatMessageCappingAsyncInit`) |
| Salt in HistorySync | nicht dokumentiert | `HistorySync.nctSalt` (`C25838BCy`), gespeichert durch `CMP` |
| `nctSalt = 12` in `ConversationThreadInfo` | behauptet | nicht gefunden; `nctSalt_` existiert in HistorySync |
| SyncActionValue-Feld 80 | `C8MG`/`C8HG` | `C49639Lse` / `C49554LrH`, Feld 80 bestätigt |
| `JidGroupInfo.tcToken = 8`, `contactPrimaryIdentityKey = 9` | behauptet | kein `JidGroupInfo`; `Conversation` (`BD1`): `tcToken` 21, `tcTokenTimestamp` 22, `contactPrimaryIdentityKey` 23, `tcTokenSenderTimestamp` 28 |
| `NctSaltSyncAction.salt`-Nummer | nicht angegeben | 1 (einziges Feld) |
| `HistorySync.nctSalt`-Nummer | nicht angegeben | 19 |
| IQ-Type-Int `299` | "flag 299" | IQ-Request-Type-ID, an `MessageClient` übergeben, kein Flag |
| `wa_nct_token_send_enabled`, WA-Web-Spalte | behauptet | Web-only, auf Android nicht anwendbar; Android-Gate ist Flag 24941 |
| `463` | behauptet | keine Codestelle im Sendepfad; unverifiziert |
| ACSToken | "string not found" | ACS-Config-Klasse `C31991Nz` found (`acs.whatsapp.com/graphql`); Privacy-Pass-Beschreibung ist Web-only/unverifiziert |
