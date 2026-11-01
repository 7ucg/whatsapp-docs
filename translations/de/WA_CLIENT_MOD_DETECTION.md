<!-- src-sha1: acf9c9e68ca59b17d45a787d66ae2550607b66cc -->
# WhatsApp Client-Mod-Erkennung — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-11-01
**Umfang:** Client-seitige Erkennung inoffizieller/modifizierter Android-Clients (GB-WhatsApp-Familie von Repacks, Xposed/LSPosed-Hook-Module wie WaEnhancer, neu signierte APKs) — die eine dedizierte Mod-Heuristik, die gefunden wurde (`is_whatsapp_plus_user`), die Suche nach Hook-Framework-Artefakten (Xposed/Frida/Substrate), was der Client mit der bereits in `WA_CLIENT_INTEGRITY.md` katalogisierten Signatur-/Install-Source-/Root-Telemetrie tut, der Umgang der WFAC-Ban-UI mit vom Server gesendeten Ban-Gründen, sowie die Angriffsfläche, die ein Third-Party-Hook-Modul (WaEnhancer) bekanntermaßen innerhalb des Host-Prozesses adressiert

---

## 1. Überblick

Dieser Report ist auf **Mod-/Tamper-Erkennung** eingegrenzt, nicht auf Account-Attestation. Keystore-Attestation, Play Integrity, WASafe, der Signatur-Selbstcheck (WAM **6251**) und das Install-Source-Flag (WAM **10255**) sind vollständig in [`WA_CLIENT_INTEGRITY.md`](WA_CLIENT_INTEGRITY.md) dokumentiert; dieser Report gibt nur an, was sie zur Mod-Erkennung beitragen, und wiederholt nicht deren Mechanik.

| Mechanismus | Erkennt | Gemeldet als | Enforcement gefunden |
|-----------|---------|-------------|--------------------|
| `is_whatsapp_plus_user` (reflektive Class-Probe) | Einen Third-Party-Client, der die ACRA-Crash-Reporter-Library bündelt | `wam_daily`-Telemetriefeld; `diagnostic`-String in Contact-us (`nw-wap`) und Debug-Report (`NW-WAP-1`) | keines |
| App-Signatur-Selbstcheck (`AbstractC38241gg` / `C27965CCj`) — siehe Integrity-Report §5 | Neu signierte/repackte APK (Signing-Zertifikat ≠ eingebetteter Wert von WhatsApp) | WAM Common Attribute **6251** | keines |
| Install-Source-Flag (`CHH`) — siehe Integrity-Report §5.4 | Sideload / Nicht-Play-Installation | WAM **10255**, `install_source_official` | nur Modul-Download-Routing, kein Gate |
| Root-/Emulator-/Custom-ROM-Flags (`C00L`, `Cdt`) — siehe Integrity-Report §6 | Gerootetes oder emuliertes Gerät (ein gängiger Enabler, aber kein Mod-Signal an sich) | `wam_daily` | keines |
| Hook-Framework-Artefakt-Strings (Xposed, Frida, Substrate, LSPosed, TracerPid) | — | — | **nicht gefunden** in diesem Build (§3) |
| Native-Library-/Dex-Selbst-Checksumme | — | — | **nicht gefunden** in diesem Build (§3) |
| WFAC-Ban-UI (`WfacBanActivity`) | — | zeigt vom Server gesendete `ban_violation_type` / `ban_violation_source` / `ban_violation_reason` an | Server-Entscheidung, für den Client opak (§5) |

Es wurde kein Codepfad irgendwo im dekompilierten Client gefunden, der die Ausführung verweigert, ein Feature degradiert oder eine Aktion blockiert aufgrund eines der oben genannten Punkte. Jeder gefundene Mechanismus ist **Telemetrie**, konsistent mit der bereits für Account-Integrity gezogenen Schlussfolgerung.

---

## 2. Die eine dedizierte Mod-Heuristik: `is_whatsapp_plus_user`

### 2.1 Was wird geprüft

