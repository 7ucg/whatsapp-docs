<!-- src-sha1: 193c35598b4e82f9c32a0c5d2cee4dbf2d708588 -->
# WhatsApp Sunucu Güdümlü Arayüz — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** Android'de sunucu güdümlü ekranlar ve eylemler: Phoenix/FCS eylem durum makinesi (IQ `xmlns="phoenix"`, durum tipleri, choice operatörleri, resource registry), Bloks ekranları (GraphQL fetch, doc id'ler ve app-id yönlendirmesi, JSON payload, Lispy function id'leri, eylem ad alanları, component query'leri, cache'ler), native flow mesajları (NFM button registry), WhatsApp Flows (WebView bridge, SecureWebView host politikası, flow JSON), AI rich response ve FMX kartı (sunucu güdümlü olmayanlar), uygulama içi tarayıcı script'leri (iabjs bridge ve nonce), sandbox ve feature flag'ler, Baileys ile ilgisi

---

## 1. Nedir (teknik olarak)

WhatsApp Android'de tek bir sunucu güdümlü arayüz motoru yoktur. Dört bağımsız mekanizma vardır; her biri bir açıklamayı sunucudan alır (veya bir mesajdan okur) ve native kodu yönlendirir. Tüm ifadeler decompile edilmiş APK'nın statik analizine dayanır; ağ üzerinde hiçbir şey yakalanmadı. Katmanlar: **found** = kodda veya veride okundu, **inferred** = çıkarım, **unknown** = çözülemedi. Obfuscate edilmiş adlar build'e özeldir ve 2.26.41.6 içinde yeniden çözüldü.

| Mekanizma | Neyi tanımlar | Taşıyıcı | Renderer / yürütücü | Nerede kullanılır |
|-----------|---------------|----------|---------------------|-------------------|
| Phoenix (sınıf adları FCS "flow configuration service" der, log etiketi FDS) | Akış kontrolü: `resource` / `choice` / `pass` / `succeed` / `subflow` durumları | `<fds>` alt öğeli IQ `<iq xmlns="phoenix">` | `QKb` durum makinesi, resource handler'ları (`AbstractC57917Pxu`) | Ödeme onboarding'i, address message, business survey, Brezilya kart akışları |
| Bloks | Ekranlar: component ağacı + Lispy script'leri + asenkron component query'leri | `graph.<domain>/graphql` adresine HTTPS GraphQL POST | Litho/RenderCore host activity ve fragment'ları | Ödemeler, destek, abonelikler, consent, Accounts Center bağlama, minishops, anketler, Meta AI business consent |
| Native flow mesajları (NFM) | Interactive mesajlardaki butonlar (`nativeFlowInfo` name + params JSON) | Mesaj (protobuf) | `C33370Efz` dispatch'i, yaklaşık 40 eylem sınıfına | CTA butonları, `address_message`, `galaxy_message` (Flows) |
| WhatsApp Flows web uygulaması | Barındırılan bir web uygulamasının render ettiği flow JSON | `SecureWebView` içine HTTPS (`flows.whatsapp.net`) + bir `WhatsAppBridge` mesaj kanalı | `WaFlowsWebViewBottomsheetModalActivity` / `FlowsWebBottomSheetContainer` | Business formları (`galaxy_message`, flexible checkout) |

Belirleyici noktalar:

- Phoenix kontrol katmanıdır, Bloks görünüm katmanıdır. `open_bloks_screen_graphql` id'li bir Phoenix `resource` durumu bir Bloks ekranı açar; Bloks `wa.action.phoenix.*` eylemleri durum makinesine geri döner (bölüm 3.5; bağlantı adlardan çıkarılmıştır).
- Bloks MEX değildir ve IQ değildir. HTTPS üzerinden Meta tarzı bir GraphQL POST'tur (`doc_id` + `variables`) (found, `AbstractC40195HfH`). Phoenix ise IQ'dur. Flows endpoint query sonuç sınıfı (`AnonymousClass456`) Bloks response-parser tabanını paylaşır; taşıması çözülmedi (bölüm 4.5).
- Sunucu içeriği keyfi native kodu adlandıramaz. Her yol sabit bir registry'den geçer: Phoenix resource id'leri (kodda 15), Bloks function id'leri (681 adlandırılmış), NFM button adları (39), Flows bridge metotları (30), Bloks IQ xmlns allow-list'i (2 giriş).
- Bloks veya Phoenix payload'ları için payload imza doğrulaması bulunmadı. `BloksTrustedPayload` (`verifiedRoot`) mevcut ve sıfır referansı var (found, smali ve Java).
- Sunucu güdümlü olmayanlar: FMX trust kartı (istemcinin oluşturduğu sistem mesajı), AI rich response (sabit protobuf component kümesi), üç `assets/json/bloks_*_template.json` dosyası (yükleme/hata iskeletleri, ürün ekranı değil).

İlgili raporlar: AB props (`abt` IQ, flag id'leri) `WA_AB_PROPS.md` içinde; AI rich response `WA_META_AI.md` bölüm 6.3 içinde. Genie adlı bir framework bulunamadı (string araması; yokluk kanıtlanmadı).

---

## 2. Phoenix eylem durum makinesi

### 2.1 Bileşenler (found, 2.26.41.6 adları)

| Rol | Sınıf | Notlar |
|-----|-------|--------|
| Runtime | `QKb` | Log etiketi `FcsStateMachine`; `A03` bir durumu çalıştırır, `A04` `next`'i izler veya stack'i pop eder, `A05` sonlandırır |
| FDS manager | `C58392QJx` | Bir config başlatır (`A08`), IQ'yu gönderir (`A07`), yanıttan durum haritasını oluşturur (`A01`) |
| IQ builder | `C31107Dfz` (`C9E1` ile ctor), `C9E1`, `C31085Dfd` | `xmlns="phoenix"` |
| Yanıt parser'ları | `F7J` (`<iq><fds>`), `F8I` (17 ila 20, 27, 28 numaralı case'ler), `F7Y` resource, `F7Z` choice, `C34784F7b` pass, `C34783F7a` succeed, `C34785F7c` subflow, `C34786F7d` version_check | Genel öznitelik-şema parser'ı (`C197428ac`) |
| Parse edilmiş durumlar | `P2W` resource, `P2U` choice, `P2T` pass, `P2S` succeed, `P2V` subflow, `C31057DfB` version_check | Ortak kısım `P2Q`: `name`, `input_path`, `input_selector`, `next`, `result_selector`, `result_path` (`C33411Ege.A03`) |
| Runtime durumları | `C55819P7c` resource, `C55817P7a` choice, `C55818P7b` pass, `P7Z` succeed, `C55820P7d` subflow | `C58392QJx.A01` içindeki eşleme |
| Resource tabanı | `AbstractC57917Pxu` | `A02()` = resource id, `A04(...)` = param map ile yürüt, varsayılan id `throw_error` |
| Binding / registry | `C51E` (id + lazy handler), `InterfaceC148426Oz.CP3()`, birleşim `C138515tp` | Registry'ler: `C135435oi`, `C135425oh`, `C135415og`, `C53207NpW`..`C53211Npa` |
| Operatörler / hatalar / callback | `RsJ` (28 operatör), `AbstractC56245PPq`; `Q6G` (`catch`); `C57560Pry` (`A00(error, result)`, `A01(result)`) | |

### 2.2 Fetch: IQ (found, `C31107Dfz`, `C58392QJx.A07`)

```
<iq xmlns="phoenix" type="get|set" id="...">
  <fds config="<config name>" state="<start state>" parameters="<json>">
    <context ... parameters='{"session-id":"...","bloks-versioning-id":"13c6e3b8...(64 hex)"}'/>
  </fds>
</iq>
```

