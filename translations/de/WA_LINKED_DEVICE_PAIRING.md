<!-- src-sha1: 2c3f9604f03ccc7f3d3160d18810a86e62b8172f -->
# WhatsApp Linked-Device Pairing — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-17
**Umfang:** primärgeräteseitiges Companion-Pairing, QR-Flow, Telefonnummer-/Pair-Code-Flow, `pair-device`- und `pair-success`-Stanzas, Schlüsselmaterial, ADV-signierte Geräteidentität und Key-Index-Liste, Geräteliste und Limits, Unlink, Fehler, Vergleich mit Baileys

---

## 1. Was es ist (technisch)

Ein Linked Device (Companion) ist ein zweiter Endpunkt desselben Accounts. Das primäre Telefon autorisiert ihn, indem es eine ADV-signierte Identität (account device verification) über den Identity Key des Companions erzeugt. Alle Aussagen beruhen auf statischer Analyse der dekompilierten APK; nichts wurde auf der Leitung mitgeschnitten. Tier: **found** = im Code gelesen, **inferred** = aus dem Code abgeleitet, **unknown** = nicht aufgelöst.

Obfuskierte Namen gelten pro Build und wurden in 2.26.41.6 anhand stabiler Strings neu aufgelöst.

| Entity | Name in 2.26.41.6 | Rolle |
|--------|-------------------|-------|
| QR/Pair-Orchestrator | `C45850K0w` (Log-Präfix `CompanionDeviceQrHandler`) | parst den QR, baut ADV-Protos, sendet `pair-device` |
| `pair-device`-IQ-Builder | `RunnableC46606KYf` | baut die IQ |
| `pair-device`-Request/Response-Helper | `KRI` (`devicePairRequest/*`) | senden, Retry, Parsen von `device` / `companion-props` / Retry-Hinweisen |
| Error-Router | `C44661Jem` | bildet Server-Fehlercode auf UI-Callback ab |
| QR-String-Parser | `C45741Jxy` → `C45423Jrn` | QR-Payload zu Pairing-Daten |
| Geparste Pairing-Daten | `C44423JaU` | ref, Companion-Keys, adv secret, Plattform |
| ADV-Util | `C24270w6` (`CompanionDeviceAdvUtil`) | rawId, Key Index, Timestamp, Aufbau und Signatur der Key-Index-Liste |
| Key-Index-List-Updater | `C24250w4` (`DeviceKeyIndexListUpdateHandler`) | schiebt signierte Liste zum Server |
| ADV-Verifier | `C24230w2` (`DeviceADVInfoHandler`) | verifiziert auf der Leitung gesehene Identitäten und Listen |
| Device-List-Notification-Handler | anonyme Klasse in `C1S0` (`DeviceUpdateNotificationHandler`), `RunnableC29334CoL` | `devices`-Notification |
| Link-Code-Notification-Handler | `C10J` (`LinkCodeCompanionRegNotificationHandler`) | Notification-ID 252 |
| Link-Code-Manager (primär) | `KZ3` (Code-Eingabe, `primary_hello`), `KYB` (`companion_finish`), `C10L`, `C77` | Pair-Code-Flow |
| Link-Code-Crypto-Util | `K1T` (`CompanionRegWithLinkCodeUtil`) | HKDF, PBKDF2, base32 |
| Device-Manager | `C0XQ` (`companion-device-manager`) | Liste, Logout |
| Remove-Helper | `C28905Ch6` (`DeviceRemoveRequestProtocolHelper`) | `remove-companion-device` |
| Signal-Curve-Wrapper | `C38851hm` | `org.whispersystems.curve25519`-Provider "best" |
| ADV-Proto-Klassen | `C25815BBy`, `C25792BBb`, `C25785BAt`, `C25786BAu`, `BCB` | siehe Abschnitt 5 |
| DeviceProps | `C43105IrG` (Enum `EnumC25120ArW`) | `companion-props` im `pair-device`-Result |
| Client-Props | `C43107IrI` | `client-props`-Child |
| Account-/Verschlüsselungstyp | `EnumC32116E1o` | `E2EE` 0, `HOSTED` 1, `NON_E2EE` 2 |

In der Primär-UI gibt es drei Einstiegsmodi (`EnumC26221BZl`): `QR_CODE`, `PHONE_NUMBER_AND_CODE`, `EXTERNAL_DEEPLINK_QR_CODE` (found).

Dieselbe APK enthält auch den Registrierungscode der Companion-Rolle (State Machine `C0YS`, `companion/registration/*`-Logs). Er liegt außerhalb des Umfangs; nur die Teile, die zur Erklärung dessen nötig sind, was das Primärgerät empfängt, werden beschrieben (Abschnitt 9.6).

---

## 2. Pairing-Pfade im Überblick

| Pfad | Auslöser auf dem Primärgerät | Primärgerät sendet | Secret, das Primärgerät und Companion bindet |
|------|------------------------------|--------------------|----------------------------------------------|
| QR | Scan von `https://wa.me/settings/linked_devices#<payload>` (oder `whatsapp://settings/linked_devices#<payload>`) | `iq xmlns=md` `pair-device` | `adv secret` aus QR-Feld 4 |
| Telefonnummer + Code | `notification` `link_code_companion_reg` Stage `companion_hello`, Nutzer tippt 8-stelligen Code | `primary_hello`, später (nach `companion_finish`) dieselbe `pair-device` | `adv secret`, abgeleitet aus zwei X25519-Ergebnissen plus einem Zufallswert (Abschnitt 4.4) |

