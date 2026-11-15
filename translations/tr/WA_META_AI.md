<!-- src-sha1: 92bebfe6214e20e4e50526fbb6583d35cc44e808 -->
# WhatsApp Meta AI — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-17
**Kapsam:** Meta AI internal'leri — JID'ler, routing, proto alanları, Hatch metadata istekleri, yanıt render'ı, Baileys'in neden başarısız olduğu, düzeltme

---

## 1. Meta AI teknik olarak nedir

Meta AI, özel bot JID'leriyle (sunucu `bot`) adreslenen, sıradan mesaj tiplerinde bot-özgü proto alanları ve bir `ProtocolMessage` içinde taşınan ayrı bir JSON istek kanalı ("Hatch metadata") olan bir bot kişisidir. Tüm ifadeler decompile edilmiş APK'nın statik analizidir. Kademe: **found** = kodda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülmedi.

Bu raporda 2.26.26.4'te obfuscated olan isimler (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`), stabil referans noktalarından yeniden çözülmüştür; 2.26.41.6'da o isimlerle mevcut değillerdir.

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|------|
| BotJid | `C24770wv` | JID sınıfı, sunucu `"bot"`, tip 26, sayısal string 1-20 karakter, öncü 0 yok |
| Bot JID sabitleri | `AbstractC34361Xw` | Hatch / Fallback / LID sabitleri ve kümeleri |
| JID eşlemesi | `AbstractC24760wu` | bot ↔ LID eşlemesi, çıkış hedefi dönüşümü |
| Gating | `C39311it` | JID-başına feature-flag gating'i (`A0E(Jid)`) |
| Hatch istek yöneticisi | `HF1` (`HatchMetadataRequestManager`) | JSON istekleri, bekleyen map |
| Hatch proto builder'ı | `Hf6` | `ProtocolMessage.aiMetadataOperation`'ı inşa eder |
| Message | `C30628DTw` | proto `Message` |
| WebMessageInfo | `C30626DTu` | proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | `botMetadata`'yı tutar |
| BotMetadata | `C30615DTj` | mesaj-başına bot metadata'sı |
| Bot profil kaydı | `C199348dm` | ad, açıklama, persona ID string'i, thumb |

---

## 2. Meta AI JID'leri

### 2.1 Kodda bulunan JID'ler

| Sabit | Sınıf | Rol | Kademe |
|----------|-------|------|------|
| `1807055946647697` | `AbstractC34361Xw.A00` üzerinden `C24770wv` (`bot`) | **Hatch**, primary. Varsayılan profil, flag payload **26190**'dan `C223219iv`'de inşa edilir | found |
| `1807055946647698` | `AbstractC34361Xw.A01` üzerinden `C24770wv` (`bot`) | Fallback. Flag 27083 ile gated | found |
| `165332417282214` | `AbstractC34361Xw.A02` üzerinden `C14080dr` (sunucu `"lid"`) | `…698`'in LID karşılığı | found |
| `1807055946647696` | yok | Manus (2.26.26.4'te legacy): 2.26.41.6'da **mevcut değil** | found (yok) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), artı `A01` = `DeviceJid` cihaz 0 | Bir "bot zarfı" için oturum/cihaz hedefi olarak kullanılan bot-sunucu JID'i (CoEx v2 senkronizasyon isteği handler'ı `C53148Nnt`, senkronizasyon payload'unu kendi primary cihazına şifreler, log `coexv2 attached bot envelope`), alıcı cihaz kümelerine (`C12M`) eklenir ve retry-receipt işlemesinde (`C33020EaI`) bir bot gönderen olarak ele alınır. Bir sohbet persona'sı değil | found (kullanım); bunun ötesindeki amaç inferred |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | Yerleşik varsayılan "Meta AI" profil kaydının JID'i (`C9i5.A00`: ad `Meta AI`, varsayılan giriş metni). Bir sonraki satırla birlikte bot-JID testi `AbstractC24760wu.A07`'nin üyesi | found |
| `867051314767696555` | `AbstractC24760wu.A01` (singleton küme, `C24770wv`) | `A07` bot-JID testinin ikinci üyesi (`A07(jid)` = `C24770wv`, `…135992`'ye eşit veya bu kümede); `A07`, `AbstractC199328dk.A00`'ı (bir JID-sınıfı yüklemi) besler. Daha fazla amaç çözülmedi | found (kullanım), amaç unknown |
| `17015557208` | `AbstractC24760wu.A04` | Telefon kullanıcı string'i. `A04(jid)`, LID `165332417282214` için veya bu telefon kullanıcısı için doğrudur; `E76.A00`'da (sınıf 10 vs 1) ve uygunluk yüklemi `C736539v.ARO`'da `A03` (herhangi bir `C24770wv` bot JID'i, veya 13135550000-13135559999 / 13165550000-13165550099 aralıklarındaki PN) ile birlikte kullanılır. Meta AI'ın PN kimliği olarak okunuyor; bu iki tüketicinin bununla ne yaptığı çözülmedi | found (kullanım), amaç unknown |

`AbstractC34361Xw`'deki kümeler: `A05 = {…697, …698}`; `A03 = {…697, …698, 165332417282214}`; map `A04`: `…697 → […697]`, `…698 → […698, 165332417282214]`.

JID tipi: 2.26.26.4 raporu dördünü de `@s.whatsapp.net` olarak listelemişti. 2.26.41.6'da bot JID'leri `getServer() = "bot"` olan `C24770wv`'dir; grup/LID olanı `"lid"` sunucusuna sahip `C14080dr`'dir. `s.whatsapp.net` değil (found).

Telefon-numarasından bot-FBID tablosuna: `AbstractC199338dl.A00` (`HashBiMap`, 1313555xxxx → FBID, yaklaşık 200 girdi, örn. `13135550002 → 867051314767696`). `C0DZ.A08(UserJid)` (`convertPNJidtoBotJidIfExists`) tarafından kullanılır (found).

### 2.2 Routing dönüşümü

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

Found: bot JID `…698` ↔ LID `165332417282214`; telefon-numarası bot kişileri bot JID'lerine eşlenir. Metod "needs FBID migration" olarak assert eder (found).

### 2.3 `$1` eki: değişti

