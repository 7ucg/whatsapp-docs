<!-- src-sha1: 349e8112a4dcc4567ce203cf21c4c37e5bb47173 -->
# WhatsApp Business-App — Full RE Report
**Version:** 2.26.45.7 (Business) vs 2.26.45.10 (consumer) | **Datum:** 2026-11-15
**Umfang:** struktureller Diff der WhatsApp-Business-APK (`com.whatsapp.w4b`) gegen Consumer-WhatsApp (`com.whatsapp`) — Business-exklusive Package-Roots, der React-Native-Stack, Native-Library-Diff, GraphQL/MEX/`www`/`facebook-schema`-doc_id-Katalog-Asymmetrie, Permission-Diff; Abgrenzung zur WhatsApp Business API/Cloud API und zum Managed Account

---

## 1. Überblick

WhatsApp Business ist eine eigenständige App (`com.whatsapp.w4b`), kein Modus-Umschalter innerhalb von Consumer-WhatsApp. Sie teilt sich den Signal-Protocol-Kern, den Noise-Transport und den Großteil der Chat-UI mit Consumer-WhatsApp, bringt aber ihren eigenen Package-Satz für Business-only-Features mit und bündelt eine Abhängigkeit — eine vollständige React-Native-Runtime —, die Consumer überhaupt nicht mitführt.

Dieser Report deckt nur die **App selbst** ab, als APK gegen Consumer-WhatsApp diffed. Das ist eine andere Achse als zwei weitere "business"-nahe Konzepte, die in diesem Repo bereits dokumentiert sind:

| Konzept | Was es ist | Report |
|---|---|---|
| **WhatsApp-Business-App** (dieser Report) | Eine eigenständige Client-APK (`com.whatsapp.w4b`), die ein Unternehmen auf einem Handy installiert, mit eigener UI für Katalog, Labels, Abwesenheitsnachrichten, Ads | hier |
| **WhatsApp Business API / Cloud API** | Server-seitige Infrastruktur, die die Nachrichten einer Business-Nummer hostet/relayt, anstatt oder zusätzlich zur Business-App genutzt; in jedem Client nur über Verified-Name-Zertifikatfelder (`host_storage`, `actual_actors`, Issuer-Präfix `smb:`/`ent:`) und `business_state_id`-Coexistence-Banner erkennbar | `WA_MANAGED_ACCOUNT.md` §9 |
| **Managed Account** | Das eigene Consumer-Konto eines Minderjährigen, von einem Elternteil/Erziehungsberechtigten überwacht (`ManagedAccount*`/PAA/PMA/PMTA); unabhängig von beiden Business-Konzepten, es gibt kein "managed"-Label für den Business-Fall | `WA_MANAGED_ACCOUNT.md` §1-8 |

Ein einzelnes Unternehmen kann alle drei kombinieren: die Business-App auf einem Gerät betreiben, Teile seines Traffics an einen Cloud-API-Anbieter delegieren (Coexistence), während das Konto des Chat-Partners ein gewöhnliches Consumer-Konto ist. Siehe §9, wie diese zusammenspielen.

Evidenzquelle: ein statischer Package-/Asset-/Manifest-Diff zwischen `WA-Business_2.26.45.7.apk` und `WhatsApp_2.26.45.10.apk` (aktuelles Beta-Paar zum Diff-Zeitpunkt, kein Version-über-Version-Vergleich). Kein vollständiger jadx-Decompile wurde auf einer der beiden Seiten durchgeführt (harte Sicherheitsregel); alle Befunde unten liegen auf apktool-Smali-Baum-, Asset-JSON- und Reconstruct-Manifest-Ebene. Tiers folgen `found`/`inferred`/`unknown` gemäß dem Evidence-Contract des Brain.

---

## 2. Package-Ebenen-Diff — found

Vergleich jedes Verzeichnisses unter `smali*/` in jedem apktool-Baum: Business hat 4.281 eindeutige Package-Pfad-Verzeichnisse (15 `smali_classesN`-Bäume), Consumer hat 3.710 (14 Bäume). 853 Pfade existieren nur in Business, 282 nur in Consumer. 45 Top-Level-`com/whatsapp/*`-Package-Roots sind Business-exklusiv (das Root-Verzeichnis selbst fehlt in Consumer, nicht nur ein Unterpfad).

