# WhatsApp Server-Driven UI — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-23
**Scope:** Server-driven screens and actions on Android: Phoenix/FCS action state machine (IQ `xmlns="phoenix"`, state types, choice operators, resource registry), Bloks screens (GraphQL fetch, doc ids and app-id routing, JSON payload, Lispy function ids, action namespaces, component queries, caches), native flow messages (NFM button registry), WhatsApp Flows (WebView bridge, SecureWebView host policy, flow JSON), AI rich response and FMX card (what is not server-driven), in-app browser scripts (iabjs bridge and nonce), sandboxing and feature flags, Baileys relevance

---

## 1. What it is (technically)

WhatsApp Android has no single server-driven UI engine. Four independent mechanisms exist; each fetches a description from a server (or reads it from a message) and drives native code. All statements come from static analysis of the decompiled APK; nothing was captured on the wire. Tiers: **found** = read in code or data, **inferred** = deduced, **unknown** = not resolved. Obfuscated names are per-build and were re-resolved in 2.26.41.6.

| Mechanism | Describes | Carrier | Renderer / executor | Where it is used |
|-----------|-----------|---------|---------------------|------------------|
| Phoenix (class names say FCS "flow configuration service", log tag FDS) | Flow control: states `resource` / `choice` / `pass` / `succeed` / `subflow` | IQ `<iq xmlns="phoenix">` with child `<fds>` | `QKb` state machine, resource handlers (`AbstractC57917Pxu`) | Payments onboarding, address message, business survey, Brazil card flows |
| Bloks | Screens: component tree + Lispy scripts + async component queries | HTTPS GraphQL POST to `graph.<domain>/graphql` | Litho/RenderCore host activities and fragments | Payments, support, subscriptions, consent, Accounts Center linking, minishops, surveys, Meta AI business consent |
| Native flow messages (NFM) | Buttons on interactive messages (`nativeFlowInfo` name + params JSON) | Message (protobuf) | `C33370Efz` dispatch to about 40 action classes | CTA buttons, `address_message`, `galaxy_message` (Flows) |
| WhatsApp Flows web app | Flow JSON rendered by a hosted web app | HTTPS (`flows.whatsapp.net`) into a `SecureWebView` + a `WhatsAppBridge` message channel | `WaFlowsWebViewBottomsheetModalActivity` / `FlowsWebBottomSheetContainer` | Business forms (`galaxy_message`, flexible checkout) |

Decisive points:

- Phoenix is the control layer, Bloks is the view layer. A Phoenix `resource` state with id `open_bloks_screen_graphql` opens a Bloks screen; Bloks actions `wa.action.phoenix.*` lead back into the state machine (section 3.5; wiring inferred from the names).
- Bloks is not MEX and not IQ. It is a Meta-style GraphQL POST (`doc_id` + `variables`) over HTTPS (found, `AbstractC40195HfH`). Phoenix is IQ. The Flows endpoint query result class (`AnonymousClass456`) shares the Bloks response-parser base; its transport is not resolved (section 4.5).
- Server content cannot name arbitrary native code. Every route goes through a fixed registry: Phoenix resource ids (15 in code), Bloks function ids (681 named), NFM button names (39), Flows bridge methods (30), Bloks IQ xmlns allow-list (2 entries).
- No payload signature verification was found for Bloks or Phoenix payloads. `BloksTrustedPayload` (`verifiedRoot`) exists and has zero references (found, smali and Java).
- Not server-driven: the FMX trust card (client-created system message), AI rich response (fixed protobuf component set), the three `assets/json/bloks_*_template.json` files (loading/error scaffolds, not product screens).

Related reports: AB props (`abt` IQ, flag ids) in `WA_AB_PROPS.md`; AI rich response in `WA_META_AI.md` section 6.3. No Genie-named framework was located (string search; absence not proven).

---

## 2. Phoenix action state machine

### 2.1 Components (found, 2.26.41.6 names)

| Role | Class | Notes |
|------|-------|-------|
| Runtime | `QKb` | Log tag `FcsStateMachine`; `A03` runs one state, `A04` follows `next` or pops the stack, `A05` terminates |
| FDS manager | `C58392QJx` | Starts a config (`A08`), sends the IQ (`A07`), builds the state map from the response (`A01`) |
| IQ builder | `C31107Dfz` (ctor with `C9E1`), `C9E1`, `C31085Dfd` | `xmlns="phoenix"` |
| Response parsers | `F7J` (`<iq><fds>`), `F8I` (cases 17 to 20, 27, 28), `F7Y` resource, `F7Z` choice, `C34784F7b` pass, `C34783F7a` succeed, `C34785F7c` subflow, `C34786F7d` version_check | Generic attribute-schema parser (`C197428ac`) |
| Parsed states | `P2W` resource, `P2U` choice, `P2T` pass, `P2S` succeed, `P2V` subflow, `C31057DfB` version_check | Common part `P2Q`: `name`, `input_path`, `input_selector`, `next`, `result_selector`, `result_path` (`C33411Ege.A03`) |
| Runtime states | `C55819P7c` resource, `C55817P7a` choice, `C55818P7b` pass, `P7Z` succeed, `C55820P7d` subflow | Mapping in `C58392QJx.A01` |
| Resource base | `AbstractC57917Pxu` | `A02()` = resource id, `A04(...)` = execute with param map, default id `throw_error` |
| Binding / registry | `C51E` (id + lazy handler), `InterfaceC148426Oz.CP3()`, union `C138515tp` | Registries: `C135435oi`, `C135425oh`, `C135415og`, `C53207NpW`..`C53211Npa` |
| Operators / errors / callback | `RsJ` (28 operators), `AbstractC56245PPq`; `Q6G` (`catch`); `C57560Pry` (`A00(error, result)`, `A01(result)`) | |

### 2.2 Fetch: IQ (found, `C31107Dfz`, `C58392QJx.A07`)

```
<iq xmlns="phoenix" type="get|set" id="...">
  <fds config="<config name>" state="<start state>" parameters="<json>">
    <context ... parameters='{"session-id":"...","bloks-versioning-id":"13c6e3b8...(64 hex)"}'/>
  </fds>
</iq>
```

