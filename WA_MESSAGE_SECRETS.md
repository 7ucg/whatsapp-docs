# WhatsApp Message Secrets — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-23
**Scope:** per-message `messageSecret` (generation, `MessageContextInfo`, local store, history sync), use-case key derivation (HKDF), AES-GCM IV / AAD, encrypted add-ons (`encReactionMessage`, `pollUpdateMessage`, `encEventResponseMessage`, `encCommentMessage`, `secretEncryptedMessage` edits), sender / target identity binding and LID / PN retry, orphans and missing-secret fallbacks, `<message>` stanza extensions (attributes, `<enc>` attributes, `<meta>`, `<biz>`, `<bot>`, `<hsm>`, `<reporting>`, `<cap>`, padding, companion support check), feature flags, Baileys comparison

---

## 1. What it is (technically)

Every message that can later receive an encrypted follow-up carries a random 32-byte secret in its own end-to-end encrypted payload (`MessageContextInfo.messageSecret`). A follow-up (reaction, poll vote, event response, comment, edit) is encrypted with a key derived from that secret, the id of the original message, the original sender and the modifier. The server relays the follow-up as an ordinary E2E message but cannot read it or move it to another target, user or use case without breaking GCM authentication. All statements are static analysis of the decompiled APK; nothing was captured on the wire. Tiers: **found** = read in code, **inferred** = deduced from code, **unknown** = not resolved. Obfuscated names were re-resolved in 2.26.41.6 from stable strings (`MessageSecretCryptoHelper/`, `MessageEncUtils/`, use-case strings, `FMessage*Protobuf/`, `SecretEncryptedMessagePreProcessor/`, `CompanionSupportVerifier/`).

The same release also defines the `<message>` stanza extensions (section 10 onward): attributes and child nodes that classify and route a message but do not carry its content. They are grouped here because `<meta polltype>` / `<meta event_type>` must agree with the secret-encrypted payload (7.4).

| Entity | 2.26.41.6 name | Role |
|--------|----------------|------|
| Crypto helper (`MessageSecretCryptoHelper`) | `C33285Eeb` | `A03` encrypt, `A04` decrypt (identity retry), `A02` target-key resolve |
| Encrypt / decrypt parameter carriers | `C32833ETl` / `C32854EUg` | data, sender, target key, use case / IV, payload, keys, sender |
| Key derivation | `AbstractC33322EfC.A02` + `AbstractC38961i0.A00` | HKDF-SHA256, zero salt |
| AES-GCM | `JniBridge.WCIAPIGcmAesCreateEncryptedCiphertext`, `AbstractC32243E6m.A00` (`MessageEncUtils`) | native, 16-byte tag |
| AAD providers | `FXU`: `C34633F1g` (Poll Vote), `C34632F1f` (Event Response), `C34634F1h` (WASA), `C34631F1e` (none) | additional data |
| Secret generator | `AbstractC33322EfC.A01` | `SecureRandom`, 32 bytes |
| Secret store (`MessageSecretStore`) / in-memory extra | `C35311ad` (table `message_secret`) / `C35171aP` on the message `C13G` | persist and carry |
| Original-key mapper (`ReferentialKeyUtil`) | `C43661qB.A03` | key of the unedited original message |
| Reaction handlers | `DU8` (send), `F2P` branch (receive) | `reactionMessage` / `encReactionMessage` |
| Poll vote / event response / comment | `DUA` / `DU9` / `F3W` | `pollUpdateMessage` / `encEventResponseMessage` / `encCommentMessage` |
| Secret-encrypted edits (`SecretEncryptedMessagePreProcessor`) | `F3Y`, enum `E2Q` | `secretEncryptedMessage` |
| Poll / event creation (secret taken on receive) | `F2N` / `F2M` | reads `messageSecret` into the FMessage |
| Proto: context / message / key | `C30624DTs` / `C30628DTw` / `BD5` | `MessageContextInfo` / `Message` / `MessageKey` |
| Stanza `type` chooser | `AbstractC30999De0.A02` | `text media reaction poll event pay medianotify scheduled-call` |
| Outgoing stanza contributors | `InterfaceC35538FaZ`: `F6K` (meta), `F6M` (bot), `F68` flags, `F69` cap, `F6H` padding, `F6L` / `F6C` reporting, `F6G` cstoken, `F6I` tctoken, `F6B` device-identity, `F6X` hsm | build children of `<message>` |
| `<meta>` accumulator | `EZV` (attributes `A01`, children `A00`) | one `<meta>` node |
| `<enc>` attribute builder | `AbstractC33466EhY.A09` | `v type count mediatype ...` |
| Companion support check | `C34757F6a` + `AbstractC32927EXc` | type and child allowlist |
| Incoming spec parsers | `C33474Ehg` (status / regular), `C23206A1f` (newsletter), `C34747F5q` (bot), `C34748F5r` (biz) | attribute and child extraction |
| WAM error event | `DZ7` / `C273212s` | `wam_message_secret_errors` |

---

## 2. The per-message secret

### 2.1 Where it lives (found)

`MessageContextInfo` (`C30624DTs`) is field **35** of `Message` (`C30628DTw`). Fields relevant here:

| Field | Number | Type | Use |
|-------|--------|------|-----|
| `deviceListMetadata` / `deviceListMetadataVersion` | **1** / **2** | message / int | device list hint (not secret related) |
| `messageSecret` | **3** | bytes (32) | per-message secret |
| `paddingBytes` | **4** | bytes | padding |
| `messageAddOnDurationInSecs` | **5** | uint32 | add-on lifetime (pin: must be 0 for unpin) |
| `botMessageSecret` | **6** | bytes (32) | bot variant of the secret |
| `botMetadata` | **7** | message | bot context |
| `reportingTokenVersion` | **8** | uint32 | reporting token version of this message |
| `messageAddOnExpiryType` | **9** | enum | add-on expiry |
| `messageAssociation` | **10** | message | association |

