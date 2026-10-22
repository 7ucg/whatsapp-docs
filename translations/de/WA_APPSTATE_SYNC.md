<!-- src-sha1: f9c1d644c604d99d2f1b54082218c3f75d2cf8a7 -->
# WhatsApp App-State Sync — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** App-State-Sync (syncd) unter Android: fünf Collections, `w:sync:app:state`-IQ, Patches / Snapshots / externe Blobs, SET/REMOVE-Mutationen, Ableitung der Mutation Keys und Record-Verschlüsselung, Index- / Value-MACs, LT-Hash, Snapshot- und Patch-MACs, Sync Keys (Erzeugung, Share, Request, Ablauf), ausgehende und eingehende Validierung, Sync-Action-Katalog (96 Actions: chat, label, contact, nctSalt …), Fatal- und Retry-Behandlung, Snapshot Recovery, Feature-Flags, Baileys-Vergleich

---

## 1. Was es ist (technisch)

App-State-Sync repliziert kleinen kontobezogenen Zustand (Mute, Pin, Archive, Star, Kontakte, Labels, Einstellungen …) zwischen dem primären Telefon und jedem verknüpften Gerät. Der Server speichert nur Ende-zu-Ende-verschlüsselte Records, ordnet sie pro Collection und liefert versionierte Patches aus. Alle Aussagen beruhen auf statischer Analyse des dekompilierten APK; nichts wurde auf der Leitung mitgeschnitten. Tier: **found** = im Code gelesen, **inferred** = aus dem Code abgeleitet, **unknown** = nicht aufgelöst. Obfuskierte Namen wurden in 2.26.41.6 anhand stabiler Strings neu aufgelöst (`WhatsApp Mutation Keys`, `WhatsApp Patch Integrity`, `w:sync:app:state`, Collection-Namen, Log-Präfixe).

| Entität | Name in 2.26.41.6 | Rolle |
|--------|----------------|------|
| Sync-Manager | `C12440bB` (`sync-manager/*`) | Scheduling, `A0S` Fatal-Fehler, `A0Q` Delete-all-Data |
| Request-Handler / IQ-Builder / Parser | `C53148Nnt` / `C46361ux` / `N90` | IQ senden, `<sync>` bauen, Result parsen |
| Legacy-Response-Handler | `SyncResponseHandler` (`consumer/companiondevice/p049iq`) | Legacy-Apply-Pfad, `A08` Fatal-Behandlung |
| KMP-Engine | `com.whatsapp.kmp.syncd.syncdengine.*` | `OutgoingProcessor`, `IncomingProcessor`, `SyncdResponseHandler`, `SyncdResponseProcessor`, `CollectionHandler`, `crypto/*` |
| Collection-Enum / Action-Enum | `EnumC24862AnK` / `EnumC24865AnN` | 5 Collections / 96 Action-Wire-Namen |
| Action zu Collection | `AbstractC24863AnL.A00` | Ordinal-Switch |
| Mutation-Basis / Handler-Basis | `AbstractC24864AnM` / `AbstractC25077Aqp` | ausstehende Mutation / Action-Handler |
| Key-Manager / Store | `C12800bm` (`SyncdKeyManager`) / `C13620d6` (Tabelle `crypto_info`) | Keys erzeugen, teilen, anfordern, ablaufen lassen, persistieren |
| Key-ID / Key / Key-Daten | `CGH` / `C51259MoT` / `C51361MqC` | 6-Byte-ID / ID + Daten / Daten, `C8H`-Fingerprint, ts |
| Mutation Keys | `MhX` | HKDF-Ausgabe, 5 Slices |
| Share- / Request-Träger | `C26102BPk` (FMessage 38) / `C26101BPj` (39) | Peer-Nachrichten |
| LT-Hash, HKDF | `AbstractC50511MVx.A00` + `KmpLtHash16`, `AbstractC38961i0` | 128-Byte-Hash, RFC 5869 |
| Crypto (Legacy / KMP) | `C52959NkE` / `KmpSyncdCryptoHelper`, `KmpSyncdEncryptor`, `KmpSyncdDecryptor`, `KmpSyncdIncomingAntiTamperingValidator` | identische Formeln |
| Externe Blobs | `C17650kB` (Download), `KmpExternalMutationsUploaderImpl` | MMS-Typ `md-app-state` |
| Bootstrap / Delete-all / Recovery | `C24986ApL` / `C17630k8` / `KmpSyncdFatalErrorRecovery` | Zustandsautomat, `delete_all_data`, Snapshot-Auslieferung |
| Fatal-Kinds / Legacy-Exception | `Lx6` / `C49784Lv2` | 70 benannte Kinds / int `errorCode` |

Zwei Implementierungen desselben Protokolls existieren nebeneinander. Die KMP-Engine wird über drei serverseitig gesteuerte Booleans ausgewählt, deren einkompilierte Defaults **false** sind (**15909** Crypto, **20682** Incoming, **18234** Outgoing, Abschnitt 12). Welchen Pfad ein Konto nutzt, ist unknown. MAC- und Verschlüsselungsformeln sind in beiden identisch (verglichen in `C52959NkE` und `KmpSyncd*`).

Primary und Companion führen denselben Code aus. Gefundene Unterschiede: nur ein Primary erzeugt `contact`- / `lid_contact`-Mutationen (`Companion cannot create contact mutations`); nur ein Companion sendet `return_snapshot="true"`; die Fatal-Behandlung unterscheidet sich (11.3).

---

## 2. Collections

| Wire-Name | Enum-Ordinal | Critical | Log-Bit (`C17530jy.A00`) | Actions |
|-----------|--------------|----------|--------------------------|---------|
| `regular` | 0 | nein | 3 | 35 |
| `regular_low` | 1 | nein | 5 | 36 |
| `regular_high` | 2 | nein | 4 | 19 |
| `critical_block` | 3 | ja | 1 | 4 |
| `critical_unblock_low` | 4 | ja | 2 | 2 |

Critical-Menge = `{critical_block, critical_unblock_low}` (`EnumC24862AnK.A01`). `A00()` bildet das Ordinal auf 1..5 ab; Consumer nicht nachverfolgt.

Unter Android enthält `critical_block` Account-Setting-Actions (`setting_pushName`, `setting_locale`, `setting_securityNotification`, `generated_wui`), **keine** Blockliste; `contact` und `lid_contact` liegen in `critical_unblock_low`. Keine Action im 96-Einträge-Enum ist nach Blockieren benannt (found).

