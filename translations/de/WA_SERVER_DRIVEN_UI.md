<!-- src-sha1: 193c35598b4e82f9c32a0c5d2cee4dbf2d708588 -->
# WhatsApp Server-Driven UI — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** Server-gesteuerte Screens und Aktionen auf Android: Phoenix/FCS-Action-State-Machine (IQ `xmlns="phoenix"`, State-Typen, Choice-Operatoren, Resource-Registry), Bloks-Screens (GraphQL-Fetch, Doc-IDs und app-id-Routing, JSON-Payload, Lispy-Funktions-IDs, Action-Namespaces, Component-Queries, Caches), Native Flow Messages (NFM-Button-Registry), WhatsApp Flows (WebView-Bridge, SecureWebView-Host-Policy, Flow-JSON), AI Rich Response und FMX-Card (was nicht server-gesteuert ist), In-App-Browser-Skripte (iabjs-Bridge und Nonce), Sandboxing und Feature-Flags, Relevanz für Baileys

---

## 1. Was es ist (technisch)

WhatsApp Android hat keine einzelne Server-Driven-UI-Engine. Es gibt vier unabhängige Mechanismen; jeder holt eine Beschreibung von einem Server (oder liest sie aus einer Nachricht) und steuert damit nativen Code. Alle Aussagen stammen aus der statischen Analyse der dekompilierten APK; nichts wurde auf der Leitung mitgeschnitten. Tiers: **found** = in Code oder Daten gelesen, **inferred** = abgeleitet, **unknown** = nicht aufgelöst. Obfuskierte Namen gelten pro Build und wurden in 2.26.41.6 neu aufgelöst.

| Mechanismus | Beschreibt | Träger | Renderer / Executor | Einsatz |
|-------------|------------|--------|---------------------|---------|
| Phoenix (Klassennamen sagen FCS "flow configuration service", Log-Tag FDS) | Flow-Steuerung: States `resource` / `choice` / `pass` / `succeed` / `subflow` | IQ `<iq xmlns="phoenix">` mit Kind `<fds>` | `QKb` State-Machine, Resource-Handler (`AbstractC57917Pxu`) | Payments-Onboarding, Address Message, Business-Survey, Brazil-Card-Flows |
| Bloks | Screens: Komponentenbaum + Lispy-Skripte + asynchrone Component-Queries | HTTPS-GraphQL-POST an `graph.<domain>/graphql` | Litho/RenderCore-Host-Activities und -Fragments | Payments, Support, Subscriptions, Consent, Accounts-Center-Linking, Minishops, Surveys, Meta-AI-Business-Consent |
| Native Flow Messages (NFM) | Buttons in interaktiven Nachrichten (`nativeFlowInfo` name + params-JSON) | Nachricht (Protobuf) | `C33370Efz`-Dispatch an etwa 40 Action-Klassen | CTA-Buttons, `address_message`, `galaxy_message` (Flows) |
| WhatsApp-Flows-Web-App | Flow-JSON, gerendert von einer gehosteten Web-App | HTTPS (`flows.whatsapp.net`) in eine `SecureWebView` + ein `WhatsAppBridge`-Message-Channel | `WaFlowsWebViewBottomsheetModalActivity` / `FlowsWebBottomSheetContainer` | Business-Formulare (`galaxy_message`, Flexible Checkout) |

Entscheidende Punkte:

- Phoenix ist die Steuerungsschicht, Bloks die View-Schicht. Ein Phoenix-`resource`-State mit der id `open_bloks_screen_graphql` öffnet einen Bloks-Screen; Bloks-Actions `wa.action.phoenix.*` führen zurück in die State-Machine (Abschnitt 3.5; Verdrahtung aus den Namen inferred).
- Bloks ist weder MEX noch IQ. Es ist ein GraphQL-POST im Meta-Stil (`doc_id` + `variables`) über HTTPS (found, `AbstractC40195HfH`). Phoenix ist IQ. Die Ergebnisklasse der Flows-Endpoint-Query (`AnonymousClass456`) teilt sich die Basisklasse des Bloks-Response-Parsers; ihr Transport ist nicht aufgelöst (Abschnitt 4.5).
- Server-Inhalt kann nicht beliebigen nativen Code benennen. Jede Route läuft über eine feste Registry: Phoenix-Resource-IDs (15 im Code), Bloks-Funktions-IDs (681 benannt), NFM-Button-Namen (39), Flows-Bridge-Methoden (30), Bloks-IQ-xmlns-Allow-List (2 Einträge).
- Es wurde keine Signaturprüfung der Payloads für Bloks oder Phoenix gefunden. `BloksTrustedPayload` (`verifiedRoot`) existiert und hat null Referenzen (found, Smali und Java).
- Nicht server-gesteuert: die FMX-Trust-Card (vom Client erzeugte Systemnachricht), AI Rich Response (festes Protobuf-Komponentenset), die drei `assets/json/bloks_*_template.json`-Dateien (Lade-/Fehler-Gerüste, keine Produkt-Screens).

Verwandte Reports: AB Props (`abt`-IQ, Flag-IDs) in `WA_AB_PROPS.md`; AI Rich Response in `WA_META_AI.md` Abschnitt 6.3. Es wurde kein Framework mit Genie-Namen gefunden (Stringsuche; Abwesenheit nicht bewiesen).

---

## 2. Phoenix-Action-State-Machine

### 2.1 Komponenten (found, Namen aus 2.26.41.6)

| Rolle | Klasse | Hinweise |
|-------|--------|----------|
| Runtime | `QKb` | Log-Tag `FcsStateMachine`; `A03` führt einen State aus, `A04` folgt `next` oder poppt den Stack, `A05` beendet |
| FDS-Manager | `C58392QJx` | Startet eine Config (`A08`), sendet das IQ (`A07`), baut die State-Map aus der Antwort (`A01`) |
| IQ-Builder | `C31107Dfz` (Ctor mit `C9E1`), `C9E1`, `C31085Dfd` | `xmlns="phoenix"` |
| Response-Parser | `F7J` (`<iq><fds>`), `F8I` (Cases 17 bis 20, 27, 28), `F7Y` resource, `F7Z` choice, `C34784F7b` pass, `C34783F7a` succeed, `C34785F7c` subflow, `C34786F7d` version_check | Generischer Attribut-Schema-Parser (`C197428ac`) |
| Geparste States | `P2W` resource, `P2U` choice, `P2T` pass, `P2S` succeed, `P2V` subflow, `C31057DfB` version_check | Gemeinsamer Teil `P2Q`: `name`, `input_path`, `input_selector`, `next`, `result_selector`, `result_path` (`C33411Ege.A03`) |
| Runtime-States | `C55819P7c` resource, `C55817P7a` choice, `C55818P7b` pass, `P7Z` succeed, `C55820P7d` subflow | Mapping in `C58392QJx.A01` |
| Resource-Basis | `AbstractC57917Pxu` | `A02()` = Resource-ID, `A04(...)` = Ausführung mit Param-Map, Default-ID `throw_error` |
| Binding / Registry | `C51E` (id + Lazy-Handler), `InterfaceC148426Oz.CP3()`, Union `C138515tp` | Registries: `C135435oi`, `C135425oh`, `C135415og`, `C53207NpW`..`C53211Npa` |
| Operatoren / Fehler / Callback | `RsJ` (28 Operatoren), `AbstractC56245PPq`; `Q6G` (`catch`); `C57560Pry` (`A00(error, result)`, `A01(result)`) | |

### 2.2 Fetch: IQ (found, `C31107Dfz`, `C58392QJx.A07`)

```
<iq xmlns="phoenix" type="get|set" id="...">
  <fds config="<config name>" state="<start state>" parameters="<json>">
    <context ... parameters='{"session-id":"...","bloks-versioning-id":"13c6e3b8...(64 hex)"}'/>
  </fds>
</iq>
```

