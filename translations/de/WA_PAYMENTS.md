<!-- src-sha1: 1fe6d8278b8f0a0adfe50041466f968ec368a2e2 -->
# WhatsApp Payments — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-11-01
**Umfang:** In-Chat-Payment-Message-Typen (`sendPaymentMessage`, `requestPaymentMessage`, `declinePaymentRequestMessage`, `cancelPaymentRequestMessage`, Split Payments, Payment-Invite/Reminder) und ihre Proto-Felder, Multi-Rail-Client-Architektur (Indien UPI, Brasilien Pix, Mexiko, Indonesien, generische „UPR"-Rail), VPA-/Bankkonto-Linking und UPI-Onboarding-Flow, die eingebettete NPCI-„Common Library" (CL) für Credential/PIN/Device-Binding, Transaction-Status-Sync, Encryption-Layering (Chat-E2E vs. NPCI-Credential-Blob), GraphQL/MEX-Payment-Operationen (doc_ids), NPCI-OTP-Auto-Read-Regeln, Feature-Flags, Decline-/Error-Code-Handling

---

## 1. Was es ist (Überblick)

WhatsApp Android liefert ein gemeinsames In-Chat-Payment-Protokoll (Proto-Message-Typen innerhalb der normalen E2E-`Message`) plus mehrere länderspezifische Payment-*Rails*, jede mit eigener Onboarding-UI, GraphQL-Operationen und (für Indien) einer eingebetteten Drittanbieter-Credential-Library. Alle Findings sind statische Analyse der dekompilierten APK; nichts wurde über die Leitung mitgeschnitten. Tiers: **found** = direkt im Code/in Assets gelesen, **inferred** = aus Code abgeleitet, **unknown** = nicht aufgelöst. Obfuskierte Namen sind pro Build und wurden in 2.26.41.6 aus stabilen Strings aufgelöst (`FIELD_NUMBER`-Konstanten, AIDL-Interface-Namen, GraphQL-Operation-Kataloge, Asset-Dateinamen).

| Layer | 2.26.41.6 Name/Pfad | Rolle |
|-------|------------------------|------|
| Chat-Message-Protokoll | `DSJ` SendPaymentMessage, `C30605DSz` RequestPaymentMessage, `C30502DPa` DeclinePaymentRequestMessage, `DPZ` CancelPaymentRequestMessage, `DT0`/`C30535DQh` Split Payment, `C30586DSg` PaymentInviteMessage, `C43112IrN` PaymentReminderMessage, `DTS` PaymentInfo | Felder in Abschnitt 2 |
| Rail-Packages | `com.whatsapp.payments.{common,indiaupi,brazilpay,mexico,indonesia,globalorder,upr,dcp,remittances,split,paymentkey,productinfra,integrity,phoenix}` | ein Package pro Markt/Rail, Abschnitt 3 |
| Indien-UPI-Credential-Library | `org.npci.upi.security.{services,pinactivitycomponent}` (`CLRemoteService`, `CLRemoteServiceImpl`, `BinderC48420LDc`, `GetCredential`) | eingebettete NPCI-„Common Library" (CL), Abschnitt 6 |
| OTP-Auto-Read | `assets/npci/npci_otp_rules.json`, Consumer `org.npci.upi.security.pinactivitycomponent.C0315u` | Abschnitt 10 |
| GraphQL/MEX-Katalog | `assets/whatsapp-android-www_client_persist_ids.json` (Schema `whatsapp`), `whatsapp-android-mex_client_persist_ids.json` (Schema `whatsapp_mex`) | doc_ids, Abschnitt 9 |
| Server-Push-Handler | `C24410wL` ("PaymentsMessageHandler", Log-Tag `PaymentsMessageHandler`) | `<notification type="pay\|upi\|fbpay\|transaction\|account-recovery\|alert\|...">`, Abschnitt 8 |
| Transaction-Objekt | `F7F` (lokale Transaction-Row), `DTS` (Wire-/History-Sync-PaymentInfo), erzeugt von `EKY.A00` | Abschnitt 8 |

Rails identifiziert anhand von Package-/Klassennamen (found): **Indien UPI** (`indiaupi`), **Brasilien Pix** (`brazilpay`), **Mexiko** (`mexico`), **Indonesien** (`indonesia`), plus ein Rail-agnostisches „**UPR**"-Package (`upr` — Onboarding, Account-Management, Bubble-UI) und eine Legacy-Meta-Pay/Novi-Referenz, die in Enum-/Notification-Code noch vorhanden ist (`FBPAY`, `NOVI`), obwohl diese Services längst eingestellt sind — hier nur erfasst, weil die literalen Strings in 2.26.41.6 noch existieren. Evidenz unten ist pro Abschnitt als **Indien/UPI-spezifisch** oder **allgemein** markiert; UPI-Findings nicht automatisch auf Pix/Mexiko/Indonesien übertragen.

---

## 2. Payment-Message-Typen und Proto-Felder

### 2.1 Platzierung in `Message` (found)

Alle Payment-Message-Typen sind direkte Felder der Top-Level-`Message`-Proto (`C30628DTw`, dieselbe Klasse wie in `WA_MESSAGE_SECRETS.md` dokumentiert). Die meisten Payment-Sub-Messages exponieren **keine** öffentlichen `FIELD_NUMBER`-Konstanten auf `Message` selbst; die Nummern unten wurden durch Dekodierung des gepackten `GeneratedMessageLite`-Message-Info-Strings der Klasse ermittelt (eine reproduzierbare 2-oder-3-Zeichen-pro-Feld-Kodierung: Feldnummer-Zeichen, Typ-Marker-Zeichen, Has-Bit-Index-Zeichen; der Has-Bit-Index erhöht sich über die gesamte ~150-Felder-Message exakt um eins pro Eintrag, was ein starker interner Konsistenz-Check für das Decoding ist).

| Feld (Message) | Nummer | Typ |
|---|---|---|
| `sendPaymentMessage` | **16** | `SendPaymentMessage` (`DSJ`) |
| `requestPaymentMessage` | **22** | `RequestPaymentMessage` (`C30605DSz`) |
| `declinePaymentRequestMessage` | **23** | `DeclinePaymentRequestMessage` (`C30502DPa`) |
| `cancelPaymentRequestMessage` | **24** | `CancelPaymentRequestMessage` (`DPZ`) |
| `paymentInviteMessage` | **44** | `PaymentInviteMessage` (`C30586DSg`) |
| `splitPaymentMessage` | in diesem Pass nicht dekodiert | `SplitPaymentMessage` (`DT0`), `unknown` |
| `splitPaymentUpdateMessage` | in diesem Pass nicht dekodiert | `SplitPaymentUpdateMessage` (`C30535DQh`), `unknown` |
| `paymentReminderMessage` | in diesem Pass nicht dekodiert | `PaymentReminderMessage` (`C43112IrN`), `unknown` |

Der Stanza-Level-`<message type="pay">`-Classifier (geteilt mit anderen Add-on-Typen) ist in `WA_MESSAGE_SECRETS.md` im Abschnitt zum Type-Chooser (`AbstractC30999De0.A02`) dokumentiert; hier nicht erneut hergeleitet.

### 2.2 SendPaymentMessage (`DSJ`, found)

| Feld | Nummer | Typ | Verwendung |
|---|---|---|---|
| `noteMessage` | **2** | `Message` (`C30628DTw`) | die an eine Zahlung angehängte „Notiz" ist selbst eine vollständige `Message` (normalerweise nur `extendedTextMessage` oder Sticker) |
| `requestMessageKey` | **3** | `MessageKey` (`BD5`) | vorhanden, wenn dieser Send eine Antwort auf eine vorherige `requestPaymentMessage` ist |
| `background` | **4** | `PaymentBackground` (`DTJ`) | Abschnitt 2.7 |
| `transactionData` | **5** | string | opak; der Default-Wert im dekompilierten Source ist eine geteilte Leerstring-Konstante, kein echter Default |

Feldnummer 1 ist unbenutzt/reserviert (keine `FIELD_NUMBER`-Konstante dafür).

### 2.3 RequestPaymentMessage (`C30605DSz`, found)

| Feld | Nummer | Typ | Verwendung |
|---|---|---|---|
| `currencyCodeIso4217` | **1** | string | ISO-4217-Code |
| `amount1000` | **2** | int64 | Betrag × 1000 (Fixed-Point, keine Dezimalstellen im Wire-Wert) |
| `requestFrom` | **3** | string | Requester-Identifier (JID-String aus Call-Sites beobachtet) |
| `noteMessage` | **4** | `Message` | gleiches Muster wie 2.2 |
| `expiryTimestamp` | **5** | int64 | Unix-Sekunden |
| `amount` | **6** | `Money` (`C30561DRh`) | strukturierter Betrag, Abschnitt 2.7 |
| `background` | **7** | `PaymentBackground` (`DTJ`) | Abschnitt 2.7 |

### 2.4 DeclinePaymentRequestMessage / CancelPaymentRequestMessage (found)

Beide Messages sind minimal — ein einzelnes Feld, das auf den ursprünglichen Request verweist:

| Klasse | Feld | Nummer | Typ |
|---|---|---|---|
| `DeclinePaymentRequestMessage` (`C30502DPa`) | `key` | **1** | `MessageKey` (`BD5`) |
| `CancelPaymentRequestMessage` (`DPZ`) | `key` | **1** | `MessageKey` (`BD5`) |

**Keine der beiden Messages trägt ein Reason-/Error-Code-Feld.** Decline und Cancel sind Protokoll-No-ops jenseits von „dieser Request (identifiziert durch `key`) wird abgelehnt/abgebrochen" — jeglicher in der UI gezeigte Reason-Text ist nur lokal, nicht Teil des Wire-Payloads (found: kein zweites Feld existiert auf beiden Klassen; siehe Abschnitt 12).

### 2.5 Split Payments (found)

`SplitPaymentMessage` (`DT0`):

| Feld | Nummer | Typ |
|---|---|---|
| `splitId` | **1** | string |
| `totalAmount` | **2** | `Money` |
| `description` | **3** | string |
| `requesterJid` | **4** | string |
| `participants` | **5** | repeated `SplitPaymentParticipant` (`C30558DRe`) |
| `createdAtMs` | **6** | int64 |
| `contextInfo` | **17** | `MessageContextInfo`-ähnlich (`C30617DTl`) |

`SplitPaymentUpdateMessage` (`C30535DQh`): `splitId` (**1**, string), `participantJid` (**2**, string) — ein Per-Participant-Status-Ping, kein eigener Amount-/Status-Payload.

### 2.6 PaymentInviteMessage / PaymentReminderMessage (found)

`PaymentInviteMessage` (`C30586DSg`): `serviceType` (**1**, int/enum — verknüpft mit den `UPI`-/`PIX`-/`NOVI`-/`FBPAY`-Service-Codes aus Abschnitt 8), `expiryTimestamp` (**2**, int64), `incentiveEligible` (**3**, bool), `referralId` (**4**, string), `inviteType` (**5**, int/enum).

`PaymentReminderMessage` (`C43112IrN`):

| Feld | Nummer | Typ |
|---|---|---|
| `reminderId` | **1** | string |
| `instanceId` | **2** | string |
| `description` | **3** | string |
| `frequency` | **4** | int/enum |
| `status` | **5** | int/enum |
| `payeeVpa` | **6** | string |
| `payeeJid` | **7** | string |
| `payerJid` | **8** | string |
| `amount` | **9** | `Money` |

`payeeVpa` (Feld 6) ist ein **literales VPA-Feld im Wire-Protokoll** — direkte Proto-Level-Bestätigung, dass UPI-Virtual-Payment-Addresses innerhalb von Chat-Messages reisen, nicht nur über GraphQL-Seitenkanäle.

### 2.7 Supporting Types (found)

| Typ | Klasse | Felder |
|---|---|---|
| `Money` | `C30561DRh` | `value` (**1**, int64), `offset` (**2**, int32 — Dezimalpunkt-Offset), `currencyCode` (**3**, string) |
| `MessageKey` | `BD5` | `remoteJid` (**1**, string), `fromMe` (**2**, bool), `id` (**3**, string), `participant` (**4**, string) |
| `PaymentBackground` | `DTJ` | `id` (**1**, string), `fileLength` (**2**, int64), `width` (**3**, int32), `height` (**4**, int32), `mimetype` (**5**, string), `placeholderArgb` (**6**, int32), `textArgb` (**7**, int32), `subtextArgb` (**8**, int32), `mediaData` (**9**, `MediaData` `C30588DSi`), `type` (**10**, enum) |

### 2.8 PaymentInfo — Transaction-Status-Objekt (found)

`DTS` ("PaymentInfo") ist **kein** Chat-Message-Typ; es ist an `WebMessageInfo` (`C30626DTu`, der History-Sync-/Companion-Carrier aus `WA_MESSAGE_SECRETS.md`) als `paymentInfo_` und `quotedPaymentInfo_` angehängt. Es repräsentiert den aktuell bekannten Status einer Transaktion, gebaut aus der lokalen Transaction-Row von `EKY.A00`:

| Feld | Nummer | Typ | Hinweis |
|---|---|---|---|
| `currencyDeprecated` | **1** | enum | Legacy |
| `amount1000` | **2** | int64 | |
| `receiverJid` | **3** | string | |
| `status` | **4** | enum | grober Status |
| `transactionTimestamp` | **5** | int64 | |
| `requestMessageKey` | **6** | `MessageKey` | |
| `expiryTimestamp` | **7** | int64 | |
| `futureproofed` | **8** | bool | gesetzt, wenn das lokale Transaction-Objekt des Senders keine auflösbare Currency/Amount hat (Schema-Evolution-Escape-Hatch) |
| `currency` | **9** | string | |
| `txnStatus` | **10** | enum | feingranularer Status (NPCI-Level), eigenes Enum getrennt von `status` |
| `useNoviFiatFormat` | **11** | bool | Legacy Meta-Pay/Novi-Display-Format-Flag |
| `primaryAmount` | **12** | `Money` | |
| `exchangeAmount` | **13** | `Money` | Cross-Currency-Anzeige |

Die Enum-Konstanten-**Namen** von `status`/`txnStatus` sind auf Javalite-Bytecode-Ebene vom Obfuskator entfernt (nur Ordinals + `EnumVerifier`-Klassen bleiben übrig); ihr Ordinal→Label-Mapping ist in diesem Pass `unknown`. `EKY.A00` liest Currency/Amount des lokalen Transaction-Objekts und setzt, falls nicht vorhanden, `futureproofed=true` statt zu raten — found im Code (`f7fA00.A03 == 5 || !f7fA00.A0N()`-Guard).

---

## 3. Multi-Rail-Client-Architektur ("payment-common-library")

Payment-Code ist als ein gemeinsames UI-/Infrastruktur-Package plus ein Package pro Markt-Rail organisiert (found, aus Package-Layout unter `com.whatsapp.payments`):

| Package | Rail | Inhalt (found) |
|---|---|---|
| `common` | geteilt | `p144ui` (generische Payment-Bottom-Sheets, Settings, Transaction-History, Method-Picker), `pin` (PIN-Entry-UI rail-übergreifend geteilt), `paymentkeys`, `compliance`, `care` (CSAT), `qpl` (Quality-/Perf-Logging-Marker) |
| `indiaupi` | Indien UPI | Onboarding, Bank-/VPA-Linking, Mandates, Bill-Payments, UPI Lite, QR, Account-Recovery — Abschnitt 4 |
| `brazilpay` | Brasilien Pix | Pix-Key-Management, Biometric-/Passkey-Enrollment, CPF |
| `mexico`, `indonesia` | lokale Rails | als Packages vorhanden; in diesem Pass nicht über ihre Existenz hinaus erforscht (`unknown` Detail) |
| `upr` | rail-agnostisch | `nux` (Onboarding), `accountmanagement`, `bubble` (In-Chat-Payment-Options-Sheet), `shared` (Institution-/Account-Type-Picker) — mapped auf die `GenUprPaymentConfig`/`GenUprPaymentConfigForViewer`-GraphQL-Ops (Abschnitt 9); die „UPR"-Expansion ist in keinem gefundenen String ausgeschrieben (`inferred`: „Universal/Unified Payment Rail") |
| `globalorder`, `remittances`, `split`, `paymentkey`, `productinfra`, `integrity`, `dcp`, `phoenix` | gemischt | als Packages vorhanden; `integrity` enthält ein Payment-„Friction"-Bottom-Sheet (Risk-/Step-up-UI), unter `dcp` und `phoenix` wurden in diesem Pass auf den obersten zwei Verzeichnisebenen keine Dateien aufgelöst (`unknown`) |