Beide Pfade münden in ein `C44423JaU`-Objekt und eine `pair-device`-IQ (found: `KYB` baut `C44423JaU` aus dem `companion_finish`-Bundle mit demselben Konstruktor, den `C45850K0w.A01` für QR verwendet).

---

## 3. QR-Flow (Primärgeräteseite)

### 3.1 QR-Payload

`C45741Jxy.A01` entfernt das Präfix `https://wa.me/settings/linked_devices#` oder `whatsapp://settings/linked_devices#` und URL-dekodiert den Rest. `A02` splittet an `,` (found):

| Idx | Inhalt | Kodierung | Verwendung |
|-----|--------|-----------|------------|
| 0 | `ref` | string | Pairing-Referenz; ein ref mit Anfang `CAPI_` wird abgelehnt (`invalid ref`) |
| 1 | Companion Public Key | base64 | als `pub-key` gesendet, Salt für den Nonce-Key (3.4). Name inferred: Noise Static Key (`companion_server_auth_key_pub` im Codepfad) |
| 2 | Companion Identity Key | base64, 32 Bytes, Parser stellt `0x05` voran (Curve25519-Typ) | von der Account-Signatur abgedeckt |
| 3 | `adv secret` | base64 | HMAC-Key für den ADV-Wrapper |
| 4 | Plattformcode (optional) | ein Zeichen | bildet auf einen Plattformtyp ab; `j` = Hosted Device |

- Weniger als 3 Teile: `qrData/processQR/error/invalid_code parts`. Fehlender Identity Key oder adv secret (alter QR mit 3 Feldern): `invalid qr code, missing companion identity key or adv secret` → lokaler Code **-9**.
- Plattform-Zeichentabelle (unabhängig von `EnumC26221BZl`, `EnumC26332BbY`): `0` UNKNOWN, `1` CHROME, `2` EDGE, `3` FIREFOX, `4` IE, `5` OPERA, `6` SAFARI, `7` DESKTOP, `8` UWP, `9` OTHER_WEB, `a` IOS_TABLET, `b` IOS_PHONE, `c` IOS_CATALYST, `d` ANDROID_TABLET, `e` ANDROID_PHONE, `f` ANDROID_AMBIGUOUS, `g` WEAR_OS, `i` AR_DEVICE, `j` HOSTED_DEVICE, `k` VR, `l` SMARTGLASSES, `n` WAIL_WAI, `o` WAIL_ALEXA (found). Sie wird nur für die Hosted-Prüfung und das Logging verwendet (3.2).

### 3.2 Lokale Prüfungen vor dem Senden

| Prüfung | Code | Lokaler Code |
|---------|------|--------------|
| QR hat Identity Key und adv secret | `C45850K0w.A01` | -9 |
| Hosted-Flag konsistent: `(accountType == HOSTED) == (platform int == 20)` | `A01` | -13 |
| anderes Pairing läuft bereits (`kri.A0N`, oder Companion-Device-Manager beschäftigt) | `A04` | -17 |
| lokaler ADV-Timestamp gültig (`C24270w6.A00() != -1`) | `A04` | -8 |
| Hosted Companion | `A04`: `Hosted pairing is not supported` | -10 |
| Defense-Mode-Friction nötig | `RunnableC46606KYf`: `defense mode friction triggered` | -20 (Retry mit Challenges) |

Hosted Pairing ist in diesem Build clientseitig blockiert (`pairing for hosted device is not supported on the consumer build`).

### 3.3 Vor der IQ: syncd-Cleanup und Key Index

1. Ist der syncd-State dirty (`sync-manager/shouldCleanUpSyncdOnPairing`), bereinigt die App zuerst syncd und fährt dann fort (`handleSyncdDirty clean syncD before companion dereg`) (found).
2. `incrementCurrentKeyIndex` (in `RunnableC46617KYr`):
   - kein gespeicherter rawId oder Index: neuer zufälliger rawId, Index 1;
   - keine Companions verknüpft: `rawId + 1`, Index bleibt 1;
   - Companions vorhanden: `currentIndex + 1`; bei Überlauf rawId + 1 und alle Geräte werden ausgeloggt (`C24270w6.A03`).
3. `ts = C24270w6.A00()` (Abschnitt 5.4).

### 3.4 Was gebaut wird

In `C45850K0w.A00`, mit `E` = Companion Identity Key (32 B, roh), `P` = Primary-Identity-Key-Pair (Curve25519), `S` = adv secret:

| Schritt | Operation | Tier |
|---------|-----------|------|
| 1 | `ADVDeviceIdentity` `{rawId, timestamp=ts, keyIndex=currentIndex, accountType, deviceType}` | found |
| 2 | Account-Signatur = `Curve25519 sign(P.priv, prefix ‖ details ‖ E)`; Präfix `06 00` (hosted `06 05`) | found |
| 3 | `ADVSignedDeviceIdentity` `{details, accountSignatureKey = P.pub, accountSignature}` (`deviceSignature` bleibt leer: der Companion ergänzt sie) | found |
| 4 | `ADVSignedDeviceIdentityHMAC` `{details = serialisierter Schritt 3, hmac = HMAC-SHA256(key = S, data = Bytes von Schritt 3), accountType}`; bei hosted sind die Daten `06 05 ‖ bytes` | found |
| 5 | `BCB` (ADVKeyIndexList) aus `C24270w6.A01`, signiert durch `A02` → `ADVSignedKeyIndexList` (5.3) | found |
| 6 | Nonce-Key `K = HKDF-SHA256(salt = pub-key, IKM = S, info = "Canonical Ent Companion Nonce Encrypt", 32 B)`, als `pem`-Child verpackt | found (Ableitung); Zweck inferred |
| 7 | optionales `encryption-metadata` (`C38898Gvq`): `encrypted_key`, `nonce`, `encrypted_data`, `auth_tag`, aus `AuthProofHelper` (Account-Passwort-Verschlüsselung, Label `rsa2048`) | found (Struktur); was es beweist ist unknown |
| 8 | optionale `client-props` (`C43107IrI`, Abschnitt 3.6) | found |

