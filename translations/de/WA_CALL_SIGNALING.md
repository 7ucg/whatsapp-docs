<!-- src-sha1: 7c179c130d5822c6103aa9a9ae2e6751ec1b0bd8 -->
# WhatsApp Call Signaling — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-24
**Umfang:** Android-Signaling für Sprach- und Videoanrufe: `<call>`-Envelope und Acks, Action-Stanzas (offer, accept, preaccept, reject, terminate, transport, relaylatency, enc_rekey, mute_v2, group_info, group_update, lobby, link_*, waiting_room_*, bcall), Offer-Payload (audio / video / capability / encopt / net), Call-Key und seine Signal-Verschlüsselung, Rekey (v2 / v3), Ableitung der Media-Keys, Relay- und Transportauswahl, ICE / STUN / DTLS / SRTP gegenüber dem WhatsApp-spezifischen Media-Pfad, Gruppenanrufe, Call-Links und geplante Anrufe, Call-Log- und bcall-Nachrichten, Offer-Nack-Codes, Reject- und Terminate-Verhalten, Feature-Flags, Baileys-Vergleich

---

## 1. Was es ist (technisch)

Call Signaling besteht aus einer Menge von `<call>`-Stanzas auf der normalen chatd-Verbindung (siehe [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Jede Stanza trägt genau ein Action-Child. Die Java-Schicht baut und parst keine Call-Stanzas: das übernimmt eine native VoIP-Engine, und Java (a) verpackt ausgehende Children in `<call>`, (b) verschlüsselt den Call-Key per Signal für jedes Gerät, (c) übergibt eingehende Stanzas an die Engine, (d) reagiert auf Engine-Events. Media (RTP-ähnlicher Verkehr zu Relays, ICE, DTLS, SRTP) ist kein Signaling und läuft auf UDP/TCP-Sockets, die der Engine gehören. Alle Aussagen stammen aus statischer Analyse; auf der Leitung wurde nichts mitgeschnitten. Tiers: **found** = in Java oder in nativen Strings gelesen, **inferred** = abgeleitet, **unknown** = nicht aufgelöst.

| Schicht | Name in 2.26.41.6 | Rolle |
|---------|-------------------|-------|
| JNI-Fassade | `Voip` / `VoipNativeImpl` (`com.whatsapp.calling.voipcalling`) | 148 native Methoden (`startCall`, `acceptCall`, `rejectCall`, `nativeHandleIncomingSignalingXmpp`, ...) |
| Outbound-Hook | `OutgoingSignalingHandler` implementiert `SignalingXmppCallback.sendCallStanza(Jid, callId, VoipStanzaChildNode)` | Engine zu Java; Behandlung pro Tag, Call-Key-Verschlüsselung |
| Envelope-Writer | `CIX` (Queue), `C27410BtV` (Call-Stanza), Writer-Thread-Case 206 in `HandlerThreadC21920sG` | baut `<call to id>` |
| Inbound-Handler | `C40641lA` (`CallStanzaHandler`), `BQU` (geparste Call-Stanza), `C83` (Decrypt), `C28120CKj` / `RunnableC29343CoU` (Dispatch an die Engine) | Envelope parsen, `<enc>` entschlüsseln, Engine füttern |
| Engine-Events | `VoipEventCallback`, `VoiceServiceEventCallback` (116 Callbacks) | Engine zu UI / State |
| Crypto-Callback | `DefaultCryptoCallback`, `SignalIdentityCryptoCallback` (`CryptoCallback`) | HKDF / HMAC / Zufall / Ed-Signaturen für die Engine |
| HTTP-Signaling | `VoiceTeeHttpSignalingHandler` (`SignalingHttpCallback`) | alternativer Signaling-Träger, TEE-Request |
| Native Engine | `libwhatsapp.so` (aus dem Superpack-Archiv `libs.so` entpackt; exportiert `Java_com_whatsapp_calling_voipcalling_Voip_*`) | Stanza-Serializer / -Deserializer, Call-State-Machine, Transport, Media |

Punkte, die den Rest des Reports bestimmen:

- Die Stanza-Grammatik liegt im nativen Code: Serializer `serialize_*` (C/C++) und eine Rust-Crate `call_control` (Quellpfade `xplat/wa-voip/rust/call_control/src/stanza_deserializer/...` in ihren Panic-Strings) für das Parsen eingehender Stanzas. Die Voip-Bibliothek ließ sich nicht dekompilieren; jede native Aussage stützt sich nur auf Strings und exportierte Namen (Strings found, Bedeutung inferred).
- Java ist ein dünner Shim, deshalb ist die in Java sichtbare Tag-Menge (10 Tags in `sendCallStanza`) deutlich kleiner als die Menge, die die Engine versteht (Abschnitt 4).
- Der Call-Key wird von der Engine erzeugt und verwendet; Java verschlüsselt ihn mit der gewöhnlichen paarweisen Signal-Session (Abschnitt 6). Derselbe HKDF-Code, den die Engine braucht, ist ein Java-Callback (Abschnitt 7).
- Der WhatsApp-spezifische Media-Pfad (Relay allocate/bind, "WARP"-Pakete, Hop-by-Hop-SRTP, SFrame für Gruppenanrufe) unterscheidet sich vom ICE/DTLS-Pfad im WebRTC-Stil, der als Modus "web_p2p" existiert (Abschnitt 8).

---

## 2. Java- / Native-Schnittstelle

Beim Start registrierte Callbacks (found): `SignalingXmppCallback.sendCallStanza(to, callId, node)` (Engine zu Java, ein Call-Child); `CryptoCallback` (`generateE2EKeysV2`, `getSecureSsrc`, `hkdfSha256`, `hmacSha256`, `generateRandomBytes`; `SignalIdentityCryptoCallback` ergänzt `signWithIdentityKey` mit einer 64-Byte-Signatur und `verifySignature` mit einem 32-Byte-Key); `SignalingHttpCallback` (`sendMsg(callId, bytes, requestType)`, `cancelMsg`; Typen voice session 0, codec avatar 1); `VoipEventCallback` (Abschnitt 13). `VoipStanzaChildNode` ist der JNI-sichtbare Baum (Tag, Attribute, Children, Data); Java wandelt ihn in den chatd-Node und zurück, dessen Binärkodierung in [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) Abschnitt 8 beschrieben ist.

| JNI-Eintrag (found) | Gespeist von | Hinweise |
|---------------------|--------------|----------|
| `nativeParseXmppOffer(CallOfferInfo[], ...)` | `preprocess_call_offer` (`AbstractC24816AmW`) | parst ein Offer, ohne einen Anruf zu starten; `CallOfferInfo`: callId, fromJid, groupJid, callLinkToken, isVideoCall, isAudioChat, isJoinableCall, isOfferExpired, isCallEnded, silenceReason, groupPhash, participantHash, callGroupInfo |
| `nativeHandleIncomingXmppOffer` | `C28120CKj` | startet die Behandlung eines eingehenden Anrufs |
| `nativeHandleIncomingSignalingXmpp` / `...Ack(from, type, errorCode, children, ..)` / `...Receipt` | `RunnableC29343CoU` (Message 192) | jede Nicht-Offer-Action, Acks eigener Stanzas (Rückgabe 70004 wird als korruptes Ack geloggt), Call-Receipts |
| `peekIncomingOffer`, `handleIncomingTerminatePush` | Push-Pfad | Entscheidung vor dem Klingeln, per Push zugestelltes Terminate |
| `handleIncomingSignalingHttp(callId, bytes, ..)` | TEE-HTTP-Antwort | alternativer Träger (11.3) |

---

## 3. Envelope, Acks, Receipts

### 3.1 Ausgehendes `<call>` (found, `HandlerThreadC21920sG` Case 206)

```
<call to="<jid>" id="<stanza id>">
  <ACTION .../>                      exactly one child
</call>
```

`to` muss `C0DZ.A0R` passieren (User, Device und einige andere JID-Typen; sonst wirft `C27410BtV` `CallStanza:Wrong jid type`). Die Stanza-ID kommt vom gemeinsamen ID-Generator. Logzeile `WriterThread/write/call-stanza-<tag>`.

### 3.2 Eingehendes `<call>` (found, `C40641lA`)

| Attribut | Behandlung |
|----------|------------|
| `from` | muss eine gültige JID sein, sonst `CallStanza from invalid jid`; eine User-JID wird auf ihr Primary-Device abgebildet |
| `id` | Stanza-ID, für das Ack verwendet |
| `t` | Sekunden, mit 1000 multipliziert |
| `e` | ganzzahlige Sekunden, mit 1000 multipliziert und neben `t` an die Engine übergeben (genaue Bedeutung ungelöst; inferred: Offer-Alter / Ablauf-Eingabe) |
| `offline` | Integer; Vorhandensein markiert Zustellung aus der Offline-Queue |
| `notify`, `platform`, `version` | durchgereicht (Push-Name des Anrufers, Plattform, App-Version) |
| `participant` | Device-JID des Senders in Gruppenkontexten; ein fehlerhafter Wert fällt auf `from` zurück |
| `sender_lid` | gelesen, wenn `from` eine JID der LID-Domain ist |
| Child `call-creator` | Device-JID (für Nicht-Offer-Logik erforderlich) |
| Child `call-id` | erforderlich; ausgenommen die Tags `reminder` und `bcall_*`, die eine leere Call-ID erhalten |
| weitere Attribute | `caller_pn` (Device-JID der Telefonnummer), `username`, `caller_country_code`; nur gelesen, wenn der Creator LID ist und das Tag nicht `offer` ist |

Liegen `to` und `call-creator` in verschiedenen Adressdomains (eine LID, eine Telefonnummer), loggt der Client `CallStanzaHandler/call-mixed-domain/...`, meldet die Metrik `CallMixedDomainStanza` und fährt fort (found). Gemischte Domains werden toleriert, nicht abgelehnt.

### 3.3 Acks

| Fall | Verhalten (found) |
|------|-------------------|
| Tag nicht in {offer, accept, reject, enc_rekey, terminate} | Java sendet sofort ein Ack: `<ack class="call" type="<tag>" id to [participant]/>` (`AbstractC47181wT.A01`) |
| Tag in dieser Menge | kein sofortiges Java-Ack; der Node geht in einen separaten Pending-Ack-Pfad (`C36591ch.A0G`); Semantik nicht aufgelöst |
| Ack auf eine eigene Stanza | `nativeHandleIncomingSignalingXmppAck(from, type, errorCode, children, ...)`. In Java gesehene Ack-Typen: offer (trägt Relay-Daten, Abschnitt 8), accept, link_join, link_query, lobby; nativ werden außerdem link_create, link_edit, remove, remove_user, heartbeat, screen_share, add_extension, remove_extension, relaylatency, Video-State und waiting_room_* behandelt |
| Offer-Ack mit Fehler 435 | nach dem Ack wird eine zusätzliche Action eingeplant (Zweck nicht aufgelöst) |
| Offer- / Accept-Zustellung | Java wartet mit Timeout auf das chatd-Delivery-Ack (Flags 9257, 9431); bei Timeout wird die Stanza verworfen und `Call stanza delivery timed out` geloggt |

### 3.4 Dictionary-Tokens (found, `AbstractC40911lb`)

Single-Byte (`A00`): `call` 97, `call-id` 101, `call-creator` 68, `terminate` 208, `relaylatency` 70, `video` 86, `audio` 158, `capability` 177, `device-identity` 227, `privacy` 223, `te` 212, `te2` 198, `token` 194, `key` 155, `participant` 5, `user` 14, `remove` 172, `notify` 24, `registration` 170, `attribute_padding` 229, `relay_id` 130, `token_id` 143. Sekundäres Dictionary 0 (`A01[0]`): `offer` 28, `accept` 97, `preaccept` 18, `transport` 44, `mute_v2` 253, `group_info` 170, `group_update` 99, `net` 103, `medium` 36, `encopt` 21, `keygen` 26, `voip_settings` 10, `relay` 116, `joinable` 75, `heartbeat` 6, `transaction-id` 62, `uuid` 132, `self_pid` 71, `peer_pid` 76, `metadata` 118, `uncompressed` 20, `rate` 29, `dec` 73, `screen_width` 5, `reason` 46. Sekundär 1: `reject` 0, `enc_rekey` 205, `e` 235.

In keinem Dictionary dieses Builds (Klartext-Strings auf der Leitung): `lobby`, `flowcontrol`, `screen_share`, `link_*`, `peer_state`, `interruption`, `reminder`, `raise_hand`, `waiting_room_*`, `hbh_key`, `auth_token`, `lightweight`, `silence`, `scheduled-id`, `group-jid`, `link-token`, `caller_pn` und `enc`.

---

## 4. Action-Taxonomie

Eingehende Tags, die der native Deserializer dispatcht (found, String-Liste in `call_control`): `offer`, `accept`, `preaccept`, `reject`, `terminate`, `transport`, `relaylatency`, `enc_rekey`, `notify`, `flowcontrol`, `interruption`, `group_update`, `mute_v2`, `screen_share`, `raise_hand`, `reconfigure_bot`, `user_action`, `ready`, `relay_info_update`, `tos`, `screen`, `switchable`, `add_extension`, `waiting_room_update`, dazu `receipt`. Geparste Acks: offer, accept, Video-State, relaylatency, link_create / edit / query / join, lobby, heartbeat, remove, remove_user, screen_share, add_extension, remove_extension, waiting_room toggle / admit / deny / leave.

| Tag | Richtung (found) | Zweck |
|-----|------------------|-------|
| `offer` | out / in | Anruf starten (Abschnitt 5); in: auch Offers für bereits beendete Anrufe mit `is_call_ended` und `terminate_hint` |
| `preaccept` | out / in | Callee-Gerät klingelt / ist bereit; Engine-State `PRE_ACCEPT_RECEIVED`, Event `preacceptReceived` |
| `accept` | out / in | Callee nimmt an; trägt Media-Parameter und ein Zertifikat (native Strings `error parse voip params for accept`, `error parsing certificate for accept`) |
| `reject` | out / in | Callee lehnt ab; Reason-Strings in Abschnitt 14.2 |
| `terminate` | out / in | Anruf beenden; Transaction-ID und `call_summary` (Abschnitt 14.3) |
| `transport` | out / in | Kandidaten, ICE-Credentials, Zertifikat, Health (Abschnitt 8.5) |
| `relaylatency` | out / in | gemessene Relay-Latenzen (Abschnitt 8.4); hat ein eigenes Ack |
| `enc_rekey` | out / in | erneutes Teilen des Call-Keys (Abschnitt 6.4) |
| `video` (State) | out / in | Video an / aus / Upgrade; `kVideoState*`-Werte (Abschnitt 13); Ack trägt Relay-Info |
| `notify`, `peer_state`, `flowcontrol`, `interruption`, `ready`, `heartbeat` | out / in | In-Call-State: Peer-Hinweise, Netzwerk-Health, Flow Control, Unterbrechungen, Gruppen-Heartbeat |
| `mute_v2`, `raise_hand`, `user_action`, `tos`, `reconfigure_bot` | out / in | Mute-Request in Gruppenanrufen, Handzeichen, User-Actions, Gruppenanruf-TOS, Bot-Rekonfiguration (Attribut `req_id`) |
| `group_info`, `group_update` | in (Child von offer / ack / update) | Roster (Abschnitt 9) |
| `lobby` | out / in | Lobby-Query / -State des Gruppenanrufs; sein Ack trägt Group-Info |
| `screen`, `screen_share`, `switchable` | out / in | Screen-Share-State; Device-Switch (`switch_info`, `root_call_id`, `root_call_creator`, `peer_active_device`) |
| `add_extension`, `remove_extension` | out / in | einen Media-Endpunkt ("Extension") zu einem Anruf hinzufügen (Abschnitt 9.4) |
| `remove`, `remove_user`, `cancel_offer` | out | Teilnehmer entfernen; Offer für ausgewählte Teilnehmer abbrechen |
| `link_create`, `link_edit`, `link_query`, `link_join` | out | Call-Links (Abschnitt 10) |
| `waiting_room_toggle`, `_admit`, `_deny`, `_leave`, `_update` | out / in | Warteraum für Link-Anrufe (Abschnitt 10.3) |
| `reminder`, `bcall_*` | in | Server-Reminder; Business-Call-Familie (Abschnitt 11) |
| `dtmf`, `duration`, `connect_stat`, `group_call_duration`, `group_call_tos_accepted` | out | Serializer in der Engine vorhanden |

In Java sichtbare Tags in `sendCallStanza` (found): `offer`, `accept`, `reject`, `terminate`, `video`, `enc_rekey`, `lobby`, `link_join`, `link_query`, `link_create`; jedes andere Tag nimmt den Standard-Sendepfad.

Numerische Message-ID-Tabelle (85 Typen), Aufteilung nach Mechanismus (Child / Ack / Receipt / intern) und feste Header-Längen: in diesem Build nicht gefunden. Die Engine legt Tags und Serializer pro Tag offen, keine in Strings sichtbare ID-Enum. Jede ID-Tabelle ist für Android als unknown zu behandeln.

---

## 5. Offer

### 5.1 Bauen und Senden (found)

`startCall(...)` lässt die Engine `sendCallStanza(peer, callId, offerNode)` auslösen. Java:

1. `sendOfferStanza` speichert die Stanza-ID (`outgoingCallOfferKey`), wartet, solange ein Pre-Key-Job für irgendein Zielgerät aussteht, und verschlüsselt dann den Call-Key pro Gerät auf einem Worker (`getBulkEncryptedE2EKeys`, Abschnitt 6.1).
2. Das Ergebnis wird entweder im neuen Format (`<destination><to jid><enc/></to>...</destination>`, via `AbstractC33466EhY.A08`) oder im alten Format (einzelnes `<enc>`-Child, nur für ein Gerät gültig; `cannot have multiple encrypted messages in old format!`) geschrieben.
3. Erhielt irgendein Gerät eine `pkmsg`, wird `<device-identity>` (Bytes von `adv_signed_identity` aus den Companion-Preferences) angehängt; das geschieht nur, wenn das eigene Gerät `BRD()` passiert (Registration-Device-ID ungleich null, also ein Companion; inferred).
4. `CIX.A02` reiht die `<call>`-Stanza ein; Flag **9257** (ms) begrenzt das Warten auf die Zustellung.
5. Nach dem Senden wird ein Call-Ping-IQ eingeplant (Flag **30890**, Verzögerung **30891** ms, Default 3000, Versuche **32651**); ist die Verbindung unten, verbindet der Client neu, außer der Anruf ist nicht mehr im State `CALLING`.
6. Lassen sich die Ziele nicht verschlüsseln, bleibt das Offer als `pendingCallOfferStanza` liegen und wird später gesendet (`maybeSendPendingOffer`, wenn ein Pre-Key-Job endet, `sendPendingCallOfferStanza` bei Terminate). `preSendTerminate` entfernt ein nicht bestätigtes Offer aus der Retry-Queue, bevor ein Terminate rausgeht.

### 5.2 Children und Attribute

| Element | Quelle | Attribute / Inhalt |
|---------|--------|--------------------|
| `<offer>` | send | `call-id`, `call-creator` (Device-JID); receive: `caller_pn`, `username`, `caller_country_code`, `group-jid`, `scheduled-id`, `joinable`, `lightweight` (`1` = Lightweight- / Audio-only-Gruppenklingeln), `rering_ts`, `is_call_ended`, `type` |
| `<audio>` (wiederholt) | send | `enc` (Codec), `rate` (Samplerate); `enc` und `rate` sind Dictionary-Tokens |
| `<video>` | send | `enc`, `dec`, `device_orientation`, `screen_width`, `screen_height`; in der Engine gesehene Wert-Strings: `h.264`, `vp8`, `vp8/h.264`; das Attribut `fps` ist ebenfalls als String vorhanden (inferred Video-Attribut) |
| `<net>` | send | `medium` (Netzwerktyp), später `health_status` in transport |
| `<capability>` | send | `ver` + opake Bitmaske (`pjmedia_voip_capabilities_*`: version, `bit_mask_length`); pro Gerät listet der String `vid_dec` die dekodierbaren Video-Codecs (`vid_codec_capability_str_to_bitmask`) |
| `<encopt>` | send | `keygen` = Key-Generation-Version; die Engine lehnt andere Werte ab (`Unsupported keygen ver`); Versionen 2 und 3 existieren (Abschnitt 6.4) |
| `<destination>` / `<to jid>` / `<enc>` | send | verschlüsselter Call-Key pro Gerät (Abschnitt 6.1); `<to>` kann `peer_recipient_lid`, `peer_recipient_pn`, `peer_recipient_username`, `eph_setting` tragen |
| `<tctoken>` | send | innerhalb von `<to>`, höchstens einmal pro User, wenn Flag **20605** an ist und weniger als **20606** User bereits eines tragen; dieselbe Token-Familie wie [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `<device-identity>` | send | Bytes der ADV Signed Identity, siehe 5.1 Schritt 3 |
| `<privacy>` | receive | Privacy-Token (Tokenname im Dictionary vorhanden); Inhalt nicht verfolgt |
| `<relay>` | receive / ack | Relay-Liste (Abschnitt 8) |
| `<voip_settings>` | receive / ack | vom Server gelieferte Engine-Parameter; Attribut `uncompressed`; komprimierte Payloads werden in einem Pfad abgelehnt (`unexpected compressed voip params`) und `zlib inflate` ist gelinkt (Kompressionsformat inferred) |
| `<metadata>` | receive | A/B-Test-Bucket-Attribute des Peers (`peer_abtest_bucket`, `peer_abtest_bucket_id_list`) |
| `<silence reason>` | receive | Offer ist stumm (kein Klingeln); `BQU.A02`; Reason-Ints `kOfferSilenceReason*` (Abschnitt 13) |
| `<group_info>` | receive | Roster eines Gruppenanrufs (Abschnitt 9) |
| `<terminate_hint>` / `<call_summary>` | receive | ein Offer für einen bereits beendeten Anruf (`is_call_ended=1`): `terminate_reason`, Transaction-ID, Summary |
| `<link_info>`, `<waiting_room>`, `<bot>`, Extension-Info | receive | Link-, Warteraum-, Bot- und Extension-Daten |

Die genauen Bytewerte von `<capability>` und der `net medium`-Codes wurden aus diesem Build nicht gewonnen (eine 7-Byte-Maske `01 05 F7 09 E4 BB 13` wird für Web-Clients gelegentlich zitiert; sie liegt in der Android-Bibliothek nicht als zusammenhängendes Literal vor, der Android-Wert ist daher als unknown zu behandeln). Die Engine bündelt die Codecs, die sie in Strings nennt: Opus plus ein hauseigener Low-Bitrate-Codec ("mlow", Opus-gerahmt), OpenH264, VP8, AV1 (`wzav1`) und HEVC über MediaCodec.

### 5.3 Empfangspfad (found)

1. `CallStanzaHandler` baut `BQU`; Metrik `CallStanzaHandler/handleStanza tag=... callId=...`; Message 192 wird an den Dispatcher gepostet.
2. Bei einem Offer führt `preprocess_call_offer` `nativeParseXmppOffer` aus; ein Rückgabewert ungleich null verwirft die Stanza. Abgelaufene oder beendete Offers klingeln nicht.
3. `C83.A00` entschlüsselt das `<enc>` (Abschnitt 6.2), dann startet `nativeHandleIncomingXmppOffer` den Anruf; State `RECEIVED_CALL`.
4. `peekIncomingOffer` (Push-getriebener Vorabcheck) ignoriert stumme Offers, Gruppen-Offers (`group_info` vorhanden), Offers mit `is_call_ended=1`, 1:1-Offers ohne `<enc>` und Offers, während das Telefon belegt ist; Flag **4217** Bit 1 aktiviert Voice-Peeks, Bit 2 Video-Peeks.
5. Ein späteres `terminate` oder der Push `handleIncomingTerminatePush` beendet einen Peek.

---

## 6. Call-Key und seine Verschlüsselung

### 6.1 Outbound (found, `getBulkEncryptedE2EKeys`)

Die Engine liefert eine Map von Device-JID auf rohe Call-Key-Bytes. Für jedes Gerät ohne ausstehenden Pre-Key-Job baut der Client ein `Message`-Protobuf und verschlüsselt es per Signal mit der vorhandenen paarweisen Session (`C83` / `CallableC29363Coo`):

| Message.Call-Feld | Nummer | Typ | Gesetzt, wenn |
|-------------------|--------|-----|---------------|
| `callKey` | **1** | bytes | immer (32 Rohbytes) |
| `conversionSource` / `conversionData` / `conversionDelaySeconds` | **2** / **3** / **4** | string / bytes / uint32 | CTWA-Daten vorhanden |
| `ctwaSignals` / `ctwaPayload` | **5** / **6** | string / bytes | CTWA-Daten vorhanden |
| `contextInfo` | **7** | ContextInfo | CTWA-Flag (`externalAdReply.adType` auf einen festen Wert gesetzt) |
| `nativeFlowCallButtonPayload` | **8** | string | Anruf aus einem Native-Flow-Button gestartet |
| `deeplinkPayload` | **9** | string | Anruf aus einem Deeplink gestartet |
| `messageContextInfo` | **10** | MessageContextInfo | Anreicherung pro Peer durch `AbstractC30999De0` (Inhalt nicht verfolgt) |
| `callEntryPoint` | **11** | uint32 | Flag **24935**, nur beim initialen Fanout (`i == 0`) |
| `callReason` | **12** | string | im Proto vorhanden, in diesem Pfad nicht gesetzt |

`Message.call` ist Feld **10** von `Message` (`C30628DTw`), Klasse `Message.Call` = `C25827BCl`. Für das initiale Offer fügt Flag **520** Ad-Attribution-Kontext aus dem CTWA-Resolver hinzu (`C35832FfR`; inferred). Ein Fanout läuft mit `i == 0` für Offers und `i == 1` für Rekeys. Die Verschlüsselung blockiert mit einem Cancel-Pfad; ein Block über 5000 ms loggt `voip_e2e_encryption_blocked`.

Wire-Form eines Geräts (found, `AbstractC33466EhY.A03/A09`): `<enc v="<version>" type="msg|pkmsg|skmsg|frskmsg|msmsg" [count="<retry>"] [mediatype] [session_type="pq"] [bucket]>CIPHERTEXT</enc>`. `session_type="pq"` markiert eine Post-Quantum-Signal-Session; `count` entfällt bei 0. Call-Keys sind in diesem Pfad nie Gruppen-Sender-Key-Nachrichten (der Typ `skmsg` wird vom Helper akzeptiert, aber kein Call-Pfad erzeugt ihn; inferred).

Extension-Geräte (JID-User-Präfix `01`) nutzen `sendReKeyToExtension`: ein zuvor gepuffertes Prekey-Bundle wird verarbeitet, der Key wird als `pkmsg` mit `v="2"` verschlüsselt (found).

### 6.2 Inbound (found, `C83.A00`)

| Schritt | Detail |
|---------|--------|
| gelesene Children | `registration` (muss 4 Bytes sein; Signal-Registration-ID, für Retry verwendet), `device-identity`, `enc` |
| Duplikate | ein zweites `<enc>` wird verworfen (`duplicate <enc>`) |
| Retry-Count | `count` auf `<enc>`; fehlender Wert bricht ab (`invalid retry count`) |
| Typ | `msg` 0 oder `pkmsg` 1 akzeptiert; andere Zahlen loggen `unrecognized ciphertext type` |
| Decrypt | paarweises Signal-Decrypt (Pre-Key-Message mit der Device-Identity des Senders verarbeitet); Payload als `Message` geparst, `call.callKey` entnommen; `ExternalAdReplyInfo.adType` von CAWC wird geloggt |
| Ergebnis | `<enc>` wird durch einen schlichten `<enc>`-Node mit den Call-Key-Bytes für die Engine ersetzt |
| Fehler | Event `rejectedDecryptionFailure`, `onPeerE2EDecryptionFailed` wiederholt den Session-Aufbau (neuen Pre-Key holen, wenn die Registration-ID gleich ist und der Base-Key sich wiederholt); der Reject-Reason `enc` wird gesendet, wenn der Anruf nicht entschlüsselt werden kann |

Flag **24063** ändert den Session-Type-Pfad, der für Ciphertexts vom Typ hosted verwendet wird (inferred aus der Bedingung in `c33281EeX.A04`).

### 6.3 Retry

`sendOfferRetryRequest(device)` lässt die Engine das Offer erneut senden (`resendOfferOnDecryptionFailure`); `sendPendingRekeyRequest` wiederholt einen Rekey-Request, solange das gespeicherte Retry-Byte in 0..4 liegt. `count` reicht daher von 0 bis 4 (found, `sendPendingRekeyRequest`).

### 6.4 `enc_rekey`: drei Formen

| Form | Evidenz | Inhalt |
|------|---------|--------|
| v2 Unicast | `sendReKeyStanza` (Java) | Engine emittiert `<enc_rekey call-id call-creator transaction-id><enc count=N>RAW KEY</enc></enc_rekey>`; Java ersetzt das Child durch das Signal-verschlüsselte `<enc>` für das Zielgerät (found) |
| v2 Fanout | `sendReKeyFanoutStanza` | Ziel ist eine Gruppe; Child `<destination><to jid><enc/></to>...`; jeder Eintrag wird separat verschlüsselt (found) |
| v3 | native Strings `handle_enc_rekey_v3`, `make_and_send_rekey_v3`, `ext_rekey: ...` | Payload ist ein Protobuf mit wiederholten `wa.voip.RekeyKeyEntry` (Key-Typ + Key); Keys pro Typ haben eine feste Länge (`key type %d has unexpected length`); gewählt bei keygen 3; benötigt Extension-Support (`kCallExtensionMV1`); Übergang v3 zu v2 wird geloggt |

In Strings sichtbare Regeln: Rekeys tragen eine Transaction-ID; frühe, alte oder gleiche IDs werden ignoriert (`ignore old rekey msg with transaction id`); in einem Eins-zu-eins-Anruf wird eingehendes `enc_rekey` ignoriert (`ignore rekey msg in one to one call`); `request_keys` bittet den Creator oder eine Extension, Keys erneut zu senden (nur v3; `request_keys with unexpected keygen` wird ignoriert). Welche Seite in einem Gruppenanruf einen Rekey startet und der genaue Auslöser sind nicht aufgelöst.

---

## 7. Ableitung der Media-Keys

### 7.1 Java-Callbacks (found)

| Callback | Berechnung |
|----------|------------|
| `generateE2EKeysV2(callKey[32], out[46], info)` | HKDF-SHA256, Salt = 32 Nullbytes, IKM = Call-Key, info = UTF-8-String `info` von der Engine, 46 Ausgabebytes (`E2E_EXTENDED_V2_KEY_LENGTH`) |
| `hkdfSha256(salt, ikm, info, out)` | generisches HKDF-SHA256 (erstes Argument Salt, zweites IKM, drittes info; Ausgabelänge = `out.length`) |
| `getSecureSsrc(ikm, info, salt[4], out[4])` | HKDF-SHA256 auf 4 Bytes (`SECURE_SSRC_LENGTH`) |
| `hmacSha256(key, data, out[32])` | HMAC-SHA256 |
| `generateRandomBytes(out)` | `SecureRandom` (Quelle des 32-Byte-Call-Keys; inferred) |

### 7.2 Labels und Kontexte in der Engine (Strings found, Rolle inferred)

`e2e sframe key`, `hbh srtp key`, `uplink hbh srtcp key`, `downlink hbh srtcp key`, `warp auth key`; Funktionen `derive_sframe_key`, `derive_hbh_srtp_key`, `derive_and_update_warp_mi_keys`, `derive_extension_per_media_key`; Key-Slots `owner_e2e_key`, `extension_audio_key`, `extension_video_key`, `extension_appdata_key`.

| Key | Quelle (inferred) | Schützt |
|-----|-------------------|---------|
| E2E-SRTP-Material | Ausgabe von `generateE2EKeysV2` (46 Bytes), pro Teilnehmer | Media zwischen Endpunkten (1:1) |
| SFrame-Key | Label `e2e sframe key` | Frame-Verschlüsselung in Gruppen- / SFU-Anrufen und im Hop-by-Hop-Data-Channel (`wa_sframe_encrypt`, `sframe_keyprovider_set_chainkey`) |
| Hop-by-Hop-SRTP / -SRTCP | vom Relay gelieferter `hbh_key` (Abschnitt 8.2) mit den `hbh ...`-Labels | nur die Strecke Client zu Relay |
| WARP-MI-Key | Label `warp auth key` | Message-Integrity-Tag der WARP-Pakete (`warp_mi_tag_len`) |

Key-Layouts (welche der 46 Bytes Key oder Salt sind, pro Richtung), der Inhalt des `info`-Strings und die genauen HKDF-Ketten für SFrame / Hop-by-Hop wurden nicht gewonnen: die Aufrufer liegen in nativem Code, der nicht dekompiliert werden konnte. Eine geräte-qualifizierte JID als `info` ist plausibel, aber nicht verifiziert (**unknown**).

---

## 8. Relay, Transport und Media-Pfad

### 8.1 Was der Client erhält

Relay-Daten kommen im Offer-Ack (Caller; `error during parsing relay info`, `Failed to parse relay info in offer ack`), im Offer selbst (Callee) und später in `relay_info_update` sowie im Ack einer `video`-State-Änderung (found).

### 8.2 `<relay>`-Grammatik (found, `fill_relay_info`-Strings)

| Element | Name | Hinweise |
|---------|------|----------|
| Relay-Attribute | `uuid`, `self_participant_uuid`, `conn_id`, `medium`, `warp_mi_tag_len`, `prefer_relay`, `prefer_ipv6`, `peer_dl`, `smart_transport_signal`, `attribute_padding` | pro Relay-Set |
| Tokens | Liste `<token>` (`token_id`), mindestens eines erforderlich (`relay_token_list.num_tokens < 1`) | Relay-Credential; Liste wird in den Allocate-Request kopiert |
| Auth-Tokens | `<auth_token>` (`auth_token_id`) | statt eines Tokens verwendet, wenn die ID im Bereich liegt; sonst "falling back to relay token" |
| Key | `<key>` | Relay-Passwortmaterial |
| `hbh_key` | Child mit Rohbytes oder Base64-Bytes | Quelle des Hop-by-Hop-Keys; die Größe wird geprüft (`HBH Key of unexpected size`, "though warp_mi_tag_len = ...") |
| Endpunkte | `<te>` oder `<te2>` | nie beide (`can not receive both te and te2 endpoints`); Adressbytes IPv4 oder IPv6 (`endpoint too short for an IPv6 address`); leere Adresse abgelehnt |
| pro Endpunkt | `relay_id`, `relay_name` (gekürzt, wenn zu lang), `domain_name`, `latency`, `c2r_rtt`, `ul_bw`, `dl_bw`, `is_favored` | `latency` seedet die Relay-Wahl |
| Teilnehmer | `<participant pid jid>` | bildet Teilnehmer-IDs ab, die in WARP- / SFU-Paketen verwendet werden |

Logstrings geben Relay-Adressen über einen Platzhalter `[MetaServiceIP]` aus, Relay-Adressen werden also als Service-IPs behandelt.

### 8.3 Relay-Auswahl (Strings found, Logik inferred)

1. Der Client bindet sich an die angebotenen Relays (`wa_transport_p2p_start_relay_binds`; Bind- / Alloc-Requests sind STUN-artig, `wa_stun_*`, Transaction-IDs `tid=0x...`; Bind und Unbind brauchen Message Integrity).
2. Die Latenz wird durch Ping-Requests pro Relay (`Ping request sent to relay N`), einen TCP-Prober (`wa_transport_tcp_prober_*`) und Allocate-Roundtrips gemessen; der beste wird zum "elected relay" (`Elected relay idx=...`, `wa_transport_get_elected_relay_approximate_e2e_rtt`); ein Arbiter (`wa_transport_path_arbiter_*`) wechselt Pfade, und `prefer_relay` erzwingt Relay-Nutzung.
3. Eine aus der Allocate-Antwort gelernte Server-Reflexive-Adresse wird geloggt (`Server reflexive addr`).
4. Peer-to-Peer wird parallel über Kandidatenpaare versucht (`p2p add_cand_pair`, `e2e bind probe`); das Relay bleibt Fallback.

### 8.4 `relaylatency` (found)

Serializer und Handler: `serialize_relay_latency`, `send_or_enqueue_relay_latency`, `handle_relay_latency`, `unpack_and_apply_relay_latency`, gebatcht (`prepare_batched_relay_latencies`), mit Ack-Parsing `relaylatency ack: call_id is empty / has invalid type`. Die Stanza meldet die gemessene RTT des Senders pro Relay-Index an den Peer, der sie anwendet (`apply_relay_latencies`, Schwellen `Ignored higher relay latency ...`). Latenz wird in Gruppenanruf-Offers übersprungen (`Skip relay latency at call offer in group calls`).

### 8.5 `transport` (Strings found)

Attribute und Children: `transport-message-type`, `p2p-cand-round` (ein Restart erhöht die Runde und löscht Remote-Kandidaten), `ice-ufrag`, `ice-pwd`, `<certificate algorithm fingerprint>` (`cert_algorithm`, `cert_fingerprint`), `health_status`, Kandidateneinträge (Adresse, Priorität). Der String `Web P2P: skipping type 13 send` zeigt, dass der Message-Typ 13 zum Web-P2P-ICE- / DTLS-Austausch gehört. Die übrigen Subtyp-Nummern wurden nicht gewonnen (**unknown**).

### 8.6 Zwei Media-Pfade

| Aspekt | WhatsApp-Relay-Pfad (Standard) | Web-P2P-Pfad |
|--------|-------------------------------|--------------|
| Aufbau | Relay allocate / bind (STUN-artig), Tokens aus dem Signaling | ICE-Credentials und DTLS-Zertifikat-Fingerprint werden in `transport` ausgetauscht; `wa_ice_transport`, `CreateDtlsTransport` |
| Paketform | WhatsApp-Pakete mit RTP-Payload ("WARP", `warp_mi`-Integritätstag, Piggyback, FEC, `warp_rtx`) | RTP über DTLS-SRTP |
| Hop-Key | Relay-`hbh_key` (Hop-by-Hop-SRTP / -SRTCP, Hop-by-Hop-DTLS zum Relay `hbh_dtls_handshake_*`) | DTLS-abgeleitet |
| E2E | E2E-SRTP in 1:1, SFrame in Gruppen (SFU) | SRTP |
| Zweck | normale App-zu-App-Anrufe | Interop mit dem Web-Client (`set_peer_is_web`, `handle_transport_web_p2p`); inferred |
| TLS-Stack | statisch gelinktes mbedTLS (`mbedtls_ssl_*`, `mbedtls_gcm_*`, `mbedtls_hkdf`) | gleich |

Gruppenanrufe nutzen eine SFU mit Subscriptions (`RxSubscriptions`, `SenderSubscriptions`, `wa.voip.*`-Protobufs im Data Channel) statt Pfaden pro Peer; die Bandbreitenschätzung läuft pro Pfad (`wa_warp_sfu_*`, "one side BWE").

---

## 9. Gruppenanrufe

### 9.1 `group_info` (found, Strings aus `shared_elements/group.rs`)

| Element | Name | Hinweise |
|---------|------|----------|
| Attribute | `connected-limit`, `phash`, `transaction-id`, `media`, `joinable` | Roster-Hash und Ordnungs-ID; `group_info has invalid connected_limit` |
| Mitglieder | `<user jid [user_pn push_name guest_name account_kind state ..]>` mit `<device jid ..>`-Children, oder `<participant jid pid>`; `<bot jid>` | `<user>` und `<participant>` zusammen sind ein Fehler |
| pro User | `state`, `pid`, `capability` (`ver`), `rekey`, `terminated`, `connected`, `country_code`, `reason` | Device-Listen für nicht genackte User erforderlich |
| Extensions | `extension_creator`, `ext_creator_identity_key_sig`, `extension_id`, `hn_video`, `gen`, `cohost`, `scope` | Extension- / Co-Host-Daten |

### 9.2 Verhalten

- Limit `Voip.kMaxSupportedGroupCallParticipants` = 64 (found); die Engine beendet einen Anruf, dessen Update das Maximum überschreitet.
- `group_update` und Gruppenanruf-`terminate` tragen Transaction-IDs; veraltete oder nicht in Reihenfolge eintreffende werden ignoriert; `kInitialGroupTransactionId` = -1 (found).
- Das Gruppen-Offer trägt keinen Call-Key pro Gerät; Keys werden pro Gerät mit `enc_rekey` neu geteilt (inferred aus `sendReKeyFanoutStanza`).
- Klingel- und Roster-Actions: `invite`, `inviteToGroupCall`, `cancelInviteToGroupCall`, Re-Ring (`rering_ts`, `make_and_send_cancel_offer_for_participants`), `sendRaiseHand`, `sendMutePeerRequestInGroupCall`, `sendRemoveRequest`; `lobby` ist der Join-Schritt eines laufenden Gruppenanrufs (`joinOngoingCall`).
- Extensions: `add_extension` / `remove_extension` hängen einen zweiten Media-Endpunkt an einen Anruf (`wa_call_extension_jid_*`, Owner- und Extension-Keys in 7.2, `kCallExtensionMV1`; Java behandelt Extension-JIDs mit User-Präfix `01` gesondert, 6.1). Die Geräteklasse ist ungelöst (inferred: ein gekoppeltes Wearable, die App liefert `libsmartglasses-bundle.so` und `Voip.sendWearableAttribution` mit).

---

## 10. Call-Links, Warteraum, geplante Anrufe

### 10.1 Links (found)

| Element | Wert |
|---------|------|
| URL | `https://call.whatsapp.com/{voice|video}/{token}`; Manifest-Host `call.whatsapp.com` |
| Token-Länge | `Voip.kCallLinkTokenLength` = 22 |
| create | `Voip.createCallLink(isVideo, eventStartTimeSec, waitingRoomEnabled)` (Log `actionCreateCallLink` / `actionCreateCallLinkForEvent`); natives `wa_call_link_create_v2` lehnt eine ungültige Startzeit ab |
| edit / preview | `editCallLink(token, ..., startTime, int)`, `previewCallLink`, `queryCallLinkForLinkEdit`; Stanzas `link_edit`, `link_query` |
| join | `joinCallLink` sendet `link_join`; das Ack `LinkJoinAck` trägt `call-creator`, `group_info`, `voip_settings`, Link-Info |
| Link-States | `kCallLinkState`: None 0, QuerySent 1, QueryAcked 2, JoinSent 3, JoinAcked 4 |
| `CallLinkInfo` | creatorJid, token, videoEnabled, eventStartTsSec, isGuestEligible, linkState, waitingRoomState, self |
| Nack-Events | `linkCreateNacked`, `linkQueryNacked`, `linkJoinNacked`, `linkEditNacked` mit dem Ack-Fehlercode |

Link-Stanzas sind an eine JID der Call-Domain adressiert (der Rust-JID-Parser listet `callDomainJID` und `callJID`; der von `C0DZ.A0R` akzeptierte JID-Typ, der dazu passt, wurde nicht aufgelöst).

### 10.2 Event-Anrufe (geplant)

Ein Event-Anruf ist ein Call-Link, der mit einem `eventStartTimeSec` ungleich null erzeugt wurde (found). Das Offer für einen geplanten Anruf trägt `scheduled-id` (im Parser gefunden). `Message` trägt zwei Chat-Nachrichten:

| Message-Feld | Nummer | Typ | Inhalt (found) |
|--------------|--------|-----|----------------|
| `scheduledCallCreationMessage` | **61** | ScheduledCallCreationMessage | `scheduledTimestampMs` 1, `callType` 2 (UNKNOWN 0, VOICE 1, VIDEO 2), `title` 3 |
| `scheduledCallEditMessage` | **65** | ScheduledCallEditMessage | `key` 1 (MessageKey), `editType` 2 (UNKNOWN 0, CANCEL 1) |

Als Edit existiert nur Cancel. Lokale Speicherung (found): Tabellen `message_scheduled_call` (`scheduled_timestamp_ms`, `call_type`, `title`), `message_add_on_scheduled_call_edit` (`creation_message_row_id`, ...), `message_system_scheduled_call_start` (`call_title`, `call_timestamp_ms`), `scheduled_calls` (`key_chat_row_id`, `key_id`, `scheduled_timestamp`, `is_upcoming`, `call_log_row_id`). Der serverseitige Reminder (ein `reminder`-Call-Child, `kServerReminder*` unten) und wie die Creation-Message mit dem Call-Link-Token verknüpft ist, sind nicht aufgelöst.

### 10.3 Warteraum

Stanzas `waiting_room_toggle` (`link-token`, `media`, `enabled`, Variante für aktiven Anruf), `_admit`, `_deny`, `_leave`, `_update`; geparste User-Felder `jid`, `user_pn`, `push_name`, `guest_name`, `is_guest_eligible`, `state`. Java: `waitingRoomAdmit`, `waitingRoomAdmitAll`, `waitingRoomDeny`, `waitingRoomToggle`; Events `waitingRoomAdmitAcked`, `waitingRoomDenyAcked`, `waitingRoomStateChanged`, `waitingRoomDenied`. `kServerReminder`: Legacy 0, LinkJoinedCreator 1, LinkJoinedJoiner 2, LinkConnectedCreator 3, LinkMissedCreator 4, LinkCreatorWaitingRoomJoined 5, LinkCreatorWaitingRoomMultipleJoined 6.

---

## 11. bcall, Bot und alternative Träger

### 11.1 `bcall`-Chat-Nachricht (found)

| Feld | Nummer | Typ | Verwendung |
|------|--------|-----|------------|
| `sessionId` | **1** | string | Business-Call-Session |
| `mediaType` | **2** | enum | UNKNOWN 0, AUDIO 1, VIDEO 2 |
| `masterKey` | **3** | bytes | erforderlich: fehlender Key wirft `bcall message doesn't have master key` |
| `caption` | **4** | string | optional |

`Message.bcallMessage` = Feld **72** (Klasse `DSA`); Handler `F2V` (`FMessageBCallProtobuf`) bildet es auf Message-Typ 91 ab, mit Session-ID, Media-Typ (0 unknown, 1 audio, 2 video), Caption und Master-Key-Bytes. Der `master key` ist ein Key, der innerhalb einer Ende-zu-Ende-verschlüsselten Chat-Nachricht zugestellt wird; was er schlüsselt (inferred: die Media eines Business-Calls), ist nicht verfolgt. Engine-Events `bCallCreated(callId, key, ...)`, `bCallJoined`, `bCallEnded`, `bCallAudienceUpdated`, `bCallCreateFailed`; `CallState.BCALL_STARTING`; eingehende `<call>`-Children mit dem Namen `bcall_*` erhalten eine leere Call-ID (3.2). Native Strings `bcall_start`, `bcall_notify` existieren.

### 11.2 Bot-Anrufe und HTTP- / TEE-Signaling

Bot-Anrufe: `CallInfo.isBotCall`, `<bot>`-Nodes in `group_info`, `verifyIncomingBotIdentityKey`, `reconfigure_bot` (`req_id`), Bot-TOS-Flow (Nack 488); das Offer wird mit einem gecachten Payload-Builder zusammengeführt. Kontext: [WA_META_AI.md](WA_META_AI.md). Davon getrennt lässt `SignalingHttpCallback.sendMsg` die Engine opake Signaling-Bytes über `TeeRequestHandler` statt über chatd austauschen (`handle_http_tee_start_session_response`, `handle_http_create_extension_response`); Request-Typen voice session und codec avatar. Berechtigung und Payload-Format sind **unknown** (inferred: Bot- und Avatar-Sessions).

---

## 12. Call-Log und Verlauf

### 12.1 `callLogMesssage` (Message-Feld **69**, Klasse `C49434Loq`, found)

| Feld | Nummer | Typ | Werte |
|------|--------|-----|-------|
| `isVideo` | **1** | bool | |
| `callOutcome` | **2** | enum | CONNECTED 0, MISSED 1, FAILED 2, REJECTED 3, ACCEPTED_ELSEWHERE 4, ONGOING 5, SILENCED_BY_DND 6, SILENCED_UNKNOWN_CALLER 7 |
| `durationSecs` | **3** | int64 | |
| `callType` | **4** | enum | REGULAR 0, SCHEDULED_CALL 1, VOICE_CHAT 2 |
| `participants` | **5** | repeated `CallParticipant` | `jid` 1 (string), `callOutcome` 2 (gleiche Enum) |

Builder `C53129Nna` (found): das Call-Log-Ergebnis der Engine (`Voip.kCallLog*`) wird wie folgt abgebildet.

| Ergebnis `kCallLog` | Wire-`callOutcome` |
|---------------------|--------------------|
| Canceled 1, Missed 2 | MISSED |
| Unavailable 3 | FAILED |
| Rejected 4 | REJECTED |
| Connected 5 | CONNECTED |
| AcceptedElsewhere 6, ScreenedElsewhere 9 | ACCEPTED_ELSEWHERE |
| Invalid 0, Failed 7, ConnectedLonely 8, andere | ONGOING (dekompilierter Default-Zweig) |
| DND-Flag / Unknown-Caller-Flag am Record | SILENCED_BY_DND / SILENCED_UNKNOWN_CALLER (zuerst geprüft) |

Dass Failed 7 auf ONGOING abgebildet wird, wirkt falsch, ist aber der dekompilierte Default-Zweig; als gelesen behandeln, nicht als verifiziertes Verhalten. Call-Typ: lokaler Typ 1 wird auf SCHEDULED_CALL abgebildet, 2 oder 3 auf VOICE_CHAT, sonst REGULAR. Ein fehlender Call-Typ wirft `call log message missing call_type`.

### 12.2 Lokale Datenbank (found)

Tabellen: `call_log` (`jid_row_id`, `from_me`, `call_id`, `transaction_id`, `timestamp`, `video_call`, `duration`, `call_result`, `is_dnd_mode_on`, `bytes_transferred`, `group_jid_row_id`, `is_joinable_group_call`, `call_creator_device_jid_row_id`, `call_random_id`, `call_link_row_id`, `call_type`, `offer_silence_reason`, `scheduled_id`, `telecom_uuid`, `terminated_by_device_switch`), `call_log_participant_v2` (`call_log_row_id`, `jid_row_id`, `call_result`), `joinable_call_log` (`call_id`, `joinable_video_call`, `group_jid_row_id`, `phash_identifier`, `self_other_device_connected`, `is_lgc_add`), `message_call_log`, `call_unknown_caller`, `reminder`. Speisende Events: `callEnding(CallLogInfo, ..)`, `update1to1CallLog`, `updateJoinableCallLog` (`kUpdateJoinableCallLogType` Create 1, Update 2, Delete 3).

---

## 13. Engine-States und Konstanten (found, `Voip.java`, `CallState`)

| Gruppe | Werte |
|--------|-------|
| `CallState` | NONE, CALLING, PRE_ACCEPT_RECEIVED, RECEIVED_CALL, ACCEPT_SENT, ACCEPT_RECEIVED, ACTIVE, ACTIVE_ELSEWHERE, REJOINING, LINK, CONNECTED_LONELY, PRECALLING, ENDING, BCALL_STARTING, SCREENING |
| `kCallLog*` | Invalid 0, Canceled 1, Missed 2, Unavailable 3, Rejected 4, Connected 5, AcceptedElsewhere 6, Failed 7, ConnectedLonely 8, ScreenedElsewhere 9 |
| `kCallEndReason*` | Unknown 0, Timeout 1, Self 2, RejectDoNotDisturb 3, RejectBlocked 4, MicPermissionDenied 5, CameraPermissionDenied 6 |
| `kFatalReason*` | Unknown 0, ParticipantAllocationFailure 1, CallSetupError 2, CallTxTimeout 3, CallRxTimeout 4, VideoStreamCreateError 5, VideoPortCreateFailed 6, NoSamplingRatesForAudioRecord 7, AudioInitError 8 |
| `kOfferSilenceReason*` | None 0, Privacy 2, Lightweight 3, ScreenSharing 4, AddedAsLinkCreator 9, AddedForDeviceSwitching 10, GroupChatAdd 11 |
| `kParticipant*` | Connected 1, Incoming 2, Ringing 3, Rejected 4, Terminated 5, TimedOut 6, CreatingCall 7, Invited 11 |
| `kVideoState*` | Disabled 0, Enabled 1, Paused 2, UpgradeRequest 3, UpgradeAccept 4, UpgradeReject 5, Stopped 6, UpgradeRejectByTimeout 7, UpgradeCancel 8, UpgradeCancelByTimeout 9, UnknownPeer 10, Xr2dCodecAvatarEnabled 12, Error 20 |
| `kStatus*` | Success 0, InvalidArgument 70004, Exists 70015, Ignored 70020, CallAlreadyStarted 670001, CallNotActive 670007, CallHasNoVideo 670018, GroupCallUserExists 670021, GroupCallPeerCodecMismatch 670033, GroupCallUserExistsNotInvited 670038, NotPermitted 670040, UserNotRemovable 670041, UserNotConnected 670042 |
| `kScreenShareVersion*` | Legacy 0, 1 to 4 |
| `kNetworkHealth*` | Measuring 0, NoNetwork 1, Poor 2, Average 3, Good 4 |

`kCallEndReason`-Ints sind das, was die UI sieht; die für Terminate auf die Leitung gelegten Strings gehören nicht zu den Strings der Bibliothek (14.3).

---

## 14. Fehler, Reject, Terminate

### 14.1 Offer-Nack-Codes (found, `VoiceServiceEventCallback.callOfferNacked`)

Ein Offer-Ack mit Fehlern ruft `callOfferNacked(errors[])` auf. Ein einzelner Fehler 304 oder 400 gilt als doppeltes Offer und wird ignoriert. Der Nack ist fatal, wenn der Anruf `CALLING` / `CONNECTED_LONELY` ist und alle Empfänger (oder man selbst) genackt wurden, oder der Code 432 ist; sonst pro Empfänger und nicht fatal.

| Code | Fataler Pfad (dekompilierter Zweig) | Nicht-fataler Pfad |
|------|-------------------------------------|--------------------|
| 401 | Not-allowed-Screen (Reason-ID 3) | |
| 403 | Not-allowed-Screen, videospezifische ID bei Video | |
| 404 | Not-allowed-ID 16 | Text "contact unavailable" pro Empfänger |
| 405 | ID 4 | |
| 406 | ID 2 (Audio) / 11 (Video) | |
| 411 | ID 11, oder 37 für Lightweight | |
| 412 | ID 10; Group-Info wird bei Mitgliedschaftsabweichung aktualisiert | |
| 426 | ID 1 (Audio) / 9 (Video) | |
| 427 | ID 12, oder 36 für Lightweight-1:1 | Text pro Empfänger; in Gruppen mit mehr als 4 Teilnehmern eine alternative ID |
| 428 | ID 14 | Text pro Empfänger |
| 429 | nur UI-Event | |
| 431 | ID 15 | Text "not available" |
| 432 | ID 2; immer fatal | |
| 435 | | Text pro Empfänger; nach einem Offer-Ack löst es zusätzlich eine Extra-Action aus |
| 460 / 463 | Video 10 / Audio 2; 463 ID 17 | |
| 488 | Bot-TOS nicht akzeptiert: öffnet den Bot-TOS-Flow | gleich |
| 467, 468, 469 | | ID 46 bei mehreren Empfängern |
| 500, 502 | | Text "not available" |
| 538 | | ID 35 |
| andere | Default-ID (Video 8 / 0) | Assertion `Unknown error code` |

Im dekompilierten fatalen Zweig sind einige Returns verloren gegangen, die IDs sind daher nur richtungsweisend; die Code-Liste und die Aufteilung fatal / nicht fatal sind belastbar. Die Bedeutung der Codes über die Client-Reaktion hinaus liegt serverseitig (**unknown**). Nach einem Nack des kompletten Offers sendet die Engine keine Call-Stanza außer `terminate` (String found).

### 14.2 Reject-Reasons (found, `Voip.REJECT_REASON_*`)

| String | Bedeutung / Client-Reaktion |
|--------|-----------------------------|
| `` (leer) | abgelehnt |
| `busy` | Callee belegt; Besetztton, Anruf endet nach einer Verzögerung |
| `unavailable` | Konstante definiert; Hauptverwendung im Presence- / Verfügbarkeits-Code gefunden |
| `uncallable` | Peer kann nicht angerufen werden; Not-allowed-Screen |
| `tos` | Peer hat die TOS nicht akzeptiert; Not-allowed-Screen |
| `enc` | Entschlüsselung des Call-Keys fehlgeschlagen |
| `server_conf_corrupted` | Serverkonfiguration unbrauchbar |

`rejectCall(callId, reason, int)` und `rejectPendingCall` sind die Einstiegspunkte; `callRejectReceived` verarbeitet eingehende Reasons. Reject-Reasons werden auf lokale Call-Ergebnisse abgebildet (`reject_reason_to_call_result`, `set_call_term_reason_from_received_call_reject_reason`).

### 14.3 Terminate (Strings found)

- `terminate` trägt eine Transaction-ID und einen `call_summary`-Node (User-States, Dauer); ein Offer für einen beendeten Anruf trägt `terminate_hint` mit `terminate_reason`, `call_summary` und einer Transaction-ID. Ob `terminate` selbst ein Attribut `terminate_reason` hat, ist nicht aufgelöst.
- Ein Terminate von einem Companion-Gerät wird von der Engine ignoriert; das Primary fächert ein Terminate an Multi-Device-Peers auf (`fanout_terminate_if_peer_is_md`).
- Ein Device-Switch-Terminate im falschen State wird ignoriert; "handled elsewhere"-Ergebnisse werden aus dem Reason abgeleitet (`get_handled_elsewhere_outcome_from_terminate_reason`), und widersprüchliche Ergebnisse für dieselbe Call-ID werden ignoriert.
- Auch ein RTCP BYE auf dem Media-Pfad beendet einen Anruf (`rtcp_bye_terminate_delay`), ebenso das serverseitige Entfernen einer Extension (`extension terminated by server`).
- Java sendet `terminate` mit Retry (über Reconnects hinweg eingereiht), wenn Flag **8003** an ist und der Anruf kein Bot-Anruf ist oder sich im Lonely-State befindet; sonst ohne Retry (Zweig im dekompilierten Output teils unklar).
- Die Werte des Terminate-Strings `reason` (und jede Abbildung von `kCallEndReason`) stehen nicht in den Strings der Bibliothek und wurden anderswo in der APK nicht gefunden (**unknown**).

---

## 15. Feature-Flags (IDs wie an den Aufrufstellen gelesen; Namen ungelöst)

| ID | Typ | Steuert |
|----|-----|---------|
| **9257** | long ms | Timeout der Offer-Zustellung; Stanza bei Timeout verworfen (`CIX.A02`) |
| **9431** | long ms | Timeout der Accept-Zustellung; merkt sich außerdem die Accept-Stanza-ID, damit `preSendTerminate` sie abbrechen kann |
| **9432** | bool | bei Accept-Timeout einen Reconnect auslösen |
| **8003** | bool | Terminate mit Retry (14.3) |
| **15125** | bool | Metrik `call_stanza_drop` melden |
| **30890** | bool | nach dem Offer Ping für ausgehenden Anruf senden |
| **30891** | long ms | Ping-Timeout, Default 3000 |
| **32651** | int | Ping-Versuche, Minimum 1 |
| **31086** | bool | Tracker für ausgehende Offers |
| **24935** | bool | `callEntryPoint` in `Message.call` schreiben |
| **520** | bool | Ad-Attribution-Kontext zu `Message.call` hinzufügen (inferred) |
| **20605** / **20606** | bool / int | `<tctoken>` zu Call-Zielen hinzufügen; Obergrenze für User pro Stanza |
| **24063** | bool | Auswahl des Session-Types beim Decrypt für eine Ciphertext-Klasse (inferred) |
| **4217** | int mask | eingehende Offers peeken: Bit 1 Voice, Bit 2 Video |
| **3094** | int mask | Bit 8 = asynchrone Call-Events (`kFlagEnableCallEventAsync`); gepaart mit **9210** (bool) |
| **7481** | bool | Muted-Notification-State für verknüpfte Gruppenanrufe |
| **13630** / **13804** | int / bool | Sampling für eine Decrypt-Metrik (inferred) |

Engine-Parameter (`p->enable_sframe_tx`, `tp->web_p2p_bitmap`, `tp->enable_e2e_bind_probe_bitmap`, `options.wa_log_time_series`, ...) kommen aus den Server-`voip_settings` und werden über `Voip.getVoipParam` gelesen; ihre Namen sind Strings in der Bibliothek, ihre Werte liegen serverseitig.

---

## 16. Baileys (`baron-baileys-v2`, Quelle gelesen, nichts getestet)

| Thema | Baileys | Android |
|-------|---------|---------|
| Offer | `offerCall`: zufällige 32-Hex-`call-id`, `call-creator` = eigene ID, `<audio enc=opus rate=16000/8000>`, `<video enc=vp8 dec=vp8 ...>` (Video), `<net medium=3>`, `<capability ver=1>` 6 Bytes `01 04 FF 83 CF 04`, `<encopt keygen=2>`, `<destination>` mit Signal-verschlüsseltem `Message{call{callKey}}`, `count=0`, `device-identity`, wenn eine pkmsg entsteht | gleiche Elemente; Android baut das Offer in der Engine, Capability-Bytes unbekannt (5.2) |
| Envelope | `<call id to>` für Offer; reject / accept / terminate nutzen `from` + `to` ohne `id` | immer `<call to id>` (3.1) |
| accept | `<accept call-id call-creator count=0/>`, ohne Children | das Engine-Accept trägt Media-Parameter und ein Zertifikat (Abschnitt 4) |
| terminate | `reason="user-terminated"`, `count=0` | Reason-Strings unbekannt (14.3) |
| rekey | `<enc_rekey ...><enc v=2 type=msg/></enc_rekey>` | v2-Form entspricht 6.4; v3 fehlt |
| Inbound | entschlüsselt `<enc>` (`unpadRandomMax16`, `Message.decode`), cached das Offer, emittiert Call-Events; Media- / Relay-Tags werden nur geackt | Android entschlüsselt mit demselben Envelope und füttert die Engine |
| Links | `link_create media` (+ `event start_time`) an `@call`; `waiting_room_toggle`; `link_join token` | Grammatik passt zu den hier gefundenen Namen; Ziel-JID-Typ nicht aufgelöst |
| Terminate-Status | bildet `terminate reason`-Strings `Timeout`, `RejectDoNotDisturb`, `MicPermissionDenied`, `CameraPermissionDenied`, `RemoteBusy`, `RemoteOffline` ab | diese Strings stehen nicht in der Bibliothek; die Namen ähneln `kCallEndReason` (**inferred** Zusammenhang) |

Baileys hat keine Relay-Allocation, kein WARP / SRTP / SFrame und keine Engine; es kann also signalisieren und klingeln lassen, aber keine Media tragen. Ob ein Offer ohne die vollständigen Engine-Parameter vom Peer akzeptiert oder zum Klingeln gebracht wird, wurde nicht getestet.

---

## 17. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|---------|-----|
| `Wrong jid type` bei einer Call-Stanza | `to` ist keine User- / Device- / Call-Domain-JID | die Device- oder User-JID adressieren |
| Offer gesendet `without enc`, Peer klingelt nicht | Call-Key nicht verschlüsselt (keine Session, Pre-Key-Job ausstehend) | zuerst Sessions aufbauen; Android hält das Offer pending |
| `duplicate <enc>` / `invalid retry count` / `invalid registration` | fehlerhaftes `<enc>`; `registration` nicht 4 Bytes | ein `<enc>` mit `count`; `registration` nur beim Retry |
| Offer-Nack 304 / 400 | doppeltes Offer | ignorieren |
| Offer-Nack 401 / 403 / 463 | Caller darf diesen Peer nicht anrufen | auf dem Client nichts |
| Offer-Nack 412 / 488 | Gruppenmitgliedschaft weicht ab / Bot-TOS nicht akzeptiert | Group-Info aktualisieren / Bot-TOS akzeptieren |
| Reject `enc` | Callee konnte den Call-Key nicht entschlüsseln | Offer nach Session-Reparatur erneut senden (`count` > 0) |
| `Unsupported keygen ver`, `can not receive both te and te2`, `num_tokens < 1` | ungültiges `encopt`, ungültige Relay-Endpunkte oder Tokens | keygen 2 oder 3 senden, eine Endpunktfamilie, mindestens ein Token |
| `bcall message doesn't have master key` | `masterKey` fehlt | mitsenden |
| `Call stanza delivery timed out` | kein chatd-Ack innerhalb von Flag 9257 / 9431 | Stanza verworfen; Accept kann einen Reconnect auslösen (Flag 9432) |

---

## 18. Wichtige Unterscheidungen

| Nicht verwechseln | Mit |
|-------------------|-----|
| `Message.call` (Feld 10, E2E-Call-Key in einer Signal-Nachricht) | `callLogMesssage` (69, Outcome-Record), `bcallMessage` (72, Business-Session-Key) |
| `<enc>` in einer Call-Stanza (paarweiser Signal-Ciphertext) | `skmsg`-Sender-Key-Nachrichten und Media-Verschlüsselung |
| E2E-SRTP- / SFrame-Keys (aus dem Call-Key) | Hop-by-Hop-Keys (aus dem Relay-`hbh_key`) |
| Relay-`<token>` / `<auth_token>` (Allocation-Credentials) | `<tctoken>` (Privacy-Token innerhalb von `<to>`) |
| `kCallEndReason`-Ints (UI), `kCallLog*` (Engine-Ergebnis) | Terminate-Reason-Strings (Wire, unknown), `callOutcome`-Enum (Wire) |
| `CallLogMessage.CallType` REGULAR / SCHEDULED_CALL / VOICE_CHAT | `ScheduledCallCreationMessage.CallType` UNKNOWN / VOICE / VIDEO |
| `enc_rekey` v2 (Signal-`<enc>`-Child) | `enc_rekey` v3 (Protobuf-Liste `RekeyKeyEntry`) |
| WhatsApp-Relay-Pfad (WARP, Hop-by-Hop-SRTP) | Web-P2P-Pfad (ICE + DTLS-SRTP) |
| Event-Anruf (Link mit Startzeit) | Chat-Nachrichten für geplante Anrufe (61 / 65) |
| Signaling über chatd | HTTP- / TEE-Signaling für Bot- und Avatar-Sessions |

---

## 19. Kompletter Ablauf (1:1-Anruf)

```
[Caller app]  startCall(callId, peer, video, ...)
     │
     ▼
[Native engine]  mints 32-byte callKey ; builds <offer> (audio, video, net, capability, encopt keygen)
     │  sendCallStanza(peer, callId, node)
     ▼
[OutgoingSignalingHandler]  per device: Message{call{callKey,...}} → Signal encrypt → <enc>
     │  <destination><to jid><enc/></to>…</destination> [tctoken] [device-identity if pkmsg]
     ▼
[CIX / writer]  <call to id><offer call-id call-creator>…</offer></call>     (delivery timeout, flag 9257)
     │
     ▼
[WA Server]  (not observed) enriches the offer: relay, voip_settings, metadata, privacy
     ├──────► [Caller]  offer ack: <relay> tokens, endpoints, hbh_key ; voip_settings ; or nack (14.1)
     ▼
[Callee]  <call from t e offline><offer/></call>
     │  CallStanzaHandler → nativeParseXmppOffer → C83 decrypt <enc> → callKey → ring (RECEIVED_CALL)
     ▼
[Callee]  preaccept ─► [Caller] PRE_ACCEPT_RECEIVED ;  accept (media params, certificate) ─► ACCEPT_RECEIVED
     │
     ▼
[Both engines]  relay allocate / bind with tokens ; transport / relaylatency / relay_info_update
     │  E2E keys from callKey (HKDF) ; hop-by-hop keys from hbh_key ; optional P2P pair or web_p2p DTLS
     ▼
[Media]  WARP packets via the elected relay or P2P ; ACTIVE ; in-call video, mute_v2, notify, heartbeat
     │
     ▼
[Either side]  terminate (transaction id, call_summary) ─► ack class="call" type="terminate"
     ▼
[Both]  callEnding(CallLogInfo) → call_log row / callLogMesssage ; teardown ; RTCP BYE
```

Unterschiede bei Gruppenanrufen: das Offer trägt `group_info` und keinen Key pro Gerät; spät Beitretende nutzen `lobby` / `link_join`; Rekeys laufen als `enc_rekey` (v2-Fanout oder v3) mit Transaction-IDs; Media läuft über eine SFU mit SFrame.

---

## 20. Unknowns

| Element | Status |
|---------|--------|
| Native Stanza-Builder / -Parser, HKDF-`info`-Strings, Key-Layouts | Voip-Bibliothek nicht dekompiliert; nur Strings |
| Capability-Bytes, `net medium`-Codes, Codec-Parameter-Defaults | nicht gewonnen |
| `transport-message-type`-Werte außer 13 | nicht gewonnen |
| Terminate-`reason`-Strings, Abbildung Reject auf End-Reason | nicht gefunden |
| Bedeutung des Envelope-Attributs `e`, Zusatzaktion bei Offer-Ack-Fehler 435 | ungelöst |
| numerische Message-ID-Tabelle mit 85 Typen | in den Strings dieses Builds nicht vorhanden |
| Geräteklasse der Extension, Auslöser für v3-Rekey, Auslöser für Gruppen-Rekey | ungelöst |
| JID-Typ für Link-Anrufe, Verknüpfung geplanter Anruf mit Token | ungelöst |
| Payload und Berechtigung des TEE- / HTTP-Signalings | ungelöst |
| Serververhalten (Anreicherung, Nack-Semantik, Relay-Wahl) | serverseitig |
| Traffic | nichts mitgeschnitten |