Drei unabhängige Stellen, jede führt dieselbe reflektive Probe aus, statt einen gemeinsamen Helper aufzurufen:

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

| Punkt | Wert | Tier |
|------|-------|------|
| Check | `Class.forName("org.acra.ACRA")` erfolgreich (Klasse auf dem Classpath vorhanden) | found |
| Feldname | `is_whatsapp_plus_user` (`LX/0Fp;->A0W`), `wam_daily`-Event | found |
| Senken | `wam_daily`-Telemetrie; Contact-us-`diagnostic`-String (`nw-wap `); Debug-Report-Text (`NW-WAP-1 `) | found |
| Begründung | ACRA (`org.acra`) ist eine Third-Party-Crash-Reporting-Library; Stock-WhatsApp bündelt sie nicht. Historisch von Repacks der "WhatsApp Plus"-Familie für deren eigene Crash-Telemetrie gebündelt (`inferred`: der Feldname ist WhatsApps eigene Bezeichnungswahl, kein aus dem Mod gelesener Wert) | found (Probe) / inferred (Bedeutung des Labels) |
| Dekompilierungslücke | `Cdt.java` selbst dekompilierte nicht (nur die Sibling-Klasse `CDT.java` existiert); der Check wird aus Smali gelesen | found |

### 2.2 Was NICHT getan wird

- Es existiert nirgends im dekompilierten Client eine Allow-/Denylist von Mod-Paketnamen (`com.gbwhatsapp`, `com.yowhatsapp`, `com.fmwhatsapp`, `com.wmods.wppenhacer`, …) — keiner dieser Strings kommt in `java_src` oder `smali*` vor.
- Die Probe ist ein einzelner reflektiver Class-Lookup, kein Signatur-, Hash- oder Verhaltenscheck. Ein Mod, der `org.acra.ACRA` schlicht nicht bündelt (oder die Klasse shadet/umbenennt), unterläuft sie trivial; dieser Report behauptet nichts anderes.
- Die drei Senken sind Diagnose-/Telemetrietext und ein tägliches Analytics-Event. Es wurde kein Branch gefunden, der `A0W`/`is_whatsapp_plus_user` liest und das Client-Verhalten ändert.

---

## 3. Suche nach Hook-Framework- und Repack-Artefakten (nicht gefunden)

Durchsucht über den gesamten dekompilierten Baum (`java_src/`, alle `smali*/`) für 2.26.41.6:

| Anker-String(s) | Ziel | Ergebnis |
|-------------------|--------|--------|
| `Xposed`, `XposedBridge`, `de.robv`, `LSPosed` | Xposed/LSPosed-Hook-Framework-Präsenz | nicht gefunden |
| `frida`, `Frida`, `re.frida`, `frida-server`, Port `27042` | Frida-Instrumentierungsserver | nicht gefunden (der eine `frida`-Substring-Treffer liegt in einem Public-Suffix/TLD-Regex-Literal, unrelated) |
| `substrate`, `Substrate` | Cydia-Substrate-Hook-Framework | nicht gefunden |
| `TracerPid` | klassische `/proc/self/status`-Ptrace-Tracer-Erkennung | nicht gefunden |
| `GBWhatsApp`, `gbwhatsapp`, `com.gbwhatsapp`, `FMWhatsApp`, `YoWhatsApp`, `OGWhatsApp`, `com.wmods.wppenhacer` | benannte Mod-Client-Paketstrings | nicht gefunden |
| `modded`, `unofficial`, `tampered`, `fake whatsapp`, `clone app` | generische Mod-Erkennungs-Prose-/Log-Strings | nicht gefunden |
| `CRC32`-Verwendungen (10 Treffer) | Dex-/Asset-Selbst-Checksumme | alle im Multidex-Loading (`dextricks`) oder beim Crash-Report-ZIP-Packaging, keiner ist ein App-Tamper-Selbstcheck |
| `checkSignatures` (3 Treffer) | Signaturvergleich | alles IPC-/Caller-Trust-Checks (`FileSharingHelper`-Same-Signature-Caller-Check, ein Pixel-Companion-App-Trust-Check), unrelated zur Erkennung eines modifizierten WhatsApp-Clients |
| `isDebuggerConnected` | Anti-Debug | nur im ANR-Detektor (`SigquitBasedANRDetector`) und Crash-Helpern, kein Tamper-Gate (bestätigt `WA_CLIENT_INTEGRITY.md` §6.4) |
| `/proc/self/status` (4 Treffer, `KGi`/`KGw`/`KH8`/`KGp`) | — | Memory-Stats-Reader (wahrscheinlich `VmRSS`-Erfassung für Diagnostics); kein `TracerPid`-Parsing dort gefunden |

