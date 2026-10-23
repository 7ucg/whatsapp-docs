# WhatsApp Noise Transport — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-23
**Scope:** Android chat transport (chatd): endpoints and connection sequence, edge routing, TCP framing, Noise XX / IK / PQ handshake, certificate chain checks, ClientPayload (UserAgent, DevicePairingData, connect type / reason), transport cipher and counters, binary node encoding, login result and failure codes, keepalive, reconnect backoff, stream:error, feature flags, related transports (Tigon HTTP, DistribGW, Tigon Noise channel, MQTT), Baileys comparison

---

## 1. What it is (technically)

chatd is the one long-lived connection that carries every stanza (messages, receipts, IQ, presence, notifications). On Android it is a plain TCP socket (not WebSocket) running a Noise handshake, then length-prefixed AES-GCM frames, each holding one binary-encoded node. All statements come from static analysis of the decompiled APK; nothing was captured on the wire. Tiers: **found** = read in code, **inferred** = deduced, **unknown** = not resolved. Obfuscated names are per-build and were re-resolved in 2.26.41.6.

| Layer | 2.26.41.6 name | Role |
|-------|----------------|------|
| Connection thread | `HandlerThreadC12340b0` (log tag `ConnectionThread`) | connect, handshake, login, read loop, disconnect |
| Connection sequence / DNS | `C37151de` (states), `C37031dS` (`A0G` advance, `A0D` socket factory), `C36881dC`, `AbstractC47101wK` (hard-coded host to IP table), `C36821d6` (fallback IPs) | which host / port / proxy next |
| Handshake driver | `C38791hg` (`NoiseSocket/*` logs) | intro bytes, ClientHello, ServerHello, cert checks, ClientFinish |
| Noise state | `C38921hv` (+ `C38941hx` hash, `C38981i2` AES-GCM, `AbstractC38961i0` HKDF), `C40331kf` (transport keys + counters) | pure Java |
| Frame I/O, node codec | `C38891hs` / `C38901ht`; `C40411kn` (encoder), `C24610wf` (decoder), `AbstractC40911lb` (dictionary) | framing, binary XML |
| Protos | `C39211ii`, `C39161id`, `C39231ik`, `C39241il` (handshake); `C24843Amz`, `C24842Amy`, `C24841Amx`, `C25757B9r`, `BC0` (certs); `C38001fP`, `C38051fp`, `C38661hS` (payload) | wire messages |
| Trust, PQ | `AbstractC44011qk` (pinned root); `C38811hi`, `AbstractC38821hj`, `AbstractC38831hk`, `C38761hd` (PQ config, server static keys) | server identity, ML-KEM-512 hybrid |
| Payload builder | contributors in `AbstractC43901qZ` collected by `C37991fK` | ClientPayload |
| Keepalive, timers, reconnect | `C14U` (`ClientPingManager`), `C9EN` (ping IQ), `HandlerC21850s9`, `C11380Yq` (`MessageHandler`), `C0X9` (backoff) | ping, timeouts, retry |
| Inbound control | `C40581l4` (`<ib>`), `C40601l6` / `C37961fH.A1B` (`stream:error`) | server notices |

Points that decide the rest of the report:

- The Noise state machine, HKDF, AES-GCM and the frame codec are **Java**. Only Curve25519 (`org.whispersystems.curve25519`, `OpportunisticCurve25519Provider`, native with Java fallback) and the ML-KEM calls (`KEMKeyPair.generateNative`, `KEMSecretKey.decapsulateNative`) are native. There is no native chatd implementation to reverse (found).
- The intro header is the constant `WA 06 03` in this build (section 3.1). The protocol-version int passed to `C38791hg` is hard-coded 6 at its only call site, so the version-5 flat-certificate branch is unreachable in practice (found; reachability inferred from the single constant call site).
- `devicePairingData` is sent only by a connection that has no user JID, which `ConnectionThread` allows only in companion registration. It is not a primary-phone registration artifact in this build (section 6.4).
- Outbound stanzas on the main send path are DEFLATE-compressed (flags `3`), not only inbound ones (section 8.1).

---

## 2. Endpoints and connection sequence

### 2.1 Hosts and ports (found)

| Host | Where | Notes |
|------|-------|-------|
| `g.whatsapp.net` | `C37151de` steps 5, 9; `C36881dC.A01` (hard-coded IPs) | primary chat host |
| `g-fallback.whatsapp.net` | steps 13, 14 | second host |
| `e1` ... `e16.whatsapp.net` | `C37151de.A0F` (16 entries), step 7 and 11 | `ConnectionSequence/getEdgeHost`; random pick, or the host stored in history |
| hard-coded IP table | `AbstractC47101wK.A00`, steps 6 and 10 | map host to IP list, covers the `eN` hosts and `g.whatsapp.net` |
| `<ib><fbip>` list | `C40581l4` to `C36821d6.A02` | comma-separated IPs, persisted by the fallback manager (steps 2 / 8 input, inferred) |
| user proxy | step 12 | plain or TLS socket to the proxy `host:chatPort`, no proxy handshake (see WA_CENSORSHIP_CIRCUMVENTION.md) |
| SOCKS tunnel (proxy service) | `C48201yM` (`ConnectionSocketTunnel`), not step 12 | `java.net.Proxy.Type.SOCKS`, connect timeout 30000 ms |

Ports: 443 and 5222 (random choice per attempt, `C37151de.A00`; the constructor also draws one coin flip that orders ports for steps 3 and 4), and 80 for the `:80` steps. The port of the last successful connection is reused when flag **33512** is on (found).

### 2.2 Sequence states (found, `C37151de.A02`, advance in `C37031dS.A0G`)

| Step | Target |
|------|--------|
| 0 | start, picks the first applicable step |
| 1 | debug / override `InetSocketAddress` (terminal) |
| 2 | server-supplied endpoint entries with the `A04` bit set (list `A0A`), one by one; each entry carries its own TLS bit `A05` |
| 3, 4 | configured host string `A07` on the two ports (443 / 5222 in random order) |
| 5 | `g.whatsapp.net` on 443 (flag **20801**) or a random 443 / 5222 |
| 8 | server-supplied entries without the `A04` bit (list `A09`); decompiled branch order is unclear |
| 9 | `g.whatsapp.net:80` |
| 15 | HISTORY: retry the step / host / port stored by the last success (inserted after 9 when the history step is valid and flag **22916** is off) |
| 13, 14 | `g-fallback.whatsapp.net` on 443 / 5222, then `:80` |
| 6, 10 | hard-coded IP for `g.whatsapp.net`, then `:80` |
| 7, 11 | random edge host `eN.whatsapp.net`, then `:80` |
| 12 | user proxy (terminal) |
| 16 | exhausted |