Detail zu Schritt 6: Der `pem`-Node ist mit `version=1`, `algorithm=rsa2048`, `ttl ts_s = 5 days`, `key_id=1` beschriftet, sein Child enthält aber `key.getEncoded()` der 32-Byte-HKDF-Ausgabe (`SecretKeySpec`-Algorithmus `AES-GCM`). Label und Inhalt passen nicht zusammen; warum, ist unknown. Die serverseitige Verwendung ist inferred (Server verschlüsselt einen Per-Device-Nonce an den Companion; vgl. Spalte `companion_meta_nonce`).

### 3.5 Die `pair-device`-IQ (Primärgerät → Server)

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

Found: alle Child-Namen, Wert des Attributs `ts` (der Key-Index-List-Timestamp), Timeout **32000 ms** (`c10140Tq.A0Q(…, 219, 32000L)`). `companion_qr_origin_source` ist `1` für Entry-Wert 3 und `2` für Entry-Wert 5 (Bedeutung der Entry-Ints unknown). Die genaue Child-Reihenfolge und der `companion_qr_origin_source`-Zweig sind vom Dekompiler teilweise zerstört; die Reihenfolge gilt als nicht verifiziert.

### 3.6 `client-props` (`C43107IrI`)

| Feld | Nummer | Typ | Gesetzt wenn |
|------|--------|-----|--------------|
| `isChatDbLidMigrated` | **1** | bool | LID-Migration der Chat-DB abgeschlossen |
| `isSyncdPureLidSession` | **2** | bool | syncd-Pure-LID-Flag vorhanden |
| `isSyncdSnapshotRecoveryEnabled` | **3** | bool | Recovery-Flag |
| `isHsThumbnailSyncEnabled` | **4** | bool | History-Sync-Thumbnail-Flag |
| `subscriptionSyncPayload` | **5** | bytes | gebaut, wenn md sync aktiviert (`buildSubscriptionSyncPayload`) |
| `isBotJidDbMigrated` | **6** | bool | Bot-JID-DB migriert |

### 3.7 Result-Behandlung (`KRI.CFS`)

Children des Erfolgs-Results (found):

| Child | Verwendung |
|-------|------------|
| `device` Attr `jid` | der neue Companion-`DeviceJid`; Device-ID **99** wird auf den Hosted-Plattform-Eintrag abgebildet |
| `companion-props` | `DeviceProps`-Proto (`C43105IrG`): `os` **1** (string), `version` **2** (message), `platformType` **3** (enum), `requireFullSync` **4** (bool), `historySyncConfig` **5** (message) |
| `retry-ts` Attr `ts` | Server verlangt einen neueren Timestamp; App wiederholt (`RunnableC46585KXj`) |
| `retry-after-challenges` | Children `friction` (Attr `variant`, muss `1` sein, optional `location` "lat,lon") oder `passkey-create` (Attr `created`) |
| `retry-with-method` | Children `qr-code` oder `shortcake-with-passkeys`; ist das zweite vorhanden, wird der 32-Byte-Handoff-Key (HKDF des adv secret, info `shortcake-passkey-handoff-v1`) abgelegt (`PairingHandoffKeyHolder`), per abprop gesteuert |

Bei Erfolg speichert die App den `CJY`-Geräteeintrag (zufälliger 24-Byte-base64-String, `adv_key_index` = aktueller Index, `requireFullSync`), sichert den Key-Index-List-Timestamp als `adv_timestamp_sec` (`C24270w6.A05`) und startet den History-Sync-State (`C8N`).

Zustellfehler (`Bog`): bis zu **3** Retries, Verzögerung `3000 * 3^(n-1)` ms (3 s, 9 s, 27 s), wenn das Retry-Flag an ist (found); danach Error-Callback.

---

## 4. Telefonnummer-/Pair-Code-Flow (Primärgeräteseite)

### 4.1 Schritte

| # | Richtung | Stanza / Aktion | Klasse |
|---|----------|-----------------|--------|
| 1 | Companion → Server → Primärgerät | `notification` `link_code_companion_reg`, `stage=companion_hello` | `C10J` (id 252) |
| 2 | Primärgerät | speichert Hello, zeigt Push-Notification → `CompanionHelloConfirmationActivity` / Code-Eingabe-Screen | `C10J`, `C77`, `JYJ` |
| 3 | Nutzer | tippt den 8-stelligen Code | `LinkedDevicesEnterCodeActivity` |
| 4 | Primärgerät → Server | `iq xmlns=md type=set` `link_code_companion_reg stage=primary_hello` | `KZ3` (Timeout 120000 ms) |
| 5 | Server → Primärgerät | `notification` `stage=companion_finish` | `C10J` → `KYB` case 0 |
| 6 | Primärgerät → Server | `pair-device`-IQ (Abschnitt 3.5) | `C45850K0w` |
| 7 | andere Stages | `refresh_code` (Primärgerät fordert Code-Refresh an, Attr `force_manual_refresh`) | `C10J` |

