# whatsapp-docs

Reverse-engineered documentation of WhatsApp Android internals.
All findings are based on static analysis of WhatsApp Android APK (JADX decompile + Kotlin decompile).

## Reports

| Report | Version | Description |
|--------|---------|-------------|
| [WA Ban System](./WA_BAN_SYSTEM_DEEP_EN.md) | 2.26.26.4 | Full ban lifecycle, WFAC, suspicious marking, GraphQL protocol, spam signals, prevention |

## Scope

- Ban system (WFAC lifecycle, GraphQL BizIntegrityQuery, trust tiers)
- Suspicious marking (when, why, ML signals, prevention)
- Report system (SMAX stanzas, spam_list, all report types)
- XMPP protocol details (stanza structures, binary token dictionary)
- Client-side signal collection (dhash, message velocity, broadcast limits, WaFA)

## Notes

- All analysis is static — no traffic interception
- Obfuscated class names (e.g. `C39833Hhl`) reflect JADX output
- Server-side ML logic is inferred from client-collected metrics