| Item | Value | Tier |
|------|-------|------|
| `type` | `get` on start (`A08`), `get` or `set` for the `send_fds_iq` resource | found |
| IQ type ints / timeout | 302 (get), 303 (set), 32000 ms | found |
| `state`, `parameters` | only written when non-empty; `parameters` = JSON of non-null entries | found |
| `bloks-versioning-id` | constant 64-hex string, same value in every Bloks request builder (section 3.2) | found |
| Context node nesting | `<context>` carrying the JSON; exact nesting of the inner node not resolved | unknown |

Response (found, `F7J`, `F8I`):

| Element | Content | Used for |
|---------|---------|----------|
| `<fds>` attrs `state`, `parameters` | start hint | parsed, not traced further |
| `<states start_at="...">` + `<state ...>`+ | the program (section 2.3) | `QKb` init, log `initializeStateMachine num_states` |
| `<next_screens>` + `<screen is_entry_screen app_id bloks_server_params sources>` | Bloks screens to preload | `C58392QJx.A06` (preload) |
| `<screen_data parameters>` | screen data blob | parsed |
| `<persist_data>` + `<data ...>` | values the host keeps | `C58392QJx.A02` (callback per key) |

An IQ error is returned to the caller as `error` (`BtN`) and the pending manager entry is removed.

### 2.3 State types (found)

Parser accepts the discriminator list `FDSResourceState|FDSChoiceState|FDSSucceedState|FDSPassState|FDSSubflowState|FDSVersionCheckState` (`F8I` case 27). Attribute `type` is the fixed string in the second column.

| Type | `type` | Own attributes | Runtime behaviour |
|------|--------|----------------|-------------------|
| Resource | `resource` | `id` (resource id), `parameters`, `merge`, `merge_param`, `catch` | Looks up `id` in the registry; missing id gives error `ResourceNotFound`; runs handler; result merged per `merge`; goes to `next` |
| Choice | `choice` | `default` (fallback next state), `catch`, children `<choice choice="{json}"/>`+ (one operator key + `next`) | Evaluates operators on the input JSON; first match wins, else `default`; at least one choice required |
| Pass | `pass` | `parameters` | Rewrites data and goes to `next`, no handler |
| Succeed | `succeed` | none | Terminal success (`A05` with no error) |
| Subflow | `subflow` | `launch_mode` (`child` or `embedded`), `config`, `parameters`, `catch` | `child`: new manager and state machine; `embedded`: fetches another config into the same session (inferred from `C55820P7d`) |
| Version check | `version_check` | `default`, child `<choice>` | Parsed (`C31057DfB`) but has no branch in `C58392QJx.A01`; the state is dropped (found); a transition to it would fail with `state not found for name` (inferred) |

The parser has no `fail` state; the manifest still lists `fail` (2.7).

Selectors and data (found):

- `input_selector` default `"$"`; the string `"null"` disables it (`C58392QJx.A01`). `result_selector` and parameter merging go through `AbstractC58328QFo`. A JSONPath-style engine is used for `catch` (`Q2G`, expressions like `$.[i].error_equals`) (found); that selectors use the same engine is inferred.
- `merge` modes in `QKb.A03`: `replace` (default), `merge`, `incremental_merge`, `wae_commerce_merge` (found).
- `catch` = JSON array of `{error_equals:[names], next:<state>}`; an empty `error_equals` matches everything (found, `Q6G.A00`). Unmatched errors terminate the machine with the error (`A05`).
- Errors raised by the interpreter itself: `ResourceNotFound`, `FailToResume`, `unsupportedComparisonTypes`, `comparingValuesWithDifferentTypes`, `genericChoiceStateError`; handler default error `NOT_CATCHABLE_ERROR` (`C5I7.A03`) (found).

### 2.4 Choice operators (found, `RsJ.A00`)

28 classes. The manifest lists 21; seven legacy names are in code only.

| Group | Names |
|-------|-------|
| Boolean | `and`, `or`, `not`, `booleanEquals` |
| Equality | `eq`, `neq`, `eq_any`, `neq_any`, `eq_path`, `neq_path`, `eq_any_path`, `neq_any_path`, `stringEquals` |
| Ordering | `gt`, `gte`, `lt`, `lte`, `gt_path`, `gte_path`, `lt_path`, `lte_path`, `numericalEquals`, `numericalGreaterThan`, `numericalGreaterThanEqual`, `numericalLessThan`, `numericalLessThanEqual` |
| Other | `isPresent`, `regex_match` (`variable` + `regex_match`) |

Each operator is selected by key presence in the choice JSON (`AbstractC56245PPq.A00`); a `JSONException` skips to the next operator. `_path` variants compare against a value resolved from a path (inferred from the name); exact resolution not read.

### 2.5 Resource registry (found)

Registered through `InterfaceC148426Oz.CP3()`; ids are held by `C05T.A00(n)` suppliers. Registries `C53207NpW`..`C53211Npa` return a set only when `L8E.A1T()` is true (`C18780mK.A03()` equals `C21610rj.A0E`); what that predicate means is unknown.

| Resource id | Handler | In `phoenix-features.json` | Behaviour |
|-------------|---------|----------------------------|-----------|
| `open_bloks_screen_graphql` | `C954246c` | yes | Opens a Bloks screen; param `app_id` required (cast fails otherwise) |
| `open_bloks_screen` | `C954346d` | no | Same, `fetch_channel` = `GRAPHQL` (uses `bloks_server_params`) or `STATIC` (uses `fetch_channel_params.static_url`, sets `should_load_bloks_through_cdn: true`); other values throw |
| `send_fds_iq` | anon in `AbstractC79003We` | yes | Params `config`, `type` (`GET`/`SET`), `state`, `parameters`; needs a live FDS manager by job id; missing manager or config logs an error and fails with `NOT_CATCHABLE_ERROR` |
| `abprop_fetch` | anon in `AbstractC79003We` | no | Params `code` (int), `abprop_type` (`string`/`json`/`boolean`/`float`/`integer`), `default_value`; returns `abprop_value` read from the AB store; no allow-list on `code` seen |
| `client_dasl_query` | `C954746h` | yes | Needs param `query`, else logs `No parameters` and fails; query executes on a background executor |
| `dismiss_bottom_sheet` | `C955346n` | yes | Closes the current sheet |
| `native_flow_call_manager` | `C954946j` | yes | Needs `phone_number`; strips to digits and `+`; starts `ACTION_DIAL` (`tel:`) with `FLAG_ACTIVITY_NEW_TASK` (dialer only, no auto-call) |
| `request_permission` | `C955046k` | no | Android permission request (link to `FcsRequestPermissionActivity` inferred) |
| `throw_error` | `C954446e` | no | Raises `error` map; looks up message by `error_map_type` + `code` |
| `payment_encrypt_with_public_key` | `C31703Dr4` | yes | Params `data_value`, `data_type`, `key_scope`, `provider_name`, `network` (gated) |
| `br_verify_card_deeplink` | `C955446o` | yes | Sends a package-restricted broadcast `com.whatsapp.payments.phoenix.action.launch_activity_for_phoenix_result` with `app_to_app_partner_app_package`, `app_to_app_partner_intent_action`, `app_to_app_request_payload` (gated) |
| `br_verify_card_check_if_app_exists` | `C31702Dr3` | no | Gated |
| `native_br_compliance`, `native_br_p2m_checkout_address`, `native_card_encryption_resource` | `C955146l`, `C955246m`, anon | no | Brazil payments, gated except the card one |

