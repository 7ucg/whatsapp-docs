<!-- src-sha1: 64389e16d6c478a5b57f43abf9ee01a01474f02f -->
# WhatsApp Meta AI — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-17
**Kapsam:** Meta AI iç yapısı — JID'ler, yönlendirme, proto alanları, Hatch metadata istekleri, yanıt render'ı, Baileys neden başarısız oluyor, çözüm

---

## 1. Meta AI nedir (teknik olarak)

Meta AI, özel bot JID'leri (sunucu `bot`) ile adreslenen bir bot kişisidir; normal mesaj tiplerinde bota özgü proto alanları vardır ve bir `ProtocolMessage` içinde taşınan ayrı bir JSON istek kanalı ("Hatch metadata") bulunur. Tüm ifadeler derlenmiş (decompiled) APK'nın statik analizine dayanır. Seviye: **found** = kodda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülmedi.

Bu raporda 2.26.26.4 sürümünde obfuske olan isimler (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`) sabit çapa noktalarından yeniden çözüldü; 2.26.41.6 sürümünde bu isimlerle mevcut değiller.

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|------|
| BotJid | `C24770wv` | JID sınıfı, sunucu `"bot"`, tip 26, 1-20 karakterlik sayısal string, başında 0 yok |
| Bot JID sabitleri | `AbstractC34361Xw` | Hatch / Fallback / LID sabitleri ve kümeleri |
| JID eşleme | `AbstractC24760wu` | bot ↔ LID eşleme, giden hedef dönüşümü |
| Gating | `C39311it` | JID başına feature-flag gating (`A0E(Jid)`) |
| Hatch istek yöneticisi | `HF1` (`HatchMetadataRequestManager`) | JSON istekleri, bekleyen harita |
| Hatch proto oluşturucu | `Hf6` | `ProtocolMessage.aiMetadataOperation` oluşturur |
| Message | `C30628DTw` | proto `Message` |
| WebMessageInfo | `C30626DTu` | proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | `botMetadata` içerir |
| BotMetadata | `C30615DTj` | mesaj başına bot metadata'sı |
| Bot profil kaydı | `C199348dm` | ad, açıklama, persona ID string'i, küçük resim |

---

## 2. Meta AI JID'leri

### 2.1 Kodda bulunan JID'ler

| Sabit | Sınıf | Rol | Seviye |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`), `AbstractC34361Xw.A00` üzerinden | **Hatch**, birincil. Varsayılan profil `C223219iv` içinde flag payload'ı **26190**'dan oluşturulur | found |
| `1807055946647698` | `C24770wv` (`bot`), `AbstractC34361Xw.A01` üzerinden | Fallback. Flag 27083 ile kapılanır | found |
| `165332417282214` | `C14080dr` (sunucu `"lid"`), `AbstractC34361Xw.A02` üzerinden | `…698`'in LID karşılığı | found |
| `1807055946647696` | yok | Manus (2.26.26.4'te eski): 2.26.41.6'da **mevcut değil** | found (absent) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), ayrıca `A01` = `DeviceJid` cihaz 0 | Bir "bot envelope" için oturum/cihaz hedefi olarak kullanılan bot-sunucu JID'si (CoEx v2 sync istek işleyicisi `C53148Nnt` sync payload'ını birincil cihazına şifreler, log `coexv2 attached bot envelope`), alıcı cihaz kümelerine eklenir (`C12M`) ve retry-receipt işlemede bot gönderici olarak ele alınır (`C33020EaI`). Sohbet persona'sı değil | found (kullanım); bunun ötesindeki amaç inferred |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | Yerleşik varsayılan "Meta AI" profil kaydının JID'si (`C9i5.A00`: ad `Meta AI`, varsayılan tanıtım metni). Bir sonraki satırla birlikte `AbstractC24760wu.A07` bot-JID testinin üyesi | found |
| `867051314767696555` | `AbstractC24760wu.A01` (tek elemanlı küme, `C24770wv`) | `A07` bot-JID testinin ikinci üyesi (`A07(jid)` = `C24770wv` ve `…135992`'ye eşit ya da bu kümede); `A07`, `AbstractC199328dk.A00`'ı (bir JID-sınıfı predicate'i) besler. Başka amacı çözülmedi | found (kullanım), amaç unknown |
| `17015557208` | `AbstractC24760wu.A04` | Telefon kullanıcı string'i. `A04(jid)`, LID `165332417282214` için veya bu telefon kullanıcısı için true'dur; `E76.A00` içinde (sınıf 10 / 1) ve uygunluk predicate'i `C736539v.ARO` içinde `A03` ile (herhangi bir `C24770wv` bot JID'si veya 13135550000-13135559999 / 13165550000-13165550099 aralıklarındaki PN) birlikte kullanılır. Meta AI'ın PN kimliği olarak okunuyor; bu iki tüketicinin bununla ne yaptığı çözülmedi | found (kullanım), amaç unknown |

`AbstractC34361Xw` içindeki kümeler: `A05 = {…697, …698}`; `A03 = {…697, …698, 165332417282214}`; harita `A04`: `…697 → […697]`, `…698 → […698, 165332417282214]`.

JID tipi: 2.26.26.4 raporu dördünü de `@s.whatsapp.net` olarak listelemişti. 2.26.41.6'da bot JID'leri `getServer() = "bot"` olan `C24770wv`'dir; grup/LID olanı sunucusu `"lid"` olan `C14080dr`'dir. `s.whatsapp.net` değil (found).

Telefon numarasından bot-FBID'ye tablo: `AbstractC199338dl.A00` (`HashBiMap`, 1313555xxxx → FBID, yaklaşık 200 giriş, örn. `13135550002 → 867051314767696`). `C0DZ.A08(UserJid)` (`convertPNJidtoBotJidIfExists`) tarafından kullanılır (found).

### 2.2 Yönlendirme dönüşümü

```java
// AbstractC24760wu.A01  (getRemoteTargetJidForOutgoingMessage)
if (A08(jid))   // LID jid with user 165332417282214
    return new C24770wv("1807055946647698");
else            // phone jid
    return C0DZ.A08((UserJid) jid);   // PN -> bot JID via AbstractC199338dl table

// AbstractC24760wu.A00
if (jid is bot "1807055946647698") return new C14080dr("165332417282214");  // bot -> LID
if (jid is bot)                      return C0DZ.A07(userJid);              // bot -> phone jid
```

Found: bot JID `…698` ↔ LID `165332417282214`; telefon numaralı bot kişileri bot JID'lerine eşlenir. Metot "needs FBID migration" assert'i içerir (found).

### 2.3 `$1` soneki: değişti

2.26.26.4 raporu `$1`'i yönlendirme JID'sine yerleştirmişti ("wire format", `C1A2.A00()/A01()`). 2.26.41.6'da bulunamadı:
- Hiçbir yönlendirme fonksiyonu bir JID'ye `$1` eklemez. 2.2'deki dönüşüm düz bot JID'leri üretir.
- `$1`, bot profil kaydında saklanan persona ID string'ine eklenir: `C24121Ab2` `personaIdString = botFbid + "$1"` yapar; `C223219iv` Hatch varsayılan profili için `"1807055946647697$1"` değerini sabit olarak yazar (found).
- Bu string (`C199348dm.A0A`), `C33473Ehf.A0G`'nin `BotMetadata.personaId` içine yazdığı değerdir (found).

Yani `$1` hedef JID'ye değil, persona ID'ye aittir.

### 2.4 isMetaAI tespiti

```java
// C39311it
boolean A02() {                       // Hatch
  if (!BRD() || capability("ai_hatch_integration_enabled")) return flag(26189);
  return false;
}
boolean A0E(Jid jid) {
  if (jid == HATCH_697)                 return A02();
  if (jid == FALLBACK_698 || jid == LID_165332417282214) {
    if (!BRD() || capability("ai_maiba_wass_migration_receiving_enabled")) return flag(27083);
  }
  return false;
}
```

Manus dalı (flag 25119) kalktı. `BRD()` ve capability sorgusunun (`C09L.A04`) anlamı çözülmedi (unknown).

---

## 3. Feature Flag'ler

| Flag ID | 2.26.41.6'daki kullanım | Seviye |
|---------|------------------|------|
| **25119** | Yalnızca flag tablolarında görünür (`C06510El`, `C08J` içinde varsayılan `false`). Okuyucu bulunamadı. Eski ad `ai_bot_integration_enabled` string olarak bulunamadı | found |
| **26189** | `C39311it.A02()` içinde Hatch gate'i. Varsayılan `false` (`C08J`) | found |
| **27083** | `C39311it.A0E()` içinde Fallback / LID gate'i. Varsayılan `false` | found |
| **26190** | Varsayılan Hatch profili için JSON config (`name`, `description`, `profile_thumb`), `C223219iv` içinde okunur | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. True olduğunda capability `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) Hatch'e bildirilir (bkz. 5); `A05` ayrıca connector telemetri/UI'ını da kapılar (`C28147CLx`, `C1427261o`, `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) bildirir; ayrıca connector kullanılabilirliğini kapılar (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. `HATCH_ARTIFACT_CARD_ENABLED` (79) bildirir; ayrıca `HatchSpacesSync` ve `C7WL` tarafından okunur | found |

`ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` string'leri flag adı değildir. Bunlar `C25056AqU` içinde 26189 / 27083 flag'lerinden oluşturulan bir feature-string listesinin girdileridir (`username_supported`, `post_status_in_companion`, ... ile birlikte); `ai_fbid_migration_receiving_enabled` koşulsuz eklenir. Listenin alıcısı ve amacı doğrulanmadı.

---

## 4. Proto Alanları

### 4.1 Message (`C30628DTw`) üst düzey

| Alan | Numara | Tip | Kullanım |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (tek alan `message` = 1) | Bot için sarılan giden mesaj; `F2K`, `C33284Eea` içinde ayarlanır |
| `botTaskMessage` | **100** | `BD2` | Bot görevi |
| `botForwardedMessage` | **104** | `BD2` | `richResponseMessage` tutan bir mesajı sarar; `F3E` içinde ayarlanır |
| `richResponseMessage` | **97** | `DSY` | AI yanıtı. Alanlar: `messageType` 1, `submessages` 2, `unifiedResponse` 3, `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | Mevcut |
| `botGroupParticipantMessage` | **137** | `BD2` | Mevcut |
| `messageContextInfo` | **35** | `C30624DTs` | `botMetadata` taşır |
| `protocolMessage` | **12** | `BD3` | `aiMetadataOperation` (31) taşır |

Alan **77** `commentMessage`'dır, `richResponseMessage` değil (2.26.26.4 raporunda 77 yazıyordu; bu build için yanlış, ayrı richResponseMessage araştırmasıyla da tutarsız: 97).

### 4.2 WebMessageInfo (`C30626DTu`), ContextInfo değil

2.26.26.4 raporu bunları ContextInfo alanları olarak listelemişti. 2.26.41.6'da `WebMessageInfo` üzerindedirler:

| Alan | Numara | Tip | Kullanım |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | `C34385EwW` içinde `C0DZ.A09(userJid)` ile ayarlanır (çağıranın birincil cihaz kullanıcısı) |
| `isSupportAiMessage` | **70** | bool | Mesajda flag biti `268435456` varsa ve bir kontrol geçerse `C34378EwP.C57` içinde ayarlanır; `C59` içinde geri okunur. `is1PBizBotMessage` (**56**) ile birlikte |
| `supportAiCitations` | **72** | repeated message | Atıflar |
| `botTargetId` | **73** | string | İstemcide yazıcı yok: `botTargetId_` yalnızca constructor varsayılanı ve `C30626DTu` şema tablosunda görünür, başka hiçbir yerde atanmaz (tam kaynak grep'i) |
| `agentId` | **47** | string | Mevcut, analiz edilmedi |

Bu WebMessageInfo alanlarının wire üzerinde görünüp görünmediği ve nasıl göründüğü doğrulanmadı (unknown). "Tüm Meta AI mesajları için `true`" desteklenmiyor: koşulsuz değil, mesaj flag'ine göre ayarlanır.

### 4.3 MessageContextInfo (`C30624DTs`)

| Alan | Numara | Tip |
|-------|--------|------|
| `botMessageSecret` | **6** | bytes |
| `botMetadata` | **7** | `BotMetadata` (`C30615DTj`) |
| `teeBotMetadata` | **17** | bytes |

### 4.4 BotMetadata (`C30615DTj`)

| Alan | Numara | Tip | Kullanım |
|-------|--------|------|-----|
| `personaId` | **2** | string | Bot profil kaydından (`C199348dm.A0A`), örn. `1807055946647697$1`. Sabit bir `"meta_ai"` değil |
| `pluginMetadata` | **3** | `DTL` | Plugin config'i |
| `invokerJid` | **5** | string | Çağıran |
| `aiConversationContext` | **20** | bytes | Konuşma durumu |
| `botResponseId` | **26** | string | Yanıt ID'si |

Mevcut diğer alanlar (adlar `*_FIELD_NUMBER` içinden, tipler okunmadı): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId` `C33473Ehf.A0G` içinde doldurulur; profilde persona string'i yoksa metot erken döner.

### 4.5 PluginMetadata (`DTL`)

| Alan | Numara | Tip | Değer |
|-------|--------|------|-------|
| `provider` | **1** | int32 | Sağlayıcı ID'si |
| `pluginType` | **2** | enum `C4E0` | Aşağıya bakın |
| `profilePhotoCdnUrl` | **4** | string | |
| `referenceIndex` | **6** | | |
| `expectedLinksCount` | **7** | | |
| `pluginVersion` | **8** | | |
| `parentPluginType` | **11** | | |
| `faviconCdnUrl` | **13** | | |

`C4E0` sabitleri (değer = constructor sıra numarası; proto numarasına eşit olması inferred): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. Eski 8/9/15 değerleri değişmedi; enum daha büyük.

### 4.6 Action oneof (`C61331Rfl`, case enum `EnumC61601RkN`)

| Numara | Case | Seviye |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

Bu, düz bir değer enum'u değil, action alanlarından oluşan bir oneof'tur. Nereye gömüldüğü izlenmedi (unknown).

### 4.7 AI metadata operation (Hatch taşıyıcısı)

| Message | Alan | Numara | Tip |
|---------|-------|--------|------|
| `ProtocolMessage` (`BD3`) | `aiMetadataOperation` | **31** | `C25754B9o` |
| `C25754B9o` | `hatchMetadataSync` | **1** | `BB2` |
| `C25754B9o` | `bizAiMetadataSync` | **2** | `C156236jd` (`serverEvent` = 1) |
| `BB2` | `data` | **1** | bytes |
| `BB2` | `timestampMs` | **2** | int64 |
| `BB2` | `requestId` | **3** | string |

---

## 5. İstek Protokolü (Hatch metadata)

İstekler `HF1` (`HatchMetadataRequestManager`) tarafından oluşturulur, coroutine sınıfı `HatchMetadataRequestManager$sendRequest$2`. JSON zarfı 2.26.26.4'ten farklıdır: `method` ve `params` `payload` altına yuvalanmıştır.

```json
{
  "version": 1,
  "type": "req",
  "payload": {
    "method": "<method_name>",
    "params": { },
    "accepts_encoding": ["gzip"]
  }
}
```

`params` ve `accepts_encoding` isteğe bağlıdır (found). İstek ID'si JSON içinde değildir; `BB2.requestId`'dir (`C20F.A0x()` ile üretilen rastgele string).

Gönderim yolu (found):
```
HF1.A01(jid, method, ..., params, viewMode, timeoutMs)
  → sendRequest$2: registers onPart callback in A03[requestId] = GuR(method, onPart)
  → JSON → bytes
  → C02381: A04[requestId] = continuation
  → GwX "HatchMetadataSyncHelper/sendMetadataToHatch" → C37393GKy(jidTo, 138, timestampMs)
       .A02 = payload bytes, .A01 = requestId, .A0M = viewMode
  → Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
```

- Bekleyen istekler: `HF1.A04` (`ConcurrentHashMap`, requestId → continuation) ve `HF1.A03` (requestId → `GuR`). İkisi de `finally` içinde temizlenir. 2.26.26.4 raporu yalnızca tek bir harita `A02` adlandırmıştı.
- Timeout: `GDB.A00` döner ve `HatchMetadataRequestManager/sendRequest timed out method=` loglanır.
- `C37393GKy`'e geçirilen `138` tamsayısı çözülmedi (unknown).
- Taşıyıcı `ProtocolMessage.aiMetadataOperation` (alan 31)'dir, düz bir sohbet mesajı değil (değişti).
- `com.whatsapp.bot.infra.message.aimetadata` paketi `Ideas*Wire` / `Idea*Wire` sınıflarını içerir (found). Bunların method adlarıyla ilişkisi yalnızca inferred; method adları listelenmedi.
- `A04`'ü tamamlayan alma tarafı izlenmedi. Bir yanıtın `requestId` ile eşleştirilmesi, `A04` haritası ve `BB2.requestId`'den inferred.

**Özel XMPP namespace yok** iddiası: izlenen yolda `w:ai` / `wa:ai` işleme görülmedi; yokluğa dayalı, kapsamlı biçimde yeniden doğrulanmadı.

**Capability bildirimi (found, `C33284Eea`):** hedef Hatch JID'si `…697` (`AbstractC34361Xw.A00`) olduğunda ve bir gate geçtiğinde, istemci `DPJ` oluşturur (tek repeated enum alanı `capabilities` = 1, değerler `EnumC32144E2q`) ve `C33473Ehf.A06` bunu giden mesajın `BotMetadata.capabilityMetadata` (13) alanında, cihazın `TimeZone` ID'si olan `BotMetadata.timezone` (8) ile birlikte saklar. Gate'e göre eklenen capability'ler:

| Gate | Capability (enum numarası) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| flag **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| flag **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| flag **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

Numaralar enum'un ikinci constructor argümanıdır; proto numaralarına eşit olmaları inferred. Enum ayrıca rich-response capability'lerini de listeler (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**İstek örnekleri (found, `params` anahtarları çağrı noktalarında okundu; çağrı noktası konuşma JID'sini kullanmıyorsa hedef Hatch JID'si `…697`'dir):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | `HatchIdeasManager$execute$job$1` içinde oluşturulur (anahtarlar okunmadı); `onPart` callback'i eklenir |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire` JSON'a serileştirilir; `onPart` callback'i eklenir |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` yalnızca boş değilse) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

`BB2.data` içindeki byte'ların biçimi (found biçim, örnek değerler):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

`accepts_encoding` yalnızca çağıranın `acceptsGzipResponse` değeri true ise yazılır; `params` yalnızca null değilse. `onPart` callback'i `A03` içine yalnızca çağıran bir tane geçirirse kaydedilir.

**Bota sohbet mesajı (found kısımlar):**
- Giden `Message`, `Message.botInvokeMessage` içine yeniden sarılır (`F2K`, `C33284Eea`); sarmalayıcı `BD2` mesajı alan 1'de tutar. `F2K` içinde `C13S.A00()` false ise, mesajın `A10`'u false ise veya flag **10646** açıksa sarma atlanır (mesaj doğrudan ayarlanır) (found).
- `BotMetadata`, `C33473Ehf.A0E` / `A0G` tarafından oluşturulur. `A0G`, hedef bot JID'si için profil kaydını arar (`C199358dn.A06(userJid)`, persona string'i `C199348dm.A0A`); bu string boşsa metot bot metadata'sı yazmadan döner, aksi halde `personaId` (2) ve varsa `suggestedPromptMetadata` (4) ile başka alt mesajları ayarlar. Persona string'i profil kaydı oluşturulurken saklanır (`C24121Ab2` `<id>$1` oluşturur; `C223219iv` Hatch için `1807055946647697$1` değerini sabit yazar). `messageContextInfo`'nun dıştaki `Message` üzerine mi yoksa `botInvokeMessage` içindeki mesajın üzerine mi düştüğü çözülmedi.
- `botMessageInvokerJid` / `isSupportAiMessage`, `WebMessageInfo` üzerinde D36 hook'larıyla ayarlanır (`C34385EwW`, `C34378EwP`).

---

## 6. Yanıt Protokolü

### 6.1 Taşıma

2.26.26.4'te belirtildiği gibi yeniden doğrulanmadı ("`hatchMetadataSync` byte'ları içeren normal mesajlar", sınıf `Azz`). Found: `hatchMetadataSync`, `ProtocolMessage.aiMetadataOperation` içindeki `C25754B9o` içinde yaşar. Hatch yanıtlarının muhtemelen aynı şekilde geldiği ve `requestId` ile eşleştiği (inferred). Hatch istekleri method çağrılarıdır; normal sohbet yanıtlarının yolu oldukları gösterilmedi.

### 6.2 Streaming / chunk'lar: anlatıldığı gibi desteklenmiyor

2.26.26.4 tablosu (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`) tek bir Meta AI streaming mekanizması olarak 2.26.41.6'da desteklenmiyor:

| Alan | 2.26.41.6'da nerede |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` alan **7** (history-sync bildirimi, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) ve `C25838BCy` alan **5** (history sync) |
| `isLastChunk` | `C55285Ou6` alan **8** (`attestationBundles`, `teeModelConfig`, `violationSignal` içeren mesaj; TEE ile ilgili) |
| `streamingSidecar` | görsel/video/ses mesajlarında alan **18** (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | proto alanı olarak bulunamadı |

Meta AI yanıtları için chunk birleştirme bulunamadı. Hatch için mevcut olan: `GuR(method, onPart)` — istek başına bir `onPart` callback'i (found); kısmi sonuçlar taşıdığı addan inferred.

### 6.3 Rich response (alan 97)

`richResponseMessage` (`DSY`) = `Message` üzerinde alan **97**. Render sınıfları mevcut: `AiRichResponseFooterView` ve `UnifiedResponseActionHandlerFactory` (paket `com.whatsapp.conversationrow.botrichresponse`) (found). Atıflar: `WebMessageInfo.supportAiCitations` (72). İçerik tipleri (görseller, tablolar, kod) burada yeniden doğrulanmadı; ayrı richResponseMessage araştırmasına bakın.

### 6.4 Yazıyor göstergesi

Giden (found, `C199098dN.A01`, log `HandleMeComposing/handleComposing`): standart XMPP sohbet durumu, okunan kodda özel namespace yok.
- Düz durum (bahsedilen bot yok veya varsayılana çözülen bir bot JID'si): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Sohbette bot bahsedildi: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- IQ-tipi int 4 ile `C10140Tq.A0X` üzerinden gönderilir.

Gelen (found, `C40511kx` stanza işleyicisi): `composing` çocuğu olan bir `<chatstate>` (isteğe bağlı `media`) `from`/`participant` ile genel composing callback'ini çağırır; `paused` paused callback'ini çağırır. Bu işleyicide bota özgü dal bulunmadı, dolayısıyla bir bot-JID `composing`'i herhangi bir kişi gibi aynı yoldan geçer (inferred; sunucu tarafı bot yazıyor stanza'sı gözlemlenmedi). `BotMetadata.progressIndicatorMetadata` (12) ve capability `PROGRESS_INDICATOR`, mesaj içi ayrı bir ilerleme mekanizması olarak mevcut (yalnızca adlar, izlenmedi).

### 6.5 Bot profil sync'i

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`), `A03()` içinde `BotProfileForChatListWorker`'ı zamanlar: `BotProfileSyncManager` etiketli, `setBackoffCriteria(policy, 1, MINUTES)` ve bir kısıtlama (tip değeri çözülmedi) içeren bir WorkManager isteği. 1 dakika bir retry **backoff**'tur, periyot değil. 2.26.26.4'teki "yaklaşık her 1 dakikada" desteklenmiyor (değişti). `A02(groupJid, userJid)` tek bir profil ister (`requestBotProfileResult`). Normal roster sync'in parçası değil (değişmedi).

Profil kaydı `C199348dm`: bot tipi (`C1XY`), jid, görünen ad (`A09`), açıklama (`A07`), persona string'i (`A0A`), küçük resimler, zaman damgası.

### 6.6 Bot tipi string'leri

`C718732k.A00(String)` şunları eşler: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; diğer her şey `AnonymousClass399(str)` olur. Bunlar bot-tipi etiketleridir (UI filtrelerinde de kullanılır), `BotMetadata.personaId` değerleri değildir (found).

---

## 7. Depolama

- `MetaAiMemoryStore`: 2.26.41.6'da bu adda sınıf yok. Bulunan eşdeğeri, `C23621AHm` şema sınıfı tarafından oluşturulan `meta_ai_memory` tablosudur (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, `memory_content` üzerinde `meta_ai_memory_memory_content_index` indeksi. Hangi veritabanı dosyasında olduğu çözülmedi. İlgili (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; ad deprecated diyor), SharedPrefs `meta_ai_memory_disclosure_seen` (sesli arama tasarım ekranı, `C29434Cpx`), capability enum'ları `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`) ve `BotMetadata.memoryMetadata` (15).
- SharedPrefs anahtarı `"meta_ai_forward_disclosure_seen"`: mevcut, boolean, `ForwardMessageToMetaAiBottomSheet` için `C230589xr.A03` içinde okunur (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: `com.whatsapp.metaai.incognito.infra` konumunda mevcut (found).
- Meta AI sohbetlerinin `msgstore.db` dışında ayrı depolanması (2.26.26.4, yeniden doğrulanmadı): sohbet-deposu sınıfı bulunamadı; `meta_ai_memory` yalnızca bellek olgularını tutar, dolayısıyla iddia ne desteklenir ne de çürütülür.

---

## 8. Baileys neden yanıt alamıyor

Tüm satırlar **inferred**: istemcinin gereksinimlerinin üçüncü taraf gönderim yoluyla statik karşılaştırması; canlı test yok.

| Sorun | 2.26.41.6'daki dayanak | Seviye |
|-------|--------------------|------|
| Yanlış hedef JID tipi | Bot JID'leri `s.whatsapp.net` değil, sunucu `bot` kullanır (`C24770wv`); telefon numaralı botlar PN→FBID tablosu üzerinden eşlenir | found (JID sınıfı), inferred (etki) |
| Yönlendirme JID'sinde `$1` | Mevcut değil. `$1` persona ID string'indedir | found |
| Eksik `botInvokeMessage` sarmalayıcısı | İstemci giden `Message`'ı alan 67'ye sarar (`F2K`) | found, gereksinim inferred |
| Eksik `messageContextInfo.botMetadata` | İstemci içine `personaId`, `invokerJid` vb. yazar | found, gereksinim inferred |
| `personaId = "meta_ai"` | İstemcinin gönderdiği bu değil; profil persona string'ini gönderir (örn. `1807055946647697$1`) | found |
| Eksik `aiConversationContext` | `BotMetadata` alan 20; ilk turdaki davranış unknown | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | İstemci hook'larının ayarladığı WebMessageInfo alanları; sunucu gereksinimi unknown | unknown |
| `botTargetId` | İstemci kodunda yazıcı yok | found |
| Yanıt ayrıştırılmıyor | `richResponseMessage` `Message` alan 97'dir | found |
| Chunk birleştirme | 2.26.41.6 kanıtıyla desteklenmiyor (bkz. 6.2) | found |

---

## 9. Baileys Çözümü

Çalışan bir uygulama iddia edilmiyor. Aşağıdaki, 2.26.41.6'ya göre alanların nerede durduğunu gösteren, **inferred** olarak işaretlenmiş yapısal bir taslaktır; bir sunucuya karşı çalıştırılmadı.

### 9.1 Hedef

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

`bot` sunucu string'inin Baileys relay hedefi olarak çalışıp çalışmadığı ve sunucunun nihai stanza `to` değerini nasıl türettiği unknown.

### 9.2 Alan yerleşimi (yalnızca biçim)

```ts
// inferred shape, field numbers found in 2.26.41.6
const content = {
  botInvokeMessage: {            // Message 67, wrapper with message = 1 (found; wrap is conditional, see 5)
    message: {
      extendedTextMessage: { text }
    }
  },
  // Placement of messageContextInfo (outer Message vs. inner message) is unresolved.
  messageContextInfo: {          // Message 35
    botMetadata: {               // MessageContextInfo 7
      personaId: '1807055946647697$1', // BotMetadata 2: profile persona string (found in C223219iv for Hatch)
      invokerJid: yourJid,             // BotMetadata 5: field exists; writer not read
      timezone: 'Europe/Berlin',       // BotMetadata 8: client sets the TimeZone ID when advertising capabilities (Hatch)
      capabilityMetadata: { capabilities: [/* EnumC32144E2q numbers, Hatch only */] } // BotMetadata 13
      // aiConversationContext (20): field exists; client write not traced, do not invent a value
    }
  }
}
```

- `botMetadata`'nın `messageContextInfo` (alan 7) içine gömülmesi **found**. `capabilityMetadata` (13) ve `timezone` (8) istemci tarafından yalnızca Hatch hedefleri için yazılır (found); sunucu tarafı gereksinimleri unknown. `baron-baileys-v2` proto'sunda bu alanların zaten olup olmadığı kontrol edilmedi; yoksa proto genişletilmelidir (inferred).
- `isSupportAiMessage` (70) ve `botMessageInvokerJid` (58) `WebMessageInfo` alanlarıdır. Wire üzerinde bulunmaları gerekip gerekmediği unknown; bunları `contextInfo` içine koymayın (2.26.26.4 raporunda yanlıştı).
- `botTargetId`: derlenmiş kodun hiçbir yerinde istemci yazıcısı yok (found); ayarlamayın.
- Tam sarma (`botInvokeMessage.message`'ın gerçek mesajı içermesi mi, yanında mı durması mı) `F2K` / `C33284Eea` yeniden sarmasını izler; tam serileştirilmiş sonuç yeniden üretilmedi (unknown).

### 9.3 Yanıt işleme

- Rich yanıtlar: `Message.richResponseMessage` alan **97**'dir (found). Alan 77'yi değil, bunu ayrıştırın.
- Chunk işlemeyi kaldırın: `chunkOrder` / `isLastChunk` Meta AI streaming alanları değildir (6.2).
- Hatch `ProtocolMessage.aiMetadataOperation` (31) JSON-istek kanalıdır; düz sohbet yanıtlarının bunu kullandığı gösterilmedi.

### 9.4 Konuşma bağlamı

`BotMetadata.aiConversationContext` (20) mevcut. Sunucunun yanıtlarda güncel durumu döndürdüğü ve bunun geri yankılanması gerektiği **inferred**'dır (alan adından ve 2.26.26.4 raporundan); doğrulanmadı.

---

## 10. Akışlar

### 10.1 Bota sohbet mesajı (istemci tarafı found, sunucu tarafı inferred)

```
[Client] outgoing Message
    │  F2K / C33284Eea: Message.botInvokeMessage = BD2{ message = original }
    │  C33473Ehf: messageContextInfo.botMetadata{ personaId = profile.A0A, ... }
    │  D36 hooks: WebMessageInfo.botMessageInvokerJid (58), isSupportAiMessage (70)
    ▼
[Routing] AbstractC24760wu.A01: LID 165332417282214 → bot 1807055946647698
    │  phone JID → bot JID via PN→FBID table
    ▼
[WA Server] (not observed; inferred) → Meta AI backend
    ▼
[Client] incoming Message.richResponseMessage (97)  →  AiRichResponseFooterView / UnifiedResponseActionHandlerFactory
```

### 10.2 Hatch metadata isteği (istemci tarafı found)

```
[Feature code] HF1.A01(jid, method, params)
    │  requestId = random; A03[requestId] = GuR(method, onPart); A04[requestId] = continuation
    ▼
JSON {"version":1,"type":"req","payload":{"method","params","accepts_encoding"}} → bytes
    ▼
Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
    ▼
[WA Server] (not observed)
    ▼
Response: matched by requestId (inferred) → continuation resumes; timeout → GDB.A00
```

---

## 11. 2.26.26.4'e göre değişiklikler

| Öğe | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | Eski, flag 25119 | Mevcut değil. 25119 yalnızca flag tablolarında, okuyucu yok |
| JID'ler 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 `bot` sunucusu (`C24770wv`); 165332417282214 `lid` (`C14080dr`) |
| Yeni JID sabitleri | listelenmemişti | `1807055946647699` (CoEx v2 bot-envelope / cihaz-kümesi hedefi), `2942131436135992` (varsayılan Meta AI profil JID'si, bot-JID testi `A07`), `867051314767696555` (ikinci `A07` üyesi, amaç unknown), `17015557208` (Meta AI'ın PN'i, `A04`) |
| `$1` soneki | Yönlendirme JID'sinde, `C1A2.A00/A01` | JID'de değil; persona ID string'ine eklenir (`C24121Ab2`, `C223219iv`) |
| Yönlendirme dönüşümü | `$1` ekleme | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`, PN → FBID tablosuyla bot |
| Flag adları 25119/26189/27083 | `ai_*` flag adları | String'ler feature-list girdileridir (`C25056AqU`); 26190 = Hatch profil JSON'u; 37227/37852/37054 Hatch capability değerlerini 76 / 77 / 79 kapılar |
| `richResponseMessage` | Alan 77 | Alan 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | "WebMessageInfo" üzerinde 67 / 100 / 104 | `Message` üzerinde 67 / 100 / 104; ayrıca 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` hiç yazılmaz |
| BotMetadata konumu | "mesaja gömülü" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | Profil persona string'i, örn. `1807055946647697$1`; `meta_ai` bir bot tipi etiketidir |
| Plugin tipleri | 8, 9, 15 | Aynı, enum 18 değerli (17'ye kadar) |
| Action enum | Değer enum'u 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| Hatch JSON zarfı | `method`, `params` üst düzey | `payload` altına yuvalanmış; `accepts_encoding` eklenmiş |
| Hatch taşıyıcısı | Standart mesaj, sınıf `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; `bizAiMetadataSync` (2) eklenmiş |
| Bekleyen haritalar | Bir tane (`A02`) | İki tane: `A04` continuation'lar, `A03` `GuR` kısmi callback'leri |
| Streaming alanları | Tek bir Meta AI chunk tablosu | `chunkOrder` (history sync), `isLastChunk` (TEE mesajı), `streamingSidecar` (medya); `clientStreaming`/`serverStreaming` bulunamadı |
| Profil sync aralığı | "yaklaşık her 1 dk" | 1 dk WorkManager backoff'udur, periyot değil |
| `MetaAiMemoryStore` | Mevcut | Adıyla bulunamadı; `meta_ai_memory` tablosu (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) bulundu |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Mevcut | Mevcut |
| Yazıyor göstergesi (chatstate'ler) | Found | Found: giden `<chatstate><composing/></chatstate>`, bot bahsedildiğinde `<bot jid/>` ile (`C199098dN.A01`); gelen `composing`/`paused` genel işleyici `C40511kx` üzerinden, bota özgü dal yok |
| Capability bildirimi | belgelenmemişti | Hatch için `BotMetadata.capabilityMetadata` (13) + `timezone` (8); flag'ler 37227 / 37852 / 37054 enum değerleri 76 / 77 / 79'a eşlenir |
| Hatch istek örnekleri | belgelenmemişti | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