The history-sync carrier `WebMessageInfo` (`C30626DTu`) has its own `messageSecret` field **49** (found), used when messages are exported to a new companion (section 2.4).

### 2.2 Generation (found, conditions partly inferred)

The secret is `SecureRandom.nextBytes(byte[32])` (`AbstractC33322EfC.A01`). It is attached before the message is serialized:

| Place | Condition |
|-------|-----------|
| `C33166Ecf.A06` (prepare send) | message has no secret and at least one of: poll class `C13J`; `EZN.A01(msg)` (bot / add-on class, with chat-type flags **2200**, **11104**, **19303**); chat-class gates: group with flag **3143**, broadcast list with **3144**, status with **3145**, class gate **3146**; `C35201aS.A00` (flag **3142**, self / bot chat); event message `C213509Ao` |
| `AJ0` (send processor) | reporting-token version `C35241aW.A05()` (AB int **8860**, capped by `AbstractC35301ac.A00`) is non-zero and the message class is not excluded by `C35241aW.A02` (status, newsletter, selected add-on classes) |
| `C72h`, `C34455Exe`, `EPA` | status objects (`AbstractC34478Ey1.A0R`) get a fresh secret on creation |
| `C33437Eh4` | bot "request welcome" message, only when its caller asks |
| `C9mW` | message type 117, flag **24741**, when none is present |

The predicates behind `EZN.A01`, `C35201aS.A00` and the `3142`..`3146` gates were not fully resolved; the list above says what code checks, not which user-visible messages qualify. Messages without a secret cannot receive encrypted add-ons from this client (section 9).

### 2.3 Local storage (found)

`C35311ad` writes `message_secret(message_row_id, message_secret)` with replace semantics (`MessageSecretStore/insertMessageSecret`) and reads the last row for a `message_row_id`. The FMessage keeps it as extra `C35171aP` (`A0L` set, `A0c` get, `A0Q` = non-empty). Two processors in `AbstractC17240jU` (`C35161aO` and an anonymous one) write it when the extra is dirty and the chat qualifies.

### 2.4 Receive-side validation and transfer (found)

| Step | Behaviour |
|------|-----------|
| Proto validator `C33475Ehh.A0V` | `message_secret` must be exactly **32** bytes, error code **67**; the bot variant (`bot_message_secret`, group `whatsapp_security`) is validated the same way |
| Poll creation `F2N` | copies `messageSecret_` into the new FMessage (`A0L`) |
| Status question answers `C34838F9e` | same copy for `statusQuestionAnswerMessage` |
| History sync export `C34388EwZ.A00` | writes the stored secret into `WebMessageInfo.messageSecret` (49) |
| History sync import `C34388EwZ.C59` | copies it back (`A0L`) |
| Comments `C34387EwY` | rebuilds a `MessageContextInfo` from `WebMessageInfo.messageSecret` for the comment thread |

`wam_message_secret_errors` (`DZ7`, `C273212s.A00`) logs `message_secret_error` **0** = missing (maps to error code 66) or **1** = invalid length (67) for messages that require a secret (`AbstractC33322EfC.A00`: has the flag and is not class `C35281aa`).

---

## 3. Use-case key derivation

### 3.1 Formula (found, `AbstractC33322EfC.A02`)

```text
info = UTF8(originalMessageId) ‖ UTF8(targetSender.rawString) ‖ UTF8(modifier.rawString) ‖ UTF8(useCase)
prk  = HMAC-SHA256(key = 32 × 0x00, data = messageSecret)          // HKDF extract
key  = HMAC-SHA256(key = prk, data = info ‖ 0x01)                  // HKDF expand, L = 32, one block
```

`AbstractC38961i0.A00(secret, info, 32)` = extract with a 32-byte zero salt (`AbstractC38971i1.A00(ikm, salt)`), then the RFC 5869 expand loop. HKDF basics: [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md) section 5.1. The 32-byte output is used as an AES-256 key (inferred from the length; the native call takes the key as `byte[]`).

Inputs:

| Input | Source | Notes |
|-------|--------|-------|
| `originalMessageId` | key id of the target after `ReferentialKeyUtil` (`C43661qB.A03`) on encrypt; key id from the proto `targetMessageKey` on decrypt | for an edited target this is the **original** message id (`getOriginalKey` log) |
| `targetSender` | author of the original message: stored sender (`C12300aw.A01`) | `UserJid`, so no device suffix (type-level; the string form `user@server` is inferred) |
| `modifier` | author of the add-on: own account JID (`C09A.A0G`, a LID, returned by `CUC()` / `Ash()`) when sending, the sender JID of the envelope when receiving | |
| `useCase` | string from 3.2 | no separator between the four components |

Own JID is a LID account JID (`C14080dr`, server `lid`, "Invalid LID" check). Both `AnonymousClass091.Ash()` and `CUC()` return the same field.

### 3.2 Use-case strings (found)