Manifest-only names (no registry entry in this build): `error_response`, `native_flow_npci_common_library` (sub-tree `mode.collect`), `native_p2m_lite_compliance`, `native_p2m_lite_hpp_checkout`, `open_bloks_screen_static`. `open_bloks_screen_static` has no handler; the STATIC path lives inside `open_bloks_screen` as `fetch_channel`.

### 2.6 Launch points (found)

`new C57778Pva(config, params, startState)` is built at: `address_message` (`C31337Djk`, NFM), `biz_survey` (`C57417PpS`), `br_merchant_onboarding` (`C33140EcF`), `br_p2m_checkout_add_card`, `br_p2p_verify_card` (`C32703EOj`), and a deep-link entry that passes a server-named config with start state `DeepLink` (`RunnableC46615KYo` case 18, referral `deeplink`). Strings `add_card_phoenix`, `verify_card_phoenix` exist; their role as config names is inferred. The config program itself comes from the server; none is shipped except the capability manifest.

### 2.7 Capability manifest

`assets/versioning/phoenix-features.json` (1,218 B, identical to the 2.26.34.4 copy): top-level `pass`, `choice` (21 operators), `resource` (12 ids plus `input_selector`, `parameters`, `result_selector`, `result_path`), `succeed`, `fail`. Its use at runtime was not located (no string reference found); treat as a name list. Code is the authority (2.4, 2.5).

---

## 3. Bloks

### 3.1 Host surfaces (found)

| Host | Role |
|------|------|
| `WaBloksActivity`, `WaBloksBottomSheetActivity`, `BloksCDSBottomSheetActivity`, `BloksCDSPreloadCDSBottomSheetActivity` | Full screen, bottom sheet, CDS (design system) sheets |
| `WaSqBloksActivity`, `WaBloksScreenQueryFragment` | Screen-query hosts (`screen_query` vs `legacy_screen` types) |
| `WaFcsModalActivity`, `WaFcsBottomSheetModalActivity`, `WaFcsPreloadedBloksActivity`; `SurveyCanonicalBloksActivity` (+ sheet) | Phoenix-hosted screens; surveys |
| Product hosts | `CommonBloksActivity`, `SupportBloksActivity`, `BrazilPayBloksActivity`, `ConsumerSubscriptionBloksActivity`, `DigitalCommerceDcpBloksActivity`, `CsatSurveyBloksActivity`, `AppointmentBloksHostActivity` (exported false), `WaBackupStorageBloksActivity` (exported false) |

No Bloks, Flows or Phoenix activity declares an intent filter; `targetSdkVersion` is 36, so activities without `android:exported` are not exported (found, manifest). Bloks can also embed a `WebView` component (`AndroidBridge.updateSize`, action `bk.action.WebViewWithOnChange`) (found).

### 3.2 Fetch: GraphQL over HTTPS (found, `AbstractC40195HfH`, `C45J`)

| Item | Value |
|------|-------|
| URL | `https://graph.<domain>/graphql<path>`; `<domain>` = pref `pref_graphql_domain`, default `whatsapp.com`; several request classes force `facebook.com`; `<path>` empty, or `/extensions` for the Flows variant |
| Query string | `?_emp=1` appended when AB prop **549** is on (default false) |
| Body | JSON `{"variables": "<json string>", "access_token": ..., "doc_id": <long>, "lang": ..., "Content-Type": "application/json"}` |
| Token | per-request token if set, else a static app-scoped token string embedded in the client (value not reproduced) |
| Headers | `X-FB-Friendly-Name: WABloksAppRootQuery-<app_id>`, `X-FB-Request-Analytics-Tags` |
| `variables` | `app_id`, version key, `params` (JSON string), `bloks_theme_params` |
| Version key name | `version`, `versioning_id` or `bloks_version` depending on request class; value is the same 64-hex constant as in Phoenix |
| Pre-consent variant (`C136975rF`) | adds `app_version`, `locale`, `df_token`, `enc_token`, `disclosure_id`, `is_paused`, `country_code`, `encrypted_rid` |
| Extensions variant (`C132735kG` case 2) | `extension_id` (= `flow_id` for flow message versions 2, 3, 4), `business_jid`, `screen_id`, `bloks_version` |
| Errors | `errors[].extensions.error_code` (default 417), `is_retryable`; `error.code` 3489039 triggers an integrity check and retry, 1675012 gives `Bad Request` (pre-consent path) |

Response root fields (`AnonymousClass451.A05`): the payload is `data.<root>.payload` (a JSON string).

| Doc id | Root field | Used by (found) |
|--------|------------|-----------------|
| 3651100555017197 | `whatsapp_bloks_getlayout` | default route; minishops link/pdp/storefront |
| 3958953970834604 | `whatsapp_bloks_getprivatelayout` | default for `C5LX.A00()`; minishops privacy notice, products preview |
| 9404809712971896 | `whatsapp_bloks_getlayout` | regex-routed families (3.3) |
| 9943385105682204 | `whatsapp_bloks_getprivatelayout` | `logged_out.cxthelp.whatsapp` |
| 6019334944816363 | Flows layout (root `whatsapp_galaxy_bloks_getflowlayout` exists in `AnonymousClass424`; link between the two inferred) | `com.bloks.www.whatsapp.galaxy.flow.v2`, `...commerce.galaxy_message`, `...commerce.extensions_message_v2` |
| 36103976949247233 | `wamo_bloks_get_layout` | WAMO surfaces |
| 9676557989071413 | not mapped to a root field | payments sample/care, `novi.care.*`, `whatsapp.ai.biz.*` consent |

