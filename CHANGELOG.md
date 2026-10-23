# Changelog

Newest first. Versions refer to the analysed WhatsApp Android APK.

## Unreleased
- New reports (APK 2.26.41.6): `WA_WAM_ANALYTICS.md`, `WA_AB_PROPS.md`, `WA_LOCAL_STORAGE.md`, `WA_MESSAGE_SECRETS.md`.
  - WAM: 4 channels, 1,008 event classes; regular upload is a `w:stats` IQ, private upload uses blinded credentials; buffer files are little-endian TLV with a `WAM` v5 header; per-event weights arrive in the AB-props response.
  - AB Props: 21,424 flag ids in five typed default maps, shared id space with WA Web; `params_map_v4_u<N>` is a unit type, not a value width.
  - Local Storage: `meta_ai_memory`, `start_chat_trust_signals`, `wa_trusted_contacts` and `wa_biz_integrity_signals` live in `wa.db`; only `integrity_chat_info` is in msgstore; no SQLCipher.
  - Message Secrets: zero-salt HKDF over original id, target sender, modifier and use case; reactions are encrypted only in `group_type == 3` groups; comments need a LID sender.
- Ban System: 34166 is an injection id, not a feature flag.
- New report (APK 2.26.41.6): `WA_BROADCAST_LISTS.md`.
  - Lists exist server-side: the client restores them with a `w:b` get-lists IQ; there are also delete and quota IQs; list ids cannot start with a leading zero.
  - The only cap with a reader is the server-provided monthly quota (<= 300); GAP is receive-side inbox evaluation, not a send limit.
- New reports (APK 2.26.41.6): `WA_USYNC.md`, `WA_GROUP_HISTORY.md`.
  - USync: Android has no `bot` protocol; a hidden status is `type="fail"` with 401/403/404; `sid`, `index`, `last` are always sent; contact sync also exists as MEX mutations.
  - Group History: the bundle carries no `<meta appdata>`, only the separate "history sent" notice (type 118) does; the 14-day window is server-set and not verifiable from the client.
- Username: the USync reason context for `UsernameUpdateNotification` is `NOTIFICATION_SIDELIST` (mode `query`), not a delta-style sync.
- New report (APK 2.26.41.6): `WA_MEDIA_UPLOAD.md`.
  - Upload is a raw `POST` with `Content-Range` resume; the `token` is `SHA-256(random secret || hash)`; HKDF derives 80 bytes, not 112.
  - Channel media uses the `newsletter` prefix, the plaintext hash as path and no encryption; `NON_E2EE` media uses HKDF info `non-e2ee-media-key`.
  - `media_conn` carries no content-length limit; the WebP sandbox is gated by flag 26414; full upload (0-39) and download (0-34) result tables.
- New report (APK 2.26.41.6): `WA_CALL_SIGNALING.md`.
  - Java is a thin shim over a native call engine; the HKDF for media keys runs in a Java callback; signaling can also use an HTTP/TEE carrier.
  - `enc_rekey` v2 carries a Signal `<enc>` child, v3 is protobuf; mixed LID/phone-number addressing is tolerated.
  - The 85-id table and the 7-byte capability mask from third-party notes are not present on Android.
- New report (APK 2.26.41.6): `WA_NOISE_TRANSPORT.md`.
  - chatd is raw TCP, not WebSocket; the Noise state machine and AES-GCM are Java; intro header is `WA 06 03`.
  - Outbound stanzas are DEFLATE-compressed; reconnect backoff is Fibonacci x 10 s, capped at 48 h.
  - A second, native "Tigon Noise" channel exists next to chatd; no MQTT client found.
- New report (APK 2.26.41.6): `WA_APPSTATE_SYNC.md`.
  - `critical_block` holds profile/locale/security-notification settings, not a block list; `contact` and `lid_contact` are in `critical_unblock_low`.
  - ProtocolMessage field numbers from the proto extractor are off by one: key share 7, key request 8, fatal notification 10.
  - A snapshot-MAC mismatch inside a patch is non-fatal on the new (KMP) path; two engines coexist, all KMP flags default to false.
