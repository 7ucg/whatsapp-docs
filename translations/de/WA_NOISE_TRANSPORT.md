<!-- src-sha1: 95a792ca8e841aadc06a8e3fae785590574c4eba -->
# WhatsApp Noise Transport — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** Android-Chat-Transport (chatd): Endpunkte und Verbindungssequenz, Edge-Routing, TCP-Framing, Noise-XX- / IK- / PQ-Handshake, Prüfungen der Zertifikatskette, ClientPayload (UserAgent, DevicePairingData, Connect-Type / Reason), Transport-Cipher und Zähler, binäre Node-Kodierung, Login-Ergebnis und Fehlercodes, Keepalive, Reconnect-Backoff, stream:error, Feature-Flags, verwandte Transporte (Tigon HTTP, DistribGW, Tigon-Noise-Kanal, MQTT), Baileys-Vergleich

---

## 1. Was es ist (technisch)

chatd ist die eine langlebige Verbindung, die jede Stanza trägt (Nachrichten, Receipts, IQ, Presence, Notifications). Unter Android ist es ein einfacher TCP-Socket (kein WebSocket), auf dem ein Noise-Handshake läuft, danach längenpräfixierte AES-GCM-Frames, die jeweils einen binär kodierten Node enthalten. Alle Aussagen stammen aus der statischen Analyse der dekompilierten APK; auf der Leitung wurde nichts mitgeschnitten. Tiers: **found** = im Code gelesen, **inferred** = abgeleitet, **unknown** = nicht aufgelöst. Obfuskierte Namen gelten pro Build und wurden in 2.26.41.6 neu aufgelöst.

| Schicht | Name in 2.26.41.6 | Rolle |
|---------|-------------------|-------|
| Connection-Thread | `HandlerThreadC12340b0` (Log-Tag `ConnectionThread`) | Connect, Handshake, Login, Read-Loop, Disconnect |
| Verbindungssequenz / DNS | `C37151de` (States), `C37031dS` (`A0G` Advance, `A0D` Socket-Factory), `C36881dC`, `AbstractC47101wK` (hartkodierte Tabelle Host zu IP), `C36821d6` (Fallback-IPs) | welcher Host / Port / Proxy als Nächstes |
| Handshake-Treiber | `C38791hg` (`NoiseSocket/*`-Logs) | Intro-Bytes, ClientHello, ServerHello, Cert-Prüfungen, ClientFinish |
| Noise-State | `C38921hv` (+ `C38941hx` Hash, `C38981i2` AES-GCM, `AbstractC38961i0` HKDF), `C40331kf` (Transport-Keys + Zähler) | reines Java |
| Frame-I/O, Node-Codec | `C38891hs` / `C38901ht`; `C40411kn` (Encoder), `C24610wf` (Decoder), `AbstractC40911lb` (Dictionary) | Framing, binäres XML |
| Protos | `C39211ii`, `C39161id`, `C39231ik`, `C39241il` (Handshake); `C24843Amz`, `C24842Amy`, `C24841Amx`, `C25757B9r`, `BC0` (Certs); `C38001fP`, `C38051fp`, `C38661hS` (Payload) | Wire-Nachrichten |
| Trust, PQ | `AbstractC44011qk` (gepinnter Root); `C38811hi`, `AbstractC38821hj`, `AbstractC38831hk`, `C38761hd` (PQ-Config, statische Server-Keys) | Server-Identität, ML-KEM-512-Hybrid |
| Payload-Builder | Contributors in `AbstractC43901qZ`, gesammelt von `C37991fK` | ClientPayload |
| Keepalive, Timer, Reconnect | `C14U` (`ClientPingManager`), `C9EN` (Ping-IQ), `HandlerC21850s9`, `C11380Yq` (`MessageHandler`), `C0X9` (Backoff) | Ping, Timeouts, Retry |
| Eingehende Steuerung | `C40581l4` (`<ib>`), `C40601l6` / `C37961fH.A1B` (`stream:error`) | Server-Hinweise |

Punkte, die den Rest des Reports bestimmen:

- Die Noise-State-Machine, HKDF, AES-GCM und der Frame-Codec sind **Java**. Nur Curve25519 (`org.whispersystems.curve25519`, `OpportunisticCurve25519Provider`, nativ mit Java-Fallback) und die ML-KEM-Aufrufe (`KEMKeyPair.generateNative`, `KEMSecretKey.decapsulateNative`) sind nativ. Es gibt keine native chatd-Implementierung zu analysieren (found).
- Der Intro-Header ist in diesem Build die Konstante `WA 06 03` (Abschnitt 3.1). Der an `C38791hg` übergebene Protokollversions-Int ist an der einzigen Aufrufstelle fest auf 6 gesetzt, daher ist der Version-5-Zweig mit flachem Zertifikat praktisch nicht erreichbar (found; Erreichbarkeit inferred aus der einzigen konstanten Aufrufstelle).
- `devicePairingData` wird nur von einer Verbindung ohne User-JID gesendet, die `ConnectionThread` nur bei der Companion-Registrierung zulässt. Es ist in diesem Build kein Artefakt der Primary-Phone-Registrierung (Abschnitt 6.4).
- Ausgehende Stanzas auf dem Haupt-Sendepfad sind DEFLATE-komprimiert (Flags `3`), nicht nur eingehende (Abschnitt 8.1).

---

## 2. Endpunkte und Verbindungssequenz

### 2.1 Hosts und Ports (found)

| Host | Wo | Hinweise |
|------|----|----------|
| `g.whatsapp.net` | `C37151de` Steps 5, 9; `C36881dC.A01` (hartkodierte IPs) | primärer Chat-Host |
| `g-fallback.whatsapp.net` | Steps 13, 14 | zweiter Host |
| `e1` ... `e16.whatsapp.net` | `C37151de.A0F` (16 Einträge), Step 7 und 11 | `ConnectionSequence/getEdgeHost`; zufällige Wahl oder der in der History gespeicherte Host |
| hartkodierte IP-Tabelle | `AbstractC47101wK.A00`, Steps 6 und 10 | bildet Host auf IP-Liste ab, deckt die `eN`-Hosts und `g.whatsapp.net` ab |
| `<ib><fbip>`-Liste | `C40581l4` nach `C36821d6.A02` | kommagetrennte IPs, vom Fallback-Manager persistiert (Eingabe für Steps 2 / 8, inferred) |
| User-Proxy / SOCKS | Step 12, `C48201yM` | `java.net.Proxy.Type.SOCKS`, Connect-Timeout 30000 ms |

Ports: 443 und 5222 (zufällige Wahl pro Versuch, `C37151de.A00`; der Konstruktor zieht außerdem einen Münzwurf, der die Ports für Steps 3 und 4 ordnet) und 80 für die `:80`-Steps. Der Port der letzten erfolgreichen Verbindung wird wiederverwendet, wenn Flag **33512** aktiv ist (found).

### 2.2 Sequenz-States (found, `C37151de.A02`, Advance in `C37031dS.A0G`)

| Step | Ziel |
|------|------|
| 0 | Start, wählt den ersten anwendbaren Step |
| 1 | Debug- / Override-`InetSocketAddress` (terminal) |
| 2 | vom Server gelieferte Endpunkt-Einträge mit gesetztem `A04`-Bit (Liste `A0A`), einzeln; jeder Eintrag trägt ein eigenes TLS-Bit `A05` |
| 3, 4 | konfigurierter Host-String `A07` auf den zwei Ports (443 / 5222 in zufälliger Reihenfolge) |
| 5 | `g.whatsapp.net` auf 443 (Flag **20801**) oder zufällig 443 / 5222 |
| 8 | vom Server gelieferte Einträge ohne `A04`-Bit (Liste `A09`); Reihenfolge der Zweige im Dekompilat unklar |
| 9 | `g.whatsapp.net:80` |
| 15 | HISTORY: den von der letzten erfolgreichen Verbindung gespeicherten Step / Host / Port wiederholen (nach 9 eingefügt, wenn der History-Step gültig und Flag **22916** aus ist) |
| 13, 14 | `g-fallback.whatsapp.net` auf 443 / 5222, dann `:80` |
| 6, 10 | hartkodierte IP für `g.whatsapp.net`, dann `:80` |
| 7, 11 | zufälliger Edge-Host `eN.whatsapp.net`, dann `:80` |
| 12 | User-Proxy (terminal) |
| 16 | erschöpft |

