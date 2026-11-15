<!-- src-sha1: 6458e557973884f0b2c8c175f4607447365f03a6 -->
# WhatsApp Verknüpfte-Geräte-Pairing — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-17
**Umfang:** Primärgerät-Seite des Companion-Pairings, QR-Flow, Telefonnummer-/Pair-Code-Flow, `pair-device`- und `pair-success`-Stanzas, Schlüsselmaterial, ADV signed device identity und Key-Index-Liste, Geräteliste und Limits, Unlink, Fehler, Baileys-Vergleich

---

## 1. Was es technisch ist

Ein verknüpftes Gerät (Companion) ist ein zweiter Endpunkt desselben Accounts. Das Primärtelefon autorisiert es, indem es eine ADV- (account device verification) signierte Identität über den Identity-Key des Companions erzeugt. Alle Aussagen sind statische Analyse der dekompilierten APK; nichts wurde auf der Leitung mitgeschnitten. Tier: **found** = im Code gelesen, **inferred** = aus Code abgeleitet, **unknown** = nicht geklärt.

Obfuskierte Namen sind pro Build und wurden aus stabilen Strings in 2.26.41.6 neu aufgelöst.

| Entität | Name in 2.26.41.6 | Rolle |
|--------|----------------|------|
| QR/Pair-Orchestrator | `C45850K0w` (Log-Präfix `CompanionDeviceQrHandler`) | parst QR, baut ADV-Protos, sendet `pair-device` |
| `pair-device`-IQ-Builder | `RunnableC46606KYf` | baut die IQ |
| `pair-device`-Request/Response-Helfer | `KRI` (`devicePairRequest/*`) | senden, retry, parsen von `device` / `companion-props` / Retry-Hinweisen |
| Error-Router | `C44661Jem` | mappt Server-Fehlercode auf UI-Callback |
| QR-String-Parser | `C45741Jxy` → `C45423Jrn` | QR-Payload zu Pairing-Daten |
| Geparste Pairing-Daten | `C44423JaU` | ref, Companion-Keys, adv secret, Plattform |
| ADV-Util | `C24270w6` (`CompanionDeviceAdvUtil`) | rawId, Key-Index, Timestamp, Aufbau und Signierung der Key-Index-Liste |
| Key-Index-Liste-Updater | `C24250w4` (`DeviceKeyIndexListUpdateHandler`) | pusht signierte Liste zum Server |
| ADV-Verifizierer | `C24230w2` (`DeviceADVInfoHandler`) | verifiziert auf der Leitung gesehene Identitäten und Listen |
| Geräteliste-Notification-Handler | anonyme Klasse in `C1S0` (`DeviceUpdateNotificationHandler`), `RunnableC29334CoL` | `devices`-Notification |
| Link-Code-Notification-Handler | `C10J` (`LinkCodeCompanionRegNotificationHandler`) | Notification-ID 252 |
| Link-Code-Manager (primär) | `KZ3` (Code-Eingabe, `primary_hello`), `KYB` (`companion_finish`), `C10L`, `C77` | Pair-Code-Flow |
| Link-Code-Crypto-Util | `K1T` (`CompanionRegWithLinkCodeUtil`) | HKDF, PBKDF2, base32 |
| Device-Manager | `C0XQ` (`companion-device-manager`) | Liste, Logout |
| Remove-Helfer | `C28905Ch6` (`DeviceRemoveRequestProtocolHelper`) | `remove-companion-device` |
| Signal-Curve-Wrapper | `C38851hm` | `org.whispersystems.curve25519`-Provider "best" |
| ADV-Proto-Klassen | `C25815BBy`, `C25792BBb`, `C25785BAt`, `C25786BAu`, `BCB` | siehe Abschnitt 5 |
| DeviceProps | `C43105IrG` (Enum `EnumC25120ArW`) | `companion-props` im `pair-device`-Ergebnis |
| Client-Props | `C43107IrI` | `client-props`-Kindknoten |
| Account-/Encryption-Typ | `EnumC32116E1o` | `E2EE` 0, `HOSTED` 1, `NON_E2EE` 2 |

In der Primär-UI gibt es drei Einstiegsmodi (`EnumC26221BZl`): `QR_CODE`, `PHONE_NUMBER_AND_CODE`, `EXTERNAL_DEEPLINK_QR_CODE` (found).

Dieselbe APK enthält auch den Code für die Companion-Rolle-Registrierung (State-Machine `C0YS`, `companion/registration/*`-Logs). Das liegt außerhalb des Umfangs; nur die Teile, die nötig sind um zu erklären, was der Primärseite ankommt, werden beschrieben (Abschnitt 9.6).

---

## 2. Pairing-Pfade im Überblick

| Pfad | Trigger auf Primärseite | Primärseite sendet | Secret, das Primär- und Companion-Seite verbindet |
|------|--------------------|---------------|----------------------------------------|
| QR | Scan von `https://wa.me/settings/linked_devices#<payload>` (oder `whatsapp://settings/linked_devices#<payload>`) | `iq xmlns=md` `pair-device` | `adv secret` aus QR-Feld 4 |
| Telefonnummer + Code | `notification` `link_code_companion_reg`, Stage `companion_hello`, User tippt 8-stelligen Code | `primary_hello`, später (nach `companion_finish`) dieselbe `pair-device` | `adv secret` abgeleitet aus zwei X25519-Ergebnissen plus einem Zufallswert (Abschnitt 4.4) |

Beide Pfade laufen zu einem `C44423JaU`-Objekt und einer `pair-device`-IQ zusammen (found: `KYB` baut `C44423JaU` aus dem `companion_finish`-Bundle mit demselben Konstruktor `C45850K0w.A01`, der auch für QR verwendet wird).

---

## 3. QR-Flow (Primärseite)

### 3.1 QR-Payload

`C45741Jxy.A01` entfernt den Präfix `https://wa.me/settings/linked_devices#` oder `whatsapp://settings/linked_devices#` und URL-dekodiert den Rest. `A02` splittet auf `,` (found):

| Idx | Inhalt | Encoding | Verwendung |
|-----|---------|----------|-----|
| 0 | `ref` | String | Pairing-Referenz; eine ref, die mit `CAPI_` beginnt, wird abgelehnt (`invalid ref`) |
| 1 | Companion-Public-Key | base64 | wird als `pub-key` gesendet, Salt für den Nonce-Key (3.4). Name inferred: Noise-Static-Key (`companion_server_auth_key_pub` im Code-Pfad) |
| 2 | Companion-Identity-Key | base64, 32 Bytes, Parser stellt `0x05` (Curve25519-Typ) voran | wird von der Account-Signatur signiert |
| 3 | `adv secret` | base64 | HMAC-Key für den ADV-Wrapper |
| 4 | Plattform-Code (optional) | ein Zeichen | mappt auf einen Plattformtyp; `j` = hosted device |

