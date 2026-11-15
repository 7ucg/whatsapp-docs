<!-- src-sha1: 03dc5e8e2a1874ff243bbae88accc3b09b397b6f -->
# WhatsApp Teen Account Sponsor Consent — Full RE Report
**Version:** 2.26.45.10 | **Datum:** 2026-11-15
**Umfang:** das Package `com.whatsapp.vpc.sponsor` — ein Eltern/Erziehungsberechtigten-("Sponsor")-Review-Screen für den Account eines Minderjährigen ("Teen") auf WhatsApp, dessen Navigationsmodell, das sponsor-seitige Altersverifikations-Gate, die drei Ergebnis-Screens (genehmigt/abgelehnt/nicht überprüfbar), die Konsequenz `account_deletion_time_ms` bei Ablehnung, was erreichbar bzw. auf dem Wire nachweisbar ist und was nicht, sowie die Abgrenzung zum Parental-Supervision-System aus `WA_MANAGED_ACCOUNT.md`

---

## 1. Was das ist

Neu in `2.26.45.10` (nicht in der `2.26.41.6`-Baseline vorhanden): vier Klassen unter
`com.whatsapp.vpc.sponsor`, die eine einmalige Review-Entscheidung implementieren, die ein
Elternteil/Erziehungsberechtigter über den WhatsApp-Account eines Minderjährigen trifft — genehmigen,
ablehnen oder melden, dass eine Überprüfung nicht möglich ist. Das ist strukturell verschieden vom
bestehenden Parental-Supervision-Produkt in `WA_MANAGED_ACCOUNT.md` (Abschnitt 8 unten erläutert die
Abgrenzung); es liest sich so, als würde WhatsApp dasselbe Teen-Account-Safety-Muster übernehmen, das
Meta bereits für Instagram und Facebook einsetzt: ein Erziehungsberechtigter muss zustimmen, dass ein
Minderjähriger überhaupt einen Account besitzt, mit einer Account-Löschungskonsequenz bei Verweigerung.

"VPC" wird nirgends im Client ausgeschrieben; "Verified Parent/guardian Consent" ist die plausibelste
Lesart angesichts der Form des Features — **inferred**, keine gefundene String-Expansion.

| Entität | Klasse | Rolle |
|---|---|---|
| Host-Screen | `VpcSponsorActivity` | nicht exportiert, kein Intent-Filter — Startmechanismus ungeklärt (§6) |
| View-Model | `X/B18` | hält erforderliche Launch-Args, führt das Age-Gate aus, steuert die Navigation |
| Nav-/Outcome-Dispatcher | `X/CaB` | gemeinsame Klasse (steht auch hinter der unabhängigen Altersverifikation `ConsentFlowActivity` und `WamoSubActivity`); der Zweig, der `VpcSponsorActivity`-Events behandelt, wird in diesem Report nachverfolgt |
| Outcome "Genehmigt" | `VpcSponsorApprovedFragment` | wird bei Genehmigung angezeigt |
| Outcome "Abgelehnt" | `VpcSponsorDeclinedFragment` | wird bei Ablehnung angezeigt; zeigt den Löschungs-Countdown |
| Outcome "Nicht überprüfbar" | `VpcSponsorCannotReviewFragment` | wird angezeigt, wenn der Sponsor zur Überprüfung nicht verifiziert werden konnte |

Alle Befunde stammen aus statischer Analyse der dekompilierten APK (`apktool`-Smali-Decode; kein
vollständiger JADX-Lauf über die gesamte APK, gemäß der Sicherheitspraxis dieses Repos für große
Builds). Nichts hier wurde auf dem Wire mitgeschnitten oder zur Laufzeit ausgeführt. Evidenz-Tiers:
**found** = direkt im Smali gelesen (ein literaler String, Field oder eine Klasse); **inferred** =
aus der Code-Struktur geschlossen, ohne dass ein Literal es benennt; **unknown** = in diesem Durchgang
nicht geklärt.

Die identischen vier Klassen existieren byteidentisch in Feld-/String-Layout in `com.whatsapp.w4b`
(WhatsApp Business) `2.26.45.7` — **found** durch Klassenpräsenz; nicht unabhängig nachverfolgt, der
unten gezeigte Trace für den Consumer-Build wird als übertragbar angenommen.

---

## 2. Navigationsmodell

Der Screen wird von einem sealed Destination-Typ, `LX/CvW`, gesteuert (gefunden durch Klassenpräsenz;
das Interface selbst trägt keinen selbstbenennenden String), mit sieben Implementierungen, die durch
ihre eigenen `toString()`-Literale identifiziert werden (found):

