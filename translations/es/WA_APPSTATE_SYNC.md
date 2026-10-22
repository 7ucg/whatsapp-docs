<!-- src-sha1: f9c1d644c604d99d2f1b54082218c3f75d2cf8a7 -->
# WhatsApp Sincronización de App-State — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** sincronización de app-state (syncd) en Android: cinco colecciones, IQ `w:sync:app:state`, patches / snapshots / blobs externos, mutaciones SET/REMOVE, derivación de claves de mutación y cifrado de registros, MAC de índice / valor, LT-Hash, MAC de snapshot y de patch, claves de sincronización (generación, share, request, expiración), validación saliente y entrante, catálogo de acciones de sincronización (96 acciones: chat, label, contact, nctSalt …), manejo de errores fatales y reintentos, recuperación de snapshot, feature flags, comparación con Baileys

---

## 1. Qué es (técnicamente)

La sincronización de app-state replica pequeños estados por cuenta (silenciar, fijar, archivar, destacar, contactos, labels, ajustes …) entre el teléfono primario y cada dispositivo vinculado. El servidor almacena únicamente registros cifrados de extremo a extremo, los ordena por colección y sirve patches versionados. Todas las afirmaciones provienen del análisis estático del APK decompilado; no se capturó nada en la red. Tier: **found** = leído en el código, **inferred** = deducido del código, **unknown** = no resuelto. Los nombres ofuscados se volvieron a resolver en 2.26.41.6 a partir de strings estables (`WhatsApp Mutation Keys`, `WhatsApp Patch Integrity`, `w:sync:app:state`, nombres de colecciones, prefijos de log).

| Entidad | Nombre en 2.26.41.6 | Función |
|--------|----------------|------|
| Gestor de sincronización | `C12440bB` (`sync-manager/*`) | planificación, `A0S` fallo fatal, `A0Q` eliminar todos los datos |
| Manejador de requests / constructor de IQ / parser | `C53148Nnt` / `C46361ux` / `N90` | enviar IQ, construir `<sync>`, parsear el resultado |
| Manejador de respuestas legacy | `SyncResponseHandler` (`consumer/companiondevice/p049iq`) | ruta de aplicación legacy, manejo fatal `A08` |
| Motor KMP | `com.whatsapp.kmp.syncd.syncdengine.*` | `OutgoingProcessor`, `IncomingProcessor`, `SyncdResponseHandler`, `SyncdResponseProcessor`, `CollectionHandler`, `crypto/*` |
| Enum de colecciones / enum de acciones | `EnumC24862AnK` / `EnumC24865AnN` | 5 colecciones / 96 nombres de acción en el wire |
| Acción a colección | `AbstractC24863AnL.A00` | switch por ordinal |
| Base de mutación / base de manejador | `AbstractC24864AnM` / `AbstractC25077Aqp` | mutación pendiente / manejador de acción |
| Gestor de claves / almacén | `C12800bm` (`SyncdKeyManager`) / `C13620d6` (tabla `crypto_info`) | generar, compartir, solicitar, expirar, persistir claves |
| Key id / clave / datos de clave | `CGH` / `C51259MoT` / `C51361MqC` | id de 6 bytes / id + datos / datos, huella `C8H`, ts |
| Claves de mutación | `MhX` | salida de HKDF, 5 segmentos |
| Portadores de share / request | `C26102BPk` (FMessage 38) / `C26101BPj` (39) | mensajes peer |
| LT-Hash, HKDF | `AbstractC50511MVx.A00` + `KmpLtHash16`, `AbstractC38961i0` | hash de 128 bytes, RFC 5869 |
| Crypto (legacy / KMP) | `C52959NkE` / `KmpSyncdCryptoHelper`, `KmpSyncdEncryptor`, `KmpSyncdDecryptor`, `KmpSyncdIncomingAntiTamperingValidator` | fórmulas idénticas |
| Blobs externos | `C17650kB` (descarga), `KmpExternalMutationsUploaderImpl` | tipo MMS `md-app-state` |
| Bootstrap / delete-all / recuperación | `C24986ApL` / `C17630k8` / `KmpSyncdFatalErrorRecovery` | máquina de estados, `delete_all_data`, entrega de snapshot |
| Tipos fatales / excepción legacy | `Lx6` / `C49784Lv2` | 70 tipos con nombre / `errorCode` int |

Dos implementaciones del mismo protocolo coexisten. El motor KMP se selecciona mediante tres booleanos controlados por el servidor cuyos valores por defecto compilados son **false** (**15909** crypto, **20682** entrante, **18234** saliente, sección 12). Qué ruta ejecuta una cuenta es desconocido. Las fórmulas de MAC y de cifrado son idénticas en ambas (comparadas en `C52959NkE` y `KmpSyncd*`).

Primario y companion ejecutan el mismo código. Diferencias encontradas: solo un primario crea mutaciones `contact` / `lid_contact` (`Companion cannot create contact mutations`); solo un companion envía `return_snapshot="true"`; el manejo de fallos fatales difiere (11.3).

---

## 2. Colecciones

| Nombre en el wire | Ordinal del enum | Crítica | Bit de log (`C17530jy.A00`) | Acciones |
|-----------|--------------|----------|--------------------------|---------|
| `regular` | 0 | no | 3 | 35 |
| `regular_low` | 1 | no | 5 | 36 |
| `regular_high` | 2 | no | 4 | 19 |
| `critical_block` | 3 | sí | 1 | 4 |
| `critical_unblock_low` | 4 | sí | 2 | 2 |

Conjunto crítico = `{critical_block, critical_unblock_low}` (`EnumC24862AnK.A01`). `A00()` mapea el ordinal a 1..5; consumidor no trazado.

