<!-- src-sha1: 5fa1223d0cb214989ef32453299c247d3ee92ecf -->
# WhatsApp Org-Accounts — Full RE Report
**Version:** 2.26.45.10 | **Datum:** 2026-11-15
**Umfang:** Org-Account-Entitätsmodell (org_id, Mitgliederverzeichnis, Member-Tag/Team-Taxonomie), Invite-Link-Join-Flow, Verfügbarkeitsprüfung des Anzeigenamens, E-Mail-gegatetes Onboarding (OTP), `GraphQlOrgApi`/`OrgEmailCodeClient`-Operationskatalog (9 Ops, `www` + `mex`), Abgrenzung zu Managed Account und zur WhatsApp Business API Delegation, Baileys/velowa-Implementierungshinweise

---

## 1. Was ein Org-Account ist

Alle Aussagen beruhen auf statischer Analyse der dekompilierten APK. Tier: **found** = Literal/Feld wortwörtlich an einer Call-Site gelesen, **inferred** = aus der Codeform abgeleitet ohne durchgehend verfolgten End-to-End-Call, **unknown** = nicht aufgelöst.

Ein "org" (interne Benennung durchgehend, nirgends als "organization" in einem gelesenen String ausgeschrieben) ist eine Mitgliedschafts-Entität mit eigener Identität, einem beitretbaren Mitgliederverzeichnis und einem Onboarding-Pfad über Invite-Link plus E-Mail-OTP, vollständig getrennt von der eigenen Telefonnummern-Registrierung des Accounts und von den beiden anderen "managed"-klingenden Systemen, die bereits in diesem Repo dokumentiert sind (Abschnitt 7).

| Entität | Interner Name | Felder (found) | Rolle |
|---|---|---|---|
| Org-Identität | `org_id` | `org_id`, `org_name`, `org_member_count`, `org_icon_url`/`org_icon_handle`/`org_icon_full_url`, `org_description` | die Org selbst, aufgelöst aus einem Invite-Link |
| Invite-Link | `link_token` | durchgehend von Referrer/Deep-Link bis zur finalen Join-Mutation getragen | Einmal(?)-Join-Credential; genaue Lebensdauer `unknown` |
| Mitgliedsidentität innerhalb der Org | `display_name` (+ optional `display_last_name`), `member_tag` | Anzeigename pro Mitglied mit eigener Verfügbarkeits-/Policy-Prüfung, unabhängig vom Hauptprofilnamen des Accounts | wie ein Mitglied im Verzeichnis der Org angezeigt wird |
| Team/Rollen-Taxonomie | `team`, `team_options`, `selected_team` | als State-Felder gefunden; Semantik der einzelnen Team-Werte nicht aufgelöst | Gruppierung von Mitgliedern innerhalb einer Org |
| Verzeichnis-Beziehung | `relationship` (`OrgDirectory`), nur beobachteter Wert `"CONTACT"` | — | der einzige beobachtete Relationship-Filterwert; weitere Ordinal→String-Mappings sind `unknown` |

Alle diese Feldnamen werden wortwörtlich als `const-string`-Literale unmittelbar vor einem `GraphQlCallInput`/`LX/0jN`-Setter-Call in `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali` und `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali` (2.26.45.10) gelesen, plus die Feldliste des `OrgJoinViewModel`-State-Objekts — alles **found**. Die Schrittfolge, die diese Ops zu einem Flow verkettet (Abschnitt 3), ist **inferred** aus der Übereinstimmung der State-Felder, nicht aus einer einzelnen verfolgten Call-Sequenz.

---

## 2. Operationskatalog

9 Operationen über zwei Transporte, alle in `com.whatsapp.orgs`. 7 auf `www` (`GraphQlOrgApi`, persisted-doc_id GraphQL via `Lcom/facebook/pando/TreeWithGraphQL`), 2 auf `mex` (`OrgEmailCodeClient`). Variablen sind in jeder Zeile unten **found** aus der Call-Site.