| Element | Wert | Tier |
|---------|------|------|
| `type` | `get` beim Start (`A08`), `get` oder `set` für die Resource `send_fds_iq` | found |
| IQ-Typ-Ints / Timeout | 302 (get), 303 (set), 32000 ms | found |
| `state`, `parameters` | nur geschrieben, wenn nicht leer; `parameters` = JSON der Nicht-null-Einträge | found |
| `bloks-versioning-id` | konstanter 64-Hex-String, gleicher Wert in jedem Bloks-Request-Builder (Abschnitt 3.2) | found |
| Verschachtelung des Context-Nodes | `<context>` trägt das JSON; genaue Verschachtelung des inneren Nodes nicht aufgelöst | unknown |

Antwort (found, `F7J`, `F8I`):

| Element | Inhalt | Verwendet für |
|---------|--------|---------------|
| `<fds>`-Attribute `state`, `parameters` | Start-Hinweis | geparst, nicht weiter verfolgt |
| `<states start_at="...">` + `<state ...>`+ | das Programm (Abschnitt 2.3) | `QKb`-Init, Log `initializeStateMachine num_states` |
| `<next_screens>` + `<screen is_entry_screen app_id bloks_server_params sources>` | vorzuladende Bloks-Screens | `C58392QJx.A06` (Preload) |
| `<screen_data parameters>` | Screen-Daten-Blob | geparst |
| `<persist_data>` + `<data ...>` | Werte, die der Host behält | `C58392QJx.A02` (Callback pro Key) |

Ein IQ-Fehler wird als `error` (`BtN`) an den Aufrufer zurückgegeben, und der ausstehende Manager-Eintrag wird entfernt.

### 2.3 State-Typen (found)

Der Parser akzeptiert die Diskriminator-Liste `FDSResourceState|FDSChoiceState|FDSSucceedState|FDSPassState|FDSSubflowState|FDSVersionCheckState` (`F8I` Case 27). Das Attribut `type` ist der feste String in der zweiten Spalte.

| Typ | `type` | Eigene Attribute | Runtime-Verhalten |
|-----|--------|------------------|-------------------|
| Resource | `resource` | `id` (Resource-ID), `parameters`, `merge`, `merge_param`, `catch` | Schlägt `id` in der Registry nach; fehlende id ergibt Fehler `ResourceNotFound`; führt Handler aus; Ergebnis gemäß `merge` gemergt; geht zu `next` |
| Choice | `choice` | `default` (Fallback-Next-State), `catch`, Kinder `<choice choice="{json}"/>`+ (ein Operator-Key + `next`) | Wertet Operatoren auf dem Input-JSON aus; erster Treffer gewinnt, sonst `default`; mindestens ein Choice erforderlich |
| Pass | `pass` | `parameters` | Schreibt Daten um und geht zu `next`, kein Handler |
| Succeed | `succeed` | keine | Terminaler Erfolg (`A05` ohne Fehler) |
| Subflow | `subflow` | `launch_mode` (`child` oder `embedded`), `config`, `parameters`, `catch` | `child`: neuer Manager und neue State-Machine; `embedded`: holt eine weitere Config in dieselbe Session (inferred aus `C55820P7d`) |
| Version check | `version_check` | `default`, Kind `<choice>` | Geparst (`C31057DfB`), hat aber keinen Branch in `C58392QJx.A01`; der State wird verworfen (found); ein Übergang dorthin würde mit `state not found for name` fehlschlagen (inferred) |

Der Parser kennt keinen `fail`-State; das Manifest listet `fail` dennoch (2.7).

Selektoren und Daten (found):

- `input_selector` Default `"$"`; der String `"null"` deaktiviert ihn (`C58392QJx.A01`). `result_selector` und Parameter-Merging laufen über `AbstractC58328QFo`. Für `catch` wird eine Engine im JSONPath-Stil verwendet (`Q2G`, Ausdrücke wie `$.[i].error_equals`) (found); dass Selektoren dieselbe Engine nutzen, ist inferred.
- `merge`-Modi in `QKb.A03`: `replace` (Default), `merge`, `incremental_merge`, `wae_commerce_merge` (found).
- `catch` = JSON-Array aus `{error_equals:[names], next:<state>}`; ein leeres `error_equals` trifft alles (found, `Q6G.A00`). Nicht abgefangene Fehler beenden die Machine mit dem Fehler (`A05`).
- Vom Interpreter selbst ausgelöste Fehler: `ResourceNotFound`, `FailToResume`, `unsupportedComparisonTypes`, `comparingValuesWithDifferentTypes`, `genericChoiceStateError`; Handler-Default-Fehler `NOT_CATCHABLE_ERROR` (`C5I7.A03`) (found).

### 2.4 Choice-Operatoren (found, `RsJ.A00`)

28 Klassen. Das Manifest listet 21; sieben Legacy-Namen stehen nur im Code.

| Gruppe | Namen |
|--------|-------|
| Boolean | `and`, `or`, `not`, `booleanEquals` |
| Gleichheit | `eq`, `neq`, `eq_any`, `neq_any`, `eq_path`, `neq_path`, `eq_any_path`, `neq_any_path`, `stringEquals` |
| Ordnung | `gt`, `gte`, `lt`, `lte`, `gt_path`, `gte_path`, `lt_path`, `lte_path`, `numericalEquals`, `numericalGreaterThan`, `numericalGreaterThanEqual`, `numericalLessThan`, `numericalLessThanEqual` |
| Sonstige | `isPresent`, `regex_match` (`variable` + `regex_match`) |

Jeder Operator wird über das Vorhandensein seines Keys im Choice-JSON gewählt (`AbstractC56245PPq.A00`); eine `JSONException` springt zum nächsten Operator. `_path`-Varianten vergleichen gegen einen aus einem Pfad aufgelösten Wert (inferred aus dem Namen); die genaue Auflösung wurde nicht gelesen.

### 2.5 Resource-Registry (found)

Registriert über `InterfaceC148426Oz.CP3()`; die IDs werden von `C05T.A00(n)`-Suppliern gehalten. Die Registries `C53207NpW`..`C53211Npa` liefern nur dann ein Set, wenn `L8E.A1T()` true ist (`C18780mK.A03()` gleich `C21610rj.A0E`); was dieses Prädikat bedeutet, ist unknown.

| Resource-ID | Handler | In `phoenix-features.json` | Verhalten |
|-------------|---------|----------------------------|-----------|
| `open_bloks_screen_graphql` | `C954246c` | ja | Öffnet einen Bloks-Screen; Param `app_id` erforderlich (sonst schlägt der Cast fehl) |
| `open_bloks_screen` | `C954346d` | nein | Dasselbe, `fetch_channel` = `GRAPHQL` (nutzt `bloks_server_params`) oder `STATIC` (nutzt `fetch_channel_params.static_url`, setzt `should_load_bloks_through_cdn: true`); andere Werte werfen |
| `send_fds_iq` | anon in `AbstractC79003We` | ja | Params `config`, `type` (`GET`/`SET`), `state`, `parameters`; braucht einen laufenden FDS-Manager per Job-ID; fehlender Manager oder fehlende Config loggt einen Fehler und scheitert mit `NOT_CATCHABLE_ERROR` |
| `abprop_fetch` | anon in `AbstractC79003We` | nein | Params `code` (int), `abprop_type` (`string`/`json`/`boolean`/`float`/`integer`), `default_value`; gibt `abprop_value` aus dem AB-Store zurück; keine Allow-List auf `code` gesehen |
| `client_dasl_query` | `C954746h` | ja | Braucht Param `query`, sonst Log `No parameters` und Fehler; Query läuft auf einem Background-Executor |
| `dismiss_bottom_sheet` | `C955346n` | ja | Schließt das aktuelle Sheet |
| `native_flow_call_manager` | `C954946j` | ja | Braucht `phone_number`; reduziert auf Ziffern und `+`; startet `ACTION_DIAL` (`tel:`) mit `FLAG_ACTIVITY_NEW_TASK` (nur Dialer, kein Auto-Call) |
| `request_permission` | `C955046k` | nein | Android-Permission-Request (Bezug zu `FcsRequestPermissionActivity` inferred) |
| `throw_error` | `C954446e` | nein | Löst die `error`-Map aus; sucht die Meldung per `error_map_type` + `code` |
| `payment_encrypt_with_public_key` | `C31703Dr4` | ja | Params `data_value`, `data_type`, `key_scope`, `provider_name`, `network` (gated) |
| `br_verify_card_deeplink` | `C955446o` | ja | Sendet einen paketbeschränkten Broadcast `com.whatsapp.payments.phoenix.action.launch_activity_for_phoenix_result` mit `app_to_app_partner_app_package`, `app_to_app_partner_intent_action`, `app_to_app_request_payload` (gated) |
| `br_verify_card_check_if_app_exists` | `C31702Dr3` | nein | Gated |
| `native_br_compliance`, `native_br_p2m_checkout_address`, `native_card_encryption_resource` | `C955146l`, `C955246m`, anon | nein | Brazil-Payments, gated bis auf die Card-Resource |

