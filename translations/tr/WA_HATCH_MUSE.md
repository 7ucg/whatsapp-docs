<!-- src-sha1: aacd3c372c813b12cfe335ddb7b3323c8eed3863 -->
# WhatsApp Hatch/Muse AI Agent — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-11-15
**Kapsam:** Hatch/Muse AI agent internal'leri — attested Noise-gateway VM transport'u, native carrier + SEV-SNP attestation, control plane ve WAFFLE onboarding, agent-browser noVNC stream'i, workspace (spaces, feed, goals, ideas, artifacts, approvals, scheduled tasks, connectors), secure credential store, CVM identity/PIN kurtarma (`hatch/cvm`, Vesta OPAQUE), ücretli abonelik katmanı, erişilebilirlik hükmü, Baileys/velowa'nın bunu neden uygulayamadığı

---

## 1. Hatch/Muse nedir

**Hatch**, WhatsApp'ın AI-agent alt sisteminin dahili kod adıdır; **Muse**, agent'ın kendisinin kullanıcıya-görünen adıdır (`str29b7` "Muse manages emails, books tables, and more."). Agent sadece bir sohbet persona'sı değildir (bu Meta AI'dır, `WA_META_AI.md`'de ele alınır): web'de gezinebilen, zamanlanmış görevler çalıştırabilen, kendi dosya sistemini tutabilen ve kullanıcı adına üçüncü-taraf servisleri çağırabilen bir **uzak confidential VM ("CVM")**'i sürer. Bu rapordaki her şey 2.26.41.6'nın (`WA-APK-BETA/WhatsApp_2.26.41.6/`) `found`/`inferred` statik analizidir, bir düzeltilmiş alt-bölge (§6, `hatch/cvm` identity sistemi) 2.26.45.10 smali'sine karşı yeniden doğrulanmıştır. **Bu raporda hiçbir şey `tested` değildir** — hiçbir cihaz/Frida çalışması bunu desteklemez; dinamik-doğrulama boşlukları satır içinde işaretlenmiştir.

### 1.1 Ana varlıklar

| Varlık | Anlam |
|--------|-------|
| Hatch | Tüm agent alt sisteminin (VM, workspace, credential store, identity/PIN katmanı) dahili kod adı |
| Muse | Kullanıcıya-görünen agent adı/persona'sı |
| CVM | "Cloud VM" / "confidential VM" — agent'ın uzak compute ortamı (AMD SEV-SNP) |
| `HatchVmEndpoint` (`C57830PwR`) | Çözülmüş VM bağlantı struct'ı: host, `auth_token`, expiry, doğrulanmış token, `notary_token` param map'i |
| Noise gateway | Tigon üzerinden taşınan, ana WA Noise_XX/chatd oturumundan ayrı, bir Meta "noise gateway"ine ayrı attested Noise oturumu |
| Agent spaces | Agent'ın CVM içinde inşa edip barındırdığı, bir telefon WebView'ına reverse-proxy edilen mini web uygulamaları |
| Connector | Agent ile bir üçüncü-taraf servis (Gmail, takvim, Messenger, ödeme rayı, özel endpoint) arasında kayıtlı bir bağlama |
| `hatch/cvm` (Vesta) | Agent'ın **cihaz/VM identity ve chip-attestation kurtarma sistemi**, PIN-gated OPAQUE PAKE — **bir ödeme kasası değil** (daha önceki bir araştırma geçişini düzeltir, bkz §6) |
| Approval gate | Riskli/geri döndürülemez bir agent eylemi öncesi insan-devreli onay |

### 1.2 Meta AI sohbetiyle ilişkisi

Muse, Meta AI ile aynı sohbet yüzeyinden erişilir ve bir kısım altyapıyı paylaşır (bot-JID yetenek reklamı — bkz §7) ve `WA_META_AI.md` §5'te belgelenen Hatch JSON metadata kanalını (`HF1`/`HatchMetadataRequestManager`, `ProtocolMessage.aiMetadataOperation`). Ama bu raporun kapsadığı agent-browser/VM/workspace sistemi **ayrı, çok daha büyük bir alt sistemdir**: chatd/Noise_XX oturumuna hiç binmez, kendi native transport'una sahiptir ve kendi durumunu (goals, feed, artifacts, approvals) sunucu tarafında CVM içinde kalıcı hale getirir. Private Processing / TEE cluster'ı (Meta AI'ın kendi sohbetleriniz hakkındaki soruları cevaplaması, Private Search), **üçüncü, ayrı** bir sistemdir — tam ayrıştırma için bkz §11.

---

## 2. Mimari genel bakış

### 2.1 Paket haritası

Tüm Hatch/agent aktiviteleri `android:exported="false"`'dür — çapraz-uygulama giriş noktası yoktur; her şey sohbet/agent yüzeyinden süreç-içi başlatılır.

| Paket | Rol |
|---------|------|
| `com.whatsapp.hatch.vm` (`p085vm`) | VM control plane / yaşam döngüsü: `HatchVmLifecycleCoordinator`, `HatchVmApiClient`, `HatchVmWaker`, `HatchVmLeaseGate`, `GraphQlHatchAbraTokenProvider`, `HatchAbraTokenRevoker` |
| `com.whatsapp.hatch.onboarding` | `HatchWaffleOnboarding`, `HatchPairingAuthBrowsingActivity`, `HatchMuseConnectionActivator` |
| `com.whatsapp.hatch.computer` / `.conversation.browser` / `.conversation.approval` | `HatchComputerActivity` (tam VM masaüstü), `HatchBrowserStreamActivity` (sohbet içi canlı browser), `HatchBrowserPreviewActivity` (approval gate) |
| `com.whatsapp.hatch.feed/goals/ideas/activity/approvalhistory` | Workspace UI: feed, goals + alt-goal'lar, ideas, approval geçmişi |
| `com.whatsapp.hatch.artifacts/media` | Agent'ın ürettiği artifact'lar ve dosyalar |
| `com.whatsapp.hatch.connectors(.ui)` | Üçüncü-taraf connector kataloğu, bağlanma akışları, sanal-kart eylemi, connector-başına izin modu |
| `com.whatsapp.hatch.identity.ui` | Agent "about me" belgeleri |
| `com.whatsapp.hatch.scheduledtasks.impl` | Agent VM tekrarlayan görev UI'si |
| `com.whatsapp.hatch.cvm` / `.cvm.pin` | **Bir kasa değil** — PIN-gated cihaz/VM identity kurtarma (Vesta OPAQUE), §6 |
| `com.whatsapp.hatch.subscription(s).iap` | Ücretli katman satın alma akışı, §7 |
| `com.whatsapp.bot.agentspaces.*` | "Spaces" host'u: `HatchSpaceActivity` + `HatchSpaceTunnel` reverse-proxy'si, `NoiseHatchVmTransport` adaptörü |
| `com.whatsapp.bot.agentbrowser.*` | Browser motoru + VM transport'u: `BrowserSessionController` (noVNC WebView), `NoiseVmConnection`/`WaNoiseChannel`, `agentbrowser.noise.carrier.*` (native JNI) |
| `com.whatsapp.bot.securecredentials.*` | `SecureCredentialVault` — CVM içinde sunucu tarafı credential store |
| `com.whatsapp.bot.agentactivity/agentfeed/agentgoals/agentapprovals` | `hatch.*` UI'sinin arkasındaki veri/feed katmanı |
| `com.whatsapp.bot.infra.vmmedia` | Agent VM dosya sistemi ham çekme (`/fs/raw/`, `/media/raw/`) |
| `com.whatsapp.bot.quiz` | `AiQuizViewerActivity` — richResponse quiz viewer'ı, bir VM özelliği **değil** (§2.3) |
| `com.crossapp.tigonhttp(.noise)` | Meta'nın paylaşılan **Tigon** çapraz-uygulama native HTTP stack'i + `NoiseChannelManagerHolder` |

### 2.2 Üç ayrı transport — bunları birbirine karıştırmayın