Order after step 9 (found): 9, [15], 13, 14, 6, 10, 7, 11, 16. The last success is stored in preferences `last_successful_connection_step`, `_host`, `_port` (found, `C37031dS.A00`). Steps 2 to 4 log `Skipping sequence ... due to active proxy` while a SOCKS service config is active and flag **23630** is off (skip semantics inferred).

### 2.3 Socket (found, `C37031dS.A0D`)

| Aspect | Value |
|--------|-------|
| Socket | plain TCP; Happy Eyeballs when both IPv4 and IPv6 addresses exist (`ConnectionSocketFactory/try_connect/using-happyEyeball`) |
| TLS wrapper | the config bit `A07` selects an `SSLSocketFactory`; set per server-supplied entry (`A05`), for step 1 on port 443, and for edge hosts (step 7) on port 443. Step 5 (`g.whatsapp.net`) is created with the bit off |
| Socket timeout | 30000 ms set through `CeF(30000)` (semantics inferred: read timeout) |
| TCP keepalive | `configureTcpKeepalive`: when flag **7831** is on and the socket supports it, keepalive is enabled and three ints from flags **7832** (default 2), **7833** (default 10), **7834** (default 10) are applied (idle / interval / count by inference) |
| Output buffering | when flag **33751** is on, the writer is wrapped in a `BufferedOutputStream` so intro bytes and ClientHello leave in one write (found) |

Whether the TLS-wrapped endpoints carry the same Noise bytes inside TLS is inferred from the code path (`C38791hg` receives only streams); a metric named `chatd_non_secure_tls_wrapper_resumption` exists in a native lib.

### 2.4 DNS resolution (found)

`DNSResolutionMethod` is reported in `ClientPayload.dnsSource` (section 6.5): `SYSTEM`, `GOOGLE`, `HARDCODED`, `OVERRIDE`, `FALLBACK`, `MNS`, `MNS_SECONDARY`, `SOCKS_PROXY`. Flag **13545** (string; values `secondary`, `hardcoded`, `none` recognized by `C37151de.A01`) tunes the resolver chain. Cached answers from earlier lookups are used until their expiry before a new lookup (`C36881dC.A03`).

---

## 3. Framing

### 3.1 Bytes before the first frame (found, `C38791hg`)

```
[ 'E' 'D' 00 01 | len24 | routing_info ]     only when routing_info is non-empty
[ 'W' 'A' 06 03 ]                             always
[ len24 | HandshakeMessage{clientHello} ]     first frame
```

- Edge header: magic `45 44 00 01` (`C38791hg.A0B`), 3-byte big-endian blob length, then the `routing_info` bytes (preference, base64 without padding or wrap; stored by `C38801hh.A00`, max 256 bytes: "The routing info should be smaller than 256 bytes."). Raw on the socket, outside the Noise transcript.
- Intro: `57 41 06 03` = "WA", protocol 6, dictionary 3 (`C38791hg.A04`); also the Noise prologue (4.2). The else branch returns `57 41 05 03`, but the constructor fixes the version at 6.

### 3.2 Frame layout (found)

Every frame is a 3-byte big-endian length (`AbstractC38721hZ.A04` / `A00`; writes must be below 2^24, else `data too large to write`) followed by the body: handshake protobuf during the handshake, AES-GCM ciphertext afterwards.

Reader (`C38891hs`): exactly 3 length bytes, then the body. While reading the ServerHello, three length bytes equal to ASCII `GOA` (`47 4F 41`, `C38891hs.A01`) throw `X.1sn` (log `socket/goaway`); the post-handshake read path (`C24610wf.Be0`) has no such check. Empty decrypted frames are skipped; a 1-byte decrypted frame throws `header only frame received`. A stanza above the optional size limit (`InterfaceC40421ko.AqJ`) throws `C31990DyW` on encode.

### 3.3 Handshake messages (found, field numbers from the protobuf classes)

| Message (class) | Fields (number in bold) |
|-----------------|-------------------------|
| `HandshakeMessage` (`C39211ii`) | clientHello **2**, serverHello **3**, clientFinish **4** |
| `ClientHello` (`C39161id`) | ephemeral **1**, static **2**, payload **3**, useExtended **4**, extendedCiphertext **5**, paddedBytes **6**, sendServerHelloPaddedBytes **7**, simulateXxkemFs **8**, pqMode **9**, extendedEphemeral **10** |
| `ServerHello` (`C39231ik`) | ephemeral **1**, static **2**, payload **3**, extendedStatic **4**, paddingBytes **5**, extendedCiphertext **6** |
| `ClientFinish` (`C39241il`) | static **1**, payload **2**, extendedCiphertext **3**, paddedBytes **4**, simulateXxkemFs **5** |

Setters seen in the driver: full XX ClientHello sets `ephemeral` (+ `pqMode` in PQ variants); the resume ClientHello sets `ephemeral`, `static`, `payload`, `extendedCiphertext`, `extendedEphemeral`, `pqMode`; ClientFinish sets `static`, `payload`, `extendedCiphertext`. The padding and simulate fields are defined but no setter was found in the driver (unknown use).

---

## 4. Noise handshake

### 4.1 Pattern names (found, `C38921hv` static fields)

| Constant | Name | Used when |
|----------|------|-----------|
| `A07` | `Noise_XX_25519_AESGCM_SHA256` (NUL-padded to 32 bytes) | full handshake, PQ none |
| `A0H` | `Noise_IK_25519_AESGCM_SHA256` (padded to 32) | resume with cached server static, PQ none |
| `A06` | `Noise_XXfallback_25519_AESGCM_SHA256` | IK rejected by the server (4.4) |
| `A0E`, `A0C`, `A08` | `Noise_XXkem_`, `Noise_XXkem-FS_`, `Noise_XXkemEph_` + `25519_MLKEM512_AESGCM_SHA256` | full, PQ on |
| `A0F`, `A0D`, `A0G` | `Noise_IKkem+`, `Noise_IKkem-FS+`, `Noise_IKkem2+` + `X25519+MLKEM512+AESGCM256+SHA256` | resume, PQ on |
| `A09`, `A0B`, `A0A` | `Noise_XXkemfallback_`, `Noise_XXkem-FSfallback_`, `Noise_XXkemEphfallback_` + `25519_MLKEM512_AESGCM_SHA256` | PQ fallbacks |