- Weniger als 3 Teile: `qrData/processQR/error/invalid_code parts`. Fehlender Identity-Key oder adv secret (alte 3-Feld-QR): `invalid qr code, missing companion identity key or adv secret` → lokaler Code **-9**.
- Plattformzeichen-Tabelle (unabhängig von `EnumC26221BZl`, `EnumC26332BbY`): `0` UNKNOWN, `1` CHROME, `2` EDGE, `3` FIREFOX, `4` IE, `5` OPERA, `6` SAFARI, `7` DESKTOP, `8` UWP, `9` OTHER_WEB, `a` IOS_TABLET, `b` IOS_PHONE, `c` IOS_CATALYST, `d` ANDROID_TABLET, `e` ANDROID_PHONE, `f` ANDROID_AMBIGUOUS, `g` WEAR_OS, `i` AR_DEVICE, `j` HOSTED_DEVICE, `k` VR, `l` SMARTGLASSES, `n` WAIL_WAI, `o` WAIL_ALEXA (found). Wird nur für die Hosted-Prüfung und das Logging verwendet (3.2).

### 3.2 Lokale Prüfungen, bevor irgendetwas gesendet wird

| Prüfung | Code | Lokaler Code |
|-------|------|------------|
| QR hat Identity-Key und adv secret | `C45850K0w.A01` | -9 |
| Hosted-Flag konsistent: `(accountType == HOSTED) == (platform int == 20)` | `A01` | -13 |
| anderes Pairing läuft bereits (`kri.A0N`, oder Companion-Device-Manager beschäftigt) | `A04` | -17 |
| lokaler ADV-Timestamp gültig (`C24270w6.A00() != -1`) | `A04` | -8 |
| Hosted-Companion | `A04`: `Hosted pairing is not supported` | -10 |
| Defense-Mode-Friction nötig | `RunnableC46606KYf`: `defense mode friction triggered` | -20 (Retry mit Challenges) |

Hosted-Pairing ist in diesem Build clientseitig blockiert (`pairing for hosted device is not supported on the consumer build`).

### 3.3 Vor der IQ: syncd-Cleanup und Key-Index

1. Ist der syncd-Zustand dirty (`sync-manager/shouldCleanUpSyncdOnPairing`), säubert die App zuerst syncd und macht dann weiter (`handleSyncdDirty clean syncD before companion dereg`) (found).
2. `incrementCurrentKeyIndex` (in `RunnableC46617KYr`):
   - keine gespeicherte rawId oder Index: neue zufällige rawId, Index 1;
   - keine Companions verlinkt: `rawId + 1`, Index bleibt 1;
   - Companions existieren: `currentIndex + 1`; bei Overflow rawId + 1 und alle Geräte werden ausgeloggt (`C24270w6.A03`).
3. `ts = C24270w6.A00()` (Abschnitt 5.4).

### 3.4 Was aufgebaut wird

In `C45850K0w.A00`, mit `E` = Companion-Identity-Key (32 B, raw), `P` = Primär-Identity-Keypaar (Curve25519), `S` = adv secret:

| Schritt | Operation | Tier |
|------|-----------|------|
| 1 | `ADVDeviceIdentity` `{rawId, timestamp=ts, keyIndex=currentIndex, accountType, deviceType}` | found |
| 2 | Account-Signatur = `Curve25519 sign(P.priv, prefix ‖ details ‖ E)`; Präfix `06 00` (hosted `06 05`) | found |
| 3 | `ADVSignedDeviceIdentity` `{details, accountSignatureKey = P.pub, accountSignature}` (`deviceSignature` bleibt leer: der Companion fügt sie hinzu) | found |
| 4 | `ADVSignedDeviceIdentityHMAC` `{details = serialisiertes Schritt 3, hmac = HMAC-SHA256(key = S, data = Schritt-3-Bytes), accountType}`; bei hosted ist die Data `06 05 ‖ bytes` | found |
| 5 | `BCB` (ADVKeyIndexList) aus `C24270w6.A01`, signiert von `A02` → `ADVSignedKeyIndexList` (5.3) | found |
| 6 | Nonce-Key `K = HKDF-SHA256(salt = pub-key, IKM = S, info = "Canonical Ent Companion Nonce Encrypt", 32 B)`, als `pem`-Kind verpackt | found (Ableitung); Zweck inferred |
| 7 | optionale `encryption-metadata` (`C38898Gvq`): `encrypted_key`, `nonce`, `encrypted_data`, `auth_tag`, aus `AuthProofHelper` (Account-Passwort-Verschlüsselung, Label `rsa2048`) | found (Struktur); was damit bewiesen wird, ist unknown |
| 8 | optionale `client-props` (`C43107IrI`, Abschnitt 3.6) | found |

Detail zu Schritt 6: Der `pem`-Knoten ist mit `version=1`, `algorithm=rsa2048`, `ttl ts_s = 5 Tage`, `key_id=1` gelabelt, aber sein Kindknoten trägt `key.getEncoded()` der 32-Byte-HKDF-Ausgabe (`SecretKeySpec`-Algorithmus `AES-GCM`). Label und Inhalt passen nicht zusammen; warum ist unknown. Server-Verwendung ist inferred (Server verschlüsselt eine Pro-Device-Nonce für den Companion; vgl. `companion_meta_nonce`-Spalte).

### 3.5 Die `pair-device`-IQ (Primärseite → Server)

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <pair-device>
    <ref>…</ref>                                    <!-- QR field 0 -->
    <pub-key>…</pub-key>                            <!-- QR field 1 -->
    <device-identity>ADVSignedDeviceIdentityHMAC</device-identity>
    <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
    <client-props>…</client-props>                  <!-- optional -->
    <pem version="1" algorithm="rsa2048"><pem>…</pem><ttl ts_s="432000"/><key_id>1</key_id></pem>
    <encryption-metadata version="1" algorithm="rsa2048">…</encryption-metadata>   <!-- optional -->
    <companion_qr_origin_source>1|2</companion_qr_origin_source>
    <challenges><supported><friction variant="1"/><passkey-create/></supported>
                <completed>…</completed></challenges>                              <!-- optional -->
  </pair-device>
