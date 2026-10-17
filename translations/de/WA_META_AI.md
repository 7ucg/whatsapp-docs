<!-- src-sha1: 64389e16d6c478a5b57f43abf9ee01a01474f02f -->
# WhatsApp Meta AI — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-17
**Umfang:** Meta-AI-Interna — JIDs, Routing, Proto-Felder, Hatch-Metadata-Requests, Rendering der Responses, warum Baileys scheitert, Fix

---

## 1. Was Meta AI ist (technisch)

Meta AI ist ein Bot-Kontakt, der über spezielle Bot-JIDs (Server `bot`) adressiert wird, mit botspezifischen Proto-Feldern auf den normalen Nachrichtentypen und einem separaten JSON-Request-Kanal ("Hatch metadata"), der in einer `ProtocolMessage` transportiert wird. Alle Aussagen beruhen auf statischer Analyse der dekompilierten APK. Tier: **found** = im Code gelesen, **inferred** = aus dem Code abgeleitet, **unknown** = nicht aufgelöst.

Namen in diesem Report, die in 2.26.26.4 obfuskiert waren (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`), wurden anhand stabiler Anker neu aufgelöst; unter diesen Namen existieren sie in 2.26.41.6 nicht.

| Entität | Name in 2.26.41.6 | Rolle |
|--------|----------------|------|
| BotJid | `C24770wv` | JID-Klasse, Server `"bot"`, Typ 26, numerischer String mit 1-20 Zeichen, keine führende 0 |
| Bot-JID-Konstanten | `AbstractC34361Xw` | Hatch-/Fallback-/LID-Konstanten und -Sets |
| JID-Mapping | `AbstractC24760wu` | Mapping Bot ↔ LID, Konvertierung des ausgehenden Ziels |
| Gating | `C39311it` | Feature-Flag-Gating pro JID (`A0E(Jid)`) |
| Hatch-Request-Manager | `HF1` (`HatchMetadataRequestManager`) | JSON-Requests, Pending-Map |
| Hatch-Proto-Builder | `Hf6` | baut `ProtocolMessage.aiMetadataOperation` |
| Message | `C30628DTw` | Proto `Message` |
| WebMessageInfo | `C30626DTu` | Proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | Proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | enthält `botMetadata` |
| BotMetadata | `C30615DTj` | Bot-Metadaten pro Nachricht |
| Bot-Profil-Record | `C199348dm` | Name, Beschreibung, Persona-ID-String, Thumb |

---

## 2. Meta-AI-JIDs

### 2.1 Im Code gefundene JIDs

| Konstante | Klasse | Rolle | Tier |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`) über `AbstractC34361Xw.A00` | **Hatch**, primär. Default-Profil, gebaut in `C223219iv` aus Flag-Payload **26190** | found |
| `1807055946647698` | `C24770wv` (`bot`) über `AbstractC34361Xw.A01` | Fallback. Gesteuert durch Flag 27083 | found |
| `165332417282214` | `C14080dr` (Server `"lid"`) über `AbstractC34361Xw.A02` | LID-Gegenstück zu `…698` | found |
| `1807055946647696` | keine | Manus (Legacy in 2.26.26.4): in 2.26.41.6 **nicht vorhanden** | found (absent) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), plus `A01` = `DeviceJid` Device 0 | Bot-Server-JID, verwendet als Session-/Device-Ziel für einen "bot envelope" (der CoEx-v2-Sync-Request-Handler `C53148Nnt` verschlüsselt die Sync-Payload an sein Primary Device, Log `coexv2 attached bot envelope`), wird zu Recipient-Device-Sets hinzugefügt (`C12M`) und in der Retry-Receipt-Behandlung als Bot-Sender behandelt (`C33020EaI`). Keine Chat-Persona | found (Verwendung); Zweck darüber hinaus inferred |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | JID des eingebauten Default-Profil-Records "Meta AI" (`C9i5.A00`: Name `Meta AI`, Default-Intro-Text). Mitglied des Bot-JID-Tests `AbstractC24760wu.A07` zusammen mit der nächsten Zeile | found |
| `867051314767696555` | `AbstractC24760wu.A01` (Singleton-Set, `C24770wv`) | Zweites Mitglied des Bot-JID-Tests `A07` (`A07(jid)` = `C24770wv` gleich `…135992` oder in diesem Set); `A07` speist `AbstractC199328dk.A00` (ein JID-Klassen-Prädikat). Weiterer Zweck nicht aufgelöst | found (Verwendung), Zweck unknown |
| `17015557208` | `AbstractC24760wu.A04` | Phone-User-String. `A04(jid)` ist true für die LID `165332417282214` oder für diesen Phone User; verwendet mit `A03` (beliebige `C24770wv`-Bot-JID oder PN in den Bereichen 13135550000-13135559999 / 13165550000-13165550099) in `E76.A00` (Klasse 10 vs 1) und im Eligibility-Prädikat `C736539v.ARO`. Liest sich als PN-Identität von Meta AI; was diese zwei Consumer damit tun, ist nicht aufgelöst | found (Verwendung), Zweck unknown |