A name longer than 32 bytes is hashed with SHA-256, otherwise the 32-byte padded value is the initial hash (found, constructor of `C38921hv`).

PQ configuration (`NoisePQConfig`): mode `NONE` / `ENABLE` / `ENFORCE` (flag **20161**, int: 1 enable, 2 to 4 enforce, else none); variant `IKKEM`, `IKKEM_FS`, `XXKEM_EPH_IKKEM2`, `XXKEM_EPH_ONLY` (flag **34536**, string, default `IKKEM`). Full handshake: PQ mode `NONE` uses `A07`; otherwise variant `IKKEM_FS` selects `A0C`, `XXKEM_EPH_ONLY` and `XXKEM_EPH_IKKEM2` select `A08`, `IKKEM` selects `A0E` (found in the `C38791hg` constructor). The `IKkem*` names pair with the resume path; their exact variant mapping was not traced.

### 4.2 Symmetric state (found, `C38921hv`)

```
h  = name (padded, or SHA256(name) if > 32 bytes)         // C38941hx.A00 = name
ck = h                                                    // A02
h  = SHA256(h || prologue)                                // prologue = WA 06 03
mixHash(d):  h = SHA256(h || d)
mixKey(dh):  okm = HKDF-SHA256(salt = ck, ikm = dh, info = none, 64)
             ck  = okm[0:32] ; k = AES-256-GCM key okm[32:64] ; n = 0
encrypt(p):  c = AES-GCM(k, iv = 00000000 || n_be64, aad = h, p) ; n++ ; mixHash(c)
decrypt(c):  p = AES-GCM(k, iv = 00000000 || n_be64, aad = h, c) ; n++ ; mixHash(c)
             (no key yet: encrypt / decrypt pass through and only mixHash)
split():     okm = HKDF-SHA256(salt = ck, ikm = empty, info = none, 64)
             sendKey = okm[0:32] ; recvKey = okm[32:64]
```

HKDF is hand-written (`AbstractC38961i0`): extract = `HMAC(key = salt, data = ikm)`, expand with a one-byte counter. IV: 12 bytes, first 4 zero, last 8 the big-endian counter (`AbstractC38721hZ.A02`). Tag 128 bit (BouncyCastle-style GCM `C39061iT`). DH is Curve25519 `calculateAgreement` through `C38851hm.A00("best")`.

### 4.3 Full XX sequence (found)

| # | Direction | Content | State operations |
|---|-----------|---------|------------------|
| 1 | C to S | `ClientHello{ephemeral}` (+ `pqMode` in PQ variants) | `mixHash(e_c)` |
| 2 | S to C | `ServerHello{ephemeral, static, payload}` | `mixHash(e_s)`; `mixKey(DH(e_c, e_s))`; `s_s = decrypt(static)`; `mixKey(DH(e_c, s_s))`; `cert = decrypt(payload)` |
| 3 | local | certificate checks (section 5) | key in cert must equal `s_s` |
| 4 | C to S | `ClientFinish{static, payload}` | `static = encrypt(s_c)`; `mixKey(DH(s_c, e_s))`; `payload = encrypt(ClientPayload)` |
| 5 | local | split | `sendKey`, `recvKey`, both counters 0 |

The order in `C38791hg.A03` (smali) matches the standard XX transcript. The client static `s_c` and the ephemeral come from `C38711hY` key pairs; the static is supplied by `C38771he.A01` (persistent client Noise key, "authKey" in disconnect logs). That it equals the key uploaded at registration is inferred.

### 4.4 Resume (IK) and fallback (found structure, step detail inferred)

When cached server static keys exist (`C38771he.A00` non-null, `C38761hd`) the driver logs `NoiseSocket/handshakeStart mode=... rs=...` and runs `handshakeResume`: the cached server static public key is hashed into the state (`C38921hv.A06`), the ClientHello carries the ephemeral, the encrypted client static and the encrypted `ClientPayload` in one message (section 3.3). If the server answers with a static key, the log is `handshakeResume server hello has static key, falling back` and `C38791hg` throws `X.1t8` carrying the ServerHello, which selects the `Noise_XXfallback_*` names. The exact fallback transcript is inferred from the standard Noise fallback modifier. Server static keys are persisted after a successful login when they change (`A1m`: classic key via `Ce3`, PQ key via `Ce2`).

### 4.5 Post-quantum material (found as present; wire detail partly unknown)

- KEM: ML-KEM-512 (algorithm string `MLKEM512`, `C38791hg.A0C`). Server PQ public key TLV: type `0x02`, length 800; TLV header type `0x01` carrying the algorithm name; FS ciphertext TLV type `0x04`, length 768 (from the error strings `Expected TLV PK type 0x02`, `length 800`, `Expected TLV header type 0x01`, `Expected FS ciphertext length 768`).
- Encapsulation (`C38921hv.A07`): `KEMPublicKey.A00()` yields ciphertext + shared secret; the ciphertext goes through `mixHash`, the shared secret through `mixKey`. Decapsulation: `KEMSecretKey.decapsulateNative`.
- Delivery: `<success static_pq_key="base64">` is read only when PQ mode is not `NONE` and the variant is `IKKEM_FS` (`A18`); without it the log is `handshake missing serverStaticPQ forcing full handshake` (`C38791hg.A01`).

TLV length-field width and the exact placement inside `ServerHello.payload` are not decoded. The ML-KEM natives come from the Signal KEM classes; the library that implements them was not identified.

---

## 5. Server certificate checks (found, `C38791hg.A03`)

Protocol version 6 (the only value used) parses `ServerHello.payload` as a `CertChain`:

`CertChain` (`C24843Amz`): leaf **1**, intermediate **2**. Each is a `NoiseCertificate` (`C24842Amy`): details **1** (bytes), signature **2** (bytes). `details` parses as chain `Details` (`C24841Amx`): serial **1**, issuerSerial **2**, key **3**, notBefore **4**, notAfter **5**.

Checks (log prefix `wa6:`; evaluation order not fully recovered, the decompiled method is incomplete):

