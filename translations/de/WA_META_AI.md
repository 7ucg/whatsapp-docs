<!-- src-sha1: 92bebfe6214e20e4e50526fbb6583d35cc44e808 -->
# WhatsApp Meta AI — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-17
**Umfang:** Meta AI Internals — JIDs, Routing, Proto-Felder, Hatch-Metadata-Requests, Response-Rendering, warum Baileys fehlschlägt, Fix

---

## 1. Was Meta AI technisch ist

Meta AI ist ein Bot-Kontakt, adressiert über spezielle Bot-JIDs (Server `bot`), mit bot-spezifischen Proto-Feldern auf den normalen Message-Typen und einem separaten JSON-Request-Kanal ("Hatch metadata"), der in einer `ProtocolMessage` transportiert wird. Alle Aussagen sind statische Analyse der dekompilierten APK. Stufe: **found** = im Code gelesen, **inferred** = aus Code abgeleitet, **unknown** = nicht aufgelöst.

Namen in diesem Report, die in 2.26.26.4 obfuskiert waren (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`), wurden über stabile Anker neu aufgelöst; sie existieren in 2.26.41.6 nicht mehr unter diesen Namen.

| Entität | Name in 2.26.41.6 | Rolle |
|--------|----------------|------|
| BotJid | `C24770wv` | JID-Klasse, Server `"bot"`, Typ 26, numerischer String 1-20 Zeichen, keine führende 0 |
| Bot-JID-Konstanten | `AbstractC34361Xw` | Hatch-/Fallback-/LID-Konstanten und -Sets |
| JID-Mapping | `AbstractC24760wu` | bot ↔ LID Mapping, Konvertierung des ausgehenden Ziels |
| Gating | `C39311it` | Feature-Flag-Gating pro JID (`A0E(Jid)`) |
| Hatch-Request-Manager | `HF1` (`HatchMetadataRequestManager`) | JSON-Requests, Pending-Map |
| Hatch-Proto-Builder | `Hf6` | baut `ProtocolMessage.aiMetadataOperation` |
| Message | `C30628DTw` | Proto `Message` |
| WebMessageInfo | `C30626DTu` | Proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | Proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | enthält `botMetadata` |
| BotMetadata | `C30615DTj` | Bot-Metadaten pro Message |
| Bot-Profil-Datensatz | `C199348dm` | Name, Beschreibung, Persona-ID-String, Thumb |

---

## 2. Meta AI JIDs

### 2.1 Im Code gefundene JIDs

| Konstante | Klasse | Rolle | Stufe |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`) via `AbstractC34361Xw.A00` | **Hatch**, primär. Standardprofil gebaut in `C223219iv` aus Flag-Payload **26190** | found |
| `1807055946647698` | `C24770wv` (`bot`) via `AbstractC34361Xw.A01` | Fallback. Gated durch Flag 27083 | found |
| `165332417282214` | `C14080dr` (Server `"lid"`) via `AbstractC34361Xw.A02` | LID-Gegenstück zu `…698` | found |
| `1807055946647696` | keine | Manus (Legacy in 2.26.26.4): **nicht vorhanden** in 2.26.41.6 | found (abwesend) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), plus `A01` = `DeviceJid` Device 0 | Bot-Server-JID, verwendet als Session-/Device-Ziel für eine "Bot-Envelope" (CoEx-v2-Sync-Request-Handler `C53148Nnt` verschlüsselt den Sync-Payload an sein primäres Device, Log `coexv2 attached bot envelope`), hinzugefügt zu Empfänger-Device-Sets (`C12M`), und im Retry-Receipt-Handling als Bot-Sender behandelt (`C33020EaI`). Keine Chat-Persona | found (Nutzung); Zweck darüber hinaus inferred |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | JID des eingebauten Standard-"Meta AI"-Profildatensatzes (`C9i5.A00`: Name `Meta AI`, Standard-Intro-Text). Mitglied des Bot-JID-Tests `AbstractC24760wu.A07` zusammen mit der nächsten Zeile | found |
| `867051314767696555` | `AbstractC24760wu.A01` (Singleton-Set, `C24770wv`) | Zweites Mitglied des `A07`-Bot-JID-Tests (`A07(jid)` = `C24770wv` gleich `…135992` oder in diesem Set); `A07` fließt in `AbstractC199328dk.A00` (ein JID-Klassen-Prädikat). Weiterer Zweck nicht aufgelöst | found (Nutzung), Zweck unbekannt |
| `17015557208` | `AbstractC24760wu.A04` | Phone-User-String. `A04(jid)` ist wahr für die LID `165332417282214` oder für diesen Phone-User; verwendet mit `A03` (jede `C24770wv`-Bot-JID, oder PN im Bereich 13135550000-13135559999 / 13165550000-13165550099) in `E76.A00` (Klasse 10 vs. 1) und im Eligibility-Prädikat `C736539v.ARO`. Liest sich als die PN-Identität von Meta AI; was diese beiden Consumer damit tun, ist nicht aufgelöst | found (Nutzung), Zweck unbekannt |

Sets in `AbstractC34361Xw`: `A05 = {…697, …698}`; `A03 = {…697, …698, 165332417282214}`; Map `A04`: `…697 → […697]`, `…698 → […698, 165332417282214]`.

JID-Typ: Der 2.26.26.4-Report führte alle vier als `@s.whatsapp.net`. In 2.26.41.6 sind die Bot-JIDs `C24770wv` mit `getServer() = "bot"`; die Gruppen-/LID-JID ist `C14080dr` mit Server `"lid"`. Nicht `s.whatsapp.net` (found).

Telefonnummer-zu-Bot-FBID-Tabelle: `AbstractC199338dl.A00` (`HashBiMap`, 1313555xxxx → FBID, ca. 200 Einträge, z. B. `13135550002 → 867051314767696`). Verwendet von `C0DZ.A08(UserJid)` (`convertPNJidtoBotJidIfExists`) (found).

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

Found: Bot-JID `…698` ↔ LID `165332417282214`; Telefonnummer-Bot-Kontakte werden auf Bot-JIDs gemappt. Die Methode enthält die Assertion "needs FBID migration" (found).

### 2.3 Das `$1`-Suffix: geändert

