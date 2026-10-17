---
hide:
  - navigation
  - toc
---

# WhatsApp Docs

Reverse-engineered documentation of **WhatsApp Android** internals. Static analysis of the APK, no traffic interception.

<div class="grid cards" markdown>

-   :material-shield-lock: **[Ban System](WA_BAN_SYSTEM_DEEP_EN.md)**

    ---

    WFAC lifecycle, BizIntegrityQuery, suspicious marking, spam signals, prevention.

    `APK 2.26.41.6`

-   :material-key-chain: **[TCToken & CSToken](WA_TCTOKEN_CSTOKEN.md)**

    ---

    Anti-spam attestation tokens, NctSalt sync, stanzas, proto fields, Baileys.

    `APK 2.26.41.6`

-   :material-robot-outline: **[Meta AI](WA_META_AI.md)**

    ---

    Bot JIDs, proto fields, request/response protocol, why Baileys fails.

    `APK 2.26.41.6`

-   :material-shield-alert: **[Reporting](WA_REPORTING.md)**

    ---

    Report types, SMAX spam_list stanza, 97 spam_flow values, reporting tokens, block flow.

    `APK 2.26.41.6`

-   :material-fingerprint: **[Client Integrity](WA_CLIENT_INTEGRITY.md)**

    ---

    Keystore attestation, Play Integrity, WASafe, telemetry flags, what is sent.

    `APK 2.26.41.6`

-   :material-link-variant: **[Linked-Device Pairing](WA_LINKED_DEVICE_PAIRING.md)**

    ---

    QR and pair-code flows, ADV signed identity, device list, unlink.

    `APK 2.26.41.6`

-   :material-at: **[Username](WA_USERNAME.md)**

    ---

    Username operations, username key, LID relation, w:mex doc_ids.

    `APK 2.26.41.6`

</div>

!!! info "Coming soon"
    More reports are coming soon: new topics and updates for every new APK version.

## Links

[:fontawesome-brands-github: GitHub](https://github.com/7ucg){ .md-button } [:material-source-repository: Repository](https://github.com/7ucg/whatsapp-docs){ .md-button } [:fontawesome-brands-discord: Discord](https://discord.gg/R77JyK2Fu6){ .md-button } [:fontawesome-brands-telegram: Telegram](https://t.me/wegschleifen){ .md-button } [:material-history: Changelog](CHANGELOG.md){ .md-button }

## How to read the reports

!!! success "found"
    Read directly in decompiled APK code.

!!! warning "inferred"
    Derived from code context or naming. Not confirmed at runtime.

!!! failure "(2.26.26.4, not re-verified)"
    Carried over from an older APK. Treat as possibly outdated.

Every report ends with a **Changes vs 2.26.26.4** table. Obfuscated class names (e.g. `C51530MtC`) change with every build.

## Scope

- Ban system: WFAC lifecycle, GraphQL BizIntegrityQuery, trust tiers
- Suspicious marking: when, why, signals, prevention
- Report system: SMAX stanzas, spam_list, report types
- XMPP details: stanza structures, binary token dictionary
- Client-side signals: dhash, message velocity, broadcast limits, WaFA
- Reporting, client integrity, linked-device pairing, usernames