| Klasse | `toString()` | Was sie macht |
|---|---|---|
| `X/CSM` | `"AgeCollectionScreen"` | springt in Metas gemeinsamen cross-app Altersverifikations-Flow |
| `X/CSO` | `"ConsentNoticeScreen"` | der eigentliche Genehmigen/Ablehnen-Prompt — **wird nirgends in diesem Package gerendert**, siehe §4 |
| `X/CSN` | `"ApprovedScreen"` | zeigt `VpcSponsorApprovedFragment` |
| `X/CSS` | `"DeclinedScreen(accountDeletionTimeMs=...)"` | zeigt `VpcSponsorDeclinedFragment`; trägt einen `long`-Löschzeitstempel |
| `X/CSR` | `"CannotReviewScreen(teenName=...)"` | zeigt `VpcSponsorCannotReviewFragment`; trägt den Anzeigenamen des Teens |
| `X/CSP` | `"ErrorExit"` | zeigt Dialog-Tag `vpc_sponsor_error_exit_dialog`, beendet die Activity beim Dismiss |
| `X/CSQ` | `"Exit"` | beendet die Activity sofort |

---

## 3. Erforderliche Launch-Argumente und das sponsor-seitige Age-Gate

Der Konstruktor von `X/B18` (found) liest drei Keys aus den Saved-State-/Navigations-Argumenten der
Activity, zwei davon erforderlich — ein fehlender Wert wirft `IllegalStateException("Required value
was null.")`:

| Key | Typ | Anmerkungen |
|---|---|---|
| `vpc_teen_name` | `String` | erforderlich; der Anzeigename des Teens, später unverändert als `teen_name` in das Bundle des Cannot-Review-Screens kopiert |
| `vpc_account_deletion_time_ms` | geboxte Zahl (`.longValue()`) | erforderlich-vorhanden, aber der hier gelesene Wert wird **verworfen** — bestätigt durch Lesen des Konstruktor-Bytecodes, die Lokalvariable wird nie in einem Field gespeichert. Die Zahl, die der Decline-Screen tatsächlich anzeigt, kommt aus einem separaten Field `X/CSS.A00`, das später gesetzt wird, wenn das Review-Ergebnis ein `DeclinedScreen`-Destination erzeugt |
| `navigation` | nullable, verglichen mit `X/CSM.A00` | falls vorhanden und ungleich `AgeCollectionScreen`, setzt dies das initiale Destination direkt (z. B. ein fortgesetzter/neu gestarteter Flow) |

Wird kein initiales Destination gesetzt, ruft `B18`
`Lcom/whatsapp/dobverification/ContextualAgeCollectionRepository;->A06()Ljava/lang/Boolean;` auf —
ein **nullable** Boolean (found):

- **`null`** → Navigation zu `AgeCollectionScreen`. Der gemeinsame Dispatcher `X/CaB` startet dafür
  einen **Bloks-Altersverifikations-Screen** — derselbe Code-Pfad, den die unabhängige
  `ConsentFlowActivity` für Altersprüfungen zur Registrierungszeit nutzt (Logzeile
  `"ConsentFlowActivity/navigate/launch Bloks age verification screen"`, gefunden in der gemeinsamen
  Klasse, nicht vpc-spezifisch, aber vom `AgeCollectionScreen`-State des vpc-sponsor-Zweigs erreicht).
- **`true`** → Navigation zu `ConsentNoticeScreen`.
- **`false`** → Navigation zu `CannotReviewScreen(teenName)`.

Der Bloks-Screen meldet sich über
`VpcSponsorActivity.onAgeCollectionResult(ContextualAgeCollectionUsecaseApi$CACResult)` zurück (found,
exakte Signatur) und durchläuft die gleiche Dreifach-Entscheidung erneut, basierend auf dem
`CACResult`-Subtyp statt einem einfachen Boolean: ein Ergebnis mit Boolean-Payload geht erneut in die
`true`/`false`-Zweige oben ein; ein dismissed/blocked-Ergebnis führt zu `Exit`; ein
no-age-available- oder failed-Ergebnis führt zu `ErrorExit`.

**Interpretation (inferred, im Client nicht benannt):** Der *Sponsor* — nicht der Teen — muss Metas
gemeinsame cross-app Altersverifikation bestehen, bevor ihm der Genehmigen/Ablehnen-Prompt gezeigt
wird. Ein Sponsor, der sie nicht abschließen kann oder will, erreicht die eigentliche
Consent-Entscheidung nie; er wird je nach Ausgang der Altersprüfung zu `CannotReviewScreen`, `Exit`
oder `ErrorExit` geleitet.

