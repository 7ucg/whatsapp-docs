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