</iq>
```

Found: alle Kindknoten-Namen, der `ts`-Attributwert (der Timestamp der Key-Index-Liste), Timeout **32000 ms** (`c10140Tq.A0Q(…, 219, 32000L)`). `companion_qr_origin_source` ist `1` für Entry-Wert 3 und `2` für Entry-Wert 5 (Bedeutung der Entry-Ints unknown). Genaue Kindknoten-Reihenfolge und der `companion_qr_origin_source`-Zweig sind durch den Dekompiler teilweise verunstaltet; Reihenfolge als unverifiziert behandeln.

### 3.6 `client-props` (`C43107IrI`)

| Feld | Nummer | Typ | Gesetzt wenn |
|-------|--------|------|----------|
| `isChatDbLidMigrated` | **1** | bool | Chat-DB-LID-Migration abgeschlossen |
| `isSyncdPureLidSession` | **2** | bool | syncd-Pure-LID-Flag gesetzt |
| `isSyncdSnapshotRecoveryEnabled` | **3** | bool | Recovery-Flag |
| `isHsThumbnailSyncEnabled` | **4** | bool | History-Sync-Thumbnail-Flag |
| `subscriptionSyncPayload` | **5** | bytes | aufgebaut, wenn md-Sync aktiviert ist (`buildSubscriptionSyncPayload`) |
| `isBotJidDbMigrated` | **6** | bool | Bot-JID-DB migriert |

### 3.7 Ergebnisbehandlung (`KRI.CFS`)

Kindknoten eines Erfolgsergebnisses (found):

| Kind | Verwendung |
|-------|-----|
| `device` Attr `jid` | die neue Companion-`DeviceJid`; Device-ID **99** wird auf den Hosted-Plattform-Eintrag gemappt |
| `companion-props` | `DeviceProps`-Proto (`C43105IrG`): `os` **1** (String), `version` **2** (Message), `platformType` **3** (Enum), `requireFullSync` **4** (bool), `historySyncConfig` **5** (Message) |
| `retry-ts` Attr `ts` | Server verlangt einen neueren Timestamp; App macht Retry (`RunnableC46585KXj`) |
| `retry-after-challenges` | Kindknoten `friction` (Attr `variant`, muss `1` sein, optional `location` "lat,lon") oder `passkey-create` (Attr `created`) |
| `retry-with-method` | Kindknoten `qr-code` oder `shortcake-with-passkeys`; ist Letzteres vorhanden, wird der 32-Byte-Handoff-Key (HKDF des adv secret, info `shortcake-passkey-handoff-v1`) gespeichert (`PairingHandoffKeyHolder`), gated durch ein abprop |

Bei Erfolg speichert die App den `CJY`-Device-Record (zufälliger 24-Byte-base64-String, `adv_key_index` = aktueller Index, `requireFullSync`), speichert den Timestamp der Key-Index-Liste als `adv_timestamp_sec` (`C24270w6.A05`) und startet den History-Sync-Zustand (`C8N`).

Zustellungsfehler (`Bog`): bis zu **3** Retries, Delay `3000 * 3^(n-1)` ms (3 s, 9 s, 27 s), falls das Retry-Flag gesetzt ist (found); dann Error-Callback.

---

## 4. Telefonnummer-/Pair-Code-Flow (Primärseite)

### 4.1 Schritte

| # | Richtung | Stanza / Aktion | Klasse |
|---|-----------|-----------------|-------|
| 1 | Companion → Server → Primärseite | `notification` `link_code_companion_reg`, `stage=companion_hello` | `C10J` (ID 252) |
| 2 | Primärseite | speichert hello, zeigt Push-Notification → `CompanionHelloConfirmationActivity` / Code-Eingabe-Screen | `C10J`, `C77`, `JYJ` |
| 3 | User | tippt den 8-stelligen Code ein | `LinkedDevicesEnterCodeActivity` |
| 4 | Primärseite → Server | `iq xmlns=md type=set` `link_code_companion_reg stage=primary_hello` | `KZ3` (Timeout 120000 ms) |
| 5 | Server → Primärseite | `notification` `stage=companion_finish` | `C10J` → `KYB` Case 0 |
| 6 | Primärseite → Server | `pair-device`-IQ (Abschnitt 3.5) | `C45850K0w` |
| 7 | andere Stages | `refresh_code` (Primärseite fordert Code-Refresh an, Attr `force_manual_refresh`) | `C10J` |

### 4.2 `companion_hello`-Notification (found)

| Kind | Verwendung |
|-------|-----|
| `link_code_pairing_wrapped_companion_ephemeral_pub` | Companion-Ephemeral-X25519-Key, mit dem Code gewrapped (4.3) |
| `companion_server_auth_key_pub` | wird später zum `pub-key` in `pair-device` |
| `link_code_pairing_ref` | Session-Ref (String) |
| `companion_platform_id` | Plattform-ID-String |
| `companion_platform_display` | Anzeigename |
| Attr `should_show_push_notification` | `true` → Push-Notification |

Gespeicherter Zustand (`C77`/`CE4`, SharedPrefs-JSON `companion_reg_with_link_code_companion_hello_info_json`): ref, Plattform-ID, Wrapped-Key, Server-Auth-Key, Ablauf `now + min(360000, flag 3816 * 1000)` ms. Abgelaufenes oder fehlendes hello → "companion hello is null or expired" (UI-State 2). Ein neueres hello mit anderer ref annulliert die vorherige ref (`KRJ.A00(oldRef, "true")`).

### 4.3 Code- und Wrap-Krypto (found)

| Item | Wert |
|------|-------|
| Code | 5 zufällige Bytes → 8 Zeichen, je 5 Bit, Alphabet `123456789ABCDEFGHJKLMNPQRSTVWXYZ` (32 Symbole, kein `0 I O U`) (`K1T.A00`, vom Companion erzeugt) |
| Code → Key | PBKDF2-HMAC-SHA256, **131072** Iterationen, 256 Bit, Passwort = Code-Zeichen, Salt = erste 32 Bytes des gewrappten Blobs (`K1T.A02`) |
| Gewrappter Ephemeral-Key | `[salt 32 ‖ IV 16 ‖ AES-256-CTR-Ciphertext]`, Plaintext = 32-Byte-X25519-Public-Key; Länge muss ≥ 48 sein |
| Antwort der Primärseite | die Primärseite erzeugt ihr eigenes Ephemeral-Keypaar, wrappt dessen Public-Key auf dieselbe Art (frisches 32-B-Salt, 16-B-IV, derselbe Code) |

### 4.4 `primary_hello` und `companion_finish`

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md">
  <link_code_companion_reg stage="primary_hello">
    <link_code_pairing_wrapped_primary_ephemeral_pub>salt32‖iv16‖ct</…>
    <primary_identity_pub>32 B primary identity key</primary_identity_pub>
    <link_code_pairing_ref>ref</link_code_pairing_ref>
  </link_code_companion_reg>
</iq>
```

Kindknoten der `companion_finish`-Notification: `link_code_pairing_wrapped_key_bundle`, `companion_identity_public`, `link_code_pairing_ref`. Verarbeitung auf der Primärseite in `KYB` Case 0:

1. `eph = X25519(primary eph priv, companion eph pub)` (gespeichert zum Zeitpunkt von `primary_hello`).
2. Bundle-Layout `[salt 32 ‖ nonce 12 ‖ AES-256-GCM-Ciphertext+Tag]`, mindestens 44 Bytes.
3. Key = HKDF-SHA256(salt = Bundle-Salt, IKM = `eph`, info = `link_code_pairing_key_bundle_encryption_key`, 32 B).
4. Plaintext = `companion identity pub (32) ‖ primary identity pub (32) ‖ random (32)`.
5. Prüfungen: Primär-Identity muss mit dem eigenen Identity-Key übereinstimmen; Companion-Identity muss mit `companion_identity_public` aus der Notification übereinstimmen; andernfalls wird die ref verworfen und die UI erhält einen Fehlerzustand.
6. `adv secret = HKDF-SHA256(salt = 32 Nullbytes, IKM = eph ‖ X25519(primary identity priv, companion identity pub) ‖ random, info = "adv_secret", 32 B)` (`K1T.A03`).
7. Handoff-Key = HKDF(adv secret, info `shortcake-passkey-handoff-v1`) (ebenfalls in `C44423JaU` gespeichert).
8. `C44423JaU` wird aufgebaut mit `pub-key` = `companion_server_auth_key_pub`, Companion-Identity, adv secret → dieselbe `pair-device`-IQ wie bei QR.