Reihenfolge nach Step 9 (found): 9, [15], 13, 14, 6, 10, 7, 11, 16. Der letzte Erfolg wird in den Preferences `last_successful_connection_step`, `_host`, `_port` gespeichert (found, `C37031dS.A00`). Steps 2 bis 4 loggen `Skipping sequence ... due to active proxy`, solange eine SOCKS-Service-Config aktiv und Flag **23630** aus ist (Skip-Semantik inferred).

### 2.3 Socket (found, `C37031dS.A0D`)

| Aspekt | Wert |
|--------|------|
| Socket | einfaches TCP; Happy Eyeballs, wenn sowohl IPv4- als auch IPv6-Adressen existieren (`ConnectionSocketFactory/try_connect/using-happyEyeball`) |
| TLS-Wrapper | das Config-Bit `A07` wählt eine `SSLSocketFactory`; gesetzt pro vom Server geliefertem Eintrag (`A05`), für Step 1 auf Port 443 und für Edge-Hosts (Step 7) auf Port 443. Step 5 (`g.whatsapp.net`) wird mit ausgeschaltetem Bit erzeugt |
| Socket-Timeout | 30000 ms, gesetzt über `CeF(30000)` (Semantik inferred: Read-Timeout) |
| TCP-Keepalive | `configureTcpKeepalive`: wenn Flag **7831** aktiv ist und der Socket es unterstützt, wird Keepalive aktiviert und drei Ints aus den Flags **7832** (Default 2), **7833** (Default 10), **7834** (Default 10) angewendet (Idle / Intervall / Anzahl per Inferenz) |
| Output-Buffering | wenn Flag **33751** aktiv ist, wird der Writer in einen `BufferedOutputStream` gewrappt, sodass Intro-Bytes und ClientHello in einem Write rausgehen (found) |

Ob die TLS-gewrappten Endpunkte dieselben Noise-Bytes innerhalb von TLS tragen, ist aus dem Codepfad inferred (`C38791hg` erhält nur Streams); eine Metrik namens `chatd_non_secure_tls_wrapper_resumption` existiert in einer nativen Lib.

### 2.4 DNS-Auflösung (found)

`DNSResolutionMethod` wird in `ClientPayload.dnsSource` gemeldet (Abschnitt 6.5): `SYSTEM`, `GOOGLE`, `HARDCODED`, `OVERRIDE`, `FALLBACK`, `MNS`, `MNS_SECONDARY`, `SOCKS_PROXY`. Flag **13545** (String; Werte `secondary`, `hardcoded`, `none` werden von `C37151de.A01` erkannt) steuert die Resolver-Kette. Gecachte Antworten früherer Lookups werden bis zu ihrem Ablauf verwendet, bevor ein neuer Lookup erfolgt (`C36881dC.A03`).

---

## 3. Framing

### 3.1 Bytes vor dem ersten Frame (found, `C38791hg`)

```
[ 'E' 'D' 00 01 | len24 | routing_info ]     only when routing_info is non-empty
[ 'W' 'A' 06 03 ]                             always
[ len24 | HandshakeMessage{clientHello} ]     first frame
```

- Edge-Header: Magic `45 44 00 01` (`C38791hg.A0B`), 3-Byte-Big-Endian-Blob-Länge, dann die `routing_info`-Bytes (Preference, Base64 ohne Padding oder Umbruch; gespeichert von `C38801hh.A00`, max. 256 Bytes: "The routing info should be smaller than 256 bytes."). Roh auf dem Socket, außerhalb des Noise-Transcripts.
- Intro: `57 41 06 03` = "WA", Protokoll 6, Dictionary 3 (`C38791hg.A04`); zugleich der Noise-Prologue (4.2). Der else-Zweig liefert `57 41 05 03`, aber der Konstruktor fixiert die Version auf 6.

### 3.2 Frame-Layout (found)

Jeder Frame ist eine 3-Byte-Big-Endian-Länge (`AbstractC38721hZ.A04` / `A00`; Writes müssen unter 2^24 liegen, sonst `data too large to write`), gefolgt vom Body: Handshake-Protobuf während des Handshakes, danach AES-GCM-Ciphertext.

Reader (`C38891hs`): genau 3 Längenbytes, dann der Body. Beim Lesen des ServerHello wirft eine Länge aus drei Bytes gleich ASCII `GOA` (`47 4F 41`, `C38891hs.A01`) `X.1sn` (Log `socket/goaway`); der Leseweg nach dem Handshake (`C24610wf.Be0`) hat keine solche Prüfung. Leere entschlüsselte Frames werden übersprungen; ein entschlüsselter Frame mit 1 Byte wirft `header only frame received`. Eine Stanza über dem optionalen Größenlimit (`InterfaceC40421ko.AqJ`) wirft beim Encode `C31990DyW`.

### 3.3 Handshake-Nachrichten (found, Feldnummern aus den Protobuf-Klassen)

| Nachricht (Klasse) | Felder (Nummer fett) |
|--------------------|----------------------|
| `HandshakeMessage` (`C39211ii`) | clientHello **2**, serverHello **3**, clientFinish **4** |
| `ClientHello` (`C39161id`) | ephemeral **1**, static **2**, payload **3**, useExtended **4**, extendedCiphertext **5**, paddedBytes **6**, sendServerHelloPaddedBytes **7**, simulateXxkemFs **8**, pqMode **9**, extendedEphemeral **10** |
| `ServerHello` (`C39231ik`) | ephemeral **1**, static **2**, payload **3**, extendedStatic **4**, paddingBytes **5**, extendedCiphertext **6** |
| `ClientFinish` (`C39241il`) | static **1**, payload **2**, extendedCiphertext **3**, paddedBytes **4**, simulateXxkemFs **5** |

Im Treiber gesehene Setter: das volle XX-ClientHello setzt `ephemeral` (+ `pqMode` in PQ-Varianten); das Resume-ClientHello setzt `ephemeral`, `static`, `payload`, `extendedCiphertext`, `extendedEphemeral`, `pqMode`; ClientFinish setzt `static`, `payload`, `extendedCiphertext`. Die Padding- und Simulate-Felder sind definiert, aber im Treiber wurde kein Setter gefunden (Verwendung unknown).

---

## 4. Noise-Handshake

### 4.1 Pattern-Namen (found, statische Felder von `C38921hv`)

| Konstante | Name | Verwendet wenn |
|-----------|------|----------------|
| `A07` | `Noise_XX_25519_AESGCM_SHA256` (NUL-aufgefüllt auf 32 Bytes) | voller Handshake, PQ none |
| `A0H` | `Noise_IK_25519_AESGCM_SHA256` (auf 32 aufgefüllt) | Resume mit gecachtem Server-Static, PQ none |
| `A06` | `Noise_XXfallback_25519_AESGCM_SHA256` | IK vom Server abgelehnt (4.4) |
| `A0E`, `A0C`, `A08` | `Noise_XXkem_`, `Noise_XXkem-FS_`, `Noise_XXkemEph_` + `25519_MLKEM512_AESGCM_SHA256` | voll, PQ an |
| `A0F`, `A0D`, `A0G` | `Noise_IKkem+`, `Noise_IKkem-FS+`, `Noise_IKkem2+` + `X25519+MLKEM512+AESGCM256+SHA256` | Resume, PQ an |
| `A09`, `A0B`, `A0A` | `Noise_XXkemfallback_`, `Noise_XXkem-FSfallback_`, `Noise_XXkemEphfallback_` + `25519_MLKEM512_AESGCM_SHA256` | PQ-Fallbacks |

