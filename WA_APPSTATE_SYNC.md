# WhatsApp App-State Sync — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-23
**Scope:** app-state sync (syncd) on Android: five collections, `w:sync:app:state` IQ, patches / snapshots / external blobs, SET/REMOVE mutations, mutation key derivation and record encryption, index / value MACs, LT-Hash, snapshot and patch MACs, sync keys (generation, share, request, expiry), outgoing and incoming validation, sync action catalog (96 actions: chat, label, contact, nctSalt …), fatal and retry handling, snapshot recovery, feature flags, Baileys comparison

---

## 1. What it is (technically)

App-state sync replicates small per-account state (mute, pin, archive, star, contacts, labels, settings …) between the primary phone and every linked device. The server stores only end-to-end encrypted records, orders them per collection and serves versioned patches. All statements are static analysis of the decompiled APK; nothing was captured on the wire. Tier: **found** = read in code, **inferred** = deduced from code, **unknown** = not resolved. Obfuscated names were re-resolved in 2.26.41.6 from stable strings (`WhatsApp Mutation Keys`, `WhatsApp Patch Integrity`, `w:sync:app:state`, collection names, log prefixes).

| Entity | 2.26.41.6 name | Role |
|--------|----------------|------|
| Sync manager | `C12440bB` (`sync-manager/*`) | scheduling, `A0S` fatal failure, `A0Q` delete-all-data |
| Request handler / IQ builder / parser | `C53148Nnt` / `C46361ux` / `N90` | send IQ, build `<sync>`, parse result |
| Legacy response handler | `SyncResponseHandler` (`consumer/companiondevice/p049iq`) | legacy apply path, `A08` fatal handling |
| KMP engine | `com.whatsapp.kmp.syncd.syncdengine.*` | `OutgoingProcessor`, `IncomingProcessor`, `SyncdResponseHandler`, `SyncdResponseProcessor`, `CollectionHandler`, `crypto/*` |
| Collection enum / action enum | `EnumC24862AnK` / `EnumC24865AnN` | 5 collections / 96 action wire names |
| Action to collection | `AbstractC24863AnL.A00` | ordinal switch |
| Mutation base / handler base | `AbstractC24864AnM` / `AbstractC25077Aqp` | pending mutation / action handler |
| Key manager / store | `C12800bm` (`SyncdKeyManager`) / `C13620d6` (table `crypto_info`) | generate, share, request, expire, persist keys |
| Key id / key / key data | `CGH` / `C51259MoT` / `C51361MqC` | 6-byte id / id + data / data, `C8H` fingerprint, ts |
| Mutation keys | `MhX` | HKDF output, 5 slices |
| Share / request carriers | `C26102BPk` (FMessage 38) / `C26101BPj` (39) | peer messages |
| LT-Hash, HKDF | `AbstractC50511MVx.A00` + `KmpLtHash16`, `AbstractC38961i0` | 128-byte hash, RFC 5869 |
| Crypto (legacy / KMP) | `C52959NkE` / `KmpSyncdCryptoHelper`, `KmpSyncdEncryptor`, `KmpSyncdDecryptor`, `KmpSyncdIncomingAntiTamperingValidator` | identical formulas |
| External blobs | `C17650kB` (download), `KmpExternalMutationsUploaderImpl` | MMS type `md-app-state` |
| Bootstrap / delete-all / recovery | `C24986ApL` / `C17630k8` / `KmpSyncdFatalErrorRecovery` | state machine, `delete_all_data`, snapshot serve |
| Fatal kinds / legacy exception | `Lx6` / `C49784Lv2` | 70 named kinds / int `errorCode` |

Two implementations of the same protocol coexist. The KMP engine is selected by three server-controlled booleans whose compiled defaults are **false** (**15909** crypto, **20682** incoming, **18234** outgoing, section 12). Which path an account runs is unknown. MAC and encryption formulas are identical in both (compared in `C52959NkE` and `KmpSyncd*`).

Primary and companion run the same code. Found differences: only a primary creates `contact` / `lid_contact` mutations (`Companion cannot create contact mutations`); only a companion sends `return_snapshot="true"`; fatal handling differs (11.3).

---

## 2. Collections

| Wire name | Enum ordinal | Critical | Log bit (`C17530jy.A00`) | Actions |
|-----------|--------------|----------|--------------------------|---------|
| `regular` | 0 | no | 3 | 35 |
| `regular_low` | 1 | no | 5 | 36 |
| `regular_high` | 2 | no | 4 | 19 |
| `critical_block` | 3 | yes | 1 | 4 |
| `critical_unblock_low` | 4 | yes | 2 | 2 |

Critical set = `{critical_block, critical_unblock_low}` (`EnumC24862AnK.A01`). `A00()` maps ordinal to 1..5; consumer not traced.

On Android `critical_block` holds account-setting actions (`setting_pushName`, `setting_locale`, `setting_securityNotification`, `generated_wui`), **not** a block list; `contact` and `lid_contact` sit in `critical_unblock_low`. No action in the 96-entry enum is named after blocking (found).

**Bootstrap (companion, partly inferred).** `syncd_bootstrap_state` (`C24986ApL`) runs 0 → 4. Found: critical set synced → state 2 and a "critical blocking complete" signal; all non-critical collections synced → state 4; state 3 is the history-sync step (inferred). Failure reasons: `critical_sync_timeout`, `history_sync_failure`, `syncd_failure`; watchdog log `syncd-critical-bootstrap-timeout`. On the primary, pairing a companion runs `prepareCriticalDataUpload`: history sync, then `shareAllKeys`; with no key and flag **27528** a key is generated first.

---

## 3. IQ layer

### 3.1 Request (found, `C46361ux`)