| Öğe | Değer | Tier |
|-----|-------|------|
| `type` | başlangıçta `get` (`A08`), `send_fds_iq` resource'u için `get` veya `set` | found |
| IQ type int'leri / timeout | 302 (get), 303 (set), 32000 ms | found |
| `state`, `parameters` | yalnızca boş değilse yazılır; `parameters` = null olmayan girdilerin JSON'u | found |
| `bloks-versioning-id` | sabit 64-hex string, her Bloks request builder'da aynı değer (bölüm 3.2) | found |
| Context node iç içeliği | JSON'u taşıyan `<context>`; iç node'un tam iç içeliği çözülmedi | unknown |

Yanıt (found, `F7J`, `F8I`):

| Öğe | İçerik | Kullanım |
|-----|--------|----------|
| `<fds>` öznitelikleri `state`, `parameters` | başlangıç ipucu | parse edilir, daha ileri izlenmedi |
| `<states start_at="...">` + `<state ...>`+ | program (bölüm 2.3) | `QKb` init, log `initializeStateMachine num_states` |
| `<next_screens>` + `<screen is_entry_screen app_id bloks_server_params sources>` | Önceden yüklenecek Bloks ekranları | `C58392QJx.A06` (preload) |
| `<screen_data parameters>` | ekran veri blob'u | parse edilir |
| `<persist_data>` + `<data ...>` | host'un tuttuğu değerler | `C58392QJx.A02` (anahtar başına callback) |

Bir IQ hatası çağırana `error` (`BtN`) olarak döndürülür ve bekleyen manager girdisi kaldırılır.

### 2.3 Durum tipleri (found)

Parser, ayırt edici listeyi kabul eder: `FDSResourceState|FDSChoiceState|FDSSucceedState|FDSPassState|FDSSubflowState|FDSVersionCheckState` (`F8I` case 27). `type` özniteliği ikinci sütundaki sabit string'dir.

| Tip | `type` | Kendi öznitelikleri | Runtime davranışı |
|-----|--------|---------------------|-------------------|
| Resource | `resource` | `id` (resource id), `parameters`, `merge`, `merge_param`, `catch` | `id`'yi registry'de arar; eksik id `ResourceNotFound` hatası verir; handler'ı çalıştırır; sonuç `merge`'e göre birleştirilir; `next`'e gider |
| Choice | `choice` | `default` (yedek next durumu), `catch`, alt öğeler `<choice choice="{json}"/>`+ (bir operatör anahtarı + `next`) | Girdi JSON'u üzerinde operatörleri değerlendirir; ilk eşleşme kazanır, yoksa `default`; en az bir choice gerekli |
| Pass | `pass` | `parameters` | Veriyi yeniden yazar ve `next`'e gider, handler yok |
| Succeed | `succeed` | yok | Terminal başarı (hatasız `A05`) |
| Subflow | `subflow` | `launch_mode` (`child` veya `embedded`), `config`, `parameters`, `catch` | `child`: yeni manager ve durum makinesi; `embedded`: aynı oturuma başka bir config çeker (`C55820P7d`'den inferred) |
| Version check | `version_check` | `default`, alt öğe `<choice>` | Parse edilir (`C31057DfB`) ancak `C58392QJx.A01` içinde dalı yoktur; durum düşürülür (found); ona geçiş `state not found for name` ile başarısız olur (inferred) |

Parser'da `fail` durumu yoktur; manifest yine de `fail`'i listeler (2.7).

Selector'lar ve veri (found):

- `input_selector` varsayılanı `"$"`; `"null"` string'i onu devre dışı bırakır (`C58392QJx.A01`). `result_selector` ve parametre birleştirme `AbstractC58328QFo` üzerinden geçer. `catch` için JSONPath tarzı bir motor kullanılır (`Q2G`, `$.[i].error_equals` gibi ifadeler) (found); selector'ların aynı motoru kullandığı inferred.
- `QKb.A03` içindeki `merge` modları: `replace` (varsayılan), `merge`, `incremental_merge`, `wae_commerce_merge` (found).
- `catch` = `{error_equals:[names], next:<state>}` JSON dizisi; boş bir `error_equals` her şeyle eşleşir (found, `Q6G.A00`). Eşleşmeyen hatalar makineyi hatayla sonlandırır (`A05`).
- Yorumlayıcının kendisinin ürettiği hatalar: `ResourceNotFound`, `FailToResume`, `unsupportedComparisonTypes`, `comparingValuesWithDifferentTypes`, `genericChoiceStateError`; handler varsayılan hatası `NOT_CATCHABLE_ERROR` (`C5I7.A03`) (found).

### 2.4 Choice operatörleri (found, `RsJ.A00`)

28 sınıf. Manifest 21 tanesini listeler; yedi eski ad yalnızca kodda bulunur.

| Grup | Adlar |
|------|-------|
| Boolean | `and`, `or`, `not`, `booleanEquals` |
| Eşitlik | `eq`, `neq`, `eq_any`, `neq_any`, `eq_path`, `neq_path`, `eq_any_path`, `neq_any_path`, `stringEquals` |
| Sıralama | `gt`, `gte`, `lt`, `lte`, `gt_path`, `gte_path`, `lt_path`, `lte_path`, `numericalEquals`, `numericalGreaterThan`, `numericalGreaterThanEqual`, `numericalLessThan`, `numericalLessThanEqual` |
| Diğer | `isPresent`, `regex_match` (`variable` + `regex_match`) |

Her operatör, choice JSON'undaki anahtarın varlığıyla seçilir (`AbstractC56245PPq.A00`); bir `JSONException` bir sonraki operatöre atlar. `_path` varyantları bir path'ten çözülen değerle karşılaştırır (addan inferred); tam çözümleme okunmadı.

### 2.5 Resource registry (found)

`InterfaceC148426Oz.CP3()` ile kaydedilir; id'ler `C05T.A00(n)` supplier'larında tutulur. `C53207NpW`..`C53211Npa` registry'leri yalnızca `L8E.A1T()` true olduğunda bir küme döndürür (`C18780mK.A03()` değeri `C21610rj.A0E`'ye eşit); bu predicate'in ne anlama geldiği unknown.

| Resource id | Handler | `phoenix-features.json` içinde | Davranış |
|-------------|---------|--------------------------------|----------|
| `open_bloks_screen_graphql` | `C954246c` | evet | Bir Bloks ekranı açar; `app_id` parametresi zorunlu (aksi halde cast başarısız olur) |
| `open_bloks_screen` | `C954346d` | hayır | Aynısı, `fetch_channel` = `GRAPHQL` (`bloks_server_params` kullanır) veya `STATIC` (`fetch_channel_params.static_url` kullanır, `should_load_bloks_through_cdn: true` ayarlar); diğer değerler exception fırlatır |
| `send_fds_iq` | `AbstractC79003We` içinde anonim | evet | Parametreler `config`, `type` (`GET`/`SET`), `state`, `parameters`; job id ile canlı bir FDS manager gerekir; eksik manager veya config hata loglar ve `NOT_CATCHABLE_ERROR` ile başarısız olur |
| `abprop_fetch` | `AbstractC79003We` içinde anonim | hayır | Parametreler `code` (int), `abprop_type` (`string`/`json`/`boolean`/`float`/`integer`), `default_value`; AB store'dan okunan `abprop_value` döndürür; `code` üzerinde allow-list görülmedi |
| `client_dasl_query` | `C954746h` | evet | `query` parametresi gerekir, aksi halde `No parameters` loglar ve başarısız olur; query bir arka plan executor'ında çalışır |
| `dismiss_bottom_sheet` | `C955346n` | evet | Mevcut sheet'i kapatır |
| `native_flow_call_manager` | `C954946j` | evet | `phone_number` gerekir; rakamlara ve `+`'ya indirger; `FLAG_ACTIVITY_NEW_TASK` ile `ACTION_DIAL` (`tel:`) başlatır (yalnızca dialer, otomatik arama yok) |
| `request_permission` | `C955046k` | hayır | Android izin isteği (`FcsRequestPermissionActivity` bağlantısı inferred) |
| `throw_error` | `C954446e` | hayır | `error` map'ini fırlatır; mesajı `error_map_type` + `code` ile arar |
| `payment_encrypt_with_public_key` | `C31703Dr4` | evet | Parametreler `data_value`, `data_type`, `key_scope`, `provider_name`, `network` (gated) |
| `br_verify_card_deeplink` | `C955446o` | evet | `app_to_app_partner_app_package`, `app_to_app_partner_intent_action`, `app_to_app_request_payload` ile paket kısıtlı `com.whatsapp.payments.phoenix.action.launch_activity_for_phoenix_result` broadcast'i gönderir (gated) |
| `br_verify_card_check_if_app_exists` | `C31702Dr3` | hayır | Gated |
| `native_br_compliance`, `native_br_p2m_checkout_address`, `native_card_encryption_resource` | `C955146l`, `C955246m`, anonim | hayır | Brezilya ödemeleri, kart olan hariç gated |

