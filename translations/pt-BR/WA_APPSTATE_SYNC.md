<!-- src-sha1: f9c1d644c604d99d2f1b54082218c3f75d2cf8a7 -->
# WhatsApp App-State Sync — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** sincronização de app-state (syncd) no Android: cinco coleções, IQ `w:sync:app:state`, patches / snapshots / blobs externos, mutações SET/REMOVE, derivação de chaves de mutação e criptografia de registros, MACs de índice / valor, LT-Hash, MACs de snapshot e patch, chaves de sincronização (geração, compartilhamento, requisição, expiração), validação de saída e entrada, catálogo de sync actions (96 ações: chat, label, contact, nctSalt …), tratamento de falhas fatais e retentativas, recuperação de snapshot, feature flags, comparação com o Baileys

---

## 1. O que é (tecnicamente)

A sincronização de app-state replica pequenos estados por conta (silenciar, fixar, arquivar, favoritar, contatos, labels, configurações …) entre o telefone primário e cada dispositivo vinculado. O servidor armazena apenas registros criptografados de ponta a ponta, ordena-os por coleção e entrega patches versionados. Todas as afirmações vêm de análise estática do APK decompilado; nada foi capturado na rede. Tier: **found** = lido no código, **inferred** = deduzido do código, **unknown** = não resolvido. Os nomes ofuscados foram re-resolvidos na 2.26.41.6 a partir de strings estáveis (`WhatsApp Mutation Keys`, `WhatsApp Patch Integrity`, `w:sync:app:state`, nomes de coleções, prefixos de log).

| Entidade | Nome na 2.26.41.6 | Função |
|----------|-------------------|--------|
| Sync manager | `C12440bB` (`sync-manager/*`) | agendamento, falha fatal `A0S`, `A0Q` apagar todos os dados |
| Request handler / construtor de IQ / parser | `C53148Nnt` / `C46361ux` / `N90` | enviar IQ, montar `<sync>`, interpretar o resultado |
| Response handler legado | `SyncResponseHandler` (`consumer/companiondevice/p049iq`) | caminho legado de aplicação, tratamento de fatal `A08` |
| Engine KMP | `com.whatsapp.kmp.syncd.syncdengine.*` | `OutgoingProcessor`, `IncomingProcessor`, `SyncdResponseHandler`, `SyncdResponseProcessor`, `CollectionHandler`, `crypto/*` |
| Enum de coleções / enum de ações | `EnumC24862AnK` / `EnumC24865AnN` | 5 coleções / 96 nomes de ações no wire |
| Ação para coleção | `AbstractC24863AnL.A00` | switch por ordinal |
| Base de mutação / base de handler | `AbstractC24864AnM` / `AbstractC25077Aqp` | mutação pendente / handler de ação |
| Gerenciador / armazenamento de chaves | `C12800bm` (`SyncdKeyManager`) / `C13620d6` (tabela `crypto_info`) | gerar, compartilhar, requisitar, expirar, persistir chaves |
| ID da chave / chave / dados da chave | `CGH` / `C51259MoT` / `C51361MqC` | id de 6 bytes / id + dados / dados, fingerprint `C8H`, ts |
| Chaves de mutação | `MhX` | saída do HKDF, 5 fatias |
| Carriers de compartilhamento / requisição | `C26102BPk` (FMessage 38) / `C26101BPj` (39) | mensagens peer |
| LT-Hash, HKDF | `AbstractC50511MVx.A00` + `KmpLtHash16`, `AbstractC38961i0` | hash de 128 bytes, RFC 5869 |
| Cripto (legado / KMP) | `C52959NkE` / `KmpSyncdCryptoHelper`, `KmpSyncdEncryptor`, `KmpSyncdDecryptor`, `KmpSyncdIncomingAntiTamperingValidator` | fórmulas idênticas |
| Blobs externos | `C17650kB` (download), `KmpExternalMutationsUploaderImpl` | tipo MMS `md-app-state` |
| Bootstrap / delete-all / recuperação | `C24986ApL` / `C17630k8` / `KmpSyncdFatalErrorRecovery` | máquina de estados, `delete_all_data`, entrega de snapshot |
| Tipos de fatal / exceção legada | `Lx6` / `C49784Lv2` | 70 tipos nomeados / `errorCode` int |

Duas implementações do mesmo protocolo coexistem. A engine KMP é selecionada por três booleanos controlados pelo servidor, cujos valores padrão compilados são **false** (**15909** cripto, **20682** entrada, **18234** saída, seção 12). Qual caminho uma conta executa é unknown. As fórmulas de MAC e de criptografia são idênticas em ambos (comparadas em `C52959NkE` e `KmpSyncd*`).

Primário e companion executam o mesmo código. Diferenças encontradas: apenas um primário cria mutações `contact` / `lid_contact` (`Companion cannot create contact mutations`); apenas um companion envia `return_snapshot="true"`; o tratamento de fatal difere (11.3).

---

## 2. Coleções

| Nome no wire | Ordinal do enum | Crítica | Bit de log (`C17530jy.A00`) | Ações |
|--------------|-----------------|---------|-----------------------------|-------|
| `regular` | 0 | não | 3 | 35 |
| `regular_low` | 1 | não | 5 | 36 |
| `regular_high` | 2 | não | 4 | 19 |
| `critical_block` | 3 | sim | 1 | 4 |
| `critical_unblock_low` | 4 | sim | 2 | 2 |

Conjunto crítico = `{critical_block, critical_unblock_low}` (`EnumC24862AnK.A01`). `A00()` mapeia o ordinal para 1..5; consumidor não rastreado.