### 4.2 `companion_hello`-Notification (found)

| Child | Verwendung |
|-------|------------|
| `link_code_pairing_wrapped_companion_ephemeral_pub` | ephemerer X25519-Key des Companions, mit dem Code verpackt (4.3) |
| `companion_server_auth_key_pub` | wird später zum `pub-key` in `pair-device` |
| `link_code_pairing_ref` | Session-Ref (string) |
| `companion_platform_id` | Plattform-ID-String |
| `companion_platform_display` | Anzeigename |
| Attr `should_show_push_notification` | `true` → Push-Notification |

Gehaltener State (`C77`/`CE4`, SharedPrefs-JSON `companion_reg_with_link_code_companion_hello_info_json`): ref, Plattform-ID, Wrapped Key, Server Auth Key, Ablauf `now + min(360000, flag 3816 * 1000)` ms. Abgelaufenes oder fehlendes Hello → "companion hello is null or expired" (UI-State 2). Ein neueres Hello mit anderem ref bricht den vorherigen ref ab (`KRJ.A00(oldRef, "true")`).

### 4.3 Code- und Wrap-Crypto (found)

| Element | Wert |
|---------|------|
| Code | 5 Zufallsbytes → 8 Zeichen, je 5 Bit, Alphabet `123456789ABCDEFGHJKLMNPQRSTVWXYZ` (32 Symbole, ohne `0 I O U`) (`K1T.A00`, vom Companion erzeugt) |
| Code → Key | PBKDF2-HMAC-SHA256, **131072** Iterationen, 256 Bit, Passwort = Code-Zeichen, Salt = erste 32 Bytes des Wrapped Blobs (`K1T.A02`) |
| Wrapped Ephemeral Key | `[salt 32 ‖ IV 16 ‖ AES-256-CTR ciphertext]`, Plaintext = 32-Byte-X25519-Public-Key; Länge muss ≥ 48 sein |
| Antwort des Primärgeräts | das Primärgerät erzeugt ein eigenes ephemeres Key-Pair und verpackt seinen Public Key genauso (frischer 32-B-Salt, 16-B-IV, gleicher Code) |

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

Children der `companion_finish`-Notification: `link_code_pairing_wrapped_key_bundle`, `companion_identity_public`, `link_code_pairing_ref`. Verarbeitung auf dem Primärgerät in `KYB` case 0:

1. `eph = X25519(primary eph priv, companion eph pub)` (zum Zeitpunkt von `primary_hello` gespeichert).
2. Bundle-Layout `[salt 32 ‖ nonce 12 ‖ AES-256-GCM ciphertext+tag]`, mindestens 44 Bytes.
3. Key = HKDF-SHA256(salt = Bundle-Salt, IKM = `eph`, info = `link_code_pairing_key_bundle_encryption_key`, 32 B).
4. Plaintext = `companion identity pub (32) ‖ primary identity pub (32) ‖ random (32)`.
5. Prüfungen: Primary Identity muss dem eigenen Identity Key entsprechen; Companion Identity muss `companion_identity_public` aus der Notification entsprechen; andernfalls wird der ref verworfen und die UI erhält einen Fehlerzustand.
6. `adv secret = HKDF-SHA256(salt = 32 Nullbytes, IKM = eph ‖ X25519(primary identity priv, companion identity pub) ‖ random, info = "adv_secret", 32 B)` (`K1T.A03`).
7. Handoff-Key = HKDF(adv secret, info `shortcake-passkey-handoff-v1`) (ebenfalls in `C44423JaU` gespeichert).
8. `C44423JaU` wird mit `pub-key` = `companion_server_auth_key_pub`, Companion Identity, adv secret gebaut → dieselbe `pair-device`-IQ wie bei QR.

Das äußere ephemere ECDH existiert (es ist das HKDF-IKM in Schritt 3). Eine Notiz aus einem früheren Build lautete "kein ECDH in dieser Stage"; das ist für diesen Build falsch.

Fehlermarker auf der Primärgeräteseite: `getCompanionPairingDataOnCompanionFinish ref not exists`, `decryption fail`, `primary identity doesn't match`, `companion identity doesn't match`, `invalid linkCodePairingWrappedKeyBundleDecrypted` (found).

---

## 5. ADV-signierte Geräteidentität

### 5.1 Proto-Felder (found, aus den Lite-Proto-Layout-Strings)

| Message | Klasse | Feld | Nummer | Typ |
|---------|--------|------|--------|-----|
| `ADVDeviceIdentity` | `C25815BBy` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `keyIndex` | **3** | uint32 |
| | | `accountType` | **4** | enum (`EnumC32116E1o`) |
| | | `deviceType` | **5** | enum (`EnumC32116E1o`) |
| `ADVSignedDeviceIdentity` | `C25792BBb` | `details` | **1** | bytes |
| | | `accountSignatureKey` | **2** | bytes |
| | | `accountSignature` | **3** | bytes |
| | | `deviceSignature` | **4** | bytes (vom Companion gesetzt) |
| `ADVSignedDeviceIdentityHMAC` | `C25785BAt` | `details` | **1** | bytes |
| | | `hmac` | **2** | bytes |
| | | `accountType` | **3** | enum |
| `ADVKeyIndexList` | `BCB` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `currentIndex` | **3** | uint32 |
| | | `validIndexes` | **4** | packed uint32 |
| | | `accountType` | **5** | enum |
| `ADVSignedKeyIndexList` | `C25786BAu` | `details` | **1** | bytes |
| | | `accountSignature` | **2** | bytes |
| | | `accountSignatureKey` | **3** | bytes (nur hosted) |

