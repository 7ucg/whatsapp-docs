<!-- src-sha1: 84ea5bd809c6118cf8363e58c56bee3ba607d23e -->
# WhatsApp Ban-System — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-17
**Umfang:** Ban-Flow, WFAC-Lebenszyklus, Erfassung von Spam-Signalen, GraphQL-Protokoll, Appeal-System, Suspicious-Markierung, Prävention

---

## 1. Architekturüberblick

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

**Zentrale Erkenntnis (korrigiert in 2.26.41.6):** Die Synchronisierung des Ban-Status (WFAC) ist **pull-basiert über MEX GraphQL**, aber Ban- und Warn-*Events* zum Verbindungszeitpunkt kommen über XMPP im Login-`<failure>`-Node an (reason 402/403/416/406, Abschnitt 8.1). Die SMB-Soft-Enforcement-Warnung ist eine XMPP-Business-Notification. Es wurde kein Ban-Signalling über `<stream:error>` gefunden (dieser Handler behandelt nur `code` 515/516, `conflict type="device_removed"` und `ack`-Kicks).

---

## 2. Ban-State-Lebenszyklus (WFAC)

### 2.1 Vier-Zustands-Automat

| Zustand | Wert | Bedeutung |
|-------|-------|---------|
| `UNKNOWN_IN_CLIENT` | 0 | Kein lokaler Cache (auch Fallback für jeden nicht erkannten String) |
| `CHECKPOINTED` | 1 | Weiche Einschränkung, ggf. Verifizierung erforderlich. Der Server-String `NO_APPEAL_OPENED` wird von `AbstractC38371GmM.A00` auf `CHECKPOINTED` abgebildet (neu) |
| `BANNED` | 3 | Harter Ban, Account eingeschränkt, Appeal möglich |
| `UNBANNED` | 2 | Voll funktionsfähig |

### 2.2 SharedPreferences (MainPreferences)

```
wfac_ban_state              → "BANNED" | "CHECKPOINTED" | "UNBANNED" | "UNKNOWN_IN_CLIENT"
wfac_ban_status_token       → server token for status updates (must be non-empty)
wfac_ban_violation_type     → INT (violation category)
wfac_ban_violation_reason   → STRING
wfac_ban_violation_source   → INT (intent extra 0/1/2 kept, anything else -1; stored only for launch_source 2/3; default -1 via `HLK`; category names for 0/1/2 not found in 2.26.41.6, so the earlier SPAM/PHISHING/UNDERAGE mapping stays unverified)
wfac_last_ban_status_fetch_timestamp_ms → LONG (throttle, new)
```

Prefs-Wrapper: `HLK` (der State-Getter parst über `C36188FnW.A00`: ein ungültiger String wirft "Invalid BanState"). ViewModel: `C36188FnW` (WfacBanViewModel).

### 2.3 Ablauf der Zustandsübergänge

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

### 2.4 Ban-Reset-Sequenz

Bei erfolgreichem Appeal oder Freigabe des Accounts (`WfacBanViewModel.A0x` / `C36188FnW`, resetRegistration):
1. Löscht: `wfac_ban_state`, `wfac_ban_status_token`, `wfac_ban_violation_*`, `wfac_last_ban_status_fetch_timestamp_ms`, `support_ban_appeal_user_banned_from_chat_disconnect` (neu)
2. Meldet den Nutzer ab (finishAffinity)
3. Leitet zum Login-Bildschirm um

---

## 3. BizIntegrityQuery — GraphQL-Protokoll

### 3.1 Technische Details

| Parameter | Wert |
|-----------|-------|
| Query-Name | `BizIntegrityQuery` |
| doc_id | `28596420510007620` (geändert; war `25975613018777537`, rotiert in 2.26.38.10, bestätigt im persist-id-Katalog von 2.26.41.6; client_doc_id `14769534217004148908396994706`) |
| Schema | `whatsapp-android-mex` |
| Transport | MEX HTTP/2 POST → `/mex/query` |
| JID-Format | `<shortNum>@lid` (z. B. `1910@lid`) |

### 3.2 Request

2.26.41.6 (found, `BizIntegritySignalsGraphQLFetcher.A00`): Input-Objekt `input { query_input: [ {jid, privacy_token{tctoken, timestamp}?} ], telemetry{context:"INTERACTIVE"} }`, Ergebnisklasse `C48528LIw`. `privacy_token` wird nur hinzugefügt, wenn ein Gate (`MZ4.A00`) zutrifft und ein gespeicherter TC-Token existiert. Response (found, `C51015Mjl`): Root `xwa2_fetch_wa_users[]`, pro Nutzer `integrity_signals_info` mit `dhash`, `fb_linked_page_number_of_likes`, `ig_linked_age_number_of_followers` (sic, literaler Key), `is_banned`, `is_suspicious`, `is_suspicious_start_chat`, `join_date_ms` (String, wird zu long geparst), `phone_country_code`, `trust_tier` (Enum `M5B`), `is_mv_subscribed` (gespeichert als `is_meta_verified`), `meta_verified_info{mv_friction_eligibility}`, `integrity_tags[]{tag, pipeline_date_ms, dates_ms[]}`, `hide_safety_tools_for_business`, `fmx_business_holdout_group`. Die folgende Feldliste ist die Rekonstruktion aus 2.26.26.4 (inferred, nicht erneut verifiziert; die Form der Request-Variablen `$userJids` weicht von der Input-Form in 2.26.41.6 ab):

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

### 3.3 Response-DTO — `BizIntegritySignals` (`C51530MtC`; war C39833Hhl in 2.26.26.4)

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

### 3.4 IntegrityTags-DTO

(`C51222Mno` Liste von `C51359MqA`; Serialisierung in `LwI`, Form unverändert)

```
IntegrityTagInfo {
  tag         → String
  pipelineDS  → Date (originally Long ms)
  taggedDates → List<Date>
}
```

**JSON-Format in der DB:**
```json
[
  {
    "tag": "automation_bulk_messaging",
    "pipelineDS": 1700000000000,
    "taggedDates": [1699000000000, 1699500000000]
  }
]
```

### 3.5 Trigger-Events

| Trigger | Usecase-String |
|---------|---------------|
| Öffnen eines Chats | `"START_CHAT_CONTEXT"` (primärer Trigger) |
| Nach dem Senden einer Nachricht | Post-Send-Hook |
| App-Start / Login | Background-Scheduler |

### 3.6 Feature Flags