Yalnızca manifestte bulunan adlar (bu build'de registry girdisi yok): `error_response`, `native_flow_npci_common_library` (alt ağaç `mode.collect`), `native_p2m_lite_compliance`, `native_p2m_lite_hpp_checkout`, `open_bloks_screen_static`. `open_bloks_screen_static` için handler yoktur; STATIC yolu `open_bloks_screen` içinde `fetch_channel` olarak yaşar.

### 2.6 Başlatma noktaları (found)

`new C57778Pva(config, params, startState)` şu noktalarda oluşturulur: `address_message` (`C31337Djk`, NFM), `biz_survey` (`C57417PpS`), `br_merchant_onboarding` (`C33140EcF`), `br_p2m_checkout_add_card`, `br_p2p_verify_card` (`C32703EOj`) ve başlangıç durumu `DeepLink` ile sunucu adlı bir config geçiren bir deep-link girişi (`RunnableC46615KYo` case 18, referral `deeplink`). `add_card_phoenix`, `verify_card_phoenix` string'leri mevcut; config adı olarak rolleri inferred. Config programının kendisi sunucudan gelir; yetenek manifesti dışında hiçbiri gönderilmez.

### 2.7 Yetenek manifesti

`assets/versioning/phoenix-features.json` (1.218 B, 2.26.34.4 kopyasıyla aynı): üst düzey `pass`, `choice` (21 operatör), `resource` (12 id artı `input_selector`, `parameters`, `result_selector`, `result_path`), `succeed`, `fail`. Runtime'da kullanımı bulunamadı (string referansı yok); ad listesi olarak değerlendirin. Yetkili olan koddur (2.4, 2.5).

---

## 3. Bloks

### 3.1 Host yüzeyleri (found)

| Host | Rol |
|------|-----|
| `WaBloksActivity`, `WaBloksBottomSheetActivity`, `BloksCDSBottomSheetActivity`, `BloksCDSPreloadCDSBottomSheetActivity` | Tam ekran, bottom sheet, CDS (tasarım sistemi) sheet'leri |
| `WaSqBloksActivity`, `WaBloksScreenQueryFragment` | Screen-query host'ları (`screen_query` ve `legacy_screen` tipleri) |
| `WaFcsModalActivity`, `WaFcsBottomSheetModalActivity`, `WaFcsPreloadedBloksActivity`; `SurveyCanonicalBloksActivity` (+ sheet) | Phoenix'in barındırdığı ekranlar; anketler |
| Ürün host'ları | `CommonBloksActivity`, `SupportBloksActivity`, `BrazilPayBloksActivity`, `ConsumerSubscriptionBloksActivity`, `DigitalCommerceDcpBloksActivity`, `CsatSurveyBloksActivity`, `AppointmentBloksHostActivity` (exported false), `WaBackupStorageBloksActivity` (exported false) |

Hiçbir Bloks, Flows veya Phoenix activity'si intent filter bildirmez; `targetSdkVersion` 36'dır, dolayısıyla `android:exported` içermeyen activity'ler export edilmez (found, manifest). Bloks ayrıca bir `WebView` component'i gömebilir (`AndroidBridge.updateSize`, eylem `bk.action.WebViewWithOnChange`) (found).

### 3.2 Fetch: HTTPS üzerinden GraphQL (found, `AbstractC40195HfH`, `C45J`)

| Öğe | Değer |
|-----|-------|
| URL | `https://graph.<domain>/graphql<path>`; `<domain>` = pref `pref_graphql_domain`, varsayılan `whatsapp.com`; birkaç request sınıfı `facebook.com`'u zorlar; `<path>` boş veya Flows varyantı için `/extensions` |
| Query string | AB prop **549** açıkken `?_emp=1` eklenir (varsayılan false) |
| Body | JSON `{"variables": "<json string>", "access_token": ..., "doc_id": <long>, "lang": ..., "Content-Type": "application/json"}` |
| Token | ayarlıysa istek başına token, değilse istemciye gömülü statik uygulama kapsamlı bir token string'i (değer yeniden üretilmedi) |
| Header'lar | `X-FB-Friendly-Name: WABloksAppRootQuery-<app_id>`, `X-FB-Request-Analytics-Tags` |
| `variables` | `app_id`, versiyon anahtarı, `params` (JSON string), `bloks_theme_params` |
| Versiyon anahtarı adı | request sınıfına göre `version`, `versioning_id` veya `bloks_version`; değer Phoenix'tekiyle aynı 64-hex sabitidir |
| Consent öncesi varyant (`C136975rF`) | `app_version`, `locale`, `df_token`, `enc_token`, `disclosure_id`, `is_paused`, `country_code`, `encrypted_rid` ekler |
| Extensions varyantı (`C132735kG` case 2) | `extension_id` (= flow message versiyon 2, 3, 4 için `flow_id`), `business_jid`, `screen_id`, `bloks_version` |
| Hatalar | `errors[].extensions.error_code` (varsayılan 417), `is_retryable`; `error.code` 3489039 bir bütünlük kontrolü ve yeniden deneme tetikler, 1675012 `Bad Request` verir (consent öncesi yol) |

Yanıt kök alanları (`AnonymousClass451.A05`): payload `data.<root>.payload`'dır (bir JSON string).

| Doc id | Kök alan | Kullanan (found) |
|--------|----------|------------------|
| 3651100555017197 | `whatsapp_bloks_getlayout` | varsayılan rota; minishops link/pdp/storefront |
| 3958953970834604 | `whatsapp_bloks_getprivatelayout` | `C5LX.A00()` için varsayılan; minishops gizlilik bildirimi, products preview |
| 9404809712971896 | `whatsapp_bloks_getlayout` | regex ile yönlendirilen aileler (3.3) |
| 9943385105682204 | `whatsapp_bloks_getprivatelayout` | `logged_out.cxthelp.whatsapp` |
| 6019334944816363 | Flows layout (kök `whatsapp_galaxy_bloks_getflowlayout` `AnonymousClass424` içinde mevcut; ikisi arasındaki bağlantı inferred) | `com.bloks.www.whatsapp.galaxy.flow.v2`, `...commerce.galaxy_message`, `...commerce.extensions_message_v2` |
| 36103976949247233 | `wamo_bloks_get_layout` | WAMO yüzeyleri |
| 9676557989071413 | kök alana eşlenmemiş | payments sample/care, `novi.care.*`, `whatsapp.ai.biz.*` consent |

Doc id'ler 26891716230495873 (pix playground) ve 25865201793138751 yönlendirme tablolarında çözülmüş kök alan olmadan görünür.

### 3.3 App-id yönlendirmesi (found)

Bir ekran `app_id` ile adreslenir (noktalı bir ad, `com.bloks.www.*`). Yönlendirme tabloları bir `app_id`'yi `C5LX(doc id, request-factory variant)` sorgu tanımlayıcısına eşler: on sabit-küme tablosu (`InterfaceC148576Pp`: `C132235jS`..`C132335jc`) ve regex tabloları (`InterfaceC148726Qe`: `C132345jd`..`C132465jp`).

| Aile | Desen veya örnek | Doc id |
|------|------------------|--------|
| Siparişler / ödemeler hub'ı | `orders_hub(\..+)*`, `fbpay_hub`, `payment.mft.wallet.fbpay_hub`, `(payment.)?mft.wallet.*`, `payment.(bloks.(commerce|ecp).checkout|fbpay.ecp).*` | 9404809712971896 |
| `gai` / `sna` / AI sticker'ları (aile anlamı adlardan inferred) | `bloks.nme.gai`, `wa.nme.gai`, `wa.sna`, `whatsapp.ai.stickers.*` | 9404809712971896 |
| Abonelikler | `dcp.subscriptions?(\..+)*` | 9404809712971896 |
| Destek | `(csf|cxthelp)(\..+)+` | 9404809712971896 |
| Minishops | `minishops.link.app`, `.whatsapp.pdp`, `.storefront.wa` | 3651100555017197 |
| Business AI consent | `whatsapp.ai.biz.{learn_more,consent,assistant_consent,third_party_consent,meta_ai_consent}` | 9676557989071413 |
| Playground / debug | `wa.playground.payments.br.pix.*` (varyant 9) ; `whatsapp.payments.phoenix.{debug,demo_*,multi_*}`, `payments.whatsapp.f2care`, `novi.care.*` (varyant 10) | 26891716230495873 ; 9676557989071413 |

Kodda 87 ayrı literal `com.bloks.www.*` id'si bulunur; geri kalanı sunucudan gelir ve regex aileleriyle yönlendirilir. `AnonymousClass514` içinde iki desen koruması vardır: `consent(...)` id'leri `extra_params_json.whatsapp_bloks_networking_feature_override` taşıyabilir; `ptt_use_case = WALLET` olan `payment.mft.security.*` `wallet_canonical` request helper'ını seçer (found).

### 3.4 Payload formatı (found)

Streaming JSON parser `AbstractC122255Jb`; üst nesne `payload` (string) ve `layout.bloks_payload` içerir.

| `bloks_payload` anahtarı | Anlam |
|--------------------------|-------|
| `tree` | Kök component (aşağıdaki bölüm); yalnızca eylem içeren payload'larda `tree` yerine `action` |
| `ft` | Function tablosu: id'den ifade string'ine |
| `data`, `values`, `templates`, `props` | Veri kayıtları (`id`, `type`, `data`, `scoped`), değer ifadeleri, şablonlar, prop ad tablosu |
| `embedded_payloads`, `hoisted_async_components` | id'ye göre iç içe payload'lar |
| `referenced`, `referenced_external`, `referenced_embedded_payloads`, `referenced_templates`, `referenced_ft_entries`, `referenced_values`, `referenced_ct`, `ct` | Kısmi/streamed payload'lar için bağımlılık listeleri |
| `component_queries` | Asenkron component query'leri (`id`, `app_id_expr`, `params`, `client_params`, `targets`, `cache_ttl_expr`, `disk_cache_enabled`, `is_scoped`) |
| `error_attribution` | `logging_id`, `source_map_id` |
| `depth`, `step_debugger_metadata.breakpoints` | Streaming derinliği, debugger |

Ağaç kodlaması (`C5AN`): bir node, tek anahtarı bir code point olan nesnedir; o code point component id'sidir (`AbstractC105654gT.A00` = `codePointAt(0)`); öznitelik anahtarları da tek code point'tir (`!`=33 id, `#`=35 child, `&`=38, `+`=43 gölge component 13347 için). Component id'den ada harita assets içinde değildir (unknown).

Function id'leri ("Lispy", `C122545Ki`): bir script node'u, ilk öğesi function olan bir JSON dizisidir: `"#<name>"` adlandırılmış, `AbstractC111054pC.A01` ad tablosuyla çözülen noktalı bir ad veya `Integer.parseInt(s, 36)` ile parse edilen base-36 string. Tipli sabitlerin sabit id'leri vardır: 17809 `bool.Const`, 18327 `f32.Const`, 18338 `f64.Const`, 19222 `i32.Const`, 19237 `i64.Const`. Ad tablosunda 681 giriş vardır, id'ler 17293 ila 26071.

Gönderilen şablonlardan çözülenler (base-36 token, id, tablo adı; found): `e2a` 18226 `core.If`; `e25` 18221 `core.GetArg`; `e2f` 18231 `core.TakeLast`; `e1w` 18212 `core.Apply`; `dng` 17692 `bloks.GetParameter`; `dnt` 17705 `bloks.GetVariable2`; `f4g` 19600 `map.Get`; `f6m` 19678 `mins.CallRuntime`; `igq` 23930 `core.AsNonnull`; `fjm` 20146 `screen.callback.DidFetchSucceed`; `foz` 20339 `ttrc.MarkerStart` (hepsi `bk.action.` altında); `h9h` 22373 literal `null` adıyla listelenir.

`ft` ve ifade string'lerindeki `\t(...)` metin formu farklı bir serileştirmedir; aynı base-36 id'leri kullandığı, yukarıdaki çözümlemelerin tutarlı olmasından çıkar (inferred). Metin parser'ı okunmadı.

Yetenek müzakeresi (inferred): 64-hex `bloks-versioning-id` her istekle gönderilir; tablo 50 `bk.versioning.*` yetenek adı içerir (örneğin `SupportsFunctionTables`, `TemplatePayloads`, `AsyncComponentBatchedWireProtocol`, `SupportsLispySignatureMinification`). Hash'in bu yetenek kümesini tanımladığı inferred.

Gönderilen assets (`assets/json/bloks_screen_template.json`, `bloks_bottomsheet_template.json`, `bloks_cds_base_screen_template.json`, 9.028 / 9.124 / 11.443 B, 2.26.34.4 ile aynı): spinner `tree` içeren kök şablon, hedefi `genScreenContent` olan bir `component_queries` girdisi ve `embedded_payloads` içinde bir hata yedeği (üçten ikisinde `Something went wrong` / `Please try again later`). Bunlar iskelettir; ürün ekranları query sonucundan gelir.

### 3.5 Eylem ad alanları (found, `AbstractC111054pC`)

| Önek | Id tablosundaki sayı | Örnekler |
|------|----------------------|----------|
| `bk.action.core/bool/num/i32/i64/f32/string/array/map/math` | 113 | `core.If`, `core.Let`, `core.While`, `array.Map`, `string.*` |
| `bk.action.mins.*` | 36 | `CallRuntime`, `PutByVal`, `Raise` (minscript VM) |
| `bk.action.bloks.*` | 61 | `OpenScreen`, `OpenBottomSheet`, `Inflate`, `FetchAsyncComponents`, `WriteLocalState`, `ReplaceChildren`, `WriteGlobalConsistencyStore` |
| `bk.action.cds.*`, `bk.callbacks.cds.*` | 13 + | `OpenCdsBottomSheet`, `PushCdsBottomSheet`, `UnwindToScreen` |
| `bk.action.animated/animation/timer/collection/textinput/text_input/video` | 58 | Arayüz davranışı |
| `bk.action.qpl/ttrc/trace` | 14 / 11 / 2 | Gecikme işaretçileri (`ttrc.MarkerStart`) |
| `bk.action.privacy.consent.*` | 10 | `OpenFlow`, `LaunchConsent`, `ShutdownExperience` |
| `bk.action.waffle.*`, `bk.fx.*`, `bk.waffle.*` | 37 / 11 / 2 | Accounts Center bağlama: `EncryptPassword`, `DeleteLocalUserCredentials`, `GetProfilePictureUrl`, `UnpauseWithNativeAuthBlob`, `PregenerateAndCacheRSAKeyPairs` |
| `bk.action.mft.*`, `bk.action.frontier.*`, `bk.action.apt.PleEncrypt`, `bk.action.commerce.GetPaymentToken`, `bk.action.payments.GetCreditCardMetaData` | 5 / 5 / 1 / 1 / 1 | Ödemeler: `ModularGeneratePTT`, `LaunchGooglePaySheet`, `IsLuhnCompliant` |
| `bk.action.navigation.OpenUrl`, `bk.fx.action.OpenURLInIAB`, `bk.action.acp.OpenUrlExternally`, `bk.action.OpenUniversalLink`, `bk.action.DeeplinkToOtherAppOrDirectToAppStore`, `bk.action.bloks.IsAppInstalled` | 6 | Bloks'tan dışarı gezinme |
| `bk.action.io.clipboard.SetString`, `bk.action.RequestPermission`, `bk.action.media.LoadAlbums`, `bk.fx.action.media.OpenMediaPicker`, `bk.action.foa.media.OpenCamera` | 5 | Cihaz erişimi |
| `wa.action.*` | 75 | WhatsApp host eylemleri (aşağıdaki tablo) |
| `wa.callbacks.*` | 10 | `FormInputOnTextChange`, `CodeInputOnTextChange`, `DatePickerOnDateSet`, `CameraViewOnMediaCaptured`, `ListViewItemSelected` |
| `bk.versioning.*`, `wa.versioning.image.base64` | 50 / 1 | Yetenek adları |

Dikkat çeken `wa.action.*` (id'ler 22391 ila 26071):

| Grup | Adlar |
|------|-------|
| Ağ | `IQRequest`, `AsyncRequest`, `UploadMedia`, `UploadProfilePicture` |
| Phoenix bridge | `phoenix.FdsIq`, `FdsIqV2`, `FcsReturnResult`, `FcsReturnResultV2`, `FcsReturnResumableData`, `statemachine.GoBack`, `GoBackV2` |
| Uygulama durumu | `GetAbPropValue`, `GetAppType`, `GetIntentParameter`, `LoadScreenParam`, `SaveScreenParam`, `IsDarkModeEnabled` |
| Gezinme | `OpenUrl`, `RouteToNativeScreen`, `RouteToNativeBenefitDetail(V2)`, `navigation.OpenChat`, `OpenContactInfo`, `OpenNativeActionSheet`, `FinishActivity(WithResult)`, `PopScreen` |
| Mesajlaşma / ticaret | `commerce.SendNFMReplyMessage`, `commerce.ActionWithCallback`, `share.Text`, `bonsai.SubmitFeedback`, `care.OpenContactSupport`, `care.OpenReportThisPayment` |
| Telemetri | `SendFieldStat(V2)`, `StartFieldStatTimer`, `GetFieldStatEventId`, `perf.TrackPerformance`, `novi.EncryptLogEvent(V2)` |
| Deeplink | `RegDeeplinkListener`, `DeregDeeplinkListener` |

Bloks IQ eyleminde bulunan koruma (`C129575f5.A0Y`, log `IQRequestHelper/sendIQRequest: Invalid XMLNS`): yalnızca `w:pay` ve `urn:xmpp:whatsapp:account` xmlns'leri geçer (`C33327EfH.A02`); diğer her şey `on_failure` callback'ini çağırır. Dolayısıyla Bloks script'leri yalnızca bu iki ad alanında IQ gönderebilir (found). Diğer `wa.action.*` id'lerinin çoğunun handler uygulamaları izlenmedi (kodlarına sayısal id ile ulaşılır).

### 3.6 Component query'leri ve cache (found)

- Bir `component_query`, asenkron bir component'i aynı GraphQL yolu üzerinden `app_id` ile çeker (manager `C5L9`, log etiketi `BloksComponentQueryManager`); `app_id_expr`, `params`, `client_params` ve `cache_ttl_expr` istemcide değerlendirilen Lispy ifadeleridir.
- İki cache katmanı: bir bellek cache'i (`cache_src: memory`, `cache_age`) ve query başına anahtarlanan bir disk cache'i (`BloksComponentQueryDiskCache`; sınıflar `C5NA`, `C5NN`, `C136885r6`). Disk kayıtları Java-serileştirilmiştir (`ComponentQueryDiskCacheRecord`: `DiskCacheData{initialResponse, extensions}`, `responseTimestampMs`, `BloksComponentQueryResources`); metadata `__disk_metadata` altında yaşar; I/O'yu bir `Bloks_ACQ_ReadWriteThread` yapar. `disk_cache_enabled` query başına bir anahtardır.
- `bk.action.AsyncComponentCacheWrite`, `bloks.ClearCachedAsyncComponents`, `bloks.InvalidateCachedAsyncComponents` eylemleri bir payload'ın cache'i yönetmesine izin verir.
- Disk cache'in dizini, boyut sınırı ve tahliyesi: unknown. Sunucunun etkilediği cache kayıtlarının Java deserialization'ı yalnızca uygulamanın kendi cache'inden gerçekleşir (kod yolundan inferred).

---

## 4. Native flow mesajları ve WhatsApp Flows

### 4.1 NFM button registry (found, `AbstractC30032D4u` case 442, sınıf `EYT`)

Bir interactive mesaj, `nativeFlowInfo.name` ve bir params JSON'u olan butonlar taşır. Dispatch: `C33370Efz.A05` adı, yaklaşık 40 `AbstractC33168Ech` alt sınıfından oluşan bir map'te (`C0VA`) arar; bilinmeyen adlar `can not recognize NFM action` loglar ve düşürülür; bir eylem kapatılabilir (sayaçlar `wa:nfm_dispatch_gate_blocked` / `_observed`).

| Küme | Adlar |
|------|-------|
| Desteklenen button adları (39) | `cta_catalog`, `review_and_pay`, `review_and_pay_v2`, `cta_call`, `cta_url`, `cta_copy`, `cta_pix_code_copy`, `offer_payment_account`, `form_message`, `open_webview`, `catalog_message`, `voice_call`, `video_call`, `landline_call`, `quick_reply`, `single_select`, `view_product`, `call_permission_request`, `cta_app_link`, `appointment`, `automated_greeting_message_view_catalog`, `send_location`, `order_status`, `booking_confirmation`, `booking_status`, `psi_nux_opt_in`, `psi_tos_opt_in`, `psi_opt_outs`, `account_authentication_request`, `request_contact_info`, `agent_api_key`, `otp`, `payment_reminder`, `cta_reminder`, `payment_request`, `api_signup`, `inapp_signup`, `split_payment`, `send_payment` |
| İkinci küme | `address_message`, `galaxy_message` (flow başlatan; rol kullanımdan inferred) |
| Karışık/quick-reply allow-list'i | `C33370Efz.A08`: `cta_url`, `cta_call`, `voice_call`, `video_call`, `cta_copy`, `menu_options`, `cta_reminder`, `view_product`, `cta_app_link`, `galaxy_message`, `otp`, `booking_*`, ... |

- `address_message`, `address_message` Phoenix config'ini başlatır (`C31337Djk`, found).
- `galaxy_message` WhatsApp Flows'u açar (4.2).
- Flow yanıtları `message_ui_elements_reply` (`flow_id`, `element_type` 8) ve `interactive_message_bloks_widget` içinde saklanır (found, SQL).

### 4.2 `galaxy_message` params ve başlatma (found, `C31338Djl`, `C31337Djk`)

| Params JSON'undaki anahtar | Kullanım |
|----------------------------|----------|
| `flow_id` | Flows v2 eylemi için `\d+` ile eşleşmeli |
| `flow_token`, `flow_cta` | `flow_id` ile zorunlu (Flows v2 yolu) |
| `flow_message_version` | `2`, `3`, `4` Bloks query'sinin extension değişkenlerini seçer |
| `flow_action` (varsayılan `navigate`, `data_exchange`), `flow_action_payload` (nesne) | ilk ekran / veri kanalı |
| `mode` | `draft` bir taslak flow'u işaretler (`is_draft`) |
| `form_type` | `FlexCheckoutNativeFormActivity`'ye yönlendirir (flexible checkout) |
| `flow_token_signature`, `www_proxy_secret` | yalnızca AB prop **14825** açıkken sayfaya iletilir |

Gönderen business JID'i sohbetten gelir (`FlowsV2Action`); onsuz başlatma iptal edilir (`cannot launch flow without business jid`). İki renderer vardır: web uygulaması (4.3) ve bir Bloks yolu (`com.bloks.www.whatsapp.galaxy.flow.v2`, bölüm 3.2). Belirli bir mesajın hangisini izlediği çözülmedi; AB prop'ları **22787** (ayrı activity ile bottom sheet) ve **14222** web yolunda okunur.

### 4.3 Flows web uygulaması (found)

| Öğe | Değer |
|-----|-------|
| Taban URL'ler (AB string prop'ları) | **7153** `https://flows.whatsapp.net/flows` (preload, `C35814Ff9`), **6060** aynı varsayılan (flow JSON fetch `EP6`: taban + `/json/` + flow id, builder sırasından inferred), **7125** `.../flows/cache_management/` (cache temizleyici `C39066GzF`, aralık **7126** = 1382400), **16723** `.../flows-app/catalog` (catalog) |
| Host | `SecureWebView` (`com.facebook.secure.securewebview`): dosya ve content erişimi kapalı; yükleme yalnızca scheme `https` VE host, launch URL host'una eşit veya onun alt alan adı ise izinli (`GAP.A00`, `H26`, `GAL` içinde AND ile birleşik); aksi halde `Uri is blocked` loglanır |
| Launch URL | bundle'dan (`url`, varsayılan `about:blank`); taban bir AB prop'udur, dolayısıyla sunucu onu taşıyabilir; host politikası launch URL'yi izler (inferred sonuç) |
| Preload | `FlowsWebPreloader` AB **7153**'ü gizli bir WebView'da yükler (`setCacheMode(2)`); service-worker cache versiyonu `flows_service_workers_cache_version` ile izlenir |
| Sayfa enjeksiyonu | viewport, `layoutDirection`, `locale`, `timeZone`, `supportedStyles` içeren `meta` etiketi |
| Bridge | `window.WhatsAppBridge.invoke(method, data, cb)`; native bir `MessageChannel` oluşturur ve port 1 ile `init-port` gönderir (`HQD`); mesajlar JSON `{method, data, callbackID}`; yanıtlar `{callbackID, responseData}` |
| Origin bağlama | Bridge script'i WebView'ın gösterdiği her şeye `evaluateJavascript` ile enjekte edilir; port `Uri.EMPTY` hedefine gönderilir; kapılama SecureWebView URL politikasına dayanır (inferred) |
| Flow JSON | `flow_json`, `EP6.A01` ile çekilir (HTTP GET, diskte serileştirilmiş string olarak saklanır, anahtar `<id>_<id2>`), yalnızca AB **8552** açıkken; `FlowsWebViewDataRepository` bundle'ı oluşturur (`flow_json`, `flow_action_payload`, `creation_source`, oturum id'leri) |
| Public key | `WAExtensionsGetPublicKey`, bir GraphQL metadata çağrısıyla elde edilen endpoint public key'ini döndürür (`extensions-metadata-graphql-*` hataları, mod `required` veya `optional`); veriyi şifrelemek için kullanım sayfa tarafında yapılır (inferred) |