En Android `critical_block` contiene acciones de ajustes de cuenta (`setting_pushName`, `setting_locale`, `setting_securityNotification`, `generated_wui`), **no** una lista de bloqueo; `contact` y `lid_contact` están en `critical_unblock_low`. Ninguna acción del enum de 96 entradas lleva un nombre relacionado con bloquear (found).

**Bootstrap (companion, parcialmente inferred).** `syncd_bootstrap_state` (`C24986ApL`) recorre 0 → 4. Found: conjunto crítico sincronizado → estado 2 y una señal "critical blocking complete"; todas las colecciones no críticas sincronizadas → estado 4; el estado 3 es el paso de history sync (inferred). Motivos de fallo: `critical_sync_timeout`, `history_sync_failure`, `syncd_failure`; log del watchdog `syncd-critical-bootstrap-timeout`. En el primario, vincular un companion ejecuta `prepareCriticalDataUpload`: history sync, luego `shareAllKeys`; sin clave y con el flag **27528** se genera primero una clave.

---

## 3. Capa IQ

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

| Atributo | Valor |
|-----------|-------|
| `data_namespace` | constante `3` en `<sync>` |
| `order` | `0` para `critical_unblock_low`, `1` en los demás; significado desconocido |
| `version` | versión de la colección almacenada localmente (`C17540jz.A02`); se omite si no hay ninguna |
| `return_snapshot` | `"true"` solo para un companion con versión null o 0 |
| `<patch>` | solo cuando hay mutaciones locales pendientes |
| `<coex><bot>` | coexistence-v2: las claves de sincronización usadas se cifran hacia un bot (`sync-request-handler/coexv2 *`); si falla, el IQ se envía sin él y las claves se comparten fuera de banda |

Timeout de 32 s; un IQ puede llevar varias colecciones.

### 3.2 Resultado (found, `N90`)

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

Un `<sync>` ausente o un cuerpo `<snapshot>` / `<patch>` vacío → fallo transitorio. Una colección sin versión, patches ni snapshot se conserva como un nombre simple (significado inferred: nada nuevo). Los cuerpos de snapshot son siempre un `ExternalBlobReference`, nunca registros inline.

Errores de colección (`M4T`): -1 `UNKNOWN` reintentable; 400 / 404 / 405 / 406 fatal (`Xmpp*ForCollection`); 409 `CONFLICT` aplicar los patches adjuntos y luego reintentar, si no, reintentable (la condición de la rama es ambigua en el decompilado); 500 reintentable.

Error global de IQ (`C53148Nnt.Brt`, `backoff` en segundos):

| Código | Manejo |
|------|----------|
| 400, 404, 405, 406 | fatal; códigos legacy 64, 65, 66, 67; tipos KMP 55-58 |
| otros 4xx | sin reintento, `client_error:<code>` |
| 5xx | reintento tras `max(server backoff, client delay)`, `server_error:<code>` |
| otros | `global_error:<code>` |

Los fallos transitorios de más de 7 días (`first_transient_server_failure_timestamp` > 604 800 000 ms) escalan a fatal. Otros motivos no fatales: `network_error`, `sqlite_full`, `unexpected_error`, `mms_local_io`, `mms_upload`.

---

## 4. Mensajes protobuf

Los números se recuperaron de las clases de 2.26.41.6, contrastados con el orden de declaración y, cuando existen, con las constantes `*_FIELD_NUMBER` generadas (`*`).

| Mensaje (clase) | Campos (número) |
|-----------------|-----------------|
| `SyncdPatch` (`C49631LsW`, lite `Lp6`) | version **1** `SyncdVersion{uint64=1}`, mutations **2**, externalMutations **3** `ExternalBlobReference`, snapshotMac **4**, patchMac **5**, keyId **6** `KeyId{bytes id=1}`, exitCode **7** `ExitCode{uint64 code=1; string text=2}`, deviceIndex **8**, clientDebugData **9** |
| `SyncdMutation` (`C49601Ls2`) | operation **1** (`SET`=0, `REMOVE`=1), record **2** |
| `SyncdRecord` (`C49610LsB`) | index **1** `SyncdIndex{bytes blob=1}` (MAC de índice), value **2** `SyncdValue{bytes blob=1}`, keyId **3** |
| `SyncdMutations` (`C49583Lrk`) | mutations **1** (cuerpo de patch externo) |
| `SyncdSnapshot` (`C49617LsI`, lite `C49419Lob`) | version **1**, records **2**, mac **3**, keyId **4** |
| `SyncActionData` (`C49612LsD`) | index **1** (array de strings JSON en UTF-8), value **2** `SyncActionValue` (`BD4`), padding **3** (siempre vacío), version **4** int32 |
| `ExternalBlobReference` (`C49439Lov`) * | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `AppStateSyncKeyShare` (`C25704B7n`) * / `AppStateSyncKey` (`C25764B9y`) * | keys **1** / keyId **1** (`B89{keyId=1}`), keyData **2** |
| `AppStateSyncKeyData` (`BB9`) * | keyData **1** (32 bytes), fingerprint **2**, timestamp **3** (ms) |
| `AppStateSyncKeyFingerprint` (`BBU`) * | rawId **1**, currentIndex **2**, deviceIndexes **3** |
| `AppStateSyncKeyRequest` (`C25703B7m`) * | keyIds **1** |
| `AppStateFatalExceptionNotification` (`C25763B9x`) * | collectionNames **1**, timestamp **2** |
| `SyncDCollectionFatalRecoveryRequest` | collectionName **1**, timestamp **2** |
| `SyncDSnapshotFatalRecoveryResponse` | collectionSnapshot **1**, isCompressed **2** |
| `SyncdSnapshotRecovery` (`C49432Loo`) * / `SyncdPlainTextRecord` (`C49416LoY`) * | version **1**, collectionName **2**, mutationRecords **3**, collectionLthash **4** / value **1** `SyncActionData`, keyId **2**, mac **3** |
| `KeyExpiration` (`B8Y`) | expiredKeyEpoch **1** |
| `SyncActionValue` (`BD4`) * | timestamp **1** (int64; un SET sin él falla), un campo por acción (10.1) |