Bu, yapısal açıdan en önemli tek gerçektir, ve önceki bir araştırma geçişi bunlardan birini yanlış değerlendirmişti (§6.1 bunu düzeltir):

| # | Transport | Taşıdığı | Üçüncü-taraf istemci için engel |
|---|-----------|---------|-----------------------------------|
| 1 | **Attested Noise-gateway VM kanalı** — Tigon üzerinden `/v1/noise`, native `libwa-noise-gateway-carrier-jni.so` | Agent-etkileşimli her şey: browser-VM HTTP'si (`/api/*`, `/fs/*`, `/spaces/*`), noVNC ekran stream'i, workspace özellikleri, secure-credential CRUD | Native Noise+WebSocket carrier **ve** WAFFLE resmi-istemci onboarding'i — sert şekilde bloklanmış |
| 2 | **Düz HTTPS control plane** `hatch-api.meta.ai`'a | VM wake, Abra bearer token, pairing URL'i, **ve** (düzeltildi, §6) `hatch/vesta-auth/*` / `hatch/cvm-*` identity-kurtarma endpoint'leri | Transport prensip olarak MITM-gözlenebilir (root'lanmış cihaz, pinning bypass); identity endpoint'leri ayrıca geçerli istek gövdeleri üretmek için native OPAQUE + post-quantum matematik (`libvesta_client_jni.so`) gerektirir |
| 3 | **Düz MEX/GraphQL**, sıradan WhatsApp `whatsapp-android-mex`/`whatsapp-android-www` transport'u üzerinden | Zamanlanmış-görev/hatırlatıcı okuma+silme (1:1 ve grup), abonelik compliance-bilgisi okuma, Hatch ödemeler-token basımı | Native/attested engel yok — herhangi bir diğer MEX operasyonu gibi erişilebilir |

Transport 1, orijinal (2.26.41.6) araştırma geçişinin "Hatch VM transport'u" olarak adlandırdığı şeydir ve alt sistemin yüzeyinin büyük çoğunluğunu oluşturur. Transport 3, bir Baileys/velowa-tarzı istemcinin olabilirlik dahilinde sürebileceği Hatch'in **tek** parçasıdır.

### 2.3 VM'in parçası değil — quiz ilişkisi

`com.whatsapp.bot.quiz.AiQuizViewerActivity`, saklanmış bir bot rich-response mesajına gömülü bir quiz için tam-ekran bir viewer'dır (richResponse "Jarvis" quiz ilkeli — `WA_META_AI.md` §4.3/§6.3 bölgesi, Hatch değil). Quiz'i **yerel mesaj mağazasından** satır id'si + key + bölüm ile yükler (intent extra'ları `ai_quiz_viewer_message_row_id`, `ai_quiz_viewer_quiz_key`, `ai_quiz_viewer_section_index`) — ağ çağrısı yok, VM transport'u yok. Burada sadece bir Hatch özelliğiyle karıştırılmaması için bahsedilmiştir; tam ayrıştırma tablosu için bkz §11.

---

## 3. Control plane ve onboarding

### 3.1 WAFFLE onboarding (`found`)

Agent yüzeyinin ilk kullanımı **`HatchWaffleOnboarding`**'i çalıştırır: istemci, **WAFFLE** bütünlük attestation'ı üzerinden gerçek, değiştirilmemiş bir WhatsApp build'i olduğunu kanıtlar (`com.whatsapp.waffle.wfac` ban UI / hesap bağlama ile aynı resmi-istemci attestation ailesi — kardeş WFAC bileşeni için bkz `WA_CLIENT_INTEGRITY.md` §11). Log breadcrumb'leri: `"waffle-onboarding"`, `"vm-credentials"`, `"pairing-url"`, `"HatchWaffleOnboarding/link pairing-url-received="`. Bir üçüncü-taraf istemci geçerli bir WAFFLE token'ı üretemez, bu yüzden bir VM'i provision bile edemez — bu, Noise-gateway carrier'ından bağımsız sert onboarding-tarafı engeldir.

### 3.2 Pairing (`found`)

`HatchPairingAuthBrowsingActivity`, WhatsApp hesabını Meta AI agent/Meta hesabına bağlayan OAuth-tarzı bir **pairing URL'i** açar; tamamlanma `pairing-url-received` olarak loglanır.

### 3.3 VM wake ve Abra bearer'ı (`found`)

`GraphQlHatchAbraTokenProvider`, VM için bir GraphQL "Abra" bearer token'ı basar; ardından `HatchVmApiClient` şunu yapar:

```
POST https://hatch-api.meta.ai/hatch/vm/wake
{"vm_id": "...", "retry_count": N}
```

Bu sıradan HTTPS'tir, Noise kanalı değil. Yanıt, `HatchVmLifecycleCoordinator`'ın cached-endpoint mantığını besler ("connect cached-endpoint", "invalidateToken failed") ve bir `HatchVmEndpoint`'e (`C57830PwR`) çözülür: host/base-URL, `auth_token`, `bearerExpiresAtMs`, doğrulanmış-token flag'i ve `/v1/noise` `notary_token`'ını taşıyan bir param map'i. `HatchAbraTokenRevoker` iptal işlemini yürütür.

**Erişilebilirlik:** wake çağrısı ve token basımı düz HTTPS/GraphQL'dir, prensip olarak root'lanmış bir cihazda pinning bypass'ıyla MITM-gözlenebilir — ama bir WAFFLE-provision edilmiş hesap olmadan işe yaramaz, çünkü sunucu tanınmayan bir istemciye çalışan bir VM endpoint'i vermez (`inferred`; sunucu tarafında bağımsız doğrulanmamış).

---

## 4. Attested agent-browser VM transport'u

Bu alt sistemin öne çıkan bulgusudur: agent-browser VM'i ana WhatsApp Noise/XMPP oturumuna **binmez**. Bir Meta "noise gateway"ine, Meta'nın Tigon HTTP stack'i üzerinden taşınan, özel bir native kütüphane aracılığıyla, bir attestation verifier'ı ve opsiyonel bir pre-shared private-auth key'iyle **ayrı bir Noise oturumu** açar.

### 4.1 Handshake (`found`, `WaNoiseChannel`)

`WaNoiseChannel`, VM endpoint host'unu alır ve handshake'ten önce URL-encoded query param'ları ekler:

| Param | Kaynak |
|-------|--------|
| `auth_token` | `HatchVmEndpoint.auth_token` (VM bearer'ı) |
| `notary_token` | endpoint'in param map'indeki `/v1/noise` key'inin değeri, sadece boş değilse |
| `app_id` | WA app-id sabiti (`inferred`, literal olarak çözülmemiş) |
| `app_version` | hardcoded literal `"2.26.41.6"` |

Handshake path'i: **`/v1/noise`**. Handshake timeout'u **20000 ms**; toplam kanal-açma bütçesi **60000 ms** (`NoiseVmConnection`). Log breadcrumb'leri: `noise/open-start`, `noise/reused`, `noise/closed reason=...`, `noise/use-once`.

### 4.2 Native carrier ve attestation (`found`)

`NoiseGatewayCarrier`, `NoiseGatewayCarrierSoLoader` tarafından **`libwa-noise-gateway-carrier-jni.so`** olarak yüklenen bir `com.facebook.jni.HybridData` JNI nesnesidir — `lib/arm64-v8a/`'da gevşek bir dosya değildir, superpack `libs.so` blob'u içinde paketlenmiştir (byte-exact statik çıkarım mevcut değil).

Native giriş noktaları: `createNative(TigonServiceHolder, NoiseChannelManagerHolder)`, `start(endpoint, ..., byte[32]?, AttestationVerifierHolder, Stream0Listener)`, `sendWebsocketFrameNative`, `stopNative`, `cancelHandshakeNative`. `Stream0Listener` callback'leri (`onWebSocketUpgraded`, `onTransportReady`, `onReady(NoiseHandshakeOutcome)`, `onMessage`, `onClose/onFailure`), kanalın bir WebSocket içine **Noise framed** olduğunu gösterir.

`AttestationVerifierHolder`'ın üç native constructor'ı vardır:

| Varyant | Anlam |
|---------|---------|
| `createNoOpNative()` | Attestation yok — bu geçişte görülen decompile edilmiş yolda örneklenen varyant |
| `createSnpNative(bool)` | AMD SEV-SNP confidential-compute attestation'ı |
| `createSnpPinnedToChipsNative(chips[], bool)` | SNP, belirli izin verilen chip ID'lerine pinned |

**Çalışma zamanında hangi varyantın çalıştığı** bu statik geçişten `unknown`'dır. 2.26.45.10 `hatch/cvm` geçişi (§6), SEV-SNP chip ID'lerini allowlist'e alan/commit eden somut control-plane endpoint'lerini (`/hatch/cvm-chip-allowlist`, `/hatch/cvm-chip-selection`) bağımsız olarak bulmuş, pinned-chip attestation modunun gerçek altyapı olduğunu, sadece uyuyan bir kod yolu olmadığını doğrulamıştır.

`NoisePrivateAuthMode.REQUIRED` artı 32-byte'lık bir key, opsiyonel bir pre-shared-key "private auth" modudur (`inferred`: channel binding); görülen yolda doldurulmamıştır, hiç kullanılıp kullanılmadığı `unknown`'dır.

### 4.3 Noise-üzerinden-HTTP transport'u (`found`)

Kanal açıldıktan sonra, `WaVmHttpTransportImpl`/`VmHttpClient`, Tigon aracılığıyla Noise tüneli içinden sıradan JSON HTTP istekleri gönderir. Uygulama-seviyesi adaptör (`NoiseHatchVmTransport`, §5'teki her workspace özelliği tarafından kullanılır) dört fiil sunar:

| fiil | tag | kullanım |
|------|-----|-----|
| `CQ4(url, accept)` | `hatch_vm_read` | GET okuma |
| `AEV(method,url,body,…)` | `hatch_vm_call` | genel tek-seferlik çağrı |
| `CXY(method,url,headers,body,streaming)` | `hatch_vm_request` | stream'lenmiş istek (120 s, veya `streaming` iken sınırsız) |
| `Cly(url,body,…)` | `hatch_vm_subscribe` | uzun-ömürlü SSE/duplex subscribe |

`NoiseChannelHolds`, açık "hold"ları ref-sayar; son hold serbest kaldıktan sonra kanal yıkılır (yapılandırılabilir aralık). VM HTTP path yüzeyi (`found`, string literal'ler): `/v1/noise`, `/api/`, `/api/computer/subscribe`, `/api/artifacts/pin`, `/spaces/`, `/spaces/v2`, `/spaces/cvm/<slug>`, `/spaces/share/`, `/workspace/`, `/home/hatch/`, `/media/raw/`, `/fs/raw/`, artı §5.9'daki credential path'leri.

### 4.4 noVNC ekran stream'i (`found`)

`assets/vmvnc/`, gerçek bir **noVNC** web istemcisini paketler (`novnc-rfb.js`, `vnc.html`, MPL-2.0 `LICENSE.txt`) — 2.26.41.6 ve 2.26.45.10 build'lerinin her ikisinde bağımsız olarak mevcut olduğu doğrulanmıştır (`assets-sweep.md`). `BrowserSessionController`, `https://appassets.androidplatform.net/assets/vmvnc/vnc.html`'i bir WebView'a yükler. HTML, `window.WebSocket`'i override eden bir **`BridgedWebSocket`** tanımlar: noVNC, `wss://bridge.invalid/`'i (subprotocol `binary`) açtığına inanır, ama her RFB frame'i Android JS bridge'i `window.AndroidVncBridge` (`socketSend`/`socketClose`/`socketOpen`, callback'ler `window.__vncBridge.*`) üzerinden relay edilir. Gönderilen HTML'in kendi yorumu bunun nedenini açıklar: **gerçek websockify endpoint'i `Authorization: Bearer <jwt>` gerektirir**, bu bir WebView WebSocket'inin ayarlayamayacağı bir şeydir, bu yüzden gerçek socket'in sahibi native kod'dur (VM bearer'ıyla Tigon üzerinden açılır) ve JS shim'i sadece frame'leri relay eder.

Sonuç: VM masaüstü/browser'ı, telefona gerçek **RFB (VNC) over a JWT-bearer-authenticated WebSocket** olarak stream edilir, bu da kendisi attested Noise gateway'i üzerinden tünellenir; noVNC bunu bir WebView'da render eder. Girdi gating'i (`isViewOnly`, `isInputEnabled`, `isPanModeEnabled`, zoom/viewport metotları) ve boyutlandırma (`BrowserViewerJson{width,height,devicePixelRatio}`) native-sürümlüdür. `inferred`: daha hafif "present"/preview sabit frame'leri (`BrowserTaskScreenshotJson`, `BrowserTaskPresentationJson`), sohbet-içi `HatchBrowserStreamActivity`'yi besler, tam etkileşimli VNC `HatchComputerActivity` için ayrılmıştır.

### 4.5 Control lease (`found`)

`BrowserControlLeaseJson{controlOwner, taskId, controlExpiresAtMs}` + `BrowserControlGrantJson`/`BrowserControlEnvelopeJson`, browser'ı kimin sürdüğünü (agent vs. insan "take control") uygular, `controlExpiresAtMs` ile zaman-sınırlıdır. `BrowserViewerRequestJson`, bir viewer slot'u talep eder. Bu **browser control lease**'ini §6'daki ilgisiz SEV-SNP **chip-seçimi "bid"i** ile karıştırmayın — bkz §11.

### 4.6 Agentspaces tunnel framing'i (`found`)

`HatchSpaceTunnel`, bir WebView'ı `hatch_vm_*` üzerinden CVM-barındırılan "spaces" uygulamalarına `/spaces/cvm/<slug>`'da proxy'ler. Küçük JSON zarf protokolü: `{"type":"http.res",id,status,streaming}`, `{"type":"http.end",…}`, `{"type":"http.err",…}`, artı cache-bozan bir push `{"type":"hatch:space:query-invalidated","spaceSlug":…,"payload":{"queryKeys":[…]}}`. Relay etmeden önce **hop-by-hop ve kimlik-belirleyici header'ları çıkarır** — blocklist şunları içerir: `authorization, cookie, host, origin, x-forwarded-*, x-real-ip, x-noise-connection-id` — CVM tarafının yalnızca Noise connection id üzerinden erişilen gerçek bir HTTP sunucusu sonlandırdığını doğrular.

---

## 5. Agent workspace'i

Aşağıdaki her özellik §4.3'teki dört `NoiseHatchVmTransport` fiili üzerine inşa edilmiştir, yani aşağıdaki her path literal'i, CVM'e Noise tüneli *içinde* bir HTTP isteğidir. Bootstrap: `HatchBootstrapRequest`, bir `channel.bootstrap` subscribe metodunda `{"sections":[…]}` post eder ve geri `{"accepted":[…]}` okur — istemci hangi workspace bölümlerinin push edilmesini istediğini beyan eder. `HatchSpacesSync`, sadece "Hatch bağlı ve bir VM endpoint'i var"ken başlar (`found` log koruyucuları).

### 5.1 Agent spaces

Bir **space**, string bir `slug` ile adreslenen, CVM içinden sunulan agent-barındırılan bir mini web uygulaması / etkileşimli sonuç sayfasıdır. Telefon HTML'i doğrudan hiç almaz — yerel bir WebView (`HatchSpaceActivity`), CVM'in HTTP yanıtlarını frame-frame geri stream eden tünele (§4.6) yönlendirilir, bu yüzden bir space, statik bir artifact değil canlı, durum-tutan bir uygulama olabilir.

| eylem | metod + path | notlar |
|--------|---------------|-------|
| katalog | `GET /spaces/v2` | `{"spaces":[{"slug","preview_card_url","preview_image",…}]}` |
| paylaşım-durumu | `GET /spaces/share/<slug>` | paylaşılmış+herkese-açıksa bir paylaşım URL'i döndürür |
| yayınlama | çok-adımlı (`publish`/`post`/`poll`) | "onay gerekiyor" döndürebilir |
| yayından kaldırma | `DELETE /spaces/share/<slug>` | |
| silme | `DELETE /spaces/v2/<slug>?source=space` | |
| artifact pinleme / pin kaldırma | `POST /api/artifacts/pin {"artifact_ref":…,"pinned":bool}` | bir space'in çıktısını artifact olarak pinler |

Gerçek-dünya örneği (`inferred`): kullanıcı "200€'nin altında Lizbon'a uçuşları takip et" der; Muse bir tracker space inşa eder; kullanıcı onu canlı açar, paylaşılabilir bir link yayınlar ve en iyi sonucu artifact olarak pinler.

### 5.2 Feed ve activity

`HatchFeedApi`, her biri **unit**'ler (`unit_id, title, kicker, emoji, body_md, days`) tutan tarihli bir **edition**'lar digest'ini çözer — agent'ın periyodik brifingi. Activity timeline'ı tarafından beslenir: `GET /api/activity?limit=200`, kayıtlara (`timestamp, type, status, title, subtitle, messageId, taskLabel, details.goal{…}`) çözülür, her kaydı bir sohbet mesajına ve opsiyonel olarak bir goal'a bağlar. Bağımsız Feed giriş noktası 41.6'da debug-gated'dir (`str5508` "[Debug Only] Feed"); onu besleyen activity timeline'ı değildir.

### 5.3 Goals

`HatchGoalsApi`: liste `GET /api/goals?<query>`, detay `GET /api/goals/<goal_id>`. Bir goal kalıcı bir hedeftir: `{goal_id, title, emoji, summary, momentum_status, sub_goals:[…], updates:[{text, effective_at}]}` — bir sağlık durumu ve agent'ın eklediği zaman-damgalı bir güncelleme kaydı olan kalıcı bir hedef. Giriş debug-gated'dir (`str5511` "[Debug Only] Goals").

### 5.4 Ideas

Kullanıcının **Execute** veya **Cancel** edebileceği agent-önerili, çalıştırılabilir eylemler (`HatchIdeaDetailBottomSheet`). String'ler: "This idea is already running.", "This idea isn't available anymore.", "No ideas right now. Check back later.", "Couldn't start that idea. Try again." Örnek: agent "Draft the Q3 recap" önerir; Execute'a dokunmak feed/activity'de kaydedilen çalışan bir görev başlatır.

### 5.5 Artifacts ve workspace medya/dosyaları

Artifact'lar agent-üretimi çıktılardır (belge, görüntü, hesap tablosu, bir space'in sonucu), `/api/artifacts/pin` üzerinden pinlenir/pin'i kaldırılır. Agent'ın dosyaları **gerçek, agent-başına bir CVM dosya sisteminde** yaşar (`com.whatsapp.bot.infra.vmmedia.HatchWorkspaceMediaApi`):

