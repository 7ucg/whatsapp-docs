<!-- src-sha1: 12b80567ad9e73698ea38209998c12bdf3666099 -->
# WhatsApp Call-Links — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-11-02
**Umfang:** Gast-Call-Links (`call.whatsapp.com/{voice|video}/{token}`): der `link_query`/`link_join`-Handshake, der Warteraum, das Gast-Teilnehmer-/JID-Zuteilungsmodell sowie das Relay- und Schlüsselmaterial, das einem Gast bei der Zulassung übergeben wird. Dieser Report deckt nur die Link-/Warteraum-/Gast-Schicht ab; die generische `<call>`-Envelope-Grammatik, offer/accept/terminate, der Call-Key, die Relay-Auswahllogik und der Media-Pfad sind in [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md) beschrieben und werden hier nur referenziert, nicht wiederholt.

---

## 1. Was es ist

Ein Call-Link ist ein Token, das einem Teilnehmer erlaubt, einem Anruf beizutreten, ohne per JID eingeladen zu werden. Der Server löst das Token zu einem laufenden oder startbaren Anruf auf und hält den Beitretenden, falls der Anruf einen Warteraum hat, dort fest, bis er eingelassen wird. Alles ab Abschnitt 3, unterhalb der Stanza-Form-Tabellen, ist **tested**: gelesen aus einem echten Wire-Capture eines Clients, der seinem eigenen Test-Call-Link beitritt, entschlüsselt und dekodiert vom beitretenden Client selbst (keine Interception von Drittverkehr). APK-Statik (**found**) bestätigt die Teile, die das Capture nicht zeigt, vor allem die Link-Erstellung. Serverseitige Begründungen sind **unknown**, sofern nicht anders angegeben.

| Entität | Form | Gesetzt von | Tier |
|--------|------|--------|------|
| Link-URL | `https://call.whatsapp.com/{voice\|video}/{token}` | Client baut sie um ein Token | found |
| Token | 22 Zeichen, alphanumerisch gemischte Groß-/Kleinschreibung (`Voip.kCallLinkTokenLength`=22) | Erstellungs-Call-Site hat in Java keinen Token-Parameter; serverseitige Zuweisung ist die Arbeitsannahme | found (Länge), inferred (Ursprung) |
| Call-id | 32 Hex-Zeichen (16 Bytes), z. B. `0076804DB4CA9D41EFCB547F08AE87BD` | Server, zurückgegeben im `link_join`-Ack | tested |
| `is_guest_eligible` | Bool am Link | Host wählt es bei der Erstellung (`CallLinkInfo.isGuestEligible`) | found (Feld), tested (Wire-Wert) |
| `waiting_room` `enabled` | Bool am Link | Host wählt es bei der Erstellung (`Voip.createCallLink(..., waitingRoomEnabled)`) | found (Feld), tested (Wire-Wert) |
| Gast-Teilnehmer | ein Roster-Eintrag mit `account_kind="guest"` und einer server-zugewiesenen JID | Server, bei der Zulassung | tested |
| Call-Domain-JID | nackte `call`-Domain, bevor eine Call-id existiert, danach `<call-id>@call` | Server | tested |

---

## 2. Beweisbasis

Zwei unabhängige Gast-Joins wurden end-to-end aufgezeichnet, beide über eine bereits authentifizierte chatd-Verbindung (die beitretende Session hat ihre eigene Identität auf der Leitung), die bewusst den Link-Pfad mit einem selbstgewählten Anzeigenamen und ohne offengelegte Identität aufruft, statt mit der eigenen JID des Accounts beizutreten:

| | Video-Link | Audio-only-Link |
|---|---|---|
| Token | `7vEdtKy61dqCtbWAQ59zuO` | `ENcQnTAwKj7lQOdOHVJPmQ` |
| Call-id | `0076804DB4CA9D41EFCB547F08AE87BD` | `00BC509C0194CE83E26FA85A0319FD9C` |
| Call-Creator (Host) | `48615137533978` Device 24 | `21428363591910` Device 0 |
| Gesendeter Gast-push_name | `Baron als Gast ohne wa` | `Baron aus web testt` |