### 2.1 Business-exklusive Package-Roots, nach Feature-Cluster

| Cluster | Package-Roots | Notizen |
|---|---|---|
| Abwesenheit / Begrüßung / Schnellantwort-Messaging | `businessaway`, `businessgreeting`, `businessquickreply`, `businessmissedcallfollowup` | Kern-SMB-Auto-Reply-Features |
| Labels / Agenten / Chat-Zuweisung | `chatassignment`, `authagent`, `authagentfeaturecontrol`, `smbmultideviceagents`, `businesscontactmanager`, plus `lists/smb/labels` (Unterpfad; `lists`-Root ist shared) | Agent-Seats und Label-Bearbeitung |
| Profil-Einrichtung / Verifizierung | `businessregistration`, `protectedbusinessaccounts`, `metaverified` | |
| Katalog/Bestellungen (Management-Seite) | `ordermanagement` | Das Katalog-Browsen/-Bearbeiten selbst (`catalog`, `businessproduct`, `businesscollection`) ist **shared** — siehe §2.2 |
| Ads / Meta-Ads-Integration | `ads4ads`, `adscreation`, `adcreationinterfaces` | siehe §3 für die React-Native-Verbindung |
| Billing / Abonnements (API-Tiers) | `metabilling`, `metabillingui`, `subscription`, `billingui` | |
| App-zu-API-Coexistence | `coexistence`, `connectedaccounts`, `linkedaccounts`, `dynamicaudience` | Brücken zur Cloud-API-Seite, §9 |
| Meta-AI-Business-Agent | `bizai`, `genai`, `maiba` | |
| Business-Tooling / Compliance | `businesstools`, `businessinsights`, `rapidfeedbacksurvey`, `reportblocksharing`, `statistics`, `integrityenforcementsinfra`, `eligibilitychecker`, `googleeligibilityapi`, `smb`, `smbauth`, `waloginmbs`, `marketingmessage`, `marketingmessagemanagement`, `mediatemplates`, `bizdatasharing`, `bizgallerypicker`, `bizmedia` | |

### 2.2 Shared Roots mit Business-exklusiven Subpackages

Manche Roots existieren in beiden Apps, weil Consumer Business-seitige Daten ansehen/konsumieren kann, aber die Bearbeitungs-/Management-Subpackages sind Business-only:

- `com/whatsapp/businessprofile/` — shared Root; `businessprofileaddress`, `businessprofilecategory`, `businessprofileedit` (+ `boostmedia`, `businessprofilecompleteness`), `businessvertical`, `businesscompliance/smb/...` sind Business-only. Consumer behält nur die Read-Side-Profil-Ansichts-Subpackages.
- `com/whatsapp/lists/` — shared Root (Label-Datenmodell/UI, `labelitem` in beiden); das Label-**Bearbeitungs**-Subpackage `lists/smb/labels` ist Business-only.
- `catalog`, `businessproduct` (+ `businessproductlist`), `businesscollection` — shared Roots, bestätigt vorhanden im Smali-Baum von Consumer als die Katalog-/Produkt-**Browsing**-UI, die beim Ansehen eines Business-Chats angezeigt wird.

Netto-Form: Katalog-/Produkt-Betrachtung, Business-Profil-Betrachtung und Label-Anzeige sind shared; Katalog-/Profil-Bearbeitung, Away/Greeting/Quick-Reply-Messaging, Label-Bearbeitung, Agenten-/Multi-Device-Auth, Ads-Erstellung und Cloud-API-Coexistence sind Business-exklusiv.

### 2.3 Consumer-exklusive Packages — found, nicht geclustert

282 Pfade existieren nur in Consumer. Eine Stichprobenprüfung ergab keinen thematischen Cluster von vergleichbarer Größe wie beim Business-exklusiven Set; der Großteil sind verschachtelte Kinder einer kleineren Anzahl von Consumer-only-Roots. Nicht tiefer untersucht — als offene Lücke in §8 gelistet.