Sets in `AbstractC34361Xw`: `A05 = {…697, …698}`; `A03 = {…697, …698, 165332417282214}`; Map `A04`: `…697 → […697]`, `…698 → […698, 165332417282214]`.

JID-Typ: Der Report zu 2.26.26.4 führte alle vier als `@s.whatsapp.net` auf. In 2.26.41.6 sind die Bot-JIDs `C24770wv` mit `getServer() = "bot"`; die Gruppen-/LID-JID ist `C14080dr` mit Server `"lid"`. Nicht `s.whatsapp.net` (found).

Tabelle Telefonnummer zu Bot-FBID: `AbstractC199338dl.A00` (`HashBiMap`, 1313555xxxx → FBID, etwa 200 Einträge, z. B. `13135550002 → 867051314767696`). Verwendet von `C0DZ.A08(UserJid)` (`convertPNJidtoBotJidIfExists`) (found).

### 2.2 Routing-Konvertierung

```java
// AbstractC24760wu.A01  (getRemoteTargetJidForOutgoingMessage)
if (A08(jid))   // LID jid with user 165332417282214
    return new C24770wv("1807055946647698");
else            // phone jid
    return C0DZ.A08((UserJid) jid);   // PN -> bot JID via AbstractC199338dl table

// AbstractC24760wu.A00
if (jid is bot "1807055946647698") return new C14080dr("165332417282214");  // bot -> LID
if (jid is bot)                      return C0DZ.A07(userJid);              // bot -> phone jid
```

Found: Bot-JID `…698` ↔ LID `165332417282214`; Bot-Kontakte mit Telefonnummer werden auf Bot-JIDs abgebildet. Die Methode asserted "needs FBID migration" (found).

### 2.3 Das Suffix `$1`: geändert

Der Report zu 2.26.26.4 platzierte `$1` auf der Routing-JID ("wire format", `C1A2.A00()/A01()`). In 2.26.41.6 nicht found:
- Keine Routing-Funktion hängt `$1` an eine JID an. Die Konvertierung in 2.2 erzeugt einfache Bot-JIDs.
- `$1` wird an den Persona-ID-String im Bot-Profil-Record angehängt: `C24121Ab2` macht `personaIdString = botFbid + "$1"`; `C223219iv` hardcodet `"1807055946647697$1"` für das Hatch-Default-Profil (found).
- Dieser String (`C199348dm.A0A`) ist das, was `C33473Ehf.A0G` in `BotMetadata.personaId` schreibt (found).

`$1` gehört also zur Persona-ID, nicht zur Ziel-JID.

### 2.4 isMetaAI-Erkennung

```java
// C39311it
boolean A02() {                       // Hatch
  if (!BRD() || capability("ai_hatch_integration_enabled")) return flag(26189);
  return false;
}
boolean A0E(Jid jid) {
  if (jid == HATCH_697)                 return A02();
  if (jid == FALLBACK_698 || jid == LID_165332417282214) {
    if (!BRD() || capability("ai_maiba_wass_migration_receiving_enabled")) return flag(27083);
  }
  return false;
}
```

Der Manus-Zweig (Flag 25119) ist weg. Bedeutung von `BRD()` und des Capability-Lookups (`C09L.A04`) nicht aufgelöst (unknown).

---

## 3. Feature Flags

