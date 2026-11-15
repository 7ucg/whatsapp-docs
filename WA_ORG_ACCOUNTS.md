# WhatsApp Org Accounts — Full RE Report
**Version:** 2.26.45.10 | **Date:** 2026-11-15
**Scope:** org-account entity model (org_id, member directory, member-tag/team taxonomy), invite-link join flow, display-name availability check, email-gated onboarding (OTP), `GraphQlOrgApi`/`OrgEmailCodeClient` operation catalog (9 ops, `www` + `mex`), distinction from Managed Account and from WhatsApp Business API delegation, Baileys/velowa implementation notes

---

## 1. What an org account is

All statements are static analysis of the decompiled APK. Tier: **found** = literal string/field read at a call site, **inferred** = deduced from code shape without a traced end-to-end call, **unknown** = not resolved.

An "org" (internal naming throughout, never expanded to "organization" in any string read) is a membership entity with its own identity, a joinable member directory, and an invite-link-plus-email-OTP onboarding path, entirely separate from the account's own phone-number registration and from the two other "managed"-sounding systems already in this repo (section 7).

| Entity | Internal name | Fields (found) | Role |
|---|---|---|---|
| Org identity | `org_id` | `org_id`, `org_name`, `org_member_count`, `org_icon_url`/`org_icon_handle`/`org_icon_full_url`, `org_description` | the org itself, resolved from an invite link |
| Invite link | `link_token` | carried end-to-end from referrer/deep-link through to the final join mutation | single-use(?) join credential; exact lifetime `unknown` |
| Member identity within the org | `display_name` (+ optional `display_last_name`), `member_tag` | per-member display name subject to its own availability/policy check, independent of the account's main profile name | how a member is shown inside the org's directory |
| Team/role taxonomy | `team`, `team_options`, `selected_team` | found as state fields; semantics of individual team values not resolved | grouping of members within an org |
| Directory relationship | `relationship` (`OrgDirectory`), only observed value `"CONTACT"` | — | the only relationship-filter value seen; other ordinal→string mappings are `unknown` |

All of these field names are read verbatim as `const-string` literals immediately preceding a `GraphQlCallInput`/`LX/0jN` setter call in `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali` and `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali` (2.26.45.10), plus the `OrgJoinViewModel` state-object field list — all **found**. The step ordering that strings these ops into a flow (section 3) is **inferred** from how the state fields line up, not from a single traced call sequence.

---

## 2. Operation catalog

9 operations across two transports, all in `com.whatsapp.orgs`. 7 on `www` (`GraphQlOrgApi`, persisted-doc_id GraphQL via `Lcom/facebook/pando/TreeWithGraphQL`), 2 on `mex` (`OrgEmailCodeClient`). Variables are **found** from the call site in every row below.

| Op | Transport | doc_id (2.26.45.10) | Type | Variables | Purpose |
|---|---|---|---|---|---|
| `OrgInvitePreview` | www | `29166886682947630` | Query | `link_token` | preview org (name/icon/member count) before committing to join |
| `OrgCheckDisplayName` | www | `28738875225734024` | Query | `display_name` | availability/policy check for the member's display name inside the org |
| `OrgCheckEmailEligibility` | www | `28705126895811065` | Query | `link_token`, `email` | is this email usable for this specific org invite |
| `OrgSendEmailCode` | mex | `28659396457057459` | Mutation | `email` | send email OTP |
| `OrgVerifyEmailCode` | mex | `29096159596657036` | Mutation | `email`, `code` | verify email OTP |
| `OrgJoin` | www | `29366364109633604` | Mutation | `link_token`, `email`, `org_display_name`, `member_tag`, `org_display_last_name` | final join submission |
| `OrgDirectory` | www | `28698253656512395` (rotated from `28049955604655823` in 2.26.41.6) | Query | `org_id`, `relationship` (only `"CONTACT"` observed), `first`, `after` | paginated member directory, post-join |
| `OrgMemberSearch` | www | `39884553687825642` (rotated from `28199835469697557`) | Query | `query`, `org_id`, `first`, `after` | search within the member directory |
| `OrgLeaveMutation` | www | `28491454287217875` | Mutation | `org_id` | leave the org, any time after joining |
| `OrgList` | www | `28999557569709709` (rotated from `27920891847589435`) | Query | `unknown` (no static call site found beyond the doc_id/rotation) | list orgs the account belongs to |

All 7 `www` ops live in one class, `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali`; both `mex` ops in `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`. Namespace/schema for the `www` ops is `whatsapp-android-www`; for the `mex` ops, `whatsapp-android-mex`. `OrgDirectory`/`OrgList`/`OrgMemberSearch` existed before 2.26.45.10 (first captured against 2.26.41.6); their doc_ids rotated between the two builds (same class, same field names) — the other 7 are new in 2.26.45.10.