---

## 3. Der React-Native-Stack — found, Business-exklusiv

Unerwarteter Befund: Business bündelt einen vollständigen React-Native-Stack, der in Consumer auf Package-Ebene komplett fehlt, nicht nur ein zusätzliches Feature-Modul.

| Package | Business | Consumer |
|---|---|---|
| `com/facebook/react/*` (Bridge, Fabric, Animated, DevSupport, TurboModule, …) | 88 Verzeichnisse | 0 |
| `com/facebook/catalyst/*`, `com/facebook/fbreact/*` (RN-Bridge-Module, i18n, Safe-Area) | vorhanden | fehlt |
| `com/facebook/hermes/*` | 3 Verzeichnisse | 1 Verzeichnis — nur eine verwaiste Referenz, kein `com/facebook/react` zum Paaren, d.h. keine funktionierende RN-Runtime |
| `com/caverock/androidsvg`, `com/crossapp/graphql/facebook/*` | vorhanden | fehlt |

Bestätigt auf Native-Library-Ebene (§4): `libreactnative.so` (RN-Runtime), `libappmodules.so` (der native Loader des RN-JS-Bundles) und `libimagepipeline.so` (Fresco, die Bildpipeline von RN) sind Business-exklusive `.so`-Dateien.

**Inferred**, nicht bestätigt: manche Business-only-Oberfläche — am plausibelsten Ads-Erstellung (`adscreation/lwi/react/*` hat ein `react`-Subpackage direkt innerhalb von `lwi`), Meta-Billing oder Coexistence-Onboarding — ist als eingebettete React-Native-Screens implementiert statt als native Android-UI. Welche konkrete(n) Feature(s) den RN-Stack nutzen, ist aus den Package-Namen allein nicht bestätigt; dafür wäre ein gezielter Decompile der `adscreation/lwi/react/activity`-Klassen nötig. Das ist die klarste verbleibende "überraschende Abhängigkeit": eine Business-Messaging-App bettet eine plattformübergreifende JS-UI-Runtime ein, offenbar nur für einen oder wenige Screens (Ads-Erstellung ist die stärkste Namens-Übereinstimmung).

---

## 4. Native-Library-Diff — found

Verglichen wurde `superpack_index.csv` (das eigene Library-Manifest des SUPERPACK_OB-Containers) zwischen den Reconstruct-Outputs der beiden Apps:

| | Anzahl |
|---|---|
| Consumer-Libraries indexiert | 84 |
| Business-Libraries indexiert | 89 |

**Business-exklusiv (5):** `libappmodules.so`, `libimagepipeline.so`, `libreactnative.so`, `libwacomponents.so` (Name legt eine von WhatsApp selbst geschriebene RN-Bridge-Component-Library nahe, kein Stock-RN), `libzstddecoder.so` (vermutlich RN-Bundle-/Asset-Dekompression).

**Consumer-exklusiv:** keine — jeder Consumer-Library-Name taucht auch im Business-Index auf.

Die 6 von der Device-Oracle dekompilierten Libraries, die beide Apps teilen (`libwhatsapp.so`, `libwhatsappmerged.so`, `libwasafe.so`, `libvoprf-ed25519.so`, `libohai.so`, `libcurve25519.so`), sind zwischen den beiden Apps identisch (gleiche Größen, gleiche Symbol-/Export-Zahlen) — der Signal-Protocol-/Attestation-/Client-Integrity-Kern ist vom Business-Build unberührt. Der React-Native-+-Fresco-Stack ist sowohl auf Java/Kotlin-Package-Ebene als auch auf Native-Library-Ebene Business-exklusiv — ein konsistenter, zweischichtiger Befund.

---

## 5. GraphQL-/MEX-/`www`-/`facebook-schema`-doc_id-Katalog-Diff — found

Jede App liefert ihren eigenen `assets/whatsapp-android-<schema>_client_persist_ids.json`-doc_id-Katalog aus, direkt aus dem apktool-dekodierten Asset-Baum gelesen (kein Decompile nötig).

