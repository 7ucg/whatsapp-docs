<!-- src-sha1: 8d1c772149420abe245fd6a70c2b6615d2ab4fc5 -->
# WhatsApp Interop — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** Interoperabilität mit Drittanbieter-Chats auf Android (DMA-Stil): Feature-Gating und AB-Flags, Consent-Hinweis und Opt-in, Integrator-Liste, Interop-JID-Domains und binärer JID-Tag, Nutzer-Discovery (`w:interop` FetchUsers), `w:interop` IQ set, eingeschränkter `InteropMessage`-Plaintext und unterstützte Nachrichtentypen, Unterschiede bei Verschlüsselung und Stanza, Interop-Gruppen (MEX-Ops, Notifications, Add-Privacy), Reachability-Ping, Blockieren und Melden, Speicherung, Fehlerfälle, Unterschiede zu nativen Chats, Vergleich mit Baileys

---

## 1. Was es ist (technisch)

Interop lässt einen WhatsApp-Account 1:1-Nachrichten und Gruppennachrichten mit Accounts anderer Messaging-Apps ("Integratoren") austauschen. Der Client spricht nie mit diesen Apps. Er spricht mit den WhatsApp-Servern, die jeden Drittanbieter-Account als synthetische JID in der Domain `interop` abbilden (Gruppen: `interop.g.us`). Alle Aussagen stammen aus der statischen Analyse der dekompilierten APK; es wurde nichts auf der Leitung mitgeschnitten oder gegen einen Server ausgeführt. Tiers: **found** = in Code oder Ressourcen gelesen, **inferred** = aus dem Code abgeleitet, **unknown** = nicht aufgelöst. Obfuskierte Namen gelten pro Build und wurden in 2.26.41.6 anhand stabiler Strings neu aufgelöst (`InteropOptInManager/`, `InteropChatMessageHandler/`, `IntegratorManager/`, `w:interop`, `integrator_display_name`, `xwa2_interop_*`).

Status in diesem Build:

| Teil | Zustand in 2.26.41.6 |
|------|----------------------|
| Code | **Vorhanden und vollständig**: UI (10 Activities plus Fragments und Dialoge), IQ-Client, MEX-Gruppen- und Privacy-Ops, strikte Receive-Pipeline, Speicherung, Notification-Handler |
| Server-Schalter | **Standardmäßig deaktiviert**: Root-AB-Flag **7495** hat Default `false`; jedes im Code gelesene Interop-Flag hat Default `false` (Abschnitt 2) |
| Region | Produkttext beschränkt es auf Nutzer mit einer Telefonnummer der Europäischen Region; **keine clientseitige Länderprüfung gefunden** (Durchsetzung serverseitig inferred, über Flag 7495 und die Integrator-Liste) |
| Integratoren | **Keine hartcodiert**: kein Integrator-Name, keine feste Integrator-ID in Code, Ressourcen oder Assets; die Liste kommt vom Server (Abschnitt 4) |

| Entität | Name in 2.26.41.6 | Rolle |
|---------|-------------------|-------|
| Gate (`InteropRolloutManager`, Name aus einem Getter inferred) | `C32001Oa` | `A01` berechtigt, `A02` berechtigt und primär, `A00` Gruppen, `A03` Unified Inbox |
| IQ-Client / Builder / Parser | `DmaInteropRPCManager` (`com.whatsapp.infra.smax.generated.dmainterop.outgoing`); `C31107Dfz` (Cases 20-23), `C31106Dfy`; `C214369Ee`, `C9EQ`, `C9EP`, `C214389Eg`, `A1J` | fünf `w:interop` RPCs, striktes Schema-Parsing |
| Integratoren | `C227409sQ` Manager, `C23765ANa` Store, `A3X` (`IntegratorInfo`), `InteropUiCache` = `SharedPreferencesOnSharedPreferenceChangeListenerC20390p5` (Prefs `interop_ui`) | Liste, Opt-in-Zustand, UI-Cache |
| JIDs | `C99O` User, `C41021lm` Device, `C55529Oy6` Gruppe, `C9YC` Parser; Writer `C40411kn.A00`, Reader `C24610wf` (Tag 244) | Abschnitt 3 |
| Receive | `ENP` -> `C34471Exu` (`DecryptionCallbackInterop`) -> `C34720F4p` (`InteropChatMessageHandler`); `DTF` (Plaintext mit 9 Feldern), `EUQ` (`ParseInteropMessageParams`) | strikte Pipeline |
| Type-Registry | `C32718EOz`; `FBN` Text, `FBK` Bild, `FBL` Video, `FBJ` GIF, `FBH` Audio, `FBI` Dokument, `FBM` Reaction, `FBG` nicht unterstützt | Protobuf <-> FMessage |
| Send | `C33446EhE` (Branch), `F6P` (`E2eMessageEncryptor`), `F6K` (`<meta>`) | ausgehend |
| Gruppen / Privacy | `InteropGroupsManager`, `C3R2`, nur in Smali vorhanden `C3Rb` / `C3Qh`; `C0WQ` (Notifications); `InteropPrivacySettingsManager`, `C3Q4` / `C3Q1` / `C29664Cuh` | MEX |
| Opt-in | `C229349vm` (`InteropOptInManager`), `ARH`, `A4N`, `C224669lg` / `C24380wI` (Hinweis), `PaaInteropMigrator` | Wizard, Consent |
| Ping | anonymes `X.0xL` in `C1S0` (`InteropNotificationHandler`), ID 270 in `AbstractC32331E9w` | Notification |
| Analytics | `AnonymousClass590` | WAM 6684, 7044, 7168, 6680 |

---

## 2. Feature-Gating

### 2.1 Gate-Kette (found, `C32001Oa`)

| Methode | Bedingung | Verwendet für |
|---------|-----------|---------------|
| `A01()` | Account ist kein abhängiger Account nach Altersregeln (`C14980fa.A00` -> `C08520Ne.A03()` -> `C08530Nf.A03()` false; abhängiger Typ `EnumC08540Ng.DEPENDENT`) **und** AB **7495** | alles; Chatlisten-Ordner, Badge, Compose |
| `A02()` | `A01()` und kein Companion (`AnonymousClass091.BRD()` false, d. h. `registration_device_id` ist 0) | Opt-in-Manager, Einstellungen, Integrator-Auswahl, Notification-Handler |
| `A00()` | `A01()` und AB **15732** | Eintrag "New group", Gruppen-Privacy-Schritt |
| `A03()` | `A01()` und AB **11479** | Unified-Inbox-Schritt und kombinierte Inbox |