Supporting lookup ops exist one package over, `com/whatsapp/work/publicidentity/` — not part of the join flow itself, but the way a peer's client learns someone belongs to an org at all before any invite is involved:

| Op | Transport | doc_id | Variables | Purpose |
|---|---|---|---|---|
| `WorkPublicContactInfoQuery` | www | `29154186964216430` | `lids` (list) | per-contact work/business-account status, batched (`CoalescingBatcher`, debounced, max 100 keys/round) |
| `WorkPublicOrgInfoQuery` | www | `28899689926378846` | `ids` (list, org ids) | public org info (`id`, `name`, 2 further opaque string fields — `inferred`: logo/domain) for orgs a contact belongs to |

---

## 3. End-to-end join flow

**Inferred** ordering, assembled from `OrgJoinViewModel`'s state-object field names (no single traced call sequence covers this end to end):

### 3.1 Entry

Invite arrives as a link token, either through a referrer/deep-link (`OrgInviteReferrerOpener`, literal `org_invite_token_from_referrer` → becomes `link_token`) or directly opened (`OrgInviteLandingActivity`, with failure states `org_invite_landing_failure` / `org_invite_landing_already_in_org`).

### 3.2 Preview

`OrgInvitePreview(link_token)` returns enough to populate `org_name`, `org_member_count`, `org_icon_url`/`org_icon_handle`/`org_icon_full_url`, `org_description` before the user commits to anything.

### 3.3 Display-name check

`OrgJoinActivity`/`OrgJoinViewModel` collects `display_name` (+ optional `display_last_name`) and a team selection (`team`/`team_options`/`selected_team`). `OrgCheckDisplayName(display_name)` is the policy/availability gate; on rejection the nested continuation `OrgJoinViewModel$checkName$2` sets `name_refusal` and/or `last_name_refused` independently — first name and last name can each be refused on their own.

### 3.4 Email eligibility and OTP

`OrgCheckEmailEligibility(link_token, email)` checks whether a given email may be used for this specific invite. `OrgSendEmailCode(email)` (mex) then sends the OTP; after the user enters it, `OrgVerifyEmailCode(email, code)` (mex) verifies it. Verification can surface `username_pending_email` / `rejoin_after_username` / `username_screen_open` — join can be gated behind the main account's own username setup, a dependency on `WA_USERNAME.md`'s system that is otherwise unrelated to orgs.

### 3.5 Join

`OrgJoin(link_token, email, org_display_name, member_tag, org_display_last_name)` is the final submission. Success sets `joined=true` and populates the org fields (`org_id`, `org_name`, `org_member_count`, `org_icon_*`, `org_description`) in local state.

### 3.6 Post-join

`OrgDirectory(org_id, relationship="CONTACT", first, after)` fetches the member directory; `OrgMemberSearch(query, org_id, first, after)` searches it. `OrgLeaveMutation(org_id)` leaves, at any point after joining.

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

## 4. Key distinctions — do not confuse

Three unrelated "account structure" concepts exist in/around this client. They share no code, no proto, no doc_id space.

| | Org Accounts (this report) | Managed Account (`WA_MANAGED_ACCOUNT.md`) | Business API delegation (BSP/Cloud API) |
|---|---|---|---|
| Entity identity | `org_id`, own directory | `ManagedAccountConnection`, keyed by `connectionLid`/`connectionPnJid` | verified-name certificate fields (`host_storage`/`actual_actors`), no new entity id |
| Relationship | voluntary join via invite link, N members per org | one sponsor ↔ one dependent, a supervision link | a business number operated by Meta/a provider over Cloud API |
| Onboarding | invite link + email OTP + display-name availability check | deep link + sponsor-initiated linking (`ManagedAccountInitiateLinkingQuery` etc.) | server-side provisioning on Meta's business platform; invisible to this client beyond resulting markers |
| Code location | `com.whatsapp.orgs.*` | `com.whatsapp.managedaccount.*` / `pma.*` / `pmta.*` | no dedicated package; signalled via `w:biz` certificate fields and multi-device `HOSTED` account type |
| Transport | `whatsapp-android-www` GraphQL + `whatsapp-android-mex` (OTP) | `whatsapp-android-mex` only | `w:biz` stanza fields, not a join/invite protocol at all |
| Leave/unlink | `OrgLeaveMutation(org_id)` | `ManagedAccountRevokeLinkingMutation` | not applicable — no per-account join/leave; the number itself is provisioned/deprovisioned server-side |
| Directory concept | yes — `OrgDirectory`/`OrgMemberSearch`, relationship-scoped | no | no |