| Schema | Business-Ops | Consumer-Ops | Nur Business | Nur Consumer |
|---|---|---|---|---|
| `mex` | 242 | 242 | 0 | 0 — identisches Set |
| `wamo` | 22 | 22 | 0 | 0 — identisches Set |
| `www` | 237 | 244 | 4 | 11 |
| `facebook-schema` | 224 | 17 | 215 | 7 |

### 5.1 `mex` und `wamo` — identisch zwischen den Apps

Beide Kataloge haben in beiden APKs exakt die gleichen Operationsnamen (die Mengendifferenz ist leer, nicht nur gleich in der Anzahl). Business trägt auf dieser Schema-Ebene keine Business-spezifische MEX-/GraphQL-Oberfläche — es teilt sich den Consumer-Katalog vollständig.

### 5.2 `www` — kleine Asymmetrie

- Nur Business (4): `BPAccessTokenAndSessionCookiesMutation`, `CatkitTypeaheadProxy`, `WACreateEnforcementAppeal`, `WAGetEnforcementAppealStatus`.
- Nur Consumer (11): `WaAutofillAcknowledgeWalletTerms`, `WaAutofillFetchContactData`, `WaAutofillFetchSettings`, `WaAutofillSaveContactData`, `WaAutofillUpdateNegativeInteraction`, `WaAutofillUpdateSaveCvv`, `WaCreateLabyrinthBackupMutation`, `WaDeleteLabyrinthAccountMutation`, `WaDeleteLabyrinthThreadsMutation`, `WaRotateLabyrinthEpochMutation`, `WaUploadLabyrinthMessagesMutation`.

Consumer führt eigene Personal-Payments/Autofill- (`WaAutofill*`) und E2E-Chat-Backup- (`WaCreateLabyrinthBackupMutation` etc. — WhatsApps Chat-Backup-System, intern "Labyrinth") Ops, die Business nicht hat; Business führt ein paar Account-Enforcement-Appeal- und Session-/Typeahead-Ops, die Consumer nicht braucht.

### 5.3 `facebook-schema` — der Hauptbefund: 215 Business-only-Ops

Hier liegt die eigentliche Business-spezifische GraphQL-Oberfläche — nicht in `mex`/`wamo`, die zwischen den beiden Apps byte-identisch sind. Business führt 224 Ops in diesem Schema gegen 17 bei Consumer; die 17 von Consumer sind unabhängige Personal-Payment-/Commerce-Nonce-Ops (`AcDcCreateCanonicalDigitalCommerceNonce`, `WaAutofillAddPayCreditCard`, `WaGetServerEncryptionKey`, etc.), die Business nicht führt.

Die 215 Business-only-Ops, nach Namen geclustert (beschreibende Gruppierung, aus statischer Analyse abgeleitet, keine bestätigte funktionale Taxonomie):

