<!-- src-sha1: 4d9d5b315c46409ac06e2eb825a231a35f91cbba -->
---
hide:
  - navigation
  - toc
---

# WhatsApp Docs

Documentación de ingeniería inversa de los componentes internos de **WhatsApp Android**. Análisis estático del APK, sin interceptación de tráfico.

<div class="grid cards" markdown>

-   :material-shield-lock: **[Sistema de baneos](WA_BAN_SYSTEM_DEEP_EN.md)**

    ---

    Ciclo de vida de WFAC, BizIntegrityQuery, marcado como sospechoso, señales de spam, prevención.

    `APK 2.26.41.6`

-   :material-key-chain: **[TCToken y CSToken](WA_TCTOKEN_CSTOKEN.md)**

    ---

    Tokens de atestación anti-spam, sincronización de NctSalt, stanzas, campos proto, Baileys.

    `APK 2.26.41.6`

-   :material-robot-outline: **[Meta AI](WA_META_AI.md)**

    ---

    JIDs de bots, campos proto, protocolo de solicitud/respuesta, por qué falla Baileys.

    `APK 2.26.41.6`

-   :material-shield-alert: **[Reportes](WA_REPORTING.md)**

    ---

    Tipos de reporte, stanza spam_list de SMAX, 97 valores de spam_flow, tokens de reporte, flujo de bloqueo.

    `APK 2.26.41.6`

-   :material-fingerprint: **[Integridad del cliente](WA_CLIENT_INTEGRITY.md)**

    ---

    Atestación de Keystore, Play Integrity, WASafe, flags de telemetría, qué se envía.

    `APK 2.26.41.6`

-   :material-link-variant: **[Emparejamiento de dispositivos vinculados](WA_LINKED_DEVICE_PAIRING.md)**

    ---

    Flujos de QR y código de emparejamiento, identidad firmada ADV, lista de dispositivos, desvinculación.

    `APK 2.26.41.6`

-   :material-at: **[Nombre de usuario](WA_USERNAME.md)**

    ---

    Operaciones de nombre de usuario, clave de usuario, relación con LID, doc_ids de w:mex.

    `APK 2.26.41.6`

</div>

!!! info "Próximamente"
    Pronto habrá más informes: nuevos temas y actualizaciones con cada nueva versión del APK.

## Enlaces

[:fontawesome-brands-github: GitHub](https://github.com/7ucg){ .md-button } [:material-source-repository: Repositorio](https://github.com/7ucg/whatsapp-docs){ .md-button } [:fontawesome-brands-discord: Discord](https://discord.gg/R77JyK2Fu6){ .md-button } [:fontawesome-brands-telegram: Telegram](https://t.me/wegschleifen){ .md-button } [:material-history: Registro de cambios](CHANGELOG.md){ .md-button }

## Cómo leer los reportes

!!! success "found"
    Leído directamente en el código descompilado del APK.

!!! warning "inferred"
    Derivado del contexto del código o de los nombres. No confirmado en tiempo de ejecución.

!!! failure "(2.26.26.4, not re-verified)"
    Heredado de un APK anterior. Tratar como posiblemente desactualizado.

Cada reporte termina con una tabla **Changes vs 2.26.26.4**. Los nombres de clase ofuscados (p. ej. `C51530MtC`) cambian en cada build.

## Alcance

- Sistema de baneos: ciclo de vida de WFAC, GraphQL BizIntegrityQuery, niveles de confianza
- Marcado como sospechoso: cuándo, por qué, señales, prevención
- Sistema de reportes: stanzas SMAX, spam_list, tipos de reporte
- Detalles de XMPP: estructuras de stanza, diccionario de tokens binarios
- Señales del lado del cliente: dhash, velocidad de mensajes, límites de difusión, WaFA
- Reportes, integridad del cliente, emparejamiento de dispositivos vinculados, nombres de usuario
