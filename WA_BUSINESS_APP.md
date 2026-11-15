# WhatsApp Business App — Full RE Report
**Version:** 2.26.45.7 (Business) vs 2.26.45.10 (consumer) | **Date:** 2026-11-15
**Scope:** structural diff of the WhatsApp Business APK (`com.whatsapp.w4b`) against consumer WhatsApp (`com.whatsapp`) — Business-exclusive package roots, the React Native stack, native-library diff, GraphQL/MEX/`www`/`facebook-schema` doc_id catalog asymmetry, permission diff; distinction from the WhatsApp Business API/Cloud API and from Managed Account

---

## 1. Overview

WhatsApp Business is a separate app (`com.whatsapp.w4b`), not a mode switch inside consumer WhatsApp. It shares the Signal-protocol core, the Noise transport, and most of the chat UI with consumer WhatsApp, but ships its own package set for business-only features and bundles a dependency — a full React Native runtime — that consumer does not carry at all.

This report covers only the **app itself**, diffed as an APK against consumer WhatsApp. It is a different axis from two other "business"-adjacent concepts already documented in this repo:

| Concept | What it is | Report |
|---|---|---|
| **WhatsApp Business app** (this report) | A distinct client APK (`com.whatsapp.w4b`) a business installs on a phone, with its own UI for catalog, labels, away messages, ads | here |
| **WhatsApp Business API / Cloud API** | Server-side infrastructure that hosts/relays a business number's messages, used instead of or alongside the Business app; signalled in any client only via verified-name certificate fields (`host_storage`, `actual_actors`, issuer prefix `smb:`/`ent:`) and `business_state_id` coexistence banners | `WA_MANAGED_ACCOUNT.md` §9 |
| **Managed Account** | A minor's own consumer account, supervised by a parent/guardian (`ManagedAccount*`/PAA/PMA/PMTA); unrelated to either business concept, no "managed" label exists for the business case | `WA_MANAGED_ACCOUNT.md` §1-8 |

A single business can combine all three: run the Business app on a device, delegate parts of its traffic to a Cloud API provider (coexistence), while the chat partner's account is an ordinary consumer account. See §9 for how these interact.

Evidence source: a static package/asset/manifest diff between `WA-Business_2.26.45.7.apk` and `WhatsApp_2.26.45.10.apk` (current beta pair at diff time, not a version-over-version comparison). No full-APK jadx decompile was run on either side (hard safety rule); all findings below are apktool smali-tree, asset-JSON, and reconstruct-manifest level. Tiers follow `found`/`inferred`/`unknown` per the brain's evidence contract.

---

## 2. Package-level diff — found

Comparing every directory under `smali*/` in each apktool tree: Business has 4,281 unique package-path directories (15 `smali_classesN` trees), consumer has 3,710 (14 trees). 853 paths exist only in Business, 282 only in consumer. 45 top-level `com/whatsapp/*` package roots are Business-exclusive (root directory itself absent from consumer, not just a sub-path).

### 2.1 Business-exclusive package roots, by feature cluster

| Cluster | Package roots | Notes |
|---|---|---|
| Away / greeting / quick-reply messaging | `businessaway`, `businessgreeting`, `businessquickreply`, `businessmissedcallfollowup` | core SMB auto-reply features |
| Labels / agents / chat assignment | `chatassignment`, `authagent`, `authagentfeaturecontrol`, `smbmultideviceagents`, `businesscontactmanager`, plus `lists/smb/labels` (sub-path; `lists` root is shared) | agent seats and label editing |
| Profile setup / verification | `businessregistration`, `protectedbusinessaccounts`, `metaverified` | |
| Catalog/orders (management side) | `ordermanagement` | catalog browsing/editing itself (`catalog`, `businessproduct`, `businesscollection`) is **shared** — see §2.2 |
| Ads / Meta Ads integration | `ads4ads`, `adscreation`, `adcreationinterfaces` | see §3 for the React Native link |
| Billing / subscriptions (API tiers) | `metabilling`, `metabillingui`, `subscription`, `billingui` | |
| App-to-API coexistence | `coexistence`, `connectedaccounts`, `linkedaccounts`, `dynamicaudience` | bridges to the Cloud API side, §9 |
| Meta AI business agent | `bizai`, `genai`, `maiba` | |
| Business tooling / compliance | `businesstools`, `businessinsights`, `rapidfeedbacksurvey`, `reportblocksharing`, `statistics`, `integrityenforcementsinfra`, `eligibilitychecker`, `googleeligibilityapi`, `smb`, `smbauth`, `waloginmbs`, `marketingmessage`, `marketingmessagemanagement`, `mediatemplates`, `bizdatasharing`, `bizgallerypicker`, `bizmedia` | |

