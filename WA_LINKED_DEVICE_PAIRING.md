# WhatsApp Linked-Device Pairing — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-17
**Scope:** primary-device side of companion pairing, QR flow, phone-number / pair-code flow, `pair-device` and `pair-success` stanzas, key material, ADV signed device identity and key-index list, device list and limits, unlink, errors, Baileys comparison

---

## 1. What it is (technically)

A linked device (companion) is a second endpoint of the same account. The primary phone authorises it by producing an ADV (account device verification) signed identity over the companion's identity key. All statements are static analysis of the decompiled APK; nothing was captured on the wire. Tier: **found** = read in code, **inferred** = deduced from code, **unknown** = not resolved.

Obfuscated names are per-build and were re-resolved from stable strings in 2.26.41.6.

| Entity | 2.26.41.6 name | Role |
|--------|----------------|------|
| QR/pair orchestrator | `C45850K0w` (log prefix `CompanionDeviceQrHandler`) | parses QR, builds ADV protos, sends `pair-device` |
| `pair-device` IQ builder | `RunnableC46606KYf` | builds the IQ |
| `pair-device` request/response helper | `KRI` (`devicePairRequest/*`) | send, retry, parse `device` / `companion-props` / retry hints |
| Error router | `C44661Jem` | maps server error code to UI callback |
| QR string parser | `C45741Jxy` → `C45423Jrn` | QR payload to pairing data |
| Parsed pairing data | `C44423JaU` | ref, companion keys, adv secret, platform |
| ADV util | `C24270w6` (`CompanionDeviceAdvUtil`) | rawId, key index, timestamp, key-index-list build and sign |
| Key-index-list updater | `C24250w4` (`DeviceKeyIndexListUpdateHandler`) | pushes signed list to server |
| ADV verifier | `C24230w2` (`DeviceADVInfoHandler`) | verifies identities and lists seen on the wire |
| Device-list notification handler | anonymous class in `C1S0` (`DeviceUpdateNotificationHandler`), `RunnableC29334CoL` | `devices` notification |
| Link-code notification handler | `C10J` (`LinkCodeCompanionRegNotificationHandler`) | notification id 252 |
| Link-code manager (primary) | `KZ3` (input code, `primary_hello`), `KYB` (`companion_finish`), `C10L`, `C77` | pair-code flow |
| Link-code crypto util | `K1T` (`CompanionRegWithLinkCodeUtil`) | HKDF, PBKDF2, base32 |
| Device manager | `C0XQ` (`companion-device-manager`) | list, logout |
| Remove helper | `C28905Ch6` (`DeviceRemoveRequestProtocolHelper`) | `remove-companion-device` |
| Signal curve wrapper | `C38851hm` | `org.whispersystems.curve25519` provider "best" |
| ADV proto classes | `C25815BBy`, `C25792BBb`, `C25785BAt`, `C25786BAu`, `BCB` | see section 5 |
| DeviceProps | `C43105IrG` (enum `EnumC25120ArW`) | `companion-props` in the `pair-device` result |
| Client props | `C43107IrI` | `client-props` child |
| Account/encryption type | `EnumC32116E1o` | `E2EE` 0, `HOSTED` 1, `NON_E2EE` 2 |

Three entry modes exist in the primary UI (`EnumC26221BZl`): `QR_CODE`, `PHONE_NUMBER_AND_CODE`, `EXTERNAL_DEEPLINK_QR_CODE` (found).

The same APK also contains the companion-role registration code (state machine `C0YS`, `companion/registration/*` logs). It is outside the scope; only the parts needed to explain what the primary receives are described (section 9.6).

---

## 2. Pairing paths at a glance

| Path | Trigger on primary | Primary sends | Secret that ties primary and companion |
|------|--------------------|---------------|----------------------------------------|
| QR | scan of `https://wa.me/settings/linked_devices#<payload>` (or `whatsapp://settings/linked_devices#<payload>`) | `iq xmlns=md` `pair-device` | `adv secret` from QR field 4 |
| Phone number + code | `notification` `link_code_companion_reg` stage `companion_hello`, user types 8-char code | `primary_hello`, later (after `companion_finish`) the same `pair-device` | `adv secret` derived from two X25519 results plus a random (section 4.4) |

Both paths converge on one `C44423JaU` object and one `pair-device` IQ (found: `KYB` builds `C44423JaU` from the `companion_finish` bundle with the same constructor `C45850K0w.A01` uses for QR).

---

## 3. QR flow (primary side)

### 3.1 QR payload

`C45741Jxy.A01` strips the prefix `https://wa.me/settings/linked_devices#` or `whatsapp://settings/linked_devices#` and URL-decodes the rest. `A02` splits on `,` (found):

