<!-- src-sha1: aacd3c372c813b12cfe335ddb7b3323c8eed3863 -->
# WhatsApp Hatch/Muse AI Agent — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-11-15
**Umfang:** Hatch/Muse AI-Agent-Internals — attestierter Noise-Gateway-VM-Transport, native Carrier + SEV-SNP-Attestierung, Control Plane und WAFFLE-Onboarding, Agent-Browser noVNC-Stream, Workspace (Spaces, Feed, Goals, Ideas, Artifacts, Approvals, Scheduled Tasks, Connectors), sicherer Credential Store, CVM-Identität/PIN-Recovery (`hatch/cvm`, Vesta OPAQUE), kostenpflichtige Subscription-Stufe, Erreichbarkeits-Verdikt, warum Baileys/velowa es nicht implementieren können

---

## 1. Was Hatch/Muse ist

**Hatch** ist der interne Codename für WhatsApps AI-Agent-Subsystem; **Muse** ist der nutzerseitige Name des Agenten selbst (`str29b7` "Muse manages emails, books tables, and more."). Der Agent ist nicht nur eine Chat-Persona (das ist Meta AI, behandelt in `WA_META_AI.md`): er steuert eine **remote confidential VM ("CVM")**, die im Namen des Nutzers im Web browsen, Scheduled Tasks ausführen, ein eigenes Filesystem halten und Drittanbieter-Dienste aufrufen kann. Alles in diesem Report ist `found`/`inferred` statische Analyse von 2.26.41.6 (`WA-APK-BETA/WhatsApp_2.26.41.6/`), mit einem korrigierten Teilbereich (§6, das `hatch/cvm`-Identitätssystem), der gegen 2.26.45.10-Smali re-verifiziert wurde. **Nichts in diesem Report ist `tested`** — kein Gerät-/Frida-Lauf stützt irgendetwas davon; Lücken bei der dynamischen Bestätigung sind inline markiert.

### 1.1 Haupt-Entitäten

| Entität | Bedeutung |
|--------|---------|
| Hatch | Interner Codename für das gesamte Agent-Subsystem (VM, Workspace, Credential Store, Identitäts-/PIN-Layer) |
| Muse | Nutzerseitiger Agent-Name/Persona |
| CVM | "Cloud VM" / "confidential VM" — die remote Compute-Umgebung des Agenten (AMD SEV-SNP) |
| `HatchVmEndpoint` (`C57830PwR`) | Aufgelöste VM-Verbindungsstruktur: Host, `auth_token`, Ablauf, validierter Token, `notary_token`-Parameter-Map |
| Noise Gateway | Eine separate attestierte Noise-Session zu einem Meta "Noise Gateway", getragen über Tigon, getrennt von der Haupt-WA-Noise_XX/chatd-Session |
| Agent Spaces | Mini-Web-Apps, die der Agent baut und innerhalb der CVM hostet, reverse-proxied zu einer Phone-WebView |
| Connector | Eine registrierte Bindung zwischen dem Agenten und einem Drittanbieter-Dienst (Gmail, Kalender, Messenger, Payment-Rail, Custom-Endpoint) |
| `hatch/cvm` (Vesta) | Das **Geräte-/VM-Identitäts- und Chip-Attestierungs-Recovery-System** des Agenten, PIN-gated OPAQUE PAKE — **kein** Payment-Vault (korrigiert einen früheren Research-Pass, siehe §6) |
| Approval Gate | Human-in-the-loop-Bestätigung vor einer riskanten/irreversiblen Agent-Aktion |

### 1.2 Verhältnis zum Meta-AI-Chat

Muse wird über dieselbe Chat-Oberfläche erreicht wie Meta AI und teilt sich etwas Plumbing (Bot-JID-Capability-Advertisement — siehe §7 — und den Hatch-JSON-Metadaten-Kanal, dokumentiert in `WA_META_AI.md` §5, `HF1`/`HatchMetadataRequestManager`, `ProtocolMessage.aiMetadataOperation`). Aber das Agent-Browser-/VM-/Workspace-System, das dieser Report behandelt, ist ein **separates, deutlich größeres Subsystem**: es läuft überhaupt nicht über die chatd/Noise_XX-Session, hat seinen eigenen nativen Transport und persistiert seinen eigenen State (Goals, Feed, Artifacts, Approvals) serverseitig in der CVM. Private Processing / der TEE-Cluster (Meta AI beantwortet Fragen zu den eigenen Chats, Private Search) ist ein **drittes, eigenständiges** System — siehe §11 für die vollständige Abgrenzung.

---

## 2. Architektur-Überblick

### 2.1 Package-Map

Alle Hatch-/Agent-Aktivitäten sind `android:exported="false"` — kein App-übergreifender Einstiegspunkt; alles wird in-process von der Chat-/Agent-Oberfläche aus gestartet.

| Package | Rolle |
|---------|------|
| `com.whatsapp.hatch.vm` (`p085vm`) | VM-Control-Plane/Lifecycle: `HatchVmLifecycleCoordinator`, `HatchVmApiClient`, `HatchVmWaker`, `HatchVmLeaseGate`, `GraphQlHatchAbraTokenProvider`, `HatchAbraTokenRevoker` |
| `com.whatsapp.hatch.onboarding` | `HatchWaffleOnboarding`, `HatchPairingAuthBrowsingActivity`, `HatchMuseConnectionActivator` |
| `com.whatsapp.hatch.computer` / `.conversation.browser` / `.conversation.approval` | `HatchComputerActivity` (voller VM-Desktop), `HatchBrowserStreamActivity` (Live-Browser im Chat), `HatchBrowserPreviewActivity` (Approval Gate) |
| `com.whatsapp.hatch.feed/goals/ideas/activity/approvalhistory` | Workspace-UI: Feed, Goals + Sub-Goals, Ideas, Approval History |
| `com.whatsapp.hatch.artifacts/media` | Vom Agenten erzeugte Artifacts und Dateien |
| `com.whatsapp.hatch.connectors(.ui)` | Drittanbieter-Connector-Katalog, Connect-Flows, Virtual-Card-Aktion, Permission-Mode pro Connector |
| `com.whatsapp.hatch.identity.ui` | Agent-"Über mich"-Dokumente |
| `com.whatsapp.hatch.scheduledtasks.impl` | UI für wiederkehrende Agent-VM-Tasks |
| `com.whatsapp.hatch.cvm` / `.cvm.pin` | **Kein Vault** — PIN-gated Geräte-/VM-Identitäts-Recovery (Vesta OPAQUE), §6 |
| `com.whatsapp.hatch.subscription(s).iap` | Kaufflow für kostenpflichtige Stufe, §7 |
| `com.whatsapp.bot.agentspaces.*` | "Spaces"-Host: `HatchSpaceActivity` + `HatchSpaceTunnel`-Reverse-Proxy, `NoiseHatchVmTransport`-Adapter |
| `com.whatsapp.bot.agentbrowser.*` | Browser-Engine + VM-Transport: `BrowserSessionController` (noVNC-WebView), `NoiseVmConnection`/`WaNoiseChannel`, `agentbrowser.noise.carrier.*` (native JNI) |
| `com.whatsapp.bot.securecredentials.*` | `SecureCredentialVault` — Credential Store, serverseitig in der CVM |
| `com.whatsapp.bot.agentactivity/agentfeed/agentgoals/agentapprovals` | Daten-/Feed-Layer hinter der `hatch.*`-UI |
| `com.whatsapp.bot.infra.vmmedia` | Roh-Fetch des Agent-VM-Filesystems (`/fs/raw/`, `/media/raw/`) |
| `com.whatsapp.bot.quiz` | `AiQuizViewerActivity` — richResponse-Quiz-Viewer, **kein** VM-Feature (§2.3) |
| `com.crossapp.tigonhttp(.noise)` | Metas geteilter **Tigon**-App-übergreifender nativer HTTP-Stack + `NoiseChannelManagerHolder` |