1. Both `details` parse as chain `Details`.
2. `intermediate.issuerSerial == 0` and `leaf.issuerSerial == intermediate.serial`.
3. `leaf.key` equals the handshake server static `s_s` ("noise certificate key does not match proposed server static key").
4. The intermediate signature verifies over `intermediate.details` with the pinned root key for issuer `WhatsAppLongTerm1` (`AbstractC44011qk.A00`).
5. The leaf signature verifies over `leaf.details` with the intermediate `key`.

`notBefore` / `notAfter` are not read in the chain path. A failure throws `X.1so` (log `socket/invalid-certificate-exception`).

Pinned root (public key, found, `AbstractC44011qk.A01`): `142375574d0a587166aae71ebe516437c4a28b73e3695c6ce1f7f9545da8ee6b`.

Flat form (dead code at the constant version 6): `NoiseCertificate{details = 1, signature = 2}` (`C25757B9r`), flat `Details{serial = 1, issuer = 2, expires = 3, subject = 4, key = 5}` (`BC0`). The code verifies the single signature against the pinned key by issuer name, compares `key` with `s_s`, and rejects when `expires` (seconds) is below the current time (log `noise certificate expired`).

---

## 6. ClientPayload

### 6.1 Fields (found, `C38001fP`; numbers from the descriptor)

| Field | Number | Type | Set by in 2.26.41.6 |
|-------|--------|------|---------------------|
| username | **1** | int64 | numeric user part of the login JID (LID user for a LID login) |
| passive | **3** | bool | connection mode flag of the session info (7.2) |
| userAgent | **5** | `UserAgent` | 6.2 |
| webInfo | **6** | `WebInfo` | not set by the contributors read |
| pushName | **7** | string | account push name, if non-empty |
| sessionId | **9** | int32 | per-connect session id (`C37121db`) |
| shortConnect | **10** | bool | `C11750a1.A03()` |
| connectType / connectReason | **12** / **13** | enum | 6.5 |
| shards | **14** | repeated int32 | not set |
| dnsSource | **15** | message | `dnsMethod` **15**, `appCached` **16** |
| connectAttemptCount | **16** | int32 | attempts so far |
| device | **18** | int32 | companion mode: preference `registration_device_id` |
| devicePairingData | **19** | message | 6.3 / 6.4 |
| product | **20** | enum | `WHATSAPP_LID` for a LID login, else default `WHATSAPP` |
| oc / lc | **23** / **24** | bool / int32 | `oc`: build or signature check result (`AbstractC38241gg`, name not expanded); `lc`: preference `connection_lc` |
| pull | **33** | bool | **never set in this build** (no writer found) |
| yearClass / memClass | **36** / **37** | int32 | device class heuristics (`C38261gi`, `C38271gj`) |
| trafficAnonymization | **40** | enum | `STANDARD` when `C17830kT.A0L()` else `OFF` |
| lidDbMigrated | **41** | bool | only with a user JID and not companion |
| connectionSequenceInfo | **43** | int32 | counter 0-31 derived from the sequence step |
| paaLink | **44** | bool | `C0NZ.A02()` |
| preacksCount / processingQueueSize | **45** / **46** | int32 | queue state (flags **20485** / **22413**) |
| pairedPeripherals | **47** | repeated string | `smart_glasses`, `garmin` |
| messageSts | **49** | int64 | last message timestamp, if known |

Defined but not set here: fbCat **21**, fbUserAgent **22**, iosAppExtension **30**, fbAppId **31**, fbDeviceId **32**, paddingBytes **34**, interopData **38** (`accountId` **1**, `token` **2**, `enableReadReceipts` **3**), accountType **42**, testIsolationId **48**.

### 6.2 UserAgent (found, `C38051fp`)

| Field | Number | Value in this build |
|-------|--------|---------------------|
| platform | **1** | `ANDROID` (0), constant |
| appVersion | **2** | `{primary 1, secondary 2, tertiary 3, quaternary 4}` parsed from `2.26.41.6` |
| mcc / mnc | **3** / **4** | `getNetworkOperator()`, default `000` |
| osVersion / manufacturer / device / osBuildNumber | **5** / **6** / **7** / **8** | system strings |
| phoneId | **9** | device-level id (`C38141gV`) |
| releaseChannel | **10** | `BETA` (1) in this beta build; `RELEASE 0, BETA 1, ALPHA 2, DEBUG 3` |
| localeLanguageIso6391 / localeCountryIso31661Alpha2 | **11** / **12** | skipped for `zz` / `ZZ` |
| deviceBoard / deviceExpId | **13** / **14** | board string if non-empty; experiment id |
| deviceType | **15** | `PHONE`, `TABLET`, `DESKTOP`, `VR` from the device class |
| deviceModelType | **16** | |
| distributionChannel | **17** | not set |

`UserAgent.Platform` (`EnumC38071fr`, 0-40): 0 ANDROID, 1 IOS, 10 SMB_ANDROID, 12 SMB_IOS, 13 WINDOWS, 14 WEB, 24 MACOS, 29 WEAROS, 33 IPAD, 35 SMART_GLASSES, 39 WORK_ANDROID, 40 WORK_IOS (others omitted).

### 6.3 DevicePairingRegistrationData (found, `C38661hS`)

`DevicePairingRegistrationData` fields: eRegid **1** (4-byte registration id), eKeytype **2** (`05`), eIdent **3** (identity public key), eSkeyId **4**, eSkeyVal **5**, eSkeySig **6** (signed prekey id, public, signature), buildHash **7**, deviceProps **8** (serialized `DeviceProps`).

`buildHash`: the code computes `Base64.decode(hexMD5("2.26.41.6"), 0)` (`C00L.A04` returns the 32-char lowercase hex MD5, which is then fed to the base64 decoder), giving 24 bytes, not the 16-byte digest (found as read).

`DeviceProps` (`C43105IrG`): os **1** (OS string), version **2** (`AppVersion`), platformType **3**, requireFullSync **4** (= true), historySyncConfig **5**. The history-sync block is assembled by a class that logs as `CompanionRegInfoProvider`; its fields (full sync days / size limits, recent sync, thumbnail sync, support flags such as call logs, bot history, group history) are driven by flags **15284**, **15283**, **21217**, **20658**, **18953**, **26445**, **26614**.

### 6.4 Which variant is sent (found)