| Idx | Content | Encoding | Use |
|-----|---------|----------|-----|
| 0 | `ref` | string | pairing reference; a ref starting `CAPI_` is rejected (`invalid ref`) |
| 1 | companion public key | base64 | sent as `pub-key`, salt for the nonce key (3.4). Name inferred: Noise static key (`companion_server_auth_key_pub` in the code path) |
| 2 | companion identity key | base64, 32 bytes, parser prepends `0x05` (Curve25519 type) | signed over by the account signature |
| 3 | `adv secret` | base64 | HMAC key for the ADV wrapper |
| 4 | platform code (optional) | one char | maps to a platform type; `j` = hosted device |

- Fewer than 3 parts: `qrData/processQR/error/invalid_code parts`. Missing identity key or adv secret (old 3-field QR): `invalid qr code, missing companion identity key or adv secret` → local code **-9**.
- Platform char table (`EnumC26221BZl`-independent, `EnumC26332BbY`): `0` UNKNOWN, `1` CHROME, `2` EDGE, `3` FIREFOX, `4` IE, `5` OPERA, `6` SAFARI, `7` DESKTOP, `8` UWP, `9` OTHER_WEB, `a` IOS_TABLET, `b` IOS_PHONE, `c` IOS_CATALYST, `d` ANDROID_TABLET, `e` ANDROID_PHONE, `f` ANDROID_AMBIGUOUS, `g` WEAR_OS, `i` AR_DEVICE, `j` HOSTED_DEVICE, `k` VR, `l` SMARTGLASSES, `n` WAIL_WAI, `o` WAIL_ALEXA (found). It is only used for the hosted check and logging (3.2).

### 3.2 Local checks before anything is sent

| Check | Code | Local code |
|-------|------|------------|
| QR has identity key and adv secret | `C45850K0w.A01` | -9 |
| hosted flag consistent: `(accountType == HOSTED) == (platform int == 20)` | `A01` | -13 |
| another pairing already running (`kri.A0N`, or companion-device manager busy) | `A04` | -17 |
| local ADV timestamp valid (`C24270w6.A00() != -1`) | `A04` | -8 |
| hosted companion | `A04`: `Hosted pairing is not supported` | -10 |
| defense-mode friction needed | `RunnableC46606KYf`: `defense mode friction triggered` | -20 (retry with challenges) |

Hosted pairing is blocked client-side in this build (`pairing for hosted device is not supported on the consumer build`).

### 3.3 Before the IQ: syncd cleanup and key index

1. If syncd state is dirty (`sync-manager/shouldCleanUpSyncdOnPairing`), the app first cleans syncd, then continues (`handleSyncdDirty clean syncD before companion dereg`) (found).
2. `incrementCurrentKeyIndex` (in `RunnableC46617KYr`):
   - no stored rawId or index: new random rawId, index 1;
   - no companions linked: `rawId + 1`, index stays 1;
   - companions exist: `currentIndex + 1`; on overflow rawId + 1 and all devices are logged out (`C24270w6.A03`).
3. `ts = C24270w6.A00()` (section 5.4).

### 3.4 What is built

In `C45850K0w.A00`, with `E` = companion identity key (32 B, raw), `P` = primary identity key pair (Curve25519), `S` = adv secret:

| Step | Operation | Tier |
|------|-----------|------|
| 1 | `ADVDeviceIdentity` `{rawId, timestamp=ts, keyIndex=currentIndex, accountType, deviceType}` | found |
| 2 | account signature = `Curve25519 sign(P.priv, prefix ‖ details ‖ E)`; prefix `06 00` (hosted `06 05`) | found |
| 3 | `ADVSignedDeviceIdentity` `{details, accountSignatureKey = P.pub, accountSignature}` (`deviceSignature` left empty: the companion adds it) | found |
| 4 | `ADVSignedDeviceIdentityHMAC` `{details = serialized step 3, hmac = HMAC-SHA256(key = S, data = step 3 bytes), accountType}`; for hosted the data is `06 05 ‖ bytes` | found |
| 5 | `BCB` (ADVKeyIndexList) from `C24270w6.A01`, signed by `A02` → `ADVSignedKeyIndexList` (5.3) | found |
| 6 | nonce key `K = HKDF-SHA256(salt = pub-key, IKM = S, info = "Canonical Ent Companion Nonce Encrypt", 32 B)`, wrapped as `pem` child | found (derivation); purpose inferred |
| 7 | optional `encryption-metadata` (`C38898Gvq`): `encrypted_key`, `nonce`, `encrypted_data`, `auth_tag`, from `AuthProofHelper` (account password encryption, `rsa2048` label) | found (structure); what it proves is unknown |
| 8 | optional `client-props` (`C43107IrI`, section 3.6) | found |

Detail on step 6: the `pem` node is labelled `version=1`, `algorithm=rsa2048`, `ttl ts_s = 5 days`, `key_id=1`, but its child carries `key.getEncoded()` of the 32-byte HKDF output (`SecretKeySpec` algorithm `AES-GCM`). Label and content do not match; why is unknown. Server use is inferred (server encrypts a per-device nonce to the companion; cf. `companion_meta_nonce` column).

