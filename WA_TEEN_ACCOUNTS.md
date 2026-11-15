# WhatsApp Teen Account Sponsor Consent — Full RE Report
**Version:** 2.26.45.10 | **Date:** 2026-11-15
**Scope:** the `com.whatsapp.vpc.sponsor` package — a parent/guardian ("sponsor") review screen for a minor's ("teen") WhatsApp account, its navigation model, the sponsor-side age-verification gate, the three outcome screens (approved/declined/cannot-review), the `account_deletion_time_ms` consequence on decline, what is and is not reachable or wire-traced, and the distinction from `WA_MANAGED_ACCOUNT.md`'s parental-supervision system

---

## 1. What this is

New in `2.26.45.10` (absent from the `2.26.41.6` baseline): four classes under
`com.whatsapp.vpc.sponsor` implementing a one-shot review decision a parent/guardian makes about a
minor's WhatsApp account — approve it, decline it, or report being unable to review it. This is
structurally different from the existing `WA_MANAGED_ACCOUNT.md` parental-supervision product
(section 8 below spells out the distinction); it reads as WhatsApp adopting the same
teen-account-safety pattern Meta already ships for Instagram and Facebook: a guardian must sign
off on a minor having an account at all, with an account-deletion consequence on refusal.

"VPC" is not spelled out anywhere in the client; "Verified Parent/guardian Consent" is the most
plausible reading given the feature's shape — **inferred**, not a found string expansion.

| Entity | Class | Role |
|---|---|---|
| Host screen | `VpcSponsorActivity` | not exported, no intent-filter — launch mechanism unresolved (§6) |
| View model | `X/B18` | holds required launch args, runs the age-gate, drives navigation |
| Nav/outcome dispatcher | `X/CaB` | shared class (also backs the unrelated age-verification `ConsentFlowActivity` and `WamoSubActivity`); the branch handling `VpcSponsorActivity` events is what this report traces |
| Approved outcome | `VpcSponsorApprovedFragment` | shown on approval |
| Declined outcome | `VpcSponsorDeclinedFragment` | shown on decline; displays the deletion countdown |
| Cannot-review outcome | `VpcSponsorCannotReviewFragment` | shown when the sponsor could not be verified to review |