**Korrektur am Framing einer früheren Research-Notiz:** eine frühere statische Analysenotiz beschreibt WaEnhancer als "genau die Art von moddiertem/inoffiziellem Client, auf den das Integrity-System der Stock-App zielt", behauptet aber nicht, dass die Stock-App ihn namentlich erkennt — diese Lesart wird hier bestätigt: es existiert in 2.26.41.6 kein WaEnhancer-spezifischer, GB-spezifischer oder Xposed-spezifischer Erkennungscode. Das einzige client-seitige Signal, das bei einer WaEnhancer-Installation auslösen würde, ist die generische `is_whatsapp_plus_user`-ACRA-Probe, und nur falls das Modul (oder eine gebündelte Abhängigkeit) zufällig diese Klasse mitbringt — für WaEnhancer konkret weder bestätigt noch widerlegt (`unknown`).

Dies erweitert `WA_CLIENT_INTEGRITY.md` §6.4, die Dex-/Asset-CRC als "nicht erschöpfend durchsucht" markierte — sie ist nun durchsucht und weiterhin nicht gefunden.

---

## 4. Server-seitige Konsequenzen, die client-seitig sichtbar sind

### 4.1 WFAC-Ban-UI

`WfacBanActivity` (`com.whatsapp.waffle.wfac.p191ui`) liest drei server-seitig übergebene Extras und rendert sie; sie berechnet keinen Grund:

```java
int violationType   = getIntent().getIntExtra("ban_violation_type", -1);
String violationReason = getIntent().getStringExtra("ban_violation_reason");
int violationSource  = getIntent().getIntExtra("ban_violation_source", -1);
```

| Punkt | Tier |
|------|------|
| `ban_violation_type` / `ban_violation_source` sind opake Integer; kein Enum, das sie zu benannten Ursachen (z. B. "modifizierter Client") auflöst, wurde client-seitig gefunden | found (absence) |
| `ban_violation_reason` ist ein Freitext-String, vermutlich server-seitig templated | found |
| Kein Codepfad verbindet eines der Erkennungssignale aus §1–§3 (`is_whatsapp_plus_user`, Signatur-Mismatch, Root, Install Source) mit einem `ban_violation_*`-Wert | found (absence) |

Die vollständige Ban-State-Machine, GraphQL (`BizIntegrityQuery`), Trust-Tiers und XMPP-Fehler-Stanzas stehen in [`WA_BAN_SYSTEM_DEEP_EN.md`](WA_BAN_SYSTEM_DEEP_EN.md); dieser Report wiederholt diesen Inhalt nicht. Ob der Server eines der §1-Telemetriesignale (Signatur-Mismatch, `is_whatsapp_plus_user`, Root) als Ban-Input nutzt, ist **unknown** — das ist server-seitig und statisch nicht beobachtbar, dieselbe Schlussfolgerung wie `WA_CLIENT_INTEGRITY.md` §13.

### 4.2 Feature-Gating

Es wurde kein client-seitiger Branch gefunden, der ein Feature aufgrund der Signale aus §1 deaktiviert. Das einzige "Gating", das irgendwo in der Integrity-/Mod-Angriffsfläche beobachtet wurde, ist die Drosselung der Attestation-/Token-Requests selbst (ab-props, im Integrity-Report dokumentiert) — keine Reaktion auf eine erkannte Mod.

---

