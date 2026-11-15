# WhatsApp Hatch/Muse AI Agent — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-11-15
**Scope:** Hatch/Muse AI agent internals — attested Noise-gateway VM transport, native carrier + SEV-SNP attestation, control plane and WAFFLE onboarding, agent-browser noVNC stream, workspace (spaces, feed, goals, ideas, artifacts, approvals, scheduled tasks, connectors), secure credential store, CVM identity/PIN recovery (`hatch/cvm`, Vesta OPAQUE), paid subscription tier, reachability verdict, why Baileys/velowa cannot implement it

---

## 1. What Hatch/Muse is

**Hatch** is the internal codename for WhatsApp's AI-agent subsystem; **Muse** is the user-facing name of the agent itself (`str29b7` "Muse manages emails, books tables, and more."). The agent is not just a chat persona (that is Meta AI, covered in `WA_META_AI.md`): it drives a **remote confidential VM ("CVM")** that can browse the web, run scheduled tasks, hold its own filesystem, and call third-party services on the user's behalf. Everything in this report is `found`/`inferred` static analysis of 2.26.41.6 (`WA-APK-BETA/WhatsApp_2.26.41.6/`), with one corrected sub-area (§6, the `hatch/cvm` identity system) re-verified against 2.26.45.10 smali. **Nothing in this report is `tested`** — no device/Frida run backs any of it; dynamic-confirmation gaps are flagged inline.

### 1.1 Main entities

| Entity | Meaning |
|--------|---------|
| Hatch | Internal codename for the whole agent subsystem (VM, workspace, credential store, identity/PIN layer) |
| Muse | User-facing agent name/persona |
| CVM | "Cloud VM" / "confidential VM" — the agent's remote compute environment (AMD SEV-SNP) |
| `HatchVmEndpoint` (`C57830PwR`) | Resolved VM connection struct: host, `auth_token`, expiry, validated token, `notary_token` param map |
| Noise gateway | A separate attested Noise session to a Meta "noise gateway", carried over Tigon, distinct from the main WA Noise_XX/chatd session |
| Agent spaces | Mini web apps the agent builds and hosts inside the CVM, reverse-proxied to a phone WebView |
| Connector | A registered binding between the agent and a third-party service (Gmail, calendar, Messenger, payment rail, custom endpoint) |
| `hatch/cvm` (Vesta) | The agent's **device/VM identity and chip-attestation recovery system**, PIN-gated OPAQUE PAKE — **not** a payment vault (corrects an earlier research pass, see §6) |
| Approval gate | Human-in-the-loop confirmation before a risky/irreversible agent action |

### 1.2 Relation to Meta AI chat

Muse is reached from the same chat surface as Meta AI, and shares some plumbing (bot-JID capability advertisement — see §7) and the Hatch JSON metadata channel documented in `WA_META_AI.md` §5 (`HF1`/`HatchMetadataRequestManager`, `ProtocolMessage.aiMetadataOperation`). But the agent-browser/VM/workspace system this report covers is a **separate, much larger subsystem**: it does not ride the chatd/Noise_XX session at all, has its own native transport, and persists its own state (goals, feed, artifacts, approvals) server-side in the CVM. Private Processing / the TEE cluster (Meta AI answering questions about your own chats, Private Search) is a **third, distinct** system — see §11 for the full disambiguation.

---

## 2. Architecture overview

### 2.1 Package map

All Hatch/agent activities are `android:exported="false"` — no cross-app entry point; everything is launched in-process from the chat/agent surface.

| Package | Role |
|---------|------|
| `com.whatsapp.hatch.vm` (`p085vm`) | VM control plane / lifecycle: `HatchVmLifecycleCoordinator`, `HatchVmApiClient`, `HatchVmWaker`, `HatchVmLeaseGate`, `GraphQlHatchAbraTokenProvider`, `HatchAbraTokenRevoker` |
| `com.whatsapp.hatch.onboarding` | `HatchWaffleOnboarding`, `HatchPairingAuthBrowsingActivity`, `HatchMuseConnectionActivator` |
| `com.whatsapp.hatch.computer` / `.conversation.browser` / `.conversation.approval` | `HatchComputerActivity` (full VM desktop), `HatchBrowserStreamActivity` (in-chat live browser), `HatchBrowserPreviewActivity` (approval gate) |
| `com.whatsapp.hatch.feed/goals/ideas/activity/approvalhistory` | Workspace UI: feed, goals + sub-goals, ideas, approval history |
| `com.whatsapp.hatch.artifacts/media` | Agent-produced artifacts and files |
| `com.whatsapp.hatch.connectors(.ui)` | Third-party connector catalog, connect flows, virtual-card action, per-connector permission mode |
| `com.whatsapp.hatch.identity.ui` | Agent "about me" documents |
| `com.whatsapp.hatch.scheduledtasks.impl` | Agent VM recurring task UI |
| `com.whatsapp.hatch.cvm` / `.cvm.pin` | **Not a vault** — PIN-gated device/VM identity recovery (Vesta OPAQUE), §6 |
| `com.whatsapp.hatch.subscription(s).iap` | Paid tier purchase flow, §7 |
| `com.whatsapp.bot.agentspaces.*` | "Spaces" host: `HatchSpaceActivity` + `HatchSpaceTunnel` reverse-proxy, `NoiseHatchVmTransport` adapter |
| `com.whatsapp.bot.agentbrowser.*` | Browser engine + VM transport: `BrowserSessionController` (noVNC WebView), `NoiseVmConnection`/`WaNoiseChannel`, `agentbrowser.noise.carrier.*` (native JNI) |
| `com.whatsapp.bot.securecredentials.*` | `SecureCredentialVault` — credential store, server-side in the CVM |
| `com.whatsapp.bot.agentactivity/agentfeed/agentgoals/agentapprovals` | Data/feed layer behind the `hatch.*` UI |
| `com.whatsapp.bot.infra.vmmedia` | Agent VM filesystem raw fetch (`/fs/raw/`, `/media/raw/`) |
| `com.whatsapp.bot.quiz` | `AiQuizViewerActivity` — richResponse quiz viewer, **not** a VM feature (§2.3) |
| `com.crossapp.tigonhttp(.noise)` | Meta's shared **Tigon** cross-app native HTTP stack + `NoiseChannelManagerHolder` |