### 3.5 The `pair-device` IQ (primary → server)

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <pair-device>
    <ref>…</ref>                                    <!-- QR field 0 -->
    <pub-key>…</pub-key>                            <!-- QR field 1 -->
    <device-identity>ADVSignedDeviceIdentityHMAC</device-identity>
    <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
    <client-props>…</client-props>                  <!-- optional -->
    <pem version="1" algorithm="rsa2048"><pem>…</pem><ttl ts_s="432000"/><key_id>1</key_id></pem>
    <encryption-metadata version="1" algorithm="rsa2048">…</encryption-metadata>   <!-- optional -->
    <companion_qr_origin_source>1|2</companion_qr_origin_source>
    <challenges><supported><friction variant="1"/><passkey-create/></supported>
                <completed>…</completed></challenges>                              <!-- optional -->
  </pair-device>
</iq>
```

Found: all child names, `ts` attribute value (the key-index-list timestamp), timeout **32000 ms** (`c10140Tq.A0Q(…, 219, 32000L)`). `companion_qr_origin_source` is `1` for entry value 3 and `2` for entry value 5 (meaning of the entry ints unknown). Exact child order and the `companion_qr_origin_source` branch are partly mangled by the decompiler; treat order as unverified.

### 3.6 `client-props` (`C43107IrI`)

| Field | Number | Type | Set when |
|-------|--------|------|----------|
| `isChatDbLidMigrated` | **1** | bool | chat DB LID migration done |
| `isSyncdPureLidSession` | **2** | bool | syncd pure-LID flag present |
| `isSyncdSnapshotRecoveryEnabled` | **3** | bool | recovery flag |
| `isHsThumbnailSyncEnabled` | **4** | bool | history-sync thumbnail flag |
| `subscriptionSyncPayload` | **5** | bytes | built when md sync enabled (`buildSubscriptionSyncPayload`) |
| `isBotJidDbMigrated` | **6** | bool | bot JID DB migrated |

### 3.7 Result handling (`KRI.CFS`)

Success result children (found):

| Child | Use |
|-------|-----|
| `device` attr `jid` | the new companion `DeviceJid`; device id **99** is mapped to the hosted platform entry |
| `companion-props` | `DeviceProps` proto (`C43105IrG`): `os` **1** (string), `version` **2** (message), `platformType` **3** (enum), `requireFullSync` **4** (bool), `historySyncConfig` **5** (message) |
| `retry-ts` attr `ts` | server asks for a newer timestamp; app retries (`RunnableC46585KXj`) |
| `retry-after-challenges` | children `friction` (attr `variant`, must be `1`, optional `location` "lat,lon") or `passkey-create` (attr `created`) |
| `retry-with-method` | children `qr-code` or `shortcake-with-passkeys`; if the second is present the 32-byte handoff key (HKDF of adv secret, info `shortcake-passkey-handoff-v1`) is stashed (`PairingHandoffKeyHolder`), gated by an abprop |

On success the app stores the `CJY` device record (random 24-byte base64 string, `adv_key_index` = current index, `requireFullSync`), saves the key-index-list timestamp as `adv_timestamp_sec` (`C24270w6.A05`), and starts history sync state (`C8N`).

Delivery failure (`Bog`): up to **3** retries, delay `3000 * 3^(n-1)` ms (3 s, 9 s, 27 s) if the retry flag is on (found); then error callback.

---

## 4. Phone-number / pair-code flow (primary side)

### 4.1 Steps

| # | Direction | Stanza / action | Class |
|---|-----------|-----------------|-------|
| 1 | companion → server → primary | `notification` `link_code_companion_reg`, `stage=companion_hello` | `C10J` (id 252) |
| 2 | primary | stores hello, shows push notification → `CompanionHelloConfirmationActivity` / enter-code screen | `C10J`, `C77`, `JYJ` |
| 3 | user | types the 8-char code | `LinkedDevicesEnterCodeActivity` |
| 4 | primary → server | `iq xmlns=md type=set` `link_code_companion_reg stage=primary_hello` | `KZ3` (timeout 120000 ms) |
| 5 | server → primary | `notification` `stage=companion_finish` | `C10J` → `KYB` case 0 |
| 6 | primary → server | `pair-device` IQ (section 3.5) | `C45850K0w` |
| 7 | other stages | `refresh_code` (primary asks code refresh, attr `force_manual_refresh`) | `C10J` |

### 4.2 `companion_hello` notification (found)

| Child | Use |
|-------|-----|
| `link_code_pairing_wrapped_companion_ephemeral_pub` | companion ephemeral X25519 key, wrapped with the code (4.3) |
| `companion_server_auth_key_pub` | later becomes the `pub-key` in `pair-device` |
| `link_code_pairing_ref` | session ref (string) |
| `companion_platform_id` | platform id string |
| `companion_platform_display` | display name |
| attr `should_show_push_notification` | `true` → push notification |

State kept (`C77`/`CE4`, SharedPrefs JSON `companion_reg_with_link_code_companion_hello_info_json`): ref, platform id, wrapped key, server auth key, expiry `now + min(360000, flag 3816 * 1000)` ms. Expired or absent hello → "companion hello is null or expired" (UI state 2). A newer hello with a different ref cancels the previous ref (`KRJ.A00(oldRef, "true")`).

### 4.3 Code and wrap crypto (found)

| Item | Value |
|------|-------|
| Code | 5 random bytes → 8 chars, 5 bits each, alphabet `123456789ABCDEFGHJKLMNPQRSTVWXYZ` (32 symbols, no `0 I O U`) (`K1T.A00`, generated by the companion) |
| Code → key | PBKDF2-HMAC-SHA256, **131072** iterations, 256-bit, password = code chars, salt = first 32 bytes of the wrapped blob (`K1T.A02`) |
| Wrapped ephemeral key | `[salt 32 ‖ IV 16 ‖ AES-256-CTR ciphertext]`, plaintext = 32-byte X25519 public key; length must be ≥ 48 |
| Primary reply | the primary makes its own ephemeral key pair, wraps its public key the same way (fresh 32 B salt, 16 B IV, same code) |

### 4.4 `primary_hello` and `companion_finish`

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md">
  <link_code_companion_reg stage="primary_hello">
    <link_code_pairing_wrapped_primary_ephemeral_pub>salt32‖iv16‖ct</…>
    <primary_identity_pub>32 B primary identity key</primary_identity_pub>
    <link_code_pairing_ref>ref</link_code_pairing_ref>
  </link_code_companion_reg>
</iq>
```