### 2.2 Drei getrennte Transporte — nicht verwechseln

Das ist die wichtigste strukturelle Tatsache überhaupt, und ein früherer Research-Pass hat sie für einen der drei falsch eingeschätzt (§6.1 korrigiert das):

| # | Transport | Trägt | Blocker für einen Drittanbieter-Client |
|---|-----------|---------|-----------------------------------|
| 1 | **Attestierter Noise-Gateway-VM-Kanal** — `/v1/noise` über Tigon, native `libwa-noise-gateway-carrier-jni.so` | Alles Agent-interaktive: Browser-VM-HTTP (`/api/*`, `/fs/*`, `/spaces/*`), noVNC-Screen-Stream, Workspace-Features, Secure-Credential-CRUD | Nativer Noise+WebSocket-Carrier **und** WAFFLE-Official-Client-Onboarding — hart blockiert |
| 2 | **Plain-HTTPS-Control-Plane** zu `hatch-api.meta.ai` | VM-Wake, Abra-Bearer-Token, Pairing-URL, **und** (korrigiert, §6) die `hatch/vesta-auth/*`/`hatch/cvm-*`-Identitäts-Recovery-Endpoints | Transport ist prinzipiell MITM-beobachtbar (gerootetes Gerät, Pinning-Bypass); die Identitäts-Endpoints brauchen zusätzlich native OPAQUE- + Post-Quantum-Mathematik (`libvesta_client_jni.so`), um gültige Request-Bodies zu produzieren |
| 3 | **Plain MEX/GraphQL** über den gewöhnlichen WhatsApp-`whatsapp-android-mex`/`whatsapp-android-www`-Transport | Lese-/Löschvorgänge für Scheduled Tasks/Reminders (1:1 und Gruppe), Lesen der Subscription-Compliance-Info, Mint des Hatch-Payments-Tokens | Kein nativer/attestierter Blocker — erreichbar wie jede andere MEX-Operation |

Transport 1 ist, was der ursprüngliche (2.26.41.6-)Research-Pass "den Hatch-VM-Transport" nennt und macht die überwältigende Mehrheit der Angriffsfläche des Subsystems aus. Transport 3 ist der **einzige** Teil von Hatch, den ein Baileys/velowa-artiger Client plausibel ansteuern kann.

### 2.3 Nicht Teil der VM — die Quiz-Anbindung

`com.whatsapp.bot.quiz.AiQuizViewerActivity` ist ein Vollbild-Viewer für ein Quiz, das in einer gespeicherten Bot-richResponse-Nachricht eingebettet ist (die richResponse-"Jarvis"-Quiz-Primitive — Territorium von `WA_META_AI.md` §4.3/§6.3, nicht Hatch). Es lädt das Quiz **aus dem lokalen Message Store** per Row-ID + Key + Section (Intent-Extras `ai_quiz_viewer_message_row_id`, `ai_quiz_viewer_quiz_key`, `ai_quiz_viewer_section_index`) — kein Netzwerkaufruf, kein VM-Transport. Hier nur erwähnt, damit es nicht mit einem Hatch-Feature verwechselt wird; siehe §11 für die vollständige Abgrenzungstabelle.

---

## 3. Control Plane und Onboarding

### 3.1 WAFFLE-Onboarding (`found`)

Die erste Nutzung der Agent-Oberfläche führt **`HatchWaffleOnboarding`** aus: der Client beweist, dass er ein echter, unmodifizierter WhatsApp-Build ist, via **WAFFLE**-Integritätsattestierung (dieselbe Official-Client-Attestierungsfamilie wie die `com.whatsapp.waffle.wfac`-Ban-UI/Account-Linking — siehe `WA_CLIENT_INTEGRITY.md` §11 für die Schwester-Komponente WFAC). Log-Breadcrumbs: `"waffle-onboarding"`, `"vm-credentials"`, `"pairing-url"`, `"HatchWaffleOnboarding/link pairing-url-received="`. Ein Drittanbieter-Client kann keinen gültigen WAFFLE-Token produzieren, kann also nicht einmal eine VM provisionieren — das ist der harte Onboarding-seitige Blocker, unabhängig vom Noise-Gateway-Carrier.

### 3.2 Pairing (`found`)

`HatchPairingAuthBrowsingActivity` öffnet eine OAuth-artige **Pairing-URL**, die den WhatsApp-Account mit dem Meta-AI-Agent/Meta-Account verknüpft; Abschluss wird als `pairing-url-received` geloggt.

### 3.3 VM-Wake und der Abra-Bearer (`found`)

`GraphQlHatchAbraTokenProvider` mintet einen GraphQL-"Abra"-Bearer-Token für die VM; `HatchVmApiClient` macht dann:

```
POST https://hatch-api.meta.ai/hatch/vm/wake
{"vm_id": "...", "retry_count": N}
```

Das ist gewöhnliches HTTPS, nicht der Noise-Kanal. Die Response füttert `HatchVmLifecycleCoordinator`s Cached-Endpoint-Logik ("connect cached-endpoint", "invalidateToken failed") und löst sich in einen `HatchVmEndpoint` (`C57830PwR`) auf: Host/Base-URL, `auth_token`, `bearerExpiresAtMs`, validierter-Token-Flag und eine Parameter-Map, die den `/v1/noise`-`notary_token` trägt. `HatchAbraTokenRevoker` handhabt die Invalidierung.

**Erreichbarkeit:** der Wake-Call und das Token-Minting sind plain HTTPS/GraphQL, prinzipiell MITM-beobachtbar auf einem gerooteten Gerät mit Pinning-Bypass — aber nutzlos ohne einen WAFFLE-provisionierten Account, da der Server einem unerkannten Client keinen funktionierenden VM-Endpoint aushändigt (`inferred`; serverseitig nicht unabhängig bestätigt).

---

## 4. Der attestierte Agent-Browser-VM-Transport

Das ist der Haupt-Befund des Subsystems: die Agent-Browser-VM läuft **nicht** über die Haupt-WhatsApp-Noise/XMPP-Session. Sie öffnet eine **separate Noise-Session zu einem Meta-"Noise-Gateway"**, getragen über Metas Tigon-HTTP-Stack, durch eine dedizierte native Library, mit einem Attestierungs-Verifier und einem optionalen Pre-Shared-Private-Auth-Key.

### 4.1 Handshake (`found`, `WaNoiseChannel`)

`WaNoiseChannel` nimmt den VM-Endpoint-Host und hängt URL-kodierte Query-Parameter vor dem Handshake an:

| Parameter | Quelle |
|-------|--------|
| `auth_token` | `HatchVmEndpoint.auth_token` (VM-Bearer) |
| `notary_token` | Wert für Key `/v1/noise` in der Parameter-Map des Endpoints, nur wenn nicht leer |
| `app_id` | WA-App-ID-Konstante (`inferred`, nicht literal aufgelöst) |
| `app_version` | hartcodiertes Literal `"2.26.41.6"` |

Handshake-Pfad: **`/v1/noise`**. Handshake-Timeout **20000 ms**; Gesamt-Channel-Open-Budget **60000 ms** (`NoiseVmConnection`). Log-Breadcrumbs: `noise/open-start`, `noise/reused`, `noise/closed reason=...`, `noise/use-once`.

### 4.2 Nativer Carrier und Attestierung (`found`)

`NoiseGatewayCarrier` ist ein `com.facebook.jni.HybridData`-JNI-Objekt, geladen von `NoiseGatewayCarrierSoLoader` als **`libwa-noise-gateway-carrier-jni.so`** — keine losen Datei in `lib/arm64-v8a/`, sondern eingepackt im Superpack-`libs.so`-Blob (keine byte-exakte statische Extraktion verfügbar).