| Use case | Carrier | AAD | Java literal in 2.26.41.6 |
|----------|---------|-----|---------------------------|
| `Enc Reaction` | `encReactionMessage` | none | `DU8`, `F2P` |
| `Poll Vote` | `pollUpdateMessage.vote` | `targetId ‖ 0x00 ‖ modifier` | `DUA`, `C0ZG`, `C33285Eeb.A00` |
| `Event Response` | `encEventResponseMessage` | `targetId ‖ 0x00 ‖ modifier` | `DU9`, `F2P`, `C33285Eeb.A00` |
| `Enc Comment` | `encCommentMessage` | none | `F3W` |
| `Event Edit` | `secretEncryptedMessage` type 1 | none | `F3Y.A00` |
| `Message Edit` | `secretEncryptedMessage` type 2 | none | `F3Y.A00`, only with flag **17811** |
| `Poll Edit` | `secretEncryptedMessage` type 4 | none | `F3Y.A00` |
| `Poll Add Option` | `secretEncryptedMessage` type 5 | none | `F3Y.A00` |
| `WASA` | bot path (`C33284Eea`) | `keyId ‖ 0x00 ‖ jid` | two-stage, 3.3 |
| `Report Token` | reporting token key | native | no Java literal; present in `libwhatsapp.so`, derived natively (3.4) |

### 3.3 Bot / WASA variant (found, details inferred)

For use case `WASA` the derivation has two stages and no use-case string in the second:

```text
k1  = HKDF-SHA256(secret, salt = 0×32, info = "Bot Message", L = 32)      // AbstractC33322EfC.A00
key = HKDF-SHA256(k1,     salt = 0×32, info = id ‖ jidA.raw ‖ jidB.raw, L = 32)
AAD = UTF8(keyId) ‖ 0x00 ‖ UTF8(modifier.raw)                              // C34634F1h
```

`jidA` is the modifier and `jidB` the remote (chat) JID, which must be a `UserJid` (`WASA info jid must be a UserJid (hatch_jid)`); the id is the current message key when present, else the target key (`C33285Eeb.A03` lambda). Native counterpart: `WcmBotMessageSecretAPICreateWithMessageSecret`. Meta AI context: [WA_META_AI.md](./WA_META_AI.md).

### 3.4 Reporting token key (found / inferred)

`C33364Efs.A06` and `C33421Ego` call `JniBridge.WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)`: the native object derives the key for use case id **5**; the Java side only passes JID raw strings. The string `Report Token` exists in the native library; the mapping of id 5 to that string is inferred. Token and upload: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 4. AEAD layout

| Item | Value | Tier |
|------|-------|------|
| Cipher | AES-GCM, native (`WCIAPIGcmAesCreateEncryptedCiphertext(key, iv, plaintext, aad, 16)`; decrypt `jvidispatchOIOOOOO(6, 16L, ctx, key, iv, ciphertext, aad)`) | found |
| Key | 32 bytes from section 3 | found |
| IV | **12** random bytes per encryption (`SecureRandom`); decrypt rejects any other size | found |
| Tag | 16 bytes; the constant 16 is passed on both calls; position (appended to ciphertext) inferred from Baileys decrypt | found / inferred |
| AAD | per use case (3.2); `null` when the provider is `C34631F1e` | found |
| Plaintext | the serialized inner proto (table 5) | found |
| Output | `(encIv, encPayload, targetMessageKey)` triple (`C53966OMp`) | found |
| Empty result | `encryption values are invalid` log, error `Encryption using iJniBridge failed` | found |

Poll-vote retry: if the vote already holds IV and payload (`C30957Dd6.A03` / `A04`) the same ciphertext is resent instead of re-encrypting (found, `DUA` legacy branch).

---

## 5. Carriers and plaintexts

