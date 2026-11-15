# WhatsApp Groups & Communities — Full RE Report
**Version:** 2.26.41.6 (membership-approval/join-approval wire surface additionally verified on 2.26.45.10, noted inline) | **Date:** 2026-11-15
**Scope:** Group vs. community structural model (parent group, linked sub-groups, default sub-group, general chat), JID addressing, legacy `w:g2`/`w:gp2` wire surface, the `whatsapp-android-mex` group/community GraphQL operation catalog, creation/invite/admin-action flows, invite links, and community join approval (`QueryMembershipApprovalRequests`, `GroupMembershipRequestUpdate`, the legacy `w:g2` fallback, and the inferred `JoinMembershipForm` submit op).

---

## 1. What it is

A WhatsApp **community** is not a distinct addressable entity. It is a **group** — same JID space, same `<group>` node parser, same `wa_group_admin_settings` table — that plays the role of a **parent group** for a set of **linked sub-groups**. This report pulls together the group/community model that is otherwise scattered across [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2 (classification, addressing), [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) (DB tables), [WA_REPORTING.md](WA_REPORTING.md) (the `w:g2` report-to-admin surface) and [WA_POLLS.md](WA_POLLS.md) (default-subgroup poll variant), and adds the group/community MEX operation catalog and the 2.26.45.10 community join-approval finding.

### 1.1 Entities

| Entity | Addressing | Relation | Tier |
|--------|-----------|----------|------|
| Group | own `@g.us` JID | — | found |
| Community | **same** `@g.us` JID space as a group; classified, not separately typed | is a group acting as a parent | found |
| Parent group | `<group>` node type **1** (`parent` child present) | top of a community | found |
| Linked sub-group | `<group>` node type **2** (`linked_parent jid` child) | `linked_parent jid` points at the parent's JID | found |
| Default sub-group | `<group>` node type **3** (`default_sub_group` child) | auto-created sub-group of a community; `group_type` **3** locally, also the trigger for `pollCreationMessageV2` (WA_POLLS §1) | found |
| General chat | `<group>` node type **6** (`general_chat` child) | community-wide announcement-style chat | found |
| Normal group | `<group>` node type **0** | no community relation | found |

Classification and parent-JID extraction: `C23201A1a.A01` (type 0/1/2/3/6 above), `C23201A1a.A03` (reads the parent JID from `linked_parent jid`) — both `found` in [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.3, re-cited here rather than re-derived. `membership_approval_mode` for a sub-group defaults from `parent/default_membership_approval_mode="request_required"`.

---

## 2. Addressing and participant model

Condensed from [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.1–2.2 (full detail there; group-history-specific fields omitted here):

- `<group>` node, legacy path `C23201A1a.A0C` (shared with group notifications); a MEX/SMAX twin exists (`AbstractC23204A1d`, `AN6`, `C23690AKd`).
- Core attrs: `id`, `creation`, `subject`, `s_t`/`s_o`/`s_o_pn`, `creator`/`creator_pn` (the `_pn` twins carry the phone JID next to a LID).
- `addressing_mode` (`lid` / `pn`) — stored in `wa_group_admin_settings.addressing_mode`; anything other than `pn` is read as `lid`.
- `<participant jid lid phone_number type display_name username join_time group_history_sent>` (`C23201A1a.A05`, `C23205A1e.A0J`). `type` is the per-group role attribute behind admin status; `jid`/`lid`/`phone_number` carry the two address forms depending on `addressing_mode`.

No separate `community_jid` or `newsletter_jid`-style key exists anywhere in the client — confirmed with fresh code evidence in §11.3 below, consistent with §1's "community is a group" model.

---

## 3. Legacy wire protocol (`w:g2` / `w:gp2`)

Pre-MEX group operations still run as binary XMPP IQs under namespace `w:g2`; `w:gp2` is listed as one of the `notification` push-stanza variants (`Protocols/xml-stanzas`, `Protocols/xmpp-namespaces-android` namespace inventories, `found`). Concrete, structurally-recovered example (`found`, `WASmaxGroupsGetGroupInfoRPC`):

```
iq[id=<stanzaId>, to=<groupJid>, type="get", xmlns="w:g2"]
  query[request=<string>, phash=<string?>]
    add_request[admin=<userJid>, code=<string>, expiration=<int>]   (optional, min=0 max=1)
```

Response variants: `ClientError` / `ServerError` / `Success` (full group metadata: participants, subject, creation, description, ephemeral settings). The same namespace carries unrelated group operations documented elsewhere in this repo and not repeated here:

- Report-to-admin (`<iq to=groupJid type=set xmlns=w:g2><reports><report message_id=.../></reports></iq>`) and the admin-report toggle (`allow_admin_reports`/`not_allow_admin_reports`) — [WA_REPORTING.md](WA_REPORTING.md) §9.
- The membership-approval-requests legacy fallback — §11.2 below.

---

## 4. MEX GraphQL surface

`whatsapp-android-mex` persisted-query catalog, `found in` the shipped `whatsapp-android-mex_client_persist_ids.json` asset. `doc_id` values rotate every APK build (95 rotations logged between 2.26.41.6 and 2.26.45.10, `Querys/graphql-diff-2.26.41.6-to-2.26.45.10.md` in the brain) — the tables below are the 2.26.41.6 snapshot.

### 4.1 Group operations (21)

| Operation | doc_id (2.26.41.6) | Type |
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

### 4.2 Community operations (4)

| Operation | doc_id (2.26.41.6) | Type |
|---|---|---|
| `QueryCommunityParticipantCount` | `31981537024824321` | Query |
| `QuerySubgroupParticipantCount` | `24784259781196779` | Query |
| `QuerySubgroups` | `25554052094203120` | Query |
| `UpdateCommunityOwner` | `24781435194845316` | Mutation |

No `CreateCommunity`-named operation exists in this catalog — `unknown` whether community creation is a client-local wizard that chains `CreateGroup` + linking calls, or a server-side implicit promotion of a group to parent; not resolved in this pass.

### 4.3 Variables recovered from APK call sites (`found`)

| Operation | Variables | Call site |
|---|---|---|
| `CreateGroup` | `participants`, `subject`, `expiration_time_in_sec`, `trigger`, `member_add_mode`, `member_link_mode`, `member_share_group_history_mode`, `username`, `user_lid` | `X/C36500G6k.java` |
| `AddParticipantsToGroupV2` | `mode`, `user_lid`, `username`, `group_id`, `participants`, `add_participants_metadata`, `input` | `X/C08600aH.java` |
| `AddParticipantsToGroupsV3` | `mode`, `group_ids`, `participants`, `tctoken`, `privacy_token`, `add_participants_metadata` | `X/RunnableC24380AnV.java` |
| `QueryGroupInfo` | `group_jid`, `query_context`, `input` | `X/C08630aK.java` |
| `QueryGroupInfoByCode` | `invite_code`, `query_context`, `get`, `input` | `X/C08600aH.java` |
| `QueryLinkedGroupInfo` | `group_jid`, `sub_group_jid_hint`, `query_context`, `input` | `X/JOF.java` |
| `QueryBatchGetGroups` | `group_jid`, `query_context`, `groups`, `request_context` | `X/FGG.java` |
| `QueryParticipatingGroups` | `input` | `X/C16710ou.java` |
| `SetGroupProperty` | see §9 | `X/A18.java`, `X/A19.java` |
| `SetGroupResetInviteLink` | `group_id`, `query_context`, `group_input`, `group_jid`, `max_use`, `seconds_for_expiry` | `X/C54392a5.java` |
| `AllowNonAdminGroupCreation` | `allow_non_admin_sub_group_creation` (bool) | `com/whatsapp/community/mex/AllowNonAdminSubGroupCreationGraphQlHandler.java` |
| `QuerySuggestedGroups` | `group_input` | `com/whatsapp/community/mex/GetSuggestedGroupsGraphQlHandler.java` |
| `QuerySubgroups` | `group_input` | `com/whatsapp/community/mex/GetSubgroupsGraphQlHandler.java` |
| `UpdateCommunityOwner` | `new_role`, `group_id`, `role_updates`, `user_jid` | `com/whatsapp/community/mex/TransferCommunityOwnershipGraphQlHandler.java` |
| `GroupsStoreAndSendInvitesSMSMutation` | `server_sent_sms`, `participants`, `entry_point`, `is_bundle_invite`, `participant`, `group_jid` | `com/whatsapp/invite/api/ServerSentGroupInviteMutationHelper.java`, `com/whatsapp/invite/ui/SMSPreviewGroupInviteBottomSheetFragment.java` |
| `GroupsStoreInvitesSMSMutation` | `partcipants` (sic), `group_jid` | `X/C67052zD.java` |
| `AddParticipantsToInteropGroup` | `gid`, `participants`, `jid`, `input` | `X/C3ZT.java` |
| `QueryInteropGroupInfo` | `gid`, `group_input` | `X/C3ZT.java` |

The rest (`GetPreRegGroupAddRequestsQuery`, `GroupsCreateInteropGroup`, `LeaveInteropGroup`, `QueryCommunityParticipantCount`, `QuerySubgroupParticipantCount`) have no static call site recovered: `unknown`, likely sending `{}`.

---

## 5. Creating a group

`CreateGroup` (§4.3) sets `member_add_mode`, `member_link_mode`, `member_share_group_history_mode` at creation time — the same three admin properties `SetGroupProperty` later edits (§9). `trigger` is a string entry-point tag (`found`, exact value set not enumerated this pass).

---

## 6. Invite links and invites

| Item | Detail | Tier |
|------|--------|------|
| Reset/create invite link | `SetGroupResetInviteLink`: `group_id`, `group_jid`, `max_use`, `seconds_for_expiry` | found |
| Resolve an invite code | `QueryGroupInfoByCode`: `invite_code` -> group info | found |
| SMS invite (bundle) | `GroupsStoreAndSendInvitesSMSMutation`: `participants`, `entry_point`, `is_bundle_invite`, `server_sent_sms` | found |
| SMS invite (store only) | `GroupsStoreInvitesSMSMutation`: `group_jid`, participants | found |
| Allow/deny list | DB `wa_group_add_allow_list`, `wa_group_add_black_list` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) | found |
| Non-WhatsApp invites | DB `group_non_wa_invites` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) | found |

### 6.1 `groupInviteMessage` wire form

`Message.groupInviteMessage`, field **28**, nested type `Message.GroupInviteMessage` (found in WAProto.proto):

| Field | # | Type |
|-------|---|------|
| `groupJid` | 1 | string |
| `inviteCode` | 2 | string |
| `inviteExpiration` | 3 | int64 |
| `groupName` | 4 | string |
| `jpegThumbnail` | 5 | bytes |
| `caption` | 6 | string |
| `contextInfo` | 7 | ContextInfo |
| `groupType` | 8 | enum `GroupType` |

`GroupType`: `DEFAULT` = 0, `PARENT` = 1 — the invite message itself distinguishes a plain group invite from a community (parent-group) invite, consistent with §1's "community is a classified group" model. A second, unrelated top-level `GroupInviteMessage` type exists elsewhere in the same proto file; this table covers only the nested `Message.GroupInviteMessage` used by field 28.

---

## 7. Participants: add, suggest, enumerate

| Operation | Purpose (inferred from name + variables) |
|---|---|
| `AddParticipantsToGroupV2` / `V3` | add one or more users to one or more groups |
| `QueryParticipatingGroups` | list groups the caller is in |
| `QueryBatchGetGroups` | batch metadata fetch for a set of group JIDs |
| `QuerySuggestedGroups` | community/group suggestions surface; DB `member_suggested_groups_v2` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) |
| `QuerySubgroups` / `QuerySubgroupParticipantCount` / `QueryCommunityParticipantCount` | community-level counts over the linked sub-groups |