Cross-Rail-GraphQL-Transport ist von `PaymentsMexGraphQlClient$ApiEventCallBuilder` (`com.whatsapp.payments.indiaupi.common.graphql`, trotz des Package-Namens der geteilte MEX-Call-Wrapper, found) umschlossen — er versieht jeden Payment-MEX-Call mit QPL-/Event-Logging-Start/Success/Failure-Callbacks (`FDA.BYz`), bevor an den darunterliegenden Transport `InterfaceC17070jD` delegiert wird. Das ist in diesem Build die engste Entsprechung zu einer „Payment Common Library" auf **Client**-Ebene: eine obfuskierte Call-Wrapper-Klasse, wiederverwendet von Indiens UPI-GraphQL-Managern (`IndiaUpiChangeMpinGraphqlManager`, `IndiaUpiCheckBalanceGraphqlManager`, `IndiaUpiEnrollIncentiveGraphqlManager` usw. — found, gleiches Package).

Separat liefert Indien eine eingebettete **Drittanbieter**-Library unter dem NPCI-eigenen Package `org.npci.upi.security.*` (nicht `com.whatsapp.*`) — das ist die von NPCIs eigenen `.properties`-Assets referenzierte "CL" ("Common Library") (`version.properties`, `validation.properties`, `cl-*.properties`) und wird in Abschnitt 6 behandelt. Das Vokabular der NPCI-Assets selbst (`salt`, `payInfo`, `controls`, `configuration`, `trust`, `keyXmlPayload`, `keyCode`) stimmt exakt mit den Bundle-Key-Strings überein, die in diesem Build in den `CLRemoteService.Acc`/`Acf`-Implementierungen gefunden wurden (Abschnitt 6) — direkte Bestätigung, in diesem Build, einer früheren reinen Asset-Analyse. Die literale Ausschreibung „Common Library" ist weiterhin nirgends als String ausgeschrieben (`inferred`, nun bestätigt durch die Klassennamen `CLRemoteService`/`CLResultReceiver`/`CLRemoteServiceImpl` selbst, was neue Evidenz dieses Passes ist).