Native olarak işlenen bridge metotları (30; `C41342Hyk`, `FlowsWebBottomSheetContainer.CKc`):

| Grup | Metotlar |
|------|----------|
| Oturum | `WAExtensionsGetFlowData`, `WAExtensionsDataChannelExchange`, `WAExtensionsNavigate`, `WAExtensionsComplete`, `WAExtensionsClose`, `WAExtensionsGetPublicKey`, `WAExtensionsGetClientAbProps` |
| Arayüz | `WAFlowsShowNativeInputDialogComponent`, `WAExtensionsConfigureNavBar`, `WAFlowsMediaSelect`, `WAFlowsMediaRetry`, `WAFlowsMediaDelete`, `WAFlowsCopyText`, `WAFlowsOpenURL`, `WAExtensionsLearnMore`, `WAExtensionsContextualHelp` |
| Business | `WAExtensionsSpamReport`, `WAExtensionsReportItem`, `WAFlowsDownloadResponse`, `WAFlowsMarketingDisclosureState`, `WAFlowsMarketingDisclosureUserAction` |
| Sepet | `WAFlowsStoreShoppingFlowContext`, `WAFlowsGetCart`, `WAFlowsSetCartItem`, `WAFlowsClearCart` |
| Telemetri | `WAMLogger`, `WAQPLLogger.start`, `.end`, `.annotate`, `.point` |