Doc ids 26891716230495873 (pix playground) and 25865201793138751 appear in the routing tables without a resolved root field.

### 3.3 App-id routing (found)

A screen is addressed by `app_id` (a dotted name, `com.bloks.www.*`). Routing tables map an `app_id` to a query descriptor `C5LX(doc id, request-factory variant)`: ten fixed-set tables (`InterfaceC148576Pp`: `C132235jS`..`C132335jc`) and regex tables (`InterfaceC148726Qe`: `C132345jd`..`C132465jp`).

| Family | Pattern or example | Doc id |
|--------|--------------------|--------|
| Orders / payments hub | `orders_hub(\..+)*`, `fbpay_hub`, `payment.mft.wallet.fbpay_hub`, `(payment.)?mft.wallet.*`, `payment.(bloks.(commerce|ecp).checkout|fbpay.ecp).*` | 9404809712971896 |
| `gai` / `sna` / AI stickers (family meaning inferred from names) | `bloks.nme.gai`, `wa.nme.gai`, `wa.sna`, `whatsapp.ai.stickers.*` | 9404809712971896 |
| Subscriptions | `dcp.subscriptions?(\..+)*` | 9404809712971896 |
| Support | `(csf|cxthelp)(\..+)+` | 9404809712971896 |
| Minishops | `minishops.link.app`, `.whatsapp.pdp`, `.storefront.wa` | 3651100555017197 |
| Business AI consent | `whatsapp.ai.biz.{learn_more,consent,assistant_consent,third_party_consent,meta_ai_consent}` | 9676557989071413 |
| Playground / debug | `wa.playground.payments.br.pix.*` (variant 9) ; `whatsapp.payments.phoenix.{debug,demo_*,multi_*}`, `payments.whatsapp.f2care`, `novi.care.*` (variant 10) | 26891716230495873 ; 9676557989071413 |

87 distinct literal `com.bloks.www.*` ids sit in code; the rest arrive from the server and are routed by the regex families. Two pattern guards exist in `AnonymousClass514`: `consent(...)` ids may carry `extra_params_json.whatsapp_bloks_networking_feature_override`; `payment.mft.security.*` with `ptt_use_case = WALLET` selects request helper `wallet_canonical` (found).

### 3.4 Payload format (found)

Streaming JSON parser `AbstractC122255Jb`; the top object has `payload` (string) and `layout.bloks_payload`.

| `bloks_payload` key | Meaning |
|---------------------|---------|
| `tree` | Root component (section below); `action` instead of `tree` for action-only payloads |
| `ft` | Function table: id to expression string |
| `data`, `values`, `templates`, `props` | Data records (`id`, `type`, `data`, `scoped`), value expressions, templates, prop name table |
| `embedded_payloads`, `hoisted_async_components` | Nested payloads by id |
| `referenced`, `referenced_external`, `referenced_embedded_payloads`, `referenced_templates`, `referenced_ft_entries`, `referenced_values`, `referenced_ct`, `ct` | Dependency lists for partial/streamed payloads |
| `component_queries` | Async component queries (`id`, `app_id_expr`, `params`, `client_params`, `targets`, `cache_ttl_expr`, `disk_cache_enabled`, `is_scoped`) |
| `error_attribution` | `logging_id`, `source_map_id` |
| `depth`, `step_debugger_metadata.breakpoints` | Streaming depth, debugger |

Tree encoding (`C5AN`): a node is an object whose single key is one code point; that code point is the component id (`AbstractC105654gT.A00` = `codePointAt(0)`); attribute keys are also single code points (`!`=33 id, `#`=35 child, `&`=38, `+`=43 for the shadow component 13347). The component id to name map is not in the assets (unknown).

Function ids ("Lispy", `C122545Ki`): a script node is a JSON array whose first element is the function: `"#<name>"` named, a dotted name resolved through the name table `AbstractC111054pC.A01`, or a base-36 string parsed with `Integer.parseInt(s, 36)`. Typed constants have fixed ids: 17809 `bool.Const`, 18327 `f32.Const`, 18338 `f64.Const`, 19222 `i32.Const`, 19237 `i64.Const`. The name table has 681 entries, ids 17293 to 26071.

Decoded from the shipped templates (base-36 token, id, table name; found): `e2a` 18226 `core.If`; `e25` 18221 `core.GetArg`; `e2f` 18231 `core.TakeLast`; `e1w` 18212 `core.Apply`; `dng` 17692 `bloks.GetParameter`; `dnt` 17705 `bloks.GetVariable2`; `f4g` 19600 `map.Get`; `f6m` 19678 `mins.CallRuntime`; `igq` 23930 `core.AsNonnull`; `fjm` 20146 `screen.callback.DidFetchSucceed`; `foz` 20339 `ttrc.MarkerStart` (all under `bk.action.`); `h9h` 22373 is listed with the literal name `null`.

The `\t(...)` text form in `ft` and expression strings is a different serialisation; that it uses the same base-36 ids follows from the decodes above being coherent (inferred). The text parser was not read.

Capability negotiation (inferred): the 64-hex `bloks-versioning-id` is sent with every request; the table holds 50 `bk.versioning.*` capability names (for example `SupportsFunctionTables`, `TemplatePayloads`, `AsyncComponentBatchedWireProtocol`, `SupportsLispySignatureMinification`). That the hash identifies this capability set is inferred.

Shipped assets (`assets/json/bloks_screen_template.json`, `bloks_bottomsheet_template.json`, `bloks_cds_base_screen_template.json`, 9,028 / 9,124 / 11,443 B, identical to 2.26.34.4): root template with a spinner `tree`, one `component_queries` entry whose target is `genScreenContent`, and an error fallback in `embedded_payloads` (`Something went wrong` / `Please try again later` in two of the three). They are scaffolds; product screens come from the query result.

### 3.5 Action namespaces (found, `AbstractC111054pC`)