---

## 4. VPA-/Bankkonto-Linking und UPI-Onboarding (Indien-spezifisch)

Activity-Namen, ermittelt aus `com.whatsapp.payments.indiaupi.*` (found, nur Klassen-Existenz und -Benennung — die genaue Navigationsreihenfolge zwischen ihnen ist `inferred` aus Benennung und NICHT über Intent-Graphen in diesem Pass nachverfolgt):

| Schritt | Activity/Fragment |
|---|---|
| Entry / Value Props | `IndiaUpiPaymentsValuePropsActivity`, `IndiaUpiPaymentsValuePropsBottomSheetActivity`, `IndiaUpiPaymentsTosActivity` |
| SIM-Verifizierung | `IndiaUpiSimPickerDialogFragment`, `IndiaUpiSimVerificationActivity` |
| Bankauswahl | `IndiaUpiBankPickerActivity` (`onboarding`-Package), `IndiaUpiBankAccountPickerActivity` |
| Identitäts-/Kartenverifizierung | `IndiaUpiDebitCardVerificationActivity`, `IndiaUpiAadhaarCardVerificationActivity`, `IndiaUpiDobPickerActivity` |
| Device Binding | `IndiaUpiDeviceBindStepActivity` (siehe Abschnitt 6 für die Krypto hinter diesem Schritt) |
| PIN-Einrichtung | `IndiaUpiPinPrimerDialogFragment` / `...FullSheetActivity`, `IndiaUpiPinHandlerActivity`, `IndiaUpiPinSetUpCompletedActivity`, `IndiaUpiChangePinActivity`, `IndiaUpiForgotPinDialogFragment` |
| Abschluss | `IndiaUpiBankAccountAddedLandingActivity`, `IndiaUpiPaymentsAccountSetupActivity` |
| Nummer-zu-VPA-Mapper | `IndiaUpiMapperValuePropsActivity` → `IndiaUpiMapperLinkActivity` → `IndiaUpiMapperPendingActivity` → `IndiaUpiMapperConfirmationActivity`; `IndiaUpiCreateCustomNumberActivity` für eine nicht-standardmäßige Mobilnummer |
| VPA-Kontakt-Auflösung | `IndiaUpiVpaContactInfoActivity`, `IndiaUpiSendPaymentToVpaFragment` |