İşleme notları: `WAFlowsOpenURL` yalnızca `https` URL'leri için `ACTION_VIEW` başlatır, aksi halde snackbar gösterir; `WAExtensionsGetClientAbProps` herhangi bir AB prop'unu kod ve tipe (`bool`, `int`, `float`, `string`, `json`) göre döndürür, allow-list görülmedi (`C37367GJs`); bilinmeyen metotlar varsayılan bir handler'a gider (`GJW`); parse edilemeyen girdi `extensions-bridge-api-input-parse-error` üretir.

### 4.4 Flow tamamlama

`WAExtensionsComplete` oturumu sonlandırır ve istemci bir native-flow yanıt mesajı gönderir (`native_flow_response_*` sütunları; params `wa_flow_response_params`, `flow_creation_source`, `response_message` taşır) (adlardan found; gönderim yolu izlenmedi).

### 4.5 Flows endpoint query

Sonuç sınıfı `AnonymousClass456`, kök `whatsapp_galaxy_forward_flow_data_response` veya `xwa_flows_make_flow_endpoint_request` ile bir `status_code` okur: 200 tamam, 421 ve 504 ayrı sonuçlara eşlenir, diğerleri genel başarısızlık (found). Bunun MEX üzerinden mi yoksa HTTPS GraphQL stack'i üzerinden mi çalıştığı unknown (parser tabanı Bloks ile paylaşılır).