## 5. Angriffsfläche: Was ein Hook-Modul angreift (WaEnhancer, `com.wmods.wppenhacer`)

Dieser Abschnitt beschreibt die andere Seite der Grenze — was ein repräsentatives Xposed/LSPosed-Modul innerhalb des Host-Prozesses hookt — um zu zeigen, was die (weitgehend fehlende) client-seitige Erkennung abdecken müsste. Evidenzquelle: Artefakte, die eine mit WaEnhancer modifizierte Installation in einem aufgezeichneten `wa-data-root/`-Testverzeichnis hinterlassen hat (`Protocols/waenhancer-mod/info.md`), keine statische Analyse der eigenen APK von WhatsApp. Tiers wie dort erfasst.

| Fähigkeit | Mechanismus | Tier |
|------------|-----------|------|
| Delivery | Xposed/LSPosed-Modul, das **innerhalb** des `com.whatsapp`-Prozesses läuft (keine separate App, kein Repack) | found |
| Obfuskations-Handling | Laufzeit-"Unobfuscator": löst WhatsApps obfuskierte Klassen-/Methodennamen beim Modulstart auf und cacht aufgelöste Handles (`UnobfuscatorCache.xml`, `UnobfuscatorCacheStrings.xml`), verknüpft mit WhatsApps eigenem Versionsnamen, sodass der Cache bei jedem Update auf beiden Seiten invalidiert | found |
| Presence-Verschleierung ("Ghost Mode") | Hookt Presence-bezogene Methoden; Einstellung gespeichert in `WaGlobal.xml` (`ghostmode`) | found (artifact) |
| Anti-Revoke / Anti-Read-Receipt | Fängt Delete-for-everyone- und Read-Receipt-Codepfade ab; hält Schattenkopien in eigenen Stores (`com_waenhancer_message_history.db`, und eine Room-gestützte `MessageHistory.db` — WhatsApp selbst nutzt kein Room für Nachrichtenspeicherung) | found |
| Rohe Protokollsichtbarkeit | `StanzaLogger.logStanza(...)` schreibt ausgehende/eingehende XMPP-Stanzas in eine Klartextdatei (`wae_stanzas.txt`) — d. h. das Modul zapft den eigenen Stanza-Send/Receive-Pfad des Clients an, nachdem die Noise-/E2E-Schicht bereits entschlüsselt hat | found |
| Hook-Buchführung | Lauf-Diagnostics pro Ausführung, die eine Hook-Anzahl loggen (`devtrace_logs/*.jsonl`, `eventType:"hook_config_loaded"`, `payload.hookCount`) | found |
| Scope-Grenze | Hookt nur die Java-/UI-Schicht; ersetzt offenbar nicht die native Kryptografie oder den Noise-/chatd-Transport (Axolotl/Signal-Store, Post-Quantum-Prekeys, Keystore, OHAI/OPAQUE/WAFFLE-Natives unberührt) | inferred |

Zusammen mit §3 gelesen: der Stock-Client hat keinen Code, der geladene Xposed/LSPosed-Module enumeriert, den eigenen Prozessspeicher nach Hook-Trampolinen scannt oder `TracerPid`/`/proc/self/maps` auf injizierte Libraries prüft. Das Einzige, das zwischen dieser Angriffsfläche und einer Erkennung steht, ist die eine generische `is_whatsapp_plus_user`-Class-Probe (§2), die auf eine Crash-Reporting-Library zielt, nicht auf ein Hook-Framework.

---

## 6. Fehlerfälle / Fallstricke