No Android, `critical_block` contém ações de configuração da conta (`setting_pushName`, `setting_locale`, `setting_securityNotification`, `generated_wui`), **não** uma lista de bloqueio; `contact` e `lid_contact` ficam em `critical_unblock_low`. Nenhuma ação do enum de 96 entradas tem nome relacionado a bloqueio (found).

**Bootstrap (companion, parcialmente inferred).** `syncd_bootstrap_state` (`C24986ApL`) percorre 0 → 4. Found: conjunto crítico sincronizado → estado 2 e um sinal de "critical blocking complete"; todas as coleções não críticas sincronizadas → estado 4; o estado 3 é a etapa de history sync (inferred). Motivos de falha: `critical_sync_timeout`, `history_sync_failure`, `syncd_failure`; log do watchdog `syncd-critical-bootstrap-timeout`. No primário, o pareamento de um companion executa `prepareCriticalDataUpload`: history sync, depois `shareAllKeys`; sem chave e com a flag **27528**, uma chave é gerada primeiro.

---

## 3. Camada IQ

### 3.1 Requisição (found, `C46361ux`)

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
|----------|-------|
| `data_namespace` | constante `3` em `<sync>` |
| `order` | `0` para `critical_unblock_low`, `1` nos demais; significado unknown |
| `version` | versão da coleção armazenada localmente (`C17540jz.A02`); omitido se não houver |
| `return_snapshot` | `"true"` apenas para um companion com versão null ou 0 |
| `<patch>` | somente quando há mutações locais pendentes |
| `<coex><bot>` | coexistence-v2: as chaves de sincronização usadas são criptografadas para um bot (`sync-request-handler/coexv2 *`); em caso de falha o IQ segue sem ele e as chaves são compartilhadas fora de banda |

Timeout de 32 s; um IQ pode carregar várias coleções.

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

`<sync>` ausente ou um corpo `<snapshot>` / `<patch>` vazio → falha transitória. Uma coleção sem versão, patches nem snapshot é mantida como um nome simples (significado inferred: nada novo). Os corpos de snapshot são sempre um `ExternalBlobReference`, nunca registros inline.

Erros de coleção (`M4T`): -1 `UNKNOWN` com nova tentativa; 400 / 404 / 405 / 406 fatal (`Xmpp*ForCollection`); 409 `CONFLICT` aplica os patches anexados e tenta de novo, caso contrário permite nova tentativa (condição do branch ambígua no decompilado); 500 com nova tentativa.

Erro global de IQ (`C53148Nnt.Brt`, `backoff` em segundos):

| Código | Tratamento |
|--------|------------|
| 400, 404, 405, 406 | fatal; códigos legados 64, 65, 66, 67; tipos KMP 55-58 |
| demais 4xx | sem nova tentativa, `client_error:<code>` |
| 5xx | nova tentativa após `max(server backoff, client delay)`, `server_error:<code>` |
| outros | `global_error:<code>` |

Falhas transitórias com mais de 7 dias (`first_transient_server_failure_timestamp` > 604 800 000 ms) escalam para fatal. Outros motivos não fatais: `network_error`, `sqlite_full`, `unexpected_error`, `mms_local_io`, `mms_upload`.

---

## 4. Mensagens protobuf

Os números foram recuperados das classes da 2.26.41.6, conferidos com a ordem de declaração e, quando presentes, com as constantes `*_FIELD_NUMBER` geradas (`*`).

| Mensagem (classe) | Campos (número) |
|-------------------|-----------------|
| `SyncdPatch` (`C49631LsW`, lite `Lp6`) | version **1** `SyncdVersion{uint64=1}`, mutations **2**, externalMutations **3** `ExternalBlobReference`, snapshotMac **4**, patchMac **5**, keyId **6** `KeyId{bytes id=1}`, exitCode **7** `ExitCode{uint64 code=1; string text=2}`, deviceIndex **8**, clientDebugData **9** |
| `SyncdMutation` (`C49601Ls2`) | operation **1** (`SET`=0, `REMOVE`=1), record **2** |
| `SyncdRecord` (`C49610LsB`) | index **1** `SyncdIndex{bytes blob=1}` (MAC de índice), value **2** `SyncdValue{bytes blob=1}`, keyId **3** |
| `SyncdMutations` (`C49583Lrk`) | mutations **1** (corpo de patch externo) |
| `SyncdSnapshot` (`C49617LsI`, lite `C49419Lob`) | version **1**, records **2**, mac **3**, keyId **4** |
| `SyncActionData` (`C49612LsD`) | index **1** (array de strings JSON em UTF-8), value **2** `SyncActionValue` (`BD4`), padding **3** (sempre vazio), version **4** int32 |
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
| `SyncActionValue` (`BD4`) * | timestamp **1** (int64; um SET sem ele falha), um campo por ação (10.1) |

Carriers (found, `*`): `ProtocolMessage` (`BD3`) `appStateSyncKeyShare` campo **7** / tipo **6**, `appStateSyncKeyRequest` campo **8** / tipo **7**, `appStateFatalExceptionNotification` campo **10** / tipo **10** (`EnumC26463Bdz`). `PeerDataOperationRequestMessage.syncdCollectionFatalRecoveryRequest` campo **7**, tipo de requisição `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` = **8** (`EnumC26460Bdv`); resposta `syncdSnapshotFatalRecoveryResponse` campo **8** (`C25828BCm`). Client-props do companion (`C43107IrI`): `isSyncdPureLidSession` **2**, `isSyncdSnapshotRecoveryEnabled` **3**. Números internos de FMessage: compartilhamento de chave **38**, requisição de chave **39**, notificação fatal **50**. Compartilhamento e requisição trafegam como mensagens peer para um único `DeviceJid` (`SendPeerMessageJob`), prioridade do compartilhamento `high`.