---

## 4. Der Genehmigen/Ablehnen-Prompt wird nicht von diesem Package gerendert

Beim Lesen des `ConsentNoticeScreen`-Zweigs von `X/CaB` (found, exakter Bytecode): beim Erreichen
dieses States prüft der Code den *aktuellen* Wert des Navigations-`StateFlow`s erneut gegen
`ConsentNoticeScreen` — und falls er weiterhin übereinstimmt, wird sofort zu `ErrorExit` geroutet,
statt irgendetwas zu rendern. Kein Fragment, keine Activity und kein Bloks-Launch ist für diesen
State irgendwo in `com.whatsapp.vpc.sponsor` oder dem nachverfolgten `X/CaB`-Zweig verdrahtet.

**Schlussfolgerung (inferred):** Das eigentliche Genehmigen/Ablehnen-UI, auf dem der Sponsor agiert,
ist nativ aus diesem Package nicht erreichbar. Die konsistenteste Erklärung, gegeben dass auch das
Age-Gate Bloks-getrieben ist, ist ein serverseitig gerenderter Bloks-Screen, der *vor* dem Start von
`VpcSponsorActivity` gestartet wird, wobei diese Activity nur das **Ergebnis** — genehmigt, abgelehnt
oder nicht überprüfbar — empfängt, um das passende Terminal-Fragment anzuzeigen. Kein
GraphQL/MEX-Operationsname und keine Bloks-Screen-ID für die eigentliche
Genehmigen/Ablehnen-Übermittlung wurde in diesem Durchgang gefunden. **Unknown.**

---

## 5. Terminal-Outcome-Screens

| Screen | Liest | Zeigt | Netzwerkaufruf im Fragment selbst |
|---|---|---|---|
| `VpcSponsorApprovedFragment` | nichts aus eigenen Args | Header-Bild, Headline-/Body-Text, einen anklickbaren `"manage"`-getaggten Span im Body, einen `"Done"`-Button | keiner gefunden |
| `VpcSponsorDeclinedFragment` | `account_deletion_time_ms` (long, Fragment-Arg-Bundle, gesetzt aus `CSS.A00`) | Header-Bild, Headline, Body-Text mit der Löschzeit **formatiert als relativer/Dauer-String** (via `LX/0Fg;->A05(LX/0Fc;J)Ljava/lang/String;`, kein bloßer Zeitstempel), einen `"Done"`-Button | keiner gefunden |
| `VpcSponsorCannotReviewFragment` | `teen_name` (String, Fragment-Arg-Bundle, gesetzt aus `CSR.A00`) | Header-Bild, Headline mit interpoliertem Namen des Teens, Body-Text, einen `"OK"`-Button, der dismissed | keiner gefunden |

**Was `account_deletion_time_ms` in der Praxis bedeutet:** Der Decline-Screen formatiert diesen Wert
über einen Relativ-Dauer-Formatter und zeigt ihn als "verbleibende Zeit" an, d. h. dies wird dem
Betrachter als **Countdown** präsentiert, nicht als Hinweis, dass die Löschung bereits erfolgt ist —
found, aus dem Formatter-Aufruf. Ob das Ablehnen die Löschung serverseitig tatsächlich *plant*, im
Gegensatz dazu, dass die Löschung bereits läuft, wenn dieser Screen rendert, ist **unknown**: kein
Fragment in diesem Package tätigt einen eigenen Netzwerkaufruf; der Wert kommt einfach als
Launch-/Navigations-Argument an, das der Screen anzeigt.

Sämtlicher Body-Text dieser drei Screens (`str5e24`-`str5e2c` in der `res/values/strings.xml` dieses
Builds) ist wörtlicher Lorem-Ipsum-Platzhaltertext — das ist ein Beta-Build; Layout und
Data-Binding sind found, der endgültige ausgelieferte Text ist **unknown**.

---

## 6. Einstiegspunkt — ungeklärt

`VpcSponsorActivity` ist im Manifest als `android:exported="false"` ohne `<intent-filter>` deklariert
(found). Eine repository-weite Suche nach den literalen Navigations-Argument-Keys (`vpc_teen_name`,
`vpc_account_deletion_time_ms`) und nach jeder Konstruktion von `VpcSponsorActivity` außerhalb ihrer
eigenen vier Klassen und der gemeinsamen `X/CaB`-/Nav-Plumbing-Helper-Klassen liefert **keine Treffer
irgendwo im dekodierten Smali-Baum** — ein negatives, found-Ergebnis.

