# whatsapp-docs

Reverse-engineered documentation of WhatsApp Android internals.
All findings are based on static analysis of WhatsApp Android APK (JADX decompile + Kotlin decompile).

> More reports are coming soon: new topics and updates for every new APK version.

## Links

- Website: https://docs.baron0.com
- GitHub: https://github.com/7ucg
- Repository: https://github.com/7ucg/whatsapp-docs
- Discord: https://discord.gg/R77JyK2Fu6
- Telegram: https://t.me/wegschleifen
- [Changelog](./CHANGELOG.md)

## Languages

English is the original. Full translations: Deutsch, Español, Português (BR), Русский, العربية, Türkçe, available on https://docs.baron0.com (language switcher in the header) and in [`translations/`](./translations). Translated files carry the SHA-1 of their English source; the site build warns when a translation is outdated.

## Reports

| Report | Version | Description |
|--------|---------|-------------|
| [WA Ban System](./WA_BAN_SYSTEM_DEEP_EN.md) | 2.26.41.6 | Full ban lifecycle, WFAC, suspicious marking, GraphQL protocol, spam signals, prevention |
| [WA TCToken & CSToken](./WA_TCTOKEN_CSTOKEN.md) | 2.26.41.6 | TCToken and CSToken internals, NctSalt sync, proto fields, Baileys implementation |
| [WA Meta AI](./WA_META_AI.md) | 2.26.41.6 | Meta AI JIDs, proto fields, request/response protocol, why Baileys fails, fix |
| [WA Reporting](./WA_REPORTING.md) | 2.26.41.6 | Report types, SMAX `spam_list`, spam_flow entry points, reporting tokens, block, server errors |
| [WA Client Integrity](./WA_CLIENT_INTEGRITY.md) | 2.26.41.6 | Keystore attestation, Play Integrity, WASafe, root/emulator telemetry, what the client sends |
| [WA Linked-Device Pairing](./WA_LINKED_DEVICE_PAIRING.md) | 2.26.41.6 | QR and pair-code flows, pair-device / pair-success, ADV signed identity, device list, unlink |
| [WA Username](./WA_USERNAME.md) | 2.26.41.6 | Username check/set/delete, username key, LID, w:mex operations and doc_ids |
| [WA Account Security](./WA_ACCOUNT_SECURITY.md) | 2.26.41.6 | Password login (#PWD_WA envelope), PIN, recovery email, passkeys, trusted devices, native OPAQUE |
| [WA App-State Sync](./WA_APPSTATE_SYNC.md) | 2.26.41.6 | syncd collections, patches/snapshots, MACs and LTHash, key sharing, 96 sync actions |
| [WA Noise Transport](./WA_NOISE_TRANSPORT.md) | 2.26.41.6 | chatd over TCP, Noise XX handshake, ClientPayload, binary node encoding, reconnect, Tigon |
| [WA Call Signaling](./WA_CALL_SIGNALING.md) | 2.26.41.6 | call stanzas, offer and call key, rekey, relay and media path, group calls, links, call log |
| [WA Media Upload](./WA_MEDIA_UPLOAD.md) | 2.26.41.6 | media_conn, upload/download URLs, HKDF media keys, AES-CBC + HMAC, resume/retry, result codes, native hardening |
| [WA USync](./WA_USYNC.md) | 2.26.41.6 | usync, contact and device sync, 4 modes, 10 contexts, 30 sync types, LID mapping |
| [WA Group History](./WA_GROUP_HISTORY.md) | 2.26.41.6 | sending recent group history to new members, history sync of companion devices, addressing modes |
| [WA Broadcast Lists](./WA_BROADCAST_LISTS.md) | 2.26.41.6 | w:b list IQs, fan-out, monthly quota, spam-warning bans, status@broadcast |
| [WA WAM Analytics](./WA_WAM_ANALYTICS.md) | 2.26.41.6 | WAM event model, 4 channels, w:stats upload, private stats, daily events, on-device buffer format |
| [WA AB Props](./WA_AB_PROPS.md) | 2.26.41.6 | flag tables (21,424 ids), MobileConfig, props sync, storage, overrides, flag catalog |
| [WA Local Storage](./WA_LOCAL_STORAGE.md) | 2.26.41.6 | msgstore.db and wa.db, key tables, prefs, caches, backups, logout wipe paths |
| [WA Message Secrets](./WA_MESSAGE_SECRETS.md) | 2.26.41.6 | messageSecret, HKDF use-case keys, encrypted reactions, polls and events, message stanza extensions |
| [WA Interop](./WA_INTEROP.md) | 2.26.41.6 | third-party chat interop (gated off): w:interop IQs, InteropMessage, JID domains, consent |
| [WA Censorship Circumvention](./WA_CENSORSHIP_CIRCUMVENTION.md) | 2.26.41.6 | WhatsApp Proxy, Psiphon SOCKS tunnel, unblocking push, registration relay, what is absent |
| [WA Server-Driven UI](./WA_SERVER_DRIVEN_UI.md) | 2.26.41.6 | Phoenix, Bloks, native flows and WhatsApp Flows, payload formats, actions, security |
| [WA Account-less Surface](./WA_ACCOUNT_LESS_SURFACE.md) | 2.26.41.6 | pre-registration screens, deep links, hosts, identifiers, 97 exported components |

## Scope

- Ban system (WFAC lifecycle, GraphQL BizIntegrityQuery, trust tiers)
- Suspicious marking (when, why, ML signals, prevention)
- Report system (SMAX stanzas, spam_list, all report types)
- XMPP protocol details (stanza structures, binary token dictionary)
- Client-side signal collection (dhash, message velocity, broadcast limits, WaFA)
- Meta AI bots (JIDs, proto fields, Hatch requests)
- Reporting, client integrity/attestation, linked-device pairing, usernames

## Notes

- All analysis is static — no traffic interception
- Obfuscated class names (e.g. `C39833Hhl`) reflect JADX output
- Server-side ML logic is inferred from client-collected metrics