| çağrı | path | şekil |
|------|------|-------|
| kütüphane | `POST /fs/library {"preset":"media","limit":n,"offset":m}` | `{entries:[{path,size,modified_ms}],total,has_more}` |
| ham | `GET /fs/raw/<path>` | ham byte'lar |
| küçük resim | `GET /fs/thumbnail/<path>?p=sm` | |
| silme | `POST /fs/delete {"path":…,"recursive":false}` | |

Silme-onayı string'i: "This file will be removed from your agent's files. You can't undo this."

### 5.6 Identity belgeleri

Agent'ın "about me" belgeleri, ayrı bir depo değil, **aynı VM dosya sisteminde düz-metin dosyaları** olarak saklanır: `GET /fs/read {path,offset,len}` → `{text,bytes,eof,not_found}`; `POST /fs/write {path,text|bytes,offset,append,overwrite,create_parent}`. Kullanıcı, agent'ın daha sonra kalıcı context olarak okuduğu belgeleri düzenler.

### 5.7 Approvals ve approval geçmişi

**Canlı kapı:** riskli/geri döndürülemez bir eylemden önce agent bir onay yükseltir (`HatchBrowserPreviewActivity`, `str54e1` "Approval required"). **Geçmiş/audit:** `GET /approvals/history?record_schema=snapshot_v1&limit=50`, `next_cursor` ile sayfalanan, her onay için yapılandırılmış bir kayda çözülür: `{approval_id, status, decision, outcome_label, summary_title, purpose_summary, scope_summary, requested_at_ms, permission_question, payload_preview, request_preview_document, display_name, icon_key, blocks, rows, fields, items, links, attachments, version, truncated}`. Giriş debug-gated'dir (`str54e8` "[Debug Only] Approval history"), alttaki log değildir.

### 5.8 Zamanlanmış görevler — üç ayrı uygulama