Beide Sessions adressieren den Host und den Ersteller der Call-id mit einer JID-Form `type=1, domainType=1` ohne explizites `server`-Attribut; an anderer Stelle in denselben Captures wird dieselbe Form, für denselben Account, mit einem expliziten `server="lid"` gepaart (z. B. bei den Receipt-Acks der Message-Klasse). Zusammen gelesen: Call-Signaling läuft hier über LID-Identitäten, konsistent mit der Anmerkung in [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md) §3.2, dass Call-Stanzas ein LID-`to` gegen einen `call-creator` mit anderer Domain tolerieren.

Was dieses Capture nicht zeigt: eine wirklich account-lose Browser-Session (ohne jeden vorherigen WhatsApp-Login), die denselben Link aufruft. Die unten gezeigten Stanza-Formen sind das Call-Signaling-Protokoll für einen Gast-Join; ob der Client eines anonymen Web-Besuchers byte-identische Stanzas erzeugt oder zuvor einen zusätzlichen Provisioning-Schritt durchläuft, ist **unknown**.

---

## 3. Link-Erstellung (found, APK; nicht auf der Leitung erfasst)

| Schritt | Klasse / Methode | Detail |
|------|-----------------|--------|
| Einstiegspunkte | `CreateCallLinkBottomSheet` (eigenständiger Link), `EventCallLinkManager.createCallLink` (event-gebundener Link) | beide laufen in einen Manager zusammen |
| Manager | `CallLinkManager` (Log-Tag), dispatcht `actionCreateCallLink` / `actionCreateCallLinkForEvent` | |
| Nativer Call | `Voip.createCallLink(isVideo, eventStartTimeSec, waitingRoomEnabled)` | nur 3 Parameter — kein Token, kein explizites `media`-/`guest`-Argument in der Java-Signatur |
| Stanza-Aufbau | nativ (`wa_call_link_create_v2`) | das `link_create`-IQ selbst wird unterhalb der JNI-Grenze gebaut, wie jede andere Call-Stanza (§2 von WA_CALL_SIGNALING.md) |
| Ergebnis | `CallLinkInfo` (creatorJid, token, videoEnabled, eventStartTsSec, isGuestEligible, linkState, waitingRoomState, self), befüllt aus einem nativen Callback | Token wird zurückgelesen, nicht übergeben |
| URL | `AbstractC227619sp.A01(token, isVideo)`: `Uri.Builder().scheme("https").authority("call.whatsapp.com").appendPath(isVideo?"video":"voice").appendPath(token)` | Client baut die Share-URL um das zurückerhaltene Token |

Kein `SecureRandom`/Base62-Generatorcode liegt in Java in der Nähe von `kCallLinkTokenLength` oder `createCallLink`, und die native Bibliothek ließ sich nicht dekompilieren. **Unknown**: ob das 22-Zeichen-Token clientseitig erzeugt und in `link_create` gesendet wird, oder vom Server zugewiesen und im Ack zurückgegeben wird — die clientseitig sichtbare Call-Site trägt kein Token-Argument, was für serverseitige Zuweisung spricht, aber das ist **inferred**, nicht belegt. `connected-limit` (gesehen bei `group_info`, §6) wird nur vom Server zurückgegeben; kein Client-Setter wurde gefunden. Kein clientseitiges Rate-Limit für die Link-Erstellung wurde gefunden.

---

## 4. Query und Join (tested)

### 4.1 `link_query`

Wird nackt gesendet, bevor eine Call-id bekannt ist, an die Call-Domain-JID ohne User-Teil (`to: {user: null, server: "call"}`):

```
<call to="@call" id="...">
  <link_query token="7vEdtKy61dqCtbWAQ59zuO" media="video"/>
</call>
```

Ack:

```
<ack from="@call" class="call" type="link_query" id="...">
  <link_query link_creator="<host jid>" media="video" token="...">
    <guest is_guest_eligible="1"/>
    <waiting_room enabled="1"/>
  </link_query>
</ack>
```

`link_creator` identifiziert den Host; `is_guest_eligible` und `waiting_room enabled` sind die Erstellungs-Einstellungen des Links (§3), die hier zurückgespiegelt werden. Noch keine Call-id — dieses Ack ist nur eine Vorschau des Links.