```xml
<iq to="s.whatsapp.net" xmlns="w:sync:app:state" type="set" id="…">
  <sync data_namespace="3">
    <collection name="regular_low" order="1" version="41" return_snapshot="true">
      <patch>…SyncdPatch bytes…</patch>
    </collection>
  </sync>
  <coex><bot>…enc node…</bot></coex>      <!-- optional -->
</iq>
```

| Attribute | Value |
|-----------|-------|
| `data_namespace` | constant `3` on `<sync>` |
| `order` | `0` for `critical_unblock_low`, `1` otherwise; meaning unknown |
| `version` | locally stored collection version (`C17540jz.A02`); omitted if none |
| `return_snapshot` | `"true"` only for a companion with version null or 0 |
| `<patch>` | only when local mutations are pending |
| `<coex><bot>` | coexistence-v2: the sync keys used are encrypted to a bot (`sync-request-handler/coexv2 *`); on failure the IQ goes without it and keys are shared out of band |

Timeout 32 s; one IQ may carry several collections.

### 3.2 Result (found, `N90`)

```xml
<iq type="result"><sync>
  <collection name="X" type="error"><error code="409" text="…"/> [<patches>…]</collection>
  <collection name="X" version="42"/>                    <!-- outgoing patch acked -->
  <collection name="X" has_more_patches="true">
    <snapshot>ExternalBlobReference bytes</snapshot>    <!-- companion bootstrap -->
    <patches><patch>SyncdPatch bytes</patch>…</patches>
  </collection>
</sync></iq>
```

Missing `<sync>` or an empty `<snapshot>` / `<patch>` body → transient failure. A collection with neither version, patches nor snapshot is kept as a bare name (meaning inferred: nothing new). Snapshot bodies are always an `ExternalBlobReference`, never inline records.

Collection errors (`M4T`): -1 `UNKNOWN` retriable; 400 / 404 / 405 / 406 fatal (`Xmpp*ForCollection`); 409 `CONFLICT` apply attached patches then retry, else retriable (branch condition ambiguous in the decompile); 500 retriable.

Global IQ error (`C53148Nnt.Brt`, `backoff` in seconds):

| Code | Handling |
|------|----------|
| 400, 404, 405, 406 | fatal; legacy codes 64, 65, 66, 67; KMP kinds 55-58 |
| other 4xx | no retry, `client_error:<code>` |
| 5xx | retry after `max(server backoff, client delay)`, `server_error:<code>` |
| other | `global_error:<code>` |

Transient failures older than 7 days (`first_transient_server_failure_timestamp` > 604 800 000 ms) escalate to fatal. Other non-fatal reasons: `network_error`, `sqlite_full`, `unexpected_error`, `mms_local_io`, `mms_upload`.

---

## 4. Protobuf messages

Numbers are recovered from the 2.26.41.6 classes, checked against declaration order and, where present, generated `*_FIELD_NUMBER` constants (`*`).

| Message (class) | Fields (number) |
|-----------------|-----------------|
| `SyncdPatch` (`C49631LsW`, lite `Lp6`) | version **1** `SyncdVersion{uint64=1}`, mutations **2**, externalMutations **3** `ExternalBlobReference`, snapshotMac **4**, patchMac **5**, keyId **6** `KeyId{bytes id=1}`, exitCode **7** `ExitCode{uint64 code=1; string text=2}`, deviceIndex **8**, clientDebugData **9** |
| `SyncdMutation` (`C49601Ls2`) | operation **1** (`SET`=0, `REMOVE`=1), record **2** |
| `SyncdRecord` (`C49610LsB`) | index **1** `SyncdIndex{bytes blob=1}` (index MAC), value **2** `SyncdValue{bytes blob=1}`, keyId **3** |
| `SyncdMutations` (`C49583Lrk`) | mutations **1** (external patch body) |
| `SyncdSnapshot` (`C49617LsI`, lite `C49419Lob`) | version **1**, records **2**, mac **3**, keyId **4** |
| `SyncActionData` (`C49612LsD`) | index **1** (UTF-8 JSON string array), value **2** `SyncActionValue` (`BD4`), padding **3** (always empty), version **4** int32 |
| `ExternalBlobReference` (`C49439Lov`) * | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `AppStateSyncKeyShare` (`C25704B7n`) * / `AppStateSyncKey` (`C25764B9y`) * | keys **1** / keyId **1** (`B89{keyId=1}`), keyData **2** |
| `AppStateSyncKeyData` (`BB9`) * | keyData **1** (32 bytes), fingerprint **2**, timestamp **3** (ms) |
| `AppStateSyncKeyFingerprint` (`BBU`) * | rawId **1**, currentIndex **2**, deviceIndexes **3** |
| `AppStateSyncKeyRequest` (`C25703B7m`) * | keyIds **1** |
| `AppStateFatalExceptionNotification` (`C25763B9x`) * | collectionNames **1**, timestamp **2** |
| `SyncDCollectionFatalRecoveryRequest` | collectionName **1**, timestamp **2** |
| `SyncDSnapshotFatalRecoveryResponse` | collectionSnapshot **1**, isCompressed **2** |
| `SyncdSnapshotRecovery` (`C49432Loo`) * / `SyncdPlainTextRecord` (`C49416LoY`) * | version **1**, collectionName **2**, mutationRecords **3**, collectionLthash **4** / value **1** `SyncActionData`, keyId **2**, mac **3** |
| `KeyExpiration` (`B8Y`) | expiredKeyEpoch **1** |
| `SyncActionValue` (`BD4`) * | timestamp **1** (int64; a SET without it fails), one field per action (10.1) |