| Flag-ID | Verwendung in 2.26.41.6 | Tier |
|---------|------------------|------|
| **25119** | Erscheint nur in Flag-Tabellen (`C06510El`, Default `false` in `C08J`). Kein Reader gefunden. Alter Name `ai_bot_integration_enabled` nicht als String found | found |
| **26189** | Hatch-Gate in `C39311it.A02()`. Default `false` (`C08J`) | found |
| **27083** | Fallback-/LID-Gate in `C39311it.A0E()`. Default `false` | found |
| **26190** | JSON-Config (`name`, `description`, `profile_thumb`) für das Default-Hatch-Profil, gelesen in `C223219iv` | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. Wenn true, wird die Capability `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) an Hatch advertised (siehe 5); `A05` steuert außerdem Connector-Telemetrie/UI (`C28147CLx`, `C1427261o`, `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. Advertised `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77); steuert außerdem die Connector-Verfügbarkeit (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. Advertised `HATCH_ARTIFACT_CARD_ENABLED` (79); wird auch von `HatchSpacesSync` und `C7WL` gelesen | found |

Die Strings `ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` sind keine Flag-Namen. Es sind Einträge einer Feature-String-Liste, die in `C25056AqU` aus den Flags 26189 / 27083 gebaut wird (neben `username_supported`, `post_status_in_companion`, ...); `ai_fbid_migration_receiving_enabled` wird unbedingt hinzugefügt. Empfänger und Zweck der Liste nicht verifiziert.

---

## 4. Proto-Felder

### 4.1 Message (`C30628DTw`) auf oberster Ebene

| Feld | Nummer | Typ | Verwendung |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (einziges Feld `message` = 1) | Für den Bot gewrappte ausgehende Nachricht; gesetzt in `F2K`, `C33284Eea` |
| `botTaskMessage` | **100** | `BD2` | Bot-Task |
| `botForwardedMessage` | **104** | `BD2` | Wrappt eine Nachricht mit `richResponseMessage`; gesetzt in `F3E` |
| `richResponseMessage` | **97** | `DSY` | AI-Response. Felder: `messageType` 1, `submessages` 2, `unifiedResponse` 3, `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | Vorhanden |
| `botGroupParticipantMessage` | **137** | `BD2` | Vorhanden |
| `messageContextInfo` | **35** | `C30624DTs` | Trägt `botMetadata` |
| `protocolMessage` | **12** | `BD3` | Trägt `aiMetadataOperation` (31) |

Feld **77** ist `commentMessage`, nicht `richResponseMessage` (der Report zu 2.26.26.4 hatte 77; für diesen Build falsch, und konsistent mit der separaten richResponseMessage-Recherche: 97).

### 4.2 WebMessageInfo (`C30626DTu`), nicht ContextInfo

Der Report zu 2.26.26.4 führte diese als ContextInfo-Felder auf. In 2.26.41.6 liegen sie auf `WebMessageInfo`:

| Feld | Nummer | Typ | Verwendung |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | Gesetzt in `C34385EwW` aus `C0DZ.A09(userJid)` (Primary-Device-User des Invokers) |
| `isSupportAiMessage` | **70** | bool | Gesetzt in `C34378EwP.C57`, wenn die Nachricht das Flag-Bit `268435456` hat und eine Prüfung besteht; zurückgelesen in `C59`. Zusammen mit `is1PBizBotMessage` (**56**) |
| `supportAiCitations` | **72** | repeated message | Zitate |
| `botTargetId` | **73** | string | Kein Writer im Client: `botTargetId_` erscheint nur als Konstruktor-Default und in der Schema-Tabelle von `C30626DTu`, nirgends sonst zugewiesen (Full-Source-Grep) |
| `agentId` | **47** | string | Vorhanden, nicht analysiert |

Ob und wie diese WebMessageInfo-Felder auf dem Wire erscheinen, ist nicht verifiziert (unknown). "`true` für alle Meta-AI-Nachrichten" ist nicht belegt: Es wird pro Nachrichten-Flag gesetzt, nicht unbedingt.

### 4.3 MessageContextInfo (`C30624DTs`)

| Feld | Nummer | Typ |
|-------|--------|------|
| `botMessageSecret` | **6** | bytes |
| `botMetadata` | **7** | `BotMetadata` (`C30615DTj`) |
| `teeBotMetadata` | **17** | bytes |

### 4.4 BotMetadata (`C30615DTj`)

| Feld | Nummer | Typ | Verwendung |
|-------|--------|------|-----|
| `personaId` | **2** | string | Aus dem Bot-Profil-Record (`C199348dm.A0A`), z. B. `1807055946647697$1`. Kein fester Wert `"meta_ai"` |
| `pluginMetadata` | **3** | `DTL` | Plugin-Config |
| `invokerJid` | **5** | string | Invoker |
| `aiConversationContext` | **20** | bytes | Konversationszustand |
| `botResponseId` | **26** | string | Response-ID |

