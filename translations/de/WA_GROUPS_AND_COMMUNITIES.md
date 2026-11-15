<!-- src-sha1: 900bf74a45a7fabc6e7b8c42ef4df8074e676084 -->
# WhatsApp Gruppen & Communities — Full RE Report
**Version:** 2.26.41.6 (membership-approval/join-approval wire surface additionally verified on 2.26.45.10, noted inline) | **Datum:** 2026-11-15
**Umfang:** Group vs. community structural model (parent group, linked sub-groups, default sub-group, general chat), JID addressing, legacy `w:g2`/`w:gp2` wire surface, the `whatsapp-android-mex` group/community GraphQL operation catalog, creation/invite/admin-action flows, invite links, and community join approval (`QueryMembershipApprovalRequests`, `GroupMembershipRequestUpdate`, the legacy `w:g2` fallback, and the inferred `JoinMembershipForm` submit op).

---

## 1. Was es ist

Eine WhatsApp-**Community** ist keine eigenständig adressierbare Entität. Es ist eine **Gruppe** — gleicher JID-Raum, gleicher `<group>`-Node-Parser, gleiche `wa_group_admin_settings`-Tabelle —, die die Rolle einer **Parent-Gruppe** für eine Menge **verlinkter Sub-Gruppen** einnimmt. Dieser Report führt das Gruppen-/Community-Modell zusammen, das sonst über [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2 (Klassifizierung, Adressierung), [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) (DB-Tabellen), [WA_REPORTING.md](WA_REPORTING.md) (die `w:g2` Report-to-Admin-Surface) und [WA_POLLS.md](WA_POLLS.md) (Default-Subgroup-Poll-Variante) verteilt ist, und ergänzt den Gruppen-/Community-MEX-Operationskatalog sowie den 2.26.45.10-Fund zur Community-Join-Approval.

### 1.1 Entitäten

| Entität | Adressierung | Beziehung | Tier |
|--------|-----------|----------|------|
| Gruppe | eigene `@g.us`-JID | — | found |
| Community | **dieselbe** `@g.us`-JID-Namensraum wie eine Gruppe; klassifiziert, nicht separat typisiert | ist eine Gruppe, die als Parent agiert | found |
| Parent-Gruppe | `<group>`-Node-Typ **1** (Kindelement `parent` vorhanden) | Spitze einer Community | found |
| Verlinkte Sub-Gruppe | `<group>`-Node-Typ **2** (Kindelement `linked_parent jid`) | `linked_parent jid` zeigt auf die JID der Parent-Gruppe | found |
| Default-Sub-Gruppe | `<group>`-Node-Typ **3** (Kindelement `default_sub_group`) | automatisch erzeugte Sub-Gruppe einer Community; lokal `group_type` **3**, zugleich Trigger für `pollCreationMessageV2` (WA_POLLS §1) | found |
| General Chat | `<group>`-Node-Typ **6** (Kindelement `general_chat`) | Community-weiter Announcement-artiger Chat | found |
| Normale Gruppe | `<group>`-Node-Typ **0** | keine Community-Beziehung | found |

Klassifizierung und Parent-JID-Extraktion: `C23201A1a.A01` (Typen 0/1/2/3/6 oben), `C23201A1a.A03` (liest die Parent-JID aus `linked_parent jid`) — beides `found` in [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.3, hier zitiert statt neu abgeleitet. `membership_approval_mode` einer Sub-Gruppe übernimmt standardmäßig `parent/default_membership_approval_mode="request_required"`.

---

## 2. Adressierungs- und Teilnehmermodell

Verdichtet aus [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.1–2.2 (volles Detail dort; group-history-spezifische Felder hier ausgelassen):

- `<group>`-Node, legacy Pfad `C23201A1a.A0C` (gemeinsam mit Group-Notifications genutzt); ein MEX/SMAX-Pendant existiert (`AbstractC23204A1d`, `AN6`, `C23690AKd`).
- Kern-Attribute: `id`, `creation`, `subject`, `s_t`/`s_o`/`s_o_pn`, `creator`/`creator_pn` (die `_pn`-Pendants führen die Phone-JID neben einer LID mit).
- `addressing_mode` (`lid` / `pn`) — gespeichert in `wa_group_admin_settings.addressing_mode`; alles außer `pn` wird als `lid` gelesen.
- `<participant jid lid phone_number type display_name username join_time group_history_sent>` (`C23201A1a.A05`, `C23205A1e.A0J`). `type` ist das pro Gruppe gültige Rollen-Attribut hinter dem Admin-Status; `jid`/`lid`/`phone_number` führen die beiden Adressformen je nach `addressing_mode`.

Es existiert nirgends im Client ein separater `community_jid`- oder `newsletter_jid`-artiger Schlüssel — bestätigt mit frischer Code-Evidenz in §11.3 unten, konsistent mit dem "Community ist eine Gruppe"-Modell aus §1.

---

## 3. Legacy-Wire-Protokoll (`w:g2` / `w:gp2`)

Pre-MEX-Gruppenoperationen laufen weiterhin als binäre XMPP-IQs unter dem Namespace `w:g2`; `w:gp2` ist als eine der `notification`-Push-Stanza-Varianten gelistet (`Protocols/xml-stanzas`, `Protocols/xmpp-namespaces-android` Namespace-Inventare, `found`). Konkretes, strukturell rekonstruiertes Beispiel (`found`, `WASmaxGroupsGetGroupInfoRPC`):

```
iq[id=<stanzaId>, to=<groupJid>, type="get", xmlns="w:g2"]
  query[request=<string>, phash=<string?>]
    add_request[admin=<userJid>, code=<string>, expiration=<int>]   (optional, min=0 max=1)
```

Antwort-Varianten: `ClientError` / `ServerError` / `Success` (vollständige Gruppen-Metadaten: Teilnehmer, Subject, Erstellungsdatum, Beschreibung, Ephemeral-Einstellungen). Derselbe Namespace trägt weitere, unabhängige Gruppenoperationen, die anderswo in diesem Repo dokumentiert sind und hier nicht wiederholt werden:

- Report-to-Admin (`<iq to=groupJid type=set xmlns=w:g2><reports><report message_id=.../></reports></iq>`) und der Admin-Report-Toggle (`allow_admin_reports`/`not_allow_admin_reports`) — [WA_REPORTING.md](WA_REPORTING.md) §9.
- Der Legacy-Fallback für Membership-Approval-Requests — §11.2 unten.

---

## 4. MEX-GraphQL-Surface

`whatsapp-android-mex`-Persisted-Query-Katalog, `found in` dem mitgelieferten `whatsapp-android-mex_client_persist_ids.json`-Asset. `doc_id`-Werte rotieren mit jedem APK-Build (95 Rotationen zwischen 2.26.41.6 und 2.26.45.10 protokolliert, `Querys/graphql-diff-2.26.41.6-to-2.26.45.10.md` im Brain) — die Tabellen unten sind der 2.26.41.6-Snapshot.

### 4.1 Gruppenoperationen (21)

| Operation | doc_id (2.26.41.6) | Typ |
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
| `JoinMembershipForm` | `28997137096573014` (new in 2.26.45.10 catalog only) | unknown |
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

### 4.2 Community-Operationen (4)

| Operation | doc_id (2.26.41.6) | Typ |
|---|---|---|
| `QueryCommunityParticipantCount` | `31981537024824321` | Query |
| `QuerySubgroupParticipantCount` | `24784259781196779` | Query |
| `QuerySubgroups` | `25554052094203120` | Query |
| `UpdateCommunityOwner` | `24781435194845316` | Mutation |

Es existiert keine Operation mit dem Namen `CreateCommunity` in diesem Katalog — `unknown`, ob die Community-Erstellung ein rein clientseitiger Wizard ist, der `CreateGroup` + Linking-Calls verkettet, oder eine serverseitige implizite Promotion einer Gruppe zum Parent; in diesem Durchgang nicht geklärt.

### 4.3 Aus APK-Call-Sites rekonstruierte Variablen (`found`)

| Operation | Variablen | Call-Site |
|---|---|---|
| `CreateGroup` | `participants`, `subject`, `expiration_time_in_sec`, `trigger`, `member_add_mode`, `member_link_mode`, `member_share_group_history_mode`, `username`, `user_lid` | `X/C36500G6k.java` |
| `AddParticipantsToGroupV2` | `mode`, `user_lid`, `username`, `group_id`, `participants`, `add_participants_metadata`, `input` | `X/C08600aH.java` |
| `AddParticipantsToGroupsV3` | `mode`, `group_ids`, `participants`, `tctoken`, `privacy_token`, `add_participants_metadata` | `X/RunnableC24380AnV.java` |
| `QueryGroupInfo` | `group_jid`, `query_context`, `input` | `X/C08630aK.java` |
| `QueryGroupInfoByCode` | `invite_code`, `query_context`, `get`, `input` | `X/C08600aH.java` |
| `QueryLinkedGroupInfo` | `group_jid`, `sub_group_jid_hint`, `query_context`, `input` | `X/JOF.java` |
| `QueryBatchGetGroups` | `group_jid`, `query_context`, `groups`, `request_context` | `X/FGG.java` |
| `QueryParticipatingGroups` | `input` | `X/C16710ou.java` |
| `SetGroupProperty` | siehe §9 | `X/A18.java`, `X/A19.java` |
| `SetGroupResetInviteLink` | `group_id`, `query_context`, `group_input`, `group_jid`, `max_use`, `seconds_for_expiry` | `X/C54392a5.java` |
| `AllowNonAdminGroupCreation` | `allow_non_admin_sub_group_creation` (bool) | `com/whatsapp/community/mex/AllowNonAdminSubGroupCreationGraphQlHandler.java` |
| `QuerySuggestedGroups` | `group_input` | `com/whatsapp/community/mex/GetSuggestedGroupsGraphQlHandler.java` |
| `QuerySubgroups` | `group_input` | `com/whatsapp/community/mex/GetSubgroupsGraphQlHandler.java` |
| `UpdateCommunityOwner` | `new_role`, `group_id`, `role_updates`, `user_jid` | `com/whatsapp/community/mex/TransferCommunityOwnershipGraphQlHandler.java` |
| `GroupsStoreAndSendInvitesSMSMutation` | `server_sent_sms`, `participants`, `entry_point`, `is_bundle_invite`, `participant`, `group_jid` | `com/whatsapp/invite/api/ServerSentGroupInviteMutationHelper.java`, `com/whatsapp/invite/ui/SMSPreviewGroupInviteBottomSheetFragment.java` |
| `GroupsStoreInvitesSMSMutation` | `partcipants` (sic), `group_jid` | `X/C67052zD.java` |
| `AddParticipantsToInteropGroup` | `gid`, `participants`, `jid`, `input` | `X/C3ZT.java` |
| `QueryInteropGroupInfo` | `gid`, `group_input` | `X/C3ZT.java` |

Für den Rest (`GetPreRegGroupAddRequestsQuery`, `GroupsCreateInteropGroup`, `LeaveInteropGroup`, `QueryCommunityParticipantCount`, `QuerySubgroupParticipantCount`) wurde keine statische Call-Site gefunden: `unknown`, vermutlich wird `{}` gesendet.

---

## 5. Eine Gruppe erstellen

`CreateGroup` (§4.3) setzt `member_add_mode`, `member_link_mode`, `member_share_group_history_mode` bereits bei der Erstellung — dieselben drei Admin-Eigenschaften, die `SetGroupProperty` später bearbeitet (§9). `trigger` ist ein String-Tag für den Entry-Point (`found`, genaue Werte-Menge in diesem Durchgang nicht erfasst).

---

## 6. Invite-Links und Invites

| Item | Detail | Tier |
|------|--------|------|
| Invite-Link zurücksetzen/erstellen | `SetGroupResetInviteLink`: `group_id`, `group_jid`, `max_use`, `seconds_for_expiry` | found |
| Invite-Code auflösen | `QueryGroupInfoByCode`: `invite_code` -> Gruppeninfo | found |
| SMS-Invite (Bundle) | `GroupsStoreAndSendInvitesSMSMutation`: `participants`, `entry_point`, `is_bundle_invite`, `server_sent_sms` | found |
| SMS-Invite (nur Speicherung) | `GroupsStoreInvitesSMSMutation`: `group_jid`, Teilnehmer | found |
| Allow/Deny-Liste | DB `wa_group_add_allow_list`, `wa_group_add_black_list` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) | found |
| Non-WhatsApp-Invites | DB `group_non_wa_invites` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) | found |

### 6.1 `groupInviteMessage`-Wire-Form

`Message.groupInviteMessage`, Feld **28**, verschachtelter Typ `Message.GroupInviteMessage` (found in WAProto.proto):

| Feld | # | Typ |
|-------|---|------|
| `groupJid` | 1 | string |
| `inviteCode` | 2 | string |
| `inviteExpiration` | 3 | int64 |
| `groupName` | 4 | string |
| `jpegThumbnail` | 5 | bytes |
| `caption` | 6 | string |
| `contextInfo` | 7 | ContextInfo |
| `groupType` | 8 | enum `GroupType` |

`GroupType`: `DEFAULT` = 0, `PARENT` = 1 — die Invite-Message selbst unterscheidet zwischen einer reinen Gruppen-Einladung und einer Community-Einladung (Parent-Gruppe), konsistent mit dem "Community ist eine klassifizierte Gruppe"-Modell aus §1. Ein zweiter, unabhängiger Top-Level-Typ `GroupInviteMessage` existiert anderswo in derselben Proto-Datei; diese Tabelle deckt nur den verschachtelten `Message.GroupInviteMessage`-Typ ab, der von Feld 28 verwendet wird.

---

## 7. Teilnehmer: hinzufügen, vorschlagen, auflisten

| Operation | Zweck (aus Name + Variablen abgeleitet) |
|---|---|
| `AddParticipantsToGroupV2` / `V3` | fügt einen oder mehrere Nutzer zu einer oder mehreren Gruppen hinzu |
| `QueryParticipatingGroups` | listet die Gruppen auf, in denen sich der Aufrufer befindet |
| `QueryBatchGetGroups` | Batch-Metadaten-Abruf für eine Menge von Gruppen-JIDs |
| `QuerySuggestedGroups` | Community-/Gruppen-Vorschlagsoberfläche; DB `member_suggested_groups_v2` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) |
| `QuerySubgroups` / `QuerySubgroupParticipantCount` / `QueryCommunityParticipantCount` | Community-Level-Zählwerte über die verlinkten Sub-Gruppen |