Native Entry Points: `createNative(TigonServiceHolder, NoiseChannelManagerHolder)`, `start(endpoint, ..., byte[32]?, AttestationVerifierHolder, Stream0Listener)`, `sendWebsocketFrameNative`, `stopNative`, `cancelHandshakeNative`. `Stream0Listener`-Callbacks (`onWebSocketUpgraded`, `onTransportReady`, `onReady(NoiseHandshakeOutcome)`, `onMessage`, `onClose/onFailure`) zeigen, dass der Kanal **Noise, eingerahmt in einem WebSocket**, ist.

`AttestationVerifierHolder` hat drei native Konstruktoren:

| Variante | Bedeutung |
|---------|---------|
| `createNoOpNative()` | Keine Attestierung — die Variante, die im dekompilierten Pfad in diesem Pass instanziiert gesehen wurde |
| `createSnpNative(bool)` | AMD-SEV-SNP-Confidential-Compute-Attestierung |
| `createSnpPinnedToChipsNative(chips[], bool)` | SNP, gepinnt auf bestimmte erlaubte Chip-IDs |

**Welche Variante zur Laufzeit läuft, ist `unknown`** aus diesem statischen Pass. Der 2.26.45.10-`hatch/cvm`-Pass (§6) fand unabhängig die konkreten Control-Plane-Endpoints, die SEV-SNP-Chip-IDs allowlisten/committen (`/hatch/cvm-chip-allowlist`, `/hatch/cvm-chip-selection`), was bestätigt, dass der pinned-Chip-Attestierungsmodus echte Infrastruktur ist, nicht nur ein ruhender Codepfad.

`NoisePrivateAuthMode.REQUIRED` plus ein 32-Byte-Key ist ein optionaler Pre-Shared-Key-"Private Auth"-Modus (`inferred`: Channel Binding); im gesehenen Pfad nicht befüllt, `unknown` ob er jemals verwendet wird.

### 4.3 HTTP-über-Noise-Transport (`found`)

Sobald der Kanal steht, senden `WaVmHttpTransportImpl`/`VmHttpClient` gewöhnliche JSON-HTTP-Requests durch den Noise-Tunnel via Tigon. Der App-Level-Adapter (`NoiseHatchVmTransport`, verwendet von jedem Workspace-Feature in §5) exponiert vier Verben:

| Verb | Tag | Verwendung |
|------|-----|-----|
| `CQ4(url, accept)` | `hatch_vm_read` | GET-Lesen |
| `AEV(method,url,body,…)` | `hatch_vm_call` | generischer Einmal-Call |
| `CXY(method,url,headers,body,streaming)` | `hatch_vm_request` | gestreamter Request (120 s, oder unbegrenzt bei `streaming`) |
| `Cly(url,body,…)` | `hatch_vm_subscribe` | langlebiges SSE-/Duplex-Subscribe |

`NoiseChannelHolds` zählt offene "Holds" per Refcount; der Kanal baut ab, nachdem das letzte Hold freigegeben wurde (konfigurierbares Intervall). VM-HTTP-Pfad-Oberfläche (`found`, String-Literale): `/v1/noise`, `/api/`, `/api/computer/subscribe`, `/api/artifacts/pin`, `/spaces/`, `/spaces/v2`, `/spaces/cvm/<slug>`, `/spaces/share/`, `/workspace/`, `/home/hatch/`, `/media/raw/`, `/fs/raw/`, plus Credential-Pfade in §5.9.

### 4.4 Der noVNC-Screen-Stream (`found`)

`assets/vmvnc/` bündelt einen echten **noVNC**-Web-Client (`novnc-rfb.js`, `vnc.html`, MPL-2.0-`LICENSE.txt`) — unabhängig bestätigt sowohl im 2.26.41.6- als auch im 2.26.45.10-Build vorhanden (`assets-sweep.md`). `BrowserSessionController` lädt `https://appassets.androidplatform.net/assets/vmvnc/vnc.html` in eine WebView. Das HTML definiert einen **`BridgedWebSocket`**, der `window.WebSocket` überschreibt: noVNC glaubt, es habe `wss://bridge.invalid/` (Subprotocol `binary`) geöffnet, aber jedes RFB-Frame wird über die Android-JS-Bridge `window.AndroidVncBridge` (`socketSend`/`socketClose`/`socketOpen`, Callbacks `window.__vncBridge.*`) weitergeleitet. Der eigene Kommentar des gelieferten HTML erklärt, warum: **der echte websockify-Endpoint verlangt `Authorization: Bearer <jwt>`**, was ein WebView-WebSocket nicht setzen kann, also besitzt nativer Code den echten Socket (geöffnet über Tigon mit dem VM-Bearer), und das JS-Shim relayt nur Frames.

Netto: der VM-Desktop/Browser wird zum Phone als echtes **RFB (VNC) über einen JWT-Bearer-authentifizierten WebSocket** gestreamt, selbst getunnelt durch das attestierte Noise Gateway; noVNC rendert ihn in einer WebView. Input-Gating (`isViewOnly`, `isInputEnabled`, `isPanModeEnabled`, Zoom-/Viewport-Methoden) und Sizing (`BrowserViewerJson{width,height,devicePixelRatio}`) sind native-gesteuert. `inferred`: leichtgewichtigere "Present"-/Preview-Standbilder (`BrowserTaskScreenshotJson`, `BrowserTaskPresentationJson`) füttern die In-Chat-`HatchBrowserStreamActivity`, während volles interaktives VNC `HatchComputerActivity` vorbehalten ist.

### 4.5 Control Lease (`found`)

`BrowserControlLeaseJson{controlOwner, taskId, controlExpiresAtMs}` + `BrowserControlGrantJson`/`BrowserControlEnvelopeJson` implementieren, wer den Browser steuert (Agent vs. Mensch "take control"), zeitlich begrenzt durch `controlExpiresAtMs`. `BrowserViewerRequestJson` fordert einen Viewer-Slot an. Nicht verwechseln: diese **Browser-Control-Lease** und das unverbundene SEV-SNP-**Chip-Selection-"Bid"** in §6 — siehe §11.

### 4.6 Das Agentspaces-Tunnel-Framing (`found`)

`HatchSpaceTunnel` proxyt eine WebView zu CVM-gehosteten "Spaces"-Apps unter `/spaces/cvm/<slug>` über `hatch_vm_*`. Das kleine JSON-Envelope-Protokoll: `{"type":"http.res",id,status,streaming}`, `{"type":"http.end",…}`, `{"type":"http.err",…}`, plus ein Cache-Busting-Push `{"type":"hatch:space:query-invalidated","spaceSlug":…,"payload":{"queryKeys":[…]}}`. Es **entfernt Hop-by-Hop- und identifizierende Header** vor dem Relaying — Blocklist umfasst `authorization, cookie, host, origin, x-forwarded-*, x-real-ip, x-noise-connection-id` — was bestätigt, dass die CVM-Seite einen echten HTTP-Server terminiert, der nur über die Noise-Connection-ID erreichbar ist.

---

## 5. Der Agent-Workspace

Jedes Feature unten baut auf den vier `NoiseHatchVmTransport`-Verben aus §4.3 auf, d. h. jedes Pfad-Literal unten ist ein HTTP-Request *innerhalb* des Noise-Tunnels zur CVM. Bootstrap: `HatchBootstrapRequest` postet `{"sections":[…]}` auf einer `channel.bootstrap`-Subscribe-Methode und liest `{"accepted":[…]}` zurück — der Client deklariert, welche Workspace-Sections er gepusht bekommen möchte. `HatchSpacesSync` startet erst, wenn "Hatch is linked and a VM endpoint exists" (`found` Log-Guards).

### 5.1 Agent Spaces

Ein **Space** ist eine vom Agenten gehostete Mini-Web-App/interaktive Ergebnisseite, die innerhalb der CVM serviert wird, adressiert durch einen String-`slug`. Das Phone erhält das HTML nie direkt — eine lokale WebView (`HatchSpaceActivity`) zeigt auf den Tunnel (§4.6), der die HTTP-Responses der CVM Frame für Frame zurückstreamt, sodass ein Space eine lebende, zustandsbehaftete App sein kann statt ein statisches Artifact.