`InteropSettingsActivity.onResume` (ruft `finish()` auf), `InteropOptInSelectIntegratorsActivity.onCreate`, `InteropOptInManager` und der `w:interop` Notification-Handler prüfen `A02()` erneut.

### 2.2 AB-Flags (found: ID, Default und Aufrufstellen; Namen aus der Namenstabelle eines älteren Builds, per ID zugeordnet, **inferred**)

| Flag | Alter Name (inferred) | Default | Gelesen in | Steuert |
|------|-----------------------|---------|------------|---------|
| **7495** | `IS_USER_INTEROP_ELIGIBLE` | false | `C32001Oa.A01`, `C224669lg.A01`, `C230679y0` (Badge), `RunnableC23952AUh` (Home), `C0Y5` | Root-Gate; Badge-Zustand der Startseite |
| **15732** | `INTEROP_GROUP_MESSAGING_ENABLED` | false | `C32001Oa.A00` | Gruppenerstellung, Gruppen-Privacy-Schritt |
| **11479** | `WA_INTEROP_UNIFIED_INBOX_ENABLED` | false | `C32001Oa.A03`; ID zusätzlich in `C33251Ee2` registriert | Inbox-Typ-Schritt, kombinierte Inbox |
| **25512** | `INTEROP_CONTACT_MASTER_ENABLED` | false | `C0ZT`, `C51044MkK`, `C201508iH`, `C93z`, `InteropSelectChatTypeActivity` | Eintrag "New contact", gespeicherte Interop-Kontakte, Namensauflösung |
| **5760** | `INTEROP_PROTOBUF_VALIDATION_ENABLED` | false | `ENP.A00` | leitet Interop-JIDs in die strikte `InteropMessage`-Pipeline (8.1) |
| **38723** | unbenannt | false | `EA0.A00` (Descriptor) | Sender-Key-Distribution in Interop-Gruppen (Log-String `interop_group_skdm_processing_enabled`) |
| **23701** | `DMA_INFLATE_VIEW_ONDEMAND_ANDROID` | true | `C1R9` | bedarfsgesteuertes Inflating des Interop-Headers der Chatliste |

Mit Defaults definiert, aber ohne gefundenen Literal-Reader (Verwendung unknown): **3953** `INTEROP_CLIENT_UX_ENABLED`, **5759** `INTEROP_BOOTSTRAP_ENABLED`, **6613** `INTEROP_WS8_ENABLED`, **18670** `INTEROP_ADD_GROUP_PARTICIPANT_CLIENT_ENABLED`, **20999**, **11518**, **13532**, **14070** (alle false); **22752**, **24016**, **24256**, **23652**, **24275**, **24098** (`DMA_*` UI-Tuning, alle true). Flag **11619** (`ENABLE_DMA_GROUP_JID`) hat keinen Eintrag in den Default-Tabellen. Mechanismus: WA_AB_PROPS.md.

### 2.3 Gates ohne AB-Flag (found)

- Consent-Hinweis **20240306** bei Stage **160** (`C24380wI.A0D`): Die Einstellungen zeigen den Konfigurationsbildschirm nur, wenn akzeptiert, sonst den Opt-in-Einstiegsbildschirm (5.1).
- Abhängiger Account (`C14980fa`): nicht berechtigt; `PaaInteropMigrator` verlässt Interop-Gruppen und setzt den Hinweis zurück (5.5).
- Primärgerät (`A02()`): Companions können nicht opt-in oder konfigurieren.

---

## 3. Identität: JIDs und Domains

### 3.1 Domains (found)

| Art | Klasse | JID-Typ | Format | Validierung |
|-----|--------|---------|--------|-------------|
| Interop-User | `C99O` (`InteropUserJid`) | **22** | `{integrator}-{account}@interop` | ein Bindestrich (der letzte trennt); Integrator 1-3 Ziffern, keine führende `0`, als int geparst; Account 1-15 Ziffern, keine führende `0` |
| Interop-Device | `C41021lm` | **23** | `{integrator}-{account}:{device}@interop` | Device-Index muss **0** sein, sonst `C09B` ("Interop device JIDs must have device index 0") |
| Interop-Gruppe | `C55529Oy6` (`GroupJid`) | **28** | `{gid}@interop.g.us` | gid 1-20 Ziffern, erste Ziffer 1-9, kein `-` |

- `C0DZ.A0W` = Typ 22, `A0X` = 22 oder 23 (1:1), `A0V` = 28, `A0U` = `A0X` oder `A0V` (jeder Interop-Chat); in 128 Klassen verwendet. `C41021lm.getRawString()` gibt immer `:0` aus. Die Factory (`UserJid.JID_FACTORY.A04(str, "interop")`, `C9YC.A00`) wirft bei jeder Regelverletzung `C09B` ("Invalid interop JID: ...").
- Integrator-IDs in IQ-Responses sind auf 1-999 begrenzt (entspricht der 3-Ziffern-Regel). Gruppen-IDs haben nicht die alte Form `creator-timestamp`; MEX-Gruppen-Ops nehmen die gid ohne Domain (`InteropGroupsManager.A00` entfernt `@...`).

### 3.2 Binärer Token (found)

Tag **244** `JID_INTEROP` (Writer `C40411kn.A00`, Attribut-Reader `C24610wf`): String `user` (Account-ID, bei Gruppen die gid) -> u16 **device** -> u16 **integrator** -> Byte **domain**.

Domain-Byte: **0** = `interop`, **2** = `interop.g.us`; jeder andere Wert wirft ("invalid domain received for JID_INTEROP tuple"). Ein Gruppen-Tupel muss device 0 und integrator 0 tragen (sonst "invalid interop group jid"). Der Reader rendert Domain 0 als `{integrator}-{user}[:{device}]@interop` (device entfällt bei 0). Tag **245** (eine separate Interop-JID-Form in anderen Clients) hat in diesem Build keinen Handler (grep über `C24610wf` / `C40411kn`).

### 3.3 Mapping und Anzeige (found)

| Thema | Fakt |
|-------|------|
| LID / PN | `WaJidMapRepository/setJidMapping refused mapping for interop JID`; eine Interop-JID ist ihre eigene Signal-Adresse und Chat-ID |
| Name | Namensquelle `INTEROP_NAME` (`C0Y7`), Wert aus dem Feld `display_name` des Kontakts (`c06290Dn.A07().A00.A0b`); der Stanza-Parser der Nachricht liest `notify` und `display_name` bei jeder Nachricht (`AbstractC33377Eg6.A02`); Verwendung von `display_name` für Interop-Push-Namen inferred |
| Gruppenmitglieder | `w:g2` Participant-Parsing behält die Interop-JID im Participant-Record (`C23201A1a` -> `C228499uF.A00(c99o, ...)`), dazu `display_name`, `lid`, `phone_number`, `join_time` |
| Profildaten | kein Profilbild und kein Name: "Profile name and photo are not available in third-party chats" (String); nur Integrator-Icon (8-MiB-Cache `cache/interop_image_cache`, Loader `interop_image_loader`) |

