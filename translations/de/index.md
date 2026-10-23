<!-- src-sha1: b5920296a242a0eeba7ce731008cfa04a6c63436 -->
---
hide:
  - navigation
  - toc
---

# WhatsApp Docs

Reverse-engineerte Dokumentation der **WhatsApp-Android**-Interna. Statische Analyse der APK, kein Abfangen von Traffic.

<div class="grid cards" markdown>

-   :material-shield-lock: **[Ban System](WA_BAN_SYSTEM_DEEP_EN.md)**

    ---

    WFAC-Lebenszyklus, BizIntegrityQuery, Suspicious-Markierung, Spam-Signale, Prävention.

    `APK 2.26.41.6`

-   :material-key-chain: **[TCToken & CSToken](WA_TCTOKEN_CSTOKEN.md)**

    ---

    Anti-Spam-Attestation-Tokens, NctSalt-Sync, Stanzas, Proto-Felder, Baileys.

    `APK 2.26.41.6`

-   :material-robot-outline: **[Meta AI](WA_META_AI.md)**

    ---

    Bot-JIDs, Proto-Felder, Request/Response-Protokoll, warum Baileys scheitert.

    `APK 2.26.41.6`

-   :material-shield-alert: **[Reporting](WA_REPORTING.md)**

    ---

    Report-Typen, SMAX-spam_list-Stanza, 97 spam_flow-Werte, Reporting-Tokens, Block-Flow.

    `APK 2.26.41.6`

-   :material-fingerprint: **[Client Integrity](WA_CLIENT_INTEGRITY.md)**

    ---

    Keystore-Attestation, Play Integrity, WASafe, Telemetrie-Flags, was gesendet wird.

    `APK 2.26.41.6`

-   :material-link-variant: **[Linked-Device Pairing](WA_LINKED_DEVICE_PAIRING.md)**

    ---

    QR- und Pair-Code-Flows, ADV-signierte Identität, Geräteliste, Unlink.

    `APK 2.26.41.6`

-   :material-at: **[Username](WA_USERNAME.md)**

    ---

    Username-Operationen, Username-Key, LID-Bezug, w:mex-doc_ids.

    `APK 2.26.41.6`

-   :material-lock-check: **[Kontosicherheit](WA_ACCOUNT_SECURITY.md)**

    ---

    Passwort-Login (#PWD_WA-Envelope), PIN, Recovery-E-Mail, Passkeys, vertrauenswürdige Geräte, natives OPAQUE.

    `APK 2.26.41.6`

-   :material-sync: **[App-State-Sync](WA_APPSTATE_SYNC.md)**

    ---

    syncd-Collections, Patches und Snapshots, MACs und LTHash, Key-Sharing, 96 Sync-Actions.

    `APK 2.26.41.6`

-   :material-lan-connect: **[Noise-Transport](WA_NOISE_TRANSPORT.md)**

    ---

    chatd über TCP, Noise-XX-Handshake, ClientPayload, Binary-Node-Encoding, Reconnect-Backoff, Tigon.

    `APK 2.26.41.6`

-   :material-phone-in-talk: **[Anruf-Signalisierung](WA_CALL_SIGNALING.md)**

    ---

    Call-Stanzas, Offer und Call-Key, Rekey, Relay und Medienpfad, Gruppenanrufe, Links, Anrufliste.

    `APK 2.26.41.6`

-   :material-cloud-upload: **[Medien-Upload](WA_MEDIA_UPLOAD.md)**

    ---

    media_conn, Upload- und Download-URLs, HKDF-Medienschlüssel, AES-CBC + HMAC, Resume und Retry, Ergebniscodes, natives Hardening.

    `APK 2.26.41.6`

-   :material-sync-multiple: **[USync](WA_USYNC.md)**

    ---

    USync-Stanza, 4 Modi, 10 Kontexte, 30 Sync-Typen, Kontakt- und Geräteabgleich, LID-Mapping.

    `APK 2.26.41.6`

-   :material-account-group: **[Gruppen-Historie](WA_GROUP_HISTORY.md)**

    ---

    History-Bundle für neue Mitglieder, History-Sync der Companion-Geräte, Adressierungsmodi, Limits.

    `APK 2.26.41.6`

-   :material-bullhorn: **[Broadcast-Listen](WA_BROADCAST_LISTS.md)**

    ---

    w:b-Listen-IQs, Fan-out, monatliches Kontingent, Spam-Warn-Sperren, status@broadcast.

    `APK 2.26.41.6`

</div>

!!! info "Bald mehr"
    Bald kommen weitere Reports: neue Themen und Aktualisierungen für jede neue APK-Version.

## Links

[:fontawesome-brands-github: GitHub](https://github.com/7ucg){ .md-button } [:material-source-repository: Repository](https://github.com/7ucg/whatsapp-docs){ .md-button } [:fontawesome-brands-discord: Discord](https://discord.gg/R77JyK2Fu6){ .md-button } [:fontawesome-brands-telegram: Telegram](https://t.me/wegschleifen){ .md-button } [:material-history: Changelog](CHANGELOG.md){ .md-button }

## So werden die Reports gelesen

!!! success "found"
    Direkt im dekompilierten APK-Code gelesen.

!!! warning "inferred"
    Aus Code-Kontext oder Benennung abgeleitet. Nicht zur Laufzeit bestätigt.

!!! failure "(2.26.26.4, not re-verified)"
    Aus einer älteren APK übernommen. Kann veraltet sein.

Jeder Report endet mit einer Tabelle **Changes vs 2.26.26.4**. Obfuskierte Klassennamen (z. B. `C51530MtC`) ändern sich mit jedem Build.

## Umfang

- Ban System: WFAC-Lebenszyklus, GraphQL BizIntegrityQuery, Trust-Tiers
- Suspicious-Markierung: wann, warum, Signale, Prävention
- Report-System: SMAX-Stanzas, spam_list, Report-Typen
- XMPP-Details: Stanza-Strukturen, binäres Token-Wörterbuch
- Client-seitige Signale: dhash, Message Velocity, Broadcast-Limits, WaFA
- Reporting, Client Integrity, Linked-Device Pairing, Usernames