### 2.2 Three distinct transports — do not conflate them

This is the single most important structural fact, and an earlier research pass got it wrong for one of the three (§6.1 corrects it):

| # | Transport | Carries | Blocker for a third-party client |
|---|-----------|---------|-----------------------------------|
| 1 | **Attested Noise-gateway VM channel** — `/v1/noise` over Tigon, native `libwa-noise-gateway-carrier-jni.so` | Everything agent-interactive: browser-VM HTTP (`/api/*`, `/fs/*`, `/spaces/*`), noVNC screen stream, workspace features, secure-credential CRUD | Native Noise+WebSocket carrier **and** WAFFLE official-client onboarding — hard-blocked |
| 2 | **Plain HTTPS control plane** to `hatch-api.meta.ai` | VM wake, Abra bearer token, pairing URL, **and** (corrected, §6) the `hatch/vesta-auth/*` / `hatch/cvm-*` identity-recovery endpoints | Transport is MITM-observable in principle (rooted device, pinning bypass); the identity endpoints additionally need native OPAQUE + post-quantum math (`libvesta_client_jni.so`) to produce valid request bodies |
| 3 | **Plain MEX/GraphQL** over the ordinary WhatsApp `whatsapp-android-mex`/`whatsapp-android-www` transport | Scheduled-task/reminder reads+deletes (1:1 and group), subscription compliance-info read, Hatch payments-token mint | No native/attested blocker — reachable the same way any other MEX op is |

Transport 1 is what the original (2.26.41.6) research pass calls "the Hatch VM transport" and is the overwhelming majority of the subsystem's surface. Transport 3 is the **only** part of Hatch a Baileys/velowa-style client can plausibly drive.

### 2.3 Not part of the VM — the quiz tie-in

`com.whatsapp.bot.quiz.AiQuizViewerActivity` is a full-screen viewer for a quiz embedded in a stored bot rich-response message (the richResponse "Jarvis" quiz primitive — `WA_META_AI.md` §4.3/§6.3 territory, not Hatch). It loads the quiz **from the local message store** by row id + key + section (intent extras `ai_quiz_viewer_message_row_id`, `ai_quiz_viewer_quiz_key`, `ai_quiz_viewer_section_index`) — no network call, no VM transport. Mentioned here only so it is not mistaken for a Hatch feature; see §11 for the full disambiguation table.

---

## 3. Control plane and onboarding

### 3.1 WAFFLE onboarding (`found`)

First use of the agent surface runs **`HatchWaffleOnboarding`**: the client proves it is a genuine, unmodified WhatsApp build via **WAFFLE** integrity attestation (the same official-client attestation family as `com.whatsapp.waffle.wfac` ban UI / account linking — see `WA_CLIENT_INTEGRITY.md` §11 for the sibling WFAC component). Log breadcrumbs: `"waffle-onboarding"`, `"vm-credentials"`, `"pairing-url"`, `"HatchWaffleOnboarding/link pairing-url-received="`. A third-party client cannot produce a valid WAFFLE token, so it cannot even provision a VM — this is the hard onboarding-side blocker independent of the Noise-gateway carrier.

### 3.2 Pairing (`found`)

`HatchPairingAuthBrowsingActivity` opens an OAuth-style **pairing URL** that links the WhatsApp account to the Meta AI agent/Meta account; completion is logged as `pairing-url-received`.

### 3.3 VM wake and the Abra bearer (`found`)

`GraphQlHatchAbraTokenProvider` mints a GraphQL "Abra" bearer token for the VM; `HatchVmApiClient` then does:

```
POST https://hatch-api.meta.ai/hatch/vm/wake
{"vm_id": "...", "retry_count": N}
```

This is ordinary HTTPS, not the Noise channel. The response feeds `HatchVmLifecycleCoordinator`'s cached-endpoint logic ("connect cached-endpoint", "invalidateToken failed") and resolves into a `HatchVmEndpoint` (`C57830PwR`): host/base-URL, `auth_token`, `bearerExpiresAtMs`, validated-token flag, and a param map carrying the `/v1/noise` `notary_token`. `HatchAbraTokenRevoker` handles invalidation.

**Reachability:** the wake call and token mint are plain HTTPS/GraphQL, in principle MITM-observable on a rooted device with pinning bypass — but useless without a WAFFLE-provisioned account, since the server will not hand out a working VM endpoint to an unrecognized client (`inferred`; not independently confirmed server-side).

---

## 4. The attested agent-browser VM transport

This is the standout finding of the subsystem: the agent-browser VM does **not** ride the main WhatsApp Noise/XMPP session. It opens a **separate Noise session to a Meta "noise gateway"**, carried over Meta's Tigon HTTP stack, through a dedicated native library, with an attestation verifier and an optional pre-shared private-auth key.

### 4.1 Handshake (`found`, `WaNoiseChannel`)

`WaNoiseChannel` takes the VM endpoint host and appends URL-encoded query params before the handshake:

| Param | Source |
|-------|--------|
| `auth_token` | `HatchVmEndpoint.auth_token` (VM bearer) |
| `notary_token` | value for key `/v1/noise` in the endpoint's param map, only if non-blank |
| `app_id` | WA app-id constant (`inferred`, not literal-resolved) |
| `app_version` | hardcoded literal `"2.26.41.6"` |

Handshake path: **`/v1/noise`**. Handshake timeout **20000 ms**; overall channel-open budget **60000 ms** (`NoiseVmConnection`). Log breadcrumbs: `noise/open-start`, `noise/reused`, `noise/closed reason=...`, `noise/use-once`.

### 4.2 Native carrier and attestation (`found`)