---

## 4. Integratoren

### 4.1 Modell (found)

Weder Integrator-Name noch feste ID noch eine Tabelle der Identifier-Typen existieren in Code, `res/` oder `assets/`; der Server bestimmt, welche Integratoren existieren, ihre IDs, Namen und Gruppenfähigkeit. `A3X`: `A00` ID, `A03` Name, `A02` Status (`ONBOARDING`, `ACTIVE`, `REMOVED`), `A04` Icon-URL, `A05` optedIn, `A01` Identifier-Typ (`USERNAME`, `PHONE`, `EMAIL`), `A06` supportsGroupMessaging. Integrator einer JID: `C99O.A00` -> `C227409sQ.A00` -> `A3X`.

### 4.2 Fetch (found, `C31107Dfz` Case 20, Parser `C214369Ee`)

Request `<iq type="get" xmlns="w:interop" to="s.whatsapp.net" id=".."><integrator fetch="all"/></iq>` (`to` = Server-JID, Klasse `C19380nJ.A00`). Result: `<integrator_list opted_in="true"><integrator id status identifier_type name icon opted_in><features group_messaging/></integrator>...</integrator_list>` (Attributnamen gefunden; die Form des `features`-Nodes ist aus dem Pfad `features/group_messaging` inferred).

Attribut-Mapping: `status` = `onboarding` / `active` / `removed`; `identifier_type` = `username` / `pn` / `email`; `features` -> `group_messaging` = `true` / `false`; `opted_in` Default `true`. Parser-Grenzen: 0-999 Integratoren, ID 1-999; ein Eintrag ohne `name` oder `icon` wird verworfen; unbekannter Status oder Identifier-Typ wirft. IQ-Fehler: `bad-request` (400), `internal-server-error` (500) (`A1J.A02` / `A04`).

Die Refresh-Coroutine (`C24110Aar` Case 34, Log `IntegratorManager/refreshIntegrators`) schreibt die Tabelle (5.6) und die Pref `group_capable_integrators`. Gefundene Trigger: Öffnen des Opt-in-Bildschirms; der generische `<ack error>`-Handler (`C13X`) löscht alle `integrator_display_name`-Zeilen, wenn eine Interop-1:1-Nachricht abgelehnt wird (`C24110Aar` Case 35). Weitere Trigger wurden nicht aufgelöst.

---

## 5. Consent, Opt-in, Einstellungen

### 5.1 Consent-Hinweis (found)

Hinweis-ID **20240306** ist eine Privacy-Disclosure (`C24380wI`, Klasse `PrivacyDisclosureDataManager`). Stage **160** = akzeptiert (`A0D`); Stages 105-399 zählen als "eligible/shown" (`A02`). `InteropOptInManager.A01` (`C229349vm`):

```
A02() false -> log "interop is not enabled, stop"
notice 20240306 != 160 -> render notice (C32411Pr.A05); ARH.onUserOptedIn sets has_previously_onboarded and continues; dismiss / deny / error stop
else -> InteropOptInSelectIntegratorsActivity(entryPoint)
```

Stage **162** wird von `PaaInteropMigrator` geschrieben (`C24380wI.A09(null, 20240306, 162, false)`); Bedeutung unknown (nicht 160, der Hinweis zählt danach also als nicht akzeptiert).

### 5.2 Wizard (found, `A4N`, `InteropOptInSelectIntegratorsActivity`)

```
Select integrators (list from table, header "Select the third-party apps you want people to message you from.")
   ▼
[AB 11479] Unified inbox option (COMBINED | SEPARATED) ──► else skip
   ▼
[AB 15732] Group privacy setting ("Who can add me to third-party groups") ──► else skip
   ▼
InteropOptInManager.A01: notice not accepted -> consent notice (5.1); accepted -> straight on
   ▼  onUserOptedIn
SetOptInIntegrators IQ (full list)
```

Ist der Hinweis bereits akzeptiert (Bearbeiten aus den Einstellungen), blendet der Auswahlbildschirm seine Cancel- und Continue-Buttons aus und `C201718ig.A00` speichert direkt (Speichern bei Änderung inferred); Inbox-Typ und Gruppen-Privacy sind separate Zeilen des Config-Fragments. Der Gruppen-Privacy-Schritt endet inferred in `A01` (Log `BaseInteropOptInViewModel onOptInContinue`). Einstiegspunkte sind ein int (`entryPoint`), der an WAM geloggt wird (5.6).

### 5.3 SetOptInIntegrators (found, `C31107Dfz` Case 23, Parser `C9EP`)

```xml
<iq type="set" xmlns="w:interop" to="s.whatsapp.net" id=".."><opt_in_integrators><integrator_list>
  <integrator id="12"/> ...      <!-- 0..999 entries, the full desired state -->
</integrator_list></opt_in_integrators></iq>   <!-- result: integrator_list/integrator[@id], each with an optional error child -->
```

Client-Behandlung (`C24113Aau` Case 40): Fehler pro Integrator werden gesammelt; die Tabelle wird in einer Transaktion neu geschrieben (`opt_in_status` für alle gelöscht, dann gesetzt für die angeforderten minus die fehlgeschlagenen IDs). Opt-out hat keine eigene Stanza: Die Opt-out-Dialoge und der "turn off"-Pfad nutzen dasselbe Set mit kürzerer Liste (inferred aus dem Fehlen jeder anderen Opt-out-Stanza; der Pfad mit leerer Liste wurde nicht verfolgt).

UI-Fehler-Mapping (`InteropOptInSelectIntegratorsActivity.A0X`): Codes **500**, **810**, **800** -> "Apps can't be saved right now. Please try again later."; jeder andere oder null-Code -> "Apps can't be saved right now."

### 5.4 Einstellungsbildschirme (found, `AndroidManifest.xml`)

Bildschirme (alle in `AndroidManifest.xml`): `InteropSettingsActivity` mit Main- / Optin- / Config-Fragments (Einstieg, wenn der Hinweis nicht akzeptiert ist, sonst Konfiguration; Hilfe-FAQ `317021344671277`); `InteropOptInSelectIntegratorsActivity` (Apps); `InteropUnifiedInboxOptionActivity` ("Manage inbox", COMBINED vs SEPARATED); `InteropGroupPrivacySettingUpdateActivity` und `...AddBlocklistPickerActivity` (9.4); `InteropReachNotificationSettingsActivity` ("Third-party chat requests", 6.3); `InteropOptOutDialogFragment` / `...IntegratorDialogFragment` ("Turn off third-party chats?"); `InteropConversationsActivity` (Ordnerliste); `InteropComposeSelectIntegratorActivity`, `...EnterInfoActivity`, `InteropSelectChatTypeActivity` (neuer Chat / Gruppe / Kontakt).