Carriers (found, `*`): `ProtocolMessage` (`BD3`) `appStateSyncKeyShare` field **7** / type **6**, `appStateSyncKeyRequest` field **8** / type **7**, `appStateFatalExceptionNotification` field **10** / type **10** (`EnumC26463Bdz`). `PeerDataOperationRequestMessage.syncdCollectionFatalRecoveryRequest` field **7**, request type `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` = **8** (`EnumC26460Bdv`); response `syncdSnapshotFatalRecoveryResponse` field **8** (`C25828BCm`). Companion client-props (`C43107IrI`): `isSyncdPureLidSession` **2**, `isSyncdSnapshotRecoveryEnabled` **3**. Internal FMessage numbers: key share **38**, key request **39**, fatal notification **50**. Share and request travel as peer messages to one `DeviceJid` (`SendPeerMessageJob`), share priority `high`.

---

## 5. Mutation keys and record encryption

### 5.1 Key derivation (found, `MhX`, same in `C52959NkE`)

```
expanded = HKDF-SHA256(ikm = keyData(32), salt = 32 × 0x00, info = "WhatsApp Mutation Keys", L = 160)
```

| Bytes | `MhX` field | Use |
|-------|-------------|-----|
| 0-31 | `A00` | index key, HMAC-SHA256 |
| 32-63 | `A03` | value encryption key, AES-256-CBC |
| 64-95 | `A04` | value MAC key, HMAC-SHA512 |
| 96-127 | `A02` | snapshot MAC key, HMAC-SHA256 |
| 128-159 | `A01` | patch MAC key, HMAC-SHA256 |

HKDF is `AbstractC38961i0.A00`: extract = `HMAC-SHA256(32 zero bytes, ikm)`, expand per RFC 5869. `C17930kd` caches `MhX` objects (5 entries, inferred). The sync key is random (section 7), not derived from Signal keys.

### 5.2 Encrypt one mutation (found, `KmpSyncdEncryptor`, `C52959NkE`)

```
index    = JSON string array, element 0 = action wire name, e.g. ["mute","<jid>"]
plain    = SyncActionData{ index = UTF8(index), value = SyncActionValue, padding = "", version }
iv       = SecureRandom(16)
ct       = AES-256-CBC/PKCS5(valueEncKey, iv, plain)
aad      = op ‖ keyId(6)                 op: 0x01 SET, 0x02 REMOVE
valueMac = HMAC-SHA512(valueMacKey, aad ‖ iv ‖ ct ‖ len8)[0..32)      len8 = 8-byte big-endian aad length (7)
indexMac = HMAC-SHA256(indexKey, UTF8(index))
record   = SyncdRecord{ index.blob = indexMac, value.blob = iv ‖ ct ‖ valueMac, keyId }
```

Padding length is `max(0, −indexLen − valueLen)`, always empty. Minimum blob 48 bytes. SET→0x01 assumes the local operation constant is 0 for SET (inferred; wire SET=0). Value content of a REMOVE is inferred empty (`mqt != null` branch).

### 5.3 Decrypt (found, `KmpSyncdDecryptor`)

| Step | Check | Failure |
|------|-------|---------|
| 1 | split `iv = [0..16)`, `ct = [16..n−32)`, `mac = [n−32..n)` | `Cipher text too short` |
| 2 | resolve key by `record.keyId` | key errors (7.2) |
| 3 | recompute value MAC, compare | `Data MAC mismatch` (`DecryptionFailed`) |
| 4 | AES-CBC decrypt, parse `SyncActionData` | `ActionDataProtobufDeserializationFailed` |
| 5 | index, version, (SET) value and timestamp present | `MISSING_INDEX`, `MISSING_VERSION`, `MISSING_VALUE`, `MISSING_ACTION_TIMESTAMP` |
| 6 | index is a JSON `String[]`, non-empty, no empty element | `keyArray length should have action name` |
| 7 | recompute index MAC over the index string | `Index MAC mismatch` |

Value MAC is checked before decryption, index MAC last. The action is then resolved by element 0 (`Unknown mutation name:`).

---

## 6. LT-Hash, snapshot MAC and patch MAC

**LT-Hash** (found, `AbstractC50511MVx`, `KmpLtHash16`): 128 bytes read as 64 little-endian u16 lanes; empty = 128 zero bytes.

```
expanded(valueMac) = HKDF-SHA256(ikm = valueMac(32), salt = 32 × 0x00, info = "WhatsApp Patch Integrity", L = 128)
lane'[i]           = (lane[i] ± expanded[i]) mod 2^16         + add, − subtract
```

Incoming update (`KmpSyncdCryptoHelper.A01`): for every index in the patch, **subtract** the stored `mutation_mac` of the existing record, then **add** the value MACs of the SETs. `checkLtHashConsistency` (`C17520jx`) rebuilds the hash from all stored `mutation_mac` values and compares it with the stored hash (logs `ltHashFromMutations` / `ltHashFromDb`, last 16 hex chars unless flag **624**); it runs from the daily cron when flag **1104** hours elapsed (default 0 = off) and after a snapshot-MAC mismatch with flag **1783**.

**MACs** (found):

```
version8    = 8-byte big-endian version
snapshotMac = HMAC-SHA256(snapshotMacKey, ltHash(128) ‖ version8 ‖ UTF8(collection))
patchMac    = HMAC-SHA256(patchMacKey,   snapshotMac ‖ valueMac₁ ‖ … ‖ valueMacₙ ‖ version8 ‖ UTF8(collection))
```

`valueMacᵢ` = trailing 32 bytes of each value blob, in patch order. Outgoing: version = stored + 1 for both MACs (`C50707Mbo(old + 1)`). Incoming patch MAC uses the `snapshot_mac` carried in the patch; the recomputed snapshot MAC is compared separately.