| Flag-ID | Funktion |
|---------|---------|
| 11061 | Trigger für die Erkennung verdächtiger Accounts (`N5r.A03`; vorhanden; wird nur für Kontakte ausgewertet, deren Verified-Name-Level mit `ent:` beginnt) |
| 11064 | Berechtigung für Start-Chat-Trust-Signal (an/aus) (`BizIntegritySignalsManager.A04`; vorhanden; Default false) |
| 11065 | Cache-TTL der Trust-Signale in Sekunden (`C51855N0t.A00`; Default 86400, found in `C08J`) |
| 12709 | Berechtigung für Kontakte, deren Business `hostStorage == 2` hat (`C197628ax.A06`); Default false (vorhanden) |
| 16349 | Forced-Query-Pfad in `BizIntegritySignalsManager.A04` (vorhanden; Default false) |
| 19793 | Neu in dieser Tabelle: `N5r.A02`, steuert die Wiederverwendung gespeicherter Signale in `C51855N0t.A02`; Zweck aus der Verwendung inferred; Default false |
| 12840 | JSON-Config nach Violation-Typ, Default `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}` (`C08J`); Consumer nicht lokalisiert; Zweck inferred aus den Key-Namen (`max_dismiss_count`, `max_display_days`) und aus den Typ-Strings des SMB-Soft-Enforcement-Banners (7.4) |
| 19893 | Logging der FMX-Card-Systemnachricht (vorhanden, `C198788cr`) |
| 26697 | BizIntegrity v2 (vorhanden, `C34735F5e`) |
| 27269 | Getrennte Zählung eingehender/ausgehender Nachrichten (vorhanden) |
| 34166 | Injection-ID, kein Feature-Flag (siehe WA_AB_PROPS.md); vom `start_chat_trust_signals`-Writer (`ContactInfoActivity`) genutzt |

In-Memory-Cache in `BizIntegritySignalsManager.A02`: Einträge 60000 ms gültig (found).

---

## 4. Suspicious-Markierung — Wann, Warum, Wie, Prävention (erneut geprüft in 2.26.41.6; nicht auffindbare Punkte sind an Ort und Stelle markiert)

> **Kernerkenntnis:** Für die BizIntegrity-Flags (`is_suspicious`, `trust_tier`, `is_banned`) berechnet der Client nichts: Sie werden aus der GraphQL-Response (`C51015Mjl`) geparst und nur dargestellt. Es wurde kein clientseitiger Schwellenwert und kein Scoring dafür gefunden. Unabhängig davon erzeugt ein On-Device-Modell lokale Scam-Verdicts (`odml_scam_alert_*`, 6.6, 7.6). Der BizIntegrity-Request enthält nur die abgefragten JIDs, einen optionalen Privacy-Token und einen Telemetrie-Kontext (3.2); dass der Client seine lokalen Metriken anderweitig hochlädt, ist nicht found.

### 4.1 Wer entscheidet?

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

Im Client existiert kein Pfeil von den lokalen Metriken in den BizIntegrity-Request (3.2). Welche serverseitigen Signale das Verdict erzeugen, ist aus der APK nicht ersichtlich (serverseitiges ML ist inferred). Der Client hat für die BizIntegrity-Flags **keinen lokalen Schwellenwert** wie "mehr als X Nachrichten -> suspicious".

---

### 4.2 Trust-Tier-Hierarchie (vom Server vergeben)

Found in der WhatsApp-APK als kompiliertes Enum (`M5B` in 2.26.41.6; Werte unverändert):

| Tier | Bedeutung | Auswirkung |
|------|---------|--------|
| `SUSPICIOUS` | Höchstes Risiko — aktiv markiert | Alle Warnungen aktiv, UI-Friction, möglicher Send-Block |
| `TIER_0` | Niedrigste legitime Stufe (neue Accounts) | Erhöhte Friction-Eligibility |
| `TIER_1` | Standardnutzer | Normal |
| `TIER_2` | Erhöhtes Vertrauen | Weniger Friction |
| `TIER_3` | Höchstes legitimes Vertrauen | Minimale Friction |
| `UNTIERED` | Keine Bewertung | Keine Prüfung angewendet |
| `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` | Unbekannt | Fallback |

**Prüfung auf Code-Ebene** (`BizIntegritySignalsManager`):
```java
"SUSPICIOUS".equals(trustTier)  // → triggers UI flow
```

### 4.3 Signale rund um das Verdict

Der Client hängt die folgenden Datenpunkte nicht an den BizIntegrity-Request (3.2). Die Tabelle listet, wo jeder im Client auftaucht; ob der Server ihn auswertet, ist inferred. Die Spalte "Risk weight" des früheren Reports hatte keinen clientseitigen Beleg und entfällt.

| Signal | Wo es im Client auftaucht (2.26.41.6) | Rolle |
|--------|---------------------------------------------|------|
| `isCountryMismatch` | On-Device-Feature (`integrityai.impl.InputFeatureProviderImpl`, Flag 31535) | Eingabe des On-Device-Modells, nicht des Requests |
| `mostRecentSenderScore` | On-Device-Feature (Flag 31536) | Dasselbe |
| `dhash` | Response-Feld, unverändert gespeichert | Vom Server gelieferter opaker String; kein Client-Code bildet ihn (Bedeutung unknown; die frühere Lesart "Device-Fingerprint" ist inferred) |
| `join_date_ms`, `phone_country_code` | Response-Felder | Gespeichert; kein clientseitiger Schwellenwert |
| FB/IG-Zähler | Response-Felder (`fb_linked_page_number_of_likes`, `ig_linked_age_number_of_followers`) | Angezeigt auf der FMX-Card (7.5) |
| `integrity_tags` | Response-Feld `{tag, pipeline_date_ms, dates_ms[]}` | Als JSON gespeichert; Tag-Werte sind für den Client opak |
| Privacy-Token | Request-Feld `privacy_token{tctoken, timestamp}` | Optional, nur wenn Gate `MZ4.A00` zutrifft und ein TC-Token gespeichert ist |
| Nachrichtenvolumen | lokales Zählen (`N54`, 6.2) | Upload zum Server nicht found |
| Broadcast-Limit | Flag 20278 Default `{"max_messages": 10000, "farthest_time_days": 30}` | Consumer nicht lokalisiert (6.3) |

`isCountryMismatch` und `mostRecentSenderScore` sind die beiden konkreten ML-Features, die im Client gefunden wurden (`com.whatsapp.integrityai.impl.InputFeatureProviderImpl`, 2.26.41.6). Flag 31535 liefert isCountryMismatch, 31536 mostRecentSenderScore (found).

---

### 4.4 Wann wird die GraphQL-Prüfung ausgelöst?