The `<participant type=...>` attribute (§2) carries the per-group admin/role flag, and `group_participant_user.rank` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §3.6) persists it locally — so admin rank exists as a concept, but no explicit promote/demote or remove-participant MEX operation was found in this catalog (the 21/4 group/community ops above are exhaustive for 2.26.41.6). **Unknown**: whether that path still runs purely as a legacy `w:g2` participant-list IQ (consistent with `AddParticipantsToGroupV2`'s own name implying a V1 predecessor existed) or under some operation name outside the `group`/`community` name-substring buckets; not resolved in this pass.

---

## 8. Interop groups (brief)

`AddParticipantsToInteropGroup`, `GroupsCreateInteropGroup`, `QueryInteropGroupInfo`, `LeaveInteropGroup` — a parallel small set of group operations for third-party-bridged ("interop") groups. Out of scope here beyond listing them; see [WA_INTEROP.md](WA_INTEROP.md) for the interop consent/bridge model they plug into.

---

## 9. Admin settings — `SetGroupProperty`

**Variables** (`found`, `X/A18.java`, `X/A19.java`):

| Field | Type | Meaning | Tier |
|-------|------|---------|------|
| `group_id` | str | target group | found |
| `subject` | str | group name | found |
| `description` | str | group description | found |
| `previous_id` | str | optimistic-concurrency / prior-value marker (inferred) | inferred |
| `member_add_mode` | str | who can add members (`all_member_add` / other, mirrors the legacy `<member_add_mode>` child, [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.1) | found |
| `member_link_mode` | str | invite-link permission mode (inferred from name) | inferred |
| `member_share_group_history_mode` | str | `ADMIN_SHARE` / `ALL_MEMBER_SHARE`, full enum and system-message mapping in [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.4 — not repeated here | found |
| `membership_approval_mode_enabled` | bool | turns join-request gating on/off for this group — see §11 | found |
| `limit_sharing`, `limit_sharing_enabled`, `limit_sharing_trigger` | str/bool/str | forwarding-limit toggle for this group (inferred: "limit sharing" forwarding restriction) | inferred |
| `input` | str | wrapper/context object (unresolved shape) | unknown |

Server-side notification counterpart and the full `wa_group_admin_settings` column list (`restrict_mode`, `announcement_group`, `no_frequently_forwarded`, `ephemeral_duration`, `require_membership_approval`, `addressing_mode`, `allow_member_labels`, …) are in [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4 — cross-referenced, not duplicated.

---

## 10. Community-specific structure

| Item | Detail | Tier |
|------|--------|------|
| Sub-group enumeration | `QuerySubgroups` (`group_input`) | found |
| Sub-group/community counts | `QuerySubgroupParticipantCount`, `QueryCommunityParticipantCount` | found (ops exist), unknown (variables) |
| Linked-group lookup | `QueryLinkedGroupInfo` (`group_jid`, `sub_group_jid_hint`) — resolves a sub-group given its parent | found |
| Ownership transfer | `UpdateCommunityOwner` (`new_role`, `group_id`, `role_updates`, `user_jid`) | found |
| Non-admin sub-group creation toggle | `AllowNonAdminGroupCreation` (`allow_non_admin_sub_group_creation` bool) | found |
| Default-subgroup poll variant | `pollCreationMessageV2` is the poll slot used when the chat is a default sub-group (`group_type == 3`) — [WA_POLLS.md](WA_POLLS.md) §1, §3.3 | found |
| DB tables | `subgroup_info`, `community_settings`, `group_relationship` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4) | found |

---

## 11. Membership approval and community join approval

### 11.1 Groups: request-to-join gating

`membership_approval_mode_enabled` (`SetGroupProperty`, §9) turns on admin-gated joining for a group; `wa_group_admin_settings.require_membership_approval` is the persisted flag ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4). For a **sub-group** of a community, the default comes from the parent instead: `parent/default_membership_approval_mode="request_required"` (§1.1, `C23201A1a`). Pending-request storage is split by who can approve: `group_membership_approval_requests` (admin-visible) and `non_admin_group_membership_approval_requests`; `group_membership_form_questions` holds admin-configured questions a joiner must answer, and `group_membership_count` tracks aggregate counts (all `found`, [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4). `group_membership_form_questions` is the concrete client-side evidence that a membership-form flow exists — directly relevant to `JoinMembershipForm` below.

### 11.2 Wire surface: MEX primary path + legacy fallback

`com/whatsapp/group/data/GroupFetchAllMembershipApprovalRequestsJob` (`found`, 2.26.45.10 smali) implements "fetch pending join requests awaiting admin approval" for a `groupJidRawString`, gated at runtime by `LX/00E;->A0G(LX/00E;LX/00g;)Z` against flag id `LX/4WC;->A04` (read via `LX/00U;->A03(0x10d4)`):

| Path | Condition | Mechanism |
|------|-----------|-----------|
| MEX | flag on | `GraphQlCallInput` with `query_context="INTERACTIVE"` and the target `GroupJid`, operation **`QueryMembershipApprovalRequests`** on namespace `whatsapp-android-mex` |
| Legacy binary IQ | flag off (`LX/0RD` fallback) | `<iq type="get" xmlns="w:g2" to="<group_jid>" id="..."><membership_approval_requests/></iq>` |

`doc_id` for `QueryMembershipApprovalRequests` rotates normally across builds: `28845604101745223` (2.26.41.6) → `28584744077887639` (2.26.45.10). The admin approve/deny mutation, `GroupMembershipRequestUpdate`, is the counterpart (`29469157542702726` → `28746221238391491`, same normal-rotation pattern); its call site was not traced this pass, but it is the only admin-side group-membership mutation in the catalog (§4.1).

`JoinMembershipForm` (doc_id `28997137096573014`) is genuinely new to the 2.26.45.10 catalog — absent from 2.26.41.6, not a rotation of an existing op. Its name, combined with the `group_membership_form_questions` table (§11.1), makes it the best candidate for the submit-side "answer the admin's membership-form questions and request to join" mutation — but its call site was not traced in this pass. **Inferred**, not found, for its exact role and schema.

### 11.3 Community join approval specifically (2.26.45.10, found)

New package `com/whatsapp/community/product/joinapproval/`, one class: `CommunityJoinApprovalNuxBottomSheet` — a local UI explainer sheet ("you'll need admin approval to join this community"), not a network call site itself.

- Constructed by `LX/3IN;->C3f` with bundle args `"group_jid"` (the community's own JID, read as a raw group JID string) and `"community_name"`.
- Primary-button handler `LX/3Ge;->C3f`, `pswitch_28`: reads the stored `GroupJid`, calls `LX/122;->A01(Context, GroupJid, Integer)Intent`, starts it via `LX/0KC;->A02`, dismisses the sheet.

**Key finding:** the community is addressed by `group_jid`, not a distinct `community_jid`/`newsletter_jid`-style key — direct code confirmation, not just naming convention, of the §1/§2 "community is a group" model. There is no `Community*ApprovalRequests`-style operation anywhere in the catalog; a community's pending join requests ride the exact same `QueryMembershipApprovalRequests` / `GroupMembershipRequestUpdate` MEX pair (and the same legacy `w:g2` fallback) a plain group uses, because the membership-approval job only ever sees a `groupJidRawString`.

### 11.4 Verdict

| Claim | Tier |
|-------|------|
| Community addressed by `group_jid`, same code path as groups | found |
| List pending requests: MEX `QueryMembershipApprovalRequests` | found |
| Approve/deny: MEX `GroupMembershipRequestUpdate` | found (op exists, catalogued); call site not traced |
| Legacy fallback: `<iq xmlns="w:g2"><membership_approval_requests/></iq>` | found |
| Feature gate selecting MEX vs. legacy | found (flag id, not its current rollout state) |
| Submit side is `JoinMembershipForm` | inferred |
| Exact `JoinMembershipForm` schema/variables | unknown |
| Server-side acceptance/validation logic | unknown (static analysis only, no traffic capture) |

---

## 12. Local storage cross-reference

Full column lists are in [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md); this is a pointer table, not a duplicate:

| Table | Role |
|-------|------|
| `wa_group_admin_settings` | per-group admin settings (addressing mode, history, approval, forwarding limit, ...) |
| `group_participant_user`, `group_past_participant_user`, `group_participant_device` | current/past participants, rank, per-device sender-key state |
| `group_membership_approval_requests`, `non_admin_group_membership_approval_requests` | pending join requests, split by approver visibility |
| `group_membership_form_questions` | admin-configured membership-form questions (§11.1, §11.2) |
| `group_membership_count` | aggregate counts |
| `subgroup_info`, `community_settings`, `group_relationship` | community/sub-group structure |
| `member_suggested_groups_v2` | suggested-groups surface |
| `group_suspension_appeal` | group-level suspension appeal state |
| `group_non_wa_invites` | invites to non-WhatsApp contacts |
| `group_root_key_mapping` | sender-key root mapping |

---

## 13. Baileys / velowa implementation notes

All group/community MEX ops use the same `w:mex` IQ envelope as every other persisted query in this repo (`Protocols/mex-graphql`, `graphql-invocation-guide.md`):

```js
const res = await sock.query({
  tag: 'iq', attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '<doc_id>' },
    content: Buffer.from(JSON.stringify({ queryId: '<doc_id>', variables })) }],
})
```

Legacy group metadata/participant fetch stays on `w:g2` and is already implemented by most WA Web libraries (`groupMetadata`, `groupQuery`-style calls); membership approval needs the IQ from §11.2 added explicitly — most libraries do not query it.

| Why it fails | Fix |
|---------------|-----|
| Hardcoded `doc_id` for any group/community op | `doc_id` rotates every APK build (confirmed: 4 group ops rotated between 2.26.38.10 and 2.26.41.6 alone); refresh from a current catalog extraction, don't pin |
| Assuming membership-approval is always legacy `w:g2` | It is feature-flagged; once the flag is on server-side for an account, pending requests only surface via MEX `QueryMembershipApprovalRequests` — implement both paths or MEX-only going forward |
| Assuming a community has its own JID type | It does not — address it with the parent group's own `@g.us` JID, same as any group op |
| Trying to submit a gated join request programmatically | `JoinMembershipForm`'s schema is unresolved (inferred role only); not implementable with confidence yet |

---

## 14. Key distinctions

- **Community is a classified group, not a separate entity.** No `community_jid`; the community's own JID is a group JID with node type 1 (`parent`).
- **`member_share_group_history_mode`** (who may share recent history with new joiners, [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.4) is unrelated to **`membership_approval_mode_enabled`** (join-request gating, §9/§11) — both are `SetGroupProperty` fields but control different features.
- **`w:g2` report-to-admin** ([WA_REPORTING.md](WA_REPORTING.md) §9) and **`w:g2` membership-approval-requests fallback** (§11.2) share a namespace but are unrelated child nodes (`reports`/`allow_admin_reports` vs. `membership_approval_requests`).
- **`JoinMembershipForm`** is an inferred submit-side op, not a confirmed one — do not treat it as found.
- **Promote/demote/remove-participant** has no identified MEX operation in this catalog; treat as unresolved, not as "runs over legacy `w:g2` only" (assumption, not evidence).

---

## 15. Community join-approval flow (as currently evidenced)

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

## 16. Open items / gotchas

- `JoinMembershipForm`'s variables/response shape: unknown, not call-site-traced.
- `GroupMembershipRequestUpdate`'s own variables: not recovered from a call site in this pass (op confirmed to exist only).
- Promote/demote/remove-participant: no MEX op identified; legacy-only vs. missing-from-catalog is unresolved.
- `CreateCommunity`: no such MEX op exists; community creation path is unresolved (client wizard chaining `CreateGroup` + linking is the working guess, not confirmed).
- All claims in §11 beyond the DB table existence are static analysis; nothing here is traffic-tested (per the evidence contract — no live server interaction was performed for this report).
