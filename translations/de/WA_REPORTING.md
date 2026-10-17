<!-- src-sha1: 27b3b625c1ca67d873007881de02f13ba8cbf277 -->
# WhatsApp Reporting — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-17
**Umfang:** Reporting von Nutzern/Kontakten, Gruppen, Channels, Status, Anrufen und Nachrichten — SMAX-`spam`-Stanzas, `spam_list`, Report-Typen, `spam_flow`-Einstiegspunkte, Reporting-Tokens, Content-Upload, Report-/Block-UI, Report-to-Admin, Block-Stanza und Reason-Listen, Server-Fehler, clientseitige Abuse-Signale, Baileys

---

## 1. Was Reporting ist (technisch)

Ein Report ist ein einzelnes IQ `set` an `s.whatsapp.net` im Namespace `spam`. Es trägt einen `spam_list`-Node (gemeldete Entität, gemeldete Nachrichten, Einstiegspunkt, Business-Discovery-Kontext). Der Client serialisiert die gemeldeten Nachrichten als Klartext-Protobuf neu und lädt sie zusammen mit einem Reporting-Token und dem Schlüssel hoch, der ihn verifiziert. Blockieren ist eine separate Stanza (`blocklist`). Report-to-Admin ist eine dritte, davon unabhängige Stanza (`w:g2`).

Alle Aussagen beruhen auf statischer Analyse des dekompilierten APK. Stufe: **found** = im Code gelesen, **inferred** = aus dem Code abgeleitet, **unknown** = nicht aufgelöst. Nichts davon wurde auf der Leitung mitgeschnitten.

| Entität | Name in 2.26.41.6 | Rolle |
|--------|----------------|------|
| IQ-Builder (Mehrzweck, `$t` wählt die Form) | `C9EN` | baut jedes Report-IQ (Typen 0, 18-23) und viele davon unabhängige IQs |
| Reason-/Entry-Point-Node | `C9E2` | `spam_list` mit `spam_flow`, `wi_trace_id`, `is_known_chat`, ... (`xmlns="spam"`) |
| Gruppen-Setting-Child | `C9E1` | `allow_admin_reports` / `not_allow_admin_reports` |
| Content-Wrapper | `C31080DfY` | `raw`, `content_validation`, `reporting_token`, `reporting_token_key` |
| Sonstige Nodes | `C31084Dfc`, `C31085Dfd` | Flags (`multicast`, `url_text`, ...), `biz_opt_out`, `reporting` |
| Serializer ("ReportRpcUtils") | `C33446EhE` | `getMessageMixin` / `getMessageRaw`, Token-Zusammenbau |
| SMAX-Manager | `SpamRPCManager` | `A01`-`A06`, einer pro Report-Art (Paketname nicht obfuskiert) |
| Repo | `SpamReportRepo` | routet nach JID-Klasse, lokale Seiteneffekte |
| RPC-Wrapper | `IndividualSpamReportRpc`, `GroupSpamReportRpc`, `NewsletterSpamReportRpc`, `StatusSpamReportRpc`, `ChannelStatusSpamReportRpc`, `EventSpamReportRpc` | Paket `com.whatsapp.reportinfra.rpc` |
| Origin-Whitelist | `C9ZJ` | validiert den Einstiegspunkt (78 Werte) |
| UI | `ReportSpamDialogFragment` (+ `reportAsSpam$1`, `triggerExtraAction$2`, `ReportSpamDialogViewModel`) | Report-Dialog, optional Block/Leave |
| Block-Executor | `C227489sZ` → `C34631Yx` | `blocklist`-IQ |
| Report-to-Admin | `RtaXmppClient` | `w:g2`-Reports-Queue |
| Token-Store | `C23070uA` | Tabellen `reporting_info`, `reporting_info_content` |

Namen unterscheiden sich je Build; jeder obfuskierte Name oben wurde in 2.26.41.6 anhand stabiler Strings aufgelöst (`spam_list`, `spam_flow`, `reporting_token_key`, `GET_REPORTING_INFO_LIST`, `blocklist`).

---

## 2. Report-Typen

### 2.1 Routing (found)

`SpamReportRepo.A02(contact, status, entryPoint, wiTraceId, messages, includeCallLogs)` verzweigt nach JID-Klasse:

| Gemeldete JID | RPC-Klasse | `SpamRPCManager` | Builder `$t` | Response-Klasse | Log-Label |
|--------------|-----------|------------------|--------------|----------------|-----------|
| ausgewähltes Status-Objekt (`AbstractC31014DeU` non-null) auf einer Newsletter-JID | `ChannelStatusSpamReportRpc` | `A02` | 23 | `C43535Iyq` | StatusReportV2 |
| User (PN, LID, Interop) | `IndividualSpamReportRpc` | `A01` | 20 | `C43534Iyp` | IndividualReport |
| Gruppe | `GroupSpamReportRpc` | `A04` | 19 | `C43538Iyt` | GroupReport |
| ausgewähltes Status-Objekt auf jeder anderen JID, oder Status-JID mit Nachrichtenliste | `StatusSpamReportRpc` | `A05` | 22 | `C43533Iyo` | StatusReport |
| Newsletter/Channel | `NewsletterSpamReportRpc` | `A03` | 21 | `C43536Iyr` | NewsletterReport |
| Event-ID (String) | `EventSpamReportRpc` | `A06` | 18 | `C43537Iys` | EventReport |
| alles andere | keine | keine | keine | keine | `SpamReportRepo: unrecognized jid` geworfen, als Fehlschlag zurückgegeben |
| Bot-Chat | keine (siehe 3.3) | keine | keine | keine | `C214999If` |