**Bootstrap (Companion, teilweise inferred).** `syncd_bootstrap_state` (`C24986ApL`) läuft von 0 bis 4. Found: Critical-Menge synchronisiert → Zustand 2 und ein Signal „critical blocking complete"; alle nicht-kritischen Collections synchronisiert → Zustand 4; Zustand 3 ist der History-Sync-Schritt (inferred). Fehlergründe: `critical_sync_timeout`, `history_sync_failure`, `syncd_failure`; Watchdog-Log `syncd-critical-bootstrap-timeout`. Auf dem Primary startet das Pairing eines Companions `prepareCriticalDataUpload`: History-Sync, dann `shareAllKeys`; ohne Key und mit Flag **27528** wird zuerst ein Key erzeugt.

---

## 3. IQ-Schicht

### 3.1 Request (found, `C46361ux`)

```xml
<iq to="s.whatsapp.net" xmlns="w:sync:app:state" type="set" id="…">
  <sync data_namespace="3">
    <collection name="regular_low" order="1" version="41" return_snapshot="true">
      <patch>…SyncdPatch bytes…</patch>
    </collection>
  </sync>
  <coex><bot>…enc node…</bot></coex>      <!-- optional -->
</iq>
```

| Attribut | Wert |
|-----------|-------|
| `data_namespace` | Konstante `3` auf `<sync>` |
| `order` | `0` für `critical_unblock_low`, sonst `1`; Bedeutung unknown |
| `version` | lokal gespeicherte Collection-Version (`C17540jz.A02`); entfällt, wenn keine vorhanden |
| `return_snapshot` | `"true"` nur für einen Companion mit Version null oder 0 |
| `<patch>` | nur wenn lokale Mutationen ausstehen |
| `<coex><bot>` | Coexistence-v2: die verwendeten Sync Keys werden an einen Bot verschlüsselt (`sync-request-handler/coexv2 *`); bei Fehler geht die IQ ohne diesen Teil raus und die Keys werden out-of-band geteilt |

Timeout 32 s; eine IQ kann mehrere Collections tragen.

### 3.2 Result (found, `N90`)

```xml
<iq type="result"><sync>
  <collection name="X" type="error"><error code="409" text="…"/> [<patches>…]</collection>
  <collection name="X" version="42"/>                    <!-- outgoing patch acked -->
  <collection name="X" has_more_patches="true">
    <snapshot>ExternalBlobReference bytes</snapshot>    <!-- companion bootstrap -->
    <patches><patch>SyncdPatch bytes</patch>…</patches>
  </collection>
</sync></iq>
```

Fehlendes `<sync>` oder ein leerer `<snapshot>`- / `<patch>`-Body → transienter Fehler. Eine Collection ohne Version, Patches und Snapshot bleibt als bloßer Name erhalten (Bedeutung inferred: nichts Neues). Snapshot-Bodies sind immer eine `ExternalBlobReference`, nie Inline-Records.

Collection-Fehler (`M4T`): -1 `UNKNOWN` wiederholbar; 400 / 404 / 405 / 406 fatal (`Xmpp*ForCollection`); 409 `CONFLICT` angehängte Patches anwenden, dann Retry, sonst wiederholbar (Verzweigungsbedingung im Decompilat mehrdeutig); 500 wiederholbar.

Globaler IQ-Fehler (`C53148Nnt.Brt`, `backoff` in Sekunden):

| Code | Behandlung |
|------|----------|
| 400, 404, 405, 406 | fatal; Legacy-Codes 64, 65, 66, 67; KMP-Kinds 55-58 |
| sonstige 4xx | kein Retry, `client_error:<code>` |
| 5xx | Retry nach `max(server backoff, client delay)`, `server_error:<code>` |
| sonstige | `global_error:<code>` |

Transiente Fehler, die älter als 7 Tage sind (`first_transient_server_failure_timestamp` > 604 800 000 ms), eskalieren zu fatal. Weitere nicht-fatale Gründe: `network_error`, `sqlite_full`, `unexpected_error`, `mms_local_io`, `mms_upload`.

---

## 4. Protobuf-Nachrichten

Die Nummern stammen aus den Klassen von 2.26.41.6, geprüft gegen die Deklarationsreihenfolge und, wo vorhanden, gegen generierte `*_FIELD_NUMBER`-Konstanten (`*`).

| Nachricht (Klasse) | Felder (Nummer) |
|-----------------|-----------------|
| `SyncdPatch` (`C49631LsW`, lite `Lp6`) | version **1** `SyncdVersion{uint64=1}`, mutations **2**, externalMutations **3** `ExternalBlobReference`, snapshotMac **4**, patchMac **5**, keyId **6** `KeyId{bytes id=1}`, exitCode **7** `ExitCode{uint64 code=1; string text=2}`, deviceIndex **8**, clientDebugData **9** |
| `SyncdMutation` (`C49601Ls2`) | operation **1** (`SET`=0, `REMOVE`=1), record **2** |
| `SyncdRecord` (`C49610LsB`) | index **1** `SyncdIndex{bytes blob=1}` (Index-MAC), value **2** `SyncdValue{bytes blob=1}`, keyId **3** |
| `SyncdMutations` (`C49583Lrk`) | mutations **1** (externer Patch-Body) |
| `SyncdSnapshot` (`C49617LsI`, lite `C49419Lob`) | version **1**, records **2**, mac **3**, keyId **4** |
| `SyncActionData` (`C49612LsD`) | index **1** (UTF-8-JSON-String-Array), value **2** `SyncActionValue` (`BD4`), padding **3** (immer leer), version **4** int32 |
| `ExternalBlobReference` (`C49439Lov`) * | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `AppStateSyncKeyShare` (`C25704B7n`) * / `AppStateSyncKey` (`C25764B9y`) * | keys **1** / keyId **1** (`B89{keyId=1}`), keyData **2** |
| `AppStateSyncKeyData` (`BB9`) * | keyData **1** (32 Bytes), fingerprint **2**, timestamp **3** (ms) |
| `AppStateSyncKeyFingerprint` (`BBU`) * | rawId **1**, currentIndex **2**, deviceIndexes **3** |
| `AppStateSyncKeyRequest` (`C25703B7m`) * | keyIds **1** |
| `AppStateFatalExceptionNotification` (`C25763B9x`) * | collectionNames **1**, timestamp **2** |
| `SyncDCollectionFatalRecoveryRequest` | collectionName **1**, timestamp **2** |
| `SyncDSnapshotFatalRecoveryResponse` | collectionSnapshot **1**, isCompressed **2** |
| `SyncdSnapshotRecovery` (`C49432Loo`) * / `SyncdPlainTextRecord` (`C49416LoY`) * | version **1**, collectionName **2**, mutationRecords **3**, collectionLthash **4** / value **1** `SyncActionData`, keyId **2**, mac **3** |
| `KeyExpiration` (`B8Y`) | expiredKeyEpoch **1** |
| `SyncActionValue` (`BD4`) * | timestamp **1** (int64; ein SET ohne dieses Feld schlägt fehl), ein Feld pro Action (10.1) |