Weitere vorhandene Felder (Namen aus `*_FIELD_NUMBER`, Typen nicht gelesen): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId` wird in `C33473Ehf.A0G` gefüllt; die Methode kehrt vorzeitig zurück, wenn das Profil keinen Persona-String hat.

### 4.5 PluginMetadata (`DTL`)

| Feld | Nummer | Typ | Wert |
|-------|--------|------|-------|
| `provider` | **1** | int32 | Provider-ID |
| `pluginType` | **2** | enum `C4E0` | Siehe unten |
| `profilePhotoCdnUrl` | **4** | string | |
| `referenceIndex` | **6** | | |
| `expectedLinksCount` | **7** | | |
| `pluginVersion` | **8** | | |
| `parentPluginType` | **11** | | |
| `faviconCdnUrl` | **13** | | |

`C4E0`-Konstanten (Wert = Konstruktor-Ordinal; Gleichheit mit der Proto-Nummer ist inferred): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. Die alten Werte 8/9/15 sind unverändert; das Enum ist größer.

### 4.6 Action-Oneof (`C61331Rfl`, Case-Enum `EnumC61601RkN`)

| Nummer | Case | Tier |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

Dies ist ein Oneof aus Action-Feldern, kein einfaches Wert-Enum. Wo es eingebettet ist, wurde nicht verfolgt (unknown).

### 4.7 AI Metadata Operation (Hatch-Träger)

| Message | Feld | Nummer | Typ |
|---------|-------|--------|------|
| `ProtocolMessage` (`BD3`) | `aiMetadataOperation` | **31** | `C25754B9o` |
| `C25754B9o` | `hatchMetadataSync` | **1** | `BB2` |
| `C25754B9o` | `bizAiMetadataSync` | **2** | `C156236jd` (`serverEvent` = 1) |
| `BB2` | `data` | **1** | bytes |
| `BB2` | `timestampMs` | **2** | int64 |
| `BB2` | `requestId` | **3** | string |

---

## 5. Request-Protokoll (Hatch metadata)

Requests werden von `HF1` (`HatchMetadataRequestManager`) gebaut, Coroutine-Klasse `HatchMetadataRequestManager$sendRequest$2`. Der JSON-Envelope unterscheidet sich von 2.26.26.4: `method` und `params` sind unter `payload` verschachtelt.

```json
{
  "version": 1,
  "type": "req",
  "payload": {
    "method": "<method_name>",
    "params": { },
    "accepts_encoding": ["gzip"]
  }
}
```

`params` und `accepts_encoding` sind optional (found). Die Request-ID steht nicht im JSON; sie ist `BB2.requestId` (ein zufälliger String aus `C20F.A0x()`).

Sendepfad (found):
```
HF1.A01(jid, method, ..., params, viewMode, timeoutMs)
  → sendRequest$2: registers onPart callback in A03[requestId] = GuR(method, onPart)
  → JSON → bytes
  → C02381: A04[requestId] = continuation
  → GwX "HatchMetadataSyncHelper/sendMetadataToHatch" → C37393GKy(jidTo, 138, timestampMs)
       .A02 = payload bytes, .A01 = requestId, .A0M = viewMode
  → Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