`companion_finish` notification children: `link_code_pairing_wrapped_key_bundle`, `companion_identity_public`, `link_code_pairing_ref`. Primary processing in `KYB` case 0:

1. `eph = X25519(primary eph priv, companion eph pub)` (stored at `primary_hello` time).
2. Bundle layout `[salt 32 ‖ nonce 12 ‖ AES-256-GCM ciphertext+tag]`, minimum 44 bytes.
3. Key = HKDF-SHA256(salt = bundle salt, IKM = `eph`, info = `link_code_pairing_key_bundle_encryption_key`, 32 B).
4. Plaintext = `companion identity pub (32) ‖ primary identity pub (32) ‖ random (32)`.
5. Checks: primary identity must equal the own identity key; companion identity must equal `companion_identity_public` from the notification; otherwise the ref is dropped and the UI gets an error state.
6. `adv secret = HKDF-SHA256(salt = 32 zero bytes, IKM = eph ‖ X25519(primary identity priv, companion identity pub) ‖ random, info = "adv_secret", 32 B)` (`K1T.A03`).
7. Handoff key = HKDF(adv secret, info `shortcake-passkey-handoff-v1`) (also stored in `C44423JaU`).
8. `C44423JaU` is built with `pub-key` = `companion_server_auth_key_pub`, companion identity, adv secret → same `pair-device` IQ as QR.

The outer ephemeral ECDH exists (it is the HKDF IKM of step 3). An earlier-build note said "no ECDH in this stage"; that is wrong for this build.

Error markers on the primary side: `getCompanionPairingDataOnCompanionFinish ref not exists`, `decryption fail`, `primary identity doesn't match`, `companion identity doesn't match`, `invalid linkCodePairingWrappedKeyBundleDecrypted` (found).

---

## 5. ADV signed device identity

### 5.1 Proto fields (found, from the lite-proto layout strings)

| Message | Class | Field | Number | Type |
|---------|-------|-------|--------|------|
| `ADVDeviceIdentity` | `C25815BBy` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `keyIndex` | **3** | uint32 |
| | | `accountType` | **4** | enum (`EnumC32116E1o`) |
| | | `deviceType` | **5** | enum (`EnumC32116E1o`) |
| `ADVSignedDeviceIdentity` | `C25792BBb` | `details` | **1** | bytes |
| | | `accountSignatureKey` | **2** | bytes |
| | | `accountSignature` | **3** | bytes |
| | | `deviceSignature` | **4** | bytes (set by companion) |
| `ADVSignedDeviceIdentityHMAC` | `C25785BAt` | `details` | **1** | bytes |
| | | `hmac` | **2** | bytes |
| | | `accountType` | **3** | enum |
| `ADVKeyIndexList` | `BCB` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `currentIndex` | **3** | uint32 |
| | | `validIndexes` | **4** | packed uint32 |
| | | `accountType` | **5** | enum |
| `ADVSignedKeyIndexList` | `C25786BAu` | `details` | **1** | bytes |
| | | `accountSignature` | **2** | bytes |
| | | `accountSignatureKey` | **3** | bytes (only hosted) |

Field numbers and wire types are read from the generated message info; names with the canonical ADV messages match. Enum names: `EnumC32116E1o` values E2EE 0, HOSTED 1, NON_E2EE 2.

### 5.2 Signature prefixes and algorithms