Die äußere Ephemeral-ECDH existiert (sie ist der HKDF-IKM von Schritt 3). Eine Notiz aus einem früheren Build sagte "no ECDH in this stage"; das ist für diesen Build falsch.

Fehlermarker auf der Primärseite: `getCompanionPairingDataOnCompanionFinish ref not exists`, `decryption fail`, `primary identity doesn't match`, `companion identity doesn't match`, `invalid linkCodePairingWrappedKeyBundleDecrypted` (found).

---

## 5. ADV signed device identity

### 5.1 Proto-Felder (found, aus den Lite-Proto-Layout-Strings)

| Message | Klasse | Feld | Nummer | Typ |
|---------|-------|-------|--------|------|
| `ADVDeviceIdentity` | `C25815BBy` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `keyIndex` | **3** | uint32 |
| | | `accountType` | **4** | Enum (`EnumC32116E1o`) |
| | | `deviceType` | **5** | Enum (`EnumC32116E1o`) |
| `ADVSignedDeviceIdentity` | `C25792BBb` | `details` | **1** | bytes |
| | | `accountSignatureKey` | **2** | bytes |
| | | `accountSignature` | **3** | bytes |
| | | `deviceSignature` | **4** | bytes (vom Companion gesetzt) |
| `ADVSignedDeviceIdentityHMAC` | `C25785BAt` | `details` | **1** | bytes |
| | | `hmac` | **2** | bytes |
| | | `accountType` | **3** | Enum |
| `ADVKeyIndexList` | `BCB` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `currentIndex` | **3** | uint32 |
| | | `validIndexes` | **4** | packed uint32 |
| | | `accountType` | **5** | Enum |
| `ADVSignedKeyIndexList` | `C25786BAu` | `details` | **1** | bytes |
| | | `accountSignature` | **2** | bytes |
| | | `accountSignatureKey` | **3** | bytes (nur hosted) |

Feldnummern und Wire-Typen stammen aus der generierten Message-Info; Namen stimmen mit den kanonischen ADV-Messages überein. Enum-Namen: `EnumC32116E1o`-Werte E2EE 0, HOSTED 1, NON_E2EE 2.

### 5.2 Signatur-Präfixe und Algorithmen

| Präfix | Konstante | Signierte / MACte Daten | Signierer | Tier |
|--------|----------|---------------------|--------|------|
| `06 00` | `AbstractC051108f.A0F` | Account-Signatur: `‖ details ‖ companion identity pub` | Primär-Identity-Key | found |
| `06 05` | `A0G` | Hosted-Variante der Account-Signatur; wird auch den HMAC-Daten für hosted vorangestellt | Primär-Identity-Key / adv secret | found |
| `06 01` | `A0H` | Device-Signatur: `‖ details ‖ companion identity pub ‖ accountSignatureKey` | Companion-Identity-Key | found (Verify-Seite) |
| `06 06` | `A0I` | Hosted-Variante der Device-Signatur | Companion-Identity-Key | found (Verify-Seite) |
| `06 02` | `A0J` | `ADVSignedKeyIndexList`: `‖ details` | Primär-Identity-Key | found |
| `06 07` | `A0K` | non-E2EE-("hybrid")-Attestation (`AeaUtils`), kein Key-Index-Liste-Präfix | Primär-Identity-Key | found |

- Signatur-Primitive: `C38851hm.A00("best")` lädt `org.whispersystems.curve25519.OpportunisticCurve25519Provider`; `A03` = `calculateSignature(random 64 B, priv, msg)`, `A01` = `verifySignature` (64-Byte-Signatur), `A02` = `calculateAgreement`. Keys sind 32 Bytes mit Type-Byte `5`. Also Curve25519-Signaturen der Signal-curve25519-Library (XEdDSA-artig, inferred aus der Library, nicht aus dem Algorithmusnamen). Die Wahl des Providers (native vs. Java) wird zur Laufzeit entschieden (unknown, welcher auf einem gegebenen Gerät verwendet wird).
- HMAC: `HmacSHA256` via `javax.crypto.Mac` (`AbstractC38971i1.A00`).

### 5.3 Key-Index-Liste

`C24270w6.A01` baut `ADVKeyIndexList` auf; `validIndexes` ist eine Menge aus (found): einem Eintrag für den Primärslot (Wert 0, wenn nicht im Companion-Modus; Bedingung des Zweigs inferred), dem `adv_key_index` jedes gespeicherten Companions (`CJY.A07`) und `currentIndex`. `A02` signiert `06 02 ‖ details`.

