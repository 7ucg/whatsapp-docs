<!-- src-sha1: 3f456309f1ce11a70a08dd912d84e40193c760ad -->
# WhatsApp Managed Account — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-11-01
**Umfang:** das client-sichtbare „Managed Account"-System der elterlichen Aufsicht (Sponsor/Dependent-Linking, Rollen, Age Experience, PIN, Privatsphäre-Einstellungen, Unlink, w:mex-Operationen, lokaler Speicher, Feature-Flags); das separate, unabhängige Signal-Set für Geschäftsnummern, die von einem Business Solution Provider über die Cloud API betrieben werden (Verified-Name-Zertifikat-Issuer, host_storage/actual_actors-Felder, Coexistence-UI, Hosted-Multi-Device-Accounttyp); wie man beide unterscheidet

---

## 1. Was „managed" in diesem Client bedeutet

Zwei voneinander unabhängige Systeme in 2.26.41.6 verwenden eine Sprache, die ein außenstehender Leser als „managed account" bezeichnen würde. Sie teilen sich keinen Code, kein Proto, kein w:mex-Schema. Alle Aussagen sind statische Analyse der dekompilierten APK; nichts wurde auf der Leitung mitgeschnitten. Tier: **found** = im Code oder in Assets gelesen, **inferred** = aus dem Code abgeleitet, **unknown** = nicht aufgelöst.

| System | Interne(r) Name(n) im Code | Was ist „managed" | Wo | Abschnitt |
|---|---|---|---|---|
| Elterliche Aufsicht | `com.whatsapp.managedaccount.*`, `com.whatsapp.pma.*`, `com.whatsapp.pmta.*`; interne Codenamen **PAA**, **PMA**, **PMTA** (found in Package-/Klassen-/Pref-Namen, nie in Strings ausgeschrieben) | das eigene WhatsApp-Konto eines Minderjährigen ("dependent"), beaufsichtigt von einem Eltern-/Erziehungsberechtigten-Konto ("sponsor") | `w:mex`, lokales SQLite/SharedPrefs | 2-8 |
| Delegation einer Geschäftsnummer an einen Provider | kein "BSP"- oder "tech provider"-String irgendwo im Client; die UI nennt es "a secure service from Meta" oder "other companies" | eine WhatsApp-Nummer eines **Unternehmens**, deren Nachrichten über Metas Cloud-Infrastruktur und/oder einen Drittanbieter abgewickelt/gehostet werden statt über das eigene Gerät des Unternehmens | Verified-Name-Zertifikat (`w:biz`), Multi-Device-Accounttyp "hosted" | 9 |

Die String-Ressourcen `str2fc9`/`str3139` ("Managed account"), `str30ae`, `str3109`, `str439d`/`str439f` und der Einstellungsbildschirm, zu dem sie gehören, sind **alle** Teil des elterlichen Systems (Abschnitt 2). Für ein von einem BSP betriebenes Unternehmen gibt es nirgendwo im Client ein "Managed account"-Label; dieser Fall wird ausschließlich über Zertifikatfelder und Chat-/Call-Banner signalisiert (Abschnitt 9). Das ist die zentrale Korrektur, die vor der Verwendung des Begriffs zu beachten ist: Eine Reverse-Engineering-Notiz oder ein Ticket, das bei einer *Business*-Nummer von „managed account" spricht, meint Abschnitt 9 und nicht etwas im Code mit dem Namen `ManagedAccount*`.

---

## 2. Elterliche Aufsicht: Rollen und Kontobeziehung

### 2.1 Rollen

`EnumC08540Ng` (found), mit einem Debug-Label pro Konstante:

| Rolle | Debug-Label | Wer |
|---|---|---|
| `NONE` | "None" | keine Aufsichtsbeziehung |
| `DEPENDENT` | "Dependent" | das eigene Konto des Minderjährigen |
| `SPONSOR` | "Sponsor" | das Eltern-/Erziehungsberechtigten-Konto |
| `SPONSOR_ADMIN` | "Sponsor Admin" | ein Sponsor mit erweiterten Rechten (genaue zusätzliche Rechte nicht nachvollzogen) |