Der 2.26.26.4-Report platzierte `$1` auf der Routing-JID ("Wire-Format", `C1A2.A00()/A01()`). In 2.26.41.6 nicht gefunden:
- Keine Routing-Funktion hängt `$1` an eine JID an. Die Konvertierung aus 2.2 produziert reine Bot-JIDs.
- `$1` wird an den im Bot-Profildatensatz gespeicherten Persona-ID-String angehängt: `C24121Ab2` macht `personaIdString = botFbid + "$1"`; `C223219iv` hardcodet `"1807055946647697$1"` für das Hatch-Standardprofil (found).
- Dieser String (`C199348dm.A0A`) ist es, den `C33473Ehf.A0G` in `BotMetadata.personaId` schreibt (found).

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

## 3. Feature-Flags

| Flag-ID | Nutzung in 2.26.41.6 | Stufe |
|---------|------------------|------|
| **25119** | Erscheint nur in Flag-Tabellen (`C06510El`, Default `false` in `C08J`). Kein Reader gefunden. Alter Name `ai_bot_integration_enabled` nicht als String gefunden | found |
| **26189** | Hatch-Gate in `C39311it.A02()`. Default `false` (`C08J`) | found |
| **27083** | Fallback-/LID-Gate in `C39311it.A0E()`. Default `false` | found |
| **26190** | JSON-Konfiguration (`name`, `description`, `profile_thumb`) für das Standard-Hatch-Profil, gelesen in `C223219iv` | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. Wenn wahr, wird Capability `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) gegenüber Hatch angekündigt (siehe 5); `A05` gated zudem Connector-Telemetrie/UI (`C28147CLx`, `C1427261o`, `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. Kündigt `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) an; gated zudem die Connector-Verfügbarkeit (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. Kündigt `HATCH_ARTIFACT_CARD_ENABLED` (79) an; wird zudem von `HatchSpacesSync` und `C7WL` gelesen | found |

Die Strings `ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` sind keine Flag-Namen. Sie sind Einträge einer Feature-String-Liste, die aus den Flags 26189 / 27083 in `C25056AqU` aufgebaut wird (neben `username_supported`, `post_status_in_companion`, ...); `ai_fbid_migration_receiving_enabled` wird unbedingt hinzugefügt. Empfänger und Zweck der Liste nicht verifiziert.

---

## 4. Proto-Felder

### 4.1 Message (`C30628DTw`) Top-Level

| Feld | Nummer | Typ | Nutzung |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (einziges Feld `message` = 1) | Ausgehende Message, für den Bot gewrappt; gesetzt in `F2K`, `C33284Eea` |
| `botTaskMessage` | **100** | `BD2` | Bot-Task |
| `botForwardedMessage` | **104** | `BD2` | Wrapt eine Message, die `richResponseMessage` enthält; gesetzt in `F3E` |
| `richResponseMessage` | **97** | `DSY` | KI-Antwort. Felder: `messageType` 1, `submessages` 2, `unifiedResponse` 3, `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | Vorhanden |
| `botGroupParticipantMessage` | **137** | `BD2` | Vorhanden |
| `messageContextInfo` | **35** | `C30624DTs` | Trägt `botMetadata` |
| `protocolMessage` | **12** | `BD3` | Trägt `aiMetadataOperation` (31) |

Feld **77** ist `commentMessage`, nicht `richResponseMessage` (der 2.26.26.4-Report hatte 77; für diesen Build falsch, deckungsgleich mit der separaten richResponseMessage-Recherche: 97).

### 4.2 WebMessageInfo (`C30626DTu`), nicht ContextInfo

Der 2.26.26.4-Report führte diese als ContextInfo-Felder. In 2.26.41.6 liegen sie auf `WebMessageInfo`:

| Feld | Nummer | Typ | Nutzung |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | Gesetzt in `C34385EwW` aus `C0DZ.A09(userJid)` (Primary-Device-User des Invokers) |
| `isSupportAiMessage` | **70** | bool | Gesetzt in `C34378EwP.C57`, wenn die Message das Flag-Bit `268435456` trägt und eine Prüfung bestanden wird; zurückgelesen in `C59`. Zusammen mit `is1PBizBotMessage` (**56**) |
| `supportAiCitations` | **72** | repeated message | Zitate |
| `botTargetId` | **73** | string | Kein Writer im Client: `botTargetId_` taucht nur als Konstruktor-Default und in der Schema-Tabelle von `C30626DTu` auf, nirgends sonst zugewiesen (Full-Source-Grep) |
| `agentId` | **47** | string | Vorhanden, nicht analysiert |

Ob und wie diese WebMessageInfo-Felder auf der Leitung erscheinen, ist nicht verifiziert (unknown). "`true` für alle Meta AI Messages" ist nicht gestützt: es wird pro Message-Flag gesetzt, nicht unbedingt.

### 4.3 MessageContextInfo (`C30624DTs`)

| Feld | Nummer | Typ |
|-------|--------|------|
| `botMessageSecret` | **6** | bytes |
| `botMetadata` | **7** | `BotMetadata` (`C30615DTj`) |
| `teeBotMetadata` | **17** | bytes |

### 4.4 BotMetadata (`C30615DTj`)

| Feld | Nummer | Typ | Nutzung |
|-------|--------|------|-----|
| `personaId` | **2** | string | Aus dem Bot-Profildatensatz (`C199348dm.A0A`), z. B. `1807055946647697$1`. Kein fixes `"meta_ai"` |
| `pluginMetadata` | **3** | `DTL` | Plugin-Konfiguration |
| `invokerJid` | **5** | string | Invoker |
| `aiConversationContext` | **20** | bytes | Conversation-State |
| `botResponseId` | **26** | string | Response-ID |

