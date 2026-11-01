<!-- src-sha1: 42c77add3dafd5b90522b32d91692dff968b2f54 -->
# WhatsApp Channels & Newsletters — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-11-01
**Umfang:** `@newsletter` JID-Domain und interne „newsletter"-Benennung, Follow/Unfollow, Channel-Erstellung, Admin-Rollen und Übergabe, die sechs `newsletterAdmin*`/`newsletterFollower*`/`newsletterScheduledMessage` Proto-Felder, Channel-Metadaten (Name, Beschreibung, Bild, Verifizierung, Status), Reaktionen auf Posts, View-/Follower-Zahlen, Admin-Invite/Revoke/Accept-Flow, GraphQL/MEX Newsletter-Operationen (doc_ids), lokaler Storage, Feature-Flags, Fehlerfälle

---

## 1. Was es technisch ist

Ein „Channel" ist die Consumer-Bezeichnung für das, was der Client intern **newsletter** nennt: eine One-to-many-Broadcast-JID mit serverseitigem (nicht E2E) Storage, einem kleinen Satz Rollen (Owner/Admin/Subscriber/Guest), und die meisten Control-Plane-Operationen laufen über `w:mex` GraphQL statt klassische XMPP IQs. Content-Delivery (Post-Fetch, Status-Fetch, geplante Nachrichten, Live-Update-Subscription) nutzt weiterhin einen dedizierten XMPP-IQ-Namespace, `xmlns="newsletter"`. Alle Aussagen sind statische Analyse der dekompilierten APK; nichts wurde im Wire-Traffic erfasst. Tiers: **found** = im Code gelesen, **inferred** = aus Code abgeleitet, **unknown** = nicht aufgelöst. Anders als bei den meisten obfuskierten-Namen-Reports dieses Repos kommt das client-sichtbare Newsletter-Package (`com.whatsapp.newsletter.*`, 122 Dateien) in 2.26.41.6 mit **lesbaren Klassen- und Methodennamen**; nur die geteilte Infrastruktur (JID, Message-Proto, IQ-Builder) ist obfuskiert und wird hier aus stabilen Strings neu aufgelöst.

Nicht im Umfang: klassische Broadcast-Listen und `status@broadcast` — siehe [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md). Contact-/Device-Lookup-Mechanik, die von Newsletters wiederverwendet wird (nicht newsletter-spezifisch) — siehe [WA_USYNC.md](WA_USYNC.md).

| Entität | Wert | Tier |
|--------|-------|------|
| JID-Server | `newsletter` (z. B. `120363000000000000@newsletter`) | found |
| `Jid.getType()` | **21** | found |
| Verschlüsselung | `EnumC14260eC.NON_E2EE` — Channel-Content ist **nicht end-to-end-verschlüsselt** | found |
| Lokale Model-Klasse | `C2130898y` ("NewsletterInfo"), erweitert die generische Chat-Zeile `C14220e7` | found |
| JID-Klasse | `C1Y7` (`NewsletterJid`) | found |
| Invite-Link | `https://whatsapp.com/channel/<invite_code>` | found |
| Lokale DB-Tabelle | `newsletter` (Spalten u. a. `membership`, `invite_code`, indiziert) | found |

| Komponente | Name in 2.26.41.6 | Rolle |
|-----------|----------------|------|
| JID-Parser | `C0DL.A03` (Server-String-Switch), `C1Y7` (JID), `C1Y8` (JID-Companion/Cache) | validiert numerische ID, keine führende Null, baut/cached `C1Y7` |
| JID-Prädikate | `C0DZ.A0a(jid)` = `getType()==21`; `C0DZ.A0M` zählt Typ 21 zu der Menge, die auch Gruppen (18), Broadcast-Liste (3), Status (5) usw. enthält | isNewsletter / Multi-Recipient-fähige Menge |
| Lokales Model | `C2130898y` | Rolle, Verifizierung, Mute, Reaktions-Einstellung, Status, Zähler |
| Rollen | `C9U5` (lokales Enum), `C9U4` (Wire-String-Enum) | Abschnitt 4 |
| Metadaten-Job | `BaseMetadataNewsletterGraphqlJob`, `GetNewsletterAdminMetadataJob` | `NewsletterMetadata` / `NewsletterAdminMetadataQuery` |
| Update-Job | `UpdateNewsletterGraphqlJob` | `NewsletterMetadataUpdate` |
| Create/Delete-Job | unter `com.whatsapp.newsletter.editcreate`, `com.whatsapp.newsletter.delete` | `NewsletterCreate(Verified)` / `NewsletterDelete` |
| Message-Fetch | `GetNewsletterMessagesJob`, `GetNewsletterMessagesUpdatesJob`, `GetNewsletterMyAddOnMessagesJob`, `SendNewsletterMessageJob`, `SendViewReceiptJob` | `com.whatsapp.newsletter.messages.job` |
| Status-(Channel-Updates)-Fetch | `GetNewsletterStatusesJob`, `GetNewsletterStatusUpdatesJob`, `GetStatusMyAddOnsJob` | `com.whatsapp.newsletter.status.job` |
| IQ-Builder | `C9EN` (`xmlns="newsletter"`-Konstruktoren), `C9E2` (View-Role-/Child-Node-Value-Sets) | Abschnitt 6 |
| Admin-Invite-Versand | `C9m6` (`UserActionsNewsletterMessaging`), `C213489Am` | Abschnitt 5.4 |
| Reaction-Store | `C12H`, `C23768ANd` → Tabelle `newsletter_message_reaction` | Abschnitt 7 |

---

## 2. JID und Domain