Ein Name länger als 32 Bytes wird mit SHA-256 gehasht, andernfalls ist der aufgefüllte 32-Byte-Wert der initiale Hash (found, Konstruktor von `C38921hv`).

PQ-Konfiguration (`NoisePQConfig`): Modus `NONE` / `ENABLE` / `ENFORCE` (Flag **20161**, int: 1 enable, 2 bis 4 enforce, sonst none); Variante `IKKEM`, `IKKEM_FS`, `XXKEM_EPH_IKKEM2`, `XXKEM_EPH_ONLY` (Flag **34536**, String, Default `IKKEM`). Voller Handshake: PQ-Modus `NONE` nutzt `A07`; andernfalls wählt Variante `IKKEM_FS` `A0C`, `XXKEM_EPH_ONLY` und `XXKEM_EPH_IKKEM2` wählen `A08`, `IKKEM` wählt `A0E` (found im Konstruktor von `C38791hg`). Die `IKkem*`-Namen gehören zum Resume-Pfad; ihre genaue Variantenzuordnung wurde nicht nachverfolgt.

### 4.2 Symmetric State (found, `C38921hv`)

```
h  = name (padded, or SHA256(name) if > 32 bytes)         // C38941hx.A00 = name
ck = h                                                    // A02
h  = SHA256(h || prologue)                                // prologue = WA 06 03
mixHash(d):  h = SHA256(h || d)
mixKey(dh):  okm = HKDF-SHA256(salt = ck, ikm = dh, info = none, 64)
             ck  = okm[0:32] ; k = AES-256-GCM key okm[32:64] ; n = 0
encrypt(p):  c = AES-GCM(k, iv = 00000000 || n_be64, aad = h, p) ; n++ ; mixHash(c)
decrypt(c):  p = AES-GCM(k, iv = 00000000 || n_be64, aad = h, c) ; n++ ; mixHash(c)
             (no key yet: encrypt / decrypt pass through and only mixHash)
split():     okm = HKDF-SHA256(salt = ck, ikm = empty, info = none, 64)
             sendKey = okm[0:32] ; recvKey = okm[32:64]
```

HKDF ist handgeschrieben (`AbstractC38961i0`): Extract = `HMAC(key = salt, data = ikm)`, Expand mit einem Ein-Byte-Zähler. IV: 12 Bytes, die ersten 4 null, die letzten 8 der Big-Endian-Zähler (`AbstractC38721hZ.A02`). Tag 128 Bit (GCM im BouncyCastle-Stil `C39061iT`). DH ist Curve25519 `calculateAgreement` über `C38851hm.A00("best")`.

### 4.3 Voller XX-Ablauf (found)

| # | Richtung | Inhalt | State-Operationen |
|---|----------|--------|-------------------|
| 1 | C to S | `ClientHello{ephemeral}` (+ `pqMode` in PQ-Varianten) | `mixHash(e_c)` |
| 2 | S to C | `ServerHello{ephemeral, static, payload}` | `mixHash(e_s)`; `mixKey(DH(e_c, e_s))`; `s_s = decrypt(static)`; `mixKey(DH(e_c, s_s))`; `cert = decrypt(payload)` |
| 3 | lokal | Zertifikatsprüfungen (Abschnitt 5) | Key im Cert muss `s_s` entsprechen |
| 4 | C to S | `ClientFinish{static, payload}` | `static = encrypt(s_c)`; `mixKey(DH(s_c, e_s))`; `payload = encrypt(ClientPayload)` |
| 5 | lokal | split | `sendKey`, `recvKey`, beide Zähler 0 |

Die Reihenfolge in `C38791hg.A03` (Smali) entspricht dem Standard-XX-Transcript. Das Client-Static `s_c` und das Ephemeral stammen aus `C38711hY`-Schlüsselpaaren; das Static liefert `C38771he.A01` (persistenter Client-Noise-Key, "authKey" in Disconnect-Logs). Dass es dem bei der Registrierung hochgeladenen Key entspricht, ist inferred.

### 4.4 Resume (IK) und Fallback (found Struktur, Schrittdetails inferred)

Existieren gecachte statische Server-Keys (`C38771he.A00` nicht null, `C38761hd`), loggt der Treiber `NoiseSocket/handshakeStart mode=... rs=...` und führt `handshakeResume` aus: Der gecachte öffentliche Static-Key des Servers wird in den State gehasht (`C38921hv.A06`), das ClientHello trägt das Ephemeral, das verschlüsselte Client-Static und die verschlüsselte `ClientPayload` in einer Nachricht (Abschnitt 3.3). Antwortet der Server mit einem Static-Key, lautet das Log `handshakeResume server hello has static key, falling back` und `C38791hg` wirft `X.1t8` mit dem ServerHello, was die `Noise_XXfallback_*`-Namen auswählt. Das genaue Fallback-Transcript ist inferred aus dem Standard-Noise-Fallback-Modifier. Statische Server-Keys werden nach einem erfolgreichen Login persistiert, wenn sie sich ändern (`A1m`: klassischer Key über `Ce3`, PQ-Key über `Ce2`).

### 4.5 Post-Quantum-Material (found als vorhanden; Wire-Details teils unknown)

- KEM: ML-KEM-512 (Algorithmus-String `MLKEM512`, `C38791hg.A0C`). TLV des öffentlichen PQ-Keys des Servers: Typ `0x02`, Länge 800; TLV-Header Typ `0x01` mit dem Algorithmusnamen; FS-Ciphertext-TLV Typ `0x04`, Länge 768 (aus den Fehlerstrings `Expected TLV PK type 0x02`, `length 800`, `Expected TLV header type 0x01`, `Expected FS ciphertext length 768`).
- Encapsulation (`C38921hv.A07`): `KEMPublicKey.A00()` liefert Ciphertext + Shared Secret; der Ciphertext geht durch `mixHash`, das Shared Secret durch `mixKey`. Decapsulation: `KEMSecretKey.decapsulateNative`.
- Zustellung: `<success static_pq_key="base64">` wird nur gelesen, wenn der PQ-Modus nicht `NONE` ist und die Variante `IKKEM_FS` (`A18`); ohne ihn lautet das Log `handshake missing serverStaticPQ forcing full handshake` (`C38791hg.A01`).

Breite des TLV-Längenfelds und exakte Platzierung innerhalb von `ServerHello.payload` sind nicht dekodiert. Die ML-KEM-Natives stammen aus den Signal-KEM-Klassen; die Bibliothek, die sie implementiert, wurde nicht identifiziert.

---

## 5. Prüfungen des Server-Zertifikats (found, `C38791hg.A03`)

Protokollversion 6 (der einzige verwendete Wert) parst `ServerHello.payload` als `CertChain`:

`CertChain` (`C24843Amz`): leaf **1**, intermediate **2**. Jedes ist ein `NoiseCertificate` (`C24842Amy`): details **1** (bytes), signature **2** (bytes). `details` parst als Chain-`Details` (`C24841Amx`): serial **1**, issuerSerial **2**, key **3**, notBefore **4**, notAfter **5**.

Prüfungen (Log-Präfix `wa6:`; Auswertungsreihenfolge nicht vollständig rekonstruiert, die dekompilierte Methode ist unvollständig):