All findings are static analysis of the decompiled APK (`apktool` smali decode; no full-APK JADX
run, per this repo's safety practice for large builds). Nothing here was captured on the wire or
exercised at runtime. Evidence tiers: **found** = read directly in smali (a literal string, field,
or class); **inferred** = reasoned from code structure without a literal naming it; **unknown** =
not resolved in this pass.

The identical four classes exist, byte-for-byte unchanged in field/string layout, in
`com.whatsapp.w4b` (WhatsApp Business) `2.26.45.7` — **found** by class presence; not independently
re-traced, the consumer-build trace below is assumed to apply.

---

## 2. Navigation model

The screen is driven by a sealed destination type, `LX/CvW` (found by class presence; interface
itself carries no self-naming string), with seven implementations identified by their own
`toString()` literals (found):

| Class | `toString()` | What it does |
|---|---|---|
| `X/CSM` | `"AgeCollectionScreen"` | detours into Meta's shared cross-app age-verification flow |
| `X/CSO` | `"ConsentNoticeScreen"` | the actual approve/decline prompt — **not rendered anywhere in this package**, see §4 |
| `X/CSN` | `"ApprovedScreen"` | shows `VpcSponsorApprovedFragment` |
| `X/CSS` | `"DeclinedScreen(accountDeletionTimeMs=...)"` | shows `VpcSponsorDeclinedFragment`; carries a `long` deletion timestamp |
| `X/CSR` | `"CannotReviewScreen(teenName=...)"` | shows `VpcSponsorCannotReviewFragment`; carries the teen's display name |
| `X/CSP` | `"ErrorExit"` | shows dialog tag `vpc_sponsor_error_exit_dialog`, finishes the activity on dismiss |
| `X/CSQ` | `"Exit"` | finishes the activity immediately |

---

## 3. Required launch arguments and the sponsor age-gate

`X/B18`'s constructor (found) reads three keys off the activity's saved-state/navigation
arguments, two of them required — a missing value throws `IllegalStateException("Required value
was null.")`:

| Key | Type | Notes |
|---|---|---|
| `vpc_teen_name` | `String` | required; the teen's display name, later copied into the cannot-review screen's bundle as plain `teen_name` |
| `vpc_account_deletion_time_ms` | boxed number (`.longValue()`) | required-present, but the value read here is **discarded** — confirmed by reading the constructor bytecode, the local is never stored to a field. The number the decline screen actually shows comes from a separate `X/CSS.A00` field set later, when the review's result produces a `DeclinedScreen` destination |
| `navigation` | nullable, compared against `X/CSM.A00` | if present and not `AgeCollectionScreen`, seeds the initial destination directly (e.g. a resumed/restarted flow) |

If no initial destination is seeded, `B18` calls
`Lcom/whatsapp/dobverification/ContextualAgeCollectionRepository;->A06()Ljava/lang/Boolean;` — a
**nullable** boolean (found):

- **`null`** → navigate to `AgeCollectionScreen`. The shared `X/CaB` dispatcher launches a **Bloks
  age-verification screen** for this state — the same code path the unrelated `ConsentFlowActivity`
  uses for registration-time age checks (log line `"ConsentFlowActivity/navigate/launch Bloks age
  verification screen"`, found in the shared class, not vpc-specific, but the branch vpc-sponsor's
  `AgeCollectionScreen` state reaches).
- **`true`** → navigate to `ConsentNoticeScreen`.
- **`false`** → navigate to `CannotReviewScreen(teenName)`.

The Bloks screen reports back through
`VpcSponsorActivity.onAgeCollectionResult(ContextualAgeCollectionUsecaseApi$CACResult)` (found,
exact signature), re-running the same three-way decision from the `CACResult` subtype instead of a
plain boolean: a result carrying a boolean re-enters the `true`/`false` branches above; a
dismissed/blocked result routes to `Exit`; a no-age-available or failed result routes to
`ErrorExit`.

**Interpretation (inferred, not named in-client):** the *sponsor* — not the teen — must pass
Meta's shared cross-app age-verification check before being shown the approve/decline prompt. A
sponsor who cannot or will not complete it never reaches the actual consent decision; they are
routed to `CannotReviewScreen`, `Exit`, or `ErrorExit` depending on how the age check resolved.

---

## 4. The approve/decline prompt is not rendered by this package

Reading the `ConsentNoticeScreen` branch of `X/CaB` (found, exact bytecode): on reaching this
state, the code re-checks the navigation `StateFlow`'s *current* value against `ConsentNoticeScreen`
again — and if it still matches, immediately routes to `ErrorExit` instead of rendering anything.
No fragment, activity, or Bloks launch is wired to this state anywhere in `com.whatsapp.vpc.sponsor`
or the traced `X/CaB` branch.

**Conclusion (inferred):** the real approve/decline UI the sponsor acts on is not native code
reachable from this package. The most consistent explanation, given the age-gate is also
Bloks-driven, is a server-rendered Bloks screen launched *before* `VpcSponsorActivity` starts, with
this activity only ever receiving the **result** — approved, declined, or cannot-review — to
display the matching terminal fragment. No GraphQL/MEX operation name or Bloks screen id for the
approve/decline submission itself was found in this pass. **Unknown.**

---

## 5. Terminal outcome screens

| Screen | Reads | Shows | Network call in the fragment itself |
|---|---|---|---|
| `VpcSponsorApprovedFragment` | nothing from its own args | header image, headline/body text, a clickable `"manage"`-tagged span inside the body, a `"Done"` button | none found |
| `VpcSponsorDeclinedFragment` | `account_deletion_time_ms` (long, Fragment-arg bundle, set from `CSS.A00`) | header image, headline, body text with the deletion time **formatted as a relative/duration string** (via `LX/0Fg;->A05(LX/0Fc;J)Ljava/lang/String;`, not a bare timestamp), a `"Done"` button | none found |
| `VpcSponsorCannotReviewFragment` | `teen_name` (String, Fragment-arg bundle, set from `CSR.A00`) | header image, headline interpolating the teen's name, body text, an `"OK"` button that dismisses | none found |

**What `account_deletion_time_ms` means in practice:** the decline screen formats this value
through a relative-duration formatter and shows it as "time remaining," i.e. this is presented to
the viewer as a **countdown**, not a notice that deletion already happened — found, from the
formatter call. Whether declining actually *schedules* the deletion server-side, versus the
deletion already being in motion by the time this screen renders, is **unknown**: no fragment in
this package makes a network call of its own; the value simply arrives as a launch/navigation
argument that the screen displays.

All body copy for these three screens (`str5e24`-`str5e2c` in this build's `res/values/strings.xml`)
is literal placeholder Lorem-ipsum text — this is a beta build; layout and data-binding are found,
final shipped copy is **unknown**.

---

## 6. Entry point — unresolved

`VpcSponsorActivity` is declared `android:exported="false"` with no `<intent-filter>` in the
manifest (found). A repository-wide search for the literal navigation-argument keys
(`vpc_teen_name`, `vpc_account_deletion_time_ms`) and for any construction of
`VpcSponsorActivity` outside its own four classes and the shared `X/CaB`/nav-plumbing helper
classes returns **no hits anywhere in the decoded smali tree** — a negative, found result.

**Inferred:** nothing in this client statically builds the launch `Intent`. The most plausible
explanation, consistent with how push-driven navigation elsewhere in this app is known to work, is
a server-driven notification action that resolves the target activity and its extras from push
payload data at runtime rather than a hard-coded call site — but no such dispatcher was identified
in this pass. **Unknown** how a sponsor is actually notified and routed to this screen.

---

## 7. Network surface

No GraphQL/MEX operation name, Bloks screen id, or binary-stanza `xmlns` was found anywhere in this
package for any step of the flow: not for notifying a sponsor a review is pending, not for the
age-gate (inferred Bloks, no screen id captured), not for the approve/decline submission itself
(§4), not for whatever actually triggers the account-deletion countdown on decline. Everything
network-shaped in this flow is inferred to ride Bloks rather than a named, persisted GraphQL/MEX
query — consistent with how the rest of Meta's cross-app age-verification tooling in this client
works — but no operation or screen identifier was captured for any of it.

---

## 8. Key distinctions

### 8.1 vs. `WA_MANAGED_ACCOUNT.md` ("Managed account")

| `vpc.sponsor` (this report) | `managedaccount.*` / PAA / PMA / PMTA (`WA_MANAGED_ACCOUNT.md` §2-8) |
|---|---|
| A **one-shot review decision**: approve, decline, or report inability to review a specific minor's account | An **ongoing supervision relationship** between two independently-registered accounts |
| No `w:mex` operation found; inferred Bloks, no op/screen id captured | Nine named `w:mex` `ManagedAccount*` operations with doc_ids, schema `whatsapp-android-mex` |
| No local relationship record found in this package | Local `ManagedAccountConnection` row (`connectionLid`, `role`, `linkTs`, `connectionPnJid`, ...) |
| Declining produces an `account_deletion_time_ms` consequence for the **teen's account itself** | Unlinking (`ManagedAccountRevokeLinkingMutation`) ends supervision; neither account is deleted |
| No roles enum; the sponsor is simply "the reviewer" | `EnumC08540Ng`: `NONE`/`DEPENDENT`/`SPONSOR`/`SPONSOR_ADMIN` |
| Entry point unresolved; activity not exported, no deep link | Entry point is an in-app deep link (`ManagedAccountSponsorOnboardingViewModel`) |
| Shares no class, package, or string with `managedaccount.*`/`pma.*`/`pmta.*` | — |

No code in either package references the other by class or string. Whether a `vpc.sponsor`
approval subsequently creates or interacts with a `managedaccount.*` relationship was not traced;
**unknown**.

### 8.2 vs. normal account creation

Normal WhatsApp registration (`WA_ACCOUNT_LESS_SURFACE.md` / the standard SMS/email OTP flow) has
no guardian-review step at all; an account becomes active once its own owner completes
registration. `vpc.sponsor` inserts an external approval gate — held by a different person, on a
different device — between some trigger (unresolved, §6) and the account's continued existence,
with decline carrying a deletion consequence. What specifically causes an account to be routed
into this guardian-review state in the first place (age at registration, an on-device age signal,
a later re-classification) was not found in this package and is **unknown**.

---

## 9. Baileys / velowa reachability note

Nothing in this flow is reachable for a third-party wire-only client. The approve/decline decision
itself is inferred to be a server-rendered Bloks screen the sponsor's own first-party client
renders (§4) — not a message, IQ, or named GraphQL/MEX mutation velowa could send or observe. The
sponsor-side age-verification gate (§3) is likewise Bloks-driven. No doc_id, MEX operation name, or
binary-node `xmlns` exists for any part of this flow in this build's catalogs. There is nothing
here to implement; this section exists to record that explicitly rather than leave it implied.

---

## 10. Unknowns

| Topic | Reason |
|---|---|
| Expansion of "VPC" | never spelled out in-client; inferred as Verified Parent/guardian Consent |
| What launches `VpcSponsorActivity` and sets its navigation args | no static call site found anywhere in the decoded tree; not exported, no intent-filter |
| The approve/decline submission itself (network operation, screen id) | not implemented in this package; inferred Bloks, no identifier captured |
| Whether declining schedules server-side deletion, or the countdown is purely informational | no network call in `VpcSponsorDeclinedFragment`; deletion assumed already server-initiated by the time this screen renders |
| What routes a teen's account into guardian review in the first place | not traced; no trigger condition found in this package |
| Relationship, if any, to `managedaccount.*` | no cross-reference found in either direction |
| Final shipped copy of all `vpc.sponsor` strings | this beta build ships Lorem-ipsum placeholder text |
| Exact semantics of `ContextualAgeCollectionRepository.A06()`'s null/true/false states beyond "unknown/sufficient/insufficient" | inferred from control flow only; no field or enum names found |
| Actual traffic | static analysis only; nothing captured or exercised at runtime |

---

## 11. Flow (as far as the evidence reaches)

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