### 2.1 Parsing (found, `C0DL.A03`)

```java
// X.0DL (C0DL)
public C1Y7 A03(String str, String str2) throws C09B {
    String strTrim = str.trim();
    if (strTrim.isEmpty() || "0".equals(strTrim) || strTrim.indexOf("0") == 0)
        throw new C09B("Identifier must be a valid number starting with non-zero");
    if (!"newsletter".equals(str2)) throw new C09B(...);
    // cache lookup/insert, returns C1Y7(str)
}
```

`C1Y7.getServer()` liefert den literalen String `"newsletter"`; `getType()` liefert `21`. Gleiche Keine-führende-Null-Regel für numerische IDs wie bei anderen Multi-Party-JID-Typen (Gruppen, Broadcast-Listen — siehe [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) §2.1). Der generische JID-Router `C0DZ.A01` fällt auf `C1Y7.A03.A02(str)` als Default-Case zurück, wenn der String weder ein bekanntes Singleton, eine `UserJid`, noch eine `GroupJid` ist — d. h. `@newsletter` ist die Fallback-Domain in diesem Parser (found).

### 2.2 Type-Set-Mitgliedschaft (found, `C0DZ.java`)

```java
public static boolean A0a(Jid jid) { return jid != null && jid.getType() == 21; }   // isNewsletter
public static boolean A0M(Jid jid) {
    int type = jid.getType();
    return type==0||type==1||type==18||type==22||type==3||type==7||type==21||type==26||type==28;
}
```
`A0a` ist das dedizierte Newsletter-Prädikat. `A0M` gruppiert Typ 21 zusammen mit Gruppen (18/22), Broadcast-Liste (3), Community (7) und anderen in eine breitere „Multi-Participant-fähige" Menge (genauer Zweck der exakten Gruppierung nicht vollständig nachvollzogen; inferred, dass sie geteilte Participant-/Session-Mechanik gated).

---

## 3. Follow / Unfollow

Folgen ist **keine** Stanza-Subscription; es ist eine `w:mex`-Mutation, und die lokale Rolle (`C9U5`) wechselt zwischen `GUEST` und `SUBSCRIBED`.

| Operation | doc_id | Variablen (found) |
|-----------|--------|--------------------|
| `NewsletterJoin` | `24658527423838739` | `entry_point`, `record`, `recipient_account_id`, `sessions`, `jid`, `fetch_and_validate_vname`, `call_offer`, `request_bottom_sheet_fragment` |
| `NewsletterLeave` | `25758579043742316` | identische Form wie `NewsletterJoin` |

Beide werden von derselben Klasse gebaut, `X/RunnableC24381AnW.java` (found). Der geteilte Variablensatz (`entry_point`, `call_offer`, `request_bottom_sheet_fragment`) legt nahe, dass Join/Leave einen generischen „Chat-Action"-Mutation-Wrapper wiederverwenden, der auch für Calls und Bottom-Sheet-getriggerte Actions anderswo in der App genutzt wird (inferred).

Lokale Rollenübergänge am `C2130898y`-Objekt ("NewsletterInfo"):

| Helper | Bedingung | Bedeutung |
|--------|-----------|---------|
| `A0p()` | `!muted && role==ADMIN` | ist Admin |
| `A0q()` | `!muted && (role==ADMIN \|\| role==OWNER)` | ist Admin oder Owner |
| `A0r()` | `role==SUBSCRIBED` | folgt |
| `A0s()` | `role==GUEST` | folgt nicht (wird genutzt, um bei einem Metadaten-Refresh `fetch_viewer_metadata=true` zu erzwingen — found in `BaseMetadataNewsletterGraphqlJob`) |
| `A0u()` | `!muted && role==OWNER` | ist Owner |

UI-Fehlerstring bei Follow-Fehlschlag: `str1c0d` "Couldn't follow channel", `str1c0e` "Couldn't follow channel. Check your device's internet connection and try again." (found, `res/values/strings.xml`).

---

## 4. Rollen

Es gibt zwei parallele Rollen-Enums: ein lokal persistiertes Enum und ein Wire-String-Enum, das in GraphQL-Variablen/Responses genutzt wird.

### 4.1 Lokale Rolle (found, `C9U5`)

```java
GUEST=0 (A03), SUBSCRIBED=1 (A05), ADMIN=2 (A02), OWNER=3 (A04)
```
`C9U5.A00()` mappt Ordinal → einen Prioritäts-Rang: GUEST→4, SUBSCRIBED→3, ADMIN→2, OWNER→1 (niedriger = privilegierter; Zweck — Sortierreihenfolge für Admin-Listen — inferred).

### 4.2 Wire-Rolle (found, `C9U4`, `serverValue` = Enum-Name)

```
UNSET_OR_UNRECOGNIZED_ENUM_VALUE, ADMIN, GUEST, OWNER, SUBSCRIBER
```
Wird als `view_role`-Attributwert auf dem `smax:any`-Child von Newsletter-XMPP-IQs (Abschnitt 6) genutzt sowie als GraphQL-`viewer_metadata.role`-Wert (Abschnitt 8).

### 4.3 Capabilities und Übergabe

