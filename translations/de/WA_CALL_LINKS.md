<!-- src-sha1: 5cbe81a4c1568d0ea9b8c065d2d8dc0fbf7e1afc -->
# WhatsApp Call Links — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-11-02
**Umfang:** Gast-Call-Links (`call.whatsapp.com/{voice|video}/{token}`): der `link_query`/`link_join`-Handshake, der Warteraum, das Gast-Teilnehmer-/JID-Allokationsmodell, sowie das Relay- und Schlüsselmaterial, das einem Gast bei Zulassung übergeben wird. Dieser Report deckt nur die Link-/Warteraum-/Gast-Schicht ab; die generische `<call>`-Umschlag-Grammatik, Offer/Accept/Terminate, der Call-Key, die Relay-Auswahl-Logik und der Medienpfad sind in [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md) behandelt und werden hier nur referenziert, nicht wiederholt.

---

## 1. Was es ist

Ein Call-Link ist ein Token, das einem Teilnehmer erlaubt, einem Call beizutreten, ohne per JID eingeladen zu werden. Der Server löst das Token zu einem laufenden oder startbaren Call auf und hält den Beitretenden, falls der Call einen Warteraum hat, dort fest, bis er zugelassen wird. Alles ab Abschnitt 3 unterhalb der Stanza-Form-Tabellen ist **tested**: gelesen aus einer echten Wire-Capture eines Clients, der seinem eigenen Test-Call-Link beitritt, entschlüsselt und dekodiert vom beitretenden Client selbst (keine Interception von Drittanbieter-Traffic). APK-Statics (**found**) untermauern die Teile, die die Capture nicht zeigt, vor allem die Link-Erstellung. Server-seitige Überlegungen sind **unknown**, sofern nicht anders angegeben.

| Entität | Form | Gesetzt von | Tier |
|--------|------|--------|------|
| Link-URL | `https://call.whatsapp.com/{voice\|video}/{token}` | Client templatet sie um ein Token | found |
| Token | 22 Zeichen, gemischt alphanumerisch (`Voip.kCallLinkTokenLength`=22) | Erstellungs-Call-Site hat keinen Token-Parameter in Java; serverseitige Zuweisung ist die arbeitende Annahme | found (Länge), inferred (Ursprung) |
| Call-ID | 32 Hex-Zeichen (16 Bytes), z. B. `0076804DB4CA9D41EFCB547F08AE87BD` | Server, zurückgegeben im `link_join`-Ack | tested |
| `is_guest_eligible` | Bool am Link | Host wählt es bei der Erstellung (`CallLinkInfo.isGuestEligible`) | found (Feld), tested (Wire-Wert) |
| `waiting_room` `enabled` | Bool am Link | Host wählt es bei der Erstellung (`Voip.createCallLink(..., waitingRoomEnabled)`) | found (Feld), tested (Wire-Wert) |
| Gast-Teilnehmer | ein Roster-Eintrag mit `account_kind="guest"` und einer serverseitig zugewiesenen JID | Server, bei Zulassung | tested |
| Call-Domain-JID | bare `call`-Domain vor Existenz einer Call-ID, `<call-id>@call` danach | Server | tested |

---

## 2. Evidenzbasis

Zwei unabhängige Gast-Beitritte wurden end-to-end aufgezeichnet, beide von einer bereits authentifizierten chatd-Verbindung aus (die beitretende Session hat ihre eigene Identität auf dem Wire), die den Link-Pfad bewusst mit einem selbstgewählten Anzeigenamen und ohne offengelegte Identität aufruft, statt mit der eigenen JID des Accounts beizutreten:

| | Video-Link | Nur-Audio-Link |
|---|---|---|
| Token | `7vEdtKy61dqCtbWAQ59zuO` | `ENcQnTAwKj7lQOdOHVJPmQ` |
| Call-ID | `0076804DB4CA9D41EFCB547F08AE87BD` | `00BC509C0194CE83E26FA85A0319FD9C` |
| Call-Ersteller (Host) | `48615137533978` Gerät 24 | `21428363591910` Gerät 0 |
| Gesendeter Gast-push_name | `Baron als Gast ohne wa` | `Baron aus web testt` |