1. Beide `details` parsen als Chain-`Details`.
2. `intermediate.issuerSerial == 0` und `leaf.issuerSerial == intermediate.serial`.
3. `leaf.key` entspricht dem Handshake-Server-Static `s_s` ("noise certificate key does not match proposed server static key").
4. Die Intermediate-Signatur verifiziert über `intermediate.details` mit dem gepinnten Root-Key für den Issuer `WhatsAppLongTerm1` (`AbstractC44011qk.A00`).
5. Die Leaf-Signatur verifiziert über `leaf.details` mit dem Intermediate-`key`.

`notBefore` / `notAfter` werden im Chain-Pfad nicht gelesen. Ein Fehlschlag wirft `X.1so` (Log `socket/invalid-certificate-exception`).

Gepinnter Root (Public Key, found, `AbstractC44011qk.A01`): `142375574d0a587166aae71ebe516437c4a28b73e3695c6ce1f7f9545da8ee6b`.

Flache Form (toter Code bei der konstanten Version 6): `NoiseCertificate{details = 1, signature = 2}` (`C25757B9r`), flaches `Details{serial = 1, issuer = 2, expires = 3, subject = 4, key = 5}` (`BC0`). Der Code verifiziert die einzelne Signatur anhand des Issuer-Namens gegen den gepinnten Key, vergleicht `key` mit `s_s` und lehnt ab, wenn `expires` (Sekunden) unter der aktuellen Zeit liegt (Log `noise certificate expired`).

---

## 6. ClientPayload

### 6.1 Felder (found, `C38001fP`; Nummern aus dem Descriptor)

| Feld | Nummer | Typ | Gesetzt von in 2.26.41.6 |
|------|--------|-----|--------------------------|
| username | **1** | int64 | numerischer User-Teil der Login-JID (LID-User bei LID-Login) |
| passive | **3** | bool | Connection-Mode-Flag der Session-Info (7.2) |
| userAgent | **5** | `UserAgent` | 6.2 |
| webInfo | **6** | `WebInfo` | von den gelesenen Contributors nicht gesetzt |
| pushName | **7** | string | Push-Name des Accounts, wenn nicht leer |
| sessionId | **9** | int32 | Session-ID pro Connect (`C37121db`) |
| shortConnect | **10** | bool | `C11750a1.A03()` |
| connectType / connectReason | **12** / **13** | enum | 6.5 |
| shards | **14** | repeated int32 | nicht gesetzt |
| dnsSource | **15** | message | `dnsMethod` **15**, `appCached` **16** |
| connectAttemptCount | **16** | int32 | bisherige Versuche |
| device | **18** | int32 | Companion-Modus: Preference `registration_device_id` |
| devicePairingData | **19** | message | 6.3 / 6.4 |
| product | **20** | enum | `WHATSAPP_LID` bei LID-Login, sonst Default `WHATSAPP` |
| oc / lc | **23** / **24** | bool / int32 | `oc`: Ergebnis der Build- oder Signaturprüfung (`AbstractC38241gg`, Name nicht expandiert); `lc`: Preference `connection_lc` |
| pull | **33** | bool | **in diesem Build nie gesetzt** (kein Writer gefunden) |
| yearClass / memClass | **36** / **37** | int32 | Heuristiken zur Geräteklasse (`C38261gi`, `C38271gj`) |
| trafficAnonymization | **40** | enum | `STANDARD`, wenn `C17830kT.A0L()`, sonst `OFF` |
| lidDbMigrated | **41** | bool | nur mit User-JID und nicht Companion |
| connectionSequenceInfo | **43** | int32 | Zähler 0-31, abgeleitet aus dem Sequenz-Step |
| paaLink | **44** | bool | `C0NZ.A02()` |
| preacksCount / processingQueueSize | **45** / **46** | int32 | Queue-Zustand (Flags **20485** / **22413**) |
| pairedPeripherals | **47** | repeated string | `smart_glasses`, `garmin` |
| messageSts | **49** | int64 | Zeitstempel der letzten Nachricht, falls bekannt |

Definiert, aber hier nicht gesetzt: fbCat **21**, fbUserAgent **22**, iosAppExtension **30**, fbAppId **31**, fbDeviceId **32**, paddingBytes **34**, interopData **38** (`accountId` **1**, `token` **2**, `enableReadReceipts` **3**), accountType **42**, testIsolationId **48**.

### 6.2 UserAgent (found, `C38051fp`)

| Feld | Nummer | Wert in diesem Build |
|------|--------|----------------------|
| platform | **1** | `ANDROID` (0), konstant |
| appVersion | **2** | `{primary 1, secondary 2, tertiary 3, quaternary 4}` aus `2.26.41.6` geparst |
| mcc / mnc | **3** / **4** | `getNetworkOperator()`, Default `000` |
| osVersion / manufacturer / device / osBuildNumber | **5** / **6** / **7** / **8** | System-Strings |
| phoneId | **9** | geräteweite ID (`C38141gV`) |
| releaseChannel | **10** | `BETA` (1) in diesem Beta-Build; `RELEASE 0, BETA 1, ALPHA 2, DEBUG 3` |
| localeLanguageIso6391 / localeCountryIso31661Alpha2 | **11** / **12** | übersprungen bei `zz` / `ZZ` |
| deviceBoard / deviceExpId | **13** / **14** | Board-String, wenn nicht leer; Experiment-ID |
| deviceType | **15** | `PHONE`, `TABLET`, `DESKTOP`, `VR` aus der Geräteklasse |
| deviceModelType | **16** | |
| distributionChannel | **17** | nicht gesetzt |

`UserAgent.Platform` (`EnumC38071fr`, 0-40): 0 ANDROID, 1 IOS, 10 SMB_ANDROID, 12 SMB_IOS, 13 WINDOWS, 14 WEB, 24 MACOS, 29 WEAROS, 33 IPAD, 35 SMART_GLASSES, 39 WORK_ANDROID, 40 WORK_IOS (übrige ausgelassen).

### 6.3 DevicePairingRegistrationData (found, `C38661hS`)

`DevicePairingRegistrationData`-Felder: eRegid **1** (4-Byte-Registration-ID), eKeytype **2** (`05`), eIdent **3** (öffentlicher Identity-Key), eSkeyId **4**, eSkeyVal **5**, eSkeySig **6** (Signed-Prekey-ID, öffentlicher Key, Signatur), buildHash **7**, deviceProps **8** (serialisiertes `DeviceProps`).

`buildHash`: Der Code berechnet `Base64.decode(hexMD5("2.26.41.6"), 0)` (`C00L.A04` liefert den 32 Zeichen langen Lowercase-Hex-MD5, der dann an den Base64-Decoder geht), was 24 Bytes ergibt, nicht den 16-Byte-Digest (found wie gelesen).

`DeviceProps` (`C43105IrG`): os **1** (OS-String), version **2** (`AppVersion`), platformType **3**, requireFullSync **4** (= true), historySyncConfig **5**. Der History-Sync-Block wird von einer Klasse zusammengesetzt, die als `CompanionRegInfoProvider` loggt; seine Felder (Full-Sync-Tage / Größenlimits, Recent Sync, Thumbnail-Sync, Support-Flags wie Call-Logs, Bot-History, Group-History) werden von den Flags **15284**, **15283**, **21217**, **20658**, **18953**, **26445**, **26614** gesteuert.

### 6.4 Welche Variante gesendet wird (found)

