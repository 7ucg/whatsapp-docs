# WhatsApp Call Links — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-11-02
**Scope:** Guest call links (`call.whatsapp.com/{voice|video}/{token}`): the `link_query` / `link_join` handshake, the waiting room, the guest participant / JID allocation model, and the relay and key material handed to a guest at admission. This report covers the link/waiting-room/guest layer only; generic `<call>` envelope grammar, offer/accept/terminate, the call key, relay selection logic and the media path are covered in [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md) and referenced here, not repeated.

---

## 1. What it is

A call link is a token that lets a participant join a call without being invited by JID. The server resolves the token to a running or startable call and, if the call has a waiting room, holds the joiner there until let in. Everything in sections 3 onward below the stanza-shape tables is **tested**: read from a real wire capture of a client joining its own test call link, decrypted and decoded by the joining client itself (not interception of third-party traffic). APK statics (**found**) corroborate the parts the capture does not show, chiefly link creation. Server-side reasoning is **unknown** unless stated.

| Entity | Form | Set by | Tier |
|--------|------|--------|------|
| Link URL | `https://call.whatsapp.com/{voice\|video}/{token}` | client templates it around a token | found |
| Token | 22 chars, mixed-case alphanumeric (`Voip.kCallLinkTokenLength`=22) | creation call-site has no token parameter in Java; server-assigned is the working assumption | found (length), inferred (origin) |
| Call-id | 32 hex chars (16 bytes), e.g. `0076804DB4CA9D41EFCB547F08AE87BD` | server, returned in the `link_join` ack | tested |
| `is_guest_eligible` | bool on the link | host chooses it at creation (`CallLinkInfo.isGuestEligible`) | found (field), tested (wire value) |
| `waiting_room` `enabled` | bool on the link | host chooses it at creation (`Voip.createCallLink(..., waitingRoomEnabled)`) | found (field), tested (wire value) |
| Guest participant | a roster entry with `account_kind="guest"` and a server-allocated JID | server, at admission | tested |
| Call-domain JID | bare `call` domain before a call-id exists, `<call-id>@call` after | server | tested |

---

## 2. Evidence base

Two independent guest joins were captured end to end, both from an already-authenticated chatd connection (the joining session has its own identity on the wire) that deliberately calls the link path with a self-chosen display name and no disclosed identity, rather than joining as the account's own JID:

| | Video link | Audio-only link |
|---|---|---|
| Token | `7vEdtKy61dqCtbWAQ59zuO` | `ENcQnTAwKj7lQOdOHVJPmQ` |
| Call-id | `0076804DB4CA9D41EFCB547F08AE87BD` | `00BC509C0194CE83E26FA85A0319FD9C` |
| Call creator (host) | `48615137533978` device 24 | `21428363591910` device 0 |
| Guest push_name sent | `Baron als Gast ohne wa` | `Baron aus web testt` |

Both sessions address the host and the call-id's own creator with a JID shape `type=1, domainType=1` and no explicit `server` attribute; elsewhere in the same captures that same shape is paired, for the identical account, with an explicit `server="lid"` (e.g. the message-class receipt acks). Read together as: call signaling here runs over LID identities, consistent with [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md) §3.2's note that call stanzas tolerate a LID `to` against a different-domain `call-creator`.

What this capture does not show: a genuinely account-less browser session (no prior WhatsApp login at all) hitting the same link. The stanza shapes below are the call-signaling-layer protocol for a guest join; whether an anonymous web visitor's client produces byte-identical stanzas, or goes through an extra provisioning step first, is **unknown**.

---

## 3. Link creation (found, APK; not captured on the wire)

| Step | Class / method | Detail |
|------|-----------------|--------|
| Entry points | `CreateCallLinkBottomSheet` (standalone link), `EventCallLinkManager.createCallLink` (event-attached link) | both funnel into one manager |
| Manager | `CallLinkManager` (log tag), dispatches `actionCreateCallLink` / `actionCreateCallLinkForEvent` | |
| Native call | `Voip.createCallLink(isVideo, eventStartTimeSec, waitingRoomEnabled)` | 3 parameters only — no token, no explicit `media`/`guest` argument in the Java signature |
| Stanza assembly | native (`wa_call_link_create_v2`) | the `link_create` IQ itself is built below the JNI boundary, like every other call stanza (§2 of WA_CALL_SIGNALING.md) |
| Result | `CallLinkInfo` (creatorJid, token, videoEnabled, eventStartTsSec, isGuestEligible, linkState, waitingRoomState, self), populated from a native callback | token is read back, not supplied |
| URL | `AbstractC227619sp.A01(token, isVideo)`: `Uri.Builder().scheme("https").authority("call.whatsapp.com").appendPath(isVideo?"video":"voice").appendPath(token)` | client templates the share URL around the token it got back |

