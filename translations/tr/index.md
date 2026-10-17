<!-- src-sha1: 4d9d5b315c46409ac06e2eb825a231a35f91cbba -->
---
hide:
  - navigation
  - toc
---

# WhatsApp Docs

**WhatsApp Android** iç yapısının tersine mühendislikle çıkarılmış dokümantasyonu. APK'nın statik analizi, trafik dinleme yok.

<div class="grid cards" markdown>

-   :material-shield-lock: **[Ban System](WA_BAN_SYSTEM_DEEP_EN.md)**

    ---

    WFAC yaşam döngüsü, BizIntegrityQuery, şüpheli işaretleme, spam sinyalleri, önleme.

    `APK 2.26.41.6`

-   :material-key-chain: **[TCToken & CSToken](WA_TCTOKEN_CSTOKEN.md)**

    ---

    Spam karşıtı doğrulama token'ları, NctSalt senkronizasyonu, stanza'lar, proto alanları, Baileys.

    `APK 2.26.41.6`

-   :material-robot-outline: **[Meta AI](WA_META_AI.md)**

    ---

    Bot JID'leri, proto alanları, istek/yanıt protokolü, Baileys neden başarısız olur.

    `APK 2.26.41.6`

-   :material-shield-alert: **[Reporting](WA_REPORTING.md)**

    ---

    Şikayet türleri, SMAX spam_list stanza'sı, 97 spam_flow değeri, şikayet token'ları, engelleme akışı.

    `APK 2.26.41.6`

-   :material-fingerprint: **[Client Integrity](WA_CLIENT_INTEGRITY.md)**

    ---

    Keystore attestation, Play Integrity, WASafe, telemetri flag'leri, nelerin gönderildiği.

    `APK 2.26.41.6`

-   :material-link-variant: **[Linked-Device Pairing](WA_LINKED_DEVICE_PAIRING.md)**

    ---

    QR ve eşleştirme kodu akışları, ADV imzalı kimlik, cihaz listesi, bağlantıyı kaldırma.

    `APK 2.26.41.6`

-   :material-at: **[Username](WA_USERNAME.md)**

    ---

    Kullanıcı adı işlemleri, kullanıcı adı anahtarı, LID ilişkisi, w:mex doc_id'leri.

    `APK 2.26.41.6`

</div>

!!! info "Yakında"
    Yakında daha fazla rapor geliyor: yeni konular ve her yeni APK sürümü için güncellemeler.

## Bağlantılar

[:fontawesome-brands-github: GitHub](https://github.com/7ucg){ .md-button } [:material-source-repository: Repository](https://github.com/7ucg/whatsapp-docs){ .md-button } [:fontawesome-brands-discord: Discord](https://discord.gg/R77JyK2Fu6){ .md-button } [:fontawesome-brands-telegram: Telegram](https://t.me/wegschleifen){ .md-button } [:material-history: Changelog](CHANGELOG.md){ .md-button }

## Raporlar nasıl okunur

!!! success "found"
    Çözülmüş (decompile edilmiş) APK kodunda doğrudan okundu.

!!! warning "inferred"
    Kod bağlamından veya adlandırmadan çıkarıldı. Çalışma zamanında doğrulanmadı.

!!! failure "(2.26.26.4, not re-verified)"
    Eski bir APK'dan devralındı. Güncelliğini yitirmiş olabileceği göz önünde bulundurulmalı.

Her rapor bir **Changes vs 2.26.26.4** tablosuyla biter. Obfuscate edilmiş sınıf adları (ör. `C51530MtC`) her derlemede değişir.

## Kapsam

- Ban sistemi: WFAC yaşam döngüsü, GraphQL BizIntegrityQuery, güven kademeleri
- Şüpheli işaretleme: ne zaman, neden, sinyaller, önleme
- Şikayet sistemi: SMAX stanza'ları, spam_list, şikayet türleri
- XMPP ayrıntıları: stanza yapıları, binary token sözlüğü
- İstemci tarafı sinyaller: dhash, mesaj hızı, broadcast limitleri, WaFA
- Şikayet, istemci bütünlüğü, bağlı cihaz eşleştirme, kullanıcı adları