Die Rolle des aktuellen Geräts wird aus dem lokalen Zustand von `SharedPreferencesOnSharedPreferenceChangeListenerC08490Nb.A04()` gelesen und von `C08530Nf` gecacht („ManagedAccountStartupPreferences", Name aus dessen Log-Tag `ManagedAccountStartupPreferences/...` abgeleitet).

### 2.2 Die Beziehung ist Konto-zu-Konto, nicht Gerät-zu-Gerät

Der Dependent hat seine **eigene Telefonnummer und seine eigene vollständige WhatsApp-Registrierung** (eigenes Primärgerät, eigene Multi-Device-Companions, falls vorhanden). Der Sponsor ist ebenso ein normales, unabhängig registriertes Konto. Was beide verbindet, ist ein serverseitiger Datensatz, lokal gespiegelt als:

```
ManagedAccountConnection(
  connectionLid,      // C14080dr — the dependent's LID, found
  role,                // EnumC08540Ng, found
  linkTs,              // long, link creation time, found
  connectionPnJid,     // PhoneUserJid — the dependent's phone-number JID, found
  graduationState,      // C4DV, section 2.3
  ageExperience)        // EnumC96934Gf, section 2.3
```

(`AnonymousClass586`, found; Felder durch dessen `toString` bestätigt.) Es gibt nirgendwo in diesem Package einen Pairing-QR-Code, keine ADV-Signatur, keinen Companion-Key-Exchange — vergleiche das tatsächliche Companion-Device-Protokoll in `WA_LINKED_DEVICE_PAIRING.md` Abschnitt 5, das damit nichts zu tun hat. Der Onboarding-Einstiegspunkt ist ein Deep Link, behandelt von `ManagedAccountSponsorOnboardingViewModel` (Package `managedaccount.deeplink`, found), kein QR-Scan-Flow.

### 2.3 Age Experience und Graduation

`EnumC96934Gf` (found): `UNKNOWN`, `U13`, `U16_BR`, `U18_BR`, `U18`, `STANDARD` (Brasilien hat eigene Altersbänder). `A00()` auf diesem Enum liefert true für `U16_BR`, `U18_BR`, `U18` — die Zustände, die der Code als „kurz vor dem Herauswachsen" behandelt.

`C4DV` (Graduation State, found): `PRE_GRADUATION`, `GRADUATION`, `PRE_GRADUATION_IMMINENT`, `UNKNOWN`. `ManagedAccountGraduationManager` und sein `triggerTeenGraduationEagerly`-Pfad (found) nehmen einen Dependent aus der Aufsicht, sobald er sich einer Altersschwelle nähert bzw. sie überschreitet; `ManagedAccountPmtaSponsorGraduationNuxActivity` und `ManagedAccountSponsorGraduationNuxActivity` zeigen den sponsorseitigen NUX für diesen Übergang.

`ManagedAccountLinkingRepository.A00` (found) ruft die Age Experience bei einem HTTP-409-Konflikt des Linking-Calls erneut ab, d. h. der Server kann das Linking ablehnen, weil die gespeicherte Age Experience veraltet ist, und der Client muss `WaAgeExperienceRepository` vor dem erneuten Versuch neu abfragen.

---

## 3. Linking-Flow und w:mex-Operationen

### 3.1 Operationskatalog

Alle neun Operationsnamen und `doc_id`-Werte unten wurden direkt aus `assets/whatsapp-android-mex_client_persist_ids.json` in diesem Build gelesen (found) — nicht aus einem Drittanbieter-Client abgeleitet. Das Schema für alle neun ist `whatsapp-android-mex` (Asset-Key: `whatsapp_mex`).

| Operation | doc_id | Call Site gefunden | Variablen (dieser Build) |
|---|---|---|---|
| `ManagedAccountInitiateLinkingQuery` | `26671873552498548` | `MexManagedAccountInitiateLinkingApi.A00` | `input:{"dummy": null}` — **es wird keine `phone_number`** gesendet; eine frühere Annahme, dieser Call trage die Nummer des Dependent, trifft für diese Call-Site nicht zu |
| `ManagedAccountQuery` | `27232244463035262` | `ManagedAccountStateSynchronizer.A01` | `input:{"unused": null}` — **keine `jid`**; die Query ist sitzungsgebunden, an dieser Call-Site nicht über JID parametrisiert |
| `ManagedAccountValidateLinkingQuery` | `35449808311284430` | referenziert (Namensübereinstimmung in Assets); Variablen keiner Call-Site in diesem Build zugeordnet | unknown |
| `ManagedAccountAcceptLinkingMutation` | `26708926155457677` | referenziert; Variablen nicht nachvollzogen | unknown |
| `ManagedAccountCompleteLinkingMutation` | `26866501363013203` | referenziert; Variablen nicht nachvollzogen | unknown |
| `ManagedAccountRevokeLinkingMutation` | `27435058196100677` | referenziert; Variablen nicht nachvollzogen | unknown |
| `ManagedAccountSyncActivities` | `26594352680227840` | referenziert; Variablen nicht nachvollzogen | unknown |
| `ManagedAccountUpdatePinMutation` | `27653949584193082` | referenziert; Variablen nicht nachvollzogen | unknown |
| `ManagedAccountGetSponsorAgeVerificationInfoQuery` | `26433623289634522` | referenziert; Variablen nicht nachvollzogen | unknown |

Response-Bodies über generische Success-/Error-Wrapper hinaus wurden für keine der neun gelesen; das Success-Ergebnis von `ManagedAccountInitiateLinkingQuery` (`C135065o7`, `toString()` wörtlich `"PAA Initiate Linking Success"`, found) trägt zwei Strings und einen Int, deren Feldnamen nicht aufgelöst sind — fast sicher ein Linking-Token/Deep-Link-URL und ein Expiry, das ist aber inferred, nicht aus einem benannten Feld gelesen.

Es existiert ein separater, Nicht-mex-Pfad: `C14E.java` (`PaaAcceptLinkingIBHandler`) parst eine eingehende Stanza/Notification mit einem `sponsor_jid`-Attribut (found) — das ist ein Server-Push, der die UI anstößt, nicht der eigene Request der `AcceptLinkingMutation`.

### 3.2 Retry bei Delivery-Failure

`MexManagedAccountInitiateLinkingApi.A01` wiederholt den Initiate-Call bis zu einer vom Aufrufer vorgegebenen Anzahl bei Fehlercode **471** ("delivery failure"), mit Log `MexManagedAccountInitiateLinkingApi/requestSponsorLinkingMaterial delivery failure, retrying` (found).

---

## 4. Geräte-/Session-Modell

Es gibt **keine Companion-artige Geräteverbindung** zwischen Sponsor und Dependent, und auch keine zwischen einem der beiden Konten und irgendeiner von WhatsApp betriebenen Infrastruktur. Jede Seite ist ein gewöhnliches, unabhängig registriertes WhatsApp-Konto (eigene Telefonnummer, eigenes Primärgerät, eigene optionale Linked Devices im normalen Multi-Device-System, beschrieben in `WA_LINKED_DEVICE_PAIRING.md`). Die Aufsichtsbeziehung ist ein serverseitiger Datensatz, indiziert über die LID und die Telefonnummer-JID des Dependent (Abschnitt 2.2), über `w:mex` auf beide Seiten synchronisiert — keine neue Session, kein Pairing, keine ADV-Identität.

Das ist ein struktureller Unterschied zum BSP/Cloud-API-Fall in Abschnitt 9, wo das „Gerät" der Geschäftsnummer gar kein Telefon ist — siehe Abschnitt 9.3 dafür, wie das stattdessen im bestehenden Multi-Device-Modell dargestellt wird.

---

## 5. Einstellungen und Berechtigungen

### 5.1 Privatsphäre-Bildschirm auf Dependent-Seite

`DependentAccountPrivacyActivity` (found) gruppiert Einstellungen über das Enum `C9SE` in drei Abschnitte:

| Abschnitt | `C9SE`-Konstante | Inhalt |
|---|---|---|
| Sichtbarkeit | `VISIBILITY` (0) | wer die Profilinfos des Dependent sehen kann |
| Kontakt | `CONTACT` (1) | wer den Dependent kontaktieren kann |
| Sponsor-Kontrolle | `SPONSOR_CONTROL` (2) | Einstellungen, die der Sponsor kontrolliert, nicht der Dependent |

Der Bildschirm verlinkt über den String `str2fc8` zu „parental controls": *"Your account is managed by your parent or guardian. They can make changes in parental controls."* Für eine solche Kontrolle existiert ein lokales Pref-Gate: `privacy_dependent_account_messages` (int, Default `1`), gelesen von `C08520Ne.A06()` und nur konsultiert, wenn das Konto ein Sponsor ist (found) — d. h., wer dem Dependent schreiben darf, wird vom App-Zustand des **Sponsors** gegated, nicht von einem Wert, den der Dependent selbst setzt.

### 5.2 Sponsorseitige Kontrollen

`SponsorControlsHubActivity` (found) ist der Hub des Sponsors, der Dependents auflistet (Fragment-/Log-Tag `"sponsor-controls-dependents"`) mit einem Kontaktfoto-Adapter pro Dependent. `SponsorControlsDependentInfoActivity` öffnet das Detail eines Dependent. `ManageNotificationsActivity` / `ManageNotificationsFragment` und `ActivityAlertsFragment` / `ManagedAccountDependentActivityAlertHandler` konfigurieren und liefern **Activity Alerts** — Benachrichtigungen an den Sponsor über die App-Aktivität des Dependent (`ManagedAccountSyncActivities`, Abschnitt 3.1, ist die Datenquelle, gegated durch Flag **31562** in `ManagedAccountAlertInfoActivity`, found).

### 5.3 PIN

`SponsorPinSetupFragment`, `SponsorPinConfirmFragment`, `ManagedAccountChangePinActivity`/`ManagedAccountChangePinFragment`/`ManagedAccountConfirmChangePinFragment` (found, anhand vorhandener Klassen) implementieren das Erstellen und Ändern der vom Sponsor gesetzten PIN; die Mutation ist `ManagedAccountUpdatePinMutation` (Abschnitt 3.1; genaue Feldnamen `old_pin`/`new_pin` in diesem Build nicht bestätigt — unknown). Ein Sync auf Dependent-Seite kann speziell wegen einer fehlenden PIN scheitern: `ManagedAccountStateSynchronizer` loggt `"ManagedAccountStateSynchronizer/fetchAndSync missing sponsor PIN for child user"` und liefert ein Fehlerergebnis, wenn der Server-/Response-Typ `C135095oA` ist (found) — der State-Sync des Dependent hängt davon ab, dass die PIN des Sponsors gesetzt ist.

### 5.4 Unlink

`ManagedAccountUnlinkAccountSettingsActivity` (found) zeigt je nach Flags in den Fragment-Argumenten einen von mehreren Bestätigungstexten: `is_pmta` (eine eigene „PMTA"-Subvariante), `is_teen_dependent`, und ob der Dependent einen Push-Namen hat — Strings `str49cb`…`str49d3`, z. B. *"Your account will no longer be managed by %1$s"* / *"...by your parent"*. `ManagedAccountRevokeLinkingMutation` (Abschnitt 3.1) ist die inferred dahinterliegende Wire-Operation; dass die Activity sie direkt aufruft, wurde in diesem Durchgang nicht nachvollzogen.

### 5.5 Reauthentication-Gate

`ManagedAccountAuthInterstitialActivity` hostet `PmaAuthInterstitialFragment` (Package `com.whatsapp.pma.product.dependent.fragments`, found) und wird mit einem String `extra_auth_entry_point` gestartet — ein Re-Authentifizierungsschritt, der den Einstieg in Managed-Account-Bildschirme von einem gegebenen Entry Point aus gated. Der genaue Auth-Mechanismus (Geräte-PIN, Biometrie, Kontopasswort) wurde nicht nachvollzogen.

### 5.6 Debug-Oberflächen

`ManagedAccountDebugConnectionActivity` und `ManagedAccountDebugPinAuthActivity` existieren in diesem Build (found). Dieser Durchgang klärt nicht, ob sie aus der Release-UI erreichbar sind oder nur aus einem internen/Debug-Build-Flag (inferred: Debug-only, aufgrund der Namenskonvention und da kein Launch-Pfad aus Produktions-Bildschirmen gefunden wurde).

---

## 6. Speicher

| Store | Keys / Spalten | Inhalt |
|---|---|---|
| Lokaler Beziehungsdatensatz | `connectionLid`, `role`, `linkTs`, `connectionPnJid`, `graduationState`, `ageExperience` (Abschnitt 2.2) | eine Zeile pro Sponsor↔Dependent-Verbindung |
| SharedPrefs | `paa_graduation_nux_pending`, `paa_sponsor_blocked`, `paa_nux_education_banner_dismissed`, `paa_nux_education_banner_start_timestamp`, `paa_review_privacy_settings_banner_dismissed_dependent_<lid>`, `privacy_dependent_account_messages` | NUX-/Banner-Dismissal-Status, Sponsor-blocked-Flag, das einzige bestätigte Dependent-Messaging-Gate |

Alle Keys wörtlich gefunden in `C08530Nf`, `ManagedAccountBannerManager`, `C08520Ne`.

---

## 7. UI-Indikator-Strings

| String-ID | Text | Wo verwendet |
|---|---|---|
| `str2629` | "Create a parent-managed account" | Onboarding-Einstieg |
| `str2fc9` / `str3139` | "Managed account" | Badge/Label |
| `str30ae` | "Managed accounts can't see this message. Learn why" | eingeschränkter Inhalt |
| `str3109` | "This is a managed account. Learn more" | Chat-/Profilhinweis |
| `str3751` / `str3752` / `str3754` | Ineligibility-Meldungen ("isn't eligible for a parent-managed account", "Couldn't create parent-managed account") | Onboarding-Fehlschlag |
| `str439d` / `str439f` | "Settings for managed accounts" / "View activity and choose settings for managed accounts" | Einstellungs-Einstiegspunkt |
| `str2fc8` | "Your account is managed by your parent or guardian..." | `DependentAccountPrivacyActivity` |
| `str49cb`-`str49d3` | Unlink-Bestätigungsvarianten | `ManagedAccountUnlinkAccountSettingsActivity` |

`ManagedAccountNotAvailableActivity` und `ManagedAccountAgeUnknownActivity` (found anhand des Klassennamens) stehen für zwei weitere Zustände — das Feature wird nicht angeboten, und das Alter des Kontos ist unbestimmt — der genaue Text ist nicht aufgelöst.

---

## 8. Feature-Flags

| ID | Wo | Steuert |
|---|---|---|
| **30174** | `C08520Ne.A02`, `ManagedAccountSponsorUpsellActivity` | Sponsor-Upsell-Eligibility |
| **31562** | `ManagedAccountAlertInfoActivity` | Feature-Gate für Activity Alerts |
| **34268** | `C08520Ne.A01` | eine zusätzliche Berechtigungsprüfung (Rolle über das Gate selbst hinaus nicht aufgelöst) |
| **16763** | `C08520Ne.A04` | nicht aufgelöstes Boolean-Gate |
| **33355** | `C08520Ne.A05` | nicht aufgelöstes Boolean-Gate, abhängig von Dependent oder einem Secondary-Interface |

---

## 9. Geschäftsnummern, die an einen Provider delegiert sind (Cloud API / BSP)

Das ist das System, das tatsächlich „ein im Auftrag von einem Provider betriebenes Geschäftskonto" entspricht. Es teilt keine Klasse, kein Proto und kein w:mex-Schema mit Abschnitt 2-8. Kein String in diesem Build sagt dem Nutzer "BSP," "tech provider," "Business Solution Provider," "on-premises API," oder "Cloud API"; das Signal ist strukturell.

### 9.1 Verified-Name-Zertifikat: Issuer-Prefix und `PrivacyMode`

Der Client speichert pro Business-JID einen lokalen Verified-Name-Zertifikat-Datensatz mit den Spalten (found, `AbstractC218419al`): `verified_name`, `industry`, `city`, `country`, `verified_level`, `cert_blob`, `identity_unconfirmed_since`, `host_storage`, `actual_actors`, `privacy_mode_ts`. Diese letzten drei Felder werden aus einem Kind-Element im Stil `<biz host_storage="" actual_actors="" privacy_mode_ts=""/>` einer `w:biz`-Stanza geparst (found, mehrere Call-Sites, z. B. `O0F.java`, `C18670m9.java`, `AbstractC24816AmW.java`) in `AnonymousClass118` (laut eigenem `toString()` „`PrivacyMode`"), dessen zwei Integer-Felder sind:

| Feld | Im Code gesehene Werte | Bedeutung |
|---|---|---|
| `hostStorage` | 0 (Default/unset), 1, 2 | welche Infrastruktur die Nachrichten des Unternehmens speichert/relayt; **inferred** Mapping auf die öffentlichen WhatsApp-Business-Platform-Begriffe On-Premises (self-hosted) vs. Meta-hosted (Cloud API) vs. ein dritter, dualer/Übergangszustand — der Client hat für diese drei Werte keine benannten Konstanten |
| `actualActors` | 0 (Default/unset), 1, 2 | wer das Konto im Alltag tatsächlich betreibt; **inferred** Mapping auf self-operated vs. von einem Provider betrieben — auch hier keine benannten Konstanten in diesem Client |

Ein zweites, unabhängig gefundenes Signal am selben Zertifikat-Wrapper (`AnonymousClass119.A02()`/`A03()`) liest den **Issuer-String** des Zertifikats (Feld `A07`) und klassifiziert ihn nach Prefix (found, exakter Code):

```java
public boolean A01() { return this.A01 == 2; }        // hostStorage == 2
public boolean A02() { return this.A07 != null && this.A07.startsWith("ent:"); }
public boolean A03() { return this.A07 != null && this.A07.startsWith("smb:"); }
```

`"ent:"` und `"smb:"` sind die beiden Issuer-Prefixe, die dieser Client unterscheidet (found, literale Strings). `smb:` passt zu einem Zertifikat, das für die reguläre, selbstbetriebene WhatsApp-Business-App ausgestellt wurde; `ent:` passt zu einem Zertifikat, das für einen Enterprise-/API-integrierten Pfad ausgestellt wurde — das ist das nächstliegende First-Party-Code-Äquivalent zu „self-managed business account" vs. „BSP/Cloud-API-managed business account" (das Mapping der Prefixe auf diese zwei realen Kategorien ist **inferred**, aus den Prefixen selbst und daraus, wie sie in `AbstractC198638cc.A00` konsumiert werden — nicht aus einem In-Client-Dokumentationsstring).

`AbstractC198638cc.A00` faltet die Issuer-Prüfung und einen separaten Boolean (`A09`, Bedeutung unresolved — möglicherweise „Zertifikat fehlt/widerrufen", konsistent mit dem nutzersichtbaren Text "no longer an official business account" in Abschnitt 9.2) in einen 4-wertigen „client"-Code (found):

```java
public static final int A00(AnonymousClass119 c) {
    if (c != null) {
        if (c.A09) return 4;
        if (c.A03()) return 2;   // smb: issuer
        if (c.A02()) return 3;   // ent: issuer
    }
    return 1;                    // default / no certificate
}
```

### 9.2 Coexistence-Banner und `business_state_id`

`C198628cb` (laut eigenem `toString()` „`BusinessState`") kombiniert den `PrivacyMode` des Zertifikats (9.1), den 4-wertigen „client"-Code und einen Boolean `isVerified` zu einem einzigen flachen Integer, den die UI `business_state_id` nennt (found, gesetzt aus `c198628cb.A02()` in `EncryptionChangeDialogFragment` und ebenso gelesen in `PrivacyInfoBottomSheet`/`ContactInfoActivity`). Die Mapping-Funktion matcht 18 explizite `(client, actualActors, hostStorage, flag)`-Tupel per Pattern auf die IDs **0-17**; die vollständige Tabelle konnte nicht rekonstruiert werden (JADX meldet für genau diese Methode einen Region-Overflow-Fehler, und mehrere Zweige werden vom Decompiler zusammengeführt), aber Folgendes ist direkt aus dem Code gesichert:

- ID **15** wird immer erreicht, wenn der „client"-Code gleich 4 ist (Zertifikat fehlt/widerrufen), unabhängig von den anderen Feldern.
- IDs **5, 6, 9, 10** sind die einzigen IDs, die erreichbar sind, wenn eine Side-Gate-Methode `A05()` (eine unabhängige Block-/Mute-artige Prüfung auf dem Chat) true ist, und sind auch über den normalen Pfad erreichbar, wenn `hostStorage == 2` — diese steuern durchgängig die einfachen *"This business uses a secure service from Meta to manage this chat/call"*-Strings (`str080d`/`str080f`/`str0c9c`/`str0f5a`, found, Resource-ID-verifizierte Call-Sites in `C23324A5w`/`ContactInfoActivity`).
- IDs **16** und **17** sind die Restfälle (weder ein bekanntes Tupel noch ID 15) und steuern die Stringfamilie „multiple tools" / „no longer an official business account" (`str38ef`-`str38fb`, `str08b3`-`str08c7`): *"This business has chosen to use multiple tools to chat with its customers... Chats between only you and this business are managed by a secure service from Meta... this business is using the WhatsApp Business app"* — also der **Coexistence**-Zustand, in dem die Nummer gleichzeitig über die Business-App auf einem Gerät und über einen API-hosted Pfad erreichbar ist, gegated durch Flags **12729**, **18047**, **23933**, **7131**, **29343** (found, in `PrivacyInfoBottomSheet`/`ContactInfoActivity`, jeweils auswählend zwischen einem älteren und einem neueren Stringpaar für denselben Zustand).

Das `remove-companion-device`-IQ-Ergebnis im unabhängigen Multi-Device-Flow kann ein `coex_token`-Kind-Element tragen (`WA_LINKED_DEVICE_PAIRING.md` §7.1) — dasselbe „Coexistence"-Konzept, der Consumer wurde auch von dieser Seite nicht nachvollzogen.

### 9.3 Geräte-/Session-Modell für eine provider-gehostete Nummer

Eine vollständig von Meta gehostete Geschäftsnummer (der Cloud-API-Fall ohne jedes physische Gerät) wird innerhalb des **bestehenden** Multi-Device-Systems dargestellt, nicht in einem neuen:

- Accounttyp `HOSTED` (`EnumC32116E1o`, Wert 1) und Device-ID **99** sind für diesen Fall reserviert (`WA_LINKED_DEVICE_PAIRING.md` §5.1, §9.2).
- die `companion-props.platformType`-Enumeration, die das Primary für seine eigenen Linked Devices speichert, enthält den Wert **23 = `CLOUD_API`** (`WA_LINKED_DEVICE_PAIRING.md` §6.2), neben **27 = `BUSINESS_BACK_OFFICE`** und **25/26 = `WAIL`/`WASS`** — alles Business-Infrastruktur-Plattformtypen im selben Enum wie gewöhnliche Phones/Desktops/Web.
- der Consumer-Build in diesem Report **verweigert** aktiv das Pairing eines Hosted-Geräts von der Primary-Seite aus (lokaler Fehlercode **-10**, `WA_LINKED_DEVICE_PAIRING.md` §3.2) — Hosted-/Cloud-API-Provisioning ist nichts, das dieser Client initiiert; er beobachtet nur den resultierenden Accounttyp und die Plattform-Marker an Konten, die ihn bereits haben.

Für die BSP/Cloud-API-Beziehung selbst wurde nirgendwo in dieser APK ein Pairing-, ADV-Signatur- oder Companion-Key-Flow gefunden; die Canonical-User-/Passwort-Mechanik der Kontosicherheit (`WA_ACCOUNT_SECURITY.md`) und die Multi-Device-Identitätsmechanik haben beide nichts damit zu tun, wie ein BSP dazu kommt, eine Nummer zu betreiben — dieses Provisioning geschieht vollständig serverseitig / auf Metas Business-Plattform und hinterlässt in diesem Client keine Spur außer den oben genannten Markern.

### 9.4 Telemetrie

Das Logging-Event `wam_ts_navigation` (`C1EO`, found) trägt pro geloggter Navigation drei unabhängige Business-Kontext-Booleans: `is_cloudapi`, `is_onpremises`, `is_smb`, plus `is_canonical_ent_present` und `is_meta_ai_thread`. `ChatDescription` (`com.whatsapp.gapenforcement.dto`) trägt separat `isEnterpriseBusiness`. Keine der beiden Klassen legt offen, wie diese Booleans berechnet werden, über das in Abschnitt 9.1/9.2 bereits Beschriebene hinaus; sie sind reporting-only und gaten in den gelesenen Dateien kein nutzersichtbares Verhalten.

---

## 10. Wichtige Unterscheidungen

| A | B |
|---|---|
| "Managed account" (`ManagedAccount*`, PAA/PMA/PMTA) — das **eigene Konto eines Minderjährigen**, von einem Elternteil beaufsichtigt | eine Geschäftsnummer, **von einem Provider über die Cloud API betrieben** — für diesen Fall gibt es nirgendwo einen "managed account"-String |
| Sponsor/Dependent-Link: zwei unabhängige, normal registrierte WhatsApp-Konten, kein Device-Pairing | Hosted-Geschäftsnummer: ein Konto, `accountType=HOSTED`, Device-ID 99, überhaupt kein Companion-Device |
| `w:mex`-`ManagedAccount*`-Operationen, Schema `whatsapp-android-mex` (Abschnitt 3.1) | Verified-Name-Zertifikatfelder über `w:biz` (`host_storage`, `actual_actors`) — andere Stanza, anderes Schema |
| `business_state_id`-Coexistence-Banner (self-managed Business-App **und** API-hosted gleichzeitig) | ein rein selbstverwaltetes Unternehmen (reguläre WhatsApp-Business-App auf eigenem Gerät, Issuer-Prefix `smb:`) |
| Telemetrie-Flag `is_smb` (Small/Medium Business mit der Business-App) | Telemetrie-Flags `is_cloudapi` / `is_onpremises` (API-seitiges Hosting) |
| `ManagedAccountRevokeLinkingMutation` (beendet elterliche Aufsicht) | `remove-companion-device` (unabhängig: entfernt ein Linked Device; siehe `WA_LINKED_DEVICE_PAIRING.md` §7) |

---

## 11. Vollständige Flows

### 11.1 Elterliche Aufsicht: einen Dependent linken

```
[Sponsor]                                  [Server]                         [Dependent]
   │ deep link / in-app entry                  │                                 │
   ▼                                            │                                 │
ManagedAccountInitiateLinkingQuery (no vars) ──►│
   │◄── linking material (token/URL, expiry)    │
   │  share with dependent (deep link / code)   │
   │                                            │                                 │
   │                                            │◄── dependent opens link ───────│
   │                                            │   ManagedAccountValidateLinkingQuery {linking_token, sponsor_jid} (assets; call site not traced)
   │                                            │   ManagedAccountAcceptLinkingMutation {linking_token} (assets; call site not traced)
   │◄── notification: sponsor_jid (PaaAcceptLinkingIBHandler) ────────────────────│
   │                                            │   ManagedAccountCompleteLinkingMutation {linking_token} (assets; call site not traced)
   ▼                                            │                                 ▼
local ManagedAccountConnection row created on both sides (role=SPONSOR / DEPENDENT, connectionLid, connectionPnJid, linkTs)
   │                                            │                                 │
   ▼                                            │                                 ▼
periodic ManagedAccountQuery (no vars) + ManagedAccountSyncActivities ──────────► sponsor controls hub / activity alerts
```

### 11.2 An einen Provider delegierte Geschäftsnummer: was der Client des Gegenübers sieht

```
[Peer opens a chat/profile/call with the business number]
   │
   ▼
local verified-name cert for that JID: host_storage, actual_actors, privacy_mode_ts, issuer (smb:/ent:)
   │
   ▼
C198628cb.A02() → business_state_id (0-17)
   │
   ├─ id 15 (certificate missing/revoked)          → "no longer an official business account" (str08b3 family)
   ├─ ids 5/6/9/10 (hostStorage==2, or chat-gated)  → "uses a secure service from Meta to manage this chat/call" (str080d/f family)
   └─ ids 16/17 (coexistence residual states)       → "uses multiple tools... Business app AND a secure service from Meta" (str38ef-fb family)
```

---

## 12. Unbekanntes

| Thema | Grund |
|---|---|
| Vollständige Tupel→`business_state_id`-Tabelle (alle 18 Werte) | Decompiler-Region-Overflow bei `C198628cb.A02()`; mehrere Zweige zusammengeführt |
| Genaue numerische Bedeutung von `hostStorage`/`actualActors` über den `smb:`/`ent:`-Issuer-Prefix-Proxy hinaus | keine benannten Konstanten in diesem Client; das Mapping auf die Begriffe On-Premises/Cloud-API/BSP ist aus der öffentlichen Business-Platform-Terminologie inferred, nicht aus dem Code gelesen |
| Variablen/Response-Felder von `ManagedAccountValidateLinkingQuery`, `AcceptLinkingMutation`, `CompleteLinkingMutation`, `RevokeLinkingMutation`, `SyncActivities`, `UpdatePinMutation`, `GetSponsorAgeVerificationInfoQuery` | doc_ids in Assets bestätigt; keine Call-Site mit Variablennamen in diesem Build gefunden |
| Bedeutung des Booleans `A09`, der in „client"-Code 4 einfließt | wird nur als Gate konsumiert; kein Name oder Kommentar |
| Zusätzliche Rechte von `SPONSOR_ADMIN` vs. `SPONSOR` | Rolle existiert; unterschiedliches Verhalten nicht nachvollzogen |
| Ausschreibung der Codenamen PAA / PMA / PMTA | nie in Strings oder Kommentaren ausgeschrieben; nur Nutzungskontext |
| Erreichbarkeit von `ManagedAccountDebugConnectionActivity`/`DebugPinAuthActivity` aus Release-Builds | Namensgebung legt Debug-only nahe; kein Launch-Pfad in beide Richtungen gefunden |
| Serverseitiges Provisioning einer Cloud-API-gehosteten Nummer (Abschnitt 9.3) | vollständig serverseitig; dieser Client initiiert es nie und beobachtet nur die resultierenden Marker |
| Ob irgendein Client-Code zwischen "operated by Meta directly" und "operated by a third-party BSP via Meta's Cloud API" unterscheiden kann | beide scheinen auf dieselben `hostStorage`/`actualActors`/Platform-Type-Signale zu kollabieren; es wurde kein separates BSP-Identifier-Feld gefunden |
| Tatsächlicher Traffic | nur statische Analyse |