Feldnummern und Wire Types stammen aus der generierten Message-Info; die Namen stimmen mit den kanonischen ADV-Messages überein. Enum-Namen: `EnumC32116E1o`-Werte E2EE 0, HOSTED 1, NON_E2EE 2.

### 5.2 Signaturpräfixe und Algorithmen

| Präfix | Konstante | Signierte / MAC-geschützte Daten | Signierer | Tier |
|--------|-----------|---------------------------|-----------|------|
| `06 00` | `AbstractC051108f.A0F` | Account-Signatur: `‖ details ‖ companion identity pub` | Primary Identity Key | found |
| `06 05` | `A0G` | Hosted-Variante der Account-Signatur; bei hosted auch den HMAC-Daten vorangestellt | Primary Identity Key / adv secret | found |
| `06 01` | `A0H` | Geräte-Signatur: `‖ details ‖ companion identity pub ‖ accountSignatureKey` | Companion Identity Key | found (Verify-Seite) |
| `06 06` | `A0I` | Hosted-Variante der Geräte-Signatur | Companion Identity Key | found (Verify-Seite) |
| `06 02` | `A0J` | `ADVSignedKeyIndexList`: `‖ details` | Primary Identity Key | found |
| `06 07` | `A0K` | Non-E2EE-("hybrid")-Attestation (`AeaUtils`), kein Key-Index-List-Präfix | Primary Identity Key | found |

- Signatur-Primitive: `C38851hm.A00("best")` lädt `org.whispersystems.curve25519.OpportunisticCurve25519Provider`; `A03` = `calculateSignature(random 64 B, priv, msg)`, `A01` = `verifySignature` (64-Byte-Signatur), `A02` = `calculateAgreement`. Keys sind 32 Bytes mit Typ-Byte `5`. Es sind also Curve25519-Signaturen der Signal-curve25519-Bibliothek (XEdDSA-artig, inferred aus der Bibliothek, nicht aus dem Algorithmusnamen). Die Provider-Wahl nativ vs. Java wird zur Laufzeit entschieden (unknown, welcher auf einem gegebenen Gerät genutzt wird).
- HMAC: `HmacSHA256` über `javax.crypto.Mac` (`AbstractC38971i1.A00`).

### 5.3 Key-Index-Liste

`C24270w6.A01` baut `ADVKeyIndexList`; `validIndexes` ist ein Set aus (found): einem Eintrag für den Primär-Slot (Wert 0, wenn nicht im Companion-Modus; Verzweigungsbedingung inferred), dem `adv_key_index` jedes gespeicherten Companions (`CJY.A07`) und `currentIndex`. `A02` signiert `06 02 ‖ details`.