---

## 5. Chaves de mutação e criptografia de registros

### 5.1 Derivação de chaves (found, `MhX`, igual em `C52959NkE`)

```
expanded = HKDF-SHA256(ikm = keyData(32), salt = 32 × 0x00, info = "WhatsApp Mutation Keys", L = 160)
```

| Bytes | Campo de `MhX` | Uso |
|-------|----------------|-----|
| 0-31 | `A00` | chave de índice, HMAC-SHA256 |
| 32-63 | `A03` | chave de criptografia do valor, AES-256-CBC |
| 64-95 | `A04` | chave de MAC do valor, HMAC-SHA512 |
| 96-127 | `A02` | chave de MAC do snapshot, HMAC-SHA256 |
| 128-159 | `A01` | chave de MAC do patch, HMAC-SHA256 |

O HKDF é `AbstractC38961i0.A00`: extract = `HMAC-SHA256(32 zero bytes, ikm)`, expand conforme a RFC 5869. `C17930kd` mantém em cache objetos `MhX` (5 entradas, inferred). A chave de sincronização é aleatória (seção 7), não derivada de chaves Signal.

### 5.2 Criptografar uma mutação (found, `KmpSyncdEncryptor`, `C52959NkE`)

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

O comprimento do padding é `max(0, −indexLen − valueLen)`, sempre vazio. Blob mínimo de 48 bytes. SET→0x01 pressupõe que a constante de operação local é 0 para SET (inferred; SET no wire = 0). O conteúdo de valor de um REMOVE é inferred vazio (branch `mqt != null`).

### 5.3 Descriptografar (found, `KmpSyncdDecryptor`)

| Etapa | Verificação | Falha |
|-------|-------------|-------|
| 1 | dividir `iv = [0..16)`, `ct = [16..n−32)`, `mac = [n−32..n)` | `Cipher text too short` |
| 2 | resolver a chave por `record.keyId` | erros de chave (7.2) |
| 3 | recalcular o MAC do valor, comparar | `Data MAC mismatch` (`DecryptionFailed`) |
| 4 | descriptografar AES-CBC, interpretar `SyncActionData` | `ActionDataProtobufDeserializationFailed` |
| 5 | índice, versão, (SET) valor e timestamp presentes | `MISSING_INDEX`, `MISSING_VERSION`, `MISSING_VALUE`, `MISSING_ACTION_TIMESTAMP` |
| 6 | o índice é um `String[]` JSON, não vazio, sem elemento vazio | `keyArray length should have action name` |
| 7 | recalcular o MAC de índice sobre a string de índice | `Index MAC mismatch` |

O MAC do valor é verificado antes da descriptografia, o MAC de índice por último. A ação é então resolvida pelo elemento 0 (`Unknown mutation name:`).

---

## 6. LT-Hash, MAC de snapshot e MAC de patch

**LT-Hash** (found, `AbstractC50511MVx`, `KmpLtHash16`): 128 bytes lidos como 64 lanes u16 little-endian; vazio = 128 bytes zero.

```
expanded(valueMac) = HKDF-SHA256(ikm = valueMac(32), salt = 32 × 0x00, info = "WhatsApp Patch Integrity", L = 128)
lane'[i]           = (lane[i] ± expanded[i]) mod 2^16         + add, − subtract
```

Atualização de entrada (`KmpSyncdCryptoHelper.A01`): para cada índice no patch, **subtrair** o `mutation_mac` armazenado do registro existente, depois **somar** os MACs de valor dos SETs. `checkLtHashConsistency` (`C17520jx`) reconstrói o hash a partir de todos os valores `mutation_mac` armazenados e o compara com o hash armazenado (registra `ltHashFromMutations` / `ltHashFromDb`, últimos 16 caracteres hex, a menos que a flag **624**); é executado pelo cron diário quando passaram as horas da flag **1104** (padrão 0 = desligado) e após um mismatch de MAC de snapshot com a flag **1783**.

**MACs** (found):

```
version8    = 8-byte big-endian version
snapshotMac = HMAC-SHA256(snapshotMacKey, ltHash(128) ‖ version8 ‖ UTF8(collection))
patchMac    = HMAC-SHA256(patchMacKey,   snapshotMac ‖ valueMac₁ ‖ … ‖ valueMacₙ ‖ version8 ‖ UTF8(collection))
```

`valueMacᵢ` = 32 bytes finais de cada blob de valor, na ordem do patch. Saída: versão = armazenada + 1 para ambos os MACs (`C50707Mbo(old + 1)`). O MAC de patch de entrada usa o `snapshot_mac` carregado no patch; o MAC de snapshot recalculado é comparado separadamente.

| Verificação de entrada | Mismatch |
|------------------------|----------|
| MAC de patch | fatal `MacMismatchPatch` (32) |
| MAC de snapshot em um snapshot | fatal `SnapshotMacMismatchInSnapshot` (52) |
| MAC de snapshot em um patch | **não fatal** no caminho KMP: `snapshot mac mismatch but do not throw fatal`, código de relatório não fatal 60, verificação de consistência opcional (**1783**); consumidor da flag retornada não resolvido |
| `snapshot_mac` / `patch_mac` ausente | fatal `MissingSnapshotMac` (39) / `MissingPatchSnapshotMac` (40) / `MissingPatchMac` (41) |

---

## 7. Chaves de sincronização

### 7.1 Chave, geração, chave ativa (found)