„Mapper" ist NPCIs eigener Begriff für den Telefonnummer↔VPA-Directory-Service; die vier `mapper.register.*`-Activities implementieren genau diesen Registrierungs-Sub-Flow (found: Package-Pfad `indiaupi.p148ui.mapper.register`).

Linking-relevante GraphQL-Operationen mit call-site-verifizierten Variablen (found, aus `com.whatsapp.payments.indiaupi.common.graphql.*` und verwandten `X/*`-Klassen; siehe Abschnitt 9 für den vollständigen Katalog):

| Operation | doc_id | Variablen (found) |
|---|---|---|
| `GetUpiBankList` | `27764018976534565` | `account_type`, `provider_type`, `request` |
| `GetUpiAccounts` | `25691302307224710` | `bank_code`, `device_id`, `provider_type`, `account_type` |
| `GetUpiToken` | `25639185495767704` | `challenge`, `device_id`, `token_type`, `provider_type` |
| `GenCreatePaymentKey` | `24662763616751127` | `add_bank`, `account_holder_name`, `display_name`, `payment_method_type`, `payment_account`, … (verrauschte Superset, Caller über mehrere Ops geteilt — siehe Caveat in Abschnitt 9) |
| `SetUpiChangeMpin` | `27149786891388216` | `credential_fbid`, `device_id`, `new_mpin`, `old_mpin`, `seq_no`, `upi_bank_info`, `vpa` |

---

## 5. Payment-Setup/Onboarding (allgemein, rail-übergreifend)

Das `upr`-Package implementiert eine rail-agnostische Onboarding-Shell: `UprOnboardingActivity` → `UprOnboardingFragment` → `UprAccountTypePickerBottomSheet` → `AddPaymentMethodFragment` / `UprInstitutionPickerBottomSheet` (found, nur Klassennamen; Flow-Reihenfolge `inferred`). Account-Management nach dem Setup läuft über `UprAccountManagementActivity`/`UprAccountManagementListFragment`, und der In-Chat-Payment-Trigger erscheint über `UprPaymentOptionsBottomSheet`/`UprPaymentAccountDetailBottomSheet` ("bubble"-Package — das schwebende Payment-Options-Sheet, das aus einem Chat geöffnet wird).

Server-seitige Konfiguration für diese Shell wird über `GenUprPaymentConfig` (doc_id `26905963415743456`) und `GenUprPaymentConfigForViewer` (doc_id `37307071662269517`) geladen — found im doc_id-Katalog, in diesem Pass nicht unabhängig call-site-verifiziert (`unknown` Variablen).

---

## 6. NPCI "Common Library" (CL): Credential, PIN und Device Binding (Indien/UPI-spezifisch)

### 6.1 Architektur (found)

UPI-PIN-Entry und Bank-Credential-Handling in Indien werden an einen eingebetteten, NPCI-eigenen Android-AIDL-Service delegiert, vollständig getrennt von WhatsApps eigenem `com.whatsapp.*`-Code:

```
org.npci.upi.security.services.CLRemoteService      <- AIDL interface
org.npci.upi.security.services.CLResultReceiver     <- AIDL callback interface
org.npci.upi.security.pinactivitycomponent.CLRemoteServiceImpl  <- Android Service, binds the AIDL
org.npci.upi.security.pinactivitycomponent.BinderC48420LDc      <- Binder implementation of CLRemoteService
org.npci.upi.security.pinactivitycomponent.GetCredential        <- PIN-entry Activity launched by the binder
org.npci.upi.security.pinactivitycomponent.Keypad               <- on-screen keypad widget
```

`CLRemoteService`-Methoden (found, Interface-Signaturen): `AQR(otpResultJson)`, `AZO(mode, nonce)` (Device-Binding-Challenge/Response, Abschnitt 6.2), `Acc(...)`/`Acf(...)` (startet die PIN-Activity mit einem Credential-Bundle), `BBj(...)` (Balance-Read), `BVz/CRh/CRi(...)` (Device-Cert-/State-Validation), `BW1()` (Device-Integrity-Check).

### 6.2 Device Binding und Credential-Exchange (found)

`BinderC48420LDc.AZO(mode, nonce)`:
- Modus "initial": baut `deviceId|randomHex|nonce`, RSA-verschlüsselt es gegen ein gebündeltes NPCI-Zertifikat (`MYU.A00`), base64-kodiert, liefert `"2.3-v1.8|" + ciphertext`. Das `2.3-v1.8`-Präfix ist ein hartkodierter CL-Protokoll-Versionstag (found, literal).
- Folgemodus: leitet einen AES-Key aus dem gespeicherten Credential-Record ab, AES/GCM-verschlüsselt dasselbe `deviceId|randomHex|nonce`-Triple mit frischem Zufalls-IV, liefert `ciphertext|iv` unter demselben Versionspräfix.

`BinderC48420LDc.Acc`/`Acf` bauen ein `Bundle` mit den Keys `keyCode`, `keyXmlPayload`, `controls`, `configuration`, `salt`, `payInfo`, `trust`, `languagePref` und starten damit die `GetCredential`-Activity (found, literale String-Keys) — exakt das Vokabular, das eine frühere reine Asset-Analyse von `version.properties`/`validation.properties` für das „CL"-Schema vermutete (`salt`, `payInfo`); der Code dieses Builds bestätigt, dass das reale Runtime-Bundle-Keys sind, nicht nur Asset-Datei-Platzhalter.

`C51962N8y` (Krypto-Helper, durchgängig im Binder verwendet):
- `A00`: erzeugt ein **RSA-2048-Keypair im Android KeyStore**, `CN=NPCI_CERT`, SHA-512/PSS, erfordert Secure Hardware (`isInsideSecureHardware()`, wirft sonst) und (SDK-abhängig) User-Authentication innerhalb eines kurzen Validity-Fensters — das ist der Device-Binding-Key.
- `A03`/`A04`: AES/GCM-NoPadding, 128-Bit-Tag, Caller-übergebener Key und IV explizit — Session-Level-Encrypt/Decrypt.
- `A02`: SHA-256-Digest (Challenge-Hashing).
- `A01`: entschlüsselt einen `ciphertext|iv`-förmigen String mit einem gespeicherten AES-Key — gepaart mit dem Ausgabeformat von `AZO` oben.

`BinderC48420LDc.BW1()` führt einen Root-/Tamper-Check aus (Build-Tags, gängige `su`-Binary-Pfade, `which su`-Probe) **und** verifiziert, dass der gerade generierte RSA-Key StrongBox-/TEE-backed ist; ein fehlgeschlagener Check lässt `BW1()` `false` zurückgeben, was den Credential-Issuance-Pfad weiter oben gated (found: Boolean-Return wird von `CRh`/`CRi`-Logikpfaden konsumiert, nicht unabhängig bis zu einer UI-Message nachverfolgt).

### 6.3 Was das für Message-Inhalte bedeutet