Träger (found, `*`): `ProtocolMessage` (`BD3`) `appStateSyncKeyShare` Feld **7** / Typ **6**, `appStateSyncKeyRequest` Feld **8** / Typ **7**, `appStateFatalExceptionNotification` Feld **10** / Typ **10** (`EnumC26463Bdz`). `PeerDataOperationRequestMessage.syncdCollectionFatalRecoveryRequest` Feld **7**, Request-Typ `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` = **8** (`EnumC26460Bdv`); Response `syncdSnapshotFatalRecoveryResponse` Feld **8** (`C25828BCm`). Companion-Client-Props (`C43107IrI`): `isSyncdPureLidSession` **2**, `isSyncdSnapshotRecoveryEnabled` **3**. Interne FMessage-Nummern: Key-Share **38**, Key-Request **39**, Fatal-Notification **50**. Share und Request werden als Peer-Nachrichten an ein `DeviceJid` gesendet (`SendPeerMessageJob`), Share-Priorität `high`.

---

## 5. Mutation Keys und Record-Verschlüsselung

### 5.1 Key-Ableitung (found, `MhX`, identisch in `C52959NkE`)

```
expanded = HKDF-SHA256(ikm = keyData(32), salt = 32 × 0x00, info = "WhatsApp Mutation Keys", L = 160)
```

| Bytes | `MhX`-Feld | Verwendung |
|-------|-------------|-----|
| 0-31 | `A00` | Index-Key, HMAC-SHA256 |
| 32-63 | `A03` | Value-Verschlüsselungs-Key, AES-256-CBC |
| 64-95 | `A04` | Value-MAC-Key, HMAC-SHA512 |
| 96-127 | `A02` | Snapshot-MAC-Key, HMAC-SHA256 |
| 128-159 | `A01` | Patch-MAC-Key, HMAC-SHA256 |

HKDF ist `AbstractC38961i0.A00`: Extract = `HMAC-SHA256(32 zero bytes, ikm)`, Expand nach RFC 5869. `C17930kd` cacht `MhX`-Objekte (5 Einträge, inferred). Der Sync Key ist zufällig (Abschnitt 7), nicht aus Signal-Keys abgeleitet.

### 5.2 Eine Mutation verschlüsseln (found, `KmpSyncdEncryptor`, `C52959NkE`)

```
index    = JSON string array, element 0 = action wire name, e.g. ["mute","<jid>"]
plain    = SyncActionData{ index = UTF8(index), value = SyncActionValue, padding = "", version }
iv       = SecureRandom(16)
ct       = AES-256-CBC/PKCS5(valueEncKey, iv, plain)
aad      = op ‖ keyId(6)                 op: 0x01 SET, 0x02 REMOVE
valueMac = HMAC-SHA512(valueMacKey, aad ‖ iv ‖ ct ‖ len8)[0..32)      len8 = 8-byte big-endian aad length (7)
indexMac = HMAC-SHA256(indexKey, UTF8(index))
record   = SyncdRecord{ index.blob = indexMac, value.blob = iv ‖ ct ‖ valueMac, keyId }
```

Die Padding-Länge ist `max(0, −indexLen − valueLen)`, immer leer. Minimale Blob-Größe 48 Bytes. SET→0x01 setzt voraus, dass die lokale Operationskonstante für SET 0 ist (inferred; Wire-SET=0). Der Value-Inhalt eines REMOVE ist als leer inferred (`mqt != null`-Zweig).

### 5.3 Entschlüsseln (found, `KmpSyncdDecryptor`)

| Schritt | Prüfung | Fehler |
|------|-------|---------|
| 1 | `iv = [0..16)`, `ct = [16..n−32)`, `mac = [n−32..n)` aufteilen | `Cipher text too short` |
| 2 | Key über `record.keyId` auflösen | Key-Fehler (7.2) |
| 3 | Value-MAC neu berechnen, vergleichen | `Data MAC mismatch` (`DecryptionFailed`) |
| 4 | AES-CBC entschlüsseln, `SyncActionData` parsen | `ActionDataProtobufDeserializationFailed` |
| 5 | Index, Version, (SET) Value und Timestamp vorhanden | `MISSING_INDEX`, `MISSING_VERSION`, `MISSING_VALUE`, `MISSING_ACTION_TIMESTAMP` |
| 6 | Index ist ein JSON-`String[]`, nicht leer, kein leeres Element | `keyArray length should have action name` |
| 7 | Index-MAC über den Index-String neu berechnen | `Index MAC mismatch` |

Der Value-MAC wird vor der Entschlüsselung geprüft, der Index-MAC zuletzt. Die Action wird anschließend über Element 0 aufgelöst (`Unknown mutation name:`).

---

## 6. LT-Hash, Snapshot-MAC und Patch-MAC

**LT-Hash** (found, `AbstractC50511MVx`, `KmpLtHash16`): 128 Bytes, gelesen als 64 Little-Endian-u16-Lanes; leer = 128 Nullbytes.

```
expanded(valueMac) = HKDF-SHA256(ikm = valueMac(32), salt = 32 × 0x00, info = "WhatsApp Patch Integrity", L = 128)
lane'[i]           = (lane[i] ± expanded[i]) mod 2^16         + add, − subtract
```

Eingehendes Update (`KmpSyncdCryptoHelper.A01`): für jeden Index im Patch das gespeicherte `mutation_mac` des vorhandenen Records **subtrahieren**, dann die Value-MACs der SETs **addieren**. `checkLtHashConsistency` (`C17520jx`) baut den Hash aus allen gespeicherten `mutation_mac`-Werten neu auf und vergleicht ihn mit dem gespeicherten Hash (loggt `ltHashFromMutations` / `ltHashFromDb`, letzte 16 Hex-Zeichen außer bei Flag **624**); er läuft im täglichen Cron, wenn Flag **1104** Stunden verstrichen sind (Default 0 = aus), und nach einem Snapshot-MAC-Mismatch mit Flag **1783**.

**MACs** (found):

```
version8    = 8-byte big-endian version
snapshotMac = HMAC-SHA256(snapshotMacKey, ltHash(128) ‖ version8 ‖ UTF8(collection))
patchMac    = HMAC-SHA256(patchMacKey,   snapshotMac ‖ valueMac₁ ‖ … ‖ valueMacₙ ‖ version8 ‖ UTF8(collection))
```