### 5.5 Opt-out und Migrator (found)

Opted out: bestehende Chats werden schreibgeschützt (Composer-Banner "Third-party chats are turned off. You can't send messages in this chat, and you won't receive messages."). `PaaInteropMigrator` (`C0q`): läuft, wenn der Account ein abhängiger Account ist (`C20K.A1W` = restricted) **und** der Hinweis akzeptiert ist; er ruft `LeaveInteropGroup` auf (`groups_to_leave`, Response-Codes in {200, 400, 401, 403, 404, 405} gelten als erledigt) und schreibt dann Hinweis-Stage 162. Die Auflösung von "PAA" ist inferred (Altersregeln); die Verbindung zum abhängigen Account ist found.

### 5.6 Gespeicherter Zustand und Analytics (found)

| Store | Keys / Schema |
|-------|---------------|
| Prefs `interop_ui` | `unified_inbox_option` (UNKNOWN / COMBINED / SEPARATED), `who_can_add_me_to_interop_groups` (int), `who_can_add_me_to_interop_groups_hash`, `who_can_add_me_to_interop_groups_deny_list` (Set), `optedInIntegratorNames` (Set) + Namens-Keys pro ID, `interop_reach_enabled` (Default true), `interop_reach_integrators` (int-Array), `interop_reach_notifs` (Set aus `id:name:display_name:t`), `suspended_interop_groups` (Set von gids), `has_previously_onboarded`, `group_capable_integrators`; Prefs `interop_badge_prefs`: `pref_interop_badge_disabled`, `pref_interop_badge_account_state`, `pref_interop_badge_third_party_chats_state` |
| Tabelle `integrator_display_name` | `integrator_id` INTEGER PK, `display_name` TEXT, `status` INTEGER, `icon_path` TEXT Default `''`, `opt_in_status` INTEGER Default 0, `identifier_type` INTEGER Default 0, `group_messaging_supported` INTEGER; Index `integrator_opt_in_index` auf `opt_in_status` |
| weitere Tabellen | `wa_block_list_interop` (Unique-Index auf `jid`); `wa_address_book`-Zeilen mit `raw_contact_id = -5` und `jid LIKE '{id}-%@interop'` (`SAVED_INTEROP_CONTACTS`), nicht in die Kontakte des Telefons geschrieben |
| WAM | 6684 (Banner-Auslieferung), 7044 (Onboarding-Flow, Session-ID `InteropOnboardingSessionIdManager`), 7168 (User-Aktion), 6680 (Third-Party-Inbox); Event 1158 trägt `interopContactsSize`, `interopContactsSizePerIntegrator` |

---

## 6. `w:interop` IQ set

Die fünf RPCs von `DmaInteropRPCManager` laufen über `MessageClientSmaxWrapper`; jede IQ trägt `type`, `xmlns="w:interop"`, `to` = Server-JID, `id`.

| Operation | Typ | Body | Limit | Result |
|-----------|-----|------|-------|--------|
| FetchIntegrators | get | `<integrator fetch="all"/>` | - | 4.2 |
| FetchUsers | get | `<users><user external_id integrator_id/></users>` | **1-20 User** | 7.2 |
| SetOptInIntegrators | set | `<opt_in_integrators><integrator_list><integrator id/>` | 0-999 | 5.3 |
| GetReachabilitySettings | get | `<reachability_settings/>` | - | 6.3 |
| SetReachabilitySettings | set | `<reachability_settings enabled="true\|false"><integrator id/>...` | 0-999 | Result / Fehler |
| Block / Unblock | set | `<blocklist><item action="block\|unblock" jid="{interop JID}"/></blocklist>` | - | Result; Fehler `IQErrorBadRequest`, `IQErrorInternalServerError` |

### 6.1 Blockieren und Melden (found)

Interop-Block nutzt `xmlns="w:interop"` (`C31106Dfy`, Helper `C9EF`, Log `InteropBlocklistHelper/getInteropBlocklist/error code:`) und die Tabelle `wa_block_list_interop`. UI: "Blocked in third-party chats"; der Block-Dialog sagt, dass auf WhatsApp blockierte Personen den Nutzer in der Drittanbieter-App weiterhin erreichen können. Spam-Meldung nutzt den generischen Spam-Flow (`spam_flow`, `C9E2`) mit Dialogtext pro Integrator. Notification-Routing: `AbstractC32331E9w` ordnet xmlns `w:interop` dem Handler-ID **270** zu; `EnumC32096E0u.NOTIFICATION_W_INTEROP` = `"w:interop"`.

### 6.2 Ping-Notification (found, anonymes `X.0xL` in `C1S0`)

`<notification xmlns="w:interop" t=".."><ping display_name=".."><X id=".." name=".."/></ping></notification>` (der Tag `X` des ersten Kindes von `ping` wird vom Code nicht geprüft).

Nur ein erstes Kind namens `ping` wird akzeptiert (sonst Log `unknown tag=`). Bei `A02()` true hängt es `id:name:display_name:t` an die Pref `interop_reach_notifs` an, postet eine lokale Notification auf dem Channel `critical_app_alerts@1` (Body "Chatting with people on third-party apps is an optional WhatsApp feature in the European Region.", Aktion "Manage requests", Dismiss-Receiver `InteropNotificationDismissReceiver`) und loggt WAM 6684. Der Server-Trigger (jemand von einem Integrator hat versucht, den Nutzer zu erreichen) ist aus dem Einstellungstext "Get notified when someone wants to message you from a third-party app." inferred.

### 6.3 Reachability (found)

Einstellungen gelten pro **Integrator** (Kinder `<integrator id>`, Grenze 0-999), nicht pro User. Der Default von `enabled` ist `true` in `interop_reach_enabled`. Es wurde kein Presence-Subscription-Code für Interop-JIDs gefunden (inferred: Reachability ersetzt ihn).

---

## 7. Nutzer-Discovery

### 7.1 FetchUsers (found, `C31107Dfz` Case 21, Parser `C9EQ`)

Interop-JIDs kommen nur aus dieser IQ; USync hat kein Interop-Protokoll (WA_USYNC.md).