| Carrier (field in `Message`) | Class | Fields | Decrypted plaintext |
|------------------------------|-------|--------|---------------------|
| `encReactionMessage` **56** | `DRO` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `ReactionMessage` (`DSH`): `key` **1** (cleared before encryption), `text` **2**, `groupingKey` **3**, `senderTimestampMs` **4** |
| `pollUpdateMessage` **50** | `DSG` | `pollCreationMessageKey` **1**, `vote` **2** (`PollEncValue` `C30530DQc`: `encPayload` **1**, `encIv` **2**), `metadata` **3** (`C30532DQe`: `pollNameHash` **1**, `lastEditStanzaId` **2**), `senderTimestampMs` **4** | `PollVoteMessage` (`DPF`): `selectedOptions` **1** (repeated bytes, option hashes) |
| `encEventResponseMessage` **76** | `DRN` | `eventCreationMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `EventResponseMessage` (`DRP`): `response` **1** (`E2D`: 0 unknown, 1 going, 2 not going, 3 maybe), `timestampMs` **2**, `extraGuestCount` **3** |
| `encCommentMessage` **71** | `DRM` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | full `Message` (the comment body); plaintext form is `commentMessage` **77** (`DQV`: `message` **1**, `targetMessageKey` **2**) |
| `secretEncryptedMessage` **82** | `DSI` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3**, `secretEncType` **4** | full `Message` |
| `reactionMessage` **46** | `DSH` | plaintext form | plain reaction |
| `conditionalRevealMessage` **120** | n/a | not the message-secret scheme (section 14.1) | scheduled messages |

`SecretEncType` (`E2Q`): `UNKNOWN` 0, `EVENT_EDIT` **1**, `MESSAGE_EDIT` **2**, `POLL_EDIT` **4**, `POLL_ADD_OPTION` **5**. Value 3 does not exist in this build (`forNumber(3)` returns null, treated as unknown and rejected).

`MessageKey` (`BD5`): `remoteJid` **1**, `fromMe` **2**, `id` **3**, `participant` **4**.

---

## 6. Sender side

### 6.1 Common path (found, `C33285Eeb.A03`)

1. Resolve the target FMessage by key (`target message not found. Cannot proceed further` -> error 71).
2. Read its secret from `message_secret`; null or length != 32 -> `message secret missing or invalid` (66).
3. Original key via `C43661qB.A03` (null -> error 0). Target sender via `C12300aw.A01`.
4. In a 1:1 chat (`C0DZ.A0k(chat)`) the target sender is converted into the modifier's namespace: modifier LID and target PN -> target mapped PN to LID; modifier PN and target LID -> target mapped LID to PN. In groups no conversion.
5. Event Response only: flag **15791**, 1:1 chat and an account-type modifier -> modifier converted to PN.
6. Random 12-byte IV, derive key (3.1), AES-GCM with the use-case AAD.
7. Build the outer `MessageKey` from target sender and original key (`C32717EOy.A01`); the carrier holds `targetMessageKey`, `encIv`, `encPayload`.

### 6.2 Per carrier (found)

| Carrier | Gate on send |
|---------|--------------|
| Reaction (`DU8.ADr`) | encrypted **only** if the chat is a group (`C0DZ.A0l`) with `group_type == 3` (`C0GQ.A0A`; set in `CMP` from `isDefaultSubgroup_`, i.e. a community default subgroup, interpretation inferred) and serialization-context flag `A09` is false. In every other chat the plain `reactionMessage` is sent. `ReactionMessage.key` is nulled before encryption (the key moves to the outer `targetMessageKey`) |
| Poll vote (`DUA.ADr`) | flag **6772** on: shared helper, always encrypted; off: legacy inline branch with the same derivation and AAD (target sender = own LID for own polls, else the JID derived from the vote's target key; modifier = own LID). `metadata` (`pollNameHash`, optional `lastEditStanzaId`) is stamped when flag **31593** is on |
| Event response (`DU9.ADr`) | always encrypted; plaintext `EventResponseMessage` has `response`, `timestampMs`, `extraGuestCount` |
| Comment (`F3W.ADr`) | always encrypted; plaintext is the whole comment `Message`; the target is `CommentMessageInfo` parent key |
| Secret-encrypted edit (`F3Y.C5S`) | only when the message has edit info of type `E2Q` and the serialization context is not forwarded / orphan; `MESSAGE_EDIT` additionally needs flag **17811** (otherwise `getUseCase` throws). For own-message edits two log lines (`sending the Message Yourself edit unwrapped`, `sending the agent reply edit unwrapped`) show cases that are sent as plain edits; the full condition (flags **37948**, **35457**) was lost in decompilation |

Nested secret-encrypted payloads are rejected on both sides (`nested_secret_encrypted_message`).

---

## 7. Receiver side

### 7.1 Decrypt (found, `C33285Eeb.A04`)

```text
target key  = A02(remoteSender, messageKey, proto.targetMessageKey)       // perspective flip, Ddz.A00
parent      = message store lookup (ReferentialKeyUtil)
secret      = message_secret[parent.row]                                   // null -> 66, len != 32 -> 67
checks      = IV == 12 bytes, payload non-empty (else 11), senderUserJid != null, targetSender != null
key, aad    = section 3 / 4
plaintext   = AES-GCM-decrypt(key, iv, payload, aad)                       // fail -> identity retry
```

`senderUserJid` (modifier) per carrier: own LID when the envelope is from me; poll: sender JID (`c0df` or `B4g()`); event response: chat user in 1:1 else envelope user; comment: LID only (`C0DZ.A0Y`: types 18, 19, 25), a PN sender fails with error 0; reaction: envelope sender only if it is a LID, otherwise null.

### 7.2 LID / PN identity retry (found structure, tail inferred)

The first attempt uses the JIDs as given. On failure the helper maps both JIDs into the other namespace (`C0YH.A0I` LID->PN, `A0F` PN->LID) and retries once; if both were already LID or the mapping is missing the result is error **51** (decrypt failed). The decompiled tail of the retry is partly lost, so the exact set of attempted pairs is inferred. The check is GCM authentication: a wrong pair fails, the right one decrypts.

### 7.3 Parent missing: orphans (found)

| Carrier | Behaviour when the parent is not found or is a placeholder |
|---------|-----------------------------------------------------------|
| Reaction | FMessage type **56** is stored with the raw `Message` bytes (`DdA(key, 56, ts).A02`); decrypt is deferred |
| Poll vote | `C30957Dd6.A02 = Message.toByteArray()`; stored undecrypted |
| Event response | `Dd7(key, target, bytes, ts)` stored undecrypted |
| Comment | placeholder `C34671Zb` with parent key and row `-1` |
| Secret-encrypted edit | `DeD(MessageOrphan)` with orphan type **5**, reason **1** (parent absent) or **2** (placeholder) |

Replay when the parent arrives is expected (orphans are persisted with the raw bytes) but the replay trigger was not traced (inferred).

### 7.4 Validation after decrypt (found)

| Case | Check | Failure |
|------|-------|---------|
| Stanza `type=poll` + `<meta polltype="edit">` | `secretEncType` must be `POLL_EDIT` | `poll_edit_message_stanza_invalid` (76) |
| `polltype="add_option"` | type `POLL_ADD_OPTION` and a second stanza field equal to `poll_add_option` (field unresolved) | `poll_add_option_stanza_invalid` (76) |
| Event edit | inner message type 92, resulting key equals outer key | `invalid secret encrypted message` (76) / `the resulting message key does not match outer key` |
| Poll edit | inner type 66, both messages polls, same end time and flags, option edits consistent with stored options, timestamp not after end time | `poll_edit_invalid_edits`, `poll_edit_invalid_option_edits`, `poll_edit_invalid_time` |
| Poll add option | inner type 137, parent is a poll, target key equals outer key, not after end time | `poll_add_option_past_end_time` |
| Poll edit receive | AB int **24886** must be non-zero | error 10016 ("futureproofing") |
| Poll add option receive | AB **25758** must be non-zero | error 10017 |
| Poll vote | selection must be valid for the poll (`AbstractC33199EdC.A02`); vote timestamp not after the poll end time | `poll_update_past_end_time`, `invalid poll vote selection` |
| Poll vote metadata | `pollNameHash` + `lastEditStanzaId` checked against the stored poll (`C32977EZa.A01`); "unstamped" when absent; mismatch drops the vote | `poll_update_tc_drop` |
| Poll vote shape | IV exactly 12 (`poll_update_invalid_vote_enc_iv`), payload present, sender timestamp present | error 11 |
| Event response | key, IV (12), payload present; parent must be an event or a sender-revoke message | `parent message is not event message nor sender revoke` |

---

## 8. Sender / target binding

| Bound by the key | Effect |
|------------------|--------|
| Original message id | a ciphertext cannot be reused on another message |
| Target sender JID | cannot be attributed to a different original author |
| Modifier JID | cannot be replayed as another user's add-on |
| Use-case string | a reaction ciphertext does not decrypt as a vote, comment or edit |
| AAD (poll vote, event response) | additionally binds `targetId` and modifier into the tag |

Not bound: chat JID, timestamp, ciphertext position in the thread, the number of previous add-ons. The envelope `participant` / `from` is what the receiver uses as the modifier; it is authenticated by the E2E session, not by the secret. Anyone holding the original secret (every participant that received the original message, in a group) can derive keys for any modifier; the scheme prevents relay-side retargeting, not impersonation by group members (inferred from the construction).

---

## 9. Missing-secret fallbacks (found unless marked)

| Situation | Sender | Receiver |
|-----------|--------|----------|
| Original has no secret | encrypt fails (66); poll legacy path: `invalid message_secret secretSize` | parent present, secret null: error **66**, logged to the error reporter with `parentMsgRowId`, `parentType`, `parentHasSecret`; `wam_message_secret_errors` code 0 |
| Secret not 32 bytes | encrypt rejected | error **67**, WAM code 1 |
| Parent not found | encrypt error 71 | stored as orphan (7.3) |
| Reaction in a non-default-subgroup chat | plaintext `reactionMessage` is sent instead (no secret needed) | handled by the plain branch |
| Message edit without flag 17811 | `getUseCase` throws (`unknown message secret encrypted type`, code 0); whether the sender avoids the type when the flag is off is unresolved | same throw |
| Add-on decrypt fails | n/a | add-on stays hidden / unavailable; no visible fallback text found (unknown) |
| New companion without the original | n/a | history sync carries the secret in `WebMessageInfo.messageSecret` (2.4) |
| `<enc decrypt-fail="hide">` | set on messages with edit info (12.3) | tells the receiver not to show a failure placeholder; consumer of the flag unresolved |

---

## 10. `<message>` stanza: what the client adds

Outgoing children are built by independent contributors (`InterfaceC35538FaZ`) that append to the stanza builder `C33150EcP`.

### 10.1 Attributes (found)

| Attribute | Producer / consumer | Values / meaning |
|-----------|--------------------|-------------------|
| `type` | `AbstractC30999De0.A02` | `text`, `media`, `reaction`, `poll`, `event`, `pay`, `medianotify`, `scheduled-call` (from the proto): `secretEncryptedMessage` with `EVENT_EDIT` -> `event`, with `POLL_EDIT` / `POLL_ADD_OPTION` -> `poll`; `MESSAGE_EDIT` falls through to `text` / `media`; reaction fields (plain or enc) -> `reaction`; poll update / creation -> `poll`; `encEventResponseMessage` and event -> `event` |
| `edit` | receive specs `C33474Ehg` (requires node tag `status`; its relation to the plain `<message>` stanza is unresolved), `C23206A1f` (newsletter); acks `AbstractC33465EhX.A05` | `1`, `7`, `8` in `C33474Ehg`; `3` and `8` in the newsletter spec; acks echo it unless `0` / empty; see 10.2 |
| `category` | stanza, acks, retry receipts | `peer` selects the peer-message path |
| `device_fanout` | `F6M` | `"false"` on targeted one-to-one retries |
| `addressing_mode`, `participant`, `recipient`, `expiration`, `offline`, `dhash`, `sts` | transport | identity / lifecycle, not content |
| `peer_recipient_pn`, `peer_recipient_lid`, `peer_recipient_username`, `recipient_latest_lid`, `participant_username`, `sender_account_kind`, `sender_country_code`, `eph_setting` | identity parsers (`AbstractC33466EhY`, `C34763F6g`) | PN / LID / username aliases |

### 10.2 `edit` values

| Value | Context | Tier |
|-------|---------|------|
| `1` | edit of a sent message (parsed in `C33474Ehg.A0L`) | found |
| `2` | pin in chat: the receive path requires internal edit version 2 (`Invalid edited version`) | inferred mapping to the attribute |
| `3` | newsletter message edit: parsed only in the newsletter spec (`C23206A1f.A0G`), and `EWW.A01` sets edit version 3 when the chat is a newsletter (JID type 21, server `newsletter`) | found (this resolves the earlier "unknown 3") |
| `7` | revoke by the sender (`C33474Ehg.A0M`) | found |
| `8` | admin delete (`C33474Ehg.A0S`, newsletter spec `A0H`) | found |
| `0` / empty | normal message; omitted from acks | found |

Internal edit version (`EWW.A01`) is `1` for normal chats and `3` for newsletters; normal-chat edits also set the `decrypt-fail` hide flag (12.3).

### 10.3 Direct children (found)

| Child | Producer | Meaning |
|-------|----------|---------|
| `enc` | encryption layer | ciphertext, see section 11 |
| `participants` / `to` | `F6E` and fanout | per-device ciphertexts |
| `device-identity` | `F6B` | signed device identity |
| `registration` | parser `C33474Ehg.A04` | exactly 4 bytes |
| `tctoken` | `F6I`, `AbstractC33466EhY.A01` | at most AB int **20606** per stanza, enabled by **20605** |
| `cstoken` | `F6G` | cold-contact token |
| `padding` | `F6H` | random bytes, `retryCount × 1571` long, flags **8311**, **9209** (`ta_pad` also present) |
| `reporting` | `F6L` / `F6C` | `<reporting><reporting_token v>` (16-byte HMAC), see [WA_REPORTING.md](./WA_REPORTING.md) |
| `meta` | `F6K` | section 12 |
| `bot` | `F6M` | 13.2 |
| `hsm` | `F6X` | `category`: `OTP`, `TRANSACTIONAL`, `NON_TRANSACTIONAL`, `OTHER`; `tag`: `AUTHENTICATION`, `UTILITY`, `MARKETING` |
| `biz` | business processor `C34748F5r` | 13.1 |
| `automated`, `multicast`, `url_text`, `url_number` | `F68` | empty flag nodes from a bitmask in the builder: `2` url_text, `4` url_number, `64` multicast, `128` automated |
| `rcat` | parser | opaque binary category (status) |
| `cap` | `F69` | `<cap client_capping_ready="true|false">` on sends to JID type 3 (broadcast list, inferred), flags **16656** (emit) and **13537** (value) |
| `verified_name` | business | verified-business certificate |
| `unavailable`, `bypassed` | parser | marker nodes; `unavailable` literal not matched in 2.26.41.6 (constant-based), semantics unverified here |

---

## 11. `<enc>` node

### 11.1 Attributes (found, `AbstractC33466EhY.A09`)

| Attribute | Value | Condition |
|-----------|-------|-----------|
| `v` | `2` or `3` | ciphertext version (receive parser accepts `EncVersion2`, `EncVersion3`, futureproof) |
| `type` | `msg`, `pkmsg`, `skmsg`, `frskmsg`, `msmsg`, `none` | Signal message, prekey message, sender key, `frskmsg`, bot `msmsg`, plaintext marker |
| `count` | retry count | omitted when 0 |
| `mediatype` | see 11.2 | media / interactive classification |
| `native_flow_name` | flow name | native-flow messages |
| `duration` | int >= 0 | live location |
| `decrypt-fail` | `hide` | message flagged hideable (12.3) |
| `state` | `false` | `pkmsg` sends under a flag in the ciphertext carrier |
| `session_type` | `pq` | post-quantum session carrier flag |
| `bucket` | string | when set on the ciphertext carrier |

Receive checks (`C33013EaB`): two `<enc>` nodes in one message must agree on retry count and ciphertext version; `enc` on a newsletter is rejected (`Received enc message for newsletters`); `decrypt-fail=hide` is honoured only when the category is not `peer` and the chat predicate `C1ZB.A0L` is false.

### 11.2 `mediatype` values accepted by the spec (found, 37 entries)

`audio`, `avatar_sticker`, `buttons_response`, `cataloglink`, `collection`, `contact`, `contact_array`, `document`, `feed_reshare`, `genai_sticker`, `gif`, `group_history`, `history`, `image`, `instant_image`, `list_response`, `location`, `motion_photo`, `motion_video`, `music`, `native_flow_response`, `order`, `product`, `productlink`, `ptt`, `ptv`, `request_location`, `request_location_update`, `sticker`, `sticker_pack`, `story_reply`, `url`, `user_created_sticker`, `vcard`, `video`, `xma`, `1p_sticker`. `native_flow_name` enum (8 entries): `a2ui_reply_action`, `account_authentication_request`, `address_message`, `api_signup`, `call_permission_request`, `form_message`, `galaxy_message`, `menu_options`. `sticker_type`: `avatar`.

---

## 12. `<meta>` node

All attributes and children are accumulated in `EZV` by the handlers `F6K` calls (per message class `FXq.AAl`, per add-on `FZH.AAl`) and emitted as one `<meta>` (`C33150EcP.A00`). An empty accumulator emits nothing.

### 12.1 Operation classifiers (found)

| Attribute | Values | Producer |
|-----------|--------|----------|
| `polltype` | `creation`, `edit` (`F2N`), `vote` (`DUA`), `add_option` (`F2L`, `F4E`) | poll handlers |
| `event_type` | `creation`, `edit` (`F2M`), **`response`** (`DU9`) | event handlers |
| `content_type` | `add_on` for add-on class `AbstractC35181aQ` (includes reactions; votes / responses inferred) in chats where `C0DZ.A0U` is false; `status_notify` / `add_on` for status notifications | `F6K` |
| `type` | `scheduled_message` with `st` (seconds, omitted for the unschedule message class) and child `<key rkid="...">` (key bytes omitted for that class) | `F6K`, conditional reveal |
| `appdata` | free string of `FZF.AVN()`; editing appdata is rejected | `F6K` |
| `tag_reason` | `user_update`, `new_member`, `rereg_recovery_request`, `rereg_recovery_response`, `user_delete` | member-tag message `F3F` |
| `context_source` | `channels_invitation`, `event_invitation` (and others) | `AJR` |
| `message_association_type` | association token, plus `hd_image_dual_upload`, `hevc_video_dual_upload`, `av1_video_dual_upload` on status uploads | `F4G`, `F4H` |
| `premium_type` | `1` | `F4F` |
| `thread_msg_id`, `thread_msg_sender_jid` | parent id / JID | `AJT` |
| `is_status_mention` / `is_group_status_mention` | `true` | `AJS` |
| `status_setting` | `contacts`, `allowlist`, `denylist`, `customlist`; `is_group_status` `true`; child `mentioned_users/to` | `F4H` |
| `origin` | `ctwa`, `group_status`, `general`, plus Meta AI entry-point strings (`favicon`, `chat_list`, `nullstate_*`, `typeahead_*`, ...) | `F6K`, `EnumC14320eI`, `C198208bu` |
| `acp` | `2` for 1:1 chats under flag **36091** (meaning unresolved) | `F6K` |
| `view_once` | `true` for view-once types under flag **11282** | `F6K` |
| `sender_intent` | `hosted` | `F6K` |
| `usecase` | `migration` (message type 108) | `F6K` |
| `share_pn` | `true` (message type 73) | `F6K` |
| `receiver_account_kind` | `guest` | `F6K` |
| `collection_type` | `document`, `image`, `video`, `mixed` | `F6K` |
| `destination_id`, `conversation_thread_id`, `thread_origin`, `peripheral` | bot / thread routing | `F6K` |

### 12.2 Parsed on receive (found)

`<meta>` inputs the client reads: `polltype`, `event_type`, `target_id`, `target_sender_jid`, `target_chat_jid`, `target_chat_jid_lid`, `from`, `capi` (group chats only), `thread_msg_id`, `message_association_type`, `status_mentioned`, `push_eligible`, `session_scope`, `content_type`, `tm_csat_exp_ts`, `tm_csat_cooldown` (seconds, stored in ms), `is_wamo_sub`, `original_msg_t`, `msg_edit_t`, and children `mention_source/to`, `mentioned_users/to`. Newsletter metas add `admin_profile`, `paid_partnership`, `ai_content` (listed from the earlier catalogue; not re-read here, unverified). `deprecated_lid_session` was not found in 2.26.41.6.

---

## 13. `<biz>`, `<bot>`

### 13.1 `<biz>` (found, `C34748F5r.CM3`)

```xml
<biz native_flow_name="...">                       <!-- or -->
<biz>
  <interactive type="native_flow">
    <native_flow name="..."/>
  </interactive>
  <buttons/> | <list/>