| Prefix | Count in id table | Examples |
|--------|-------------------|----------|
| `bk.action.core/bool/num/i32/i64/f32/string/array/map/math` | 113 | `core.If`, `core.Let`, `core.While`, `array.Map`, `string.*` |
| `bk.action.mins.*` | 36 | `CallRuntime`, `PutByVal`, `Raise` (minscript VM) |
| `bk.action.bloks.*` | 61 | `OpenScreen`, `OpenBottomSheet`, `Inflate`, `FetchAsyncComponents`, `WriteLocalState`, `ReplaceChildren`, `WriteGlobalConsistencyStore` |
| `bk.action.cds.*`, `bk.callbacks.cds.*` | 13 + | `OpenCdsBottomSheet`, `PushCdsBottomSheet`, `UnwindToScreen` |
| `bk.action.animated/animation/timer/collection/textinput/text_input/video` | 58 | UI behaviour |
| `bk.action.qpl/ttrc/trace` | 14 / 11 / 2 | Latency markers (`ttrc.MarkerStart`) |
| `bk.action.privacy.consent.*` | 10 | `OpenFlow`, `LaunchConsent`, `ShutdownExperience` |
| `bk.action.waffle.*`, `bk.fx.*`, `bk.waffle.*` | 37 / 11 / 2 | Accounts Center linking: `EncryptPassword`, `DeleteLocalUserCredentials`, `GetProfilePictureUrl`, `UnpauseWithNativeAuthBlob`, `PregenerateAndCacheRSAKeyPairs` |
| `bk.action.mft.*`, `bk.action.frontier.*`, `bk.action.apt.PleEncrypt`, `bk.action.commerce.GetPaymentToken`, `bk.action.payments.GetCreditCardMetaData` | 5 / 5 / 1 / 1 / 1 | Payments: `ModularGeneratePTT`, `LaunchGooglePaySheet`, `IsLuhnCompliant` |
| `bk.action.navigation.OpenUrl`, `bk.fx.action.OpenURLInIAB`, `bk.action.acp.OpenUrlExternally`, `bk.action.OpenUniversalLink`, `bk.action.DeeplinkToOtherAppOrDirectToAppStore`, `bk.action.bloks.IsAppInstalled` | 6 | Navigation out of Bloks |
| `bk.action.io.clipboard.SetString`, `bk.action.RequestPermission`, `bk.action.media.LoadAlbums`, `bk.fx.action.media.OpenMediaPicker`, `bk.action.foa.media.OpenCamera` | 5 | Device access |
| `wa.action.*` | 75 | WhatsApp host actions (table below) |
| `wa.callbacks.*` | 10 | `FormInputOnTextChange`, `CodeInputOnTextChange`, `DatePickerOnDateSet`, `CameraViewOnMediaCaptured`, `ListViewItemSelected` |
| `bk.versioning.*`, `wa.versioning.image.base64` | 50 / 1 | Capability names |

Notable `wa.action.*` (ids 22391 to 26071):

| Group | Names |
|-------|-------|
| Network | `IQRequest`, `AsyncRequest`, `UploadMedia`, `UploadProfilePicture` |
| Phoenix bridge | `phoenix.FdsIq`, `FdsIqV2`, `FcsReturnResult`, `FcsReturnResultV2`, `FcsReturnResumableData`, `statemachine.GoBack`, `GoBackV2` |
| App state | `GetAbPropValue`, `GetAppType`, `GetIntentParameter`, `LoadScreenParam`, `SaveScreenParam`, `IsDarkModeEnabled` |
| Navigation | `OpenUrl`, `RouteToNativeScreen`, `RouteToNativeBenefitDetail(V2)`, `navigation.OpenChat`, `OpenContactInfo`, `OpenNativeActionSheet`, `FinishActivity(WithResult)`, `PopScreen` |
| Messaging / commerce | `commerce.SendNFMReplyMessage`, `commerce.ActionWithCallback`, `share.Text`, `bonsai.SubmitFeedback`, `care.OpenContactSupport`, `care.OpenReportThisPayment` |
| Telemetry | `SendFieldStat(V2)`, `StartFieldStatTimer`, `GetFieldStatEventId`, `perf.TrackPerformance`, `novi.EncryptLogEvent(V2)` |
| Deeplink | `RegDeeplinkListener`, `DeregDeeplinkListener` |

Guard found on the Bloks IQ action (`C129575f5.A0Y`, log `IQRequestHelper/sendIQRequest: Invalid XMLNS`): only xmlns `w:pay` and `urn:xmpp:whatsapp:account` pass (`C33327EfH.A02`); anything else calls the `on_failure` callback. Bloks scripts can therefore send IQs only in those two namespaces (found). Handler implementations of most other `wa.action.*` ids were not traced (their code is reached by numeric id).

### 3.6 Component queries and caching (found)

- A `component_query` fetches an async component by `app_id` through the same GraphQL path (manager `C5L9`, log tag `BloksComponentQueryManager`); `app_id_expr`, `params`, `client_params` and `cache_ttl_expr` are Lispy expressions evaluated on the client.
- Two cache tiers: a memory cache (`cache_src: memory`, `cache_age`) and a disk cache keyed per query (`BloksComponentQueryDiskCache`; classes `C5NA`, `C5NN`, `C136885r6`). Disk records are Java-serialised (`ComponentQueryDiskCacheRecord`: `DiskCacheData{initialResponse, extensions}`, `responseTimestampMs`, `BloksComponentQueryResources`); metadata lives under `__disk_metadata`; a `Bloks_ACQ_ReadWriteThread` does the I/O. `disk_cache_enabled` is a per-query switch.
- Actions `bk.action.AsyncComponentCacheWrite`, `bloks.ClearCachedAsyncComponents`, `bloks.InvalidateCachedAsyncComponents` let a payload manage the cache.
- Directory, size limit and eviction of the disk cache: unknown. Java deserialisation of server-influenced cache records happens only from the app's own cache (inferred from the code path).

---

## 4. Native flow messages and WhatsApp Flows

### 4.1 NFM button registry (found, `AbstractC30032D4u` case 442, class `EYT`)

An interactive message carries buttons with `nativeFlowInfo.name` and a params JSON. Dispatch: `C33370Efz.A05` looks the name up in a map (`C0VA`) of about 40 `AbstractC33168Ech` subclasses; unknown names log `can not recognize NFM action` and are dropped; an action can be gated off (counters `wa:nfm_dispatch_gate_blocked` / `_observed`).