---

## 5. Sunucu tarafından tanımlanan arayüz olmayan yüzeyler

### 5.1 AI rich response (mesajla taşınan, sabit component'ler)

Protobuf `richResponseMessage` (bkz. `WA_META_AI.md` bölüm 6.3). Alt mesaj tipi enum'u `EnumC32139E2l` (found): `AI_RICH_RESPONSE_UNKNOWN` 0, `GRID_IMAGE` 1, `TEXT` 2, `INLINE_IMAGE` 3, `TABLE` 4, `CODE` 5, `DYNAMIC` 6, `MAP` 7, `LATEX` 8, `CONTENT_ITEMS` 9; kod vurgulama sınıfları (`KEYWORD`, `STRING`, `NUMBER`, `METHOD`, `COMMENT`, `DEFAULT`); dinamik metadata `IMAGE`, `GIF`. İstemci sabit bir küme render eder; eylemler dosya indirme / iletmedir (`UnifiedResponseActionHandlerFactory`). Script dili yok, eylem DSL'i yok.

### 5.2 FMX kartı

FMX kartı (`LE7`, view-model factory `fmxViewModelFactory`, avatar etiketi `fmx-card-v2`) istemci tarafından bir sistem mesajı olarak oluşturulur (`C198788cr`: `Creating FMX card system message for chat`); `fmxBizEnterpriseSenders`, `fmxMissingLidMapping`, `fmxSuspiciousBottomSheetCacheMiss` gibi sayaçlar, yerel sinyallerle yönlendirildiğini gösterir. Sunucunun herhangi bir kart metni sağlayıp sağlamadığı unknown. Native arayüz olarak değerlendirin.