**Eligibility-Gate** (found, `BizIntegritySignalsManager.A04`; die abgefragte JID ist das Chat-Gegenüber):
1. Feature Flag **11064** aktiviert (Default false)
2. Die JID gehört nicht zu den zwei ausgeschlossenen Typen (`AbstractC24760wu.A03/A04`: Bot-JIDs und eine feste Telefonnummern-JID)
3. Eines von: der Kontakt ist ein SMB-Business (`N5r.A06`, Verified-Name-Level beginnt mit `smb:`), oder Flag **12709** ist an und der Business-`hostStorage` des Kontakts ist `== 2` (`C197628ax.A06`), oder (Forced-Call, `A09`) Flag **16349** an und `N5r.A04/A06` gilt (`A04` = `!A01 && !SMB && !ENT`; die Semantik des Helpers `N5r.A01` wurde nicht aufgelöst, daher ist offen, welche Nicht-Business-JIDs dies zulässt)
4. Für den nicht erzwungenen Pfad: Cache abgelaufen oder kein lokaler Cache (`C51855N0t`)

Korrektur gegenüber dem früheren Report: In 2.26.41.6 überspringt das reguläre Gate Business-Accounts nicht, es wählt sie aus (SMB oder gehostet); der erzwungene Pfad (16349) kann weitere JIDs zulassen. Der JADX-Flow von `A04` ist teilweise umstrukturiert, daher stammt diese Lesart aus der dekompilierten Form plus den Helper-Bodies, nicht aus smali.

**Cache-TTL:** Feature Flag **11065** in Sekunden, Default **86400 (24 Stunden)** (found, `C08J`)
```java
long timeout_ms = TimeUnit.SECONDS.toMillis(remoteConfigValue(11065));
if (current_time - lastSyncTs > timeout_ms) {   // C51855N0t.A00
    // cache expired -> new GraphQL call required
}
```

**Batch-Größe:** Im GraphQL-Fetch-Pfad existiert kein 975-JID-Chunking (`BizIntegritySignalsManager.A03` reicht die JID-Liste unverändert weiter). Die Konstante 975 gehört zum lokalen SQL-Batching der Nachrichtenzählung (6.2).

---

### 4.5 Bekannte integrity_tag-Werte

Die Strings `automation_bulk_messaging` und `spam` sind in `C35896FgX` und `ViewOnClickListenerC39711HTl` found, werden dort aber mit dem `type` der SMB-Soft-Enforcement-Notification (`HAR.A07`, siehe 7.4) verglichen, nicht mit `integrity_tags` aus der BizIntegrity-Response. Sie erscheinen außerdem als Key des Defaults von Flag 12840. Der Client zählt `integrity_tags`-Werte überhaupt nicht auf; die JSON-Blobs werden opak gespeichert. `business_policy_violation` kommt in java_src, smali, assets oder res von 2.26.41.6 nirgends als String vor.

| Tag | Bedeutung |
|-----|---------|
| `automation_bulk_messaging` | Typ der Soft-Enforcement-Notification (Bulk-/automatisiertes Senden); nicht als `integrity_tags`-Wert belegt |
| `spam` | Typ der Soft-Enforcement-Notification (Spam) |

---

### 4.6 Was konkret zu suspicious führt — aus dem Code inferred

Erneut geprüft in 2.26.41.6: Der Client enthält weder Logik noch Schwellenwert noch Gewichtung für eine der Zeilen unten, und der BizIntegrity-Request trägt keine dieser Metriken (3.2). Die gesamte Tabelle bleibt **inferred** (eine Vermutung über serverseitiges Verhalten anhand der im Client vorhandenen Signale). Die Zeile "Neuer Account (< 24h)" hat keinen Beleg: Im Client existiert keine Prüfung des Account-Alters (siehe 4.9 D).

| Verhalten | Warum riskant | Gewicht |
|----------|---------------|--------|
| Hohe ausgehende vs. eingehende Nachrichten (nur senden, keine Antworten) | Bulk-Outreach-Muster | Sehr hoch |
| Telefon-Land ≠ IP-Land | `isCountryMismatch = 1.0` | Sehr hoch |
| Gleicher dhash auf mehreren Accounts | Device-Ban-Trigger | Sehr hoch |
| Broadcast > 10,000 Empfänger / 30 Tage | Hartes Limit, sofortige Markierung | Hoch |
| Hoher `mostRecentSenderScore` (Empfänger melden) | ML-Feedback-Loop | Hoch |
| Neuer Account (< 24h, keine Kontakte) | Geringe Glaubwürdigkeit (keine clientseitige Altersprüfung found) | Hoch |
| Kein FB/IG-Link + hohe Outbound-Rate | Fehlender Social Proof | Mittel |
| Vorhandene integrity_tags | Wirkung früherer Verstöße | Mittel–Hoch |
| `is_reach_out = 1` + viele unbekannte Chats starten | Cold-Contact-Muster | Mittel |

### 4.7 SpamWarning-Reason-Codes (Warnung vor dem Ban)

Unverändert in 2.26.41.6 (`SpamWarningActivity`: Default-Reason 100, Expiry-Default -1; Switch auf 101, 102, 103, 104, 106, Default deckt 105/andere ab).

Zugestellt über das Intent-Extra `spam_warning_reason_key`, gesetzt aus dem Attribut `code` (>= 100) des XMPP-Login-`<failure reason="402">` zusammen mit `expire`, `message`, `url` (found, `C0ZH.handleMessage` Typ 2; siehe 8.1):

| Code | Trigger | Countdown? |
|------|---------|-----------|
| 101 | Spam-Aktivität erkannt | Ja |
| 102 | Forwarding-Verstoß | Ja |
| 103 | Status-Spam | Ja |
| 104 | Bot-Forwarding | Ja |
| 105 | Allgemein / Default | Permanent, wenn expiry = -1 |
| 106 | Sonstiger Verstoß | Ja |
| default | Unbekannter Verstoß | Permanent, wenn expiry = -1, sonst Countdown |

`expiry_in_seconds == -1` + online: sofortiges Beenden (der Server hat die Warnung aufgehoben).

### 4.8 SpamFlow-Kategorien mit Bezug zur Suspicious-Markierung

97 Kategorien in der APK (found: `C9E2`, Array mit 96 Einträgen plus `1_1_spam_banner_report` als letztem Eintrag, Indizes 0 bis 96; die frühere Zahl 92 und die Indizes in der Tabelle sind überholt). Die Liste wird namentlich im SMAX-Node `spam_list` serialisiert (Attribut `spam_flow` pro Eintrag, optionale `wi_trace_id` mit 24 Zeichen), der Index ist also nur die Position im Client-Array, kein Wire-Wert. Neu: `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_suspicious_banner_block/_trust`, `odml_scam_alert_fmx_card_block/_trust`, `biz_spam_banner_block`, `1_1_spam_banner_block`, `chat_fmx_card_block`, `group_spam_banner_report`, `left_group_spam_banner_report`. Direkt mit dem Suspicious-Zustand verknüpft sind:

| Index | Kategorie | Bedeutung |
|-------|----------|---------|
| 23 | `chat_fmx_card_block_server_flagged_suspicious` | Server-markiert suspicious → FMX-Block |
| 24 | `chat_fmx_card_block_suspicious` | Chat wegen Suspicious-Flag blockiert |
| 27 | `chat_fmx_card_safety_tools_block_suspicious` | Safety Tools bei suspicious angezeigt |
| 70 | `odml_scam_alert_bottom_sheet_block` | On-Device-ML-Scam → Block |
| 71 | `odml_scam_alert_bottom_sheet_trust` | On-Device-ML-Scam → Trust |
| 76 | `one_to_one_spam_banner_block_server_flagged_suspicious` | 1:1-Spam-Banner (server-markiert) |
| 85 | `trust_question_bottomsheet_block_server_flagged_suspicious` | Trust-Prompt (server-markiert) |
| 89 | `user_initiated_chat_suspicious_banner_block` | Suspicious-Banner beim Chat-Start |
| 94 | `1_1_old_spam_banner_block` | Legacy-Spam-Banner |
| 96 | `1_1_spam_banner_report` | 1:1-Spam-Report |

### 4.9 Schutzmechanismen — was der Client zeigt

Die frühere Liste der "protective factors" ist eine Server-ML-Lesart ohne clientseitigen Beleg. Was 2.26.41.6 tatsächlich enthält:

#### A) Business-Status
Kein Skip. Das reguläre Eligibility-Gate wählt SMB-Kontakte aus (und Kontakte mit `hostStorage == 2` unter Flag 12709), siehe 4.4. Flag 2923 (früher: "non-business validation toggle") wurde nicht lokalisiert: In java_src oder smali von 2.26.41.6 existiert weder eine Flag-Prüfung mit dieser ID noch ein Config-Default dafür.

#### B) Meta Verified (mvFrictionEligibility)
Response-Feld `meta_verified_info.mv_friction_eligibility` (found, `C51015Mjl`), gespeichert als `mv_friction_eligibility`. `is_mv_subscribed` wird separat als `is_meta_verified` gespeichert. Die FMX-Card (`C94p`) liest das Flag und fügt bei aktivem Flag 15735 einen "learn more"-Link hinzu. Dass daraus niedrigere Friction-Schwellen resultieren, ist im Client nicht sichtbar (inferred).

#### C) Verknüpfte Social Accounts (FB/IG)
`fb_linked_page_number_of_likes` und `ig_linked_age_number_of_followers` werden als Integer geparst (`optInt`) und auf der FMX-Card angezeigt (7.5). Es sind Zähler, keine Booleans (found). Dass der Server sie als schützend gewichtet, ist inferred.

#### D) Karenzzeit nach Account-Alter
Nicht found. Der einzige altersähnliche Vergleich ist die Cache-TTL auf `last_sync_ts` gegen Flag 11065 (4.4). `join_date_ms` wird gespeichert, aber im Client existiert keine Grace-Window-Logik.

#### E) Whitelist / Validierungsliste (Flag 12709)
Geändert: Die Prüfung `C197628ax.A06(userJid)` ist `hostStorage == 2` im Verified-Name-Record des Kontakts (`AnonymousClass119`), eine lokale Eigenschaft, keine serverseitige Vorabfreigabeliste. Sie macht den Kontakt für die Abfrage berechtigt; sie kehrt nicht vorzeitig zurück.

#### F) hideSafetyToolsForBusiness (Feld aus der Response)
Response-Feld `hide_safety_tools_for_business`, gespeichert in `hide_safety_tools_for_business`. Die Auswirkung auf die UI wurde nicht erneut verfolgt; die frühere Aussage, es blende nur die Warn-UI aus und ändere den Suspicious-Status nicht, ist unverifiziert.

---

### 4.10 Prävention — was der Code verrät

Dieser Teil ist aus den obigen Feldern abgeleiteter Rat. Der Client enthält keine Logik, die davon etwas bestätigt; jeder Punkt gilt als **inferred**, außer wo found vermerkt ist.

**Verhalten (inferred):**
- Das Verhältnis ausgehend/eingehend ausgewogen halten
- Länder-Mismatch zwischen Nummer und Netzwerk vermeiden (der Client speist `isCountryMismatch` in das On-Device-Modell ein, found; serverseitige Nutzung inferred)
- Unter der Broadcast-Config von Flag 20278 bleiben (10,000 Nachrichten / 30 Tage; Consumer nicht lokalisiert)

**Account-Qualität (inferred):**
- Verknüpfte FB/IG-Zähler und Meta Verified werden vom Client angezeigt oder gespeichert (found); ihre Wirkung auf das Verdict ist inferred
- Ein Neuaccount-Fenster (24h) und dhash-Blacklisting werden von keinem Client-Code gestützt (siehe 4.9 D und 4.3)

**Technisch (found):**
- `privacy_token` (TC-Token) wird dem BizIntegrity-Request nur hinzugefügt, wenn Gate `MZ4.A00` zutrifft und ein TC-Token gespeichert ist

**Timing (found):**
- Gecachte Signale werden wiederverwendet, bis `last_sync_ts` älter als Flag 11065 ist (Default 86400 s); der Manager hält zusätzlich einen 60000-ms-Memory-Eintrag
- Signale bleiben in `wa_biz_integrity_signals` bestehen, bis eine neue Response sie überschreibt

---

## 5. Lokale SQLite-Datenbanken

### 5.1 `wa.db` — `wa_biz_integrity_signals`

2.26.41.6 (found, `C53116Nmn`, 17 Spalten inkl. `_id`): ergänzt `is_meta_verified` und `fmx_business_holdout_group`; `fb_linked_page_number_of_likes`, `ig_linked_page_number_of_followers`, `join_date_ms`, `last_sync_ts` sind REAL, `mv_friction_eligibility` und `is_meta_verified` haben keinen angegebenen Default. Unique Indexes `biz_integrity_signals_jid_index`, `biz_integrity_signals_chat_row_id_index`; Trigger `contact_bd_for_business_integrity_signals` (BEFORE DELETE ON wa_contacts). Store: `LwI` (Labels `QUERY_BIZ_INTEGRITY_SIGNALS_BY_JID` / `_BY_ROW_ID`, `BizIntegritySignalsStore/saveBusinessIntegritySignals`). Das Schema unten ist die Version aus 2.26.26.4.

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