| Item | Valor |
|------|-------|
| ID da chave (`CGH`) | 6 bytes: `deviceId` (2, BE) ‖ `epoch` (4, BE); `SyncdKeyId{deviceId=, epoch=}` |
| Dados da chave | 32 bytes aleatórios |
| Tabela `crypto_info` | `device_id, epoch, key_data, timestamp, fingerprint, stale_timestamp` |
| Fingerprint | `rawId`, `currentIndex`, `deviceIndexes` do estado do índice de chaves ADV da conta na criação |
| Geração (`C12800bm.A05`) | `epoch = max(stored max, in-memory) + 1` (aleatório em [0,65536) primeiro se 0); somente se não houver um compartilhamento recém-gerado em andamento; sem outro dispositivo a chave é salva de imediato, caso contrário um compartilhamento (peer 38, `isNewlyGeneratedKey=true`) vai para cada companion e a chave é persistida depois que essa mensagem foi **enviada** (`CXB.Bss`) |
| Chave ativa | última linha de `crypto_info`, com menos de **14488** dias (padrão 30) e fingerprint válido, senão uma nova chave é criada na próxima escrita |
| Verificação de fingerprint (`A0B`) | `rawId` igual ao raw id ADV local; `deviceIndexes ∪ (currentIndex+1 … local currentIndex)` igual ao conjunto local de device-index; senão `one of a peer device is no longer registered` |
| Sentinel (`sentinel`, `KeyExpiration`) | `C25048AqM.A00` cria um por coleção (as cinco) com `expiredKeyEpoch` = maior epoch local |
| `expireKeysWithEpochIfActive` (`A08`) | define `timestamp = 0` na última chave quando seu epoch ≤ o epoch informado; chamador ao receber um sentinel não rastreado (inferred) |
| Chaves obsoletas | o cron diário marca chaves não referenciadas por `syncd_mutations`, apaga após **14496** dias (padrão 31) |
| Re-key | um registro armazenado sob outra chave é substituído via `findMutationWithExpiredKey`; formato exato REMOVE+SET inferred |

### 7.2 Requisição e chaves ausentes (found, `C12800bm.A07`)

1. IDs de chave desconhecidos são armazenados em `missing_keys(device_id, epoch, collection_name)` e requisitados com mensagens peer de key-request (tipo 39) para todos os outros dispositivos registrados, ignorando ids já pendentes (`missing_key_counter`).
2. O respondente envia um compartilhamento com as chaves que possui (`A0C`, `isNewlyGeneratedKey=false`).
3. Sem resposta por **14492** dias (padrão 7, mensagem peer tipo 39 mais antiga, cron diário) → fatal **31** (`TimeoutWhileWaitingForMissingKey`).
4. Ninguém pode fornecê-la: `MissingKeyOnAllClients`; ninguém a quem perguntar: `RequestingMissingKeyWithNoClients`; nenhuma para criptografia: `MissingActiveKeyForEncryption`.

Os compartilhamentos são payloads `ProtocolMessage` de mensagens peer criptografadas de ponta a ponta (found). A validação de fingerprint no lado do receptor de um compartilhamento recebido não foi localizada (unknown).

---

## 8. Patches de saída e blobs externos

**Construção** (found, `OutgoingProcessor`, `KmpSyncdEncryptionProcessor`): as mutações pendentes (`pending_mutations`, `is_ready_to_sync=1`) são divididas por coleção; um índice repetido em um patch é rejeitado (`SameIndexForMultipleMutationsInOutgoingPatch`); chave ativa resolvida; cada mutação criptografada (5.2); novo LT-Hash a partir do hash armazenado (6); `snapshotMac` / `patchMac` com versão armazenada + 1; `SyncdPatch{version, mutations | externalMutations, snapshotMac, patchMac, keyId, deviceIndex?, clientDebugData?}`; IQ (3.1); o resultado traz a nova versão. `deviceIndex` (campo 8) é controlado pela flag **14486**, padrão true (consumidor não rastreado).

**Regra de upload externo** (found, `OutgoingProcessor`): `(mutationCount > P14494 or bytes > P14495 × 1024) and bytes > P5097 × 1024`, padrões 100 / 10 / 0, portanto qualquer patch acima de 100 mutações ou cerca de 10 KB vai para externo. O blob é uma mensagem `SyncdMutations`; o patch então carrega `externalMutations` e nenhum `mutations` inline (ambos presentes é rejeitado: `PatchWithBothInlineAndExternalMutations`). Erros de upload: `Upload transient network error`, `Upload local I/O failure`, `Upload failed`.

**Transporte do blob** (found, `C17650kB`, `C49831Lvs`, `C15530gU`):

| Item | Valor |
|------|-------|
| Tipo de mídia / info do HKDF da media key | `md-app-state` (caminho MMS `mms`) / `WhatsApp App State Keys` |
| Campos obrigatórios da referência | mediaKey, directPath, fileSha256, fileEncSha256 (cada ausência → `MissingExternalBlobReference*`) |
| Status de download | 5 = expirado (`ExternalPatchExpired` 3 / `SnapshotExpired` 49, fatal); status transitórios com nova tentativa; demais fatais |
| Conteúdo | patch externo → `SyncdMutations`; snapshot → `SyncdSnapshot` |

O layout compartilhado de expansão da media key não foi relido aqui (inferred comum).

**Dados de depuração** (found): `clientDebugData` = `PatchDebugData` (`C49633LsY`: `collection_name`, `current_lthash`, `new_lthash`, `new_lthash_subtract`, `patch_version`, `number_add/remove/override`, `sender_platform`, `is_sender_primary`, `first_four_bytes_from_a_hash_of_snapshot_mac_key`), escrito somente com a flag **6614** (padrão false); o receptor o registra após um mismatch de MAC de patch.

---

## 9. Patches de entrada e snapshots