- Login, primary (user JID known): username, passive, userAgent, pushName, sessionId, shortConnect, connectType, connectReason, dnsSource, connectAttemptCount, connectionSequenceInfo, lc, oc, yearClass, memClass, trafficAnonymization, lidDbMigrated, messageSts, queue counters, paaLink, pairedPeripherals; `product = WHATSAPP_LID` for LID logins.
- Login, companion: the same plus `device = registration_device_id`.
- Companion registration (user JID null): no username; `devicePairingData` (key bundle + `DeviceProps`) and `device`.

`ConnectionThread/connect/ignored/jid null and not in companion reg` shows that a null JID is refused outside companion registration. The primary phone registers over HTTPS `/v2/*` (see the account-security report); no primary-registration use of `devicePairingData` was found.

### 6.5 Enums used (found)

| Enum | Values |
|------|--------|
| `ConnectReason` (`EnumC38391gv`) | 0 PUSH, 1 USER_ACTIVATED, 2 SCHEDULED, 3 ERROR_RECONNECT, 4 NETWORK_SWITCH, 5 PING_RECONNECT, 6 UNKNOWN |
| `ConnectType` (`EnumC38311gn`) | 0 CELLULAR_UNKNOWN, 1 WIFI_UNKNOWN, 100 EDGE, 101 IDEN, 112 HSPAP; the other cellular names (UMTS, EVDO, GPRS, HSDPA, HSUPA, HSPA, CDMA, ...) take their numbers from indirect constants that were not resolved |
| `Product` (`EnumC38561hI`) | 0 WHATSAPP, 1 MESSENGER, 2 INTEROP, 3 INTEROP_MSGR, 4 WHATSAPP_LID |
| `DNSResolutionMethod` (`EnumC38321go`) | 0 SYSTEM, 1 GOOGLE, 2 HARDCODED, 3 OVERRIDE, 4 FALLBACK, 5 MNS, 6 MNS_SECONDARY, 7 SOCKS_PROXY |

Connect reason as written in this build: default `UNKNOWN`; when the session-info timestamp is within 10 s, state 1 gives `USER_ACTIVATED`, state 2 gives `PUSH`. The other values are defined but this contributor does not select them.

---

## 7. After the handshake

### 7.1 Login result (found, `HandlerThreadC12340b0.A13`)

The first inbound nodes are read in a loop. `web` is only accepted when a web ref was sent (else `web node given during login without any web ref provided`). Anything but `web`, `success`, `failure` throws `unexpected node received during login sequence`.

`<success>` attributes read:

Attributes read: `t` (server time in seconds, stored; non-numeric throws `invalid server time`), `props`, `abprops`, `mc_ep_version` (config version counters), `lid` (account LID, compared with the stored LID; mismatch reports `lid-chatd-lid-mismatch`), `pn` (phone user JID), `static_pq_key` (base64 server PQ key, 4.5).

### 7.2 Passive vs active mode (found)

`passive` in the payload comes from the session info (`C37981fJ.A0A`); log fields `forcePassiveMode`, `enablePassiveModeBasedOnQueueSize`, `duplexActive`. After login the client leaves passive mode with a set IQ built by `AbstractC44071qq`:

```xml
<iq id="..." xmlns="passive" type="set" to="s.whatsapp.net"><active/></iq>   <!-- or <passive/> -->
```

Pre-acks are sent first when queued (`ConnectionThread/send preacks`). A timer of 32000 ms (`HandlerC21850s9.A02`) arms on send; if the connection-active signal does not arrive it fires reason 10 (`connection active timeout`).

### 7.3 Information bulletins (found, `C40581l4`)

`<ib>` children handled: `edge_routing` (child `routing_info`, stored, section 3.1), `fbip` (comma-separated IPs to the fallback manager), `client_expiration` (`t`, seconds, converted to ms), `dirty`, `offline_preview`, `location`, `notice`, `recovery_nonce`, `safetynet`, `sonar` (`url`), `streamdebug`, `thread_metadata`, `gpia`, `age_experience`, `accept_paa_link`, `peer_device_presence`. `dns_domain` is not present (absent from the Android client).

---

## 8. Binary node encoding

### 8.1 Frame content and flags (found, `C40411kn.Csv`, `C24610wf.Be0`)

After AES-GCM decryption the plaintext starts with one flags byte:

| Bit | Meaning |
|-----|---------|
| `2` | the rest is a zlib (DEFLATE) stream; the decoder inflates it and keeps the flags byte |
| `1` | fragmentation; decoder throws `server to client stanza fragmentation not supported` |

Encoder: `Csv(node, flags)` with `flags & 2` deflates (`DeflaterOutputStream`) and prefixes `02`; otherwise it writes a `00` flags byte. The main send paths in `HandlerThreadC12340b0` and the writer thread `HandlerThreadC21920sG` call `Csv(node, 3)`, so those stanzas are compressed. `Csu(node)` (= flags 1, uncompressed) is called from `C40851lV`, which looks like the login-stage sender (inferred). The end-of-stream marker is `00` + list(1) + token `02` (`Clp`, `xmlstreamend`).

### 8.2 Tag bytes (found)

| Byte | Name | Body |
|------|------|------|
| 0 | empty list / absent | none |
| 1, 2 | `xmlstreamstart`, `xmlstreamend` | decoder rejects them as strings |
| 3..235 | single-byte token | index into the 236-entry table `A00` |
| 236..239 | dictionary 0..3 | 1 index byte into `A01[tag - 236]` (256 entries each) |
| 244 / 247 | JID_INTEROP / AD_JID | `user:str, device:u16, integrator:u16, domain:u8` / `domain:u8, device:u8, user:str` |
| 248 / 249 | LIST_8 / LIST_16 | `count:u8` / `count:u16` |
| 250 | JID_PAIR | `user:str or 00, server:str` |
| 251 / 255 | HEX_8 / NIBBLE_8 | `lenAndOdd:u8` + packed nibbles |
| 252 / 253 / 254 | BINARY_8 / _20 / _32 | `len:u8` / `len:u20` (3 bytes) / `len:u32`, then bytes |

Tags 245 and 246 do not exist in this codec. All multi-byte integers are big-endian.

### 8.3 Node layout (found, `C40411kn.A01`)

```
list(size)  description  (key value)*  [content]
size = 1 + 2 * attrCount + (content ? 1 : 0)
```