| # | Yüzey | Transport | Operasyonlar | İstemci-erişilebilir mi? |
|---|---------|-----------|-----|--------------------|
| a | 1:1 Meta AI hatırlatıcıları (`com.whatsapp.metaai.tasks`) | `whatsapp-android-www` üzerinden düz MEX | **`GetMetaAiReminders`**, **`DeleteMetaAiReminder`** | **Evet-gibi** — isim-tabanlı persisted-query MEX, attested/native engel yok |
| b | Grup zamanlanmış görevleri (`com.whatsapp.bot.group.groupinstructions.impl`, 41.6'da yeni) | `whatsapp-android-www` üzerinden düz MEX | **`GetMetaAiGroupReminders`** (param `groupId`), **`DeleteMetaAiGroupReminder`** (`groupId`, `reminderId`) | **Evet-gibi** — aynı mantık |
| c | Hatch VM zamanlanmış görevleri (`com.whatsapp.hatch.scheduledtasks.impl`) | Noise VM | tekrarlayan agent-VM çalışmaları, VM transport'u üzerinden iptal edilen | Hayır — sadece native |

9a/9b, bir üçüncü-taraf istemcinin olabilirlik dahilinde erişebileceği **tek** workspace operasyonlarıdır, çünkü ne native noise-gateway carrier'ına ne de WAFFLE onboarding'ine dokunurlar. Bir hatırlatıcı oluşturmak agent-tarafında (Meta AI sohbet tool-call'ı üzerinden) gerçekleşiyor gibi görünür, istemciye-görünür bir mutation üzerinden değil — sadece Get + Delete operasyonları mevcuttur. Her iki çift için sayısal `doc_id`'ler `unknown`'dır (isim-tabanlı persisted-query çözümü; bağımsız yakalanmamıştır). Group-instructions yüzeyi de bir yöneticinin grubun Meta AI'ını (kurallar, referans belgeler, ton) `CustomizeGroupMetaAiActivity` üzerinden yapılandırmasına izin verir — bitişik UI, kendisi bir zamanlanmış-görev operasyonu değildir.

### 5.9 Connector'lar ve secure credential store

Bir **connector**, agent ile harici bir servis arasında kayıtlı bir bağlamadır. Kullanıcı bir kez kimlik doğrular (OAuth / API key / kullanıcı adı+şifre / FoA / Stripe / Messenger), ve ortaya çıkan credential **CVM içinde sunucu tarafında, hiçbir zaman Android Keystore'da değil** saklanır — `SecureCredentialVault`, tüm operasyonları aynı VM Noise-HTTP transport'u üzerinden HTTP çağrıları olarak gerçekleştirir. `securecredentials/` içinde hiçbir yerde `KeyStore`, `EncryptedSharedPreferences` veya `AndroidKeyStore` referansı yoktur.

Credential endpoint'leri (`found`, Noise VM kanalı üzerinden):

| path | rol |
|------|------|
| `POST /v1/credentials/capture` | yakalanmış bir credential'ı push et |
| `POST /v1/credentials/catalog/update` | upsert; görülen alanlar: `username`, `password`; `JA9` wireValue enum'u üzerinden izin |
| `POST /v1/credentials/catalog/delete` | `{id}` → `{ok}` |
| `GET /v1/custom-connectors/list` | |
| `POST /v1/custom-connectors/register` | API-key şekli `{connector, api_key:{key}, replace_existing}` veya OAuth şekli `{connector, oauth_bootstrap:{client_id, client_secret?,…}, replace_existing}` → `authorize_url` |

Connector kataloğu + bağlanma akışları (`found`, aynı kanal üzerinden): `GET /api/connectors?surface=settings&icon_cdn=whatsapp` → `{connectors:[{id,name,description,icon,state,is_custom,management_kind,supports_multiple_accounts,consent}]}`; connector-başına bağlanma-bilgisi (`/connectors/<id>/connect/info`) ve OAuth, API key, kullanıcı adı/şifre (`two_factor_required`/`attempts_remaining`/`login_timeout_remaining_secs` ile), **FoA** (Family-of-Apps hesapları), **Messenger companion** (PIN-gated sohbet bağlama) ve **Stripe link** (ödemeler) için tip-özel auth path'leri. İzinler connector-başınadır (`GET/SET /permissions/connectors/<id>`, UI string'i "Agent permissions"). Özel connector'lar açık bir incelenmemiş-kod uyarısı taşır ("Meta doesn't review custom connectors… supervise your agent's use").

Tasarım olarak, agent **ham sırları görmez**: "Securely store passwords for your agent to use", "Shared with your agent without saving". **Sanal kart** eylemi (`HatchConnectorCardActionActivity`), agent'ın ödemeler için kullandığı tek-kullanımlık bir kart basar, böylece gerçek kart numarası asla açığa çıkmaz ("The agent will never see your credit card"). APK içinde `assets/api_key.txt` mevcuttur ve brain'in evidence contract'ına göre credential materyali olarak ele alınır — burada açılmaz/alıntılanmaz; hatch-api/GraphQL control plane'i için bir istemci/uygulama-seviyesi API key olduğu, kullanıcı-başına bir sır olmadığı `inferred`'dir.

**§5'in tümü için erişilebilirlik:** sadece native. Yukarıdaki her path literal'i APK'dan geri kazanılabilir; ama bunların hiçbiri bir üçüncü-taraf istemciden sürülemez, gözlenemez (Noise tüneli içinde şifrelidir) veya taklit edilemez, çünkü bu çağrıların her biri §4'ün attested transport'una artı WAFFLE-provision edilmiş bir VM'e gerek duyar.

---

## 6. CVM identity kurtarma — Vesta OPAQUE PIN sistemi (`hatch/cvm`)

### 6.1 "sanal-kart kasası" çerçevelemesinin düzeltilmesi

Daha önceki bir araştırma geçişi (2.26.45.10), `hatch/cvm` + `hatch/cvm/pin`'i "PIN-gated sanal-kart kasası" olarak tanımlamıştı. **Bu çerçeveleme kripto katmanında yanlıştır.** İki ilgisiz alt sistemi birbirine karıştırır:

- **`hatch.connectors` / `HatchConnectorCardActionActivity`** (§5.9) — üçüncü-taraf bir ödeme rayı (büyük olasılıkla Stripe) için gerçek, ayrı bir connector-grant akışı. Hiçbir `com.whatsapp.hatch.cvm` veya `com.facebook.vesta` sınıfına **sıfır kod referansı** vardır (kontrol edildi: `hatch.connectors` smali'sinden `HatchCvmPinActivity`/`HatchCvmVestaClient`/`HatchCvmKeyService`'e çapraz referans yok).
- **`hatch.cvm` / `hatch.cvm.pin`**, bir kart deposu değil, agent'ın **confidential-VM identity ve chip-attestation enrollment sistemidir**. **Hiçbir türde ödeme verisi** saklamaz — paket içinde hiçbir yerde PAN/CVV/fatura alanı yoktur. Koruduğu şey, CVM için AMD SEV-SNP donanım-chip seçimine bağlı, **PIN parola olarak kullanılan bir OPAQUE password-authenticated key exchange ile kurtarılan bir cihaz/VM identity sırrıdır**.

PIN **sadece-yerel bir kilit açma değildir**: `HatchCvmKeyService`'in login yolu, herhangi bir yerel key materyali türetilmeden/geri yüklenmeden önce bir Meta backend'ine (`hatch-api.meta.ai/hatch/vesta-auth/*`, düz HTTPS) gerçek bir OPAQUE exchange'i round-trip eder. Yanlış bir PIN, sadece yerel bir hash'e karşı değil, **sunucu tarafında** başarısız olur ("wrong pin", "crypto failed").

Kritik olarak, bu trafik `/hatch/vm/wake`'le (§3.3) aynı control-plane host'una, `hatch-api.meta.ai`'a **düz HTTPS'tir** — attested Noise-gateway-over-Tigon VM kanalı **değildir**. Bu yüzden §4/§5'teki genel "transport ile aynı sert engeller" iddiası burada uygulanmaz: bu alt sistem için gerçek engel attested-transport türünden değil, kriptografik türdendir.

### 6.2 Native yüzey

`com.facebook.vesta.VestaClient`, **`libvesta_client_jni.so`**'yu yükler (2.26.45.10'da yeni). Üzerinde bildirilen tüm 19 native metod, ek olarak bir post-quantum KEM/signature katmanıyla sarılmış bir **PIN-parola-olarak OPAQUE PAKE**'i, artı bir cihaz-bağlı "HSM key" doğrulama adımını uygular:

| native metod | rol |
|---|---|
| `getApiVersionNative` / `getProtocolVersionNative` | versiyon müzakeresi |
| `beginLoginNative` / `finishLoginNative` (×2 overload) | OPAQUE login adımları 1 ve 2 (oturum/export key materyali üretir) |
| `beginRegisterNative` / `finishRegisterNative` / `finishRegisterProtoNative` | OPAQUE kaydı (yeni bir PIN kaydı) |
| `unpackLoginPayloadNative` / `unpackLoginPayloadProtoNative` | sunucunun escrow'lanmış login payload'ını çözme |
| `validateHsmKeyNative` / `validateHsmKeysWithOtaBundleNative` | opsiyonel bir cihaz-key-rotation OTA bundle'ıyla donanım-destekli bir key çiftini doğrulama |
| `verifyRestoreHistoryNative` | önceki bir restore/kurtarma geçmişi kaydını doğrulama |
| `pqWrapFinishLoginNative` / `pqWrapFinishRegisterNative` / `pqUnwrapFinishLoginResponseNative` | login/register payload'larının post-quantum sarma/açma işlemi |
| `pqWrapSchemeNative` | hangi PQ scheme'in kullanıldığı (`unknown` dönüş değeri — Frida gerekiyor) |

`libvesta_client_jni.so`, Noise-gateway carrier'ı gibi, opak SUPERPACK blob'u içinde paketlenmiştir — bu geçişte byte-exact statik çıkarım mümkün olmamıştır. Aynı build'de bulunan `libvoprf-ed25519.so`, bir OPRF/VOPRF ilkeliyle (OPAQUE'in temel yapı taşı) tutarlıdır ama `VestaClient`'a bağımsız olarak çapraz bağlanmamıştır — makul bitişik bir kütüphane olarak kayıtlı, aynı uygulama olduğu kanıtlanmamıştır (`unknown`).

### 6.3 Wire endpoint'leri — `hatch-api.meta.ai`'a düz HTTPS