| Prefix | Constant | Signed / MACed data | Signer | Tier |
|--------|----------|---------------------|--------|------|
| `06 00` | `AbstractC051108f.A0F` | account signature: `‖ details ‖ companion identity pub` | primary identity key | found |
| `06 05` | `A0G` | hosted variant of account signature; also prepended to the HMAC data for hosted | primary identity key / adv secret | found |
| `06 01` | `A0H` | device signature: `‖ details ‖ companion identity pub ‖ accountSignatureKey` | companion identity key | found (verify side) |
| `06 06` | `A0I` | hosted variant of device signature | companion identity key | found (verify side) |
| `06 02` | `A0J` | `ADVSignedKeyIndexList`: `‖ details` | primary identity key | found |
| `06 07` | `A0K` | non-E2EE ("hybrid") attestation (`AeaUtils`), not a key-index-list prefix | primary identity key | found |

- Signature primitive: `C38851hm.A00("best")` loads `org.whispersystems.curve25519.OpportunisticCurve25519Provider`; `A03` = `calculateSignature(random 64 B, priv, msg)`, `A01` = `verifySignature` (64-byte signature), `A02` = `calculateAgreement`. Keys are 32 bytes with type byte `5`. So Curve25519 signatures of the Signal curve25519 library (XEdDSA-style, inferred from library, not from the algorithm name). Provider choice native vs Java is decided at runtime (unknown which is used on a given device).
- HMAC: `HmacSHA256` via `javax.crypto.Mac` (`AbstractC38971i1.A00`).

### 5.3 Key-index list

`C24270w6.A01` builds `ADVKeyIndexList`; `validIndexes` is a set made of (found): one entry for the primary slot (value 0 when not in companion mode; branch condition inferred), the `adv_key_index` of every stored companion (`CJY.A07`), and `currentIndex`. `A02` signs `06 02 ‖ details`.

`C24250w4.A00` pushes it as:

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
</iq>
```

Timeout 32000 ms. Gate `A02`: flag **477** non-zero, companions present (or companion mode), not in companion mode. On failure `adv_key_index_list_update_retry_count` is incremented; above **5** the app logs `adv-key-index-list-update … fails for more than 5 times` and logs out all companions (`C24270w6.A03`). Success clears the counters (`A05`).

### 5.4 Timestamp rule (`C24270w6.A00`)

`last` = SharedPrefs `adv_timestamp_sec`; `now` = NTP-corrected clock, `srv` = server time. `ts = max(srv if |srv - now| <= 86400 else now, last + 1)`. If `last + 1 > now + 86400` the value is invalid (-1, logged `getTimestampSec invalid ts`), which blocks pairing with local code -8. Monotonic per account (found).

### 5.5 Verification on the wire (`C24230w2`)

For any device identity the primary sees (own and contacts' companions) it checks, in order (found):

1. primary identity key known (stored, or `accountSignatureKey` from the list), else `no primary key`;
2. companion identity key parses (`0x05`+32 B), else `invalid companion public key`;
3. account signature over `prefix ‖ details ‖ companion identity`, else `fail to verify account signature`;
4. device signature over `06 01 ‖ details ‖ companion identity ‖ accountSignatureKey` (hosted `06 06`), else the device is rejected;
5. key-index-list: signature over `06 02 ‖ details` with the primary key; `adv timestamp` of the list must be consistent (`advTimestampMismatch`, `advListTimestampInvalid`); a mismatching incoming key index resets local state (`incoming key-index not matching local state, resetting`); a larger index for the same device already present drops the older entry (`filterDeviceWithKeyIndexList`).

---

## 6. Device list, record and limits

### 6.1 `devices` notification (primary receives)

`notification` with child `add` or `remove` (anything else: `unknown type of device notification`). Attributes and children (found): `device_hash`, optional `device_lid_hash` plus `lid`, `device` entries (jid, key index), optional `key-index-list` (bytes, attr `ts`, `expected_ts`). If the notification carries attr `offline` the user is queued for later sync; otherwise a sync job runs (`SyncDeviceNotificationRunnable`). The list is accepted only if its timestamp is not older than the stored `adv_timestamp_sec` (`local ts is larger than notification one` otherwise).

### 6.2 Stored device record (`devices` table, `C1h8`)

| Group | Columns (found) |
|-------|-----------------|
| Identity | `device_id`, `platform_type`, `device_os`, `adv_key_index`, `companion_meta_nonce`, `instrumentation_device_id`, `nickname`, `place_name` |
| Time | `last_active`, `login_time`, `logout_time` |
| Sync | `full_sync_required`, `full_sync_days_limit`, `full_sync_size_mb_limit`, `recent_sync_days_limit`, `storage_quota_mb`, `inline_initial_hist_sync_payload_enabled`, `history_sync_config_protobuf`, `history_sync_access_type`, `on_demand_ready` |
| Capability | `support_hosted_group_msg`, `support_biz_hosted_msg`, `support_group_history`, `support_call_log_history`, `support_message_association`, `support_add_on_history_sync_migration`, `support_guest_chat`, `support_bot_user_agent_chat_history`, `support_fbid_bot_chat_history`, `support_manus_history`, `support_hatch_history`, `support_cag_reactions_and_polls_history`, `support_recent_sync_chunk_message_tuning`, `supported_bot_channel_fbids` |

`platform_type` values come from `companion-props.platformType` (`EnumC25120ArW`): 0 UNKNOWN, 1 CHROME, 2 FIREFOX, 3 IE, 4 OPERA, 5 SAFARI, 6 EDGE, 7 DESKTOP, 8 IPAD, 9 ANDROID_TABLET, 10 OHANA, 11 ALOHA, 12 CATALINA, 13 TCL_TV, 14 IOS_PHONE, 15 IOS_CATALYST, 16 ANDROID_PHONE, 17 ANDROID_AMBIGUOUS, 18 WEAR_OS, 19 AR_WRIST, 20 AR_DEVICE, 21 UWP, 22 VR, 23 CLOUD_API, 24 SMARTGLASSES, 25 WAIL, 26 WASS, 27 BUSINESS_BACK_OFFICE, 28 WAIL_WAI, 29 WAIL_ALEXA, 30 AUTOMOTIVE (found).

### 6.3 Limits and flags

| Flag / item | Meaning | Tier |
|-------------|---------|------|
| **15550** | integer: maximum linked devices (`LinkedDevicesSharedViewModel.hasMaxDeviceLimitReached`: `loggedInDeviceCount >= max` blocks "link a device"; the QR scanner gets extra `at_device_limit`; `OrbitCompanionLinkActivity` refuses when reached) | found (use); default value unknown (server-delivered abprop); metrics field `md_linked_devices_max_devices_limit` exists |
| **3816** | seconds the `companion_hello` stays valid, capped at 360 s | found |
| **477** | gate (non-zero) for key-index-list updates | found |
| **18193** | adds `friction` (variant 1) to advertised `challenges/supported` | found (use); effect on server unknown |
| **28161** | adds the second advertised challenge (`passkey-create`) | inferred mapping (decompiler lost the branch) |
| **29500** | hosted-pairing gate used in the defense-mode check | found (read), meaning inferred |
| **31019** | adds attr `exclude_hosted_companion=true` to remove-all for some reasons | found |

Whether the server enforces the limit independently of the client check is unknown. The primary has no client-side inactivity timeout for companions in the code read here; server-side expiry of idle companions is unknown.

---

## 7. Unlink (primary side)

### 7.1 Single device

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <remove-companion-device jid="user:device@…" reason="user_initiated"/>
</iq>
```