| Aktion | Methode + Pfad | Hinweise |
|--------|---------------|-------|
| Katalog | `GET /spaces/v2` | `{"spaces":[{"slug","preview_card_url","preview_image",…}]}` |
| Share-Status | `GET /spaces/share/<slug>` | liefert eine Share-URL, falls geteilt+öffentlich |
| Publish | mehrstufig (`publish`/`post`/`poll`) | kann "needs confirmation" liefern |
| Unpublish | `DELETE /spaces/share/<slug>` | |
| Delete | `DELETE /spaces/v2/<slug>?source=space` | |
| Pin / Unpin Artifact | `POST /api/artifacts/pin {"artifact_ref":…,"pinned":bool}` | pinnt den Output eines Space als Artifact |

Praxisbeispiel (`inferred`): der Nutzer sagt "track flights to Lisbon under €200"; Muse baut einen Tracker-Space; der Nutzer öffnet ihn live, publisht einen teilbaren Link und pinnt das beste Ergebnis als Artifact.

### 5.2 Feed und Activity

`HatchFeedApi` dekodiert ein datiertes Digest aus **Editions**, jede mit **Units** (`unit_id, title, kicker, emoji, body_md, days`) — das periodische Briefing des Agenten. Unterlegt von der Activity-Timeline: `GET /api/activity?limit=200` in Records (`timestamp, type, status, title, subtitle, messageId, taskLabel, details.goal{…}`), die jeden Record mit einer Chat-Nachricht und optional einem Goal verknüpft. Der eigenständige Feed-Einstiegspunkt ist in 41.6 debug-gated (`str5508` "[Debug Only] Feed"); die Activity-Timeline, die ihn füttert, ist es nicht.

### 5.3 Goals

`HatchGoalsApi`: Liste `GET /api/goals?<query>`, Detail `GET /api/goals/<goal_id>`. Ein Goal ist ein dauerhaftes Ziel: `{goal_id, title, emoji, summary, momentum_status, sub_goals:[…], updates:[{text, effective_at}]}` — ein stehendes Ziel mit einem Gesundheitsstatus und einem zeitstempel-versehenen Update-Log, dem der Agent hinzufügt. Einstieg ist debug-gated (`str5511` "[Debug Only] Goals").

### 5.4 Ideas

Vom Agenten vorgeschlagene, ausführbare Aktionen, die der Nutzer **ausführen** oder **abbrechen** kann (`HatchIdeaDetailBottomSheet`). Strings: "This idea is already running.", "This idea isn't available anymore.", "No ideas right now. Check back later.", "Couldn't start that idea. Try again." Beispiel: der Agent schlägt vor "Draft the Q3 recap"; Tippen auf Execute startet eine laufende Task, die in Feed/Activity aufgezeichnet wird.

### 5.5 Artifacts und Workspace-Medien/Dateien

Artifacts sind vom Agenten erzeugte Outputs (Dokument, Bild, Tabelle, das Ergebnis eines Space), gepinnt/entpinnt via `/api/artifacts/pin`. Die Dateien des Agenten liegen in einem **echten Pro-Agent-CVM-Filesystem** (`com.whatsapp.bot.infra.vmmedia.HatchWorkspaceMediaApi`):

| Call | Pfad | Form |
|------|------|------|
| Library | `POST /fs/library {"preset":"media","limit":n,"offset":m}` | `{entries:[{path,size,modified_ms}],total,has_more}` |
| Raw | `GET /fs/raw/<path>` | rohe Bytes |
| Thumbnail | `GET /fs/thumbnail/<path>?p=sm` | |
| Delete | `POST /fs/delete {"path":…,"recursive":false}` | |

Delete-Bestätigungs-String: "This file will be removed from your agent's files. You can't undo this."

### 5.6 Identitäts-Dokumente

Die "Über mich"-Dokumente des Agenten sind als **reine Textdateien im selben VM-Filesystem** gespeichert, kein dedizierter Store: `GET /fs/read {path,offset,len}` → `{text,bytes,eof,not_found}`; `POST /fs/write {path,text|bytes,offset,append,overwrite,create_parent}`. Der Nutzer bearbeitet Dokumente, die der Agent dann als persistenten Kontext liest.

### 5.7 Approvals und Approval History

**Live-Gate:** vor einer riskanten/irreversiblen Aktion hebt der Agent eine Approval an (`HatchBrowserPreviewActivity`, `str54e1` "Approval required"). **History/Audit:** `GET /approvals/history?record_schema=snapshot_v1&limit=50`, paginiert via `next_cursor`, in einen strukturierten Record pro Approval: `{approval_id, status, decision, outcome_label, summary_title, purpose_summary, scope_summary, requested_at_ms, permission_question, payload_preview, request_preview_document, display_name, icon_key, blocks, rows, fields, items, links, attachments, version, truncated}`. Einstieg ist debug-gated (`str54e8` "[Debug Only] Approval history"), das zugrundeliegende Log ist es nicht.

### 5.8 Scheduled Tasks — drei getrennte Implementierungen

| # | Oberfläche | Transport | Ops | Vom Client erreichbar? |
|---|---------|-----------|-----|--------------------|
| a | 1:1-Meta-AI-Reminders (`com.whatsapp.metaai.tasks`) | plain MEX über `whatsapp-android-www` | **`GetMetaAiReminders`**, **`DeleteMetaAiReminder`** | **Ja-ish** — namensbasierte Persisted-Query-MEX, kein attestierter/nativer Blocker |
| b | Gruppen-Scheduled-Tasks (`com.whatsapp.bot.group.groupinstructions.impl`, neu in 41.6) | plain MEX über `whatsapp-android-www` | **`GetMetaAiGroupReminders`** (Parameter `groupId`), **`DeleteMetaAiGroupReminder`** (`groupId`, `reminderId`) | **Ja-ish** — gleiche Begründung |
| c | Hatch-VM-Scheduled-Tasks (`com.whatsapp.hatch.scheduledtasks.impl`) | Noise VM | wiederkehrende Agent-VM-Läufe, abgebrochen über den VM-Transport | Nein — nativ-only |

9a/9b sind die **einzigen** Workspace-Ops, die ein Drittanbieter-Client plausibel erreichen könnte, weil sie weder den nativen Noise-Gateway-Carrier noch das WAFFLE-Onboarding berühren. Das Erstellen eines Reminders scheint agentseitig zu passieren (via den Meta-AI-Chat-Tool-Call), nicht durch eine client-sichtbare Mutation — nur Get- und Delete-Ops sind präsent. Numerische `doc_id`s für beide Paare sind `unknown` (namensbasierte Persisted-Query-Auflösung; nicht unabhängig erfasst). Die Group-Instructions-Oberfläche lässt einen Admin außerdem die Meta AI der Gruppe konfigurieren (Regeln, Referenzdokumente, Ton) via `CustomizeGroupMetaAiActivity` — angrenzende UI, selbst keine Scheduled-Task-Operation.

### 5.9 Connectors und der Secure Credential Store

Ein **Connector** ist eine registrierte Bindung zwischen dem Agenten und einem externen Dienst. Der Nutzer authentifiziert sich einmal (OAuth / API-Key / Username+Passwort / FoA / Stripe / Messenger), und das resultierende Credential wird **serverseitig innerhalb der CVM gespeichert, niemals im Android Keystore** — `SecureCredentialVault` führt alle Operationen als HTTP-Calls über denselben VM-Noise-HTTP-Transport aus. Keine `KeyStore`-, `EncryptedSharedPreferences`- oder `AndroidKeyStore`-Referenz existiert irgendwo in `securecredentials/`.

Credential-Endpoints (`found`, über den Noise-VM-Kanal):