`C24250w4.A00` pusht sie als:

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
</iq>
```

Timeout 32000 ms. Gate `A02`: Flag **477** ungleich null, Companions vorhanden (oder Companion-Modus), nicht im Companion-Modus. Bei Fehlschlag wird `adv_key_index_list_update_retry_count` erhöht; über **5** loggt die App `adv-key-index-list-update … fails for more than 5 times` und loggt alle Companions aus (`C24270w6.A03`). Erfolg setzt die Zähler zurück (`A05`).

### 5.4 Timestamp-Regel (`C24270w6.A00`)

`last` = SharedPrefs `adv_timestamp_sec`; `now` = NTP-korrigierte Uhr, `srv` = Serverzeit. `ts = max(srv falls |srv - now| <= 86400 sonst now, last + 1)`. Wenn `last + 1 > now + 86400`, ist der Wert ungültig (-1, geloggt `getTimestampSec invalid ts`), was das Pairing mit lokalem Code -8 blockiert. Monoton pro Account (found).

### 5.5 Verifikation auf der Leitung (`C24230w2`)

Für jede Device-Identity, die die Primärseite sieht (eigene und Companions von Kontakten), prüft sie, in dieser Reihenfolge (found):

1. Primär-Identity-Key bekannt (gespeichert, oder `accountSignatureKey` aus der Liste), sonst `no primary key`;
2. Companion-Identity-Key parst (`0x05`+32 B), sonst `invalid companion public key`;
3. Account-Signatur über `prefix ‖ details ‖ companion identity`, sonst `fail to verify account signature`;
4. Device-Signatur über `06 01 ‖ details ‖ companion identity ‖ accountSignatureKey` (hosted `06 06`), sonst wird das Gerät abgelehnt;
5. Key-Index-Liste: Signatur über `06 02 ‖ details` mit dem Primärschlüssel; `adv timestamp` der Liste muss konsistent sein (`advTimestampMismatch`, `advListTimestampInvalid`); ein nicht passender eingehender Key-Index setzt den lokalen Zustand zurück (`incoming key-index not matching local state, resetting`); ein größerer Index für dasselbe Gerät, das bereits vorhanden ist, verwirft den älteren Eintrag (`filterDeviceWithKeyIndexList`).

---

## 6. Geräteliste, Record und Limits

### 6.1 `devices`-Notification (Primärseite empfängt)

`notification` mit Kindknoten `add` oder `remove` (alles andere: `unknown type of device notification`). Attribute und Kindknoten (found): `device_hash`, optional `device_lid_hash` plus `lid`, `device`-Einträge (jid, Key-Index), optional `key-index-list` (bytes, Attr `ts`, `expected_ts`). Trägt die Notification Attr `offline`, wird der User für späteren Sync eingereiht; sonst läuft ein Sync-Job (`SyncDeviceNotificationRunnable`). Die Liste wird nur akzeptiert, wenn ihr Timestamp nicht älter ist als der gespeicherte `adv_timestamp_sec` (sonst `local ts is larger than notification one`).

### 6.2 Gespeicherter Device-Record (`devices`-Tabelle, `C1h8`)

| Gruppe | Spalten (found) |
|-------|-----------------|
| Identität | `device_id`, `platform_type`, `device_os`, `adv_key_index`, `companion_meta_nonce`, `instrumentation_device_id`, `nickname`, `place_name` |
| Zeit | `last_active`, `login_time`, `logout_time` |
| Sync | `full_sync_required`, `full_sync_days_limit`, `full_sync_size_mb_limit`, `recent_sync_days_limit`, `storage_quota_mb`, `inline_initial_hist_sync_payload_enabled`, `history_sync_config_protobuf`, `history_sync_access_type`, `on_demand_ready` |
| Fähigkeit | `support_hosted_group_msg`, `support_biz_hosted_msg`, `support_group_history`, `support_call_log_history`, `support_message_association`, `support_add_on_history_sync_migration`, `support_guest_chat`, `support_bot_user_agent_chat_history`, `support_fbid_bot_chat_history`, `support_manus_history`, `support_hatch_history`, `support_cag_reactions_and_polls_history`, `support_recent_sync_chunk_message_tuning`, `supported_bot_channel_fbids` |

`platform_type`-Werte kommen von `companion-props.platformType` (`EnumC25120ArW`): 0 UNKNOWN, 1 CHROME, 2 FIREFOX, 3 IE, 4 OPERA, 5 SAFARI, 6 EDGE, 7 DESKTOP, 8 IPAD, 9 ANDROID_TABLET, 10 OHANA, 11 ALOHA, 12 CATALINA, 13 TCL_TV, 14 IOS_PHONE, 15 IOS_CATALYST, 16 ANDROID_PHONE, 17 ANDROID_AMBIGUOUS, 18 WEAR_OS, 19 AR_WRIST, 20 AR_DEVICE, 21 UWP, 22 VR, 23 CLOUD_API, 24 SMARTGLASSES, 25 WAIL, 26 WASS, 27 BUSINESS_BACK_OFFICE, 28 WAIL_WAI, 29 WAIL_ALEXA, 30 AUTOMOTIVE (found).

### 6.3 Limits und Flags

| Flag / Item | Bedeutung | Tier |
|-------------|---------|------|
| **15550** | Integer: maximale Anzahl verlinkter Geräte (`LinkedDevicesSharedViewModel.hasMaxDeviceLimitReached`: `loggedInDeviceCount >= max` blockiert "Gerät verknüpfen"; der QR-Scanner erhält zusätzlich `at_device_limit`; `OrbitCompanionLinkActivity` verweigert bei Erreichen) | found (Verwendung); Standardwert unknown (server-ausgeliefertes abprop); Metrikfeld `md_linked_devices_max_devices_limit` existiert |
| **3816** | Sekunden, die `companion_hello` gültig bleibt, gekappt auf 360 s | found |
| **477** | Gate (ungleich null) für Key-Index-Liste-Updates | found |
| **18193** | fügt `friction` (variant 1) zu den angebotenen `challenges/supported` hinzu | found (Verwendung); Effekt auf dem Server unknown |
| **28161** | fügt die zweite angebotene Challenge hinzu (`passkey-create`) | inferred Mapping (Dekompiler hat den Zweig verloren) |
| **29500** | Hosted-Pairing-Gate, verwendet in der Defense-Mode-Prüfung | found (gelesen), Bedeutung inferred |
| **31019** | fügt Attr `exclude_hosted_companion=true` zum Remove-All für manche Gründe hinzu | found |

Ob der Server das Limit unabhängig von der Client-Prüfung durchsetzt, ist unknown. Die Primärseite hat im hier gelesenen Code kein clientseitiges Inaktivitäts-Timeout für Companions; serverseitiger Ablauf von inaktiven Companions ist unknown.

---

## 7. Unlink (Primärseite)

### 7.1 Einzelnes Gerät

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <remove-companion-device jid="user:device@…" reason="user_initiated"/>
</iq>
```

`C28905Ch6.A00`, Timeout 32000 ms. Ergebnis kann den Kindknoten `coex_token` tragen (wird an den Coexistence-Handler weitergegeben). Zustellungsfehler oder Error ruft den Failure-Callback mit Code -1 (found).

### 7.2 Alle Geräte

`C0XQ.A0Y(reason, removeOnError, isEncryptionTypeTransitioning)`:

```xml
<remove-companion-device all="true" reason="…" [exclude_hosted_companion="true"]/>
```

Eine leere lokale Liste springt direkt zum Success-Callback. Im Code gesehene Reason-Strings: `user_initiated`, `unknown_companion`, `invalid_adv_status`, `lid_migration_peer_sync_limit_exceeded`, `lid_migration_peer_sync_message_failed`, `lid_migration_missing_mappings_in_peer_sync_message` (found; Liste kann länger sein, der Source-Ausdruck ist abgeschnitten).

### 7.3 Automatische Unlink-Trigger (found)

| Trigger | Grund |
|---------|--------|
| Key-Index-Liste-Update mehr als 5-mal fehlgeschlagen | `adv-key-index-list-update`, Logout aller |
| Key-Index-Overflow | `A03`-Reset |
| ungültiger ADV-Status / unbekannter Companion (`KZD` Case 43) | `invalid_adv_status` |
| Übergang hosted ↔ E2EE-Accounttyp | wirft alle Geräte raus (`handleADVMetadata`-Log) |
| Server sendet `devices`-Notification vom Typ `remove` | lokaler Record entfernt (inferred) |
| User-Aktion im Linked-Devices-Screen / `EavesdropMonitor/disconnectDevice` | `user_initiated` (found für den Monitor; UI-Pfad inferred) |

Account-Entfernung als Ganzes (`urn:xmpp:whatsapp:account` `remove`) ist eine andere IQ und steht in keinem Zusammenhang mit Companion-Unlink.

---

## 8. Fehlerfälle