| Set | Names |
|-----|-------|
| Supported button names (39) | `cta_catalog`, `review_and_pay`, `review_and_pay_v2`, `cta_call`, `cta_url`, `cta_copy`, `cta_pix_code_copy`, `offer_payment_account`, `form_message`, `open_webview`, `catalog_message`, `voice_call`, `video_call`, `landline_call`, `quick_reply`, `single_select`, `view_product`, `call_permission_request`, `cta_app_link`, `appointment`, `automated_greeting_message_view_catalog`, `send_location`, `order_status`, `booking_confirmation`, `booking_status`, `psi_nux_opt_in`, `psi_tos_opt_in`, `psi_opt_outs`, `account_authentication_request`, `request_contact_info`, `agent_api_key`, `otp`, `payment_reminder`, `cta_reminder`, `payment_request`, `api_signup`, `inapp_signup`, `split_payment`, `send_payment` |
| Second set | `address_message`, `galaxy_message` (flow-launching; role inferred from use) |
| Mixed/quick-reply allow-list | `C33370Efz.A08`: `cta_url`, `cta_call`, `voice_call`, `video_call`, `cta_copy`, `menu_options`, `cta_reminder`, `view_product`, `cta_app_link`, `galaxy_message`, `otp`, `booking_*`, ... |

- `address_message` starts the Phoenix config `address_message` (`C31337Djk`, found).
- `galaxy_message` opens WhatsApp Flows (4.2).
- Flow replies are stored in `message_ui_elements_reply` (`flow_id`, `element_type` 8) and `interactive_message_bloks_widget` (found, SQL).

### 4.2 `galaxy_message` params and launch (found, `C31338Djl`, `C31337Djk`)

| Key in params JSON | Use |
|--------------------|-----|
| `flow_id` | must match `\d+` for the Flows v2 action |
| `flow_token`, `flow_cta` | required with `flow_id` (Flows v2 path) |
| `flow_message_version` | `2`, `3`, `4` select the extension variables of the Bloks query |
| `flow_action` (`navigate` default, `data_exchange`), `flow_action_payload` (object) | first screen / data channel |
| `mode` | `draft` marks a draft flow (`is_draft`) |
| `form_type` | routes to `FlexCheckoutNativeFormActivity` (flexible checkout) |
| `flow_token_signature`, `www_proxy_secret` | forwarded to the page only when AB prop **14825** is on |

The sender business JID comes from the chat (`FlowsV2Action`); without it the launch aborts (`cannot launch flow without business jid`). Two renderers exist: the web app (4.3) and a Bloks path (`com.bloks.www.whatsapp.galaxy.flow.v2`, section 3.2). Which one a given message takes is not resolved; AB props **22787** (separate activity vs bottom sheet) and **14222** are read on the web path.

### 4.3 Flows web app (found)

| Item | Value |
|------|-------|
| Base URLs (AB string props) | **7153** `https://flows.whatsapp.net/flows` (preload, `C35814Ff9`), **6060** same default (flow JSON fetch `EP6`: base + `/json/` + flow id, inferred from builder order), **7125** `.../flows/cache_management/` (cache cleaner `C39066GzF`, interval **7126** = 1382400), **16723** `.../flows-app/catalog` (catalog) |
| Host | `SecureWebView` (`com.facebook.secure.securewebview`): file and content access off; load allowed only if scheme is `https` AND host equals the launch URL host or a subdomain of it (`GAP.A00`, `H26`, combined with AND in `GAL`); otherwise log `Uri is blocked` |
| Launch URL | from the bundle (`url`, default `about:blank`); base is an AB prop, so the server can move it; the host policy follows the launch URL (inferred consequence) |
| Preload | `FlowsWebPreloader` loads AB **7153** in a hidden WebView (`setCacheMode(2)`); service-worker cache version tracked via `flows_service_workers_cache_version` |
| Page injection | `meta` tag with viewport, `layoutDirection`, `locale`, `timeZone`, `supportedStyles` |
| Bridge | `window.WhatsAppBridge.invoke(method, data, cb)`; native creates a `MessageChannel` and posts `init-port` with port 1 (`HQD`); messages are JSON `{method, data, callbackID}`; replies `{callbackID, responseData}` |
| Origin binding | The bridge script is injected with `evaluateJavascript` into whatever the WebView shows; the port is posted to target `Uri.EMPTY`; gating relies on the SecureWebView URL policy (inferred) |
| Flow JSON | `flow_json` fetched by `EP6.A01` (HTTP GET, stored on disk as a serialised string, key `<id>_<id2>`), only when AB **8552** is on; `FlowsWebViewDataRepository` builds the bundle (`flow_json`, `flow_action_payload`, `creation_source`, session ids) |
| Public key | `WAExtensionsGetPublicKey` returns the endpoint public key obtained by a GraphQL metadata call (`extensions-metadata-graphql-*` errors, mode `required` or `optional`); use for encrypting data is done page-side (inferred) |

Bridge methods handled natively (30; `C41342Hyk`, `FlowsWebBottomSheetContainer.CKc`):

| Group | Methods |
|-------|---------|
| Session | `WAExtensionsGetFlowData`, `WAExtensionsDataChannelExchange`, `WAExtensionsNavigate`, `WAExtensionsComplete`, `WAExtensionsClose`, `WAExtensionsGetPublicKey`, `WAExtensionsGetClientAbProps` |
| UI | `WAFlowsShowNativeInputDialogComponent`, `WAExtensionsConfigureNavBar`, `WAFlowsMediaSelect`, `WAFlowsMediaRetry`, `WAFlowsMediaDelete`, `WAFlowsCopyText`, `WAFlowsOpenURL`, `WAExtensionsLearnMore`, `WAExtensionsContextualHelp` |
| Business | `WAExtensionsSpamReport`, `WAExtensionsReportItem`, `WAFlowsDownloadResponse`, `WAFlowsMarketingDisclosureState`, `WAFlowsMarketingDisclosureUserAction` |
| Cart | `WAFlowsStoreShoppingFlowContext`, `WAFlowsGetCart`, `WAFlowsSetCartItem`, `WAFlowsClearCart` |
| Telemetry | `WAMLogger`, `WAQPLLogger.start`, `.end`, `.annotate`, `.point` |

Handling notes: `WAFlowsOpenURL` starts `ACTION_VIEW` only for `https` URLs, else a snackbar; `WAExtensionsGetClientAbProps` returns any AB prop by code and type (`bool`, `int`, `float`, `string`, `json`) with no allow-list seen (`C37367GJs`); unknown methods go to a default handler (`GJW`); input that fails to parse yields `extensions-bridge-api-input-parse-error`.

### 4.4 Flow completion

