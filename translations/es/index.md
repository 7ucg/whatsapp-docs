<!-- src-sha1: a10cc235881df66d01adf85a7dcdb73c2853c297 -->
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

-   :material-lock-check: **[Seguridad de la cuenta](WA_ACCOUNT_SECURITY.md)**

    ---

    Inicio de sesión con contraseña (envelope #PWD_WA), PIN, correo de recuperación, passkeys, dispositivos de confianza, OPAQUE nativo.

    `APK 2.26.41.6`

-   :material-sync: **[Sincronización de estado](WA_APPSTATE_SYNC.md)**

    ---

    Colecciones syncd, parches y snapshots, MAC y LTHash, compartición de claves, 96 sync actions.

    `APK 2.26.41.6`

-   :material-lan-connect: **[Transporte Noise](WA_NOISE_TRANSPORT.md)**

    ---

    chatd sobre TCP, handshake Noise XX, ClientPayload, codificación binary node, backoff de reconexión, Tigon.

    `APK 2.26.41.6`

-   :material-phone-in-talk: **[Señalización de llamadas](WA_CALL_SIGNALING.md)**

    ---

    Stanzas de llamada, offer y call key, rekey, relay y ruta de medios, llamadas grupales, enlaces, registro de llamadas.

    `APK 2.26.41.6`

-   :material-cloud-upload: **[Subida de medios](WA_MEDIA_UPLOAD.md)**

    ---

    media_conn, URLs de subida y descarga, claves de medios HKDF, AES-CBC + HMAC, reanudación y reintentos, códigos de resultado, hardening nativo.

    `APK 2.26.41.6`

-   :material-sync-multiple: **[USync](WA_USYNC.md)**

    ---

    Stanza USync, 4 modos, 10 contextos, 30 tipos de sync, sincronización de contactos y dispositivos, mapeo LID.

    `APK 2.26.41.6`

-   :material-account-group: **[Historial de grupos](WA_GROUP_HISTORY.md)**

    ---

    Paquete de historial para nuevos miembros, history sync de dispositivos companion, modos de direccionamiento, límites.

    `APK 2.26.41.6`

-   :material-bullhorn: **[Listas de difusión](WA_BROADCAST_LISTS.md)**

    ---

    IQs w:b de listas, fan-out, cuota mensual, bloqueos por aviso de spam, status@broadcast.

    `APK 2.26.41.6`

-   :material-chart-line: **[Analítica WAM](WA_WAM_ANALYTICS.md)**

    ---

    Modelo de eventos WAM, 4 canales, subida w:stats, estadísticas privadas, eventos diarios, formato de búfer.

    `APK 2.26.41.6`

-   :material-flag: **[AB Props](WA_AB_PROPS.md)**

    ---

    Tablas de flags (21.424 ids), MobileConfig, sincronización de props, almacenamiento, overrides, catálogo de flags.

    `APK 2.26.41.6`

-   :material-database: **[Almacenamiento local](WA_LOCAL_STORAGE.md)**

    ---

    msgstore.db y wa.db, tablas clave, prefs, cachés, copias de seguridad, rutas de borrado al cerrar sesión.

    `APK 2.26.41.6`

-   :material-key-chain-variant: **[Secretos de mensaje](WA_MESSAGE_SECRETS.md)**

    ---

    messageSecret, claves HKDF por caso de uso, reacciones, encuestas y eventos cifrados, extensiones de stanza.

    `APK 2.26.41.6`

-   :material-swap-horizontal: **[Interoperabilidad](WA_INTEROP.md)**

    ---

    Interoperabilidad de chats con terceros (desactivada): IQs w:interop, InteropMessage, dominios JID, consentimiento.

    `APK 2.26.41.6`

-   :material-shield-off: **[Elusión de la censura](WA_CENSORSHIP_CIRCUMVENTION.md)**

    ---

    Proxy de WhatsApp, túnel SOCKS de Psiphon, push de desbloqueo, relay de registro, lo que no existe.

    `APK 2.26.41.6`

-   :material-view-dashboard: **[UI dirigida por servidor](WA_SERVER_DRIVEN_UI.md)**

    ---

    Phoenix, Bloks, native flows y WhatsApp Flows, formatos de payload, acciones, seguridad.

    `APK 2.26.41.6`

-   :material-account-off: **[Superficie sin cuenta](WA_ACCOUNT_LESS_SURFACE.md)**

    ---

    Pantallas previas al registro, deep links, hosts, identificadores, 97 componentes exportados.

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
