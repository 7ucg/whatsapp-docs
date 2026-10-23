<!-- src-sha1: 168a34c992451d2faa786d872e43291383aabf63 -->
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

-   :material-lock-check: **[Hesap güvenliği](WA_ACCOUNT_SECURITY.md)**

    ---

    Parola ile giriş (#PWD_WA zarfı), PIN, kurtarma e-postası, passkey'ler, güvenilen cihazlar, yerel OPAQUE.

    `APK 2.26.41.6`

-   :material-sync: **[Durum eşitleme](WA_APPSTATE_SYNC.md)**

    ---

    syncd koleksiyonları, yamalar ve anlık görüntüler, MAC'ler ve LTHash, anahtar paylaşımı, 96 sync action.

    `APK 2.26.41.6`

-   :material-lan-connect: **[Noise aktarımı](WA_NOISE_TRANSPORT.md)**

    ---

    TCP üzerinden chatd, Noise XX el sıkışması, ClientPayload, binary node kodlaması, yeniden bağlanma backoff'u, Tigon.

    `APK 2.26.41.6`

-   :material-phone-in-talk: **[Arama sinyalleşmesi](WA_CALL_SIGNALING.md)**

    ---

    Arama stanza'ları, offer ve call key, rekey, relay ve medya yolu, grup aramaları, bağlantılar, arama geçmişi.

    `APK 2.26.41.6`

-   :material-cloud-upload: **[Medya yükleme](WA_MEDIA_UPLOAD.md)**

    ---

    media_conn, yükleme ve indirme URL'leri, HKDF medya anahtarları, AES-CBC + HMAC, devam ettirme ve yeniden deneme, sonuç kodları, yerel hardening.

    `APK 2.26.41.6`

-   :material-sync-multiple: **[USync](WA_USYNC.md)**

    ---

    USync stanza'sı, 4 mod, 10 bağlam, 30 sync türü, kişi ve cihaz eşitleme, LID eşlemesi.

    `APK 2.26.41.6`

-   :material-account-group: **[Grup geçmişi](WA_GROUP_HISTORY.md)**

    ---

    Yeni üyeler için geçmiş paketi, companion cihazların history sync'i, adresleme modları, limitler.

    `APK 2.26.41.6`

-   :material-bullhorn: **[Yayın listeleri](WA_BROADCAST_LISTS.md)**

    ---

    w:b liste IQ'ları, fan-out, aylık kota, spam uyarısı yasakları, status@broadcast.

    `APK 2.26.41.6`

-   :material-chart-line: **[WAM analitiği](WA_WAM_ANALYTICS.md)**

    ---

    WAM olay modeli, 4 kanal, w:stats yüklemesi, özel istatistikler, günlük olaylar, tampon biçimi.

    `APK 2.26.41.6`

-   :material-flag: **[AB Props](WA_AB_PROPS.md)**

    ---

    Flag tabloları (21.424 id), MobileConfig, props eşitleme, depolama, override'lar, flag kataloğu.

    `APK 2.26.41.6`

-   :material-database: **[Yerel depolama](WA_LOCAL_STORAGE.md)**

    ---

    msgstore.db ve wa.db, ana tablolar, prefs, önbellekler, yedekler, çıkışta silme yolları.

    `APK 2.26.41.6`

-   :material-key-chain-variant: **[Mesaj sırları](WA_MESSAGE_SECRETS.md)**

    ---

    messageSecret, kullanım durumuna göre HKDF anahtarları, şifreli tepkiler, anketler ve etkinlikler, stanza uzantıları.

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