Weitere `C9EN`-Formen, die keine Spam-Reports sind: `$t=0` Report an Admins und `$t=1` Umschalten der Gruppeneinstellung (Abschnitt 9), `$t=2` Sub-Group-Vorschläge, `$t=24/25/26` `status`-Nodes. Die Event-RPC wird aus Coroutine-Lambdas aufgerufen (`AYs`, `Aaa`); die auslösende UI ist unknown (Event-Einstiegspunkte `event_home_report` / `event_info_report` existieren, daher sind Event-Reports inferred).

### 2.2 Call-Reports sind User-Reports (found)

`SpamReportRepo.triggerReportCallNonSuspend` (Origin `call_spam_dialog_report`) ruft `IndividualSpamReportRpc.A00` ohne gemeldete `jid`, ohne Nachrichten und mit einem Call-Item auf. Das Call-Item (`C31082Dfa`):

```xml
<call from="<callerJid>" id="<callId>" to="<ownJid>">
  <call_info duration="<s>" terminator="<jid>" start_time="<ts>" adder="<jid>" creator="<jid>"
             terminate_reason="<enum>" reason="<enum>" mediatype="audio|video"/>
</call>
```

`terminate_reason` umfasst `crash, detect_identity_change, ended_by_peer, ended_by_self, ended_by_user, reconnecting, timeout, unknown` und fatale Codec-Fehler. Flag **36386** wählt die Own-JID-Form in `to` (`CUC()` vs `Ask()`, inferred LID vs PN). Ein UI-User-Report mit `shouldIncludeCallLogsInReport` fügt bis zu 5 Call-Log-Items hinzu (`C16430i1.A0B(jid, 5)`).

---

## 3. Client-Flow

### 3.1 Dialog

`ReportSpamDialogFragment` (Bottom-Dialog). Fragment-Args (found): `flow` (der Entry-Point-String, wird zu `spam_flow`), `shouldDeleteChatOnBlock`, `notifyObservableDialogHost`, `upsellCheckboxActionDefault`, `shouldOpenHomeScreenAction`, `showLeaveCheckbox`. `ReportSpamDialogViewModel.initializeSpamDialog$1` lädt den Dialogzustand.

Bei Bestätigung läuft `reportAsSpam$1`:

1. Bot-Chat: RPC überspringen (3.3). Sonst `SpamReportRepo.A02(...)` mit der ausgewählten Nachricht in einer einelementigen Liste (oder ohne).
2. Erfolg trägt eine optionale Report-ID; Fehler zeigt Toast `str3bf8` (oder `C227489sZ.A00`, Log `spamreportmanager/spam/report/no-network-cannot-report`). WAM `wam_spam_report_perf` wird befüllt (11.3).
3. Optionale Zusatzaktion `triggerExtraAction$2` (3.2), Abschlussdialog von `H2U` (10.2), lokale Schreibvorgänge (3.3).

### 3.2 Nur Report vs. Report + Zusatzaktion (found)

Die Checkbox wird auf den String `report` (nicht angehakt) oder `report_block` (angehakt) abgebildet, verwendet für Analytics (`asd.BaC` vs `BaD`) und den Toast nach dem Report. Die Zusatzaktion unterscheidet sich je nach Ziel:

| Ziel | Zusatzaktion bei angehakter Checkbox |
|--------|--------------------------|
| User | Block über `C227489sZ.A01` → `C34631Yx` `blocklist`-IQ (Abschnitt 8), Block-Reason `null`, Entry Point = `flow`, `deleteChat` = Arg `shouldDeleteChatOnBlock` |
| Gruppe | Leave-Group-Task (`C98C` / `C9CI`, ausgeführt mit der Gruppen-JID; Leave-Semantik inferred) |
| Channel | gemeldeten Channel lokal ausblenden (`NewsletterReportCompletionListener`, Flag **25218**), danach Newsletter-Exit/Unfollow-Flow |

Das Report-IQ wird zuerst gesendet; Block/Leave läuft nach der Rückkehr der RPC, unabhängig vom Ergebnis (inferred aus dem Kontrollfluss, keine Erfolgsprüfung vor `triggerExtraAction$2`).

### 3.3 Bot-Chats und lokale Effekte (found)

Bot-Chats überspringen `SpamReportRepo`: Der Client ruft `BotMessageHelper/reportUgc` (`E1J.GENERIC`, `C27847C7h`) auf und wertet es als Erfolg (`C214999If`); Wire-Form unknown. Für andere Chats tut `C24120Ab1` case 4 Folgendes:

| Schritt | Effekt |
|------|--------|
| keine Nachricht ausgewählt | sammelt die letzten **5** Nachrichten des Chats (`C14680f4.A01(..., 5, true)`; System-Zeilen ausgeschlossen, kein `from_me`-Filter in dieser Variante) als gemeldeten Inhalt |
| User-Chat | lokales Log `S3q.A0C(jid, localCode(flow), ...)`, `OptimisedDeliveryConversionLoggingController/handleUserReport`; Flag **20085** steuert `H0J.A00(jid, ...)` (Zweck unknown) |
| nach der RPC | `contacts.is_spam_reported = true` (`ContactManagerDatabase/updateIsReportedSpam`), `C31S.A01(...)`, keine Prüfung des RPC-Ergebnisses im sichtbaren Flow |

---

## 4. Stanza-Envelope und Namespace

### 4.1 Der Reason-Node wird ins IQ gemergt (found)

Die RPCs erzeugen nicht zwei `spam_list`-Geschwister. Der Haupt-`spam_list` (jid, messages) und der Reason-Node `C9E2` (ein `<iq to="s.whatsapp.net" xmlns="spam"><spam_list .../></iq>`-Fragment) werden mit `C10340Uk.A04` kombiniert, das Attribute und gleichnamige Children zusammenführt (widersprüchliche Attributwerte oder Child-Anzahlen brechen den Merge ab). Ergebnis:

```xml
<iq type="set" id="<n..>" to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<reported>" spam_flow="<entry point>" wi_trace_id="<24 chars>">
    ...children...
  </spam_list>
</iq>
```

Beleg: `C9EN`-Konstruktoren für 18-23 rufen `C9E2.A00(iq, reasonNode)` = `iq.A04(node)` auf; `C9E2` case 5 baut `iq{to, xmlns="spam"} > spam_list{wi_trace_id, spam_flow}`; `C19380nJ.A00.getServer() = "s.whatsapp.net"`. Die IQ-`id` stammt von `MessageClientSmaxWrapper.A01()` (`n<hex counter>`, `C10140Tq.A0H`). Send-Timeout 32000 ms (`A0F(node, id, cont, type, 32000, ...)`); eine null-Antwort (Timeout/Zustellfehler) wird zu `C216549Uq`.

Typen 0 und 1 setzen `xmlns="w:g2"` und `to=<group>` wörtlich; Typen 18-23 bauen `<iq type="set">` und verlassen sich für `to` und `xmlns` auf den Merge. Die an den Sender übergebene Type-ID ist **98** (Gruppe, Newsletter, Event) und **385** (Report-to-Admin).

### 4.2 Optionale Geschwister, die in `spam_list` gemergt werden

| Node/Attr | Quelle | Gate | Stufe |
|-----------|--------|------|------|
| `spam_flow` | `flow`-Arg, normalisiert durch `C9ZJ` | immer | found |
| `wi_trace_id` (genau 24 Zeichen) | `$wiTraceId` von `reportAsSpam$1` | optional | found; Ursprung des Werts unknown |
| `is_known_chat` = `"true"`/`"false"` | `C33446EhE.A09` | Flag **22256**; User: Adressbuch-Prüfung, Gruppe: Gruppenmitgliedschafts-Prüfung | found |
| `biz_opt_out`-Child | `C33446EhE.A07` | Business-Discovery-Eintrag existiert | found (siehe 8.3) |

---

## 5. Stanzas pro Typ

`from`/`to` eines `<message>`-Items: für den User-Pfad setzt der anonyme Node `C9E4` `to=<jid>`, wenn die Nachricht ausgehend ist (`key.fromMe`), sonst `from=<jid>`. Anzahlen sind Builder-Gates (`AbstractC10350Ul.A07`).

### 5.1 User (Typ 20)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<userJid>" spam_flow="chat" wi_trace_id="...">   <!-- jid: UserJid or interop jid (C99O) -->
    <message from|to="<userJid>" t id deleted_reason>              <!-- 0..210 items -->
      <raw v="2" local_message_type="<int>" mediatype="<enum>"><proto bytes></raw>
      <content_validation type="e2e_proto_message|mms_retry|plaintext_v3">
        <reporting_token v="<n>"><tag, min 6 bytes></reporting_token>
        <reporting_token_key><key, 16-32 bytes></reporting_token_key>
      </content_validation>
    </message>
    <call .../>                                                    <!-- 0..5 items, section 2.2 -->
    <extension_screen extension_id session_id t name entry_point>  <!-- 0..5, business Flows context (A0B), data child -->
    <biz_opt_out business_discovery_timestamp business_discovery_id business_discovery_entry_point/>
  </spam_list>
</iq>
```

Der Builder nimmt drei Item-Listen mit Obergrenzen 210 (Nachrichten), 5 (Call-Items), 5 (nachrichtenlose Business-Flow-Items, `C33446EhE.A0B`: letzte 5 Einträge des Per-Business-Stores `messageless_flow_ids_per_business_<jid>`, Node `extension_screen`). `jid` wird nur gegen `UserJid` und `C99O` validiert; kein `subject` auf diesem Pfad.

### 5.2 Gruppe (Typ 19)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<groupJid>" source="<adderJid?>" subject="<group name>" spam_flow="group_info_report">
    <message from="<senderJid>" t id>...</message>     <!-- 0..210 -->
  </spam_list>
</iq>
```

- `source` ist **der User, der den Melder zur Gruppe hinzugefügt hat**, nicht der Melder. Es wird aus der lokalen Systemnachricht ("me joined") per SQL `GET_GROUP_ADDER_JID_SQL` gelesen (`C16100hT.A01`, `action_type` 12/124/144/127, `is_me_joined = 1`). Optional. (found)
- `subject` ist der Anzeigename der Gruppe aus dem Kontakteintrag (`C06290Dn.A07().A00.A0b`; Feldbedeutung inferred), leerer String `""` für Community-Parent-Gruppen oder wenn kein Eintrag existiert (`Voip.REJECT_REASON_DECLINED` ist `""`). Es ist kein Grund. Längen-Gate 0..65536. (found)
- Eine vierte Liste im Konstruktor wirft (`getNode`), wenn sie nicht leer ist; die RPC übergibt eine leere Liste.

### 5.3 Newsletter (Typ 21) und Status-Post (Typ 22)

```xml
<spam_list jid="<newsletterJid>" subject="<channel name or ''>" spam_flow="newsletter_info_report">
  <message from="<newsletterJid>">...</message>        <!-- 0..65 -->
</spam_list>
<spam_list jid="<statusPosterJid>" spam_flow="status_post_report">
  <message from="<posterJid>">...</message>           <!-- 1..2 items, only the first selected status is passed -->
  <biz_opt_out .../>                                   <!-- optional -->
</spam_list>
```

Newsletter-`subject` = Channel-Name (`C2130898y.A0j`), `""` wenn unbekannt (found). Status-Reports nutzen eigene Token-Tabellen `status_reporting_info` / `status_reporting_content`.

### 5.4 Channel-Status V2 (Typ 23)

```xml
<spam_list jid="<newsletterJid>" spam_flow="...">
  <status server_id="<99..2147476647>" t="<1577865600..4102473600>">...</status>
</spam_list>
```