Portadores (found, `*`): `ProtocolMessage` (`BD3`) `appStateSyncKeyShare` campo **7** / tipo **6**, `appStateSyncKeyRequest` campo **8** / tipo **7**, `appStateFatalExceptionNotification` campo **10** / tipo **10** (`EnumC26463Bdz`). `PeerDataOperationRequestMessage.syncdCollectionFatalRecoveryRequest` campo **7**, tipo de request `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` = **8** (`EnumC26460Bdv`); respuesta `syncdSnapshotFatalRecoveryResponse` campo **8** (`C25828BCm`). Client-props del companion (`C43107IrI`): `isSyncdPureLidSession` **2**, `isSyncdSnapshotRecoveryEnabled` **3**. Números internos de FMessage: key share **38**, key request **39**, notificación fatal **50**. Share y request viajan como mensajes peer a un único `DeviceJid` (`SendPeerMessageJob`), prioridad del share `high`.

---

## 5. Claves de mutación y cifrado de registros

### 5.1 Derivación de claves (found, `MhX`, igual en `C52959NkE`)

```
expanded = HKDF-SHA256(ikm = keyData(32), salt = 32 × 0x00, info = "WhatsApp Mutation Keys", L = 160)
```

| Bytes | Campo de `MhX` | Uso |
|-------|-------------|-----|
| 0-31 | `A00` | clave de índice, HMAC-SHA256 |
| 32-63 | `A03` | clave de cifrado de valor, AES-256-CBC |
| 64-95 | `A04` | clave MAC de valor, HMAC-SHA512 |
| 96-127 | `A02` | clave MAC de snapshot, HMAC-SHA256 |
| 128-159 | `A01` | clave MAC de patch, HMAC-SHA256 |

HKDF es `AbstractC38961i0.A00`: extract = `HMAC-SHA256(32 zero bytes, ikm)`, expand según RFC 5869. `C17930kd` cachea objetos `MhX` (5 entradas, inferred). La sync key es aleatoria (sección 7), no se deriva de claves Signal.

### 5.2 Cifrar una mutación (found, `KmpSyncdEncryptor`, `C52959NkE`)

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

La longitud del padding es `max(0, −indexLen − valueLen)`, siempre vacío. Blob mínimo de 48 bytes. SET→0x01 asume que la constante de operación local es 0 para SET (inferred; wire SET=0). El contenido de valor de un REMOVE se infiere vacío (rama `mqt != null`).

### 5.3 Descifrar (found, `KmpSyncdDecryptor`)

| Paso | Comprobación | Fallo |
|------|-------|---------|
| 1 | dividir `iv = [0..16)`, `ct = [16..n−32)`, `mac = [n−32..n)` | `Cipher text too short` |
| 2 | resolver la clave por `record.keyId` | errores de clave (7.2) |
| 3 | recalcular el MAC de valor, comparar | `Data MAC mismatch` (`DecryptionFailed`) |
| 4 | descifrar AES-CBC, parsear `SyncActionData` | `ActionDataProtobufDeserializationFailed` |
| 5 | index, version, (SET) value y timestamp presentes | `MISSING_INDEX`, `MISSING_VERSION`, `MISSING_VALUE`, `MISSING_ACTION_TIMESTAMP` |
| 6 | index es un `String[]` JSON, no vacío, sin elemento vacío | `keyArray length should have action name` |
| 7 | recalcular el MAC de índice sobre el string de índice | `Index MAC mismatch` |

El MAC de valor se comprueba antes de descifrar, el MAC de índice al final. Después la acción se resuelve por el elemento 0 (`Unknown mutation name:`).

---

## 6. LT-Hash, MAC de snapshot y MAC de patch

**LT-Hash** (found, `AbstractC50511MVx`, `KmpLtHash16`): 128 bytes leídos como 64 lanes u16 little-endian; vacío = 128 bytes cero.

```
expanded(valueMac) = HKDF-SHA256(ikm = valueMac(32), salt = 32 × 0x00, info = "WhatsApp Patch Integrity", L = 128)
lane'[i]           = (lane[i] ± expanded[i]) mod 2^16         + add, − subtract
```

Actualización entrante (`KmpSyncdCryptoHelper.A01`): para cada índice del patch, **restar** el `mutation_mac` almacenado del registro existente y luego **sumar** los MAC de valor de los SET. `checkLtHashConsistency` (`C17520jx`) reconstruye el hash a partir de todos los valores `mutation_mac` almacenados y lo compara con el hash almacenado (registra `ltHashFromMutations` / `ltHashFromDb`, últimos 16 caracteres hex salvo con el flag **624**); se ejecuta desde el cron diario cuando transcurren las horas del flag **1104** (por defecto 0 = desactivado) y tras un mismatch de MAC de snapshot con el flag **1783**.

**MACs** (found):

```
version8    = 8-byte big-endian version
snapshotMac = HMAC-SHA256(snapshotMacKey, ltHash(128) ‖ version8 ‖ UTF8(collection))
patchMac    = HMAC-SHA256(patchMacKey,   snapshotMac ‖ valueMac₁ ‖ … ‖ valueMacₙ ‖ version8 ‖ UTF8(collection))
```

`valueMacᵢ` = últimos 32 bytes de cada blob de valor, en el orden del patch. Saliente: version = almacenada + 1 para ambos MAC (`C50707Mbo(old + 1)`). El MAC de patch entrante usa el `snapshot_mac` que lleva el patch; el MAC de snapshot recalculado se compara por separado.