| Incoming check | Mismatch |
|----------------|----------|
| patch MAC | fatal `MacMismatchPatch` (32) |
| snapshot MAC in a snapshot | fatal `SnapshotMacMismatchInSnapshot` (52) |
| snapshot MAC in a patch | **not fatal** on the KMP path: `snapshot mac mismatch but do not throw fatal`, non-fatal report code 60, optional consistency check (**1783**); consumer of the returned flag unresolved |
| absent `snapshot_mac` / `patch_mac` | fatal `MissingSnapshotMac` (39) / `MissingPatchSnapshotMac` (40) / `MissingPatchMac` (41) |

---

## 7. Sync keys

### 7.1 Key, generation, active key (found)

| Item | Value |
|------|-------|
| Key id (`CGH`) | 6 bytes: `deviceId` (2, BE) ‖ `epoch` (4, BE); `SyncdKeyId{deviceId=, epoch=}` |
| Key data | 32 random bytes |
| Table `crypto_info` | `device_id, epoch, key_data, timestamp, fingerprint, stale_timestamp` |
| Fingerprint | `rawId`, `currentIndex`, `deviceIndexes` of the account's ADV key-index state at creation |
| Generation (`C12800bm.A05`) | `epoch = max(stored max, in-memory) + 1` (random in [0,65536) first if 0); only if no newly generated share is in flight; with no other device the key is saved at once, otherwise a share (peer 38, `isNewlyGeneratedKey=true`) goes to every companion and the key is persisted after that message was **sent** (`CXB.Bss`) |
| Active key | latest `crypto_info` row, younger than **14488** days (default 30) and fingerprint-valid, else a new key is made on the next write |
| Fingerprint check (`A0B`) | `rawId` equals local ADV raw id; `deviceIndexes ∪ (currentIndex+1 … local currentIndex)` equals the local device-index set; else `one of a peer device is no longer registered` |
| Sentinel (`sentinel`, `KeyExpiration`) | `C25048AqM.A00` builds one per collection (all five) with `expiredKeyEpoch` = highest local epoch |
| `expireKeysWithEpochIfActive` (`A08`) | sets `timestamp = 0` on the latest key when its epoch ≤ the given epoch; caller on receipt of a sentinel not traced (inferred) |
| Stale keys | daily cron marks keys unreferenced by `syncd_mutations`, deletes after **14496** days (default 31) |
| Re-key | a stored record under a different key is replaced via `findMutationWithExpiredKey`; exact REMOVE+SET shape inferred |

### 7.2 Request and missing keys (found, `C12800bm.A07`)

1. Unknown key ids are stored in `missing_keys(device_id, epoch, collection_name)` and requested with key-request peer messages (type 39) to every other registered device, skipping ids already pending (`missing_key_counter`).
2. The responder sends a share for the keys it has (`A0C`, `isNewlyGeneratedKey=false`).
3. Unanswered for **14492** days (default 7, oldest type-39 peer message, daily cron) → fatal **31** (`TimeoutWhileWaitingForMissingKey`).
4. Nobody can supply it: `MissingKeyOnAllClients`; nobody to ask: `RequestingMissingKeyWithNoClients`; none for encryption: `MissingActiveKeyForEncryption`.

Shares are `ProtocolMessage` payloads of end-to-end encrypted peer messages (found). Receiver-side fingerprint validation of an incoming share was not located (unknown).

---

## 8. Outgoing patches and external blobs

**Build** (found, `OutgoingProcessor`, `KmpSyncdEncryptionProcessor`): pending mutations (`pending_mutations`, `is_ready_to_sync=1`) are split per collection; a repeated index in one patch is rejected (`SameIndexForMultipleMutationsInOutgoingPatch`); active key resolved; each mutation encrypted (5.2); new LT-Hash from the stored hash (6); `snapshotMac` / `patchMac` with version stored + 1; `SyncdPatch{version, mutations | externalMutations, snapshotMac, patchMac, keyId, deviceIndex?, clientDebugData?}`; IQ (3.1); result carries the new version. `deviceIndex` (field 8) is governed by default-true flag **14486** (consumer not traced).

**External upload rule** (found, `OutgoingProcessor`): `(mutationCount > P14494 or bytes > P14495 × 1024) and bytes > P5097 × 1024`, defaults 100 / 10 / 0, so any patch above 100 mutations or about 10 KB goes external. The blob is a `SyncdMutations` message; the patch then carries `externalMutations` and no inline `mutations` (both present is rejected: `PatchWithBothInlineAndExternalMutations`). Upload errors: `Upload transient network error`, `Upload local I/O failure`, `Upload failed`.

**Blob transport** (found, `C17650kB`, `C49831Lvs`, `C15530gU`):

| Item | Value |
|------|-------|
| Media type / media-key HKDF info | `md-app-state` (MMS path `mms`) / `WhatsApp App State Keys` |
| Required reference fields | mediaKey, directPath, fileSha256, fileEncSha256 (each missing → `MissingExternalBlobReference*`) |
| Download status | 5 = expired (`ExternalPatchExpired` 3 / `SnapshotExpired` 49, fatal); transient statuses retried; others fatal |
| Content | external patch → `SyncdMutations`; snapshot → `SyncdSnapshot` |

The shared media-key expansion layout is not re-read here (inferred common).

**Debug data** (found): `clientDebugData` = `PatchDebugData` (`C49633LsY`: `collection_name`, `current_lthash`, `new_lthash`, `new_lthash_subtract`, `patch_version`, `number_add/remove/override`, `sender_platform`, `is_sender_primary`, `first_four_bytes_from_a_hash_of_snapshot_mac_key`), written only with flag **6614** (default false); the receiver logs it after a patch-MAC mismatch.