Der Status wird über `server_id` + Timestamp identifiziert, kein hochgeladener Inhalt. Der Inhalt des `status`-Childs (`InterfaceC35700FdB`) ist nicht aufgelöst.

### 5.5 Event (Typ 18)

`<spam_list event_id="<1..64 chars>" spam_flow="..."/>`, keine `wi_trace_id` (Ein-Argument-Pfad `C9E2(String)`). Nachricht an Admins (Typ 0): Abschnitt 9.1.

---

## 6. Gemeldeter Inhalt und Tokens

### 6.1 Was hochgeladen wird (found)

`C33446EhE.A0A(fmsg, entryPoint)` baut ein Message-Item pro gemeldeter Nachricht:

| Teil | Detail |
|------|--------|
| `<message>`-Attrs | `t` (Nachrichten-Timestamp, 0..2^53), `id` (Stanza-ID), `from`/`to`-jid, `deleted_reason` = `view_once_opened` / `view_once_expired` |
| `<raw v="2" local_message_type mediatype>` | neu serialisiertes `Message`-Protobuf (`C30628DTw` mit `MessageContextInfo` `C30624DTs`); `local_message_type` = interner Nachrichtentyp-Int |
| `<content_validation>` | Token + Key (6.2) |
| Meta-Flags | `<edit v="1">` (bearbeitet), `<multicast/>` (Broadcast-Flag 64), `<url_number/>` (Flag 4), `<url_text/>` (Flag 2), Template-ID, `hsm` tid, `iab reported_link`, `original_sender` / `group_history_sender`, `futureproof`/`request`/`send`-Payment-Varianten (`pay`), `reported_push_name` |
| `<reporting>`-Child | Flag **5718**: aus den `reporting_info`-Zeilen der Nachricht gebaut (`C23070uA.A03`), bis zu 1000 Einträge (`C31085Dfd` case 28); Schema pro Eintrag nicht vollständig gelesen |
| alternative Träger | `<plaintext>`, `<enc type=msg|pkmsg|skmsg|media|text>`, `<reporting_content>` (`C31084Dfc`, `C31081DfZ`) |

`mediatype` (33 Werte, found): `audio, avatar_sticker, buttons_response, catalog, cataloglink, collection, contact, contact_array, document, genai_sticker, gif, image, invite, list, list_response, livelocation, location, native_flow_response, order, product, productlink, product_list, ptt, ptv, sticker, sticker_pack, system, unknown, url, user_created_sticker, vcard, video, 1p_sticker`.

OTP-Template-Nachrichten: Der Platzhalter `<code>` in Button-Titeln wird vor der Serialisierung durch den echten Code ersetzt (`AbstractC32303E8u.A00`). View-once: Ist die Nachricht View-once und bereits geöffnet/abgelaufen und der Origin nicht `media_viewer` / `view_once_viewer`, ist `A06` true und der Serialisierungsblock wird übersprungen. Ob das Item dann ein leeres oder fehlendes `raw` trägt, ist inferred (Deklaration im Decompile nicht initialisiert).

Mediendateien werden von dieser Stanza nicht erneut hochgeladen; die serialisierte Nachricht trägt die Medienreferenzen (inferred; kein Upload-Aufruf gefunden). Die Stanza enthält das Klartext-Proto und den Key zusammen, sodass der Server den Inhalt lesen kann: Nodes **found**, Lesbarkeit **inferred**.

### 6.2 Reporting-Token und Key (found)

```xml
<content_validation type="e2e_proto_message">          <!-- "mms_retry" when the stored token row has retry mode 1 -->
  <reporting_token v="<int>"><tag, >=6 bytes></reporting_token>
  <reporting_token_key><key, 16..32 bytes></reporting_token_key>
</content_validation>
```

Zusammengebaut in `C33446EhE.A03` aus der gespeicherten Zeile (`C34539Ez0`): Token-Bytes (`A05`), Version (`A02`), Stanza-ID (`A03`), Key (`A07`). Fehlt der Key, wird er neu abgeleitet: `C33364Efs.A06(chat, sender, stanzaId, messageSecret)` → nativ `WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)` (Use-Case-ID **5**; Nicht-User-Chats laufen über `JniBridge`-Varianten). Fehlen sowohl der Key als auch ein 6-Byte-Token bzw. sind sie null, loggt der Client `ReportingToken/MissingFkAtReport` und verwendet einen 32-Byte-Key aus lauter Nullen. Ein fehlender Token liefert `null` (`ReportingToken is null`, Item ohne `content_validation`).

### 6.3 Token-Lebenszyklus (found, sofern nicht anders vermerkt)

| Phase | Detail |
|-------|--------|
| Ausgehende Nachricht | Builder `C35241aW.A00(token16, v)` → `<reporting><reporting_token v="<n>">16 bytes</reporting_token></reporting>`. Token = erste 16 Bytes von `HMAC-SHA256(key, canonicalContent)` (`C35241aW.A04`, `AbstractC38971i1.A00`). `canonicalContent` = Message-Proto mit versionsabhängiger Feldfilterung (`A07`, entfernt ausgewählte Subfelder von Feld 35; Lesart inferred). Aufrufer des Builders nicht verfolgt |
| Group-History-Share | `F6C` (`GhsReportingTokenMessageSendStanzaContributor`): für Nachrichten vom Typ 117 `<reporting>` mit einem Child pro Eintrag (Attr `id`, Child `<reporting_token v>`) |
| Eingehende Nachricht | Stanza-Child `<reporting validation_policy?><reporting_tag>BYTES</reporting_tag><reporting_token v>BYTES</reporting_token></reporting>`, geparst von `C34764F6h` / `C1S0`, Flag **5718**; Tag und Token jeweils optional, Tag erforderlich |
| Speicherung | Tabellen `reporting_info` (`reporting_tag`, `stanza_id`, `is_message_add_on`, `send_timestamp`, `receive_flow`) und `reporting_info_content` (`reporting_token`, `reporting_token_content`, `reporting_token_version`, `reporting_token_key`); `message_conditional_reveal.reporting_token_info` (Blob); `group_history_share_reporting_info`; `status_reporting_info` |
| History | `WebMessageInfo.reportingTokenInfo` Feld **62** = `ReportingTokenInfo` (`DR0`): `reportingTag` **1** bytes, `reportingTagTimestamp` **2** uint64; Flag **6578** |
| Cleanup | `reporting_info*`-Zeilen werden gelöscht, wenn `receive_timestamp` älter als ein Cutoff ist (`FP7` case 6); Cutoff-Wert nicht aufgelöst |
| Alternativer Validierungs-Node | `<reporting_validation><reporting_tag id ts_s participant>bytes</reporting_tag></reporting_validation>` (`C31081DfZ`) |