### 8.1 Von `C44661Jem.A01` behandelte Servercodes

| Code | Callback | UI | Tier |
|------|----------|----|------|
| **465** | `Blp` → `onCompanionPlatformRestricted` | `CompanionPlatformRestrictedBottomSheet` | found |
| **496** | `Blv` → `onCompanionTooOld` | Zustand "companion too old" | found |
| 404 / 405 / 443 / 445 | generisch `C2w` | String-Mapping `C44648JeY`: 405 und 443 haben eigene Texte; 404/405/443/445 teilen sich einen Titel | found (Strings nach ID); genaue Bedeutung von 404/443/445 unknown |
| andere | generisch `C2w` | pair failed | found |

`InstrumentationAuthActivity` benennt Ergebniscodes 1 `CONSUMER_SMB_CROSS_PAIRING`, 2 `UNSUPPORTED_PRIMARY_VERSION`, 3 `INVALID_QR_CODE`, 4 `COMPANION_PLATFORM_RESTRICTED`, 5 `COMPANION_TOO_OLD`, 6 `MAX_DEVICE_LIMIT_REACHED`, sonst `PAIRING_FAILED` (found). Mapping von Server-405 auf den Consumer/SMB-Fall ist inferred aus der String-ID.

### 8.2 Lokale Codes

| Code | Ursache | Fix |
|------|------|------|
| -8 | lokaler ADV-Timestamp ungültig (Uhr vs. letztem gespeicherten ts + 1) | Gerätezeit korrigieren; UI-String "invalid device time" |
| -9 | QR fehlt Identity-Key / adv secret | aktuellen QR verwenden |
| -10 | Hosted-Pairing auf Consumer-Build | n/a |
| -13 | Plattform- vs. Hosted-Flag-Mismatch | n/a |
| -17 | anderes Pairing läuft bereits | warten; Request lebt bis zu 32 s |
| -20 | Server fordert Challenges an (`retry-after-challenges`) | Friction-/Passkey-Challenge abschließen |
| -1 | Remove-Request nicht gesendet oder fehlgeschlagen | Retry |

### 8.3 Link-Code-Fehler

| Symptom (Log) | Ursache |
|---------------|-------|
| `companion hello is null or expired` | Code nach Ablauf eingegeben (Flag 3816, max. 360 s) |
| `decryption fail` (hello) | falscher Code (PBKDF2-Key unterscheidet sich; AES-CTR hat kein Tag, also liefert ein falscher Code einen Garbage-Key, der erst in späteren Schritten erkannt wird; inferred) |
| `primary identity doesn't match` | Bundle wurde für einen anderen Primärschlüssel gebaut |
| `companion identity doesn't match` | Notification und Bundle stimmen nicht überein |
| `invalid-primary-adv-key-length` / `adv public key is 0` | Prüfungen auf Companion-Seite am Primär-Ephemeral-Key |

---

## 9. Abgrenzungen

### 9.1 Nicht verwechseln

| A | B |
|---|---|
| `pair-device`, gesendet von der **Primärseite** (dieser Report) | `pair-device`, **empfangen** von einer App in der Companion-Rolle (Handler `AbstractC40501kw`, ID 242, trägt refs für den QR) |
| `ADVSignedDeviceIdentity` (signiert, ohne HMAC) | `ADVSignedDeviceIdentityHMAC` (der Wrapper, der im `device-identity` gesendet wird) |
| `device-identity`-Kindknoten der `pair-device` (HMAC-Wrapper) | `device-identity`-Kindknoten in ausgehenden Message-Stanzas (Account-Identity, von einem Companion angehängt; `adv_signed_identity`-Pref) |
| Account-Signatur (Primärschlüssel, Präfix `06 00`) | Device-Signatur (Companion-Schlüssel, Präfix `06 01`) |
| Key-Index-Liste-Präfix `06 02` | `06 07` (non-E2EE-Attestation) |
| QR `pub-key` / `companion_server_auth_key_pub` | Companion-Identity-Key (der, der die Account-Signatur erhält) |
| `rawId` (accountweite ID, die sich bei Reset ändert) | `keyIndex` (pro Companion) |
| QR-Plattformzeichen (`EnumC26332BbY`) | Wire-`DeviceProps.platformType` (`EnumC25120ArW`), unterschiedliche Nummerierung |

### 9.2 Hosted Device

JID-Device-ID **99** (`device_id should be 99 for hosted device`), Registrierungs-/Unpair-Marker `hosted_device_pairing`, Signatur-Präfixe `06 05` / `06 06`, `exclude_hosted_companion`. Die Primärseite weigert sich in diesem Build, ein Hosted Device zu pairen (lokal -10). Alles über diese Strings hinaus ist unknown.

### 9.3 Shortcake

`retry-with-method` kann `shortcake-with-passkeys` listen; die App speichert dann einen Handoff-Key und wechselt die UI. `ShortcakeJni` exponiert `nativeMlkem768GenerateKeypair/Encapsulate/Decapsulate` und `nativeResponderStart/Finish` (found). Das Handshake-Transkript ist native und wurde hier nicht dekompiliert: unknown.

#### 9.3a Silent Linking — Tethered-/Peripheral-Companion-Pairing + Epoch-Migration (neu in 2.26.45.10, found)

Ein **vierter** Pairing-Mechanismus, enger als die drei oben (klassisches ADV/QR, Pair-Code/CRSC, Hosted Device): Silent Linking von **tethered/peripheral Companions** — Wearables und Smart Glasses, `DeviceProps.platformType` `WEAR_OS` / `AR_WRIST` / `AR_DEVICE` / `SMARTGLASSES`. Package `com.whatsapp.instrumentation.product.silentlinking` (`SilentLinkingNativeRegistration`, `SilentLinkingSessionManager$Session`).

**"Silent" bedeutet kein QR-Scan, nicht keine User-Interaktion.** Telemetrie-Strings (found) zeigen einen Short-Code-Bestätigungsflow: `"code displayed to user"` → `"user confirmed code on primary"` → `"companion registration start"`. Das Peripheral-Gerät zeigt einen Short-Code an und der User bestätigt ihn auf dem Telefon — dasselbe User-Presence-Modell wie der Pair-Code-Flow (§4), nur ohne das QR-Bild. Einstiegspunkt ist die Post-Call-Wearable-Upsell-UI (`PostCallWearableUpsellBottomSheet`, `com.whatsapp.calling.wearableupsell`), die in `SilentLinkingVerificationActivity` führt (`android:exported="false"`, intern, kein Deep Link). Der Trigger ist reines Client-UI: kein `AlarmManager`/`WorkManager`/Server-Push-Einstiegspunkt wurde in einer der beiden Klassen gefunden, und keine `unlink`-/`unpair`-/"existing device"-Logik taucht irgendwo in ihnen auf — das stellt eine Verbindung her, es entfernt keine im Stillen.