---

## 9. Incoming patches and snapshots

| # | Check (found) | Failure: KMP kind (id) / legacy code |
|---|---------------|--------------------------------------|
| 1 | patch has `version` | `MissingPatchVersion` (7) / 8 |
| 2 | no duplicate version in one response | `DuplicatePatchVersionInCollection` (8) / 9 |
| 3 | not both inline and external mutations | `PatchWithBothInlineAndExternalMutations` (13) / 14 |
| 4 | `version == stored + 1` (`verifyCollectionVersion`) | `ServerDidNotSendAllPatches` (64) |
| 5 | patch `exit_code` present | legacy 36 (code 100), 37 (101), 38 (other); KMP counterpart unresolved |
| 6 | decrypt all mutations (5.3) | `DecryptionFailed` (6), shape kinds |
| 7 | no repeated index among SETs or among REMOVEs | `SameIndexForMultipleMutationsInPatch` (5) |
| 8 | cross-index dependency cycle | `CyclicMutationDependencyInPatch` (37) |
| 9 | recompute LT-Hash, patch MAC, snapshot MAC (6) | `MacMismatchPatch` (32) / non-fatal |
| 10 | apply per action handler (SQLite), store version + hash | logs `Cyclic mutation dependency`, `SQLite error` |

Snapshots: only a bootstrapping companion receives one (`Only companion devices that are undergoing bootstrap should receive and handle snapshots`). Download the blob, decrypt records like patch mutations, reject repeated indices (`SameIndexForMultipleMutationsInSnapshot`, 59), rebuild the hash, compare `snapshot.mac`; then apply `has_more_patches` patches. `applySnapshot keyMap contains null value, retry` re-requests keys. Orphan mutations (parent chat missing) are stored with `are_dependencies_missing=1`, indexed by `chat_jid`, and re-applied later (`SyncdCrossIndexDependencyUtil`).

---

## 10. Sync action types

### 10.1 Catalog (found, `EnumC24865AnN` + `AbstractC24863AnL.A00`)

Number = `SyncActionValue` field of the value; `-` = no matching constant in `BD4` (value field unknown). Index element 0 is the wire name; further elements are action specific and not enumerated.

| Collection | Wire name = field |
|------------|-------------------|
| `critical_block` (4) | `setting_securityNotification` -, `setting_pushName` 7, `setting_locale` 16, `generated_wui` 52 |
| `critical_unblock_low` (2) | `contact` 3, `lid_contact` 61 |
| `regular_high` (19) | `star` 2, `mute` 4, `deleteMessageForMe` 18, `clearChat` 21, `deleteChat` 22, `userStatusMute` 29, `ugc_bot` 43, `status_privacy` 44, `favorites` 56, `waffle_account_link_state` 58, `ctwaPerCustomerDataSharing` 62, `maiba_ai_features_control` 68, `status_post_opt_in_notification_preferences_action` 71, `private_processing_setting` 74, **`nct_salt_sync` 80**, `biz_ai_settings_nudge` 87, `wasa_root_secret` 89, `shared_device_allowlist` 94, `ai_thread_delete` - |
| `regular` (35) | `quick_reply` 8, `label_message` -, `label_edit` 14, `label_jid` 15, `primary_feature` 24, `deviceAgent` 27, `subscription` 28, `agentChatAssignment` 35, `agentChatAssignmentOpenedStatus` 36, `pnForLidChat` 37, `marketingMessage` 38, `marketingMessageBroadcast` 39, `external_web_beta` 40, `setting_relayAllCalls` 41, `call_log` 42, `delete_individual_call_log` 46, `label_reordering` 47, `setting_disableLinkPreviews` 53, `usernameChatStartMode` 59, `notificationActivitySetting` 60, `setting_channels_personalised_recommendation_optout` -, `broadcast_jid` -, `detected_outcomes_status_action` 66, `business_broadcast_list` 69, `music_user_id` 70, `avatar_updated_action` 72, `galaxy_flow_action` -, `newsletter_saved_interests` 75, `business_broadcast_campaign` 81, `business_broadcast_insights_sync` 82, `subscriptions_sync_v2` 84, `label_sublist` 91, `ctwa_message_received` 93, `shareOwnPn` -, `broadcast` - |
| `regular_low` (36) | `pin_v1` 5, `recent_emoji_weights_action` 11, `archive` 17, `sentinel` 19, `markChatAsRead` 20, `setting_unarchiveChats` 23, `android_unsupported_actions` 26, `time_format` 30, `nux` 31, `primary_version` 32, `favoriteSticker` 33, `removeRecentSticker` 34, `bot_welcome_request` 45, `payment_info` 48, `custom_payment_methods` 49, `lock` 50, `setting_chatLock` 51, `device_capabilities` 54, `note_edit` 55, `merchant_payment_partner` 57, `payment_tos` 63, `ai_thread_rename` 76, `interactive_message_action` 77, `settings_sync` 78, `out_contact` 79, `customer_data` 83, `thread_pin` 85, `setting_autoOrganizeBusinessChat` 86, `coexV2Version` 88, `lock_message` 90, `device_capabilities_v2` 92, `contact_manager_metadata` 95, `business_folder_activation` 96, `group_history_toggle` 97, `bb_pro_pending_customer_base_action` 98, `community_nesting_state` 99 |

