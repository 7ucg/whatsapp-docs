# WhatsApp Polls — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-11-01
**Scope:** poll message family (`pollCreationMessage` through `pollCreationMessageV6`, `pollCreationOptionImageMessage`, `pollAddOptionMessage`, `pollUpdateMessage`, `pollResultSnapshotMessage`/`V3`), version history and send/receive selection logic, creation validation and limits, image-poll option linking, vote selection and privacy model, multi-select vs single-select, poll editing, forward-time result snapshotting, feature flags

---

## 1. What it is

A poll is a `Message` sub-object (`PollCreationMessage`, reused unchanged across six versioned top-level fields) carrying a question, a list of options, a selection cap, and optional quiz/end-time/visibility settings. Votes (`pollUpdateMessage`), added options (`pollAddOptionMessage`) and edits (`secretEncryptedMessage`) are separate follow-up messages bound to the creation message's id and keyed off its per-message secret; that encryption (HKDF use cases, AES-GCM, AAD, identity retry) is covered in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) and is not repeated here. This report covers the message-type layer: which field carries what, how the client chooses between them, validation and limits, and what the poll-specific handlers do with the decrypted payloads. All findings are static analysis of the decompiled 2.26.41.6 APK (Java sources under `java_src/`, plus `res/values/strings.xml`); nothing was captured on the wire. Tiers: **found** = read in code/resources, **inferred** = deduced from code, **unknown** = not resolved.

| Entity | Field in `Message` | Proto type | Role |
|--------|--------------------|-----------|------|
| `pollCreationMessage` | **49** | `PollCreationMessage` (`DTM`) | original creation slot |
| `pollCreationMessageV2` | **60** | `PollCreationMessage` | creation in a community default-subgroup chat |
| `pollCreationMessageV3` | **64** | `PollCreationMessage` | plain-poll creation slot (current default for ordinary polls) |
| `pollCreationMessageV4` | **93** | `FutureProofMessage` (`BD2`) | forward-compat wrapper around an inner `Message.pollCreationMessage` (field 49) |
| `pollCreationMessageV5` | **111** | `PollCreationMessage` | quiz creation slot |
| `pollCreationMessageV6` | **119** | `PollCreationMessage` | extended-poll slot (end time / hide-voter-names / allow-add-option) |
| `pollCreationOptionImageMessage` | **90** | `FutureProofMessage` | one image-poll option image, linked to the future poll via `messageAssociation` |
| `pollAddOptionMessage` | **121** | `PollAddOptionMessage` (`C30556DRc`) | adds one option to an existing poll |
| `pollUpdateMessage` | **50** | `PollUpdateMessage` (`DSG`) | vote (encrypted) or vote metadata |
| `pollResultSnapshotMessage` | **88** | `PollResultSnapshotMessage` (`DSF`) | static result snapshot, poll forwarded to another chat |
| `pollResultSnapshotMessageV3` | **115** | `PollResultSnapshotMessage` | same, quiz variant (vote counts zeroed) |

Field numbers verified directly against `C30628DTw` (the `Message` proto class), which declares all eleven `POLL_*_FIELD_NUMBER` constants matching the table above.

---

## 2. `PollCreationMessage` (`DTM`)

### 2.1 Fields (found)