Das `<participant type=...>`-Attribut (§2) führt das Admin-/Rollen-Flag pro Gruppe, und `group_participant_user.rank` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §3.6) persistiert es lokal — Admin-Rang existiert also als Konzept, aber in diesem Katalog wurde keine explizite Promote-/Demote- oder Remove-Participant-MEX-Operation gefunden (die 21/4 Gruppen-/Community-Ops oben sind für 2.26.41.6 vollständig). **Unknown**: ob dieser Pfad weiterhin rein über eine Legacy-`w:g2`-Teilnehmerlisten-IQ läuft (konsistent damit, dass der Name `AddParticipantsToGroupV2` einen V1-Vorgänger impliziert) oder unter einem Operationsnamen außerhalb der `group`-/`community`-Namenssubstring-Buckets; in diesem Durchgang nicht geklärt.

---

## 8. Interop-Gruppen (kurz)

`AddParticipantsToInteropGroup`, `GroupsCreateInteropGroup`, `QueryInteropGroupInfo`, `LeaveInteropGroup` — eine parallele, kleine Menge von Gruppenoperationen für Drittanbieter-gebrückte ("Interop")-Gruppen. Hier nur gelistet, außerhalb des Scopes; siehe [WA_INTEROP.md](WA_INTEROP.md) für das Interop-Consent-/Bridge-Modell, in das sie eingebunden sind.