```

- Pending Requests: `HF1.A04` (`ConcurrentHashMap`, requestId → Continuation) und `HF1.A03` (requestId → `GuR`). Beide werden in `finally` geleert. Der Report zu 2.26.26.4 nannte nur eine Map `A02`.
- Timeout: gibt `GDB.A00` zurück und loggt `HatchMetadataRequestManager/sendRequest timed out method=`.
- Der Integer `138`, der an `C37393GKy` übergeben wird, ist nicht aufgelöst (unknown).
- Träger ist `ProtocolMessage.aiMetadataOperation` (Feld 31), keine normale Chat-Nachricht (geändert).
- Das Package `com.whatsapp.bot.infra.message.aimetadata` enthält `Ideas*Wire`- / `Idea*Wire`-Klassen (found). Ihre Beziehung zu den Methodennamen ist nur inferred; Methodennamen wurden nicht aufgezählt.
- Die Empfangsseite, die `A04` abschließt, wurde nicht verfolgt. Das Zuordnen einer Response zu `requestId` ist aus der `A04`-Map und `BB2.requestId` inferred.

**Keine eigene XMPP-Namespace**-Behauptung: Im verfolgten Pfad wurde keine `w:ai`- / `wa:ai`-Behandlung gesehen; abwesenheitsbasiert, nicht erschöpfend erneut verifiziert.

**Capability-Advertisement (found, `C33284Eea`):** Wenn das Ziel die Hatch-JID `…697` (`AbstractC34361Xw.A00`) ist und ein Gate besteht, baut der Client `DPJ` (einziges repeated Enum-Feld `capabilities` = 1, Werte `EnumC32144E2q`), und `C33473Ehf.A06` speichert es in `BotMetadata.capabilityMetadata` (13) der ausgehenden Nachricht, zusammen mit `BotMetadata.timezone` (8) = der `TimeZone`-ID des Geräts. Nach Gate hinzugefügte Capabilities:

| Gate | Capability (Enum-Nummer) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| Flag **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| Flag **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| Flag **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

Die Nummern sind das zweite Konstruktorargument des Enums; dass sie den Proto-Nummern entsprechen, ist inferred. Das Enum listet außerdem Rich-Response-Capabilities (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**Request-Beispiele (found, `params`-Keys an den Aufrufstellen gelesen; Ziel ist die Hatch-JID `…697`, sofern die Aufrufstelle nicht die Konversations-JID verwendet):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | gebaut in `HatchIdeasManager$execute$job$1` (Keys nicht gelesen); `onPart`-Callback angehängt |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire` zu JSON serialisiert; `onPart`-Callback angehängt |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` nur wenn nicht leer) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

Form der Bytes in `BB2.data` (found Form, Beispielwerte):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

`accepts_encoding` wird nur geschrieben, wenn `acceptsGzipResponse` des Aufrufers true ist; `params` nur, wenn nicht null. Der `onPart`-Callback wird in `A03` nur registriert, wenn der Aufrufer einen übergibt.

**Chat-Nachricht an den Bot (found Teile):**
- Die ausgehende `Message` wird in `Message.botInvokeMessage` neu gewrappt (`F2K`, `C33284Eea`), der Wrapper `BD2` hält die Nachricht in Feld 1. In `F2K` wird das Wrapping übersprungen (Nachricht direkt gesetzt), wenn `C13S.A00()` false ist, `A10` der Nachricht false ist oder Flag **10646** an ist (found).
- `BotMetadata` wird von `C33473Ehf.A0E` / `A0G` gebaut. `A0G` schlägt den Profil-Record für die Ziel-Bot-JID nach (`C199358dn.A06(userJid)`, Persona-String `C199348dm.A0A`); ist dieser String leer, kehrt die Methode zurück, ohne Bot-Metadaten zu schreiben, andernfalls setzt sie `personaId` (2) und, falls vorhanden, `suggestedPromptMetadata` (4) und weitere Sub-Messages. Der Persona-String wird gespeichert, wenn der Profil-Record erzeugt wird (`C24121Ab2` baut `<id>$1`; `C223219iv` hardcodet `1807055946647697$1` für Hatch). Ob `messageContextInfo` auf der äußeren `Message` oder auf der Nachricht innerhalb von `botInvokeMessage` landet, wurde nicht aufgelöst.
- `botMessageInvokerJid` / `isSupportAiMessage` werden von D36-Hooks (`C34385EwW`, `C34378EwP`) auf `WebMessageInfo` gesetzt.

---

## 6. Response-Protokoll

### 6.1 Transport

Nicht erneut verifiziert wie in 2.26.26.4 angegeben ("normale Nachrichten mit `hatchMetadataSync`-Bytes", Klasse `Azz`). Found: `hatchMetadataSync` liegt in `C25754B9o` innerhalb von `ProtocolMessage.aiMetadataOperation`. Hatch-Responses treffen vermutlich auf demselben Weg ein und werden über `requestId` zugeordnet (inferred). Hatch-Requests sind Methodenaufrufe; es ist nicht belegt, dass sie der Pfad normaler Chat-Antworten sind.

### 6.2 Streaming / Chunks: nicht wie beschrieben unterstützt

Die Tabelle aus 2.26.26.4 (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`) als ein Meta-AI-Streaming-Mechanismus ist in 2.26.41.6 nicht belegt:

| Feld | Wo es in 2.26.41.6 liegt |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` Feld **7** (History-Sync-Notification, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) und `C25838BCy` Feld **5** (History Sync) |
| `isLastChunk` | `C55285Ou6` Feld **8** (Nachricht mit `attestationBundles`, `teeModelConfig`, `violationSignal`; TEE-bezogen) |
| `streamingSidecar` | Feld **18** auf Image-/Video-/Audio-Nachrichten (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | nicht als Proto-Felder found |

Keine Chunk-Reassemblierung von Meta-AI-Antworten gefunden. Was für Hatch existiert: `GuR(method, onPart)` — ein `onPart`-Callback pro Request (found); dass er Teilergebnisse trägt, ist aus dem Namen inferred.

### 6.3 Rich Response (Feld 97)

`richResponseMessage` (`DSY`) = Feld **97** auf `Message`. Rendering-Klassen existieren: `AiRichResponseFooterView` und `UnifiedResponseActionHandlerFactory` (Package `com.whatsapp.conversationrow.botrichresponse`) (found). Zitate: `WebMessageInfo.supportAiCitations` (72). Inhaltstypen (Bilder, Tabellen, Code) hier nicht erneut verifiziert; siehe die separate richResponseMessage-Recherche.

### 6.4 Typing-Indikator

Ausgehend (found, `C199098dN.A01`, Log `HandleMeComposing/handleComposing`): standardmäßiger XMPP-Chat-State, im gelesenen Code kein eigener Namespace.
- Einfacher Fall (kein erwähnter Bot, oder eine Bot-JID, die auf die Default-JID aufgelöst wurde): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Bot im Chat erwähnt: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- Gesendet über `C10140Tq.A0X` mit IQ-Typ-Int 4.

Eingehend (found, Stanza-Handler `C40511kx`): Ein `<chatstate>` mit `composing`-Child (optional `media`) ruft den generischen Composing-Callback mit `from`/`participant` auf; `paused` ruft den Paused-Callback auf. In diesem Handler wurde kein botspezifischer Zweig gefunden, daher läuft ein `composing` einer Bot-JID über denselben Pfad wie bei jedem Kontakt (inferred; eine serverseitige Bot-Typing-Stanza wurde nicht beobachtet). `BotMetadata.progressIndicatorMetadata` (12) und die Capability `PROGRESS_INDICATOR` existieren als separater In-Message-Progress-Mechanismus (nur Namen, nicht verfolgt).

### 6.5 Bot-Profil-Sync

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`) plant `BotProfileForChatListWorker` in `A03()`: ein WorkManager-Request mit dem Tag `BotProfileSyncManager` und `setBackoffCriteria(policy, 1, MINUTES)` sowie einer Constraint (Typwert nicht aufgelöst). Die 1 Minute ist ein Retry-**Backoff**, keine Periode. Das "every ~1 minute" aus 2.26.26.4 ist nicht belegt (geändert). `A02(groupJid, userJid)` fordert ein einzelnes Profil an (`requestBotProfileResult`). Kein Teil des normalen Roster-Sync (unverändert).

Profil-Record `C199348dm`: Bot-Typ (`C1XY`), JID, Anzeigename (`A09`), Beschreibung (`A07`), Persona-String (`A0A`), Thumbs, Timestamp.

### 6.6 Bot-Typ-Strings

`C718732k.A00(String)` bildet ab: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; alles andere wird zu `AnonymousClass399(str)`. Dies sind Bot-Typ-Labels (auch in UI-Filtern verwendet), keine `BotMetadata.personaId`-Werte (found).

---

## 7. Speicherung