Wer `reporting_tag` ausstellt und wie der Server den Token verifiziert: serverseitig, unknown. Die Paarung (Tag in der Stanza, Token+Key im Report) ist inferred.

---

## 7. `spam_flow`-Einstiegspunkte

97 Werte (found, `C9E2` case 5, Reihenfolge = Array-Reihenfolge). Das `flow`-Arg wird durch `C9ZJ.A00` geleitet, das **78** davon akzeptiert und sonst `IllegalArgumentException("Invalid BlockSpamReportOrigin value")` wirft. Alle sechs RPC-Wrapper rufen es auf, und `SpamReportRepo.A02` fängt die Exception ab und gibt einen Fehlschlag zurück (clientseitiger Fehler, keine Stanza gesendet). Die 78 sind eine echte Teilmenge der 97. Die 19 abgelehnten Werte: `account_info, account_info_report_as_guest_user, block_dialog, call_log, call_spam_dialog_block, channel_status_report, chat_fmx_card_report_as_guest_user, chat_list_context_menu_block, chat_list_swipe_delete_block_upsell, chat_list_swipe_delete_report_upsell, ent_client, frx, group_chatlist_swipe_leave_report_upsell, group_info, guest_call_participant_report, guest_call_report, overflow_menu, overflow_menu_community_report, payment_transaction_report`. Das sind vermutlich reine Block- oder RPC-fremde Origins (inferred). `channel_status_report` ist im Enum, wird aber von `C9ZJ` abgelehnt; welchen Flow der Channel-Status-Aufrufer übergibt, ist unknown.

| Oberfläche | Werte |
|---------|--------|
| Chat / 1:1 | `chat`, `message_menu`, `overflow_menu`, `overflow_menu_report`, `overflow_menu_block`, `block_dialog`, `block_header_chat`, `chat_list_block`, `chat_list_context_menu_block`, `chat_list_noinsub_block`, `chat_list_swipe_delete_block_upsell`, `chat_list_swipe_delete_report_upsell`, `triggered_block`, `notification_block`, `missed_call_notification_block`, `feedback_not_interested_block`, `user_controls_stop_block`, `media_viewer`, `view_once_viewer`, `account_info`, `account_info_block`, `account_info_report`, `account_info_report_as_guest_user`, `album_media_menu_report`, `iab_menu_report`, `extension_menu_report`, `comment_actions_bottom_sheet`, `payment_transaction_report` |
| Spam-Banner | `1_1_spam_banner_block`, `1_1_spam_banner_report`, `1_1_old_spam_banner_block`, `one_to_one_spam_banner_block_server_flagged_suspicious`, `user_initiated_chat_suspicious_banner_block`, `user_initiated_chat_suspicious_banner_safety_tools_block`, `user_initiated_chat_suspicious_banner_safety_tools_report`, `dependant_chat_request_banner_decline_report_upsell`, `dependant_unknown_conversation_trust_signals_block` |
| FMX-Safety-Cards | `chat_fmx_card_block`, `chat_fmx_card_block_suspicious`, `chat_fmx_card_block_server_flagged_suspicious`, `chat_fmx_card_report_as_guest_user`, `chat_fmx_card_safety_tools_block`, `..._block_suspicious`, `..._report`, `..._report_suspicious`, `user_initiated_chat_fmx_card_safety_tools_block`, `..._report`, `trust_question_bottomsheet_block_server_flagged_suspicious` |
| On-Device-Scam-Alerts | `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_bottom_sheet_block`, `odml_scam_alert_bottom_sheet_trust`, `odml_scam_alert_fmx_card_block`, `odml_scam_alert_fmx_card_trust`, `odml_scam_alert_suspicious_banner_block`, `odml_scam_alert_suspicious_banner_trust` |
| Gruppe | `group_info`, `group_info_report`, `group_info_leave_report_upsell`, `group_spam_banner_exit`, `group_spam_banner_exit_group_history`, `group_spam_banner_report`, `left_group_spam_banner_report`, `group_safety_check_bottom_sheet`, `group_fmx_card_leave`, `group_fmx_card_leave_non_suspicious`, `group_chatlist_leave_report_upsell`, `group_chatlist_swipe_leave_report_upsell`, `group_overflow_menu_leave_report_upsell`, `community_home`, `community_announcement_group_suspicious_banner_exit_dialog`, `community_home_suspicious_banner_exit_dialog`, `overflow_menu_community_report` |
| Anrufe | `call_log`, `call_log_block`, `call_detail_overflow_report`, `call_detail_safety_tools_block`, `call_detail_safety_tools_report`, `call_spam_dialog_block`, `call_spam_dialog_report`, `guest_call_report`, `guest_call_participant_report` |
| Channels / Status / Events | `newsletter_info_report`, `newsletter_question_response_report`, `channel_status_report`, `status_post_report`, `status_question_answer`, `wamo_channel_report`, `event_home_report`, `event_info_report` |
| Business | `biz_account_info_block`, `biz_block_header_chat`, `biz_block_list`, `biz_call_log_block`, `biz_overflow_menu_block`, `biz_spam_banner_block`, `ent_client`, `frx` |