- Login, Primary (User-JID bekannt): username, passive, userAgent, pushName, sessionId, shortConnect, connectType, connectReason, dnsSource, connectAttemptCount, connectionSequenceInfo, lc, oc, yearClass, memClass, trafficAnonymization, lidDbMigrated, messageSts, Queue-Zähler, paaLink, pairedPeripherals; `product = WHATSAPP_LID` bei LID-Logins.
- Login, Companion: dasselbe plus `device = registration_device_id`.
- Companion-Registrierung (User-JID null): kein username; `devicePairingData` (Key-Bundle + `DeviceProps`) und `device`.

`ConnectionThread/connect/ignored/jid null and not in companion reg` zeigt, dass eine Null-JID außerhalb der Companion-Registrierung abgelehnt wird. Das Primary-Phone registriert sich über HTTPS `/v2/*` (siehe den Account-Security-Report); eine Verwendung von `devicePairingData` bei der Primary-Registrierung wurde nicht gefunden.

### 6.5 Verwendete Enums (found)

| Enum | Werte |
|------|-------|
| `ConnectReason` (`EnumC38391gv`) | 0 PUSH, 1 USER_ACTIVATED, 2 SCHEDULED, 3 ERROR_RECONNECT, 4 NETWORK_SWITCH, 5 PING_RECONNECT, 6 UNKNOWN |
| `ConnectType` (`EnumC38311gn`) | 0 CELLULAR_UNKNOWN, 1 WIFI_UNKNOWN, 100 EDGE, 101 IDEN, 112 HSPAP; die übrigen Mobilfunknamen (UMTS, EVDO, GPRS, HSDPA, HSUPA, HSPA, CDMA, ...) beziehen ihre Nummern aus indirekten Konstanten, die nicht aufgelöst wurden |
| `Product` (`EnumC38561hI`) | 0 WHATSAPP, 1 MESSENGER, 2 INTEROP, 3 INTEROP_MSGR, 4 WHATSAPP_LID |
| `DNSResolutionMethod` (`EnumC38321go`) | 0 SYSTEM, 1 GOOGLE, 2 HARDCODED, 3 OVERRIDE, 4 FALLBACK, 5 MNS, 6 MNS_SECONDARY, 7 SOCKS_PROXY |

Connect-Reason wie in diesem Build geschrieben: Default `UNKNOWN`; liegt der Zeitstempel der Session-Info innerhalb von 10 s, ergibt State 1 `USER_ACTIVATED`, State 2 ergibt `PUSH`. Die anderen Werte sind definiert, werden von diesem Contributor aber nicht gewählt.

---

## 7. Nach dem Handshake

### 7.1 Login-Ergebnis (found, `HandlerThreadC12340b0.A13`)

Die ersten eingehenden Nodes werden in einer Schleife gelesen. `web` wird nur akzeptiert, wenn eine Web-Ref gesendet wurde (sonst `web node given during login without any web ref provided`). Alles außer `web`, `success`, `failure` wirft `unexpected node received during login sequence`.

Gelesene `<success>`-Attribute:

Gelesene Attribute: `t` (Serverzeit in Sekunden, gespeichert; nicht numerisch wirft `invalid server time`), `props`, `abprops`, `mc_ep_version` (Config-Versionszähler), `lid` (Account-LID, verglichen mit der gespeicherten LID; Abweichung meldet `lid-chatd-lid-mismatch`), `pn` (Telefon-User-JID), `static_pq_key` (Base64-PQ-Key des Servers, 4.5).

### 7.2 Passiver vs. aktiver Modus (found)

`passive` im Payload stammt aus der Session-Info (`C37981fJ.A0A`); Log-Felder `forcePassiveMode`, `enablePassiveModeBasedOnQueueSize`, `duplexActive`. Nach dem Login verlässt der Client den passiven Modus mit einem set-IQ, gebaut von `AbstractC44071qq`:

```xml
<iq id="..." xmlns="passive" type="set" to="s.whatsapp.net"><active/></iq>   <!-- or <passive/> -->
```

Pre-Acks werden zuerst gesendet, wenn sie in der Queue stehen (`ConnectionThread/send preacks`). Ein Timer von 32000 ms (`HandlerC21850s9.A02`) wird beim Senden gestartet; kommt das Connection-Active-Signal nicht an, feuert er Reason 10 (`connection active timeout`).

### 7.3 Information Bulletins (found, `C40581l4`)

Behandelte `<ib>`-Children: `edge_routing` (Child `routing_info`, gespeichert, Abschnitt 3.1), `fbip` (kommagetrennte IPs an den Fallback-Manager), `client_expiration` (`t`, Sekunden, in ms umgerechnet), `dirty`, `offline_preview`, `location`, `notice`, `recovery_nonce`, `safetynet`, `sonar` (`url`), `streamdebug`, `thread_metadata`, `gpia`, `age_experience`, `accept_paa_link`, `peer_device_presence`. `dns_domain` ist nicht vorhanden (im Android-Client nicht enthalten).

---

## 8. Binäre Node-Kodierung

### 8.1 Frame-Inhalt und Flags (found, `C40411kn.Csv`, `C24610wf.Be0`)

Nach der AES-GCM-Entschlüsselung beginnt der Plaintext mit einem Flags-Byte:

| Bit | Bedeutung |
|-----|-----------|
| `2` | der Rest ist ein zlib-(DEFLATE-)Stream; der Decoder inflatet ihn und behält das Flags-Byte |
| `1` | Fragmentierung; Decoder wirft `server to client stanza fragmentation not supported` |

Encoder: `Csv(node, flags)` mit `flags & 2` deflatet (`DeflaterOutputStream`) und stellt `02` voran; andernfalls schreibt er ein Flags-Byte `00`. Die Haupt-Sendepfade in `HandlerThreadC12340b0` und der Writer-Thread `HandlerThreadC21920sG` rufen `Csv(node, 3)` auf, diese Stanzas sind also komprimiert. `Csu(node)` (= Flags 1, unkomprimiert) wird von `C40851lV` aufgerufen, das wie der Sender der Login-Phase aussieht (inferred). Der End-of-Stream-Marker ist `00` + list(1) + Token `02` (`Clp`, `xmlstreamend`).

### 8.2 Tag-Bytes (found)

| Byte | Name | Body |
|------|------|------|
| 0 | leere Liste / abwesend | keiner |
| 1, 2 | `xmlstreamstart`, `xmlstreamend` | Decoder lehnt sie als Strings ab |
| 3..235 | Single-Byte-Token | Index in die 236-Einträge-Tabelle `A00` |
| 236..239 | Dictionary 0..3 | 1 Index-Byte in `A01[tag - 236]` (je 256 Einträge) |
| 244 / 247 | JID_INTEROP / AD_JID | `user:str, device:u16, integrator:u16, domain:u8` / `domain:u8, device:u8, user:str` |
| 248 / 249 | LIST_8 / LIST_16 | `count:u8` / `count:u16` |
| 250 | JID_PAIR | `user:str or 00, server:str` |
| 251 / 255 | HEX_8 / NIBBLE_8 | `lenAndOdd:u8` + gepackte Nibbles |
| 252 / 253 / 254 | BINARY_8 / _20 / _32 | `len:u8` / `len:u20` (3 Bytes) / `len:u32`, dann Bytes |

Die Tags 245 und 246 existieren in diesem Codec nicht. Alle Multi-Byte-Integer sind Big-Endian.

### 8.3 Node-Layout (found, `C40411kn.A01`)

```
list(size)  description  (key value)*  [content]
size = 1 + 2 * attrCount + (content ? 1 : 0)
```

Ungerade Größe bedeutet kein Content. Decoder: Attributanzahl = `((size - 2) + size % 2) / 2`. Content ist entweder ein Byte-Blob (`252 / 253 / 254`) oder eine Child-Liste. Ein Node mit Blob und Children zugleich wirft `more than one source of inner data`. Listen-Header: 0 für leer, 248 unter 256 Einträgen, 249 unter 65536, sonst `list too long`.

