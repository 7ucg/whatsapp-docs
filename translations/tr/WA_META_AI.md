<!-- src-sha1: 4a0b884541f4221f33fe16d1a5659612eb6bac89 -->
# WhatsApp Meta AI — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-17
**Kapsam:** Meta AI iç yapısı — JID'ler, yönlendirme, proto alanları, Hatch metadata istekleri, yanıt render'ı, Baileys'in neden başarısız olduğu, düzeltme

---

## 1. Meta AI teknik olarak nedir

Meta AI, özel bot JID'leri (sunucu `bot`) ile adreslenen, normal mesaj tiplerinde bot'a özgü proto alanları bulunan ve `ProtocolMessage` içinde taşınan ayrı bir JSON istek kanalına ("Hatch metadata") sahip bir bot kişisidir. Bu rapordaki tüm ifadeler decompile edilmiş APK'nın statik analizine dayanır. Seviye (tier): **found** = kodda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülmedi.

Bu rapordaki 2.26.26.4'te obfuscate edilmiş adlar (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`) sabit referanslardan yeniden çözüldü; 2.26.41.6'da bu adlarla mevcut değiller.

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|------|
| BotJid | `C24770wv` | JID sınıfı, sunucu `"bot"`, tip 26, 1-20 karakter sayısal string, başında 0 yok |
| Bot JID sabitleri | `AbstractC34361Xw` | Hatch / Fallback / LID sabitleri ve kümeleri |
| JID eşlemesi | `AbstractC24760wu` | bot ↔ LID eşlemesi, giden hedef dönüşümü |
| Gating | `C39311it` | JID başına feature-flag gating (`A0E(Jid)`) |
| Hatch istek yöneticisi | `HF1` (`HatchMetadataRequestManager`) | JSON istekleri, bekleyen map |
| Hatch proto builder | `Hf6` | `ProtocolMessage.aiMetadataOperation` oluşturur |
| Message | `C30628DTw` | proto `Message` |
| WebMessageInfo | `C30626DTu` | proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | `botMetadata`'yı tutar |
| BotMetadata | `C30615DTj` | mesaj başına bot metadata |
| Bot profil kaydı | `C199348dm` | ad, açıklama, persona ID string, thumb |

---

## 2. Meta AI JID'leri

### 2.1 Kodda bulunan JID'ler