Nur im Manifest stehende Namen (kein Registry-Eintrag in diesem Build): `error_response`, `native_flow_npci_common_library` (Teilbaum `mode.collect`), `native_p2m_lite_compliance`, `native_p2m_lite_hpp_checkout`, `open_bloks_screen_static`. `open_bloks_screen_static` hat keinen Handler; der STATIC-Pfad liegt in `open_bloks_screen` als `fetch_channel`.

### 2.6 Startpunkte (found)

`new C57778Pva(config, params, startState)` wird aufgebaut bei: `address_message` (`C31337Djk`, NFM), `biz_survey` (`C57417PpS`), `br_merchant_onboarding` (`C33140EcF`), `br_p2m_checkout_add_card`, `br_p2p_verify_card` (`C32703EOj`) und einem Deep-Link-Einstieg, der eine vom Server benannte Config mit Start-State `DeepLink` übergibt (`RunnableC46615KYo` Case 18, Referral `deeplink`). Die Strings `add_card_phoenix`, `verify_card_phoenix` existieren; ihre Rolle als Config-Namen ist inferred. Das Config-Programm selbst kommt vom Server; ausgeliefert wird keines außer dem Capability-Manifest.

### 2.7 Capability-Manifest

`assets/versioning/phoenix-features.json` (1.218 B, identisch mit der Kopie aus 2.26.34.4): Top-Level `pass`, `choice` (21 Operatoren), `resource` (12 IDs plus `input_selector`, `parameters`, `result_selector`, `result_path`), `succeed`, `fail`. Seine Nutzung zur Laufzeit wurde nicht gefunden (keine String-Referenz); als Namensliste behandeln. Der Code ist maßgeblich (2.4, 2.5).

---

## 3. Bloks

### 3.1 Host-Oberflächen (found)

| Host | Rolle |
|------|-------|
| `WaBloksActivity`, `WaBloksBottomSheetActivity`, `BloksCDSBottomSheetActivity`, `BloksCDSPreloadCDSBottomSheetActivity` | Vollbild, Bottom Sheet, CDS-Sheets (Design-System) |
| `WaSqBloksActivity`, `WaBloksScreenQueryFragment` | Screen-Query-Hosts (Typen `screen_query` vs `legacy_screen`) |
| `WaFcsModalActivity`, `WaFcsBottomSheetModalActivity`, `WaFcsPreloadedBloksActivity`; `SurveyCanonicalBloksActivity` (+ Sheet) | Von Phoenix gehostete Screens; Surveys |
| Produkt-Hosts | `CommonBloksActivity`, `SupportBloksActivity`, `BrazilPayBloksActivity`, `ConsumerSubscriptionBloksActivity`, `DigitalCommerceDcpBloksActivity`, `CsatSurveyBloksActivity`, `AppointmentBloksHostActivity` (exported false), `WaBackupStorageBloksActivity` (exported false) |

Keine Bloks-, Flows- oder Phoenix-Activity deklariert einen Intent-Filter; `targetSdkVersion` ist 36, daher sind Activities ohne `android:exported` nicht exportiert (found, Manifest). Bloks kann außerdem eine `WebView`-Komponente einbetten (`AndroidBridge.updateSize`, Action `bk.action.WebViewWithOnChange`) (found).

### 3.2 Fetch: GraphQL über HTTPS (found, `AbstractC40195HfH`, `C45J`)

| Element | Wert |
|---------|------|
| URL | `https://graph.<domain>/graphql<path>`; `<domain>` = Pref `pref_graphql_domain`, Default `whatsapp.com`; mehrere Request-Klassen erzwingen `facebook.com`; `<path>` leer oder `/extensions` für die Flows-Variante |
| Query-String | `?_emp=1` angehängt, wenn AB-Prop **549** an ist (Default false) |
| Body | JSON `{"variables": "<json string>", "access_token": ..., "doc_id": <long>, "lang": ..., "Content-Type": "application/json"}` |
| Token | Token pro Request, falls gesetzt, sonst ein statischer, app-bezogener Token-String, der im Client eingebettet ist (Wert nicht wiedergegeben) |
| Header | `X-FB-Friendly-Name: WABloksAppRootQuery-<app_id>`, `X-FB-Request-Analytics-Tags` |
| `variables` | `app_id`, Versions-Key, `params` (JSON-String), `bloks_theme_params` |
| Name des Versions-Keys | `version`, `versioning_id` oder `bloks_version`, je nach Request-Klasse; der Wert ist dieselbe 64-Hex-Konstante wie in Phoenix |
| Pre-Consent-Variante (`C136975rF`) | ergänzt `app_version`, `locale`, `df_token`, `enc_token`, `disclosure_id`, `is_paused`, `country_code`, `encrypted_rid` |
| Extensions-Variante (`C132735kG` Case 2) | `extension_id` (= `flow_id` für Flow-Message-Versionen 2, 3, 4), `business_jid`, `screen_id`, `bloks_version` |
| Fehler | `errors[].extensions.error_code` (Default 417), `is_retryable`; `error.code` 3489039 löst eine Integritätsprüfung und einen Retry aus, 1675012 ergibt `Bad Request` (Pre-Consent-Pfad) |

Root-Felder der Antwort (`AnonymousClass451.A05`): die Payload ist `data.<root>.payload` (ein JSON-String).

| Doc-ID | Root-Feld | Verwendet von (found) |
|--------|-----------|-----------------------|
| 3651100555017197 | `whatsapp_bloks_getlayout` | Default-Route; Minishops link/pdp/storefront |
| 3958953970834604 | `whatsapp_bloks_getprivatelayout` | Default für `C5LX.A00()`; Minishops-Privacy-Notice, Products-Preview |
| 9404809712971896 | `whatsapp_bloks_getlayout` | per Regex geroutete Familien (3.3) |
| 9943385105682204 | `whatsapp_bloks_getprivatelayout` | `logged_out.cxthelp.whatsapp` |
| 6019334944816363 | Flows-Layout (Root `whatsapp_galaxy_bloks_getflowlayout` existiert in `AnonymousClass424`; Verbindung zwischen beiden inferred) | `com.bloks.www.whatsapp.galaxy.flow.v2`, `...commerce.galaxy_message`, `...commerce.extensions_message_v2` |
| 36103976949247233 | `wamo_bloks_get_layout` | WAMO-Oberflächen |
| 9676557989071413 | keinem Root-Feld zugeordnet | Payments-Sample/Care, `novi.care.*`, `whatsapp.ai.biz.*`-Consent |

Die Doc-IDs 26891716230495873 (Pix-Playground) und 25865201793138751 tauchen in den Routing-Tabellen ohne aufgelöstes Root-Feld auf.