### 4.2 `link_join`

Trägt dasselbe `token`/`media`, plus einen gewählten `push_name` und die üblichen Offer-förmigen Media-Children:

```
<call to="@call" id="...">
  <link_join token="7vEdtKy61dqCtbWAQ59zuO" media="video" push_name="Baron als Gast ohne wa">
    <audio enc="opus" rate="16000"/>
    <video dec="H264" device_orientation="0"/>
    <net medium="2"/>
    <capability ver="1">...7 bytes...</capability>
  </link_join>
</call>
```

Das `link_join` des Audio-only-Links (zweites Capture) lässt das `<video>`-Child vollständig weg — durch direkten Vergleich bestätigt, nicht inferiert:

```
<link_join token="ENcQnTAwKj7lQOdOHVJPmQ" media="audio" push_name="Baron aus web testt">
  <audio enc="opus" rate="16000"/>
  <net medium="2"/>
  <capability ver="1">...</capability>
</link_join>
```

`push_name` ist Freitext, den der Gast für diesen Join wählt; es ist nicht der eigene WhatsApp-Anzeigename des Accounts (der beitretende Account ist in beiden Captures eine real eingeloggte Session, aber der gewählte Name unterscheidet sich vom normalen Profilnamen — Gast-Identität ist auf dieser Stufe nur Präsentation). Die beobachteten 7 `<capability>`-Bytes (`01 05 F5 09 E0 BB 53` Video-Gast, `01 05 F7 09 E0 3B 53` Host) sind sessionsspezifische Werte, keine generelle Maske; WA_CALL_SIGNALING.md §5.2 markiert die Android-Capability-Byte-Werte bereits allgemein als unknown, und das wird hier nicht aufgelöst.

Das Ack auf `link_join` trägt jetzt eine Call-id — der Server hat den Anruf aufgelöst (oder gestartet):

```
<ack from="@call" class="call" type="link_join" id="...">
  <waiting_room link-token="7vEdtKy61dqCtbWAQ59zuO" media="video"
                call-id="0076804DB4CA9D41EFCB547F08AE87BD"
                call-creator="<host jid>" enabled="1"/>
  <guest is_guest_eligible="1"/>
</ack>
```

### 4.3 Call-Domain-JID-Adressierung (tested)

Dies löst einen Teil von WA_CALL_SIGNALING.md §10.1 auf, der den Typ der Call-Domain-JID offen ließ:

1. `link_query`/`link_join` adressieren die nackte Domain `call` — kein User-Teil (`callDomainJID`).
2. Sobald das `link_join`-Ack eine `call-id` zurückgibt, adressiert der Client weitere In-Call-Stanzas (Warteraum-Heartbeat und später mute/transport/relaylatency/video) an `<call-id>@call` — eine user-qualifizierte JID unter derselben Domain (`callJID`).
3. Der eigene Zulassungs-Push des Servers (§5) kommt später `from="<call-id>@call"` an, was dieselbe Adressierung auf der Inbound-Seite bestätigt.

Die Call-id ist also, sobald gelernt, der JID-User-Teil für alles, was folgt — kein separater Korrelationsschlüssel, der zusätzlich zur Adressierung mitgeführt wird.

---

## 5. Warteraum (tested)

Während des Wartens sendet der beigetretene, aber noch nicht zugelassene Gast einen periodischen Heartbeat an die Call-id-JID:

```
<call to="<call-id>@call" id="...">
  <heartbeat call-id="0076804DB4CA9D41EFCB547F08AE87BD" call-creator="<host jid>" type="waiting_room"/>
</call>
```
wird sofort geackt (`<ack ... type="heartbeat"/>`, ohne Inhalt).