**Inferred:** Nichts in diesem Client baut den Launch-`Intent` statisch zusammen. Die plausibelste
Erklärung, konsistent damit, wie push-getriebene Navigation an anderer Stelle in dieser App
bekanntermaßen funktioniert, ist eine serverseitig ausgelöste Notification-Action, die die
Ziel-Activity und ihre Extras zur Laufzeit aus Push-Payload-Daten auflöst, statt einer hartkodierten
Call-Site — aber kein solcher Dispatcher wurde in diesem Durchgang identifiziert. **Unknown**, wie ein
Sponsor tatsächlich benachrichtigt und zu diesem Screen geroutet wird.

---

## 7. Netzwerk-Oberfläche

Kein GraphQL/MEX-Operationsname, keine Bloks-Screen-ID und kein binärer Stanza-`xmlns` wurde irgendwo
in diesem Package für irgendeinen Schritt des Flows gefunden: nicht für die Benachrichtigung eines
Sponsors über eine ausstehende Review, nicht für das Age-Gate (inferred Bloks, keine Screen-ID
erfasst), nicht für die eigentliche Genehmigen/Ablehnen-Übermittlung (§4), nicht für das, was den
Account-Löschungs-Countdown bei Ablehnung tatsächlich auslöst. Alles Netzwerkförmige in diesem Flow
wird als über Bloks laufend inferiert, statt über eine benannte, persistierte GraphQL/MEX-Query —
konsistent damit, wie der Rest von Metas cross-app Altersverifikations-Tooling in diesem Client
funktioniert — aber für keinen Teil davon wurde eine Operation- oder Screen-Identifier erfasst.

---

## 8. Wesentliche Unterscheidungen

### 8.1 vs. `WA_MANAGED_ACCOUNT.md` ("Managed Account")

| `vpc.sponsor` (dieser Report) | `managedaccount.*` / PAA / PMA / PMTA (`WA_MANAGED_ACCOUNT.md` §2-8) |
|---|---|
| Eine **einmalige Review-Entscheidung**: genehmigen, ablehnen oder Unmöglichkeit der Überprüfung melden, für einen bestimmten Minderjährigen-Account | Eine **fortlaufende Supervision-Beziehung** zwischen zwei unabhängig registrierten Accounts |
| Keine `w:mex`-Operation gefunden; inferred Bloks, keine Op/Screen-ID erfasst | Neun benannte `w:mex`-`ManagedAccount*`-Operationen mit doc_ids, Schema `whatsapp-android-mex` |
| Kein lokaler Beziehungs-Datensatz in diesem Package gefunden | Lokale `ManagedAccountConnection`-Zeile (`connectionLid`, `role`, `linkTs`, `connectionPnJid`, ...) |
| Ablehnung erzeugt eine `account_deletion_time_ms`-Konsequenz für den **Account des Teens selbst** | Unlinking (`ManagedAccountRevokeLinkingMutation`) beendet die Supervision; keiner der beiden Accounts wird gelöscht |
| Kein Rollen-Enum; der Sponsor ist einfach "der Reviewer" | `EnumC08540Ng`: `NONE`/`DEPENDENT`/`SPONSOR`/`SPONSOR_ADMIN` |
| Einstiegspunkt ungeklärt; Activity nicht exportiert, kein Deep Link | Einstiegspunkt ist ein In-App-Deep-Link (`ManagedAccountSponsorOnboardingViewModel`) |
| Teilt keine Klasse, kein Package, keinen String mit `managedaccount.*`/`pma.*`/`pmta.*` | — |

Kein Code in einem der beiden Packages referenziert das andere über Klasse oder String. Ob eine
`vpc.sponsor`-Genehmigung anschließend eine `managedaccount.*`-Beziehung erzeugt oder mit einer
interagiert, wurde nicht nachverfolgt; **unknown**.

### 8.2 vs. normale Account-Erstellung