`valueMacᵢ` = die letzten 32 Bytes jedes Value-Blobs, in Patch-Reihenfolge. Ausgehend: Version = gespeichert + 1 für beide MACs (`C50707Mbo(old + 1)`). Der eingehende Patch-MAC verwendet den im Patch mitgelieferten `snapshot_mac`; der neu berechnete Snapshot-MAC wird separat verglichen.

| Eingehende Prüfung | Mismatch |
|----------------|----------|
| Patch-MAC | fatal `MacMismatchPatch` (32) |
| Snapshot-MAC in einem Snapshot | fatal `SnapshotMacMismatchInSnapshot` (52) |
| Snapshot-MAC in einem Patch | auf dem KMP-Pfad **nicht fatal**: `snapshot mac mismatch but do not throw fatal`, nicht-fataler Report-Code 60, optionale Consistency-Prüfung (**1783**); Consumer des zurückgegebenen Flags ungelöst |
| fehlender `snapshot_mac` / `patch_mac` | fatal `MissingSnapshotMac` (39) / `MissingPatchSnapshotMac` (40) / `MissingPatchMac` (41) |

---

## 7. Sync Keys

### 7.1 Key, Erzeugung, aktiver Key (found)

| Element | Wert |
|------|-------|
| Key-ID (`CGH`) | 6 Bytes: `deviceId` (2, BE) ‖ `epoch` (4, BE); `SyncdKeyId{deviceId=, epoch=}` |
| Key-Daten | 32 Zufallsbytes |
| Tabelle `crypto_info` | `device_id, epoch, key_data, timestamp, fingerprint, stale_timestamp` |
| Fingerprint | `rawId`, `currentIndex`, `deviceIndexes` des ADV-Key-Index-Zustands des Kontos bei der Erzeugung |
| Erzeugung (`C12800bm.A05`) | `epoch = max(stored max, in-memory) + 1` (zuerst zufällig in [0,65536), falls 0); nur wenn kein neu erzeugter Share unterwegs ist; ohne anderes Gerät wird der Key sofort gespeichert, sonst geht ein Share (Peer 38, `isNewlyGeneratedKey=true`) an jeden Companion und der Key wird persistiert, nachdem diese Nachricht **gesendet** wurde (`CXB.Bss`) |
| Aktiver Key | jüngste `crypto_info`-Zeile, jünger als **14488** Tage (Default 30) und Fingerprint-gültig, sonst wird beim nächsten Schreiben ein neuer Key erzeugt |
| Fingerprint-Prüfung (`A0B`) | `rawId` entspricht der lokalen ADV-Raw-ID; `deviceIndexes ∪ (currentIndex+1 … local currentIndex)` entspricht der lokalen Device-Index-Menge; sonst `one of a peer device is no longer registered` |
| Sentinel (`sentinel`, `KeyExpiration`) | `C25048AqM.A00` baut einen pro Collection (alle fünf) mit `expiredKeyEpoch` = höchste lokale Epoch |
| `expireKeysWithEpochIfActive` (`A08`) | setzt `timestamp = 0` beim jüngsten Key, wenn dessen Epoch ≤ der übergebenen Epoch; Aufrufer beim Empfang eines Sentinels nicht nachverfolgt (inferred) |
| Veraltete Keys | täglicher Cron markiert Keys, auf die `syncd_mutations` nicht verweist, und löscht sie nach **14496** Tagen (Default 31) |
| Re-Key | ein unter einem anderen Key gespeicherter Record wird über `findMutationWithExpiredKey` ersetzt; genaue REMOVE+SET-Form inferred |

### 7.2 Request und fehlende Keys (found, `C12800bm.A07`)

1. Unbekannte Key-IDs werden in `missing_keys(device_id, epoch, collection_name)` gespeichert und mit Key-Request-Peer-Nachrichten (Typ 39) an jedes andere registrierte Gerät angefordert; bereits ausstehende IDs werden übersprungen (`missing_key_counter`).
2. Der Responder sendet einen Share für die Keys, die er hat (`A0C`, `isNewlyGeneratedKey=false`).
3. Unbeantwortet seit **14492** Tagen (Default 7, älteste Typ-39-Peer-Nachricht, täglicher Cron) → fatal **31** (`TimeoutWhileWaitingForMissingKey`).
4. Niemand kann ihn liefern: `MissingKeyOnAllClients`; niemand zum Fragen: `RequestingMissingKeyWithNoClients`; keiner für die Verschlüsselung: `MissingActiveKeyForEncryption`.

Shares sind `ProtocolMessage`-Payloads Ende-zu-Ende-verschlüsselter Peer-Nachrichten (found). Eine empfängerseitige Fingerprint-Validierung eines eingehenden Shares wurde nicht gefunden (unknown).

---

## 8. Ausgehende Patches und externe Blobs

**Aufbau** (found, `OutgoingProcessor`, `KmpSyncdEncryptionProcessor`): ausstehende Mutationen (`pending_mutations`, `is_ready_to_sync=1`) werden pro Collection aufgeteilt; ein wiederholter Index in einem Patch wird abgelehnt (`SameIndexForMultipleMutationsInOutgoingPatch`); aktiver Key aufgelöst; jede Mutation verschlüsselt (5.2); neuer LT-Hash aus dem gespeicherten Hash (6); `snapshotMac` / `patchMac` mit Version gespeichert + 1; `SyncdPatch{version, mutations | externalMutations, snapshotMac, patchMac, keyId, deviceIndex?, clientDebugData?}`; IQ (3.1); das Result trägt die neue Version. `deviceIndex` (Feld 8) wird durch das Default-true-Flag **14486** gesteuert (Consumer nicht nachverfolgt).

**Regel für externen Upload** (found, `OutgoingProcessor`): `(mutationCount > P14494 or bytes > P14495 × 1024) and bytes > P5097 × 1024`, Defaults 100 / 10 / 0, also geht jeder Patch mit mehr als 100 Mutationen oder etwa 10 KB extern. Der Blob ist eine `SyncdMutations`-Nachricht; der Patch trägt dann `externalMutations` und keine Inline-`mutations` (beides gleichzeitig wird abgelehnt: `PatchWithBothInlineAndExternalMutations`). Upload-Fehler: `Upload transient network error`, `Upload local I/O failure`, `Upload failed`.

**Blob-Transport** (found, `C17650kB`, `C49831Lvs`, `C15530gU`):

| Element | Wert |
|------|-------|
| Media-Typ / Media-Key-HKDF-Info | `md-app-state` (MMS-Pfad `mms`) / `WhatsApp App State Keys` |
| Erforderliche Referenzfelder | mediaKey, directPath, fileSha256, fileEncSha256 (jedes fehlende → `MissingExternalBlobReference*`) |
| Download-Status | 5 = abgelaufen (`ExternalPatchExpired` 3 / `SnapshotExpired` 49, fatal); transiente Status werden wiederholt; andere fatal |
| Inhalt | externer Patch → `SyncdMutations`; Snapshot → `SyncdSnapshot` |