`WAExtensionsComplete` ends the session and the client sends a native-flow response message (`native_flow_response_*` columns; params carry `wa_flow_response_params`, `flow_creation_source`, `response_message`) (found by names; send path not traced).

### 4.5 Flows endpoint query

Result class `AnonymousClass456` reads root `whatsapp_galaxy_forward_flow_data_response` or `xwa_flows_make_flow_endpoint_request` and a `status_code`: 200 ok, 421 and 504 mapped to distinct outcomes, others generic failure (found). Whether this runs over MEX or the HTTPS GraphQL stack is unknown (the parser base is shared with Bloks).

---

## 5. Surfaces that are not server-described UI

### 5.1 AI rich response (message-carried, fixed components)

Protobuf `richResponseMessage` (see `WA_META_AI.md` section 6.3). Sub-message type enum `EnumC32139E2l` (found): `AI_RICH_RESPONSE_UNKNOWN` 0, `GRID_IMAGE` 1, `TEXT` 2, `INLINE_IMAGE` 3, `TABLE` 4, `CODE` 5, `DYNAMIC` 6, `MAP` 7, `LATEX` 8, `CONTENT_ITEMS` 9; code highlight classes (`KEYWORD`, `STRING`, `NUMBER`, `METHOD`, `COMMENT`, `DEFAULT`); dynamic metadata `IMAGE`, `GIF`. The client renders a fixed set; actions are file download / forward (`UnifiedResponseActionHandlerFactory`). No script language, no action DSL.

### 5.2 FMX card

The FMX card (`LE7`, view-model factory `fmxViewModelFactory`, avatar tag `fmx-card-v2`) is created by the client as a system message (`C198788cr`: `Creating FMX card system message for chat`); counters like `fmxBizEnterpriseSenders`, `fmxMissingLidMapping`, `fmxSuspiciousBottomSheetCacheMiss` show it is driven by local signals. Whether the server supplies any card text is unknown. Treat as native UI.

### 5.3 In-app browser scripts (iabjs)

`res/raw/iabjs_*` has 15 scripts in 2.26.41.6 (four more than the 2.26.34.4 set): `autofill_execute_callback`, `autofill_language_detect`, `autofill_payment_detection`, `otp_autofill` are new. Host `WaInAppBrowsingActivity` (exported false).

| Item | Value (found) |
|------|---------------|
| Bridge object | `iabjs_unified_bridge`: `addWebMessageListener(name, allowedOrigins, listener, jsWorld)` in the isolated JS world `iab_js` when supported (`HJY.A05`); fallback `addJavascriptInterface("iabjs_unified_bridge")` (`RunnableC40709HoJ`) |
| Page side | `window.__call_iabjs_unified_bridge(method, nonce, payload)` posts `{method, payload, nonce}`; nonce is substituted into `window.__iabjs_unified_bridge_nonce="%s"` at injection |
| Native check | `C39590HNn`: JSON `nonce` must equal the handler's stored nonce (generated once per handler by `AbstractC48382LBd.A00().toString()`, UUID-like, inferred); mismatch records `invalid_nonce` and drops the call; method `iabjs_register_proxy` registers the world; other methods go to listeners keyed by (world, method) |
| New in this build | `iabjs_autofill_payment_detection` classifies fields into `cc-number`, `cc-exp`, `cc-exp-month`, `cc-exp-year`, `cc-csc`, `cc-name` by `autocomplete` or name/id/placeholder regex; `iabjs_otp_autofill` fills `input[autocomplete="one-time-code"]`; `iabjs_autofill_language_detect` sends `languageDetermined` |
| Allowed origins set | caller-supplied `Set`; content not traced (unknown) |
| Legacy fallback | `addJavascriptInterface` has no per-origin filter (platform behaviour, inferred) |

Eight of the 11 older scripts are byte-identical to the 2.26.34.4 copies; `detect_login_forms`, `navigation_performance_logger_android`, `iabjs_bridge_init` changed (453 B vs 433 B for the bridge init).

---

## 6. Sandboxing and security summary

| Control | Where | Tier |
|---------|-------|------|
| Phoenix resource ids fixed in code; unknown id gives `ResourceNotFound` | `QKb.A03` | found |
| Phoenix operators fixed (28); unmatched operator skipped | `RsJ`, `AbstractC56245PPq` | found |
| Bloks IQ action limited to xmlns `w:pay`, `urn:xmpp:whatsapp:account` | `C33327EfH.A02` | found |
| Bloks function ids fixed (681 named) | `AbstractC111054pC`, `C122545Ki` | found |
| NFM names fixed (39 + 2); unknown dropped | `AbstractC30032D4u`, `C33370Efz` | found |
| Flows host: https + launch-host (or subdomain) only, no file/content access | `SecureWebView`, `GAP`, `H26` | found |
| Flows bridge: fixed method list; `WAFlowsOpenURL` https only | `FlowsWebBottomSheetContainer` | found |
| iabjs: nonce check, isolated world, origin set | `C39590HNn`, `HJY` | found |
| Phoenix `br_verify_card_deeplink` broadcast restricted to own package | `C955446o` | found |
| All Bloks, Flows, Phoenix activities lack intent filters; targetSdk 36 | manifest | found |
| Payload signature or hash verification of Bloks/Phoenix content | none located; `BloksTrustedPayload` unreferenced | found (absence in searched paths) |
| Server can read AB props by code (`abprop_fetch`, `WAExtensionsGetClientAbProps`) | no allow-list seen | found |
| Transport trust (TLS pinning, token handling for graph requests) | not analysed | unknown |

Consequence (inferred): trust rests on the transport and on the registries above; a compromised or malicious server-side program is limited to those registries, but the registries include payment encryption helpers, credential handling for Accounts Center, `ACTION_DIAL`, URL opening and AB reads.

---

## 7. Caching and preloading

Bloks component queries: memory + disk, TTL by `cache_ttl_expr` (3.6). Phoenix: server-listed `next_screens` are preloaded into `WaFcsPreloadedBloksActivity`; `persist_data` entries go to per-key listeners (found). Flows web: preload WebView, service-worker cache version, scheduled cleaner (AB 7125/7126), flow JSON disk cache, metadata ban marker `extensions_metadata_banned_<id>_<id>` in prefs (found).

---

## 8. Feature flags (defaults from `C08J`; meanings from the read site)