| Cluster | Beispiel-Ops |
|---|---|
| Knowledge Base / AI-Reply / Simulation ("Coach") | `FetchAIAbilities`, `KnowledgeRepoFetchV2`, `UpdateAIKnowledge`, `DeleteAIKnowledge`, `CoachSimulationMessage`, `CoachSuggestedReply`, `StartSimulation`, `SubmitSimulationFeedback`, `FetchSuggestedReply`, `MarkSuggestedReplyUsed` |
| Meta-AI-Biz-Agent / MAIBA | `MAIBAOnboarding`, `MAIBACompleteParallelOnboarding`, `Maiba1pCalendarEvents`, `MaibaGetCurrentCatalog`, `MaibaDownloadLeadGenFlow`, `MetaAIBizAgentWAAIHome`, `MetaAIBizAgentWACoachingMutation` |
| Lead-Gen / Termine | `CreateLeadGenFlow`, `GetLeadGenFlowLeads`, `UpdateLeadStages`, `CreateAppointmentFlow`, `GetAppointmentPrefill`, `GetDefaultAvailability` |
| Auth-Agent / SMB-Multi-Agent / Login | `AuthAgentCompanyInfoQuery`, `AuthAgentFeaturePolicyQuery`, `AddSmbAgentAndCoexQr`, `SmbRegistrationInit`, `WALoginClaimAuthChallenge`, `WALoginConfirmAuthChallenge` |
| App-zu-Cloud-API-Coexistence | `CoexUnifiedOnboarding`, `CoexMultiAppEligiblity`, `CoexAppsAndServicesOffboardProduct`, `CoexCompanionPairingStatusCallback`, `CoexistenceQRCodeFetch` |
| Click-to-WhatsApp-Ads (CTWA) | `CTWACreateLookAlikeAudienceMutation`, `CTWAPreviousAdsRecommendationQuery`, `CtwaLinkedMediaQuery`, `CtwaNativeUploadAdMediaMutation` |
| Ad-Account / Eligibility | `AdAccountEligibilityCheckerQuery`, `OnboardToWhatsAppAdAccount`, `WhatsAppBizFetchAdDefaults`, `WhatsAppBizGetEstimatedAdReach` |
| Katalog-Management (Write-Seite) | `WhatsAppCatalogAddProduct`, `WhatsAppCatalogEditProduct`, `WhatsAppCatalogDeleteProduct`, `WhatsAppCatalogCreateCollections`, `WhatsAppCatalogProductVisibilityUpdate` |
| Marketing-Message-Broadcast ("Pro") | `BusinessBroadcastProCampaignContent`, `BusinessBroadcastProCustomAudiencesQuery`, `BusinessBroadcastProInsights`, `WAMarketingMessagesCustomAudienceCreateMutation` |
| Contact Manager / Kundenprofile | `BizContactManagerProfiles`, `ContactManagerAccessState`, `WACustomerProfiles`, `UpsertWACustomerProfiles`, `DeleteWACustomerProfile` |
| Billing / Abonnement (Meta-abgerechnete Tiers) | `FetchSubscriptionState`, `FetchSubscriptionStateV2`, `WaSmbMetaOneTierPaymentPrefetchTargetQuery`, `AcceptBizAiPaymentTerms` |
| Chatverlauf-Export / 3P (GDrive) Integration | `FetchChatHistoryExportStatus`, `GDriveGetFiles`, `UploadHistoricalMetadata`, `Disconnect3PPartners` |
| Verknüpftes IG/FB-Konto | `SetIGDisplayContactInfoMutation`, `WAFBPageProfileImportGet`, `WhatsAppBusinessLinkedAccountsQuery` |
| QE-/Feature-Flag-Plumbing (Business-seitig) | `CheckQEBool`, `WaFetchQEBool`, `WaFetchQEString`, `WhatsAppGraphQLCheckQE` |

Die vollständige 215-Namen-Liste ist aus den oben genannten Asset-Dateien der beiden Apps reproduzierbar; hier nicht wörtlich wiedergegeben. `www`-/`facebook-schema`-doc_id-**Werte** (nicht nur Op-Namen) wurden nicht gediffed — ein geteilter Op-Name könnte prinzipiell trotzdem eine unterschiedliche doc_id zwischen den beiden Apps tragen; nicht geprüft.

---

## 6. Permission-Diff — found

Aus dem Manifest-Inventar jeder App:

| | Business-exklusiv | Consumer-exklusiv |
|---|---|---|
| Permission | `com.whatsapp.permission.MIGRATION_CONTENT_PROVIDER` | `android.permission.RECEIVE_SMS` |

Beide Apps fordern zusätzlich eigene Package-Self-Broadcast-/Maps-Permissions unter ihren jeweiligen Package-Namen an (`com.whatsapp.w4b.*` vs `com.whatsapp.*`) — das sind Package-Namen-gemangelte Äquivalente zueinander, funktional nicht neu, und oben nicht mitgezählt.

Business fordert kein SMS-Receive an. **Inferred**, nicht aus Code bestätigt: konsistent damit, dass Business-Konten sich öfter über einen Cloud-/Business-API-Pfad registrieren statt sich auf On-Device-SMS-Auto-Read für OTP zu verlassen — aber diese Argumentation ist in diesem Pass nicht gegen Registrierungsflow-Code verifiziert.