### 3.3 app-id-Routing (found)

Ein Screen wird über `app_id` adressiert (ein gepunkteter Name, `com.bloks.www.*`). Routing-Tabellen bilden eine `app_id` auf einen Query-Deskriptor `C5LX(doc id, request-factory variant)` ab: zehn Tabellen mit festen Sets (`InterfaceC148576Pp`: `C132235jS`..`C132335jc`) und Regex-Tabellen (`InterfaceC148726Qe`: `C132345jd`..`C132465jp`).

| Familie | Muster oder Beispiel | Doc-ID |
|---------|----------------------|--------|
| Orders / Payments-Hub | `orders_hub(\..+)*`, `fbpay_hub`, `payment.mft.wallet.fbpay_hub`, `(payment.)?mft.wallet.*`, `payment.(bloks.(commerce|ecp).checkout|fbpay.ecp).*` | 9404809712971896 |
| `gai` / `sna` / AI-Sticker (Bedeutung der Familie aus Namen inferred) | `bloks.nme.gai`, `wa.nme.gai`, `wa.sna`, `whatsapp.ai.stickers.*` | 9404809712971896 |
| Subscriptions | `dcp.subscriptions?(\..+)*` | 9404809712971896 |
| Support | `(csf|cxthelp)(\..+)+` | 9404809712971896 |
| Minishops | `minishops.link.app`, `.whatsapp.pdp`, `.storefront.wa` | 3651100555017197 |
| Business-AI-Consent | `whatsapp.ai.biz.{learn_more,consent,assistant_consent,third_party_consent,meta_ai_consent}` | 9676557989071413 |
| Playground / Debug | `wa.playground.payments.br.pix.*` (Variante 9) ; `whatsapp.payments.phoenix.{debug,demo_*,multi_*}`, `payments.whatsapp.f2care`, `novi.care.*` (Variante 10) | 26891716230495873 ; 9676557989071413 |

87 verschiedene literale `com.bloks.www.*`-IDs stehen im Code; der Rest kommt vom Server und wird über die Regex-Familien geroutet. In `AnonymousClass514` gibt es zwei Muster-Guards: `consent(...)`-IDs können `extra_params_json.whatsapp_bloks_networking_feature_override` tragen; `payment.mft.security.*` mit `ptt_use_case = WALLET` wählt den Request-Helper `wallet_canonical` (found).

### 3.4 Payload-Format (found)

Streaming-JSON-Parser `AbstractC122255Jb`; das oberste Objekt hat `payload` (String) und `layout.bloks_payload`.

| `bloks_payload`-Key | Bedeutung |
|---------------------|-----------|
| `tree` | Root-Komponente (Abschnitt unten); `action` statt `tree` bei reinen Action-Payloads |
| `ft` | Function-Table: id auf Ausdrucks-String |
| `data`, `values`, `templates`, `props` | Datensätze (`id`, `type`, `data`, `scoped`), Wert-Ausdrücke, Templates, Prop-Namenstabelle |
| `embedded_payloads`, `hoisted_async_components` | Verschachtelte Payloads nach id |
| `referenced`, `referenced_external`, `referenced_embedded_payloads`, `referenced_templates`, `referenced_ft_entries`, `referenced_values`, `referenced_ct`, `ct` | Abhängigkeitslisten für partielle/gestreamte Payloads |
| `component_queries` | Asynchrone Component-Queries (`id`, `app_id_expr`, `params`, `client_params`, `targets`, `cache_ttl_expr`, `disk_cache_enabled`, `is_scoped`) |
| `error_attribution` | `logging_id`, `source_map_id` |
| `depth`, `step_debugger_metadata.breakpoints` | Streaming-Tiefe, Debugger |

Baum-Kodierung (`C5AN`): ein Node ist ein Objekt, dessen einziger Key ein Code Point ist; dieser Code Point ist die Komponenten-ID (`AbstractC105654gT.A00` = `codePointAt(0)`); Attribut-Keys sind ebenfalls einzelne Code Points (`!`=33 id, `#`=35 child, `&`=38, `+`=43 für die Shadow-Komponente 13347). Die Zuordnung Komponenten-ID zu Name liegt nicht in den Assets (unknown).

Funktions-IDs ("Lispy", `C122545Ki`): ein Skript-Node ist ein JSON-Array, dessen erstes Element die Funktion ist: `"#<name>"` benannt, ein gepunkteter Name, aufgelöst über die Namenstabelle `AbstractC111054pC.A01`, oder ein Base-36-String, geparst mit `Integer.parseInt(s, 36)`. Typisierte Konstanten haben feste IDs: 17809 `bool.Const`, 18327 `f32.Const`, 18338 `f64.Const`, 19222 `i32.Const`, 19237 `i64.Const`. Die Namenstabelle hat 681 Einträge, IDs 17293 bis 26071.

Aus den ausgelieferten Templates dekodiert (Base-36-Token, id, Tabellenname; found): `e2a` 18226 `core.If`; `e25` 18221 `core.GetArg`; `e2f` 18231 `core.TakeLast`; `e1w` 18212 `core.Apply`; `dng` 17692 `bloks.GetParameter`; `dnt` 17705 `bloks.GetVariable2`; `f4g` 19600 `map.Get`; `f6m` 19678 `mins.CallRuntime`; `igq` 23930 `core.AsNonnull`; `fjm` 20146 `screen.callback.DidFetchSucceed`; `foz` 20339 `ttrc.MarkerStart` (alle unter `bk.action.`); `h9h` 22373 ist mit dem literalen Namen `null` gelistet.

Die `\t(...)`-Textform in `ft` und in Ausdrucks-Strings ist eine andere Serialisierung; dass sie dieselben Base-36-IDs verwendet, folgt daraus, dass die obigen Dekodierungen stimmig sind (inferred). Der Text-Parser wurde nicht gelesen.

Capability-Aushandlung (inferred): die 64-Hex-`bloks-versioning-id` wird mit jedem Request gesendet; die Tabelle enthält 50 `bk.versioning.*`-Capability-Namen (zum Beispiel `SupportsFunctionTables`, `TemplatePayloads`, `AsyncComponentBatchedWireProtocol`, `SupportsLispySignatureMinification`). Dass der Hash dieses Capability-Set identifiziert, ist inferred.

Ausgelieferte Assets (`assets/json/bloks_screen_template.json`, `bloks_bottomsheet_template.json`, `bloks_cds_base_screen_template.json`, 9.028 / 9.124 / 11.443 B, identisch mit 2.26.34.4): Root-Template mit einem Spinner-`tree`, einem `component_queries`-Eintrag mit Ziel `genScreenContent` und einem Fehler-Fallback in `embedded_payloads` (`Something went wrong` / `Please try again later` in zwei der drei). Es sind Gerüste; Produkt-Screens kommen aus dem Query-Ergebnis.

### 3.5 Action-Namespaces (found, `AbstractC111054pC`)