| Comprobación entrante | Mismatch |
|----------------|----------|
| MAC de patch | fatal `MacMismatchPatch` (32) |
| MAC de snapshot en un snapshot | fatal `SnapshotMacMismatchInSnapshot` (52) |
| MAC de snapshot en un patch | **no fatal** en la ruta KMP: `snapshot mac mismatch but do not throw fatal`, código de reporte no fatal 60, comprobación de consistencia opcional (**1783**); consumidor del flag devuelto sin resolver |
| `snapshot_mac` / `patch_mac` ausente | fatal `MissingSnapshotMac` (39) / `MissingPatchSnapshotMac` (40) / `MissingPatchMac` (41) |

---

## 7. Claves de sincronización

### 7.1 Clave, generación, clave activa (found)

| Elemento | Valor |
|------|-------|
| Key id (`CGH`) | 6 bytes: `deviceId` (2, BE) ‖ `epoch` (4, BE); `SyncdKeyId{deviceId=, epoch=}` |
| Datos de clave | 32 bytes aleatorios |
| Tabla `crypto_info` | `device_id, epoch, key_data, timestamp, fingerprint, stale_timestamp` |
| Fingerprint | `rawId`, `currentIndex`, `deviceIndexes` del estado de índice de claves ADV de la cuenta en el momento de la creación |
| Generación (`C12800bm.A05`) | `epoch = max(stored max, in-memory) + 1` (primero aleatorio en [0,65536) si es 0); solo si no hay un share recién generado en curso; sin otro dispositivo la clave se guarda de inmediato, de lo contrario se envía un share (peer 38, `isNewlyGeneratedKey=true`) a cada companion y la clave se persiste después de que ese mensaje fue **enviado** (`CXB.Bss`) |
| Clave activa | última fila de `crypto_info`, de menos de **14488** días (por defecto 30) y con fingerprint válido; si no, se crea una clave nueva en la siguiente escritura |
| Comprobación de fingerprint (`A0B`) | `rawId` igual al raw id ADV local; `deviceIndexes ∪ (currentIndex+1 … local currentIndex)` igual al conjunto local de device-index; si no, `one of a peer device is no longer registered` |
| Sentinel (`sentinel`, `KeyExpiration`) | `C25048AqM.A00` construye uno por colección (las cinco) con `expiredKeyEpoch` = epoch local más alto |
| `expireKeysWithEpochIfActive` (`A08`) | pone `timestamp = 0` en la última clave cuando su epoch ≤ el epoch dado; el llamador al recibir un sentinel no se trazó (inferred) |
| Claves stale | el cron diario marca las claves no referenciadas por `syncd_mutations`, las elimina tras **14496** días (por defecto 31) |
| Re-key | un registro almacenado bajo otra clave se reemplaza vía `findMutationWithExpiredKey`; la forma exacta REMOVE+SET es inferred |

### 7.2 Request y claves faltantes (found, `C12800bm.A07`)

1. Los key ids desconocidos se almacenan en `missing_keys(device_id, epoch, collection_name)` y se solicitan con mensajes peer de key request (tipo 39) a todos los demás dispositivos registrados, omitiendo ids ya pendientes (`missing_key_counter`).
2. El respondedor envía un share con las claves que tiene (`A0C`, `isNewlyGeneratedKey=false`).
3. Sin respuesta durante **14492** días (por defecto 7, mensaje peer tipo 39 más antiguo, cron diario) → fatal **31** (`TimeoutWhileWaitingForMissingKey`).
4. Nadie puede proporcionarla: `MissingKeyOnAllClients`; nadie a quien preguntar: `RequestingMissingKeyWithNoClients`; ninguna para cifrar: `MissingActiveKeyForEncryption`.

Los shares son payloads `ProtocolMessage` de mensajes peer cifrados de extremo a extremo (found). La validación de fingerprint de un share entrante en el lado receptor no se localizó (unknown).

---

## 8. Patches salientes y blobs externos

**Construcción** (found, `OutgoingProcessor`, `KmpSyncdEncryptionProcessor`): las mutaciones pendientes (`pending_mutations`, `is_ready_to_sync=1`) se dividen por colección; un índice repetido en un mismo patch se rechaza (`SameIndexForMultipleMutationsInOutgoingPatch`); se resuelve la clave activa; cada mutación se cifra (5.2); nuevo LT-Hash a partir del hash almacenado (6); `snapshotMac` / `patchMac` con versión almacenada + 1; `SyncdPatch{version, mutations | externalMutations, snapshotMac, patchMac, keyId, deviceIndex?, clientDebugData?}`; IQ (3.1); el resultado trae la nueva versión. `deviceIndex` (campo 8) lo gobierna el flag **14486**, true por defecto (consumidor no trazado).

**Regla de subida externa** (found, `OutgoingProcessor`): `(mutationCount > P14494 or bytes > P14495 × 1024) and bytes > P5097 × 1024`, valores por defecto 100 / 10 / 0, de modo que cualquier patch con más de 100 mutaciones o cerca de 10 KB va a externo. El blob es un mensaje `SyncdMutations`; el patch lleva entonces `externalMutations` y ninguna `mutations` inline (tener ambos se rechaza: `PatchWithBothInlineAndExternalMutations`). Errores de subida: `Upload transient network error`, `Upload local I/O failure`, `Upload failed`.

**Transporte del blob** (found, `C17650kB`, `C49831Lvs`, `C15530gU`):

| Elemento | Valor |
|------|-------|
| Tipo de media / info HKDF de la media key | `md-app-state` (ruta MMS `mms`) / `WhatsApp App State Keys` |
| Campos de referencia requeridos | mediaKey, directPath, fileSha256, fileEncSha256 (cada ausencia → `MissingExternalBlobReference*`) |
| Estado de descarga | 5 = expirado (`ExternalPatchExpired` 3 / `SnapshotExpired` 49, fatal); estados transitorios se reintentan; los demás son fatales |
| Contenido | patch externo → `SyncdMutations`; snapshot → `SyncdSnapshot` |

El layout compartido de expansión de la media key no se releyó aquí (inferred común).