---

## 7. Baileys-/velowa-Notiz

Fast keine Oberfläche dieses Reports ist von einem vanilla WhatsApp-Web-Client (velowa oder einer beliebigen Noise-/Multi-Device-Protokoll-Implementierung) aus erreichbar:

- Die `mex`-/`wamo`-Kataloge sind **identisch** mit denen von Consumer — nichts Business-Spezifisches hinzuzufügen; jeder WA-Web-Client hat bereits die gleichen doc_ids.
- Die 215 `facebook-schema`-Ops (§5.3) sind die echte Business-spezifische GraphQL-Oberfläche, aber das sind Business-**App**-UI-getriebene Flows (Katalog-Bearbeitung, Ads-Erstellung, Coaching/MAIBA, Coexistence-Onboarding, Agent-Auth), gated hinter dem eigenen Account-Zustand der Business-App und, in mehreren Clustern, komplett hinter der Server-Seite der WhatsApp Business API/Cloud API (Coexistence, Billing, Ad-Accounts). Ein WA-Web-Client, der das gewöhnliche Multi-Device-Protokoll spricht, hat zu den meisten davon keinen Zugang — es sind gar keine Wire-Protokoll-Features, sondern REST-/GraphQL-Calls, die die eigene UI der Business-App gegen Metas Business-Platform-Backend macht.
- Die React-Native-Oberfläche für Ads-Erstellung (§3) ist Android-App-UI-only (eingebettete JS-Screens, gerendert von `libreactnative.so`); daran reitet nichts auf dem Chat-Wire-Protokoll.
- Der einzige Bereich mit irgendeiner Multi-Device-Protokoll-Relevanz ist Coexistence (`coexistence`/`connectedaccounts`/`linkedaccounts`), deren Device-/Session-Repräsentation durch die bestehende Dokumentation in `WA_MANAGED_ACCOUNT.md` §9.3 und `WA_LINKED_DEVICE_PAIRING.md` abgedeckt ist (Account-Typ `HOSTED`, Device-ID 99, `platformType` 23/25-27) — das ist bereits so weit, wie eine rein client-seitige Sicht kommen kann.

Fazit: Dieser Report ist nützlich zum Verständnis, was die Business-APK *enthält*, nicht als Quelle neuer Wire-Protokoll-Oberfläche für velowa.

---

## 8. Was dieser Report NICHT verifiziert hat

| Lücke | Warum | Nötiger Follow-up |
|---|---|---|
| Proto-/Wire-Schema-Diff zwischen den beiden Apps | `unknown`, nicht inferred-same. Die Proto-Stufe der Reconstruct-Pipeline lief für keinen der beiden Builds (`protoc_ok=False` auf beiden Seiten); die tiefere Proto-Extraktion, die in diesem Versions-Refresh-Pass anderswo genutzt wurde (1089 Messages, `protoc`-Exit 0), lief nur gegen den bereits bestehenden jadx-Decompile von Consumer — kein äquivalenter Decompile existiert in diesem Workspace für `com.whatsapp.w4b`. Einen zu erzeugen braucht einen vollständigen jadx-Lauf über die ganze APK, verboten durch die harte Sicherheitsregel dieser Session (hat zuvor die Analysemaschine zum Absturz gebracht). Fehlende Evidenz ist keine Evidenz für Abwesenheit. | Eine auf Message-/Proto-Klassen beschränkte jadx-Extraktion einer einzelnen Klasse oder eines einzelnen DEX (kein vollständiger APK-Decompile) |
| Welche(s) Feature(s) über den Business-exklusiven React-Native-Stack rendern | Nur Package-/Library-Namens-Korrelation (`adscreation/lwi/react/*` ist die stärkste Namensübereinstimmung, aber nicht bestätigt) | Gezielter Decompile der `com/whatsapp/adscreation/lwi/react/*`-Klassen |
| Consumer-exklusiver Package-Cluster (282 Pfade) | In diesem Pass nicht thematisch geclustert — niedrigere Priorität angesichts der Aufgabenstellung auf Business-exklusive Oberfläche | Ein dedizierter Pass über den 282-Pfade-Diff |
| `www`-/`facebook-schema`-doc_id-**Werte** | Nur Op-**Namen** wurden gediffed; ein geteilter Name könnte eine unterschiedliche doc_id pro App tragen | Werte-Diff beider Asset-JSONs |
| Vollständige 215-Op-`facebook-schema`-Liste / Variablen / Response-Shapes | Clustering nur nach Namens-Keyword; keine Call-Site- oder Response-Field-Rekonstruktion versucht | Gezieltes Call-Site-Tracing pro Cluster, wie bei MEX-Ops anderer Reports gemacht |