### 5.3 Uygulama içi tarayıcı script'leri (iabjs)

`res/raw/iabjs_*` 2.26.41.6'da 15 script içerir (2.26.34.4 kümesinden dört fazla): `autofill_execute_callback`, `autofill_language_detect`, `autofill_payment_detection`, `otp_autofill` yenidir. Host `WaInAppBrowsingActivity` (exported false).

| Öğe | Değer (found) |
|-----|---------------|
| Bridge nesnesi | `iabjs_unified_bridge`: desteklendiğinde izole JS world `iab_js` içinde `addWebMessageListener(name, allowedOrigins, listener, jsWorld)` (`HJY.A05`); yedek `addJavascriptInterface("iabjs_unified_bridge")` (`RunnableC40709HoJ`) |
| Sayfa tarafı | `window.__call_iabjs_unified_bridge(method, nonce, payload)` `{method, payload, nonce}` gönderir; nonce enjeksiyon sırasında `window.__iabjs_unified_bridge_nonce="%s"` içine yerleştirilir |
| Native kontrol | `C39590HNn`: JSON `nonce`, handler'ın saklanan nonce'una eşit olmalı (handler başına bir kez `AbstractC48382LBd.A00().toString()` ile üretilir, UUID benzeri, inferred); uyuşmazlık `invalid_nonce` kaydeder ve çağrıyı düşürür; `iabjs_register_proxy` metodu world'ü kaydeder; diğer metotlar (world, method) ile anahtarlanan listener'lara gider |
| Bu build'de yeni | `iabjs_autofill_payment_detection` alanları `autocomplete` veya name/id/placeholder regex'iyle `cc-number`, `cc-exp`, `cc-exp-month`, `cc-exp-year`, `cc-csc`, `cc-name` olarak sınıflandırır; `iabjs_otp_autofill` `input[autocomplete="one-time-code"]` alanını doldurur; `iabjs_autofill_language_detect` `languageDetermined` gönderir |
| İzinli origin kümesi | çağıranın verdiği `Set`; içeriği izlenmedi (unknown) |
| Eski yedek | `addJavascriptInterface` origin başına filtre içermez (platform davranışı, inferred) |

11 eski script'ten sekizi 2.26.34.4 kopyalarıyla bayt düzeyinde aynıdır; `detect_login_forms`, `navigation_performance_logger_android`, `iabjs_bridge_init` değişti (bridge init için 453 B'a karşı 433 B).

---

## 6. Sandbox ve güvenlik özeti

| Kontrol | Nerede | Tier |
|---------|--------|------|
| Phoenix resource id'leri kodda sabit; bilinmeyen id `ResourceNotFound` verir | `QKb.A03` | found |
| Phoenix operatörleri sabit (28); eşleşmeyen operatör atlanır | `RsJ`, `AbstractC56245PPq` | found |
| Bloks IQ eylemi xmlns `w:pay`, `urn:xmpp:whatsapp:account` ile sınırlı | `C33327EfH.A02` | found |
| Bloks function id'leri sabit (681 adlandırılmış) | `AbstractC111054pC`, `C122545Ki` | found |
| NFM adları sabit (39 + 2); bilinmeyen düşürülür | `AbstractC30032D4u`, `C33370Efz` | found |
| Flows host: yalnızca https + launch host (veya alt alan adı), dosya/content erişimi yok | `SecureWebView`, `GAP`, `H26` | found |
| Flows bridge: sabit metot listesi; `WAFlowsOpenURL` yalnızca https | `FlowsWebBottomSheetContainer` | found |
| iabjs: nonce kontrolü, izole world, origin kümesi | `C39590HNn`, `HJY` | found |
| Phoenix `br_verify_card_deeplink` broadcast'i kendi paketiyle sınırlı | `C955446o` | found |
| Tüm Bloks, Flows, Phoenix activity'lerinde intent filter yok; targetSdk 36 | manifest | found |
| Bloks/Phoenix içeriğinin payload imza veya hash doğrulaması | bulunamadı; `BloksTrustedPayload` referanssız | found (aranan yollarda yokluk) |
| Sunucu AB prop'larını kodla okuyabilir (`abprop_fetch`, `WAExtensionsGetClientAbProps`) | allow-list görülmedi | found |
| Taşıma güveni (TLS pinning, graph istekleri için token işleme) | analiz edilmedi | unknown |

Sonuç (inferred): güven taşımaya ve yukarıdaki registry'lere dayanır; ele geçirilmiş veya kötü niyetli bir sunucu tarafı program bu registry'lerle sınırlıdır, ancak registry'ler ödeme şifreleme yardımcılarını, Accounts Center için kimlik bilgisi işlemeyi, `ACTION_DIAL`'ı, URL açmayı ve AB okumalarını içerir.

---

## 7. Cache ve preload

Bloks component query'leri: bellek + disk, TTL `cache_ttl_expr` ile (3.6). Phoenix: sunucunun listelediği `next_screens` `WaFcsPreloadedBloksActivity` içine preload edilir; `persist_data` girdileri anahtar başına listener'lara gider (found). Flows web: preload WebView, service-worker cache versiyonu, zamanlanmış temizleyici (AB 7125/7126), flow JSON disk cache'i, prefs içinde metadata ban işaretçisi `extensions_metadata_banned_<id>_<id>` (found).

---

## 8. Feature flag'ler (varsayılanlar `C08J`'den; anlamlar okuma noktasından)

| ID | Tip | Varsayılan | Okunduğu yer | Etki |
|----|-----|------------|--------------|------|
| **549** | bool | false | `AbstractC40195HfH.A03` | GraphQL URL'sine `?_emp=1` ekler (`C0GD.A02()` değilse) |
| **7153** | string | `https://flows.whatsapp.net/flows` | `C35814Ff9` | Flows preload URL'si |
| **6060** | string | aynı | `EP6`, `C33350Efe` | `/json/<id>` için Flows tabanı |
| **7125** | string | `.../flows/cache_management/` | `C39066GzF` | Flows cache temizleyici URL'si |
| **7126** | int | 1382400 | `C39066GzF` | Temizleyici aralığı/etkinleştirme (birim unknown; > 0 etkinleştirir) |
| **8552** | bool | false | `FlowsWebViewDataRepository.A07` | Flow JSON'u native olarak çek ve sayfaya ilet |
| **14825** | bool | false | `FlowsWebViewDataRepository.A06` | `www_proxy_secret` ve `flow_token_signature` ilet |
| **22787** | bool | false | `C31338Djl` | Flows ayrı activity ile bottom sheet |
| **24781** | bool | false | `FlowsWebBottomSheetContainer` | Olmadan, geri yüklenen bir sheet kendini kapatır |
| **14222** | bool | false | `C31338Djl` | Flows başlatma yolunda kapı (tam etki unknown) |
| **5333**, **1319** | bool | false / false | `C45J` Flows varyantı | İkisi de açık: Flows layout hataları `extensions-layout-unexpected-error` olarak raporlanır |

Flag id'leri `WA_AB_PROPS.md` içindeki sayısal alanı kullanır.

---

## 9. Baileys (`baron-baileys-v2`)