- `MetaAiMemoryStore`: In 2.26.41.6 gibt es keine Klasse dieses Namens. Das gefundene Äquivalent ist eine Tabelle `meta_ai_memory`, angelegt von der Schema-Klasse `C23621AHm` (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, Index `meta_ai_memory_memory_content_index` auf `memory_content`. Welche Datenbankdatei sie hält, ist nicht aufgelöst. Verwandt (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; der Name sagt deprecated), SharedPrefs `meta_ai_memory_disclosure_seen` (Voice-Call-Design-Screen, `C29434Cpx`), Capability-Enums `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`) und `BotMetadata.memoryMetadata` (15).
- SharedPrefs-Key `"meta_ai_forward_disclosure_seen"`: vorhanden, boolean, gelesen in `C230589xr.A03` für `ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: vorhanden unter `com.whatsapp.metaai.incognito.infra` (found).
- Getrennte Speicherung von Meta-AI-Chats außerhalb von `msgstore.db` (2.26.26.4, nicht erneut verifiziert): keine Chat-Store-Klasse gefunden; `meta_ai_memory` hält nur Memory-Fakten, die Behauptung ist daher weder belegt noch widerlegt.

---

## 8. Warum Baileys keine Antwort bekommt

Alle Zeilen sind **inferred**: statischer Vergleich der Anforderungen des Clients mit einem Send-Pfad eines Drittanbieters; kein Live-Test.

| Problem | Grundlage in 2.26.41.6 | Tier |
|-------|--------------------|------|
| Falscher Ziel-JID-Typ | Bot-JIDs nutzen Server `bot` (`C24770wv`), nicht `s.whatsapp.net`; Bots mit Telefonnummer werden über eine PN→FBID-Tabelle abgebildet | found (JID-Klasse), inferred (Wirkung) |
| `$1` auf der Routing-JID | Nicht vorhanden. `$1` liegt am Persona-ID-String | found |
| Fehlender `botInvokeMessage`-Wrapper | Der Client wrappt die ausgehende `Message` in Feld 67 (`F2K`) | found, Anforderung inferred |
| Fehlendes `messageContextInfo.botMetadata` | Der Client schreibt `personaId`, `invokerJid` usw. hinein | found, Anforderung inferred |
| `personaId = "meta_ai"` | Nicht das, was der Client sendet; er sendet den Profil-Persona-String (z. B. `1807055946647697$1`) | found |
| Fehlendes `aiConversationContext` | Feld 20 von `BotMetadata`; Verhalten beim ersten Turn unknown | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | WebMessageInfo-Felder, von Client-Hooks gesetzt; Server-Anforderung unknown | unknown |
| `botTargetId` | Kein Writer im Client-Code | found |
| Antwort nicht geparst | `richResponseMessage` ist `Message`-Feld 97 | found |
| Chunk-Reassemblierung | Von der Evidenz aus 2.26.41.6 nicht unterstützt (siehe 6.2) | found |

---

## 9. Baileys-Fix

Es wird keine funktionierende Implementierung behauptet. Das Folgende ist eine strukturelle Skizze, wo Felder laut 2.26.41.6 liegen, als **inferred** markiert; sie wurde nicht gegen einen Server ausgeführt.

### 9.1 Ziel

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

Ob der `bot`-Server-String als Baileys-Relay-Ziel funktioniert und wie der Server das finale Stanza-`to` ableitet, ist unknown.

### 9.2 Feld-Platzierung (nur Form)

```ts
// inferred shape, field numbers found in 2.26.41.6
const content = {
  botInvokeMessage: {            // Message 67, wrapper with message = 1 (found; wrap is conditional, see 5)
    message: {
      extendedTextMessage: { text }
    }
  },
  // Placement of messageContextInfo (outer Message vs. inner message) is unresolved.
  messageContextInfo: {          // Message 35
    botMetadata: {               // MessageContextInfo 7
      personaId: '1807055946647697$1', // BotMetadata 2: profile persona string (found in C223219iv for Hatch)
      invokerJid: yourJid,             // BotMetadata 5: field exists; writer not read
      timezone: 'Europe/Berlin',       // BotMetadata 8: client sets the TimeZone ID when advertising capabilities (Hatch)
      capabilityMetadata: { capabilities: [/* EnumC32144E2q numbers, Hatch only */] } // BotMetadata 13
      // aiConversationContext (20): field exists; client write not traced, do not invent a value
    }
  }
}
```

- Das Einbetten von `botMetadata` in `messageContextInfo` (Feld 7) ist **found**. `capabilityMetadata` (13) und `timezone` (8) werden vom Client nur für Hatch-Ziele geschrieben (found); ihre serverseitige Anforderung ist unknown. Ob das Proto von `baron-baileys-v2` diese Felder bereits hat, ist nicht geprüft; falls nicht, muss das Proto erweitert werden (inferred).
- `isSupportAiMessage` (70) und `botMessageInvokerJid` (58) sind `WebMessageInfo`-Felder. Ob sie auf dem Wire vorhanden sein müssen, ist unknown; nicht in `contextInfo` legen (das war im Report zu 2.26.26.4 falsch).
- `botTargetId`: nirgends im dekompilierten Code ein Client-Writer (found); nicht setzen.
- Das genaue Wrapping (`botInvokeMessage.message` enthält die echte Nachricht vs. daneben) folgt dem Re-Wrapping von `F2K` / `C33284Eea`; das genaue serialisierte Ergebnis wurde nicht reproduziert (unknown).

### 9.3 Response-Behandlung

- Rich Replies: `Message.richResponseMessage` ist Feld **97** (found). Dieses parsen, nicht Feld 77.
- Chunk-Handling entfernen: `chunkOrder` / `isLastChunk` sind keine Meta-AI-Streaming-Felder (6.2).
- Hatch `ProtocolMessage.aiMetadataOperation` (31) ist der JSON-Request-Kanal; für einfache Chat-Antworten ist nicht belegt, dass sie ihn nutzen.

### 9.4 Konversationskontext

`BotMetadata.aiConversationContext` (20) existiert. Dass der Server in Antworten aktualisierten State zurückgibt und dieser zurückgespielt werden muss, ist **inferred** (aus dem Feldnamen und dem Report zu 2.26.26.4); nicht verifiziert.

---

## 10. Flows

### 10.1 Chat-Nachricht an den Bot (client-seitig found, server-seitig inferred)

```
[Client] outgoing Message
    │  F2K / C33284Eea: Message.botInvokeMessage = BD2{ message = original }
    │  C33473Ehf: messageContextInfo.botMetadata{ personaId = profile.A0A, ... }
    │  D36 hooks: WebMessageInfo.botMessageInvokerJid (58), isSupportAiMessage (70)
    ▼