| Präfix | Anzahl in ID-Tabelle | Beispiele |
|--------|----------------------|-----------|
| `bk.action.core/bool/num/i32/i64/f32/string/array/map/math` | 113 | `core.If`, `core.Let`, `core.While`, `array.Map`, `string.*` |
| `bk.action.mins.*` | 36 | `CallRuntime`, `PutByVal`, `Raise` (minscript-VM) |
| `bk.action.bloks.*` | 61 | `OpenScreen`, `OpenBottomSheet`, `Inflate`, `FetchAsyncComponents`, `WriteLocalState`, `ReplaceChildren`, `WriteGlobalConsistencyStore` |
| `bk.action.cds.*`, `bk.callbacks.cds.*` | 13 + | `OpenCdsBottomSheet`, `PushCdsBottomSheet`, `UnwindToScreen` |
| `bk.action.animated/animation/timer/collection/textinput/text_input/video` | 58 | UI-Verhalten |
| `bk.action.qpl/ttrc/trace` | 14 / 11 / 2 | Latenz-Marker (`ttrc.MarkerStart`) |
| `bk.action.privacy.consent.*` | 10 | `OpenFlow`, `LaunchConsent`, `ShutdownExperience` |
| `bk.action.waffle.*`, `bk.fx.*`, `bk.waffle.*` | 37 / 11 / 2 | Accounts-Center-Linking: `EncryptPassword`, `DeleteLocalUserCredentials`, `GetProfilePictureUrl`, `UnpauseWithNativeAuthBlob`, `PregenerateAndCacheRSAKeyPairs` |
| `bk.action.mft.*`, `bk.action.frontier.*`, `bk.action.apt.PleEncrypt`, `bk.action.commerce.GetPaymentToken`, `bk.action.payments.GetCreditCardMetaData` | 5 / 5 / 1 / 1 / 1 | Payments: `ModularGeneratePTT`, `LaunchGooglePaySheet`, `IsLuhnCompliant` |
| `bk.action.navigation.OpenUrl`, `bk.fx.action.OpenURLInIAB`, `bk.action.acp.OpenUrlExternally`, `bk.action.OpenUniversalLink`, `bk.action.DeeplinkToOtherAppOrDirectToAppStore`, `bk.action.bloks.IsAppInstalled` | 6 | Navigation aus Bloks heraus |
| `bk.action.io.clipboard.SetString`, `bk.action.RequestPermission`, `bk.action.media.LoadAlbums`, `bk.fx.action.media.OpenMediaPicker`, `bk.action.foa.media.OpenCamera` | 5 | Gerätezugriff |
| `wa.action.*` | 75 | WhatsApp-Host-Actions (Tabelle unten) |
| `wa.callbacks.*` | 10 | `FormInputOnTextChange`, `CodeInputOnTextChange`, `DatePickerOnDateSet`, `CameraViewOnMediaCaptured`, `ListViewItemSelected` |
| `bk.versioning.*`, `wa.versioning.image.base64` | 50 / 1 | Capability-Namen |

Bemerkenswerte `wa.action.*` (IDs 22391 bis 26071):

| Gruppe | Namen |
|--------|-------|
| Network | `IQRequest`, `AsyncRequest`, `UploadMedia`, `UploadProfilePicture` |
| Phoenix-Bridge | `phoenix.FdsIq`, `FdsIqV2`, `FcsReturnResult`, `FcsReturnResultV2`, `FcsReturnResumableData`, `statemachine.GoBack`, `GoBackV2` |
| App-State | `GetAbPropValue`, `GetAppType`, `GetIntentParameter`, `LoadScreenParam`, `SaveScreenParam`, `IsDarkModeEnabled` |
| Navigation | `OpenUrl`, `RouteToNativeScreen`, `RouteToNativeBenefitDetail(V2)`, `navigation.OpenChat`, `OpenContactInfo`, `OpenNativeActionSheet`, `FinishActivity(WithResult)`, `PopScreen` |
| Messaging / Commerce | `commerce.SendNFMReplyMessage`, `commerce.ActionWithCallback`, `share.Text`, `bonsai.SubmitFeedback`, `care.OpenContactSupport`, `care.OpenReportThisPayment` |
| Telemetrie | `SendFieldStat(V2)`, `StartFieldStatTimer`, `GetFieldStatEventId`, `perf.TrackPerformance`, `novi.EncryptLogEvent(V2)` |
| Deeplink | `RegDeeplinkListener`, `DeregDeeplinkListener` |

Guard an der Bloks-IQ-Action (`C129575f5.A0Y`, Log `IQRequestHelper/sendIQRequest: Invalid XMLNS`): nur die xmlns `w:pay` und `urn:xmpp:whatsapp:account` passieren (`C33327EfH.A02`); alles andere ruft den `on_failure`-Callback auf. Bloks-Skripte können daher IQs nur in diesen zwei Namespaces senden (found). Handler-Implementierungen der meisten anderen `wa.action.*`-IDs wurden nicht verfolgt (ihr Code wird über die numerische id erreicht).

### 3.6 Component-Queries und Caching (found)

- Eine `component_query` holt eine asynchrone Komponente per `app_id` über denselben GraphQL-Pfad (Manager `C5L9`, Log-Tag `BloksComponentQueryManager`); `app_id_expr`, `params`, `client_params` und `cache_ttl_expr` sind Lispy-Ausdrücke, die auf dem Client ausgewertet werden.
- Zwei Cache-Stufen: ein Memory-Cache (`cache_src: memory`, `cache_age`) und ein Disk-Cache, pro Query geschlüsselt (`BloksComponentQueryDiskCache`; Klassen `C5NA`, `C5NN`, `C136885r6`). Disk-Records sind Java-serialisiert (`ComponentQueryDiskCacheRecord`: `DiskCacheData{initialResponse, extensions}`, `responseTimestampMs`, `BloksComponentQueryResources`); Metadaten liegen unter `__disk_metadata`; ein `Bloks_ACQ_ReadWriteThread` erledigt die I/O. `disk_cache_enabled` ist ein Schalter pro Query.
- Die Actions `bk.action.AsyncComponentCacheWrite`, `bloks.ClearCachedAsyncComponents`, `bloks.InvalidateCachedAsyncComponents` lassen eine Payload den Cache verwalten.
- Verzeichnis, Größenlimit und Eviction des Disk-Caches: unknown. Java-Deserialisierung von server-beeinflussten Cache-Records geschieht nur aus dem eigenen Cache der App (inferred aus dem Codepfad).

---

## 4. Native Flow Messages und WhatsApp Flows

### 4.1 NFM-Button-Registry (found, `AbstractC30032D4u` Case 442, Klasse `EYT`)

Eine interaktive Nachricht trägt Buttons mit `nativeFlowInfo.name` und einem params-JSON. Dispatch: `C33370Efz.A05` schlägt den Namen in einer Map (`C0VA`) mit etwa 40 `AbstractC33168Ech`-Subklassen nach; unbekannte Namen loggen `can not recognize NFM action` und werden verworfen; eine Action kann abgeschaltet sein (Zähler `wa:nfm_dispatch_gate_blocked` / `_observed`).

| Set | Namen |
|-----|-------|
| Unterstützte Button-Namen (39) | `cta_catalog`, `review_and_pay`, `review_and_pay_v2`, `cta_call`, `cta_url`, `cta_copy`, `cta_pix_code_copy`, `offer_payment_account`, `form_message`, `open_webview`, `catalog_message`, `voice_call`, `video_call`, `landline_call`, `quick_reply`, `single_select`, `view_product`, `call_permission_request`, `cta_app_link`, `appointment`, `automated_greeting_message_view_catalog`, `send_location`, `order_status`, `booking_confirmation`, `booking_status`, `psi_nux_opt_in`, `psi_tos_opt_in`, `psi_opt_outs`, `account_authentication_request`, `request_contact_info`, `agent_api_key`, `otp`, `payment_reminder`, `cta_reminder`, `payment_request`, `api_signup`, `inapp_signup`, `split_payment`, `send_payment` |
| Zweites Set | `address_message`, `galaxy_message` (Flow-startend; Rolle aus der Verwendung inferred) |
| Mixed/Quick-Reply-Allow-List | `C33370Efz.A08`: `cta_url`, `cta_call`, `voice_call`, `video_call`, `cta_copy`, `menu_options`, `cta_reminder`, `view_product`, `cta_app_link`, `galaxy_message`, `otp`, `booking_*`, ... |

- `address_message` startet die Phoenix-Config `address_message` (`C31337Djk`, found).
- `galaxy_message` öffnet WhatsApp Flows (4.2).
- Flow-Antworten werden in `message_ui_elements_reply` (`flow_id`, `element_type` 8) und `interactive_message_bloks_widget` gespeichert (found, SQL).

### 4.2 `galaxy_message`-Params und Start (found, `C31338Djl`, `C31337Djk`)