`SilentLinkingNativeRegistration` least einen Registrierungsslot aus dem bestehenden CRSC-v2/v3-Seitenkanal (`CompanionRegOverSideChannelV2Manager`/`V3Manager`, dieselbe Infrastruktur wie §4), um den entstehenden Identity-Registration zu transportieren. Der eigentliche Companion-Schlüsselaustausch ist eine separate, bisher nicht dokumentierte Protobuf-Familie:

**Shortcake-RPC-Envelope-Familie** (found, Feldnamen/-nummern aus smali, nicht unabhängig nach Java dekompiliert):

| Klasse | Rolle |
|-------|------|
| `LX/R9f` | Top-Level-`oneof`-Envelope: `protocolVersion`(1), `bootstrapAndHello`(2), `finishAndReady`(3), `peripheralAck`(4), `postCommitProofEnvelope`(5), `readinessRequestEnvelope`(6), `readinessResponseEnvelope`(7), `exactCleanupRequest`(8), `exactCleanupReceipt`(9) |
| `LX/RAN` | Bootstrap&Hello: `linkId`(1), `setupAttemptId`(2), `epochId`(3), `purpose`(4), `hnSignPub`(5), `hnEpoch1EphPub`(6, klassisches ECDH-Ephemeral), `hnMlkemPub`(7, ML-KEM-768-Public-Key), `protocolVersion`(8), `selectedCapabilities`(9), `migrationContextHash`(10), `hnDeviceSerial`(11) |
| `LX/RA1` | Signal-Ciphertext-verpackter Envelope: `signalCiphertext`(1), `signalMessageType`(2), `peripheralHello`(3), `signalRequestId`(4), `companionAdvFingerprint`(5), `primarySignalPeerFingerprint`(6) — verknüpft den Handshake mit dem eigenen ADV-Identity-Fingerprint des Companions (§5) |
| `LX/RAW` | zweiter `oneof`-Envelope, Epoch-Migrations-Seite: `rpcRequest`(1), `rpcResponse`(2), `primaryReady`(3), `peripheralAck`(4), `rotationControl`(5), `requestStatus`(6), `migrationPostCommitProof`(7), `migrationStatusRequest`(8), `migrationStatusResponse`(9), `migrationProbeRequest`(10), `migrationProbeResponse`(11) |
| `LX/RUe` | Enum `PERIPHERAL_PROPS_PLATFORM_{UNKNOWN,IOS,ANDROID}` — das eigene OS des Peripheral-Geräts |

`RAN.hnEpoch1EphPub` (klassisch) neben `RAN.hnMlkemPub` (ML-KEM-768) bestätigt einen **hybriden klassischen-ECDH-plus-Post-Quantum-Schlüsselaustausch**, nicht reines PQ. Dies ist der **erste in diesem Report dokumentierte Post-Quantum-Krypto-Mechanismus**: ML-KEM-768 (FIPS 203 / Kyber-768), ausgeführt über native `ShortcakeJni` (liboqs `OQS_KEM_ml_kem_768`, umhüllt von libsignals `KEMPublicKey`/`KEMSecretKey` — found durch native Dekompilierung in einem separaten Durchgang, siehe Brain `research/2.26.36.1/shortcake-kem-native.md`). Diese Java-seitige Schema ist das Transkript-Framing, das die native Analyse allein unknown gelassen hatte; der Byte-Level-Responder-Start/Finish-Handshake selbst bleibt native-only und unknown.

**HKDF-Context-Labels** (found, wörtliche Strings in `LX/SdB`, KDF = HMAC-SHA256 / HKDF-SHA256, dieselbe Primitive wie das Link-Code-Wrap-KDF in §4.3): `WA_TETHERED_EPOCH1_PERIPHERAL_HELLO_V1`, `WA_TETHERED_EPOCH1_HN_KEY_POP_V1`, `WA_TETHERED_EPOCH1_PERIPHERAL_HELLO_HASH_V1`, `WA_TETHERED_EPOCH1_PRIMARY_FINISH_V1`, `WA_TETHERED_EPOCH1_WA_KEY_POP_V1`, `WA_TETHERED_EPOCH1_HYBRID_KX_V1`, `WA_TETHERED_LINK_IDENTITY_CONTEXT_V1`. ("HN" = die Primär-/Telefonseite; wird im Tree nirgends ausgeschrieben, vermutlich "Host/Home Network".)

**Epoch-Rotation/-Migration (found Strings, inferred Rolle).** `LX/TIR` trägt ein umfangreiches Migrationsfehler-Vokabular (`"Invalid migration frame version"`, `"Migration epoch mismatch"`, `"Migration shadow serial mismatch"`, `migration_shadow` usw.), kombiniert mit `RAN.epochId` und den Rotation-/Migration-Probe-/Status-/Post-Commit-Proof-Feldern von `RAW`. Zusammen gelesen ist dies ein Hintergrund-**Key-Epoch-Rotationsprotokoll für einen bereits etablierten Tethered-Link** — `SilentLinkingSessionManager$Session` ruft periodisch `SilentLinkingNativeRegistration` erneut auf, um die Shortcake-Keys unter einer neuen `epochId` zu rotieren, mit Probe/Status/Promotion/Replay und einem "Shadow"-Record-Rollback-Pfad. Dies ist inferred Erzählung über found Strings/Felder; es ist kein Recovery-Mechanismus für eine verlorene klassische Companion-Session und kein serverseitig gepushtes Unlink. Die konkrete Auslösebedingung für einen Rotationszyklus und der genaue Wire-Transport für `R9f`/`RAW` (CRSC-Seitenkanal-Payload vs. eigene Stanza/IQ) sind unknown.

**Keine Baileys-/velowa-Relevanz.** Abgesichert hinter nativer `ShortcakeJni`-Krypto und einer internen (`exported="false"`) Activity, die nur aus der In-App-UI erreichbar ist, und beschränkt gänzlich auf WhatsApps eigene Wearable-/Smart-Glasses-Companion-Kategorie. Es berührt nicht das klassische ADV/CRSC-Companion-Pairing (§2-§4, das, was ein Drittanbieter-Multi-Device-Client implementiert), und es wurde kein Mechanismus gefunden, über den es einen Web-/Desktop-Companion unlinken oder im Stillen neu verlinken würde.

### 9.4 Friction / Defense Mode

`pair-device` kündigt unterstützte Challenges an und liefert bei Retry abgeschlossene (`completed`) zurück. Die Primärseite entscheidet lokal, Friction zu verlangen, wenn Defense Mode aktiv ist (`C271211x.A0N()`) und die Friction-Challenge noch nicht abgeschlossen ist; diese Entscheidung fällt vor der ersten IQ (`defense mode friction triggered`). Serverseitige Policy, die `retry-after-challenges` sendet, ist nicht sichtbar (unknown).

### 9.5 Keine Client-Attestation des Companions

Nichts im `pair-device`-Payload beweist, welche Software der Companion ausführt: `ref`, `pub-key`, Identity-Key, adv secret und Plattformzeichen sind vom QR selbst deklariert. Was die Signaturen beweisen, ist, dass dieser Primär-Account diesen Identity-Key autorisiert hat. Jede "offizieller Client"-Prüfung findet serverseitig statt (das 465-Urteil wird nur clientseitig behandelt).

