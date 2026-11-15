<!-- src-sha1: 900bf74a45a7fabc6e7b8c42ef4df8074e676084 -->
# WhatsApp Gruplar & Topluluklar — Full RE Report
**Sürüm:** 2.26.41.6 (üyelik onayı/katılma onayı wire yüzeyi ek olarak 2.26.45.10 üzerinde doğrulandı, satır içinde belirtildi) | **Tarih:** 2026-11-15
**Kapsam:** Grup ve topluluk yapısal modeli (ana grup, bağlı alt gruplar, varsayılan alt grup, genel sohbet), JID adresleme, eski `w:g2`/`w:gp2` wire yüzeyi, `whatsapp-android-mex` grup/topluluk GraphQL operasyon kataloğu, oluşturma/davet/yönetici-işlemi akışları, davet linkleri ve topluluk katılım onayı (`QueryMembershipApprovalRequests`, `GroupMembershipRequestUpdate`, eski `w:g2` fallback'i ve inferred `JoinMembershipForm` submit operasyonu).

---

## 1. Nedir

Bir WhatsApp **topluluğu** ayrı, adreslenebilir bir varlık değildir. Bir dizi **bağlı alt grup** için **ana grup** rolünü üstlenen bir **gruptur** — aynı JID alanı, aynı `<group>` node parser'ı, aynı `wa_group_admin_settings` tablosu. Bu rapor, başka yerlerde dağınık halde bulunan grup/topluluk modelini bir araya getirir: [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2 (sınıflandırma, adresleme), [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) (DB tabloları), [WA_REPORTING.md](WA_REPORTING.md) (`w:g2` yöneticiye-bildirme yüzeyi) ve [WA_POLLS.md](WA_POLLS.md) (varsayılan-alt-grup anket varyantı), ayrıca grup/topluluk MEX operasyon kataloğunu ve 2.26.45.10 topluluk katılım-onayı bulgusunu ekler.

### 1.1 Varlıklar

| Varlık | Adresleme | İlişki | Kademe |
|--------|-----------|----------|------|
| Grup | kendi `@g.us` JID'i | — | found |
| Topluluk | bir grupla **aynı** `@g.us` JID alanı; sınıflandırılmış, ayrı tiplendirilmemiş | ana rol üstlenen bir gruptur | found |
| Ana grup | `<group>` node tipi **1** (`parent` alt öğesi mevcut) | bir topluluğun tepesi | found |
| Bağlı alt grup | `<group>` node tipi **2** (`linked_parent jid` alt öğesi) | `linked_parent jid` ana grubun JID'ine işaret eder | found |
| Varsayılan alt grup | `<group>` node tipi **3** (`default_sub_group` alt öğesi) | topluluğun otomatik oluşturulan alt grubu; yerel olarak `group_type` **3**, ayrıca `pollCreationMessageV2` için tetikleyici (WA_POLLS §1) | found |
| Genel sohbet | `<group>` node tipi **6** (`general_chat` alt öğesi) | topluluk-çapında duyuru-tarzı sohbet | found |
| Normal grup | `<group>` node tipi **0** | topluluk ilişkisi yok | found |

Sınıflandırma ve ana-JID çıkarımı: `C23201A1a.A01` (yukarıdaki tip 0/1/2/3/6), `C23201A1a.A03` (ana JID'i `linked_parent jid`'den okur) — her ikisi de [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.3'te `found`, burada yeniden türetilmeden tekrar referans verilmiştir. Bir alt grup için `membership_approval_mode`, varsayılan olarak ana gruptan gelir: `parent/default_membership_approval_mode="request_required"`.

---

## 2. Adresleme ve katılımcı modeli

[WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.1–2.2'den kısaltılmıştır (tam detay orada; grup-geçmişine özel alanlar burada atlanmıştır):

- `<group>` node'u, eski yol `C23201A1a.A0C` (grup bildirimleriyle paylaşılır); bir MEX/SMAX ikizi mevcut (`AbstractC23204A1d`, `AN6`, `C23690AKd`).
- Temel attribute'lar: `id`, `creation`, `subject`, `s_t`/`s_o`/`s_o_pn`, `creator`/`creator_pn` (`_pn` ikizleri, bir LID'in yanında telefon JID'ini taşır).
- `addressing_mode` (`lid` / `pn`) — `wa_group_admin_settings.addressing_mode`'da saklanır; `pn` dışındaki her şey `lid` olarak okunur.
- `<participant jid lid phone_number type display_name username join_time group_history_sent>` (`C23201A1a.A05`, `C23205A1e.A0J`). `type`, yönetici statüsünün arkasındaki grup-başına rol attribute'udur; `addressing_mode`'a bağlı olarak `jid`/`lid`/`phone_number` iki adres biçimini taşır.

İstemcinin hiçbir yerinde ayrı bir `community_jid` veya `newsletter_jid` tarzı bir key yoktur — aşağıdaki §11.3'te güncel kod kanıtıyla doğrulanmıştır, §1'deki "topluluk bir gruptur" modeliyle tutarlıdır.

---

## 3. Eski wire protokolü (`w:g2` / `w:gp2`)

MEX öncesi grup operasyonları halen `w:g2` namespace'i altında binary XMPP IQ'ları olarak çalışır; `w:gp2`, `notification` push-stanza varyantlarından biri olarak listelenir (`Protocols/xml-stanzas`, `Protocols/xmpp-namespaces-android` namespace envanterleri, `found`). Somut, yapısal olarak geri kazanılmış örnek (`found`, `WASmaxGroupsGetGroupInfoRPC`):

```
iq[id=<stanzaId>, to=<groupJid>, type="get", xmlns="w:g2"]
  query[request=<string>, phash=<string?>]
    add_request[admin=<userJid>, code=<string>, expiration=<int>]   (optional, min=0 max=1)
```

Yanıt varyantları: `ClientError` / `ServerError` / `Success` (tam grup metadata'sı: katılımcılar, konu, oluşturulma, açıklama, geçicilik ayarları). Aynı namespace, bu repo içinde başka yerlerde belgelenmiş ve burada tekrar edilmeyen ilgisiz grup operasyonları da taşır:

- Yöneticiye-bildirme (`<iq to=groupJid type=set xmlns=w:g2><reports><report message_id=.../></reports></iq>`) ve yönetici-bildirim toggle'ı (`allow_admin_reports`/`not_allow_admin_reports`) — [WA_REPORTING.md](WA_REPORTING.md) §9.
- Üyelik-onay-istekleri eski fallback'i — aşağıda §11.2.

---

## 4. MEX GraphQL yüzeyi

`whatsapp-android-mex` persisted-query kataloğu, gönderilen `whatsapp-android-mex_client_persist_ids.json` asset'inde `found`. `doc_id` değerleri her APK build'inde döner (2.26.41.6 ile 2.26.45.10 arasında 95 rotasyon kaydedildi, brain'deki `Querys/graphql-diff-2.26.41.6-to-2.26.45.10.md`) — aşağıdaki tablolar 2.26.41.6 anlık görüntüsüdür.

### 4.1 Grup operasyonları (21)

| Operasyon | doc_id (2.26.41.6) | Tip |
|---|---|---|
| `AddParticipantsToGroupV2` | `28425601030437902` | Mutation |
| `AddParticipantsToGroupsV3` | `26857242513977310` | Mutation |
| `AddParticipantsToInteropGroup` | `25732168276369451` | Mutation |
| `AllowNonAdminGroupCreation` | `32024438593867697` | Query |
| `CreateGroup` | `38588807217433890` | Mutation |
| `GetPreRegGroupAddRequestsQuery` | `25018599251091282` | Query |
| `GroupMembershipRequestUpdate` | `29469157542702726` | Mutation |
| `GroupsCreateInteropGroup` | `25726817620301611` | Mutation |
| `GroupsStoreAndSendInvitesSMSMutation` | `27018112604523582` | Mutation |
| `GroupsStoreInvitesSMSMutation` | `25508574885415377` | Mutation |
| `JoinMembershipForm` | `28997137096573014` (sadece 2.26.45.10 kataloğunda yeni) | unknown |
| `LeaveInteropGroup` | `25346167795013271` | Query |
| `QueryBatchGetGroups` | `28340966318889583` | Query |
| `QueryGroupInfo` | `38342717635376065` | Query |
| `QueryGroupInfoByCode` | `27616410928049563` | Query |
| `QueryInteropGroupInfo` | `32734144032867938` | Query |
| `QueryLinkedGroupInfo` | `28221051120830416` | Query |
| `QueryMembershipApprovalRequests` | `28845604101745223` | Query |
| `QueryParticipatingGroups` | `28394594513526802` | Query |
| `QuerySuggestedGroups` | `26012055225051917` | Query |
| `SetGroupProperty` | `24688994337458819` | Mutation |
| `SetGroupResetInviteLink` | `24812851838367451` | Mutation |

### 4.2 Topluluk operasyonları (4)

| Operasyon | doc_id (2.26.41.6) | Tip |
|---|---|---|
| `QueryCommunityParticipantCount` | `31981537024824321` | Query |
| `QuerySubgroupParticipantCount` | `24784259781196779` | Query |
| `QuerySubgroups` | `25554052094203120` | Query |
| `UpdateCommunityOwner` | `24781435194845316` | Mutation |

Bu katalogda `CreateCommunity` adlı bir operasyon yoktur — topluluk oluşturmanın, `CreateGroup` + linking çağrılarını zincirleyen bir istemci-yerel sihirbaz mı, yoksa bir grubun ana grup rolüne sunucu tarafı örtük bir yükseltilmesi mi olduğu `unknown`'dır; bu geçişte çözülmemiştir.

### 4.3 APK çağrı noktalarından geri kazanılan değişkenler (`found`)

| Operasyon | Değişkenler | Çağrı noktası |
|---|---|---|
| `CreateGroup` | `participants`, `subject`, `expiration_time_in_sec`, `trigger`, `member_add_mode`, `member_link_mode`, `member_share_group_history_mode`, `username`, `user_lid` | `X/C36500G6k.java` |
| `AddParticipantsToGroupV2` | `mode`, `user_lid`, `username`, `group_id`, `participants`, `add_participants_metadata`, `input` | `X/C08600aH.java` |
| `AddParticipantsToGroupsV3` | `mode`, `group_ids`, `participants`, `tctoken`, `privacy_token`, `add_participants_metadata` | `X/RunnableC24380AnV.java` |
| `QueryGroupInfo` | `group_jid`, `query_context`, `input` | `X/C08630aK.java` |
| `QueryGroupInfoByCode` | `invite_code`, `query_context`, `get`, `input` | `X/C08600aH.java` |
| `QueryLinkedGroupInfo` | `group_jid`, `sub_group_jid_hint`, `query_context`, `input` | `X/JOF.java` |
| `QueryBatchGetGroups` | `group_jid`, `query_context`, `groups`, `request_context` | `X/FGG.java` |
| `QueryParticipatingGroups` | `input` | `X/C16710ou.java` |
| `SetGroupProperty` | §9'a bakın | `X/A18.java`, `X/A19.java` |
| `SetGroupResetInviteLink` | `group_id`, `query_context`, `group_input`, `group_jid`, `max_use`, `seconds_for_expiry` | `X/C54392a5.java` |
| `AllowNonAdminGroupCreation` | `allow_non_admin_sub_group_creation` (bool) | `com/whatsapp/community/mex/AllowNonAdminSubGroupCreationGraphQlHandler.java` |
| `QuerySuggestedGroups` | `group_input` | `com/whatsapp/community/mex/GetSuggestedGroupsGraphQlHandler.java` |
| `QuerySubgroups` | `group_input` | `com/whatsapp/community/mex/GetSubgroupsGraphQlHandler.java` |
| `UpdateCommunityOwner` | `new_role`, `group_id`, `role_updates`, `user_jid` | `com/whatsapp/community/mex/TransferCommunityOwnershipGraphQlHandler.java` |
| `GroupsStoreAndSendInvitesSMSMutation` | `server_sent_sms`, `participants`, `entry_point`, `is_bundle_invite`, `participant`, `group_jid` | `com/whatsapp/invite/api/ServerSentGroupInviteMutationHelper.java`, `com/whatsapp/invite/ui/SMSPreviewGroupInviteBottomSheetFragment.java` |
| `GroupsStoreInvitesSMSMutation` | `partcipants` (sic), `group_jid` | `X/C67052zD.java` |
| `AddParticipantsToInteropGroup` | `gid`, `participants`, `jid`, `input` | `X/C3ZT.java` |
| `QueryInteropGroupInfo` | `gid`, `group_input` | `X/C3ZT.java` |

Kalanlar (`GetPreRegGroupAddRequestsQuery`, `GroupsCreateInteropGroup`, `LeaveInteropGroup`, `QueryCommunityParticipantCount`, `QuerySubgroupParticipantCount`) için statik bir çağrı noktası geri kazanılmamıştır: `unknown`, büyük olasılıkla `{}` gönderiyorlar.

---

## 5. Grup oluşturma

`CreateGroup` (§4.3), oluşturma anında `member_add_mode`, `member_link_mode`, `member_share_group_history_mode`'u ayarlar — bunlar `SetGroupProperty`'nin daha sonra düzenlediği aynı üç yönetici özelliğidir (§9). `trigger`, string tipinde bir giriş-noktası etiketidir (`found`, tam değer kümesi bu geçişte sayılmamıştır).

---

## 6. Davet linkleri ve davetler

| Öğe | Detay | Kademe |
|------|--------|------|
| Davet linki sıfırlama/oluşturma | `SetGroupResetInviteLink`: `group_id`, `group_jid`, `max_use`, `seconds_for_expiry` | found |
| Davet kodunu çözme | `QueryGroupInfoByCode`: `invite_code` -> grup bilgisi | found |
| SMS daveti (bundle) | `GroupsStoreAndSendInvitesSMSMutation`: `participants`, `entry_point`, `is_bundle_invite`, `server_sent_sms` | found |
| SMS daveti (sadece kayıt) | `GroupsStoreInvitesSMSMutation`: `group_jid`, participants | found |
| İzin ver/engelle listesi | DB `wa_group_add_allow_list`, `wa_group_add_black_list` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) | found |
| WhatsApp dışı davetler | DB `group_non_wa_invites` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) | found |

### 6.1 `groupInviteMessage` wire formu

`Message.groupInviteMessage`, alan **28**, nested tip `Message.GroupInviteMessage` (WAProto.proto'da found):

| Alan | # | Tip |
|-------|---|------|
| `groupJid` | 1 | string |
| `inviteCode` | 2 | string |
| `inviteExpiration` | 3 | int64 |
| `groupName` | 4 | string |
| `jpegThumbnail` | 5 | bytes |
| `caption` | 6 | string |
| `contextInfo` | 7 | ContextInfo |
| `groupType` | 8 | enum `GroupType` |

`GroupType`: `DEFAULT` = 0, `PARENT` = 1 — davet mesajının kendisi, düz bir grup davetini bir topluluk (ana-grup) davetinden ayırt eder, §1'deki "topluluk sınıflandırılmış bir gruptur" modeliyle tutarlıdır. Aynı proto dosyasında, bununla ilgisiz ikinci bir üst-seviye `GroupInviteMessage` tipi mevcuttur; bu tablo sadece alan 28'in kullandığı nested `Message.GroupInviteMessage`'ı kapsar.

---

## 7. Katılımcılar: ekleme, önerme, sayma

| Operasyon | Amaç (isim + değişkenlerden inferred) |
|---|---|
| `AddParticipantsToGroupV2` / `V3` | bir veya daha fazla gruba bir veya daha fazla kullanıcı ekleme |
| `QueryParticipatingGroups` | çağıranın içinde olduğu grupları listeleme |
| `QueryBatchGetGroups` | bir grup JID kümesi için toplu metadata çekme |
| `QuerySuggestedGroups` | topluluk/grup önerileri yüzeyi; DB `member_suggested_groups_v2` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) |
| `QuerySubgroups` / `QuerySubgroupParticipantCount` / `QueryCommunityParticipantCount` | bağlı alt gruplar üzerinden topluluk seviyesi sayımlar |

`<participant type=...>` attribute'u (§2) grup-başına yönetici/rol flag'ini taşır ve `group_participant_user.rank` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §3.6) bunu yerel olarak kalıcı hale getirir — yani yönetici rank'ı bir kavram olarak var, ama bu katalogda açık bir promote/demote veya katılımcı-kaldırma MEX operasyonu bulunmamıştır (yukarıdaki 21/4 grup/topluluk operasyonu 2.26.41.6 için eksiksizdir). **Unknown**: bu yolun halen salt eski bir `w:g2` katılımcı-listesi IQ'su olarak mı çalıştığı (`AddParticipantsToGroupV2`'nin kendi isminin bir V1 öncülü ima etmesiyle tutarlı), yoksa `group`/`community` isim-alt-dizgi gruplamalarının dışında bir operasyon adı altında mı olduğu; bu geçişte çözülmemiştir.

---

## 8. Interop grupları (kısaca)

`AddParticipantsToInteropGroup`, `GroupsCreateInteropGroup`, `QueryInteropGroupInfo`, `LeaveInteropGroup` — üçüncü-taraf-köprülenmiş ("interop") gruplar için paralel, küçük bir operasyon kümesi. Burada sadece listelenmekle sınırlı kapsam dışı; bunların bağlandığı interop onay/köprü modeli için [WA_INTEROP.md](WA_INTEROP.md)'a bakın.

---

## 9. Yönetici ayarları — `SetGroupProperty`

**Değişkenler** (`found`, `X/A18.java`, `X/A19.java`):

| Alan | Tip | Anlam | Kademe |
|-------|------|---------|------|
| `group_id` | str | hedef grup | found |
| `subject` | str | grup adı | found |
| `description` | str | grup açıklaması | found |
| `previous_id` | str | optimistic-concurrency / önceki-değer işareti (inferred) | inferred |
| `member_add_mode` | str | üye ekleme yetkisi (`all_member_add` / diğer, eski `<member_add_mode>` alt öğesini yansıtır, [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.1) | found |
| `member_link_mode` | str | davet-linki izin modu (isimden inferred) | inferred |
| `member_share_group_history_mode` | str | `ADMIN_SHARE` / `ALL_MEMBER_SHARE`, tam enum ve sistem-mesajı eşlemesi [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.4'te — burada tekrarlanmamıştır | found |
| `membership_approval_mode_enabled` | bool | bu grup için katılma-isteği gating'ini açar/kapatır — bkz §11 | found |
| `limit_sharing`, `limit_sharing_enabled`, `limit_sharing_trigger` | str/bool/str | bu grup için iletme-sınırı toggle'ı (inferred: "limit sharing" iletme kısıtlaması) | inferred |
| `input` | str | wrapper/context nesnesi (şekli çözülmemiş) | unknown |

Sunucu tarafı bildirim karşılığı ve tam `wa_group_admin_settings` kolon listesi (`restrict_mode`, `announcement_group`, `no_frequently_forwarded`, `ephemeral_duration`, `require_membership_approval`, `addressing_mode`, `allow_member_labels`, …) [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4'tedir — çapraz referans verilmiş, tekrarlanmamıştır.

---

## 10. Topluluğa özgü yapı

| Öğe | Detay | Kademe |
|------|--------|------|
| Alt grup sayma | `QuerySubgroups` (`group_input`) | found |
| Alt grup/topluluk sayımları | `QuerySubgroupParticipantCount`, `QueryCommunityParticipantCount` | found (operasyonlar var), unknown (değişkenler) |
| Bağlı-grup araması | `QueryLinkedGroupInfo` (`group_jid`, `sub_group_jid_hint`) — bir alt grubu ana grubu üzerinden çözer | found |
| Sahiplik devri | `UpdateCommunityOwner` (`new_role`, `group_id`, `role_updates`, `user_jid`) | found |
| Yönetici-olmayan alt grup oluşturma toggle'ı | `AllowNonAdminGroupCreation` (`allow_non_admin_sub_group_creation` bool) | found |
| Varsayılan-alt-grup anket varyantı | `pollCreationMessageV2`, sohbet bir varsayılan alt grup olduğunda (`group_type == 3`) kullanılan anket slotudur — [WA_POLLS.md](WA_POLLS.md) §1, §3.3 | found |
| DB tabloları | `subgroup_info`, `community_settings`, `group_relationship` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4) | found |

---

## 11. Üyelik onayı ve topluluk katılım onayı

### 11.1 Gruplar: katılma-isteği gating

`membership_approval_mode_enabled` (`SetGroupProperty`, §9), bir grup için yönetici-gated katılımı açar; `wa_group_admin_settings.require_membership_approval` kalıcı hale getirilen flag'tir ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4). Bir topluluğun **alt grubu** için varsayılan değer bunun yerine ana gruptan gelir: `parent/default_membership_approval_mode="request_required"` (§1.1, `C23201A1a`). Bekleyen-istek depolaması kimin onaylayabileceğine göre bölünmüştür: `group_membership_approval_requests` (yönetici-görünür) ve `non_admin_group_membership_approval_requests`; `group_membership_form_questions`, bir katılımcının cevaplaması gereken yönetici-tarafından-yapılandırılmış soruları tutar, `group_membership_count` ise toplam sayıları takip eder (hepsi `found`, [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4). `group_membership_form_questions`, bir üyelik-formu akışının var olduğunun somut istemci-tarafı kanıtıdır — aşağıdaki `JoinMembershipForm` ile doğrudan ilişkilidir.

### 11.2 Wire yüzeyi: MEX ana yolu + eski fallback

`com/whatsapp/group/data/GroupFetchAllMembershipApprovalRequestsJob` (`found`, 2.26.45.10 smali), bir `groupJidRawString` için "yönetici onayını bekleyen katılma isteklerini çek" işlevini uygular, çalışma zamanında `LX/00E;->A0G(LX/00E;LX/00g;)Z` ile flag id `LX/4WC;->A04`'e karşı gated edilir (`LX/00U;->A03(0x10d4)` üzerinden okunur):

| Yol | Koşul | Mekanizma |
|------|-----------|-----------|
| MEX | flag açık | `query_context="INTERACTIVE"` ve hedef `GroupJid` ile `GraphQlCallInput`, `whatsapp-android-mex` namespace'inde operasyon **`QueryMembershipApprovalRequests`** |
| Eski binary IQ | flag kapalı (`LX/0RD` fallback) | `<iq type="get" xmlns="w:g2" to="<group_jid>" id="..."><membership_approval_requests/></iq>` |

`QueryMembershipApprovalRequests` için `doc_id`, build'ler arasında normal şekilde döner: `28845604101745223` (2.26.41.6) → `28584744077887639` (2.26.45.10). Yönetici onay/reddetme mutation'ı, `GroupMembershipRequestUpdate`, karşılığıdır (`29469157542702726` → `28746221238391491`, aynı normal-rotasyon deseni); bu geçişte çağrı noktası izlenmemiştir, ama katalogdaki (§4.1) tek yönetici-tarafı grup-üyeliği mutation'ıdır.

`JoinMembershipForm` (doc_id `28997137096573014`), 2.26.45.10 kataloğuna gerçekten yenidir — 2.26.41.6'da yoktur, mevcut bir operasyonun rotasyonu değildir. İsmi, `group_membership_form_questions` tablosuyla (§11.1) birleştiğinde, bunu "yöneticinin üyelik-formu sorularını cevapla ve katılma talep et" submit-tarafı mutation'ı için en iyi adayı yapar — ama bu geçişte çağrı noktası izlenmemiştir. Tam rolü ve şeması için **inferred**, found değil.

### 11.3 Özel olarak topluluk katılım onayı (2.26.45.10, found)

Yeni paket `com/whatsapp/community/product/joinapproval/`, bir sınıf: `CommunityJoinApprovalNuxBottomSheet` — yerel bir UI açıklama sheet'i ("bu topluluğa katılmak için yönetici onayına ihtiyacınız olacak"), kendisi bir ağ çağrısı noktası değildir.

- `"group_jid"` (topluluğun kendi JID'i, ham bir grup JID string'i olarak okunur) ve `"community_name"` bundle argümanlarıyla `LX/3IN;->C3f` tarafından oluşturulur.
- Birincil-buton handler'ı `LX/3Ge;->C3f`, `pswitch_28`: saklanan `GroupJid`'i okur, `LX/122;->A01(Context, GroupJid, Integer)Intent`'i çağırır, `LX/0KC;->A02` üzerinden başlatır, sheet'i kapatır.

**Önemli bulgu:** topluluk `group_jid` ile adreslenir, ayrı bir `community_jid`/`newsletter_jid` tarzı key ile değil — bu, sadece isimlendirme kuralının değil, §1/§2'deki "topluluk bir gruptur" modelinin doğrudan kod doğrulamasıdır. Katalogda hiçbir yerde `Community*ApprovalRequests` tarzı bir operasyon yoktur; bir topluluğun bekleyen katılma istekleri, düz bir grubun kullandığı tam olarak aynı `QueryMembershipApprovalRequests` / `GroupMembershipRequestUpdate` MEX çiftinde (ve aynı eski `w:g2` fallback'inde) gezinir, çünkü üyelik-onayı job'ı yalnızca bir `groupJidRawString` görür.

### 11.4 Hüküm

| İddia | Kademe |
|-------|------|
| Topluluk `group_jid` ile adreslenir, gruplarla aynı kod yolu | found |
| Bekleyen istekleri listeleme: MEX `QueryMembershipApprovalRequests` | found |
| Onay/ret: MEX `GroupMembershipRequestUpdate` | found (operasyon var, kataloglanmış); çağrı noktası izlenmemiş |
| Eski fallback: `<iq xmlns="w:g2"><membership_approval_requests/></iq>` | found |
| MEX ile eski arasında seçim yapan feature gate | found (flag id, mevcut rollout durumu değil) |
| Submit tarafı `JoinMembershipForm`'dur | inferred |
| Tam `JoinMembershipForm` şeması/değişkenleri | unknown |
| Sunucu tarafı kabul/doğrulama mantığı | unknown (sadece statik analiz, traffic capture yok) |

---

## 12. Yerel depolama çapraz referansı

Tam kolon listeleri [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)'dadır; bu bir pointer tablosudur, kopya değildir:

| Tablo | Rol |
|-------|-------|
| `wa_group_admin_settings` | grup-başına yönetici ayarları (adresleme modu, geçmiş, onay, iletme sınırı, ...) |
| `group_participant_user`, `group_past_participant_user`, `group_participant_device` | mevcut/geçmiş katılımcılar, rank, cihaz-başına sender-key durumu |
| `group_membership_approval_requests`, `non_admin_group_membership_approval_requests` | bekleyen katılma istekleri, onaylayan görünürlüğüne göre bölünmüş |
| `group_membership_form_questions` | yönetici-tarafından-yapılandırılmış üyelik-formu soruları (§11.1, §11.2) |
| `group_membership_count` | toplam sayılar |
| `subgroup_info`, `community_settings`, `group_relationship` | topluluk/alt-grup yapısı |
| `member_suggested_groups_v2` | önerilen-gruplar yüzeyi |
| `group_suspension_appeal` | grup-seviyesi askıya alma itirazı durumu |
| `group_non_wa_invites` | WhatsApp dışı kişilere davetler |
| `group_root_key_mapping` | sender-key root eşlemesi |

---

## 13. Baileys / velowa uygulama notları

Tüm grup/topluluk MEX operasyonları, bu repodaki diğer her persisted query ile aynı `w:mex` IQ zarfını kullanır (`Protocols/mex-graphql`, `graphql-invocation-guide.md`):

```js
const res = await sock.query({
  tag: 'iq', attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '<doc_id>' },
    content: Buffer.from(JSON.stringify({ queryId: '<doc_id>', variables })) }],
})
```

Eski grup metadata/katılımcı çekme işlemi `w:g2` üzerinde kalır ve çoğu WA Web kütüphanesi tarafından halihazırda uygulanmıştır (`groupMetadata`, `groupQuery` tarzı çağrılar); üyelik onayı için §11.2'deki IQ'nun açıkça eklenmesi gerekir — çoğu kütüphane bunu sormaz.

| Neden başarısız olur | Düzeltme |
|---------------|-----|
| Herhangi bir grup/topluluk operasyonu için sabitlenmiş `doc_id` | `doc_id` her APK build'inde döner (doğrulandı: sadece 2.26.38.10 ile 2.26.41.6 arasında 4 grup operasyonu döndü); güncel bir katalog çıkarımından yenileyin, sabitlemeyin |
| Üyelik-onayının her zaman eski `w:g2` olduğunu varsaymak | Feature-flagged'dir; bir hesap için flag sunucu tarafında açıldığında, bekleyen istekler sadece MEX `QueryMembershipApprovalRequests` üzerinden görünür hale gelir — her iki yolu da uygulayın veya ileriye dönük sadece MEX kullanın |
| Bir topluluğun kendi JID tipine sahip olduğunu varsaymak | Sahip değildir — herhangi bir grup operasyonunda olduğu gibi ana grubun kendi `@g.us` JID'i ile adresleyin |
| Gated bir katılma isteğini programatik olarak göndermeye çalışmak | `JoinMembershipForm`'un şeması çözülmemiştir (sadece inferred rol); henüz güvenle uygulanabilir değil |

---

## 14. Ayırt edilmesi gereken noktalar

- **Topluluk sınıflandırılmış bir gruptur, ayrı bir varlık değildir.** `community_jid` yoktur; topluluğun kendi JID'i, node tipi 1 (`parent`) olan bir grup JID'idir.
- **`member_share_group_history_mode`** (yeni katılanlarla son geçmişi kimin paylaşabileceği, [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.4), **`membership_approval_mode_enabled`** (katılma-isteği gating, §9/§11) ile ilgisizdir — her ikisi de `SetGroupProperty` alanlarıdır ama farklı özellikleri kontrol eder.
- **`w:g2` yöneticiye-bildirme** ([WA_REPORTING.md](WA_REPORTING.md) §9) ile **`w:g2` üyelik-onay-istekleri fallback'i** (§11.2) bir namespace paylaşır ama ilgisiz alt node'lardır (`reports`/`allow_admin_reports` vs. `membership_approval_requests`).
- **`JoinMembershipForm`**, inferred bir submit-tarafı operasyonudur, doğrulanmış değil — found olarak ele almayın.
- **Promote/demote/katılımcı-kaldırma** için bu katalogda tanımlanmış bir MEX operasyonu yoktur; çözülmemiş olarak ele alın, "sadece eski `w:g2` üzerinden çalışır" olarak değil (varsayım, kanıt değil).

---

## 15. Topluluk katılım-onayı akışı (şu an kanıtlandığı haliyle)

```
[Member]                         [Client]                              [Server / whatsapp-android-mex]
   │ taps "Request to join"         │                                        │
   ├────────────────────────────────▶ CommunityJoinApprovalNuxBottomSheet    │
   │                                 │  (local explainer, group_jid+name)    │
   │ taps primary button             │                                        │
   ├────────────────────────────────▶ LX/3Ge;->C3f pswitch_28                │
   │                                 │  -> LX/122;->A01(ctx, GroupJid, int)  │
   │                                 │     Intent into group/community flow  │
   │                                 │  (submit side, inferred)              │
   │                                 ├───────────────────────────────────────▶ JoinMembershipForm (inferred)
   │                                 │                                        │
[Admin]                           [Client]                                 │
   │ opens pending-requests screen   │                                        │
   ├────────────────────────────────▶ GroupFetchAllMembershipApprovalRequestsJob
   │                                 │  flag on  ─▶ QueryMembershipApprovalRequests (MEX)
   │                                 │  flag off ─▶ <iq xmlns="w:g2"><membership_approval_requests/></iq>
   │                                 │                                        │
   │ approves / denies               │                                        │
   ├────────────────────────────────▶ GroupMembershipRequestUpdate (MEX) ────▶ server
```

---

## 16. Açık noktalar / dikkat edilmesi gerekenler

- `JoinMembershipForm`'un değişkenleri/yanıt şekli: unknown, çağrı-noktası-izlenmemiş.
- `GroupMembershipRequestUpdate`'in kendi değişkenleri: bu geçişte bir çağrı noktasından geri kazanılmamıştır (operasyon sadece var olduğu onaylanmıştır).
- Promote/demote/katılımcı-kaldırma: tanımlanmış bir MEX operasyonu yok; sadece-eski mi yoksa katalogda eksik mi olduğu çözülmemiştir.
- `CreateCommunity`: böyle bir MEX operasyonu yoktur; topluluk oluşturma yolu çözülmemiştir (`CreateGroup` + linking'i zincirleyen istemci sihirbazı çalışan tahmindir, doğrulanmamıştır).
- §11'deki DB tablo varlığı dışındaki tüm iddialar statik analizdir; burada hiçbir şey traffic-test edilmemiştir (evidence contract'a göre — bu rapor için canlı sunucu etkileşimi gerçekleştirilmemiştir).