| # | Verificação (found) | Falha: tipo KMP (id) / código legado |
|---|---------------------|--------------------------------------|
| 1 | o patch tem `version` | `MissingPatchVersion` (7) / 8 |
| 2 | sem versão duplicada em uma resposta | `DuplicatePatchVersionInCollection` (8) / 9 |
| 3 | não há mutações inline e externas ao mesmo tempo | `PatchWithBothInlineAndExternalMutations` (13) / 14 |
| 4 | `version == stored + 1` (`verifyCollectionVersion`) | `ServerDidNotSendAllPatches` (64) |
| 5 | `exit_code` do patch presente | legado 36 (código 100), 37 (101), 38 (outro); equivalente KMP não resolvido |
| 6 | descriptografar todas as mutações (5.3) | `DecryptionFailed` (6), tipos de formato |
| 7 | nenhum índice repetido entre SETs nem entre REMOVEs | `SameIndexForMultipleMutationsInPatch` (5) |
| 8 | ciclo de dependência entre índices | `CyclicMutationDependencyInPatch` (37) |
| 9 | recalcular LT-Hash, MAC de patch, MAC de snapshot (6) | `MacMismatchPatch` (32) / não fatal |
| 10 | aplicar por handler de ação (SQLite), armazenar versão + hash | registra `Cyclic mutation dependency`, `SQLite error` |

Snapshots: apenas um companion em bootstrap recebe um (`Only companion devices that are undergoing bootstrap should receive and handle snapshots`). Baixar o blob, descriptografar os registros como mutações de patch, rejeitar índices repetidos (`SameIndexForMultipleMutationsInSnapshot`, 59), reconstruir o hash, comparar `snapshot.mac`; depois aplicar os patches de `has_more_patches`. `applySnapshot keyMap contains null value, retry` requisita as chaves de novo. Mutações órfãs (chat pai ausente) são armazenadas com `are_dependencies_missing=1`, indexadas por `chat_jid`, e reaplicadas depois (`SyncdCrossIndexDependencyUtil`).

---

## 10. Tipos de sync action

### 10.1 Catálogo (found, `EnumC24865AnN` + `AbstractC24863AnL.A00`)

Número = campo de `SyncActionValue` do valor; `-` = sem constante correspondente em `BD4` (campo do valor unknown). O elemento 0 do índice é o nome no wire; os demais elementos são específicos de cada ação e não são enumerados.

| Coleção | Nome no wire = campo |
|---------|----------------------|
| `critical_block` (4) | `setting_securityNotification` -, `setting_pushName` 7, `setting_locale` 16, `generated_wui` 52 |
| `critical_unblock_low` (2) | `contact` 3, `lid_contact` 61 |
| `regular_high` (19) | `star` 2, `mute` 4, `deleteMessageForMe` 18, `clearChat` 21, `deleteChat` 22, `userStatusMute` 29, `ugc_bot` 43, `status_privacy` 44, `favorites` 56, `waffle_account_link_state` 58, `ctwaPerCustomerDataSharing` 62, `maiba_ai_features_control` 68, `status_post_opt_in_notification_preferences_action` 71, `private_processing_setting` 74, **`nct_salt_sync` 80**, `biz_ai_settings_nudge` 87, `wasa_root_secret` 89, `shared_device_allowlist` 94, `ai_thread_delete` - |
| `regular` (35) | `quick_reply` 8, `label_message` -, `label_edit` 14, `label_jid` 15, `primary_feature` 24, `deviceAgent` 27, `subscription` 28, `agentChatAssignment` 35, `agentChatAssignmentOpenedStatus` 36, `pnForLidChat` 37, `marketingMessage` 38, `marketingMessageBroadcast` 39, `external_web_beta` 40, `setting_relayAllCalls` 41, `call_log` 42, `delete_individual_call_log` 46, `label_reordering` 47, `setting_disableLinkPreviews` 53, `usernameChatStartMode` 59, `notificationActivitySetting` 60, `setting_channels_personalised_recommendation_optout` -, `broadcast_jid` -, `detected_outcomes_status_action` 66, `business_broadcast_list` 69, `music_user_id` 70, `avatar_updated_action` 72, `galaxy_flow_action` -, `newsletter_saved_interests` 75, `business_broadcast_campaign` 81, `business_broadcast_insights_sync` 82, `subscriptions_sync_v2` 84, `label_sublist` 91, `ctwa_message_received` 93, `shareOwnPn` -, `broadcast` - |
| `regular_low` (36) | `pin_v1` 5, `recent_emoji_weights_action` 11, `archive` 17, `sentinel` 19, `markChatAsRead` 20, `setting_unarchiveChats` 23, `android_unsupported_actions` 26, `time_format` 30, `nux` 31, `primary_version` 32, `favoriteSticker` 33, `removeRecentSticker` 34, `bot_welcome_request` 45, `payment_info` 48, `custom_payment_methods` 49, `lock` 50, `setting_chatLock` 51, `device_capabilities` 54, `note_edit` 55, `merchant_payment_partner` 57, `payment_tos` 63, `ai_thread_rename` 76, `interactive_message_action` 77, `settings_sync` 78, `out_contact` 79, `customer_data` 83, `thread_pin` 85, `setting_autoOrganizeBusinessChat` 86, `coexV2Version` 88, `lock_message` 90, `device_capabilities_v2` 92, `contact_manager_metadata` 95, `business_folder_activation` 96, `group_history_toggle` 97, `bb_pro_pending_customer_base_action` 98, `community_nesting_state` 99 |