| Op | Transport | doc_id (2.26.45.10) | Typ | Variablen | Zweck |
|---|---|---|---|---|---|
| `OrgInvitePreview` | www | `29166886682947630` | Query | `link_token` | Vorschau der Org (Name/Icon/Mitgliederanzahl) vor dem Beitritt |
| `OrgCheckDisplayName` | www | `28738875225734024` | Query | `display_name` | Verfügbarkeits-/Policy-Prüfung des Anzeigenamens innerhalb der Org |
| `OrgCheckEmailEligibility` | www | `28705126895811065` | Query | `link_token`, `email` | ob diese E-Mail für genau diesen Org-Invite nutzbar ist |
| `OrgSendEmailCode` | mex | `28659396457057459` | Mutation | `email` | E-Mail-OTP senden |
| `OrgVerifyEmailCode` | mex | `29096159596657036` | Mutation | `email`, `code` | E-Mail-OTP verifizieren |
| `OrgJoin` | www | `29366364109633604` | Mutation | `link_token`, `email`, `org_display_name`, `member_tag`, `org_display_last_name` | finale Join-Einreichung |
| `OrgDirectory` | www | `28698253656512395` (rotiert von `28049955604655823` in 2.26.41.6) | Query | `org_id`, `relationship` (nur `"CONTACT"` beobachtet), `first`, `after` | paginiertes Mitgliederverzeichnis, nach dem Join |
| `OrgMemberSearch` | www | `39884553687825642` (rotiert von `28199835469697557`) | Query | `query`, `org_id`, `first`, `after` | Suche innerhalb des Mitgliederverzeichnisses |
| `OrgLeaveMutation` | www | `28491454287217875` | Mutation | `org_id` | Org verlassen, jederzeit nach dem Beitritt |
| `OrgList` | www | `28999557569709709` (rotiert von `27920891847589435`) | Query | `unknown` (keine statische Call-Site gefunden, über doc_id/Rotation hinaus) | Orgs auflisten, denen der Account angehört |

Alle 7 `www`-Ops liegen in einer Klasse, `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali`; beide `mex`-Ops in `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`. Namespace/Schema für die `www`-Ops ist `whatsapp-android-www`; für die `mex`-Ops `whatsapp-android-mex`. `OrgDirectory`/`OrgList`/`OrgMemberSearch` existierten bereits vor 2.26.45.10 (erstmals gegen 2.26.41.6 erfasst); ihre doc_ids rotierten zwischen den beiden Builds (gleiche Klasse, gleiche Feldnamen) — die anderen 7 sind neu in 2.26.45.10.

Ergänzende Lookup-Ops existieren ein Package weiter, `com/whatsapp/work/publicidentity/` — nicht Teil des Join-Flows selbst, sondern der Weg, auf dem der Client eines Kontakts überhaupt erfährt, dass jemand zu einer Org gehört, bevor irgendein Invite im Spiel ist:

| Op | Transport | doc_id | Variablen | Zweck |
|---|---|---|---|---|
| `WorkPublicContactInfoQuery` | www | `29154186964216430` | `lids` (Liste) | Work/Business-Account-Status pro Kontakt, gebatcht (`CoalescingBatcher`, debounced, max. 100 Keys/Runde) |
| `WorkPublicOrgInfoQuery` | www | `28899689926378846` | `ids` (Liste, Org-IDs) | öffentliche Org-Info (`id`, `name`, 2 weitere opake String-Felder — `inferred`: Logo/Domain) für Orgs, denen ein Kontakt angehört |

---

## 3. End-to-End-Join-Flow

**Inferred**-Reihenfolge, zusammengesetzt aus den State-Objekt-Feldnamen von `OrgJoinViewModel` (keine einzelne verfolgte Call-Sequenz deckt dies End-to-End ab):

### 3.1 Einstieg

Der Invite kommt als Link-Token an, entweder über Referrer/Deep-Link (`OrgInviteReferrerOpener`, Literal `org_invite_token_from_referrer` → wird zu `link_token`) oder direkt geöffnet (`OrgInviteLandingActivity`, mit Fehlerzuständen `org_invite_landing_failure` / `org_invite_landing_already_in_org`).

### 3.2 Vorschau

`OrgInvitePreview(link_token)` liefert genug, um `org_name`, `org_member_count`, `org_icon_url`/`org_icon_handle`/`org_icon_full_url`, `org_description` zu befüllen, bevor sich der Nutzer auf irgendetwas festlegt.