Die Wahl zwischen `*_suspicious` und der einfachen Variante für FMX-Cards erfolgt in `C230769yA.A05` anhand von `A0D(userJid)` (Kontakt bekannt oder nicht); dieses Prädikat ist inferred ein Adressbuch-Check. Die `server_flagged`-Varianten werden nach Card-Typ gewählt; woher das Server-Flag stammt, ist unknown.

`wi_trace_id`: optionales 24-Zeichen-Attribut, vom Aufrufer durchgereicht; sein Generator wurde nicht gefunden (unknown). Es ist auch ein Feld von WAM `wam_spam_report_perf` (11.3).

---

## 8. Block, Reasons und Business-Kontext

### 8.1 Block-IQ (found, Bereich `C34631Yx.A0M`)

```xml
<iq to="s.whatsapp.net" id="<id>" type="set" xmlns="blocklist">
  <item action="block|unblock" jid="<chat jid>" dhash="<list hash?>" pn_jid|username|display_name|unknown_identifier="...">
    <biz_opt_out first_message="true|false|none" reason="<code>" reason_description="<text>"
                 entry_point="<flow>" business_discovery_entry_point business_discovery_timestamp business_discovery_id/>
  </item>
  <entry_point source="<flow>"/>
</iq>
```

`biz_opt_out` und `entry_point` werden nur für `action="block"` ausgegeben. `jid` wird per Settings-Prüfung zwischen PN- und LID-Form gewählt (`zA02`-Zweig; genaue Regel nicht vollständig gelesen); bei einem Block ist der zusätzliche Identifier einer von `pn_jid` / `username` / `display_name` / `unknown_identifier="true"`. Timeout 20000 ms. Entry Points, die mit `odml_scam_alert_*` beginnen, werden zu `1_1_spam_banner_block` umgeschrieben (`odml_scam_alert_fmx_card_block` → `chat_fmx_card_block`). PSA-Chats nutzen ein anderes IQ (`xmlns="w:comms:chat"`, `<blocking action>`). Abruf: `type="get"`, optional `<item dhash>`.

### 8.2 Block-Reasons (found)

Hartcodierter String → lokaler Int in `AbstractC227579sl.A00`: `no_longer_needed`/`no_longer_interested` = 1, `no_sign_up` = 2, `spam` = 3, `offensive_messages` = 4, `otp_did_not_request` = 5, `scam_or_fraud` = 6, other = 0. `RunnableC40792Hpk` bildet dieselben Strings auf ein zweites Code-Set ab. Diese Ints fließen in lokale Log-Aufrufe; ob sie einen Server erreichen, ist unknown.

Business-Block-Sheet (`C24126Ab7`): Server-Reason-Map, falls nicht leer, sonst `no_longer_needed, no_sign_up, spam, scam_or_fraud, other`; OTP-Template-Chats: `no_longer_interested, otp_did_not_request, other`.

### 8.3 Business-Discovery-Kontext (found)

`C33446EhE.A07` liest den Business-Discovery-Eintrag für die gemeldete JID (Store `LA8`): Timestamp, ID, Entry Point. Entry-Point-Enum (18 + `unknown`): `biz_profile, broadcast_list_context_menu, catalog_link, click_to_chat_link, contact_card, contact_search, ctwa, global_search_new_chat, group_participant_list, message_short_link, other_qbm, otp_qbm, phone_number_hyperlink, product_link, promotional_qbm, qr_code, status, transactional_qbm`. Er wird sowohl an Reports (`biz_opt_out` unter `spam_list`) als auch an Blocks angehängt. Das sind die einzigen Signale darüber, wie ein Chat begann, die im Client gefunden wurden.

### 8.4 Report-Reason-Listen (found)

Nur Business-Ads haben eine auswählbare Liste. `ReportReasonListFragment` startet leer und wird gefüllt aus `<iq xmlns="w:biz" type="get"><mobile_config name="biz_report_reasons" v="1" report_type="status_ad|business_user"/></iq>` (Antwort `mobile_config` > `list` mit `name`, `v`, `country`). Hartcodiertes Fallback-Enum (`EnumC37888GeT`): `scam_or_fraud`, `pretending_impersonation`, `illegal_dangerous`, `inappropriate_hateful_violent`, `dont_like_ad`. Wann der Fallback genutzt wird: inferred als Server-Liste nicht verfügbar. Es gibt keinen Reason-Picker für gewöhnliche User-/Gruppen-/Nachrichten-Reports; der einzige "Grund" auf der Leitung ist `spam_flow`.

---

## 9. Report an Gruppenadmins

### 9.1 Senden und Abrufen (found, `RtaXmppClient`)

```xml
<!-- reportMessageToAdmin, type 0, smax 385 -->
<iq to="<groupJid>" type="set" xmlns="w:g2" id><reports><report message_id="<stanza id>"/></reports></iq>

<!-- getReportedMessages, admin side -->
<iq to="<groupJid>" type="get" xmlns="w:g2" id><reports/></iq>
<!-- response: report{message_id} > reporter{jid, timestamp} x1..19999 -->
```

Es werden weder Inhalt, Token noch `spam_flow` gesendet; nur die Message-ID. Fehler loggen nur `Rta::<op>/onError: <code>` oder `/onDeliveryFailure: Network Failure`.

### 9.2 Member-Report-Toggle (found)