Odd size means no content. Decoder: attribute count = `((size - 2) + size % 2) / 2`. Content is either a byte blob (`252 / 253 / 254`) or a child list. A node with both blob and children throws `more than one source of inner data`. List header: 0 for empty, 248 below 256 entries, 249 below 65536, otherwise `list too long`.

### 8.4 String ladder (found, `C40411kn.A05` / `A06`)

| Slot | Order tried |
|------|-------------|
| description | token, dictionary, JID (if parseable), length-prefixed UTF-8 |
| attribute key | token, dictionary, UTF-8 |
| attribute value | token, dictionary, JID, packed, UTF-8 |
| content bytes | raw BINARY (`A06(bytes, false)`), never tokenized or packed |

Packing (`A06` with the packed flag, attribute values only): length below 128 and all chars in `[0-9-.]` gives NIBBLE_8 (`255`; `0-9` = 0..9, `-` = 10, `.` = 11); length below 128 and all chars in `[0-9A-F]` gives HEX_8 (`251`); the odd-length bit is `0x80` in the length byte. Lengths 256 and above use BINARY_20 up to 1 MiB, BINARY_32 beyond. Decoder nibble map: 10 `-`, 11 `.`, 12 `:` (the encoder never emits 12).

### 8.5 JIDs (found, `C40411kn.A00`, `C24610wf.A02`)

| JID | Encoding |
|-----|----------|
| interop user (`C99O`, type 22) | `244, user, device u16, integrator u16, 00`; decodes to `{integrator}-{user}[:device]@interop` |
| interop group (`C55529Oy6`, type 28, server `interop.g.us`) | `244, user, 0000, 0000, 02`; decoder requires device and integrator 0 |
| agent or device present | `247, domainByte, device, user`; domainByte bit `1` = LID, bit `128` = hosted |
| otherwise | `250, user (or 00), server` |

AD_JID server mapping: `0` `s.whatsapp.net`, `1` `lid`, `128` `hosted`, `129` `hosted.lid`. Device `99` is expected exactly when the hosted bit is set; a mismatch is logged and the JID still accepted. Non-compliant JIDs throw `failed to write jid`.

### 8.6 Dictionary (found, `AbstractC40911lb`)

236 single-byte tokens (index 0 is null) and four 256-entry dictionaries; the dictionary version is the last intro byte, `03`. Indices re-resolved in this build:

| Token | Index | Token | Index |
|-------|-------|-------|-------|
| `s.whatsapp.net` | 3 | `iq` / `ack` / `message` | 25 / 27 / 19 |
| `type`, `id`, `from`, `to` | 4, 8, 6, 17 | `get` / `set` / `result` / `error` | 41 / 90 / 20 / 168 |
| `routing_info` / `edge_routing` | 39 / 40 | `urn:xmpp:ping` / `ping` / `w:p` | 43 / 86 / 87 |
| `handshake` / `success` | 53 / 76 | `stream:error` / `not-authorized` | 157 / 209 |
| dict 0: `active` / `conflict` / `replaced` / `passive` | 1 / 14 / 17 / 24 | dict 1: `dirty` / `server-error` / `pair-device` | 1 / 145 / 238 |
| dict 2: `failure` / `rate-overlimit` | 60 / 239 | `call` / `usync` / `w:m` | 100 / 121 / 194 |

A few tokens in the table are Java constants imported from other classes (for example `enc`); they were not resolved by this index list. Indices change between builds; do not reuse them across versions.

---

## 9. Keepalive and timers

| Timer | Value | Tier |
|-------|-------|------|
| Client ping | `<iq type="get" xmlns="w:p" to="s.whatsapp.net"/>` (`C9EN`); the reply must carry `from`, `id`, `t` in 1577865600..4102473600 and `type="result"` (`C14U`) | found |
| Ping timeout | `clamp(flag 15103, 8000, 32000)` ms; on timeout `C14R.CY1()` runs once per ping (reconnect reaction inferred) | found / inferred |
| Ping interval | flag **15270** (first), **15183** (later); delayed runnable or alarm `com.whatsapp.alarm.CLIENT_PING_TIMEOUT`, chosen by flag **6493** | found, values server-side |
| Server ping | `<iq type="get" xmlns="urn:xmpp:ping" t="...">` (`AbstractC40501kw`) | found |
| Active-mode ack | 32000 ms, then disconnect reason 10 | found |
| Message receipt | 45000 ms after send, still unacknowledged: reconnect reason 9 (`HandlerC21850s9`) | found |
| Logout timeout / socket timeout | 10000 ms / 30000 ms | found |

---

## 10. Reconnect and backoff (found, `C11380Yq.A07`, `C0X9`)

`C11380Yq` schedules a reconnect through `AlarmManager` (`com.whatsapp.MessageHandler.RECONNECT_ACTION`, `connect_reason` extra 3). Delay unit is 10 s (0x2710 ms in the smali).

| Step | Rule |
|------|------|
| Counter | `C0X9(1, 17280)`: Fibonacci in units, sequence 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55 ... capped at 17280 units (48 h) |
| First retry | 0 units: `scheduleReconnect/immediate` |
| Jitter | `d = units * 10 s`; delay uniform in `[d / 2, 1.5 d)` |
| Clamp | when the caller flag is set, delays above 15 min become 15 min plus a random offset in `-30 .. +29` ms (`backoff clamped to ~15mins`) |
| Reset | `A02()` resets the counter on a `reset` reconnect request |
| Overrides | `force` clears the pending deadline; `force_no_ongoing_backoff` skips waiting; `reset` resets the counter |
| No network | `handleDisconnected/retry/network_unavailable` waits for connectivity (alarm `CONNECTIVITY_RETRY_ACTION`) |

Within one attempt the connection sequence of section 2.2 walks hosts and ports; backoff applies between failed attempts of the whole connect.

---

## 11. Stream errors and failure codes

### 11.1 `<failure reason="N">` at login (found, `A13`)

| Reason | Handling | Extra attributes read |
|--------|----------|-----------------------|
| 5xx | retryable server failure, `C45351tB(type 4)` | none |
| 402 | ban family; type 13 (code 106 with `appeal_token`), 14 (code 107), 15 (code 109), else 2 | `appeal_token`, `code`, `expire`, `message`, `url`, `age_collection` |
| 403 | type 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` |
| 405 | type 3, `expiration_time = t * 1000` | `t` |
| 406 | type 5 | `code` |
| 416 | type 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` |
| other | type 0 (generic logout path) | none |