Bir Baileys istemcisinin renderer'ı yoktur, dolayısıyla Bloks ve Flows web erişilemezdir. Dokunabileceği şey mesajla taşınan kısım ve prensipte IQ'dur.

| Hedef | Ne işe yarar | Neden başarısız olabilir | Düzeltme |
|-------|--------------|--------------------------|----------|
| Flow butonu gönder | `name: 'galaxy_message'` ve 4.2'deki anahtarları (`flow_message_version`, `flow_id`, `flow_token`, `flow_cta`, `flow_action`, `flow_action_payload`) tutan `buttonParamsJson` ile `interactiveMessage.nativeFlowMessage.buttons[]` | Alıcı bir business JID bağlamı, sayısal `flow_id`, `flow_token`, `flow_cta` gerektirir; kullanıcı (business olmayan) gönderenlerin dikkate alınması olası değil (inferred) | Business kayıtlı bir hesaptan gönder; `flow_id`'yi sayısal tut |
| Bilinmeyen bir button adı kullan | yok | `C33370Efz` 39 + 2 dışındaki adları düşürür | 4.1'den bir ad kullan |
| Bir Phoenix programı çek | `<iq xmlns="phoenix" type="get"><fds config=... /></iq>` | Sunucu hesap/uygulama durumuna göre karar verir; yanıt içeriği hiç yakalanmadı | Denenmedi; unknown olarak değerlendir |
| Bir Bloks ekranı oku | uygulanamaz | graph token'ı, doc id ve `bloks-versioning-id` gerekir; Baileys yolu yok | Kapsam dışı |

---

## 10. Hata durumları

| Belirti | Neden | Düzeltme |
|---------|-------|----------|
| `ResourceNotFound` ve akış biter | `resource` durumu registry'de olmayan bir id'yi adlandırıyor (veya eşleşmeyen bir build'de gated bir Brezilya id'si) | 2.5'teki id'leri kullan |
| `state not found for name: <x>` | `next` eksik bir duruma veya bir `version_check` durumuna işaret ediyor (`C58392QJx.A01` tarafından düşürülür) | Hedefi desteklenen bir tip olarak bildir |
| `unsupportedComparisonTypes` / `comparingValuesWithDifferentTypes` | Operatör yanlış tiplere uygulandı | Tipleri eşleştir; `catch` kullan; `NOT_CATCHABLE_ERROR` yakalanamaz |
| `FdsIqResource/execute: can't find FdsManager from the job_id` | `send_fds_iq` canlı bir oturum dışında | Onu başlatan oturum içinde çalıştır |
| Bloks `Invalid XMLNS` | allow-list dışı bir xmlns ile `wa.action.IQRequest` | Yalnızca `w:pay`, `urn:xmpp:whatsapp:account` |
| `FcsScreenOpenerBloksDelegate: app_id is not present` | `app_id` olmadan `open_bloks_screen*` | `app_id` ver |
| `error.code` 3489039 | Bütünlük kontrolü talep edildi (consent öncesi fetch) | İstemci kontrolden sonra yeniden dener |
| Flows sayfası boş, log `Uri is blocked` | Gezinme launch host'unu terk etti veya https olmayan scheme kullandı | İçeriği launch host'unda tut |
| `extensions-bridge-api-input-parse-error` | Bridge mesajı beklenen biçimde geçerli JSON değil | `{method, data, callbackID}` gönder |
| iabjs `invalid_nonce` | Yanlış veya eksik nonce | Enjekte edilen `__iabjs_unified_bridge_nonce` değerini kullan |

---

## 11. Temel ayrımlar

| Karıştırma | Fark |
|------------|------|
| Phoenix ve Bloks | Phoenix = IQ üzerinden kontrol akışı; Bloks = GraphQL üzerinden ekranlar; `open_bloks_screen*` ve `wa.action.phoenix.*` noktasında buluşurlar |
| FCS ve FDS | İkisi de görünür: `flowconfigurationservice` (paket, `FcsStateMachine`) ve `FDS` (IQ manager, `<fds>`, log `FDSManage`); "FDS" kısaltmasının açılımı kodda yok |
| Manifest ve kod | `phoenix-features.json` 12 resource id ve 21 operatör listeler; kodda 15 resource id ve 28 operatör var; kod kazanır |
| `open_bloks_screen_static` ve `open_bloks_screen` + `fetch_channel=STATIC` | Yalnızca ikincisinin handler'ı var |
| Bloks ağaç anahtarları ve opcode'lar | Ağaç anahtarları component code point'leridir; script başları function id'leridir (base-36) |
| Flows web ve Flows Bloks | `galaxy_message` için iki renderer: WebView (`flows.whatsapp.net`) ve `com.bloks.www.whatsapp.galaxy.flow.v2` |
| Bloks GraphQL ve MEX | Bloks `doc_id` ile `graph.<domain>/graphql` adresine post eder; MEX başka yerlerde kullanılan XMPP taşımalı query katmanıdır |
| iabjs nonce ve Flows bridge | iabjs zarfta handler başına nonce kullanır; Flows bridge'in nonce'u yoktur, port el sıkışmasına ve URL politikasına dayanır |
| Rich response ve Bloks | Rich response sabit bir protobuf kümesidir; Bloks programlanabilir bir ağaçtır |

---

## 12. Tam akış

```
[Server]                                          [WhatsApp client]
   │  message: interactive nativeFlowInfo name        │
   ├─────────────────────────────────────────────────►│ C33370Efz: name in registry? gated?
   │        address_message              galaxy_message│
   │             ▼                              ▼      │
   │  Phoenix start C58392QJx.A08       Flows launch C31338Djl: SecureWebView (https, launch host)
   │  IQ <iq xmlns="phoenix"><fds config>      + MessageChannel init-port, or Bloks galaxy.flow.v2
   │◄────────────────────────────────────────────────┤
   │  <fds><states start_at><state type=..>           │
   ├─────────────────────────────────────────────────►│ QKb.A03 loop: resource | choice(28 ops) | pass | subflow | succeed
   │                                                  │ resource -> registry: open_bloks_screen_graphql, send_fds_iq, abprop_fetch, ...
   │  POST graph.<domain>/graphql {doc_id, variables{app_id, versioning id, params}}  (route by app_id: C5LX)
   │◄────────────────────────────────────────────────┤
   │  layout.bloks_payload {tree, ft, component_queries, ...}
   ├─────────────────────────────────────────────────►│ AbstractC122255Jb: tree (code-point keys) + Lispy (base-36 ids)
   │                                                  │ user action -> bk.* / wa.* function id
   │◄── IQ (w:pay | urn:xmpp:whatsapp:account only) ──┤ wa.action.IQRequest
   │                                                  │ wa.action.phoenix.FdsIq / FcsReturnResult -> back into QKb (next / catch / end)
   │◄── WAExtensionsComplete -> native-flow response ─┤
```

---

## 13. Bilinmeyenler

| Öğe | Durum |
|-----|-------|
| "FDS" açılımı; `L8E.A1T()` kapısının anlamı | unknown |
| Component code point'ten ada harita; listelenen 681'in ötesindeki Lispy adları; metin formu parser'ı | unknown |
| Çoğu `wa.action.*` / `bk.action.*` id'sinin handler kodu (sayısal id ile ulaşılır) | unknown |
| Gerçek sunucu içeriği: hiçbir Phoenix programı veya Bloks ekranı yakalanmadı | unknown (yalnızca statik) |
| `xwa_flows_make_flow_endpoint_request` taşıması; bir `galaxy_message`'ın izlediği renderer; AB **14222**'nin etkisi | unknown |
| Disk cache konumu, boyutu, tahliyesi; iabjs izinli origin kümesi; TLS ötesinde sunucu tarafı bütünlük | unknown |
| Başka bir build'de Genie tarzı bir framework'ün var olup olmadığı | unknown |