`BD4` não tem constante para os números de campo 6, 9, 10, 12, 13, 25, 65, 67, 73. Grupos por finalidade (inferred a partir dos nomes): estado do chat (`mute`, `pin_v1`, `thread_pin`, `archive`, `markChatAsRead`, `clearChat`, `deleteChat`, `deleteMessageForMe`, `star`, `lock*`); labels (`label_*`); contatos (`contact`, `lid_contact`, `out_contact`, `pnForLidChat`, `shareOwnPn`); configurações da conta (`setting_*`, `time_format`, `status_privacy`); chaves e tokens (`sentinel`, `nct_salt_sync`, `wasa_root_secret`, `generated_wui`, `shared_device_allowlist`); business, IA, chamadas, pagamentos (o restante).

### 10.2 Valores selecionados (found)

| Ação | Valor |
|------|-------|
| `nct_salt_sync` (ordinal 73, `regular_high`) | `NctSaltSyncAction{bytes salt=1}` no campo **80** de `SyncActionValue`; é como o primário entrega o salt NCT aos companions, origem e uso em `WA_TCTOKEN_CSTOKEN.md` (3.2) |
| `contact` (`ContactAction`) | fullName 1, firstName 2, lidJid 3, saveOnPrimaryAddressbook 4, pnJid 5, username 6, birthday 7; criado apenas pelo primário, de modo que um companion em bootstrap recebe sua agenda antes de qualquer coleção `regular*` |
| `mute` (`MuteAction`) | muted 1, muteEndTimestamp 2, autoMuted 3, muteEveryoneMentionEndTimestamp 4 |
| `sentinel` | `KeyExpiration{expiredKeyEpoch}` (7.1) |
| `android_unsupported_actions` (26), flag **14490** (padrão false) | um caminho de "Android unsupported mutation"; semântica unknown |

---

## 11. Erros fatais, retentativa e recuperação

### 11.1 Tipos fatais KMP (found, `Lx6.A00`; os ids são internos, não valores do wire)

| Grupo | Ids e nomes |
|-------|-------------|
| Transporte | 53 `XmppBadRequestForCollection`, 54 `…NotFoundForCollection`, 55 `XmppBadRequestGlobalError`, 56 `…NotFoundGlobalError`, 57 `…BadMethodGlobalError`, 58 `…NotAcceptableGlobalError` |
| Formato de patch / snapshot | 4 `MissingOrEmptyIndex`, 5 `SameIndexForMultipleMutationsInPatch`, 7 `MissingPatchVersion`, 8 `DuplicatePatchVersionInCollection`, 13 `PatchWithBothInlineAndExternalMutations`, 37 `CyclicMutationDependencyInPatch`, 38 `MissingSnapshotVersion`, 47 `MissingPatchKeyId`, 50 `MissingSnapshotKeyId`, 59 `SameIndexForMultipleMutationsInSnapshot`, 64 `ServerDidNotSendAllPatches`, 65 `ServerSentEarlierPatch`, 71 `InvalidSnapshotRecords` |
| Formato de mutação / ação | 10-12, 14-16, 19-24 (`MissingMutationVersion/Value/Index/Operation/Record/KeyId`, `MissingActionIndex/Value/Version/Timestamp`, `InvalidMutationIndex`, `InvalidActionIndex`) |
| Cripto | 6 `DecryptionFailed`, 9 `EncryptionFailed`, 31 `MacMismatchSnapshot`, 32 `MacMismatchPatch`, 39-41 `Missing*Mac`, 51 `SnapshotMacMismatchInPatch`, 52 `SnapshotMacMismatchInSnapshot` |
| Chaves | 29 `MissingKeyOnAllClients`, 30 `TimeoutWhileWaitingForMissingKey`, 46 `InvalidKeyShareKeyId`, 48 `InvalidKeyShareKeyData`, 62, 66-69 (`RequestingMissingKeyWithNoClients`, `MissingKeyForMutationInLocalSnapshot`, `MissingActiveKeyAfterRotation`, `MissingActiveKeyForEncryption`, `MissingCurrentEpochForActiveKeyValidation`) |
| Blobs / protobuf | 3 `ExternalPatchExpired`, 49 `SnapshotExpired`, 42-45 e 72 `MissingExternalBlobReference*`, 60 / 61 falha de parse de referência / snapshot, 17 / 18 / 25-28 tipos de (de)serialização, 34-36 `TerminalPatch*` |
| Local | 33 `DbStoreNotReady`, 63 `DbStoreNotReadyLowDiskSpace`, 70 `SameIndexForMultipleMutationsInOutgoingPatch` |

### 11.2 Códigos numéricos legados (found, `C49784Lv2.errorCode`, alimentam o WAM `md_fatal_error`; numeração separada)

8 / 9 / 14 (`N90`: sem versão / versão duplicada / inline + externo), 18 / 69 (falha de parse de patch / snapshot), 36 / 37 / 38 (`exit_code` 100 / 101 / outro), 64-67 (erros globais de IQ 400 / 404 / 405 / 406), 71 (resolução de chave falhou após a requisição de chave ausente), 31 (timeout de espera pela chave), 60 (mismatch não fatal de MAC de snapshot em um patch, `A0F(60, collection, false)`). O mapeamento para os tipos KMP não está resolvido.

### 11.3 Reação a uma falha fatal (found, `SyncResponseHandler.A08`, `C12440bB.A0S/A0Q`)

| Papel | Ação |
|-------|------|
| Qualquer | registra `app-state-sync-handle-fatal-exception`, WAM `md_fatal_error`, limpa a sincronização em andamento |
| Flag **25799** | companion: `companion_syncd_dirty=true`; primário: `C17630k8.A01(1)` (motivo de dirty 1, inferred) |
| Primário | `A0Q(1)` apaga todos os dados do syncd. Máquina de dirty (`C17630k8`, cadeia a partir de `A0Q` inferred): contador `syncd_dirty` até 4, `syncd_dirty_reason`, `<iq xmlns="w:sync:app:state" type="set"><delete_all_data/></iq>` (atributo type inferred), `logoutAllCompanionDevices` |
| Companion | `companion_syncd_dirty=true`, mensagem peer `AppStateFatalExceptionNotification` (FMessage 50) ao primário (dispositivo 0), espera de 5 s, logout com `syncd_failure` ou `syncd_error_during_bootstrap` |