| Sabit | Sınıf | Rol | Seviye |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`) via `AbstractC34361Xw.A00` | **Hatch**, birincil (primary). `C223219iv` içinde flag payload **26190**'dan oluşturulan varsayılan profil | found |
| `1807055946647698` | `C24770wv` (`bot`) via `AbstractC34361Xw.A01` | Fallback. Flag 27083 ile gated | found |
| `165332417282214` | `C14080dr` (sunucu `"lid"`) via `AbstractC34361Xw.A02` | `…698`'in LID karşılığı | found |
| `1807055946647696` | none | Manus (2.26.26.4'te legacy): 2.26.41.6'da **mevcut değil** | found (yok) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), ayrıca `A01` = `DeviceJid` device 0 | Bir "bot zarfı (bot envelope)" için session/device hedefi olarak kullanılan bot-server JID'i (CoEx v2 sync request handler `C53148Nnt`, sync payload'ını birincil cihazına şifreler, log `coexv2 attached bot envelope`), alıcı cihaz kümelerine (`C12M`) eklenir ve retry-receipt handling'de (`C33020EaI`) bir bot gönderici olarak işlenir. Bir chat kişisi değil | found (kullanım); bunun ötesindeki amaç inferred |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | Yerleşik varsayılan "Meta AI" profil kaydının JID'i (`C9i5.A00`: ad `Meta AI`, varsayılan giriş metni). Bir sonraki satırla birlikte bot-JID testi `AbstractC24760wu.A07`'nin üyesi | found |
| `867051314767696555` | `AbstractC24760wu.A01` (singleton set, `C24770wv`) | `A07` bot-JID testinin ikinci üyesi (`A07(jid)` = `C24770wv`, `…135992`'ye eşit veya bu kümede); `A07`, `AbstractC199328dk.A00`'ı besler (bir JID-sınıfı predicate'i). Başka bir amacı çözülmedi | found (kullanım), amaç unknown |
| `17015557208` | `AbstractC24760wu.A04` | Telefon kullanıcı string'i. `A04(jid)`, LID `165332417282214` için veya bu telefon kullanıcısı için true; `A03` ile birlikte kullanılır (herhangi bir `C24770wv` bot JID'i, veya 13135550000-13135559999 / 13165550000-13165550099 aralığındaki bir PN) `E76.A00`'da (sınıf 10 vs 1) ve uygunluk predicate'i `C736539v.ARO`'da. Meta AI'nin PN kimliği olarak okunuyor; bu iki tüketicinin bununla ne yaptığı çözülmedi | found (kullanım), amaç unknown |

`AbstractC34361Xw` içindeki kümeler: `A05 = {…697, …698}`; `A03 = {…697, …698, 165332417282214}`; map `A04`: `…697 → […697]`, `…698 → […698, 165332417282214]`.

JID tipi: 2.26.26.4 raporu dördünü de `@s.whatsapp.net` olarak listelemişti. 2.26.41.6'da bot JID'leri `getServer() = "bot"` olan `C24770wv`'dir; grup/LID olanı ise sunucusu `"lid"` olan `C14080dr`'dir. `s.whatsapp.net` değil (found).

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

Found: bot JID `…698` ↔ LID `165332417282214`; telefon numarası bot kişileri bot JID'lerine eşlenir. Metot "needs FBID migration" assert eder (found).

### 2.3 `$1` eki: değişti

2.26.26.4 raporu `$1`'i routing JID'in üzerine yerleştirmişti ("wire format", `C1A2.A00()/A01()`). 2.26.41.6'da bulunmadı:
- Hiçbir routing fonksiyonu bir JID'e `$1` eklemiyor. 2.2'deki dönüşüm düz bot JID'leri üretiyor.
- `$1`, bot profil kaydında saklanan persona ID string'ine eklenir: `C24121Ab2`, `personaIdString = botFbid + "$1"` işlemini yapar; `C223219iv`, Hatch varsayılan profili için `"1807055946647697$1"`'i hardcode eder (found).
- Bu string (`C199348dm.A0A`), `C33473Ehf.A0G`'nin `BotMetadata.personaId`'ye yazdığı şeydir (found).

Yani `$1`, hedef JID'e değil, persona ID'ye aittir.

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

Manus dalı (flag 25119) kaldırılmış. `BRD()`'nin ve capability lookup'ın (`C09L.A04`) anlamı çözülmedi (unknown).

---

## 3. Özellik Flag'leri

| Flag ID | 2.26.41.6'daki kullanım | Seviye |
|---------|------------------|------|
| **25119** | Sadece flag tablolarında görünüyor (`C06510El`, `C08J`'de varsayılan `false`). Hiçbir okuyucu (reader) bulunamadı. Eski ad `ai_bot_integration_enabled` bir string olarak bulunamadı | found |
| **26189** | `C39311it.A02()`'de Hatch gate'i. Varsayılan `false` (`C08J`) | found |
| **27083** | `C39311it.A0E()`'de Fallback / LID gate'i. Varsayılan `false` | found |
| **26190** | Varsayılan Hatch profili için JSON config (`name`, `description`, `profile_thumb`), `C223219iv`'de okunuyor | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. True olduğunda, capability `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) Hatch'e advertise edilir (bkz. 5); `A05` ayrıca connector telemetry/UI'yi de gate'ler (`C28147CLx`, `C1427261o`, `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. `HATCH_SECURE_CREDENTIAL_CARD_ENABLED`'ı (77) advertise eder; ayrıca connector availability'yi de gate'ler (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. `HATCH_ARTIFACT_CARD_ENABLED`'ı (79) advertise eder; ayrıca `HatchSpacesSync` ve `C7WL` tarafından da okunur | found |

`ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` string'leri flag adları değildir. Bunlar, `C25056AqU`'da flag 26189 / 27083'ten oluşturulan bir feature-string listesinin girdileridir (`username_supported`, `post_status_in_companion`, ... ile birlikte); `ai_fbid_migration_receiving_enabled` koşulsuz olarak eklenir. Listenin alıcısı ve amacı doğrulanmadı.

---

## 4. Proto Alanları

### 4.1 Message (`C30628DTw`) üst seviye

| Alan | Numara | Tip | Kullanım |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (single field `message` = 1) | Bot için sarmalanmış (wrapped) giden mesaj; `F2K`, `C33284Eea`'da set edilir |
| `botTaskMessage` | **100** | `BD2` | Bot görevi (task) |
| `botForwardedMessage` | **104** | `BD2` | `richResponseMessage` tutan bir mesajı sarmalar; `F3E`'de set edilir |
| `richResponseMessage` | **97** | `DSY` | AI yanıtı. Alanlar: `messageType` 1, `submessages` 2, `unifiedResponse` 3, `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | Mevcut |
| `botGroupParticipantMessage` | **137** | `BD2` | Mevcut |
| `messageContextInfo` | **35** | `C30624DTs` | `botMetadata`'yı taşır |
| `protocolMessage` | **12** | `BD3` | `aiMetadataOperation`'ı (31) taşır |

Alan **77**, `richResponseMessage` değil `commentMessage`'dır (2.26.26.4 raporunda 77 vardı; bu build için yanlış, ve ayrı richResponseMessage araştırmasıyla tutarlı: 97).

### 4.2 WebMessageInfo (`C30626DTu`), ContextInfo değil

2.26.26.4 raporu bunları ContextInfo alanları olarak listelemişti. 2.26.41.6'da bunlar `WebMessageInfo` üzerinde:

| Alan | Numara | Tip | Kullanım |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | `C34385EwW`'de `C0DZ.A09(userJid)`'den set edilir (invoker'ın primary device kullanıcısı) |
| `isSupportAiMessage` | **70** | bool | Mesaj `268435456` flag bit'ine sahip olduğunda ve bir kontrol geçtiğinde `C34378EwP.C57`'de set edilir; `C59`'da geri okunur. `is1PBizBotMessage` (**56**) ile birlikte |
| `supportAiCitations` | **72** | repeated message | Alıntılar (citations) |
| `botTargetId` | **73** | string | Client'ta hiçbir writer yok: `botTargetId_`, sadece constructor default'u olarak ve `C30626DTu`'nun schema tablosunda görünür, başka hiçbir yerde atanmaz (full-source grep) |
| `agentId` | **47** | string | Mevcut, analiz edilmedi |

Bu WebMessageInfo alanlarının wire üzerinde görünüp görünmediği ve nasıl göründüğü doğrulanmadı (unknown). "Tüm Meta AI mesajları için `true`" iddiası desteklenmiyor: koşulsuz değil, mesaj flag'ine göre set ediliyor.

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
| `invokerJid` | **5** | string | Invoker |
| `aiConversationContext` | **20** | bytes | Konuşma durumu (conversation state) |
| `botResponseId` | **26** | string | Yanıt ID'si |

Mevcut diğer alanlar (adlar `*_FIELD_NUMBER`'dan, tipler okunmadı): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId`, `C33473Ehf.A0G`'de doldurulur; profilin persona string'i yoksa erken döner (return).

### 4.5 PluginMetadata (`DTL`)

| Alan | Numara | Tip | Değer |
|-------|--------|------|-------|
| `provider` | **1** | int32 | Provider ID'si |
| `pluginType` | **2** | enum `C4E0` | Aşağıya bakın |
| `profilePhotoCdnUrl` | **4** | string | |
| `referenceIndex` | **6** | | |
| `expectedLinksCount` | **7** | | |
| `pluginVersion` | **8** | | |
| `parentPluginType` | **11** | | |
| `faviconCdnUrl` | **13** | | |

`C4E0` sabitleri (değer = constructor ordinal'i; proto numarasına eşit olması inferred): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. Eski 8/9/15 değerleri değişmedi; enum daha büyük.

### 4.6 Action oneof (`C61331Rfl`, case enum `EnumC61601RkN`)

| Numara | Case | Seviye |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

Bu, düz bir value enum değil, action alanlarının bir oneof'udur. Nereye embed edildiği izlenmedi (unknown).

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

İstekler `HF1` (`HatchMetadataRequestManager`) tarafından oluşturulur, coroutine sınıfı `HatchMetadataRequestManager$sendRequest$2`. JSON zarfı (envelope) 2.26.26.4'ten farklıdır: `method` ve `params`, `payload` altına nest edilmiştir.

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

`params` ve `accepts_encoding` opsiyoneldir (found). Request ID JSON içinde değildir; `BB2.requestId`'dir (`C20F.A0x()`'ten rastgele bir string).

Gönderim yolu (send path) (found):
```
HF1.A01(jid, method, ..., params, viewMode, timeoutMs)
  → sendRequest$2: registers onPart callback in A03[requestId] = GuR(method, onPart)
  → JSON → bytes
  → C02381: A04[requestId] = continuation
  → GwX "HatchMetadataSyncHelper/sendMetadataToHatch" → C37393GKy(jidTo, 138, timestampMs)
       .A02 = payload bytes, .A01 = requestId, .A0M = viewMode
  → Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
```

- Bekleyen istekler: `HF1.A04` (`ConcurrentHashMap`, requestId → continuation) ve `HF1.A03` (requestId → `GuR`). İkisi de `finally`'de temizlenir. 2.26.26.4 raporu sadece bir map'i `A02` olarak adlandırmıştı.
- Timeout: `GDB.A00`'ı döner ve `HatchMetadataRequestManager/sendRequest timed out method=` logunu yazar.
- `C37393GKy`'ye geçirilen `138` tam sayısı çözülmedi (unknown).
- Taşıyıcı, düz bir chat mesajı değil `ProtocolMessage.aiMetadataOperation`'dır (alan 31) (changed).
- `com.whatsapp.bot.infra.message.aimetadata` paketi `Ideas*Wire` / `Idea*Wire` sınıflarını içerir (found). Method adlarıyla ilişkileri sadece inferred'dir; method adları enumerate edilmedi.
- `A04`'ü complete eden alım (receive) tarafı izlenmedi. Bir yanıtın `requestId`'ye eşleştirilmesi, `A04` map'inden ve `BB2.requestId`'den inferred'dir.

**Özel XMPP namespace yok** iddiası: izlenen yolda `w:ai` / `wa:ai` handling'i görülmedi; yokluğa dayalı (absence-based), kapsamlı olarak yeniden doğrulanmadı.

**Capability advertisement (found, `C33284Eea`):** hedef Hatch JID `…697` (`AbstractC34361Xw.A00`) olduğunda ve bir gate geçtiğinde, client `DPJ`'yi oluşturur (tek repeated enum alanı `capabilities` = 1, değerler `EnumC32144E2q`) ve `C33473Ehf.A06`, bunu giden mesajın `BotMetadata.capabilityMetadata`'sına (13), `BotMetadata.timezone` (8) = cihazın `TimeZone` ID'si ile birlikte saklar. Gate'e göre eklenen capability'ler:

| Gate | Capability (enum numarası) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| flag **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| flag **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| flag **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

Numaralar enum'un ikinci constructor argümanıdır; proto numaralarına eşit olmaları inferred'dir. Enum ayrıca rich-response capability'lerini de listeler (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**İstek örnekleri (found, `params` key'leri call site'larda okundu; call site konuşma JID'ini kullanmadıkça hedef Hatch JID `…697`'dir):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | `HatchIdeasManager$execute$job$1`'de oluşturulur (key'ler okunmadı); `onPart` callback'i attach edilir |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire` JSON'a serialize edilir; `onPart` callback'i attach edilir |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` sadece boş olmadığında) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

`BB2.data` içindeki byte'ların şekli (found shape, örnek değerler):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

`accepts_encoding`, sadece caller'ın `acceptsGzipResponse`'u true olduğunda yazılır; `params` sadece non-null olduğunda. `onPart` callback'i, sadece caller bir tane geçirdiğinde `A03`'e register edilir.

**Bot'a chat mesajı (found kısımlar):**
- Giden `Message`, `Message.botInvokeMessage`'a (`F2K`, `C33284Eea`) yeniden sarmalanır (re-wrapped), wrapper `BD2` mesajı field 1'de tutar. `F2K`'de, `C13S.A00()` false olduğunda, mesajın `A10`'u false olduğunda veya flag **10646** açık olduğunda sarmalama (wrap) atlanır (mesaj doğrudan set edilir) (found).
- `BotMetadata`, `C33473Ehf.A0E` / `A0G` tarafından oluşturulur. `A0G`, hedef bot JID'i için profil kaydına bakar (`C199358dn.A06(userJid)`, persona string `C199348dm.A0A`); bu string boşsa metot bot metadata yazmadan döner, aksi halde `personaId`'yi (2) ve, mevcutsa, `suggestedPromptMetadata`'yı (4) ve diğer sub-message'ları set eder. Persona string'i, profil kaydı oluşturulduğunda saklanır (`C24121Ab2`, `<id>$1`'i oluşturur; `C223219iv`, Hatch için `1807055946647697$1`'i hardcode eder). `messageContextInfo`'nun dış `Message`'a mı yoksa `botInvokeMessage` içindeki mesaja mı yerleştiği (lands) çözülmedi.
- `botMessageInvokerJid` / `isSupportAiMessage`, D36 hook'ları tarafından (`C34385EwW`, `C34378EwP`) `WebMessageInfo` üzerinde set edilir.

---

## 6. Yanıt Protokolü

### 6.1 Transport

2.26.26.4'te belirtildiği gibi yeniden doğrulanmadı ("`hatchMetadataSync` byte'larına sahip normal mesajlar", sınıf `Azz`). Found: `hatchMetadataSync`, `ProtocolMessage.aiMetadataOperation` içindeki `C25754B9o`'da yaşar. Hatch yanıtları muhtemelen aynı şekilde gelir ve `requestId` ile eşleşir (inferred). Hatch istekleri method call'lardır; normal chat yanıtlarının yolu oldukları gösterilmedi.

### 6.2 Streaming / chunk'lar: açıklandığı gibi desteklenmiyor

2.26.26.4 tablosu (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`), tek bir Meta AI streaming mekanizması olarak 2.26.41.6'da desteklenmiyor:

| Alan | 2.26.41.6'da nerede |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` alan **7** (history-sync bildirimi, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) ve `C25838BCy` alan **5** (history sync) |
| `isLastChunk` | `C55285Ou6` alan **8** (`attestationBundles`, `teeModelConfig`, `violationSignal` içeren mesaj; TEE ile ilgili) |
| `streamingSidecar` | image/video/audio mesajlarında alan **18** (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | proto alanları olarak bulunamadı |

Meta AI yanıtlarının chunk reassembly'si bulunamadı. Hatch için var olan: `GuR(method, onPart)` — istek başına bir `onPart` callback'i (found); partial sonuçlar taşıdığı isimden inferred'dir.

### 6.3 Rich response (alan 97)

`richResponseMessage` (`DSY`) = `Message` üzerinde alan **97**. Rendering sınıfları mevcut: `AiRichResponseFooterView` ve `UnifiedResponseActionHandlerFactory` (paket `com.whatsapp.conversationrow.botrichresponse`) (found). Alıntılar (citations): `WebMessageInfo.supportAiCitations` (72). İçerik tipleri (görseller, tablolar, kod) burada yeniden doğrulanmadı; ayrı richResponseMessage araştırmasına bakın.

### 6.4 Typing indicator (yazıyor göstergesi)

Giden (found, `C199098dN.A01`, log `HandleMeComposing/handleComposing`): standart XMPP chat state, okunan kodda özel namespace yok.
- Düz durum (bahsedilen (mentioned) bir bot yok, veya bir bot JID'i varsayılana çözüldü): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Chat'te bahsedilen (mentioned) bir bot var: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- `C10140Tq.A0X` üzerinden IQ-type int 4 ile gönderilir.

Gelen (found, `C40511kx` stanza handler'ı): bir `composing` child'ı olan (opsiyonel `media`) bir `<chatstate>`, generic composing callback'ini `from`/`participant` ile çağırır; `paused`, paused callback'ini çağırır. Bu handler'da bot'a özgü bir branch bulunamadı, dolayısıyla bir bot-JID `composing`'i herhangi bir kişi (contact) ile aynı yoldan geçer (inferred; server-side bir bot typing stanza'sı gözlemlenmedi). `BotMetadata.progressIndicatorMetadata` (12) ve `PROGRESS_INDICATOR` capability'si, ayrı bir in-message progress mekanizması olarak mevcut (sadece adlar, izlenmedi).

### 6.5 Bot profil sync'i

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`), `A03()`'te `BotProfileForChatListWorker`'ı schedule eder: `setBackoffCriteria(policy, 1, MINUTES)` ve bir constraint (type değeri çözülmedi) ile `BotProfileSyncManager` tag'li bir WorkManager isteği. 1 dakika bir retry **backoff**'udur, bir periyot değil. 2.26.26.4'teki "her ~1 dakika" desteklenmiyor (changed). `A02(groupJid, userJid)`, tek bir profil ister (`requestBotProfileResult`). Normal roster sync'in bir parçası değil (unchanged).

Profil kaydı `C199348dm`: bot type'ı (`C1XY`), jid, görünen ad (`A09`), açıklama (`A07`), persona string'i (`A0A`), thumb'lar, timestamp.

### 6.6 Bot type string'leri

`C718732k.A00(String)` şunları map eder: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; başka her şey `AnonymousClass399(str)` olur. Bunlar bot-type label'larıdır (UI filtrelerinde de kullanılır), `BotMetadata.personaId` değerleri değildir (found).

---

## 7. Depolama (Storage)

- `MetaAiMemoryStore`: 2.26.41.6'da bu ada sahip bir sınıf yok. Bulunan eşdeğeri, schema sınıfı `C23621AHm` tarafından oluşturulan bir `meta_ai_memory` tablosudur (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, `memory_content` üzerinde `meta_ai_memory_memory_content_index` index'i. Hangi database dosyasının bunu tuttuğu çözülmedi. İlgili (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; ad deprecated olduğunu söylüyor), SharedPrefs `meta_ai_memory_disclosure_seen` (sesli arama tasarım ekranı, `C29434Cpx`), capability enum'ları `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`), ve `BotMetadata.memoryMetadata` (15).
- SharedPrefs key'i `"meta_ai_forward_disclosure_seen"`: mevcut, boolean, `ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) için `C230589xr.A03`'te okunur (found).
- `MetaAiIncognitoSessionManager`: `com.whatsapp.metaai.incognito.infra`'da mevcut (found).
- Meta AI chat'lerinin `msgstore.db` dışında ayrı depolanması (2.26.26.4, yeniden doğrulanmadı): hiçbir chat-store sınıfı bulunamadı; `meta_ai_memory` sadece memory fact'lerini tutuyor, dolayısıyla iddia ne desteklenmiyor ne de çürütülüyor.

---

## 8. Baileys'in neden yanıt alamadığı

Tüm satırlar **inferred**'dir: client'ın gereksinimlerinin üçüncü taraf bir gönderim (send) yolu ile statik karşılaştırması; canlı test yok.

| Sorun | 2.26.41.6'daki dayanak | Seviye |
|-------|--------------------|------|
| Yanlış hedef JID tipi | Bot JID'leri `s.whatsapp.net` değil `bot` sunucusunu (`C24770wv`) kullanır; telefon numarası bot'ları bir PN→FBID tablosu üzerinden map edilir | found (JID sınıfı), inferred (etki) |
| Routing JID'inde `$1` | Mevcut değil. `$1`, persona ID string'inde | found |
| Eksik `botInvokeMessage` wrapper'ı | Client, giden `Message`'ı alan 67'de sarmalar (`F2K`) | found, gereksinim inferred |
| Eksik `messageContextInfo.botMetadata` | Client, buraya `personaId`, `invokerJid` vb. yazar | found, gereksinim inferred |
| `personaId = "meta_ai"` | Client'ın gönderdiği bu değil; profil persona string'ini gönderir (örn. `1807055946647697$1`) | found |
| Eksik `aiConversationContext` | `BotMetadata`'nın alan 20'si; ilk turdaki davranış unknown | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | Client hook'ları tarafından set edilen WebMessageInfo alanları; server gereksinimi unknown | unknown |
| `botTargetId` | Client kodunda hiçbir writer yok | found |
| Yanıt parse edilmedi | `richResponseMessage`, `Message`'ın alan 97'sidir | found |
| Chunk reassembly | 2.26.41.6 kanıtlarına göre desteklenmiyor (bkz. 6.2) | found |

---

## 9. Bot İmza Doğrulaması (içerik özgünlüğü)

Yukarıdakilerin hepsinden ayrı: `richResponseMessage` içeriğinin, mesajı kimin relay ettiğinden bağımsız olarak gerçekten Meta'nın AI backend'inden geldiğini **alıcı** client'ın doğrulamasına izin veren bir mekanizma. Aşağıdaki statik bulgular 2.26.41.6 kodunda `found`'dur; 9.4'teki replay sonucu `tested`'dır (canlı, yazarın kendi hesabında — trafik interception değil, kendi mesajını oluşturan ve relay eden meşru bir client).

### 9.1 Proto konumu

`BotMetadata.verificationMetadata` — alan **27** (`messageContextInfo` (35) → `botMetadata` (7) → `verificationMetadata` (27)), tip `DPC`/`BotSignatureVerificationMetadata` (toString gerçek adı ortaya çıkarıyor): `proofs[]`, her biri `version` (int), `useCase` (enum `WA_BOT_MSG` / `WA_TEE_BOT_MSG`), `signature` (bytes), `certificateChain` (repeated bytes, DER X.509) içeren bir `BotSignatureVerificationUseCaseProof`.

### 9.2 Doğrulama algoritması

Sınıf `C33259EeB`, internal adı `BotSignatureVerificationUtils` (log string'lerinden):

1. `HFg.A01(date, certs, true)` üzerinden, `certificateChain`'in bir trust anchor'a karşı **certificate-chain doğrulaması**.
2. **İmzalanan byte'ların oluşturulması (signed-bytes construction)**: `"1" + <phone-number string> + <unifiedResponse bytes>` — imza, sadece içeriği değil, **içerik ve telefon numarasını birlikte** bağlar.
3. Leaf certificate'in SubjectPublicKeyInfo'sundan çıkarılan ham Ed25519 anahtarı kullanılarak **EdDSA verify** (log: `"EdDSA signature verification result"`).
4. Config **19590**'dan okunan **Enforcement mode**, enum `EnumC32057Dzg`: `NONE` (`"none"`, disabled, her zaman pass), `LOG_ONLY` (`"log_only"`, verify + log, hiçbir zaman block etmez), `ENFORCE_BLOCKING` (`"enforce_blocking"`, başarısız bir kontrol `false` döner). Sonuç `E05` olarak saklanır: `UNKNOWN` / `VALID` / `FAILED` / `DOWNLOAD_CONSENT_ACCEPTED`, SQLite kolonu `bot_message_info.signature_validation_status`'ta persist edilir (tabloda `bot_client_public_key` da var).

### 9.3 Satır render gate'i

`C30085D6v.A00` (row-type dispatcher'ı) ve `EOK`/`C32608EKo`: imza durumu `FAILED` ise ve flag **27635** açıksa → maskeli satır `ConversationRowAiUnknownSenderMasked` ("signature verification failed"). Bağımsız olarak, gönderici JID'i locally-synced bot-profile store'da (`C224899mg`, `BotProfileSyncManagerImpl` ile aynı sync) mevcut değilse ve flag **27355** açıksa → `ConversationRowAiUnknownSenderPreview` ("unknown sender with unconsented content"), sert bir block değil, consent-gated bir preview.

### 9.4 Gerçek capture ve canlı replay (tested)

Gerçek bir konuşmada client-side olarak capture edilen gerçek bir Meta AI yanıtı (kendi hesap, yazarın kendi client'ı tarafından decrypt edildi — trafik interception değil), şunları taşıyordu:

- `botMetadata.verificationMetadata.proofs[0]`: `version: 1`, `useCase: "WA_BOT_MSG"`, 64 byte'lık (Ed25519 boyutunda) bir `signature`, 2 girdili bir `certificateChain`.
- Leaf certificate: `CN=svc:wa-bot-msg-leaf`, Ed25519 anahtarı, `Meta WA SS Int CA 2025-09` tarafından issue edildi, `Meta WA Feature Root CA`'ya (`O=Meta Platforms Inc.`) chain'leniyor, validity ≈7 ay (auto-rotated service cert) — imzalayan private key sadece Meta'nın backend'inde mevcut.
- `botMetadata.botInfrastructureDiagnostics.botBackend: "CLIPPY"` — daha önce dokümante edilmemiş bir bot backend adı (bkz. 1–6. bölümlerdeki "Hatch").
- `messageContextInfo.accountEncryptionAttestation.accountType: "NON_E2EE"`, `botMetadata`'nın bir sibling (kardeş) alanı.
- Delivery şekli: `type: MESSAGE_EDIT` olan `protocolMessage`, `editedMessage.richResponseMessage` (thread'deki ilk yanıt, bir placeholder'ın edit'i olarak pre-wrapped gelir), `key.remoteJid` = yazarın kendi JID'i.

**Test:** tam olarak aynı `richResponseMessage` + `messageContextInfo.botMetadata` (signature ve certificate chain byte-for-byte değişmeden), bot JID'i `867051314767696@bot` değil, yazarın kendi cihazından `relayMessage` üzerinden yazarın kendi numarasına (imzalanan byte'lara zaten embed edilmiş olan aynı numara) relay edildi.

**Sonuç:** içerik, tam "AI" styling'i ve gerçek metinle, "Forwarded" etiketiyle render edildi. Aynı payload'ın bazı delivery'leri bunun yerine bir Download action'ı ile "WhatsApp can't verify the security of this media. Only download if you trust the sender." gösterdi; Download'a dokunmak, 9.3'teki `DOWNLOAD_CONSENT_ACCEPTED` durumu ve "unknown sender with unconsented content" kod yoluyla eşleşen aynı içeriği ortaya çıkardı. Bir delivery, bunun yerine generic bir "your version of WhatsApp doesn't support it" fallback'i gösterdi; sebep belirlenmedi (unknown).

**Sonuç (tested):** 9.2'deki kriptografik kontrol, canlı göndericinin kimliğine veya JID'ine değil, *(içerik, telefon numarası)*'na bağlanır. Geçerli şekilde imzalanmış bir `richResponseMessage`, alıcının numarası imzaya pişirilmiş (baked into) numarayla eşleştiği sürece, bot olmayan bir göndericiden replay edilebilir ve yine de signature verification'ı geçer — alıcı client bunu gerçek AI içeriği olarak render eder (en fazla, sert bir block değil, tek dokunuşlu, kozmetik bir "unknown sender" consent adımıyla gate'lenir). Bu bir içerik-özgünlüğü mekanizmasıdır, gönderici-özgünlüğü mekanizması değil; canlı göndericiyi doğrulayan bu imza değil, WhatsApp'ın kendi Signal-layer şifrelemesidir.

---

## 10. Baileys Düzeltmesi (Fix)

Çalışan bir implementasyon iddia edilmiyor. Aşağıda, alanların 2.26.41.6'ya göre nerede yaşadığına dair yapısal bir taslak var, **inferred** olarak işaretlendi; bir server'a karşı çalıştırılmadı.

### 9.1 Hedef

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

`bot` sunucu string'inin bir Baileys relay hedefi olarak çalışıp çalışmadığı ve server'ın final stanza `to`'sunu nasıl türettiği unknown.

### 9.2 Alan yerleşimi (sadece şekil)

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

- `botMetadata`'nın `messageContextInfo`'ya (alan 7) embed edilmesi **found**'dur. `capabilityMetadata` (13) ve `timezone` (8), client tarafından sadece Hatch hedefleri için yazılır (found); server-side gereksinimleri unknown. `baron-baileys-v2` proto'sunun bu alanlara zaten sahip olup olmadığı kontrol edilmedi; değilse, proto'nun genişletilmesi gerekir (inferred).
- `isSupportAiMessage` (70) ve `botMessageInvokerJid` (58), `WebMessageInfo` alanlarıdır. Wire'da bulunmaları gerekip gerekmediği unknown; bunları `contextInfo`'ya koymayın (bu, 2.26.26.4 raporunda yanlıştı).
- `botTargetId`: decompile edilmiş kodda hiçbir yerde client writer'ı yok (found); bunu set etmeyin.
- Tam sarmalama (wrapping) (`botInvokeMessage.message`'ın gerçek mesajı içermesi vs. yanında olması), `F2K` / `C33284Eea` re-wrapping'ini takip eder; tam serialize edilmiş sonuç reproduce edilmedi (unknown).

### 9.3 Yanıt handling'i

- Rich yanıtlar: `Message.richResponseMessage`, alan **97**'dir (found). Alan 77'yi değil, bunu parse edin.
- Chunk handling'i kaldırın: `chunkOrder` / `isLastChunk`, Meta AI streaming alanları değildir (6.2).
- Hatch `ProtocolMessage.aiMetadataOperation` (31), JSON-request kanalıdır; düz chat yanıtlarının bunu kullandığı gösterilmedi.

### 9.4 Konuşma context'i

`BotMetadata.aiConversationContext` (20) mevcut. Server'ın yanıtlarda güncellenmiş state döndürdüğü ve bunun geri echo edilmesi gerektiği **inferred**'dir (alan adından ve 2.26.26.4 raporundan); doğrulanmadı.

---

## 11. Akışlar (Flows)

### 10.1 Bot'a chat mesajı (found client side, inferred server side)

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

### 10.2 Hatch metadata isteği (found client side)

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

## 12. 2.26.26.4'e göre değişiklikler

| Öğe | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | Legacy, flag 25119 | Mevcut değil. 25119 sadece flag tablolarında, reader yok |
| JID'ler 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 `bot` sunucusu (`C24770wv`); 165332417282214 `lid` (`C14080dr`) |
| Yeni JID sabitleri | listelenmemiş | `1807055946647699` (CoEx v2 bot-envelope / device-set hedefi), `2942131436135992` (varsayılan Meta AI profil JID'i, bot-JID testi `A07`), `867051314767696555` (ikinci `A07` üyesi, amaç unknown), `17015557208` (Meta AI'nin PN'i, `A04`) |
| `$1` eki | Routing JID'inde, `C1A2.A00/A01` | JID'de değil; persona ID string'ine eklendi (`C24121Ab2`, `C223219iv`) |
| Routing dönüşümü | `$1` ekleme | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`, PN → FBID tablosu üzerinden bot |
| Flag adları 25119/26189/27083 | `ai_*` flag adları | String'ler feature-list girdileridir (`C25056AqU`); 26190 = Hatch profil JSON'u; 37227/37852/37054, Hatch capability değerlerini 76 / 77 / 79 gate'ler |
| `richResponseMessage` | Alan 77 | Alan 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | "WebMessageInfo" üzerinde 67 / 100 / 104 | `Message` üzerinde 67 / 100 / 104; ayrıca 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` hiçbir zaman yazılmıyor |
| BotMetadata konumu | "mesaja embed edilmiş" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | Profil persona string'i, örn. `1807055946647697$1`; `meta_ai` bir bot type label'ı |
| Plugin type'ları | 8, 9, 15 | Aynı, enum 18 değere sahip (17'ye kadar) |
| Action enum | Value enum 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| Hatch JSON envelope'u | `method`, `params` top-level | `payload` altına nest edildi; `accepts_encoding` eklendi |
| Hatch taşıyıcısı | Standart mesaj, sınıf `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; `bizAiMetadataSync` (2) eklendi |
| Bot signature verification'ı | dokümante edilmemiş | Yeni: `BotMetadata.verificationMetadata` (27), (içerik, telefon numarası) üzerinde EdDSA + X.509 cert chain; canlı test edildi, canlı göndericiye değil telefon numarasına bağlanıyor (bölüm 9) |
| Pending map'ler | Bir (`A02`) | İki: `A04` continuation'ları, `A03` `GuR` part callback'leri |
| Streaming alanları | Bir Meta AI chunk tablosu | `chunkOrder` (history sync), `isLastChunk` (TEE mesajı), `streamingSidecar` (media); `clientStreaming`/`serverStreaming` bulunamadı |
| Profil sync aralığı | "her ~1 dakika" | 1 dakika bir WorkManager backoff'udur, bir periyot değil |
| `MetaAiMemoryStore` | Mevcut | Adıyla bulunamadı; `meta_ai_memory` tablosu bulundu (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Mevcut | Mevcut |
| Typing indicator (chatstate'ler) | Found | Found: bir bot mentioned olduğunda `<bot jid/>` ile giden `<chatstate><composing/></chatstate>` (`C199098dN.A01`); generic handler `C40511kx` üzerinden gelen `composing`/`paused`, bot'a özgü branch yok |
| Capability advertisement'i | dokümante edilmemiş | Hatch için `BotMetadata.capabilityMetadata` (13) + `timezone` (8); flag 37227 / 37852 / 37054, enum değerleri 76 / 77 / 79'a map eder |
| Hatch istek örnekleri | dokümante edilmemiş | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