`C28905Ch6.A00`, timeout 32000 ms. Result may carry child `coex_token` (passed to the coexistence handler). Delivery failure or error calls the failure callback with code -1 (found).

### 7.2 All devices

`C0XQ.A0Y(reason, removeOnError, isEncryptionTypeTransitioning)`:

```xml
<remove-companion-device all="true" reason="…" [exclude_hosted_companion="true"]/>
```

Empty local list short-circuits to the success callback. Reason strings seen in code: `user_initiated`, `unknown_companion`, `invalid_adv_status`, `lid_migration_peer_sync_limit_exceeded`, `lid_migration_peer_sync_message_failed`, `lid_migration_missing_mappings_in_peer_sync_message` (found; list may be longer, the source expression is truncated).

### 7.3 Automatic unlink triggers (found)

| Trigger | Reason |
|---------|--------|
| key-index-list update failed more than 5 times | `adv-key-index-list-update`, logout all |
| key index overflow | `A03` reset |
| invalid ADV status / unknown companion (`KZD` case 43) | `invalid_adv_status` |
| hosted ↔ E2EE account type transition | kicks out all devices (`handleADVMetadata` log) |
| server sends `devices` notification type `remove` | local record removed (inferred) |
| user action in linked-devices screen / `EavesdropMonitor/disconnectDevice` | `user_initiated` (found for the monitor; UI path inferred) |

Account removal on the whole (`urn:xmpp:whatsapp:account` `remove`) is a different IQ and unrelated to companion unlink.

---

## 8. Error cases

### 8.1 Server codes handled by `C44661Jem.A01`

| Code | Callback | UI | Tier |
|------|----------|----|------|
| **465** | `Blp` → `onCompanionPlatformRestricted` | `CompanionPlatformRestrictedBottomSheet` | found |
| **496** | `Blv` → `onCompanionTooOld` | "companion too old" state | found |
| 404 / 405 / 443 / 445 | generic `C2w` | string mapping `C44648JeY`: 405 and 443 have dedicated texts; 404/405/443/445 share one title | found (strings by id); exact meaning of 404/443/445 unknown |
| other | generic `C2w` | pair failed | found |

`InstrumentationAuthActivity` names result codes 1 `CONSUMER_SMB_CROSS_PAIRING`, 2 `UNSUPPORTED_PRIMARY_VERSION`, 3 `INVALID_QR_CODE`, 4 `COMPANION_PLATFORM_RESTRICTED`, 5 `COMPANION_TOO_OLD`, 6 `MAX_DEVICE_LIMIT_REACHED`, else `PAIRING_FAILED` (found). Mapping of server 405 to the consumer/SMB case is inferred from the string id.