Das gemeinsame Media-Key-Expansion-Layout wird hier nicht erneut gelesen (gemeinsam genutzt, inferred).

**Debug-Daten** (found): `clientDebugData` = `PatchDebugData` (`C49633LsY`: `collection_name`, `current_lthash`, `new_lthash`, `new_lthash_subtract`, `patch_version`, `number_add/remove/override`, `sender_platform`, `is_sender_primary`, `first_four_bytes_from_a_hash_of_snapshot_mac_key`), nur mit Flag **6614** geschrieben (Default false); der Empfänger loggt es nach einem Patch-MAC-Mismatch.

---

## 9. Eingehende Patches und Snapshots

| # | Prüfung (found) | Fehler: KMP-Kind (ID) / Legacy-Code |
|---|---------------|--------------------------------------|
| 1 | Patch hat `version` | `MissingPatchVersion` (7) / 8 |
| 2 | keine doppelte Version in einer Response | `DuplicatePatchVersionInCollection` (8) / 9 |
| 3 | nicht Inline- und externe Mutationen zugleich | `PatchWithBothInlineAndExternalMutations` (13) / 14 |
| 4 | `version == stored + 1` (`verifyCollectionVersion`) | `ServerDidNotSendAllPatches` (64) |
| 5 | Patch-`exit_code` vorhanden | Legacy 36 (Code 100), 37 (101), 38 (sonstige); KMP-Gegenstück ungelöst |
| 6 | alle Mutationen entschlüsseln (5.3) | `DecryptionFailed` (6), Shape-Kinds |
| 7 | kein wiederholter Index unter SETs oder unter REMOVEs | `SameIndexForMultipleMutationsInPatch` (5) |
| 8 | Zyklus in Cross-Index-Abhängigkeiten | `CyclicMutationDependencyInPatch` (37) |
| 9 | LT-Hash, Patch-MAC, Snapshot-MAC neu berechnen (6) | `MacMismatchPatch` (32) / nicht fatal |
| 10 | per Action-Handler anwenden (SQLite), Version + Hash speichern | loggt `Cyclic mutation dependency`, `SQLite error` |

Snapshots: nur ein Companion im Bootstrap erhält einen (`Only companion devices that are undergoing bootstrap should receive and handle snapshots`). Blob herunterladen, Records wie Patch-Mutationen entschlüsseln, wiederholte Indizes ablehnen (`SameIndexForMultipleMutationsInSnapshot`, 59), Hash neu aufbauen, `snapshot.mac` vergleichen; danach die `has_more_patches`-Patches anwenden. `applySnapshot keyMap contains null value, retry` fordert Keys erneut an. Orphan-Mutationen (übergeordneter Chat fehlt) werden mit `are_dependencies_missing=1` gespeichert, über `chat_jid` indiziert und später erneut angewendet (`SyncdCrossIndexDependencyUtil`).

---

## 10. Sync-Action-Typen

### 10.1 Katalog (found, `EnumC24865AnN` + `AbstractC24863AnL.A00`)

Nummer = `SyncActionValue`-Feld des Values; `-` = keine passende Konstante in `BD4` (Value-Feld unknown). Index-Element 0 ist der Wire-Name; weitere Elemente sind actionspezifisch und nicht aufgezählt.

| Collection | Wire-Name = Feld |
|------------|-------------------|
| `critical_block` (4) | `setting_securityNotification` -, `setting_pushName` 7, `setting_locale` 16, `generated_wui` 52 |
| `critical_unblock_low` (2) | `contact` 3, `lid_contact` 61 |
| `regular_high` (19) | `star` 2, `mute` 4, `deleteMessageForMe` 18, `clearChat` 21, `deleteChat` 22, `userStatusMute` 29, `ugc_bot` 43, `status_privacy` 44, `favorites` 56, `waffle_account_link_state` 58, `ctwaPerCustomerDataSharing` 62, `maiba_ai_features_control` 68, `status_post_opt_in_notification_preferences_action` 71, `private_processing_setting` 74, **`nct_salt_sync` 80**, `biz_ai_settings_nudge` 87, `wasa_root_secret` 89, `shared_device_allowlist` 94, `ai_thread_delete` - |
| `regular` (35) | `quick_reply` 8, `label_message` -, `label_edit` 14, `label_jid` 15, `primary_feature` 24, `deviceAgent` 27, `subscription` 28, `agentChatAssignment` 35, `agentChatAssignmentOpenedStatus` 36, `pnForLidChat` 37, `marketingMessage` 38, `marketingMessageBroadcast` 39, `external_web_beta` 40, `setting_relayAllCalls` 41, `call_log` 42, `delete_individual_call_log` 46, `label_reordering` 47, `setting_disableLinkPreviews` 53, `usernameChatStartMode` 59, `notificationActivitySetting` 60, `setting_channels_personalised_recommendation_optout` -, `broadcast_jid` -, `detected_outcomes_status_action` 66, `business_broadcast_list` 69, `music_user_id` 70, `avatar_updated_action` 72, `galaxy_flow_action` -, `newsletter_saved_interests` 75, `business_broadcast_campaign` 81, `business_broadcast_insights_sync` 82, `subscriptions_sync_v2` 84, `label_sublist` 91, `ctwa_message_received` 93, `shareOwnPn` -, `broadcast` - |
| `regular_low` (36) | `pin_v1` 5, `recent_emoji_weights_action` 11, `archive` 17, `sentinel` 19, `markChatAsRead` 20, `setting_unarchiveChats` 23, `android_unsupported_actions` 26, `time_format` 30, `nux` 31, `primary_version` 32, `favoriteSticker` 33, `removeRecentSticker` 34, `bot_welcome_request` 45, `payment_info` 48, `custom_payment_methods` 49, `lock` 50, `setting_chatLock` 51, `device_capabilities` 54, `note_edit` 55, `merchant_payment_partner` 57, `payment_tos` 63, `ai_thread_rename` 76, `interactive_message_action` 77, `settings_sync` 78, `out_contact` 79, `customer_data` 83, `thread_pin` 85, `setting_autoOrganizeBusinessChat` 86, `coexV2Version` 88, `lock_message` 90, `device_capabilities_v2` 92, `contact_manager_metadata` 95, `business_folder_activation` 96, `group_history_toggle` 97, `bb_pro_pending_customer_base_action` 98, `community_nesting_state` 99 |