Every failure also reads the optional logout UI fields `logout_message_header`, `logout_message_subtext`, `logout_message_locale`, `logout_main_button_text` / `_url`, `logout_secondary_button_text` / `_url` (`A17`). Mapping of the type ints to user-facing screens was not traced; account-ban semantics are covered by the ban report.

### 11.2 `<stream:error code="N">` (found, `C40601l6`, `C37961fH.A1B`)

| Case | Handling |
|------|----------|
| Any `stream:error` | `ConnectionThreadRequestsImpl/stream/error` logged with the first child; a message with `errorCode` is posted to `MessageHandler` |
| Code 500-599 | `MessageHandler` sets a flag and runs a reconnect pass (`onConnectionStreamError`) |
| Child `ack` | treated as an ack-kick: the pending stanza with that id is looked up, metrics emitted, the connection stops (`1t7` thrown) |
| Child `conflict type="device_removed"` | companion only: deregister (`C24100vp.A02`), unless state 9 |
| 515 / 516 (companion path) | forwarded as typed messages; the decompiled branch for 515 is unclear |
| `<error code="479">` | `smax-invalid` reported (`SmaxInvalidError`) |
| `<error class="status" id=...>` | fails the pending status ack callback |

### 11.3 Handshake and socket failures (found as log tags, reactions partly traced)

| Log tag | Cause |
|---------|-------|
| `socket/goaway` (`X.1sn`) | ServerHello length bytes equal `GOA` |
| `socket/invalid-certificate-exception` (`X.1so`) | cert chain check failed (5); calls `C37031dS.A0C` |
| `socket/disconnect/invalid-server-static-key` (`X.1sp`), `.../authKey` (`X.1sm`) | server static rejected; client static key problem |
| `socket/disconnect/noise` (`X.1sr`) | protocol exception (bad handshake data, TLV sizes); AEAD failure `X.1t9` and KEM input error `X.1tC` are rethrown into this family |
| `socket/disconnect/io`, `socket/closed`, `socket/error/EPERM` | I/O errors, blocked network |
| `connect/not-allowed/clock`, `software-expired`, `login-failed`, `quit-flag-set` | pre-connect gates |
| `ReaderThread/corrupt-stream-error` | bad node stream; `next-port/corrupt-stream-exception` advances the port |

---

## 12. Feature flags (ids as read in `AbstractC36791d3` and call sites)

| Id | Type | Controls |
|----|------|----------|
| **20161**, **34536** | int, string | PQ mode (1 enable, 2-4 enforce), PQ variant (default `IKKEM`) |
| **38643**, **15716** | string, bool | KEM choice (`MLKEM768` recognized), gate for it; effect unresolved |
| **33751** | bool | buffered writer for intro + ClientHello |
| **22916**, **30712**, **33512** | bool | disable HISTORY step; load last-success record; reuse stored port |
| **20801**, **23630**, **24645** | bool | step 5 fixed 443; steps 2-4 under SOCKS config; SOCKS service config source |
| **13545** | string | DNS resolver mode (`secondary` / `hardcoded` / `none`) |
| **7831**-**7834** | bool, ints | TCP keepalive enable and parameters |
| **15103**, **15270**, **15183**, **6493** | int, bool | ping timeout, intervals, scheduling method |
| **20485**, **22413** | bool | queue state in the payload |

All values are server-side; defaults are the compiled ones in the flag declarations.

---

## 13. Other transports

| Transport | State in 2.26.41.6 | Tier |
|-----------|--------------------|------|
| Tigon HTTP client | `com/crossapp/tigonhttp/TigonHttpClient*`, `com/facebook/tigon/**`, `com/whatsapp/infra/tigon/WAHucClient`, auth via `WATigonAsyncAuthServiceHolder`; HTTP/2 and HTTP/3 strings (`MNS/mvfst-mobile`, `MNS/ngtcp2`) in `libwhatsappmerged.so` | classes and strings found; per-feature use inferred |
| DistribGW (DGW) | `com/facebook/distribgw/client/*`, `RequestStreamDGWBuilder`; only app-side registration found: `WaFalcoStreamingRegistration.nativeRegisterStreaming(DGWClient)`; strings `distribgw_tigon_tunnel`, `DGW_MQTTBYPASS`, `XPLAT_RS_MQTT`, `XPLAT_RS_STARGATE`, `wa_request_stream` | found; wire format unknown |
| MQTT client | none; `mqtt` appears only in analytics event names and DGW stream-type labels | found |
| GraphQL over chatd | `com.whatsapp.pando.chatd.WAChatdGraphQLClient`, `WAChatdGraphQLCallbacks`, `WATigonMexdServiceHolder` | names found; rides chatd as an inferred w:mex path |

### 13.1 Tigon Noise channel (second Noise stack, native)

This is a different transport from chatd. Evidence is strings and class names, not decompiled logic.

- Carrier: WebSocket over the MNS network stack (`NoiseCarrierWebSocket`, `Stream0Listener`); numbered streams with a control stream 0 and chunk reassembly (`noise.framer.*`).
- Handshake outcomes (`NoiseHandshakeOutcome`): `LEGACY_PEER_VERIFIED`, `PRIVATE_AUTH_PEER_VERIFIED`, `ENROLLMENT_REQUIRED`, `KEY_REQUIRED`, `VERIFICATION_FAILED`; `NoisePrivateAuthMode`: `MIGRATION`, `REQUIRED`; errors such as `noise.handshake.attestation_failed`, `chip_binding_rejected`, `private_auth.vm_proof_failed`.
- Attestation: AMD SEV-SNP verifier (`NoiseSevSnpAttestationVerifier`, VCEK / ASK / ARK chain checks, chip id binding); labels `hatch.noise-auth.key.v1`, `.client-proof.v1`, `.vm-proof.v1`.
- Demand control: `NoiseConnectionDemandRejectionReason` `OFFLINE`, `BACKGROUND`, `PAUSED`, `SESSION_ENDED`, `RETRY_EXHAUSTED`, `INTERNAL`.
- Java users: `WaVmHttpTransportImpl`, `NoiseVmConnection` (path `/v1/noise`, steps `hatch-noise status=opening` / `result=ready`), `NoiseGatewayCarrier`. Purpose (HTTP-over-Noise to a confidential-compute VM for the agent browser) is inferred from names and attestation strings.

Nothing here shares code with the chatd handshake in section 4; the equal pattern name does not mean equal framing, prologue or payload.