`BD4` has no constant for field numbers 6, 9, 10, 12, 13, 25, 65, 67, 73. Purpose groups (inferred from names): chat state (`mute`, `pin_v1`, `thread_pin`, `archive`, `markChatAsRead`, `clearChat`, `deleteChat`, `deleteMessageForMe`, `star`, `lock*`); labels (`label_*`); contacts (`contact`, `lid_contact`, `out_contact`, `pnForLidChat`, `shareOwnPn`); account settings (`setting_*`, `time_format`, `status_privacy`); keys and tokens (`sentinel`, `nct_salt_sync`, `wasa_root_secret`, `generated_wui`, `shared_device_allowlist`); business, AI, calls, payments (the rest).

### 10.2 Selected values (found)

| Action | Value |
|--------|-------|
| `nct_salt_sync` (ordinal 73, `regular_high`) | `NctSaltSyncAction{bytes salt=1}` in `SyncActionValue` field **80**; how the primary delivers the NCT salt to companions, origin and use in `WA_TCTOKEN_CSTOKEN.md` (3.2) |
| `contact` (`ContactAction`) | fullName 1, firstName 2, lidJid 3, saveOnPrimaryAddressbook 4, pnJid 5, username 6, birthday 7; created only by the primary, so a bootstrapping companion gets its address book before any `regular*` collection |
| `mute` (`MuteAction`) | muted 1, muteEndTimestamp 2, autoMuted 3, muteEveryoneMentionEndTimestamp 4 |
| `sentinel` | `KeyExpiration{expiredKeyEpoch}` (7.1) |
| `android_unsupported_actions` (26), flag **14490** (default false) | an "Android unsupported mutation" path; semantics unknown |

---

## 11. Fatal errors, retry and recovery

### 11.1 KMP fatal kinds (found, `Lx6.A00`; ids are internal, not wire values)

| Group | Ids and names |
|-------|---------------|
| Transport | 53 `XmppBadRequestForCollection`, 54 `…NotFoundForCollection`, 55 `XmppBadRequestGlobalError`, 56 `…NotFoundGlobalError`, 57 `…BadMethodGlobalError`, 58 `…NotAcceptableGlobalError` |
| Patch / snapshot shape | 4 `MissingOrEmptyIndex`, 5 `SameIndexForMultipleMutationsInPatch`, 7 `MissingPatchVersion`, 8 `DuplicatePatchVersionInCollection`, 13 `PatchWithBothInlineAndExternalMutations`, 37 `CyclicMutationDependencyInPatch`, 38 `MissingSnapshotVersion`, 47 `MissingPatchKeyId`, 50 `MissingSnapshotKeyId`, 59 `SameIndexForMultipleMutationsInSnapshot`, 64 `ServerDidNotSendAllPatches`, 65 `ServerSentEarlierPatch`, 71 `InvalidSnapshotRecords` |
| Mutation / action shape | 10-12, 14-16, 19-24 (`MissingMutationVersion/Value/Index/Operation/Record/KeyId`, `MissingActionIndex/Value/Version/Timestamp`, `InvalidMutationIndex`, `InvalidActionIndex`) |
| Crypto | 6 `DecryptionFailed`, 9 `EncryptionFailed`, 31 `MacMismatchSnapshot`, 32 `MacMismatchPatch`, 39-41 `Missing*Mac`, 51 `SnapshotMacMismatchInPatch`, 52 `SnapshotMacMismatchInSnapshot` |
| Keys | 29 `MissingKeyOnAllClients`, 30 `TimeoutWhileWaitingForMissingKey`, 46 `InvalidKeyShareKeyId`, 48 `InvalidKeyShareKeyData`, 62, 66-69 (`RequestingMissingKeyWithNoClients`, `MissingKeyForMutationInLocalSnapshot`, `MissingActiveKeyAfterRotation`, `MissingActiveKeyForEncryption`, `MissingCurrentEpochForActiveKeyValidation`) |
| Blobs / protobuf | 3 `ExternalPatchExpired`, 49 `SnapshotExpired`, 42-45 and 72 `MissingExternalBlobReference*`, 60 / 61 reference / snapshot parse failure, 17 / 18 / 25-28 (de)serialisation kinds, 34-36 `TerminalPatch*` |
| Local | 33 `DbStoreNotReady`, 63 `DbStoreNotReadyLowDiskSpace`, 70 `SameIndexForMultipleMutationsInOutgoingPatch` |

### 11.2 Legacy numeric codes (found, `C49784Lv2.errorCode`, feed WAM `md_fatal_error`; separate numbering)

8 / 9 / 14 (`N90`: no version / duplicate version / inline + external), 18 / 69 (patch / snapshot parse failure), 36 / 37 / 38 (`exit_code` 100 / 101 / other), 64-67 (global IQ errors 400 / 404 / 405 / 406), 71 (key resolution failed after the missing-key request), 31 (wait-for-key timeout), 60 (non-fatal snapshot-MAC mismatch in a patch, `A0F(60, collection, false)`). The mapping to the KMP kinds is unresolved.

### 11.3 Reaction to a fatal failure (found, `SyncResponseHandler.A08`, `C12440bB.A0S/A0Q`)

| Role | Action |
|------|--------|
| Any | log `app-state-sync-handle-fatal-exception`, WAM `md_fatal_error`, clear running sync |
| Flag **25799** | companion: `companion_syncd_dirty=true`; primary: `C17630k8.A01(1)` (dirty reason 1, inferred) |
| Primary | `A0Q(1)` delete all syncd data. Dirty machine (`C17630k8`, chain from `A0Q` inferred): `syncd_dirty` counter up to 4, `syncd_dirty_reason`, `<iq xmlns="w:sync:app:state" type="set"><delete_all_data/></iq>` (type attribute inferred), `logoutAllCompanionDevices` |
| Companion | `companion_syncd_dirty=true`, peer message `AppStateFatalExceptionNotification` (FMessage 50) to the primary (device 0), 5 s wait, logout with `syncd_failure` or `syncd_error_during_bootstrap` |