### 2.2 Shared roots with Business-exclusive subpackages

Some roots exist in both apps because consumer can view/consume business-side data, but the editing/management subpackages are Business-only:

- `com/whatsapp/businessprofile/` — shared root; `businessprofileaddress`, `businessprofilecategory`, `businessprofileedit` (+ `boostmedia`, `businessprofilecompleteness`), `businessvertical`, `businesscompliance/smb/...` are Business-only. Consumer keeps only the read-side profile-view subpackages.
- `com/whatsapp/lists/` — shared root (label data model/UI, `labelitem` in both); the label-**editing** subpackage `lists/smb/labels` is Business-only.
- `catalog`, `businessproduct` (+ `businessproductlist`), `businesscollection` — shared roots, confirmed present in consumer's smali tree as the catalog/product **browsing** UI shown when viewing a business chat.

Net shape: catalog/product viewing, business-profile viewing, and label display are shared; catalog/profile editing, away/greeting/quick-reply messaging, label editing, agent/multi-device auth, ads creation, and Cloud-API coexistence are Business-exclusive.

### 2.3 Consumer-exclusive packages — found, not clustered

282 paths exist only in consumer. A spot-check did not surface a thematic cluster comparable in size to the Business-exclusive set; the bulk are nested children of a smaller number of consumer-only roots. Not deep-dived — listed as an open gap in §8.

---

## 3. The React Native stack — found, business-exclusive

Unexpected finding: Business bundles a full React Native stack absent from consumer at the package level, not just an extra feature module.

| Package | Business | Consumer |
|---|---|---|
| `com/facebook/react/*` (bridge, fabric, animated, devsupport, turbomodule, …) | 88 dirs | 0 |
| `com/facebook/catalyst/*`, `com/facebook/fbreact/*` (RN bridge modules, i18n, safe-area) | present | absent |
| `com/facebook/hermes/*` | 3 dirs | 1 dir — a stray reference only, no `com/facebook/react` to pair with it, i.e. not a working RN runtime |
| `com/caverock/androidsvg`, `com/crossapp/graphql/facebook/*` | present | absent |

Corroborated at the native-library level (§4): `libreactnative.so` (RN runtime), `libappmodules.so` (the RN JS bundle's native loader), and `libimagepipeline.so` (Fresco, RN's image pipeline) are Business-exclusive `.so` files.

**Inferred**, not confirmed: some Business-only surface — most plausibly ads creation (`adscreation/lwi/react/*` has a `react` subpackage directly inside `lwi`), Meta-billing, or coexistence onboarding — is implemented as embedded React Native screens rather than native Android UI. Which specific feature(s) use the RN stack is not confirmed from package names alone; it would need a scoped decompile of `adscreation/lwi/react/activity` classes. This is the clearest remaining "surprising dependency": a business messaging app embeds a cross-platform JS UI runtime, apparently just for one or a few screens (ads creation is the strongest naming match).

---

## 4. Native library diff — found