### 3.3 Prüfung des Anzeigenamens

`OrgJoinActivity`/`OrgJoinViewModel` erfasst `display_name` (+ optional `display_last_name`) und eine Teamauswahl (`team`/`team_options`/`selected_team`). `OrgCheckDisplayName(display_name)` ist das Policy-/Verfügbarkeits-Gate; bei Ablehnung setzt die verschachtelte Continuation `OrgJoinViewModel$checkName$2` `name_refusal` und/oder `last_name_refused` unabhängig voneinander — Vorname und Nachname können jeweils eigenständig abgelehnt werden.

### 3.4 E-Mail-Eligibilität und OTP

`OrgCheckEmailEligibility(link_token, email)` prüft, ob eine gegebene E-Mail für diesen spezifischen Invite verwendet werden darf. `OrgSendEmailCode(email)` (mex) sendet dann den OTP; nachdem der Nutzer ihn eingegeben hat, verifiziert `OrgVerifyEmailCode(email, code)` (mex) ihn. Die Verifizierung kann `username_pending_email` / `rejoin_after_username` / `username_screen_open` zutage bringen — der Join kann hinter dem Setup des eigenen Usernames des Hauptaccounts gegatet sein, eine Abhängigkeit vom System aus `WA_USERNAME.md`, das sonst mit Orgs nichts zu tun hat.

### 3.5 Join

`OrgJoin(link_token, email, org_display_name, member_tag, org_display_last_name)` ist die finale Einreichung. Bei Erfolg wird `joined=true` gesetzt und die Org-Felder (`org_id`, `org_name`, `org_member_count`, `org_icon_*`, `org_description`) werden im lokalen State befüllt.

### 3.6 Nach dem Join

`OrgDirectory(org_id, relationship="CONTACT", first, after)` holt das Mitgliederverzeichnis; `OrgMemberSearch(query, org_id, first, after)` durchsucht es. `OrgLeaveMutation(org_id)` verlässt die Org, zu jedem Zeitpunkt nach dem Beitritt.

```
[Invite link / referrer]
  │ OrgInviteReferrerOpener: org_invite_token_from_referrer -> link_token
  │ (or OrgInviteLandingActivity: org_invite_landing_failure / _already_in_org)
  ▼
[OrgInvitePreview(link_token)]
  │  org_name, org_member_count, org_icon_*, org_description
  ▼
[OrgJoinActivity / OrgJoinViewModel]
  │  org_join_offline, step, team/team_options/selected_team, display_name, display_last_name
  ▼
[OrgCheckDisplayName(display_name)]
  │  -> name_refusal / last_name_refused on rejection
  ▼
[OrgCheckEmailEligibility(link_token, email)]
  ▼
[OrgSendEmailCode(email)]           -- mex, OTP send
  ▼
[user enters code]
  ▼
[OrgVerifyEmailCode(email, code)]   -- mex, OTP verify
  │  -> username_pending_email / rejoin_after_username / username_screen_open
  ▼
[OrgJoin(link_token, email, org_display_name, member_tag, org_display_last_name)]
  │  -> joined=true, org_id/org_name/org_member_count/org_icon_*/org_description populated
  ▼
[OrgDirectory(org_id, relationship="CONTACT", first, after)]
[OrgMemberSearch(query, org_id, first, after)]
[OrgLeaveMutation(org_id)]
```

---

## 4. Wichtige Abgrenzungen — nicht verwechseln

Drei voneinander unabhängige "Account-Struktur"-Konzepte existieren in/um diesen Client. Sie teilen sich keinen Code, kein Proto, keinen doc_id-Namensraum.