</biz>
<hsm category="..." tag="..."/>                    <!-- sibling, template classification -->
```

The receiver reads the flow name (`native_flow_name` or the nested `name`), then classifies: `buttons` present, `list` present, or native flow; with a name and an `hsm` sibling it becomes a template. Validation failures are named `InvalidTemplateMessage`, `InvalidListMessage`, `InvalidButtonMessage`, `InvalidInconsistentFlowName`, `InvalidFlowNotOwned`, `InvalidDeeplyNested`: a `biz` classifier that disagrees with the encrypted payload is a validation failure, not a different message type. Other `biz` attributes read elsewhere: `campaign_id`, `notification_cta`, `privacy_mode_ts`, `host_storage`, `actual_actors`, `biz_bot`, child `quality_control` with `decision_source`.

### 13.2 `<bot>` (found)

Outgoing (`F6M`): attributes `type` (`request_welcome`, `prompt`, `command`, `search`, `memu_onboarding`, `memu_invoke`, `voice`, `voice_background`, `text_input`, `live_ai`, `feedback`), `client_thread_id`, `mode_selected`, `persona_type` (`1p`, `ugc`, `3p`), `local_automated_type` (`1p_partial`), `agent_engagement_type`, `is_lid`, child `tee_routing` (`tee_routing_token`, `tee_ik_id`). Incoming (`C34747F5q`): `<bot edit="full|...">` default `full`, `edit_target_id`, `sender_timestamp_ms`, `type`, `client_thread_id`; without `<meta target_id>` the message is not handled as a bot response. Details: [WA_META_AI.md](./WA_META_AI.md).

---

## 14. Related schemes that are not message-secret

### 14.1 Conditional reveal (scheduled messages)

`conditionalRevealMessage` (field **120**) uses a separate random reveal key (`<meta type="scheduled_message" st><key rkid>`); the server controls the reveal. No HKDF from `messageSecret`. Reveal protocol internals not traced (unknown).

### 14.2 Reporting token

`reportingTokenVersion` (field **8**) and the 16-byte `<reporting_token>` use the native use-case id 5 key (3.4), not Java HKDF. Token content: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 15. Companion support verifier (found)

`CompanionSupportVerifier` (`C34757F6a`, only on a companion, behind a flag): non-`peer` messages are accepted only if the `type` is in `{text, media, reaction, poll, event}` (or `pay` with a remittance `transaction` / `pay` child) and every direct child is in `{registration, enc, device-identity, verified_name, url_text, url_number, padding, biz, meta, automated, multicast, rcat, reporting, bot, hsm}`. Otherwise it logs `unsupported child node=` / `unsupported message type=` and the message is classified unsupported on the companion. A peer broadcast with `participants` on a companion is dropped (`received peer broadcast message on companion-mode, dropping`, nack 415 / 18). The new `cap` child and `tctoken` / `cstoken` are not in the list; where they are handled before this check is unresolved. `unavailable` and `participants` go through their own paths.

---

## 16. Feature flags (ids as read at call sites; names unresolved)

| ID | Type | Controls |
|----|------|----------|
| **6772** | bool | poll vote: shared helper vs legacy inline encryption |
| **31593** | bool | poll vote `metadata` stamping |
| **17811** | bool | `Message Edit` use case (send and receive) |
| **37948**, **35457** | bool | conditions for wrapping own message edits |
| **24886** | int | poll edit receive (0 = rejected, 10016) |
| **25758** | int | poll add option receive (0 = rejected, 10017) |
| **15791** | bool | event response modifier LID -> PN in 1:1 chats |
| **3142**-**3146**, **2200**, **11104**, **19303** | bool | secret generation by chat class |
| **8860** | int | maximum reporting-token version (secret generation) |
| **24741** | bool | secret for message type 117 |
| **36091** | bool | `meta acp="2"` |
| **11282** | bool | `meta view_once` |
| **16656**, **13537** | bool | `cap` child and its value |
| **8311**, **9209** | bool | padding |
| **20605**, **20606** | bool / int | `tctoken` enable / per-stanza cap |

---

## 17. Baileys (`baron-baileys-v2` 1.5.17, source read, nothing tested)

Only facts read in `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`.

| Topic | Baileys | Android |
|-------|---------|---------|
| Key | `key0 = HMAC-SHA256(key = 0×32, secret)`; `decKey = HMAC-SHA256(key = key0, id ‖ creator ‖ modifier ‖ useCase ‖ 0x01)` | identical (3.1) |
| Use cases | `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option`, plus `Message Schedule` for enum 3 | same strings; value 3 is not defined in 2.26.41.6 |
| AAD | `id\0modifier` for poll and event, empty for edit / comment / reaction | same |
| Identity | tries PN and LID candidates of creator and modifier, GCM authenticates the right pair | same idea (7.2) |
| Missing secret | logs, emits the raw `encReactionMessage` / `pollUpdateMessage` update, no decrypt | stored as orphan |
| Secret generation | `randomBytes(32)` for poll, event and when `messageContextInfo.messageSecret` is missing | 2.2 |
| Reporting key | `hkdf(secret, 32, { info: id ‖ sender ‖ modifier ‖ 'Report Token' })`; reporting skipped for reactions, `encReactionMessage`, `encEventResponseMessage`, `pollUpdateMessage` | native id 5 (3.4) |
| Send side | no sender for `pollUpdateMessage`, `encReactionMessage`, `encEventResponseMessage` or `encCommentMessage` was found in the files read | Android sends all four |

Consequence read from the code: Baileys can decrypt follow-ups it receives but the files read contain no encryption for them. Whether a send helper exists elsewhere was not searched.

---

## 18. Error cases

| Symptom | Cause | Fix |
|---------|-------|-----|
| Error 11 | IV not 12 bytes or empty payload / missing field | check `encIv` (field 3, or 2 for `PollEncValue`) |
| Error 51 | wrong sender / target JID namespace (PN vs LID), wrong original id | retry both namespaces, use the original (unedited) message id |
| Vote for an edited poll fails | key id must be the original poll id, not the latest edit id | resolve the original key |
| Comment from a PN sender fails | comment decrypt requires a LID sender | use the LID |
| Poll edit / add option rejected | flags **24886** / **25758** off, or stanza `polltype` disagrees with `secretEncType` | send matching `<meta polltype>` and type |
| Message ignored on a companion | unknown child node or `type` | keep to the allowlist (section 15) |
| `<biz>` message unsupported | classifier disagrees with payload | derive classifier from the payload |

---

## 19. Key distinctions

| This | Not this |
|------|----------|
| `messageSecret` (per message, random, 32 bytes) | media key, sender key, app-state sync key, call key |
| Use-case key (HKDF, per target / user / use case) | the secret itself |
| `secretEncryptedMessage` (wraps a complete `Message`) | `encReactionMessage` (wraps a `ReactionMessage`) |
| `Poll Vote` / `Event Response` AAD = id + NUL + modifier | edit / comment / reaction with empty AAD |
| `targetMessageKey` in the outer carrier | `ReactionMessage.key` inside the plaintext (cleared on send) |
| `meta polltype` / `event_type` (classifier) | the encrypted payload (content) |
| `edit` stanza attribute | `secretEncType` (encryption use case) |
| `decrypt-fail="hide"` on `<enc>` | retry receipt / `retry` node |

---

## 20. Complete flow (poll vote, 1:1 or group)

```
[Creator]                                            [Server]                      [Voter]
   │ poll creation Message                              │                             │
   │ messageContextInfo.messageSecret = random 32       │                             │
   │ store message_secret[row]                          │                             │
   │ <message type="poll"><meta polltype="creation">────▶────────────────────────────▶ stores secret
   │                                                    │                             │
   │                                                    │      select options (hashes)│
   │                                                    │      secret = store[poll]   │
   │                                                    │      key = HKDF(secret,     │
   │                                                    │        pollId‖creator‖voter │
   │                                                    │        ‖"Poll Vote")        │
   │                                                    │      iv = random 12         │
   │                                                    │      ct = GCM(key, iv,      │
   │                                                    │        PollVoteMessage,     │
   │                                                    │        aad = pollId\0voter) │
   │              <message type="poll"><meta polltype="vote">                         │
   │◀────────────────────────────────────────────────────◀ pollUpdateMessage{key,vote{ct,iv},metadata,ts}
   │ parent found? no -> orphan, keep raw bytes         │                             │
   │ validate end time, enc iv = 12                     │                             │
   │ key = HKDF(secret, pollId‖creator‖voter‖"Poll Vote")                              │
   │ GCM-decrypt, fail -> retry PN/LID pair, else 51    │                             │
   │ check option hashes ⊂ poll options, stamp match    │                             │
   │ apply vote                                         │                             │
```

---

## 21. Unknowns

| Item | State |
|------|-------|
| Exact predicates for `EZN.A01`, `C35201aS.A00`, flags 3142-3146 | per-chat-class gating seen, user-visible set unresolved |
| Native use-case id table (names to ids other than 5 = Report Token) | not read |
| GCM tag position and AES key size | inferred from constants and Baileys |
| Full condition for sending own `MESSAGE_EDIT` wrapped vs plain (flags 37948, 35457) | decompiler lost control flow |
| Meaning of `acp="2"`, serialization flag `A09`, second poll-add-option stanza field | unresolved |
| Consumer of `decrypt-fail="hide"` on the parsed envelope | flag carried into the envelope, effect not traced |
| User-visible result of a permanently undecryptable add-on | no fallback text found |
| `unavailable`, `bypassed`, `deprecated_lid_session` | not re-verified in 2.26.41.6 |