No `SecureRandom`/base62 generator code sits near `kCallLinkTokenLength` or `createCallLink` in Java, and the native library could not be decompiled. **Unknown**: whether the 22-char token is minted client-side and sent in `link_create`, or assigned by the server and returned in the ack — the client-visible call-site carries no token argument, which favors server-assigned, but this is **inferred**, not proven. `connected-limit` (seen on `group_info`, §6) is server-returned only; no client setter was found. No client-side rate limit on link creation was found.

---

## 4. Query and join (tested)

### 4.1 `link_query`

Sent bare, before any call-id is known, to the call-domain JID with no user part (`to: {user: null, server: "call"}`):

```
<call to="@call" id="...">
  <link_query token="7vEdtKy61dqCtbWAQ59zuO" media="video"/>
</call>
```

Ack:

```
<ack from="@call" class="call" type="link_query" id="...">
  <link_query link_creator="<host jid>" media="video" token="...">
    <guest is_guest_eligible="1"/>
    <waiting_room enabled="1"/>
  </link_query>
</ack>
```

`link_creator` identifies the host; `is_guest_eligible` and `waiting_room enabled` are the link's creation-time settings (§3) echoed back. No call-id yet — this ack only previews the link.

### 4.2 `link_join`

Carries the same `token`/`media`, plus a chosen `push_name` and the usual offer-shaped media children:

```
<call to="@call" id="...">
  <link_join token="7vEdtKy61dqCtbWAQ59zuO" media="video" push_name="Baron als Gast ohne wa">
    <audio enc="opus" rate="16000"/>
    <video dec="H264" device_orientation="0"/>
    <net medium="2"/>
    <capability ver="1">...7 bytes...</capability>
  </link_join>
</call>
```

The audio-only link's `link_join` (second capture) omits the `<video>` child entirely — confirmed by direct comparison, not inferred:

```
<link_join token="ENcQnTAwKj7lQOdOHVJPmQ" media="audio" push_name="Baron aus web testt">
  <audio enc="opus" rate="16000"/>
  <net medium="2"/>
  <capability ver="1">...</capability>
</link_join>
```

`push_name` is freeform text the guest chooses for this join; it is not the account's own WhatsApp display name (the joining account in both captures is a real logged-in session, but the chosen name differs from its normal profile name — guest identity is presentation-only at this stage). The `<capability>` 7 bytes observed (`01 05 F5 09 E0 BB 53` video guest, `01 05 F7 09 E0 3B 53` host) are session-specific values, not a general mask; WA_CALL_SIGNALING.md §5.2 already marks the Android capability byte values unknown in general and this does not resolve that.

Ack to `link_join` now carries a call-id — the server has resolved (or started) the call:

```
<ack from="@call" class="call" type="link_join" id="...">
  <waiting_room link-token="7vEdtKy61dqCtbWAQ59zuO" media="video"
                call-id="0076804DB4CA9D41EFCB547F08AE87BD"
                call-creator="<host jid>" enabled="1"/>
  <guest is_guest_eligible="1"/>
</ack>
```

### 4.3 Call-domain JID addressing (tested)

This resolves part of WA_CALL_SIGNALING.md §10.1, which left the call-domain JID type unidentified:

1. `link_query` / `link_join` address the bare domain `call` — no user part (`callDomainJID`).
2. The moment the `link_join` ack returns a `call-id`, the client starts addressing further in-call stanzas (waiting-room heartbeat, and later mute/transport/relaylatency/video) to `<call-id>@call` — a user-qualified JID under the same domain (`callJID`).
3. The server's own admission push (§5) later arrives `from="<call-id>@call"`, confirming the same addressing on the inbound side.

So the call-id, once learned, *is* the JID user-part for everything that follows — not a separate correlation key carried alongside addressing.