| | Org Accounts (dieser Report) | Managed Account (`WA_MANAGED_ACCOUNT.md`) | Business API Delegation (BSP/Cloud API) |
|---|---|---|---|
| Entitäts-Identität | `org_id`, eigenes Verzeichnis | `ManagedAccountConnection`, verschlüsselt über `connectionLid`/`connectionPnJid` | Verified-Name-Zertifikatsfelder (`host_storage`/`actual_actors`), keine neue Entitäts-ID |
| Beziehung | freiwilliger Beitritt via Invite-Link, N Mitglieder pro Org | ein Sponsor ↔ ein Dependent, ein Supervision-Link | eine Business-Nummer, betrieben von Meta/einem Provider über die Cloud API |
| Onboarding | Invite-Link + E-Mail-OTP + Verfügbarkeitsprüfung des Anzeigenamens | Deep-Link + vom Sponsor initiierte Verknüpfung (`ManagedAccountInitiateLinkingQuery` etc.) | serverseitiges Provisioning auf Metas Business-Plattform; für diesen Client unsichtbar, abgesehen von resultierenden Markern |
| Code-Standort | `com.whatsapp.orgs.*` | `com.whatsapp.managedaccount.*` / `pma.*` / `pmta.*` | kein dediziertes Package; signalisiert über `w:biz`-Zertifikatsfelder und Multi-Device-Accounttyp `HOSTED` |
| Transport | `whatsapp-android-www` GraphQL + `whatsapp-android-mex` (OTP) | nur `whatsapp-android-mex` | `w:biz`-Stanza-Felder, überhaupt kein Join-/Invite-Protokoll |
| Verlassen/Entkoppeln | `OrgLeaveMutation(org_id)` | `ManagedAccountRevokeLinkingMutation` | nicht anwendbar — kein Join/Leave pro Account; die Nummer selbst wird serverseitig provisioniert/deprovisioniert |
| Verzeichniskonzept | ja — `OrgDirectory`/`OrgMemberSearch`, relationship-gescoped | nein | nein |

Keines der drei ist eine Umbenennung oder Weiterentwicklung eines anderen: ein Org-Account hat keine Supervision-Semantik (keinen Alters-/Graduation-State, keine Sponsor-PIN) und keine Business-Zertifikats-Semantik (kein `host_storage`/`actual_actors`, keine Issuer-Prefix-Prüfung); es ist ein schlichtes, freiwilliges Mitgliedschaft-mit-Verzeichnis-Modell, aufgesetzt auf einen bereits registrierten WhatsApp-Account. Die produktbezogene Schlussfolgerung ("WhatsApps eigenes Organizations-Feature für Unternehmen/Institutionen") ist **inferred**, allein aus der Feldform (`org_id` + Mitgliederverzeichnis + Verfügbarkeitsprüfung des Anzeigenamens + E-Mail-Domain-Verifizierung) — es wurde kein Marketing- oder In-Client-Text gelesen, der das Feature benennt.

---

## 5. Fehlerfälle

Aus den Call-Sites dieses Builds konnte keine Fehlercode-Tabelle erstellt werden — für keine der 9 Ops wurden in diesem Durchgang response-seitige Literale (Success-/Failure-Feldnamen, numerische Fehlercodes) gefunden. Die einzigen gelesenen Ablehnungssignale sind die beiden booleschen State-Felder in `OrgJoinViewModel$checkName$2`:

| Symptom | Ursache | Evidenz |
|---|---|---|
| Anzeigename abgelehnt | `OrgCheckDisplayName`-Policy-/Verfügbarkeits-Fehlschlag | `name_refusal` gesetzt (found, State-Feld) |
| Nachname unabhängig vom Vornamen abgelehnt | gleiche Prüfung, nachname-spezifischer Branch | `last_name_refused` gesetzt (found, State-Feld) |
| Join blockiert bis zum Username-Setup | `OrgVerifyEmailCode`-Erfolg gatet auf dem eigenen Username-State des Accounts | `username_pending_email`/`rejoin_after_username`/`username_screen_open` (found, State-Felder; genaue Serverbedingung `unknown`) |
| Invite geöffnet, während bereits Mitglied | Landing-Page-Shortcircuit | `org_invite_landing_already_in_org` (found, String-Literal) |
| Invite-Link ungültig/abgelaufen | generischer Landing-Fehlschlag | `org_invite_landing_failure` (found, String-Literal; kein eigener Teil-Grund gefunden) |

---

## 6. Baileys/velowa-Implementierungshinweise

Alle 9 Ops sind Standard-persisted-doc_id-GraphQL/MEX-Calls auf denselben `whatsapp-android-www`/`whatsapp-android-mex`-Namespaces, die velowa für andere Features (Username, Gruppen) bereits implementiert — kein neuartiger Transport, keine native, orgs-spezifische Krypto-Schicht gefunden.