| Key im params-JSON | Verwendung |
|--------------------|------------|
| `flow_id` | muss für die Flows-v2-Action auf `\d+` passen |
| `flow_token`, `flow_cta` | zusammen mit `flow_id` erforderlich (Flows-v2-Pfad) |
| `flow_message_version` | `2`, `3`, `4` wählen die Extension-Variablen der Bloks-Query |
| `flow_action` (`navigate` Default, `data_exchange`), `flow_action_payload` (Objekt) | erster Screen / Datenkanal |
| `mode` | `draft` markiert einen Draft-Flow (`is_draft`) |
| `form_type` | routet zu `FlexCheckoutNativeFormActivity` (Flexible Checkout) |
| `flow_token_signature`, `www_proxy_secret` | werden nur dann an die Seite weitergereicht, wenn AB-Prop **14825** an ist |

Die Business-JID des Senders kommt aus dem Chat (`FlowsV2Action`); ohne sie bricht der Start ab (`cannot launch flow without business jid`). Es gibt zwei Renderer: die Web-App (4.3) und einen Bloks-Pfad (`com.bloks.www.whatsapp.galaxy.flow.v2`, Abschnitt 3.2). Welchen eine bestimmte Nachricht nimmt, ist nicht aufgelöst; die AB-Props **22787** (separate Activity vs Bottom Sheet) und **14222** werden auf dem Web-Pfad gelesen.

### 4.3 Flows-Web-App (found)

| Element | Wert |
|---------|------|
| Basis-URLs (AB-String-Props) | **7153** `https://flows.whatsapp.net/flows` (Preload, `C35814Ff9`), **6060** gleicher Default (Flow-JSON-Fetch `EP6`: Basis + `/json/` + Flow-ID, inferred aus der Builder-Reihenfolge), **7125** `.../flows/cache_management/` (Cache-Cleaner `C39066GzF`, Intervall **7126** = 1382400), **16723** `.../flows-app/catalog` (Katalog) |
| Host | `SecureWebView` (`com.facebook.secure.securewebview`): Datei- und Content-Zugriff aus; Laden nur erlaubt, wenn das Schema `https` ist UND der Host dem Host der Start-URL oder einer ihrer Subdomains entspricht (`GAP.A00`, `H26`, in `GAL` mit AND verknüpft); sonst Log `Uri is blocked` |
| Start-URL | aus dem Bundle (`url`, Default `about:blank`); die Basis ist ein AB-Prop, der Server kann sie also verschieben; die Host-Policy folgt der Start-URL (inferred Konsequenz) |
| Preload | `FlowsWebPreloader` lädt AB **7153** in einer versteckten WebView (`setCacheMode(2)`); Service-Worker-Cache-Version wird über `flows_service_workers_cache_version` verfolgt |
| Seiten-Injection | `meta`-Tag mit viewport, `layoutDirection`, `locale`, `timeZone`, `supportedStyles` |
| Bridge | `window.WhatsAppBridge.invoke(method, data, cb)`; nativ wird ein `MessageChannel` erzeugt und `init-port` mit Port 1 gepostet (`HQD`); Nachrichten sind JSON `{method, data, callbackID}`; Antworten `{callbackID, responseData}` |
| Origin-Bindung | Das Bridge-Skript wird per `evaluateJavascript` in alles injiziert, was die WebView zeigt; der Port wird an das Target `Uri.EMPTY` gepostet; das Gating stützt sich auf die URL-Policy der SecureWebView (inferred) |
| Flow-JSON | `flow_json` wird von `EP6.A01` geholt (HTTP GET, auf Disk als serialisierter String abgelegt, Key `<id>_<id2>`), nur wenn AB **8552** an ist; `FlowsWebViewDataRepository` baut das Bundle (`flow_json`, `flow_action_payload`, `creation_source`, Session-IDs) |
| Public Key | `WAExtensionsGetPublicKey` gibt den Public Key des Endpoints zurück, der über einen GraphQL-Metadata-Call bezogen wird (Fehler `extensions-metadata-graphql-*`, Modus `required` oder `optional`); die Verwendung zur Datenverschlüsselung geschieht seitenseitig (inferred) |

Nativ behandelte Bridge-Methoden (30; `C41342Hyk`, `FlowsWebBottomSheetContainer.CKc`):

| Gruppe | Methoden |
|--------|----------|
| Session | `WAExtensionsGetFlowData`, `WAExtensionsDataChannelExchange`, `WAExtensionsNavigate`, `WAExtensionsComplete`, `WAExtensionsClose`, `WAExtensionsGetPublicKey`, `WAExtensionsGetClientAbProps` |
| UI | `WAFlowsShowNativeInputDialogComponent`, `WAExtensionsConfigureNavBar`, `WAFlowsMediaSelect`, `WAFlowsMediaRetry`, `WAFlowsMediaDelete`, `WAFlowsCopyText`, `WAFlowsOpenURL`, `WAExtensionsLearnMore`, `WAExtensionsContextualHelp` |
| Business | `WAExtensionsSpamReport`, `WAExtensionsReportItem`, `WAFlowsDownloadResponse`, `WAFlowsMarketingDisclosureState`, `WAFlowsMarketingDisclosureUserAction` |
| Cart | `WAFlowsStoreShoppingFlowContext`, `WAFlowsGetCart`, `WAFlowsSetCartItem`, `WAFlowsClearCart` |
| Telemetrie | `WAMLogger`, `WAQPLLogger.start`, `.end`, `.annotate`, `.point` |

Hinweise zur Behandlung: `WAFlowsOpenURL` startet `ACTION_VIEW` nur für `https`-URLs, sonst eine Snackbar; `WAExtensionsGetClientAbProps` gibt jeden AB-Prop nach Code und Typ (`bool`, `int`, `float`, `string`, `json`) zurück, ohne gesehene Allow-List (`C37367GJs`); unbekannte Methoden gehen an einen Default-Handler (`GJW`); Eingaben, die sich nicht parsen lassen, ergeben `extensions-bridge-api-input-parse-error`.

### 4.4 Flow-Abschluss

`WAExtensionsComplete` beendet die Session, und der Client sendet eine Native-Flow-Response-Nachricht (`native_flow_response_*`-Spalten; Params tragen `wa_flow_response_params`, `flow_creation_source`, `response_message`) (found anhand der Namen; Sendepfad nicht verfolgt).

### 4.5 Flows-Endpoint-Query

Die Ergebnisklasse `AnonymousClass456` liest das Root `whatsapp_galaxy_forward_flow_data_response` oder `xwa_flows_make_flow_endpoint_request` und einen `status_code`: 200 ok, 421 und 504 auf eigene Ergebnisse abgebildet, andere generischer Fehlschlag (found). Ob dies über MEX oder den HTTPS-GraphQL-Stack läuft, ist unknown (die Parser-Basis wird mit Bloks geteilt).

---

## 5. Oberflächen, die keine server-beschriebene UI sind

### 5.1 AI Rich Response (nachrichtengetragen, feste Komponenten)

Protobuf `richResponseMessage` (siehe `WA_META_AI.md` Abschnitt 6.3). Enum der Sub-Message-Typen `EnumC32139E2l` (found): `AI_RICH_RESPONSE_UNKNOWN` 0, `GRID_IMAGE` 1, `TEXT` 2, `INLINE_IMAGE` 3, `TABLE` 4, `CODE` 5, `DYNAMIC` 6, `MAP` 7, `LATEX` 8, `CONTENT_ITEMS` 9; Code-Highlight-Klassen (`KEYWORD`, `STRING`, `NUMBER`, `METHOD`, `COMMENT`, `DEFAULT`); dynamische Metadaten `IMAGE`, `GIF`. Der Client rendert ein festes Set; Actions sind Datei-Download / Forward (`UnifiedResponseActionHandlerFactory`). Keine Skriptsprache, keine Action-DSL.