- New report (APK 2.26.41.6): `WA_ACCOUNT_SECURITY.md`.
  - The native OPAQUE code serves the encrypted-backup password; the account password uses an RSA/AES `#PWD_WA:11` envelope.
  - `SetPassword` / `CheckPassword` have no call site in this build; `libvoprf-*` belongs to ACS tokens.
  - "Account recovery" means Meta canonical-user credentials; several passkey variables differ from third-party notes.
- Multilingual website: full translations of all reports and the landing page in German, Spanish, Brazilian Portuguese, Russian, Arabic (right-to-left) and Turkish, with a language switcher. Outdated translations are flagged automatically (`translations/check.py`, `build.py`).
- New reports (APK 2.26.41.6): `WA_REPORTING.md`, `WA_CLIENT_INTEGRITY.md`, `WA_LINKED_DEVICE_PAIRING.md`, `WA_USERNAME.md`.
  - Reporting: reason and jid are one merged `spam_list`; call reports are type 20; error 548 treated as success.
  - Client Integrity: attestation data is produced and sent but never blocks the client; install-source and root checks exist only as telemetry.
  - Linked-Device Pairing: pair-code flow uses an outer X25519 exchange; ADV signing is curve25519 + HMAC-SHA256; device-limit flag 15550.
  - Username: doc_ids come from a persisted-ids asset, not Java; default username key is 4 digits or 6 uppercase alphanumerics.
- Second verification pass on 2.26.41.6 closed most open items.
  - Ban System: bans do arrive over XMPP in the login `<failure>` node (reasons 402/403/405/406/416), the old "no XMPP ban signalling" claim was wrong; business-account gate corrected; 97 SpamFlow categories; appeal is a Graph request by doc_id with a `purpose_public_keys` fetch.
  - TCToken/CSToken: confirmed proto fields (`NctSaltSyncAction.salt`=1, `HistorySync.nctSalt`=19, `Conversation.tcToken`=21); 299 is the IQ request type, not a flag; Web-only claims marked.
  - Meta AI: `meta_ai_memory` table, Hatch capabilities 76/77/79 behind flags 37227/37852/37054, six Hatch request examples; Baileys section reduced to confirmed facts.
- All three reports re-verified on APK 2.26.41.6 and given a "Changes vs 2.26.26.4" section.
  - TCToken/CSToken: cstoken HMAC and stanza injection found in Java (flag 24941); salt generated locally, companions get it via App-State-Sync; tctoken request IQ carries no token bytes; new class names and 13 new flags.
  - Ban System: BizIntegrityQuery doc_id now `28596420510007620`; new request shape; DTO `C51530MtC` with 17 fields (`isMetaVerified`, `fmxBusinessHoldoutGroup`); WFAC UI moved to `com.whatsapp.waffle.wfac.ui`; new section 10 (appeal payload).
  - Meta AI: `richResponseMessage` is field 97 (not 77); `$1` is appended to the persona ID, not the routing JID; bot fields on `Message`/`WebMessageInfo`, not ContextInfo; Hatch requests ride `ProtocolMessage.aiMetadataOperation` (31); Manus JID gone; no Meta AI chunk reassembly.

## 2026-07-16 — APK 2.26.26.4
- `e17f399` Meta AI: remove APK class table, fix Baileys import.
- `7811cb4` Add `WA_META_AI.md` (JIDs, flags, proto fields, request/response protocol, Baileys fix).
- `f83ffe2` Add `WA_TCTOKEN_CSTOKEN.md` (TCToken, CSToken/NCT, NctSalt sync, Baileys implementation).
- `9353ad0` Add `WA_BAN_SYSTEM_DEEP_EN.md` (WFAC lifecycle, BizIntegrityQuery, suspicious marking, spam signals) and README index.

## Initial
- `efba0b0` Initial commit.
