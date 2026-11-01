# WhatsApp Client Mod Detection — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-11-01
**Scope:** Client-side detection of unofficial/modified Android clients (GB WhatsApp-family repacks, Xposed/LSPosed hook modules such as WaEnhancer, re-signed APKs) — the one dedicated mod heuristic found (`is_whatsapp_plus_user`), hook-framework artifact search (Xposed/Frida/Substrate), what the client does with the signature/install-source/root telemetry already catalogued in `WA_CLIENT_INTEGRITY.md`, the WFAC ban UI's handling of server-sent ban reasons, and the attack surface a third-party hook module (WaEnhancer) is known to target inside the host process

---

## 1. Overview

This report is scoped to **mod/tamper detection**, not account attestation. Keystore attestation, Play Integrity, WASafe, the signature self-check (WAM **6251**) and the install-source flag (WAM **10255**) are fully documented in [`WA_CLIENT_INTEGRITY.md`](WA_CLIENT_INTEGRITY.md); this report only states what they contribute to mod detection and does not repeat their mechanics.

| Mechanism | Detects | Reported as | Enforcement found |
|-----------|---------|-------------|--------------------|
| `is_whatsapp_plus_user` (reflective class probe) | A third-party client that bundles the ACRA crash-reporter library | `wam_daily` telemetry field; `diagnostic` string in contact-us (`nw-wap`) and debug report (`NW-WAP-1`) | none |
| App signature self-check (`AbstractC38241gg` / `C27965CCj`) — see integrity report §5 | Re-signed/repackaged APK (signing cert ≠ WhatsApp's embedded value) | WAM common attribute **6251** | none |
| Install source flag (`CHH`) — see integrity report §5.4 | Sideloaded / non-Play install | WAM **10255**, `install_source_official` | module-download routing only, no gate |
| Root / emulator / custom-ROM flags (`C00L`, `Cdt`) — see integrity report §6 | Rooted or emulated device (a common enabler, not itself a mod signal) | `wam_daily` | none |
| Hook-framework artifact strings (Xposed, Frida, Substrate, LSPosed, TracerPid) | — | — | **not found** in this build (§3) |
| Native library / dex self-checksum | — | — | **not found** in this build (§3) |
| WFAC ban UI (`WfacBanActivity`) | — | displays server-sent `ban_violation_type` / `ban_violation_source` / `ban_violation_reason` | server decision, opaque to the client (§5) |

No code path was found anywhere in the decompiled client that refuses to run, degrades a feature, or blocks an action because of any of the above. Every mechanism found is **telemetry**, consistent with the conclusion already reached for account integrity.

---

## 2. The one dedicated mod heuristic: `is_whatsapp_plus_user`

### 2.1 What it checks

Three independent sites, each running the **same reflective probe** rather than calling a shared helper:

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

| Item | Value | Tier |
|------|-------|------|
| Check | `Class.forName("org.acra.ACRA")` succeeds (class present on the classpath) | found |
| Field name | `is_whatsapp_plus_user` (`LX/0Fp;->A0W`), `wam_daily` event | found |
| Sinks | `wam_daily` telemetry; contact-us `diagnostic` string (`nw-wap `); debug-report text (`NW-WAP-1 `) | found |
| Rationale | ACRA (`org.acra`) is a third-party crash-reporting library; stock WhatsApp does not bundle it. Historically bundled by "WhatsApp Plus"-family repacks for their own crash telemetry (`inferred`: the field name is WhatsApp's own choice of label, not a value read from the mod) | found (probe) / inferred (label meaning) |
| Decompile gap | `Cdt.java` itself did not decompile (only the sibling `CDT.java` exists); the check is read from smali | found |

### 2.2 What it does NOT do

- No allowlist/denylist of mod package names (`com.gbwhatsapp`, `com.yowhatsapp`, `com.fmwhatsapp`, `com.wmods.wppenhacer`, …) exists anywhere in the decompiled client — none of these strings occur in `java_src` or `smali*`.
- The probe is a single reflective class lookup, not a signature, hash, or behavior check. A mod that simply does not bundle `org.acra.ACRA` (or shades/renames the class) defeats it trivially; this report does not claim otherwise.
- The three sinks are diagnostics/telemetry text and a daily analytics event. No branch reading `A0W`/`is_whatsapp_plus_user` was found that changes client behavior.

---

## 3. Hook-framework and repack artifact search (not found)

Searched across the full decompiled tree (`java_src/`, all `smali*/`) for 2.26.41.6:

| Anchor string(s) | Target | Result |
|-------------------|--------|--------|
| `Xposed`, `XposedBridge`, `de.robv`, `LSPosed` | Xposed/LSPosed hook framework presence | not found |
| `frida`, `Frida`, `re.frida`, `frida-server`, port `27042` | Frida instrumentation server | not found (the one `frida` substring hit is inside a public-suffix/TLD regex literal, unrelated) |
| `substrate`, `Substrate` | Cydia Substrate hook framework | not found |
| `TracerPid` | classic `/proc/self/status` ptrace-tracer detection | not found |
| `GBWhatsApp`, `gbwhatsapp`, `com.gbwhatsapp`, `FMWhatsApp`, `YoWhatsApp`, `OGWhatsApp`, `com.wmods.wppenhacer` | named mod-client package strings | not found |
| `modded`, `unofficial`, `tampered`, `fake whatsapp`, `clone app` | generic mod-detection prose/log strings | not found |
| `CRC32` usages (10 hits) | dex/asset self-checksum | all in multidex loading (`dextricks`) or crash-report zip packaging, none is an app-tamper self-check |
| `checkSignatures` (3 hits) | signature comparison | all are IPC/caller-trust checks (`FileSharingHelper` same-signature caller check, a Pixel companion-app trust check) unrelated to detecting a modified WhatsApp client |
| `isDebuggerConnected` | anti-debug | only in the ANR detector (`SigquitBasedANRDetector`) and crash helpers, not a tamper gate (confirms `WA_CLIENT_INTEGRITY.md` §6.4) |
| `/proc/self/status` (4 hits, `KGi`/`KGw`/`KH8`/`KGp`) | — | memory-stats readers (likely `VmRSS` collection for diagnostics); no `TracerPid` parsing found there |

**Correction to an earlier research note's framing:** a prior static-analysis note describes WaEnhancer as "exactly the kind of modded/unofficial client the stock app's integrity system targets" but does not claim the stock app detects it by name — that reading is confirmed here: there is no WaEnhancer-specific, GB-specific, or Xposed-specific detection code in 2.26.41.6. The only client-side signal that would fire for a WaEnhancer install is the generic `is_whatsapp_plus_user` ACRA probe, and only if the module (or a bundled dependency) happens to ship that class — not verified either way for WaEnhancer specifically (`unknown`).

This extends `WA_CLIENT_INTEGRITY.md` §6.4, which flagged dex/asset CRC as "not exhaustively searched" — it is now searched and still not found.

---

## 4. Server-side consequences visible client-side

### 4.1 WFAC ban UI

`WfacBanActivity` (`com.whatsapp.waffle.wfac.p191ui`) reads three server-supplied extras and renders them; it does not compute a reason:

```java
int violationType   = getIntent().getIntExtra("ban_violation_type", -1);
String violationReason = getIntent().getStringExtra("ban_violation_reason");
int violationSource  = getIntent().getIntExtra("ban_violation_source", -1);
```

| Item | Tier |
|------|------|
| `ban_violation_type` / `ban_violation_source` are opaque integers; no enum resolving them to named causes (e.g. "modified client") was found client-side | found (absence) |
| `ban_violation_reason` is a free-text string, presumably server-templated | found |
| No code path connects any of the detection signals in §1–§3 (`is_whatsapp_plus_user`, signature mismatch, root, install source) to a `ban_violation_*` value | found (absence) |

Full ban-state machine, GraphQL (`BizIntegrityQuery`), trust tiers, and XMPP failure stanzas are in [`WA_BAN_SYSTEM_DEEP_EN.md`](WA_BAN_SYSTEM_DEEP_EN.md); this report does not repeat that content. Whether the server uses any of §1's telemetry (signature mismatch, `is_whatsapp_plus_user`, root) as a ban input is **unknown** — it is server-side and not observable statically, same conclusion as `WA_CLIENT_INTEGRITY.md` §13.

### 4.2 Feature gating

No client-side branch was found that disables a feature based on §1's signals. The only "gating" observed anywhere in the integrity/mod surface is throttling of the attestation/token requests themselves (ab-props, documented in the integrity report) — not a response to detecting a mod.

---

## 5. Attack surface: what a hook module targets (WaEnhancer, `com.wmods.wppenhacer`)

This section describes the other side of the boundary — what a representative Xposed/LSPosed module hooks inside the host process — to frame what the (largely absent) client-side detection would need to cover. Evidence source: artifacts a WaEnhancer-modified install left in a captured `wa-data-root/` test directory (`Protocols/waenhancer-mod/info.md`), not static analysis of WhatsApp's own APK. Tiers as recorded there.

| Capability | Mechanism | Tier |
|------------|-----------|------|
| Delivery | Xposed/LSPosed module running **inside** the `com.whatsapp` process (not a separate app, not a repack) | found |
| Obfuscation handling | Runtime "Unobfuscator": resolves WhatsApp's obfuscated class/method names at module startup and caches resolved handles (`UnobfuscatorCache.xml`, `UnobfuscatorCacheStrings.xml`), keyed to WhatsApp's own version name so the cache invalidates on either side's update | found |
| Presence hiding ("ghost mode") | Hooks presence-related methods; setting stored in `WaGlobal.xml` (`ghostmode`) | found (artifact) |
| Anti-revoke / anti-read-receipt | Intercepts delete-for-everyone and read-receipt code paths; keeps shadow copies in its own stores (`com_waenhancer_message_history.db`, and a Room-backed `MessageHistory.db` — WhatsApp itself does not use Room for message storage) | found |
| Raw protocol visibility | `StanzaLogger.logStanza(...)` writes outgoing/incoming XMPP stanzas to a plaintext file (`wae_stanzas.txt`) — i.e. the module taps the client's own stanza-send/receive path after the Noise/E2E layer has already decrypted it | found |
| Hook bookkeeping | Per-run diagnostics logging a hook count (`devtrace_logs/*.jsonl`, `eventType:"hook_config_loaded"`, `payload.hookCount`) | found |
| Scope limit | Hooks the Java/UI layer only; does not appear to replace native crypto or the Noise/chatd transport (axolotl/Signal store, post-quantum prekeys, keystore, OHAI/OPAQUE/WAFFLE natives untouched) | inferred |

Read together with §3: the stock client has no code that enumerates loaded Xposed/LSPosed modules, scans its own process memory for hook trampolines, or checks `TracerPid`/`/proc/self/maps` for injected libraries. The only thing standing between this attack surface and detection is the single generic `is_whatsapp_plus_user` class probe (§2), which targets a crash-reporting library, not a hook framework.

---

## 6. Error cases / gotchas

| Symptom | Cause | Note |
|---------|-------|------|
| `is_whatsapp_plus_user = true` in `wam_daily` with no further client effect | `org.acra.ACRA` resolvable on the classpath | telemetry only, by design |
| `diagnostic` contains `nw-wap` / `NW-WAP-1` in contact-us or debug reports | same ACRA probe, different sink | support-flow text, not a gate |
| No WFAC ban screen reason beyond a numeric code | `ban_violation_type`/`ban_violation_source` have no client-side enum | server-controlled, cannot be resolved statically |
| Searching for "Xposed"/"Frida" turns up nothing | correct — this build contains no hook-framework detection | not a decompile gap for these specific strings (full-tree search) |
| A WaEnhancer install changes message/read-receipt behavior with no WhatsApp-side log | WaEnhancer hooks the Java layer before WhatsApp's own telemetry can observe the original call | expected given §5's scope |

---

## 7. Key distinctions

| Do not confuse | Fact |
|-----------------|------|
| `is_whatsapp_plus_user` vs a mod-client allowlist | one reflective probe for a third-party library class; no list of mod package names exists |
| Mod/tamper detection (this report) vs account attestation (`WA_CLIENT_INTEGRITY.md`) | different problems: this report is about detecting a *modified client binary/runtime*; the integrity report is about *attesting a genuine device/key* to the server — they overlap only in that both are telemetry, not enforcement |
| WFAC ban UI (`WfacBanActivity`) vs ban decision logic | the activity renders server-supplied codes/strings; it does not decide or compute a ban reason |
| WaEnhancer's `StanzaLogger` tap vs breaking E2E encryption | the module reads stanzas inside the already-decrypted client process; it does not attack the Signal/Noise cryptography itself |
| `safety-net-attestation` / signature / install-source telemetry | these exist and are documented in `WA_CLIENT_INTEGRITY.md`; this report adds no new mechanics for them, only states that none of them gate anything |
| "Not found" in this report | means absent from the decompiled Java/smali/strings of this specific build (2.26.41.6); it is not a claim about server-side detection, which is unobservable statically |

---

## 8. End-to-end flow

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

## 9. Unknowns

| Question | Why unknown |
|----------|-------------|
| Whether the server uses `is_whatsapp_plus_user`, signature mismatch (6251), install source (10255) or root flags as ban/trust-score inputs | server-side, no traffic observed |
| Whether `org.acra.ACRA` is actually present in a current WaEnhancer/GB WhatsApp build (i.e. whether the one heuristic that exists would even fire on it) | not verified against a live mod build in this pass |
| Named ban-reason mapping for `ban_violation_type` / `ban_violation_source` values | no enum resolved client-side; server-defined |
| Whether any native (`libwhatsapp.so`, `libwasafe.so`) code performs hook/tamper detection beyond what `WA_CLIENT_INTEGRITY.md` already found absent | stripped native libraries not exhaustively re-traced for this report beyond the string search in §3 |
| Server-side handling of a WaEnhancer-tapped `wae_stanzas.txt`-style visibility (i.e. whether the server can distinguish a hooked client from a genuine one at the protocol level) | not observable statically |
