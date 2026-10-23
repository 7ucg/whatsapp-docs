<!-- src-sha1: 8678a730de6a0b84185733d9edd5ef1ba49ca935 -->
---
hide:
  - navigation
  - toc
---

# WhatsApp Docs

Documentação por engenharia reversa dos componentes internos do **WhatsApp Android**. Análise estática do APK, sem interceptação de tráfego.

<div class="grid cards" markdown>

-   :material-shield-lock: **[Ban System](WA_BAN_SYSTEM_DEEP_EN.md)**

    ---

    Ciclo de vida do WFAC, BizIntegrityQuery, marcação como suspeito, sinais de spam, prevenção.

    `APK 2.26.41.6`

-   :material-key-chain: **[TCToken & CSToken](WA_TCTOKEN_CSTOKEN.md)**

    ---

    Tokens de atestação antispam, sync de NctSalt, stanzas, campos proto, Baileys.

    `APK 2.26.41.6`

-   :material-robot-outline: **[Meta AI](WA_META_AI.md)**

    ---

    JIDs de bot, campos proto, protocolo de requisição/resposta, por que o Baileys falha.

    `APK 2.26.41.6`

-   :material-shield-alert: **[Reporting](WA_REPORTING.md)**

    ---

    Tipos de denúncia, stanza SMAX spam_list, 97 valores de spam_flow, tokens de denúncia, fluxo de bloqueio.

    `APK 2.26.41.6`

-   :material-fingerprint: **[Client Integrity](WA_CLIENT_INTEGRITY.md)**

    ---

    Atestação Keystore, Play Integrity, WASafe, flags de telemetria, o que é enviado.

    `APK 2.26.41.6`

-   :material-link-variant: **[Linked-Device Pairing](WA_LINKED_DEVICE_PAIRING.md)**

    ---

    Fluxos de QR e código de pareamento, identidade assinada ADV, lista de dispositivos, desvinculação.

    `APK 2.26.41.6`

-   :material-at: **[Username](WA_USERNAME.md)**

    ---

    Operações de username, chave do username, relação com LID, doc_ids de w:mex.

    `APK 2.26.41.6`

-   :material-lock-check: **[Segurança da conta](WA_ACCOUNT_SECURITY.md)**

    ---

    Login com senha (envelope #PWD_WA), PIN, e-mail de recuperação, passkeys, dispositivos confiáveis, OPAQUE nativo.

    `APK 2.26.41.6`

-   :material-sync: **[Sincronização de estado](WA_APPSTATE_SYNC.md)**

    ---

    Coleções syncd, patches e snapshots, MACs e LTHash, compartilhamento de chaves, 96 sync actions.

    `APK 2.26.41.6`

-   :material-lan-connect: **[Transporte Noise](WA_NOISE_TRANSPORT.md)**

    ---

    chatd sobre TCP, handshake Noise XX, ClientPayload, codificação binary node, backoff de reconexão, Tigon.

    `APK 2.26.41.6`

</div>

!!! info "Em breve"
    Em breve haverá mais relatórios: novos temas e atualizações a cada nova versão do APK.

## Links

[:fontawesome-brands-github: GitHub](https://github.com/7ucg){ .md-button } [:material-source-repository: Repository](https://github.com/7ucg/whatsapp-docs){ .md-button } [:fontawesome-brands-discord: Discord](https://discord.gg/R77JyK2Fu6){ .md-button } [:fontawesome-brands-telegram: Telegram](https://t.me/wegschleifen){ .md-button } [:material-history: Changelog](CHANGELOG.md){ .md-button }

## Como ler os reports

!!! success "found"
    Lido diretamente no código decompilado do APK.

!!! warning "inferred"
    Derivado do contexto do código ou de nomes. Não confirmado em runtime.

!!! failure "(2.26.26.4, not re-verified)"
    Herdado de um APK mais antigo. Trate como possivelmente desatualizado.

Todo report termina com uma tabela **Changes vs 2.26.26.4**. Os nomes de classe ofuscados (por exemplo `C51530MtC`) mudam a cada build.

## Escopo

- Ban system: ciclo de vida do WFAC, GraphQL BizIntegrityQuery, níveis de confiança
- Marcação como suspeito: quando, por quê, sinais, prevenção
- Sistema de denúncias: stanzas SMAX, spam_list, tipos de denúncia
- Detalhes de XMPP: estruturas de stanza, dicionário binário de tokens
- Sinais do lado do cliente: dhash, velocidade de mensagens, limites de broadcast, WaFA
- Reporting, client integrity, pareamento de dispositivos vinculados, usernames