### 8.4 String-Leiter (found, `C40411kn.A05` / `A06`)

| Slot | Reihenfolge der Versuche |
|------|--------------------------|
| description | Token, Dictionary, JID (falls parsebar), längenpräfixiertes UTF-8 |
| Attribut-Key | Token, Dictionary, UTF-8 |
| Attribut-Wert | Token, Dictionary, JID, gepackt, UTF-8 |
| Content-Bytes | rohes BINARY (`A06(bytes, false)`), nie tokenisiert oder gepackt |

Packing (`A06` mit dem Packed-Flag, nur Attributwerte): Länge unter 128 und alle Zeichen in `[0-9-.]` ergibt NIBBLE_8 (`255`; `0-9` = 0..9, `-` = 10, `.` = 11); Länge unter 128 und alle Zeichen in `[0-9A-F]` ergibt HEX_8 (`251`); das Odd-Length-Bit ist `0x80` im Längenbyte. Längen ab 256 nutzen BINARY_20 bis 1 MiB, darüber BINARY_32. Nibble-Map des Decoders: 10 `-`, 11 `.`, 12 `:` (der Encoder gibt 12 nie aus).

### 8.5 JIDs (found, `C40411kn.A00`, `C24610wf.A02`)

| JID | Kodierung |
|-----|-----------|
| Interop-User (`C99O`, Typ 22) | `244, user, device u16, integrator u16, 00`; dekodiert zu `{integrator}-{user}[:device]@interop` |
| Interop-Gruppe (`C55529Oy6`, Typ 28, Server `interop.g.us`) | `244, user, 0000, 0000, 02`; Decoder verlangt device und integrator 0 |
| Agent oder Device vorhanden | `247, domainByte, device, user`; domainByte-Bit `1` = LID, Bit `128` = hosted |
| sonst | `250, user (or 00), server` |

AD_JID-Server-Zuordnung: `0` `s.whatsapp.net`, `1` `lid`, `128` `hosted`, `129` `hosted.lid`. Device `99` wird genau dann erwartet, wenn das Hosted-Bit gesetzt ist; eine Abweichung wird geloggt und die JID trotzdem akzeptiert. Nicht konforme JIDs werfen `failed to write jid`.

### 8.6 Dictionary (found, `AbstractC40911lb`)

236 Single-Byte-Tokens (Index 0 ist null) und vier Dictionaries mit je 256 Einträgen; die Dictionary-Version ist das letzte Intro-Byte, `03`. In diesem Build neu aufgelöste Indizes:

| Token | Index | Token | Index |
|-------|-------|-------|-------|
| `s.whatsapp.net` | 3 | `iq` / `ack` / `message` | 25 / 27 / 19 |
| `type`, `id`, `from`, `to` | 4, 8, 6, 17 | `get` / `set` / `result` / `error` | 41 / 90 / 20 / 168 |
| `routing_info` / `edge_routing` | 39 / 40 | `urn:xmpp:ping` / `ping` / `w:p` | 43 / 86 / 87 |
| `handshake` / `success` | 53 / 76 | `stream:error` / `not-authorized` | 157 / 209 |
| dict 0: `active` / `conflict` / `replaced` / `passive` | 1 / 14 / 17 / 24 | dict 1: `dirty` / `server-error` / `pair-device` | 1 / 145 / 238 |
| dict 2: `failure` / `rate-overlimit` | 60 / 239 | `call` / `usync` / `w:m` | 100 / 121 / 194 |

Einige Tokens der Tabelle sind Java-Konstanten, die aus anderen Klassen importiert werden (zum Beispiel `enc`); diese Indexliste löst sie nicht auf. Indizes ändern sich zwischen Builds; nicht über Versionen hinweg wiederverwenden.

---

## 9. Keepalive und Timer

| Timer | Wert | Tier |
|-------|------|------|
| Client-Ping | `<iq type="get" xmlns="w:p" to="s.whatsapp.net"/>` (`C9EN`); die Antwort muss `from`, `id`, `t` in 1577865600..4102473600 und `type="result"` tragen (`C14U`) | found |
| Ping-Timeout | `clamp(flag 15103, 8000, 32000)` ms; bei Timeout läuft `C14R.CY1()` einmal pro Ping (Reconnect-Reaktion inferred) | found / inferred |
| Ping-Intervall | Flag **15270** (erster), **15183** (spätere); verzögerter Runnable oder Alarm `com.whatsapp.alarm.CLIENT_PING_TIMEOUT`, gewählt durch Flag **6493** | found, Werte serverseitig |
| Server-Ping | `<iq type="get" xmlns="urn:xmpp:ping" t="...">` (`AbstractC40501kw`) | found |
| Active-Mode-Ack | 32000 ms, dann Disconnect Reason 10 | found |
| Message-Receipt | 45000 ms nach dem Senden, noch nicht bestätigt: Reconnect Reason 9 (`HandlerC21850s9`) | found |
| Logout-Timeout / Socket-Timeout | 10000 ms / 30000 ms | found |

---

## 10. Reconnect und Backoff (found, `C11380Yq.A07`, `C0X9`)

`C11380Yq` plant einen Reconnect über `AlarmManager` (`com.whatsapp.MessageHandler.RECONNECT_ACTION`, Extra `connect_reason` 3). Die Delay-Einheit ist 10 s (0x2710 ms im Smali).

| Schritt | Regel |
|---------|-------|
| Zähler | `C0X9(1, 17280)`: Fibonacci in Einheiten, Folge 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55 ... gedeckelt bei 17280 Einheiten (48 h) |
| Erster Retry | 0 Einheiten: `scheduleReconnect/immediate` |
| Jitter | `d = units * 10 s`; Delay gleichverteilt in `[d / 2, 1.5 d)` |
| Clamp | ist das Caller-Flag gesetzt, werden Delays über 15 min zu 15 min plus einem zufälligen Offset in `-30 .. +29` ms (`backoff clamped to ~15mins`) |
| Reset | `A02()` setzt den Zähler bei einer `reset`-Reconnect-Anfrage zurück |
| Overrides | `force` löscht die ausstehende Deadline; `force_no_ongoing_backoff` überspringt das Warten; `reset` setzt den Zähler zurück |
| Kein Netzwerk | `handleDisconnected/retry/network_unavailable` wartet auf Konnektivität (Alarm `CONNECTIVITY_RETRY_ACTION`) |

Innerhalb eines Versuchs durchläuft die Verbindungssequenz aus Abschnitt 2.2 Hosts und Ports; Backoff gilt zwischen fehlgeschlagenen Versuchen des gesamten Connects.

---

## 11. Stream-Fehler und Fehlercodes

### 11.1 `<failure reason="N">` beim Login (found, `A13`)

| Reason | Behandlung | Zusätzlich gelesene Attribute |
|--------|------------|-------------------------------|
| 5xx | retrybarer Serverfehler, `C45351tB(type 4)` | keine |
| 402 | Ban-Familie; Type 13 (Code 106 mit `appeal_token`), 14 (Code 107), 15 (Code 109), sonst 2 | `appeal_token`, `code`, `expire`, `message`, `url`, `age_collection` |
| 403 | Type 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` |
| 405 | Type 3, `expiration_time = t * 1000` | `t` |
| 406 | Type 5 | `code` |
| 416 | Type 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` |
| sonstige | Type 0 (generischer Logout-Pfad) | keine |

Jedes Failure liest zudem die optionalen Logout-UI-Felder `logout_message_header`, `logout_message_subtext`, `logout_message_locale`, `logout_main_button_text` / `_url`, `logout_secondary_button_text` / `_url` (`A17`). Die Zuordnung der Type-Ints zu nutzersichtbaren Screens wurde nicht nachverfolgt; die Semantik von Account-Bans deckt der Ban-Report ab.