| Pfad | Rolle |
|------|------|
| `POST /v1/credentials/capture` | pusht ein erfasstes Credential |
| `POST /v1/credentials/catalog/update` | Upsert; gesehene Felder: `username`, `password`; Permission via `JA9`-wireValue-Enum |
| `POST /v1/credentials/catalog/delete` | `{id}` → `{ok}` |
| `GET /v1/custom-connectors/list` | |
| `POST /v1/custom-connectors/register` | API-Key-Form `{connector, api_key:{key}, replace_existing}` oder OAuth-Form `{connector, oauth_bootstrap:{client_id, client_secret?,…}, replace_existing}` → `authorize_url` |

Connector-Katalog + Connect-Flows (`found`, über denselben Kanal): `GET /api/connectors?surface=settings&icon_cdn=whatsapp` → `{connectors:[{id,name,description,icon,state,is_custom,management_kind,supports_multiple_accounts,consent}]}`; Connect-Info pro Connector (`/connectors/<id>/connect/info`) und typ-spezifische Auth-Pfade für OAuth, API-Key, Username/Passwort (mit `two_factor_required`/`attempts_remaining`/`login_timeout_remaining_secs`), **FoA** (Family-of-Apps-Accounts), **Messenger-Companion** (PIN-gated Chat-Linking) und **Stripe-Link** (Payments). Permissions sind pro Connector (`GET/SET /permissions/connectors/<id>`, UI-String "Agent permissions"). Custom Connectors tragen eine explizite Unreviewed-Code-Warnung ("Meta doesn't review custom connectors… supervise your agent's use").

Per Design sieht der Agent **keine rohen Secrets**: "Securely store passwords for your agent to use", "Shared with your agent without saving". Die **Virtual-Card**-Aktion (`HatchConnectorCardActionActivity`) mintet eine Einmal-Karte, die der Agent für Payments verwendet, sodass die echte Kartennummer nie exponiert wird ("The agent will never see your credit card"). `assets/api_key.txt` existiert in der APK und wird gemäß dem Evidence-Contract des Brain als Credential-Material behandelt — hier nicht geöffnet/zitiert; `inferred`, dass es sich um einen Client-/App-Level-API-Key für die Hatch-API-/GraphQL-Control-Plane handelt, nicht um ein Pro-Nutzer-Secret.

**Erreichbarkeit für ganz §5:** nativ-only. Jedes Pfad-Literal oben ist aus der APK rekonstruierbar; nichts davon ist von einem Drittanbieter-Client steuerbar, beobachtbar (es ist innerhalb des Noise-Tunnels verschlüsselt) oder imitierbar, weil jeder dieser Calls den §4-attestierten Transport plus eine WAFFLE-provisionierte VM benötigt.

---

## 6. CVM-Identitäts-Recovery — das Vesta-OPAQUE-PIN-System (`hatch/cvm`)

### 6.1 Korrektur des "Virtual-Card-Vault"-Framings

Ein früherer Research-Pass (2.26.45.10) beschrieb `hatch/cvm` + `hatch/cvm/pin` als "PIN-gated Virtual-Card-Vault". **Dieses Framing ist auf der Crypto-Ebene falsch.** Es vermischt zwei unabhängige Subsysteme:

- **`hatch.connectors` / `HatchConnectorCardActionActivity`** (§5.9) — ein echter, separater Connector-Grant-Flow für eine Drittanbieter-Payment-Rail (fast sicher Stripe). Er hat **null Code-Referenzen** auf irgendeine `com.whatsapp.hatch.cvm`- oder `com.facebook.vesta`-Klasse (geprüft: keine Cross-Referenz von `hatch.connectors`-Smali zu `HatchCvmPinActivity`/`HatchCvmVestaClient`/`HatchCvmKeyService`).
- **`hatch.cvm` / `hatch.cvm.pin`** ist das **Confidential-VM-Identitäts- und Chip-Attestierungs-Enrollment-System** des Agenten, kein Kartenspeicher. Es speichert **keine Payment-Daten irgendeiner Art** — kein PAN/CVV/Billing-Feld irgendwo im Package. Was es schützt, ist ein **Geräte-/VM-Identitäts-Secret, wiederherstellbar über einen OPAQUE-Password-Authenticated-Key-Exchange, PIN als Passwort**, gebunden an AMD-SEV-SNP-Hardware-Chip-Auswahl für die CVM.

Die PIN ist **kein rein lokales Unlock**: der Login-Pfad von `HatchCvmKeyService` macht einen echten OPAQUE-Exchange-Round-Trip zu einem Meta-Backend (`hatch-api.meta.ai/hatch/vesta-auth/*`, plain HTTPS), bevor überhaupt lokales Key-Material abgeleitet/wiederhergestellt wird. Eine falsche PIN schlägt **serverseitig** fehl ("wrong pin", "crypto failed"), nicht nur gegen einen lokalen Hash.

Entscheidend: dieser Traffic ist **plain HTTPS zu `hatch-api.meta.ai`** — derselbe Control-Plane-Host wie `/hatch/vm/wake` (§3.3) — **nicht** der attestierte Noise-Gateway-über-Tigon-VM-Kanal. Die pauschale Behauptung "gleiche harte Blocker wie der Transport" aus §4/§5 gilt hier also nicht: der eigentliche Blocker für dieses Subsystem ist ein kryptographischer, kein attestierungs-transportbezogener.

### 6.2 Die native Oberfläche

`com.facebook.vesta.VestaClient` lädt **`libvesta_client_jni.so`** (neu in 2.26.45.10). Alle 19 auf ihr deklarierten nativen Methoden implementieren eine **PIN-als-Passwort-OPAQUE-PAKE, zusätzlich umhüllt mit einer Post-Quantum-KEM-/Signatur-Schicht**, plus einen gerätegebundenen "HSM-Key"-Validierungsschritt:

| Native Methode | Rolle |
|---|---|
| `getApiVersionNative` / `getProtocolVersionNative` | Versionsverhandlung |
| `beginLoginNative` / `finishLoginNative` (×2 Overloads) | OPAQUE-Login-Schritte 1 und 2 (erzeugt Session-/Export-Key-Material) |
| `beginRegisterNative` / `finishRegisterNative` / `finishRegisterProtoNative` | OPAQUE-Registrierung (Anmelden einer neuen PIN) |
| `unpackLoginPayloadNative` / `unpackLoginPayloadProtoNative` | Dekodiert das eskrowte Login-Payload des Servers |
| `validateHsmKeyNative` / `validateHsmKeysWithOtaBundleNative` | validiert ein hardware-gebundenes Keypair, optional mit einem Device-Key-Rotation-OTA-Bundle |
| `verifyRestoreHistoryNative` | verifiziert einen früheren Restore-/Recovery-History-Record |
| `pqWrapFinishLoginNative` / `pqWrapFinishRegisterNative` / `pqUnwrapFinishLoginResponseNative` | Post-Quantum-Wrap/Unwrap von Login-/Register-Payloads |
| `pqWrapSchemeNative` | welches PQ-Scheme in Verwendung ist (`unknown` Return-Wert — braucht Frida) |

`libvesta_client_jni.so` ist, wie der Noise-Gateway-Carrier, eingepackt im opaken SUPERPACK-Blob — keine byte-exakte statische Extraktion war in diesem Pass möglich. `libvoprf-ed25519.so` (im selben Build vorhanden) ist konsistent mit einer OPRF-/VOPRF-Primitive (die Kernbaustein von OPAQUE), wurde aber **nicht** unabhängig mit `VestaClient` verkreuzt — notiert als plausible angrenzende Library, nicht nachgewiesen als dieselbe Implementierung (`unknown`).

### 6.3 Wire-Endpoints — plain HTTPS zu `hatch-api.meta.ai`