`C24250w4.A00` schiebt sie so:

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
</iq>
```

Timeout 32000 ms. Gate `A02`: Flag **477** ungleich null, Companions vorhanden (oder Companion-Modus), nicht im Companion-Modus. Bei Fehlschlag wird `adv_key_index_list_update_retry_count` erhöht; über **5** loggt die App `adv-key-index-list-update … fails for more than 5 times` und loggt alle Companions aus (`C24270w6.A03`). Erfolg setzt die Zähler zurück (`A05`).

### 5.4 Timestamp-Regel (`C24270w6.A00`)

`last` = SharedPrefs `adv_timestamp_sec`; `now` = NTP-korrigierte Uhr, `srv` = Serverzeit. `ts = max(srv if |srv - now| <= 86400 else now, last + 1)`. Ist `last + 1 > now + 86400`, ist der Wert ungültig (-1, geloggt `getTimestampSec invalid ts`), was das Pairing mit lokalem Code -8 blockiert. Pro Account monoton (found).

### 5.5 Verifikation auf der Leitung (`C24230w2`)

Für jede Geräteidentität, die das Primärgerät sieht (eigene und die Companions von Kontakten), prüft es der Reihe nach (found):

1. Primary Identity Key bekannt (gespeichert oder `accountSignatureKey` aus der Liste), sonst `no primary key`;
2. Companion Identity Key lässt sich parsen (`0x05`+32 B), sonst `invalid companion public key`;
3. Account-Signatur über `prefix ‖ details ‖ companion identity`, sonst `fail to verify account signature`;
4. Geräte-Signatur über `06 01 ‖ details ‖ companion identity ‖ accountSignatureKey` (hosted `06 06`), sonst wird das Gerät abgelehnt;
5. Key-Index-Liste: Signatur über `06 02 ‖ details` mit dem Primary Key; der `adv timestamp` der Liste muss konsistent sein (`advTimestampMismatch`, `advListTimestampInvalid`); ein nicht passender eingehender Key Index setzt den lokalen State zurück (`incoming key-index not matching local state, resetting`); ein größerer Index für dasselbe, bereits vorhandene Gerät verwirft den älteren Eintrag (`filterDeviceWithKeyIndexList`).

---

## 6. Geräteliste, Eintrag und Limits

### 6.1 `devices`-Notification (Primärgerät empfängt)

`notification` mit Child `add` oder `remove` (alles andere: `unknown type of device notification`). Attribute und Children (found): `device_hash`, optional `device_lid_hash` plus `lid`, `device`-Einträge (jid, Key Index), optional `key-index-list` (bytes, Attr `ts`, `expected_ts`). Trägt die Notification das Attr `offline`, wird der Nutzer für späteren Sync eingereiht; andernfalls läuft ein Sync-Job (`SyncDeviceNotificationRunnable`). Die Liste wird nur akzeptiert, wenn ihr Timestamp nicht älter ist als der gespeicherte `adv_timestamp_sec` (sonst `local ts is larger than notification one`).

### 6.2 Gespeicherter Geräteeintrag (Tabelle `devices`, `C1h8`)

| Gruppe | Spalten (found) |
|--------|-----------------|
| Identity | `device_id`, `platform_type`, `device_os`, `adv_key_index`, `companion_meta_nonce`, `instrumentation_device_id`, `nickname`, `place_name` |
| Time | `last_active`, `login_time`, `logout_time` |
| Sync | `full_sync_required`, `full_sync_days_limit`, `full_sync_size_mb_limit`, `recent_sync_days_limit`, `storage_quota_mb`, `inline_initial_hist_sync_payload_enabled`, `history_sync_config_protobuf`, `history_sync_access_type`, `on_demand_ready` |
| Capability | `support_hosted_group_msg`, `support_biz_hosted_msg`, `support_group_history`, `support_call_log_history`, `support_message_association`, `support_add_on_history_sync_migration`, `support_guest_chat`, `support_bot_user_agent_chat_history`, `support_fbid_bot_chat_history`, `support_manus_history`, `support_hatch_history`, `support_cag_reactions_and_polls_history`, `support_recent_sync_chunk_message_tuning`, `supported_bot_channel_fbids` |

Die Werte von `platform_type` stammen aus `companion-props.platformType` (`EnumC25120ArW`): 0 UNKNOWN, 1 CHROME, 2 FIREFOX, 3 IE, 4 OPERA, 5 SAFARI, 6 EDGE, 7 DESKTOP, 8 IPAD, 9 ANDROID_TABLET, 10 OHANA, 11 ALOHA, 12 CATALINA, 13 TCL_TV, 14 IOS_PHONE, 15 IOS_CATALYST, 16 ANDROID_PHONE, 17 ANDROID_AMBIGUOUS, 18 WEAR_OS, 19 AR_WRIST, 20 AR_DEVICE, 21 UWP, 22 VR, 23 CLOUD_API, 24 SMARTGLASSES, 25 WAIL, 26 WASS, 27 BUSINESS_BACK_OFFICE, 28 WAIL_WAI, 29 WAIL_ALEXA, 30 AUTOMOTIVE (found).

### 6.3 Limits und Flags

| Flag / Element | Bedeutung | Tier |
|----------------|-----------|------|
| **15550** | Integer: maximale Anzahl verknüpfter Geräte (`LinkedDevicesSharedViewModel.hasMaxDeviceLimitReached`: `loggedInDeviceCount >= max` blockiert "Gerät verknüpfen"; der QR-Scanner erhält das Extra `at_device_limit`; `OrbitCompanionLinkActivity` lehnt ab, wenn erreicht) | found (Verwendung); Standardwert unknown (vom Server gelieferter abprop); das Metrikfeld `md_linked_devices_max_devices_limit` existiert |
| **3816** | Sekunden, die das `companion_hello` gültig bleibt, gedeckelt auf 360 s | found |
| **477** | Gate (ungleich null) für Key-Index-List-Updates | found |
| **18193** | fügt `friction` (variant 1) zu den beworbenen `challenges/supported` hinzu | found (Verwendung); Wirkung auf dem Server unknown |
| **28161** | fügt die zweite beworbene Challenge (`passkey-create`) hinzu | inferred Zuordnung (Dekompiler hat den Zweig verloren) |
| **29500** | Hosted-Pairing-Gate in der Defense-Mode-Prüfung | found (gelesen), Bedeutung inferred |
| **31019** | fügt Attr `exclude_hosted_companion=true` zu remove-all aus bestimmten Gründen hinzu | found |

Ob der Server das Limit unabhängig von der Client-Prüfung durchsetzt, ist unknown. Das Primärgerät hat im hier gelesenen Code kein clientseitiges Inaktivitäts-Timeout für Companions; ein serverseitiger Ablauf inaktiver Companions ist unknown.

---

## 7. Unlink (Primärgeräteseite)

### 7.1 Einzelnes Gerät

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <remove-companion-device jid="user:device@…" reason="user_initiated"/>
</iq>
```

`C28905Ch6.A00`, Timeout 32000 ms. Das Result kann das Child `coex_token` tragen (an den Coexistence-Handler übergeben). Zustellfehler oder Fehler rufen den Failure-Callback mit Code -1 auf (found).

### 7.2 Alle Geräte

`C0XQ.A0Y(reason, removeOnError, isEncryptionTypeTransitioning)`:

```xml
<remove-companion-device all="true" reason="…" [exclude_hosted_companion="true"]/>
```