Die normale WhatsApp-Registrierung (`WA_ACCOUNT_LESS_SURFACE.md` / der Standard-SMS/E-Mail-OTP-Flow)
hat überhaupt keinen Erziehungsberechtigten-Review-Schritt; ein Account wird aktiv, sobald der
eigene Owner die Registrierung abschließt. `vpc.sponsor` fügt ein externes Genehmigungs-Gate ein —
gehalten von einer anderen Person, auf einem anderen Gerät — zwischen irgendeinem Trigger
(ungeklärt, §6) und dem Fortbestehen des Accounts, wobei Ablehnung eine Löschungskonsequenz nach
sich zieht. Was einen Account überhaupt in diesen Guardian-Review-State routet (Alter zur
Registrierungszeit, ein On-Device-Alterssignal, eine spätere Neuklassifizierung), wurde in diesem
Package nicht gefunden und ist **unknown**.

---

## 9. Baileys-/velowa-Erreichbarkeits-Hinweis

Nichts in diesem Flow ist für einen reinen Wire-Drittclient erreichbar. Die
Genehmigen/Ablehnen-Entscheidung selbst wird als serverseitig gerenderter Bloks-Screen inferiert, der
vom First-Party-Client des Sponsors selbst gerendert wird (§4) — keine Message, IQ oder benannte
GraphQL/MEX-Mutation, die velowa senden oder beobachten könnte. Das sponsor-seitige
Altersverifikations-Gate (§3) ist ebenso Bloks-getrieben. Keine doc_id, kein MEX-Operationsname und
kein binärer Node-`xmlns` existiert für irgendeinen Teil dieses Flows in den Katalogen dieses Builds.
Es gibt hier nichts zu implementieren; dieser Abschnitt existiert, um das explizit festzuhalten,
statt es implizit zu lassen.

---

## 10. Unknowns

| Thema | Grund |
|---|---|
| Expansion von "VPC" | im Client nie ausgeschrieben; inferiert als Verified Parent/guardian Consent |
| Was `VpcSponsorActivity` startet und ihre Navigations-Args setzt | keine statische Call-Site irgendwo im dekodierten Baum gefunden; nicht exportiert, kein Intent-Filter |
| Die Genehmigen/Ablehnen-Übermittlung selbst (Netzwerkoperation, Screen-ID) | in diesem Package nicht implementiert; inferred Bloks, keine ID erfasst |
| Ob Ablehnung serverseitige Löschung plant, oder der Countdown rein informativ ist | kein Netzwerkaufruf in `VpcSponsorDeclinedFragment`; Löschung wird als bereits serverseitig initiiert angenommen, wenn dieser Screen rendert |
| Was einen Teen-Account überhaupt in das Guardian-Review routet | nicht nachverfolgt; keine Trigger-Bedingung in diesem Package gefunden |
| Beziehung, falls vorhanden, zu `managedaccount.*` | keine Querreferenz in beide Richtungen gefunden |
| Endgültiger ausgelieferter Text aller `vpc.sponsor`-Strings | dieser Beta-Build liefert Lorem-Ipsum-Platzhaltertext aus |
| Exakte Semantik der null-/true-/false-States von `ContextualAgeCollectionRepository.A06()` jenseits von "unbekannt/ausreichend/unzureichend" | nur aus Kontrollfluss inferiert; keine Field- oder Enum-Namen gefunden |
| Tatsächlicher Traffic | nur statische Analyse; nichts zur Laufzeit erfasst oder ausgeführt |

---

## 11. Flow (soweit die Evidenz reicht)

```
[Server / push — mechanism unresolved]
   │
   ▼
[VpcSponsorActivity starts] (launch args: vpc_teen_name, vpc_account_deletion_time_ms, navigation)
   │
   ▼
ContextualAgeCollectionRepository.A06() : Boolean?
   │
   ├─ null  ──► [Bloks age-verification screen] ──► onAgeCollectionResult(CACResult)
   │                                                     │
   │                                     ┌───────────────┼───────────────────┐
   │                                     ▼               ▼                   ▼
   │                             boolean payload   dismissed/blocked   no-age / failed
   │                             (re-enter below)      Exit               ErrorExit
   │
   ├─ true  ──► ConsentNoticeScreen
   │                 │
   │                 ▼
   │      [approve/decline prompt — not native to this package; inferred Bloks, unknown op]
   │                 │
   │      ┌──────────┼──────────────────┐
   │      ▼          ▼                  ▼
   │  ApprovedScreen  DeclinedScreen      (re-check of current state == ConsentNoticeScreen
   │      │          (accountDeletionTimeMs)   with no result yet falls to ErrorExit)
   │      ▼                 ▼
   │  VpcSponsorApproved  VpcSponsorDeclined
   │  Fragment ("Done")   Fragment (countdown text, "Done")
   │
   └─ false ──► CannotReviewScreen(teenName) ──► VpcSponsorCannotReviewFragment ("OK")
```