`$t=1`: `<iq to="<groupJid>" type="set" xmlns="w:g2"><allow_admin_reports/></iq>` (aktivieren) oder `<not_allow_admin_reports/>` (deaktivieren), smax 384. Die Nodes sind direkte Children des IQ, nicht in einen `group`-Node gewickelt. Der Builder akzeptiert bis zu vier Setting-Geschwister-Nodes in einem IQ.

---

## 10. Server-Antwort und Abschlussdialoge

### 10.1 Antwort (found)

Erfolg (`type=result`): Child `report` mit Attribut `id` (max. 20 Zeichen) → `C213959Ch.A01` → als Report-ID an die UI zurückgegeben. Fehler (`<error code text>`), pro Response-Klasse:

| Code | Name | Individual | Group | Newsletter | Status | Status V2 | Event |
|------|------|------------|-------|------------|--------|-----------|-------|
| 400 | `bad-request` | x | x | x | x | x | x |
| 403 | `forbidden` | x | | | x | x | |
| 429 | `rate-overlimit` | x | | | x | x | |
| 500 | `internal-server-error` | x | x | x | x | x | x |
| 501 | `feature-not-implemented` | x | x | | | | x |
| 548 | `report-token-validation-fail` | x | x | | x | | x |

### 10.2 Abschlussdialoge

`H2U` entscheidet anhand der Report-ID und der Gates, dann baut `C5BD` das Fragment (`arg_report_id`, `arg_is_ad_report`):

| Gate | Dialog |
|------|--------|
| Flag **25818**, User-Chat, Nachricht vorhanden | `NciiCompletionDialogFragment` |
| Flag **6145** | `DsaCompletionDialogFragment` (EU) |
| Flag **14249** | `UkOsaCompletionDialogFragment` |
| Flags **12987** / **12990** | `AustraliaOsaCompletionDialogFragment` |

Alle außer NCII benötigen eine nicht-null Report-ID; ohne ID kein Dialog.

---

## 11. Abuse-Signale im Client

### 11.1 Was der Client über den Inhalt hinaus sendet (found)

Entry Points mit `*_server_flagged_suspicious` bedeuten, dass die Card für einen Chat angezeigt wurde, der durch ein anderes Signal als den lokalen Kontakt-Check markiert war; wie der Client dieses Flag erfährt, ist unknown. In Reports gesendet: `is_known_chat`, `biz_opt_out` (wie der Business-Chat begann), Call-Items (Dauer, wer beendet hat, Terminate-Reason), Business-Flows-`extension_screen`-Kontext, `source` (wer mich zur Gruppe hinzugefügt hat), `reported_push_name`, Forward-/Broadcast-/URL-Flags pro Nachricht, Edited-Flag, View-once-Zustand, Entry Point, optionale `wi_trace_id`.

### 11.2 On-Device-Scam-Erkennung (found, eingegrenzt)

`com.whatsapp.integrityai` führt ein heruntergeladenes Modell-Set (`scam_detection`) auf dem Gerät über ExecuTorch aus (`ScamDetectorImpl`, `EmbeddingProviderImpl`, `InputFeatureProviderImpl`; Features `mostRecentSenderScore`, `isCountryMismatch`). Ergebnisse steuern Warn-Banner/-Sheets und die oben genannten `odml_scam_alert_*`-Entry-Points. Ein lokaler JSON-Scan-Record (`outcome`, `inputs`, `model_info`, `verification`) wird in einen `FileStash` geschrieben, wenn `integrity_warning_report_enabled` (`C57375Pog`). Kein Upload dieses Records gefunden (unknown). Er ist unabhängig von der `spam`-Report-Stanza.

### 11.3 Telemetrie (found)

WAM `wam_spam_report_perf` (`C97R`, id 6310): `dedup_key`, `report_attempt_count`, `report_duration_ms`, `report_error_code`, `report_spam_flow`, `report_status`, `wi_trace_id`. Fehlercode-Mapping in `reportAsSpam$1`: Abbruch -4, Timeout/keine Antwort -1, sonstige Exception -3, Protokollfehler = IQ-Fehlercode.

---

## 12. Baileys

Das Paket `baron-baileys-v2` hat keine Report-API. Die folgenden Formen stammen aus den gefundenen Nodes und sind untested.

```ts
// report to group admins (smallest, no token needed)
await sock.query({
  tag: 'iq',
  attrs: { to: groupJid, type: 'set', xmlns: 'w:g2' },
  content: [{ tag: 'reports', attrs: {}, content: [
    { tag: 'report', attrs: { message_id: stanzaId } } ] }]
})
```

Report-Formen für User/Gruppe/Channel folgen Abschnitt 5 (ein gemergter `spam_list`, `xmlns: 'spam'`, `to: 's.whatsapp.net'`).

| Warum es fehlschlägt (alles inferred) | Ursache | Behebung |
|--------------|-------|-----|
| Fehler 548 oder stilles No-op | kein gültiger Reporting-Token/-Key: Baileys verwirft das `<reporting>`-Child eingehender Nachrichten und leitet den Key nie ab | `reporting_tag`/`reporting_token` beim Empfang parsen, pro Nachricht speichern, Key zur Report-Zeit aus `messageSecret` ableiten (Use Case 5) |
| 400 | `jid` der falschen Klasse (muss für Typ 20 User/Interop sein), Item-Anzahlen über den Obergrenzen, `spam_flow` falscher Typ | `spam_flow`-Strings aus Abschnitt 7 verwenden; unter 210 / 5 Items bleiben |
| IQ abgelehnt | zwei `spam_list`-Geschwister (Reason als zweiter Node gesendet) statt eines gemergten Nodes | einen `spam_list` mit allen Attributen senden |

`wi_trace_id` und `is_known_chat` sind im Builder beide optional; ob der Server Reports mit erfundenen Tokens akzeptiert, ist unknown.