| Aktion | GraphQL-Op | doc_id |
|--------|-----------|--------|
| Nutzer als Admin einladen | `NewsletterAdminInvite` | `26278681041745438` |
| Ausstehenden Admin-Invite zurückziehen | `NewsletterAdminInviteRevoke` | `24369392486051948` |
| Admin-Invite annehmen | `NewsletterAcceptAdminInvite` | `24934958956134858` |
| Admin degradieren | `NewsletterAdminDemote` | `25054538847517281` |
| Ownership übertragen | `NewsletterChangeOwner` | `24737692515842078` |
| Admin-Profile Batch-Fetch | `NewsletterAdminProfilesQuery` | `28089989690595314` |
| Admin-Profil-Update (Name/Foto) | `NewsletterAdminProfileUpdate` | `25959584293627630` |
| Admin-Metadaten (vollständig, Admin-only-Felder) | `NewsletterAdminMetadataQuery` | `26882701001369256` |
| Capabilities-Gate | `NewslettersAdminCapabilitiesQuery` | `27579307995002556` |

Admin-Invite-Flow-Action-Enum (found, `EnumC215899Sc`, genutzt von `AdminInviteErrorDialog`): `NOT_SUPPORTED=0`, `INVITE=1`, `ACCEPT_INVITE=2`, `REVOKE=3`, `DISMISS=4`.

UI-Fehlerstrings (found): `str0095` "Couldn't accept the admin invite. Please try again.", `str106c`/`str2bed` "Couldn't transfer ownership. Please try again(.)/ later.", `str2300`/`str2abd` "Channel admin invite", `str22fb` "Invite %s as admin?", `str2bd8` "Invite as channel admin".

---

## 5. Admin-Invite — Client-zu-Client-Nachricht, nicht nur GraphQL

Der Admin-Invite-UX-Flow hat **zwei** separate Mechanismen, die beide laufen: eine MEX-Mutation (`NewsletterAdminInvite`, serverseitiger Grant) und eine normale end-to-end **1:1-Nachricht**, die das Invite-Payload an den Invitee trägt, unabhängig von MEX aufgebaut.

### 5.1 Proto (found, bestätigt und erweitert das `Messages/newsletterAdminInviteMessage`-Ausgangsmaterial)

`Message.newsletterAdminInviteMessage` — Feld **78** von `Message` (`C30628DTw`), Typ `NewsletterAdminInviteMessage` (obfuskiert `C30596DSq` in 2.26.41.6; JADX-Konstanten an der Klasse selbst, nicht die Feldnummer an `Message`, da die Admin-Invite-Feldkonstante nicht im gegrepten Set war; Feld 78 stimmt mit einer früheren WAProto.proto-Referenz überein und wird unabhängig durch jedes andere Feld unten bestätigt, das exakt wie dokumentiert aufgelöst wird):

| Feld | Nummer | Typ |
|-------|--------|------|
| `newsletterJid` | **1** | string |
| `newsletterName` | **2** | string |
| `jpegThumbnail` | **3** | bytes |
| `caption` | **4** | string |
| `inviteExpiration` | **5** | int64 |
| `contextInfo` | **6** | `ContextInfo` |

Bestätigte Feldnummer-Konstanten `CAPTION_FIELD_NUMBER=4`, `CONTEXT_INFO_FIELD_NUMBER=6`, `INVITE_EXPIRATION_FIELD_NUMBER=5`, `JPEG_THUMBNAIL_FIELD_NUMBER=3`, `NEWSLETTER_JID_FIELD_NUMBER=1`, `NEWSLETTER_NAME_FIELD_NUMBER=2`, direkt von `C30596DSq` gelesen (found) — stimmt exakt mit einer früheren Feldkarte für diese Version überein.

### 5.2 Sendepfad (found, `C9m6` = `UserActionsNewsletterMessaging`)

```java
public final void A00(Context context, C1Y7 c1y7, String name, String caption, HashMap userJidToExpiration) {
    byte[] thumbnail = A01(context, c1y7);           // JPEG of the channel picture, quality 80
    for (entry in userJidToExpiration) {
        C213489Am item = new C213489Am(..., 94, ...); // message-type tag 94
        item.A01 = c1y7;          // newsletterJid
        item.A03 = name;          // newsletterName
        item.A00 = entry.value;   // inviteExpiration
        item.A02 = caption;
        item.A0O(thumbnail, false);
        // enqueued as a normal E2E message to the invitee's UserJid
    }
}
```
Log-Zeile: `"UserActionsNewsletterMessaging/userActionSendNewsletterAdminInviteMessages"`. Pro Invitee wird eine Nachricht gesendet, jede mit ihrem eigenen Expiration-Timestamp — d. h. der Invite ist eine **Per-Recipient-E2E-Nachricht**, während die MEX-`NewsletterAdminInvite`-Op (serverseitig) der maßgebliche Grant-Record ist (inferred Beziehung zwischen den beiden Pfaden; beide im Code vorhanden, Reihenfolge/Abhängigkeit nicht nachvollzogen).

### 5.3 Annahme

Der Client des Invitees ruft `NewsletterAcceptAdminInvite` (MEX) auf. Dessen Request trägt bereits den vollständigen Metadaten-Fetch-Variablensatz (`fetch_followers_count`, `fetch_state`, `fetch_verification`, `fetch_viewer_metadata`, …) — einen Invite anzunehmen und die Channel-Metadaten neu zu fetchen ist ein einziger Roundtrip (found, Variablen aus `X/AbstractC23610Aaw.java`).

---

## 6. Weitere Newsletter-Nachrichten: Follower-Invite, Admin-Profil, geplant

### 6.1 `newsletterFollowerInviteMessage` / `newsletterFollowerInviteMessageV2`

Bestätigt in 2.26.41.6 genau wie im Ausgangsmaterial angegeben, und hier unabhängig neu verifiziert: beide `Message`-Felder existieren (`NEWSLETTER_FOLLOWER_INVITE_MESSAGE_FIELD_NUMBER` = **108**, `NEWSLETTER_FOLLOWER_INVITE_MESSAGE_V2_FIELD_NUMBER` = **113**, beide found als benannte Konstanten auf `C30628DTw`), und **beide mappen auf den identischen Submessage-Typ**, `C30585DSf`:

| Feld | Nummer | Typ |
|-------|--------|------|
| `newsletterJid` | **1** | string |
| `newsletterName` | **2** | string |
| `jpegThumbnail` | **3** | bytes |
| `caption` | **4** | string |
| `contextInfo` | **5** | `ContextInfo` |

Warum beide Feldnummern für einen Typ existieren, ist weiterhin **unknown** — auch in diesem Durchgang wurde kein verhaltenstechnischer Split auf Java-Ebene gefunden (konsistent mit einem früheren Befund).

### 6.2 `newsletterAdminProfileMessage` / `newsletterAdminProfileStatusMessage` / `newsletterScheduledMessage`

Alle drei bestätigt vorhanden als benannte Konstanten auf `C30628DTw` (`NEWSLETTER_ADMIN_PROFILE_MESSAGE_FIELD_NUMBER` = **116**, `NEWSLETTER_ADMIN_PROFILE_STATUS_MESSAGE_FIELD_NUMBER` = **126**, `NEWSLETTER_SCHEDULED_MESSAGE_FIELD_NUMBER` = **132**), und alle drei lösen sich zum selben generischen One-Field-Wrapper-Typ auf, `BD2` (= `FutureProofMessage`):

```java
public final class BD2 { public C30628DTw message_; }   // field "message", number 1, type Message (recursive)
```

Keine feldspezifische Render-/Validator-Klasse existiert für eines der drei (found, deckt sich mit einer früheren Notiz zu `newsletterAdminProfileMessage` und `newsletterScheduledMessage`). `newsletterScheduledMessage` hat jedoch eine dedizierte Nicht-Message-Oberfläche: die lokale Tabelle `newsletter_scheduled_message` (`chat_row_id`, `scheduled_server_id`, unique-indiziert) und das Wire-IQ-Child `<scheduled_messages/>` (Abschnitt 6.3) — das Scheduling-*Feature* ist real und nachvollzogen; nur das Proto-Feld `Message.newsletterScheduledMessage` selbst bleibt ein nicht expandierter Wrapper.

### 6.3 Zugehörige lokale Tabellen

`newsletter_scheduled_message`, `newsletter_admin_profile` (`chat_row_id`, `admin_profile_id`, `timestamp`) stehen hinter `NewsletterAdminProfilesQuery`/`NewsletterAdminProfileUpdate` bzw. der Scheduling-UI (found, `C0SG.java`, `C0S3.java`).

---

## 7. Channel-Posts: Fetch, Senden, Reaktionen, View-Zahlen

### 7.1 XMPP-IQ-Namespace `newsletter` (found, `C9EN`)

Content-Retrieval und einige Write-Actions nutzen einen dedizierten IQ-Namespace, getrennt von MEX:

```xml
<iq xmlns="newsletter" type="get" to="<jid>@newsletter" id="…">
  <messages count="N">
    <smax:any type="jid" jid="<jid>@newsletter" view_role="admin|guest|owner|subscriber"/>
    <before count="N"/> <!-- or <after count="N"/> -->
  </messages>
</iq>
```

| Child-Element | Konstruktor | Zweck |
|---------------|-------------|---------|
| `<messages count/>` + `<before>`/`<after>` | `C9EN(C9EB, C9E2, id, count)` | Channel-Posts paginieren |
| `<message_updates count since/>` | `C9EN(C1Y7, C9E8, Long, id, count)` | Delta-Sync bearbeiteter/gelöschter Posts |
| `<statuses count/>` | `C9EN(C9E9, C9E2, id, count)` | Channel-Status-/Update-Fetch |
| `<status_updates count since/>` | `C9EN(C1Y7, C9EA, Long, id, count)` | Delta-Sync von Status-Posts |
| `<scheduled_messages count/>` | `C9EN(C1Y7, C31085Dfd, id, count)` | ausstehende geplante Posts |
| `<question_responses server_id count/>` (plain und `type="status"`) | `C9EN(...)` | Poll-/Frage-Antworten auf einen Post |
| `<my_question_responses server_id/>` | `C9EN(C1Y7, String, long)` | eigene Antworten des Callers |
| `<my_addons type="status" limit jid/>` | `C9EN(C1Y7, String, int, long)` | eigene Reaktionen/Add-ons des Callers |
| `<live_updates/>` (`type="set"`) | `C9EN(C1Y7, String)` | Live-Push für einen Channel abonnieren |

Das `view_role`-Attribut am `smax:any` trägt den eigenen `C9U4`-Rollenstring des Callers (admin/guest/owner/subscriber) mit jedem Content-Fetch-IQ — der Server scheint Response-Content (z. B. Admin-only-Felder) pro Request zu gaten, statt rein über den Session-Status (inferred).

### 7.2 Senden (found, `SendNewsletterMessageJob`) und View-Receipts

Das Posten in einen Channel nutzt die Standard-Send-Pipeline (hier nicht weiter detailliert; der Job umschließt die normale `<message>`-Stanza-Mechanik). Das Ansehen eines Posts ist explizit und getrennt von Delivery-/Read-Receipts:

```java
// com.whatsapp.newsletter.messages.job.SendViewReceiptJob
<receipt to="<jid>@newsletter" id="…" type="view">
  <list><item server_id="…"/> …</list>
</receipt>
```
Ein `view`-Receipt bündelt mehrere Server-Message-IDs. Das ist der Mechanismus, der den pro-Post **View-Count** in der Channel-UI speist (found; der Zähler selbst ist serverseitig aggregiert — der Client berichtet nur, liest über dieses IQ nie einen Count zurück).