Weitere vorhandene Felder (Namen aus `*_FIELD_NUMBER`, Typen nicht gelesen): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId` wird in `C33473Ehf.A0G` gefüllt; die Methode kehrt früh zurück, wenn das Profil keinen Persona-String hat.

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

`C4E0`-Konstanten (Wert = Konstruktor-Ordinal; dass dies gleich der Proto-Nummer ist, ist inferred): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. Die alten Werte 8/9/15 sind unverändert; das Enum ist größer.

### 4.6 Action-Oneof (`C61331Rfl`, Case-Enum `EnumC61601RkN`)

| Nummer | Case | Stufe |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

Dies ist ein Oneof aus Action-Feldern, kein einfaches Value-Enum. Wo dies eingebettet ist, ist nicht nachverfolgt (unknown).

### 4.7 AI-Metadata-Operation (Hatch-Carrier)

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

Requests werden von `HF1` (`HatchMetadataRequestManager`) gebaut, Coroutine-Klasse `HatchMetadataRequestManager$sendRequest$2`. Der JSON-Envelope unterscheidet sich von 2.26.26.4: `method` und `params` liegen verschachtelt unter `payload`.

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

Send-Pfad (found):
```
HF1.A01(jid, method, ..., params, viewMode, timeoutMs)
  → sendRequest$2: registers onPart callback in A03[requestId] = GuR(method, onPart)
  → JSON → bytes
  → C02381: A04[requestId] = continuation
  → GwX "HatchMetadataSyncHelper/sendMetadataToHatch" → C37393GKy(jidTo, 138, timestampMs)
       .A02 = payload bytes, .A01 = requestId, .A0M = viewMode
  → Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
```

- Pending Requests: `HF1.A04` (`ConcurrentHashMap`, requestId → continuation) und `HF1.A03` (requestId → `GuR`). Beide werden im `finally` gelöscht. Der 2.26.26.4-Report nannte nur eine Map `A02`.
- Timeout: gibt `GDB.A00` zurück und loggt `HatchMetadataRequestManager/sendRequest timed out method=`.
- Die an `C37393GKy` übergebene Integer `138` ist nicht aufgelöst (unknown).
- Carrier ist `ProtocolMessage.aiMetadataOperation` (Feld 31), keine einfache Chat-Message (geändert).
- Das Package `com.whatsapp.bot.infra.message.aimetadata` enthält `Ideas*Wire`-/`Idea*Wire`-Klassen (found). Deren Bezug zu den Methodennamen ist nur inferred; Methodennamen wurden nicht enumeriert.
- Die Empfangsseite, die `A04` vervollständigt, wurde nicht nachverfolgt. Das Matching einer Response zu `requestId` ist inferred aus der `A04`-Map und `BB2.requestId`.

**Behauptung "kein eigener XMPP-Namespace":** Im nachverfolgten Pfad wurde kein `w:ai`-/`wa:ai`-Handling gesehen; absenzbasiert, nicht erschöpfend reverifiziert.

**Capability-Ankündigung (found, `C33284Eea`):** Wenn das Ziel die Hatch-JID `…697` ist (`AbstractC34361Xw.A00`) und ein Gate passiert, baut der Client `DPJ` (einziges repeated-Enum-Feld `capabilities` = 1, Werte `EnumC32144E2q`) und `C33473Ehf.A06` speichert es in `BotMetadata.capabilityMetadata` (13) der ausgehenden Message, zusammen mit `BotMetadata.timezone` (8) = der Device-`TimeZone`-ID. Nach Gate hinzugefügte Capabilities:

| Gate | Capability (Enum-Nummer) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| Flag **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| Flag **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| Flag **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

Die Zahlen sind das zweite Konstruktor-Argument des Enums; dass sie gleich den Proto-Nummern sind, ist inferred. Das Enum führt zudem Rich-Response-Capabilities auf (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**Request-Beispiele (found, `params`-Keys an den Call-Sites gelesen; Ziel ist die Hatch-JID `…697`, sofern die Call-Site nicht die Conversation-JID nutzt):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | gebaut in `HatchIdeasManager$execute$job$1` (Keys nicht gelesen); `onPart`-Callback angehängt |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire` zu JSON serialisiert; `onPart`-Callback angehängt |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` nur wenn nicht leer) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

Form der Bytes in `BB2.data` (found shape, Beispielwerte):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

`accepts_encoding` wird nur geschrieben, wenn das `acceptsGzipResponse` des Callers wahr ist; `params` nur wenn nicht null. Der `onPart`-Callback wird in `A03` nur registriert, wenn der Caller einen übergibt.

**Chat-Message an den Bot (found Teile):**
- Die ausgehende `Message` wird in `Message.botInvokeMessage` re-gewrapped (`F2K`, `C33284Eea`), der Wrapper `BD2` hält die Message in Feld 1. In `F2K` wird das Wrapping übersprungen (Message direkt gesetzt), wenn `C13S.A00()` falsch ist, das `A10` der Message falsch ist, oder Flag **10646** aktiv ist (found).
- `BotMetadata` wird von `C33473Ehf.A0E` / `A0G` gebaut. `A0G` sucht den Profildatensatz für die Ziel-Bot-JID (`C199358dn.A06(userJid)`, Persona-String `C199348dm.A0A`); ist dieser String leer, kehrt die Methode ohne Schreiben von Bot-Metadaten zurück, ansonsten setzt sie `personaId` (2) und, falls vorhanden, `suggestedPromptMetadata` (4) und weitere Submessages. Der Persona-String wird bei Erstellung des Profildatensatzes gespeichert (`C24121Ab2` baut `<id>$1`; `C223219iv` hardcodet `1807055946647697$1` für Hatch). Ob `messageContextInfo` auf der äußeren `Message` oder auf der Message innerhalb von `botInvokeMessage` landet, wurde nicht aufgelöst.
- `botMessageInvokerJid` / `isSupportAiMessage` werden von D36-Hooks (`C34385EwW`, `C34378EwP`) auf `WebMessageInfo` gesetzt.

---

## 6. Response-Protokoll

### 6.1 Transport

Nicht reverifiziert wie in 2.26.26.4 angegeben ("normale Messages mit `hatchMetadataSync`-Bytes", Klasse `Azz`). Found: `hatchMetadataSync` liegt in `C25754B9o` innerhalb von `ProtocolMessage.aiMetadataOperation`. Hatch-Responses treffen vermutlich auf demselben Weg ein und werden per `requestId` gematcht (inferred). Hatch-Requests sind Methodenaufrufe; dass sie der Pfad normaler Chat-Antworten sind, ist nicht gezeigt.

### 6.2 Streaming / Chunks: nicht wie beschrieben unterstützt

Die 2.26.26.4-Tabelle (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`) als ein Meta-AI-Streaming-Mechanismus wird in 2.26.41.6 nicht gestützt:

| Feld | Wo es in 2.26.41.6 liegt |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` Feld **7** (History-Sync-Notification, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) und `C25838BCy` Feld **5** (History-Sync) |
| `isLastChunk` | `C55285Ou6` Feld **8** (Message mit `attestationBundles`, `teeModelConfig`, `violationSignal`; TEE-bezogen) |
| `streamingSidecar` | Feld **18** auf Bild-/Video-/Audio-Messages (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | nicht als Proto-Felder gefunden |

Keine Chunk-Reassembly von Meta-AI-Antworten gefunden. Was für Hatch existiert: `GuR(method, onPart)` — ein `onPart`-Callback pro Request (found); dass er Teilergebnisse trägt, ist aus dem Namen inferred.

### 6.3 Rich Response (Feld 97)

`richResponseMessage` (`DSY`) = Feld **97** auf `Message`. Rendering-Klassen existieren: `AiRichResponseFooterView` und `UnifiedResponseActionHandlerFactory` (Package `com.whatsapp.conversationrow.botrichresponse`) (found). Zitate: `WebMessageInfo.supportAiCitations` (72). Content-Typen (Bilder, Tabellen, Code) hier nicht reverifiziert; siehe die separate richResponseMessage-Recherche.

### 6.4 Typing-Indikator

Ausgehend (found, `C199098dN.A01`, Log `HandleMeComposing/handleComposing`): Standard-XMPP-Chatstate, kein eigener Namespace im gelesenen Code.
- Normalfall (kein erwähnter Bot, oder eine Bot-JID, die auf die Standard-JID aufgelöst wird): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Bot im Chat erwähnt: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- Gesendet über `C10140Tq.A0X` mit IQ-Typ int 4.

Eingehend (found, `C40511kx`-Stanza-Handler): Ein `<chatstate>` mit einem `composing`-Kind (optional `media`) ruft den generischen Composing-Callback mit `from`/`participant` auf; `paused` ruft den Paused-Callback auf. Kein bot-spezifischer Zweig wurde in diesem Handler gefunden, sodass ein `composing` von einer Bot-JID denselben Pfad nimmt wie bei jedem Kontakt (inferred; ein serverseitiges Bot-Typing-Stanza wurde nicht beobachtet). `BotMetadata.progressIndicatorMetadata` (12) und die Capability `PROGRESS_INDICATOR` existieren als separater In-Message-Progress-Mechanismus (nur Namen, nicht nachverfolgt).

### 6.5 Bot-Profil-Sync

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`) planed in `A03()` den `BotProfileForChatListWorker`: ein WorkManager-Request, getaggt `BotProfileSyncManager`, mit `setBackoffCriteria(policy, 1, MINUTES)` und einer Constraint (Typ-Wert nicht aufgelöst). Die 1 Minute ist ein Retry-**Backoff**, keine Periode. Das "alle ~1 Minute" aus 2.26.26.4 ist nicht gestützt (geändert). `A02(groupJid, userJid)` fragt ein einzelnes Profil an (`requestBotProfileResult`). Nicht Teil des normalen Roster-Syncs (unverändert).

Profildatensatz `C199348dm`: Bot-Typ (`C1XY`), JID, Anzeigename (`A09`), Beschreibung (`A07`), Persona-String (`A0A`), Thumbs, Timestamp.

### 6.6 Bot-Typ-Strings

`C718732k.A00(String)` mappt: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; alles andere wird `AnonymousClass399(str)`. Dies sind Bot-Typ-Labels (auch in UI-Filtern verwendet), keine `BotMetadata.personaId`-Werte (found).

---

## 7. Storage