### 5.2 FMX-Card

Die FMX-Card (`LE7`, View-Model-Factory `fmxViewModelFactory`, Avatar-Tag `fmx-card-v2`) wird vom Client als Systemnachricht erzeugt (`C198788cr`: `Creating FMX card system message for chat`); Zähler wie `fmxBizEnterpriseSenders`, `fmxMissingLidMapping`, `fmxSuspiciousBottomSheetCacheMiss` zeigen, dass sie von lokalen Signalen gesteuert wird. Ob der Server irgendeinen Card-Text liefert, ist unknown. Als native UI behandeln.

### 5.3 In-App-Browser-Skripte (iabjs)

`res/raw/iabjs_*` enthält in 2.26.41.6 15 Skripte (vier mehr als im Set von 2.26.34.4): `autofill_execute_callback`, `autofill_language_detect`, `autofill_payment_detection`, `otp_autofill` sind neu. Host `WaInAppBrowsingActivity` (exported false).

| Element | Wert (found) |
|---------|--------------|
| Bridge-Objekt | `iabjs_unified_bridge`: `addWebMessageListener(name, allowedOrigins, listener, jsWorld)` in der isolierten JS-World `iab_js`, wenn unterstützt (`HJY.A05`); Fallback `addJavascriptInterface("iabjs_unified_bridge")` (`RunnableC40709HoJ`) |
| Seitenseite | `window.__call_iabjs_unified_bridge(method, nonce, payload)` postet `{method, payload, nonce}`; die Nonce wird bei der Injection in `window.__iabjs_unified_bridge_nonce="%s"` eingesetzt |
| Native Prüfung | `C39590HNn`: die JSON-`nonce` muss der im Handler gespeicherten Nonce entsprechen (einmal pro Handler durch `AbstractC48382LBd.A00().toString()` erzeugt, UUID-artig, inferred); bei Abweichung wird `invalid_nonce` aufgezeichnet und der Aufruf verworfen; die Methode `iabjs_register_proxy` registriert die World; andere Methoden gehen an Listener, die nach (World, Methode) geschlüsselt sind |
| Neu in diesem Build | `iabjs_autofill_payment_detection` klassifiziert Felder in `cc-number`, `cc-exp`, `cc-exp-month`, `cc-exp-year`, `cc-csc`, `cc-name` anhand von `autocomplete` oder Name/id/Placeholder-Regex; `iabjs_otp_autofill` füllt `input[autocomplete="one-time-code"]`; `iabjs_autofill_language_detect` sendet `languageDetermined` |
| Set erlaubter Origins | vom Aufrufer gelieferte `Set`; Inhalt nicht verfolgt (unknown) |
| Legacy-Fallback | `addJavascriptInterface` hat keinen Filter pro Origin (Plattformverhalten, inferred) |

Acht der 11 älteren Skripte sind byte-identisch mit den Kopien aus 2.26.34.4; `detect_login_forms`, `navigation_performance_logger_android`, `iabjs_bridge_init` haben sich geändert (453 B vs 433 B beim Bridge-Init).

---

## 6. Sandboxing und Sicherheitsübersicht

| Kontrolle | Wo | Tier |
|-----------|----|------|
| Phoenix-Resource-IDs im Code fest; unbekannte id ergibt `ResourceNotFound` | `QKb.A03` | found |
| Phoenix-Operatoren fest (28); nicht passender Operator wird übersprungen | `RsJ`, `AbstractC56245PPq` | found |
| Bloks-IQ-Action auf xmlns `w:pay`, `urn:xmpp:whatsapp:account` beschränkt | `C33327EfH.A02` | found |
| Bloks-Funktions-IDs fest (681 benannt) | `AbstractC111054pC`, `C122545Ki` | found |
| NFM-Namen fest (39 + 2); unbekannte verworfen | `AbstractC30032D4u`, `C33370Efz` | found |
| Flows-Host: nur https + Launch-Host (oder Subdomain), kein Datei-/Content-Zugriff | `SecureWebView`, `GAP`, `H26` | found |
| Flows-Bridge: feste Methodenliste; `WAFlowsOpenURL` nur https | `FlowsWebBottomSheetContainer` | found |
| iabjs: Nonce-Prüfung, isolierte World, Origin-Set | `C39590HNn`, `HJY` | found |
| Phoenix-`br_verify_card_deeplink`-Broadcast auf eigenes Paket beschränkt | `C955446o` | found |
| Alle Bloks-, Flows-, Phoenix-Activities ohne Intent-Filter; targetSdk 36 | Manifest | found |
| Signatur- oder Hash-Prüfung des Bloks/Phoenix-Inhalts | keine gefunden; `BloksTrustedPayload` unreferenziert | found (Abwesenheit in durchsuchten Pfaden) |
| Server kann AB-Props per Code lesen (`abprop_fetch`, `WAExtensionsGetClientAbProps`) | keine Allow-List gesehen | found |
| Transport-Vertrauen (TLS-Pinning, Token-Handling für Graph-Requests) | nicht analysiert | unknown |

Konsequenz (inferred): das Vertrauen ruht auf dem Transport und auf den obigen Registries; ein kompromittiertes oder bösartiges serverseitiges Programm ist auf diese Registries beschränkt, doch die Registries enthalten Payment-Verschlüsselungs-Helper, Credential-Handling für den Accounts Center, `ACTION_DIAL`, URL-Öffnen und AB-Lesezugriffe.

---

## 7. Caching und Preloading

Bloks-Component-Queries: Memory + Disk, TTL über `cache_ttl_expr` (3.6). Phoenix: vom Server gelistete `next_screens` werden in `WaFcsPreloadedBloksActivity` vorgeladen; `persist_data`-Einträge gehen an Listener pro Key (found). Flows Web: Preload-WebView, Service-Worker-Cache-Version, geplanter Cleaner (AB 7125/7126), Flow-JSON-Disk-Cache, Metadata-Ban-Marker `extensions_metadata_banned_<id>_<id>` in den Prefs (found).

---

## 8. Feature-Flags (Defaults aus `C08J`; Bedeutungen aus der Lesestelle)

| ID | Typ | Default | Gelesen in | Wirkung |
|----|-----|---------|------------|---------|
| **549** | bool | false | `AbstractC40195HfH.A03` | Hängt `?_emp=1` an die GraphQL-URL an (außer bei `C0GD.A02()`) |
| **7153** | string | `https://flows.whatsapp.net/flows` | `C35814Ff9` | Flows-Preload-URL |
| **6060** | string | gleich | `EP6`, `C33350Efe` | Flows-Basis für `/json/<id>` |
| **7125** | string | `.../flows/cache_management/` | `C39066GzF` | URL des Flows-Cache-Cleaners |
| **7126** | int | 1382400 | `C39066GzF` | Cleaner-Intervall/Aktivierung (Einheit unknown; > 0 aktiviert) |
| **8552** | bool | false | `FlowsWebViewDataRepository.A07` | Flow-JSON nativ holen und an die Seite übergeben |
| **14825** | bool | false | `FlowsWebViewDataRepository.A06` | `www_proxy_secret` und `flow_token_signature` übergeben |
| **22787** | bool | false | `C31338Djl` | Flows in separater Activity vs Bottom Sheet |
| **24781** | bool | false | `FlowsWebBottomSheetContainer` | Ohne ihn schließt sich ein wiederhergestelltes Sheet selbst |
| **14222** | bool | false | `C31338Djl` | Gate im Flows-Startpfad (genaue Wirkung unknown) |
| **5333**, **1319** | bool | false / false | `C45J` Flows-Variante | Beide an: Flows-Layout-Fehler werden als `extensions-layout-unexpected-error` gemeldet |

Flag-IDs nutzen den numerischen Raum von `WA_AB_PROPS.md`.

---

## 9. Baileys (`baron-baileys-v2`)