2.26.26.4 raporu `$1`'i routing JID'ine yerleştirmişti ("wire formatı", `C1A2.A00()/A01()`). 2.26.41.6'da bulunamadı:
- Hiçbir routing fonksiyonu bir JID'e `$1` eklemiyor. 2.2'deki dönüşüm düz bot JID'leri üretir.
- `$1`, bot profil kaydında saklanan persona ID string'ine eklenir: `C24121Ab2`, `personaIdString = botFbid + "$1"` yapar; `C223219iv`, Hatch varsayılan profili için `"1807055946647697$1"`'i hardcode eder (found).
- O string (`C199348dm.A0A`), `C33473Ehf.A0G`'nin `BotMetadata.personaId`'ye yazdığı şeydir (found).

Yani `$1`, hedef JID'e değil, persona ID'ye aittir.

### 2.4 isMetaAI algılaması

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

Manus dalı (flag 25119) ortadan kalkmış. `BRD()`'nin ve capability aramasının (`C09L.A04`) anlamı çözülmedi (unknown).

---

## 3. Feature Flag'leri

| Flag ID | 2.26.41.6'da kullanım | Kademe |
|---------|------------------|------|
| **25119** | Sadece flag tablolarında görünüyor (`C06510El`, `C08J`'de varsayılan `false`). Hiçbir okuyucu bulunamadı. Eski ad `ai_bot_integration_enabled` bir string olarak bulunamadı | found |
| **26189** | `C39311it.A02()`'de Hatch gate'i. Varsayılan `false` (`C08J`) | found |
| **27083** | `C39311it.A0E()`'de Fallback / LID gate'i. Varsayılan `false` | found |
| **26190** | Varsayılan Hatch profili için JSON config (`name`, `description`, `profile_thumb`), `C223219iv`'de okunur | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. Doğru olduğunda, capability `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76), Hatch'e reklam edilir (bkz 5); `A05` ayrıca connector telemetri/UI'sini (`C28147CLx`, `C1427261o`, `C36186FnU`) gater | found |
| **37852** | `C39311it.A0A() = A02() && flag`. `HATCH_SECURE_CREDENTIAL_CARD_ENABLED`'i (77) reklam eder; ayrıca connector mevcudiyetini (`AbstractC26695Bhv`) gater | found |
| **37054** | `C39311it.A0B() = A02() && flag`. `HATCH_ARTIFACT_CARD_ENABLED`'i (79) reklam eder; ayrıca `HatchSpacesSync` ve `C7WL` tarafından okunur | found |

`ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` string'leri flag adları değildir. Bunlar, flag 26189 / 27083'ten `C25056AqU`'da inşa edilen bir feature-string listesinin girdileridir (`username_supported`, `post_status_in_companion`, ... ile birlikte); `ai_fbid_migration_receiving_enabled`, koşulsuz eklenir. Listenin alıcısı ve amacı doğrulanmadı.

---

## 4. Proto Alanları

### 4.1 Message (`C30628DTw`) üst-seviye

| Alan | Numara | Tip | Kullanım |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (tek alan `message` = 1) | Bot için sarılmış çıkış mesajı; `F2K`, `C33284Eea`'da ayarlanır |
| `botTaskMessage` | **100** | `BD2` | Bot görevi |
| `botForwardedMessage` | **104** | `BD2` | `richResponseMessage` tutan bir mesajı sarar; `F3E`'de ayarlanır |
| `richResponseMessage` | **97** | `DSY` | AI yanıtı. Alanlar: `messageType` 1, `submessages` 2, `unifiedResponse` 3, `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | Mevcut |
| `botGroupParticipantMessage` | **137** | `BD2` | Mevcut |
| `messageContextInfo` | **35** | `C30624DTs` | `botMetadata`'yı taşır |
| `protocolMessage` | **12** | `BD3` | `aiMetadataOperation`'ı (31) taşır |

Alan **77**, `commentMessage`'dır, `richResponseMessage` değil (2.26.26.4 raporu 77'yi vermişti; bu build için yanlış, ve ayrı richResponseMessage araştırmasıyla tutarlı: 97).

### 4.2 WebMessageInfo (`C30626DTu`), ContextInfo değil

2.26.26.4 raporu bunları ContextInfo alanları olarak listelemişti. 2.26.41.6'da `WebMessageInfo` üzerindedirler:

| Alan | Numara | Tip | Kullanım |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | `C34385EwW`'de `C0DZ.A09(userJid)`'den (çağıranın primary cihaz kullanıcısı) ayarlanır |
| `isSupportAiMessage` | **70** | bool | Mesaj `268435456` flag bitine sahip olduğunda ve bir kontrol geçtiğinde `C34378EwP.C57`'de ayarlanır; `C59`'da geri okunur. `is1PBizBotMessage` (**56**) ile birlikte |
| `supportAiCitations` | **72** | repeated message | Alıntılar |
| `botTargetId` | **73** | string | İstemcide yazıcı yok: `botTargetId_`, sadece constructor varsayılanı olarak ve `C30626DTu`'nun schema tablosunda görünüyor, başka hiçbir yerde atanmıyor (tam-kaynak grep) |
| `agentId` | **47** | string | Mevcut, analiz edilmedi |

Bu WebMessageInfo alanlarının wire'da görünüp görünmediği ve nasıl göründüğü doğrulanmadı (unknown). "Her Meta AI mesajı için `true`" desteklenmiyor: mesaj-başına bir flag'e göre ayarlanıyor, koşulsuz değil.

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
| `aiConversationContext` | **20** | bytes | Sohbet durumu |
| `botResponseId` | **26** | string | Yanıt ID'si |

Mevcut diğer alanlar (isimler `*_FIELD_NUMBER`'dan, tipler okunmadı): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId`, `C33473Ehf.A0G`'de doldurulur; profilin bir persona string'i yoksa erken döner.

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

`C4E0` sabitleri (değer = constructor ordinal'i; proto numarasına eşit olduğu inferred'dir): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. Eski 8/9/15 değerleri değişmemiştir; enum daha büyük.

### 4.6 Action oneof'u (`C61331Rfl`, durum enum'u `EnumC61601RkN`)

| Numara | Durum | Kademe |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

Bu bir action alanları oneof'udur, düz bir değer enum'u değil. Nerede gömülü olduğu izlenmedi (unknown).

### 4.7 AI metadata operasyonu (Hatch taşıyıcısı)

| Mesaj | Alan | Numara | Tip |
|---------|-------|--------|------|
| `ProtocolMessage` (`BD3`) | `aiMetadataOperation` | **31** | `C25754B9o` |
| `C25754B9o` | `hatchMetadataSync` | **1** | `BB2` |
| `C25754B9o` | `bizAiMetadataSync` | **2** | `C156236jd` (`serverEvent` = 1) |
| `BB2` | `data` | **1** | bytes |
| `BB2` | `timestampMs` | **2** | int64 |
| `BB2` | `requestId` | **3** | string |

---

## 5. İstek Protokolü (Hatch metadata)

İstekler `HF1` (`HatchMetadataRequestManager`), coroutine sınıfı `HatchMetadataRequestManager$sendRequest$2` tarafından inşa edilir. JSON zarfı 2.26.26.4'ten farklıdır: `method` ve `params`, `payload` altında nested'dir.

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

`params` ve `accepts_encoding` opsiyoneldir (found). İstek ID'si JSON'da değildir; `BB2.requestId`'dir (`C20F.A0x()`'ten rastgele bir string).