**Datos de depuración** (found): `clientDebugData` = `PatchDebugData` (`C49633LsY`: `collection_name`, `current_lthash`, `new_lthash`, `new_lthash_subtract`, `patch_version`, `number_add/remove/override`, `sender_platform`, `is_sender_primary`, `first_four_bytes_from_a_hash_of_snapshot_mac_key`), escrito solo con el flag **6614** (por defecto false); el receptor lo registra tras un mismatch de MAC de patch.

---

## 9. Patches y snapshots entrantes

| # | Comprobación (found) | Fallo: tipo KMP (id) / código legacy |
|---|---------------|--------------------------------------|
| 1 | el patch tiene `version` | `MissingPatchVersion` (7) / 8 |
| 2 | sin versión duplicada en una misma respuesta | `DuplicatePatchVersionInCollection` (8) / 9 |
| 3 | no hay mutaciones inline y externas a la vez | `PatchWithBothInlineAndExternalMutations` (13) / 14 |
| 4 | `version == stored + 1` (`verifyCollectionVersion`) | `ServerDidNotSendAllPatches` (64) |
| 5 | `exit_code` del patch presente | legacy 36 (código 100), 37 (101), 38 (otro); contraparte KMP sin resolver |
| 6 | descifrar todas las mutaciones (5.3) | `DecryptionFailed` (6), tipos de forma |
| 7 | sin índice repetido entre SET ni entre REMOVE | `SameIndexForMultipleMutationsInPatch` (5) |
| 8 | ciclo de dependencia entre índices | `CyclicMutationDependencyInPatch` (37) |
| 9 | recalcular LT-Hash, MAC de patch, MAC de snapshot (6) | `MacMismatchPatch` (32) / no fatal |
| 10 | aplicar según el manejador de acción (SQLite), almacenar versión + hash | registra `Cyclic mutation dependency`, `SQLite error` |

Snapshots: solo un companion en bootstrap recibe uno (`Only companion devices that are undergoing bootstrap should receive and handle snapshots`). Descargar el blob, descifrar los registros como las mutaciones de patch, rechazar índices repetidos (`SameIndexForMultipleMutationsInSnapshot`, 59), reconstruir el hash, comparar `snapshot.mac`; luego aplicar los patches de `has_more_patches`. `applySnapshot keyMap contains null value, retry` vuelve a solicitar claves. Las mutaciones huérfanas (falta el chat padre) se almacenan con `are_dependencies_missing=1`, indexadas por `chat_jid`, y se reaplican más tarde (`SyncdCrossIndexDependencyUtil`).

---

## 10. Tipos de acción de sincronización

### 10.1 Catálogo (found, `EnumC24865AnN` + `AbstractC24863AnL.A00`)

Número = campo de `SyncActionValue` del valor; `-` = sin constante correspondiente en `BD4` (campo de valor desconocido). El elemento 0 del índice es el nombre en el wire; los demás elementos son específicos de cada acción y no se enumeran.

| Colección | Nombre en el wire = campo |
|------------|-------------------|
| `critical_block` (4) | `setting_securityNotification` -, `setting_pushName` 7, `setting_locale` 16, `generated_wui` 52 |
| `critical_unblock_low` (2) | `contact` 3, `lid_contact` 61 |
| `regular_high` (19) | `star` 2, `mute` 4, `deleteMessageForMe` 18, `clearChat` 21, `deleteChat` 22, `userStatusMute` 29, `ugc_bot` 43, `status_privacy` 44, `favorites` 56, `waffle_account_link_state` 58, `ctwaPerCustomerDataSharing` 62, `maiba_ai_features_control` 68, `status_post_opt_in_notification_preferences_action` 71, `private_processing_setting` 74, **`nct_salt_sync` 80**, `biz_ai_settings_nudge` 87, `wasa_root_secret` 89, `shared_device_allowlist` 94, `ai_thread_delete` - |
| `regular` (35) | `quick_reply` 8, `label_message` -, `label_edit` 14, `label_jid` 15, `primary_feature` 24, `deviceAgent` 27, `subscription` 28, `agentChatAssignment` 35, `agentChatAssignmentOpenedStatus` 36, `pnForLidChat` 37, `marketingMessage` 38, `marketingMessageBroadcast` 39, `external_web_beta` 40, `setting_relayAllCalls` 41, `call_log` 42, `delete_individual_call_log` 46, `label_reordering` 47, `setting_disableLinkPreviews` 53, `usernameChatStartMode` 59, `notificationActivitySetting` 60, `setting_channels_personalised_recommendation_optout` -, `broadcast_jid` -, `detected_outcomes_status_action` 66, `business_broadcast_list` 69, `music_user_id` 70, `avatar_updated_action` 72, `galaxy_flow_action` -, `newsletter_saved_interests` 75, `business_broadcast_campaign` 81, `business_broadcast_insights_sync` 82, `subscriptions_sync_v2` 84, `label_sublist` 91, `ctwa_message_received` 93, `shareOwnPn` -, `broadcast` - |
| `regular_low` (36) | `pin_v1` 5, `recent_emoji_weights_action` 11, `archive` 17, `sentinel` 19, `markChatAsRead` 20, `setting_unarchiveChats` 23, `android_unsupported_actions` 26, `time_format` 30, `nux` 31, `primary_version` 32, `favoriteSticker` 33, `removeRecentSticker` 34, `bot_welcome_request` 45, `payment_info` 48, `custom_payment_methods` 49, `lock` 50, `setting_chatLock` 51, `device_capabilities` 54, `note_edit` 55, `merchant_payment_partner` 57, `payment_tos` 63, `ai_thread_rename` 76, `interactive_message_action` 77, `settings_sync` 78, `out_contact` 79, `customer_data` 83, `thread_pin` 85, `setting_autoOrganizeBusinessChat` 86, `coexV2Version` 88, `lock_message` 90, `device_capabilities_v2` 92, `contact_manager_metadata` 95, `business_folder_activation` 96, `group_history_toggle` 97, `bb_pro_pending_customer_base_action` 98, `community_nesting_state` 99 |