```xml
<iq type="get" xmlns="w:interop" to="s.whatsapp.net" id=".."><users>
  <user external_id="alice@example.org" integrator_id="12"/>          <!-- 1..20 -->
</users></iq>
<!-- result -->
<users>
  <user jid="12-105012705411308@interop" external_id=".." normalized_external_id=".." integrator_id="12"/>
  <user external_id=".." normalized_external_id=".." integrator_id="12"><error code="404" text="item-not-found"/></user>
</users>
```

Ergebnisse pro User: Erfolg `user[@jid]` (`C9DG`, jid als `C99O` geparst); `item-not-found` Code-Default **404** (`C9DH`); `forbidden` Default **403** (`C9DF`); `internal-server-error` (`C9DE`).

Fehler der gesamten IQ: `bad-request`, `internal-server-error`. Ergebnislisten in `C9FA`: not found, forbidden, Server-Fehler, aufgelöste Map `{(external_id, integrator) -> UserJid}`. Request und Response lehnen 0 oder mehr als **20** User ab.

### 7.2 Identifier-Eingabe und gespeicherte Kontakte (found, `InteropComposeEnterInfoActivity`)

| Identifier-Typ | UI | Als `external_id` gesendeter Wert |
|----------------|----|-----------------------------------|
| `USERNAME` | ein Feld ("Enter Username") | Text |
| `PHONE` | Länderauswahl + Nummer | Ländercode und Nummer verkettet (Filter pro Zeichen, Regel nicht verfolgt) |
| `EMAIL` | ein Feld | Text |

Ablauf: App wählen (`InteropComposeSelectIntegratorActivity`, opted-in Integratoren aus der Tabelle) -> Chat-Typ (`InteropSelectChatTypeActivity`: "New chat", "New group" bei AB 15732 und wenn der Integrator Gruppen unterstützt, "New contact" bei AB 25512) -> ID eingeben -> FetchUsers -> Chat auf der zurückgegebenen JID öffnen. Strings: "This user can't be found" (nicht gefunden), "This user is already a group member" (Gruppen-Add), "Couldn't create the chat. Please try again.".

Mit AB 25512 löst `ContactFormActivity.verifyInteropIdentifierAndSave` die ID über FetchUsers auf (`C24113Aau` Case 41) und speichert eine `wa_address_book`-Zeile (raw_contact_id -5); "Usernames and contacts added to third-party chats will not save to your phone."

---

## 8. Messaging

### 8.1 Pipeline-Auswahl (found)

Entschlüsselung (`ENP.A00`): Ist AB **5760** an und erfüllt die Chat-JID `A0U` (Interop-1:1 oder Interop-Gruppe), wird der Ciphertext von `C34471Exu` (`DecryptionCallbackInterop`) behandelt; sonst laufen die regulären Callbacks. Von `ENP` behandelte Ciphertext-Typen sind die üblichen: **0** (`msg`), **1** (`pkmsg`), **2** (`skmsg`, Sender Key), **4** (Bot-Pfad, nicht Interop). Interop nutzt also dieselben Signal-Sessions und Sender Keys wie native Chats.

```
<message from="12-123[:0]@interop" ..><enc type=pkmsg|msg|skmsg v=2>...</enc></message>
   │  ENP.decryptMessage (Signal / sender key)
   ▼
C34471Exu.handlePlaintext
   │  remove padding (last byte = pad length; empty / zero / >= length fails, log DecryptUtil/removePadding)
   │  C33369Efy.A03(E0T.INTEROP_MESSAGE, ...)          ── message pipeline type "interop_message"
   ▼
C34720F4p (InteropChatMessageHandler)
   │  parse bytes as DTF (InteropMessage subset)
   │  unknown-field check -> failure 70
   │  C32718EOz.A00(EUQ) -> FMessage via type handlers; SKDM (group) processed if AB 38723
   ▼
store, receipt, notification
```

Fehlerreporting: `C34720F4p.A00` gibt `C33063Eaz(reason)` zurück und ruft auf dem Receipt-Pfad `A0Y(null, key, reason, 491)` auf; `C34471Exu` ruft bei ungültigem Plaintext `C33369Efy.A07(.., 491, reason, ..)` auf. Das Literal **491** ist beiden gemeinsam (Bedeutung ungeklärt).

### 8.2 `InteropMessage`-Plaintext-Teilmenge (found, `DTF`)

Der Plaintext ist **nicht** die vollständige `Message`. `DTF` deklariert genau diese Felder, nummeriert wie die vollständige `Message`:

| Feld | Nummer | Typ | Handler | Hinweise |
|------|--------|-----|---------|----------|
| `conversation` | **1** | string | `FBN` | einfacher Text |
| `senderKeyDistributionMessage` | **2** | message | `C34720F4p` | Gruppen-ID + Axolotl-SKDM; die Gruppen-ID muss dem Chat entsprechen, wenn der Chat eine Gruppe ist |
| `imageMessage` | **3** | message | `FBK` | |
| `extendedTextMessage` | **6** | message | `FBN` | Link-Preview-Felder |
| `documentMessage` | **7** | message | `FBI` | nicht, wenn Stanza-`type` `medianotify` ist |
| `audioMessage` | **8** | message | `FBH` | Sprachnachrichten über `ptt` |
| `videoMessage` | **9** | message | `FBL` (ohne `gifPlayback`) / `FBJ` (`gifPlayback`) | |
| `reactionMessage` | **46** | message | `FBM` | |
| `ptvMessage` | **66** | message | keiner gefunden | vom Schema akzeptiert und auf unbekannte Felder validiert; in der Registry existiert kein FMessage-Parser (Video-Note-Empfang ungeklärt) |

Die Unknown-Field-Prüfung liest den Unknown-Field-Count per Reflection aus `DTF` und aus den Sub-Messages Bild, Video, PTV, Audio, Dokument, Extended Text und Reaction; ein Count von 1 oder mehr liefert Failure **70**. Felder außerhalb von `DTF` lassen die Nachricht daher fehlschlagen: zum Beispiel `messageContextInfo` (35), `protocolMessage` (12), Sticker, Kontakt, Standort, Umfrage (inferred aus dem Schema; die Wirkung eines einzelnen Feldes wurde nicht ausgeführt).

### 8.3 Unterstützte Nachrichtentypen und Limits (found)