| Wire-ready | Nicht wire-ready |
|---|---|
| Alle 9 Op-Namen + doc_ids + Variablen-Keys (Abschnitt 2) — genug, um einen Request zu formen | Response-Feldnamen sind für jede Op außer den vier, die explizit in den `OrgJoinViewModel`-State gelesen werden (Abschnitt 1), unknown; ein Client muss alle Responses bis zu einer Live-Capture-Bestätigung als opakes JSON behandeln |
| `link_token`-Propagationspfad (Referrer → Vorschau → Join) | Exakte Step-Gatierung — ob der Server die Reihenfolge aus Abschnitt 3 erzwingt, oder ob z. B. `OrgCheckDisplayName`/`OrgCheckEmailEligibility` übersprungen werden können — ist `inferred`, nicht bestätigt |
| `OrgDirectory`/`OrgMemberSearch`-Paginierungsform (`first`/`after`, Standard-Cursor-Pattern) | `relationship`-Enum: nur `"CONTACT"` ist bestätigt; andere mögliche Werte sind `unknown`, ein Client sollte also nicht annehmen, dass dies der einzig gültige Filter ist |
| `OrgLeaveMutation(org_id)` — Single-Field-Mutation, trivial zu implementieren | `OrgList`s Variablen vollständig (keine Call-Site gefunden — sendet wahrscheinlich `{}`, nicht bestätigt) |
| `WorkPublicContactInfoQuery`/`WorkPublicOrgInfoQuery` für read-only "ist dieser Kontakt in einer Org"-Lookups, unabhängig vom Join-Flow | Invite-Link-URL-/Deep-Link-Format selbst (Host, Pfad, Token-Encoding) — in diesem Durchgang nicht erfasst |

Eine velowa-Implementierung, die diesen Flow umsetzt, sollte erwarten, Response-Formen empirisch gegen einen Live-Account zu entdecken — derselbe Caveat, der bereits in anderen `inferred`-Transport-Reports dieses Repos getragen wird (z. B. `WA_USERNAME.md`).

---

## 7. Unknowns

| Thema | Grund |
|---|---|
| `OrgList`s Variablen | keine statische Call-Site gefunden, über doc_id + Rotation hinaus; wahrscheinlich `{}`, aber nicht bestätigt |
| `relationship`-Enum-Werte außer `"CONTACT"` | nur ein Ordinal→String-Mapping beobachtet (Ordinal 0 → `"CONTACT"`); andere Branches in diesem Durchgang nicht abgedeckt |
| Response-Feldformen für alle 9 Ops | keine response-seitigen Literale/Feldnamen an irgendeiner Call-Site gefunden; alles jenseits der `OrgJoinViewModel`-State-Felder ist opak |
| `link_token`-Lebensdauer/Einmal-Semantik | nicht verfolgt; Einmaligkeit nur aus der Namenskonvention angenommen |
| Serverseitige Erzwingung der Schrittfolge aus Abschnitt 3 | aus der State-Feldform zusammengesetzt, nicht aus einer verfolgten sequenziellen Call-Chain — ein Client könnte Schritte umordnen oder überspringen können; ungetestet |
| `member_tag`/`team`-Wertemengen | Felder existieren (`team_options`, `member_tag`), aber keine enumerierten Werte gefunden |
| Invite-Link-URL-Format | in diesem Durchgang nicht erfasst |

---

## 8. Evidenz

Statische Analyse von WhatsApp Android 2.26.45.10 Smali, alle Literale und Variablen-Keys gelesen als `const-string` unmittelbar vor ihrem `GraphQlCallInput`/`LX/0jN`-Setter-Call. Kein Traffic wurde abgefangen; alle Transport-/Response-Form-Aussagen sind `inferred`. Quelle: `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali`, `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`, `com/whatsapp/orgs/ui/join/OrgJoinActivity.smali`, `OrgJoinViewModel.smali`, `OrgJoinViewModel$checkName$2.smali`, `com/whatsapp/orgs/ui/invite/OrgInviteReferrerOpener.smali`, `com/whatsapp/orgs/ui/invite/OrgInviteLandingActivity.smali`, `com/whatsapp/work/publicidentity/graphql/MexWorkIdentityTransport.smali`.
