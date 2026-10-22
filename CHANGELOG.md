# Changelog

Newest first. Versions refer to the analysed WhatsApp Android APK.

## Unreleased
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