---

## 5. Waiting room (tested)

While waiting, the joined-but-not-admitted guest sends a periodic heartbeat to the call-id JID:

```
<call to="<call-id>@call" id="...">
  <heartbeat call-id="0076804DB4CA9D41EFCB547F08AE87BD" call-creator="<host jid>" type="waiting_room"/>
</call>
```
acked immediately (`<ack ... type="heartbeat"/>`, no content).

**Caveat on admission**: this capture is single-ended — it shows the guest's own connection only. The host-side action that admits a waiting guest (`waitingRoomAdmit`, sending a `waiting_room_toggle`/`_admit` stanza, per WA_CALL_SIGNALING.md §10.3) runs on the *host's* connection and was not observed here; this report only shows its result. In both captures, admission (§6) followed the single visible heartbeat within well under a second — fast enough that it is **unknown** whether this reflects an alert host tapping Admit immediately, or some auto-admit condition (e.g. host already active in the call); no evidence here distinguishes the two.

---

## 6. Guest JID allocation (tested)

Admission arrives as an ordinary `group_update`/`group_info` push from `<call-id>@call`, with two `<user>` entries — host and guest side by side:

| Field | Host entry | Guest entry |
|-------|-----------|--------------|
| `jid` | `48615137533978` (device 24 under `<device>`) | `29554559176938` (device 0) |
| `type` | `admin` | *(absent — no elevated role)* |
| `account_kind` | *(absent)* | `guest` |
| `push_name` | *(absent on this entry)* | `Baron als Gast ohne wa` — the name sent in `link_join` §4.2, copied verbatim into the roster |
| `state` | `connected` | `connected` |
| device `platform` | `web` | `web` |
| device `pid` | `0` | `1` |

The guest's JID (`29554559176938`) is in the same address-shape class (`type=1`, `domainType=1`, i.e. LID-style, §2) as the host's, allocated fresh by the server for this call — it is not the joining session's own account identity. Device `pid` (`1` for the guest) matches the relay block's `self_pid="1"` in the same stanza (§7) — the roster's per-device participant id and the relay's own participant id are the same number.

**Unknown**: whether this guest JID is reused across repeated joins of the same link by the same browser/session, how long it is held, or whether it is visible to the host beyond `push_name` and `account_kind`.

---

## 7. Relay and key handoff at admission (tested)

The same admission stanza carries a `<relay>` block, sibling to `<group_info>`, giving the guest everything needed to reach media without further round trips. Fields match the grammar in WA_CALL_SIGNALING.md §8.2; this section adds concrete wire-level detail that report left open.

| Child | Count seen | Notes |
|-------|-----------|-------|
| `<token id=N>` | 3 (ids 0, 1, 2) | raw binary, 194 bytes each |
| `<auth_token id=0>` | 1 | raw binary, 70 bytes |
| `<key>` | 1 | 24 wire bytes — but those 24 bytes are themselves ASCII text of a base64 string, which decodes again to a 16-byte raw key |
| `<hbh_key>` | 1 | 40 wire bytes — same pattern: ASCII base64 text, decoding to 30 raw bytes |
| `<te2 relay_id auth_token_id token_id domain_name relay_name c2r_rtt>` | 6 (2 relays: `edgeray-ham3-1.wt.whatsapp.com`/`ham3c01`, `edgeray-ber1-1.wt.whatsapp.com`/`ber1c01`) | no `<te>` present — confirms the "never both" rule, this call used `te2` |
| relay attrs | `attribute_padding`, `transaction-id`, `self_pid`, `uuid`, `participant_uuid` | `self_pid="1"` ties to the guest's own device `pid` in `group_info` (§6) |
| `<participant pid jid>` | not present | the 8.2 participant-id-to-JID mapping child was not seen in this 2-party capture; unknown whether it appears only in larger group calls |

Only `<key>` and `<hbh_key>` carry the double-encoded (binary-node-holding-ASCII-base64) form; `<token>` and `<auth_token>` are plain raw binary. What this double-layer buys over sending raw bytes directly is **unknown** (a leftover of a text-oriented transport internally, inferred).