| Typ | Beim Empfang durchgesetzte Regeln (Failure-Reason) |
|-----|-----------------------------------------------------|
| Text, Video | `conversation` oder `extendedTextMessage.text`, gekürzt auf **65536** Zeichen; Link-Preview nur, wenn `matchedText` eine gültige, im Text enthaltene URL ist; Titel und Beschreibung auf 65536 gekürzt; Preview-Typ auf 0, 1, 4, 5, 6, 7 gemappt; Video und GIF teilen den Media-Parser `C33395EgO.A05` (`gifPlayback` wählt `FBJ`) |
| Bild | `mediaKey` erforderlich (16); `fileLength` >= 0 (13); `fileSha256` 32 Bytes (14); `fileEncSha256` 32 Bytes, falls gesetzt (14); Mime **nur `image/jpeg` oder `image/png`** (17); `directPath`, Breite, Höhe werden kopiert; Thumbnail-Triple (Direct Path, SHA, Enc-SHA) optional; Progressive Scans werden akzeptiert, wenn 2-20 Scan-Längen vorliegen, `scansSidecar`-Länge / 10 der Anzahl entspricht und die Summe in ein int passt |
| Audio | `mediaKey` erforderlich (16); `fileLength` > 0 (13); Hashes 32 Bytes (14); Mime muss ein bekannter Audio-Typ sein (17); `ptt`-Flag; `waveform` nur bei 1-192 Bytes behalten; `backgroundArgb`; `seconds` |
| Dokument | `mediaKey` erforderlich (16); `fileLength` >= 0 (13); Hashes 32 Bytes (14); `title` auf 65536 gekürzt; JPEG-Thumbnail wird behalten, wenn es die Größenprüfung besteht |
| Reaction | `key.id` und `key.remoteJid` nicht leer; `text` plus eine Edit-Version ungleich null wird abgelehnt (Warnung `edit version and text message are both set`); `senderTimestampMs` bleibt erhalten; eine Stanza mit `type="reaction"` muss eine Reaction-Nachricht ergeben (sonst Failure **76**) |
| Reply / Quote | `ContextInfo` mit `stanzaId`, `participant`, zitierter Nachricht (erneut als `DTF` geparst, `ContextInfoProtobufInterop`), `quotedType`; auf der Senderseite serialisiert `InteropContextInfoBuilder` die zitierte Nachricht rekursiv |

Nicht akzeptiert (außerhalb der 9 Felder): Sticker, Kontakte, Standorte, Umfragen, Events, Templates, View-once. Der Attachment-Picker blendet für Interop-Chats die Einträge Kontakt, Standort, Umfrage, Event, Gruppenstatus, Imagine, Zahlung, Pix und Überweisung aus (Prüfungen `A0L`, `A0M`, `A0P`, `A0Q`, `A0R`, `A0T`, `A0U`, `A0X` von `ConversationAttachmentContentView`); Dokument, Kamera, Galerie und Audio werden nicht durch Interop-Prüfungen gesperrt (Verbleib inferred). Verschwindende Nachrichten werden nicht unterstützt ("disappearing messages are not supported in third-party chats", auch von der Default-Timer-Einstellung ausgenommen). Media-Bytes laufen über den normalen WhatsApp-Media-Pfad (Key, Hashes und `directPath` in der Nachricht; Analytics-Wert für die Download-Herkunft 15 = `interop`).

### 8.4 Senderseite (found)

| Schritt | Verhalten |
|---------|-----------|
| Serializer | `C33446EhE`: Chat-JID-Typ 22/23 (`A0X`) nutzt den Interop-Serializer (`C32718EOz.A01` mit `ADs` pro Typ, loggt `buildE2eInteropMessage`); andere Chats nutzen den regulären Builder, daher nehmen Interop-**Gruppen** (Typ 28) den regulären Builder |
| Nicht unterstützte FMessage-Klasse | Handler `FBG` -> wirft `E3G` 70 vor dem Senden; falsche Klasse für einen Handler -> `E3G` 0 |
| Bild-Prüfungen | Mime `image/jpeg` oder `image/png`, sonst `E3G` 17 (`null` wird zu `image/jpeg`); Hash nicht 32 Bytes `E3G` 14; fehlender Media Key `E3G` 16; Stanza-Contributors `F6B`, `F6G`, `F6I`, `F68`, `F69`, `F6H`, `F6M`, `F6X` haben keinen Interop-Branch (Attachment ungeklärt) |
| Encryptor (`F6P`) | für Interop-Chats (`A0U`) überspringt der Encryptor `C33284Eea.A02` (fügt Device-List-Metadaten über `AbstractC30999De0.A03` hinzu, inferred) und überspringt `paddingBytes` (Größe aus AB 1723) |
| `<meta>` (`F6K`) | `content_type="add_on"` wird für Interop-Chats übersprungen |
| Reporting-Token (`F6L`) | übersprungen, wenn das Ziel eine Interop-Device-JID ist |
| Device-Liste / ADV | Interop-Device-Index ist immer 0; `DeviceADVInfoHandler` hat am Eingang eine Interop-Prüfung (`C24230w2`, vorzeitiger Ausstieg inferred); Multi-Device-Fan-out ist nicht möglich (inferred: ein Device pro Kontakt) |

Weitere Unterschiede zu nativen Nachrichten: Interop-Chats nutzen den Pipeline-Typ `interop_message` (`E0T`) statt der Typen Text / Media / Reaction; WAM-Chat-Typ-Wert 5 im Decrypt-Event (`AbstractC33424Egr`) und 6 im `FNR`-Event (nativ 3 / 1); Message-Secret-Add-ons (Poll-Votes, verschlüsselte Reactions, siehe WA_MESSAGE_SECRETS.md) gehören nicht zu den 9 Feldern und können Interop-Chats daher nicht erreichen (inferred).

---

## 9. Interop-Gruppen

### 9.1 Modell (found)

Eine Gruppe ist `{gid}@interop.g.us` (Typ 28). Mitglieder sind WhatsApp-Accounts (als **LID**-User-JIDs hinzugefügt; auf dem Add-Pfad found, der Create-Pfad inferred gleich) und Interop-JIDs. Gruppen-Metadaten kommen aus MEX statt aus `w:g2`: `C11410Yt.A0F` ruft für Typ 28 `GroupXmppMethods/sendGetInteropGroupInfo` auf. Der Zustand ist `UNSET`, `ACTIVE`, `SUSPENDED`; suspendierte gids werden in der Pref `suspended_interop_groups` gehalten. Composer-Banner: suspendierte Gruppe "You can't send messages to this group because all third-party members have left."; Opt-out oder entfernt "... because you're no longer a member."

### 9.2 MEX-Operationen (found; doc_ids aus `assets/whatsapp-android-mex_client_persist_ids.json`)