Writer/Reader: `LwI` (Store), `BizIntegritySignalsManager.A06(UserJid)` liest die In-Memory-`ConcurrentHashMap` (found: `A06` liest die In-Memory-Map, `A07` liest sie mit Lazy-DB-Load, `A0A` führt Upsert aus und persistiert; die Namen `A08`/`A01` aus 2.26.26.4 sind weg)

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

Reader: `C57342Yp` (`SELECT * ... QUERY_START_CHAT_TRUST_SIGNALS_BY_JID`; war C2M7.A0K) → gibt das Tupel `(is_sender_new_account, is_sender_suspicious)` zurück

### 5.3 `msgstore.db` — `integrity_chat_info`

```sql
CREATE TABLE integrity_chat_info (
  chat_row_id                        LONG PRIMARY KEY,
  is_reach_out                       INTEGER,  -- 1 = unknown contact initiated
  is_eligible_for_link_friction_banner INTEGER
);
```

Query-Label: `"GET_INTEGRITY_CHAT_INFO"` (Batch-Query mit `chat_row_id IN (...)`), Store `C33O`, Schema `C08970Ox` (Index `integrity_chat_info_chat_row_id_index`, Trigger `chat_bd_for_integrity_chat_info_trigger` BEFORE DELETE ON chat). Unverändert.

### 5.4 `wa.db` — `wa_biz_integrity_chat_settings`

Found in 2.26.41.6: Schema `AHY` (Spalten `jid`, `last_delivered_sort_id` LONG, `last_read_sort_id` LONG), Unique Index `biz_integrity_chat_settings_index` auf `jid`, Trigger `contact_bd_for_biz_integrity_chat_settings` (BEFORE DELETE ON wa_contacts). Rolle unknown.

---

## 6. Erfassung von Spam-Signalen (Client-seitig)

(Erneut geprüft in 2.26.41.6; nicht auffindbare Punkte sind an Ort und Stelle markiert.)

### 6.1 dhash

`dhash` ist ein String in der BizIntegrity-Response (`integrity_signals_info.dhash`), im Klartext in `wa_biz_integrity_signals.dhash` gespeichert. Kein Client-Code bildet ihn: Es wurde keine Eingabe aus Gerätemodell, OS, App-Version, Nummer, Zeitzone, Android ID oder Build-Fingerprint gefunden, und nichts lädt eine solche hoch. Die frühere Beschreibung "Device-Fingerprint / serverseitige Blacklist" ist nicht belegt; die Bedeutung ist unknown. Andere `dhash`-Strings in der APK (Blocklist, Business-Opt-out) sind nicht verwandte Verzeichnis-Hashes.

---

### 6.2 Message Velocity

Found: `com.whatsapp.bizintegrity.logger.receiver.handler` (`C0236xdea74a22`, Helper `N54`) zählt Nachrichten lokal über eine Zeitspanne für eine Liste von JIDs, mit SQL-Aliasen:
- `incoming_count`: Nachrichten mit `from_me = 0`
- `incoming_threads_count`: eindeutige `chat_row_id` für empfangene Nachrichten
- `outgoing_count`: Nachrichten mit `from_me = 1`
- `outgoing_threads_count`: eindeutige `chat_row_id` für gesendete Nachrichten
- Anzahl gelöschter Nachrichten: `messages_count_after_privacy_token` (auch `messages_count`, `outgoing_messages_count`) aus `integrity_deleted_chat_message_count`

Feature Flag 27269 steuert, ob eingehend/ausgehend getrennt oder als kombinierte Summe gezählt wird (found im selben Handler).
Batch-Größe: **975 JIDs** pro SQL-Verarbeitungsaufruf (found: `C20H.A1A(list, 975)`, ein Chunk gemäß SQLite-Variablenlimit, kein Netzwerk-Batch).
Nicht lokalisiert: tägliches/stündliches Binning, Rate pro Kontakt; wohin die Zählwerte nach dem Zählen gehen, wurde nicht verfolgt.

---

### 6.3 Broadcast-Limits (Business-Accounts)

Feature-Config 20278: `{"max_messages": 10000, "farthest_time_days": 30}` (found als Default in `C08J`/`C09W`).
- Das Limit von 10,000 Nachrichten pro 30 Tage ist der Config-Default; der Consumer dieses JSON (der Code, der es vor dem Senden durchsetzt, `renewal_date`, Throttling pro Empfänger, Klassifizierung Marketing vs. regulär) wurde nicht lokalisiert: Die Key-Strings `max_messages`/`farthest_time_days` kommen nur in den Default-Tabellen vor und `renewal_date` kommt in java_src nicht vor.

---

### 6.4 GAP Enforcement (Global Abuse Prevention)

Found: `com.whatsapp.gapenforcement.triggers.GapEnforcementTrigger.A03` (`onMarketingMessageReceived`) wird übersprungen, wenn Feature Flag 14837 aus ist, und speichert `LAST_MARKETING_MESSAGE_TIMESTAMP` in SharedPreferences (`C67902uK`), wenn eine neuere Marketing-Nachricht eintrifft. Flag 25631 steuert einen weiteren Trigger-Pfad. Die Auflösung "Global Abuse Prevention" steht nicht im Code (Benennung unverifiziert).

Verfolgter Zustand (`ChatDescription`, found):
- `isEnterpriseBusiness` (Boolean)
- `isMarketingMessageThread` (Boolean)
- `sortTimestamp` (Long)
- `chatJid` (UserJid)

---

### 6.5 WaFA (Federated Analytics)

Found: Package `com.whatsapp.federatedanalytics.impl` (`WaFaConfigFetcher`, `WaFaReportScheduler`, `FaReportRunner`, `WaFaReportSubmitter`, `FaTeeConnection`, `FaTeeAcsRepository`, `FaAcsWarmer`). Reports laufen über eine TEE-Verbindung, authentifiziert mit ACS (Header `x-acs-token`, `x-acs-configid`, `x-acs-project-name`; OHAI-Public-Key-Fetch). Nächster Ausführungszeitpunkt in Pref `fa_next_report_run_timestamp`.
Nicht lokalisiert: der Inhalt der Reports. Die Metrikliste des früheren Reports (Feature-Adoption, Crashes, Latenz, RAM/Storage/OS, Geofencing, Session-Daten, Verbindungstyp) wurde nicht als Code gefunden; der Report-Inhalt ist config-gesteuert und daher aus dem Client nicht lesbar.