| Symptom | Ursache | Hinweis |
|---------|-------|------|
| `is_whatsapp_plus_user = true` in `wam_daily` ohne weiteren Client-Effekt | `org.acra.ACRA` auf dem Classpath auflösbar | nur Telemetrie, by design |
| `diagnostic` enthält `nw-wap` / `NW-WAP-1` in Contact-us oder Debug-Reports | dieselbe ACRA-Probe, andere Senke | Support-Flow-Text, kein Gate |
| Kein WFAC-Ban-Screen-Grund über einen numerischen Code hinaus | `ban_violation_type`/`ban_violation_source` haben kein client-seitiges Enum | server-gesteuert, statisch nicht aufzulösen |
| Suche nach "Xposed"/"Frida" liefert nichts | korrekt — dieser Build enthält keine Hook-Framework-Erkennung | keine Dekompilierungslücke für diese konkreten Strings (vollständige Baum-Suche) |
| Eine WaEnhancer-Installation ändert Nachrichten-/Read-Receipt-Verhalten ohne jegliches WhatsApp-seitiges Log | WaEnhancer hookt die Java-Schicht, bevor WhatsApps eigene Telemetrie den ursprünglichen Call beobachten kann | erwartet angesichts des Scopes von §5 |

---

## 7. Wichtige Unterscheidungen

| Nicht verwechseln | Fakt |
|-----------------|------|
| `is_whatsapp_plus_user` vs. eine Mod-Client-Allowlist | eine reflektive Probe für eine Third-Party-Library-Klasse; es existiert keine Liste von Mod-Paketnamen |
| Mod-/Tamper-Erkennung (dieser Report) vs. Account-Attestation (`WA_CLIENT_INTEGRITY.md`) | unterschiedliche Probleme: dieser Report behandelt die Erkennung eines *modifizierten Client-Binaries/Runtime*; der Integrity-Report behandelt die *Attestation eines echten Geräts/Keys* gegenüber dem Server — sie überlappen nur darin, dass beides Telemetrie ist, kein Enforcement |
| WFAC-Ban-UI (`WfacBanActivity`) vs. Ban-Entscheidungslogik | die Activity rendert server-seitig übergebene Codes/Strings; sie entscheidet oder berechnet keinen Ban-Grund |
| WaEnhancers `StanzaLogger`-Tap vs. Bruch der E2E-Verschlüsselung | das Modul liest Stanzas innerhalb des bereits entschlüsselten Client-Prozesses; es attackiert nicht die Signal-/Noise-Kryptografie selbst |
| `safety-net-attestation` / Signatur-/Install-Source-Telemetrie | diese existieren und sind in `WA_CLIENT_INTEGRITY.md` dokumentiert; dieser Report fügt keine neue Mechanik für sie hinzu, sondern stellt nur fest, dass keine von ihnen irgendetwas gated |
| "Nicht gefunden" in diesem Report | bedeutet abwesend im dekompilierten Java/Smali/Strings dieses konkreten Builds (2.26.41.6); es ist keine Aussage über server-seitige Erkennung, die statisch nicht beobachtbar ist |

---

## 8. End-to-End-Flow

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

## 9. Unbekannte

| Frage | Warum unbekannt |
|----------|-------------|
| Ob der Server `is_whatsapp_plus_user`, Signatur-Mismatch (6251), Install Source (10255) oder Root-Flags als Ban-/Trust-Score-Input nutzt | server-seitig, kein Traffic beobachtet |
| Ob `org.acra.ACRA` tatsächlich in einem aktuellen WaEnhancer-/GB-WhatsApp-Build vorhanden ist (d. h. ob die eine existierende Heuristik dort überhaupt auslösen würde) | nicht gegen einen Live-Mod-Build in diesem Durchlauf verifiziert |
| Benanntes Ban-Grund-Mapping für `ban_violation_type` / `ban_violation_source`-Werte | kein client-seitig aufgelöstes Enum; server-definiert |
| Ob native Libraries (`libwhatsapp.so`, `libwasafe.so`) irgendeine Hook-/Tamper-Erkennung über das hinaus durchführen, was `WA_CLIENT_INTEGRITY.md` bereits als abwesend fand | strippte native Libraries nicht erschöpfend für diesen Report über die String-Suche in §3 hinaus nachverfolgt |
| Server-seitiger Umgang mit einer durch WaEnhancer angezapften `wae_stanzas.txt`-artigen Sichtbarkeit (d. h. ob der Server einen gehookten Client auf Protokollebene von einem echten unterscheiden kann) | statisch nicht beobachtbar |
</content>