---

## 14. Baileys (`baron-baileys-v2`, confirmed against its source)

| Aspect | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| Intro header | `NOISE_WA_HEADER = [87, 65, 6, 3]` | `57 41 06 03` |
| Pattern | `NOISE_MODE = 'Noise_XX_25519_AESGCM_SHA256\0\0\0\0'` | same 32-byte padded name |
| Server cert | `CertChain` decode; leaf signature checked with the intermediate key; intermediate checked with the pinned root `142375574d0a...da8ee6b`; `issuerSerial` must be 0 | same chain and the same root bytes; the APK additionally requires `leaf.issuerSerial == intermediate.serial` |
| Edge routing | stores `routing_info` from `<ib><edge_routing>`; appends it as query `ED=<base64url>` on `wss://web.whatsapp.com/ws/chat` | stores it (max 256 bytes); sends `45 44 00 01 len24 blob` raw before the intro |
| Keepalive | `<iq type="get" xmlns="w:p"/>` without children, default interval 30000 ms, connect timeout 20000 ms | same IQ; interval and timeout from server flags |
| Login payload | `passive`, `pull` true, `username`, `device`, `connectType WIFI_UNKNOWN`, `connectReason USER_ACTIVATED`, `lidDbMigrated false`, `releaseChannel RELEASE` | no `pull`, `connectReason` from session state, `releaseChannel BETA` in this build |
| Registration payload | `passive false`, `pull false`, `devicePairingData` | `devicePairingData` only for the companion registration connect |
| Transport | WebSocket frames | raw TCP, 3-byte length frames |

Confirmed differences that matter for an Android-style transport: the edge hint is a query parameter on the WebSocket URL in Baileys but a raw header before the intro on Android; Baileys does not enforce `leaf.issuerSerial == intermediate.serial`; Baileys sends `pull` and `passive` as true on login while the Android payload has no `pull`. Baileys keeps the server static key for a fast reconnect (a code comment names `NoiseIkSession`), matching the IK resume of section 4.4 in intent only; its wire form was not compared.

---

## 15. Error cases

| Symptom | Cause | Fix |
|---------|-------|-----|
| `GOA` in the first three bytes | server goaway during the handshake | try the next endpoint |
| `Handshake message does not contain server hello!` | first server frame is no ServerHello | check prologue and edge header |
| `noise certificate key does not match proposed server static key` | leaf key differs from the handshake static | verify the chain before ClientFinish |
| `server to client stanza fragmentation not supported` | flags bit `1` set | not supported by the client |
| `unexpected node received during login sequence` | first node is not `web`, `success`, `failure` | none |
| `noise-pq-static-key-decode-failed` | `static_pq_key` not valid base64 | key not stored, reported once |
| `scheduleReconnect backoff=...` | repeated failures | wait out the backoff or force a reconnect |

---

## 16. Key distinctions

| Do not confuse | Detail |
|----------------|--------|
| chatd Noise vs Tigon Noise channel | Java vs native, TCP vs WebSocket carrier, different purpose; the equal pattern name implies nothing about framing or payload |
| Intro header vs edge header | `WA 06 03` is hashed as prologue; `ED 00 01 len blob` is not part of the transcript |
| Edge host `eN.whatsapp.net` vs `routing_info` | hosts come from the client sequence; `routing_info` is an opaque blob replayed in the edge header |
| `fallback_hostname` / `fallback_ip4` / `fallback_ip6` | attributes of `media_conn` hosts (CDN), not chatd fallbacks; chatd fallbacks come from `<ib><fbip>` and the hard-coded table |
| `passive` payload flag vs `<passive/>` IQ | flag set at connect; the IQ switches to active mode afterwards |
| `devicePairingData` vs HTTP registration | pairing data belongs to the companion registration connect |
| Frame length vs list size | the 3-byte length wraps ciphertext; list size counts node slots |
| Protocol vs dictionary version | both in the intro: `06` and `03` |
| `stream:error` vs `failure` | `failure` answers the login; `stream:error` can arrive any time |

---

## 17. Complete flow

```
[Connection thread]  C37031dS.A0G picks step (history, g, g-fallback, hard-coded, eN, proxy)
     │  DNS ─► TCP connect ─► optional TLS wrapper
     ▼
[Client]  write [ED 00 01 len24 routing_info]?  [WA 06 03]        h = SHA256(name) ; h = SHA256(h || WA 06 03)
     │  frame1: HandshakeMessage{clientHello{ephemeral}}           mixHash(e_c)    (resume: + static + payload)
     ▼
[Server]  frame2: serverHello{ephemeral, static, payload}
     │  mixHash(e_s) ; mixKey(ee) ; s_s = decrypt(static) ; mixKey(es) ; cert = decrypt(payload)
     │  CertChain: leaf.key == s_s ; intermediate by pinned root ; leaf by intermediate
     ▼
[Client]  frame3: clientFinish{static = enc(s_c), payload = enc(ClientPayload)}      mixKey(se) ; split
     ▼
[Server]  [len24 | AES-GCM(flags | node)] ─► <success t props abprops lid pn static_pq_key/>  or  <failure reason/>
     ▼
[Client]  <iq xmlns="passive" type="set"><active/></iq> (+ pre-acks) ; steady state both ways, own counter per direction
     │  ping <iq xmlns="w:p"/> ; ib / notification / message / receipt / call ...
     ▼
[Failure]  stream:error / ping timeout / socket error ─► disconnect ─► Fibonacci backoff ─► next attempt
```

---

## 18. Unknowns

| Item | Status |
|------|--------|
| Wire traffic of any kind | nothing captured; no item is `tested` |
| IK resume and fallback transcript | structure found, steps inferred |
| PQ key placement in `ServerHello.payload`, TLV length width, library behind the ML-KEM calls | not decoded / not identified |
| What the TLS-wrapped endpoints carry inside TLS | inferred from code path |
| Ping and TCP-keepalive values | server flags |
| Failure type ints 0-15 to client screens; effect of flags **38643**, **15716** | not traced / unresolved |
| Payload fields without a writer (`webInfo`, `shards`, `fb*`, `accountType`, `testIsolationId`, `paddingBytes`, `pull`) | none found in this build |
| Tigon Noise channel handshake, framing; DGW wire protocol and users | native, strings only |
| Dictionary strings that are imported Java constants (for example `enc`) | not resolved in the index list |