### 8.2 Local codes

| Code | Cause | Fix |
|------|-------|-----|
| -8 | local ADV timestamp invalid (clock vs last stored ts + 1) | correct device time; UI string "invalid device time" |
| -9 | QR missing identity key / adv secret | use a current QR |
| -10 | hosted pairing on consumer build | n/a |
| -13 | platform vs hosted flag mismatch | n/a |
| -17 | another pairing running | wait; request lives up to 32 s |
| -20 | server asked for challenges (`retry-after-challenges`) | complete friction / passkey challenge |
| -1 | remove request not sent or failed | retry |

### 8.3 Link-code failures

| Symptom (log) | Cause |
|---------------|-------|
| `companion hello is null or expired` | code typed after expiry (flag 3816, max 360 s) |
| `decryption fail` (hello) | wrong code (PBKDF2 key differs; AES-CTR has no tag, so a wrong code gives garbage key, caught at later steps; inferred) |
| `primary identity doesn't match` | bundle was built for another primary key |
| `companion identity doesn't match` | notification and bundle disagree |
| `invalid-primary-adv-key-length` / `adv public key is 0` | companion-role checks on the primary ephemeral key |

---

## 9. Key distinctions

### 9.1 Not to confuse

| A | B |
|---|---|
| `pair-device` sent by the **primary** (this report) | `pair-device` **received** by a companion-role app (handler `AbstractC40501kw`, id 242, carries refs for the QR) |
| `ADVSignedDeviceIdentity` (signed, no HMAC) | `ADVSignedDeviceIdentityHMAC` (the wrapper sent in `device-identity`) |
| `device-identity` child of `pair-device` (HMAC wrapper) | `device-identity` child in outgoing message stanzas (account identity attached by a companion; `adv_signed_identity` pref) |
| account signature (primary key, prefix `06 00`) | device signature (companion key, prefix `06 01`) |
| key-index-list prefix `06 02` | `06 07` (non-E2EE attestation) |
| QR `pub-key` / `companion_server_auth_key_pub` | companion identity key (the one that gets the account signature) |
| `rawId` (account-wide id that changes on reset) | `keyIndex` (per companion) |
| QR platform char (`EnumC26332BbY`) | wire `DeviceProps.platformType` (`EnumC25120ArW`), different numbering |

### 9.2 Hosted device

JID device id **99** (`device_id should be 99 for hosted device`), registration/unpair marker `hosted_device_pairing`, signature prefixes `06 05` / `06 06`, `exclude_hosted_companion`. The primary refuses to pair a hosted device on this build (local -10). Everything beyond these strings is unknown.

### 9.3 Shortcake

`retry-with-method` can list `shortcake-with-passkeys`; the app then stores a handoff key and switches UI. `ShortcakeJni` exposes `nativeMlkem768GenerateKeypair/Encapsulate/Decapsulate` and `nativeResponderStart/Finish` (found). The handshake transcript is native and was not decompiled here: unknown.

### 9.4 Friction / defense mode

`pair-device` advertises supported challenges and returns `completed` ones on retry. The primary decides locally to require friction when defense mode is on (`C271211x.A0N()`) and the friction challenge is not yet completed; this decision is made before the first IQ (`defense mode friction triggered`). Server-side policy that sends `retry-after-challenges` is not visible (unknown).

### 9.5 No client attestation of the companion

Nothing in the pair-device payload proves which software the companion runs: `ref`, `pub-key`, identity key, adv secret and platform char are self-declared by the QR. What the signatures prove is that this primary account authorised that identity key. Any "official client" check is server side (the 465 verdict is only handled client side).

### 9.6 Companion-role code in the same APK (brief)

| Item | Finding |
|------|---------|
| `companion_hello` IQ children | `link_code_pairing_wrapped_companion_ephemeral_pub`, `companion_server_auth_key_pub`, `companion_platform_id`, `companion_platform_display`, `link_code_pairing_nonce`; attr `should_show_push_notification` (found, `C0YS`) |
| code | `K1T.A00` base32 of 5 random bytes (4.3) |
| rotate QR | IQ `pair-device-rotate-qr` with attrs `stage` 0/1/2 and optional `sentinel`, child `ref` |
| incoming md IQs | `pair-device`, `pair-success`, `ref`, `companion_reg_refresh`, `integrity` (ids 242, 243, 266, 278, 279) |
| `pair-success` content and companion `pair-device-sign` reply | not traced in this build: unknown |

---

## 10. Baileys (`baron-baileys-v2`)

Compared against the local source; only matches and one difference that were checked on both sides.