| Operation | doc_id | Root-Feld | Input | Output / Hinweise |
|-----------|--------|-----------|-------|-------------------|
| `GroupsCreateInteropGroup` | `25726817620301611` | `xwa2_interop_group_create` | `input.participants[{jid}]` | `group`: `gid`, `creation_time`, `creator_v2`, `display_name`, `participants_v2`; kein Subject gesendet |
| `LeaveInteropGroup` | `25346167795013271` | `xwa2_interop_group_leave` | `input.groups_to_leave[{gid}]` | pro Gruppe `response_code`; {200, 400, 401, 403, 404, 405} als endgültig behandelt |
| `AddParticipantsToInteropGroup` | `25732168276369451` | `xwa2_interop_add_participants_to_group` | `input.gid`, `input.participants[{jid}]` | WhatsApp-Mitglieder werden zuerst von PN auf LID gemappt; `null`-LID bricht den Aufruf ab |
| `QueryInteropGroupInfo` | `32734144032867938` | `xwa2_interop_group_query_by_id` | `group_input.gid` | `state`, `gid`, `creation_time`, `creator_v2`, `participants_v2` |
| `InteropPrivacySettingsQuery` | `24849123668112654` | `xwa2_fetch_wa_users` -> `interop_privacy_settings` | `interop_privacy_settings_query_input{feature, dhash}` für die eigene LID | `settings_data`, `dhash`, `denied_contacts[{jid}]` |
| `InteropPrivacySettingsUpdate` | `25421856497452763` | `xwa2_interop_privacy_setting_update` | `feature`, `setting` | `success` |
| `InteropPrivacySettingWithContactListUpdate` | `24913399124998598` | `xwa2_interop_privacy_setting_with_contact_list_update` | `contact_list_type`, `contacts`, `dhash` (`none`, falls nicht vorhanden), `feature`, `setting` | `success` |

Create- und Add-Fehler erscheinen als "This group couldn't be created" / "Make sure everyone you add to this group has third-party chats turned on." / "A group with these members already exists." (gefundene Strings). Das Erstellen einer Gruppe erfordert mindestens einen User des gewählten Integrators ("To create this third-party group, you need to select at least one %1$s user.").

### 9.3 MEX-Notifications (found, `C0WQ`)

| Notification | Handler | Wirkung |
|--------------|---------|---------|
| `NotificationInteropGroupCreateUpdate` | `AbstractC23194A0r`-Branch (Log `CreateInteropGroupNotificationHandler/`) | erstellt die lokale Gruppe aus `gid`, Creator und Participants |
| `NotificationInteropGroupParticipantsUpdate` (`Xwa2NotifyInteropGroupOnParticipantChange`) | `A0B` | fügt Participants mit Source `general_chat_auto_add` hinzu, entfernt ausgetretene Participants; kehrt früh zurück (`no updates needed to gid=`), wenn `C22300su.A15()` false ist |
| `NotificationInteropGroupPropertyUpdate` | `A0C` | `state` ACTIVE oder SUSPENDED -> `suspended_interop_groups` |

### 9.4 Wer darf mich hinzufügen (found, Feature `GROUPADD`)