Janela de nova tentativa do delete-all: **14493** minutos (padrão 360). O primário faz a limpeza quando um companion foi desregistrado e nenhum permanece (`shouldCleanUpSyncd`).

### 11.4 Recuperação de snapshot (found, `KmpSyncdFatalErrorRecovery`)

Controlada pela client-prop `isSyncdSnapshotRecoveryEnabled`. O companion envia a peer data operation `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` (8) com `SyncDCollectionFatalRecoveryRequest{collectionName}`. O respondente monta um `SyncdSnapshotRecovery` a partir de suas mutações armazenadas em **texto plano** (`syncd_mutations`, `collection_versions.version / lt_hash`), aplica gzip e devolve `SyncDSnapshotFatalRecoveryResponse`. Recusas: `Invalid collection name` (requisição para `critical_block`), `Collection version/ltHash invalid`, `Snapshot keyId invalid`, `Mutation count (…) more than the limit`, `Mutation snapshot data size (…) more than the limit`, `Error encoding mutation data`, `Compression failed` (props de limite não resolvidas). O texto plano trafega dentro de uma mensagem peer criptografada de ponta a ponta. A aplicação no lado do companion não foi rastreada (unknown).

---

## 12. Estado local e feature flags

| Armazenamento | Conteúdo (found) |
|---------------|------------------|
| `syncd_mutations` | `mutation_index` (único), `mutation_value`, `mutation_version`, `collection_name`, `are_dependencies_missing`, `mutation_mac`, `device_id`, `epoch`, `chat_jid`, `mutation_name` |
| `collection_versions` / `pending_mutations` / `missing_keys` / `crypto_info` | `collection_name, version, lt_hash` / fila de saída (`is_ready_to_sync`) / requisições de chave / chaves de sincronização |
| Prefs | `syncd_bootstrap_state`, `companion_syncd_critical_bootstrap_state`, `syncd_dirty`, `syncd_dirty_reason`, `companion_syncd_dirty`, `syncd_last_companion_dereg_time`, `syncd_last_lthash_consistency_check_time`, `first_transient_server_failure_timestamp` |

O cron diário (`C46413KPv`) reporta os contadores `mutation_counter`, `invalid_action_counter`, `upload_conflict_counter`, `unsupported_action_counter`, `cross_index_conflict_counter`, `unset_action_mutation_counter`, `key_rotation_remove_counter`, `missing_key_counter`.

| ID da flag | Tipo / padrão | Controla |
|------------|---------------|----------|
| **15909**, **20682**, **18234** | bool / false | `XplatSyncdEncryptionManager` vs padrão (`AbstractC17550k0`); entrada KMP (`RunnableC53542Nwj`); saída KMP (`C12440bB`). Apenas padrões compilados, valor real unknown. Nome da 15909 em build anterior: `KMP_SYNCD_ENGINE_CRYPTO_ENABLED` (reuso de ID inferred) |
| **14488** / **14496** / **14492** | int / 30 / 31 / 7 | idade da chave ativa, retenção de chaves obsoletas, timeout de espera por chave (dias) |
| **14493** | int / 360 | janela de delete-all / dereg (minutos) |
| **14494**, **14495**, **5097** | int / 100, 10, 0 | limiares de patch externo |
| **14497** | int / 1000 | limite de carga de mutações do DB (inferred) |
| **1104** / **1783** | int 0 / bool false | intervalo da verificação de consistência (h) / verificação após mismatch de MAC de snapshot |
| **6614** | bool / false | `clientDebugData` nos patches |
| **25799** | bool / false | tratamento de estado dirty em falha fatal |
| **27528** | bool / false | gerar uma chave quando o primário não tem nenhuma |
| **14486** | bool / true | `deviceIndex` nos patches (consumidor não rastreado) |
| **14489**, **14490**, **1221**, **624** | int 90 / bool false / bool false / bool | limite `min()` em `C15310g7` (não resolvido) / caminho de unsupported-mutation / estatísticas de mutação / hashes completos nos logs |

---

## 13. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|----------|
| `Data MAC mismatch` | chave errada, blob adulterado, byte de op ou keyId errado no AAD | chave indicada por `record.keyId`; AAD = `op ‖ keyId`, op 1 SET / 2 REMOVE |
| `Index MAC mismatch` | a string de índice difere byte a byte (espaçamento do JSON) | aplicar o MAC sobre a string UTF-8 exata de `SyncActionData.index` |
| fatal 64 `ServerDidNotSendAllPatches` | versão do patch ≠ armazenada + 1 | ressincronizar a partir da versão armazenada; requisitar um snapshot se o estado foi perdido |
| mismatch de MAC de patch (32) | deriva do LT-Hash, largura do version8, MAC de snapshot de origem errada | usar primeiro o `snapshot_mac` do patch; versão como big-endian de 8 bytes |
| `PatchWithBothInlineAndExternalMutations` | ambos os campos definidos | enviar apenas um |
| `MissingActionTimestamp` | `SyncActionValue.timestamp` ausente em um SET | definir o campo 1 |
| chave ausente | compartilhamento não recebido | requisição tipo 39; fatal 31 após 7 dias |
| `one of a peer device is no longer registered` | lista de dispositivos mudou desde a criação da chave | chave inutilizável como chave ativa; gerar uma nova |
| erro de IQ 400 / 404 / 405 / 406 | formato de requisição inválido, coleção desconhecida | fatal; corrigir a requisição |
| `ExternalPatchExpired` / `SnapshotExpired` | status 5 do blob | recuperação de snapshot ou novo vínculo |
| logout do companion `syncd_failure` | falha fatal irrecuperável | parear de novo, ou recuperação de snapshot se habilitada |