None of the three is a renaming or evolution of another: an org account has no supervision semantics (no age/graduation state, no sponsor PIN) and no business-certificate semantics (no `host_storage`/`actual_actors`, no issuer-prefix check); it is a plain, voluntary membership-with-directory model layered on top of an already-registered WhatsApp account. The product-naming conclusion ("WhatsApp's own organizations feature for companies/institutions") is **inferred** from field shape only (`org_id` + member directory + display-name-availability-check + email-domain verification) — no marketing or in-client copy was read naming the feature.

---

## 5. Error cases

No error-code table could be built from this build's call sites — no response-shape literals (success/failure field names, numeric error codes) were found for any of the 9 ops in this pass. The only refusal signals read are the two boolean state fields in `OrgJoinViewModel$checkName$2`:

| Symptom | Cause | Evidence |
|---|---|---|
| Display name rejected | `OrgCheckDisplayName` policy/availability failure | `name_refusal` set (found, state field) |
| Last name rejected independently of first name | same check, last-name-specific branch | `last_name_refused` set (found, state field) |
| Join blocked pending username setup | `OrgVerifyEmailCode` success gates on the account's own username state | `username_pending_email`/`rejoin_after_username`/`username_screen_open` (found, state fields; exact server condition `unknown`) |
| Invite opened while already a member | landing page short-circuit | `org_invite_landing_already_in_org` (found, string literal) |
| Invite link invalid/expired | generic landing failure | `org_invite_landing_failure` (found, string literal; no distinct sub-reason found) |

---

## 6. Baileys / velowa implementation notes

All 9 ops are standard persisted-doc_id GraphQL/MEX calls on the same `whatsapp-android-www`/`whatsapp-android-mex` namespaces velowa already implements for other features (username, groups) — no novel transport, no native crypto layer specific to orgs was found.

| Wire-ready | Not wire-ready |
|---|---|
| All 9 op names + doc_ids + variable keys (section 2) — enough to shape a request | Response field names are unknown for every op except the four explicitly read into `OrgJoinViewModel` state (section 1); a client must treat all responses as opaque JSON until a live capture confirms shapes |
| `link_token` propagation path (referrer → preview → join) | Exact step gating — whether the server enforces the section 3 ordering, or whether e.g. `OrgCheckDisplayName`/`OrgCheckEmailEligibility` can be skipped — is `inferred`, not confirmed |
| `OrgDirectory`/`OrgMemberSearch` pagination shape (`first`/`after`, standard cursor pattern) | `relationship` enum: only `"CONTACT"` is confirmed; other possible values are `unknown`, so a client should not assume it is the only valid filter |
| `OrgLeaveMutation(org_id)` — single-field mutation, trivial to implement | `OrgList`'s variables entirely (no call site found — likely sends `{}`, not confirmed) |
| `WorkPublicContactInfoQuery`/`WorkPublicOrgInfoQuery` for read-only "is this contact in an org" lookups, independent of the join flow | Invite-link URL/deep-link format itself (host, path, token encoding) — not captured in this pass |

A velowa implementation attempting this flow should expect to discover response shapes empirically against a live account, the same caveat already carried in this repo's other `inferred`-transport reports (e.g. `WA_USERNAME.md`).

---

## 7. Unknowns

| Topic | Reason |
|---|---|
| `OrgList`'s variables | no static call site found beyond doc_id + rotation; likely `{}` but not confirmed |
| `relationship` enum values other than `"CONTACT"` | only one ordinal→string mapping observed (ordinal 0 → `"CONTACT"`); other branches not covered by this pass |
| Response field shapes for all 9 ops | no response-side literal/field names found at any call site; everything beyond the `OrgJoinViewModel` state fields is opaque |
| `link_token` lifetime/single-use semantics | not traced; assumed single-use by naming convention only |
| Server-side enforcement of the section 3 step ordering | assembled from state-field shape, not a traced sequential call chain — a client might be able to reorder or skip steps; untested |
| `member_tag`/`team` value sets | fields exist (`team_options`, `member_tag`) but no enumerated values were found |
| Invite-link URL format | not captured this pass |

---

## 8. Evidence

Static analysis of WhatsApp Android 2.26.45.10 smali, all literals and variable keys read as `const-string` immediately preceding their `GraphQlCallInput`/`LX/0jN` setter call. No traffic was intercepted; all transport/response-shape statements are `inferred`. Source: `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali`, `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`, `com/whatsapp/orgs/ui/join/OrgJoinActivity.smali`, `OrgJoinViewModel.smali`, `OrgJoinViewModel$checkName$2.smali`, `com/whatsapp/orgs/ui/invite/OrgInviteReferrerOpener.smali`, `com/whatsapp/orgs/ui/invite/OrgInviteLandingActivity.smali`, `com/whatsapp/work/publicidentity/graphql/MexWorkIdentityTransport.smali`.