`BD4` hat keine Konstante für die Feldnummern 6, 9, 10, 12, 13, 25, 65, 67, 73. Zweckgruppen (aus den Namen inferred): Chat-Zustand (`mute`, `pin_v1`, `thread_pin`, `archive`, `markChatAsRead`, `clearChat`, `deleteChat`, `deleteMessageForMe`, `star`, `lock*`); Labels (`label_*`); Kontakte (`contact`, `lid_contact`, `out_contact`, `pnForLidChat`, `shareOwnPn`); Account-Einstellungen (`setting_*`, `time_format`, `status_privacy`); Keys und Tokens (`sentinel`, `nct_salt_sync`, `wasa_root_secret`, `generated_wui`, `shared_device_allowlist`); Business, AI, Calls, Payments (der Rest).

### 10.2 Ausgewählte Values (found)

| Action | Value |
|--------|-------|
| `nct_salt_sync` (Ordinal 73, `regular_high`) | `NctSaltSyncAction{bytes salt=1}` in `SyncActionValue`-Feld **80**; so liefert der Primary den NCT-Salt an Companions, Ursprung und Verwendung in `WA_TCTOKEN_CSTOKEN.md` (3.2) |
| `contact` (`ContactAction`) | fullName 1, firstName 2, lidJid 3, saveOnPrimaryAddressbook 4, pnJid 5, username 6, birthday 7; nur vom Primary erzeugt, daher erhält ein Companion im Bootstrap sein Adressbuch vor jeder `regular*`-Collection |
| `mute` (`MuteAction`) | muted 1, muteEndTimestamp 2, autoMuted 3, muteEveryoneMentionEndTimestamp 4 |
| `sentinel` | `KeyExpiration{expiredKeyEpoch}` (7.1) |
| `android_unsupported_actions` (26), Flag **14490** (Default false) | ein „Android unsupported mutation"-Pfad; Semantik unknown |

---

## 11. Fatal-Fehler, Retry und Recovery

### 11.1 KMP-Fatal-Kinds (found, `Lx6.A00`; IDs sind intern, keine Wire-Werte)

| Gruppe | IDs und Namen |
|-------|---------------|
| Transport | 53 `XmppBadRequestForCollection`, 54 `…NotFoundForCollection`, 55 `XmppBadRequestGlobalError`, 56 `…NotFoundGlobalError`, 57 `…BadMethodGlobalError`, 58 `…NotAcceptableGlobalError` |
| Patch- / Snapshot-Form | 4 `MissingOrEmptyIndex`, 5 `SameIndexForMultipleMutationsInPatch`, 7 `MissingPatchVersion`, 8 `DuplicatePatchVersionInCollection`, 13 `PatchWithBothInlineAndExternalMutations`, 37 `CyclicMutationDependencyInPatch`, 38 `MissingSnapshotVersion`, 47 `MissingPatchKeyId`, 50 `MissingSnapshotKeyId`, 59 `SameIndexForMultipleMutationsInSnapshot`, 64 `ServerDidNotSendAllPatches`, 65 `ServerSentEarlierPatch`, 71 `InvalidSnapshotRecords` |
| Mutation- / Action-Form | 10-12, 14-16, 19-24 (`MissingMutationVersion/Value/Index/Operation/Record/KeyId`, `MissingActionIndex/Value/Version/Timestamp`, `InvalidMutationIndex`, `InvalidActionIndex`) |
| Crypto | 6 `DecryptionFailed`, 9 `EncryptionFailed`, 31 `MacMismatchSnapshot`, 32 `MacMismatchPatch`, 39-41 `Missing*Mac`, 51 `SnapshotMacMismatchInPatch`, 52 `SnapshotMacMismatchInSnapshot` |
| Keys | 29 `MissingKeyOnAllClients`, 30 `TimeoutWhileWaitingForMissingKey`, 46 `InvalidKeyShareKeyId`, 48 `InvalidKeyShareKeyData`, 62, 66-69 (`RequestingMissingKeyWithNoClients`, `MissingKeyForMutationInLocalSnapshot`, `MissingActiveKeyAfterRotation`, `MissingActiveKeyForEncryption`, `MissingCurrentEpochForActiveKeyValidation`) |
| Blobs / Protobuf | 3 `ExternalPatchExpired`, 49 `SnapshotExpired`, 42-45 und 72 `MissingExternalBlobReference*`, 60 / 61 Parse-Fehler bei Referenz / Snapshot, 17 / 18 / 25-28 (De-)Serialisierungs-Kinds, 34-36 `TerminalPatch*` |
| Lokal | 33 `DbStoreNotReady`, 63 `DbStoreNotReadyLowDiskSpace`, 70 `SameIndexForMultipleMutationsInOutgoingPatch` |

### 11.2 Legacy-Numerikcodes (found, `C49784Lv2.errorCode`, speisen WAM `md_fatal_error`; separate Nummerierung)

8 / 9 / 14 (`N90`: keine Version / doppelte Version / Inline + extern), 18 / 69 (Parse-Fehler Patch / Snapshot), 36 / 37 / 38 (`exit_code` 100 / 101 / sonstige), 64-67 (globale IQ-Fehler 400 / 404 / 405 / 406), 71 (Key-Auflösung nach dem Missing-Key-Request fehlgeschlagen), 31 (Timeout beim Warten auf Key), 60 (nicht-fataler Snapshot-MAC-Mismatch in einem Patch, `A0F(60, collection, false)`). Die Zuordnung zu den KMP-Kinds ist ungelöst.

### 11.3 Reaktion auf einen Fatal-Fehler (found, `SyncResponseHandler.A08`, `C12440bB.A0S/A0Q`)

| Rolle | Aktion |
|------|--------|
| Beliebig | Log `app-state-sync-handle-fatal-exception`, WAM `md_fatal_error`, laufenden Sync löschen |
| Flag **25799** | Companion: `companion_syncd_dirty=true`; Primary: `C17630k8.A01(1)` (Dirty-Grund 1, inferred) |
| Primary | `A0Q(1)` löscht alle syncd-Daten. Dirty-Automat (`C17630k8`, Kette ab `A0Q` inferred): `syncd_dirty`-Zähler bis 4, `syncd_dirty_reason`, `<iq xmlns="w:sync:app:state" type="set"><delete_all_data/></iq>` (type-Attribut inferred), `logoutAllCompanionDevices` |
| Companion | `companion_syncd_dirty=true`, Peer-Nachricht `AppStateFatalExceptionNotification` (FMessage 50) an den Primary (Gerät 0), 5 s Wartezeit, Logout mit `syncd_failure` oder `syncd_error_during_bootstrap` |

Retry-Fenster für Delete-all **14493** Minuten (Default 360). Der Primary räumt auf, wenn ein Companion deregistriert wurde und keiner mehr übrig ist (`shouldCleanUpSyncd`).