[Routing] AbstractC24760wu.A01: LID 165332417282214 → bot 1807055946647698
    │  phone JID → bot JID via PN→FBID table
    ▼
[WA Server] (not observed; inferred) → Meta AI backend
    ▼
[Client] incoming Message.richResponseMessage (97)  →  AiRichResponseFooterView / UnifiedResponseActionHandlerFactory
```

### 10.2 Hatch-Metadata-Request (client-seitig found)

```
[Feature code] HF1.A01(jid, method, params)
    │  requestId = random; A03[requestId] = GuR(method, onPart); A04[requestId] = continuation
    ▼
JSON {"version":1,"type":"req","payload":{"method","params","accepts_encoding"}} → bytes
    ▼
Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
    ▼
[WA Server] (not observed)
    ▼
Response: matched by requestId (inferred) → continuation resumes; timeout → GDB.A00
```

---

## 11. Änderungen gegenüber 2.26.26.4

| Punkt | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | Legacy, Flag 25119 | Nicht vorhanden. 25119 nur in Flag-Tabellen, kein Reader |
| JIDs 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 sind Server `bot` (`C24770wv`); 165332417282214 ist `lid` (`C14080dr`) |
| Neue JID-Konstanten | keine aufgeführt | `1807055946647699` (CoEx-v2-Bot-Envelope- / Device-Set-Ziel), `2942131436135992` (Default-Meta-AI-Profil-JID, Bot-JID-Test `A07`), `867051314767696555` (zweites `A07`-Mitglied, Zweck unknown), `17015557208` (PN von Meta AI, `A04`) |
| Suffix `$1` | Auf der Routing-JID, `C1A2.A00/A01` | Nicht auf der JID; an den Persona-ID-String angehängt (`C24121Ab2`, `C223219iv`) |
| Routing-Konvertierung | `$1` anhängen | `AbstractC24760wu.A01`: LID `165332417282214` → Bot `…698`, PN → Bot über FBID-Tabelle |
| Flag-Namen 25119/26189/27083 | `ai_*`-Flag-Namen | Strings sind Feature-Listen-Einträge (`C25056AqU`); 26190 = Hatch-Profil-JSON; 37227/37852/37054 steuern die Hatch-Capability-Werte 76 / 77 / 79 |
| `richResponseMessage` | Feld 77 | Feld 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | 67 / 100 / 104 auf "WebMessageInfo" | 67 / 100 / 104 auf `Message`; außerdem 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` nie geschrieben |
| Ort von BotMetadata | "embedded in message" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | Profil-Persona-String, z. B. `1807055946647697$1`; `meta_ai` ist ein Bot-Typ-Label |
| Plugin-Typen | 8, 9, 15 | Gleich, Enum hat 18 Werte (bis 17) |
| Action-Enum | Wert-Enum 1/2/3 | Oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| Hatch-JSON-Envelope | `method`, `params` auf oberster Ebene | Unter `payload` verschachtelt; ergänzt `accepts_encoding` |
| Hatch-Träger | Standardnachricht, Klasse `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; ergänzt `bizAiMetadataSync` (2) |
| Pending-Maps | Eine (`A02`) | Zwei: `A04` Continuations, `A03` `GuR`-Part-Callbacks |
| Streaming-Felder | Eine Meta-AI-Chunk-Tabelle | `chunkOrder` (History Sync), `isLastChunk` (TEE-Nachricht), `streamingSidecar` (Media); `clientStreaming`/`serverStreaming` nicht found |
| Profil-Sync-Intervall | "every ~1 min" | 1 min ist der WorkManager-Backoff, keine Periode |
| `MetaAiMemoryStore` | Vorhanden | Nicht per Name found; Tabelle `meta_ai_memory` (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) found |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Vorhanden | Vorhanden |
| Typing-Indikator (Chatstates) | Found | Found: ausgehend `<chatstate><composing/></chatstate>`, mit `<bot jid/>`, wenn ein Bot erwähnt wird (`C199098dN.A01`); eingehend `composing`/`paused` über den generischen Handler `C40511kx`, kein botspezifischer Zweig |
| Capability-Advertisement | nicht dokumentiert | `BotMetadata.capabilityMetadata` (13) + `timezone` (8) für Hatch; Flags 37227 / 37852 / 37054 bilden auf die Enum-Werte 76 / 77 / 79 ab |
| Hatch-Request-Beispiele | nicht dokumentiert | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