---

## 14. Distinções importantes

| Não confundir | Com |
|---------------|-----|
| Chave de sincronização (32 bytes aleatórios por dispositivo+epoch) | chaves de mutação (saída do HKDF, cinco fatias) |
| MAC de índice (HMAC-SHA256 sobre a string de índice) | MAC de valor (HMAC-SHA512 truncado a 32 sobre AAD + iv + ct + len) |
| MAC de valor (por mutação) | MAC de snapshot (LT-Hash + versão + coleção) e MAC de patch (MAC de snapshot + todos os MACs de valor) |
| nó `<snapshot>` (um `ExternalBlobReference`) | proto `SyncdSnapshot` (o conteúdo do blob); igualmente `externalMutations` vs `SyncdMutations` |
| `critical_block` no Android (configurações da conta) | uma coleção de lista de bloqueio (não encontrada) |
| tipos de `ProtocolMessage` 6 / 7 / 10 | números de campo 7 / 8 / 10 |
| Campo 7 da peer data request | campo 8 da peer data response |
| ids de tipo KMP (`Lx6`) | ints legados de `errorCode` |
| `sentinel` (marcador de expiração de chave nas cinco coleções) | `primary_version`, `android_unsupported_actions` |
| Tabelas de ações / coleções do WhatsApp Web | a tabela do Android aqui (96 ações, atribuição diferente) |

---

## 15. Baileys (`baron-baileys-v2` 1.5.17)

Somente fatos lidos em `src/Utils/chat-utils.js`, `src/Socket/chats.js`, `src/Utils/process-message.js`. Nada foi testado contra um servidor; nenhuma falha é alegada.

| Tópico | Baileys | Android |
|--------|---------|---------|
| Expansão de chaves, LT-Hash | bridge nativa `expandAppStateKeys`, `LTHashAntiTampering` (128 bytes); mesmos cinco nomes de fatias | 5.1, 6 |
| MAC de valor | `HMAC-SHA512(op ‖ keyId ‖ data ‖ 8 bytes, last = len)[0..32)`, op 1 / 2 | idêntico |
| MAC de snapshot / patch | mesmas entradas e ordem; `ver8` escreve apenas os 32 bits baixos | big-endian completo de 64 bits |
| Índice, padding | `JSON.stringify(index)`, padding vazio | igual |
| Blob externo | `downloadContentFromMessage(blob, 'md-app-state')` | mesmo tipo de mídia |
| Coleções | `critical_block, critical_unblock_low, regular_high, regular_low, regular` | mesmos nomes |
| Nó de requisição | `<sync>` sem atributos; `<collection name version return_snapshot>`, `return_snapshot` sempre `'true'`/`'false'` | `data_namespace="3"`, `order`, `return_snapshot` somente quando true |
| Envio de patch | `version = state.version − 1`, `return_snapshot='false'` | versão armazenada |
| Continuidade de versão | não verificada (`newState.version = patchVersion`); uma versão de patch ausente vira versão da coleção + 1 | deve ser igual a armazenada + 1 |
| MAC de snapshot em um patch | recalculado, lança `failed to verify LTHash` | não fatal no caminho KMP |
| Compartilhamento de chave | armazena apenas `keyData` por key id em base64; `myAppStateKeyId` = última chave da mensagem | mantém fingerprint e timestamp, verifica o fingerprint, escolhe a última chave válida |
| Notificação fatal | registrada, emitida como `app-state.sync-error` | companion envia, primário age |
| Nova tentativa | `MAX_SYNC_ATTEMPTS = 2`, nova tentativa com snapshot forçado, chave ausente estaciona a coleção | seção 11 |
| Salt NCT | `nctSaltSyncAction.salt` armazenado como `nct-salt` | 10.2 |

Não presentes no código-fonte do Baileys: `data_namespace`, `order`, tratamento de `exit_code`, recuperação de snapshot. O efeito no servidor é unknown.

---

## 16. Fluxos completos

### 16.1 Primário grava uma alteração (exemplo `mute`)

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

### 16.2 Companion puxa

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

### 16.3 Falha fatal

```
[Companion]  patch MAC mismatch / key timeout / version gap
     ├─ recovery enabled ─► peer data op 8 {collectionName} ─► [Primary] SyncdSnapshotRecovery (gzip)
     └─ else companion_syncd_dirty ; peer AppStateFatalExceptionNotification ; 5 s ; logout syncd_failure
               ▼
         [Primary]  delete syncd data ; iq <delete_all_data/> ; logout companions ; re-pair
```

---

## 17. Unknowns

| Item | Status |
|------|--------|
| Engine ativa (legada ou KMP) por conta | flags do servidor |
| Significado do atributo `order` | unknown |
| Verificação de fingerprint no lado do receptor de um compartilhamento de chave recebido | não localizada |
| Lado de aplicação de um `sentinel` recebido (`expireKeysWithEpochIfActive`) | não rastreado |
| Mapeamento tipo KMP ↔ código legado; gatilho de `ServerSentEarlierPatch`; significado de `exit_code` 100 / 101 | não resolvido |
| Campo de valor das 9 ações marcadas com `-` | unknown |
| Lado de aplicação da recuperação de snapshot, props de limite | não rastreado |
| Ordenação, retenção e regras de merge do servidor | lado do servidor |
| Tráfego | nada capturado |