---

### 6.6 ML-Feature-Extraktion (On-Device-Scam-Erkennung)

Zwei konkrete Features im dekompilierten Client gefunden:
- `isCountryMismatch` (float 0.0/1.0): Land des Senders ≠ Land des Empfängers → **HIGH RISK**
- `mostRecentSenderScore` (float): ML-Reputationsscore für den Sender

Feature Flags 31535/31536 steuern ihre Werte (found). Ergebnisse werden zum Server für sekundäres ML-Scoring gesendet (inferred).

---

## 7. UI-Komponenten: Suspicious, Warnungen, Ban

(Erneut geprüft in 2.26.41.6: `SpamWarningActivity` jetzt `com.whatsapp.userban.spamwarning`, `SuspiciousFmxBottomSheetFragment` `com.whatsapp.fmx` plus neue Subklasse `SuspiciousSmbFmxBottomSheetFragment`. Die Trigger-Bedingungen von 7.2, 7.4 und 7.5 sind unten korrigiert.)

### 7.1 SpamWarningActivity

Intent-Parameter:
- `spam_warning_reason_key` (int): Reason-Code
- `expiry_in_seconds`: Countdown (-1 = permanent)
- `spam_warning_message_key`: eigener Text
- `faq_url_key`: FAQ-Link

Reason-Codes:

| Code | Bedeutung |
|------|---------|
| 100 | Allgemeine Spam-Warnung |
| 101 | Spam-Aktivität erkannt |
| 102 | Forwarding-Verstoß |
| 103 | Status-Spam |
| 104 | Bot-Forwarding |
| 105 | Allgemein / permanent |
| 106 | Sonstige Verstöße |

Wenn `expiry_in_seconds != -1` → Countdown-Timer wird angezeigt.
Bei `-1` + online → sofortiges Beenden (der Server hat die Warnung aufgehoben).

### 7.2 Suspicious FMX Bottom Sheet (`SuspiciousFmxBottomSheetFragment`)

Found: ein Informations-Sheet ("learn more"-Links `about-blocking-reporting`, `examples-of-scams`), kein zustandsgesteuerter Blocker. Es wird durch Antippen eines Suspicious-Buttons auf der FMX-Card geöffnet (`C93z.setupSuspiciousButtons`, SMB-Variante `C94p` öffnet `SuspiciousSmbFmxBottomSheetFragment`) und von `C512928n` (SMB-Variante, wenn der Kontakt ein Business ist, `A0T()`), über die Helper `AbstractC61092ir.A00` / `AbstractC61102is.A00`.

Die vier Trigger-Bedingungen des früheren Reports (`is_suspicious == 1`, `is_suspicious_start_chat == 1`, `is_reach_out == 1`, `chat_fmx_card_block_suspicious == 1` als Send-Block) sind nicht belegt: Das Fragment selbst liest keine davon, und `chat_fmx_card_block_suspicious` ist ein SpamFlow-Kategoriename (4.8), kein gespeichertes Flag. Found ist: Der Start-Chat-Kontext wird angezeigt, wenn `is_suspicious_start_chat` true ist (`StartChatContextUtils`), und die FMX-Card berechnet `"SUSPICIOUS".equals(trust_tier)` (`C94p`).

---

### 7.3 WFAC Hard-Ban-UI

| Klasse | Funktion |
|-------|---------|
| `WfacBanActivity` | Einstiegspunkt, Ban-Info + Appeal-Button |
| `WfacBanInfoFragment` | Verstoßdetails + Appeal-Link |
| `WfacBanDecisionFragment` | Nutzeraktion (Appeal eingereicht) |
| `WfacUnbanDecisionFragment` | Bestätigung nach dem Appeal |

Trigger (geändert): `Main.A5D()` existiert nicht mehr; sein Äquivalent ist `Main.A5W()`, das `wfac_ban_state` beim Start liest (Switch auf "UNBANNED" / "BANNED" / "CHECKPOINTED", Registration State 21, Log "main/me/wfac ban") und `WfacBanActivity` über `HBC` startet. Es wurde kein SharedPreferences-Change-Listener gefunden. `wfac_ban_state` wird vom Ban-Status-Fetch-Handler und von `WfacBanActivity.onCreate` geschrieben (2.3). Der Login-Failure-Pfad (403) öffnet stattdessen die ältere `com.whatsapp.userban.ui.BanAppealActivity` (`HBB`). 2.26.41.6: Klassen jetzt in `com.whatsapp.waffle.wfac.ui` (auch `WfacBanBaseFragment`); Activity wird über den Intent-Helper `HBC` und den Screen-Übergang `I1T` (`transitionToScreen`) geöffnet.

### 7.4 SMB Soft Enforcement

Geändert: Der Trigger ist nicht `is_suspicious=true` + `integrity_tags` mit `"business_policy_violation"` (dieser String existiert in 2.26.41.6 nicht). Es ist eine XMPP-Business-Notification (Handler `AnonymousClass142`, Notification-ID 202) mit Child `biz_integrity_warning_notification > violation`:

| Attribut | Verwendung |
|-----------|-----|
| `source` | Ursprung des Verstoßes (erforderlich) |
| `type` | Verstoßtyp, z. B. `automation_bulk_messaging`, `spam` (verglichen in `C35896FgX`) |
| `severity` | z. B. ändert `"severe"` den Banner-Text (`C35896FgX`, `WABIEnforcementEducationFragment`) |
| `policy_url` | Link-Ziel (erforderlich) |
| `priority` | int >= 0 (erforderlich) |
| `status` | `active` (gespeichert, Zähler zurückgesetzt) oder `inactive` (entfernt) |

Der Client baut eine `SMBSoftEnforcementNotification` (`HAR`) mit fest auf `"warning"` gesetztem `notificationType` und `bannerNotificationTimeStamp` = Empfangszeit und persistiert ein JSON-Array unter der Preference `smb_soft_enforcement_banner-all-json-<notificationType>` (`C35894FgV`) mit den unten gezeigten Keys. Zähler pro Notification sind Int-Preferences `smb_soft_enforcement_banner-<notificationType>-<source>-<severity>-<type>-total_days|click_count|dismiss_count`.

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

Das JSON des früheren Reports (`notification_type: soft_enforcement`, `violation_type`, `education_url`, `action_required`) ist im Client nicht vorhanden. UI: `SMBSoftEnforcementEducationFragment`, `WABIEnforcementEducationFragment` in `com.whatsapp.banner.softenforcementsmb`.

---

### 7.5 FMX-Card (Trust-Signal-Card)