Gönderme yolu (found):
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
- Timeout: `GDB.A00`'ı döndürür ve `HatchMetadataRequestManager/sendRequest timed out method=`'i loglar.
- `C37393GKy`'ye geçirilen `138` tam sayısı çözülmedi (unknown).
- Taşıyıcı, düz bir sohbet mesajı değil, `ProtocolMessage.aiMetadataOperation`'dır (alan 31) (değişti).
- `com.whatsapp.bot.infra.message.aimetadata` paketi `Ideas*Wire` / `Idea*Wire` sınıflarını içerir (found). Bunların metod adlarıyla ilişkisi sadece inferred'dir; metod adları sayılmadı.
- `A04`'ü tamamlayan alım tarafı izlenmedi. Bir yanıtı `requestId`'ye eşleştirme, `A04` map'inden ve `BB2.requestId`'den inferred'dir.

**Özel XMPP namespace'i yok** iddiası: izlenen yolda hiçbir `w:ai` / `wa:ai` işlemesi görülmedi; yokluk-tabanlı, kapsamlı olarak yeniden doğrulanmadı.

**Capability reklamı (found, `C33284Eea`):** hedef Hatch JID'i `…697` (`AbstractC34361Xw.A00`) olduğunda ve bir gate geçtiğinde, istemci `DPJ`'yi (tek repeated enum alanı `capabilities` = 1, değerler `EnumC32144E2q`) inşa eder ve `C33473Ehf.A06`, çıkış mesajının `BotMetadata.capabilityMetadata`'sında (13), `BotMetadata.timezone`'la (8) = cihazın `TimeZone` ID'siyle birlikte saklar. Gate'e göre eklenen capability'ler:

| Gate | Capability (enum numarası) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| flag **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| flag **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| flag **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

Numaralar, enum'un ikinci constructor argümanıdır; bunların proto numaralarına eşit olduğu inferred'dir. Enum ayrıca rich-response capability'lerini listeler (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**İstek örnekleri (found, çağrı noktalarında okunan `params` key'leri; çağrı noktası sohbet JID'ini kullanmadığı sürece hedef Hatch JID'i `…697`'dir):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | `HatchIdeasManager$execute$job$1`'de inşa edilir (key'ler okunmadı); `onPart` callback'i bağlanır |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire`, JSON'a serileştirilir; `onPart` callback'i bağlanır |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` sadece boş-olmayansa) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

`BB2.data`'daki byte'ların şekli (found şekil, örnek değerler):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

`accepts_encoding`, sadece çağıranın `acceptsGzipResponse`'u doğruysa yazılır; `params`, sadece null-olmayansa. `onPart` callback'i, sadece çağıran biri geçirdiğinde `A03`'te kaydedilir.

**Bota sohbet mesajı (found parçalar):**
- Çıkış `Message`'ı, `Message.botInvokeMessage`'a yeniden sarılır (`F2K`, `C33284Eea`), wrapper `BD2`, mesajı alan 1'de tutar. `F2K`'de, `C13S.A00()` yanlış olduğunda, mesajın `A10`'u yanlış olduğunda, veya flag **10646** açık olduğunda sarma atlanır (mesaj doğrudan ayarlanır) (found).
- `BotMetadata`, `C33473Ehf.A0E` / `A0G` tarafından inşa edilir. `A0G`, hedef bot JID'i için profil kaydını arar (`C199358dn.A06(userJid)`, persona string'i `C199348dm.A0A`); o string boşsa metod bot metadata'sını yazmadan döner, aksi halde `personaId`'yi (2) ve, mevcutsa, `suggestedPromptMetadata`'yı (4) ve daha fazla alt-mesajı ayarlar. Persona string'i, profil kaydı oluşturulduğunda saklanır (`C24121Ab2`, `<id>$1`'i inşa eder; `C223219iv`, Hatch için `1807055946647697$1`'i hardcode eder). `messageContextInfo`'nun dış `Message`'a mı yoksa `botInvokeMessage` içindeki mesaja mı düştüğü çözülmedi.
- `botMessageInvokerJid` / `isSupportAiMessage`, D36 hook'ları (`C34385EwW`, `C34378EwP`) tarafından `WebMessageInfo` üzerinde ayarlanır.

---

## 6. Yanıt Protokolü

### 6.1 Transport

2.26.26.4'te belirtildiği gibi yeniden doğrulanmadı ("hatchMetadataSync byte'larıyla normal mesajlar", sınıf `Azz`). Found: `hatchMetadataSync`, `ProtocolMessage.aiMetadataOperation` içindeki `C25754B9o`'da yaşıyor. Hatch yanıtları muhtemelen aynı şekilde gelir ve `requestId`'ye göre eşleşir (inferred). Hatch istekleri metod çağrılarıdır; normal sohbet yanıtlarının yolu olduğu gösterilmemiştir.

### 6.2 Streaming / parçalar: açıklandığı gibi desteklenmiyor