### 9.6 Companion-Rolle-Code in derselben APK (kurz)

| Item | Befund |
|------|------|
| `companion_hello`-IQ-Kindknoten | `link_code_pairing_wrapped_companion_ephemeral_pub`, `companion_server_auth_key_pub`, `companion_platform_id`, `companion_platform_display`, `link_code_pairing_nonce`; Attr `should_show_push_notification` (found, `C0YS`) |
| Code | `K1T.A00` base32 von 5 zufälligen Bytes (4.3) |
| QR rotieren | IQ `pair-device-rotate-qr` mit Attr `stage` 0/1/2 und optional `sentinel`, Kindknoten `ref` |
| eingehende md-IQs | `pair-device`, `pair-success`, `ref`, `companion_reg_refresh`, `integrity` (IDs 242, 243, 266, 278, 279) |
| `pair-success`-Inhalt und Companion-`pair-device-sign`-Antwort | in diesem Build nicht nachverfolgt: unknown |

---

## 10. Baileys (`baron-baileys-v2`)

Verglichen mit dem lokalen Source; nur Übereinstimmungen und ein Unterschied, die auf beiden Seiten geprüft wurden.

| Item | APK 2.26.41.6 | `baron-baileys-v2` | Ergebnis |
|------|---------------|--------------------|--------|
| QR-Payload | `ref,noisePub,identityPub,advSecret[,platform]` | `[ref, noiseKeyB64, identityKeyB64, advB64].join(',')` (`socket.js`) | Match (4 Felder) |
| Pair-Code-Ableitung | PBKDF2-SHA256 131072 It., Alphabet `123456789ABCDEFGHJKLMNPQRSTVWXYZ` | `iterations: 2 << 16`, dasselbe Alphabet (`crypto.js`, `generics.js`) | Match |
| Key-Bundle | `[salt32 ‖ nonce12 ‖ GCM]`, info `link_code_pairing_key_bundle_encryption_key`, Plaintext identity ‖ identity ‖ random32 | gleiches Layout (`messages-recv.js`) | Match |
| adv secret | HKDF(zero salt, `eph ‖ DH(identity) ‖ random`, info `adv_secret`) | `hkdf(identityPayload, 32, {info:'adv_secret'})` | Match |
| HMAC-Wrapper | HMAC-SHA256(adv secret, [06 05 für hosted ‖] ADVSignedDeviceIdentity-Bytes) | gleich (`validate-connection.js`) | Match |
| Account-/Device-Signatur-Messages | `06 00 ‖ details ‖ companionIdentity`; `06 01 ‖ details ‖ companionIdentity ‖ accountSignatureKey` | gleich | Match |
| Hosted-Key-Index-Liste-Präfix | Verifizierer und Signierer verwenden `06 02` für jede Liste; `06 07` ist das non-E2EE-Attestation-Präfix | `WA_ADV_HOSTED_KEY_INDEX_LIST_SIG_PREFIX = [6, 7]`, verwendet wenn `accountType == HOSTED` (`chats.js`) | **weicht ab**; der Hosted-Flow wird von diesem Consumer-Build nicht ausgeführt, daher ist der Effekt des Unterschieds unknown |

Es wird keine "why it fails"-Aussage getroffen: ein Baileys-Companion, der den übereinstimmenden Zeilen folgt, ist konsistent mit dem, was die Primärseite hier parst; die Akzeptanz durch den Server ist statisch nicht verifizierbar.

---

## 11. Vollständige Abläufe

### 11.1 QR-Flow

```
[Companion]  shows QR  https://wa.me/settings/linked_devices#ref,noisePub,identityPub,advSecret[,platform]
     │
     ▼
[Primary]    scan → C45741Jxy.A02 → C45423Jrn → C44423JaU
     │       checks: -9 / -13 / -17 / -8 / -10 ; defense mode → challenges (-20)
     │       incrementCurrentKeyIndex ; ts = C24270w6.A00()
     │       details  = ADVDeviceIdentity{rawId, ts, keyIndex, accountType, deviceType}
     │       accSig   = Curve25519.sign(P.priv, 06 00 ‖ details ‖ companionIdentity)
     │       signed   = ADVSignedDeviceIdentity{details, P.pub, accSig}
     │       wrapper  = ADVSignedDeviceIdentityHMAC{signed, HMAC-SHA256(advSecret, signed)}
     │       list     = ADVSignedKeyIndexList (sig 06 02)
     │       K        = HKDF(salt = noisePub, IKM = advSecret, "Canonical Ent Companion Nonce Encrypt")
     ▼
iq set xmlns=md  <pair-device> ref, pub-key, device-identity, key-index-list ts, client-props, pem, … </pair-device>
     │
     ▼
[WA Server]   (not observed) validates, creates device jid, sends pair-device / pair-success to the companion
     │
     ▼
Result to primary: <device jid/> <companion-props/>   (or retry-ts / retry-after-challenges / retry-with-method / error 465, 496, …)
     │
     ▼
[Primary]    store CJY record, adv_timestamp_sec = list ts, start history sync
     │
     ▼
[Server → Primary]  notification devices add{device_hash, device…, key-index-list ts}  → SyncDeviceNotificationRunnable → verify (5.5)
```

### 11.2 Pair-Code-Flow

```
[Companion]  iq link_code_companion_reg stage=companion_hello
     │         wrapped_ephemeral = salt32 ‖ iv16 ‖ AES-CTR(PBKDF2(code, salt), ephPub)
     ▼
[WA Server]  → notification stage=companion_hello  → [Primary] C10J (id 252)
     │                                               store hello (ttl ≤ 360 s), push notification
     │                                               user types 8-char code
     ▼
[Primary]    unwrap companion eph pub ; make own eph pair ; eph = X25519(...)
     │         iq link_code_companion_reg stage=primary_hello
     │             wrapped_primary_ephemeral_pub, primary_identity_pub, link_code_pairing_ref
     ▼
[Companion]  eph = X25519(...) ; bundle = salt32 ‖ nonce12 ‖ GCM(HKDF(eph, salt), companionId ‖ primaryId ‖ random32)
     │         iq stage=companion_finish
     ▼
[WA Server]  → notification stage=companion_finish → [Primary] KYB
     │            decrypt, check both identities, advSecret = HKDF0(eph ‖ DH(id) ‖ random, "adv_secret")
     ▼
[Primary]    pair-device IQ (same as 11.1, pub-key = companion_server_auth_key_pub)
     ▼
(11.1 continues)
```

### 11.3 Unlink

```
[Primary UI / auto trigger]
     │   remove-companion-device jid=… reason=…     (or all="true")
     ▼
iq set xmlns=md  →  [WA Server]  →  result (optional coex_token)
     │
     ▼
[Primary]   remove local record, new key-index-list on next update (iq key-index-list ts)
[Server → other devices]  notification devices remove{…}
```