Found: Eine Systemnachricht vom Typ 129 (`0x81`, `C57172Xr`) wird in `C198788cr` erzeugt ("Creating FMX card system message for chat", "ContactsProcessor/added contact info message"); Flag 19893 steuert dort nur ein Analytics-Event. Der asynchrone Write nach `start_chat_trust_signals` wird durch `C1P2.A01()` gesteuert (Flag nicht aufgelöst) und läuft über `C65972r0`. Die Card (`C94p`) rendert die FB-Likes- und IG-Follower-Zähler und das Meta-Verified-Friction-Flag; `"SUSPICIOUS".equals(trust_tier)` wählt die Suspicious-Variante. Anzeige des Account-Alters und die Anzeigebedingung "Business/unbekannter Kontakt" wurden nicht lokalisiert.

---

### 7.6 ODML Scam Alert (On-Device-ML)

Herunterladbares ML-Modell über das ACS-Token `"WA_ODML"` (found in `OdmlModelDownloadClient`, `ODML_MODEL_DOWNLOAD`, ID `27301080136160169`, TTL 345600 s = 4 Tage; Cache-Größe 64 nicht lokalisiert). Vom Nutzer über `ScamDetectionSettingsActivity` ein-/ausschaltbar. Funnel wird über Session-ID / Source / Entry-Point-Intent-Extras getrackt.

---

## 8. XMPP & Stanzas (Ban-Kontext)

(Erneut geprüft in 2.26.41.6 durch Lesen der Login- und Stream-Error-Handler; Abschnitt 8.1 ist korrigiert. Eine frühere Prüfung von 2.26.35.2 sah keinen XMPP-Ban-Push; diese Beobachtung ist durch den Login-Failure-Pfad unten überholt.)

### 8.1 Login-`<failure>` trägt Bans und Warnungen

Die frühere Aussage "Bans kommen nur über MEX GraphQL" ist für Events zum Verbindungszeitpunkt falsch. `HandlerThreadC12340b0.A13` liest den Login-Result-Node; bei `<failure>` nimmt er `reason` (int) und baut eine `C45351tB`-Exception (found):

| `reason` | Typ | Gelesene Attribute | Client-Reaktion (`C0ZH.handleMessage`) |
|----------|------|-----------------|-----------------------------------------|
| 5xx | 4 | - | Serverfehler, Retry-Pfad |
| 402 | 2 (Default) | `code`, `expire`, `message`, `url`, `appeal_token`, `age_collection` | `SpamWarningActivity` mit `spam_warning_reason_key` = `code` (>= 100), `expiry_in_seconds`, Text, FAQ-URL |
| 402 + `appeal_token` + `code` 106 | 13 | gleich | `ContextualAgeCollectionActivity` (Extras `appealToken`, `expireTimeout`) |
| 402 + `appeal_token` + `code` 107 / `code` 109 | 14 / 15 | gleich | Pfad "U13 Banned PAA Pending" (Managed-Account-Prefs, Onboarding) |
| 403 | 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` | Permanenter Ban: `HGB.startPermanentBanFlow` -> `BanAppealActivity` (nach Verzögerung durch Flag 19714 in ms) |
| 405 | 3 | `t` (Sekunden) | Schreibt Pref `software_forced_expiration` |
| 406 | 5 | `code` | Pref `underage_account_banned` |
| 416 | 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` | `WfacManager.startUnderageBanFlow`; `violation_reason == "u13_checkpoint"` setzt `support_ban_appeal_user_banned_from_chat_disconnect` |
| sonstige | 0 | - | Logout (Pfad "exception-password") |

Alle Failure-Typen lesen außerdem optionale Logout-UI-Attribute: `logout_message_header`, `logout_message_subtext`, `logout_message_locale`, `logout_main_button_text`, `logout_main_button_url`, `logout_secondary_button_text`, `logout_secondary_button_url`. `location` wird für das Routing aus dem Node gelesen.

`<stream:error>` (zugehöriger Read-Interceptor, `C40601l6`): `code` 515 / 516, Child `conflict type="device_removed"` (Deregister), Child `ack` (Kick). Es wurde kein Ban-spezifisches Child gefunden. `<presence type="unavailable">` und WebSocket-Close-Codes wurden nicht untersucht.

### 8.2 XMPP-Fehler-Tokens (binäres Dictionary)

Dictionary `AbstractC40911lb` (Single-Byte `A00`, Double-Byte `A01`). Vorhandensein der Tokens aus der früheren Tabelle:

| Token-String | Im Dictionary |
|-------------|---------------|
| `stream:error` | ja |
| `conflict` | ja |
| `not-authorized` | ja |
| `item-not-found` | ja |
| `server-error` | ja |
| `401` | ja |
| `policy-violation` | nicht found |
| `403` | nicht als Token found (der `reason`-Wert 403 wird als Int-Attribut gelesen) |

Die Spalte "Meaning" des früheren Reports (z. B. `403` = "Forbidden (ban-related)") war inferred; nur die Bedeutung von 403 ist jetzt durch die obige `<failure>`-Behandlung belegt. Ebenfalls im Dictionary: `404`, `407`, `failure`, `locked`.

### 8.3 IQ-Responses für eingeschränkte Accounts

Nicht found. Weder der Namespace `urn:ietf:params:xml:ns:xmpp-stanzas` noch die Texte "Account restricted" / "User banned" existieren in java_src oder Resources von 2.26.41.6, und im Dictionary gibt es keine Tokens `forbidden` / `service-unavailable`. Die XML-Beispiele des früheren Reports sind unverifiziert und sollten nicht als verlässlich gelten (sie können illustrativ gewesen sein). Die Fehlerbehandlung pro IQ (z. B. `item-not-found`, `not-authorized`-Parser wie `K3P`, `C23205A1e`) wurde für eingeschränkte Accounts nicht verfolgt.

---

## 9. Vollständiger Datenfluss (End-to-End)

(Erneut geprüft in 2.26.41.6: doc_id `28596420510007620`, Input-Form `query_input`, Klassennamen oben. Die Pfeile `isBanned` -> `wfac_ban_state` -> `Main.A5D()` des Diagramms aus 2.26.26.4 sind entfernt, weil im Code keine solche Verbindung existiert; siehe Abschnitte 1 und 2.3.)

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

## 10. Appeal-Request (2.26.41.6)