| Pfad | Rolle |
|---|---|
| `POST /hatch/vesta-auth/begin-login` | OPAQUE-Login-Schritt 1 |
| `POST /hatch/vesta-auth/finish-login` | OPAQUE-Login-Schritt 2, liefert das eskrowte Payload |
| `POST /hatch/vesta-auth/begin-register` | OPAQUE-Registrierungs-Schritt 1 (neue/geänderte PIN) |
| `POST /hatch/vesta-auth/finish-register` | OPAQUE-Registrierungs-Schritt 2 |
| `GET /hatch/vesta-auth/user-info` | `is_registered` + Versuchs-/Lockout-Zähler |
| `GET /hatch/fetch_vms?notary_token=true[&vm_id=]` | listet/löst die CVM(s) des Nutzers auf |
| `POST /hatch/lease_vm` / `POST /hatch/cold-lease-cvm` | least eine CVM-Instanz (warm / kalt) |
| `GET /hatch/cvm-replace-state?env_id=` | CVM-State-Machine-Übergang |
| `GET /hatch/cvm-chip-allowlist?env_id=` | welche SEV-SNP-Chip-IDs für diese CVM erlaubt sind |
| `POST /hatch/cvm-chip-selection` | committet die Chip-Auswahl/den Bid |
| `GET /hatch/onboarding_statuses` | Onboarding-Status-Check |
| `POST /hatch/vm/wake` | weckt/resumed die CVM (auch §3.3) |

Keiner davon berührt `/v1/noise` oder die `hatch_vm_*`-Verben — was §6.1s Korrektur bestätigt. `/hatch/cvm-chip-allowlist` und `/hatch/cvm-chip-selection` sind die ersten **konkreten Wire-Beweise** für den SEV-SNP-"pinned to specific chip IDs"-Attestierungsmodus, den §4.2 nur als native Konstruktor-Signatur fand.

Wire-DTOs (`kotlinx.serialization`-Serial-Name-Felder, keine obfuskierten Java-Feldnamen) umfassen OPAQUEs eigene **L1/L2/L3**-Drei-Nachrichten-Exchange-Benennung (`base64url_encoded_opaque_l1/l2/l3`, plus `_sig`-Varianten), gerätegebundene **"Island"-RSA/Ed25519-Public-Keys** (`unknown` Herkunft — HSM/Keystore vs. ein Vesta-internes Format) und ein lokales Journal (`HatchCvmJournal`: `candidate_chip_ids`, `accepted_chip_ids`, `bid_state`-Enum `PENDING/ACCEPTED/RETIRED`, `abra_user_id` — dieselbe Bearer-Identität wie `GraphQlHatchAbraTokenProvider`).

### 6.4 Was die PIN tatsächlich schützt

`HatchCvmKeyService.A00` (der Recovery-Pfad): (1) führt OPAQUE-Login aus (`begin-login` dann `finish-login`, native Mathematik); (2) nur bei Erfolg leitet `HatchCvmKeyProviderImpl` das echte lokale Key-Material aus dem eskrowten Login-Payload ab/stellt es wieder her; (3) ein Wipe-Pfad existiert bei Device-Key-Mismatch oder explizitem Reset. **Eine korrekte PIN ist erforderlich, um einen echten Client↔Server-OPAQUE-Exchange abzuschließen** — der Server gibt das eskrowte Payload nur bei einem korrekten Finish-Login frei, ratelimitiert und serverseitig verifiziert (`attempts_remaining`, `login_timeout_remaining_secs` bei jeder Response). Ein Angreifer mit dem Gerät, aber ohne die PIN, kann das lokal nicht brute-forcen. Das geschützte Secret ist **das CVM-/Geräte-Identitäts-Key-Material, das nötig ist, um die Confidential-VM-Session dieses Nutzers fortzusetzen** — kein Payment-Credential.

Separat verwendet `HatchCvmPinReminder` einen **rein lokalen** AES/GCM-Key (Alias `hatch:pin-reminder:v1:...`) ausschließlich, um einen "remind me to set a PIN"-Notification-State zu verschlüsseln — unabhängig vom Vesta-Exchange und das einzige Stück Nicht-Wire-beobachtbarer Crypto in diesem Subsystem.

### 6.5 Erreichbarkeits-Verdikt für §6

Wire-Schema vollständig rekonstruierbar (oben); Transport ist plain HTTPS, prinzipiell MITM-beobachtbar **ohne** die WAFFLE-Attestierung oder den nativen Noise-Gateway-Carrier zu überwinden. Aber **tatsächlich teilnehmen** (ein echtes Login/Register) ist von der APK allein nicht möglich: jedes Request-/Response-Feld wird von nativen OPAQUE- + Post-Quantum-Wrap-/Unwrap-Operationen innerhalb von `libvesta_client_jni.so` produziert oder konsumiert, eingepackt im Superpack ohne verfügbare byte-exakte Extraktion. Ein Client könnte die JSON-*Form* im Klartext erfassen und replayen, kann aber kein gültiges `opaque_l1`/`l3`, keinen Island-Keypair-Proof und kein PQ-gewrapptes Payload berechnen — ein **kryptographischer** Blocker, strukturell anders als der attestierungs-transportbezogene Blocker in §4.

---

## 7. Monetarisierung — die kostenpflichtige Hatch-Subscription-Stufe

Ein 2.26.45.10-era Subscription-Cluster fügt eine echte, abgerechnete Stufe für Muse hinzu. Der Kaufflow (`inferred`-Kette, jeder Schritt einzeln `found`):

1. Der Client prüft das Feature-Flag **`ai_hatch_in_app_subscriptions_enabled`** (Log: "`ai_hatch_in_app_subscriptions_enabled` is off"). Keine numerische Flag-ID wurde dafür gefunden — es wird nur namentlich referenziert.
2. Tier-Konstante **`NME_SUBSCRIPTION`**; Produktdetails werden pro Tier abgerufen (`HatchSubscriptionPurchase$launch$2`, Log "Fetching product details for tier"; Tier-Name interpoliert, keine hartcodierte SKU).
3. Compliance-Check: **`WamoSubGetComplianceInfo`** (`whatsapp-android-mex`, namensbasiert, keine Input-Felder an der Call-Site gesetzt — nur session-/identitäts-scoped).
4. Payments-Token-Mint: **`HatchGenFrlPaymentsAccessTokenMutation`** (`GraphQlHatchFrlPaymentsTokenProvider`, Namespace `whatsapp-android-www`; "FRL"-Expansion in diesem Pass in keinem String gefunden — `unknown`).
5. Google-Play-Billing-Launch (`HatchManageSubscriptionViewModel$openBilling$1`) — Standard-Android-`BillingClient` via ein geteiltes Meta-Commerce-SDK (`com.facebook.payments.dcp.xapp.*`), getaggt `app="WHATSAPP"`.
6. Bei Kauf serverseitige Fulfillment-Reconciliation (`HatchSubscriptionPurchaseReconciler`), wahrscheinlich via **`DCPFulfillIAPTransactionsMutation`** (`pay_dcp_fulfill_iap_transactions`, direkter Pando-Request, Felder `platform`/`app`/`purchase_tokens`/`subscription_purchase_tokens`/`upl_session_id`, alle mandatory an dieser Call-Site) — nicht unabhängig bestätigt als der exakte Call, den dieser Reconciler verwendet (`unknown`).

Vier weitere Ops, nur im Persisted-Query-Katalog deklariert (`IACQueryProductInfo`, `IACQuoteDisplay`, `IACSandboxPlatformMode`, `DCPInternalSandboxCreateSessionMutation`), haben **keine Calling-Class irgendwo im Smali gefunden** — `unknown` ob das toter/zukünftiger Code, ein Server-/Flag-Gate oder eine String-konkatenierte Call-Site ist, die ein einfacher Grep verfehlt.

**Erreichbarkeit:**