---

## 9. Wesentliche Unterscheidungen

| A | B |
|---|---|
| WhatsApp-Business-**App** (`com.whatsapp.w4b`) — eine eigenständige APK mit eigenem Package-Satz, dieser Report | WhatsApp Business-**API / Cloud API** — server-seitiges Hosting/Relaying der Nachrichten einer Business-Nummer; keine dedizierte Client-APK, in jedem Client über Verified-Name-Zertifikatfelder erkennbar (`WA_MANAGED_ACCOUNT.md` §9) |
| Die `coexistence`-/`connectedaccounts`-/`linkedaccounts`-Packages der Business-App — die eigene UI der App zur Brücke zu einem Cloud-API-Anbieter | `business_state_id`-Coexistence-Banner, die der Client eines **Peers** sieht (Consumer oder Business), wenn eine Business-Nummer sowohl die App als auch die API gleichzeitig betreibt (`WA_MANAGED_ACCOUNT.md` §9.2) |
| Managed Account (`ManagedAccount*`, PAA/PMA/PMTA) — das eigene **Consumer**-Konto eines Minderjährigen unter elterlicher Aufsicht | Business-App — das Konto eines Unternehmens, völlig unabhängiges Konzept, kein Code-/Schema-Overlap |
| `mex`-/`wamo`-doc_id-Kataloge — byte-identische Op-Namen-Sets in beiden Apps | `facebook-schema`-doc_id-Katalog — 215 Ops existieren nur in Business; hier liegt die eigentliche Business-spezifische GraphQL-Oberfläche |
| Katalog-/Profil-/Label-**Betrachtung** — shared Package-Roots, auch in Consumer vorhanden (sodass ein Consumer-Nutzer den Katalog eines Unternehmens durchsehen kann) | Katalog-/Profil-/Label-**Bearbeitung** — Business-exklusive Package-Roots (die Write-Seite, die nur das Unternehmen selbst erreichen kann) |

---

## 10. Zusammenfassung

Bestätigt die von vornherein erwartete Form — Katalog, Business-Profil/Verifizierung, Labels, Quick-Replies/Greeting/Away-Messaging, Agenten-/Multi-Device-Auth-Cluster liegen in Business-only-Code, mit der Betrachtungs-/Anzeige-Hälfte jeweils shared mit Consumer — und fügt zwei nicht erwartete Befunde hinzu:

1. **`facebook-schema` ist dort, wo die echte Business-spezifische GraphQL-Oberfläche liegt** (215 Business-only-Ops: AI-Coach/Knowledge-Base, MAIBA, Lead-Gen, Auth-Agent, Coexistence, CTWA-Ads, Katalog-Write-Ops, Marketing-Broadcast, Billing), nicht die Haupt-`mex`-/`wamo`-Kataloge, die zwischen den beiden Apps byte-identische Op-Namen-Sets sind.
2. **Business bündelt einen vollständigen React-Native-+-Fresco-Stack** (`com.facebook.react.*`, `libreactnative.so`, `libimagepipeline.so`, `libwacomponents.so`), der in Consumer sowohl auf Package- als auch auf Native-Library-Ebene komplett fehlt — am plausibelsten für Ads-Erstellungs-Screens, aber die genaue Feature-Grenze ist ohne gezielten Decompile nicht bestätigt.

Der Proto-/Wire-Schema-Diff konnte in diesem Pass nicht durchgeführt werden (§8) und wird als unknown, nicht als inferred-same, vermerkt.