### 11.2 `<stream:error code="N">` (found, `C40601l6`, `C37961fH.A1B`)

| Fall | Behandlung |
|------|------------|
| Jeder `stream:error` | `ConnectionThreadRequestsImpl/stream/error` wird mit dem ersten Child geloggt; eine Nachricht mit `errorCode` wird an `MessageHandler` gepostet |
| Code 500-599 | `MessageHandler` setzt ein Flag und führt einen Reconnect-Durchlauf aus (`onConnectionStreamError`) |
| Child `ack` | als Ack-Kick behandelt: die ausstehende Stanza mit dieser ID wird nachgeschlagen, Metriken werden ausgegeben, die Verbindung stoppt (`1t7` geworfen) |
| Child `conflict type="device_removed"` | nur Companion: Deregistrierung (`C24100vp.A02`), außer State 9 |
| 515 / 516 (Companion-Pfad) | als typisierte Nachrichten weitergeleitet; der dekompilierte Zweig für 515 ist unklar |
| `<error code="479">` | `smax-invalid` gemeldet (`SmaxInvalidError`) |
| `<error class="status" id=...>` | lässt den ausstehenden Status-Ack-Callback fehlschlagen |

### 11.3 Handshake- und Socket-Fehler (found als Log-Tags, Reaktionen teils nachverfolgt)

| Log-Tag | Ursache |
|---------|---------|
| `socket/goaway` (`X.1sn`) | ServerHello-Längenbytes gleich `GOA` |
| `socket/invalid-certificate-exception` (`X.1so`) | Cert-Chain-Prüfung fehlgeschlagen (5); ruft `C37031dS.A0C` auf |
| `socket/disconnect/invalid-server-static-key` (`X.1sp`), `.../authKey` (`X.1sm`) | Server-Static abgelehnt; Problem mit dem Client-Static-Key |
| `socket/disconnect/noise` (`X.1sr`) | Protokoll-Exception (fehlerhafte Handshake-Daten, TLV-Größen); AEAD-Fehler `X.1t9` und KEM-Eingabefehler `X.1tC` werden in diese Familie weitergeworfen |
| `socket/disconnect/io`, `socket/closed`, `socket/error/EPERM` | I/O-Fehler, blockiertes Netzwerk |
| `connect/not-allowed/clock`, `software-expired`, `login-failed`, `quit-flag-set` | Gates vor dem Connect |
| `ReaderThread/corrupt-stream-error` | fehlerhafter Node-Stream; `next-port/corrupt-stream-exception` rückt den Port vor |

---

## 12. Feature-Flags (IDs wie in `AbstractC36791d3` und an Aufrufstellen gelesen)

| ID | Typ | Steuert |
|----|-----|---------|
| **20161**, **34536** | int, string | PQ-Modus (1 enable, 2-4 enforce), PQ-Variante (Default `IKKEM`) |
| **38643**, **15716** | string, bool | KEM-Wahl (`MLKEM768` erkannt), Gate dafür; Wirkung unaufgelöst |
| **33751** | bool | gepufferter Writer für Intro + ClientHello |
| **22916**, **30712**, **33512** | bool | HISTORY-Step deaktivieren; Last-Success-Record laden; gespeicherten Port wiederverwenden |
| **20801**, **23630**, **24645** | bool | Step 5 fest 443; Steps 2-4 unter SOCKS-Config; Quelle der SOCKS-Service-Config |
| **13545** | string | DNS-Resolver-Modus (`secondary` / `hardcoded` / `none`) |
| **7831**-**7834** | bool, ints | TCP-Keepalive aktivieren und Parameter |
| **15103**, **15270**, **15183**, **6493** | int, bool | Ping-Timeout, Intervalle, Scheduling-Methode |
| **20485**, **22413** | bool | Queue-Zustand im Payload |

Alle Werte sind serverseitig; Defaults sind die einkompilierten aus den Flag-Deklarationen.

---

## 13. Andere Transporte

| Transport | Zustand in 2.26.41.6 | Tier |
|-----------|----------------------|------|
| Tigon-HTTP-Client | `com/crossapp/tigonhttp/TigonHttpClient*`, `com/facebook/tigon/**`, `com/whatsapp/infra/tigon/WAHucClient`, Auth über `WATigonAsyncAuthServiceHolder`; HTTP/2- und HTTP/3-Strings (`MNS/mvfst-mobile`, `MNS/ngtcp2`) in `libwhatsappmerged.so` | Klassen und Strings found; Nutzung pro Feature inferred |
| DistribGW (DGW) | `com/facebook/distribgw/client/*`, `RequestStreamDGWBuilder`; nur app-seitige Registrierung gefunden: `WaFalcoStreamingRegistration.nativeRegisterStreaming(DGWClient)`; Strings `distribgw_tigon_tunnel`, `DGW_MQTTBYPASS`, `XPLAT_RS_MQTT`, `XPLAT_RS_STARGATE`, `wa_request_stream` | found; Wire-Format unknown |
| MQTT-Client | keiner; `mqtt` taucht nur in Analytics-Event-Namen und DGW-Stream-Type-Labels auf | found |
| GraphQL über chatd | `com.whatsapp.pando.chatd.WAChatdGraphQLClient`, `WAChatdGraphQLCallbacks`, `WATigonMexdServiceHolder` | Namen found; läuft über chatd als inferred w:mex-Pfad |

### 13.1 Tigon-Noise-Kanal (zweiter Noise-Stack, nativ)

Dies ist ein anderer Transport als chatd. Belege sind Strings und Klassennamen, keine dekompilierte Logik.

- Carrier: WebSocket über den MNS-Netzwerkstack (`NoiseCarrierWebSocket`, `Stream0Listener`); nummerierte Streams mit einem Control-Stream 0 und Chunk-Reassembly (`noise.framer.*`).
- Handshake-Ergebnisse (`NoiseHandshakeOutcome`): `LEGACY_PEER_VERIFIED`, `PRIVATE_AUTH_PEER_VERIFIED`, `ENROLLMENT_REQUIRED`, `KEY_REQUIRED`, `VERIFICATION_FAILED`; `NoisePrivateAuthMode`: `MIGRATION`, `REQUIRED`; Fehler wie `noise.handshake.attestation_failed`, `chip_binding_rejected`, `private_auth.vm_proof_failed`.
- Attestation: AMD-SEV-SNP-Verifier (`NoiseSevSnpAttestationVerifier`, VCEK- / ASK- / ARK-Chain-Prüfungen, Chip-ID-Binding); Labels `hatch.noise-auth.key.v1`, `.client-proof.v1`, `.vm-proof.v1`.
- Demand Control: `NoiseConnectionDemandRejectionReason` `OFFLINE`, `BACKGROUND`, `PAUSED`, `SESSION_ENDED`, `RETRY_EXHAUSTED`, `INTERNAL`.
- Java-Nutzer: `WaVmHttpTransportImpl`, `NoiseVmConnection` (Pfad `/v1/noise`, Schritte `hatch-noise status=opening` / `result=ready`), `NoiseGatewayCarrier`. Der Zweck (HTTP-over-Noise zu einer Confidential-Compute-VM für den Agent-Browser) ist inferred aus Namen und Attestation-Strings.

Nichts davon teilt Code mit dem chatd-Handshake aus Abschnitt 4; der gleiche Pattern-Name bedeutet kein gleiches Framing, keinen gleichen Prologue und keinen gleichen Payload.

---

## 14. Baileys (`baron-baileys-v2`, gegen den Quellcode bestätigt)