- `MetaAiMemoryStore`: keine Klasse mit diesem Namen in 2.26.41.6. Das gefundene Äquivalent ist eine Tabelle `meta_ai_memory`, erstellt von Schema-Klasse `C23621AHm` (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, Index `meta_ai_memory_memory_content_index` auf `memory_content`. Welche Datenbankdatei sie hält, ist nicht aufgelöst. Verwandt (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; der Name sagt deprecated), SharedPrefs `meta_ai_memory_disclosure_seen` (Voice-Call-Design-Screen, `C29434Cpx`), Capability-Enums `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`), und `BotMetadata.memoryMetadata` (15).
- SharedPrefs-Key `"meta_ai_forward_disclosure_seen"`: vorhanden, boolean, gelesen in `C230589xr.A03` für `ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: vorhanden unter `com.whatsapp.metaai.incognito.infra` (found).
- Separate Speicherung von Meta-AI-Chats außerhalb von `msgstore.db` (2.26.26.4, nicht reverifiziert): keine Chat-Store-Klasse gefunden; `meta_ai_memory` hält nur Memory-Fakten, die Behauptung ist daher weder gestützt noch widerlegt.

### 7.1 Private Search als Bot-Chat-Thread-Art (neu in 2.26.45.10, found)

Neue Klassen (`com.whatsapp.privateai.privatesearch`, `com.whatsapp.searchui.search.psisearch`):

| Klasse | Rolle |
|-------|------|
| `PrivateSearchSessionManager` | Verfolgt den einzigen aktiven/aktuellsten Private-Search-Thread; verweigert das Fortsetzen eines Threads, der von einer neueren Suche überholt wurde |
| `PrivateSearchThreadsManager` | Erstellt einen Bot-Thread der Art `PRIVATE_SEARCH`; erweitert `LX/1gu`, dieselbe `BotThreadsManager`-Basis, die `IncognitoAiThreadsManager` (oben) bereits nutzt |
| `PsiSearchManager` (obfuskiert `LX/JjA`) | Besitzt den Query-Send-/Follow-up-("Echo")-Flow |
| `PsiSearchDialogFragment` | Dialog-UI; ein `"kind"`-Arg von `"TURN_ON_PRIVATE_PROCESSING"` zeigt das Private-Processing-Opt-in-Gate inline an |
| `PsiSearchUnifiedResponseRenderer` | Rendert die Bot-Antwort |

Private Search ist als eine weitere **Bot-Chat-Thread-Art** implementiert, kein neues Netzwerk-Primitiv. `PrivateSearchThreadsManager` ruft den geteilten Bot-Thread-Konstruktor `LX/1gv;->A00(LX/2p4, ...)` mit einem 5-wertigen Enum `LX/2p4`: `UNKNOWN`(0) / `DEFAULT`(1) / `INCOGNITO`(2) / `SIDE_CHAT`(3) / `PRIVATE_SEARCH`(4). `PsiSearchManager` validiert die Art eines Threads erneut gegen diesen Diskriminator vor dem Senden und weist eine leere Query oder einen Nicht-`PRIVATE_SEARCH`-Thread zurück.

**Query-Send-Pfad (found).** `PsiSearchManager.onEchoSelected` baut die ausgehende Message über dasselbe generische Message-Creation-Utility, das andere Chat-Sends nutzen, `LX/D1D;->A05(...)`, und dispatcht das Ergebnis dann über die normale ausgehende Message-Queue (`LX/JjA;->A0H:LX/0JB;->D2A`). Kein GraphQL-/MEX-/IQ-Call erscheint irgendwo in diesem Pfad — es ist derselbe `botInvokeMessage`-(Feld-67-)Wrapping-zur-Bot-JID-Mechanismus, in §11 ("Chat-Message an den Bot") dokumentiert, wörtlich wiederverwendet und hier nicht erneut hergeleitet.

**Was native bleibt (Querverweis).** Die PSI-/TEE-Retrieval-Pipeline, die die Query tatsächlich beantwortet — `TeeClientToolOrchestrator`, `PsiSearchToolHandler` (`wa_search`-Client-Tool), `IplsdHandshakeExecutor`, gestützt durch native `libpsi.so`/`libxplat_psi.so` — ist gegenüber 2.26.41.6 unverändert und in der Labyrinth-/TEE-Recherche der Brain dokumentiert (hier nicht erneut hergeleitet); keine der fünf obigen Klassen fasst sie an — sie bauen lediglich die ausgehende Message und rendern die Antwort.

**Reachability-Urteil: erreichbares Senden, unerreichbarer Wert.** Das Suchauslöse-Senden ist von einem Drittclient erreichbar, genau in dem Sinn, in dem Meta-AI-Chat es bereits ist (§8, §11) — nichts Neues zu überwinden. Nicht erreichbar ist der tatsächliche Datenschutzwert des Features: Die On-Device-PSI-Suche über die lokale Chat-DB und der Attested-Enclave-Round-Trip sind native, und die ausgehende `Message` trägt kein vorberechnetes PSI-Material. Ein Drittclient, der Klartext an die Private-Search-Bot-JID sendet, würde bekommen, was der serverseitige Bot mit einer nicht-PSI'd Klartext-Query macht, nicht WhatsApps eigene Private-Search-Semantik (unknown, in keiner Richtung verifiziert).

### 7.2 Stop-Generation vom Wire-Message-Pfad verschoben (neu in 2.26.45.10)

Der `promptMessageKey`-Fehlerstring (seit 2.26.35.8 vorhanden, gebunden an `FMessageStopGeneration` / `ProtocolMessage.extraJson_`, Typ 26) hat **null Treffer** über alle 14 DEX-Dateien in 2.26.45.10 (found, erschöpfender String-Scan). Das zugrundeliegende Feld `extraJson_` ist weiterhin auf `LX/DHC;` (der `ProtocolMessage`-Host-Klasse) deklariert, wird aber nur innerhalb der eigenen Feld-Deklaration und des Reflection-Arrays dieser Klasse referenziert — kein Getter, keine andere Klasse in der App liest es (found). D8 hat in diesem Build Debug-Info vollständig gestrippt (null rekonstruierbare `DBG_SET_FILE`-Dateinamen über 34.255 Methoden in `classes6.dex`), sodass die obfuskierte Klasse, die früher `FMessageStopGeneration` zugrunde lag, nicht aus Debug-Metadaten festgenagelt werden konnte; die drei `.kt`-Dateinamen-Strings dafür überleben nur als verwaiste String-Pool-Einträge, nicht als erreichbarer Code (found).

Stattdessen gefunden: eine neue, **nicht obfuskierte** Klasse `com/meta/metaai/stopgeneration/data/StopGenerationRepository`, deren `A00(threadIdentifier, messageIdentifier, messageIdString, surface, mode, Continuation)` eine Pando-GraphQL-Mutation `MetaAIStopGenerationMutation` auslöst (Op `xfb_genai_stop_generation`), mit Feldern `thread_identifier`, `message_identifier`, `message_id_string`, `surface`, `mode`, validiert durch generische, nicht string-keyed Null-Checks (`LX/00m;->A09`) — kein `promptMessageKey`-artiger Fehlertext.

Beste Erklärung (**inferred**, nicht belegt): Stop-Generation wurde für diese Surface auf diese GraphQL-Mutation verschoben, statt die alte Wire-Message-Prüfung an Ort und Stelle umzubenennen. Ob der Legacy-`protocolMessage`-/Typ-26-/`extraJson_`-Pfad nun Dead Code ist, für Kompatibilität mit älteren Clients gehalten wird, oder von irgendeinem nicht nachverfolgten Caller weiterhin erreichbar ist, ist **unknown** — kein Caller wurde in diesem Build gefunden, aber ein Single-DEX-statischer Scan kann Entfernung nicht beweisen.

---

## 8. Warum Baileys keine Antwort bekommt

Alle Zeilen sind **inferred**: statischer Vergleich der Client-Anforderungen mit einem Drittanbieter-Sendepfad; kein Live-Test.

| Problem | Basis in 2.26.41.6 | Stufe |
|-------|--------------------|------|
| Falscher Ziel-JID-Typ | Bot-JIDs nutzen Server `bot` (`C24770wv`), nicht `s.whatsapp.net`; Telefonnummer-Bots mappen über eine PN→FBID-Tabelle | found (JID-Klasse), inferred (Effekt) |
| `$1` auf der Routing-JID | Nicht vorhanden. `$1` liegt auf dem Persona-ID-String | found |
| Fehlender `botInvokeMessage`-Wrapper | Client wrapt die ausgehende `Message` in Feld 67 (`F2K`) | found, Anforderung inferred |
| Fehlende `messageContextInfo.botMetadata` | Client schreibt `personaId`, `invokerJid`, etc. hinein | found, Anforderung inferred |
| `personaId = "meta_ai"` | Nicht das, was der Client sendet; er sendet den Profil-Persona-String (z. B. `1807055946647697$1`) | found |
| Fehlender `aiConversationContext` | Feld 20 von `BotMetadata`; Verhalten beim ersten Turn unknown | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | WebMessageInfo-Felder, von Client-Hooks gesetzt; Server-Anforderung unknown | unknown |
| `botTargetId` | Kein Writer im Client-Code | found |
| Antwort nicht geparst | `richResponseMessage` ist `Message`-Feld 97 | found |
| Chunk-Reassembly | Durch 2.26.41.6-Evidenz nicht gestützt (siehe 6.2) | found |

---

## 9. Bot-Signaturverifikation (Content-Authentizität)

Getrennt von allem oben: ein Mechanismus, der dem **empfangenden** Client erlaubt zu verifizieren, dass `richResponseMessage`-Content tatsächlich vom Meta-KI-Backend stammt, unabhängig davon, wer die Message weiterleitete. Die statischen Befunde unten sind `found` im 2.26.41.6-Code; das Replay-Ergebnis in 9.4 ist `tested` (live, auf dem eigenen Account des Autors — keine Traffic-Interception, sondern ein legitimer Client, der seine eigene Message komponiert und weiterleitet).

### 9.1 Proto-Ort

`BotMetadata.verificationMetadata` — Feld **27** (`messageContextInfo` (35) → `botMetadata` (7) → `verificationMetadata` (27)), Typ `DPC`/`BotSignatureVerificationMetadata` (toString offenbart den echten Namen): `proofs[]`, jeweils ein `BotSignatureVerificationUseCaseProof` mit `version` (int), `useCase` (Enum `WA_BOT_MSG` / `WA_TEE_BOT_MSG`), `signature` (bytes), `certificateChain` (repeated bytes, DER X.509).

### 9.2 Verifikationsalgorithmus

Klasse `C33259EeB`, interner Name `BotSignatureVerificationUtils` (aus Log-Strings):

1. **Zertifikatsketten-Validierung** der `certificateChain` gegen einen Trust-Anchor, via `HFg.A01(date, certs, true)`.
2. **Signed-Bytes-Konstruktion**: `"1" + <Telefonnummer-String> + <unifiedResponse-Bytes>` — die Signatur bindet **Content und Telefonnummer zusammen**, nicht Content allein.
3. **EdDSA-Verifikation** (Log: `"EdDSA signature verification result"`) mit dem rohen Ed25519-Schlüssel, extrahiert aus dem SubjectPublicKeyInfo des Leaf-Zertifikats.
4. **Enforcement-Modus**, gelesen aus Config **19590**, Enum `EnumC32057Dzg`: `NONE` (`"none"`, deaktiviert, immer bestanden), `LOG_ONLY` (`"log_only"`, verifiziert + loggt, nie blockierend), `ENFORCE_BLOCKING` (`"enforce_blocking"`, eine fehlgeschlagene Prüfung gibt `false` zurück). Ergebnis gespeichert als `E05`: `UNKNOWN` / `VALID` / `FAILED` / `DOWNLOAD_CONSENT_ACCEPTED`, persistiert in der SQLite-Spalte `bot_message_info.signature_validation_status` (die Tabelle hat zudem `bot_client_public_key`).

### 9.3 Row-Rendering-Gate

`C30085D6v.A00` (Row-Typ-Dispatcher) und `EOK`/`C32608EKo`: Ist der Signaturstatus `FAILED` und Flag **27635** aktiv → maskierte Row `ConversationRowAiUnknownSenderMasked` ("signature verification failed"). Unabhängig davon: Ist die Sender-JID nicht im lokal synchronisierten Bot-Profil-Store (`C224899mg`, derselbe Sync wie `BotProfileSyncManagerImpl`) vorhanden und Flag **27355** aktiv → `ConversationRowAiUnknownSenderPreview` ("unknown sender with unconsented content"), eine consent-gated Preview statt eines Hard Blocks.

### 9.4 Echte Aufnahme und Live-Replay (tested)

Eine echte Meta-AI-Antwort, clientseitig in einer echten Conversation aufgenommen (eigener Account, vom eigenen Client des Autors entschlüsselt — keine Traffic-Interception), trug:

- `botMetadata.verificationMetadata.proofs[0]`: `version: 1`, `useCase: "WA_BOT_MSG"`, eine 64-Byte-(Ed25519-große)-`signature`, eine 2-elementige `certificateChain`.
- Leaf-Zertifikat: `CN=svc:wa-bot-msg-leaf`, Ed25519-Schlüssel, ausgestellt von `Meta WA SS Int CA 2025-09`, kettet zur `Meta WA Feature Root CA` (`O=Meta Platforms Inc.`), Gültigkeit ≈7 Monate (automatisch rotiertes Service-Zertifikat) — der signierende Private Key existiert nur im Backend von Meta.
- `botMetadata.botInfrastructureDiagnostics.botBackend: "CLIPPY"` — ein bisher nicht dokumentierter Bot-Backend-Name (siehe auch "Hatch" in Abschnitten 1-6).
- `messageContextInfo.accountEncryptionAttestation.accountType: "NON_E2EE"`, ein Sibling-Feld von `botMetadata`.
- Delivery-Form: `protocolMessage` mit `type: MESSAGE_EDIT`, `editedMessage.richResponseMessage` (die erste Antwort in einem Thread trifft vorverpackt als Edit eines Placeholders ein), `key.remoteJid` = die eigene JID des Autors.

**Test:** Die exakte `richResponseMessage` + `messageContextInfo.botMetadata` (Signatur und Zertifikatskette byte-für-byte unverändert) wurde via `relayMessage` vom eigenen Gerät des Autors weitergeleitet — nicht von der Bot-JID `867051314767696@bot` — an die eigene Nummer des Autors (dieselbe Nummer, die bereits in den signierten Bytes eingebettet ist).

**Ergebnis:** Der Content rendert mit vollem "KI"-Styling und dem echten Text, gelabelt "Weitergeleitet". Manche Deliveries der identischen Payload zeigten stattdessen "WhatsApp kann die Sicherheit dieser Medien nicht verifizieren. Nur herunterladen, wenn du dem Absender vertraust." mit einer Download-Aktion; ein Tap auf Download offenbarte den identischen Content, passend zum `DOWNLOAD_CONSENT_ACCEPTED`-Status und dem "unknown sender with unconsented content"-Code-Pfad aus 9.3. Eine Delivery zeigte einen generischen "Deine WhatsApp-Version unterstützt dies nicht"-Fallback; Ursache nicht ermittelt (unknown).

**Fazit (tested):** Die kryptografische Prüfung aus 9.2 bindet an *(Content, Telefonnummer)*, nicht an die Identität oder JID des Live-Senders. Eine gültig signierte `richResponseMessage` kann von einem Nicht-Bot-Sender replayed werden und die Signaturverifikation trotzdem bestehen, solange die Nummer des Empfängers zur in der Signatur eingebackenen Nummer passt — der empfangende Client rendert sie als echten KI-Content (höchstens gated durch einen einmaligen, kosmetischen "unknown sender"-Consent-Schritt, kein Hard Block). Dies ist ein Content-Authentizitäts-, kein Sender-Authentizitätsmechanismus; WhatsApps eigene Signal-Layer-Verschlüsselung, nicht diese Signatur, authentifiziert den Live-Sender.

### 9.5 Certificate-Revocation-List-(CRL)-Prüfung (neu in 2.26.45.10, found)

Der Kettenvalidierungs-Schritt aus 9.2 (Schritt 1, "Zertifikatsketten-Validierung... via `HFg.A01`") hat eine CRL-Prüfung sowohl gegen das Leaf- als auch das Intermediate-Zertifikat in `certificateChain` erhalten, vor der Ed25519-Signatur-über-(Telefon, Content)-Prüfung (9.2 Schritt 3). Klassen: `BotPkiCrlGraphQLFetcher`/`BotPkiCrlManager` (`com/whatsapp/bot/infra/message/signature/`), aufgerufen von der 2.26.45.10-Kettenvalidierungs-Klasse `BotSignatureVerificationCertificateManager` (`LX/HEe` — umbenannter Nachfolger von `BotSignatureVerificationUtils`/`C33259EeB` aus 9.2; dieselbe Klasse, bestätigt durch geteilte Log-Strings `"Certificate chain validation successful"`/`"Parsed <n> certificates from chain"`).

- **GraphQL-Op**: `FetchBotPKICRL` auf `whatsapp-android-mex` — Request-Feld `crl_name`, Response `xwa2FetchFeaturePkiCrl` hält die CRL als rohen DER-Byte-Blob (keine vorparste Revoked-Serial-Liste) plus `fetchedAt`-/`nextUpdate`-Timestamps und einen Revoked-Entry-Count.
- **Zwei CRLs im Einsatz**, nach Namen: `whatsapp_simple_signal` für das **Leaf**-Zertifikat, `whatsapp_feature` für das **Intermediate**-Zertifikat (Log-Strings `"...Leaf certificate CRL validation passed"` / `"...is revoked"` / `"...CRL unavailable..."`, dasselbe Paar für "Intermediate").
- **Trust-Anchor**: ein 40-jähriges Root-Zertifikat, als PEM-Literal in `LX/HEe` gepinnt — `CN=Meta WA Feature Root CA`, `O=Meta Platforms Inc.`, EC-Schlüssel, gültig 2025-09-04 bis 2065-09-04. Die eigene Signatur jeder abgerufenen CRL wird gegen den öffentlichen Schlüssel des jeweiligen Issuers verifiziert (`X509CRL.verify(...)`), bevor ihrer Revoked-Liste vertraut wird — außer bei `whatsapp_simple_signal`, die als Sonderfall diesen Selbstverifikationsschritt überspringt (`inferred` Grund, nicht aufgelöst).
- **Caching/Refresh**: Per-`crlName`-`SharedPreferences`-Cache (`crl-data`/`crl-fetched-at`/`crl-next-update`), einmal beim App-Init vorab abgerufen, nachdem der User registriert und die DB bereit ist (Log: `"BotPkiCrlManager/...starting CRL prefetch"`), aktualisiert per Timer, gekoppelt an das eigene `nextUpdate` der CRL (floored auf 60s), und on-demand abgerufen mit einem Backoff-Fenster, falls der Cache fehlt/veraltet ist, wenn eine Prüfung läuft.
- **Effekt**: Ein widerrufenes Leaf- oder Intermediate-Zertifikat lässt die Kettenvalidierung auf dieselbe Weise fehlschlagen wie ein bereits abgelaufenes — das fließt in den bestehenden `E05`-Status (`FAILED`) und das `ENFORCE_BLOCKING`-/`LOG_ONLY`-/`NONE`-Gate aus 9.2 Schritt 4, kein neuer, separater Enforcement-Pfad.
- **Stufe**: found — Op, Namespace, beide crlNames, Cache-/Refresh-Mechanik, Call-Sites, gepinntes Root-Zertifikat. Inferred — exaktes Revoked-Entry-Byte-Layout (Serial vs. vollständige Zert-Bytes) und der Grund, warum `whatsapp_simple_signal` die CRL-Selbstverifikation überspringt. Alles statische Analyse; kein widerrufenes Zertifikat wurde in der Praxis beobachtet.
- **Client-/Baileys-Oberfläche**: `FetchBotPKICRL` ist eine konkrete, benannte MEX-Op, erreichbar auf demselben Weg wie andere `whatsapp-android-mex`-Ops, aber sie füttert nur clientseitige Trust-Entscheidungen über Bot-Message-Zertifikate — sie hat keinen Effekt darauf, was ein Nicht-Client-Sender relayen kann (9.4s Replay-Ergebnis ist unberührt: Revocation ändert Ergebnisse nur für ein tatsächlich widerrufenes Zert, was hier nie ausgelöst wird).

---

## 10. Baileys-Fix

Es wird keine funktionierende Implementierung behauptet. Was folgt, ist eine strukturelle Skizze, wo Felder gemäß 2.26.41.6 liegen, markiert **inferred**; nicht gegen einen Server gelaufen.

### 9.1 Ziel

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

Ob der Server-String `bot` als Baileys-Relay-Ziel funktioniert und wie der Server das finale Stanza-`to` ableitet, ist unknown.

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

- Die Einbettung von `botMetadata` in `messageContextInfo` (Feld 7) ist **found**. `capabilityMetadata` (13) und `timezone` (8) werden vom Client nur für Hatch-Ziele geschrieben (found); deren Server-Anforderung ist unknown. Ob das `baron-baileys-v2`-Proto diese Felder bereits hat, ist nicht geprüft; falls nicht, muss das Proto erweitert werden (inferred).
- `isSupportAiMessage` (70) und `botMessageInvokerJid` (58) sind `WebMessageInfo`-Felder. Ob sie auf der Leitung vorhanden sein müssen, ist unknown; nicht in `contextInfo` legen (das war im 2.26.26.4-Report falsch).
- `botTargetId`: kein Client-Writer irgendwo im dekompilierten Code (found); nicht setzen.
- Exaktes Wrapping (`botInvokeMessage.message`, das die echte Message enthält, vs. daneben) folgt dem `F2K`-/`C33284Eea`-Re-Wrapping; das exakte serialisierte Ergebnis wurde nicht reproduziert (unknown).

### 9.3 Response-Handling

- Rich Replies: `Message.richResponseMessage` ist Feld **97** (found). Das parsen, nicht Feld 77.
- Chunk-Handling entfernen: `chunkOrder` / `isLastChunk` sind keine Meta-AI-Streaming-Felder (6.2).
- Hatchs `ProtocolMessage.aiMetadataOperation` (31) ist der JSON-Request-Kanal; dass einfache Chat-Antworten diesen nutzen, ist nicht gezeigt.

### 9.4 Conversation-Context

`BotMetadata.aiConversationContext` (20) existiert. Dass der Server aktualisierten State in Antworten zurückgibt und dieser zurückgespiegelt werden muss, ist **inferred** (aus dem Feldnamen und dem 2.26.26.4-Report); nicht verifiziert.

---

## 11. Flows

### 10.1 Chat-Message an den Bot (found clientseitig, inferred serverseitig)

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

### 10.2 Hatch-Metadata-Request (found clientseitig)

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

## 12. Änderungen gegenüber 2.26.26.4

| Punkt | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | Legacy, Flag 25119 | Nicht vorhanden. 25119 nur in Flag-Tabellen, kein Reader |
| JIDs 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 sind `bot`-Server (`C24770wv`); 165332417282214 ist `lid` (`C14080dr`) |
| Neue JID-Konstanten | keine aufgeführt | `1807055946647699` (CoEx-v2-Bot-Envelope/Device-Set-Ziel), `2942131436135992` (Standard-Meta-AI-Profil-JID, Bot-JID-Test `A07`), `867051314767696555` (zweites `A07`-Mitglied, Zweck unbekannt), `17015557208` (PN von Meta AI, `A04`) |
| `$1`-Suffix | Auf Routing-JID, `C1A2.A00/A01` | Nicht auf JID; an den Persona-ID-String angehängt (`C24121Ab2`, `C223219iv`) |
| Routing-Konvertierung | `$1`-Anhängung | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`, PN → bot via FBID-Tabelle |
| Flag-Namen 25119/26189/27083 | `ai_*`-Flag-Namen | Strings sind Feature-Listen-Einträge (`C25056AqU`); 26190 = Hatch-Profil-JSON; 37227/37852/37054 gaten Hatch-Capability-Werte 76 / 77 / 79 |
| `richResponseMessage` | Feld 77 | Feld 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | 67 / 100 / 104 auf "WebMessageInfo" | 67 / 100 / 104 auf `Message`; zudem 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` nie geschrieben |
| BotMetadata-Ort | "embedded in message" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | Profil-Persona-String, z. B. `1807055946647697$1`; `meta_ai` ist ein Bot-Typ-Label |
| Plugin-Typen | 8, 9, 15 | Gleich, Enum hat 18 Werte (bis 17) |
| Action-Enum | Value-Enum 1/2/3 | Oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| Hatch-JSON-Envelope | `method`, `params` top-level | Verschachtelt unter `payload`; fügt `accepts_encoding` hinzu |
| Hatch-Carrier | Standard-Message, Klasse `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; fügt `bizAiMetadataSync` (2) hinzu |
| Bot-Signaturverifikation | nicht dokumentiert | Neu: `BotMetadata.verificationMetadata` (27), EdDSA + X.509-Zertkette über (Content, Telefonnummer); live getestet, bindet an Telefonnummer, nicht an Live-Sender (Abschnitt 9) |
| Pending-Maps | Eine (`A02`) | Zwei: `A04`-Continuations, `A03`-`GuR`-Part-Callbacks |
| Streaming-Felder | Eine Meta-AI-Chunk-Tabelle | `chunkOrder` (History-Sync), `isLastChunk` (TEE-Message), `streamingSidecar` (Media); `clientStreaming`/`serverStreaming` nicht gefunden |
| Profil-Sync-Intervall | "alle ~1 Min" | 1 Min ist WorkManager-Backoff, keine Periode |
| `MetaAiMemoryStore` | Vorhanden | Nicht unter diesem Namen gefunden; Tabelle `meta_ai_memory` (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) gefunden |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Vorhanden | Vorhanden |
| Typing-Indikator (Chatstates) | Gefunden | Gefunden: ausgehend `<chatstate><composing/></chatstate>`, mit `<bot jid/>` wenn ein Bot erwähnt wird (`C199098dN.A01`); eingehend `composing`/`paused` via generischem Handler `C40511kx`, kein bot-spezifischer Zweig |
| Capability-Ankündigung | nicht dokumentiert | `BotMetadata.capabilityMetadata` (13) + `timezone` (8) für Hatch; Flags 37227 / 37852 / 37054 mappen auf Enum-Werte 76 / 77 / 79 |
| Hatch-Request-Beispiele | nicht dokumentiert | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