**Vorbehalt zur Zulassung**: Dieses Capture ist einseitig — es zeigt nur die Verbindung des Gastes. Die hostseitige Aktion, die einen wartenden Gast zulässt (`waitingRoomAdmit`, das Senden einer `waiting_room_toggle`/`_admit`-Stanza, laut WA_CALL_SIGNALING.md §10.3), läuft auf der Verbindung des *Hosts* und wurde hier nicht beobachtet; dieser Report zeigt nur ihr Ergebnis. In beiden Captures folgte die Zulassung (§6) dem einzigen sichtbaren Heartbeat innerhalb von deutlich unter einer Sekunde — so schnell, dass **unknown** ist, ob das einen aufmerksamen Host widerspiegelt, der sofort auf Zulassen tippt, oder eine Auto-Admit-Bedingung (z. B. Host bereits aktiv im Anruf); keine Evidenz hier unterscheidet die beiden.

---

## 6. Gast-JID-Zuteilung (tested)

Die Zulassung kommt als gewöhnlicher `group_update`/`group_info`-Push von `<call-id>@call` an, mit zwei `<user>`-Einträgen — Host und Gast nebeneinander:

| Feld | Host-Eintrag | Gast-Eintrag |
|-------|-----------|--------------|
| `jid` | `48615137533978` (Device 24 unter `<device>`) | `29554559176938` (Device 0) |
| `type` | `admin` | *(fehlt — keine erhöhte Rolle)* |
| `account_kind` | *(fehlt)* | `guest` |
| `push_name` | *(fehlt bei diesem Eintrag)* | `Baron als Gast ohne wa` — der in `link_join` §4.2 gesendete Name, wortgetreu in das Roster kopiert |
| `state` | `connected` | `connected` |
| Device `platform` | `web` | `web` |
| Device `pid` | `0` | `1` |

Die JID des Gastes (`29554559176938`) liegt in derselben Adressform-Klasse (`type=1`, `domainType=1`, also LID-artig, §2) wie die des Hosts, vom Server für diesen Anruf frisch zugewiesen — nicht die eigene Account-Identität der beitretenden Session. Device `pid` (`1` beim Gast) stimmt mit dem `self_pid="1"` des Relay-Blocks in derselben Stanza (§7) überein — die Per-Device-Participant-id des Rosters und die eigene Participant-id des Relays sind dieselbe Zahl.

**Unknown**: ob diese Gast-JID bei wiederholten Joins desselben Links durch denselben Browser/dieselbe Session wiederverwendet wird, wie lange sie gehalten wird, oder ob sie dem Host über `push_name` und `account_kind` hinaus sichtbar ist.

---

## 7. Relay- und Schlüsselübergabe bei der Zulassung (tested)

Dieselbe Zulassungs-Stanza trägt einen `<relay>`-Block, Sibling von `<group_info>`, der dem Gast alles gibt, was er braucht, um Media ohne weitere Round-Trips zu erreichen. Die Felder entsprechen der Grammatik in WA_CALL_SIGNALING.md §8.2; dieser Abschnitt ergänzt konkretes Wire-Level-Detail, das jener Report offen ließ.

| Child | Gesehene Anzahl | Hinweise |
|-------|-----------|-------|
| `<token id=N>` | 3 (ids 0, 1, 2) | rohes Binär, je 194 Bytes |
| `<auth_token id=0>` | 1 | rohes Binär, 70 Bytes |
| `<key>` | 1 | 24 Wire-Bytes — aber diese 24 Bytes sind selbst ASCII-Text eines Base64-Strings, der erneut zu einem 16-Byte-Rohschlüssel dekodiert |
| `<hbh_key>` | 1 | 40 Wire-Bytes — gleiches Muster: ASCII-Base64-Text, dekodiert zu 30 Rohbytes |
| `<te2 relay_id auth_token_id token_id domain_name relay_name c2r_rtt>` | 6 (2 Relays: `edgeray-ham3-1.wt.whatsapp.com`/`ham3c01`, `edgeray-ber1-1.wt.whatsapp.com`/`ber1c01`) | kein `<te>` vorhanden — bestätigt die "nie beide"-Regel, dieser Anruf nutzte `te2` |
| Relay-Attribute | `attribute_padding`, `transaction-id`, `self_pid`, `uuid`, `participant_uuid` | `self_pid="1"` hängt mit dem eigenen Device-`pid` des Gastes in `group_info` zusammen (§6) |
| `<participant pid jid>` | nicht vorhanden | das in 8.2 beschriebene Mapping-Child von Participant-id zu JID wurde in diesem 2-Parteien-Capture nicht gesehen; unknown, ob es nur bei größeren Gruppenanrufen erscheint |