`C9U8`-Setting-Enum: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALL`, `MYCONTACTS`, `MYCONTACTSEXCEPT`, `MYCONTACTS_AND_ENABLED_INTEROP_INTEGRATORS`, `NONE`. Die Variante mit Kontaktliste trägt die Deny-Liste (`contact_list_type`, `contacts`). Text: "You can only be added to third-party chats by people who either use or have selected the same messaging app." Das Setting wird pro eigener LID gespeichert und mit `dhash` gecacht; die Durchsetzung erfolgt serverseitig (inferred), der Client zeigt das Setting nur an.

---

## 10. Chatliste, Thread-Modell, UI

| Element | Fakt (found) |
|---------|--------------|
| Thread | ein Chat pro Interop-JID (1:1) oder pro gid; in den normalen Chat-Tabellen gespeichert; keine separate Thread-Tabelle |
| Ordner | `InteropConversationsActivity` / `Fragment`; Header-View `InteropView` in der Chatliste (`C31071Ju`, Log `ChatListInteropChatsDelegate/`); sichtbar, wenn berechtigt und Hinweis akzeptiert, oder wenn bereits Interop-Chats existieren; ausgeblendet, wenn die Inbox COMBINED ist |
| Inbox-Modus | SEPARATED: Ordner innerhalb der Haupt-Inbox oder im "More"-Menü; COMBINED: Interop-Chats im Chats-Tab aufgelistet (Filter-Chip `interop` in den Chat-Filtern, `THIRD_PARTY_FILTER`) |
| Zeile / Suche | Integrator-Namenslabel und Icon-Badge am Avatar; Drittanbieter-Chats sind nicht in den Suchergebnissen enthalten |
| Banner / Badge | "You're messaging someone outside of WhatsApp. Third-party apps may have different security."; Home-Badge aus `pref_interop_badge_*`, geschaltet durch AB 7495 (`C230679y0`) |

---

## 11. Baileys (`baron-baileys-v2` 1.5.17, `src/Socket/interop.js`, `WABinary/decode.js`, Quellcode gelesen, nichts getestet)

| Thema | Baileys | Android 2.26.41.6 |
|-------|---------|-------------------|
| Integratoren | hartcodiert `12` (BirdyChat, email) und `13` (Haiket, pn) | keine im Client; Server-Liste |
| Batch-Lookup | `INTEROP_BATCH_MAX = 256` | **20** (Request-Builder und Response-Parser) |
| Opt-out | `<opt_out_integrators><integrator_list>` | kein solcher Node; Opt-in-IQ mit kürzerer Liste |
| Reachability set | `<reachability_settings enabled><user external_id integrator_id/>` | `<integrator id/>`-Kinder |
| Consent | `tos` IQ `trackable id=20240306 result=105`, dann `160` | Hinweis 20240306 Stage 160 = akzeptiert (found); Wire-Form der Hinweis-IQ nicht verfolgt |
| Binäre JID | Tupel-244-Reader wirft, außer Domain = 0; Tag 245 behandelt | Tag 244 mit Domain 0 **und** 2 (Gruppen); kein Tag 245 |
| Notifications | `type="interop"` mit `stella_interop_enabled`, `peer_device_presence`, `ig_profile`, fbid | `w:interop` Handler-ID 270 behandelt nur `ping` |
| Send / Receive | Plaintext als `conversation`, Reporting-Token übersprungen; Kommentar in `Defaults/index.js`: Interop-Receive nicht implementiert | Serializer auf die 9 Felder beschränkt; strikter `InteropMessage`-Parser; Gruppen-MEX-IDs und Notifications im Umfang identisch |

Warum es fehlschlägt (inferred aus dem oben verglichenen Code):

| Symptom | Ursache | Fix |
|---------|---------|-----|
| Decode-Fehler bei Interop-Gruppen-JID | Tupel-Reader lehnt Domain-Byte 2 ab | Domain 2 akzeptieren -> `{gid}@interop.g.us`, device und integrator 0 verlangen |
| Peer verwirft die Nachricht mit Unknown-Field-Failure | jedes Feld außerhalb der 9 (zum Beispiel `messageContextInfo` mit einem `messageSecret`, `protocolMessage`) schlägt fehl, wenn der Peer dasselbe strikte Parsing nutzt (inferred; Baileys-Interop-Sends wurden für diese Felder nicht verfolgt) | `Message` nur mit den Feldern 1, 2, 3, 6, 7, 8, 9, 46 (und 66) bauen |
| Opt-out bleibt wirkungslos | `opt_out_integrators` existiert im Client nicht | SetOptInIntegrators mit den verbleibenden IDs senden |
| Auf Companion-Sessions kommt nichts an | Interop-Kontakte haben nur Device 0 | Interop auf der Primär-Session halten |

---

## 12. Fehlerfälle

| Symptom | Ursache | Wo |
|---------|---------|----|
| Interop-Bildschirme schließen sofort oder erscheinen nie | `C32001Oa.A02()` false: Flag 7495 aus, abhängiger Account oder Companion-Device | 2.1 |
| "Apps can't be saved right now" | SetOptInIntegrators-Fehler; die Codes 500 / 810 / 800 erhalten den "try again later"-Text | 5.3 |
| "This user can't be found" | FetchUsers `item-not-found` (404) | 7.1 |
| Exception für ungültige Interop-JID | Integrator nicht 1-3 Ziffern / führende 0, Account nicht 1-15 Ziffern, Device-Index nicht 0 | 3.1 |
| Gruppe nicht erstellt / Composer deaktiviert | MEX-Create-Fehler oder doppelte Mitgliedermenge / Opt-out, Gruppe suspendiert, kein Mitglied mehr | 9.1, 9.2 |
| Eingehende Nachricht verworfen, Reason 70 / 13 / 14 / 16 / 17 / 76 / 26 | unbekanntes Feld oder Typ ohne Handler / falsche Größe / falsche Hash-Länge / fehlender Media Key / ungültiger Mime / Reaction-Typ-Mismatch / Parse-Exception | 8.2, 8.3 |
| Gruppen-SKDM ignoriert | AB 38723 aus (Log `sender key distribution message skipped`) | 8.1 |
| Integrator-Namen fehlen nach einem Send-Fehler | Ack-Fehler hat `integrator_display_name` geleert | 4.2 |

---

## 13. Wichtige Unterscheidungen

| Nicht verwechseln | Fakt |
|-------------------|------|
| `w:interop` vs USync | Kontakt-Discovery ist FetchUsers auf `w:interop` (max. 20), kein USync-Protokoll |
| `@interop` / `@interop.g.us` / `@g.us` | User und Device, Gruppe, native Gruppe; eine Interop-JID wird nie auf LID oder PN gemappt |
| `InteropMessage` vs `Message` | Receive akzeptiert 9 Felder; Send lässt Context und Padding für Interop weg |
| `trusted_contact` Privacy-Token | generischer Privacy-Token-Job (WA_TCTOKEN_CSTOKEN.md); in diesem Build wurde kein Interop-spezifischer Code gefunden |
| UPI "interop" | `IndiaUpiInterOpHybridActivity`, `IndiaUpiInteropSendToUpiActivity`, `isInterop`-Payment-Note-Flags sind Zahlungsfunktionen, unabhängig |
| Compose / EXIF "interop" | `androidx.compose.ui.viewinterop`, `InteroperabilityIFDPointer` sind Bibliotheken |
| Berechtigt vs opted in vs Consent | Flag 7495 = berechtigt; `opted_in` pro Integrator kommt vom Server; Consent = Hinweis 20240306 Stage 160 |

---

## 14. Kompletter Ablauf

```
[User]              [Client]                                   [WA server]              [Integrator app]
  │ Settings > Third-party chats
  ├──────────────────► A02(): flag 7495, primary, not dependent
  │                    notice 20240306 != 160 ──► show ──► accept ──► stage 160
  │ apps (+ inbox type, + group privacy)
  ├──────────────────► SetOptInIntegrators ─────────────────► opted_in list; table rewritten
  │ New chat > app > id
  ├──────────────────► FetchUsers (1..20) ──────────────────► jid 12-<account>@interop / 404 / 403 / 500
  │ send text / image / video / audio / doc / reaction
  ├──────────────────► restricted Message (no context, no padding), Signal encrypt, device 0
  │                    <message to=..@interop> ─────────────► bridge (inferred) ───► [Integrator app]
  │                    <message from=..@interop><enc/> ◄──────────────────────────── reply
  │                    ENP -> DecryptionCallbackInterop -> DTF parse (unknown field -> 70) -> FBx -> FMessage
  │ ◄──────────────── chat row, notification
  │                    <notification xmlns=w:interop><ping/> ◄─ server (trigger inferred)
  │ ◄──────────────── local notification "Manage requests"; reachability per integrator
  │ New group (flag 15732)
  ├──────────────────► GroupsCreateInteropGroup (LID + interop JIDs) ──► gid@interop.g.us
  │                    MEX notifications: create / participants / property; SUSPENDED -> composer blocked
```

---

## 15. Unbekanntes

| Thema | Zustand |
|-------|---------|
| Wire-Form der Consent-Hinweis-IQ | nicht verfolgt; nur die Stages 160 (akzeptiert) und 162 (vom Migrator geschrieben) sind bekannt |
| Server-seitige Bridge, Zustellung an den Integrator, Key-Handling auf dieser Seite | im Client nicht sichtbar; der Client nutzt gewöhnliche Signal-Sessions und Sender Keys |
| Identity Change / Safety Number für Interop-Kontakte | nicht verfolgt |
| Calls, Polls, Edits, Revokes, Identity Change / Safety Number für Interop-Chats | kein Interop-Codepfad gefunden (kein Interop-String im Call-Code); nicht verfolgt |
| PTV-Empfang (`ptvMessage`) | Feld akzeptiert, kein Parser gefunden |
| Literal 491 im Failure-Pfad; Fehlercodes 810 / 800; andere FetchIntegrators-Trigger als der Opt-in-Bildschirm | ungeklärt |
| Reader der Flags 3953, 5759, 6613, 18670, 20999, 11518, 13532, 14070 | kein Literal-Reader; evtl. über Descriptors gelesen |
| Read Receipts gegenüber Interop-Kontakten | `ClientPayload.interopData` (Feld **38**, `C38671hT`: `accountId` 1, `token` 2, `enableReadReceipts` 3) existiert im Schema; nichts in diesem Build befüllt es |
| Ob der Server die Regel der Europäischen Region durchsetzt | nur UI-Text; keine Client-Prüfung |