`NoiseGatewayCarrier` is a `com.facebook.jni.HybridData` JNI object loaded by `NoiseGatewayCarrierSoLoader` as **`libwa-noise-gateway-carrier-jni.so`** — not a loose file in `lib/arm64-v8a/`, it is packed inside the superpack `libs.so` blob (no byte-exact static extraction available).

Native entry points: `createNative(TigonServiceHolder, NoiseChannelManagerHolder)`, `start(endpoint, ..., byte[32]?, AttestationVerifierHolder, Stream0Listener)`, `sendWebsocketFrameNative`, `stopNative`, `cancelHandshakeNative`. `Stream0Listener` callbacks (`onWebSocketUpgraded`, `onTransportReady`, `onReady(NoiseHandshakeOutcome)`, `onMessage`, `onClose/onFailure`) show the channel is **Noise framed inside a WebSocket**.

`AttestationVerifierHolder` has three native constructors:

| Variant | Meaning |
|---------|---------|
| `createNoOpNative()` | No attestation — the variant instantiated in the decompiled path seen in this pass |
| `createSnpNative(bool)` | AMD SEV-SNP confidential-compute attestation |
| `createSnpPinnedToChipsNative(chips[], bool)` | SNP pinned to specific allowed chip IDs |

**Which variant runs at runtime is `unknown`** from this static pass. The 2.26.45.10 `hatch/cvm` pass (§6) independently found the concrete control-plane endpoints that allowlist/commit SEV-SNP chip IDs (`/hatch/cvm-chip-allowlist`, `/hatch/cvm-chip-selection`), confirming the pinned-chip attestation mode is real infrastructure, not just a dormant code path.

`NoisePrivateAuthMode.REQUIRED` plus a 32-byte key is an optional pre-shared-key "private auth" mode (`inferred`: channel binding); not populated in the path seen, `unknown` whether it is ever used.

### 4.3 HTTP-over-Noise transport (`found`)

Once the channel is up, `WaVmHttpTransportImpl`/`VmHttpClient` send ordinary JSON HTTP requests through the Noise tunnel via Tigon. The app-level adapter (`NoiseHatchVmTransport`, used by every workspace feature in §5) exposes four verbs:

| verb | tag | use |
|------|-----|-----|
| `CQ4(url, accept)` | `hatch_vm_read` | GET read |
| `AEV(method,url,body,…)` | `hatch_vm_call` | generic one-shot call |
| `CXY(method,url,headers,body,streaming)` | `hatch_vm_request` | streamed request (120 s, or unbounded when `streaming`) |
| `Cly(url,body,…)` | `hatch_vm_subscribe` | long-lived SSE/duplex subscribe |

`NoiseChannelHolds` ref-counts open "holds"; the channel tears down after the last hold releases (configurable interval). VM HTTP path surface (`found`, string literals): `/v1/noise`, `/api/`, `/api/computer/subscribe`, `/api/artifacts/pin`, `/spaces/`, `/spaces/v2`, `/spaces/cvm/<slug>`, `/spaces/share/`, `/workspace/`, `/home/hatch/`, `/media/raw/`, `/fs/raw/`, plus credential paths in §5.9.

### 4.4 The noVNC screen stream (`found`)

`assets/vmvnc/` bundles a real **noVNC** web client (`novnc-rfb.js`, `vnc.html`, MPL-2.0 `LICENSE.txt`) — confirmed independently present in both the 2.26.41.6 and 2.26.45.10 builds (`assets-sweep.md`). `BrowserSessionController` loads `https://appassets.androidplatform.net/assets/vmvnc/vnc.html` into a WebView. The HTML defines a **`BridgedWebSocket`** overriding `window.WebSocket`: noVNC believes it opened `wss://bridge.invalid/` (subprotocol `binary`), but every RFB frame is relayed through the Android JS bridge `window.AndroidVncBridge` (`socketSend`/`socketClose`/`socketOpen`, callbacks `window.__vncBridge.*`). The shipped HTML's own comment explains why: **the real websockify endpoint requires `Authorization: Bearer <jwt>`**, which a WebView WebSocket cannot set, so native code owns the real socket (opened over Tigon with the VM bearer) and the JS shim only relays frames.

Net: the VM desktop/browser is streamed to the phone as genuine **RFB (VNC) over a JWT-bearer-authenticated WebSocket**, itself tunneled through the attested Noise gateway; noVNC renders it in a WebView. Input gating (`isViewOnly`, `isInputEnabled`, `isPanModeEnabled`, zoom/viewport methods) and sizing (`BrowserViewerJson{width,height,devicePixelRatio}`) are native-driven. `inferred`: lighter-weight "present"/preview still frames (`BrowserTaskScreenshotJson`, `BrowserTaskPresentationJson`) back the in-chat `HatchBrowserStreamActivity`, with full interactive VNC reserved for `HatchComputerActivity`.

### 4.5 Control lease (`found`)

`BrowserControlLeaseJson{controlOwner, taskId, controlExpiresAtMs}` + `BrowserControlGrantJson`/`BrowserControlEnvelopeJson` implement who is driving the browser (agent vs. human "take control"), time-boxed by `controlExpiresAtMs`. `BrowserViewerRequestJson` requests a viewer slot. Do not confuse this **browser control lease** with the unrelated SEV-SNP **chip-selection "bid"** in §6 — see §11.

### 4.6 The agentspaces tunnel framing (`found`)

`HatchSpaceTunnel` proxies a WebView to CVM-hosted "spaces" apps at `/spaces/cvm/<slug>` over `hatch_vm_*`. The small JSON envelope protocol: `{"type":"http.res",id,status,streaming}`, `{"type":"http.end",…}`, `{"type":"http.err",…}`, plus a cache-busting push `{"type":"hatch:space:query-invalidated","spaceSlug":…,"payload":{"queryKeys":[…]}}`. It **strips hop-by-hop and identifying headers** before relaying — blocklist includes `authorization, cookie, host, origin, x-forwarded-*, x-real-ip, x-noise-connection-id` — confirming the CVM side terminates a real HTTP server reached only through the Noise connection id.