Nur `<key>` und `<hbh_key>` tragen die doppelt kodierte Form (Binär-Node, die ASCII-Base64 enthält); `<token>` und `<auth_token>` sind reines rohes Binär. Was diese doppelte Schicht gegenüber dem direkten Senden roher Bytes bringt, ist **unknown** (ein Überbleibsel eines intern textorientierten Transports, inferiert).

Ein `<voip_settings uncompressed="1">`-Child, ebenfalls Sibling von `<group_info>`/`<relay>`, trägt einen JSON-Blob mit Engine-Parametern (in diesem Capture nicht komprimiert, konsistent mit der Anmerkung in WA_CALL_SIGNALING.md §5.2, dass komprimierte Payloads auf mindestens einem Pfad abgelehnt werden). Darin, unter dem `fs`-Objekt (Feature-Switch): `"guest_calling_logging_enabled": "true"` — der einzige gast-spezifische Key in einem sonst generischen ~32-KB-Settings-Dokument (`aec`, `bwe`, `decode`, `encode`, `sfu`, `rc`, ... — alles generisches Media-Engine-Tuning, ohne Bezug zum Gast-Join). Die vom beitretenden Client rund um diesen Anruf gesendeten Telemetrie-Events nutzen unabhängig davon den Kategorie-String `guest_calling` (gesehen in den eigenen `w:stats`/WAM-Blobs des Clients), passend zur Benennung des Settings-Keys.

Zwei harmlose Siblings, `<uploadfieldstat/>` und `<userrate interval="0"/>`, reiten in derselben Stanza mit; kein gast-spezifischer Inhalt.

Der Client sendet für diesen Push sofort ein einfaches `<ack class="call" type="group_update">` (ohne Inhalt) — gewöhnliche Behandlung laut WA_CALL_SIGNALING.md §3.3 (group_update ist nicht in der Tag-Menge ohne Sofort-Ack).

---

## 8. Traffic nach der Zulassung (tested, kurz)

Nach der Zulassung ist der Traffic nicht von einem normalen Anruf auf derselben Call-id-JID zu unterscheiden: `mute_v2` (der Host mutet den Gast in diesem Capture sofort nach der Zulassung), `transport` (`transport-message-type="4"`, ein `<net medium="2" protocol="0"/>`-Child), `relaylatency` (beide Richtungen, jede mit einem `<te latency relay_name>`, das auf die Relay-Namen aus §7 verweist), und `video`-State-Änderungen (`state="6"`, also `Stopped` laut der `kVideoState*`-Tabelle in WA_CALL_SIGNALING.md §13, dreimal in schneller Folge während des Setups wiederholt). Nichts davon ist link-spezifisch; siehe WA_CALL_SIGNALING.md §§8, 13 für die allgemeine Semantik.

---

## 9. Video- vs. Audio-only-Link — beobachtete Unterschiede (tested)

| Aspekt | Video-Link | Audio-only-Link |
|--------|-----------|------------------|
| `link_query`/`link_join`-`media`-Attribut | `video` | `audio` |
| `link_join`-Children | `<audio>`, `<video>`, `<net>`, `<capability>` | `<audio>`, `<net>`, `<capability>` — `<video>` weggelassen |
| `waiting_room`-Ack `media` | `video` | `audio` |
| Warteraum-/Gast-Eligibility-Mechanik | identisch | identisch |

Zwischen beiden wurde kein weiterer Protokollunterschied beobachtet; der Media-Typ wird end-to-end als einfaches Attribut mitgeführt, nicht als eigene Stanza-Familie.

---

## 10. Unterschiede zu einem normalen 1:1- oder Gruppenanruf