A `<voip_settings uncompressed="1">` child, also a sibling of `<group_info>`/`<relay>`, carries an engine-parameter JSON blob (not compressed in this capture, consistent with WA_CALL_SIGNALING.md §5.2's note that compressed payloads are rejected on at least one path). Inside it, under the `fs` (feature-switch) object: `"guest_calling_logging_enabled": "true"` — the only guest-specific key found in an otherwise generic ~32 KB settings document (`aec`, `bwe`, `decode`, `encode`, `sfu`, `rc`, ... — all generic media-engine tuning, unrelated to guest joining). The telemetry events sent by the joining client around this call independently use the category string `guest_calling` (seen in the client's own `w:stats`/WAM blobs), matching the settings key's naming.

Two harmless siblings, `<uploadfieldstat/>` and `<userrate interval="0"/>`, ride along in the same stanza; no guest-specific content.

The client immediately sends a plain `<ack class="call" type="group_update">` for this push (no content) — ordinary handling per WA_CALL_SIGNALING.md §3.3 (group_update is not in the no-immediate-ack tag set).

---

## 8. Post-admission traffic (tested, brief)

Once admitted, traffic is indistinguishable from a normal call on the same call-id JID: `mute_v2` (host mutes the guest immediately after admission in this capture), `transport` (`transport-message-type="4"`, a `<net medium="2" protocol="0"/>` child), `relaylatency` (both directions, each carrying a `<te latency relay_name>` referencing the relay names from §7), and `video` state changes (`state="6"`, i.e. `Stopped` per WA_CALL_SIGNALING.md §13's `kVideoState*` table, repeated three times in quick succession during setup). None of this is link-specific; see WA_CALL_SIGNALING.md §§8, 13 for the general semantics.

---

## 9. Video vs audio-only link — differences observed (tested)

| Aspect | Video link | Audio-only link |
|--------|-----------|------------------|
| `link_query`/`link_join` `media` attr | `video` | `audio` |
| `link_join` children | `<audio>`, `<video>`, `<net>`, `<capability>` | `<audio>`, `<net>`, `<capability>` — `<video>` omitted |
| `waiting_room` ack `media` | `video` | `audio` |
| Waiting room / guest eligibility mechanics | identical | identical |

No other protocol difference was observed between the two; media type is carried end to end as a plain attribute, not a different stanza family.

---

## 10. Differences from a normal 1:1 or group call

| Aspect | Normal 1:1 / group call (WA_CALL_SIGNALING.md) | Guest link join (this report) |
|--------|------------------------------------------------|-------------------------------|
| Entry stanza | `offer` to a known peer/group JID | `link_query` then `link_join` to the bare `call` domain |
| Call key | per-device Signal-encrypted `Message.call.callKey` in the offer | not observed in this capture's admission; the guest receives relay/key material (§7) directly, not a Signal-wrapped call key — consistent with a guest having no pairwise Signal session with the host |
| Caller/callee identity | both sides are known JIDs before the call starts | the joining side's real identity is not exposed in the roster; server allocates a fresh JID and labels it `account_kind="guest"` |
| Admission | none — offer/accept is the only gate | optional waiting room: `waiting_room enabled`, held until an (unobserved, host-side) admit |
| Roster delivery | `group_info` inside the offer or a later update | `group_update`/`group_info` push from `<call-id>@call`, bundled with `<relay>` and `<voip_settings>` in the same stanza |
| JID addressing | peer/group JID throughout | bare `call` domain until a call-id exists, then `<call-id>@call` |

The missing per-device call key for the guest (row 2) is the most consequential difference and is **tested** only as an absence in this capture — not confirmed as a protocol rule; it is also consistent with WA_CALL_SIGNALING.md §9.2's note that group offers carry no per-device key and keys are re-shared out of band (`enc_rekey`). Whether a guest ever receives an `enc_rekey` was not observed in either capture window used here.

---

## 11. Error cases / gotchas

| Symptom | Cause | Fix / note |
|---------|-------|-----------|
| `link_query` ack has no `call-id` | the link has not been resolved to a running/startable call yet | normal for a bare preview; call-id arrives only in the `link_join` ack |
| Guest stuck after `link_join` ack, only heartbeats exchanged | waiting room is enabled and the host has not admitted yet | host-side action required; not visible from the guest's connection |
| `link_join` carries a `<video>` child for an audio-only link | client bug — the two captures show this child must be entirely absent for `media="audio"` | omit `<video>` for audio-only joins |
| Guest's own account JID appears in the call roster instead of a fresh guest JID | wrong join path (ordinary `offer`/group join rather than `link_join`) | use `link_query`→`link_join` to get `account_kind="guest"` handling |
| Guest receives no call key but has relay/key material | expected for this path (§10) — guest is not getting a Signal-wrapped key the way a normal callee does | do not treat it as a decryption failure |

---

## 12. Key distinctions

| Do not confuse | With |
|-----------------|------|
| Call-link **token** (22 chars, URL-facing) | Call-**id** (32 hex chars, protocol-facing, appears only after `link_join`) |
| Bare `call` domain JID (pre-call-id) | `<call-id>@call` (post-call-id) — both are "the call-domain JID" at different stages, not two unrelated addresses |
| `is_guest_eligible` (link setting: can *anyone* join this link as a guest) | `waiting_room enabled` (link setting: are guests held for admission) — independent flags, both echoed in the same acks |
| Guest `push_name` on `link_join` (freeform, chosen per join) | the joining account's own WhatsApp profile name (not what ends up in the roster for a guest join) |
| `<key>` / `<hbh_key>` wire bytes (binary node containing ASCII base64 text, double-decode needed) | `<token>` / `<auth_token>` wire bytes (plain raw binary, single decode) |
| Guest JID allocation (server-side, at admission, per call) | normal LID/PN JIDs (account-level, persistent) |

---

## 13. Complete flow (guest join, from capture)

```
[Guest client]  already has a chatd session (own identity, not used for the call)
     │  <call to="@call"><link_query token media/></call>
     ▼
[WA Server]  resolves the token
     │  ack: link_creator, media, token, <guest is_guest_eligible/>, <waiting_room enabled/>
     ▼
[Guest client]  <call to="@call"><link_join token media push_name><audio/>[<video/>]<net/><capability/></link_join></call>
     ▼
[WA Server]  starts/resolves the call
     │  ack: <waiting_room link-token media call-id call-creator enabled/>, <guest is_guest_eligible/>
     ▼
[Guest client]  learns call-id → addresses it as <call-id>@call from now on
     │  <call to="<call-id>@call"><heartbeat call-id call-creator type="waiting_room"/></call>  (repeats)
     ▼
[Host, out of band — not in this capture]  taps Admit (waiting_room_toggle/_admit)
     ▼
[WA Server]  <call from="<call-id>@call"><group_update><group_info ...>
                 <user host .../><user account_kind="guest" push_name jid=<allocated> .../>
              </group_info>
              <relay token×N auth_token key hbh_key te2×N/>
              <voip_settings uncompressed fs.guest_calling_logging_enabled=true/>
              </group_update></call>
     │  ack: <ack class="call" type="group_update"/>
     ▼
[Both]  ordinary call traffic on <call-id>@call: mute_v2, transport, relaylatency, video state
              (see WA_CALL_SIGNALING.md §§8, 13 for generic semantics)
```

---

## 14. Unknowns

| Item | Status |
|------|--------|
| Token generation site (client-minted vs. server-assigned) | `createCallLink` call site carries no token argument (found); true origin is native (unknown) |
| Whether a genuinely account-less browser session produces the same stanza sequence | not captured — both captures ran over an already-authenticated connection choosing to join as a guest |
| Host-side admit action (`waiting_room_toggle`/`_admit`) wire shape | not in this capture (single-ended); described only from WA_CALL_SIGNALING.md §10.3 statics |
| Why admission followed the single observed heartbeat so quickly | alert host vs. an auto-admit condition — not distinguishable from this evidence |
| Guest JID lifetime / reuse across repeated joins | not observed |
| Whether a guest ever receives `enc_rekey` or any Signal-wrapped call key | not observed in either capture window |
| `<participant pid jid>` mapping under `<relay>` | not present in this 2-party capture; unknown if group calls with guests use it |
| Purpose of double base64 encoding on `<key>`/`<hbh_key>` vs. raw `<token>`/`<auth_token>` | unknown |
| `connected-limit` as a client-settable cap vs. always server-assigned | no client setter found (found: server-returned only) |
| Rate limits / abuse controls on link creation or guest joins | nothing found client-side; server behavior unknown |