`BD4` no tiene constante para los números de campo 6, 9, 10, 12, 13, 25, 65, 67, 73. Grupos por propósito (inferred a partir de los nombres): estado del chat (`mute`, `pin_v1`, `thread_pin`, `archive`, `markChatAsRead`, `clearChat`, `deleteChat`, `deleteMessageForMe`, `star`, `lock*`); labels (`label_*`); contactos (`contact`, `lid_contact`, `out_contact`, `pnForLidChat`, `shareOwnPn`); ajustes de cuenta (`setting_*`, `time_format`, `status_privacy`); claves y tokens (`sentinel`, `nct_salt_sync`, `wasa_root_secret`, `generated_wui`, `shared_device_allowlist`); business, IA, llamadas, pagos (el resto).

### 10.2 Valores seleccionados (found)

| Acción | Valor |
|--------|-------|
| `nct_salt_sync` (ordinal 73, `regular_high`) | `NctSaltSyncAction{bytes salt=1}` en el campo **80** de `SyncActionValue`; cómo el primario entrega el NCT salt a los companions, origen y uso en `WA_TCTOKEN_CSTOKEN.md` (3.2) |
| `contact` (`ContactAction`) | fullName 1, firstName 2, lidJid 3, saveOnPrimaryAddressbook 4, pnJid 5, username 6, birthday 7; creado solo por el primario, de modo que un companion en bootstrap recibe su libreta de direcciones antes que cualquier colección `regular*` |
| `mute` (`MuteAction`) | muted 1, muteEndTimestamp 2, autoMuted 3, muteEveryoneMentionEndTimestamp 4 |
| `sentinel` | `KeyExpiration{expiredKeyEpoch}` (7.1) |
| `android_unsupported_actions` (26), flag **14490** (por defecto false) | una ruta "Android unsupported mutation"; semántica desconocida |

---

## 11. Errores fatales, reintento y recuperación

### 11.1 Tipos fatales KMP (found, `Lx6.A00`; los ids son internos, no valores del wire)

| Grupo | Ids y nombres |
|-------|---------------|
| Transporte | 53 `XmppBadRequestForCollection`, 54 `…NotFoundForCollection`, 55 `XmppBadRequestGlobalError`, 56 `…NotFoundGlobalError`, 57 `…BadMethodGlobalError`, 58 `…NotAcceptableGlobalError` |
| Forma de patch / snapshot | 4 `MissingOrEmptyIndex`, 5 `SameIndexForMultipleMutationsInPatch`, 7 `MissingPatchVersion`, 8 `DuplicatePatchVersionInCollection`, 13 `PatchWithBothInlineAndExternalMutations`, 37 `CyclicMutationDependencyInPatch`, 38 `MissingSnapshotVersion`, 47 `MissingPatchKeyId`, 50 `MissingSnapshotKeyId`, 59 `SameIndexForMultipleMutationsInSnapshot`, 64 `ServerDidNotSendAllPatches`, 65 `ServerSentEarlierPatch`, 71 `InvalidSnapshotRecords` |
| Forma de mutación / acción | 10-12, 14-16, 19-24 (`MissingMutationVersion/Value/Index/Operation/Record/KeyId`, `MissingActionIndex/Value/Version/Timestamp`, `InvalidMutationIndex`, `InvalidActionIndex`) |
| Crypto | 6 `DecryptionFailed`, 9 `EncryptionFailed`, 31 `MacMismatchSnapshot`, 32 `MacMismatchPatch`, 39-41 `Missing*Mac`, 51 `SnapshotMacMismatchInPatch`, 52 `SnapshotMacMismatchInSnapshot` |
| Claves | 29 `MissingKeyOnAllClients`, 30 `TimeoutWhileWaitingForMissingKey`, 46 `InvalidKeyShareKeyId`, 48 `InvalidKeyShareKeyData`, 62, 66-69 (`RequestingMissingKeyWithNoClients`, `MissingKeyForMutationInLocalSnapshot`, `MissingActiveKeyAfterRotation`, `MissingActiveKeyForEncryption`, `MissingCurrentEpochForActiveKeyValidation`) |
| Blobs / protobuf | 3 `ExternalPatchExpired`, 49 `SnapshotExpired`, 42-45 y 72 `MissingExternalBlobReference*`, 60 / 61 fallo de parseo de referencia / snapshot, 17 / 18 / 25-28 tipos de (de)serialización, 34-36 `TerminalPatch*` |
| Local | 33 `DbStoreNotReady`, 63 `DbStoreNotReadyLowDiskSpace`, 70 `SameIndexForMultipleMutationsInOutgoingPatch` |

### 11.2 Códigos numéricos legacy (found, `C49784Lv2.errorCode`, alimentan WAM `md_fatal_error`; numeración separada)

8 / 9 / 14 (`N90`: sin versión / versión duplicada / inline + externo), 18 / 69 (fallo de parseo de patch / snapshot), 36 / 37 / 38 (`exit_code` 100 / 101 / otro), 64-67 (errores globales de IQ 400 / 404 / 405 / 406), 71 (falló la resolución de clave tras el request de clave faltante), 31 (timeout de espera de clave), 60 (mismatch de MAC de snapshot no fatal en un patch, `A0F(60, collection, false)`). El mapeo a los tipos KMP está sin resolver.

### 11.3 Reacción ante un fallo fatal (found, `SyncResponseHandler.A08`, `C12440bB.A0S/A0Q`)