Die UPI-MPIN selbst erscheint nie in einer Chat-Message oder in den Proto-Feldern aus Abschnitt 2 dieses Reports — sie wird vollständig innerhalb der `GetCredential`-Activity gehandhabt und mit der Issuer-Bank/dem NPCI-Switch über den RSA/AES-Layer oben ausgetauscht, wodurch ein opaker *Credential-Blob* entsteht, der letztlich in GraphQL-Variablen wie `new_mpin`/`old_mpin`/`mpin` in `SetUpiChangeMpin`/`CheckUpiBalance` (Abschnitt 9) landet. Dass der String, den eine GraphQL-Variable tatsächlich trägt, bereits NPCI-verschlüsselt ist (statt clientseitig nur im Klartext durch TLS geschützt), ist aus dem Zweck des vorangehenden CL-Flows **inferred**, nicht durch Lesen des Byte-Inhalts der GraphQL-Call-Site unabhängig bestätigt.

---

## 7. Encryption-Layering: Chat-E2E vs. NPCI-Credential-Blob

Zwei unabhängige Verschlüsselungs-Layer sind bei einer Zahlung involviert und dürfen nicht verwechselt werden (Abschnitt 13):

| Layer | Schützt | Mechanismus | Evidenz |
|---|---|---|---|
| Chat-Message-E2E | die gesamte `Message`-Proto, inklusive jedes Felds aus Abschnitt 2 (Amount, Note, VPA in `payeeVpa`, JIDs, `MessageKey`-Referenzen) | WhatsApps Standard-Signal-Protocol-/Noise-Session-Encryption — out of scope für diesen Report, siehe andere RE-Reports für diesen Layer | hier nicht erneut hergeleitet |
| NPCI-Credential-/Device-Binding-Blob | MPIN, Device-Binding-Challenge/Response, Risk-Check-Payloads, mit der Issuer-Bank über NPCI ausgetauscht | RSA-2048 (KeyStore, TEE-bound, `CN=NPCI_CERT`) für Device Binding; AES/GCM-128 mit explizitem IV für Session-Daten; SHA-256 für Challenge-Hashing | Abschnitt 6.2, found |

Der zweite Layer ist **Indien/UPI-spezifisch** und läuft unterhalb/vor dem GraphQL-Call, nie innerhalb der Chat-`Message`-Proto. Für Brasilien Pix oder Mexiko wurde in diesem Pass kein payment-spezifischer AES/RSA-Layer gefunden (`unknown` — nicht erforscht).

---

## 8. Transaction-Status-Sync

### 8.1 Lokales Objekt und History Sync (found)

`F7F` ist das In-Memory-/lokale Payment-Transaction-Objekt (geholt via `D8X.A00(c13g)` aus der generischen Message-Row `C13G`). `EKY.A00` konvertiert es in die Wire-Level-`PaymentInfo` (`DTS`, Abschnitt 2.8), angehängt an `WebMessageInfo.paymentInfo_`/`quotedPaymentInfo_` für History-Sync-/Companion-Export.

### 8.2 Server-gepushte Status-Updates (found, `C24410wL` "PaymentsMessageHandler")

Der client-seitige Push-Channel ist eine `<notification>`-Stanza mit einem `type`-Attribut, dispatched von `PaymentsMessageHandler.A0A`. Beobachtete `type`-Werte und ihre Handhabung:

| `type` | Handhabung |
|---|---|
| `pay` (mit `hash`) | base64-Hash dekodiert, als Side-List-USync-Refresh eingereiht (`EnumC21760rz.A0Q`, `C21820s6.A0N`-Protokoll-Set) — nutzt den USync-Mechanismus aus `WA_USYNC.md` statt den Status selbst zu tragen |
| `transaction` | parst die Transaktion via `C24880x6.A07`, loggt `onPaymentTransactionStatusUpdate`, aktualisiert das lokale `F7F`, zeigt einen Transaction-Error-String an jede angehängte UI (`InterfaceC35566Fb1.BIp`), und kann (gegated von Flags **1746** + **5049**) eine Order-Summary-„Custom Item"-Karte für einen Post-Payment-Education-Nudge bauen |
| `upi` | `consumer_status{value,dhash}` → `onPaymentConsumerStatusUpdate` (Indien-spezifischer Consumer-Eligibility-Ping, getrennt vom Transaction-Status) |
| `fbpay` | Legacy-Meta-Pay-Eligibility-Ping, gleicher Handler-Pfad wie `upi` mit anderem Offer-Map-Key |
| `account-recovery` | `service=UPI` oder `service=BR`; treibt die Indien-/Brasilien-Account-Recovery-Flows, gegated von Flags **1644**/**2000** |
| `alert`, `step_up`, `merchant_status`, `merchant-update`, `account`, `kyc-state`, `invite`, `alias`, `age_verification_update`, `document_verification_status` | diverse UI-Nudges/Compliance-Updates, kein Transaction-Status |

### 8.3 Sync-Bookkeeping (found, Preference-Key-Strings)

`payments_all_transactions_last_sync_time`, `payments_block_list_last_sync_time`, `payments_error_map_last_sync_time_millis` — periodische Full-List- und Error-Map-Syncs existieren (Consumer-Klassen in diesem Pass nicht vollständig nachverfolgt; `unknown` Kadenz).

---

## 9. GraphQL-/MEX-Payment-Operationen

### 9.1 Zwei Transporte, zwei Schemas (found)

| Schema | Transport | Anzahl (dieser Build) |
|---|---|---|
| `whatsapp` (`www`-Katalog) | Persisted-doc_id-GraphQL-POST, Transport-Mechanismus selbst `inferred` (in diesem Pass nicht bis zu einer HTTP-/IQ-Call-Site nachverfolgt) | 81 payment-getaggte Operationen |
| `whatsapp_mex` (`mex`-Katalog) | `w:mex`-IQ über die bestehende Stanza-Verbindung (`xmlns="w:mex"`) | 1 payment-getaggte Operation: `PaymentsIsAccountRecoverable` (doc_id `27351347491148282`) |

Quelle: `assets/whatsapp-android-www_client_persist_ids.json` und `assets/whatsapp-android-mex_client_persist_ids.json`, beide First-Party-deklarative Assets, zur Laufzeit gelesen (found, stärkster Tier kurz vor einem Traffic-Capture — die doc_id-Werte selbst sind nicht „tested", nur als im Build vorhanden bestätigt).

### 9.2 Repräsentative Operationen mit call-site-verifizierten Variablen (found)

| Operation | doc_id | Typ | Variablen |
|---|---|---|---|
| `GetUpiAccounts` | `25691302307224710` | Query | `bank_code`, `device_id`, `provider_type`, `account_type` |
| `CheckUpiBalance` | `37205951525662520` | Query | `credential_fbid`, `device_id`, `mpin`, `seq_no`, `upi_bank_info`, `vpa`, `cl_version`, `device_ssid`, `request` |
| `SetUpiChangeMpin` | `27149786891388216` | Mutation | `credential_fbid`, `device_id`, `new_mpin`, `old_mpin`, `seq_no`, `upi_bank_info`, `vpa` |
| `GetUpiBankList` | `27764018976534565` | Query | `account_type`, `provider_type`, `request` |
| `GetUpiToken` | `25639185495767704` | Query | `challenge`, `device_id`, `token_type`, `provider_type` |
| `UpiCreateMandate` / `UpiAcceptMandate` | `26775212245448044` / `26786867597629452` | Mutation | geteilter Caller (`C42562IuV`): `frequency_rule`, `mandate_no`, `purpose_code`, `recurrence_day`, `recurring_rule`, `ref_id`, `device_id`, `top_up_amount`, `provider_type`, `upi_banks`, `is_revocable`, … |
| `CreateEnrollment` | `34570903025891763` | Mutation | `participant_id`, `device_id` |
| `GenRaisePaymentComplaint` | `27569318002686860` | Query | `complaint_type`, `reason`, `transaction_ref_id`, `user_description` |
| `PaymentsIsAccountRecoverable` (MEX) | `27351347491148282` | Query | keine gefunden (vermutlich `{}`) |

Dass `CheckUpiBalance` eine `mpin`-Variable führt, direkt neben `cl_version` gelesen, ist konsistent mit Abschnitt 6.3: der Variablenname allein beweist nicht, dass der Inhalt vorverschlüsselt ist, aber er reist zusammen mit einem expliziten CL-Protokoll-Versionsstring, was nur Sinn ergibt, wenn der Wert aus dem CL-Exchange stammt.

**Caveat (found als Limitation, keine Finding über WhatsApp):** `GenCreatePaymentKey`, `RevokeEnrollment` und `BrSaveCPF` lösen alle zur *gleichen* geteilten Caller-Klasse (`C42325Iq9`/`C42327IqB`, `RunnableC42211IoJ`) im Source-Katalog auf, was jeden String-Literal nahe diesem Caller als „Variablen" für alle drei Ops zurückgibt — das übersammelt (z. B. Pix-spezifische Felder wie `pix_key` tauchen unter einer UPI-benannten Op auf). Die langen Variablenlisten für diese drei Operationen als verrauschte Superset behandeln, nicht als bestätigtes Per-Operation-Schema.

Die übrigen Operationen im 81-Einträge-Katalog (vollständige Liste: `UpiPauseMandate`, `UpiResumeMandate`, `UpiRevokeMandate`, `UpiRejectMandate`, `UpiExecuteMandate`, `GetUpiLiteDetails`, `GetUpiP2mConfig`, `GetUpiPurposeLimitingKey`, `GetUpiSmsContentAndVmn`, `PaymentReminderCreate/Get/Cancel/Stop`, `GetBillReceipt`, `GetBillerPlans`, Brasilien Pix (`GetPixInfo`, `GetPixBankList`, `GetMerchantPixInfo`, `CompletePixTransaction`, `GenPayWithPixPrecheck`), Biometric/Passkey (`Br*Passkey*`, `BrAuthorizeBiometricPayment`), und die `Wamo*`-Subscription-/Promo-Ops) sind mit ihren doc_ids katalogisiert, wurden aber in diesem Pass nicht einzeln gegen eine Call-Site re-verifiziert — ihr Vorhandensein als `found` behandeln (sie sind literale Einträge im 2.26.41.6-Asset), ihre exakte Request-Form als `unknown`, sofern nicht oben gelistet.

---

## 10. NPCI-OTP-Auto-Read-Regeln (Indien/UPI-spezifisch)

`assets/npci/npci_otp_rules.json` (found, 5 Regeln) wird von `org.npci.upi.security.pinactivitycomponent.C0315u` konsumiert, um während eines UPI-Flows eine 6-stellige OTP aus einer eingehenden Bank-/NPCI-SMS automatisch zu extrahieren — rein als Tipp-Komfort, es generiert, validiert oder übermittelt die OTP nicht. Alle 5 Regeln teilen `sender: ["[a-zA-Z]+"]` (alphabetischer Short-Code) und `otp: "\d{6}"`; nur die Trigger-Phrase unterscheidet sich (`"is your OTP"`, `"OTP is"`, `"one time password is"`, `"is your one time password"`, `".*OTP for Aadhaar.*"`). Der Caller kann die OTP-Digit-Count-Regex zur Laufzeit überschreiben (`\d{` + `i` + `}`), wenn er eine Nicht-Null-Länge übergibt. Ein Body mit `"Aadhaar"`/`"AADHAAR"` wird unter dem SharedPreferences-Key `otp_type_aadhaar` gecacht, sonst unter `otp_type_bank`.

Dieses Asset und die Consumer-Klasse sind unverändert gegenüber einer früheren `2.26.34.4`-Analyse; in diesem Pass nicht unabhängig Byte-für-Byte gegen 2.26.41.6 nachgediffed (`inferred` Kontinuität, nicht re-verifiziert).

---

## 11. Feature-Flags

AB-Prop-IDs, direkt in `PaymentsMessageHandler` (`C24410wL`, found Call-Sites) gelesen, sofern nicht anders vermerkt. Keine numerischen Flag-IDs wurden gefunden, die die Section-2-Proto-Felder selbst gaten (diese sind unconditional auf dem Wire); alle in diesem Pass gefundenen Flags gaten *Handling* von Server-Pushes oder UI-Nudges.

| Flag | Steuert |
|---|---|
| **1458** | entfernt einen lokal gecachten UPI-Payment-Alias, sobald der Server ihn als `deregistered` meldet |
| **1644** | UPI-Account-Recovery-Eligibility (`payments-enabled:account-recovery-enabled`) |
| **2000** | Brasilien-Pix-Account-Recovery-Eligibility (äquivalentes Gate für `service=BR`) |
| **1746** + **5049** (beide erforderlich) | Post-Transaction-„Custom Item"-/Order-Summary-Education-Karte nach einer abgeschlossenen Zahlung (BIP-Education-Nudge) |
| **12214** | Create-FB-User-Pfad während UPI-Account-Recovery (vs. direkter Recovery-Call) |
| **423** | Payments-Invite-Used-Tracking, älterer Pfad |
| **544** | Payments-Invite-Used-Tracking, zusätzlicher Pfad (zusammen mit 423 via OR geprüft) |
| **20869** | PSP-Allow-List-Check während Account-Recovery-Notification-Handling; gepaarter String-Pref `32353` (Komma-getrennte Opted-in-PSP-Liste, über eine String-wertige AB-Prop gelesen, kein numerisches Flag) |

Keine Feature-Flag-IDs wurden gefunden, die spezifisch die Indien-UPI-Onboarding-Activity-Sequenz (Abschnitt 4) oder den NPCI-CL-Device-Binding-Pfad (Abschnitt 6) gaten — `unknown`, über die obige Handler-Klasse hinaus nicht nachverfolgt.

---

## 12. Error-/Decline-Reason-Codes

### 12.1 In-Protokoll Decline/Cancel (found)

Wie in Abschnitt 2.4 festgestellt, tragen `declinePaymentRequestMessage`/`cancelPaymentRequestMessage` **nur** eine `MessageKey`-Referenz auf den ursprünglichen Request — kein Reason-Enum, kein Freitext-Feld. Ein Client, der „declined: insufficient funds" o. Ä. anzeigt, tut dies aus **lokalem** State (die eigene UI-Kopie des Senders, oder ein korrelierter späterer `transaction`-/`PaymentInfo`-Status, Abschnitt 8), nicht aus etwas, das die Decline-/Cancel-Message selbst übermittelt.

### 12.2 PaymentInfo-Status-Felder (found Existenz, unknown Mapping)

`DTS.status_` (Feld 4) und `DTS.txnStatus_` (Feld 10) sind separate enum-typisierte Felder (Abschnitt 2.8). Ihr Ordinal→Label-Mapping konnte allein aus dem Javalite-Bytecode nicht rekonstruiert werden (Enum-Konstanten-Namen sind durch die Obfuskierung der `Internal.EnumVerifier`-Klassen des Builds entfernt) — `unknown`. `futureproofed` (Feld 8, bool) ist ein bewusster Escape-Hatch, gesetzt, wenn das lokale Objekt des Senders keinen auflösbaren Amount/Currency hat, damit ein Empfänger auf einem neueren Client einen Status rendern kann, den er sonst nicht parsen könnte.

### 12.3 Server-gepushte Error-Map (found Pref-Keys, Consumer nicht vollständig nachverfolgt)

Die Preference-Keys `payments_error_code`, `payments_error_text`, `payments_error_title`, `payments_error_map_tag`, `payments_error_map_last_sync_time_millis` zeigen, dass Error-Codes gegen eine **server-synchronisierte Map** (Code → Title/Text) aufgelöst werden, nicht gegen ein festes clientseitiges Enum oder eine Stringtabelle. Das heißt, der einem Nutzer angezeigte Decline-/Error-*Text* kann sich über Zeit/Region ändern, ohne App-Update. Die Klasse, die diesen Sync durchführt, wurde in diesem Pass nicht identifiziert (`unknown`).

### 12.4 NPCI-CL-Layer-Failures (found, keine strukturierten Codes)

`BinderC48420LDc.BW1()` (Device-Integrity-Check), `CRH`/`CRh`/`CRi` (Device-Cert-/State-Validation) scheitern alle **silent** — sie geben `false` zurück bzw. werfen, ohne einen Error-Code über die AIDL-Grenze hinaus, jenseits des Booleans. Jede nutzerseitig sichtbare Message für einen CL-Layer-Failure wird daher vollständig auf WhatsApp-Seite aus dem Boolean-Resultat konstruiert, nicht aus einem von NPCI gelieferten Code (`inferred`, konsistent mit der AIDL-Interface-Form in Abschnitt 6.1, die keine Error-Code-Return-Methoden hat).

---

## 13. Indien/UPI-spezifisch vs. allgemein — expliziter Split

| Finding | Scope |
|---|---|
| Proto-Felder von `sendPaymentMessage`/`requestPaymentMessage`/`declinePaymentRequestMessage`/`cancelPaymentRequestMessage`/Split Payment/`PaymentInviteMessage`/`PaymentReminderMessage` (Abschnitt 2) | **allgemein** — gleiche `Message`-Proto-Felder unabhängig von der Rail; `payeeVpa` (Abschnitt 2.6) ist das einzige UPI-geprägte Feldname, aber das Feld selbst ist unconditional im Schema vorhanden |
| `PaymentInfo` (`DTS`) Transaction-Status-Objekt (Abschnitt 2.8, 8) | **allgemeine** Struktur; `useNoviFiatFormat` und die Legacy-Service-Codes `FBPAY`/`NOVI`/`PIX`/`UPI` zeigen, dass derselbe Objekt-/Notification-Pfad rail-übergreifend geteilt wird |
| Rail-Packages `indiaupi`, `brazilpay`, `mexico`, `indonesia`, `upr` (Abschnitt 3) | explizit nach Package gesplittet; `upr`/`common` sind rail-agnostisch, die übrigen sind Single-Country |
| VPA-Linking, UPI-Mapper-Flow, Onboarding-Activities (Abschnitt 4) | **nur Indien/UPI** |
| NPCI-„CL"-Credential-/Device-Binding-Library, RSA/AES-Krypto, OTP-Auto-Read (Abschnitte 6, 7, 10) | **nur Indien/UPI** — dieser gesamte Layer fehlt für Pix/Mexiko/Indonesien im erforschten Code |
| GraphQL-doc_id-Katalog (Abschnitt 9) | gemischt — der Katalog selbst spannt UPI, Pix, Biometric/Passkey (Brasilien) und rail-agnostische (`Wamo*`, `Gen*`) Operationen unter einem Schema; der Scope jeder Op folgt ihrem Namen/Präfix (`Br*` = Brasilien, `Upi*`/`GetUpi*`/`SetUpi*` = Indien) |
| `PaymentsMessageHandler`-Notification-Typen (Abschnitt 8.2) | gemischt — `pay`-/`transaction`-/`alert`-/`step_up`-/`account`-artige Typen sind generisch; der `upi`-Typ und `service=UPI`-Zweige sind Indien-spezifisch, `service=BR`-Zweige Brasilien-spezifisch |

---

## 14. Baileys-Hinweis

Baileys-artige Clients können die Section-2-Message-Typen konstruieren und parsen (es sind plain Protobuf-Felder auf der Standard-`Message`), und können im Prinzip die `whatsapp`-/`whatsapp_mex`-GraphQL-doc_ids mit handgebauten Variablen aufrufen. Sie **können keine** UPI-Zahlung sinnvoll abschließen: der MPIN-/Device-Binding-Exchange in Abschnitt 6 läuft über eine eingebettete, NPCI-signierte native Android-Komponente, gebunden an eine echte Bank-/NPCI-Backend-Trust-Relationship (TEE-backed RSA-Key, `CN=NPCI_CERT`), die außerhalb der offiziellen App keine Entsprechung hat. Eine Baileys-`sendPaymentMessage` ist daher eine protokoll-korrekte, aber funktional inerte Message, sofern sie nicht mit einer Transaktion gepaart wird, die tatsächlich über den echten NPCI-Flow autorisiert wurde.

---

## 15. Error Cases / Gotchas

| Symptom | Ursache | Fix/Hinweis |
|---|---|---|
| Decline-/Cancel-Message zeigt keinen sichtbaren Grund auf dem Wire | Protokolldesign (Abschnitt 2.4) — es existiert nur eine `MessageKey`-Rückreferenz | keinen Reason-Code aus der Message selbst erwarten; mit einer späteren `transaction`-Notification oder lokalem State korrelieren |
| `BW1()`-gegatete Credential-Operation scheitert ohne Error-Text | Gerät hat kein StrongBox/TEE, oder ist gerootet | nur als Boolean-Failure auf WhatsApp-Seite sichtbar; ohne zusätzliches Logging nicht von anderen CL-Failures zu unterscheiden |
| `mpin`-/`new_mpin`-/`old_mpin`-GraphQL-Variablen wirken in einem dekompilierten Call-Site-Dump wie Klartext | sie werden durch den CL-Exchange (Abschnitt 6.3) erzeugt, nicht direkt in den GraphQL-Call eingetippt | keine Klartext-PIN-Übertragung annehmen, ohne die tatsächlichen Bytes zur Laufzeit nachzuverfolgen — dieser Report behauptet nicht, das getan zu haben |
| `GenCreatePaymentKey`/`RevokeEnrollment`/`BrSaveCPF` zeigen riesige, Pix-geprägte Variablenlisten | geteilte Caller-Klasse übersammelt in der doc_id-Katalog-Extraktion (Abschnitt 9.2) | als verrauscht behandeln, pro Feld verifizieren, bevor man sich darauf verlässt |
| `txnStatus`/`status`-Enum-Werte können nicht benannt werden | obfuskierter `EnumVerifier` entfernt Konstanten-Namen | erfordert Runtime-String-Korrelation (UI-Resource-Strings auf Ordinals gemappt), in diesem Pass nicht erfolgt |

---

## 16. Key Distinctions

| Nicht verwechseln | Detail |
|---|---|
| Chat-Message-E2E vs. NPCI-Credential-Blob (Abschnitt 7) | zwei getrennte Krypto-Layer; der zweite ist nur Indien/UPI und liegt vollständig außerhalb der `Message`-Proto |
| `DTS` PaymentInfo vs. die vier Chat-Payment-Message-Typen | `DTS` ist ein History-Sync-/Status-Objekt (`WebMessageInfo.paymentInfo_`), niemals eine eigenständig sendbare Chat-Message |
| `status` vs. `txnStatus` auf `DTS` | zwei unabhängige Enums, unterschiedliche Granularität, beide auf Ordinal-Ebene in diesem Build opak |
| `www`-/`whatsapp`-Schema vs. `mex`-/`whatsapp_mex`-Schema doc_ids | unterschiedlicher Transport (Persisted-doc_id-GraphQL-POST vs. `w:mex`-IQ); fast alle Payment-Ops liegen in diesem Build auf der `www`-/`whatsapp`-Seite |
| "UPR" rail-agnostisches Onboarding vs. Indien-UPI-Onboarding | UPR (`com.whatsapp.payments.upr`) ist eine neuere, generische Shell; die Indien-spezifischen `indiaupi`-Onboarding-Activities (Abschnitt 4) sind ein separater, älterer, deutlich größerer Flow, der in 2.26.41.6 weiterhin parallel existiert |
| NPCI-„Common Library" (`org.npci.upi.*`) vs. WhatsApps eigener `com.whatsapp.payments.*`-Code | die erstere ist eine eingebettete Drittanbieter-Komponente mit eigener AIDL-Fläche; WhatsApp-Code startet sie nur und liest einen opaken String/Bundle zurück |

---

## 17. Kompletter Flow (Indien UPI, Send-Money-Fall)

```
[Payer chat]                 [WhatsApp client]                    [NPCI CL component]            [NPCI / Issuer bank]
     │ tap "Pay"                    │                                      │                             │
     ▼                              ▼                                      │                             │
 open IndiaUpiSendPaymentActivity → IndiaUpiSendPaymentToVpaFragment       │                             │
     │                              │ amount/VPA/note entered              │                             │
     │                              ▼                                      │                             │
     │                     CLRemoteService.Acc(keyCode, keyXmlPayload,     │                             │
     │                       controls, configuration, salt, payInfo, …) ──►│                             │
     │                              │                                GetCredential activity (PIN pad)    │
     │                              │                                      │ user enters MPIN            │
     │                              │                             AZO(): RSA/AES challenge-response ────►│
     │                              │                                      │◄──── signed/verified ────── │
     │                              │◄──── opaque credential blob ─────────│                             │
     │                              │                                      │                             │
     │                     build RequestPaymentMessage / SendPaymentMessage (section 2)                  │
     │                              │ amount, note, requestMessageKey, background                        │
     │                              ▼                                                                     │
     │                     chat E2E encrypt, send as normal <message>                                    │
     │                              │                                                                     │
     │                     CheckUpiBalance / SetUpiChangeMpin / mandate GraphQL op ─────────────────────► │
     │                              │          (credential_fbid, device_id, mpin blob, vpa, seq_no)       │
     │                              │◄──────────────── result / error (section 12.3 error map) ────────── │
     ▼                              ▼                                                                     │
[Payee chat]            server pushes <notification type="transaction"> ──────────────────────────────── │
     │                              │  PaymentsMessageHandler.A0A updates local F7F,                      │
     │                              │  EKY.A00 builds PaymentInfo (DTS) for history sync                  │
     ▼                              ▼
 status shown in chat        transaction row updated, payments_all_transactions_last_sync_time bumped
```

---

## 18. Unknowns

| Thema | Grund |
|---|---|
| Top-Level-`Message`-Feldnummern für `splitPaymentMessage`, `splitPaymentUpdateMessage`, `paymentReminderMessage` | Info-String-Decode in diesem Pass nicht weit genug getrieben; die eigenen Felder der Sub-Message (Abschnitt 2.5/2.6) sind davon nicht betroffen |
| `DTS.status_`/`txnStatus_`-Enum-Label-Mapping | obfuskierter `EnumVerifier`, Konstanten-Namen entfernt |
| Exakter Transport-Mechanismus für `whatsapp`-Schema-(`www`-)Persisted-doc_id-GraphQL-Calls | in diesem Pass nicht bis zu einer HTTP-/IQ-Call-Site nachverfolgt; durchgehend als `inferred` markiert |
| Consumer-Klasse(n) für die server-synchronisierte `payments_error_map_*`-Error-Map | Pref-Keys gefunden, lesende/schreibende Klasse nicht identifiziert |
| Inhalte der Packages `mexico`/`indonesia`/`dcp`/`phoenix` | Package-Existenz bestätigt, Inhalte nicht erforscht |
| Ob die GraphQL-Variablen `mpin`/`new_mpin`/`old_mpin` einen bereits NPCI-verschlüsselten Blob tragen oder zusätzlicher Schutz nur auf TLS-Ebene angewendet wird | aus dem Zweck des CL-Flows inferred, nicht durch Inspektion der tatsächlichen Runtime-Bytes bestätigt |
| Feature-Flag-IDs (falls vorhanden), die die Indien-UPI-Onboarding-Sequenz oder den CL-Device-Binding-Pfad selbst gaten | in den erforschten Klassen keine gefunden |
| Byte-für-Byte-Kontinuität von `npci_otp_rules.json` und den `.properties`-CL-Assets zwischen `2.26.34.4` (einer früheren Analyse) und `2.26.41.6` | nicht nachgediffed; die konsumierenden Klassen und das Runtime-Bundle-Key-Vokabular wurden in 2.26.41.6 unabhängig re-bestätigt, die Asset-Bytes selbst nicht |
| Tatsächliches Traffic-/Live-Transaction-Verhalten | nur statische Analyse, kein Traffic-Capture, keine Live-Transaktion durchgeführt |