| path | rol |
|---|---|
| `POST /hatch/vesta-auth/begin-login` | OPAQUE login adımı 1 |
| `POST /hatch/vesta-auth/finish-login` | OPAQUE login adımı 2, escrow'lanmış payload'ı döndürür |
| `POST /hatch/vesta-auth/begin-register` | OPAQUE kaydı adımı 1 (yeni/değiştirilmiş PIN) |
| `POST /hatch/vesta-auth/finish-register` | OPAQUE kaydı adımı 2 |
| `GET /hatch/vesta-auth/user-info` | `is_registered` + deneme/kilitleme sayaçları |
| `GET /hatch/fetch_vms?notary_token=true[&vm_id=]` | kullanıcının CVM'(ler)ini listeleme/çözme |
| `POST /hatch/lease_vm` / `POST /hatch/cold-lease-cvm` | bir CVM örneğini kiralama (sıcak / soğuk) |
| `GET /hatch/cvm-replace-state?env_id=` | CVM durum-makinesi geçişi |
| `GET /hatch/cvm-chip-allowlist?env_id=` | bu CVM için hangi SEV-SNP chip ID'lerinin izinli olduğu |
| `POST /hatch/cvm-chip-selection` | chip seçimini/teklifini commit etme |
| `GET /hatch/onboarding_statuses` | onboarding durum kontrolü |
| `POST /hatch/vm/wake` | CVM'i uyandırma/sürdürme (§3.3'te de) |

Bunların hiçbiri `/v1/noise`'a veya `hatch_vm_*` fiillerine dokunmaz — §6.1'in düzeltmesini doğrular. `/hatch/cvm-chip-allowlist` ve `/hatch/cvm-chip-selection`, SEV-SNP "pinned to specific chip IDs" attestation modu için §4.2'nin sadece bir native constructor imzası olarak bulduğu şeyin ilk **somut wire kanıtıdır**.