| Rol | Acción |
|------|--------|
| Cualquiera | registrar `app-state-sync-handle-fatal-exception`, WAM `md_fatal_error`, limpiar la sincronización en curso |
| Flag **25799** | companion: `companion_syncd_dirty=true`; primario: `C17630k8.A01(1)` (motivo dirty 1, inferred) |
| Primario | `A0Q(1)` eliminar todos los datos de syncd. Máquina dirty (`C17630k8`, cadena desde `A0Q` inferred): contador `syncd_dirty` hasta 4, `syncd_dirty_reason`, `<iq xmlns="w:sync:app:state" type="set"><delete_all_data/></iq>` (atributo type inferred), `logoutAllCompanionDevices` |
| Companion | `companion_syncd_dirty=true`, mensaje peer `AppStateFatalExceptionNotification` (FMessage 50) al primario (device 0), espera de 5 s, logout con `syncd_failure` o `syncd_error_during_bootstrap` |

Ventana de reintento de delete-all **14493** minutos (por defecto 360). El primario limpia cuando un companion fue dado de baja y no queda ninguno (`shouldCleanUpSyncd`).

### 11.4 Recuperación de snapshot (found, `KmpSyncdFatalErrorRecovery`)

Condicionada por la client-prop `isSyncdSnapshotRecoveryEnabled`. El companion envía la peer data operation `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` (8) con `SyncDCollectionFatalRecoveryRequest{collectionName}`. El respondedor construye un `SyncdSnapshotRecovery` a partir de sus mutaciones **plaintext** almacenadas (`syncd_mutations`, `collection_versions.version / lt_hash`), lo comprime con gzip y devuelve `SyncDSnapshotFatalRecoveryResponse`. Rechazos: `Invalid collection name` (request para `critical_block`), `Collection version/ltHash invalid`, `Snapshot keyId invalid`, `Mutation count (…) more than the limit`, `Mutation snapshot data size (…) more than the limit`, `Error encoding mutation data`, `Compression failed` (props de límite no resueltas). El plaintext viaja dentro de un mensaje peer cifrado de extremo a extremo. La aplicación en el lado del companion no se trazó (unknown).

---

## 12. Estado local y feature flags

| Almacén | Contenido (found) |
|-------|-----------------|
| `syncd_mutations` | `mutation_index` (único), `mutation_value`, `mutation_version`, `collection_name`, `are_dependencies_missing`, `mutation_mac`, `device_id`, `epoch`, `chat_jid`, `mutation_name` |
| `collection_versions` / `pending_mutations` / `missing_keys` / `crypto_info` | `collection_name, version, lt_hash` / cola saliente (`is_ready_to_sync`) / requests de claves / claves de sincronización |
| Prefs | `syncd_bootstrap_state`, `companion_syncd_critical_bootstrap_state`, `syncd_dirty`, `syncd_dirty_reason`, `companion_syncd_dirty`, `syncd_last_companion_dereg_time`, `syncd_last_lthash_consistency_check_time`, `first_transient_server_failure_timestamp` |

El cron diario (`C46413KPv`) reporta los contadores `mutation_counter`, `invalid_action_counter`, `upload_conflict_counter`, `unsupported_action_counter`, `cross_index_conflict_counter`, `unset_action_mutation_counter`, `key_rotation_remove_counter`, `missing_key_counter`.

| Flag ID | Tipo / por defecto | Controla |
|---------|----------------|----------|
| **15909**, **20682**, **18234** | bool / false | `XplatSyncdEncryptionManager` frente al predeterminado (`AbstractC17550k0`); KMP entrante (`RunnableC53542Nwj`); KMP saliente (`C12440bB`). Solo valores por defecto compilados, valor en vivo desconocido. Nombre de 15909 en una build anterior: `KMP_SYNCD_ENGINE_CRYPTO_ENABLED` (reutilización de ID inferred) |
| **14488** / **14496** / **14492** | int / 30 / 31 / 7 | antigüedad de la clave activa, retención de claves stale, timeout de espera de clave (días) |
| **14493** | int / 360 | ventana de delete-all / dereg (minutos) |
| **14494**, **14495**, **5097** | int / 100, 10, 0 | umbrales de patch externo |
| **14497** | int / 1000 | límite de carga de mutaciones de DB (inferred) |
| **1104** / **1783** | int 0 / bool false | intervalo de comprobación de consistencia (h) / comprobación tras mismatch de MAC de snapshot |
| **6614** | bool / false | `clientDebugData` en patches |
| **25799** | bool / false | manejo del estado dirty ante un fallo fatal |
| **27528** | bool / false | generar una clave cuando el primario no tiene ninguna |
| **14486** | bool / true | `deviceIndex` en patches (consumidor no trazado) |
| **14489**, **14490**, **1221**, **624** | int 90 / bool false / bool false / bool | tope `min()` en `C15310g7` (sin resolver) / ruta de mutación no soportada / estadísticas de mutaciones / hashes completos en logs |

---

## 13. Casos de error

| Síntoma | Causa | Solución |
|---------|-------|-----|
| `Data MAC mismatch` | clave incorrecta, blob manipulado, byte op o keyId incorrectos en el AAD | clave indicada por `record.keyId`; AAD = `op ‖ keyId`, op 1 SET / 2 REMOVE |
| `Index MAC mismatch` | el string de índice difiere byte a byte (espaciado JSON) | calcular el MAC sobre el string UTF-8 exacto de `SyncActionData.index` |
| fatal 64 `ServerDidNotSendAllPatches` | versión del patch ≠ almacenada + 1 | resincronizar desde la versión almacenada; solicitar un snapshot si el estado se perdió |
| mismatch de MAC de patch (32) | deriva del LT-Hash, ancho de version8, MAC de snapshot de la fuente equivocada | usar primero el `snapshot_mac` del patch; versión como big-endian de 8 bytes |
| `PatchWithBothInlineAndExternalMutations` | ambos campos establecidos | enviar uno solo |
| `MissingActionTimestamp` | `SyncActionValue.timestamp` ausente en un SET | establecer el campo 1 |
| falta una clave | share no recibido | request tipo 39; fatal 31 tras 7 días |
| `one of a peer device is no longer registered` | la lista de dispositivos cambió desde la creación de la clave | la clave no es utilizable como clave activa; generar una nueva |
| error de IQ 400 / 404 / 405 / 406 | forma de request incorrecta, colección desconocida | fatal; corregir el request |
| `ExternalPatchExpired` / `SnapshotExpired` | estado de blob 5 | recuperación de snapshot o re-vinculación |
| logout del companion `syncd_failure` | fallo fatal irrecuperable | re-emparejar, o recuperación de snapshot si está habilitada |