Beide Sessions adressieren den Host und den Ersteller der jeweiligen Call-ID mit einer JID-Form `type=1, domainType=1` und ohne explizites `server`-Attribut; an anderer Stelle in denselben Captures ist dieselbe Form, für denselben Account, mit einem expliziten `server="lid"` gepaart (z. B. bei den Message-Class-Receipt-Acks). Zusammengelesen: Call-Signaling läuft hier über LID-Identitäten, konsistent mit WA_CALL_SIGNALING.md §3.2's Hinweis, dass Call-Stanzas ein LID-`to` gegen einen `call-creator` anderer Domain tolerieren.

Eine dritte Capture, aus einer wirklich account-losen Browser-Session (gar kein vorheriger WhatsApp-Login, menschengesteuert, nichts automatisiert), schließt einen Teil dieser Lücke: sie zeigt den Registrierungsschritt, der die Identität erzeugt, die die obigen Abschnitte als bereits existierend voraussetzen, und bestätigt, dass dieser Schritt über den gewöhnlichen Web-Transport läuft, nicht über einen separaten. Siehe §14–§15. Der entschlüsselte Gast-Stanza-Inhalt dieser Session (ob er mit §4's Formen byteidentisch ist) wurde nicht erfasst — der Noise-Channel verbirgt ihn vor einer passiven Netzwerksicht, genau wie bei jedem anderen Client.

---

## 3. Link-Erstellung (found, APK; nicht auf dem Wire erfasst)

| Schritt | Klasse/Methode | Detail |
|------|-----------------|--------|
| Einstiegspunkte | `CreateCallLinkBottomSheet` (eigenständiger Link), `EventCallLinkManager.createCallLink` (event-gebundener Link) | beide laufen in einen Manager zusammen |
| Manager | `CallLinkManager` (Log-Tag), dispatcht `actionCreateCallLink`/`actionCreateCallLinkForEvent` | |
| Native Call | `Voip.createCallLink(isVideo, eventStartTimeSec, waitingRoomEnabled)` | nur 3 Parameter — kein Token, kein explizites `media`-/`guest`-Argument in der Java-Signatur |
| Stanza-Aufbau | native (`wa_call_link_create_v2`) | die `link_create`-IQ selbst wird unterhalb der JNI-Grenze aufgebaut, wie jede andere Call-Stanza (§2 von WA_CALL_SIGNALING.md) |
| Ergebnis | `CallLinkInfo` (creatorJid, token, videoEnabled, eventStartTsSec, isGuestEligible, linkState, waitingRoomState, self), befüllt aus einem nativen Callback | Token wird zurückgelesen, nicht übergeben |
| URL | `AbstractC227619sp.A01(token, isVideo)`: `Uri.Builder().scheme("https").authority("call.whatsapp.com").appendPath(isVideo?"video":"voice").appendPath(token)` | Client templatet die Share-URL um das Token, das er zurückbekommen hat |

Kein `SecureRandom`-/Base62-Generator-Code sitzt in der Nähe von `kCallLinkTokenLength` oder `createCallLink` in Java, und die native Library ließ sich nicht dekompilieren. **Unknown**: ob das 22-Zeichen-Token clientseitig erzeugt und in `link_create` gesendet wird, oder vom Server zugewiesen und im Ack zurückgegeben wird — die clientseitig sichtbare Call-Site führt kein Token-Argument, was für serverseitige Zuweisung spricht, aber das ist **inferred**, nicht bewiesen. `connected-limit` (gesehen auf `group_info`, §6) wird nur serverseitig zurückgegeben; kein Client-Setter wurde gefunden. Kein clientseitiges Rate-Limit bei der Link-Erstellung wurde gefunden.

---

## 4. Query und Join (tested)

### 4.1 `link_query`

Wird bare gesendet, bevor eine Call-ID bekannt ist, an die Call-Domain-JID ohne User-Part (`to: {user: null, server: "call"}`):

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

`link_creator` identifiziert den Host; `is_guest_eligible` und `waiting_room enabled` sind die zur Erstellungszeit festgelegten Link-Einstellungen (§3), die hier zurückgespiegelt werden. Noch keine Call-ID — dieser Ack liefert nur eine Vorschau des Links.

### 4.2 `link_join`

Trägt denselben `token`/`media`, plus einen gewählten `push_name` und die üblichen offer-förmigen Media-Kinder:

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

Der `link_join` des Nur-Audio-Links (zweite Capture) lässt das `<video>`-Kind komplett weg — durch direkten Vergleich bestätigt, nicht erschlossen:

```
<link_join token="ENcQnTAwKj7lQOdOHVJPmQ" media="audio" push_name="Baron aus web testt">
  <audio enc="opus" rate="16000"/>
  <net medium="2"/>
  <capability ver="1">...</capability>
</link_join>
```

`push_name` ist freier Text, den der Gast für diesen Join wählt; es ist nicht der eigene WhatsApp-Anzeigename des Accounts (der beitretende Account ist in beiden Captures eine echte eingeloggte Session, aber der gewählte Name unterscheidet sich vom normalen Profilnamen — Gast-Identität ist auf dieser Stufe nur Darstellung). Die beobachteten 7 `<capability>`-Bytes (`01 05 F5 09 E0 BB 53` Video-Gast, `01 05 F7 09 E0 3B 53` Host) sind sessionspezifische Werte, keine generelle Maske; WA_CALL_SIGNALING.md §5.2 markiert die Android-Capability-Byte-Werte bereits allgemein als unknown, und dies löst das nicht auf.

Der Ack auf `link_join` trägt nun eine Call-ID — der Server hat den Call aufgelöst (oder gestartet):

```
<ack from="@call" class="call" type="link_join" id="...">
  <waiting_room link-token="7vEdtKy61dqCtbWAQ59zuO" media="video"
                call-id="0076804DB4CA9D41EFCB547F08AE87BD"
                call-creator="<host jid>" enabled="1"/>
  <guest is_guest_eligible="1"/>
</ack>
```

### 4.3 Call-Domain-JID-Adressierung (tested)

Dies löst einen Teil von WA_CALL_SIGNALING.md §10.1 auf, das den Call-Domain-JID-Typ ungeklärt ließ:

1. `link_query`/`link_join` adressieren die bare Domain `call` — kein User-Part (`callDomainJID`).
2. In dem Moment, wo der `link_join`-Ack eine `call-id` zurückgibt, beginnt der Client, weitere In-Call-Stanzas (Warteraum-Heartbeat, und später mute/transport/relaylatency/video) an `<call-id>@call` zu adressieren — eine user-qualifizierte JID unter derselben Domain (`callJID`).
3. Der eigene Zulassungs-Push des Servers (§5) kommt später `from="<call-id>@call"` an, was dieselbe Adressierung auch auf der eingehenden Seite bestätigt.

Die Call-ID, einmal erfahren, *ist* also der JID-User-Part für alles, was folgt — kein separater Korrelationsschlüssel, der neben der Adressierung mitgeführt wird.

---

## 5. Warteraum (tested)

Während des Wartens sendet der beigetretene, aber nicht zugelassene Gast einen periodischen Heartbeat an die Call-ID-JID:

```
<call to="<call-id>@call" id="...">
  <heartbeat call-id="0076804DB4CA9D41EFCB547F08AE87BD" call-creator="<host jid>" type="waiting_room"/>
</call>
```
sofort bestätigt (`<ack ... type="heartbeat"/>`, ohne Inhalt).

**Vorbehalt zur Zulassung**: diese Capture ist einseitig — sie zeigt nur die eigene Verbindung des Gasts. Die hostseitige Aktion, die einen wartenden Gast zulässt (`waitingRoomAdmit`, das Senden einer `waiting_room_toggle`/`_admit`-Stanza, laut WA_CALL_SIGNALING.md §10.3), läuft auf der Verbindung des *Hosts* und wurde hier nicht beobachtet; dieser Report zeigt nur ihr Ergebnis. In beiden Captures folgte die Zulassung (§6) dem einzigen sichtbaren Heartbeat innerhalb von deutlich unter einer Sekunde — schnell genug, dass **unknown** ist, ob dies einen aufmerksamen Host widerspiegelt, der sofort auf Zulassen tippt, oder eine Auto-Admit-Bedingung (z. B. Host bereits aktiv im Call); keine Evidenz hier unterscheidet die beiden.

---

## 6. Gast-JID-Allokation (tested)

Die Zulassung kommt als gewöhnlicher `group_update`/`group_info`-Push von `<call-id>@call` an, mit zwei `<user>`-Einträgen — Host und Gast Seite an Seite:

| Feld | Host-Eintrag | Gast-Eintrag |
|-------|-----------|--------------|
| `jid` | `48615137533978` (Gerät 24 unter `<device>`) | `29554559176938` (Gerät 0) |
| `type` | `admin` | *(fehlt — keine erhöhte Rolle)* |
| `account_kind` | *(fehlt)* | `guest` |
| `push_name` | *(fehlt bei diesem Eintrag)* | `Baron als Gast ohne wa` — der in `link_join` §4.2 gesendete Name, wortgetreu in das Roster übernommen |
| `state` | `connected` | `connected` |
| Gerät `platform` | `web` | `web` |
| Gerät `pid` | `0` | `1` |

Die JID des Gastes (`29554559176938`) liegt in derselben Adressform-Klasse (`type=1`, `domainType=1`, also LID-artig, §2) wie die des Hosts, frisch vom Server für diesen Call zugewiesen — sie ist nicht die eigene Account-Identität der beitretenden Session. Geräte-`pid` (`1` beim Gast) stimmt mit dem `self_pid="1"` des Relay-Blocks in derselben Stanza (§7) überein — die Per-Device-Teilnehmer-ID des Rosters und die eigene Teilnehmer-ID des Relays sind dieselbe Nummer.

**Unknown**: ob diese Gast-JID bei wiederholten Beitritten desselben Links durch denselben Browser/dieselbe Session wiederverwendet wird, wie lange sie gehalten wird, oder ob sie dem Host über `push_name` und `account_kind` hinaus sichtbar ist.

---

## 7. Relay- und Schlüsselübergabe bei Zulassung (tested)

Dieselbe Zulassungs-Stanza trägt einen `<relay>`-Block, Geschwister von `<group_info>`, der dem Gast alles Nötige gibt, um Medien ohne weitere Roundtrips zu erreichen. Die Felder entsprechen der Grammatik in WA_CALL_SIGNALING.md §8.2; dieser Abschnitt fügt konkrete Wire-Level-Details hinzu, die jener Report offengelassen hat.

| Kind | Beobachtete Anzahl | Hinweise |
|-------|-----------|-------|
| `<token id=N>` | 3 (ids 0, 1, 2) | roh binär, je 194 Bytes |
| `<auth_token id=0>` | 1 | roh binär, 70 Bytes |
| `<key>` | 1 | 24 Wire-Bytes — aber diese 24 Bytes sind selbst ASCII-Text eines Base64-Strings, der nochmal zu einem 16-Byte-Rohschlüssel dekodiert |
| `<hbh_key>` | 1 | 40 Wire-Bytes — gleiches Muster: ASCII-Base64-Text, dekodiert zu 30 Rohbytes |
| `<te2 relay_id auth_token_id token_id domain_name relay_name c2r_rtt>` | 6 (2 Relays: `edgeray-ham3-1.wt.whatsapp.com`/`ham3c01`, `edgeray-ber1-1.wt.whatsapp.com`/`ber1c01`) | kein `<te>` vorhanden — bestätigt die "nie beide"-Regel, dieser Call nutzte `te2` |
| Relay-Attribute | `attribute_padding`, `transaction-id`, `self_pid`, `uuid`, `participant_uuid` | `self_pid="1"` verknüpft sich mit der eigenen Geräte-`pid` des Gasts in `group_info` (§6) |
| `<participant pid jid>` | nicht vorhanden | das 8.2-Kind für die Zuordnung Teilnehmer-ID-zu-JID wurde in dieser 2-Parteien-Capture nicht gesehen; unknown, ob es nur in größeren Gruppen-Calls erscheint |

Nur `<key>` und `<hbh_key>` tragen die doppelt kodierte (Binär-Node-mit-ASCII-Base64) Form; `<token>` und `<auth_token>` sind einfach roh binär. Was dieses Doppel-Layer gegenüber dem direkten Senden roher Bytes bringt, ist **unknown** (ein Überbleibsel eines intern textorientierten Transports, inferred).

Ein `<voip_settings uncompressed="1">`-Kind, ebenfalls ein Geschwister von `<group_info>`/`<relay>`, trägt einen Engine-Parameter-JSON-Blob (in dieser Capture nicht komprimiert, konsistent mit WA_CALL_SIGNALING.md §5.2's Hinweis, dass komprimierte Payloads auf mindestens einem Pfad zurückgewiesen werden). Darin, unter dem `fs`-Objekt (Feature-Switch): `"guest_calling_logging_enabled": "true"` — der einzige gastspezifische Key in einem sonst generischen ~32-KB-Settings-Dokument (`aec`, `bwe`, `decode`, `encode`, `sfu`, `rc`, ... — alles generisches Media-Engine-Tuning, unabhängig vom Gast-Beitritt). Die Telemetrie-Events, die der beitretende Client um diesen Call herum sendet, nutzen unabhängig davon die Kategorie-Zeichenkette `guest_calling` (gesehen in den eigenen `w:stats`/WAM-Blobs des Clients), passend zur Benennung des Settings-Keys.

Zwei harmlose Geschwister, `<uploadfieldstat/>` und `<userrate interval="0"/>`, fahren in derselben Stanza mit; kein gastspezifischer Inhalt.

Der Client sendet sofort einen einfachen `<ack class="call" type="group_update">` für diesen Push (ohne Inhalt) — gewöhnliche Behandlung laut WA_CALL_SIGNALING.md §3.3 (group_update ist nicht in der no-immediate-ack-Tag-Menge).

---

## 8. Traffic nach Zulassung (tested, kurz)

Einmal zugelassen, ist der Traffic nicht von einem normalen Call auf derselben Call-ID-JID zu unterscheiden: `mute_v2` (Host muted den Gast in dieser Capture unmittelbar nach Zulassung), `transport` (`transport-message-type="4"`, ein `<net medium="2" protocol="0"/>`-Kind), `relaylatency` (beide Richtungen, jeweils mit einem `<te latency relay_name>`, das auf die Relay-Namen aus §7 verweist), und `video`-Zustandsänderungen (`state="6"`, also `Stopped` laut WA_CALL_SIGNALING.md §13's `kVideoState*`-Tabelle, dreimal in schneller Folge während des Setups wiederholt). Nichts davon ist linkspezifisch; siehe WA_CALL_SIGNALING.md §§8, 13 für die generelle Semantik.

---

## 9. Video- vs. Nur-Audio-Link — beobachtete Unterschiede (tested)

| Aspekt | Video-Link | Nur-Audio-Link |
|--------|-----------|------------------|
| `media`-Attribut bei `link_query`/`link_join` | `video` | `audio` |
| `link_join`-Kinder | `<audio>`, `<video>`, `<net>`, `<capability>` | `<audio>`, `<net>`, `<capability>` — `<video>` weggelassen |
| `media` im `waiting_room`-Ack | `video` | `audio` |
| Warteraum-/Gast-Eligibility-Mechanik | identisch | identisch |

Kein weiterer Protokollunterschied wurde zwischen den beiden beobachtet; der Medientyp wird end-to-end als einfaches Attribut geführt, nicht als eigene Stanza-Familie.

---

## 10. Unterschiede zu einem normalen 1:1- oder Gruppen-Call

| Aspekt | Normaler 1:1-/Gruppen-Call (WA_CALL_SIGNALING.md) | Gast-Link-Join (dieser Report) |
|--------|------------------------------------------------|-------------------------------|
| Einstiegs-Stanza | `offer` an eine bekannte Peer-/Gruppen-JID | `link_query`, dann `link_join` an die bare `call`-Domain |
| Call-Key | per-Device Signal-verschlüsselter `Message.call.callKey` im Offer | in der Zulassung dieser Capture nicht beobachtet; der Gast erhält Relay-/Schlüsselmaterial (§7) direkt, keinen Signal-umhüllten Call-Key — konsistent damit, dass ein Gast keine paarweise Signal-Session mit dem Host hat |
| Caller-/Callee-Identität | beide Seiten sind bekannte JIDs, bevor der Call startet | die echte Identität der beitretenden Seite wird im Roster nicht offengelegt; der Server weist eine frische JID zu und beschriftet sie mit `account_kind="guest"` |
| Zulassung | keine — offer/accept ist das einzige Gate | optionaler Warteraum: `waiting_room enabled`, gehalten bis zu einem (unbeobachteten, hostseitigen) Admit |
| Roster-Zustellung | `group_info` im Offer oder einem späteren Update | `group_update`/`group_info`-Push von `<call-id>@call`, gebündelt mit `<relay>` und `<voip_settings>` in derselben Stanza |
| JID-Adressierung | durchgehend Peer-/Gruppen-JID | bare `call`-Domain bis eine Call-ID existiert, dann `<call-id>@call` |

Der fehlende Per-Device-Call-Key für den Gast (Zeile 2) ist der folgenreichste Unterschied und ist nur als Abwesenheit in dieser Capture **tested** — nicht als Protokollregel bestätigt; es ist auch konsistent mit WA_CALL_SIGNALING.md §9.2's Hinweis, dass Gruppen-Offers keinen Per-Device-Key tragen und Keys außerhalb des Bandes neu geteilt werden (`enc_rekey`). Ob ein Gast jemals ein `enc_rekey` erhält, wurde in keinem der hier verwendeten Capture-Fenster beobachtet.

---

## 11. Fehlerfälle / Fallstricke

| Symptom | Ursache | Fix/Hinweis |
|---------|-------|-----------|
| `link_query`-Ack hat keine `call-id` | der Link wurde noch nicht zu einem laufenden/startbaren Call aufgelöst | normal für eine bare Vorschau; die Call-ID kommt erst im `link_join`-Ack |
| Gast bleibt nach `link_join`-Ack stecken, nur Heartbeats werden ausgetauscht | Warteraum ist aktiviert und der Host hat noch nicht zugelassen | hostseitige Aktion nötig; von der Verbindung des Gasts aus nicht sichtbar |
| `link_join` trägt ein `<video>`-Kind für einen Nur-Audio-Link | Client-Bug — die beiden Captures zeigen, dass dieses Kind für `media="audio"` komplett fehlen muss | `<video>` bei Nur-Audio-Joins weglassen |
| Die eigene Account-JID des Gasts erscheint im Call-Roster statt einer frischen Gast-JID | falscher Join-Pfad (gewöhnlicher `offer`-/Gruppen-Join statt `link_join`) | `link_query`→`link_join` benutzen, um `account_kind="guest"`-Behandlung zu erhalten |
| Gast erhält keinen Call-Key, aber Relay-/Schlüsselmaterial | für diesen Pfad erwartet (§10) — der Gast erhält keinen Signal-umhüllten Key wie ein normaler Callee | nicht als Entschlüsselungsfehler behandeln |

---

## 12. Wichtige Unterscheidungen

| Nicht verwechseln | Mit |
|-----------------|------|
| Call-Link-**Token** (22 Zeichen, URL-seitig) | Call-**ID** (32 Hex-Zeichen, protokollseitig, erscheint erst nach `link_join`) |
| Bare `call`-Domain-JID (vor Call-ID) | `<call-id>@call` (nach Call-ID) — beide sind "die Call-Domain-JID" auf unterschiedlichen Stufen, nicht zwei unabhängige Adressen |
| `is_guest_eligible` (Link-Einstellung: kann *irgendjemand* diesem Link als Gast beitreten) | `waiting_room enabled` (Link-Einstellung: werden Gäste zur Zulassung festgehalten) — unabhängige Flags, beide in denselben Acks gespiegelt |
| Gast-`push_name` bei `link_join` (freiform, pro Join gewählt) | der eigene WhatsApp-Profilname des beitretenden Accounts (nicht das, was bei einem Gast-Join im Roster landet) |
| `<key>`/`<hbh_key>`-Wire-Bytes (Binär-Node mit ASCII-Base64-Text, doppelte Dekodierung nötig) | `<token>`/`<auth_token>`-Wire-Bytes (roh binär, einfache Dekodierung) |
| Gast-JID-Allokation (serverseitig, bei Zulassung, pro Call) | normale LID-/PN-JIDs (account-level, persistent) |

---

## 13. Kompletter Ablauf (Gast-Join, aus der Capture)

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

## 14. Gast-Registrierung (Web-Client, tested)

Eine wirklich account-lose Browser-Session — kein vorheriger WhatsApp-Login — registriert eine Wegwerf-Identität, bevor sie überhaupt `link_query` sendet. Evidenz: eine CDP-Capture einer menschengesteuerten Session, die einen echten Call-Link im Browser öffnet; nichts im untenstehenden Ablauf war automatisiert oder skriptgesteuert, abgesehen vom Öffnen der Seite und Eintippen eines Namens.

```
GET https://v.whatsapp.net/v2/guest_reg?...
```

| Parameter | Beispiel | Bedeutung |
|-------|---------|---------|
| `mcc`/`mnc` | `310`/`999` | Dummy-Carrier-Codes |
| `lc`/`lg` | Locale (z. B. `DE`/`DE`) | UI-Locale |
| `device_id` | uuid | browserseitig generierte Device-ID |
| `access_session_id` | uuid | Session-ID |
| `authkey` | base64, 32 Bytes | Curve25519 Noise-Static-Public-Key |
| `e_regid` | base64, 4 Bytes | Registration-ID |
| `e_keytype` | base64, 1 Byte | `0x05` = Curve25519 |
| `e_ident` | base64, 32 Bytes | Signal-Identity-Public-Key |
| `e_skey_id`/`e_skey_val`/`e_skey_sig` | — | Signed-Prekey-ID, Public Key (32 B), Signatur (64 B) |
| `os_name`/`os_version`/`browser`/`browser_version` | UA-Fakten | Client-Fingerprint |
| `web_build_version` | z. B. `2.3000.1052682108` | Client-Build |
| `guest_type` | `guest_calling` | markiert dies als Call-Link-Gast-Registrierung |
| `invite_code` | das Token des Links | welchem Link der Gast beitritt |
| `guest_name` | freiform | der vom Gast eingetippte Anzeigename |
| `id` | 20 Rohbytes | nimmt den Platz ein, den eine Telefonnummer bei normaler Registrierung füllt |
| `backup_token` | 20 Rohbytes | gleich `id` in dieser Capture |

Die Antwort (200, Body nicht erfasst) gibt die Credentials zurück, mit denen sich der Gast einloggt. Strukturell ist dies das **gleiche Registrierungsbündel** (regid, Identity-Key, Signed-Prekey, Signatur) wie die normale WhatsApp-Registrierung — `guest_type`/`invite_code`/`guest_name` sind die einzigen gastspezifischen Ergänzungen, und `guest_reg` ist ein eigener Endpoint, getrennt vom normalen `/v2/reg`-Pfad (**found**, unterschiedliche Hostnamen/Pfade beobachtet; hier nicht gegen Androids eigenen Registrierungscode abgeglichen — siehe `WA_MOBILE_REGISTRATION`-Scope-Hinweis, falls dieses Thema anderswo abgedeckt ist).

Ein CSP-Allow-List-Eintrag für einen Anti-Automation-Challenge-Anbieter war auf der Seite vorhanden, und Gast-Bootstrap-Code referenziert ein Captcha-/Challenge-Konzept, aber kein Challenge-Token wurde in dieser wenig-volumigen, menschengesteuerten Session angefordert oder gesendet (**tested**: hier abwesend; **unknown**: unter welchen Bedingungen es auslöst — risikobasiertes Anti-Abuse-Gating ist die arbeitende Annahme, nicht bestätigt). Dieser Report untersucht diese Kontrolle nicht weiter; das würde bedeuten, einen Anti-Abuse-Mechanismus zu untersuchen, was hier außerhalb des Umfangs liegt.

Clientseitige Evidenz, dass dies ein eigener, gast-bewusster Code-Pfad ist (found, repräsentative Teilmenge vieler ähnlicher Modulnamen, die gesehen wurden): ein Modul zur Teilnehmer-Namensbehandlung und ein gastspezifisches Messaging-/Job-Persistence-Modul, getrennt von den Äquivalenten des normalen Chat-Clients, plus ein Modul, das wörtlich dafür benannt ist, "ob diese Call-UI für einen Gast läuft".

## 15. Noise-Transport für eine Gast-Session (tested)

Die registrierte Gast-Identität loggt sich über **denselben** Transport ein, der bereits in [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) dokumentiert ist: ein längenpräfixierter WebSocket zu `wss://web.whatsapp.com/ws/chat` (beobachteter Alternativ-Port `5222`), das `WA`+Versions-Prologue, und dieselbe Noise-XX-Nachrichtensequenz (ClientHello → ServerHello mit Zertifikatskette → verschlüsseltes ClientFinish, das den Static-/Identity-Key trägt → die erste verschlüsselte `ClientPayload`). Am Handshake-Framing unterscheidet sich nichts für einen Gast; dies bestätigt unabhängig, von einer zweiten Client-Plattform aus (ein Browser, nicht die anderswo in diesem Projekt behandelte Android-App), dass Call-Link-Gäste gewöhnliche Noise-XX-Clients sind, kein paralleles Leichtgewichtsprotokoll.

Ein Proto-Level-Fakt, den dies hinzufügt: `ClientPayload` definiert im gemeinsamen WhatsApp-Proto-Schema bereits ein `AccountType`-Feld (`DEFAULT = 0`, `GUEST = 1`). [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) fand dieses Feld auf Android vorhanden, aber unbeschrieben vor (kein Code-Pfad setzt es — Android ist nie ein Gast). Eine Browser-Gast-Session ist der Client, der es tatsächlich setzt: `accountType = GUEST` ist der eine `ClientPayload`-Unterschied zwischen einer Gast- und einer normalen Client-Anmeldung, zusätzlich dazu, dass die Identität aus `guest_reg` (§14) statt aus normaler Telefon-Registrierung stammt und keine Device-Pairing-Daten trägt.

Das tiefere funktionsgenaue Detail (der exakte Code, der eine Gast-`ClientPayload` aufbaut, und der `guest_reg`-Response-Body) sitzt in lazy-geladenen, session-gated Script-Bundles, die mit der Seite verfallen; es zu beschaffen braucht eine frische Live-Capture mit Script-Source-Zugriff, keinen statischen Fetch. Was oben bereits etabliert ist — der Transport ist unmodifiziertes Noise XX, das Identitätsbündel ist ein normales Registrierungsbündel, und das einzige markierte Feld ist `accountType = GUEST` — hängt nicht davon ab, diese Quelle wiederzugewinnen.

---

## 16. Unknowns

| Punkt | Status |
|------|--------|
| Ort der Token-Generierung (clientseitig erzeugt vs. serverseitig zugewiesen) | Die `createCallLink`-Call-Site führt kein Token-Argument (found); der wahre Ursprung ist native (unknown) |
| Ob eine wirklich account-lose Browser-Session dieselbe entschlüsselte Stanza-Sequenz erzeugt | teilweise aufgelöst (§14–§15): die Session registriert sich über `guest_reg` und loggt sich über denselben Noise-XX-Transport mit `ClientPayload.accountType = GUEST` ein; der entschlüsselte `link_query`/`link_join`-Inhalt selbst wurde für diese Session nicht erfasst |
| Wire-Form der hostseitigen Admit-Aktion (`waiting_room_toggle`/`_admit`) | nicht in dieser Capture (einseitig); nur aus WA_CALL_SIGNALING.md §10.3-Statics beschrieben |
| Warum die Zulassung dem einzigen beobachteten Heartbeat so schnell folgte | aufmerksamer Host vs. eine Auto-Admit-Bedingung — aus dieser Evidenz nicht unterscheidbar |
| Lebensdauer/Wiederverwendung der Gast-JID über wiederholte Joins | nicht beobachtet |
| Ob ein Gast jemals ein `enc_rekey` oder einen Signal-umhüllten Call-Key erhält | in keinem der beiden Capture-Fenster beobachtet |
| `<participant pid jid>`-Mapping unter `<relay>` | in dieser 2-Parteien-Capture nicht vorhanden; unknown, ob Gruppen-Calls mit Gästen es nutzen |
| Zweck der doppelten Base64-Kodierung bei `<key>`/`<hbh_key>` vs. rohem `<token>`/`<auth_token>` | unknown |
| `connected-limit` als clientseitig setzbare Obergrenze vs. immer serverseitig zugewiesen | kein Client-Setter gefunden (found: nur serverseitig zurückgegeben) |
| Rate-Limits/Abuse-Kontrollen bei Link-Erstellung oder Gast-Joins | clientseitig nichts gefunden; Serververhalten unknown |