| Aspekt | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| Intro-Header | `NOISE_WA_HEADER = [87, 65, 6, 3]` | `57 41 06 03` |
| Pattern | `NOISE_MODE = 'Noise_XX_25519_AESGCM_SHA256\0\0\0\0'` | derselbe aufgefüllte 32-Byte-Name |
| Server-Cert | `CertChain`-Decode; Leaf-Signatur mit dem Intermediate-Key geprüft; Intermediate mit dem gepinnten Root `142375574d0a...da8ee6b` geprüft; `issuerSerial` muss 0 sein | dieselbe Chain und dieselben Root-Bytes; die APK verlangt zusätzlich `leaf.issuerSerial == intermediate.serial` |
| Edge-Routing | speichert `routing_info` aus `<ib><edge_routing>`; hängt es als Query `ED=<base64url>` an `wss://web.whatsapp.com/ws/chat` an | speichert es (max. 256 Bytes); sendet `45 44 00 01 len24 blob` roh vor dem Intro |
| Keepalive | `<iq type="get" xmlns="w:p"/>` ohne Children, Default-Intervall 30000 ms, Connect-Timeout 20000 ms | gleiches IQ; Intervall und Timeout aus Server-Flags |
| Login-Payload | `passive`, `pull` true, `username`, `device`, `connectType WIFI_UNKNOWN`, `connectReason USER_ACTIVATED`, `lidDbMigrated false`, `releaseChannel RELEASE` | kein `pull`, `connectReason` aus dem Session-State, `releaseChannel BETA` in diesem Build |
| Registrierungs-Payload | `passive false`, `pull false`, `devicePairingData` | `devicePairingData` nur für den Connect der Companion-Registrierung |
| Transport | WebSocket-Frames | rohes TCP, 3-Byte-Längen-Frames |

Bestätigte Unterschiede, die für einen Transport im Android-Stil zählen: Der Edge-Hinweis ist in Baileys ein Query-Parameter an der WebSocket-URL, unter Android aber ein roher Header vor dem Intro; Baileys erzwingt `leaf.issuerSerial == intermediate.serial` nicht; Baileys sendet `pull` und `passive` beim Login als true, während der Android-Payload kein `pull` hat. Baileys behält den statischen Server-Key für einen schnellen Reconnect (ein Code-Kommentar nennt `NoiseIkSession`), was dem IK-Resume aus Abschnitt 4.4 nur der Absicht nach entspricht; seine Wire-Form wurde nicht verglichen.

---

## 15. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|---------|-----|
| `GOA` in den ersten drei Bytes | Server-Goaway während des Handshakes | nächsten Endpunkt versuchen |
| `Handshake message does not contain server hello!` | erster Server-Frame ist kein ServerHello | Prologue und Edge-Header prüfen |
| `noise certificate key does not match proposed server static key` | Leaf-Key weicht vom Handshake-Static ab | Chain vor ClientFinish verifizieren |
| `server to client stanza fragmentation not supported` | Flags-Bit `1` gesetzt | vom Client nicht unterstützt |
| `unexpected node received during login sequence` | erster Node ist nicht `web`, `success`, `failure` | keiner |
| `noise-pq-static-key-decode-failed` | `static_pq_key` ist kein gültiges Base64 | Key nicht gespeichert, einmal gemeldet |
| `scheduleReconnect backoff=...` | wiederholte Fehlschläge | Backoff abwarten oder Reconnect erzwingen |

---

## 16. Wichtige Abgrenzungen

| Nicht verwechseln | Detail |
|-------------------|--------|
| chatd-Noise vs. Tigon-Noise-Kanal | Java vs. nativ, TCP- vs. WebSocket-Carrier, anderer Zweck; der gleiche Pattern-Name sagt nichts über Framing oder Payload |
| Intro-Header vs. Edge-Header | `WA 06 03` wird als Prologue gehasht; `ED 00 01 len blob` ist nicht Teil des Transcripts |
| Edge-Host `eN.whatsapp.net` vs. `routing_info` | Hosts stammen aus der Client-Sequenz; `routing_info` ist ein opaker Blob, der im Edge-Header wieder eingespielt wird |
| `fallback_hostname` / `fallback_ip4` / `fallback_ip6` | Attribute von `media_conn`-Hosts (CDN), keine chatd-Fallbacks; chatd-Fallbacks kommen aus `<ib><fbip>` und der hartkodierten Tabelle |
| `passive`-Payload-Flag vs. `<passive/>`-IQ | Flag beim Connect gesetzt; das IQ schaltet danach in den aktiven Modus |
| `devicePairingData` vs. HTTP-Registrierung | Pairing-Daten gehören zum Connect der Companion-Registrierung |
| Frame-Länge vs. Listengröße | die 3-Byte-Länge umschließt den Ciphertext; die Listengröße zählt Node-Slots |
| Protokoll- vs. Dictionary-Version | beide im Intro: `06` und `03` |
| `stream:error` vs. `failure` | `failure` beantwortet den Login; `stream:error` kann jederzeit eintreffen |

---

## 17. Kompletter Ablauf

```
[Connection thread]  C37031dS.A0G picks step (history, g, g-fallback, hard-coded, eN, proxy)
     │  DNS ─► TCP connect ─► optional TLS wrapper
     ▼
[Client]  write [ED 00 01 len24 routing_info]?  [WA 06 03]        h = SHA256(name) ; h = SHA256(h || WA 06 03)
     │  frame1: HandshakeMessage{clientHello{ephemeral}}           mixHash(e_c)    (resume: + static + payload)
     ▼
[Server]  frame2: serverHello{ephemeral, static, payload}
     │  mixHash(e_s) ; mixKey(ee) ; s_s = decrypt(static) ; mixKey(es) ; cert = decrypt(payload)
     │  CertChain: leaf.key == s_s ; intermediate by pinned root ; leaf by intermediate
     ▼
[Client]  frame3: clientFinish{static = enc(s_c), payload = enc(ClientPayload)}      mixKey(se) ; split
     ▼
[Server]  [len24 | AES-GCM(flags | node)] ─► <success t props abprops lid pn static_pq_key/>  or  <failure reason/>
     ▼
[Client]  <iq xmlns="passive" type="set"><active/></iq> (+ pre-acks) ; steady state both ways, own counter per direction
     │  ping <iq xmlns="w:p"/> ; ib / notification / message / receipt / call ...
     ▼
[Failure]  stream:error / ping timeout / socket error ─► disconnect ─► Fibonacci backoff ─► next attempt
```

---

## 18. Unbekanntes

| Punkt | Status |
|-------|--------|
| Wire-Traffic jeder Art | nichts mitgeschnitten; kein Punkt ist `tested` |
| IK-Resume- und Fallback-Transcript | Struktur found, Schritte inferred |
| PQ-Key-Platzierung in `ServerHello.payload`, TLV-Längenbreite, Bibliothek hinter den ML-KEM-Aufrufen | nicht dekodiert / nicht identifiziert |
| Was die TLS-gewrappten Endpunkte innerhalb von TLS tragen | inferred aus dem Codepfad |
| Ping- und TCP-Keepalive-Werte | Server-Flags |
| Failure-Type-Ints 0-15 zu Client-Screens; Wirkung der Flags **38643**, **15716** | nicht nachverfolgt / unaufgelöst |
| Payload-Felder ohne Writer (`webInfo`, `shards`, `fb*`, `accountType`, `testIsolationId`, `paddingBytes`, `pull`) | in diesem Build keine gefunden |
| Tigon-Noise-Kanal-Handshake, Framing; DGW-Wire-Protokoll und Nutzer | nativ, nur Strings |
| Dictionary-Strings, die importierte Java-Konstanten sind (zum Beispiel `enc`) | in der Indexliste nicht aufgelöst |