Delete-all retry window **14493** minutes (default 360). The primary cleans up when a companion was deregistered and none remains (`shouldCleanUpSyncd`).

### 11.4 Snapshot recovery (found, `KmpSyncdFatalErrorRecovery`)

Gated by client-prop `isSyncdSnapshotRecoveryEnabled`. The companion sends peer data operation `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` (8) with `SyncDCollectionFatalRecoveryRequest{collectionName}`. The responder builds a `SyncdSnapshotRecovery` from its **plaintext** stored mutations (`syncd_mutations`, `collection_versions.version / lt_hash`), gzips it and returns `SyncDSnapshotFatalRecoveryResponse`. Refusals: `Invalid collection name` (request for `critical_block`), `Collection version/ltHash invalid`, `Snapshot keyId invalid`, `Mutation count (…) more than the limit`, `Mutation snapshot data size (…) more than the limit`, `Error encoding mutation data`, `Compression failed` (cap props not resolved). The plaintext travels inside an end-to-end encrypted peer message. Companion-side apply was not traced (unknown).

---

## 12. Local state and feature flags

| Store | Content (found) |
|-------|-----------------|
| `syncd_mutations` | `mutation_index` (unique), `mutation_value`, `mutation_version`, `collection_name`, `are_dependencies_missing`, `mutation_mac`, `device_id`, `epoch`, `chat_jid`, `mutation_name` |
| `collection_versions` / `pending_mutations` / `missing_keys` / `crypto_info` | `collection_name, version, lt_hash` / outgoing queue (`is_ready_to_sync`) / key requests / sync keys |
| Prefs | `syncd_bootstrap_state`, `companion_syncd_critical_bootstrap_state`, `syncd_dirty`, `syncd_dirty_reason`, `companion_syncd_dirty`, `syncd_last_companion_dereg_time`, `syncd_last_lthash_consistency_check_time`, `first_transient_server_failure_timestamp` |

Daily cron (`C46413KPv`) reports counters `mutation_counter`, `invalid_action_counter`, `upload_conflict_counter`, `unsupported_action_counter`, `cross_index_conflict_counter`, `unset_action_mutation_counter`, `key_rotation_remove_counter`, `missing_key_counter`.

| Flag ID | Type / default | Controls |
|---------|----------------|----------|
| **15909**, **20682**, **18234** | bool / false | `XplatSyncdEncryptionManager` vs default (`AbstractC17550k0`); KMP incoming (`RunnableC53542Nwj`); KMP outgoing (`C12440bB`). Compiled defaults only, live value unknown. Earlier-build name of 15909: `KMP_SYNCD_ENGINE_CRYPTO_ENABLED` (inferred ID reuse) |
| **14488** / **14496** / **14492** | int / 30 / 31 / 7 | active-key age, stale-key retention, key-wait timeout (days) |
| **14493** | int / 360 | delete-all / dereg window (minutes) |
| **14494**, **14495**, **5097** | int / 100, 10, 0 | external-patch thresholds |
| **14497** | int / 1000 | DB mutation load limit (inferred) |
| **1104** / **1783** | int 0 / bool false | consistency-check interval (h) / check after snapshot-MAC mismatch |
| **6614** | bool / false | `clientDebugData` in patches |
| **25799** | bool / false | dirty-state handling on fatal failure |
| **27528** | bool / false | generate a key when the primary has none |
| **14486** | bool / true | `deviceIndex` in patches (consumer not traced) |
| **14489**, **14490**, **1221**, **624** | int 90 / bool false / bool false / bool | `min()` cap in `C15310g7` (unresolved) / unsupported-mutation path / mutation stats / full hashes in logs |

---