### 11.4 Snapshot Recovery (found, `KmpSyncdFatalErrorRecovery`)

Gesteuert durch die Client-Prop `isSyncdSnapshotRecoveryEnabled`. Der Companion sendet die Peer-Data-Operation `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` (8) mit `SyncDCollectionFatalRecoveryRequest{collectionName}`. Der Responder baut aus seinen gespeicherten **Klartext**-Mutationen (`syncd_mutations`, `collection_versions.version / lt_hash`) ein `SyncdSnapshotRecovery`, komprimiert es mit gzip und gibt `SyncDSnapshotFatalRecoveryResponse` zurück. Ablehnungen: `Invalid collection name` (Request für `critical_block`), `Collection version/ltHash invalid`, `Snapshot keyId invalid`, `Mutation count (…) more than the limit`, `Mutation snapshot data size (…) more than the limit`, `Error encoding mutation data`, `Compression failed` (Cap-Props nicht aufgelöst). Der Klartext wandert in einer Ende-zu-Ende-verschlüsselten Peer-Nachricht. Das Anwenden auf Companion-Seite wurde nicht nachverfolgt (unknown).

---

## 12. Lokaler Zustand und Feature-Flags

| Store | Inhalt (found) |
|-------|-----------------|
| `syncd_mutations` | `mutation_index` (unique), `mutation_value`, `mutation_version`, `collection_name`, `are_dependencies_missing`, `mutation_mac`, `device_id`, `epoch`, `chat_jid`, `mutation_name` |
| `collection_versions` / `pending_mutations` / `missing_keys` / `crypto_info` | `collection_name, version, lt_hash` / ausgehende Queue (`is_ready_to_sync`) / Key-Requests / Sync Keys |
| Prefs | `syncd_bootstrap_state`, `companion_syncd_critical_bootstrap_state`, `syncd_dirty`, `syncd_dirty_reason`, `companion_syncd_dirty`, `syncd_last_companion_dereg_time`, `syncd_last_lthash_consistency_check_time`, `first_transient_server_failure_timestamp` |

Der tägliche Cron (`C46413KPv`) meldet die Zähler `mutation_counter`, `invalid_action_counter`, `upload_conflict_counter`, `unsupported_action_counter`, `cross_index_conflict_counter`, `unset_action_mutation_counter`, `key_rotation_remove_counter`, `missing_key_counter`.

| Flag-ID | Typ / Default | Steuert |
|---------|---------------|----------|
| **15909**, **20682**, **18234** | bool / false | `XplatSyncdEncryptionManager` vs. Default (`AbstractC17550k0`); KMP Incoming (`RunnableC53542Nwj`); KMP Outgoing (`C12440bB`). Nur einkompilierte Defaults, Live-Wert unknown. Name von 15909 in einem früheren Build: `KMP_SYNCD_ENGINE_CRYPTO_ENABLED` (ID-Wiederverwendung inferred) |
| **14488** / **14496** / **14492** | int / 30 / 31 / 7 | Alter des aktiven Keys, Aufbewahrung veralteter Keys, Key-Wait-Timeout (Tage) |
| **14493** | int / 360 | Delete-all- / Dereg-Fenster (Minuten) |
| **14494**, **14495**, **5097** | int / 100, 10, 0 | Schwellen für externe Patches |
| **14497** | int / 1000 | Ladelimit für DB-Mutationen (inferred) |
| **1104** / **1783** | int 0 / bool false | Intervall der Consistency-Prüfung (h) / Prüfung nach Snapshot-MAC-Mismatch |
| **6614** | bool / false | `clientDebugData` in Patches |
| **25799** | bool / false | Dirty-State-Behandlung bei Fatal-Fehler |
| **27528** | bool / false | Key erzeugen, wenn der Primary keinen hat |
| **14486** | bool / true | `deviceIndex` in Patches (Consumer nicht nachverfolgt) |
| **14489**, **14490**, **1221**, **624** | int 90 / bool false / bool false / bool | `min()`-Cap in `C15310g7` (ungelöst) / Unsupported-Mutation-Pfad / Mutationsstatistik / volle Hashes in Logs |

---

## 13. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|-------|-----|
| `Data MAC mismatch` | falscher Key, manipulierter Blob, falsches Op-Byte oder keyId in der AAD | Key, den `record.keyId` nennt; AAD = `op ‖ keyId`, op 1 SET / 2 REMOVE |
| `Index MAC mismatch` | Index-String weicht byteweise ab (JSON-Spacing) | exakten UTF-8-String von `SyncActionData.index` MACen |
| fatal 64 `ServerDidNotSendAllPatches` | Patch-Version ≠ gespeichert + 1 | ab der gespeicherten Version neu synchronisieren; Snapshot anfordern, wenn der Zustand verloren ist |
| Patch-MAC-Mismatch (32) | LT-Hash-Drift, version8-Breite, Snapshot-MAC aus der falschen Quelle | zuerst den `snapshot_mac` des Patches verwenden; Version als 8-Byte-Big-Endian |
| `PatchWithBothInlineAndExternalMutations` | beide Felder gesetzt | nur eines senden |
| `MissingActionTimestamp` | `SyncActionValue.timestamp` fehlt bei SET | Feld 1 setzen |
| Key fehlt | Share nicht empfangen | Typ-39-Request; fatal 31 nach 7 Tagen |
| `one of a peer device is no longer registered` | Geräteliste seit Key-Erzeugung geändert | Key nicht als aktiver Key nutzbar; neuen erzeugen |
| IQ-Fehler 400 / 404 / 405 / 406 | fehlerhafte Request-Form, unbekannte Collection | fatal; Request korrigieren |
| `ExternalPatchExpired` / `SnapshotExpired` | Blob-Status 5 | Snapshot Recovery oder erneut verknüpfen |
| Companion-Logout `syncd_failure` | nicht behebbarer Fatal-Fehler | neu pairen, oder Snapshot Recovery falls aktiviert |

---

## 14. Wichtige Unterscheidungen

| Nicht verwechseln | Mit |
|----------------|------|
| Sync Key (32 Zufallsbytes pro Gerät+Epoch) | Mutation Keys (HKDF-Ausgabe, fünf Slices) |
| Index-MAC (HMAC-SHA256 über den Index-String) | Value-MAC (HMAC-SHA512, auf 32 gekürzt, über AAD + iv + ct + len) |
| Value-MAC (pro Mutation) | Snapshot-MAC (LT-Hash + Version + Collection) und Patch-MAC (Snapshot-MAC + alle Value-MACs) |
| `<snapshot>`-Node (eine `ExternalBlobReference`) | `SyncdSnapshot`-Proto (der Blob-Inhalt); ebenso `externalMutations` vs. `SyncdMutations` |
| `critical_block` unter Android (Account-Einstellungen) | eine Blocklisten-Collection (nicht gefunden) |
| `ProtocolMessage`-Typen 6 / 7 / 10 | Feldnummern 7 / 8 / 10 |
| Peer-Data-Request-Feld 7 | Peer-Data-Response-Feld 8 |
| KMP-Kind-IDs (`Lx6`) | Legacy-`errorCode`-Ints |
| `sentinel` (Key-Ablauf-Marker in allen fünf Collections) | `primary_version`, `android_unsupported_actions` |
| WhatsApp-Web-Action- / Collection-Tabellen | die Android-Tabelle hier (96 Actions, andere Zuordnung) |