2.26.26.4 tablosu (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`), tek bir Meta AI streaming mekanizması olarak 2.26.41.6'da desteklenmiyor:

| Alan | 2.26.41.6'da nerede olduğu |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` alanı **7** (geçmiş-senkronizasyon bildirimi, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) ve `C25838BCy` alanı **5** (geçmiş senkronizasyonu) |
| `isLastChunk` | `C55285Ou6` alanı **8** (`attestationBundles`, `teeModelConfig`, `violationSignal` ile mesaj; TEE-ilgili) |
| `streamingSidecar` | görüntü/video/ses mesajlarında alan **18** (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | proto alanı olarak bulunamadı |

Meta AI yanıtlarının hiçbir parça yeniden-birleştirmesi bulunamadı. Hatch için var olan: `GuR(method, onPart)` — istek-başına bir `onPart` callback'i (found); kısmi sonuçlar taşıdığı isimden inferred'dir.

### 6.3 Rich response (alan 97)

`richResponseMessage` (`DSY`) = `Message` üzerinde alan **97**. Render sınıfları mevcuttur: `AiRichResponseFooterView` ve `UnifiedResponseActionHandlerFactory` (paket `com.whatsapp.conversationrow.botrichresponse`) (found). Alıntılar: `WebMessageInfo.supportAiCitations` (72). İçerik tipleri (görüntüler, tablolar, kod), burada yeniden doğrulanmadı; ayrı richResponseMessage araştırmasına bakın.

### 6.4 Yazıyor göstergesi

Çıkış (found, `C199098dN.A01`, log `HandleMeComposing/handleComposing`): standart XMPP chat state, okunan kodda özel bir namespace yok.
- Düz durum (bahsedilen bir bot yok, veya varsayılan olana çözülmüş bir bot JID'i): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Sohbette bahsedilen bot: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- IQ-tipi int 4 ile `C10140Tq.A0X` üzerinden gönderilir.

Gelen (found, `C40511kx` stanza handler'ı): bir `composing` çocuğu olan (opsiyonel `media`) bir `<chatstate>`, genel composing callback'ini `from`/`participant` ile çağırır; `paused`, paused callback'ini çağırır. Bu handler'da bot-özgü bir dal bulunamadı, bu yüzden bir bot-JID `composing`, herhangi bir kişi gibi aynı yoldan geçer (inferred; sunucu-tarafı bir bot yazıyor stanza'sı gözlenmedi). `BotMetadata.progressIndicatorMetadata` (12) ve capability `PROGRESS_INDICATOR`, ayrı bir mesaj-içi ilerleme mekanizması olarak mevcuttur (sadece isimler, izlenmedi).

### 6.5 Bot profil senkronizasyonu

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`), `A03()`'te `BotProfileForChatListWorker`'ı zamanlar: `setBackoffCriteria(policy, 1, MINUTES)` ile `BotProfileSyncManager` etiketli bir WorkManager isteği ve bir kısıtlama (tip değeri çözülmedi). 1 dakika bir retry **backoff**'tur, bir periyot değildir. 2.26.26.4'ün "her ~1 dakikada" desteklenmiyor (değişti). `A02(groupJid, userJid)`, tek bir profil ister (`requestBotProfileResult`). Normal roster senkronizasyonunun parçası değildir (değişmedi).

Profil kaydı `C199348dm`: bot tipi (`C1XY`), jid, görünen ad (`A09`), açıklama (`A07`), persona string'i (`A0A`), thumb'lar, zaman damgası.

### 6.6 Bot tip string'leri

`C718732k.A00(String)` eşlemesi: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; başka herhangi bir şey `AnonymousClass399(str)` olur. Bunlar bot-tipi etiketleridir (UI filtrelerinde de kullanılır), `BotMetadata.personaId` değerleri değil (found).

---

## 7. Depolama

- `MetaAiMemoryStore`: 2.26.41.6'da o adla bir sınıf yok. Bulunan eşdeğer, schema sınıfı `C23621AHm` tarafından oluşturulan bir tablo `meta_ai_memory`'dir (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, `memory_content` üzerinde index `meta_ai_memory_memory_content_index`. Hangi veritabanı dosyasının onu tuttuğu çözülmedi. İlgili (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; isim deprecated diyor), SharedPrefs `meta_ai_memory_disclosure_seen` (sesli-çağrı tasarım ekranı, `C29434Cpx`), capability enum'ları `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`), ve `BotMetadata.memoryMetadata` (15).
- SharedPrefs key'i `"meta_ai_forward_disclosure_seen"`: mevcut, boolean, `ForwardMessageToMetaAiBottomSheet` için `C230589xr.A03`'te okunur (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: `com.whatsapp.metaai.incognito.infra`'da mevcut (found).
- `msgstore.db` dışında Meta AI sohbetlerinin ayrı depolanması (2.26.26.4, yeniden doğrulanmadı): bir sohbet-deposu sınıfı bulunamadı; `meta_ai_memory`, sadece hafıza gerçeklerini tutuyor, bu yüzden iddia ne desteklenmiş ne de çürütülmüştür.

### 7.1 Private Search, bir bot-sohbet thread türü olarak (2.26.45.10'da yeni, found)

Yeni sınıflar (`com.whatsapp.privateai.privatesearch`, `com.whatsapp.searchui.search.psisearch`):

| Sınıf | Rol |
|-------|------|
| `PrivateSearchSessionManager` | Tek aktif/en-son Private Search thread'ini takip eder; daha yeni bir aramayla yerine geçilmiş bir thread'i sürdürmeyi reddeder |
| `PrivateSearchThreadsManager` | `PRIVATE_SEARCH` türünde bir bot thread'i oluşturur; yukarıdaki (`IncognitoAiThreadsManager`) zaten kullandığı aynı `BotThreadsManager` tabanı `LX/1gu`'yu extend eder |
| `PsiSearchManager` (obfuscated `LX/JjA`) | Sorgu gönderme/takip ("echo") akışına sahiptir |
| `PsiSearchDialogFragment` | Dialog UI'si; `"TURN_ON_PRIVATE_PROCESSING"` değerinde bir `"kind"` argümanı, Private Processing opt-in gate'ini satır içi yüzeye çıkarır |
| `PsiSearchUnifiedResponseRenderer` | Botun yanıtını render eder |

Private Search, yeni bir ağ ilkeli değil, bir **bot-sohbet thread türü** daha olarak uygulanır. `PrivateSearchThreadsManager`, 5-değerli bir enum `LX/2p4` ile paylaşımlı bot-thread constructor'ını `LX/1gv;->A00(LX/2p4, ...)`'u çağırır: `UNKNOWN`(0) / `DEFAULT`(1) / `INCOGNITO`(2) / `SIDE_CHAT`(3) / `PRIVATE_SEARCH`(4). `PsiSearchManager`, göndermeden önce bir thread'in türünü bu discriminator'a karşı yeniden doğrular, boş bir sorguyu veya `PRIVATE_SEARCH`-olmayan bir thread'i reddeder.

**Sorgu gönderme yolu (found).** `PsiSearchManager.onEchoSelected`, diğer sohbet gönderimlerinin kullandığı aynı genel mesaj-oluşturma yardımcısı aracılığıyla, `LX/D1D;->A05(...)`, çıkış mesajını inşa eder, sonra sonucu sıradan çıkış-mesajı kuyruğu (`LX/JjA;->A0H:LX/0JB;->D2A`) üzerinden dispatch eder. Bu yolun hiçbir yerinde GraphQL/MEX/IQ çağrısı görünmez — bu, §11'de ("Chat message to the bot") belgelenen aynı `botInvokeMessage` (alan 67) bota-sarma mekanizmasıdır, kelimesi kelimesine yeniden kullanılmıştır ve burada yeniden türetilmemiştir.

**Native kalan şey (çapraz referans).** Sorguyu gerçekte cevaplayan PSI/TEE alım hattı — `TeeClientToolOrchestrator`, `PsiSearchToolHandler` (`wa_search` istemci aracı), `IplsdHandshakeExecutor`, native `libpsi.so`/`libxplat_psi.so` tarafından desteklenir — 2.26.41.6'dan değişmemiştir ve brain'in Labyrinth/TEE araştırmasında belgelenmiştir (burada yeniden türetilmemiştir); yukarıdaki beş sınıf buna dokunmaz, onlar sadece çıkış mesajını inşa eder ve yanıtı render eder.

**Erişilebilirlik hükmü: erişilebilir gönderi, erişilemez değer.** Arama-başlatma gönderimi, bir üçüncü-taraf istemci tarafından Meta AI sohbetinin zaten (§8, §11) olduğu tam anlamda erişilebilirdir — yenmek için yeni bir şey yok. Erişilemez olan, özelliğin gerçek gizlilik-koruyucu değeridir: yerel sohbet DB'si üzerindeki cihaz-üzerinde PSI araması ve attested-enclave round-trip'i native'dir, ve çıkış `Message`'ı önceden-hesaplanmış hiçbir PSI materyali taşımaz. Private Search bot JID'ine düz metin gönderen bir üçüncü-taraf istemci, sunucu-tarafı botun PSI'lenmemiş bir düz-metin sorguyla yaptığı her şeyi alır, WhatsApp'ın kendi private-search semantiğini değil (unknown, her iki yönde de doğrulanmamış).

### 7.2 Üretim-durdurma, wire-mesajı yolundan taşındı (2.26.45.10'da yeni)

`promptMessageKey` hata string'i (`FMessageStopGeneration` / `ProtocolMessage.extraJson_`'a bağlı, tip 26, 2.26.35.8'den beri mevcut), 2.26.45.10'daki tüm 14 DEX dosyası boyunca **sıfır** eşleşmeye sahiptir (found, kapsamlı string taraması). Altta yatan alan `extraJson_`, hâlâ `LX/DHC;`'de (`ProtocolMessage` host sınıfı) deklare edilmiş ama sadece o sınıfın kendi alan deklarasyonu ve reflection dizisi içinde referanslanıyor — uygulamadaki hiçbir başka sınıf onu okumuyor (found). D8, bu build'de debug bilgisini tamamen soyduğundan (`classes6.dex`'teki 34.255 metod boyunca sıfır geri-kazanılabilir `DBG_SET_FILE` dosya adı), `FMessageStopGeneration`'ı eskiden destekleyen obfuscated sınıf debug metadata'sından tespit edilemedi; onun için üç `.kt` dosya-adı string'i sadece yetim string-pool girdileri olarak hayatta kalıyor, erişilebilir kod olarak değil (found).

Bunun yerine bulunan: `A00(threadIdentifier, messageIdentifier, messageIdString, surface, mode, Continuation)`'ı bir Pando GraphQL mutation'ını (`MetaAIStopGenerationMutation`, op `xfb_genai_stop_generation`) tetikleyen, yeni, **obfuscated-olmayan** bir sınıf `com/meta/metaai/stopgeneration/data/StopGenerationRepository`, `thread_identifier`, `message_identifier`, `message_id_string`, `surface`, `mode` alanlarıyla, generic string-key-olmayan null-kontrolleriyle (`LX/00m;->A09`) doğrulanmış — `promptMessageKey`-tarzı hata metni yok.

En iyi açıklama (**inferred**, kanıtlanmamış): üretim-durdurma, eski wire-mesajı kontrolünün yerinde yeniden adlandırılması yerine bu surface için bu GraphQL mutation'ına taşındı. Eski `protocolMessage`/tip-26/`extraJson_` yolunun artık ölü kod mu olduğu, eski-istemci uyumluluğu için mi tutulduğu, yoksa izlenmemiş bir çağırandan hâlâ erişilebilir mi olduğu **unknown**'dır — bu build'de hiçbir çağıran bulunamadı, ama tek-DEX statik bir tarama kaldırmayı kanıtlayamaz.

---

## 8. Baileys neden bir yanıt almıyor

Tüm satırlar **inferred**'dir: istemcinin gereksinimlerinin bir üçüncü-taraf gönderme yoluyla statik karşılaştırması; canlı test yok.

| Sorun | 2.26.41.6'daki temel | Kademe |
|-------|--------------------|------|
| Yanlış hedef JID tipi | Bot JID'leri sunucu `bot`'u (`C24770wv`) kullanır, `s.whatsapp.net`'i değil; telefon-numarası bot'ları bir PN→FBID tablosu üzerinden eşlenir | found (JID sınıfı), inferred (etki) |
| Routing JID'inde `$1` | Mevcut değil. `$1`, persona ID string'indedir | found |
| Eksik `botInvokeMessage` wrapper'ı | İstemci, çıkış `Message`'ını alan 67'de sarar (`F2K`) | found, gereksinim inferred |
| Eksik `messageContextInfo.botMetadata` | İstemci `personaId`, `invokerJid`, vb. onun içine yazar | found, gereksinim inferred |
| `personaId = "meta_ai"` | İstemcinin gönderdiği şey değil; profil persona string'ini gönderir (örn. `1807055946647697$1`) | found |
| Eksik `aiConversationContext` | `BotMetadata`'nın alanı 20; ilk turda davranış unknown | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | İstemci hook'ları tarafından ayarlanan WebMessageInfo alanları; sunucu gereksinimi unknown | unknown |
| `botTargetId` | İstemci kodunda yazıcı yok | found |
| Yanıt ayrıştırılmadı | `richResponseMessage`, `Message`'ın alanı 97'dir | found |
| Parça yeniden-birleştirme | 2.26.41.6 kanıtı tarafından desteklenmiyor (bkz 6.2) | found |

---

## 9. Bot İmza Doğrulaması (içerik gerçekliği)

Yukarıdakinden ayrı olarak: **alıcı** istemcinin, mesajı kimin relay ettiğinden bağımsız olarak, `richResponseMessage` içeriğinin gerçekten Meta'nın AI backend'inden geldiğini doğrulamasını sağlayan bir mekanizma. Aşağıdaki statik bulgular 2.26.41.6 kodunda `found`'dur; 9.4'teki replay sonucu `tested`'dir (canlı, yazarın kendi hesabında — trafik interception değil, kendi mesajını oluşturan ve relay eden meşru bir istemci).

### 9.1 Proto konumu

`BotMetadata.verificationMetadata` — alan **27** (`messageContextInfo` (35) → `botMetadata` (7) → `verificationMetadata` (27)), tip `DPC`/`BotSignatureVerificationMetadata` (toString gerçek adı açığa çıkarır): `proofs[]`, her biri `version` (int), `useCase` (enum `WA_BOT_MSG` / `WA_TEE_BOT_MSG`), `signature` (bytes), `certificateChain` (repeated bytes, DER X.509) ile bir `BotSignatureVerificationUseCaseProof`.

### 9.2 Doğrulama algoritması

Sınıf `C33259EeB`, dahili ad `BotSignatureVerificationUtils` (log string'lerinden):

1. `HFg.A01(date, certs, true)` aracılığıyla bir güven kökü'ne karşı `certificateChain`'in **sertifika-zinciri doğrulaması**.
2. **İmzalanan-byte'ların inşası**: `"1" + <telefon-numarası string'i> + <unifiedResponse byte'ları>` — imza **içeriği ve bir telefon numarasını birlikte** bağlar, sadece içeriği değil.
3. Leaf sertifikanın SubjectPublicKeyInfo'sundan çıkarılan ham Ed25519 key'i kullanarak **EdDSA doğrulaması** (log: `"EdDSA signature verification result"`).
4. Config **19590**'dan okunan **enforcement modu**, enum `EnumC32057Dzg`: `NONE` (`"none"`, devre dışı, her zaman geçer), `LOG_ONLY` (`"log_only"`, doğrular + loglar, hiçbir zaman bloklamaz), `ENFORCE_BLOCKING` (`"enforce_blocking"`, başarısız bir kontrol `false` döndürür). Sonuç, `E05` olarak saklanır: `UNKNOWN` / `VALID` / `FAILED` / `DOWNLOAD_CONSENT_ACCEPTED`, SQLite kolonunda `bot_message_info.signature_validation_status`'ta kalıcı hale getirilir (tabloda `bot_client_public_key` da var).

### 9.3 Satır render gate'i

`C30085D6v.A00` (satır-tipi dispatcher) ve `EOK`/`C32608EKo`: imza durumu `FAILED`'sa ve flag **27635** açıksa → maskelenmiş satır `ConversationRowAiUnknownSenderMasked` ("signature verification failed"). Bağımsız olarak, gönderen JID'i yerel-senkronize bot-profil deposunda (`C224899mg`, `BotProfileSyncManagerImpl`'inkiyle aynı senkronizasyon) yoksa ve flag **27355** açıksa → `ConversationRowAiUnknownSenderPreview` ("unknown sender with unconsented content"), sert bir blok yerine consent-gated bir önizleme.

### 9.4 Gerçek yakalama ve canlı replay (tested)

Gerçek bir sohbette istemci-tarafında yakalanan (kendi hesap, yazarın kendi istemcisi tarafından çözülmüş — trafik interception değil) gerçek bir Meta AI yanıtı şunları taşıyordu:

- `botMetadata.verificationMetadata.proofs[0]`: `version: 1`, `useCase: "WA_BOT_MSG"`, 64-byte'lık (Ed25519-boyutunda) bir `signature`, 2-girdili bir `certificateChain`.
- Leaf sertifikası: `CN=svc:wa-bot-msg-leaf`, Ed25519 key, `Meta WA SS Int CA 2025-09` tarafından yayınlanmış, `Meta WA Feature Root CA`'ya (`O=Meta Platforms Inc.`) zincirleniyor, geçerlilik ≈7 ay (otomatik-döndürülen servis sertifikası) — imzalayan özel key sadece Meta'nın backend'inde var.
- `botMetadata.botInfrastructureDiagnostics.botBackend: "CLIPPY"` — daha önce belgelenmemiş bir bot backend adı (bkz ayrıca bölüm 1-6'da "Hatch").
- `messageContextInfo.accountEncryptionAttestation.accountType: "NON_E2EE"`, `botMetadata`'nın bir kardeş alanı.
- Teslimat şekli: `type: MESSAGE_EDIT` ile `protocolMessage`, `editedMessage.richResponseMessage` (bir thread'deki ilk yanıt, bir placeholder'ın düzenlemesi olarak önceden-sarılmış gelir), `key.remoteJid` = yazarın kendi JID'i.

**Test:** tam `richResponseMessage` + `messageContextInfo.botMetadata` (imza ve sertifika zinciri byte-byte değişmeden), yazarın kendi cihazından — bot JID'i `867051314767696@bot` değil — yazarın kendi numarasına (imzalanan byte'lara zaten gömülü aynı numara) `relayMessage` üzerinden relay edildi.

**Sonuç:** içerik tam "AI" stilizasyonuyla ve gerçek metinle render edildi, "Forwarded" etiketli. Aynı payload'ın bazı teslimatları bunun yerine "WhatsApp can't verify the security of this media. Only download if you trust the sender." gösterdi, bir Download eylemiyle; Download'a dokunmak, `DOWNLOAD_CONSENT_ACCEPTED` durumuyla ve 9.3'teki "unknown sender with unconsented content" kod yoluyla eşleşen aynı içeriği ortaya çıkardı. Bir teslimat bunun yerine genel bir "your version of WhatsApp doesn't support it" fallback'i gösterdi; neden tespit edilmedi (unknown).

**Sonuç (tested):** 9.2'deki kriptografik kontrol, canlı gönderenin kimliğine veya JID'ine değil, *(içerik, telefon numarası)*'na bağlanır. Geçerli şekilde imzalanmış bir `richResponseMessage`, alıcının numarası imzaya pişirilmiş numarayla eşleştiği sürece bot-olmayan bir gönderenden relay edilebilir ve hâlâ imza doğrulamasını geçer — alıcı istemci onu gerçek AI içeriği olarak render eder (en fazla bir-dokunuşluk, kozmetik bir "unknown sender" consent adımıyla gated, sert bir blok değil). Bu, bir içerik-gerçekliği mekanizmasıdır, bir gönderen-gerçekliği mekanizması değildir; canlı gönderenin kimliğini doğrulayan şey bu imza değil, WhatsApp'ın kendi Signal-katmanı şifrelemesidir.

### 9.5 Sertifika-iptal-listesi (CRL) kontrolü (2.26.45.10'da yeni, found)

9.2'deki zincir-doğrulama adımı (adım 1, "sertifika-zinciri doğrulaması... `HFg.A01` üzerinden"), Ed25519 imza-üzerinde-(telefon, içerik) kontrolünden (9.2 adım 3) önce, `certificateChain`'deki hem leaf hem de intermediate sertifikalara karşı bir CRL kontrolü edindi. Sınıflar: `BotPkiCrlGraphQLFetcher`/`BotPkiCrlManager` (`com/whatsapp/bot/infra/message/signature/`), 2.26.45.10 zincir-doğrulama sınıfı `BotSignatureVerificationCertificateManager`'dan (`LX/HEe` — 9.2'deki `BotSignatureVerificationUtils`/`C33259EeB`'nin yeniden-adlandırılmış ardılı; paylaşımlı log string'leriyle (`"Certificate chain validation successful"`/`"Parsed <n> certificates from chain"`) doğrulanan aynı sınıf) çağrılır.

- **GraphQL operasyonu**: `whatsapp-android-mex` üzerinde `FetchBotPKICRL` — istek alanı `crl_name`, yanıt `xwa2FetchFeaturePkiCrl`, CRL'i önceden-ayrıştırılmış bir iptal-edilmiş-seri listesi olarak değil ham bir DER byte blob'u olarak, artı `fetchedAt`/`nextUpdate` zaman damgaları ve bir iptal-edilmiş-girdi sayısı olarak tutuyor.
- **Ada göre kullanımda iki CRL**: **leaf** sertifikası için `whatsapp_simple_signal`, **intermediate** sertifikası için `whatsapp_feature` (log string'leri `"...Leaf certificate CRL validation passed"` / `"...is revoked"` / `"...CRL unavailable..."`, "Intermediate" için aynı çift).
- **Güven kökü**: `LX/HEe` içinde bir PEM literal olarak pinned 40-yıllık bir kök sertifika — `CN=Meta WA Feature Root CA`, `O=Meta Platforms Inc.`, EC key, 2025-09-04'ten 2065-09-04'e geçerli. Her çekilen CRL'in kendi imzası, iptal-edilmiş listesine güvenilmeden önce ilgili issuer'ın public key'ine karşı doğrulanır (`X509CRL.verify(...)`) — `whatsapp_simple_signal` hariç, bu kendi-doğrulama adımını atlamak için özel durum olarak ele alınır (`inferred` neden, çözülmedi).
- **Cache'leme/yenileme**: crlName-başına `SharedPreferences` cache'i (`crl-data`/`crl-fetched-at`/`crl-next-update`), kullanıcı kayıtlı ve DB hazır olduktan sonra uygulama init'inde bir kez prefetch edilir (log: `"BotPkiCrlManager/...starting CRL prefetch"`), CRL'in kendi `nextUpdate`'ine (60 saniyede taban değere sahip) bağlı bir zamanlayıcıda yenilenir, ve bir kontrol çalıştığında cache eksik/bayat ise bir backoff penceresiyle talep üzerine çekilir.
- **Etki**: iptal edilmiş bir leaf veya intermediate sertifikası, zaten süresi dolmuş bir sertifikanın yaptığı aynı şekilde zincir doğrulamasında başarısız olur — bu, 9.2 adım 4'teki mevcut `E05` durumunu (`FAILED`) ve `ENFORCE_BLOCKING`/`LOG_ONLY`/`NONE` gate'ini besler, yeni, ayrı bir enforcement yolu değil.
- **Kademe**: found — operasyon, namespace, her iki crlName, cache/yenileme mekaniği, çağrı noktaları, pinned kök sertifika. Inferred — tam iptal-edilmiş-girdi byte düzeni (seri vs. tam sertifika byte'ları) ve `whatsapp_simple_signal`'in CRL kendi-doğrulamasını neden atladığı. Hepsi statik analiz; pratikte hiçbir iptal edilmiş sertifika gözlenmedi.
- **İstemci/Baileys yüzeyi**: `FetchBotPKICRL`, diğer `whatsapp-android-mex` operasyonlarının erişilebilir olduğu aynı şekilde erişilebilir, somut, adlandırılmış bir MEX operasyonudur, ama sadece bot-mesajı sertifikaları hakkında istemci-tarafı güven kararlarını besler — bot-olmayan bir gönderenin neyi relay edebileceği üzerinde hiçbir etkisi yoktur (9.4'ün replay sonucu etkilenmez: iptal, bunun hiç çalıştırmadığı, gerçekte-iptal-edilmiş bir sertifika için sonuçları değiştirir sadece).

---

## 10. Baileys Düzeltmesi

Çalışan bir uygulama iddia edilmiyor. Aşağıda, alanların 2.26.41.6'ya göre nerede yaşadığına dair yapısal bir taslak **inferred** olarak işaretlenmiştir; bir sunucuya karşı çalıştırılmamıştır.

### 9.1 Hedef

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

`bot` sunucu string'inin bir Baileys relay hedefi olarak çalışıp çalışmadığı, ve sunucunun nihai stanza `to`'yu nasıl türettiği unknown'dır.

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

- `botMetadata`'nın `messageContextInfo` içine (alan 7) gömülmesi **found**'dur. `capabilityMetadata` (13) ve `timezone` (8), istemci tarafından sadece Hatch hedefleri için yazılır (found); sunucu-tarafı gereksinimleri unknown'dır. `baron-baileys-v2` proto'sunun bu alanlara zaten sahip olup olmadığı kontrol edilmedi; değilse, proto genişletilmelidir (inferred).
- `isSupportAiMessage` (70) ve `botMessageInvokerJid` (58), `WebMessageInfo` alanlarıdır. Wire'da mevcut olmaları gerekip gerekmediği unknown'dır; onları `contextInfo`'ya koymayın (bu, 2.26.26.4'ün raporunda yanlıştı).
- `botTargetId`: decompile edilmiş kodun hiçbir yerinde istemci yazıcısı yok (found); onu ayarlamayın.
- Tam sarma (`botInvokeMessage.message`'ın gerçek mesajı tutması vs. yanında), `F2K` / `C33284Eea` yeniden-sarmasını izler; tam serileştirilmiş sonuç yeniden üretilmedi (unknown).

### 9.3 Yanıt işleme

- Rich yanıtlar: `Message.richResponseMessage`, alan **97**'dir (found). Alan 77'yi değil, onu ayrıştırın.
- Parça işlemeyi kaldırın: `chunkOrder` / `isLastChunk`, Meta AI streaming alanları değildir (6.2).
- Hatch `ProtocolMessage.aiMetadataOperation` (31), JSON-istek kanalıdır; düz sohbet yanıtlarının onu kullandığı gösterilmemiştir.

### 9.4 Sohbet context'i

`BotMetadata.aiConversationContext` (20) mevcuttur. Sunucunun yanıtlarda güncellenmiş durum döndürdüğü ve bunun geri yankılanması gerektiği **inferred**'dir (alan adından ve 2.26.26.4 raporundan); doğrulanmamıştır.

---

## 11. Akışlar

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

## 12. 2.26.26.4'e göre değişiklikler

| Öğe | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | Legacy, flag 25119 | Mevcut değil. 25119 sadece flag tablolarında, okuyucu yok |
| JID'ler 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 `bot` sunucusudur (`C24770wv`); 165332417282214 `lid`'dir (`C14080dr`) |
| Yeni JID sabitleri | listelenmedi | `1807055946647699` (CoEx v2 bot-zarfı / cihaz-kümesi hedefi), `2942131436135992` (varsayılan Meta AI profil JID'i, bot-JID testi `A07`), `867051314767696555` (ikinci `A07` üyesi, amaç unknown), `17015557208` (Meta AI'nın PN'si, `A04`) |
| `$1` eki | Routing JID'inde, `C1A2.A00/A01` | JID'de değil; persona ID string'ine eklenmiş (`C24121Ab2`, `C223219iv`) |
| Routing dönüşümü | `$1` ekleme | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`, PN → FBID tablosu üzerinden bot |
| Flag adları 25119/26189/27083 | `ai_*` flag adları | String'ler feature-list girdileridir (`C25056AqU`); 26190 = Hatch profil JSON'u; 37227/37852/37054, enum değerlerine 76 / 77 / 79 gater |
| `richResponseMessage` | Alan 77 | Alan 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | "WebMessageInfo"'da 67 / 100 / 104 | `Message`'da 67 / 100 / 104; ayrıca 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` hiç yazılmamış |
| BotMetadata konumu | "mesaja gömülü" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | Profil persona string'i, örn. `1807055946647697$1`; `meta_ai` bir bot-tipi etiketi |
| Plugin tipleri | 8, 9, 15 | Aynı, enum'un 18 değeri var (17'ye kadar) |
| Action enum'u | Değer enum'u 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| Hatch JSON zarfı | üst-seviye `method`, `params` | `payload` altında nested; `accepts_encoding` ekler |
| Hatch taşıyıcısı | Standart mesaj, sınıf `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; `bizAiMetadataSync`'i (2) ekler |
| Bot imza doğrulaması | belgelenmedi | Yeni: `BotMetadata.verificationMetadata` (27), EdDSA + X.509 sertifika zinciri (içerik, telefon numarası) üzerinde; canlı test edildi, canlı gönderene değil telefon numarasına bağlanır (bölüm 9) |
| Bekleyen map'ler | Bir (`A02`) | İki: `A04` continuation'lar, `A03` `GuR` parça callback'leri |
| Streaming alanları | Bir Meta AI parça tablosu | `chunkOrder` (geçmiş senkronizasyonu), `isLastChunk` (TEE mesajı), `streamingSidecar` (medya); `clientStreaming`/`serverStreaming` bulunamadı |
| Profil senkronizasyon aralığı | "her ~1 dakikada" | 1 dakika bir WorkManager backoff'u, bir periyot değil |
| `MetaAiMemoryStore` | Mevcut | İsimle bulunamadı; tablo `meta_ai_memory` (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) bulundu |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Mevcut | Mevcut |
| Yazıyor göstergesi (chatstate'ler) | Bulundu | Bulundu: çıkış `<chatstate><composing/></chatstate>`, bir bot bahsedildiğinde `<bot jid/>` ile (`C199098dN.A01`); gelen `composing`/`paused`, genel handler `C40511kx` üzerinden, bot-özgü bir dal yok |
| Capability reklamı | belgelenmedi | Hatch için `BotMetadata.capabilityMetadata` (13) + `timezone` (8); flag 37227 / 37852 / 37054, enum değerlerine 76 / 77 / 79 eşlenir |
| Hatch istek örnekleri | belgelenmedi | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