Eine leere lokale Liste springt direkt zum Success-Callback. Im Code gesehene Reason-Strings: `user_initiated`, `unknown_companion`, `invalid_adv_status`, `lid_migration_peer_sync_limit_exceeded`, `lid_migration_peer_sync_message_failed`, `lid_migration_missing_mappings_in_peer_sync_message` (found; die Liste kann länger sein, der Quellausdruck ist abgeschnitten).

### 7.3 Automatische Unlink-Auslöser (found)

| Auslöser | Reason |
|----------|--------|
| Key-Index-List-Update mehr als 5-mal fehlgeschlagen | `adv-key-index-list-update`, alle ausloggen |
| Key-Index-Überlauf | `A03` Reset |
| ungültiger ADV-Status / unbekannter Companion (`KZD` case 43) | `invalid_adv_status` |
| Hosted ↔ E2EE-Account-Typ-Übergang | wirft alle Geräte raus (`handleADVMetadata`-Log) |
| Server sendet `devices`-Notification vom Typ `remove` | lokaler Eintrag entfernt (inferred) |
| Nutzeraktion im Linked-Devices-Screen / `EavesdropMonitor/disconnectDevice` | `user_initiated` (found für den Monitor; UI-Pfad inferred) |

Die Entfernung des gesamten Accounts (`urn:xmpp:whatsapp:account` `remove`) ist eine andere IQ und hat mit dem Companion-Unlink nichts zu tun.

---

## 8. Fehlerfälle

### 8.1 Vom `C44661Jem.A01` behandelte Server-Codes

| Code | Callback | UI | Tier |
|------|----------|----|------|
| **465** | `Blp` → `onCompanionPlatformRestricted` | `CompanionPlatformRestrictedBottomSheet` | found |
| **496** | `Blv` → `onCompanionTooOld` | Zustand "companion too old" | found |
| 404 / 405 / 443 / 445 | generisch `C2w` | String-Zuordnung `C44648JeY`: 405 und 443 haben eigene Texte; 404/405/443/445 teilen einen Titel | found (Strings per ID); genaue Bedeutung von 404/443/445 unknown |
| andere | generisch `C2w` | Pairing fehlgeschlagen | found |

`InstrumentationAuthActivity` benennt Result-Codes 1 `CONSUMER_SMB_CROSS_PAIRING`, 2 `UNSUPPORTED_PRIMARY_VERSION`, 3 `INVALID_QR_CODE`, 4 `COMPANION_PLATFORM_RESTRICTED`, 5 `COMPANION_TOO_OLD`, 6 `MAX_DEVICE_LIMIT_REACHED`, sonst `PAIRING_FAILED` (found). Die Zuordnung von Server-405 zum Consumer/SMB-Fall ist aus der String-ID inferred.

### 8.2 Lokale Codes

| Code | Ursache | Behebung |
|------|---------|----------|
| -8 | lokaler ADV-Timestamp ungültig (Uhr vs. zuletzt gespeicherter ts + 1) | Gerätezeit korrigieren; UI-String "invalid device time" |
| -9 | QR ohne Identity Key / adv secret | aktuellen QR verwenden |
| -10 | Hosted Pairing im Consumer-Build | n/a |
| -13 | Plattform passt nicht zum Hosted-Flag | n/a |
| -17 | anderes Pairing läuft | warten; Request lebt bis zu 32 s |
| -20 | Server verlangte Challenges (`retry-after-challenges`) | Friction-/Passkey-Challenge abschließen |
| -1 | Remove-Request nicht gesendet oder fehlgeschlagen | wiederholen |

### 8.3 Link-Code-Fehler

| Symptom (Log) | Ursache |
|---------------|---------|
| `companion hello is null or expired` | Code nach Ablauf eingegeben (Flag 3816, max. 360 s) |
| `decryption fail` (hello) | falscher Code (PBKDF2-Key weicht ab; AES-CTR hat kein Tag, ein falscher Code liefert also einen Müll-Key, der in späteren Schritten auffällt; inferred) |
| `primary identity doesn't match` | Bundle wurde für einen anderen Primary Key gebaut |
| `companion identity doesn't match` | Notification und Bundle widersprechen sich |
| `invalid-primary-adv-key-length` / `adv public key is 0` | Companion-Rollen-Prüfungen auf den ephemeren Primary Key |

---

## 9. Wichtige Unterscheidungen

### 9.1 Nicht verwechseln

| A | B |
|---|---|
| `pair-device`, vom **Primärgerät** gesendet (dieser Report) | `pair-device`, von einer App in Companion-Rolle **empfangen** (Handler `AbstractC40501kw`, id 242, trägt Refs für den QR) |
| `ADVSignedDeviceIdentity` (signiert, kein HMAC) | `ADVSignedDeviceIdentityHMAC` (der Wrapper, der in `device-identity` gesendet wird) |
| `device-identity`-Child von `pair-device` (HMAC-Wrapper) | `device-identity`-Child in ausgehenden Message-Stanzas (von einem Companion angehängte Account-Identität; Pref `adv_signed_identity`) |
| Account-Signatur (Primary Key, Präfix `06 00`) | Geräte-Signatur (Companion Key, Präfix `06 01`) |
| Key-Index-List-Präfix `06 02` | `06 07` (Non-E2EE-Attestation) |
| QR-`pub-key` / `companion_server_auth_key_pub` | Companion Identity Key (der, der die Account-Signatur erhält) |
| `rawId` (accountweite ID, die sich bei Reset ändert) | `keyIndex` (pro Companion) |
| QR-Plattformzeichen (`EnumC26332BbY`) | Wire-`DeviceProps.platformType` (`EnumC25120ArW`), andere Nummerierung |