---

## 14. Distinciones clave

| No confundir | Con |
|----------------|------|
| Sync key (32 bytes aleatorios por dispositivo+epoch) | claves de mutación (salida de HKDF, cinco segmentos) |
| MAC de índice (HMAC-SHA256 sobre el string de índice) | MAC de valor (HMAC-SHA512 truncado a 32 sobre AAD + iv + ct + len) |
| MAC de valor (por mutación) | MAC de snapshot (LT-Hash + versión + colección) y MAC de patch (MAC de snapshot + todos los MAC de valor) |
| nodo `<snapshot>` (un `ExternalBlobReference`) | proto `SyncdSnapshot` (el contenido del blob); igualmente `externalMutations` frente a `SyncdMutations` |
| `critical_block` en Android (ajustes de cuenta) | una colección de lista de bloqueo (no encontrada) |
| tipos de `ProtocolMessage` 6 / 7 / 10 | números de campo 7 / 8 / 10 |
| campo 7 del request de peer data | campo 8 de la respuesta de peer data |
| ids de tipo KMP (`Lx6`) | ints legacy `errorCode` |
| `sentinel` (marcador de expiración de claves en las cinco colecciones) | `primary_version`, `android_unsupported_actions` |
| tablas de acciones / colecciones de WhatsApp Web | la tabla de Android aquí (96 acciones, asignación distinta) |

---

## 15. Baileys (`baron-baileys-v2` 1.5.17)

Solo hechos leídos en `src/Utils/chat-utils.js`, `src/Socket/chats.js`, `src/Utils/process-message.js`. Nada se probó contra un servidor; no se afirma ningún fallo.

| Tema | Baileys | Android |
|-------|---------|---------|
| Expansión de claves, LT-Hash | bridge nativo `expandAppStateKeys`, `LTHashAntiTampering` (128 bytes); mismos cinco nombres de segmento | 5.1, 6 |
| MAC de valor | `HMAC-SHA512(op ‖ keyId ‖ data ‖ 8 bytes, last = len)[0..32)`, op 1 / 2 | idéntico |
| MAC de snapshot / patch | mismas entradas y orden; `ver8` escribe solo los 32 bits bajos | big-endian completo de 64 bits |
| Índice, padding | `JSON.stringify(index)`, padding vacío | igual |
| Blob externo | `downloadContentFromMessage(blob, 'md-app-state')` | mismo tipo de media |
| Colecciones | `critical_block, critical_unblock_low, regular_high, regular_low, regular` | mismos nombres |
| Nodo de request | `<sync>` sin atributos; `<collection name version return_snapshot>`, `return_snapshot` siempre `'true'`/`'false'` | `data_namespace="3"`, `order`, `return_snapshot` solo cuando es true |
| Envío de patch | `version = state.version − 1`, `return_snapshot='false'` | versión almacenada |
| Continuidad de versión | no se comprueba (`newState.version = patchVersion`); una versión de patch ausente pasa a ser versión de colección + 1 | debe ser igual a almacenada + 1 |
| MAC de snapshot en un patch | recalculado, lanza `failed to verify LTHash` | no fatal en la ruta KMP |
| Key share | almacena solo `keyData` por key id en base64; `myAppStateKeyId` = última clave del mensaje | conserva fingerprint y timestamp, verifica el fingerprint, elige la última clave válida |
| Notificación fatal | registrada, emitida como `app-state.sync-error` | el companion envía, el primario actúa |
| Reintento | `MAX_SYNC_ATTEMPTS = 2`, reintento con snapshot forzado, una clave faltante aparca la colección | sección 11 |
| NCT salt | `nctSaltSyncAction.salt` almacenado como `nct-salt` | 10.2 |

No presentes en el código fuente de Baileys: `data_namespace`, `order`, manejo de `exit_code`, recuperación de snapshot. El efecto en el servidor es desconocido.

---

## 16. Flujos completos

### 16.1 El primario escribe un cambio (ejemplo `mute`)

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

### 16.2 El companion hace pull

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

### 16.3 Fallo fatal

```
[Companion]  patch MAC mismatch / key timeout / version gap
     ├─ recovery enabled ─► peer data op 8 {collectionName} ─► [Primary] SyncdSnapshotRecovery (gzip)
     └─ else companion_syncd_dirty ; peer AppStateFatalExceptionNotification ; 5 s ; logout syncd_failure
               ▼
         [Primary]  delete syncd data ; iq <delete_all_data/> ; logout companions ; re-pair
```

---

## 17. Desconocidos

| Elemento | Estado |
|------|--------|
| Motor activo (legacy o KMP) por cuenta | flags del servidor |
| Significado del atributo `order` | unknown |
| Comprobación de fingerprint en el lado receptor de un key share entrante | no localizada |
| Lado de aplicación de un `sentinel` recibido (`expireKeysWithEpochIfActive`) | no trazado |
| Mapeo tipo KMP ↔ código legacy; disparador de `ServerSentEarlierPatch`; significado de `exit_code` 100 / 101 | sin resolver |
| Campo de valor de las 9 acciones marcadas con `-` | unknown |
| Lado de aplicación de la recuperación de snapshot, props de límite | no trazado |
| Ordenamiento, retención y reglas de merge del servidor | lado del servidor |
| Tráfico | nada capturado |