| Field | Number | Type | Use |
|-------|--------|------|-----|
| `encKey` | **1** | bytes | present on the wire but unused by the handlers read in this pass (votes use the per-message `messageSecret`, not this field; see [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3) |
| `name` | **2** | string | poll question, max 5000 chars, required |
| `options` | **3** | repeated `Option` | answer options |
| `selectableOptionsCount` | **4** | uint32 | selection cap, required (§11) |
| `contextInfo` | **5** | `ContextInfo` | standard context |
| `pollContentType` | **6** | enum `PollContentType` (`E25`) | `UNKNOWN`=0 (`A03`), `TEXT`=1 (`A02`), `IMAGE`=2 (`A01`) |
| `pollType` | **7** | enum `PollType` (`EnumC32108E1g`) | `POLL`=0 (`A01`), `QUIZ`=1 (`A02`) |
| `correctAnswer` | **8** | `Option` | quiz correct-answer option, required when `pollType=QUIZ` |
| `endTime` | **9** | int64 | poll close timestamp (ms) |
| `hideParticipantName` | **10** | bool | "Hide voter names" (§10) |
| `allowAddOption` | **11** | bool | "Allow others to add options" (§6) |

`PollCreationMessage.Option` (`C30529DQb`): `optionName` **1** (string), `optionHash` **2** (string, only populated for image-poll options, §5).

### 2.2 Local representation

The client stores a parsed poll as `C13J` (quiz image variant `C13K`), with options as `C33283EeZ` objects carrying the raw name (`A04`), a locally computed SHA-256 digest of the name (`A02`, §9.1) and, for image options, the wire `optionHash` (`A08`).

---

## 3. Version history

### 3.1 Which field is used to send (found, `F2N.A00`/`A02`)

```text
pollType == QUIZ (correct answer set)              -> pollCreationMessageV5
chat is a community default-subgroup (group_type 3) -> pollCreationMessageV2
else:
  hideParticipantName / endTime / allowAddOption set -> pollCreationMessageV6
  none of those set                                   -> pollCreationMessageV3
```

`pollCreationMessageV4` is never populated by the send path read in this pass; it only appears on receive (§3.3). The community check reuses the same `group_type == 3` predicate as the plaintext-reaction fallback in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.2 (`C0GQ.A0A(chat) == 3`, set from `isDefaultSubgroup_`); why a default-subgroup poll gets its own versioned slot instead of V3/V6 is not explained in the code read here (inferred: historical rollout ordering, since V2's field number is the lowest of the extended set).

So in practice: **V3** is the current slot for an ordinary multi/single-choice poll with no extras, **V6** is current for a poll using end time, hidden voter names or add-option, **V5** is current for quizzes, and **V2** is a community-subgroup-specific variant of the same base shape. **V1** (the unversioned field 49) and **V4** are not chosen by the sender in this build.

### 3.2 `pollCreationMessageV4` = forward-compat wrapper (found, `F2N.CM7`)

V4's proto type is `FutureProofMessage` (`BD2`, single field `message` = an inner `Message`). On receive, when the V4 slot is populated the client unwraps `BD2.message_` and reads *that* inner message's own `pollCreationMessage` field (49) as the actual `PollCreationMessage`. This is a genuine fallback envelope, not a dead field: a sender that needs to emit a newer/undefined poll variant can wrap a basic (field-49-shaped) poll inside V4 so that older clients — which only understand the generic `FutureProofMessage` unwrap, not the newer slot — still render a plain poll. No code path in this pass populates V4 on send, so this exists for forward/backward compatibility between client versions, not for anything the 2.26.41.6 client itself emits (inferred).

### 3.3 Receive-side selection and downgrade (found, approximate; decompiler lost some branch structure)

`F2N.CM7` checks the `Message` bitfields in order V1 → V2 → V4 → V5 → V6 → V3-fallback and parses whichever versioned field is populated into the same validator (`F2N.A01`, §4). Three flags gate acceptance of V6's extra fields on receive; when a flag is off the poll is **downgraded** (parsed as the generic future-proof placeholder instead of a poll bubble) rather than rejected outright:

| Extra field | Gate | Effect when gate is off |
|-------------|------|--------------------------|
| `endTime` | AB int **24884** (`receivingEnabled`) | logged `poll downgraded to FMessageFuture (receiving disabled)`, not rendered as a poll |
| `hideParticipantName` | AB int **24885** | downgrade (exact polarity of the check not fully resolved from the decompiled control flow) |
| `allowAddOption` | AB int **25758** | downgrade |

The exact nesting of these three conditions could not be fully reconstructed (JADX reports duplicated/unreachable blocks in `F2N.CM7`); the gating flags and the downgrade outcome are found, the precise boolean combination is inferred.

### 3.4 Image-content gate

`pollContentType = IMAGE` is only honoured on the V3/V5 parse path when the bit for `pollContentType` is set; if it is set but the value is not `IMAGE`, the message is rejected (`return null`, falls through to the generic parser) rather than silently treated as text.

---

## 4. Creation validation (found, `F2N.A01`)

Single validator shared by all versioned creation fields. Throws, error code **11** unless noted:

| Check | Rule | Error string |
|-------|------|--------------|
| Name present | `name` bit must be set | `poll_creation_missing_name` |
| Name length | 1–5000 chars (unless a lenient parse context bypasses this, §4.1) | `poll_creation_invalid_name` |
| Quiz correct answer | if `pollType=QUIZ`, `correctAnswer` bit must be set | `poll_creation_missing_correct_answer` |
| Options present | at least one option, unless the zero-options bypass (§4.1) applies | `poll_creation_missing_options` |
| Option count (lower) | ≥ 2 options (0 under the bypass) | `poll_creation_invalid_options_count` |
| Option count (upper) | ≤ `min(AB int 1408, 12)` — 12 is a hard client ceiling regardless of server value | `poll_creation_invalid_options_count` |
| Option name length | 1–2500 chars per option | `poll_creation_invalid_option` |
| Correct-answer name | if quiz, `correctAnswer.optionName` must be non-empty | `poll_creation_missing_correct_answer_name` |
| Duplicate options | option names must be unique | `poll_creation_duplicate_options` |
| Duplicate trimmed options | under AB flag **25758**, whitespace-trimmed names must also be unique | `poll_creation_duplicate_trimmed_options` |
| Correct answer matches an option | quiz correct-answer name must equal one option's name | `poll_creation_unmatched_correct_answer` |
| Selectable count present | `selectableOptionsCount` bit must be set | `poll_creation_missing_selectable_options_count` |
| Selectable count range | `0 <= selectableOptionsCount <= options.size()` (or `<= min(1408,12)` under the bypass) | `poll_creation_invalid_selectable_options_count` |

### 4.1 Zero-option / lenient bypass (found code path, semantics inferred)

A local boolean (`z`) computed from AB bool **37909**, only consulted when an internal parse-context counter equals 1, relaxes the minimum option count to 0 and widens the selectable-count ceiling to the raw `min(1408,12)` bound instead of `options.size()`. The parse-context value this corresponds to (normal receive vs. some other ingestion path, e.g. history sync) was not resolved; this is recorded as found-but-unexplained rather than a confirmed user-visible "optionless poll" feature.

### 4.2 History-sync / lenient-name bypass

A separate context flag (`c33371Eg0.A0W`) short-circuits both the name-length and (equivalently, in `F39`, §9) the result-snapshot name-length check, accepting the raw string unchecked. Consistent with a trusted-source parse path (e.g. local history re-import) rather than a normal network receive; not independently confirmed.

---

## 5. Image-poll options: `pollCreationOptionImageMessage`

### 5.1 Structure and linking (found)

`pollCreationOptionImageMessage` (field 90) wraps an ordinary uploaded `ImageMessage` inside a `FutureProofMessage` — the image is **not** embedded in `PollCreationMessage.Option`. Each option image is sent as its own child message, associated with the (not-yet-sent) poll via `MessageContextInfo.messageAssociation`, association type `MEDIA_POLL = 6` (`AnonymousClass122.MEDIA_POLL`; this build's enum value — a prior build had it at 7, the numeric value is not stable across versions and must be re-read per release). The "MediaPollAssociationProvider" send-side helper (in `C20M`) counts `message_association` rows for the parent poll's row id and association type `6`; once the count reaches the option count, all option images are considered uploaded and the client proceeds to send the poll itself with `pollContentType = IMAGE`.

### 5.2 Option hash for image options (inferred, carried from an earlier build, not re-derived line-by-line in 2.26.41.6)

For plain text options the wire `optionHash` field is left empty; the only hash computed for a plain text option is the local lookup digest `C13J.A00`:

```text
optionHash(text option) = Base64(SHA-256(UTF8(optionName)))
```

(confirmed directly in 2.26.41.6, §9.1 — this is the hash used to match vote selections, not the proto `optionHash` field). For **image** options the proto `optionHash` field is populated; a prior-version trace of the send sequence found it combines the option name hash with the uploaded image's `fileSha256`:

```text
nameHash   = lowerHex(SHA-256(UTF8(optionName)))
imageHash  = base64(imageMessage.fileSha256)
optionHash = lowerHex(SHA-256(UTF8(nameHash + imageHash)))
```

This formula was not re-verified against 2.26.41.6 code in this pass (the computing class was not located); it is carried over as inferred and should be re-checked before being relied on.

---

## 6. `pollAddOptionMessage` (`C30556DRc`, field 121)

### 6.1 Fields (found)

`pollCreationMessageKey` **1** (`MessageKey`), `addOption` **2** (`PollCreationMessage.Option`), `metadata` **3** (`PollUpdateMessageMetadata`, same shape as the vote's, §7).

### 6.2 Send (found, `F2L.ADr`)

Builds one `Option` from the new name (and, for image polls, its hash), attaches the originating poll's key, and — for 1:1 chats, when not an edit context — resolves the sender identity across the LID/PN boundary the same way the message-secret layer does for other add-ons (see [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.1 step 4). The option is *not* itself secret-encrypted at this layer as a `pollUpdateMessage` is: the add-option payload travels as a normal message field; what gets wrapped in `secretEncryptedMessage` (type `POLL_ADD_OPTION`) is the add-option attempt as a whole when it must ride the message-secret scheme (§8).

### 6.3 Receive validation (found, `F2L.CM7`)

| Check | Error |
|-------|-------|
| Feature gate: AB int **25758** must be non-zero | error **10017** |
| `pollCreationMessageKey` present | `poll_add_option_missing_poll_message_key` |
| `addOption` present | `poll_add_option_missing_poll_option` |
| Option name non-empty, ≤ 2500 chars | `poll_add_option_invalid_option` |

The resulting local object is secret-encrypted for transport using use case `Poll Add Option` (confirmed call into the message-secret helper with `AnonymousClass122.POLL_ADD_OPTION` as the association tag). Added options are tracked for existing-option matching the same way image-poll options are (association type `POLL_ADD_OPTION = 18`).

---

## 7. `pollUpdateMessage` (vote and vote metadata)

Full crypto (HKDF use case `Poll Vote`, AAD, AES-GCM, LID/PN identity retry) is in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3–§7; this section covers only what the poll-vote handler (`DUA`, extends `F2P`) does with the plaintext.

### 7.1 Two send/receive paths (found)

AB bool **6772** selects between:
- **on** (current): a shared encryption helper (`C33285Eeb`) builds the ciphertext and `MessageKey`; vote retried from a previously stored `(iv, payload)` pair when present instead of re-encrypting.
- **off** (legacy): an inline branch in `DUA` does the same HKDF/AES-GCM call directly, deriving the target sender identity itself (own LID for votes on the voter's own poll, else the vote target's resolved JID).

### 7.2 Vote payload: `PollVoteMessage` (`DPF`)

Single field `selectedOptions` **1**, repeated bytes — each entry is a 32-byte SHA-256 option-name digest (§9.1), not an index. `MessageAddOnPollVoteUtils` (`AbstractC33199EdC`) validates the decrypted selection:

| Check | Rule | Log tag |
|-------|------|---------|
| Selection size | ≤ 12 **and** ≤ the poll's `selectableOptionsCount` (when > 0) | `poll_vote_invalid_options_count` |
| Hash shape | each selected hash decodes to exactly 32 bytes | `poll_vote_invalid_option_hashes` |
| Duplicates | no repeated hash in one vote | `poll_vote_duplicate_option_hashes` |
| Resolution | every selected hash must match one of the poll's known (non-removed) option hashes | returns an error result, no match -> vote rejected |

### 7.3 End-time and metadata (found, `DUA.A01`)

A vote whose `senderTimestampMs` is after the poll's `endTime` is rejected (`poll_update_past_end_time`); under AB bool **2321** a rejected-vote event additionally feeds a telemetry counter (`N0e`). Vote `metadata` (`pollNameHash`, `lastEditStanzaId`) is stamped on send only under AB bool **31593**; on receive, a missing/empty metadata block is logged `"unstamped"` (not rejected by itself) while a *mismatching* stamp (checked by `C32977EZa`) drops the vote with `poll_update_tc_drop`. This metadata exists so a client can detect that it is voting against a poll whose edit history it has not caught up with yet.

---

## 8. Poll editing (`secretEncryptedMessage`, `secretEncType = POLL_EDIT`)

Carried inside the generic `secretEncryptedMessage` wrapper (field 82), not a poll-specific carrier; see [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §5/§7.4 for the envelope, AAD, and the error-code table (`poll_edit_message_stanza_invalid`, AB int **24886** gate, error **10016**). The poll-specific validation (`F3Y`, `SecretEncryptedMessageDeserializationValidator`) requires:

- the inner message is FMessage type 66 and is a poll both before and after the edit;
- `endTime`, `hideParticipantName`, `allowAddOption`, `selectableOptionsCount` and `pollType` are **unchanged** between the stored poll and the edited one — only the question text and/or option texts may differ;
- option matching: with a per-chat flag (`EOI.A01()`, id not resolved) enabled, edited options are matched against a stored rename history via a sequential (order-preserving) match, allowing options to be renamed in place; the exact behaviour of the non-renaming comparison branch is inferred (JADX again drops part of the control flow — the function falls through to `poll_edit_invalid_edits` in that branch in the decompiled form, which is unlikely to be the real client behaviour for a no-op edit).

A `"Couldn't edit poll"` toast string exists in resources, confirming poll editing is user-facing in this build, not merely a reserved protocol path.

---

## 9. Vote matching internals

### 9.1 Option hash (found, `C13J.A00`)

```text
optionHash = Base64(SHA-256(UTF8(optionName)))
```

Plain SHA-256 of the option's visible text, no key material. This is the value stored per local option (`C33283EeZ.A02`) and the value a vote's `selectedOptions` entries are matched against. Any application that knows the option's text can compute the same hash — the privacy of a vote comes entirely from the message-secret encryption of the vote payload (§7, and [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md)), not from the hash being unguessable.

---

## 10. Vote privacy / anonymity model

| Claim | Status |
|-------|--------|
| Votes are end-to-end encrypted per-voter, per-poll (HKDF `Poll Vote` use case) | found, [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3 |
| The option selected is identified by a content hash, not an index | found, §9.1 |
| `hideParticipantName` ("Hide voter names") suppresses display of who voted, in the UI | found (string `str2137`, field 10 of `PollCreationMessage`) |
| `hideParticipantName` hides the voter from the server or from other clients at the protocol level | **not supported by code read here** — the envelope `participant`/`from` (i.e. the voter's identity) is delivered and authenticated the same way for every add-on regardless of this flag (see [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §8); `hideParticipantName` is a display-only setting on the poll object, not a routing or encryption change |
| The poll creator can always determine who voted | inferred — nothing in the vote-decrypt path (§7, §9) depends on `hideParticipantName`; the creator's client decrypts every vote with the voter's identity as the modifier |

In short: WhatsApp polls are not anonymous to the poll creator. "Hide voter names" only controls whether *other participants* (in the "Poll votes" list) see who voted; it does not change what is cryptographically bound into the vote, and the server never learns the vote content either way (the usual E2E guarantee, not something specific to this flag).

---

## 11. Multi-select vs single-select

`selectableOptionsCount` (field 4) is the only mechanism: a vote with more selections than this value is rejected (§7.2). There is no separate "is multi-select" boolean on the wire — single-select is simply `selectableOptionsCount = 1`. The creation UI exposes this as a single toggle, **"Allow multiple answers"** (string `str425f`); when off the client is inferred to send `selectableOptionsCount = 1`, when on it is inferred to send `selectableOptionsCount = options.size()` (the UI does not appear to expose an arbitrary numeric cap — inferred from the single boolean string, not independently confirmed in the creation-UI code). The protocol itself permits any value `0..options.size()` (§4), so a client-side value other than 1 or "all options" is possible even if the stock UI does not offer it. Quizzes are implicitly single-select (one correct answer; voter-facing string `"Quiz • Select one correct answer"`, `str57a5`).

Voter-facing labels confirm the two modes: `"Select one"` (`str3865`) vs. `"Select one or more"` (`str3866`).

---

## 12. `pollResultSnapshotMessage` / `V3`: forward-time snapshot

### 12.1 Purpose (found, `F1A`)

Forwarding a live poll to another chat does **not** forward the interactive poll. `F1A` (one of several "forward" converters that all implement the same conversion interface used across message types — the sibling converter for unsupported types throws `"Cannot forward message of type: ..."`) converts the live poll (`C13J`) into a `Dd2` object: question text, every option's name and **current local vote count**, and the poll/quiz type. This is then serialized as `pollResultSnapshotMessage` (plain poll) or `pollResultSnapshotMessageV3` (quiz) and rendered with a dedicated view holder (`DWH`), distinct from the interactive poll bubble.

### 12.2 Fields (found, `DSF`)

`name` **1** (string), `pollVotes` **2** (repeated `PollVote` — `optionName` **1**, `optionVoteCount` **2**), `contextInfo` **3**, `pollType` **4** (same `PollType` enum as creation).

### 12.3 Validation (found, `F39`)

Same shape of checks as creation: name 1–5000 chars, at least 2 options, at most `min(AB 1408, 12)` options, each option name 1–2500 chars. For the **quiz** variant (`V3`), vote counts are forced to 0 on send — a forwarded quiz snapshot never discloses tallies, only the question and option list.

---

## 13. Limits summary

| Item | Limit | Source |
|------|-------|--------|
| Poll/question name length | 1–5000 chars | `F2N.A01`, `F39.A00` |
| Option name length | 1–2500 chars | `F2N.A01`, `F2L.CM7`, `F39.A00` |
| Option count (creation, snapshot) | 2–min(AB **1408**, 12) | `F2N.A01`, `F39.A00` |
| Selected options per vote | ≤ 12 and ≤ `selectableOptionsCount` | `AbstractC33199EdC.A02` |
| `selectableOptionsCount` range | 0–options.size() (0–12 under the lenient-context bypass, §4.1) | `F2N.A01` |
| Option-hash size (vote entries) | exactly 32 bytes | `AbstractC33199EdC` |

---

## 14. Feature flags (ids as read at call sites; names unresolved)

| ID | Type | Controls |
|----|------|----------|
| **1408** | int | server-configured max poll option count, hard client ceiling 12 regardless of value |
| **24884** | bool | honour `endTime` on receive of an extended poll (V5/V6); off -> downgraded to a future-proof placeholder |
| **24885** | int | gates acceptance of `hideParticipantName` on receive (exact polarity unresolved) |
| **24886** | int | poll edit receive gate; 0 -> rejected, error 10016 |
| **25758** | int (truthy) | poll add-option receive gate (error 10017); also gates duplicate-trimmed-option rejection on creation |
| **31593** | bool | stamp `pollNameHash`/`lastEditStanzaId` metadata on an outgoing vote |
| **6772** | bool | poll vote: shared encryption helper (on) vs legacy inline path (off) |
| **37909** | bool | permits a poll with zero options in a specific (unresolved) parse context |
| **2321** | bool | extra telemetry detail logged when a vote is rejected as past the poll end time |

Message-secret-layer flags that also affect polls (edit use case gate **17811**, generation gates, etc.) are documented in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §16 and not repeated here.

---

## 15. Baileys (confirmed facts only)

[WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §17 already covers the parts of a JavaScript implementation (`baron-baileys-v2` 1.5.17) that are relevant to polls, from reading `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`:

- The HKDF derivation and the `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option` use-case strings match the Android client's literals exactly, including the `id\0modifier` AAD for `Poll Vote`.
- The AAD, identity-retry (PN/LID), and missing-secret handling (fall back to the raw, un-decrypted update) match the Android behaviour described in this report (§7) and in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §7.2–§7.3.
- No send-side encryption path for `pollUpdateMessage` (or `encReactionMessage`, `encEventResponseMessage`, `encCommentMessage`) was found in the files read — i.e. that implementation could decrypt an incoming vote but the reviewed files contained no code to encrypt and send one.

Nothing poll-specific beyond what is already stated there was independently re-verified in this pass (no Baileys poll-creation, option-hash, or poll-edit code was read); no further Baileys claims are made here.

---

## 16. Error cases

| Symptom | Cause | Fix |
|---------|-------|-----|
| `poll_creation_invalid_options_count` | fewer than 2 or more than `min(1408,12)` options | keep options within range |
| `poll_creation_unmatched_correct_answer` | quiz `correctAnswer.optionName` does not equal any option's name | set the correct answer to an exact match |
| Poll silently not shown (downgraded) | `endTime`/`hideParticipantName`/`allowAddOption` set on a V6 poll but the matching AB flag is off on the receiver | sender-side, not fixable by content; receiver capability gap |
| `poll_vote_invalid_options_count` | vote selects more options than `selectableOptionsCount`, or more than 12 | respect the poll's cap |
| `poll_update_past_end_time` | vote (or add option / edit) timestamp after `endTime` | vote before the poll closes |
| `poll_update_tc_drop` | vote's `pollNameHash`/`lastEditStanzaId` does not match the receiver's view of the poll | resync poll edit history before voting |
| error **10017** on add-option | AB **25758** is zero on the receiver | receiver capability gap |
| error **10016** on poll edit | AB **24886** is zero on the receiver | receiver capability gap |
| `poll_add_option_past_end_time` | option added after `endTime` | add options before the poll closes |

---

## 17. Key distinctions

| This | Not this |
|------|----------|
| `pollCreationMessage`/V2/V3/V5/V6 (`PollCreationMessage` type) | `pollCreationMessageV4` (`FutureProofMessage` wrapping an inner basic poll) |
| `pollUpdateMessage` (vote, or vote metadata) | `secretEncryptedMessage` with `secretEncType=POLL_EDIT`/`POLL_ADD_OPTION` (poll edit / add option) |
| `pollAddOptionMessage` (the new option payload) | `secretEncryptedMessage` wrapper that carries it over the wire when message-secret-bound |
| `pollResultSnapshotMessage`/V3 (static, forwarded) | the live interactive poll (`pollCreationMessage*`) |
| Option selection by SHA-256(name) hash | selection by index — WhatsApp polls never select by position |
| `hideParticipantName` (UI display setting) | vote sender anonymity (does not exist; creator always resolves the voter) |
| `selectableOptionsCount` (the only multi/single-select signal) | a separate "is multi-select" boolean (none exists) |

---

## 18. Complete flow (creation, image option, vote, forward)

```
[Creator]                                          [Server]                     [Participant]
   │ build PollCreationMessage                        │                              │
   │  (quiz? -> V5; community subgroup? -> V2;         │                              │
   │   extras(endTime/hide/addOpt)? -> V6; else V3)    │                              │
   │ [image poll]                                      │                              │
   │  send N × pollCreationOptionImageMessage           │                              │
   │   (messageAssociation MEDIA_POLL=6, parent key)───▶───────────────────────────▶ received,
   │  wait for all fileSha256                           │                              associated
   │  compute optionHash per option                     │                              │
   │ send pollCreationMessage* ─────────────────────────▶──────────────────────────▶ store poll,
   │                                                    │                              secret
   │                                                    │        select option(s)     │
   │                                                    │        hash = SHA256(name)  │
   │                                                    │        key = HKDF(secret,   │
   │                                                    │          pollId‖creator‖    │
   │                                                    │          voter‖"Poll Vote") │
   │                                                    │        pollUpdateMessage    │
   │◀────────────────────────────────────────────────────◀ {key, vote{ct,iv}, ts} ────│
   │ validate: end time, selection count/hash shape     │                              │
   │ decrypt, resolve hash -> known option              │                              │
   │ apply vote                                         │                              │
   │                                                    │                              │
   │ [user forwards the poll elsewhere]                 │                              │
   │ convert live poll -> Dd2 (name, per-option count)  │                              │
   │ quiz? zero the counts                              │                              │
   │ send pollResultSnapshotMessage[/V3] ───────────────▶──────────────────────────▶ static bubble,
   │                                                    │                              not interactive
```

---

## 19. Unknowns

| Item | State |
|------|-------|
| Exact polarity of AB **24885** (hideParticipantName accept/downgrade) | decompiled branch structure incomplete |
| Image-option hash formula (`nameHash`+`imageHash`) for 2.26.41.6 | carried from a prior build, not re-derived in this build's code |
| AB flag id behind the per-chat "ordered option rename" toggle used in poll-edit matching (`EOI.A01()`) | id not resolved |
| Non-renaming branch of poll-edit option comparison | decompiler drops part of the control flow; the literal decompiled form always falls through to `poll_edit_invalid_edits`, which is unlikely to be the real behaviour for a no-op edit |
| Parse-context value (`c33371Eg0.A00 == 1`) that enables the zero-option bypass (AB **37909**) | not identified (history sync vs. another path) |
| Whether the stock creation UI can send `selectableOptionsCount` values other than 1 or "all options" | inferred from a single boolean toggle string, not confirmed against UI code |
| `MEDIA_POLL` association numeric value stability across versions | found as 6 in 2.26.41.6; a prior build used a different value, so do not hardcode it across versions |