### 7.3 Reaktionen (found)

Reaktionen auf Channel-Posts sind im lokalen Storage **aggregiert, nicht attribuiert**:

```sql
CREATE UNIQUE INDEX newsletter_message_reaction_index
  ON newsletter_message_reaction (message_row_id, reaction);
-- columns include: reaction, reaction_count
```
d. h. eine Zeile pro `(Message, Emoji)`-Paar mit einem laufenden Count, nicht eine Zeile pro reagierendem Nutzer — passend dazu, dass die Channel-UI einen Aggregat-Count pro Emoji zeigt statt einer Liste von Reagierenden wie bei gewöhnlichen Nutzern. `newsletter_my_reaction_orphan_message` (`chat_row_id`, `server_message_id`, unique-indiziert) hält die **eigene** Reaktion des Callers, wenn sie vor dem Post ankommt, auf den sie sich bezieht, zur Abstimmung, sobald der Post eintrifft.

Wer reagiert hat, ist nur für Admins sichtbar, über eine dedizierte MEX-Query:

| Operation | doc_id | Variablen |
|-----------|--------|-----------|
| `NewsletterReactionSendersList` | `25219734117717032` | `server_id` |

Die Reaktions-Policy ist pro Channel konfigurierbar (Abschnitt 8.2, `reaction_codes`): `ALL`, `BASIC`, `BLOCKLIST`, `NONE` (Wire-Strings, siehe `C9U3`/`C9TA` unten).

### 7.4 Follower-/View-Zahlen in Metadaten

`thread_metadata.followers_count` wird als Teil von `NewsletterMetadata` zurückgegeben (Abschnitt 8.1). Es existiert zudem eine dedizierte paginierte Op:

| Operation | doc_id | Variablen |
|-----------|--------|-----------|
| `NewsletterFollowers` | `25646542368289354` | `newsletter_id`, `count` |

Pro-Post-View-Counts werden in diesem Durchgang nicht von einer dokumentierten Standalone-Op zurückgegeben; sie werden als vermutlich innerhalb der per-Message-Metadaten in der `messages`/`message_updates`-IQ-Response liegend eingestuft (Abschnitt 7.1), die hier nicht weiter expandiert wurde (unknown, exakter Feldname).

---

## 8. Channel-Metadaten (GraphQL-Response-Form)

### 8.1 `NewsletterMetadata`-Response (found, Kette `C208048tR → C208038tQ → C208028tP`, GraphQL-Node `xwa2_newsletter`)

```
xwa2_newsletter {
  id
  refresh_after_interval_sec
  state { type }                                    // C9UA
  status_metadata { last_status_sent_time, last_status_server_id }
  thread_metadata {
    creation_time
    description { text, id }
    followers_count
    handle
    invite                                           // invite code / link token
    name { text, id }
    picture { direct_path, type, url, id }
    pinned_messages[]
    preview
    settings { reaction_codes { value } }            // C9U3
    verification                                     // EnumC216369Tx
    verification_source                              // EnumC216219Ti
    wamo_sub { plan_id }
  }
  viewer_metadata {
    role                                             // C9U4
    settings[]                                       // { type, value } = EnumC216349Tv / EnumC216359Tw
    wamo_sub_status                                  // EnumC216229Tj
  }
}
```

### 8.2 Enums (found)