---

## 5. The agent workspace

Every feature below is built on the four `NoiseHatchVmTransport` verbs from §4.3, i.e. every path literal below is an HTTP request *inside* the Noise tunnel to the CVM. Bootstrap: `HatchBootstrapRequest` posts `{"sections":[…]}` on a `channel.bootstrap` subscribe method and reads back `{"accepted":[…]}` — the client declares which workspace sections it wants pushed. `HatchSpacesSync` only starts when "Hatch is linked and a VM endpoint exists" (`found` log guards).

### 5.1 Agent spaces

A **space** is an agent-hosted mini web app / interactive result page served from inside the CVM, addressed by a string `slug`. The phone never gets the HTML directly — a local WebView (`HatchSpaceActivity`) is pointed at the tunnel (§4.6), which streams the CVM's HTTP responses back frame by frame, so a space can be a live, stateful app rather than a static artifact.

| action | method + path | notes |
|--------|---------------|-------|
| catalog | `GET /spaces/v2` | `{"spaces":[{"slug","preview_card_url","preview_image",…}]}` |
| share-status | `GET /spaces/share/<slug>` | returns a share URL if shared+public |
| publish | multi-step (`publish`/`post`/`poll`) | may return "needs confirmation" |
| unpublish | `DELETE /spaces/share/<slug>` | |
| delete | `DELETE /spaces/v2/<slug>?source=space` | |
| pin / unpin artifact | `POST /api/artifacts/pin {"artifact_ref":…,"pinned":bool}` | pins a space's output as an artifact |

Real-world example (`inferred`): the user says "track flights to Lisbon under €200"; Muse builds a tracker space; the user opens it live, publishes a shareable link, and pins the best result as an artifact.

### 5.2 Feed and activity

`HatchFeedApi` decodes a dated digest of **editions**, each holding **units** (`unit_id, title, kicker, emoji, body_md, days`) — the agent's periodic briefing. Backed by the activity timeline: `GET /api/activity?limit=200` into records (`timestamp, type, status, title, subtitle, messageId, taskLabel, details.goal{…}`), linking each record to a chat message and optionally a goal. The standalone Feed entry point is debug-gated in 41.6 (`str5508` "[Debug Only] Feed"); the activity timeline that feeds it is not.

### 5.3 Goals

`HatchGoalsApi`: list `GET /api/goals?<query>`, detail `GET /api/goals/<goal_id>`. A goal is a durable objective: `{goal_id, title, emoji, summary, momentum_status, sub_goals:[…], updates:[{text, effective_at}]}` — a standing objective with a health status and a timestamped update log the agent appends to. Entry is debug-gated (`str5511` "[Debug Only] Goals").

### 5.4 Ideas

Agent-proposed, runnable actions the user can **Execute** or **Cancel** (`HatchIdeaDetailBottomSheet`). Strings: "This idea is already running.", "This idea isn't available anymore.", "No ideas right now. Check back later.", "Couldn't start that idea. Try again." Example: the agent suggests "Draft the Q3 recap"; tapping Execute starts a running task recorded in feed/activity.

### 5.5 Artifacts and workspace media/files