---

## 13. Fehlerfälle

| Symptom | Ursache | Stufe |
|---------|-------|------|
| Toast `str3bf8`, nichts gesendet | `C9ZJ` hat den `flow`-Wert abgelehnt (`Invalid BlockSpamReportOrigin value`) | found |
| Fehlschlag `unrecognized jid` | Chat-JID ist weder User/Gruppe/Status/Newsletter | found |
| Report "schlägt fehl" ohne Toast | Server-Fehler 548: `C9ZI.A00` gibt dasselbe Nicht-Fehler-Ergebnisobjekt zurück wie der Bot-Pfad | found |
| generischer Fehler-Toast | 400/403/429/500/501 oder Timeout (32 s) → `C216549Uq` | found |
| Report-Inhalt fehlt | View-once geöffnet/abgelaufen und Origin kein Viewer; Nachricht hat keinen gespeicherten Token | found / inferred |
| lokaler Zustand sagt gemeldet, Server hat abgelehnt | `is_spam_reported` wird nach der RPC ohne sichtbare Ergebnisprüfung geschrieben | found (Flow), inferred (Folge) |

---

## 14. Wichtige Unterscheidungen

| Nicht verwechseln | Mit |
|----------------|------|
| `spam_list@source` | dem Melder. Es ist der User, der den Melder zur Gruppe hinzugefügt hat |
| `spam_list@subject` (Gruppe, Channel) | einem Grund. Es ist der Gruppen-/Channel-Name |
| `spam_flow` | einem Report-Grund. Es ist die UI-Oberfläche, die den Report ausgelöst hat (97 Werte) |
| Report (xmlns `spam`) | Block (xmlns `blocklist`), Report-to-Admin (xmlns `w:g2`), Marketing-Opt-out (xmlns `optoutlist`, `C31105Dfx`, nicht weiter analysiert) |
| zwei `spam_list`-Nodes | ein gemergter `spam_list` (Attribute und Children kombiniert) |
| Call-Spam | Event-Spam. Call-Reports sind Typ 20 mit einem `call`-Item; Typ 18 ist `event_id` |
| `reporting_tag` (vom Server ausgestellt, beim Empfang gespeichert) | `reporting_token` (16-Byte-HMAC, mit ausgehenden Nachrichten gesendet und in Reports hochgeladen) und `reporting_token_key` (abgeleitet, hochgeladen) |
| Report-to-Admin | Report an WhatsApp. Der Admin-Report sendet nur `message_id`; kein Inhalt, kein Token |
| `wi_trace_id` (vom Client gesendete Trace-ID) | der Report-ID, die der Server in `<report id>` zurückgibt |
| `report_block` | ein Wire-Wert. Es ist ein Client-Analytics-/Toast-String; Blockieren ist ein eigenes IQ |
| `allow_admin_reports`-Toggle (`$t=1`) | Report-to-Admin-Nachricht (`$t=0`) |

---

## 15. End-to-End-Flow

```
[User]                  [Client]                                        [WhatsApp server]
  │ Report / Block+Report    │                                               │
  ├────────────────────────▶│ ReportSpamDialogFragment(flow = spam_flow)     │
  │ confirm (+block/leave)   │ reportAsSpam$1                                │
  │                          │  bot chat ──▶ BotMessageHelper/reportUgc      │
  │                          │ SpamReportRepo.A02: route by JID class        │
  │                          │  C9ZJ(flow) ──✗ IllegalArgumentException      │
  │                          │  no message ──▶ last 5 messages from DB       │
  │                          │ serialize msgs (EhE) + token + key,           │
  │                          │ is_known_chat, biz_opt_out, call items        │
  │                          │ C9EN + C9E2 merged into ONE spam_list         │
  │                          │ ── iq set xmlns=spam to=s.whatsapp.net ─────▶│
  │                          │                                   verify token│
  │                          │◀── result <report id> | error 400/403/429/    │
  │                          │    500/501/548 (548 treated as success)       │
  │                          │ WAM wam_spam_report_perf                      │
  │                          │ contacts.is_spam_reported = 1                 │
  │                          │ extra action:                                 │
  │                          │  user ── iq set xmlns=blocklist (block) ────▶│
  │                          │  group ─ leave   channel ─ hide + exit        │
  │◀─ completion dialog (DSA / UK OSA / AU OSA / NCII; needs report id)      │
  │                                                                          │
  │ member: iq set xmlns=w:g2 to=group reports>report{message_id} ──────────▶│
  │ admin : iq get xmlns=w:g2 to=group <reports/> ◀── report > reporter      │
```

---

## 16. Unknown

| Punkt | Grund |
|------|--------|
| Serverseitige Token-Verifikation, Ausstellung von `reporting_tag`, wie `server_flagged` entschieden wird | Serverlogik, nicht im APK |
| Ursprung von `wi_trace_id` | Generator im Decompile nicht gefunden |
| UI-Trigger des Event-Reports, Wire-Form des Bot-Chat-Reports | nur Lambda-Aufrufer (`AYs`, `Aaa`) / `reportUgc` nicht über `C33437Eh4` hinaus verfolgt |
| Flow-String, den der Channel-Status-Report-Aufrufer übergibt | `channel_status_report` wird von `C9ZJ` abgelehnt |
| Cutoff des `reporting_info*`-Cleanups | Aufrufer von `FP7` case 6 nicht verfolgt |
| Upload des lokalen Scam-Scan-Records | kein Consumer gefunden |
| Schema pro Eintrag des `reporting`-Childs pro Nachricht und Zweck des Aufrufs von Flag 20085 | aus DB-Zeilen gebaut, Consumer-Logik nicht gelesen |
| Live-Akzeptanz jeder Stanza in Abschnitt 12 | es wurde kein Traffic mitgeschnitten |