| Enum | Werte (Server-Value-Strings, wo anwendbar) |
|------|---|
| `state.type` (`C9UA`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `DELETED`, `GEOSUSPENDED`, `NON_EXISTING`, `SUSPENDED` |
| `verification` (`EnumC216369Tx`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `UNVERIFIED`, `VERIFIED` |
| `verification_source` (`EnumC216219Ti`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `LEGACY_MANUAL_REVIEW`, `META_VERIFIED_SUBSCRIPTION` |
| `viewer_metadata.role` (`C9U4`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ADMIN`, `GUEST`, `OWNER`, `SUBSCRIBER` |
| `wamo_sub_status` (`EnumC216229Tj`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `INACTIVE` |
| `settings[].type` (`EnumC216349Tv`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `MUTE_ADMIN_ACTIVITY`, `MUTE_FOLLOWER_ACTIVITY` |
| `settings[].value` (`EnumC216359Tw`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `OFF`, `ON` |
| `reaction_codes.value` (`C9U3`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALL`, `BASIC`, `BLOCKLIST`, `NONE` |

Lokale Spiegel an `C2130898y` ("NewsletterInfo"): Verifizierungsstatus `EnumC216079Su` (`NOT_VERIFIED=0`, `VERIFIED=1`), Verifizierungsquelle `C9T1` (`UNKNOWN_VERIFICATION_SOURCE=0`, `META_VERIFIED_SUBSCRIPTION=1`, `LEGACY_MANUAL_REVIEW=2`), Enforcement-Status `C9T2` (`NOT_ENFORCED`, `SUSPENDED`, `GEOSUSPENDED` — für Lesen hinter Flag **3877** in `A0w`/`A0x` gated), lokaler „aktiv"-Status `C9T3` (`NOT_SET`, `INACTIVE`, `ACTIVE`), Migrations-/Erstellungs-Fortschritt `C9T9` (`NOT_STARTED`, `IN_PROGRESS`, `FAILED`, `COMPLETED`), Verzeichnis-Sichtbarkeit `EnumC216039Sq` (`PUBLIC`, `PRIVATE`) und lokale Reaktions-Einstellung `C9TA` (`DEFAULT=0`→Wire `"BASIC"`, `ALL=1`→`"ALL"`, `NONE=2`→`"NONE"`, `BLOCKLIST=3`→`"BLOCKLIST"` — Mapping gelesen aus `UpdateNewsletterGraphqlJob.A0M`).

### 8.3 Update (found, `UpdateNewsletterGraphqlJob` → `NewsletterMetadataUpdate`)

```js
// GraphQl input built for doc_id 27150690864552229
updates: {
  description?: string,   // "" clears
  name?: string,
  picture?: base64,        // "" clears
  admin_profiles_enabled?: { settings: { admin_profiles_enabled, reaction_codes: { value: "ALL"|"BASIC"|"NONE"|"BLOCKLIST" } } }
}
newsletter_id: <jid>
fetch_image: true, fetch_preview: true, fetch_name: true,
fetch_viewer_metadata / fetch_state / fetch_verification / fetch_followers_count: <bool, usually mirrors viewer role>
```

### 8.4 Verifizierungs-UI-Strings (found)

`str136f` "New verified channel", `str2be2`/`str2be3` "Create verified channel"/Icon, `str2c51` "Verified channels", `str2c78` "Your verified badge will be removed from this channel. Your Meta Verified subscription will remain active.", `str2ca9` "Sorry, you cannot change the name of a verified channel from the app. Please contact customer support for assistance." — d. h. verifizierte Channels haben einen serverseitig erzwungenen unveränderlichen Namen (Client-Seite nur UX; Durchsetzung serverseitig unknown).

---

## 9. GraphQL-/MEX-Newsletter-Operationen (doc_ids)

Alle unten aufgeführten doc_ids wurden für diesen Build unabhängig gegen `assets/whatsapp-android-mex_client_persist_ids.json` innerhalb der `WhatsApp_2.26.41.6.apk` neu verifiziert (found — doc_ids sind statische Asset-Einträge, nicht obfuskiert, und über den hier versuchten Versionsvergleich hinweg stabil). In diesem Asset existieren insgesamt 46 `Newsletter*`-Operationen; diejenigen, die nicht an anderer Stelle im Report detailliert sind:

| Operation | doc_id | Zweck (inferred aus Name/Variablen) |
|-----------|--------|------------------------------------------|
| `NewsletterCreate` | `27009199332109318` | Channel erstellen |
| `NewsletterCreateVerified` | `27777918425146464` | vorverifizierten Channel erstellen (privilegierte Accounts) |
| `NewsletterDelete` | `31838460859131915` | Channel löschen |
| `NewsletterUpdateVerification` | `27133493439664458` | Verifizierungsstatus anfragen/aktualisieren |
| `NewsletterHide` / `NewsletterUnhide` | `25033614912931367` / `24551592861177484` | Umschalten der Verzeichnis-Sichtbarkeit (lokal `EnumC216039Sq`) |
| `NewsletterFollowing` | `26856957210673444` | Liste der vom Account gefolgten Channels |
| `NewsletterDirectoryList` / `Search` / `CategoryPreview` | `27480627564903390` / `27887355094203575` / `27432651036395658` | öffentliches Verzeichnis-Browsing |
| `NewsletterSimilar` / `NewsletterRecommended` | `36410329795280256` / `26638880912457992` | Discovery |
| `NewsletterInsights` | `24672564052397921` | Owner-/Admin-Analytics |
| `NewsletterPinMessages` / `NewsletterUnpinMessages` | `28521965914059511` / `37386851567568720` | Pinned-Post-Management (`message_ids`) |
| `NewsletterBlockUser` | `25106066249006236` | Follower blockieren |
| `NewsletterLogExposures` | `24606408825709914` | Directory-Impression-Telemetrie |
| `NewsletterLinkPreviewCheck` | `24188786150796507` | Link-Preview-Domains in Posts validieren |
| `NewsletterPollVoterList` | `24803802869271956` | Poll-Voter auf einem Post (`jid`, `vote_hash`) |
| `NewsletterQuestionResponseStateUpdate` | `24896618076668076` | Q&A-Moderationsstatus |
| `NewsletterLabelAiContent` / `NewsletterLabelPaidPartnership` | `27470054215955630` / `26221505494211174` | Pro-Post-Label „KI-generiert" / „Paid Partnership" |
| `NewsletterChangeWamoSub` / `Enable`/`DisableWamoSub` | `25201342542835866` / `25122474967344830` / `31916794074578680` | WhatsApp-Monetarisierungs-Subscription-Status |
| `NewsletterUserReports` / `NewsletterCreateReportAppeal` | `27149305681394065` / `27792557363683798` | Abuse-Reporting / Einspruch |
| `NewsletterEnforcements` / `NewsletterEnforcementAlertStates` | `27089116857425014` / `27640745535604048` | Enforcement-/Suspension-Status (eigenes Package `com.whatsapp.newsletterenforcements`) |
| `NewsletterUpdateUserSetting` | `24935528202764688` | Per-User-UI-Pref (z. B. Contact-Picker-Tooltip-Count) |
| `FetchNewsletterRankingFeatures` | `24742757908756088` | Ranking-Signal-Fetch (Directory/Recommendation) |

Alle sind `w:mex`-IQs (`type="get"`), Schema `whatsapp_mex`, Transport bestätigt durch das geteilte `C16880is`/`TreeWithGraphQL`-Call-Pattern aus §5–8 (found). Response-Formen über das `NewsletterMetadata` aus §8 hinaus wurden in diesem Durchgang nicht expandiert (unknown).

---

## 10. Storage

| Tabelle | Key-Spalten (found) |
|-------|----------------------|
| `newsletter` | `membership` (indiziert), `invite_code` (indiziert) |
| `newsletter_message` | unique auf `(chat_row_id, server_message_id)`; `is_autodelete_eligible` (indiziert) |
| `newsletter_message_reaction` | unique auf `(message_row_id, reaction)`; `reaction`, `reaction_count` |
| `newsletter_my_reaction_orphan_message` | unique auf `(chat_row_id, server_message_id)` — eigene Reaktion des Callers, die vor ihrem Ziel-Post ankommt |
| `newsletter_admin_profile` | unique auf `(chat_row_id, admin_profile_id)`; `timestamp` (indiziert) |
| `newsletter_subscribers` | indiziert auf `(chat_row_id, type_of_fetch)` |
| `newsletter_scheduled_message` | unique auf `(chat_row_id, scheduled_server_id)` |
| `newsletter_interaction` | indiziert auf `timestamp_ms` und `(newsletter_jid_row_id, timestamp_ms)` |
| `newsletter_linked_account` | indiziert auf `chat_row_id` |
| `newsletter_pinned_message` | indiziert auf `(chat_row_id, pin_timestamp_ms)` |
| `newsletter_media_clear` | unique auf `(chat_row_id, media_type)` |

Geteilte Chat-Infrastruktur (`chat`/`chat_view`, Kernspalten von `message`) wird wie bei jedem `Jid`-typisierten Chat wiederverwendet, genauso wie bei Gruppen/Broadcast-Listen (siehe [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) §3.5) — hier nicht erneut detailliert.

---

## 11. Feature-Flags

IDs, wie an den Call-Sites in `com.whatsapp.newsletter.*` gelesen; Default-Werte nicht alle in diesem Durchgang aufgelöst (markiert, wo bekannt).

| ID | Steuert |
|----|----------|
| **3877** | gated das Lesen der lokalen Enforcement-State-Helper `A0w`/`A0x` (`SUSPENDED`/`GEOSUSPENDED`-Checks) an `C2130898y` |
| **1777** | Länderauswahl in Directory-Filtern |
| **5276** | Channel-Identity-View während Newsletter→Irgendwas-Migrations-UI |
| **6445** | `ShareNewsletterInviteLinkActivity` |
| **6618** | `ViewNewsletterProfilePhoto` |
| **7237** | `NewsletterStatusView` |
| **9096** | `SendNewsletterMessageJob` |
| **12989** | `NewsletterDirectoryCategoriesActivity` |
| **15754** | Perf-Tracker-Marker "messages_fetch_end" in `GetNewsletterMessagesJob` |
| **17985** | `ForwardCounterAcsRepository` (Forwarded-Post-Counter) |
| **19889** | `ForwardCounterApi` |
| **23797** | `NewsletterDescriptionView` |

Exakte Default-Werte und der volle Umfang des gegateten Verhaltens wurden nicht über „Klasse ist nur erreichbar, wenn das Flag an ist" hinaus nachvollzogen (inferred aus der Call-Site-Form); diese Tabelle ist als Karte dafür zu verstehen, wo man suchen muss, nicht als bestätigte An-/Aus-Defaults (unknown für die meisten Zeilen).

---

## 12. Fehlerfälle

| Symptom | Ursache | Fix / erwartetes Verhalten |
|---------|-------|--------------------------|
| "Couldn't follow channel" (`str1c0d`/`str1c0e`) | `NewsletterJoin` fehlgeschlagen oder keine Konnektivität | erneut versuchen; Verbindung prüfen |
| "Couldn't accept the admin invite. Please try again." (`str0095`) | `NewsletterAcceptAdminInvite` fehlgeschlagen | erneut versuchen |
| "Couldn't transfer ownership…" (`str106c`/`str2bed`) | `NewsletterChangeOwner` fehlgeschlagen | später erneut versuchen |
| "Sorry, you cannot change the name of a verified channel from the app." (`str2ca9`) | Channel ist `VERIFIED`; Name client-seitig unveränderlich | Support kontaktieren (serverseitig; genaue Durchsetzung unknown) |
| Eigene Reaktion hat noch keinen passenden Post | Reaktions-Stanza/-Event lief dem eigenen Delivery des Posts voraus | gehalten in `newsletter_my_reaction_orphan_message`, bis der Post eintrifft, dann abgestimmt |
| `state.type` = `SUSPENDED`/`GEOSUSPENDED` | Enforcement-Maßnahme gegen den Channel | Content-Fetch liefert weiterhin `state`; Posten/Admin-Aktionen vermutlich serverseitig blockiert (genaues Gate unknown) |
| `state.type` = `DELETED`/`NON_EXISTING` | Channel gelöscht oder nie existiert | Client sollte die lokale `newsletter`-Zeile verwerfen (Anwendungspfad nicht nachvollzogen) |
| Admin-Invite-Action = `NOT_SUPPORTED` (`EnumC215899Sc`) | Invite/Accept/Revoke in einem nicht unterstützten Kontext versucht (z. B. Rolle, Build) | generischer Fehlerdialog, kein Retry-Button (`str5735`) |

---

## 13. Wichtige Unterscheidungen

| Nicht verwechseln | Unterschied |
|----------------|------------|
| Newsletter (`@newsletter`, Typ 21) vs. Broadcast-Liste (`@broadcast`, Typ 3) | Newsletter: serverseitig gespeichert, nicht E2E, öffentliches Follow-Modell, Rollen; Broadcast-Liste: E2E-Sender-Key-Fan-out ausschließlich an gespeicherte Kontakte — siehe [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) |
| `xmlns="newsletter"`-IQ vs. `w:mex` `Newsletter*`-GraphQL-Ops | IQ = Content-Fetch/Paginierung/Subscription (Messages, Statuses, Scheduled, Live-Updates); MEX = Metadaten, Rollen, Directory, Moderation, Monetarisierung |
| `newsletterAdminInviteMessage` (E2E-1:1-Nachricht, Feld 78) vs. `NewsletterAdminInvite` (MEX-Mutation) | die Nachricht ist die Per-Recipient-Benachrichtigung mit eigener Expiration; die MEX-Op ist der serverseitige Grant — beide existieren, Beziehung inferred |
| `newsletterFollowerInviteMessage` (Feld 108) vs. `newsletterFollowerInviteMessageV2` (Feld 113) | identischer Payload-Typ (`C30585DSf`); Grund für die Duplizierung unknown |
| Lokale Rolle `C9U5` (GUEST/SUBSCRIBED/ADMIN/OWNER) vs. Wire-Rolle `C9U4` (…GUEST/ADMIN/OWNER/SUBSCRIBER) | dieselben vier Rollen, unterschiedliche Ordinal-Reihenfolge und unterschiedliche String-Schreibweise/-Reihenfolge — Ordinal-Kompatibilität nicht annehmen |
| `reaction_codes`-Wire-Value (`ALL`/`BASIC`/`BLOCKLIST`/`NONE`, aus `C9U3`) vs. lokale `C9TA`-Ordinal-zu-String-Karte | lokales Ordinal 0 (`DEFAULT`) serialisiert zum Wire-String `"BASIC"`, nicht `"DEFAULT"` |
| Pro-Post-Reaktions-Storage (`newsletter_message_reaction`, aggregierter Count) vs. normale Nachrichten-Reaktionen | Channels speichern eine Zeile pro `(Message, Emoji)` mit einem Count, nicht eine Zeile pro reagierendem Nutzer |

---

## 14. Vollständiger Flow

```
[Admin]  create channel
    │   NewsletterCreate / NewsletterCreateVerified (MEX) ──► [WA Server] allocates <id>@newsletter
    ▼
[Admin]  set name/description/picture, reaction policy
    │   UpdateNewsletterGraphqlJob ──► NewsletterMetadataUpdate (MEX)
    ▼
[Admin]  invite co-admin
    │   C9m6: per-recipient E2E message (newsletterAdminInviteMessage, field 78, own expiration)
    │   + NewsletterAdminInvite (MEX, server-side grant)
    ▼
[Invitee]  NewsletterAcceptAdminInvite (MEX) ──► role GUEST/SUBSCRIBED → ADMIN (C9U5)

[User]  discover channel (directory / shared link https://whatsapp.com/channel/<code>)
    ▼
[Client]  NewsletterJoin (MEX) ──► role → SUBSCRIBED
    ▼
[Client]  <iq xmlns="newsletter" type="get"><messages count view_role=subscriber/></iq>
    │◄── posts, paginated by before/after server_id
    ▼
[User]  views post ──► <receipt type="view"><list><item server_id/></list></receipt> (view count)
[User]  reacts ──► newsletter_message_reaction (aggregate count, own reaction may be orphaned until post lands)

[Admin]  moderates: NewsletterReactionSendersList (who reacted), NewsletterBlockUser,
         NewsletterPinMessages/Unpin, NewsletterUpdateVerification, NewsletterChangeOwner
    ▼
[Owner]  delete channel ──► NewsletterDelete (MEX)
```

---

## 15. Unknowns

| Punkt | Grund |
|------|--------|
| Exakte Beziehung/Reihenfolge zwischen der E2E-Admin-Invite-Nachricht und dem MEX-`NewsletterAdminInvite`-Grant | beide existieren im Code; welche maßgeblich ist, oder ob eine die andere triggert, nicht nachvollzogen |
| Warum `newsletterFollowerInviteMessage` (108) und `…V2` (113) sich einen Proto-Typ teilen | kein verhaltenstechnischer Split auf Java-Ebene gefunden |
| Feldname/-ort des Pro-Post-View-Counts in der Message-Fetch-Response | inferred, dass er innerhalb des `messages`/`message_updates`-IQ-Payloads existiert; nicht expandiert |
| Serverseitige Durchsetzung des unveränderlichen Namens bei verifizierten Channels | Client zeigt nur einen statischen Fehlerstring |
| Vollständige Response-Form der meisten MEX-Ops über `NewsletterMetadata` hinaus | in diesem Durchgang nicht gelesen |
| Default-Werte für die meisten Feature-Flags in §11 | nur Klassen-Erreichbarkeit, nicht bestätigter Default-Status |
| Traffic / Live-Server-Verhalten | nichts erfasst; nur statische Analyse |

---

## 16. Baileys

Nicht abgedeckt: `baron-baileys-v2` (der Baileys-Fork, der in den anderen Reports dieses Repos als Vergleichsbasis dient) hat zum Zeitpunkt der Erstellung keine bestätigte, gegen diese APK verifizierte Newsletter-/Channel-Implementierung zum Vergleich. Für diesen Report wurde kein Baileys-seitiger Code inspiziert; einen Baileys-Abschnitt ohne geprüfte Fakten hinzuzufügen würde die Evidenzregeln dieses Repos verletzen. Sollte `baron-baileys-v2` künftig Newsletter-Support ausliefern, sollte dieser Abschnitt gegen die JID (Typ 21, Server `newsletter`), die `xmlns="newsletter"`-IQs aus §7.1 und die MEX-doc_ids aus §9 gefüllt werden.