| Aspekt | Normaler 1:1-/Gruppenanruf (WA_CALL_SIGNALING.md) | Gast-Link-Join (dieser Report) |
|--------|------------------------------------------------|-------------------------------|
| Einstiegs-Stanza | `offer` an eine bekannte Peer-/Gruppen-JID | `link_query`, dann `link_join` an die nackte `call`-Domain |
| Call-Key | per-Device Signal-verschlüsselter `Message.call.callKey` im Offer | in der Zulassung dieses Captures nicht beobachtet; der Gast erhält Relay-/Schlüsselmaterial (§7) direkt, keinen Signal-umhüllten Call-Key — konsistent damit, dass ein Gast keine paarweise Signal-Session mit dem Host hat |
| Caller-/Callee-Identität | beide Seiten sind vor Anrufbeginn bekannte JIDs | die reale Identität der beitretenden Seite wird im Roster nicht offengelegt; der Server weist eine frische JID zu und markiert sie als `account_kind="guest"` |
| Zulassung | keine — offer/accept ist das einzige Gate | optionaler Warteraum: `waiting_room enabled`, gehalten bis zu einem (unbeobachteten, hostseitigen) Admit |
| Roster-Zustellung | `group_info` im Offer oder in einem späteren Update | `group_update`/`group_info`-Push von `<call-id>@call`, gebündelt mit `<relay>` und `<voip_settings>` in derselben Stanza |
| JID-Adressierung | durchgehend Peer-/Gruppen-JID | nackte `call`-Domain, bis eine Call-id existiert, dann `<call-id>@call` |

Der fehlende Per-Device-Call-Key für den Gast (Zeile 2) ist der folgenreichste Unterschied und ist nur als Abwesenheit in diesem Capture **tested** — nicht als Protokollregel bestätigt; das ist auch konsistent mit der Anmerkung in WA_CALL_SIGNALING.md §9.2, dass Gruppen-Offers keinen Per-Device-Key tragen und Keys out of band (`enc_rekey`) nachgereicht werden. Ob ein Gast jemals ein `enc_rekey` erhält, wurde in keinem der hier verwendeten Capture-Fenster beobachtet.

---

## 11. Fehlerfälle / Gotchas

| Symptom | Ursache | Fix / Hinweis |
|---------|-------|-----------|
| `link_query`-Ack hat keine `call-id` | der Link wurde noch nicht zu einem laufenden/startbaren Anruf aufgelöst | normal für eine nackte Vorschau; Call-id kommt erst im `link_join`-Ack |
| Gast bleibt nach `link_join`-Ack stecken, nur Heartbeats werden ausgetauscht | Warteraum ist aktiviert und der Host hat noch nicht zugelassen | hostseitige Aktion erforderlich; von der Verbindung des Gastes aus nicht sichtbar |
| `link_join` trägt ein `<video>`-Child für einen Audio-only-Link | Client-Bug — die beiden Captures zeigen, dass dieses Child bei `media="audio"` vollständig fehlen muss | `<video>` für Audio-only-Joins weglassen |
| Die eigene Account-JID des Gastes erscheint im Call-Roster statt einer frischen Gast-JID | falscher Join-Pfad (gewöhnliches `offer`/Gruppen-Join statt `link_join`) | `link_query`→`link_join` verwenden, um `account_kind="guest"`-Behandlung zu erhalten |
| Gast erhält keinen Call-Key, aber Relay-/Schlüsselmaterial | erwartet für diesen Pfad (§10) — der Gast erhält keinen Signal-umhüllten Key wie ein normaler Callee | nicht als Entschlüsselungsfehler behandeln |

---

## 12. Wichtige Unterscheidungen

| Nicht verwechseln | Mit |
|-----------------|------|
| Call-Link-**Token** (22 Zeichen, URL-seitig) | Call-**id** (32 Hex-Zeichen, protokollseitig, erscheint erst nach `link_join`) |
| Nackte `call`-Domain-JID (vor der Call-id) | `<call-id>@call` (nach der Call-id) — beide sind "die Call-Domain-JID" auf unterschiedlichen Stufen, nicht zwei unabhängige Adressen |
| `is_guest_eligible` (Link-Einstellung: kann *irgendjemand* diesem Link als Gast beitreten) | `waiting_room enabled` (Link-Einstellung: werden Gäste zur Zulassung festgehalten) — unabhängige Flags, beide in denselben Acks gespiegelt |
| Gast-`push_name` bei `link_join` (Freitext, pro Join gewählt) | der eigene WhatsApp-Profilname des beitretenden Accounts (nicht das, was bei einem Gast-Join im Roster landet) |
| `<key>`/`<hbh_key>`-Wire-Bytes (Binär-Node mit ASCII-Base64-Text, doppeltes Dekodieren nötig) | `<token>`/`<auth_token>`-Wire-Bytes (reines rohes Binär, einfaches Dekodieren) |
| Gast-JID-Zuteilung (serverseitig, bei der Zulassung, pro Anruf) | normale LID-/PN-JIDs (account-seitig, dauerhaft) |