Compared `superpack_index.csv` (the SUPERPACK_OB container's own library manifest) between the two apps' reconstruct outputs:

| | Count |
|---|---|
| Consumer libraries indexed | 84 |
| Business libraries indexed | 89 |

**Business-exclusive (5):** `libappmodules.so`, `libimagepipeline.so`, `libreactnative.so`, `libwacomponents.so` (name suggests a WhatsApp-authored RN bridge-component library, not stock RN), `libzstddecoder.so` (likely RN bundle/asset decompression).

**Consumer-exclusive:** none — every consumer library name also appears in the Business index.

The 6 device-oracle-decompiled libraries shared by both apps (`libwhatsapp.so`, `libwhatsappmerged.so`, `libwasafe.so`, `libvoprf-ed25519.so`, `libohai.so`, `libcurve25519.so`) are identical between the two apps (same sizes, same symbol/export counts) — the Signal-protocol/attestation/client-integrity core is untouched by the Business build. The React Native + Fresco stack is Business-exclusive at both the Java/Kotlin package level and the native-library level — a consistent, two-layer finding.

---

## 5. GraphQL / MEX / `www` / `facebook-schema` doc_id catalog diff — found

Each app ships its own `assets/whatsapp-android-<schema>_client_persist_ids.json` doc_id catalog, read directly from the apktool-decoded asset tree (no decompile needed).

| Schema | Business ops | Consumer ops | Business-only | Consumer-only |
|---|---|---|---|---|
| `mex` | 242 | 242 | 0 | 0 — identical set |
| `wamo` | 22 | 22 | 0 | 0 — identical set |
| `www` | 237 | 244 | 4 | 11 |
| `facebook-schema` | 224 | 17 | 215 | 7 |

### 5.1 `mex` and `wamo` — identical between apps

Both catalogs have the exact same operation names in both APKs (the set difference is empty, not merely equal in count). Business carries no Business-specific MEX/GraphQL surface at this schema level — it shares the consumer catalog wholesale.

### 5.2 `www` — small asymmetry

- Business-only (4): `BPAccessTokenAndSessionCookiesMutation`, `CatkitTypeaheadProxy`, `WACreateEnforcementAppeal`, `WAGetEnforcementAppealStatus`.
- Consumer-only (11): `WaAutofillAcknowledgeWalletTerms`, `WaAutofillFetchContactData`, `WaAutofillFetchSettings`, `WaAutofillSaveContactData`, `WaAutofillUpdateNegativeInteraction`, `WaAutofillUpdateSaveCvv`, `WaCreateLabyrinthBackupMutation`, `WaDeleteLabyrinthAccountMutation`, `WaDeleteLabyrinthThreadsMutation`, `WaRotateLabyrinthEpochMutation`, `WaUploadLabyrinthMessagesMutation`.

Consumer carries its own personal-payments/autofill (`WaAutofill*`) and E2E chat-backup (`WaCreateLabyrinthBackupMutation` etc. — WhatsApp's chat-backup system, "Labyrinth" internally) ops that Business lacks; Business carries a couple of account-enforcement-appeal and session/typeahead ops consumer doesn't need.

### 5.3 `facebook-schema` — the headline finding: 215 Business-only ops

This is where the real Business-specific GraphQL surface lives — not `mex`/`wamo`, which are byte-identical between the two apps. Business carries 224 ops in this schema against consumer's 17; consumer's 17 are unrelated personal-payment/commerce-nonce ops (`AcDcCreateCanonicalDigitalCommerceNonce`, `WaAutofillAddPayCreditCard`, `WaGetServerEncryptionKey`, etc.) that Business doesn't carry.

The 215 Business-only ops, clustered by name (descriptive grouping, static-analysis-derived, not a confirmed functional taxonomy):

| Cluster | Example ops |
|---|---|
| Knowledge base / AI-reply / simulation ("coach") | `FetchAIAbilities`, `KnowledgeRepoFetchV2`, `UpdateAIKnowledge`, `DeleteAIKnowledge`, `CoachSimulationMessage`, `CoachSuggestedReply`, `StartSimulation`, `SubmitSimulationFeedback`, `FetchSuggestedReply`, `MarkSuggestedReplyUsed` |
| Meta AI biz agent / MAIBA | `MAIBAOnboarding`, `MAIBACompleteParallelOnboarding`, `Maiba1pCalendarEvents`, `MaibaGetCurrentCatalog`, `MaibaDownloadLeadGenFlow`, `MetaAIBizAgentWAAIHome`, `MetaAIBizAgentWACoachingMutation` |
| Lead-gen / appointments | `CreateLeadGenFlow`, `GetLeadGenFlowLeads`, `UpdateLeadStages`, `CreateAppointmentFlow`, `GetAppointmentPrefill`, `GetDefaultAvailability` |
| Auth agent / SMB multi-agent / login | `AuthAgentCompanyInfoQuery`, `AuthAgentFeaturePolicyQuery`, `AddSmbAgentAndCoexQr`, `SmbRegistrationInit`, `WALoginClaimAuthChallenge`, `WALoginConfirmAuthChallenge` |
| App-to-Cloud-API coexistence | `CoexUnifiedOnboarding`, `CoexMultiAppEligiblity`, `CoexAppsAndServicesOffboardProduct`, `CoexCompanionPairingStatusCallback`, `CoexistenceQRCodeFetch` |
| Click-to-WhatsApp ads (CTWA) | `CTWACreateLookAlikeAudienceMutation`, `CTWAPreviousAdsRecommendationQuery`, `CtwaLinkedMediaQuery`, `CtwaNativeUploadAdMediaMutation` |
| Ad account / eligibility | `AdAccountEligibilityCheckerQuery`, `OnboardToWhatsAppAdAccount`, `WhatsAppBizFetchAdDefaults`, `WhatsAppBizGetEstimatedAdReach` |
| Catalog management (write side) | `WhatsAppCatalogAddProduct`, `WhatsAppCatalogEditProduct`, `WhatsAppCatalogDeleteProduct`, `WhatsAppCatalogCreateCollections`, `WhatsAppCatalogProductVisibilityUpdate` |
| Marketing-message broadcast ("Pro") | `BusinessBroadcastProCampaignContent`, `BusinessBroadcastProCustomAudiencesQuery`, `BusinessBroadcastProInsights`, `WAMarketingMessagesCustomAudienceCreateMutation` |
| Contact manager / customer profiles | `BizContactManagerProfiles`, `ContactManagerAccessState`, `WACustomerProfiles`, `UpsertWACustomerProfiles`, `DeleteWACustomerProfile` |
| Billing / subscription (Meta-billed tiers) | `FetchSubscriptionState`, `FetchSubscriptionStateV2`, `WaSmbMetaOneTierPaymentPrefetchTargetQuery`, `AcceptBizAiPaymentTerms` |
| Chat-history export / 3P (GDrive) integration | `FetchChatHistoryExportStatus`, `GDriveGetFiles`, `UploadHistoricalMetadata`, `Disconnect3PPartners` |
| Linked IG/FB account | `SetIGDisplayContactInfoMutation`, `WAFBPageProfileImportGet`, `WhatsAppBusinessLinkedAccountsQuery` |
| QE/feature-flag plumbing (business-side) | `CheckQEBool`, `WaFetchQEBool`, `WaFetchQEString`, `WhatsAppGraphQLCheckQE` |

The full 215-name list is reproducible from the two apps' asset files cited above; not reproduced verbatim here. `www`/`facebook-schema` doc_id **values** (not just op names) were not diffed — a shared op name could in principle still carry a different doc_id between the two apps; not checked.

---

## 6. Permission diff — found

From each app's manifest inventory:

| | Business-exclusive | Consumer-exclusive |
|---|---|---|
| Permission | `com.whatsapp.permission.MIGRATION_CONTENT_PROVIDER` | `android.permission.RECEIVE_SMS` |

Both apps additionally request own-package self-broadcast/maps permissions under their respective package names (`com.whatsapp.w4b.*` vs `com.whatsapp.*`) — these are package-name-mangled equivalents of each other, not functionally new, and are not counted above.

Business does not request SMS-receive. **Inferred**, not confirmed from code: consistent with Business accounts more often registering via a Cloud/Business API path rather than relying on on-device SMS auto-read for OTP — but this reasoning is not verified against any registration-flow code in this pass.

---

## 7. Baileys / velowa note

Almost none of this report's surface is reachable from a vanilla WhatsApp Web client (velowa or any Noise/multi-device-protocol implementation):

- The `mex`/`wamo` catalogs are **identical** to consumer's — nothing Business-specific to add there; any WA Web client already has the same doc_ids.
- The 215 `facebook-schema` ops (§5.3) are the real Business-specific GraphQL surface, but these are Business-**app**-UI-driven flows (catalog editing, ads creation, coaching/MAIBA, coexistence onboarding, agent auth) gated behind the Business app's own account state and, in several clusters, behind the WhatsApp Business API/Cloud API server side entirely (coexistence, billing, ad accounts). A WA Web client speaking the ordinary multi-device protocol has no path to most of these — they are not wire-protocol features at all, they are REST/GraphQL calls the Business app's own UI makes against Meta's business-platform backend.
- The ads-creation React Native surface (§3) is Android-app-UI only (embedded JS screens rendered by `libreactnative.so`); nothing about it rides the chat wire protocol.
- The one area with any multi-device-protocol relevance is coexistence (`coexistence`/`connectedaccounts`/`linkedaccounts`), whose device/session representation is covered by the existing documentation in `WA_MANAGED_ACCOUNT.md` §9.3 and `WA_LINKED_DEVICE_PAIRING.md` (account type `HOSTED`, device id 99, `platformType` 23/25-27) — that part is already as far as a client-side-only view can go.

Net: this report is useful for understanding what the Business APK *contains*, not as a source of new wire-protocol surface for velowa.

---

## 8. What this report has NOT verified

| Gap | Why | Follow-up needed |
|---|---|---|
| Proto/wire-schema diff between the two apps | `unknown`, not inferred-same. The reconstruct pipeline's proto stage did not run for either build (`protoc_ok=False` on both sides); the deeper proto extraction used elsewhere this version-refresh pass (1089 messages, `protoc` exit 0) ran only against consumer's pre-existing jadx decompile — no equivalent decompile exists for `com.whatsapp.w4b` in this workspace. Producing one needs a full-APK jadx run, forbidden by this session's hard safety rule (previously crashed the analysis machine). Absent evidence is not evidence of absence. | A single-class or single-DEX jadx extraction scoped to the message/proto classes only (not a full-APK decompile) |
| Which feature(s) render through the Business-exclusive React Native stack | Package/library-name correlation only (`adscreation/lwi/react/*` is the strongest naming match, but not confirmed) | Scoped decompile of `com/whatsapp/adscreation/lwi/react/*` classes |
| Consumer-exclusive package cluster (282 paths) | Not thematically clustered this pass — lower priority given the task's framing on Business-exclusive surface | A dedicated pass over the 282-path diff |
| `www`/`facebook-schema` doc_id **values** | Only op **names** were diffed; a shared name could carry a different doc_id per app | Value-level diff of both asset JSONs |
| Full 215-op `facebook-schema` list / variables / response shapes | Clustering is by name keyword only; no call-site or response-field recovery attempted | Targeted call-site tracing per cluster, as done for other reports' MEX ops |

---

## 9. Key distinctions

| A | B |
|---|---|
| WhatsApp Business **app** (`com.whatsapp.w4b`) — a distinct APK with its own package set, this report | WhatsApp Business **API / Cloud API** — server-side hosting/relay of a business number's messages; no dedicated client APK, signalled in any client via verified-name certificate fields (`WA_MANAGED_ACCOUNT.md` §9) |
| Business app's `coexistence`/`connectedaccounts`/`linkedaccounts` packages — the app's own UI for bridging to a Cloud API provider | `business_state_id` coexistence banners seen by a **peer's** client (consumer or Business) when a business number runs both the app and the API at once (`WA_MANAGED_ACCOUNT.md` §9.2) |
| Managed Account (`ManagedAccount*`, PAA/PMA/PMTA) — a minor's own **consumer** account under parental supervision | Business app — a business's account, entirely unrelated concept, no code/schema overlap |
| `mex`/`wamo` doc_id catalogs — byte-identical op-name sets in both apps | `facebook-schema` doc_id catalog — 215 ops exist only in Business; this is where Business-specific GraphQL surface actually lives |
| Catalog/profile/label **viewing** — shared package roots, present in consumer too (so a consumer user can browse a business's catalog) | Catalog/profile/label **editing** — Business-exclusive package roots (the write side only the business itself can reach) |

---

## 10. Summary

Confirms the expected shape going in — catalog, business-profile/verification, labels, quick-replies/greeting/away messaging, agent/multi-device auth cluster in Business-only code, with the viewing/display half of each shared with consumer — and adds two findings not anticipated:

1. **`facebook-schema` is where the real Business-specific GraphQL surface lives** (215 Business-only ops: AI-coach/knowledge-base, MAIBA, lead-gen, auth-agent, coexistence, CTWA ads, catalog write ops, marketing broadcast, billing), not the main `mex`/`wamo` catalogs, which are byte-identical op-name sets between the two apps.
2. **Business bundles a full React Native + Fresco stack** (`com.facebook.react.*`, `libreactnative.so`, `libimagepipeline.so`, `libwacomponents.so`) entirely absent from consumer, at both the package and native-library level — most plausibly backing ads-creation screens, but the exact feature boundary is not confirmed without a scoped decompile.

The proto/wire-schema diff could not be done this pass (§8) and is recorded as unknown, not inferred-same.