| Op | Namespace | braucht | erreichbar durch einen Drittanbieter-Client? |
|---|---|---|---|
| `WamoSubGetComplianceInfo` | `whatsapp-android-mex` | nur eine authentifizierte MEX-Session | **Ja, prinzipiell** — plain parameterlose MEX-Query |
| `HatchGenFrlPaymentsAccessTokenMutation` | `whatsapp-android-www` | authentifizierte Session | **Transport-erreichbar**; der praktische Wert des gemintetn Tokens außerhalb des beabsichtigten Flows ist `unknown` |
| `DCPFulfillIAPTransactionsMutation` | `whatsapp-schema` (Pando) | einen echten Google-signierten Play-Billing-Kauf-/Subscription-Token | **Nein** — der Request ist formbar, aber nichts Wahrhaftiges lässt sich hineinschreiben ohne einen echten Play-Billing-Kauf durch einen signierten `com.whatsapp`-Kontext |
| `IAC*` / `DCPInternalSandboxCreateSessionMutation` | `whatsapp-schema` | unknown (keine Calling-Class gefunden) | **Unknown** |
| Google Play Billing selbst | n/a | Play Store + signierter App-Kontext | **Nein** — nicht einmal ein WhatsApp-Server-Call |

---

## 8. Erreichbarkeits-Verdikt

| Komponente | Transport | Blocker | Erreichbar von einem Drittanbieter-Client (Baileys/velowa)? |
|---|---|---|---|
| Agent Spaces, Feed/Activity, Goals, Ideas, Artifacts, Workspace-Medien/Dateien, Identitäts-Dokumente, Approvals+History, Hatch-VM-Scheduled-Tasks, Connectors (alle Flows), Secure Credential Store | Attestierter Noise-VM-Kanal (§4) | nativer Noise-Gateway-Carrier `.so` + WAFFLE-Onboarding | **Nein** |
| Control Plane (VM-Wake, Abra-Token, Pairing-URL) | plain HTTPS zu `hatch-api.meta.ai` | WAFFLE-gated Provisionierung (Server gibt ohne sie keine funktionierende VM aus) | **Nein** (Schema MITM-beobachtbar; nicht unabhängig steuerbar) |
| CVM-Identitäts-/PIN-Recovery (`hatch/cvm`, Vesta OPAQUE) | plain HTTPS zu `hatch-api.meta.ai` | native OPAQUE + Post-Quantum-Mathematik in `libvesta_client_jni.so` | **Nein** — kryptographischer Blocker, kein attestierungs-transportbezogener |
| 1:1-Reminders — `GetMetaAiReminders` / `DeleteMetaAiReminder` | plain MEX, `whatsapp-android-www` | keiner gefunden | **Ja-ish** (doc_id `unknown`) |
| Gruppen-Reminders — `GetMetaAiGroupReminders` / `DeleteMetaAiGroupReminder` | plain MEX, `whatsapp-android-www` | keiner gefunden | **Ja-ish** (doc_id `unknown`) |
| Subscription-Compliance-Info — `WamoSubGetComplianceInfo` | plain MEX, `whatsapp-android-mex` | keiner gefunden | **Ja, prinzipiell** |
| Payments-Token-Mint — `HatchGenFrlPaymentsAccessTokenMutation` | plain GraphQL, `whatsapp-android-www` | keiner auf Transport-Ebene; praktischer Wert des Tokens anderswo unknown | **Transport-erreichbar** |
| IAP-Fulfillment — `DCPFulfillIAPTransactionsMutation` | plain Pando GraphQL, `whatsapp-schema` | braucht einen echten signierten Play-Billing-Token | **Nein** (nichts Wahrhaftiges zu senden) |
| `IAC*` / Sandbox-IAP-Ops | `whatsapp-schema` | keine Calling-Class gefunden | **Unknown** |
| richResponse-Quiz (bot.quiz) | lokaler Message Store | keiner — kein VM-Feature | Payload rekonstruierbar; kommt als normale Bot-Nachricht an |

Die "Ja-ish"/"Ja, prinzipiell"-Zeilen sind die **gesamte** client-erreichbare Oberfläche dieses Subsystems. Alles andere — was den Großteil des Agenten ausmacht — benötigt entweder den nativen Noise-Gateway-Carrier plus eine gültige WAFFLE-Attestierung, oder native OPAQUE-/Post-Quantum-Kryptographie, die aus dieser APK nicht statisch extrahiert werden kann.

---

## 9. Baileys / velowa

**Verdikt: dieses Subsystem ist für einen Drittanbieter-Client JS-unmöglich, Punkt — kein fehlendes Feature, ein strukturelles.** velowa (das aktive Client-Projekt hinter diesen Docs) kann die Hatch/Muse-Agent-Browser-VM oder den Workspace aus denselben Gründen nicht implementieren, die der ursprüngliche Research-Pass nannte:

| Blocker | Warum er in JS/WASM nicht umgangen werden kann |
|---|---|
| `libwa-noise-gateway-carrier-jni.so` | Der gesamte Noise-Handshake und das WebSocket-Framing für den VM-Kanal ist nativer Code innerhalb des opaken SUPERPACK-Blobs. Es gibt kein Protokolldokument, gegen das man reimplementieren könnte — die Wire-Form (Query-Parameter, `/v1/noise`-Pfad, HTTP-über-Noise-Verben, noVNC-RFB-Subprotocol) ist oben rekonstruiert, aber die eigentliche Noise-Kryptographie (Key-Ableitung, Frame-Authentifizierung) existiert nur in diese `.so` kompiliert. Sie zu reimplementieren bedeutet, eine gestrippte native Library zurückzuentwickeln, nicht einen Client gegen eine Spec zu schreiben. |
| WAFFLE-Official-Client-Attestierung | Gated VM-Onboarding, bevor überhaupt ein Noise-Kanal geöffnet wird. Ein Drittanbieter-Client kann keinen gültigen WAFFLE-Token produzieren, kann also von Anfang an keine VM provisionieren — das blockiert sogar den Versuch des Noise-Handshakes. |
| `libvesta_client_jni.so` (OPAQUE + PQ) | Getrennt vom Obigen: selbst wo der Identitäts-Recovery-Traffic (§6) plain HTTPS und beobachtbar ist, ist die clientseitige OPAQUE-Mathematik (`opaque_l1`/`l3`, die "Island"-Keypair-Proofs, das Post-Quantum-Wrap) nativ. Die JSON-Form zu erfassen, gibt nichts, womit man einen gültigen Request berechnen könnte. |
| AMD-SEV-SNP-Attestierung | Orthogonal zum Client — es ist die *serverseitige* VM, die sich der offiziellen App gegenüber als echt beweist — bestätigt aber, dass das gesamte Design einen nativen, attestierten Peer auf beiden Enden voraussetzt. |
| Tigon | Metas interner App-übergreifender nativer HTTP-Stack trägt jeden Request in §4 und §6; seine Request-Objekte sind kein öffentliches, versioniertes Wire-Format. |

Was velowa (oder irgendein Protokoll-Client) *erreichen könnte* ohne irgendetwas Obiges zu berühren: die vier namensbasierten MEX-Reminder-Ops (§5.8) und die Subscription-Compliance-/Payments-Token-GraphQL-Ops (§7) — alle über denselben plain-WA-MEX/GraphQL-Transport, den velowa für alles andere in diesem Repo bereits spricht. Kein Code-Beispiel wird hier gegeben, weil kein Quellenmaterial dieses Reports einen konkreten Request/Response für diese Ops über die Operationsnamen und Parameterformen hinaus erfasst hat, die bereits in §5.8/§7/§8 aufgeführt sind; das Erfinden von Payload-Bytes würde die Evidence-Tier falsch darstellen.

---

## 10. Fehlerfälle / Gotchas