---

## 13. Vollständiger Ablauf (Gast-Join, aus dem Capture)

```
[Guest client]  already has a chatd session (own identity, not used for the call)
     │  <call to="@call"><link_query token media/></call>
     ▼
[WA Server]  resolves the token
     │  ack: link_creator, media, token, <guest is_guest_eligible/>, <waiting_room enabled/>
     ▼
[Guest client]  <call to="@call"><link_join token media push_name><audio/>[<video/>]<net/><capability/></link_join></call>
     ▼
[WA Server]  starts/resolves the call
     │  ack: <waiting_room link-token media call-id call-creator enabled/>, <guest is_guest_eligible/>
     ▼
[Guest client]  learns call-id → addresses it as <call-id>@call from now on
     │  <call to="<call-id>@call"><heartbeat call-id call-creator type="waiting_room"/></call>  (repeats)
     ▼
[Host, out of band — not in this capture]  taps Admit (waiting_room_toggle/_admit)
     ▼
[WA Server]  <call from="<call-id>@call"><group_update><group_info ...>
                 <user host .../><user account_kind="guest" push_name jid=<allocated> .../>
              </group_info>
              <relay token×N auth_token key hbh_key te2×N/>
              <voip_settings uncompressed fs.guest_calling_logging_enabled=true/>
              </group_update></call>
     │  ack: <ack class="call" type="group_update"/>
     ▼
[Both]  ordinary call traffic on <call-id>@call: mute_v2, transport, relaylatency, video state
              (see WA_CALL_SIGNALING.md §§8, 13 for generic semantics)
```

---

## 14. Unknowns

| Element | Status |
|------|--------|
| Ort der Token-Generierung (clientseitig erzeugt vs. serverseitig zugewiesen) | `createCallLink`-Call-Site trägt kein Token-Argument (found); wahrer Ursprung ist nativ (unknown) |
| Ob eine wirklich account-lose Browser-Session dieselbe Stanza-Sequenz erzeugt | nicht erfasst — beide Captures liefen über eine bereits authentifizierte Verbindung, die sich entschied, als Gast beizutreten |
| Wire-Form der hostseitigen Admit-Aktion (`waiting_room_toggle`/`_admit`) | nicht in diesem Capture (einseitig); nur aus den Statics von WA_CALL_SIGNALING.md §10.3 beschrieben |
| Warum die Zulassung dem einzigen beobachteten Heartbeat so schnell folgte | aufmerksamer Host vs. eine Auto-Admit-Bedingung — aus dieser Evidenz nicht unterscheidbar |
| Lebensdauer/Wiederverwendung der Gast-JID über wiederholte Joins | nicht beobachtet |
| Ob ein Gast jemals `enc_rekey` oder einen Signal-umhüllten Call-Key erhält | in keinem der beiden Capture-Fenster beobachtet |
| `<participant pid jid>`-Mapping unter `<relay>` | nicht vorhanden in diesem 2-Parteien-Capture; unknown, ob Gruppenanrufe mit Gästen es nutzen |
| Zweck der doppelten Base64-Kodierung bei `<key>`/`<hbh_key>` gegenüber rohem `<token>`/`<auth_token>` | unknown |
| `connected-limit` als clientseitig setzbares Limit vs. immer serverseitig zugewiesen | kein Client-Setter gefunden (found: nur serverseitig zurückgegeben) |
| Rate-Limits / Abuse-Kontrollen bei Link-Erstellung oder Gast-Joins | clientseitig nichts gefunden; Serververhalten unknown |
</content>