## 13. Error cases

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Data MAC mismatch` | wrong key, tampered blob, wrong op byte or keyId in the AAD | key named by `record.keyId`; AAD = `op ‖ keyId`, op 1 SET / 2 REMOVE |
| `Index MAC mismatch` | index string differs byte-wise (JSON spacing) | MAC the exact UTF-8 string of `SyncActionData.index` |
| fatal 64 `ServerDidNotSendAllPatches` | patch version ≠ stored + 1 | resync from the stored version; request a snapshot if state is lost |
| patch MAC mismatch (32) | LT-Hash drift, version8 width, snapshot MAC from the wrong source | use the patch's `snapshot_mac` first; version as 8-byte big-endian |
| `PatchWithBothInlineAndExternalMutations` | both fields set | send one |
| `MissingActionTimestamp` | `SyncActionValue.timestamp` absent on SET | set field 1 |
| key missing | share not received | type-39 request; fatal 31 after 7 days |
| `one of a peer device is no longer registered` | device list changed since key creation | key not usable as active key; generate a new one |
| IQ error 400 / 404 / 405 / 406 | bad request shape, unknown collection | fatal; fix the request |
| `ExternalPatchExpired` / `SnapshotExpired` | blob status 5 | snapshot recovery or re-link |
| companion logout `syncd_failure` | unrecoverable fatal failure | re-pair, or snapshot recovery if enabled |

---

## 14. Key distinctions

| Do not confuse | With |
|----------------|------|
| Sync key (32 random bytes per device+epoch) | mutation keys (HKDF output, five slices) |
| Index MAC (HMAC-SHA256 over the index string) | value MAC (HMAC-SHA512 truncated to 32 over AAD + iv + ct + len) |
| Value MAC (per mutation) | snapshot MAC (LT-Hash + version + collection) and patch MAC (snapshot MAC + all value MACs) |
| `<snapshot>` node (an `ExternalBlobReference`) | `SyncdSnapshot` proto (the blob content); likewise `externalMutations` vs `SyncdMutations` |
| `critical_block` on Android (account settings) | a block-list collection (not found) |
| `ProtocolMessage` types 6 / 7 / 10 | field numbers 7 / 8 / 10 |
| Peer data request field 7 | peer data response field 8 |
| KMP kind ids (`Lx6`) | legacy `errorCode` ints |
| `sentinel` (key-expiry marker in all five collections) | `primary_version`, `android_unsupported_actions` |
| WhatsApp Web action / collection tables | the Android table here (96 actions, different assignment) |

---

## 15. Baileys (`baron-baileys-v2` 1.5.17)

Only facts read in `src/Utils/chat-utils.js`, `src/Socket/chats.js`, `src/Utils/process-message.js`. Nothing was tested against a server; no failure is claimed.

| Topic | Baileys | Android |
|-------|---------|---------|
| Key expansion, LT-Hash | native bridge `expandAppStateKeys`, `LTHashAntiTampering` (128 bytes); same five slice names | 5.1, 6 |
| Value MAC | `HMAC-SHA512(op ‖ keyId ‖ data ‖ 8 bytes, last = len)[0..32)`, op 1 / 2 | identical |
| Snapshot / patch MAC | same inputs and order; `ver8` writes the low 32 bits only | full 64-bit big-endian |
| Index, padding | `JSON.stringify(index)`, empty padding | same |
| External blob | `downloadContentFromMessage(blob, 'md-app-state')` | same media type |
| Collections | `critical_block, critical_unblock_low, regular_high, regular_low, regular` | same names |
| Request node | `<sync>` without attributes; `<collection name version return_snapshot>`, `return_snapshot` always `'true'`/`'false'` | `data_namespace="3"`, `order`, `return_snapshot` only when true |
| Patch send | `version = state.version − 1`, `return_snapshot='false'` | stored version |
| Version continuity | not checked (`newState.version = patchVersion`); a missing patch version becomes collection version + 1 | must equal stored + 1 |
| Snapshot MAC in a patch | recomputed, throws `failed to verify LTHash` | non-fatal on KMP path |
| Key share | stores only `keyData` per base64 key id; `myAppStateKeyId` = last key in the message | keeps fingerprint and timestamp, verifies fingerprint, picks latest valid key |
| Fatal notification | logged, emitted as `app-state.sync-error` | companion sends, primary acts |
| Retry | `MAX_SYNC_ATTEMPTS = 2`, forced-snapshot retry, missing key parks the collection | section 11 |
| NCT salt | `nctSaltSyncAction.salt` stored as `nct-salt` | 10.2 |

Not present in the Baileys source: `data_namespace`, `order`, `exit_code` handling, snapshot recovery. Effect on the server is unknown.

---

## 16. Complete flows

### 16.1 Primary writes a change (example `mute`)

```
[User]  → handler builds mutation  ["mute","<chatJid>"]  MuteAction  collection regular_high
     │
     ▼
[SyncManager C12440bB]  pending_mutations ; active key (≤ 30 d, fingerprint ok) else generate, share (peer 38)
     │
     ▼
[Encrypt]  iv ; AES-CBC ; aad = 01 ‖ keyId ; valueMac ; indexMac
     │     ltHash' = ltHash − oldValueMac + newValueMac ; ver = stored + 1 ; snapshotMac ; patchMac
     │     SyncdPatch inline, or externalMutations above the thresholds (md-app-state upload)
     ▼
iq set w:sync:app:state  <sync data_namespace=3><collection name order version><patch/></collection></sync>
     │
     ▼
[WA Server]  (not observed) orders patch, assigns version
     │
     ▼
Result <collection name version="N+1"/>  →  store version, hash, mutation_mac
     │
     ▼
[Companions]  sync (16.2)
```

### 16.2 Companion pulls

```
[Companion]  iq set  <collection name version=V [return_snapshot=true if V=0]/>
     │
     ▼
Result <collection has_more_patches?> [<snapshot ExternalBlobReference/>] <patches><patch/>…</patches>
     │
     ├─ snapshot ─► download md-app-state ─► SyncdSnapshot ─► decrypt ─► hash ─► snapshot MAC
     └─ each patch (V+1 …) ─► version check ─► external blob? download SyncdMutations
            │  key unknown ─► missing_keys + peer 39 ─► [Primary] peer 38 share
            │  decrypt (valueMac → AES → SyncActionData → indexMac) ; ltHash − old + new
            │  patchMac ; snapshotMac ; action handler apply (are_dependencies_missing for orphans)
            ▼
         store version, hash ; has_more_patches → repeat
```

### 16.3 Fatal failure

```
[Companion]  patch MAC mismatch / key timeout / version gap
     ├─ recovery enabled ─► peer data op 8 {collectionName} ─► [Primary] SyncdSnapshotRecovery (gzip)
     └─ else companion_syncd_dirty ; peer AppStateFatalExceptionNotification ; 5 s ; logout syncd_failure
               ▼
         [Primary]  delete syncd data ; iq <delete_all_data/> ; logout companions ; re-pair
```

---

## 17. Unknowns

| Item | Status |
|------|--------|
| Active engine (legacy or KMP) per account | server flags |
| Meaning of the `order` attribute | unknown |
| Receiver-side fingerprint check of an incoming key share | not located |
| Apply side of a received `sentinel` (`expireKeysWithEpochIfActive`) | not traced |
| KMP kind ↔ legacy code mapping; `ServerSentEarlierPatch` trigger; `exit_code` 100 / 101 meaning | unresolved |
| Value field of the 9 actions marked `-` | unknown |
| Snapshot-recovery apply side, cap props | not traced |
| Server ordering, retention, merge rules | server side |
| Traffic | nothing captured |