| Symptom | Ursache | Hinweis |
|---|---|---|
| "Computer is turned off on this VM" | VM für die volle Desktop-Oberfläche nicht provisioniert/wach | `HatchComputerActivity`-String |
| "Approval required" löst sich nie in eine Aktion auf | Nutzer hat das Approval-Gate nicht bestätigt | per Design — Human-in-the-loop |
| "This idea isn't available anymore." / "This idea is already running." | Idea-Card überholt oder läuft bereits | `HatchIdeaDetailBottomSheet` |
| "No goals yet" / "No ideas right now. Check back later." / "No approvals yet" | leere Workspace-Sections, kein Fehler | |
| "Couldn't load your agent's files" | `/fs/library`- oder `/fs/raw/`-Call über den Noise-Tunnel fehlgeschlagen | |
| `PrivateSearchSessionManager`-artiges "thread superseded by a newer search, refusing" (angrenzendes TEE-System, nicht Hatch) | hier nur in §11 aufgeführt, um Kreuzkontamination von Error-Strings zwischen den beiden Systemen zu vermeiden | siehe Key Distinctions |
| 400 "already exists; set replace_existing=true" | Custom-Connector-Register ohne das `replace_existing`-Flag | `HatchConnectorsListRequester` |
| "wrong pin" / "finish-login crypto failed" | OPAQUE-Login serverseitig fehlgeschlagen | ratelimitiert via `attempts_remaining`/`login_timeout_remaining_secs` |
| "hsm key missing" / "hsm key invalid" / "hsm key check failed" | gerätegebundene HSM-Key-Validierung innerhalb des Vesta-Recovery-Pfads fehlgeschlagen | §6.4 |
| `noise/gave-up limit=deadline` | VM-Noise-Channel-Open-Budget (60 s) überschritten | `NoiseVmConnection` |
| `NoiseHandshakeOutcome.VERIFICATION_FAILED` | Attestierungs-Check beim Noise-Gateway-Handshake fehlgeschlagen | §4.2 |
| "`ai_hatch_in_app_subscriptions_enabled` is off" | Subscription-Feature-Flag serverseitig deaktiviert | §7 |
| "HatchSubscriptionPurchase/purchase no compliance data" | `WamoSubGetComplianceInfo`-Ergebnis vor einem Kaufversuch fehlend | §7 |

---

## 11. Wichtige Abgrenzungen — was NICHT zu verwechseln ist

| Nicht verwechseln | Fakt |
|---|---|
| Hatch/Muse-Agent (dieser Report) vs. **Meta-AI-Chat** (`WA_META_AI.md`) | Meta AI ist ein Bot-Kontakt, erreicht über `botInvokeMessage`/Bot-JIDs auf dem normalen Message-Proto; Hatch/Muse ist ein separater Agent, der eine remote attestierte VM steuert. Sie teilen etwas Plumbing (Hatch-JSON-Metadaten-Kanal via `ProtocolMessage.aiMetadataOperation`, Capability-Flags, die der Hatch-Bot-JID `1807055946647697@bot` beworben werden), sind aber architektonisch getrennte Subsysteme |
| Hatch/Muse-VM vs. **Private Processing / TEE-Cluster** (Chat-Kontext-AI, Private Search) | Der TEE-Cluster (`ClusterFetchPrekeyBundleConnection`, `IplsdHandshakeExecutor`, `PsiSearchToolHandler`, `TeePrefixCacheAnchor`) ist Meta AI, das Fragen **über die eigenen lokalen Chats** via eine attestierte Enklave + PSI-Suche beantwortet — es hat nichts mit der Hatch-Agent-Browser-VM zu tun. Private Searchs *Query-Send* läuft über eine plain Bot-Chat-Nachricht (erreichbar), während die PSI-/Enklaven-Berechnung selbst nativ bleibt — eine andere Erreichbarkeits-Form als alles in diesem Report |
| `hatch.cvm` (Identitäts-/Chip-Recovery, §6) vs. `hatch.connectors` (Virtual Card / Stripe, §5.9) | Zwei getrennte Features, die nur die beiläufigen Worte "card"/"vault" im Produkt-Framing teilen; keine Code-Abhängigkeit zwischen ihnen (geprüft) |
| `HatchCvmPinReminder`s lokaler AES/GCM-Key vs. der Vesta-OPAQUE-Exchange | Rein lokale Notification-State-Verschlüsselung vs. eine echte, server-round-getrippte Identitäts-Recovery — nur Letzteres ist "serverseitiges" PIN-Gating |
| "bid_state"-/"chip"-Felder (§6) vs. die Browser-**Control-Lease** (§4.5) | SEV-SNP-Hardware-Chip-Auswahl-Buchführung vs. wer den Agent-Browser steuert (Agent/Mensch) — drei verschiedene Verwendungen überlappendes Vokabular ("bid"/"lease"/"control") in dieser Codebase |
| Vestas Plain-HTTPS-Control-Plane (§3, §6) vs. der attestierte Noise-Gateway-VM-Kanal (§4) | Unterschiedliche Transporte, unterschiedliche Blocker (native OPAQUE-Mathematik vs. native Noise + WAFFLE-Attestierung) — sie zu vermischen überschätzt, wo der attestierungs-transportbezogene Blocker tatsächlich gilt |
| Agent Spaces (§5.1) vs. vom Agenten erzeugte Artifacts (§5.5) | Ein Space ist eine lebende, zustandsbehaftete gehostete App; ein Artifact ist ein statischer Output (das *gepinnte Ergebnis* eines Space wird zum Artifact, aber der Space selbst läuft weiter) |
| `com.whatsapp.bot.quiz.AiQuizViewerActivity` vs. ein Hatch-Feature | Liest ein richResponse-Quiz, das bereits als normale Bot-Nachricht aus dem lokalen Speicher geliefert wurde — keine VM, kein Netzwerkaufruf, überhaupt nicht Teil dieses Subsystems |

---

## 12. End-to-End-Flow — eine Agent-Browser-Task-Session

```
[User, in chat]
    │  "book me a table for two tonight"
    ▼
[Onboarding, first use only]
    │  HatchWaffleOnboarding: official-client WAFFLE attestation
    │  HatchPairingAuthBrowsingActivity: pairing URL (account ↔ agent link)
    ▼
[Control plane]  plain HTTPS to hatch-api.meta.ai
    │  GraphQlHatchAbraTokenProvider → Abra bearer
    │  HatchVmApiClient: POST /hatch/vm/wake {vm_id, retry_count}
    │  → HatchVmEndpoint{host, auth_token, notary_token, ...}
    ▼
[Noise-gateway handshake]  native libwa-noise-gateway-carrier-jni.so over Tigon
    │  GET …<vmhost>…?auth_token&notary_token&app_id&app_version=2.26.41.6
    │  path /v1/noise, 20s handshake timeout, attestation verifier (noOp/SNP/SNP-pinned)
    ▼
[Attested Noise channel open]  (60s budget, ref-counted "holds")
    │
    ├──▶ hatch_vm_request /api/computer/subscribe  — live task state (SSE-style)
    │
    ├──▶ hatch_vm_call   — agent navigates the booking site inside the CVM
    │        │
    │        ▼
    │    [Phone shows it live]  noVNC (RFB) over JWT-bearer WebSocket, viewOnly
    │        unless user takes a BrowserControlLeaseJson "control lease"
    │
    ├──▶ Login needed → /v1/credentials/... fetched INSIDE the VM
    │        (SecureCredentialVault; raw secret never reaches the agent's
    │         reasoning context, per design)
    │
    ├──▶ Payment needed → HatchConnectorCardActionActivity mints a virtual card;
    │        real card number never exposed to the agent
    │
    ├──▶ Risky/irreversible step → HatchBrowserPreviewActivity "Approval required"
    │        user confirms → recorded in HatchApprovalHistoryApi
    │
    ▼
[Outcome]
    │  artifact/feed entry (hatch.artifacts / hatch.feed)
    │  optionally scheduled to recur (HatchScheduledTasksActivity, native VM path)
    ▼
[Noise channel teardown]  last "hold" released → noise/closed reason=unlink
```

Separat (nicht Teil derselben Session, plain MEX/GraphQL, kein attestierter Transport beteiligt):

```
[Client]  GetMetaAiReminders / GetMetaAiGroupReminders
    │  whatsapp-android-www, name-based persisted query
    ▼
[WA server]  reminder list (status SCHEDULED/CLAIMED/FULFILLED)

[Client]  DeleteMetaAiReminder / DeleteMetaAiGroupReminder
    ▼
[WA server]  reminder removed
```
</content>