Found in `C37414GLt`: Die `variables`-JSON des Requests trägt `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}` und `app_id` (`"dev.app.id"`); der Klartext vor der Verschlüsselung ist `{token, debug_info, description}`; Kontext-Label `"WA_INAPP_BAN_APPEALS"` (Key-Derivation-Info). Transport (found, `AbstractC40195HfH`): ein einfacher Facebook-Graph-POST an `https://<host>.facebook.com/graphql` mit `doc_id` und einem Feld `access_token`, nicht MEX. `C37414GLt` übergibt `doc_id` **38509456535312323**, wenn `hg3.A04.A00()` true ist, sonst **5473316762755318**. Der Operationsname `submitBanAppeal` kommt in java_src, smali, assets oder res von 2.26.41.6 nicht als String vor, und keine der beiden doc_ids steht im Query-Katalog des Projekts, daher ist der Name unverifiziert. Vor dem Submit parst `C40191HfD` eine erste Response mit `data.purpose_public_keys{purpose_public_ek, purpose_public_ik, purpose_public_ik_sig, purpose_dummy_ciphertext, purpose_dummy_nonce}`, die das Schlüsselmaterial für die Verschlüsselung liefert.

---

## 11. Änderungen gegenüber 2.26.26.4

| Punkt | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| BizIntegrityQuery doc_id | `25975613018777537` | `28596420510007620` (rotiert in 2.26.38.10) |
| Request-Form | `$userJids`-Liste (rekonstruiert) | `input{query_input[{jid, privacy_token{tctoken,timestamp}}], telemetry{context}}` |
| DTO-Klasse | `C39833Hhl` | `C51530MtC` (17 Felder: + `isMetaVerified`, `fmxBusinessHoldoutGroup`) |
| `wa_biz_integrity_signals` | 14 Spalten | + `is_meta_verified`, `fmx_business_holdout_group`; Zähler REAL |
| Store / Manager | `BizIntegritySignalsManager.A08/A01` | Store `LwI`, Schema `C53116Nmn`, Manager A02 60-s-Memory-Cache |
| start_chat_trust_signals-Reader | `C2M7.A0K` | `C57342Yp` |
| Trust-Tier-Enum | nicht erfasst, 7 Werte | `M5B`, dieselben 7 Werte |
| WFAC-UI-Package | `com.whatsapp.waffle.wfac` (flach) | `com.whatsapp.waffle.wfac.ui` (+ `WfacBanBaseFragment`) |
| WFAC-Prefs | 5 Keys | + `wfac_last_ban_status_fetch_timestamp_ms` (5-s-Refresh-Throttle), `support_ban_appeal_user_banned_from_chat_disconnect` wird beim Reset gelöscht |
| Ban-State-Parsing | 4 Zustände | gleich; `NO_APPEAL_OPENED` auf `CHECKPOINTED` abgebildet |
| Flags | 11061/11064/11065/12709/16349/19893/26697/27269 | alle vorhanden; + 19793 (N5r.A02) |
| SpamWarning-Codes 100-106 | ja | unverändert |
| integrity_tags | `automation_bulk_messaging`, `spam` | unverändert |
| SpamFlow | 92 Kategorien | 97; `odml_scam_alert_*`, `biz_spam_banner_block`, weitere ergänzt |
| ML-Features | `isCountryMismatch`, `mostRecentSenderScore` (31535/31536) | unverändert, in `integrityai.impl.InputFeatureProviderImpl` |
| Broadcast-Limit 20278 | 10000 / 30 Tage | unverändert |
| Ban-/Warn-Events zum Verbindungszeitpunkt | "no XMPP ban signalling" | XMPP-Login-`<failure>`: reason 402 (SpamWarning / U13), 403 (perm ban -> `BanAppealActivity`), 405, 406, 416 (WFAC underage); `C45351tB`, `C0ZH` |
| `Main.A5D()` | reagiert auf Änderung von `wfac_ban_state` | weg; `Main.A5W()` liest den State beim Start (Reg State 21) und öffnet `WfacBanActivity` über `HBC` |
| `wfac_ban_state`-Writer | nicht erfasst | Ban-Status-Fetch-Handler `C40191HfD`; `WfacBanActivity.onCreate` (CHECKPOINTED / BANNED / UNBANNED nach Launch Source); keine Verbindung von `is_banned` |
| BizIntegrity-Eligibility | "business accounts skip the check" | wählt SMB-Kontakte (`smb:`-Level) oder `hostStorage == 2` (12709); Forced-Pfad 16349; kein 975-JID-Chunking im Fetch |
| 975-Batch | GraphQL-Batch | lokaler SQL-Chunk der Nachrichtenzählung (`N54`) |
| Flag 12709 | serverseitige Whitelist | lokale Prüfung `hostStorage == 2` |
| Flag 2923, 24h-Account-Alters-Karenz, `dhash`-Bildung | behauptet | in 2.26.41.6 nicht found |
| `integrity_tags`-Werte | `automation_bulk_messaging`, `spam` | diese Strings sind `type`-Werte der SMB-Soft-Enforcement-Notification, keine `integrity_tags` |
| SMB Soft Enforcement | Tag `business_policy_violation` + JSON `notification_type`/`education_url` | XMPP `biz_integrity_warning_notification > violation{source,type,severity,policy_url,priority,status}`; gespeicherte JSON-Keys `source,type,severity,notificationType,policyUrl,status,bannerNotificationTimeStamp,priority`; Flag 12840 |
| SpamFlow-Indizes/Anzahl | 92, z. B. `odml_scam_alert_bottom_sheet_block` = 65 | 97 Einträge (`C9E2`), gleiche Namen an verschobenen Indizes (70, 71, 76, 85, 89, 94, 96) |
| `SuspiciousFmxBottomSheetFragment` | durch 4 Datenbedingungen geöffnet | Info-Sheet, geöffnet über FMX-Card-Buttons / `C512928n` |
| Appeal-Request | MEX-Mutation `submitBanAppeal` | Graph `https://<host>.facebook.com/graphql` per doc_id 38509456535312323 / 5473316762755318, vorangestellt ein `purpose_public_keys`-Fetch; Operationsname nicht found |
| `wa_biz_integrity_chat_settings` | nicht lokalisiert | found (`AHY`) |
| XMPP-Fehler-Tokens | Tokens `policy-violation`, `403` | nicht im Dictionary; `forbidden`/`service-unavailable` und die Texte aus 8.3 fehlen |

Weiterhin offen in 2.26.41.6: Kategorienamen hinter `wfac_ban_violation_source` 0/1/2; Consumer von Flag 20278 und Flag 12840; Semantik des Helpers `N5r.A01`; Inhalt der WaFA-Reports; Fehlerbehandlung pro IQ für eingeschränkte Accounts (8.3); Anzeige des Account-Alters auf der FMX-Card; Flag hinter `C1P2.A01()`.