| Item | APK 2.26.41.6 | `baron-baileys-v2` | Result |
|------|---------------|--------------------|--------|
| QR payload | `ref,noisePub,identityPub,advSecret[,platform]` | `[ref, noiseKeyB64, identityKeyB64, advB64].join(',')` (`socket.js`) | match (4 fields) |
| Pair-code derivation | PBKDF2-SHA256 131072 it., alphabet `123456789ABCDEFGHJKLMNPQRSTVWXYZ` | `iterations: 2 << 16`, same alphabet (`crypto.js`, `generics.js`) | match |
| Key bundle | `[salt32 ‖ nonce12 ‖ GCM]`, info `link_code_pairing_key_bundle_encryption_key`, plaintext identity ‖ identity ‖ random32 | same layout (`messages-recv.js`) | match |
| adv secret | HKDF(zero salt, `eph ‖ DH(identity) ‖ random`, info `adv_secret`) | `hkdf(identityPayload, 32, {info:'adv_secret'})` | match |
| HMAC wrapper | HMAC-SHA256(adv secret, [06 05 for hosted ‖] ADVSignedDeviceIdentity bytes) | same (`validate-connection.js`) | match |
| Account / device signature messages | `06 00 ‖ details ‖ companionIdentity`; `06 01 ‖ details ‖ companionIdentity ‖ accountSignatureKey` | same | match |
| Hosted key-index-list prefix | verifier and signer use `06 02` for every list; `06 07` is the non-E2EE attestation prefix | `WA_ADV_HOSTED_KEY_INDEX_LIST_SIG_PREFIX = [6, 7]` used when `accountType == HOSTED` (`chats.js`) | **differs**; hosted flow is not exercised by this consumer build, so the effect of the difference is unknown |

No "why it fails" claim is made: a Baileys companion that follows the matched rows is consistent with what the primary parses here; acceptance by the server is not verifiable statically.

---

## 11. Complete flows

### 11.1 QR flow

```
[Companion]  shows QR  https://wa.me/settings/linked_devices#ref,noisePub,identityPub,advSecret[,platform]
     │
     ▼
[Primary]    scan → C45741Jxy.A02 → C45423Jrn → C44423JaU
     │       checks: -9 / -13 / -17 / -8 / -10 ; defense mode → challenges (-20)
     │       incrementCurrentKeyIndex ; ts = C24270w6.A00()
     │       details  = ADVDeviceIdentity{rawId, ts, keyIndex, accountType, deviceType}
     │       accSig   = Curve25519.sign(P.priv, 06 00 ‖ details ‖ companionIdentity)
     │       signed   = ADVSignedDeviceIdentity{details, P.pub, accSig}
     │       wrapper  = ADVSignedDeviceIdentityHMAC{signed, HMAC-SHA256(advSecret, signed)}
     │       list     = ADVSignedKeyIndexList (sig 06 02)
     │       K        = HKDF(salt = noisePub, IKM = advSecret, "Canonical Ent Companion Nonce Encrypt")
     ▼
iq set xmlns=md  <pair-device> ref, pub-key, device-identity, key-index-list ts, client-props, pem, … </pair-device>
     │
     ▼
[WA Server]   (not observed) validates, creates device jid, sends pair-device / pair-success to the companion
     │
     ▼
Result to primary: <device jid/> <companion-props/>   (or retry-ts / retry-after-challenges / retry-with-method / error 465, 496, …)
     │
     ▼
[Primary]    store CJY record, adv_timestamp_sec = list ts, start history sync
     │
     ▼
[Server → Primary]  notification devices add{device_hash, device…, key-index-list ts}  → SyncDeviceNotificationRunnable → verify (5.5)
```

### 11.2 Pair-code flow

```
[Companion]  iq link_code_companion_reg stage=companion_hello
     │         wrapped_ephemeral = salt32 ‖ iv16 ‖ AES-CTR(PBKDF2(code, salt), ephPub)
     ▼
[WA Server]  → notification stage=companion_hello  → [Primary] C10J (id 252)
     │                                               store hello (ttl ≤ 360 s), push notification
     │                                               user types 8-char code
     ▼
[Primary]    unwrap companion eph pub ; make own eph pair ; eph = X25519(...)
     │         iq link_code_companion_reg stage=primary_hello
     │             wrapped_primary_ephemeral_pub, primary_identity_pub, link_code_pairing_ref
     ▼
[Companion]  eph = X25519(...) ; bundle = salt32 ‖ nonce12 ‖ GCM(HKDF(eph, salt), companionId ‖ primaryId ‖ random32)
     │         iq stage=companion_finish
     ▼
[WA Server]  → notification stage=companion_finish → [Primary] KYB
     │            decrypt, check both identities, advSecret = HKDF0(eph ‖ DH(id) ‖ random, "adv_secret")
     ▼
[Primary]    pair-device IQ (same as 11.1, pub-key = companion_server_auth_key_pub)
     ▼
(11.1 continues)
```

### 11.3 Unlink

```
[Primary UI / auto trigger]
     │   remove-companion-device jid=… reason=…     (or all="true")
     ▼
iq set xmlns=md  →  [WA Server]  →  result (optional coex_token)
     │
     ▼
[Primary]   remove local record, new key-index-list on next update (iq key-index-list ts)
[Server → other devices]  notification devices remove{…}
```