Ein Baileys-Client hat keinen Renderer, daher sind Bloks und Flows Web außer Reichweite. Berührbar ist der nachrichtengetragene Teil und prinzipiell das IQ.

| Ziel | Was funktioniert | Warum es scheitern kann | Fix |
|------|------------------|-------------------------|-----|
| Flow-Button senden | `interactiveMessage.nativeFlowMessage.buttons[]` mit `name: 'galaxy_message'` und `buttonParamsJson` mit den Keys aus 4.2 (`flow_message_version`, `flow_id`, `flow_token`, `flow_cta`, `flow_action`, `flow_action_payload`) | Der Empfänger braucht einen Business-JID-Kontext, numerische `flow_id`, `flow_token`, `flow_cta`; Nutzer-Sender (kein Business) werden voraussichtlich nicht berücksichtigt (inferred) | Von einem Business-registrierten Account senden; `flow_id` numerisch halten |
| Unbekannten Button-Namen verwenden | keine | `C33370Efz` verwirft Namen außerhalb der 39 + 2 | Einen Namen aus 4.1 verwenden |
| Ein Phoenix-Programm holen | `<iq xmlns="phoenix" type="get"><fds config=... /></iq>` | Der Server entscheidet nach Account-/App-Zustand; Antwortinhalt nie mitgeschnitten | Nicht versucht; als unknown behandeln |
| Einen Bloks-Screen lesen | nicht anwendbar | Braucht das Graph-Token, die Doc-ID und die `bloks-versioning-id`; kein Baileys-Pfad | Außerhalb des Umfangs |

---

## 10. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|---------|-----|
| `ResourceNotFound` und der Flow endet | `resource`-State nennt eine id, die nicht in der Registry steht (oder eine gegatete Brazil-id auf einem nicht passenden Build) | IDs aus 2.5 verwenden |
| `state not found for name: <x>` | `next` zeigt auf einen fehlenden State oder auf einen `version_check`-State (von `C58392QJx.A01` verworfen) | Ziel als unterstützten Typ deklarieren |
| `unsupportedComparisonTypes` / `comparingValuesWithDifferentTypes` | Operator auf falsche Typen angewendet | Typen angleichen; `catch` verwenden; `NOT_CATCHABLE_ERROR` kann nicht abgefangen werden |
| `FdsIqResource/execute: can't find FdsManager from the job_id` | `send_fds_iq` außerhalb einer laufenden Session | Innerhalb der Session ausführen, die es gestartet hat |
| Bloks `Invalid XMLNS` | `wa.action.IQRequest` mit einer xmlns außerhalb der Allow-List | Nur `w:pay`, `urn:xmpp:whatsapp:account` |
| `FcsScreenOpenerBloksDelegate: app_id is not present` | `open_bloks_screen*` ohne `app_id` | `app_id` übergeben |
| `error.code` 3489039 | Integritätsprüfung verlangt (Pre-Consent-Fetch) | Client wiederholt nach der Prüfung |
| Flows-Seite leer, Log `Uri is blocked` | Navigation verließ den Launch-Host oder nutzte ein Nicht-https-Schema | Inhalt auf dem Launch-Host halten |
| `extensions-bridge-api-input-parse-error` | Bridge-Nachricht ist kein gültiges JSON der erwarteten Form | `{method, data, callbackID}` senden |
| iabjs `invalid_nonce` | Falsche oder fehlende Nonce | Die injizierte `__iabjs_unified_bridge_nonce` verwenden |

---

## 11. Zentrale Unterscheidungen

| Nicht verwechseln | Unterschied |
|-------------------|-------------|
| Phoenix vs Bloks | Phoenix = Kontrollfluss über IQ; Bloks = Screens über GraphQL; sie treffen sich bei `open_bloks_screen*` und `wa.action.phoenix.*` |
| FCS vs FDS | Beide kommen vor: `flowconfigurationservice` (Paket, `FcsStateMachine`) und `FDS` (IQ-Manager, `<fds>`, Log `FDSManage`); die Auflösung von "FDS" steht nicht im Code |
| Manifest vs Code | `phoenix-features.json` listet 12 Resource-IDs und 21 Operatoren; der Code hat 15 Resource-IDs und 28 Operatoren; der Code gewinnt |
| `open_bloks_screen_static` vs `open_bloks_screen` + `fetch_channel=STATIC` | Nur Letzteres hat einen Handler |
| Bloks-Baum-Keys vs Opcodes | Baum-Keys sind Komponenten-Code-Points; Skript-Köpfe sind Funktions-IDs (Base-36) |
| Flows Web vs Flows Bloks | Zwei Renderer für `galaxy_message`: WebView (`flows.whatsapp.net`) und `com.bloks.www.whatsapp.galaxy.flow.v2` |
| Bloks-GraphQL vs MEX | Bloks postet an `graph.<domain>/graphql` mit `doc_id`; MEX ist die XMPP-getragene Query-Schicht, die anderswo genutzt wird |
| iabjs-Nonce vs Flows-Bridge | iabjs nutzt eine Nonce pro Handler im Envelope; die Flows-Bridge hat keine Nonce, sie stützt sich auf den Port-Handshake und die URL-Policy |
| Rich Response vs Bloks | Rich Response ist ein festes Protobuf-Set; Bloks ist ein programmierbarer Baum |

---

## 12. Kompletter Ablauf

```
[Server]                                          [WhatsApp client]
   │  message: interactive nativeFlowInfo name        │
   ├─────────────────────────────────────────────────►│ C33370Efz: name in registry? gated?
   │        address_message              galaxy_message│
   │             ▼                              ▼      │
   │  Phoenix start C58392QJx.A08       Flows launch C31338Djl: SecureWebView (https, launch host)
   │  IQ <iq xmlns="phoenix"><fds config>      + MessageChannel init-port, or Bloks galaxy.flow.v2
   │◄────────────────────────────────────────────────┤
   │  <fds><states start_at><state type=..>           │
   ├─────────────────────────────────────────────────►│ QKb.A03 loop: resource | choice(28 ops) | pass | subflow | succeed
   │                                                  │ resource -> registry: open_bloks_screen_graphql, send_fds_iq, abprop_fetch, ...
   │  POST graph.<domain>/graphql {doc_id, variables{app_id, versioning id, params}}  (route by app_id: C5LX)
   │◄────────────────────────────────────────────────┤
   │  layout.bloks_payload {tree, ft, component_queries, ...}
   ├─────────────────────────────────────────────────►│ AbstractC122255Jb: tree (code-point keys) + Lispy (base-36 ids)
   │                                                  │ user action -> bk.* / wa.* function id
   │◄── IQ (w:pay | urn:xmpp:whatsapp:account only) ──┤ wa.action.IQRequest
   │                                                  │ wa.action.phoenix.FdsIq / FcsReturnResult -> back into QKb (next / catch / end)
   │◄── WAExtensionsComplete -> native-flow response ─┤
```

---

## 13. Unbekanntes

| Punkt | Status |
|-------|--------|
| Auflösung von "FDS"; Bedeutung des `L8E.A1T()`-Gates | unknown |
| Zuordnung Component-Code-Point zu Name; Lispy-Namen jenseits der 681 gelisteten; Text-Form-Parser | unknown |
| Handler-Code der meisten `wa.action.*` / `bk.action.*`-IDs (über numerische id erreicht) | unknown |
| Echter Server-Inhalt: es wurde kein Phoenix-Programm und kein Bloks-Screen mitgeschnitten | unknown (nur statisch) |
| Transport von `xwa_flows_make_flow_endpoint_request`; welchen Renderer ein `galaxy_message` nimmt; Wirkung von AB **14222** | unknown |
| Disk-Cache-Ort, -Größe, -Eviction; iabjs-Set erlaubter Origins; serverseitige Integrität jenseits von TLS | unknown |
| Ob in einem anderen Build ein Framework im Genie-Stil existiert | unknown |