Artifacts are agent-produced outputs (document, image, spreadsheet, a space's result), pinned/unpinned via `/api/artifacts/pin`. The agent's files live in a **real per-agent CVM filesystem** (`com.whatsapp.bot.infra.vmmedia.HatchWorkspaceMediaApi`):

| call | path | shape |
|------|------|-------|
| library | `POST /fs/library {"preset":"media","limit":n,"offset":m}` | `{entries:[{path,size,modified_ms}],total,has_more}` |
| raw | `GET /fs/raw/<path>` | raw bytes |
| thumbnail | `GET /fs/thumbnail/<path>?p=sm` | |
| delete | `POST /fs/delete {"path":…,"recursive":false}` | |

Delete-confirm string: "This file will be removed from your agent's files. You can't undo this."

### 5.6 Identity documents

The agent's "about me" documents are stored as **plain-text files in the same VM filesystem**, not a dedicated store: `GET /fs/read {path,offset,len}` → `{text,bytes,eof,not_found}`; `POST /fs/write {path,text|bytes,offset,append,overwrite,create_parent}`. The user edits documents the agent then reads as persistent context.

### 5.7 Approvals and approval history

**Live gate:** before a risky/irreversible action the agent raises an approval (`HatchBrowserPreviewActivity`, `str54e1` "Approval required"). **History/audit:** `GET /approvals/history?record_schema=snapshot_v1&limit=50`, paged via `next_cursor`, into a structured record per approval: `{approval_id, status, decision, outcome_label, summary_title, purpose_summary, scope_summary, requested_at_ms, permission_question, payload_preview, request_preview_document, display_name, icon_key, blocks, rows, fields, items, links, attachments, version, truncated}`. Entry is debug-gated (`str54e8` "[Debug Only] Approval history"), the underlying log is not.

### 5.8 Scheduled tasks — three distinct implementations

| # | Surface | Transport | Ops | Client-reachable? |
|---|---------|-----------|-----|--------------------|
| a | 1:1 Meta AI reminders (`com.whatsapp.metaai.tasks`) | plain MEX over `whatsapp-android-www` | **`GetMetaAiReminders`**, **`DeleteMetaAiReminder`** | **Yes-ish** — name-based persisted-query MEX, no attested/native blocker |
| b | Group scheduled tasks (`com.whatsapp.bot.group.groupinstructions.impl`, new 41.6) | plain MEX over `whatsapp-android-www` | **`GetMetaAiGroupReminders`** (param `groupId`), **`DeleteMetaAiGroupReminder`** (`groupId`, `reminderId`) | **Yes-ish** — same reasoning |
| c | Hatch VM scheduled tasks (`com.whatsapp.hatch.scheduledtasks.impl`) | Noise VM | recurring agent-VM runs, cancelled over the VM transport | No — native-only |

9a/9b are the **only** workspace ops a third-party client could plausibly reach, because they touch neither the native noise-gateway carrier nor WAFFLE onboarding. Creating a reminder appears to happen agent-side (via the Meta AI chat tool-call), not through a client-visible mutation — only Get + Delete ops are present. Numeric `doc_id`s for both pairs are `unknown` (name-based persisted-query resolution; not independently captured). The group-instructions surface also lets an admin configure the group's Meta AI (rules, reference docs, tone) via `CustomizeGroupMetaAiActivity` — adjacent UI, not itself a scheduled-task op.

### 5.9 Connectors and the secure credential store

A **connector** is a registered binding between the agent and an external service. The user authenticates once (OAuth / API key / username+password / FoA / Stripe / Messenger), and the resulting credential is stored **server-side inside the CVM, never in Android Keystore** — `SecureCredentialVault` performs all operations as HTTP calls over the same VM Noise-HTTP transport. No `KeyStore`, `EncryptedSharedPreferences`, or `AndroidKeyStore` reference exists anywhere in `securecredentials/`.

Credential endpoints (`found`, over the Noise VM channel):

| path | role |
|------|------|
| `POST /v1/credentials/capture` | push a captured credential |
| `POST /v1/credentials/catalog/update` | upsert; fields seen: `username`, `password`; permission via `JA9` wireValue enum |
| `POST /v1/credentials/catalog/delete` | `{id}` → `{ok}` |
| `GET /v1/custom-connectors/list` | |
| `POST /v1/custom-connectors/register` | API-key shape `{connector, api_key:{key}, replace_existing}` or OAuth shape `{connector, oauth_bootstrap:{client_id, client_secret?,…}, replace_existing}` → `authorize_url` |

Connector catalog + connect flows (`found`, over the same channel): `GET /api/connectors?surface=settings&icon_cdn=whatsapp` → `{connectors:[{id,name,description,icon,state,is_custom,management_kind,supports_multiple_accounts,consent}]}`; per-connector connect-info (`/connectors/<id>/connect/info`) and type-specific auth paths for OAuth, API key, username/password (with `two_factor_required`/`attempts_remaining`/`login_timeout_remaining_secs`), **FoA** (Family-of-Apps accounts), **Messenger companion** (PIN-gated chat linking), and **Stripe link** (payments). Permissions are per-connector (`GET/SET /permissions/connectors/<id>`, UI string "Agent permissions"). Custom connectors carry an explicit unreviewed-code warning ("Meta doesn't review custom connectors… supervise your agent's use").

By design, the agent **does not see raw secrets**: "Securely store passwords for your agent to use", "Shared with your agent without saving". The **virtual card** action (`HatchConnectorCardActionActivity`) mints a one-time card the agent uses for payments so the real card number is never exposed ("The agent will never see your credit card"). `assets/api_key.txt` exists in the APK and is treated as credential material per the brain's evidence contract — not opened/quoted here; `inferred` to be a client/app-level API key for the hatch-api/GraphQL control plane, not a per-user secret.

**Reachability for all of §5:** native-only. Every path literal above is recoverable from the APK; none of it is drivable, observable (it is encrypted inside the Noise tunnel), or impersonable from a third-party client, because every one of these calls needs the §4 attested transport plus a WAFFLE-provisioned VM.

---

## 6. CVM identity recovery — the Vesta OPAQUE PIN system (`hatch/cvm`)

### 6.1 Correcting the "virtual-card vault" framing

An earlier research pass (2.26.45.10) described `hatch/cvm` + `hatch/cvm/pin` as a "PIN-gated virtual-card vault". **That framing is wrong at the crypto layer.** It conflates two unrelated subsystems:

- **`hatch.connectors` / `HatchConnectorCardActionActivity`** (§5.9) — a real, separate connector-grant flow for a third-party payment rail (almost certainly Stripe). It has **zero code references** to any `com.whatsapp.hatch.cvm` or `com.facebook.vesta` class (checked: no cross-reference from `hatch.connectors` smali to `HatchCvmPinActivity`/`HatchCvmVestaClient`/`HatchCvmKeyService`).
- **`hatch.cvm` / `hatch.cvm.pin`** is the agent's **confidential-VM identity and chip-attestation enrollment system**, not a card store. It stores **no payment data of any kind** — no PAN/CVV/billing field anywhere in the package. What it protects is a **device/VM identity secret recovered via an OPAQUE password-authenticated key exchange, PIN as the password**, tied to AMD SEV-SNP hardware-chip selection for the CVM.

The PIN is **not a local-only unlock**: `HatchCvmKeyService`'s login path round-trips a real OPAQUE exchange to a Meta backend (`hatch-api.meta.ai/hatch/vesta-auth/*`, plain HTTPS) before any local key material is derived/restored. A wrong PIN fails **server-side** ("wrong pin", "crypto failed"), not just against a local hash.

Critically, this traffic is **plain HTTPS to `hatch-api.meta.ai`** — the same control-plane host as `/hatch/vm/wake` (§3.3) — **not** the attested Noise-gateway-over-Tigon VM channel. So the blanket "same hard blockers as the transport" claim from §4/§5 does not apply here: the real blocker for this subsystem is a cryptographic one, not an attested-transport one.

### 6.2 The native surface

`com.facebook.vesta.VestaClient` loads **`libvesta_client_jni.so`** (new in 2.26.45.10). All 19 native methods declared on it implement a **PIN-as-password OPAQUE PAKE, additionally wrapped with a post-quantum KEM/signature layer**, plus a device-bound "HSM key" validation step:

| native method | role |
|---|---|
| `getApiVersionNative` / `getProtocolVersionNative` | version negotiation |
| `beginLoginNative` / `finishLoginNative` (×2 overloads) | OPAQUE login steps 1 and 2 (produces session/export key material) |
| `beginRegisterNative` / `finishRegisterNative` / `finishRegisterProtoNative` | OPAQUE registration (enrolling a new PIN) |
| `unpackLoginPayloadNative` / `unpackLoginPayloadProtoNative` | decode the server's escrowed login payload |
| `validateHsmKeyNative` / `validateHsmKeysWithOtaBundleNative` | validate a hardware-backed key pair, optionally with a device-key-rotation OTA bundle |
| `verifyRestoreHistoryNative` | verify a prior-restore/recovery history record |
| `pqWrapFinishLoginNative` / `pqWrapFinishRegisterNative` / `pqUnwrapFinishLoginResponseNative` | post-quantum wrap/unwrap of login/register payloads |
| `pqWrapSchemeNative` | which PQ scheme is in use (`unknown` return value — needs Frida) |

`libvesta_client_jni.so` is, like the Noise-gateway carrier, packed inside the opaque SUPERPACK blob — no byte-exact static extraction was possible this pass. `libvoprf-ed25519.so` (present in the same build) is consistent with an OPRF/VOPRF primitive (OPAQUE's core building block) but was **not** independently cross-linked to `VestaClient` — recorded as a plausible adjacent library, not proven to be the same implementation (`unknown`).

### 6.3 Wire endpoints — plain HTTPS to `hatch-api.meta.ai`

| path | role |
|---|---|
| `POST /hatch/vesta-auth/begin-login` | OPAQUE login step 1 |
| `POST /hatch/vesta-auth/finish-login` | OPAQUE login step 2, returns the escrowed payload |
| `POST /hatch/vesta-auth/begin-register` | OPAQUE registration step 1 (new/changed PIN) |
| `POST /hatch/vesta-auth/finish-register` | OPAQUE registration step 2 |
| `GET /hatch/vesta-auth/user-info` | `is_registered` + attempt/lockout counters |
| `GET /hatch/fetch_vms?notary_token=true[&vm_id=]` | list/resolve the user's CVM(s) |
| `POST /hatch/lease_vm` / `POST /hatch/cold-lease-cvm` | lease a CVM instance (warm / cold) |
| `GET /hatch/cvm-replace-state?env_id=` | CVM state-machine transition |
| `GET /hatch/cvm-chip-allowlist?env_id=` | which SEV-SNP chip IDs are allowed for this CVM |
| `POST /hatch/cvm-chip-selection` | commit the chip selection/bid |
| `GET /hatch/onboarding_statuses` | onboarding status check |
| `POST /hatch/vm/wake` | wake/resume the CVM (also §3.3) |

None of these touch `/v1/noise` or the `hatch_vm_*` verbs — confirming §6.1's correction. `/hatch/cvm-chip-allowlist` and `/hatch/cvm-chip-selection` are the first **concrete wire evidence** for the SEV-SNP "pinned to specific chip IDs" attestation mode that §4.2 only found as a native constructor signature.

Wire DTOs (`kotlinx.serialization` serial-name fields, not obfuscated Java field names) include OPAQUE's own **L1/L2/L3** three-message exchange naming (`base64url_encoded_opaque_l1/l2/l3`, plus `_sig` variants), device-bound **"island" RSA/Ed25519 public keys** (`unknown` provenance — HSM/Keystore vs. a Vesta-internal format), and a local journal (`HatchCvmJournal`: `candidate_chip_ids`, `accepted_chip_ids`, `bid_state` enum `PENDING/ACCEPTED/RETIRED`, `abra_user_id` — the same bearer identity as `GraphQlHatchAbraTokenProvider`).

### 6.4 What the PIN actually gates

`HatchCvmKeyService.A00` (the recover path): (1) runs OPAQUE login (`begin-login` then `finish-login`, native math); (2) only on success, `HatchCvmKeyProviderImpl` derives/restores the actual local key material from the escrowed login payload; (3) a wipe path exists for device-key mismatch or explicit reset. **A correct PIN is required to complete a real client↔server OPAQUE exchange** — the server only releases the escrowed payload on a correct finish-login, rate-limited and verified server-side (`attempts_remaining`, `login_timeout_remaining_secs` on every response). An attacker with the device but not the PIN cannot brute-force past this locally. The protected secret is **the CVM/device-identity key material needed to resume this user's confidential-VM session** — not a payment credential.

Separately, `HatchCvmPinReminder` uses a **local-only** AES/GCM key (alias `hatch:pin-reminder:v1:...`) purely to encrypt a "remind me to set a PIN" notification state — unrelated to the Vesta exchange and the only piece of not-wire-observable crypto in this subsystem.

### 6.5 Reachability verdict for §6

Wire schema fully recoverable (above); transport is plain HTTPS, in principle MITM-observable **without** defeating WAFFLE attestation or the native Noise-gateway carrier. But **actually participating** (a real login/register) is not possible from the APK alone: every request/response field is produced or consumed by native OPAQUE + post-quantum wrap/unwrap operations inside `libvesta_client_jni.so`, packed in the superpack with no byte-exact extraction available. A client could capture and replay the plaintext JSON *shape* but cannot compute a valid `opaque_l1`/`l3`, island key-pair proof, or PQ-wrapped payload — a **cryptographic** blocker, structurally different from the attested-transport blocker in §4.

---

## 7. Monetization — the Hatch paid subscription tier

A 2.26.45.10-era subscription cluster adds a real, billed tier for Muse. The purchase flow (`inferred` chain, each step `found` individually):

1. Client checks the feature flag **`ai_hatch_in_app_subscriptions_enabled`** (log: "`ai_hatch_in_app_subscriptions_enabled` is off"). No numeric flag ID was found for it — it is referenced by name only.
2. Tier constant **`NME_SUBSCRIPTION`**; product details fetched per tier (`HatchSubscriptionPurchase$launch$2`, log "Fetching product details for tier"; tier name interpolated, not a hardcoded SKU).
3. Compliance check: **`WamoSubGetComplianceInfo`** (`whatsapp-android-mex`, name-based, no input fields set at the call site — session/identity-scoped only).
4. Payments token mint: **`HatchGenFrlPaymentsAccessTokenMutation`** (`GraphQlHatchFrlPaymentsTokenProvider`, namespace `whatsapp-android-www`; "FRL" expansion not found in any string this pass — `unknown`).
5. Google Play Billing launch (`HatchManageSubscriptionViewModel$openBilling$1`) — standard Android `BillingClient` via a shared Meta commerce SDK (`com.facebook.payments.dcp.xapp.*`), tagged `app="WHATSAPP"`.
6. On purchase, server-side fulfillment reconciliation (`HatchSubscriptionPurchaseReconciler`), likely via **`DCPFulfillIAPTransactionsMutation`** (`pay_dcp_fulfill_iap_transactions`, direct Pando request, fields `platform`/`app`/`purchase_tokens`/`subscription_purchase_tokens`/`upl_session_id`, all mandatory at this call site) — not independently confirmed as the exact call this reconciler uses (`unknown`).

Four further ops declared only in the persisted-query catalog (`IACQueryProductInfo`, `IACQuoteDisplay`, `IACSandboxPlatformMode`, `DCPInternalSandboxCreateSessionMutation`) have **no calling class found anywhere in smali** — `unknown` whether that is dead/future code, a server/flag gate, or a string-concatenated call site a plain grep misses.

**Reachability:**

| op | namespace | needs | reachable by a third-party client? |
|---|---|---|---|
| `WamoSubGetComplianceInfo` | `whatsapp-android-mex` | an authenticated mex session only | **Yes, in principle** — plain parameterless mex query |
| `HatchGenFrlPaymentsAccessTokenMutation` | `whatsapp-android-www` | authenticated session | **Transport-reachable**; the minted token's value outside the intended flow is `unknown` |
| `DCPFulfillIAPTransactionsMutation` | `whatsapp-schema` (Pando) | a genuine Google-signed Play Billing purchase/subscription token | **No** — request is shapeable, but nothing truthful can be put in it without a real Play Billing purchase through a signed `com.whatsapp` context |
| `IAC*` / `DCPInternalSandboxCreateSessionMutation` | `whatsapp-schema` | unknown (no calling class found) | **Unknown** |
| Google Play Billing itself | n/a | Play Store + signed app context | **No** — not even a WhatsApp server call |

---

## 8. Reachability verdict

| Component | Transport | Blocker | Reachable from a third-party (Baileys/velowa) client? |
|---|---|---|---|
| Agent spaces, feed/activity, goals, ideas, artifacts, workspace media/files, identity docs, approvals+history, Hatch VM scheduled tasks, connectors (all flows), secure credential store | Attested Noise VM channel (§4) | native noise-gateway carrier `.so` + WAFFLE onboarding | **No** |
| Control plane (VM wake, Abra token, pairing URL) | plain HTTPS to `hatch-api.meta.ai` | WAFFLE-gated provisioning (server won't issue a working VM without it) | **No** (schema MITM-observable; not independently drivable) |
| CVM identity/PIN recovery (`hatch/cvm`, Vesta OPAQUE) | plain HTTPS to `hatch-api.meta.ai` | native OPAQUE + post-quantum math in `libvesta_client_jni.so` | **No** — cryptographic blocker, not an attested-transport one |
| 1:1 reminders — `GetMetaAiReminders` / `DeleteMetaAiReminder` | plain MEX, `whatsapp-android-www` | none found | **Yes-ish** (doc_id `unknown`) |
| Group reminders — `GetMetaAiGroupReminders` / `DeleteMetaAiGroupReminder` | plain MEX, `whatsapp-android-www` | none found | **Yes-ish** (doc_id `unknown`) |
| Subscription compliance info — `WamoSubGetComplianceInfo` | plain MEX, `whatsapp-android-mex` | none found | **Yes, in principle** |
| Payments token mint — `HatchGenFrlPaymentsAccessTokenMutation` | plain GraphQL, `whatsapp-android-www` | none at transport level; token's practical value elsewhere unknown | **Transport-reachable** |
| IAP fulfillment — `DCPFulfillIAPTransactionsMutation` | plain Pando GraphQL, `whatsapp-schema` | needs a genuine signed Play Billing token | **No** (nothing truthful to send) |
| `IAC*` / sandbox IAP ops | `whatsapp-schema` | no calling class found | **Unknown** |
| richResponse quiz (bot.quiz) | local message store | none — not a VM feature | payload recoverable; arrives as a normal bot message |

The "Yes-ish"/"Yes, in principle" rows are the **entire** client-reachable surface of this subsystem. Everything else — which is most of the agent — requires either the native Noise-gateway carrier plus a valid WAFFLE attestation, or native OPAQUE/post-quantum cryptography that cannot be statically extracted from this APK.

---

## 9. Baileys / velowa

**Verdict: this subsystem is JS-impossible for a third-party client, full stop — not a missing feature, a structural one.** velowa (the active client project behind these docs) cannot implement the Hatch/Muse agent-browser VM or workspace for the same reasons the original research pass gave:

| Blocker | Why it cannot be worked around in JS/WASM |
|---|---|
| `libwa-noise-gateway-carrier-jni.so` | The entire Noise handshake and WebSocket framing for the VM channel is native code inside the opaque SUPERPACK blob. There is no protocol document to reimplement against — the wire shape (query params, `/v1/noise` path, HTTP-over-Noise verbs, noVNC RFB subprotocol) is recovered above, but the actual Noise cryptography (key derivation, frame authentication) only exists compiled into that `.so`. Reimplementing it means reverse-engineering a stripped native library, not writing a client against a spec. |
| WAFFLE official-client attestation | Gates VM onboarding before any Noise channel is even opened. A third-party client cannot produce a valid WAFFLE token, so it cannot provision a VM in the first place — this blocks even an attempt at the Noise handshake. |
| `libvesta_client_jni.so` (OPAQUE + PQ) | Separate from the above: even where the identity-recovery traffic (§6) is plain HTTPS and observable, the client-side OPAQUE math (`opaque_l1`/`l3`, the "island" key-pair proofs, the post-quantum wrap) is native. Capturing the JSON shape does not give you anything to compute a valid request with. |
| AMD SEV-SNP attestation | Orthogonal to the client — it is the *server's* VM proving itself genuine to the official app — but confirms the whole design assumes a native, attested peer on both ends. |
| Tigon | Meta's internal cross-app native HTTP stack carries every request in §4 and §6; its request objects are not a public, versioned wire format. |

What velowa (or any protocol client) *could* reach without touching any of the above: the four name-based MEX reminder ops (§5.8) and the subscription-compliance/payments-token GraphQL ops (§7) — all of which ride the same plain WA MEX/GraphQL transport velowa already speaks for everything else in this repo. No code example is given here because none of this report's source material captured a concrete request/response for those ops beyond the operation names and parameter shapes already listed in §5.8/§7/§8; inventing payload bytes would misrepresent evidence tier.

---

## 10. Error cases / gotchas

| Symptom | Cause | Note |
|---|---|---|
| "Computer is turned off on this VM" | VM not provisioned/awake for the full desktop surface | `HatchComputerActivity` string |
| "Approval required" never resolves to an action | user has not confirmed the approval gate | by design — human-in-the-loop |
| "This idea isn't available anymore." / "This idea is already running." | idea card superseded or already executing | `HatchIdeaDetailBottomSheet` |
| "No goals yet" / "No ideas right now. Check back later." / "No approvals yet" | empty workspace sections, not an error | |
| "Couldn't load your agent's files" | `/fs/library` or `/fs/raw/` call failed over the Noise tunnel | |
| `PrivateSearchSessionManager`-style "thread superseded by a newer search, refusing" (adjacent TEE system, not Hatch) | listed in §11 only to avoid cross-contamination of error strings between the two systems | see Key Distinctions |
| 400 "already exists; set replace_existing=true" | custom-connector register without the `replace_existing` flag | `HatchConnectorsListRequester` |
| "wrong pin" / "finish-login crypto failed" | OPAQUE login failed server-side | rate-limited via `attempts_remaining`/`login_timeout_remaining_secs` |
| "hsm key missing" / "hsm key invalid" / "hsm key check failed" | device-bound HSM key validation failed inside the Vesta recovery path | §6.4 |
| `noise/gave-up limit=deadline` | VM Noise channel open budget (60 s) exceeded | `NoiseVmConnection` |
| `NoiseHandshakeOutcome.VERIFICATION_FAILED` | attestation check failed on the Noise-gateway handshake | §4.2 |
| "`ai_hatch_in_app_subscriptions_enabled` is off" | subscription feature flag disabled server-side | §7 |
| "HatchSubscriptionPurchase/purchase no compliance data" | `WamoSubGetComplianceInfo` result missing before a purchase attempt | §7 |

---

## 11. Key distinctions — what NOT to confuse

| Do not confuse | Fact |
|---|---|
| Hatch/Muse agent (this report) vs. **Meta AI chat** (`WA_META_AI.md`) | Meta AI is a bot contact reached by `botInvokeMessage`/bot JIDs on the normal message proto; Hatch/Muse is a separate agent that drives a remote attested VM. They share some plumbing (Hatch JSON metadata channel via `ProtocolMessage.aiMetadataOperation`, capability flags advertised to the Hatch bot JID `1807055946647697@bot`) but are architecturally distinct subsystems |
| Hatch/Muse VM vs. **Private Processing / TEE cluster** (chat-context AI, Private Search) | The TEE cluster (`ClusterFetchPrekeyBundleConnection`, `IplsdHandshakeExecutor`, `PsiSearchToolHandler`, `TeePrefixCacheAnchor`) is Meta AI answering questions **about your own local chats** via an attested enclave + PSI search — it has nothing to do with the Hatch agent-browser VM. Private Search's *query send* rides a plain bot-chat message (reachable), while the PSI/enclave computation itself stays native — a different reachability shape than anything in this report |
| `hatch.cvm` (identity/chip recovery, §6) vs. `hatch.connectors` (virtual card / Stripe, §5.9) | Two separate features sharing only the casual words "card"/"vault" in product framing; no code dependency between them (checked) |
| `HatchCvmPinReminder`'s local AES/GCM key vs. the Vesta OPAQUE exchange | Local-only notification-state encryption vs. a real server-round-tripped identity recovery — only the latter is "server-side" PIN gating |
| "bid_state"/"chip" fields (§6) vs. the browser **control lease** (§4.5) | SEV-SNP hardware-chip-selection bookkeeping vs. who is driving the agent browser (agent/human) — three different uses of overlapping vocabulary ("bid"/"lease"/"control") in this codebase |
| Vesta's plain-HTTPS control plane (§3, §6) vs. the attested Noise-gateway VM channel (§4) | Different transports, different blockers (native OPAQUE math vs. native Noise + WAFFLE attestation) — conflating them overstates where the attested-transport blocker actually applies |
| Agent spaces (§5.1) vs. agent-produced artifacts (§5.5) | A space is a live, stateful hosted app; an artifact is a static output (a space's *pinned result* becomes an artifact, but the space itself keeps running) |
| `com.whatsapp.bot.quiz.AiQuizViewerActivity` vs. a Hatch feature | Reads a richResponse quiz already delivered as a normal bot message from local storage — no VM, no network call, not part of this subsystem at all |

---

## 12. End-to-end flow — one agent-browser-task session

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

Separately (not part of the same session, plain MEX/GraphQL, no attested transport involved):

```
[Client]  GetMetaAiReminders / GetMetaAiGroupReminders
    │  whatsapp-android-www, name-based persisted query
    ▼
[WA server]  reminder list (status SCHEDULED/CLAIMED/FULFILLED)

[Client]  DeleteMetaAiReminder / DeleteMetaAiGroupReminder
    ▼
[WA server]  reminder removed
```