---

## 9. Admin-Einstellungen — `SetGroupProperty`

**Variablen** (`found`, `X/A18.java`, `X/A19.java`):

| Feld | Typ | Bedeutung | Tier |
|-------|------|---------|------|
| `group_id` | str | Zielgruppe | found |
| `subject` | str | Gruppenname | found |
| `description` | str | Gruppenbeschreibung | found |
| `previous_id` | str | Optimistic-Concurrency-/Vorwert-Marker (inferred) | inferred |
| `member_add_mode` | str | wer Mitglieder hinzufügen darf (`all_member_add` / andere, spiegelt das Legacy-Kindelement `<member_add_mode>`, [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.1) | found |
| `member_link_mode` | str | Berechtigungsmodus für Invite-Links (aus dem Namen abgeleitet) | inferred |
| `member_share_group_history_mode` | str | `ADMIN_SHARE` / `ALL_MEMBER_SHARE`, vollständiges Enum und System-Message-Mapping in [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.4 — hier nicht wiederholt | found |
| `membership_approval_mode_enabled` | bool | schaltet Join-Request-Gating für diese Gruppe ein/aus — siehe §11 | found |
| `limit_sharing`, `limit_sharing_enabled`, `limit_sharing_trigger` | str/bool/str | Toggle für Forwarding-Limit dieser Gruppe (inferred: "limit sharing"-Weiterleitungsbeschränkung) | inferred |
| `input` | str | Wrapper-/Kontextobjekt (Form nicht aufgelöst) | unknown |

Server-seitiges Notification-Pendant und die vollständige Spaltenliste von `wa_group_admin_settings` (`restrict_mode`, `announcement_group`, `no_frequently_forwarded`, `ephemeral_duration`, `require_membership_approval`, `addressing_mode`, `allow_member_labels`, …) stehen in [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4 — querverwiesen, nicht duplicated.

---

## 10. Community-spezifische Struktur

| Item | Detail | Tier |
|------|--------|------|
| Sub-Gruppen-Auflistung | `QuerySubgroups` (`group_input`) | found |
| Sub-Gruppen-/Community-Zählwerte | `QuerySubgroupParticipantCount`, `QueryCommunityParticipantCount` | found (Ops existieren), unknown (Variablen) |
| Linked-Group-Lookup | `QueryLinkedGroupInfo` (`group_jid`, `sub_group_jid_hint`) — löst eine Sub-Gruppe anhand ihres Parents auf | found |
| Ownership-Transfer | `UpdateCommunityOwner` (`new_role`, `group_id`, `role_updates`, `user_jid`) | found |
| Toggle für Non-Admin-Sub-Gruppen-Erstellung | `AllowNonAdminGroupCreation` (`allow_non_admin_sub_group_creation` bool) | found |
| Default-Subgroup-Poll-Variante | `pollCreationMessageV2` ist der Poll-Slot, der verwendet wird, wenn der Chat eine Default-Sub-Gruppe ist (`group_type == 3`) — [WA_POLLS.md](WA_POLLS.md) §1, §3.3 | found |
| DB-Tabellen | `subgroup_info`, `community_settings`, `group_relationship` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4) | found |

---

## 11. Membership Approval und Community-Join-Approval

### 11.1 Gruppen: Request-to-Join-Gating

`membership_approval_mode_enabled` (`SetGroupProperty`, §9) schaltet admin-gated Joining für eine Gruppe ein; `wa_group_admin_settings.require_membership_approval` ist das persistierte Flag ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4). Für eine **Sub-Gruppe** einer Community kommt der Default stattdessen vom Parent: `parent/default_membership_approval_mode="request_required"` (§1.1, `C23201A1a`). Die Speicherung ausstehender Requests ist danach aufgeteilt, wer approven darf: `group_membership_approval_requests` (admin-sichtbar) und `non_admin_group_membership_approval_requests`; `group_membership_form_questions` hält admin-konfigurierte Fragen, die ein Beitretender beantworten muss, und `group_membership_count` trackt aggregierte Zählwerte (alles `found`, [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4). `group_membership_form_questions` ist der konkrete clientseitige Beleg dafür, dass ein Membership-Form-Flow existiert — direkt relevant für `JoinMembershipForm` unten.

### 11.2 Wire-Surface: MEX-Primärpfad + Legacy-Fallback

`com/whatsapp/group/data/GroupFetchAllMembershipApprovalRequestsJob` (`found`, 2.26.45.10 smali) implementiert "fetch pending join requests awaiting admin approval" für einen `groupJidRawString`, zur Laufzeit gated durch `LX/00E;->A0G(LX/00E;LX/00g;)Z` gegen Flag-ID `LX/4WC;->A04` (gelesen via `LX/00U;->A03(0x10d4)`):

| Pfad | Bedingung | Mechanismus |
|------|-----------|--------------|
| MEX | Flag an | `GraphQlCallInput` mit `query_context="INTERACTIVE"` und der Ziel-`GroupJid`, Operation **`QueryMembershipApprovalRequests`** auf Namespace `whatsapp-android-mex` |
| Legacy-Binär-IQ | Flag aus (`LX/0RD`-Fallback) | `<iq type="get" xmlns="w:g2" to="<group_jid>" id="..."><membership_approval_requests/></iq>` |

Die `doc_id` von `QueryMembershipApprovalRequests` rotiert normal über die Builds hinweg: `28845604101745223` (2.26.41.6) → `28584744077887639` (2.26.45.10). Die Admin-Approve/Deny-Mutation, `GroupMembershipRequestUpdate`, ist das Gegenstück (`29469157542702726` → `28746221238391491`, gleiches normales Rotationsmuster); ihre Call-Site wurde in diesem Durchgang nicht getraced, aber sie ist die einzige adminseitige Group-Membership-Mutation im Katalog (§4.1).

`JoinMembershipForm` (doc_id `28997137096573014`) ist tatsächlich neu im 2.26.45.10-Katalog — in 2.26.41.6 nicht vorhanden, keine Rotation einer existierenden Op. Ihr Name macht sie, zusammen mit der `group_membership_form_questions`-Tabelle (§11.1), zum besten Kandidaten für die Submit-seitige Mutation "beantworte die Admin-Membership-Form-Fragen und beantrage den Beitritt" — ihre Call-Site wurde in diesem Durchgang jedoch nicht getraced. **Inferred**, nicht found, für ihre genaue Rolle und ihr Schema.

### 11.3 Community-Join-Approval im Speziellen (2.26.45.10, found)

Neues Package `com/whatsapp/community/product/joinapproval/`, eine Klasse: `CommunityJoinApprovalNuxBottomSheet` — ein lokales UI-Erklär-Sheet ("du brauchst Admin-Genehmigung, um dieser Community beizutreten"), keine eigene Netzwerk-Call-Site.

- Konstruiert von `LX/3IN;->C3f` mit Bundle-Args `"group_jid"` (die eigene JID der Community, als roher Group-JID-String gelesen) und `"community_name"`.
- Primary-Button-Handler `LX/3Ge;->C3f`, `pswitch_28`: liest die gespeicherte `GroupJid`, ruft `LX/122;->A01(Context, GroupJid, Integer)Intent` auf, startet sie via `LX/0KC;->A02`, verwirft das Sheet.

**Key Finding:** die Community wird über `group_jid` adressiert, nicht über einen distinkten `community_jid`-/`newsletter_jid`-artigen Schlüssel — direkte Code-Bestätigung, nicht nur Namenskonvention, des "Community ist eine Gruppe"-Modells aus §1/§2. Es existiert keine `Community*ApprovalRequests`-artige Operation irgendwo im Katalog; die ausstehenden Join-Requests einer Community laufen über genau dasselbe `QueryMembershipApprovalRequests`-/`GroupMembershipRequestUpdate`-MEX-Paar (und denselben Legacy-`w:g2`-Fallback), das eine normale Gruppe verwendet, weil der Membership-Approval-Job immer nur einen `groupJidRawString` sieht.

### 11.4 Fazit

| Claim | Tier |
|-------|------|
| Community über `group_jid` adressiert, gleicher Code-Pfad wie Gruppen | found |
| Pending Requests auflisten: MEX `QueryMembershipApprovalRequests` | found |
| Approve/Deny: MEX `GroupMembershipRequestUpdate` | found (Op existiert, katalogisiert); Call-Site nicht getraced |
| Legacy-Fallback: `<iq xmlns="w:g2"><membership_approval_requests/></iq>` | found |
| Feature-Gate zur Auswahl MEX vs. Legacy | found (Flag-ID, nicht ihr aktueller Rollout-Zustand) |
| Submit-Seite ist `JoinMembershipForm` | inferred |
| Genaues `JoinMembershipForm`-Schema/Variablen | unknown |
| Serverseitige Acceptance-/Validierungslogik | unknown (nur statische Analyse, kein Traffic-Capture) |

---

## 12. Local-Storage-Querverweis

Vollständige Spaltenlisten stehen in [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md); dies ist eine Verweistabelle, keine Duplikat:

| Tabelle | Rolle |
|-------|------|
| `wa_group_admin_settings` | Admin-Einstellungen pro Gruppe (Addressing-Mode, History, Approval, Forwarding-Limit, ...) |
| `group_participant_user`, `group_past_participant_user`, `group_participant_device` | aktuelle/vergangene Teilnehmer, Rang, Sender-Key-State pro Gerät |
| `group_membership_approval_requests`, `non_admin_group_membership_approval_requests` | ausstehende Join-Requests, aufgeteilt nach Approver-Sichtbarkeit |
| `group_membership_form_questions` | admin-konfigurierte Membership-Form-Fragen (§11.1, §11.2) |
| `group_membership_count` | aggregierte Zählwerte |
| `subgroup_info`, `community_settings`, `group_relationship` | Community-/Sub-Group-Struktur |
| `member_suggested_groups_v2` | Vorschlags-Oberfläche für Gruppen |
| `group_suspension_appeal` | Suspension-Appeal-State auf Gruppenebene |
| `group_non_wa_invites` | Invites an Non-WhatsApp-Kontakte |
| `group_root_key_mapping` | Sender-Key-Root-Mapping |

---

## 13. Baileys-/velowa-Implementierungshinweise

Alle Gruppen-/Community-MEX-Ops nutzen denselben `w:mex`-IQ-Envelope wie jede andere Persisted Query in diesem Repo (`Protocols/mex-graphql`, `graphql-invocation-guide.md`):

```js
const res = await sock.query({
  tag: 'iq', attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '<doc_id>' },
    content: Buffer.from(JSON.stringify({ queryId: '<doc_id>', variables })) }],
})
```

Der Legacy-Abruf von Gruppenmetadaten/Teilnehmern bleibt auf `w:g2` und ist bei den meisten WA-Web-Libraries bereits implementiert (`groupMetadata`, `groupQuery`-artige Calls); Membership-Approval braucht die IQ aus §11.2 explizit ergänzt — die meisten Libraries fragen sie nicht ab.

| Warum es scheitert | Fix |
|---------------|-----|
| Fest kodierte `doc_id` für eine Gruppen-/Community-Op | `doc_id` rotiert mit jedem APK-Build (bestätigt: 4 Gruppen-Ops rotierten allein zwischen 2.26.38.10 und 2.26.41.6); aus einer aktuellen Katalog-Extraktion beziehen, nicht fest pinnen |
| Annahme, Membership-Approval sei immer Legacy-`w:g2` | Es ist feature-gegated; sobald das Flag serverseitig für einen Account an ist, erscheinen ausstehende Requests nur noch via MEX `QueryMembershipApprovalRequests` — beide Pfade implementieren oder künftig MEX-only |
| Annahme, eine Community habe ihren eigenen JID-Typ | Hat sie nicht — über die eigene `@g.us`-JID der Parent-Gruppe adressieren, wie jede andere Gruppen-Op |
| Versuch, einen gated Join-Request programmatisch zu submitten | Das Schema von `JoinMembershipForm` ist ungeklärt (nur inferred role); noch nicht mit Zuversicht implementierbar |

---

## 14. Wichtige Unterscheidungen

- **Eine Community ist eine klassifizierte Gruppe, keine separate Entität.** Keine `community_jid`; die eigene JID der Community ist eine Gruppen-JID mit Node-Typ 1 (`parent`).
- **`member_share_group_history_mode`** (wer darf neuen Beitretenden aktuelle History teilen, [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.4) ist unabhängig von **`membership_approval_mode_enabled`** (Join-Request-Gating, §9/§11) — beides sind `SetGroupProperty`-Felder, die aber unterschiedliche Features steuern.
- **`w:g2`-Report-to-Admin** ([WA_REPORTING.md](WA_REPORTING.md) §9) und der **`w:g2`-Membership-Approval-Requests-Fallback** (§11.2) teilen sich einen Namespace, sind aber unabhängige Kindelemente (`reports`/`allow_admin_reports` vs. `membership_approval_requests`).
- **`JoinMembershipForm`** ist eine inferred Submit-seitige Op, keine bestätigte — nicht als found behandeln.
- **Promote/Demote/Remove-Participant** hat keine identifizierte MEX-Operation in diesem Katalog; als ungeklärt behandeln, nicht als "läuft nur über Legacy-`w:g2`" (Annahme, keine Evidenz).

---

## 15. Community-Join-Approval-Flow (wie derzeit belegt)

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

## 16. Offene Punkte / Gotchas

- Variablen/Response-Form von `JoinMembershipForm`: unknown, nicht call-site-getraced.
- Eigene Variablen von `GroupMembershipRequestUpdate`: in diesem Durchgang aus keiner Call-Site rekonstruiert (Op nur als existent bestätigt).
- Promote/Demote/Remove-Participant: keine MEX-Op identifiziert; Legacy-only vs. fehlend-im-Katalog ist ungeklärt.
- `CreateCommunity`: keine solche MEX-Op existiert; der Community-Erstellungspfad ist ungeklärt (Client-Wizard, der `CreateGroup` + Linking verkettet, ist die Arbeits-Vermutung, nicht bestätigt).
- Alle Claims in §11 über die reine DB-Tabellen-Existenz hinaus sind statische Analyse; nichts hier ist traffic-getestet (gemäß dem Evidence-Contract — es wurde für diesen Report keine Live-Server-Interaktion durchgeführt).