---

## 15. Baileys (`baron-baileys-v2` 1.5.17)

Nur Fakten, die in `src/Utils/chat-utils.js`, `src/Socket/chats.js`, `src/Utils/process-message.js` gelesen wurden. Nichts wurde gegen einen Server getestet; kein Fehlschlag wird behauptet.

| Thema | Baileys | Android |
|-------|---------|---------|
| Key-Expansion, LT-Hash | nativer Bridge `expandAppStateKeys`, `LTHashAntiTampering` (128 Bytes); dieselben fünf Slice-Namen | 5.1, 6 |
| Value-MAC | `HMAC-SHA512(op ‖ keyId ‖ data ‖ 8 bytes, last = len)[0..32)`, op 1 / 2 | identisch |
| Snapshot- / Patch-MAC | gleiche Eingaben und Reihenfolge; `ver8` schreibt nur die unteren 32 Bit | volle 64-Bit-Big-Endian |
| Index, Padding | `JSON.stringify(index)`, leeres Padding | gleich |
| Externer Blob | `downloadContentFromMessage(blob, 'md-app-state')` | gleicher Media-Typ |
| Collections | `critical_block, critical_unblock_low, regular_high, regular_low, regular` | gleiche Namen |
| Request-Node | `<sync>` ohne Attribute; `<collection name version return_snapshot>`, `return_snapshot` immer `'true'`/`'false'` | `data_namespace="3"`, `order`, `return_snapshot` nur wenn true |
| Patch senden | `version = state.version − 1`, `return_snapshot='false'` | gespeicherte Version |
| Versionskontinuität | nicht geprüft (`newState.version = patchVersion`); eine fehlende Patch-Version wird zur Collection-Version + 1 | muss gespeichert + 1 entsprechen |
| Snapshot-MAC in einem Patch | neu berechnet, wirft `failed to verify LTHash` | auf dem KMP-Pfad nicht fatal |
| Key-Share | speichert nur `keyData` pro Base64-Key-ID; `myAppStateKeyId` = letzter Key in der Nachricht | behält Fingerprint und Timestamp, verifiziert den Fingerprint, wählt den jüngsten gültigen Key |
| Fatal-Notification | geloggt, als `app-state.sync-error` emittiert | Companion sendet, Primary handelt |
| Retry | `MAX_SYNC_ATTEMPTS = 2`, Forced-Snapshot-Retry, fehlender Key parkt die Collection | Abschnitt 11 |
| NCT-Salt | `nctSaltSyncAction.salt` gespeichert als `nct-salt` | 10.2 |

Nicht im Baileys-Quellcode vorhanden: `data_namespace`, `order`, `exit_code`-Behandlung, Snapshot Recovery. Auswirkung auf den Server ist unknown.

---

## 16. Vollständige Abläufe

### 16.1 Primary schreibt eine Änderung (Beispiel `mute`)

```
[User]  → handler builds mutation  ["mute","<chatJid>"]  MuteAction  collection regular_high
     │
     ▼
[SyncManager C12440bB]  pending_mutations ; active key (≤ 30 d, fingerprint ok) else generate, share (peer 38)
     │
     ▼
[Encrypt]  iv ; AES-CBC ; aad = 01 ‖ keyId ; valueMac ; indexMac
     │     ltHash' = ltHash − oldValueMac + newValueMac ; ver = stored + 1 ; snapshotMac ; patchMac
     │     SyncdPatch inline, or externalMutations above the thresholds (md-app-state upload)
     ▼
iq set w:sync:app:state  <sync data_namespace=3><collection name order version><patch/></collection></sync>
     │
     ▼
[WA Server]  (not observed) orders patch, assigns version
     │
     ▼
Result <collection name version="N+1"/>  →  store version, hash, mutation_mac
     │
     ▼
[Companions]  sync (16.2)
```

### 16.2 Companion zieht

```
[Companion]  iq set  <collection name version=V [return_snapshot=true if V=0]/>
     │
     ▼
Result <collection has_more_patches?> [<snapshot ExternalBlobReference/>] <patches><patch/>…</patches>
     │
     ├─ snapshot ─► download md-app-state ─► SyncdSnapshot ─► decrypt ─► hash ─► snapshot MAC
     └─ each patch (V+1 …) ─► version check ─► external blob? download SyncdMutations
            │  key unknown ─► missing_keys + peer 39 ─► [Primary] peer 38 share
            │  decrypt (valueMac → AES → SyncActionData → indexMac) ; ltHash − old + new
            │  patchMac ; snapshotMac ; action handler apply (are_dependencies_missing for orphans)
            ▼
         store version, hash ; has_more_patches → repeat
```

### 16.3 Fatal-Fehler

```
[Companion]  patch MAC mismatch / key timeout / version gap
     ├─ recovery enabled ─► peer data op 8 {collectionName} ─► [Primary] SyncdSnapshotRecovery (gzip)
     └─ else companion_syncd_dirty ; peer AppStateFatalExceptionNotification ; 5 s ; logout syncd_failure
               ▼
         [Primary]  delete syncd data ; iq <delete_all_data/> ; logout companions ; re-pair
```

---

## 17. Unknowns

| Element | Status |
|------|--------|
| Aktive Engine (Legacy oder KMP) pro Konto | Server-Flags |
| Bedeutung des Attributs `order` | unknown |
| Empfängerseitige Fingerprint-Prüfung eines eingehenden Key-Shares | nicht gefunden |
| Apply-Seite eines empfangenen `sentinel` (`expireKeysWithEpochIfActive`) | nicht nachverfolgt |
| Zuordnung KMP-Kind ↔ Legacy-Code; Auslöser von `ServerSentEarlierPatch`; Bedeutung von `exit_code` 100 / 101 | ungelöst |
| Value-Feld der 9 mit `-` markierten Actions | unknown |
| Apply-Seite der Snapshot Recovery, Cap-Props | nicht nachverfolgt |
| Server-Ordnung, Aufbewahrung, Merge-Regeln | serverseitig |
| Traffic | nichts mitgeschnitten |