Wire DTO'ları (`kotlinx.serialization` serial-name alanları, obfuscated Java alan adları değil), OPAQUE'in kendi **L1/L2/L3** üç-mesajlık exchange isimlendirmesini (`base64url_encoded_opaque_l1/l2/l3`, artı `_sig` varyantlarını), cihaz-bağlı **"island" RSA/Ed25519 public key'lerini** (`unknown` kökeni — HSM/Keystore vs. bir Vesta-dahili format) ve yerel bir journal'ı içerir (`HatchCvmJournal`: `candidate_chip_ids`, `accepted_chip_ids`, `bid_state` enum `PENDING/ACCEPTED/RETIRED`, `abra_user_id` — `GraphQlHatchAbraTokenProvider` ile aynı bearer identity'si).

### 6.4 PIN'in gerçekte neyi gated ettiği

`HatchCvmKeyService.A00` (kurtarma yolu): (1) OPAQUE login'i çalıştırır (`begin-login` sonra `finish-login`, native matematik); (2) sadece başarılı olursa, `HatchCvmKeyProviderImpl`, gerçek yerel key materyalini escrow'lanmış login payload'ından türetir/geri yükler; (3) cihaz-key uyuşmazlığı veya açık sıfırlama için bir wipe yolu vardır. **Gerçek bir client↔server OPAQUE exchange'ini tamamlamak için doğru bir PIN gereklidir** — sunucu, escrow'lanmış payload'ı sadece doğru bir finish-login'de serbest bırakır, oran-sınırlı ve sunucu tarafında doğrulanmış (her yanıtta `attempts_remaining`, `login_timeout_remaining_secs`). Cihaza sahip ama PIN'e sahip olmayan bir saldırgan, bunu yerel olarak brute-force edemez. Korunan sır, bu kullanıcının confidential-VM oturumunu sürdürmek için gereken **CVM/cihaz-identity key materyalidir** — bir ödeme credential'ı değil.

Ayrı olarak, `HatchCvmPinReminder`, sadece bir "PIN ayarlamayı hatırlat" bildirim durumunu şifrelemek için **sadece-yerel** bir AES/GCM key'i kullanır (alias `hatch:pin-reminder:v1:...`) — Vesta exchange'iyle ilgisizdir ve bu alt sistemdeki wire-üzerinde-gözlenemeyen tek kripto parçasıdır.

### 6.5 §6 için erişilebilirlik hükmü

Wire schema tamamen geri kazanılabilir (yukarıda); transport düz HTTPS'tir, prensip olarak WAFFLE attestation'ı veya native Noise-gateway carrier'ını yenmeden MITM-gözlenebilir. Ama **gerçekte katılmak** (gerçek bir login/register) sadece APK'dan mümkün değildir: her istek/yanıt alanı, `libvesta_client_jni.so` içindeki native OPAQUE + post-quantum sarma/açma operasyonları tarafından üretilir veya tüketilir, superpack içinde paketlenmiştir, byte-exact çıkarım mevcut değildir. Bir istemci, JSON *şeklini* yakalayabilir ve tekrar oynatabilir ama geçerli bir `opaque_l1`/`l3`, island key-pair kanıtı veya PQ-sarılmış bir payload hesaplayamaz — §4'teki attested-transport engelinden yapısal olarak farklı bir **kriptografik** engel.

---

## 7. Monetizasyon — Hatch ücretli abonelik katmanı

2.26.45.10-dönemi bir abonelik kümesi, Muse için gerçek, faturalanan bir katman ekler. Satın alma akışı (`inferred` zincir, her adım tek tek `found`):

1. İstemci, feature flag'i **`ai_hatch_in_app_subscriptions_enabled`**'i kontrol eder (log: "`ai_hatch_in_app_subscriptions_enabled` is off"). Bunun için sayısal bir flag ID'si bulunamadı — sadece isimle referanslanır.
2. Katman sabiti **`NME_SUBSCRIPTION`**; ürün detayları katman başına çekilir (`HatchSubscriptionPurchase$launch$2`, log "Fetching product details for tier"; katman adı interpolasyonludur, hardcoded bir SKU değil).
3. Compliance kontrolü: **`WamoSubGetComplianceInfo`** (`whatsapp-android-mex`, isim-tabanlı, çağrı noktasında girdi alanı ayarlanmamış — sadece oturum/identity-kapsamlı).
4. Ödemeler token basımı: **`HatchGenFrlPaymentsAccessTokenMutation`** (`GraphQlHatchFrlPaymentsTokenProvider`, namespace `whatsapp-android-www`; "FRL" açılımı bu geçişte hiçbir string'de bulunamadı — `unknown`).
5. Google Play Billing başlatma (`HatchManageSubscriptionViewModel$openBilling$1`) — paylaşılan bir Meta commerce SDK'sı üzerinden standart Android `BillingClient` (`com.facebook.payments.dcp.xapp.*`), `app="WHATSAPP"` etiketli.
6. Satın alma üzerine, sunucu tarafı yerine getirme reconciliation'ı (`HatchSubscriptionPurchaseReconciler`), muhtemelen **`DCPFulfillIAPTransactionsMutation`** üzerinden (`pay_dcp_fulfill_iap_transactions`, doğrudan Pando isteği, alanlar `platform`/`app`/`purchase_tokens`/`subscription_purchase_tokens`/`upl_session_id`, bu çağrı noktasında hepsi zorunlu) — bu reconciler'ın kullandığı tam çağrı olduğu bağımsız doğrulanmamıştır (`unknown`).

Persisted-query kataloğunda sadece deklare edilmiş dört ek operasyon (`IACQueryProductInfo`, `IACQuoteDisplay`, `IACSandboxPlatformMode`, `DCPInternalSandboxCreateSessionMutation`), smali'nin hiçbir yerinde **çağıran bir sınıf bulunamamıştır** — bunun dead/gelecek kod, bir sunucu/flag kapısı, veya düz bir grep'in kaçırdığı string-birleştirilmiş bir çağrı noktası mı olduğu `unknown`'dır.

**Erişilebilirlik:**

| operasyon | namespace | gereksinim | üçüncü-taraf istemci tarafından erişilebilir mi? |
|---|---|---|---|
| `WamoSubGetComplianceInfo` | `whatsapp-android-mex` | sadece doğrulanmış bir mex oturumu | **Evet, prensip olarak** — düz parametresiz mex query'si |
| `HatchGenFrlPaymentsAccessTokenMutation` | `whatsapp-android-www` | doğrulanmış oturum | **Transport-erişilebilir**; basılan token'ın amaçlanan akış dışındaki değeri `unknown`'dır |
| `DCPFulfillIAPTransactionsMutation` | `whatsapp-schema` (Pando) | gerçek bir Google-imzalı Play Billing satın alma/abonelik token'ı | **Hayır** — istek şekillendirilebilir, ama imzalı bir `com.whatsapp` context üzerinden gerçek bir Play Billing satın alması olmadan içine doğru hiçbir şey konamaz |
| `IAC*` / `DCPInternalSandboxCreateSessionMutation` | `whatsapp-schema` | unknown (çağıran sınıf bulunamadı) | **Unknown** |
| Google Play Billing'in kendisi | n/a | Play Store + imzalı uygulama context'i | **Hayır** — bu bir WhatsApp sunucu çağrısı bile değil |

---

## 8. Erişilebilirlik hükmü

| Bileşen | Transport | Engel | Üçüncü-taraf (Baileys/velowa) istemciden erişilebilir mi? |
|---|---|---|---|
| Agent spaces, feed/activity, goals, ideas, artifacts, workspace medya/dosyaları, identity belgeleri, approvals+geçmiş, Hatch VM zamanlanmış görevleri, connector'lar (tüm akışlar), secure credential store | Attested Noise VM kanalı (§4) | native noise-gateway carrier `.so`'su + WAFFLE onboarding'i | **Hayır** |
| Control plane (VM wake, Abra token, pairing URL) | `hatch-api.meta.ai`'a düz HTTPS | WAFFLE-gated provisioning (sunucu onsuz çalışan bir VM vermez) | **Hayır** (schema MITM-gözlenebilir; bağımsız sürülebilir değil) |
| CVM identity/PIN kurtarma (`hatch/cvm`, Vesta OPAQUE) | `hatch-api.meta.ai`'a düz HTTPS | `libvesta_client_jni.so` içinde native OPAQUE + post-quantum matematik | **Hayır** — kriptografik bir engel, attested-transport engeli değil |
| 1:1 hatırlatıcılar — `GetMetaAiReminders` / `DeleteMetaAiReminder` | düz MEX, `whatsapp-android-www` | bulunamadı | **Evet-gibi** (doc_id `unknown`) |
| Grup hatırlatıcıları — `GetMetaAiGroupReminders` / `DeleteMetaAiGroupReminder` | düz MEX, `whatsapp-android-www` | bulunamadı | **Evet-gibi** (doc_id `unknown`) |
| Abonelik compliance bilgisi — `WamoSubGetComplianceInfo` | düz MEX, `whatsapp-android-mex` | bulunamadı | **Evet, prensip olarak** |
| Ödemeler token basımı — `HatchGenFrlPaymentsAccessTokenMutation` | düz GraphQL, `whatsapp-android-www` | transport seviyesinde yok; token'ın başka yerdeki pratik değeri unknown | **Transport-erişilebilir** |
| IAP yerine getirme — `DCPFulfillIAPTransactionsMutation` | düz Pando GraphQL, `whatsapp-schema` | gerçek bir imzalı Play Billing token'ı gerekiyor | **Hayır** (gönderilecek doğru bir şey yok) |
| `IAC*` / sandbox IAP operasyonları | `whatsapp-schema` | çağıran sınıf bulunamadı | **Unknown** |
| richResponse quiz (bot.quiz) | yerel mesaj mağazası | yok — bir VM özelliği değil | payload geri kazanılabilir; normal bir bot mesajı olarak gelir |

"Evet-gibi"/"Evet, prensip olarak" satırları, bu alt sistemin istemciye-erişilebilir yüzeyinin **tamamıdır**. Diğer her şey — agent'ın büyük çoğunluğu — ya native Noise-gateway carrier'ını artı geçerli bir WAFFLE attestation'ını, ya da bu APK'dan statik olarak çıkarılamayan native OPAQUE/post-quantum kriptografiyi gerektirir.

---

## 9. Baileys / velowa

**Hüküm: bu alt sistem bir üçüncü-taraf istemci için JS-imkânsızdır, nokta — eksik bir özellik değil, yapısal bir sorundur.** velowa (bu belgelerin arkasındaki aktif istemci projesi), orijinal araştırma geçişinin verdiği aynı nedenlerle Hatch/Muse agent-browser VM'ini veya workspace'ini uygulayamaz:

| Engel | JS/WASM'de neden etrafından dolaşılamaz |
|---|---|
| `libwa-noise-gateway-carrier-jni.so` | VM kanalı için tüm Noise handshake'i ve WebSocket framing'i, opak SUPERPACK blob'u içinde native koddur. Buna karşı yeniden uygulanacak bir protokol belgesi yoktur — wire şekli (query param'ları, `/v1/noise` path'i, HTTP-over-Noise fiilleri, noVNC RFB subprotocol'ü) yukarıda geri kazanılmıştır, ama gerçek Noise kriptografisi (key türetme, frame doğrulama) sadece bu `.so`'ya derlenmiş olarak var. Bunu yeniden uygulamak, bir spesifikasyona karşı bir istemci yazmak değil, soyulmuş bir native kütüphaneyi reverse-engineer etmek demektir. |
| WAFFLE resmi-istemci attestation'ı | Herhangi bir Noise kanalı açılmadan önce VM onboarding'ini gated eder. Bir üçüncü-taraf istemci geçerli bir WAFFLE token'ı üretemez, bu yüzden en baştan bir VM'i provision edemez — bu, Noise handshake'ine bir deneme girişimini bile bloklar. |
| `libvesta_client_jni.so` (OPAQUE + PQ) | Yukarıdakinden ayrı: identity-kurtarma trafiği (§6) düz HTTPS ve gözlenebilir olsa bile, istemci-tarafı OPAQUE matematiği (`opaque_l1`/`l3`, "island" key-pair kanıtları, post-quantum sarma) native'dir. JSON şeklini yakalamak, size geçerli bir istek hesaplamak için hiçbir şey vermez. |
| AMD SEV-SNP attestation'ı | İstemciye ortogonal — bu *sunucunun* VM'inin resmi uygulamaya gerçek olduğunu kanıtlamasıdır — ama tüm tasarımın her iki uçta native, attested bir eş varsaydığını doğrular. |
| Tigon | Meta'nın dahili çapraz-uygulama native HTTP stack'i, §4 ve §6'daki her isteği taşır; istek nesneleri herkese açık, versiyonlanmış bir wire formatı değildir. |

velowa'nın (veya herhangi bir protokol istemcisinin) yukarıdakilerin hiçbirine dokunmadan erişebileceği şey: dört isim-tabanlı MEX hatırlatıcı operasyonu (§5.8) ve abonelik-compliance/ödemeler-token GraphQL operasyonları (§7) — bunların tümü, velowa'nın bu repodaki diğer her şey için zaten konuştuğu aynı düz WA MEX/GraphQL transport'una biner. Burada kod örneği verilmemiştir, çünkü bu raporun kaynak materyalinin hiçbiri, §5.8/§7/§8'de zaten listelenmiş operasyon adları ve parametre şekilleri dışında bu operasyonlar için somut bir istek/yanıt yakalamamıştır; payload byte'larını icat etmek, evidence kademesini yanlış temsil eder.

---

## 10. Hata durumları / dikkat edilmesi gerekenler

| Belirti | Neden | Not |
|---|---|---|
| "Computer is turned off on this VM" | tam masaüstü yüzeyi için VM provision edilmemiş/uyanık değil | `HatchComputerActivity` string'i |
| "Approval required" bir eyleme asla çözülmüyor | kullanıcı approval gate'ini onaylamadı | tasarım gereği — insan-devreli |
| "This idea isn't available anymore." / "This idea is already running." | idea kartı yerine geçildi veya zaten çalışıyor | `HatchIdeaDetailBottomSheet` |
| "No goals yet" / "No ideas right now. Check back later." / "No approvals yet" | boş workspace bölümleri, bir hata değil | |
| "Couldn't load your agent's files" | `/fs/library` veya `/fs/raw/` çağrısı Noise tüneli üzerinden başarısız oldu | |
| `PrivateSearchSessionManager`-tarzı "thread superseded by a newer search, refusing" (bitişik TEE sistemi, Hatch değil) | sadece iki sistem arasında hata string'lerinin çapraz-kirlenmesini önlemek için §11'de listelenmiştir | bkz Ayırt Edilmesi Gereken Noktalar |
| 400 "already exists; set replace_existing=true" | `replace_existing` flag'i olmadan özel-connector kaydı | `HatchConnectorsListRequester` |
| "wrong pin" / "finish-login crypto failed" | OPAQUE login sunucu tarafında başarısız oldu | `attempts_remaining`/`login_timeout_remaining_secs` ile oran-sınırlı |
| "hsm key missing" / "hsm key invalid" / "hsm key check failed" | Vesta kurtarma yolu içinde cihaz-bağlı HSM key doğrulaması başarısız oldu | §6.4 |
| `noise/gave-up limit=deadline` | VM Noise kanalı açma bütçesi (60 s) aşıldı | `NoiseVmConnection` |
| `NoiseHandshakeOutcome.VERIFICATION_FAILED` | Noise-gateway handshake'inde attestation kontrolü başarısız oldu | §4.2 |
| "`ai_hatch_in_app_subscriptions_enabled` is off" | abonelik feature flag'i sunucu tarafında devre dışı | §7 |
| "HatchSubscriptionPurchase/purchase no compliance data" | bir satın alma denemesinden önce `WamoSubGetComplianceInfo` sonucu eksik | §7 |

---

## 11. Ayırt edilmesi gereken noktalar — karıştırılmaması gerekenler

| Karıştırılmaması gereken | Gerçek |
|---|---|
| Hatch/Muse agent (bu rapor) vs. **Meta AI sohbeti** (`WA_META_AI.md`) | Meta AI, normal mesaj proto'sunda `botInvokeMessage`/bot JID'leriyle erişilen bir bot kişisidir; Hatch/Muse, uzak bir attested VM'i süren ayrı bir agent'tır. Bir kısım altyapıyı paylaşırlar (`ProtocolMessage.aiMetadataOperation` üzerinden Hatch JSON metadata kanalı, Hatch bot JID'i `1807055946647697@bot`'a reklam edilen yetenek flag'leri) ama mimari olarak ayrı alt sistemlerdir |
| Hatch/Muse VM'i vs. **Private Processing / TEE cluster'ı** (sohbet-context AI'ı, Private Search) | TEE cluster'ı (`ClusterFetchPrekeyBundleConnection`, `IplsdHandshakeExecutor`, `PsiSearchToolHandler`, `TeePrefixCacheAnchor`), Meta AI'ın **kendi yerel sohbetleriniz hakkındaki** soruları attested bir enclave + PSI araması üzerinden cevaplamasıdır — Hatch agent-browser VM'iyle hiçbir ilgisi yoktur. Private Search'ün *sorgu gönderimi* düz bir bot-sohbet mesajına biner (erişilebilir), PSI/enclave hesaplamasının kendisi ise native kalır — bu raporun herhangi bir yerindekinden farklı bir erişilebilirlik şekli |
| `hatch.cvm` (identity/chip kurtarma, §6) vs. `hatch.connectors` (sanal kart / Stripe, §5.9) | Ürün çerçevelemesinde sadece gündelik "card"/"vault" sözcüklerini paylaşan iki ayrı özellik; aralarında kod bağımlılığı yok (kontrol edildi) |
| `HatchCvmPinReminder`'ın yerel AES/GCM key'i vs. Vesta OPAQUE exchange'i | Sadece-yerel bildirim-durumu şifrelemesi vs. gerçek sunucu-round-trip'li bir identity kurtarma — sadece ikincisi "sunucu tarafı" PIN gating'idir |
| "bid_state"/"chip" alanları (§6) vs. browser **control lease**'i (§4.5) | SEV-SNP donanım-chip-seçimi defteri vs. agent browser'ını kimin sürdüğü (agent/insan) — bu kod tabanında örtüşen kelime dağarcığının ("bid"/"lease"/"control") üç farklı kullanımı |
| Vesta'nın düz-HTTPS control plane'i (§3, §6) vs. attested Noise-gateway VM kanalı (§4) | Farklı transport'lar, farklı engeller (native OPAQUE matematik vs. native Noise + WAFFLE attestation) — bunları birbirine karıştırmak, attested-transport engelinin gerçekte nerede uygulandığını abartır |
| Agent spaces (§5.1) vs. agent-üretimi artifact'lar (§5.5) | Bir space canlı, durum-tutan barındırılmış bir uygulamadır; bir artifact statik bir çıktıdır (bir space'in *pinlenmiş sonucu* bir artifact olur, ama space'in kendisi çalışmayı sürdürür) |
| `com.whatsapp.bot.quiz.AiQuizViewerActivity` vs. bir Hatch özelliği | Normal bir bot mesajı olarak zaten teslim edilmiş bir richResponse quiz'ini yerel depodan okur — VM yok, ağ çağrısı yok, bu alt sistemin hiç parçası değil |

---

## 12. Baştan sona akış — bir agent-browser-task oturumu

```
[User, in chat]
    │  "book me a table for two tonight"
    ▼
[Onboarding, first use only]
    │  HatchWaffleOnboarding: official-client WAFFLE attestation
    │  HatchPairingAuthBrowsingActivity: pairing URL (account ↔ agent link)
    ▼
[Control plane]  plain HTTPS to hatch-api.meta.ai
    │  GraphQlHatchAbraTokenProvider → Abra bearer
    │  HatchVmApiClient: POST /hatch/vm/wake {vm_id, retry_count}
    │  → HatchVmEndpoint{host, auth_token, notary_token, ...}
    ▼
[Noise-gateway handshake]  native libwa-noise-gateway-carrier-jni.so over Tigon
    │  GET …<vmhost>…?auth_token&notary_token&app_id&app_version=2.26.41.6
    │  path /v1/noise, 20s handshake timeout, attestation verifier (noOp/SNP/SNP-pinned)
    ▼
[Attested Noise channel open]  (60s budget, ref-counted "holds")
    │
    ├──▶ hatch_vm_request /api/computer/subscribe  — live task state (SSE-style)
    │
    ├──▶ hatch_vm_call   — agent navigates the booking site inside the CVM
    │        │
    │        ▼
    │    [Phone shows it live]  noVNC (RFB) over JWT-bearer WebSocket, viewOnly
    │        unless user takes a BrowserControlLeaseJson "control lease"
    │
    ├──▶ Login needed → /v1/credentials/... fetched INSIDE the VM
    │        (SecureCredentialVault; raw secret never reaches the agent's
    │         reasoning context, per design)
    │
    ├──▶ Payment needed → HatchConnectorCardActionActivity mints a virtual card;
    │        real card number never exposed to the agent
    │
    ├──▶ Risky/irreversible step → HatchBrowserPreviewActivity "Approval required"
    │        user confirms → recorded in HatchApprovalHistoryApi
    │
    ▼
[Outcome]
    │  artifact/feed entry (hatch.artifacts / hatch.feed)
    │  optionally scheduled to recur (HatchScheduledTasksActivity, native VM path)
    ▼
[Noise channel teardown]  last "hold" released → noise/closed reason=unlink
```

Ayrı olarak (aynı oturumun parçası değil, düz MEX/GraphQL, attested transport dahil değil):

```
[Client]  GetMetaAiReminders / GetMetaAiGroupReminders
    │  whatsapp-android-www, name-based persisted query
    ▼
[WA server]  reminder list (status SCHEDULED/CLAIMED/FULFILLED)

[Client]  DeleteMetaAiReminder / DeleteMetaAiGroupReminder
    ▼
[WA server]  reminder removed
```