### 9.2 Hosted Device

JID-Device-ID **99** (`device_id should be 99 for hosted device`), Registrierungs-/Unpair-Marker `hosted_device_pairing`, Signaturpräfixe `06 05` / `06 06`, `exclude_hosted_companion`. Das Primärgerät weigert sich in diesem Build, ein Hosted Device zu pairen (lokal -10). Alles darüber Hinausgehende ist unknown.

### 9.3 Shortcake

`retry-with-method` kann `shortcake-with-passkeys` auflisten; die App legt dann einen Handoff-Key ab und wechselt die UI. `ShortcakeJni` stellt `nativeMlkem768GenerateKeypair/Encapsulate/Decapsulate` und `nativeResponderStart/Finish` bereit (found). Das Handshake-Transcript ist nativ und wurde hier nicht dekompiliert: unknown.

### 9.4 Friction / Defense Mode

`pair-device` bewirbt unterstützte Challenges und liefert beim Retry `completed`-Challenges zurück. Das Primärgerät entscheidet lokal, Friction zu verlangen, wenn der Defense Mode an ist (`C271211x.A0N()`) und die Friction-Challenge noch nicht abgeschlossen ist; diese Entscheidung fällt vor der ersten IQ (`defense mode friction triggered`). Die serverseitige Policy, die `retry-after-challenges` sendet, ist nicht sichtbar (unknown).

### 9.5 Keine Client-Attestation des Companions

Nichts in der pair-device-Payload beweist, welche Software der Companion ausführt: `ref`, `pub-key`, Identity Key, adv secret und Plattformzeichen werden vom QR selbst deklariert. Was die Signaturen beweisen, ist, dass dieser Primär-Account genau diesen Identity Key autorisiert hat. Jede "Official Client"-Prüfung liegt serverseitig (das 465-Verdikt wird nur clientseitig behandelt).

### 9.6 Companion-Rollen-Code in derselben APK (kurz)

| Element | Befund |
|---------|--------|
| `companion_hello`-IQ-Children | `link_code_pairing_wrapped_companion_ephemeral_pub`, `companion_server_auth_key_pub`, `companion_platform_id`, `companion_platform_display`, `link_code_pairing_nonce`; Attr `should_show_push_notification` (found, `C0YS`) |
| Code | `K1T.A00` base32 von 5 Zufallsbytes (4.3) |
| QR rotieren | IQ `pair-device-rotate-qr` mit Attrs `stage` 0/1/2 und optional `sentinel`, Child `ref` |
| eingehende md-IQs | `pair-device`, `pair-success`, `ref`, `companion_reg_refresh`, `integrity` (ids 242, 243, 266, 278, 279) |
| Inhalt von `pair-success` und Companion-Antwort `pair-device-sign` | in diesem Build nicht verfolgt: unknown |

---

## 10. Baileys (`baron-baileys-v2`)

Verglichen mit dem lokalen Source; nur Übereinstimmungen und ein Unterschied, die auf beiden Seiten geprüft wurden.

| Element | APK 2.26.41.6 | `baron-baileys-v2` | Ergebnis |
|---------|---------------|--------------------|----------|
| QR-Payload | `ref,noisePub,identityPub,advSecret[,platform]` | `[ref, noiseKeyB64, identityKeyB64, advB64].join(',')` (`socket.js`) | match (4 Felder) |
| Pair-Code-Ableitung | PBKDF2-SHA256 131072 it., Alphabet `123456789ABCDEFGHJKLMNPQRSTVWXYZ` | `iterations: 2 << 16`, gleiches Alphabet (`crypto.js`, `generics.js`) | match |
| Key Bundle | `[salt32 ‖ nonce12 ‖ GCM]`, info `link_code_pairing_key_bundle_encryption_key`, Plaintext identity ‖ identity ‖ random32 | gleiches Layout (`messages-recv.js`) | match |
| adv secret | HKDF(zero salt, `eph ‖ DH(identity) ‖ random`, info `adv_secret`) | `hkdf(identityPayload, 32, {info:'adv_secret'})` | match |
| HMAC-Wrapper | HMAC-SHA256(adv secret, [06 05 bei hosted ‖] ADVSignedDeviceIdentity-Bytes) | gleich (`validate-connection.js`) | match |
| Account-/Geräte-Signatur-Messages | `06 00 ‖ details ‖ companionIdentity`; `06 01 ‖ details ‖ companionIdentity ‖ accountSignatureKey` | gleich | match |
| Hosted-Key-Index-List-Präfix | Verifier und Signierer verwenden `06 02` für jede Liste; `06 07` ist das Non-E2EE-Attestationspräfix | `WA_ADV_HOSTED_KEY_INDEX_LIST_SIG_PREFIX = [6, 7]`, verwendet bei `accountType == HOSTED` (`chats.js`) | **abweichend**; der Hosted-Flow wird von diesem Consumer-Build nicht ausgeübt, daher ist die Wirkung des Unterschieds unknown |

Es wird keine "Warum es scheitert"-Aussage getroffen: Ein Baileys-Companion, der den übereinstimmenden Zeilen folgt, ist konsistent mit dem, was das Primärgerät hier parst; die Akzeptanz durch den Server ist statisch nicht überprüfbar.

---

## 11. Vollständige Flows

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
