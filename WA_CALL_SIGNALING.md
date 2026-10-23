# WhatsApp Call Signaling — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-24
**Scope:** Android voice/video call signaling: `<call>` envelope and acks, action stanzas (offer, accept, preaccept, reject, terminate, transport, relaylatency, enc_rekey, mute_v2, group_info, group_update, lobby, link_*, waiting_room_*, bcall), offer payload (audio / video / capability / encopt / net), call key and its Signal encryption, rekey (v2 / v3), media key derivation, relay and transport selection, ICE / STUN / DTLS / SRTP versus the WhatsApp-specific media path, group calls, call links and scheduled calls, call log and bcall messages, offer nack codes, reject and terminate behaviour, feature flags, Baileys comparison

---

## 1. What it is (technically)

Call signaling is a set of `<call>` stanzas on the normal chatd connection (see [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Every stanza carries exactly one action child. The Java layer does not build or parse call stanzas: a native VoIP engine does, and Java only (a) wraps outbound children into `<call>`, (b) Signal-encrypts the call key for each device, (c) hands inbound stanzas to the engine, (d) reacts to engine events. Media (RTP-like traffic to relays, ICE, DTLS, SRTP) is not signaling and runs on UDP/TCP sockets owned by the engine. All statements come from static analysis; nothing was captured on the wire. Tiers: **found** = read in Java or in native strings, **inferred** = deduced, **unknown** = not resolved.

| Layer | 2.26.41.6 name | Role |
|-------|----------------|------|
| JNI facade | `Voip` / `VoipNativeImpl` (`com.whatsapp.calling.voipcalling`) | 148 native methods (`startCall`, `acceptCall`, `rejectCall`, `nativeHandleIncomingSignalingXmpp`, ...) |
| Outbound hook | `OutgoingSignalingHandler` implements `SignalingXmppCallback.sendCallStanza(Jid, callId, VoipStanzaChildNode)` | engine to Java; per-tag handling, call-key encryption |
| Envelope writer | `CIX` (queue), `C27410BtV` (call stanza), writer-thread case 206 in `HandlerThreadC21920sG` | builds `<call to id>` |
| Inbound handler | `C40641lA` (`CallStanzaHandler`), `BQU` (parsed call stanza), `C83` (decrypt), `C28120CKj` / `RunnableC29343CoU` (dispatch to engine) | parse envelope, decrypt `<enc>`, feed engine |
| Engine events | `VoipEventCallback`, `VoiceServiceEventCallback` (116 callbacks) | engine to UI / state |
| Crypto callback | `DefaultCryptoCallback`, `SignalIdentityCryptoCallback` (`CryptoCallback`) | HKDF / HMAC / random / Ed signatures for the engine |
| HTTP signaling | `VoiceTeeHttpSignalingHandler` (`SignalingHttpCallback`) | alternative signaling carrier, TEE request |
| Native engine | `libwhatsapp.so` (unpacked from the superpack archive `libs.so`; exports `Java_com_whatsapp_calling_voipcalling_Voip_*`) | stanza serializers / deserializers, call state machine, transport, media |

Points that decide the rest of the report:

- The stanza grammar lives in native code: serializers `serialize_*` (C/C++) and a Rust crate `call_control` (source paths `xplat/wa-voip/rust/call_control/src/stanza_deserializer/...` in its panic strings) for inbound parsing. The voip library could not be decompiled; every native statement rests on strings and exported names only (found strings, inferred meaning).
- Java is a thin shim, which is why the tag set seen in Java (10 tags in `sendCallStanza`) is much smaller than the set the engine understands (section 4).
- The call key is minted and used by the engine; Java encrypts it with the ordinary pairwise Signal session (section 6). The same HKDF code the engine needs is a Java callback (section 7).
- The WhatsApp-specific media path (relay allocate/bind, "WARP" packets, hop-by-hop SRTP, SFrame for group calls) is distinct from the WebRTC-style ICE/DTLS path, which exists as a "web_p2p" mode (section 8).

---

## 2. Java / native interface

Callbacks registered at start (found): `SignalingXmppCallback.sendCallStanza(to, callId, node)` (engine to Java, one call child); `CryptoCallback` (`generateE2EKeysV2`, `getSecureSsrc`, `hkdfSha256`, `hmacSha256`, `generateRandomBytes`; `SignalIdentityCryptoCallback` adds `signWithIdentityKey` with a 64-byte signature and `verifySignature` with a 32-byte key); `SignalingHttpCallback` (`sendMsg(callId, bytes, requestType)`, `cancelMsg`; types voice session 0, codec avatar 1); `VoipEventCallback` (section 13). `VoipStanzaChildNode` is the JNI-visible tree (tag, attributes, children, data); Java converts it to and from the chatd node whose binary encoding is described in [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) section 8.

| JNI entry (found) | Fed by | Notes |
|-------------------|--------|-------|
| `nativeParseXmppOffer(CallOfferInfo[], ...)` | `preprocess_call_offer` (`AbstractC24816AmW`) | parses an offer without starting a call; `CallOfferInfo`: callId, fromJid, groupJid, callLinkToken, isVideoCall, isAudioChat, isJoinableCall, isOfferExpired, isCallEnded, silenceReason, groupPhash, participantHash, callGroupInfo |
| `nativeHandleIncomingXmppOffer` | `C28120CKj` | starts incoming-call handling |
| `nativeHandleIncomingSignalingXmpp` / `...Ack(from, type, errorCode, children, ..)` / `...Receipt` | `RunnableC29343CoU` (message 192) | every non-offer action, acks of own stanzas (return 70004 is logged as corrupt ack), call receipts |
| `peekIncomingOffer`, `handleIncomingTerminatePush` | push path | pre-ring decision, terminate delivered by push |
| `handleIncomingSignalingHttp(callId, bytes, ..)` | TEE HTTP response | alternative carrier (11.3) |

---

## 3. Envelope, acks, receipts

### 3.1 Outbound `<call>` (found, `HandlerThreadC21920sG` case 206)

```
<call to="<jid>" id="<stanza id>">
  <ACTION .../>                      exactly one child
</call>
```

`to` must pass `C0DZ.A0R` (user, device and a few other JID types; `C27410BtV` throws `CallStanza:Wrong jid type` otherwise). The stanza id comes from the shared id generator. Log line `WriterThread/write/call-stanza-<tag>`.

### 3.2 Inbound `<call>` (found, `C40641lA`)

| Attribute | Handling |
|-----------|----------|
| `from` | must be a valid JID, else `CallStanza from invalid jid`; a user JID is mapped to its primary device |
| `id` | stanza id, used for the ack |
| `t` | seconds, multiplied by 1000 |
| `e` | integer seconds, multiplied by 1000 and passed to the engine next to `t` (exact meaning unresolved; inferred offer age / expiry input) |
| `offline` | integer; presence marks delivery from the offline queue |
| `notify`, `platform`, `version` | passed on (caller push name, platform, app version) |
| `participant` | device JID of the sender in group contexts; a malformed value falls back to `from` |
| `sender_lid` | read when `from` is a LID-domain JID |
| child `call-creator` | device JID (required for non-offer logic) |
| child `call-id` | required; except tags `reminder` and `bcall_*`, which get an empty call id |
| other attributes | `caller_pn` (phone-number device JID), `username`, `caller_country_code`; read only when the creator is LID and the tag is not `offer` |

If `to` and `call-creator` are in different address domains (one LID, one phone number) the client logs `CallStanzaHandler/call-mixed-domain/...` and reports metric `CallMixedDomainStanza`, then continues (found). Mixed domains are tolerated, not rejected.

### 3.3 Acks

| Case | Behaviour (found) |
|------|-------------------|
| tag not in {offer, accept, reject, enc_rekey, terminate} | Java sends an ack immediately: `<ack class="call" type="<tag>" id to [participant]/>` (`AbstractC47181wT.A01`) |
| tag in that set | no immediate Java ack; the node goes to a separate pending-ack path (`C36591ch.A0G`); semantics not resolved |
| ack to an own stanza | `nativeHandleIncomingSignalingXmppAck(from, type, errorCode, children, ...)`. Ack types seen in Java: offer (carries relay data, section 8), accept, link_join, link_query, lobby; native also handles link_create, link_edit, remove, remove_user, heartbeat, screen_share, add_extension, remove_extension, relaylatency, video state, waiting_room_* |
| offer ack with error 435 | extra action scheduled after the ack (purpose not resolved) |
| offer / accept delivery | Java waits for the chatd delivery ack with a timeout (flags 9257, 9431); on timeout the stanza is dropped and logged `Call stanza delivery timed out` |

### 3.4 Dictionary tokens (found, `AbstractC40911lb`)

Single-byte (`A00`): `call` 97, `call-id` 101, `call-creator` 68, `terminate` 208, `relaylatency` 70, `video` 86, `audio` 158, `capability` 177, `device-identity` 227, `privacy` 223, `te` 212, `te2` 198, `token` 194, `key` 155, `participant` 5, `user` 14, `remove` 172, `notify` 24, `registration` 170, `attribute_padding` 229, `relay_id` 130, `token_id` 143. Secondary dictionary 0 (`A01[0]`): `offer` 28, `accept` 97, `preaccept` 18, `transport` 44, `mute_v2` 253, `group_info` 170, `group_update` 99, `net` 103, `medium` 36, `encopt` 21, `keygen` 26, `voip_settings` 10, `relay` 116, `joinable` 75, `heartbeat` 6, `transaction-id` 62, `uuid` 132, `self_pid` 71, `peer_pid` 76, `metadata` 118, `uncompressed` 20, `rate` 29, `dec` 73, `screen_width` 5, `reason` 46. Secondary 1: `reject` 0, `enc_rekey` 205, `e` 235.

Not in any dictionary of this build (plain strings on the wire): `lobby`, `flowcontrol`, `screen_share`, `link_*`, `peer_state`, `interruption`, `reminder`, `raise_hand`, `waiting_room_*`, `hbh_key`, `auth_token`, `lightweight`, `silence`, `scheduled-id`, `group-jid`, `link-token`, `caller_pn`, and `enc`.

---

## 4. Action taxonomy

Inbound tags the native deserializer dispatches (found, string list in `call_control`): `offer`, `accept`, `preaccept`, `reject`, `terminate`, `transport`, `relaylatency`, `enc_rekey`, `notify`, `flowcontrol`, `interruption`, `group_update`, `mute_v2`, `screen_share`, `raise_hand`, `reconfigure_bot`, `user_action`, `ready`, `relay_info_update`, `tos`, `screen`, `switchable`, `add_extension`, `waiting_room_update`, plus `receipt`. Acks parsed: offer, accept, video state, relaylatency, link_create / edit / query / join, lobby, heartbeat, remove, remove_user, screen_share, add_extension, remove_extension, waiting_room toggle / admit / deny / leave.

| Tag | Direction (found) | Purpose |
|-----|-------------------|---------|
| `offer` | out / in | start a call (section 5); in: also offers for already ended calls with `is_call_ended` and `terminate_hint` |
| `preaccept` | out / in | callee device is ringing / ready; engine state `PRE_ACCEPT_RECEIVED`, event `preacceptReceived` |
| `accept` | out / in | callee accepts; carries media params and a certificate (native strings `error parse voip params for accept`, `error parsing certificate for accept`) |
| `reject` | out / in | callee declines; reason strings in section 14.2 |
| `terminate` | out / in | end call; transaction id and `call_summary` (section 14.3) |
| `transport` | out / in | candidates, ICE credentials, certificate, health (section 8.5) |
| `relaylatency` | out / in | measured relay latencies (section 8.4); has its own ack |
| `enc_rekey` | out / in | call key re-share (section 6.4) |
| `video` (state) | out / in | video on / off / upgrade; `kVideoState*` values (section 13); ack carries relay info |
| `notify`, `peer_state`, `flowcontrol`, `interruption`, `ready`, `heartbeat` | out / in | in-call state: peer notices, network health, flow control, interruptions, group heartbeat |
| `mute_v2`, `raise_hand`, `user_action`, `tos`, `reconfigure_bot` | out / in | mute request in group calls, hand raise, user actions, group-call TOS, bot reconfigure (`req_id` attr) |
| `group_info`, `group_update` | in (child of offer / ack / update) | roster (section 9) |
| `lobby` | out / in | group call lobby query / state; its ack carries group info |
| `screen`, `screen_share`, `switchable` | out / in | screen-share state; device-switch (`switch_info`, `root_call_id`, `root_call_creator`, `peer_active_device`) |
| `add_extension`, `remove_extension` | out / in | add a media endpoint ("extension") to a call (section 9.4) |
| `remove`, `remove_user`, `cancel_offer` | out | remove participants; cancel an offer for chosen participants |
| `link_create`, `link_edit`, `link_query`, `link_join` | out | call links (section 10) |
| `waiting_room_toggle`, `_admit`, `_deny`, `_leave`, `_update` | out / in | link-call waiting room (section 10.3) |
| `reminder`, `bcall_*` | in | server reminders; business-call family (section 11) |
| `dtmf`, `duration`, `connect_stat`, `group_call_duration`, `group_call_tos_accepted` | out | serializers present in the engine |

Java-visible tags in `sendCallStanza` (found): `offer`, `accept`, `reject`, `terminate`, `video`, `enc_rekey`, `lobby`, `link_join`, `link_query`, `link_create`; every other tag takes the default send path.

Numeric message-id table (85 types), mechanism split (child / ack / receipt / internal) and fixed header lengths: not found in this build. The engine exposes tags and per-tag serializers, not an id enum visible in strings. Treat any id table as unknown for Android.

---

## 5. Offer

### 5.1 Build and send (found)

`startCall(...)` makes the engine emit `sendCallStanza(peer, callId, offerNode)`. Java:

1. `sendOfferStanza` stores the stanza id (`outgoingCallOfferKey`), waits while a pre-key job for any destination device is pending, then encrypts the call key per device on a worker (`getBulkEncryptedE2EKeys`, section 6.1).
2. Result is written either in the new format (`<destination><to jid><enc/></to>...</destination>`, via `AbstractC33466EhY.A08`) or the old format (single `<enc>` child, only valid for one device; `cannot have multiple encrypted messages in old format!`).
3. If any device got a `pkmsg`, `<device-identity>` (bytes of `adv_signed_identity` from the companion preferences) is appended; this happens only when the self device passes `BRD()` (registration device id nonzero, i.e. a companion; inferred).
4. `CIX.A02` queues the `<call>` stanza; flag **9257** (ms) bounds delivery wait.
5. After the send, a call ping IQ is scheduled (flag **30890**, delay **30891** ms default 3000, attempts **32651**); if the connection is down the client reconnects, unless the call is no longer in state `CALLING`.
6. If the destinations cannot be encrypted the offer is kept as `pendingCallOfferStanza` and sent later (`maybeSendPendingOffer` when a pre-key job ends, `sendPendingCallOfferStanza` on terminate). `preSendTerminate` drops an unacked offer from the retry queue before a terminate goes out.

### 5.2 Children and attributes

| Element | Source | Attributes / content |
|---------|--------|----------------------|
| `<offer>` | send | `call-id`, `call-creator` (device JID); receive: `caller_pn`, `username`, `caller_country_code`, `group-jid`, `scheduled-id`, `joinable`, `lightweight` (`1` = lightweight / audio-only group ring), `rering_ts`, `is_call_ended`, `type` |
| `<audio>` (repeats) | send | `enc` (codec), `rate` (sample rate); `enc` and `rate` are dictionary tokens |
| `<video>` | send | `enc`, `dec`, `device_orientation`, `screen_width`, `screen_height`; value strings seen in the engine: `h.264`, `vp8`, `vp8/h.264`; attribute `fps` also present as a string (inferred video attribute) |
| `<net>` | send | `medium` (network type), later `health_status` in transport |
| `<capability>` | send | `ver` + opaque bit mask (`pjmedia_voip_capabilities_*`: version, `bit_mask_length`); per-device `vid_dec` string lists decodable video codecs (`vid_codec_capability_str_to_bitmask`) |
| `<encopt>` | send | `keygen` = key generation version; engine rejects other values (`Unsupported keygen ver`); versions 2 and 3 exist (section 6.4) |
| `<destination>` / `<to jid>` / `<enc>` | send | per-device encrypted call key (section 6.1); `<to>` may carry `peer_recipient_lid`, `peer_recipient_pn`, `peer_recipient_username`, `eph_setting` |
| `<tctoken>` | send | inside `<to>`, at most once per user, when flag **20605** is on and fewer than **20606** users already carry one; same token family as [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `<device-identity>` | send | ADV signed identity bytes, see 5.1 step 3 |
| `<privacy>` | receive | privacy token (token name present in dictionary); contents not traced |
| `<relay>` | receive / ack | relay list (section 8) |
| `<voip_settings>` | receive / ack | server-provided engine parameters; attribute `uncompressed`; compressed payloads rejected in one path (`unexpected compressed voip params`) and `zlib inflate` is linked (compression format inferred) |
| `<metadata>` | receive | peer A/B test bucket attributes (`peer_abtest_bucket`, `peer_abtest_bucket_id_list`) |
| `<silence reason>` | receive | offer is silent (no ring); `BQU.A02`; reason ints `kOfferSilenceReason*` (section 13) |
| `<group_info>` | receive | roster of a group call (section 9) |
| `<terminate_hint>` / `<call_summary>` | receive | an offer for a call that already ended (`is_call_ended=1`): `terminate_reason`, transaction id, summary |
| `<link_info>`, `<waiting_room>`, `<bot>`, extension info | receive | link, waiting room, bot and extension data |

The exact byte values of `<capability>` and of the `net medium` codes were not recovered from this build (a 7-byte mask `01 05 F7 09 E4 BB 13` is sometimes quoted for web clients; it is not present as a contiguous literal in the Android library, so treat the Android value as unknown). The engine bundles the codecs it names in strings: Opus plus an in-house low-bitrate codec ("mlow", Opus-framed), OpenH264, VP8, AV1 (`wzav1`) and HEVC through MediaCodec.

### 5.3 Receive path (found)

1. `CallStanzaHandler` builds `BQU`; metric `CallStanzaHandler/handleStanza tag=... callId=...`; message 192 is posted to the dispatcher.
2. For an offer, `preprocess_call_offer` runs `nativeParseXmppOffer`; non-zero return drops the stanza. Expired or ended offers are not rung.
3. `C83.A00` decrypts the `<enc>` (section 6.2), then `nativeHandleIncomingXmppOffer` starts the call; state `RECEIVED_CALL`.
4. `peekIncomingOffer` (push-driven pre-check) ignores silenced offers, group offers (`group_info` present), offers with `is_call_ended=1`, 1:1 offers without `<enc>` and offers while the phone is busy; flag **4217** bit 1 enables voice peeks, bit 2 video peeks.
5. A later `terminate` or push `handleIncomingTerminatePush` ends a peek.

---

## 6. Call key and its encryption

### 6.1 Outbound (found, `getBulkEncryptedE2EKeys`)

The engine delivers a map device JID to raw call key bytes. For each device without a pending pre-key job the client builds a `Message` protobuf and Signal-encrypts it with the existing pairwise session (`C83` / `CallableC29363Coo`):

| Message.Call field | Number | Type | Set when |
|--------------------|--------|------|----------|
| `callKey` | **1** | bytes | always (32 raw bytes) |
| `conversionSource` / `conversionData` / `conversionDelaySeconds` | **2** / **3** / **4** | string / bytes / uint32 | CTWA data present |
| `ctwaSignals` / `ctwaPayload` | **5** / **6** | string / bytes | CTWA data present |
| `contextInfo` | **7** | ContextInfo | CTWA flag (`externalAdReply.adType` set to a fixed value) |
| `nativeFlowCallButtonPayload` | **8** | string | call started from a native-flow button |
| `deeplinkPayload` | **9** | string | call started from a deeplink |
| `messageContextInfo` | **10** | MessageContextInfo | per-peer enrichment by `AbstractC30999De0` (content not traced) |
| `callEntryPoint` | **11** | uint32 | flag **24935**, only on the initial fanout (`i == 0`) |
| `callReason` | **12** | string | present in the proto, not set in this path |

`Message.call` is field **10** of `Message` (`C30628DTw`), class `Message.Call` = `C25827BCl`. For the initial offer, flag **520** adds ad-attribution context from the CTWA resolver (`C35832FfR`; inferred). A fanout runs with `i == 0` for offers and `i == 1` for rekeys. Encryption is blocking with a cancel path; a block above 5000 ms logs `voip_e2e_encryption_blocked`.

Wire form of one device (found, `AbstractC33466EhY.A03/A09`): `<enc v="<version>" type="msg|pkmsg|skmsg|frskmsg|msmsg" [count="<retry>"] [mediatype] [session_type="pq"] [bucket]>CIPHERTEXT</enc>`. `session_type="pq"` marks a post-quantum Signal session; `count` is omitted when 0. Call keys are never group sender-key messages in this path (type `skmsg` is accepted by the helper but no call path produces it; inferred).

Extension devices (JID user prefix `01`) use `sendReKeyToExtension`: a prekey bundle buffered earlier is processed, the key is encrypted as `pkmsg` with `v="2"` (found).

### 6.2 Inbound (found, `C83.A00`)

| Step | Detail |
|------|--------|
| children read | `registration` (must be 4 bytes; Signal registration id, used for retry), `device-identity`, `enc` |
| duplicates | a second `<enc>` is dropped (`duplicate <enc>`) |
| retry count | `count` on `<enc>`; missing value aborts (`invalid retry count`) |
| type | `msg` 0 or `pkmsg` 1 accepted; other numbers log `unrecognized ciphertext type` |
| decrypt | pairwise Signal decrypt (pre-key message processed with the sender's device identity); payload parsed as `Message`, `call.callKey` taken; `ExternalAdReplyInfo.adType` of CAWC is logged |
| result | `<enc>` replaced by a plain `<enc>` node holding the call key bytes for the engine |
| failure | `rejectedDecryptionFailure` event, `onPeerE2EDecryptionFailed` retries session setup (fetch a new pre-key when the registration id is equal and the base key repeats); the reject reason `enc` is sent when the call cannot be decrypted |

Flag **24063** changes the session-type path used for hosted-type ciphertexts (inferred from the `c33281EeX.A04` condition).

### 6.3 Retry

`sendOfferRetryRequest(device)` makes the engine resend the offer (`resendOfferOnDecryptionFailure`); `sendPendingRekeyRequest` repeats a rekey request while the stored retry byte is within 0..4. `count` therefore ranges 0 to 4 (found, `sendPendingRekeyRequest`).

### 6.4 `enc_rekey`: three shapes

| Shape | Evidence | Content |
|-------|----------|---------|
| v2 unicast | `sendReKeyStanza` (Java) | engine emits `<enc_rekey call-id call-creator transaction-id><enc count=N>RAW KEY</enc></enc_rekey>`; Java replaces the child by the Signal-encrypted `<enc>` for the target device (found) |
| v2 fanout | `sendReKeyFanoutStanza` | target is a group; child `<destination><to jid><enc/></to>...`; each entry encrypted separately (found) |
| v3 | native strings `handle_enc_rekey_v3`, `make_and_send_rekey_v3`, `ext_rekey: ...` | payload is a protobuf with repeated `wa.voip.RekeyKeyEntry` (key type + key); keys per type have a fixed length (`key type %d has unexpected length`); selected when keygen is 3; requires extension support (`kCallExtensionMV1`); v3 to v2 transition logged |

Rules visible in strings: rekeys carry a transaction id; early, old or equal ids are ignored (`ignore old rekey msg with transaction id`); in a one-to-one call incoming `enc_rekey` is ignored (`ignore rekey msg in one to one call`); `request_keys` asks the creator or an extension to resend keys (v3 only; `request_keys with unexpected keygen` is ignored). Which side starts a rekey in a group call, and the exact trigger, are not resolved.

---

## 7. Media key derivation

### 7.1 Java callbacks (found)

| Callback | Computation |
|----------|-------------|
| `generateE2EKeysV2(callKey[32], out[46], info)` | HKDF-SHA256, salt = 32 zero bytes, IKM = call key, info = UTF-8 `info` string supplied by the engine, 46 output bytes (`E2E_EXTENDED_V2_KEY_LENGTH`) |
| `hkdfSha256(salt, ikm, info, out)` | generic HKDF-SHA256 (first arg salt, second IKM, third info; output length = `out.length`) |
| `getSecureSsrc(ikm, info, salt[4], out[4])` | HKDF-SHA256 to 4 bytes (`SECURE_SSRC_LENGTH`) |
| `hmacSha256(key, data, out[32])` | HMAC-SHA256 |
| `generateRandomBytes(out)` | `SecureRandom` (source of the 32-byte call key; inferred) |

### 7.2 Labels and contexts in the engine (found strings, role inferred)

`e2e sframe key`, `hbh srtp key`, `uplink hbh srtcp key`, `downlink hbh srtcp key`, `warp auth key`; functions `derive_sframe_key`, `derive_hbh_srtp_key`, `derive_and_update_warp_mi_keys`, `derive_extension_per_media_key`; key slots `owner_e2e_key`, `extension_audio_key`, `extension_video_key`, `extension_appdata_key`.

| Key | Source (inferred) | Protects |
|-----|-------------------|----------|
| E2E SRTP material | `generateE2EKeysV2` output (46 bytes), per participant | media between endpoints (1:1) |
| SFrame key | label `e2e sframe key` | frame encryption in group / SFU calls and the hop-by-hop data channel (`wa_sframe_encrypt`, `sframe_keyprovider_set_chainkey`) |
| hop-by-hop SRTP / SRTCP | relay-provided `hbh_key` (section 8.2) with the `hbh ...` labels | client to relay leg only |
| WARP MI key | label `warp auth key` | message-integrity tag of WARP packets (`warp_mi_tag_len`) |

Key layouts (which of the 46 bytes is key or salt, per direction), the `info` string content and the exact HKDF chains for SFrame / hop-by-hop were not recovered: the callers are in native code that could not be decompiled. A device-qualified JID as `info` is plausible but unverified (**unknown**).

---

## 8. Relay, transport and media path

### 8.1 What the client receives

Relay data arrives in the offer ack (caller; `error during parsing relay info`, `Failed to parse relay info in offer ack`), in the offer itself (callee), and later in `relay_info_update` and in the ack of a `video` state change (found).

### 8.2 `<relay>` grammar (found, `fill_relay_info` strings)

| Item | Name | Notes |
|------|------|-------|
| relay attrs | `uuid`, `self_participant_uuid`, `conn_id`, `medium`, `warp_mi_tag_len`, `prefer_relay`, `prefer_ipv6`, `peer_dl`, `smart_transport_signal`, `attribute_padding` | per relay set |
| tokens | `<token>` (`token_id`) list, at least one required (`relay_token_list.num_tokens < 1`) | relay credential; list copied into the allocate request |
| auth tokens | `<auth_token>` (`auth_token_id`) | used instead of a token when the id is in range; otherwise "falling back to relay token" |
| key | `<key>` | relay password material |
| `hbh_key` | child with raw or base64 bytes | hop-by-hop key source; size is checked (`HBH Key of unexpected size`, "though warp_mi_tag_len = ...") |
| endpoints | `<te>` or `<te2>` | never both (`can not receive both te and te2 endpoints`); address bytes IPv4 or IPv6 (`endpoint too short for an IPv6 address`); empty address rejected |
| per endpoint | `relay_id`, `relay_name` (truncated if too long), `domain_name`, `latency`, `c2r_rtt`, `ul_bw`, `dl_bw`, `is_favored` | `latency` seeds relay choice |
| participants | `<participant pid jid>` | maps participant ids used in WARP / SFU packets |

Log strings print relay addresses through a `[MetaServiceIP]` placeholder, so relay addresses are treated as service IPs.

### 8.3 Relay selection (found strings, logic inferred)

1. The client binds to the offered relays (`wa_transport_p2p_start_relay_binds`; bind / alloc requests are STUN-style, `wa_stun_*`, transaction ids `tid=0x...`; bind and unbind need message integrity).
2. Latency is measured by ping requests per relay (`Ping request sent to relay N`), a TCP prober (`wa_transport_tcp_prober_*`) and allocate round trips; the best becomes the "elected relay" (`Elected relay idx=...`, `wa_transport_get_elected_relay_approximate_e2e_rtt`); an arbiter (`wa_transport_path_arbiter_*`) switches paths, and `prefer_relay` forces relay use.
3. A server reflexive address learned from the allocate response is logged (`Server reflexive addr`).
4. Peer-to-peer is attempted in parallel by candidate pairs (`p2p add_cand_pair`, `e2e bind probe`); relay stays as fallback.

### 8.4 `relaylatency` (found)

Serializers and handlers: `serialize_relay_latency`, `send_or_enqueue_relay_latency`, `handle_relay_latency`, `unpack_and_apply_relay_latency`, batched (`prepare_batched_relay_latencies`), with ack parsing `relaylatency ack: call_id is empty / has invalid type`. The stanza reports the sender's measured RTT per relay index to the peer, which applies it (`apply_relay_latencies`, thresholds `Ignored higher relay latency ...`). Latency is skipped in group-call offers (`Skip relay latency at call offer in group calls`).

### 8.5 `transport` (found strings)

Attributes and children: `transport-message-type`, `p2p-cand-round` (a restart increments the round and clears remote candidates), `ice-ufrag`, `ice-pwd`, `<certificate algorithm fingerprint>` (`cert_algorithm`, `cert_fingerprint`), `health_status`, candidate entries (address, priority). The string `Web P2P: skipping type 13 send` shows message type 13 belongs to the web-P2P ICE / DTLS exchange. The other subtype numbers were not recovered (**unknown**).

### 8.6 Two media paths

| Aspect | WhatsApp relay path (default) | web-P2P path |
|--------|-------------------------------|--------------|
| Setup | relay allocate / bind (STUN-style), tokens from signaling | ICE credentials and DTLS certificate fingerprint exchanged in `transport`; `wa_ice_transport`, `CreateDtlsTransport` |
| Packet form | WhatsApp packets with RTP payload ("WARP", `warp_mi` integrity tag, piggyback, FEC, `warp_rtx`) | RTP over DTLS-SRTP |
| Hop key | relay `hbh_key` (hop-by-hop SRTP / SRTCP, hop-by-hop DTLS to the relay `hbh_dtls_handshake_*`) | DTLS-derived |
| E2E | E2E SRTP in 1:1, SFrame in group (SFU) | SRTP |
| Purpose | normal app-to-app calls | interop with the web client (`set_peer_is_web`, `handle_transport_web_p2p`); inferred |
| TLS stack | statically linked mbedTLS (`mbedtls_ssl_*`, `mbedtls_gcm_*`, `mbedtls_hkdf`) | same |

Group calls use an SFU with subscriptions (`RxSubscriptions`, `SenderSubscriptions`, `wa.voip.*` protobufs inside the data channel) rather than per-peer paths; bandwidth estimation runs per path (`wa_warp_sfu_*`, "one side BWE").

---

## 9. Group calls

### 9.1 `group_info` (found, `shared_elements/group.rs` strings)

| Item | Name | Notes |
|------|------|-------|
| attrs | `connected-limit`, `phash`, `transaction-id`, `media`, `joinable` | roster hash and ordering id; `group_info has invalid connected_limit` |
| members | `<user jid [user_pn push_name guest_name account_kind state ..]>` with `<device jid ..>` children, or `<participant jid pid>`; `<bot jid>` | `<user>` and `<participant>` together is an error |
| per user | `state`, `pid`, `capability` (`ver`), `rekey`, `terminated`, `connected`, `country_code`, `reason` | device lists required for non-nacked users |
| extensions | `extension_creator`, `ext_creator_identity_key_sig`, `extension_id`, `hn_video`, `gen`, `cohost`, `scope` | extension / co-host data |

### 9.2 Behaviour

- Limit `Voip.kMaxSupportedGroupCallParticipants` = 64 (found); the engine terminates a call whose update exceeds the maximum.
- `group_update` and group-call `terminate` carry transaction ids; obsolete or out-of-order ones are ignored; `kInitialGroupTransactionId` = -1 (found).
- The group offer carries no per-device call key; keys are re-shared per device with `enc_rekey` (inferred from `sendReKeyFanoutStanza`).
- Ringing and roster actions: `invite`, `inviteToGroupCall`, `cancelInviteToGroupCall`, re-ring (`rering_ts`, `make_and_send_cancel_offer_for_participants`), `sendRaiseHand`, `sendMutePeerRequestInGroupCall`, `sendRemoveRequest`; `lobby` is the join step of a running group call (`joinOngoingCall`).
- Extensions: `add_extension` / `remove_extension` attach a second media endpoint to a call (`wa_call_extension_jid_*`, owner and extension keys in 7.2, `kCallExtensionMV1`; Java treats extension JIDs with user prefix `01` specially, 6.1). The device class is unresolved (inferred: a paired wearable, the app ships `libsmartglasses-bundle.so` and `Voip.sendWearableAttribution`).

---

## 10. Call links, waiting room, scheduled calls

### 10.1 Links (found)

| Item | Value |
|------|-------|
| URL | `https://call.whatsapp.com/{voice|video}/{token}`; manifest host `call.whatsapp.com` |
| token length | `Voip.kCallLinkTokenLength` = 22 |
| create | `Voip.createCallLink(isVideo, eventStartTimeSec, waitingRoomEnabled)` (log `actionCreateCallLink` / `actionCreateCallLinkForEvent`); native `wa_call_link_create_v2` rejects a bad start time |
| edit / preview | `editCallLink(token, ..., startTime, int)`, `previewCallLink`, `queryCallLinkForLinkEdit`; stanzas `link_edit`, `link_query` |
| join | `joinCallLink` sends `link_join`; ack `LinkJoinAck` carries `call-creator`, `group_info`, `voip_settings`, link info |
| link states | `kCallLinkState`: None 0, QuerySent 1, QueryAcked 2, JoinSent 3, JoinAcked 4 |
| `CallLinkInfo` | creatorJid, token, videoEnabled, eventStartTsSec, isGuestEligible, linkState, waitingRoomState, self |
| nack events | `linkCreateNacked`, `linkQueryNacked`, `linkJoinNacked`, `linkEditNacked` with the ack error code |

Link stanzas are addressed to a call-domain JID (the Rust JID parser lists `callDomainJID` and `callJID`; the JID type accepted by `C0DZ.A0R` that corresponds to it was not resolved).

### 10.2 Event (scheduled) calls

An event call is a call link created with a nonzero `eventStartTimeSec` (found). The offer for a scheduled call carries `scheduled-id` (found in the parser). `Message` carries two chat messages:

| Message field | Number | Type | Content (found) |
|---------------|--------|------|-----------------|
| `scheduledCallCreationMessage` | **61** | ScheduledCallCreationMessage | `scheduledTimestampMs` 1, `callType` 2 (UNKNOWN 0, VOICE 1, VIDEO 2), `title` 3 |
| `scheduledCallEditMessage` | **65** | ScheduledCallEditMessage | `key` 1 (MessageKey), `editType` 2 (UNKNOWN 0, CANCEL 1) |

Only cancel exists as an edit. Local storage (found): tables `message_scheduled_call` (`scheduled_timestamp_ms`, `call_type`, `title`), `message_add_on_scheduled_call_edit` (`creation_message_row_id`, ...), `message_system_scheduled_call_start` (`call_title`, `call_timestamp_ms`), `scheduled_calls` (`key_chat_row_id`, `key_id`, `scheduled_timestamp`, `is_upcoming`, `call_log_row_id`). The server-side reminder (a `reminder` call child, `kServerReminder*` below) and how the creation message links to the call-link token are not resolved.

### 10.3 Waiting room

Stanzas `waiting_room_toggle` (`link-token`, `media`, `enabled`, active-call variant), `_admit`, `_deny`, `_leave`, `_update`; parsed user fields `jid`, `user_pn`, `push_name`, `guest_name`, `is_guest_eligible`, `state`. Java: `waitingRoomAdmit`, `waitingRoomAdmitAll`, `waitingRoomDeny`, `waitingRoomToggle`; events `waitingRoomAdmitAcked`, `waitingRoomDenyAcked`, `waitingRoomStateChanged`, `waitingRoomDenied`. `kServerReminder`: Legacy 0, LinkJoinedCreator 1, LinkJoinedJoiner 2, LinkConnectedCreator 3, LinkMissedCreator 4, LinkCreatorWaitingRoomJoined 5, LinkCreatorWaitingRoomMultipleJoined 6.

---

## 11. bcall, bot and alternative carriers

### 11.1 `bcall` chat message (found)

| Field | Number | Type | Use |
|-------|--------|------|-----|
| `sessionId` | **1** | string | business-call session |
| `mediaType` | **2** | enum | UNKNOWN 0, AUDIO 1, VIDEO 2 |
| `masterKey` | **3** | bytes | required: missing key throws `bcall message doesn't have master key` |
| `caption` | **4** | string | optional |

`Message.bcallMessage` = field **72** (class `DSA`); handler `F2V` (`FMessageBCallProtobuf`) maps it to message type 91 with session id, media type (0 unknown, 1 audio, 2 video), caption and master key bytes. The `master key` is a key delivered inside an end-to-end encrypted chat message; what it keys (inferred: the media of a business call) is not traced. Engine events `bCallCreated(callId, key, ...)`, `bCallJoined`, `bCallEnded`, `bCallAudienceUpdated`, `bCallCreateFailed`; `CallState.BCALL_STARTING`; incoming `<call>` children named `bcall_*` get an empty call id (3.2). Native `bcall_start`, `bcall_notify` strings exist.

### 11.2 Bot calls and HTTP / TEE signaling

Bot calls: `CallInfo.isBotCall`, `<bot>` nodes in `group_info`, `verifyIncomingBotIdentityKey`, `reconfigure_bot` (`req_id`), bot TOS flow (nack 488); the offer is merged with a cached payload builder. Context: [WA_META_AI.md](WA_META_AI.md). Separately, `SignalingHttpCallback.sendMsg` lets the engine exchange opaque signaling bytes through `TeeRequestHandler` instead of chatd (`handle_http_tee_start_session_response`, `handle_http_create_extension_response`); request types voice session and codec avatar. Eligibility and payload format are **unknown** (inferred: bot and avatar sessions).

---

## 12. Call log and history

### 12.1 `callLogMesssage` (Message field **69**, class `C49434Loq`, found)

| Field | Number | Type | Values |
|-------|--------|------|--------|
| `isVideo` | **1** | bool | |
| `callOutcome` | **2** | enum | CONNECTED 0, MISSED 1, FAILED 2, REJECTED 3, ACCEPTED_ELSEWHERE 4, ONGOING 5, SILENCED_BY_DND 6, SILENCED_UNKNOWN_CALLER 7 |
| `durationSecs` | **3** | int64 | |
| `callType` | **4** | enum | REGULAR 0, SCHEDULED_CALL 1, VOICE_CHAT 2 |
| `participants` | **5** | repeated `CallParticipant` | `jid` 1 (string), `callOutcome` 2 (same enum) |

Builder `C53129Nna` (found): the engine's call-log result (`Voip.kCallLog*`) maps as follows.

| `kCallLog` result | Wire `callOutcome` |
|-------------------|--------------------|
| Canceled 1, Missed 2 | MISSED |
| Unavailable 3 | FAILED |
| Rejected 4 | REJECTED |
| Connected 5 | CONNECTED |
| AcceptedElsewhere 6, ScreenedElsewhere 9 | ACCEPTED_ELSEWHERE |
| Invalid 0, Failed 7, ConnectedLonely 8, others | ONGOING (decompiled default branch) |
| DND flag / unknown-caller flag on the record | SILENCED_BY_DND / SILENCED_UNKNOWN_CALLER (checked first) |

Failed 7 mapping to ONGOING looks wrong but is the decompiled default branch; treat it as read, not as verified behaviour. Call type: local type 1 maps to SCHEDULED_CALL, 2 or 3 to VOICE_CHAT, else REGULAR. A missing call type throws `call log message missing call_type`.

### 12.2 Local database (found)

Tables: `call_log` (`jid_row_id`, `from_me`, `call_id`, `transaction_id`, `timestamp`, `video_call`, `duration`, `call_result`, `is_dnd_mode_on`, `bytes_transferred`, `group_jid_row_id`, `is_joinable_group_call`, `call_creator_device_jid_row_id`, `call_random_id`, `call_link_row_id`, `call_type`, `offer_silence_reason`, `scheduled_id`, `telecom_uuid`, `terminated_by_device_switch`), `call_log_participant_v2` (`call_log_row_id`, `jid_row_id`, `call_result`), `joinable_call_log` (`call_id`, `joinable_video_call`, `group_jid_row_id`, `phash_identifier`, `self_other_device_connected`, `is_lgc_add`), `message_call_log`, `call_unknown_caller`, `reminder`. Feeding events: `callEnding(CallLogInfo, ..)`, `update1to1CallLog`, `updateJoinableCallLog` (`kUpdateJoinableCallLogType` Create 1, Update 2, Delete 3).

---

## 13. Engine states and constants (found, `Voip.java`, `CallState`)

| Group | Values |
|-------|--------|
| `CallState` | NONE, CALLING, PRE_ACCEPT_RECEIVED, RECEIVED_CALL, ACCEPT_SENT, ACCEPT_RECEIVED, ACTIVE, ACTIVE_ELSEWHERE, REJOINING, LINK, CONNECTED_LONELY, PRECALLING, ENDING, BCALL_STARTING, SCREENING |
| `kCallLog*` | Invalid 0, Canceled 1, Missed 2, Unavailable 3, Rejected 4, Connected 5, AcceptedElsewhere 6, Failed 7, ConnectedLonely 8, ScreenedElsewhere 9 |
| `kCallEndReason*` | Unknown 0, Timeout 1, Self 2, RejectDoNotDisturb 3, RejectBlocked 4, MicPermissionDenied 5, CameraPermissionDenied 6 |
| `kFatalReason*` | Unknown 0, ParticipantAllocationFailure 1, CallSetupError 2, CallTxTimeout 3, CallRxTimeout 4, VideoStreamCreateError 5, VideoPortCreateFailed 6, NoSamplingRatesForAudioRecord 7, AudioInitError 8 |
| `kOfferSilenceReason*` | None 0, Privacy 2, Lightweight 3, ScreenSharing 4, AddedAsLinkCreator 9, AddedForDeviceSwitching 10, GroupChatAdd 11 |
| `kParticipant*` | Connected 1, Incoming 2, Ringing 3, Rejected 4, Terminated 5, TimedOut 6, CreatingCall 7, Invited 11 |
| `kVideoState*` | Disabled 0, Enabled 1, Paused 2, UpgradeRequest 3, UpgradeAccept 4, UpgradeReject 5, Stopped 6, UpgradeRejectByTimeout 7, UpgradeCancel 8, UpgradeCancelByTimeout 9, UnknownPeer 10, Xr2dCodecAvatarEnabled 12, Error 20 |
| `kStatus*` | Success 0, InvalidArgument 70004, Exists 70015, Ignored 70020, CallAlreadyStarted 670001, CallNotActive 670007, CallHasNoVideo 670018, GroupCallUserExists 670021, GroupCallPeerCodecMismatch 670033, GroupCallUserExistsNotInvited 670038, NotPermitted 670040, UserNotRemovable 670041, UserNotConnected 670042 |
| `kScreenShareVersion*` | Legacy 0, 1 to 4 |
| `kNetworkHealth*` | Measuring 0, NoNetwork 1, Poor 2, Average 3, Good 4 |

`kCallEndReason` ints are what the UI sees; the strings placed on the wire for terminate are not among the library strings (14.3).

---

## 14. Errors, reject, terminate

### 14.1 Offer nack codes (found, `VoiceServiceEventCallback.callOfferNacked`)

An offer ack with errors calls `callOfferNacked(errors[])`. A single error 304 or 400 is treated as a duplicate offer and ignored. The nack is fatal when the call is `CALLING` / `CONNECTED_LONELY` and all recipients (or self) were nacked, or the code is 432; otherwise per-recipient and non-fatal.

| Code | Fatal path (decompiled branch) | Non-fatal path |
|------|-------------------------------|----------------|
| 401 | not-allowed screen (reason id 3) | |
| 403 | not-allowed screen, video-specific id when video | |
| 404 | not-allowed id 16 | "contact unavailable" text per recipient |
| 405 | id 4 | |
| 406 | id 2 (audio) / 11 (video) | |
| 411 | id 11, or 37 for lightweight | |
| 412 | id 10; group info refreshed on membership mismatch | |
| 426 | id 1 (audio) / 9 (video) | |
| 427 | id 12, or 36 for lightweight 1:1 | text per recipient; in groups above 4 participants an alternate id |
| 428 | id 14 | text per recipient |
| 429 | UI event only | |
| 431 | id 15 | "not available" text |
| 432 | id 2; always fatal | |
| 435 | | text per recipient; after an offer ack also triggers an extra action |
| 460 / 463 | video 10 / audio 2; 463 id 17 | |
| 488 | bot TOS not accepted: opens the bot TOS flow | same |
| 467, 468, 469 | | id 46 for multiple recipients |
| 500, 502 | | "not available" text |
| 538 | | id 35 |
| other | default id (video 8 / 0) | assertion `Unknown error code` |

The decompiled fatal branch has lost some returns, so the ids are indicative only; the code list and the fatal / non-fatal split are firm. Meanings of the codes beyond the client reaction are server side (**unknown**). After a complete-offer nack the engine sends no call stanza except `terminate` (found string).

### 14.2 Reject reasons (found, `Voip.REJECT_REASON_*`)

| String | Meaning / client reaction |
|--------|---------------------------|
| `` (empty) | declined |
| `busy` | callee busy; busy tone, call ends after a delay |
| `unavailable` | constant defined; main use found in presence / availability code |
| `uncallable` | peer cannot be called; not-allowed screen |
| `tos` | peer has not accepted the TOS; not-allowed screen |
| `enc` | decryption of the call key failed |
| `server_conf_corrupted` | server configuration unusable |

`rejectCall(callId, reason, int)` and `rejectPendingCall` are the entry points; `callRejectReceived` consumes inbound reasons. Reject reasons are mapped to local call results (`reject_reason_to_call_result`, `set_call_term_reason_from_received_call_reject_reason`).

### 14.3 Terminate (found strings)

- `terminate` carries a transaction id and a `call_summary` node (user states, duration); an offer for an ended call carries `terminate_hint` with `terminate_reason`, `call_summary` and a transaction id. Whether `terminate` itself has a `terminate_reason` attribute is not resolved.
- Terminate from a companion device is ignored by the engine; the primary fans a terminate out to multi-device peers (`fanout_terminate_if_peer_is_md`).
- A device switch terminate in the wrong state is ignored; "handled elsewhere" outcomes are derived from the reason (`get_handled_elsewhere_outcome_from_terminate_reason`) and conflicting outcomes for the same call id are ignored.
- RTCP BYE on the media path also ends a call (`rtcp_bye_terminate_delay`), and server-side extension removal does (`extension terminated by server`).
- Java sends `terminate` with retry (queued across reconnects) when flag **8003** is on and the call is not a bot call or in lonely state; otherwise without retry (branch partly unclear in the decompiled output).
- The terminate `reason` string values (and any mapping from `kCallEndReason`) are not in the library strings and were not found elsewhere in the APK (**unknown**).

---

## 15. Feature flags (ids as read at call sites; names unresolved)

| ID | Type | Controls |
|----|------|----------|
| **9257** | long ms | offer delivery timeout; stanza dropped on timeout (`CIX.A02`) |
| **9431** | long ms | accept delivery timeout; also remembers the accept stanza id so `preSendTerminate` can cancel it |
| **9432** | bool | on accept timeout trigger a reconnect |
| **8003** | bool | terminate with retry (14.3) |
| **15125** | bool | report metric `call_stanza_drop` |
| **30890** | bool | send outgoing-call ping after offer |
| **30891** | long ms | ping timeout, default 3000 |
| **32651** | int | ping attempts, minimum 1 |
| **31086** | bool | outgoing offer tracker |
| **24935** | bool | write `callEntryPoint` into `Message.call` |
| **520** | bool | add ad-attribution context to `Message.call` (inferred) |
| **20605** / **20606** | bool / int | add `<tctoken>` to call destinations; cap on users per stanza |
| **24063** | bool | decrypt session-type selection for a ciphertext class (inferred) |
| **4217** | int mask | peek incoming offers: bit 1 voice, bit 2 video |
| **3094** | int mask | bit 8 = async call events (`kFlagEnableCallEventAsync`); paired with **9210** (bool) |
| **7481** | bool | group-call muted-notification state for linked group calls |
| **13630** / **13804** | int / bool | sampling for a decrypt metric (inferred) |

Engine parameters (`p->enable_sframe_tx`, `tp->web_p2p_bitmap`, `tp->enable_e2e_bind_probe_bitmap`, `options.wa_log_time_series`, ...) come from the server `voip_settings` and are read through `Voip.getVoipParam`; their names are strings in the library, their values are server side.

---

## 16. Baileys (`baron-baileys-v2`, source read, nothing tested)

| Topic | Baileys | Android |
|-------|---------|---------|
| Offer | `offerCall`: random 32-hex `call-id`, `call-creator` = own id, `<audio enc=opus rate=16000/8000>`, `<video enc=vp8 dec=vp8 ...>` (video), `<net medium=3>`, `<capability ver=1>` 6 bytes `01 04 FF 83 CF 04`, `<encopt keygen=2>`, `<destination>` with Signal-encrypted `Message{call{callKey}}`, `count=0`, `device-identity` when a pkmsg is produced | same elements; Android builds the offer in the engine, capability bytes unknown (5.2) |
| Envelope | `<call id to>` for offer; reject / accept / terminate use `from` + `to` without `id` | `<call to id>` always (3.1) |
| accept | `<accept call-id call-creator count=0/>`, no children | engine accept carries media params and a certificate (section 4) |
| terminate | `reason="user-terminated"`, `count=0` | reason strings unknown (14.3) |
| rekey | `<enc_rekey ...><enc v=2 type=msg/></enc_rekey>` | v2 shape matches 6.4; v3 absent |
| Inbound | decrypts `<enc>` (`unpadRandomMax16`, `Message.decode`), caches the offer, emits call events; media / relay tags only acked | Android decrypts with the same envelope and feeds the engine |
| Links | `link_create media` (+ `event start_time`) to `@call`; `waiting_room_toggle`; `link_join token` | grammar matches names found here; target JID type not resolved |
| Terminate statuses | maps `terminate reason` strings `Timeout`, `RejectDoNotDisturb`, `MicPermissionDenied`, `CameraPermissionDenied`, `RemoteBusy`, `RemoteOffline` | these strings are not in the library; the names resemble `kCallEndReason` (**inferred** link) |

Baileys has no relay allocation, no WARP / SRTP / SFrame, and no engine, so it can signal and ring but cannot carry media. Whether an offer without the full engine parameters is accepted or rung by the peer was not tested.

---

## 17. Error cases

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Wrong jid type` for a call stanza | `to` is not a user / device / call-domain JID | address the device or user JID |
| offer sent `without enc`, peer does not ring | call key not encrypted (no session, pre-key job pending) | build sessions first; Android keeps the offer pending |
| `duplicate <enc>` / `invalid retry count` / `invalid registration` | malformed `<enc>`; `registration` not 4 bytes | one `<enc>` with `count`; `registration` only on retry |
| offer nack 304 / 400 | duplicate offer | ignore |
| offer nack 401 / 403 / 463 | caller not allowed to call this peer | none on the client |
| offer nack 412 / 488 | group membership differs / bot TOS not accepted | refresh group info / accept the bot TOS |
| reject `enc` | callee could not decrypt the call key | resend the offer after session repair (`count` > 0) |
| `Unsupported keygen ver`, `can not receive both te and te2`, `num_tokens < 1` | invalid `encopt`, relay endpoints or tokens | send keygen 2 or 3, one endpoint family, at least one token |
| `bcall message doesn't have master key` | `masterKey` missing | include it |
| `Call stanza delivery timed out` | no chatd ack within flag 9257 / 9431 | stanza dropped; accept may reconnect (flag 9432) |

---

## 18. Key distinctions

| Do not confuse | With |
|----------------|------|
| `Message.call` (field 10, E2E call key inside a Signal message) | `callLogMesssage` (69, outcome record), `bcallMessage` (72, business session key) |
| `<enc>` in a call stanza (pairwise Signal ciphertext) | `skmsg` sender-key messages and media encryption |
| E2E SRTP / SFrame keys (from the call key) | hop-by-hop keys (from the relay `hbh_key`) |
| Relay `<token>` / `<auth_token>` (allocation credentials) | `<tctoken>` (privacy token inside `<to>`) |
| `kCallEndReason` ints (UI), `kCallLog*` (engine result) | terminate reason strings (wire, unknown), `callOutcome` enum (wire) |
| `CallLogMessage.CallType` REGULAR / SCHEDULED_CALL / VOICE_CHAT | `ScheduledCallCreationMessage.CallType` UNKNOWN / VOICE / VIDEO |
| `enc_rekey` v2 (Signal `<enc>` child) | `enc_rekey` v3 (protobuf `RekeyKeyEntry` list) |
| WhatsApp relay path (WARP, hop-by-hop SRTP) | web-P2P path (ICE + DTLS-SRTP) |
| Event call (link with start time) | scheduled-call chat messages (61 / 65) |
| Signaling over chatd | HTTP / TEE signaling for bot and avatar sessions |

---

## 19. Complete flow (1:1 call)

```
[Caller app]  startCall(callId, peer, video, ...)
     │
     ▼
[Native engine]  mints 32-byte callKey ; builds <offer> (audio, video, net, capability, encopt keygen)
     │  sendCallStanza(peer, callId, node)
     ▼
[OutgoingSignalingHandler]  per device: Message{call{callKey,...}} → Signal encrypt → <enc>
     │  <destination><to jid><enc/></to>…</destination> [tctoken] [device-identity if pkmsg]
     ▼
[CIX / writer]  <call to id><offer call-id call-creator>…</offer></call>     (delivery timeout, flag 9257)
     │
     ▼
[WA Server]  (not observed) enriches the offer: relay, voip_settings, metadata, privacy
     ├──────► [Caller]  offer ack: <relay> tokens, endpoints, hbh_key ; voip_settings ; or nack (14.1)
     ▼
[Callee]  <call from t e offline><offer/></call>
     │  CallStanzaHandler → nativeParseXmppOffer → C83 decrypt <enc> → callKey → ring (RECEIVED_CALL)
     ▼
[Callee]  preaccept ─► [Caller] PRE_ACCEPT_RECEIVED ;  accept (media params, certificate) ─► ACCEPT_RECEIVED
     │
     ▼
[Both engines]  relay allocate / bind with tokens ; transport / relaylatency / relay_info_update
     │  E2E keys from callKey (HKDF) ; hop-by-hop keys from hbh_key ; optional P2P pair or web_p2p DTLS
     ▼
[Media]  WARP packets via the elected relay or P2P ; ACTIVE ; in-call video, mute_v2, notify, heartbeat
     │
     ▼
[Either side]  terminate (transaction id, call_summary) ─► ack class="call" type="terminate"
     ▼
[Both]  callEnding(CallLogInfo) → call_log row / callLogMesssage ; teardown ; RTCP BYE
```

Group call differences: the offer carries `group_info` and no per-device key; late joiners use `lobby` / `link_join`; rekeys travel as `enc_rekey` (v2 fanout or v3) with transaction ids; media goes through an SFU with SFrame.

---

## 20. Unknowns

| Item | Status |
|------|--------|
| Native stanza builders / parsers, HKDF `info` strings, key layouts | voip library not decompiled; strings only |
| Capability bytes, `net medium` codes, codec parameter defaults | not recovered |
| `transport-message-type` values other than 13 | not recovered |
| Terminate `reason` strings, reject-to-end-reason mapping | not found |
| Meaning of envelope `e`, offer ack error 435 side action | unresolved |
| 85-type numeric message-id table | not present in this build's strings |
| Extension device class, v3 rekey trigger, group rekey trigger | unresolved |
| Link-call JID type, scheduled-call link to token | unresolved |
| TEE / HTTP signaling payload and eligibility | unresolved |
| Server behaviour (enrichment, nack semantics, relay choice) | server side |
| Traffic | nothing captured |