| ID | Type | Default | Read in | Effect |
|----|------|---------|---------|--------|
| **549** | bool | false | `AbstractC40195HfH.A03` | Appends `?_emp=1` to the GraphQL URL (unless `C0GD.A02()`) |
| **7153** | string | `https://flows.whatsapp.net/flows` | `C35814Ff9` | Flows preload URL |
| **6060** | string | same | `EP6`, `C33350Efe` | Flows base for `/json/<id>` |
| **7125** | string | `.../flows/cache_management/` | `C39066GzF` | Flows cache cleaner URL |
| **7126** | int | 1382400 | `C39066GzF` | Cleaner interval/enable (unit unknown; > 0 enables) |
| **8552** | bool | false | `FlowsWebViewDataRepository.A07` | Fetch flow JSON natively and pass it to the page |
| **14825** | bool | false | `FlowsWebViewDataRepository.A06` | Pass `www_proxy_secret` and `flow_token_signature` |
| **22787** | bool | false | `C31338Djl` | Flows in a separate activity vs bottom sheet |
| **24781** | bool | false | `FlowsWebBottomSheetContainer` | Without it, a restored sheet closes itself |
| **14222** | bool | false | `C31338Djl` | Gate in the Flows launch path (exact effect unknown) |
| **5333**, **1319** | bool | false / false | `C45J` Flows variant | Both on: Flows layout errors reported as `extensions-layout-unexpected-error` |

Flag ids use the numeric space of `WA_AB_PROPS.md`.

---

## 9. Baileys (`baron-baileys-v2`)

A Baileys client has no renderer, so Bloks and Flows web are out of reach. What it can touch is the message-carried part and, in principle, the IQ.

| Goal | What works | Why it may fail | Fix |
|------|------------|-----------------|-----|
| Send a Flow button | `interactiveMessage.nativeFlowMessage.buttons[]` with `name: 'galaxy_message'` and `buttonParamsJson` holding the keys in 4.2 (`flow_message_version`, `flow_id`, `flow_token`, `flow_cta`, `flow_action`, `flow_action_payload`) | Receiver needs a business JID context, numeric `flow_id`, `flow_token`, `flow_cta`; user (non-business) senders are unlikely to be honoured (inferred) | Send from a business-registered account; keep `flow_id` numeric |
| Use an unknown button name | none | `C33370Efz` drops names outside the 39 + 2 | Use a name from 4.1 |
| Fetch a Phoenix program | `<iq xmlns="phoenix" type="get"><fds config=... /></iq>` | Server decides by account/app state; response content never captured | Not attempted; treat as unknown |
| Read a Bloks screen | not applicable | Needs the graph token, doc id and `bloks-versioning-id`; no Baileys path | Out of scope |

---

## 10. Error cases

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ResourceNotFound` and flow ends | `resource` state names an id not in the registry (or a gated Brazil id on a non-matching build) | Use ids from 2.5 |
| `state not found for name: <x>` | `next` points to a missing state, or to a `version_check` state (dropped by `C58392QJx.A01`) | Declare the target as a supported type |
| `unsupportedComparisonTypes` / `comparingValuesWithDifferentTypes` | Operator applied to wrong types | Match types; use `catch`; `NOT_CATCHABLE_ERROR` cannot be caught |
| `FdsIqResource/execute: can't find FdsManager from the job_id` | `send_fds_iq` outside a live session | Run inside the session that started it |
| Bloks `Invalid XMLNS` | `wa.action.IQRequest` with an xmlns outside the allow-list | Only `w:pay`, `urn:xmpp:whatsapp:account` |
| `FcsScreenOpenerBloksDelegate: app_id is not present` | `open_bloks_screen*` without `app_id` | Pass `app_id` |
| `error.code` 3489039 | Integrity check demanded (pre-consent fetch) | Client retries after the check |
| Flows page blank, log `Uri is blocked` | Navigation left the launch host or used a non-https scheme | Keep content on the launch host |
| `extensions-bridge-api-input-parse-error` | Bridge message is not valid JSON of the expected shape | Send `{method, data, callbackID}` |
| iabjs `invalid_nonce` | Wrong or missing nonce | Use the injected `__iabjs_unified_bridge_nonce` |

---

## 11. Key distinctions

| Do not confuse | Difference |
|----------------|------------|
| Phoenix vs Bloks | Phoenix = control flow over IQ; Bloks = screens over GraphQL; they meet at `open_bloks_screen*` and `wa.action.phoenix.*` |
| FCS vs FDS | Both appear: `flowconfigurationservice` (package, `FcsStateMachine`) and `FDS` (IQ manager, `<fds>`, log `FDSManage`); expansion of "FDS" is not in the code |
| Manifest vs code | `phoenix-features.json` lists 12 resource ids and 21 operators; code has 15 resource ids and 28 operators; code wins |
| `open_bloks_screen_static` vs `open_bloks_screen` + `fetch_channel=STATIC` | Only the latter has a handler |
| Bloks tree keys vs opcodes | Tree keys are component code points; script heads are function ids (base-36) |
| Flows web vs Flows Bloks | Two renderers for `galaxy_message`: WebView (`flows.whatsapp.net`) and `com.bloks.www.whatsapp.galaxy.flow.v2` |
| Bloks GraphQL vs MEX | Bloks posts to `graph.<domain>/graphql` with `doc_id`; MEX is the XMPP-carried query layer used elsewhere |
| iabjs nonce vs Flows bridge | iabjs uses a per-handler nonce in the envelope; the Flows bridge has no nonce, it relies on the port handshake and the URL policy |
| Rich response vs Bloks | Rich response is a fixed protobuf set; Bloks is a programmable tree |

---

## 12. Complete flow

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

## 13. Unknowns

| Item | Status |
|------|--------|
| Expansion of "FDS"; meaning of the `L8E.A1T()` gate | unknown |
| Component code point to name map; Lispy names beyond the 681 listed; text-form parser | unknown |
| Handler code of most `wa.action.*` / `bk.action.*` ids (reached by numeric id) | unknown |
| Real server content: no Phoenix program or Bloks screen was captured | unknown (static only) |
| Transport of `xwa_flows_make_flow_endpoint_request`; renderer a `galaxy_message` takes; effect of AB **14222** | unknown |
| Disk cache location, size, eviction; iabjs allowed-origin set; server-side integrity beyond TLS | unknown |
| Whether a Genie-style framework exists in another build | unknown |
