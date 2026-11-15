<!-- src-sha1: b8f7c5d44373d4a7bc19be29e7bd26af81a86f85 -->
# WhatsApp Message Secrets — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** per-Message `messageSecret` (Generierung, `MessageContextInfo`, lokaler Store, History-Sync), Use-Case-Schlüsselableitung (HKDF), AES-GCM IV / AAD, verschlüsselte Add-ons (`encReactionMessage`, `pollUpdateMessage`, `encEventResponseMessage`, `encCommentMessage`, `secretEncryptedMessage`-Edits), Sender-/Target-Identitätsbindung und LID/PN-Retry, Orphans und Missing-Secret-Fallbacks, `<message>`-Stanza-Erweiterungen (Attribute, `<enc>`-Attribute, `<meta>`, `<biz>`, `<bot>`, `<hsm>`, `<reporting>`, `<cap>`, Padding, Companion-Support-Check), Feature-Flags, Baileys-Vergleich

---

## 1. Was es technisch ist

Jede Nachricht, die später ein verschlüsseltes Follow-up erhalten kann, trägt ein zufälliges 32-Byte-Secret in ihrem eigenen Ende-zu-Ende-verschlüsselten Payload (`MessageContextInfo.messageSecret`). Ein Follow-up (Reaction, Poll-Vote, Event-Response, Comment, Edit) wird mit einem Schlüssel verschlüsselt, der aus diesem Secret, der ID der Originalnachricht, dem Original-Sender und dem Modifier abgeleitet wird. Der Server leitet das Follow-up als gewöhnliche E2E-Nachricht weiter, kann es aber nicht lesen oder auf ein anderes Target, einen anderen User oder Use-Case umlenken, ohne die GCM-Authentifizierung zu brechen. Alle Aussagen sind statische Analyse der dekompilierten APK; nichts wurde auf der Leitung mitgeschnitten. Tiers: **found** = im Code gelesen, **inferred** = aus Code abgeleitet, **unknown** = nicht aufgelöst. Obfuskierte Namen wurden in 2.26.41.6 anhand stabiler Strings neu aufgelöst (`MessageSecretCryptoHelper/`, `MessageEncUtils/`, Use-Case-Strings, `FMessage*Protobuf/`, `SecretEncryptedMessagePreProcessor/`, `CompanionSupportVerifier/`).

Dasselbe Release definiert auch die `<message>`-Stanza-Erweiterungen (Abschnitt 10 ff.): Attribute und Kind-Knoten, die eine Nachricht klassifizieren und routen, aber nicht ihren Inhalt tragen. Sie sind hier gruppiert, weil `<meta polltype>` / `<meta event_type>` mit dem secret-encrypted Payload übereinstimmen müssen (7.4).

| Entity | Name in 2.26.41.6 | Rolle |
|--------|----------------|------|
| Crypto-Helper (`MessageSecretCryptoHelper`) | `C33285Eeb` | `A03` verschlüsseln, `A04` entschlüsseln (Identity-Retry), `A02` Target-Key-Auflösung |
| Encrypt-/Decrypt-Parameter-Träger | `C32833ETl` / `C32854EUg` | Daten, Sender, Target-Key, Use-Case / IV, Payload, Keys, Sender |
| Schlüsselableitung | `AbstractC33322EfC.A02` + `AbstractC38961i0.A00` | HKDF-SHA256, Zero-Salt |
| AES-GCM | `JniBridge.WCIAPIGcmAesCreateEncryptedCiphertext`, `AbstractC32243E6m.A00` (`MessageEncUtils`) | native, 16-Byte-Tag |
| AAD-Provider | `FXU`: `C34633F1g` (Poll Vote), `C34632F1f` (Event Response), `C34634F1h` (WASA), `C34631F1e` (keiner) | zusätzliche Daten |
| Secret-Generator | `AbstractC33322EfC.A01` | `SecureRandom`, 32 Byte |
| Secret-Store (`MessageSecretStore`) / In-Memory-Extra | `C35311ad` (Tabelle `message_secret`) / `C35171aP` auf der Nachricht `C13G` | persistieren und mitführen |
| Original-Key-Mapper (`ReferentialKeyUtil`) | `C43661qB.A03` | Key der unbearbeiteten Originalnachricht |
| Reaction-Handler | `DU8` (senden), `F2P`-Zweig (empfangen) | `reactionMessage` / `encReactionMessage` |
| Poll-Vote / Event-Response / Comment | `DUA` / `DU9` / `F3W` | `pollUpdateMessage` / `encEventResponseMessage` / `encCommentMessage` |
| Secret-encrypted Edits (`SecretEncryptedMessagePreProcessor`) | `F3Y`, Enum `E2Q` | `secretEncryptedMessage` |
| Poll-/Event-Erstellung (Secret wird beim Empfang übernommen) | `F2N` / `F2M` | liest `messageSecret` in die FMessage |
| Proto: Context / Message / Key | `C30624DTs` / `C30628DTw` / `BD5` | `MessageContextInfo` / `Message` / `MessageKey` |
| Stanza-`type`-Auswahl | `AbstractC30999De0.A02` | `text media reaction poll event pay medianotify scheduled-call` |
| Outgoing-Stanza-Contributor | `InterfaceC35538FaZ`: `F6K` (meta), `F6M` (bot), `F68` Flags, `F69` cap, `F6H` Padding, `F6L` / `F6C` Reporting, `F6G` cstoken, `F6I` tctoken, `F6B` Device-Identity, `F6X` hsm | bauen Kind-Knoten von `<message>` |
| `<meta>`-Sammler | `EZV` (Attribute `A01`, Kinder `A00`) | ein `<meta>`-Knoten |
| `<enc>`-Attribut-Builder | `AbstractC33466EhY.A09` | `v type count mediatype ...` |
| Companion-Support-Check | `C34757F6a` + `AbstractC32927EXc` | Typ- und Kind-Allowlist |
| Incoming-Spec-Parser | `C33474Ehg` (Status / regulär), `C23206A1f` (Newsletter), `C34747F5q` (Bot), `C34748F5r` (Biz) | Attribut- und Kind-Extraktion |
| WAM-Error-Event | `DZ7` / `C273212s` | `wam_message_secret_errors` |

---

## 2. Das Per-Message-Secret

### 2.1 Wo es liegt (found)

`MessageContextInfo` (`C30624DTs`) ist Feld **35** von `Message` (`C30628DTw`). Hier relevante Felder:

| Feld | Nummer | Typ | Verwendung |
|-------|--------|-----|-----|
| `deviceListMetadata` / `deviceListMetadataVersion` | **1** / **2** | message / int | Device-List-Hinweis (nicht secret-bezogen) |
| `messageSecret` | **3** | bytes (32) | Per-Message-Secret |
| `paddingBytes` | **4** | bytes | Padding |
| `messageAddOnDurationInSecs` | **5** | uint32 | Add-on-Lebensdauer (Pin: muss 0 sein für Unpin) |
| `botMessageSecret` | **6** | bytes (32) | Bot-Variante des Secrets |
| `botMetadata` | **7** | message | Bot-Kontext |
| `reportingTokenVersion` | **8** | uint32 | Reporting-Token-Version dieser Nachricht |
| `messageAddOnExpiryType` | **9** | enum | Add-on-Expiry |
| `messageAssociation` | **10** | message | Assoziation |

Der History-Sync-Träger `WebMessageInfo` (`C30626DTu`) hat sein eigenes `messageSecret`-Feld **49** (found), verwendet beim Export von Nachrichten an einen neuen Companion (Abschnitt 2.4).

### 2.2 Generierung (found, Bedingungen teilweise inferred)

Das Secret ist `SecureRandom.nextBytes(byte[32])` (`AbstractC33322EfC.A01`). Es wird angehängt, bevor die Nachricht serialisiert wird:

| Stelle | Bedingung |
|-------|-----------|
| `C33166Ecf.A06` (Send vorbereiten) | Nachricht hat kein Secret und mindestens eines von: Poll-Klasse `C13J`; `EZN.A01(msg)` (Bot-/Add-on-Klasse, mit Chat-Typ-Flags **2200**, **11104**, **19303**); Chat-Klassen-Gates: Gruppe mit Flag **3143**, Broadcast-Liste mit **3144**, Status mit **3145**, Klassen-Gate **3146**; `C35201aS.A00` (Flag **3142**, Self-/Bot-Chat); Event-Nachricht `C213509Ao` |
| `AJ0` (Send-Prozessor) | Reporting-Token-Version `C35241aW.A05()` (AB-Int **8860**, begrenzt durch `AbstractC35301ac.A00`) ist ungleich null und die Nachrichtenklasse ist nicht durch `C35241aW.A02` ausgeschlossen (Status, Newsletter, ausgewählte Add-on-Klassen) |
| `C72h`, `C34455Exe`, `EPA` | Status-Objekte (`AbstractC34478Ey1.A0R`) erhalten bei Erstellung ein frisches Secret |
| `C33437Eh4` | Bot-"Request-Welcome"-Nachricht, nur wenn der Aufrufer es verlangt |
| `C9mW` | Nachrichtentyp 117, Flag **24741**, wenn keines vorhanden ist |

Die Prädikate hinter `EZN.A01`, `C35201aS.A00` und den `3142`..`3146`-Gates wurden nicht vollständig aufgelöst; die obige Liste sagt, was der Code prüft, nicht welche nutzersichtbaren Nachrichten qualifizieren. Nachrichten ohne Secret können von diesem Client keine verschlüsselten Add-ons erhalten (Abschnitt 9).

### 2.3 Lokale Speicherung (found)

`C35311ad` schreibt `message_secret(message_row_id, message_secret)` mit Replace-Semantik (`MessageSecretStore/insertMessageSecret`) und liest die letzte Zeile für eine `message_row_id`. Die FMessage führt es als Extra `C35171aP` mit (`A0L` setzen, `A0c` lesen, `A0Q` = nicht leer). Zwei Prozessoren in `AbstractC17240jU` (`C35161aO` und ein anonymer) schreiben es, wenn das Extra dirty ist und der Chat qualifiziert.

### 2.4 Receive-seitige Validierung und Transfer (found)

| Schritt | Verhalten |
|------|-----------|
| Proto-Validator `C33475Ehh.A0V` | `message_secret` muss exakt **32** Byte sein, Fehlercode **67**; die Bot-Variante (`bot_message_secret`, Gruppe `whatsapp_security`) wird gleich validiert |
| Poll-Erstellung `F2N` | kopiert `messageSecret_` in die neue FMessage (`A0L`) |
| Status-Fragen-Antworten `C34838F9e` | gleiche Kopie für `statusQuestionAnswerMessage` |
| History-Sync-Export `C34388EwZ.A00` | schreibt das gespeicherte Secret in `WebMessageInfo.messageSecret` (49) |
| History-Sync-Import `C34388EwZ.C59` | kopiert es zurück (`A0L`) |
| Comments `C34387EwY` | baut einen `MessageContextInfo` aus `WebMessageInfo.messageSecret` für den Comment-Thread neu auf |

`wam_message_secret_errors` (`DZ7`, `C273212s.A00`) loggt `message_secret_error` **0** = fehlend (entspricht Fehlercode 66) oder **1** = ungültige Länge (67) für Nachrichten, die ein Secret benötigen (`AbstractC33322EfC.A00`: hat das Flag und ist nicht Klasse `C35281aa`).

---

## 3. Use-Case-Schlüsselableitung

### 3.1 Formel (found, `AbstractC33322EfC.A02`)

```text
info = UTF8(originalMessageId) ‖ UTF8(targetSender.rawString) ‖ UTF8(modifier.rawString) ‖ UTF8(useCase)
prk  = HMAC-SHA256(key = 32 × 0x00, data = messageSecret)          // HKDF extract
key  = HMAC-SHA256(key = prk, data = info ‖ 0x01)                  // HKDF expand, L = 32, one block
```

`AbstractC38961i0.A00(secret, info, 32)` = Extract mit 32-Byte-Zero-Salt (`AbstractC38971i1.A00(ikm, salt)`), danach die RFC-5869-Expand-Schleife. HKDF-Grundlagen: [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md) Abschnitt 5.1. Der 32-Byte-Output wird als AES-256-Schlüssel verwendet (inferred aus der Länge; der native Call nimmt den Key als `byte[]`).

Inputs:

| Input | Quelle | Anmerkungen |
|-------|--------|-------|
| `originalMessageId` | Key-ID des Targets nach `ReferentialKeyUtil` (`C43661qB.A03`) beim Verschlüsseln; Key-ID aus dem Proto `targetMessageKey` beim Entschlüsseln | für ein bearbeitetes Target ist dies die **originale** Nachrichten-ID (`getOriginalKey`-Log) |
| `targetSender` | Autor der Originalnachricht: gespeicherter Sender (`C12300aw.A01`) | `UserJid`, also ohne Device-Suffix (Typ-Ebene; die String-Form `user@server` ist inferred) |
| `modifier` | Autor des Add-ons: eigene Account-JID (`C09A.A0G`, eine LID, zurückgegeben von `CUC()` / `Ash()`) beim Senden, Sender-JID des Envelopes beim Empfangen | |
| `useCase` | String aus 3.2 | kein Separator zwischen den vier Komponenten |

Die eigene JID ist eine LID-Account-JID (`C14080dr`, Server `lid`, "Invalid LID"-Check). Sowohl `AnonymousClass091.Ash()` als auch `CUC()` geben dasselbe Feld zurück.

### 3.2 Use-Case-Strings (found)

| Use-Case | Träger | AAD | Java-Literal in 2.26.41.6 |
|----------|---------|-----|---------------------------|
| `Enc Reaction` | `encReactionMessage` | keine | `DU8`, `F2P` |
| `Poll Vote` | `pollUpdateMessage.vote` | `targetId ‖ 0x00 ‖ modifier` | `DUA`, `C0ZG`, `C33285Eeb.A00` |
| `Event Response` | `encEventResponseMessage` | `targetId ‖ 0x00 ‖ modifier` | `DU9`, `F2P`, `C33285Eeb.A00` |
| `Enc Comment` | `encCommentMessage` | keine | `F3W` |
| `Event Edit` | `secretEncryptedMessage` Typ 1 | keine | `F3Y.A00` |
| `Message Edit` | `secretEncryptedMessage` Typ 2 | keine | `F3Y.A00`, nur mit Flag **17811** |
| `Poll Edit` | `secretEncryptedMessage` Typ 4 | keine | `F3Y.A00` |
| `Poll Add Option` | `secretEncryptedMessage` Typ 5 | keine | `F3Y.A00` |
| `WASA` | Bot-Pfad (`C33284Eea`) | `keyId ‖ 0x00 ‖ jid` | zweistufig, 3.3 |
| `Report Token` | Reporting-Token-Key | native | kein Java-Literal; vorhanden in `libwhatsapp.so`, native abgeleitet (3.4) |

### 3.3 Bot-/WASA-Variante (found, Details inferred)

Für Use-Case `WASA` hat die Ableitung zwei Stufen und keinen Use-Case-String in der zweiten:

```text
k1  = HKDF-SHA256(secret, salt = 0×32, info = "Bot Message", L = 32)      // AbstractC33322EfC.A00
key = HKDF-SHA256(k1,     salt = 0×32, info = id ‖ jidA.raw ‖ jidB.raw, L = 32)
AAD = UTF8(keyId) ‖ 0x00 ‖ UTF8(modifier.raw)                              // C34634F1h
```

`jidA` ist der Modifier und `jidB` der Remote-(Chat-)JID, der eine `UserJid` sein muss (`WASA info jid must be a UserJid (hatch_jid)`); die ID ist der aktuelle Nachrichten-Key, wenn vorhanden, sonst der Target-Key (`C33285Eeb.A03`-Lambda). Native Gegenstück: `WcmBotMessageSecretAPICreateWithMessageSecret`. Meta-AI-Kontext: [WA_META_AI.md](./WA_META_AI.md).

### 3.4 Reporting-Token-Key (found / inferred)

`C33364Efs.A06` und `C33421Ego` rufen `JniBridge.WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)` auf: das native Objekt leitet den Schlüssel für Use-Case-ID **5** ab; die Java-Seite übergibt nur JID-Raw-Strings. Der String `Report Token` existiert in der nativen Library; die Zuordnung von ID 5 zu diesem String ist inferred. Token und Upload: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 4. AEAD-Layout

| Item | Wert | Tier |
|------|-------|------|
| Cipher | AES-GCM, native (`WCIAPIGcmAesCreateEncryptedCiphertext(key, iv, plaintext, aad, 16)`; entschlüsseln `jvidispatchOIOOOOO(6, 16L, ctx, key, iv, ciphertext, aad)`) | found |
| Key | 32 Byte aus Abschnitt 3 | found |
| IV | **12** zufällige Byte pro Verschlüsselung (`SecureRandom`); Decrypt lehnt jede andere Größe ab | found |
| Tag | 16 Byte; die Konstante 16 wird bei beiden Calls übergeben; Position (an Ciphertext angehängt) inferred aus Baileys-Decrypt | found / inferred |
| AAD | pro Use-Case (3.2); `null`, wenn der Provider `C34631F1e` ist | found |
| Plaintext | das serialisierte innere Proto (Tabelle 5) | found |
| Output | `(encIv, encPayload, targetMessageKey)`-Tripel (`C53966OMp`) | found |
| Leeres Ergebnis | Log `encryption values are invalid`, Fehler `Encryption using iJniBridge failed` | found |

Poll-Vote-Retry: Wenn der Vote bereits IV und Payload hält (`C30957Dd6.A03` / `A04`), wird dasselbe Ciphertext erneut gesendet, statt neu zu verschlüsseln (found, `DUA`-Legacy-Zweig).

---

## 5. Träger und Plaintexte

| Träger (Feld in `Message`) | Klasse | Felder | Entschlüsselter Plaintext |
|------------------------------|-------|--------|---------------------|
| `encReactionMessage` **56** | `DRO` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `ReactionMessage` (`DSH`): `key` **1** (vor Verschlüsselung gelöscht), `text` **2**, `groupingKey` **3**, `senderTimestampMs` **4** |
| `pollUpdateMessage` **50** | `DSG` | `pollCreationMessageKey` **1**, `vote` **2** (`PollEncValue` `C30530DQc`: `encPayload` **1**, `encIv` **2**), `metadata` **3** (`C30532DQe`: `pollNameHash` **1**, `lastEditStanzaId` **2**), `senderTimestampMs` **4** | `PollVoteMessage` (`DPF`): `selectedOptions` **1** (repeated bytes, Options-Hashes) |
| `encEventResponseMessage` **76** | `DRN` | `eventCreationMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `EventResponseMessage` (`DRP`): `response` **1** (`E2D`: 0 unbekannt, 1 zusagen, 2 absagen, 3 vielleicht), `timestampMs` **2**, `extraGuestCount` **3** |
| `encCommentMessage` **71** | `DRM` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | vollständiges `Message` (der Comment-Body); Plaintext-Form ist `commentMessage` **77** (`DQV`: `message` **1**, `targetMessageKey` **2**) |
| `secretEncryptedMessage` **82** | `DSI` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3**, `secretEncType` **4** | vollständiges `Message` |
| `reactionMessage` **46** | `DSH` | Plaintext-Form | plaine Reaction |
| `conditionalRevealMessage` **120** | n/a | nicht das Message-Secret-Schema (Abschnitt 14.1) | zeitgesteuerte Nachrichten |

`SecretEncType` (`E2Q`): `UNKNOWN` 0, `EVENT_EDIT` **1**, `MESSAGE_EDIT` **2**, `POLL_EDIT` **4**, `POLL_ADD_OPTION` **5**. Wert 3 existiert in diesem Build nicht (`forNumber(3)` gibt null zurück, wird als unknown behandelt und abgelehnt).

`MessageKey` (`BD5`): `remoteJid` **1**, `fromMe` **2**, `id` **3**, `participant` **4**.

---

## 6. Sender-Seite

### 6.1 Gemeinsamer Pfad (found, `C33285Eeb.A03`)

1. Target-FMessage per Key auflösen (`target message not found. Cannot proceed further` -> Fehler 71).
2. Secret aus `message_secret` lesen; null oder Länge != 32 -> `message secret missing or invalid` (66).
3. Original-Key via `C43661qB.A03` (null -> Fehler 0). Target-Sender via `C12300aw.A01`.
4. In einem 1:1-Chat (`C0DZ.A0k(chat)`) wird der Target-Sender in den Namensraum des Modifiers konvertiert: Modifier-LID und Target-PN -> Target gemappt von PN auf LID; Modifier-PN und Target-LID -> Target gemappt von LID auf PN. In Gruppen keine Konvertierung.
5. Nur Event Response: Flag **15791**, 1:1-Chat und ein Account-Typ-Modifier -> Modifier wird zu PN konvertiert.
6. Zufälliger 12-Byte-IV, Key ableiten (3.1), AES-GCM mit der Use-Case-AAD.
7. Äußeren `MessageKey` aus Target-Sender und Original-Key bauen (`C32717EOy.A01`); der Träger hält `targetMessageKey`, `encIv`, `encPayload`.

### 6.2 Pro Träger (found)

| Träger | Gate beim Senden |
|---------|--------------|
| Reaction (`DU8.ADr`) | wird **nur** verschlüsselt, wenn der Chat eine Gruppe ist (`C0DZ.A0l`) mit `group_type == 3` (`C0GQ.A0A`; in `CMP` aus `isDefaultSubgroup_` gesetzt, also eine Community-Default-Subgroup, Interpretation inferred) und das Serialisierungskontext-Flag `A09` falsch ist. In jedem anderen Chat wird die plaine `reactionMessage` gesendet. `ReactionMessage.key` wird vor der Verschlüsselung geleert (der Key wandert in den äußeren `targetMessageKey`) |
| Poll-Vote (`DUA.ADr`) | Flag **6772** an: gemeinsamer Helper, immer verschlüsselt; aus: Legacy-Inline-Zweig mit derselben Ableitung und AAD (Target-Sender = eigene LID für eigene Polls, sonst die aus dem Vote-Target-Key abgeleitete JID; Modifier = eigene LID). `metadata` (`pollNameHash`, optional `lastEditStanzaId`) wird gestempelt, wenn Flag **31593** an ist |
| Event-Response (`DU9.ADr`) | immer verschlüsselt; Plaintext `EventResponseMessage` hat `response`, `timestampMs`, `extraGuestCount` |
| Comment (`F3W.ADr`) | immer verschlüsselt; Plaintext ist das gesamte Comment-`Message`; das Target ist der `CommentMessageInfo`-Parent-Key |
| Secret-encrypted Edit (`F3Y.C5S`) | nur wenn die Nachricht Edit-Info vom Typ `E2Q` hat und der Serialisierungskontext nicht forwarded / orphan ist; `MESSAGE_EDIT` benötigt zusätzlich Flag **17811** (sonst wirft `getUseCase`). Für Edits eigener Nachrichten zeigen zwei Log-Zeilen (`sending the Message Yourself edit unwrapped`, `sending the agent reply edit unwrapped`) Fälle, die als plaine Edits gesendet werden; die vollständige Bedingung (Flags **37948**, **35457**) ging bei der Dekompilierung verloren |

Verschachtelte secret-encrypted Payloads werden auf beiden Seiten abgelehnt (`nested_secret_encrypted_message`).

---

## 7. Empfänger-Seite

### 7.1 Entschlüsseln (found, `C33285Eeb.A04`)

```text
target key  = A02(remoteSender, messageKey, proto.targetMessageKey)       // perspective flip, Ddz.A00
parent      = message store lookup (ReferentialKeyUtil)
secret      = message_secret[parent.row]                                   // null -> 66, len != 32 -> 67
checks      = IV == 12 bytes, payload non-empty (else 11), senderUserJid != null, targetSender != null
key, aad    = section 3 / 4
plaintext   = AES-GCM-decrypt(key, iv, payload, aad)                       // fail -> identity retry
```

`senderUserJid` (Modifier) pro Träger: eigene LID, wenn das Envelope von mir ist; Poll: Sender-JID (`c0df` oder `B4g()`); Event-Response: Chat-User in 1:1, sonst Envelope-User; Comment: nur LID (`C0DZ.A0Y`: Typen 18, 19, 25), ein PN-Sender schlägt mit Fehler 0 fehl; Reaction: Envelope-Sender nur, wenn er eine LID ist, sonst null.

### 7.2 LID-/PN-Identity-Retry (found Struktur, Ende inferred)

Der erste Versuch verwendet die JIDs wie angegeben. Bei Fehlschlag mappt der Helper beide JIDs in den anderen Namensraum (`C0YH.A0I` LID->PN, `A0F` PN->LID) und versucht es erneut; wenn beide bereits LID waren oder das Mapping fehlt, ist das Ergebnis Fehler **51** (Decrypt fehlgeschlagen). Das dekompilierte Ende des Retrys ist teilweise verloren, daher ist die genaue Menge der versuchten Paare inferred. Der Check ist GCM-Authentifizierung: ein falsches Paar schlägt fehl, das richtige entschlüsselt.

### 7.3 Parent fehlt: Orphans (found)

| Träger | Verhalten, wenn der Parent nicht gefunden wird oder ein Platzhalter ist |
|---------|-----------------------------------------------------------|
| Reaction | FMessage Typ **56** wird mit den rohen `Message`-Bytes gespeichert (`DdA(key, 56, ts).A02`); Decrypt wird aufgeschoben |
| Poll-Vote | `C30957Dd6.A02 = Message.toByteArray()`; unentschlüsselt gespeichert |
| Event-Response | `Dd7(key, target, bytes, ts)` unentschlüsselt gespeichert |
| Comment | Platzhalter `C34671Zb` mit Parent-Key und Row `-1` |
| Secret-encrypted Edit | `DeD(MessageOrphan)` mit Orphan-Typ **5**, Grund **1** (Parent fehlt) oder **2** (Platzhalter) |

Ein Replay, wenn der Parent eintrifft, wird erwartet (Orphans werden mit den rohen Bytes persistiert), aber der Replay-Trigger wurde nicht nachverfolgt (inferred).

### 7.4 Validierung nach dem Entschlüsseln (found)

| Fall | Check | Fehlschlag |
|------|-------|--------|
| Stanza `type=poll` + `<meta polltype="edit">` | `secretEncType` muss `POLL_EDIT` sein | `poll_edit_message_stanza_invalid` (76) |
| `polltype="add_option"` | Typ `POLL_ADD_OPTION` und ein zweites Stanza-Feld gleich `poll_add_option` (Feld nicht aufgelöst) | `poll_add_option_stanza_invalid` (76) |
| Event-Edit | innerer Nachrichtentyp 92, resultierender Key entspricht äußerem Key | `invalid secret encrypted message` (76) / `the resulting message key does not match outer key` |
| Poll-Edit | innerer Typ 66, beide Nachrichten Polls, gleiche Endzeit und Flags, Options-Edits konsistent mit gespeicherten Optionen, Timestamp nicht nach der Endzeit | `poll_edit_invalid_edits`, `poll_edit_invalid_option_edits`, `poll_edit_invalid_time` |
| Poll Add Option | innerer Typ 137, Parent ist eine Poll, Target-Key entspricht äußerem Key, nicht nach Endzeit | `poll_add_option_past_end_time` |
| Poll-Edit empfangen | AB-Int **24886** muss ungleich null sein | Fehler 10016 ("futureproofing") |
| Poll Add Option empfangen | AB **25758** muss ungleich null sein | Fehler 10017 |
| Poll-Vote | Auswahl muss für die Poll gültig sein (`AbstractC33199EdC.A02`); Vote-Timestamp nicht nach der Poll-Endzeit | `poll_update_past_end_time`, `invalid poll vote selection` |
| Poll-Vote-Metadata | `pollNameHash` + `lastEditStanzaId` werden gegen die gespeicherte Poll geprüft (`C32977EZa.A01`); "unstamped", wenn abwesend; Mismatch verwirft den Vote | `poll_update_tc_drop` |
| Poll-Vote-Form | IV exakt 12 (`poll_update_invalid_vote_enc_iv`), Payload vorhanden, Sender-Timestamp vorhanden | Fehler 11 |
| Event-Response | Key, IV (12), Payload vorhanden; Parent muss eine Event- oder eine Sender-Revoke-Nachricht sein | `parent message is not event message nor sender revoke` |

---

## 8. Sender-/Target-Bindung

| Gebunden durch den Key | Effekt |
|------------------|--------|
| Original-Nachrichten-ID | ein Ciphertext kann nicht auf einer anderen Nachricht wiederverwendet werden |
| Target-Sender-JID | kann nicht einem anderen Original-Autor zugeschrieben werden |
| Modifier-JID | kann nicht als Add-on eines anderen Users replayed werden |
| Use-Case-String | ein Reaction-Ciphertext entschlüsselt nicht als Vote, Comment oder Edit |
| AAD (Poll-Vote, Event-Response) | bindet zusätzlich `targetId` und Modifier in den Tag |

Nicht gebunden: Chat-JID, Timestamp, Position des Ciphertext im Thread, Anzahl vorheriger Add-ons. Das Envelope-`participant` / `from` ist, was der Empfänger als Modifier verwendet; es wird durch die E2E-Session authentifiziert, nicht durch das Secret. Jeder, der das Original-Secret besitzt (jeder Teilnehmer, der die Originalnachricht erhalten hat, in einer Gruppe), kann Schlüssel für jeden beliebigen Modifier ableiten; das Schema verhindert Relay-seitiges Retargeting, nicht Impersonation durch Gruppenmitglieder (inferred aus der Konstruktion).

---

## 9. Missing-Secret-Fallbacks (found, sofern nicht anders markiert)

| Situation | Sender | Empfänger |
|-----------|--------|----------|
| Original hat kein Secret | Verschlüsselung schlägt fehl (66); Poll-Legacy-Pfad: `invalid message_secret secretSize` | Parent vorhanden, Secret null: Fehler **66**, geloggt an den Error-Reporter mit `parentMsgRowId`, `parentType`, `parentHasSecret`; `wam_message_secret_errors` Code 0 |
| Secret nicht 32 Byte | Verschlüsselung abgelehnt | Fehler **67**, WAM Code 1 |
| Parent nicht gefunden | Verschlüsselungsfehler 71 | als Orphan gespeichert (7.3) |
| Reaction in einem Nicht-Default-Subgroup-Chat | plaine `reactionMessage` wird stattdessen gesendet (kein Secret benötigt) | vom plainen Zweig behandelt |
| Message-Edit ohne Flag 17811 | `getUseCase` wirft (`unknown message secret encrypted type`, Code 0); ob der Sender den Typ vermeidet, wenn das Flag aus ist, ist ungeklärt | derselbe Throw |
| Add-on-Decrypt schlägt fehl | n/a | Add-on bleibt verborgen / nicht verfügbar; kein sichtbarer Fallback-Text gefunden (unknown) |
| Neuer Companion ohne das Original | n/a | History-Sync trägt das Secret in `WebMessageInfo.messageSecret` (2.4) |
| `<enc decrypt-fail="hide">` | gesetzt auf Nachrichten mit Edit-Info (12.3) | sagt dem Empfänger, keinen Fehler-Platzhalter zu zeigen; Konsument des Flags ungeklärt |

---

## 10. `<message>`-Stanza: was der Client hinzufügt

Outgoing-Kinder werden von unabhängigen Contributors (`InterfaceC35538FaZ`) gebaut, die an den Stanza-Builder `C33150EcP` anhängen.

### 10.1 Attribute (found)

| Attribut | Producer / Consumer | Werte / Bedeutung |
|-----------|--------------------|-------------------|
| `type` | `AbstractC30999De0.A02` | `text`, `media`, `reaction`, `poll`, `event`, `pay`, `medianotify`, `scheduled-call` (aus dem Proto): `secretEncryptedMessage` mit `EVENT_EDIT` -> `event`, mit `POLL_EDIT` / `POLL_ADD_OPTION` -> `poll`; `MESSAGE_EDIT` fällt durch zu `text` / `media`; Reaction-Felder (plain oder enc) -> `reaction`; Poll-Update / -Creation -> `poll`; `encEventResponseMessage` und Event -> `event` |
| `edit` | Receive-Specs `C33474Ehg` (benötigt Node-Tag `status`; Beziehung zur plainen `<message>`-Stanza ungeklärt), `C23206A1f` (Newsletter); Acks `AbstractC33465EhX.A05` | `1`, `7`, `8` in `C33474Ehg`; `3` und `8` in der Newsletter-Spec; Acks echoen es, außer `0` / leer; siehe 10.2 |
| `category` | Stanza, Acks, Retry-Receipts | `peer` wählt den Peer-Message-Pfad |
| `device_fanout` | `F6M` | `"false"` bei gezielten One-to-One-Retries |
| `addressing_mode`, `participant`, `recipient`, `expiration`, `offline`, `dhash`, `sts` | Transport | Identität / Lifecycle, kein Inhalt |
| `peer_recipient_pn`, `peer_recipient_lid`, `peer_recipient_username`, `recipient_latest_lid`, `participant_username`, `sender_account_kind`, `sender_country_code`, `eph_setting` | Identitäts-Parser (`AbstractC33466EhY`, `C34763F6g`) | PN-/LID-/Username-Aliase |

### 10.2 `edit`-Werte

| Wert | Kontext | Tier |
|-------|---------|------|
| `1` | Edit einer gesendeten Nachricht (parsed in `C33474Ehg.A0L`) | found |
| `2` | Pin im Chat: der Receive-Pfad benötigt interne Edit-Version 2 (`Invalid edited version`) | inferred Mapping zum Attribut |
| `3` | Newsletter-Nachrichten-Edit: nur in der Newsletter-Spec geparst (`C23206A1f.A0G`), und `EWW.A01` setzt Edit-Version 3, wenn der Chat ein Newsletter ist (JID-Typ 21, Server `newsletter`) | found (löst das frühere "unknown 3" auf) |
| `7` | Revoke durch den Sender (`C33474Ehg.A0M`) | found |
| `8` | Admin-Delete (`C33474Ehg.A0S`, Newsletter-Spec `A0H`) | found |
| `0` / leer | normale Nachricht; in Acks ausgelassen | found |

Interne Edit-Version (`EWW.A01`) ist `1` für normale Chats und `3` für Newsletter; normale-Chat-Edits setzen zusätzlich das `decrypt-fail`-Hide-Flag (12.3).

### 10.3 Direkte Kinder (found)

| Kind | Producer | Bedeutung |
|-------|----------|---------|
| `enc` | Verschlüsselungs-Layer | Ciphertext, siehe Abschnitt 11 |
| `participants` / `to` | `F6E` und Fanout | Per-Device-Ciphertexte |
| `device-identity` | `F6B` | signierte Device-Identität |
| `registration` | Parser `C33474Ehg.A04` | exakt 4 Byte |
| `tctoken` | `F6I`, `AbstractC33466EhY.A01` | höchstens AB-Int **20606** pro Stanza, aktiviert durch **20605** |
| `cstoken` | `F6G` | Cold-Contact-Token |
| `padding` | `F6H` | zufällige Bytes, `retryCount × 1571` lang, Flags **8311**, **9209** (`ta_pad` ebenfalls vorhanden) |
| `reporting` | `F6L` / `F6C` | `<reporting><reporting_token v>` (16-Byte-HMAC), siehe [WA_REPORTING.md](./WA_REPORTING.md) |
| `meta` | `F6K` | Abschnitt 12 |
| `bot` | `F6M` | 13.2 |
| `hsm` | `F6X` | `category`: `OTP`, `TRANSACTIONAL`, `NON_TRANSACTIONAL`, `OTHER`; `tag`: `AUTHENTICATION`, `UTILITY`, `MARKETING` |
| `biz` | Business-Prozessor `C34748F5r` | 13.1 |
| `automated`, `multicast`, `url_text`, `url_number` | `F68` | leere Flag-Knoten aus einer Bitmaske im Builder: `2` url_text, `4` url_number, `64` multicast, `128` automated |
| `rcat` | Parser | opake binäre Kategorie (Status) |
| `cap` | `F69` | `<cap client_capping_ready="true|false">` bei Sends an JID-Typ 3 (Broadcast-Liste, inferred), Flags **16656** (emit) und **13537** (Wert) |
| `verified_name` | Business | Verified-Business-Zertifikat |
| `unavailable`, `bypassed` | Parser | Marker-Knoten; `unavailable`-Literal in 2.26.41.6 nicht gematcht (konstantenbasiert), Semantik hier unverified |

---

## 11. `<enc>`-Knoten

### 11.1 Attribute (found, `AbstractC33466EhY.A09`)

| Attribut | Wert | Bedingung |
|-----------|-------|-----------|
| `v` | `2` oder `3` | Ciphertext-Version (Receive-Parser akzeptiert `EncVersion2`, `EncVersion3`, futureproof) |
| `type` | `msg`, `pkmsg`, `skmsg`, `frskmsg`, `msmsg`, `none` | Signal-Message, Prekey-Message, Sender-Key, `frskmsg`, Bot-`msmsg`, Plaintext-Marker |
| `count` | Retry-Count | ausgelassen bei 0 |
| `mediatype` | siehe 11.2 | Media-/Interactive-Klassifikation |
| `native_flow_name` | Flow-Name | Native-Flow-Nachrichten |
| `duration` | int >= 0 | Live-Location |
| `decrypt-fail` | `hide` | Nachricht als hideable markiert (12.3) |
| `state` | `false` | `pkmsg`-Sends unter einem Flag im Ciphertext-Träger |
| `session_type` | `pq` | Post-Quantum-Session-Träger-Flag |
| `bucket` | String | wenn am Ciphertext-Träger gesetzt |

Receive-Checks (`C33013EaB`): zwei `<enc>`-Knoten in einer Nachricht müssen bei Retry-Count und Ciphertext-Version übereinstimmen; `enc` auf einem Newsletter wird abgelehnt (`Received enc message for newsletters`); `decrypt-fail=hide` wird nur beachtet, wenn die Kategorie nicht `peer` ist und das Chat-Prädikat `C1ZB.A0L` falsch ist.

### 11.2 `mediatype`-Werte, die von der Spec akzeptiert werden (found, 37 Einträge)

`audio`, `avatar_sticker`, `buttons_response`, `cataloglink`, `collection`, `contact`, `contact_array`, `document`, `feed_reshare`, `genai_sticker`, `gif`, `group_history`, `history`, `image`, `instant_image`, `list_response`, `location`, `motion_photo`, `motion_video`, `music`, `native_flow_response`, `order`, `product`, `productlink`, `ptt`, `ptv`, `request_location`, `request_location_update`, `sticker`, `sticker_pack`, `story_reply`, `url`, `user_created_sticker`, `vcard`, `video`, `xma`, `1p_sticker`. `native_flow_name`-Enum (8 Einträge): `a2ui_reply_action`, `account_authentication_request`, `address_message`, `api_signup`, `call_permission_request`, `form_message`, `galaxy_message`, `menu_options`. `sticker_type`: `avatar`.

---

## 12. `<meta>`-Knoten

Alle Attribute und Kinder werden in `EZV` von den Handlern angesammelt, die `F6K` aufruft (pro Nachrichtenklasse `FXq.AAl`, pro Add-on `FZH.AAl`) und als ein `<meta>` emittiert (`C33150EcP.A00`). Ein leerer Sammler emittiert nichts.

### 12.1 Operation-Klassifizierer (found)

| Attribut | Werte | Producer |
|-----------|--------|----------|
| `polltype` | `creation`, `edit` (`F2N`), `vote` (`DUA`), `add_option` (`F2L`, `F4E`) | Poll-Handler |
| `event_type` | `creation`, `edit` (`F2M`), **`response`** (`DU9`) | Event-Handler |
| `content_type` | `add_on` für Add-on-Klasse `AbstractC35181aQ` (umfasst Reactions; Votes / Responses inferred) in Chats, in denen `C0DZ.A0U` falsch ist; `status_notify` / `add_on` für Status-Benachrichtigungen | `F6K` |
| `type` | `scheduled_message` mit `st` (Sekunden, ausgelassen für die Unschedule-Nachrichtenklasse) und Kind `<key rkid="...">` (Key-Bytes ausgelassen für diese Klasse) | `F6K`, Conditional Reveal |
| `appdata` | freier String von `FZF.AVN()`; Bearbeiten von appdata wird abgelehnt | `F6K` |
| `tag_reason` | `user_update`, `new_member`, `rereg_recovery_request`, `rereg_recovery_response`, `user_delete` | Member-Tag-Nachricht `F3F` |
| `context_source` | `channels_invitation`, `event_invitation` (und andere) | `AJR` |
| `message_association_type` | Assoziations-Token, plus `hd_image_dual_upload`, `hevc_video_dual_upload`, `av1_video_dual_upload` bei Status-Uploads | `F4G`, `F4H` |
| `premium_type` | `1` | `F4F` |
| `thread_msg_id`, `thread_msg_sender_jid` | Parent-ID / JID | `AJT` |
| `is_status_mention` / `is_group_status_mention` | `true` | `AJS` |
| `status_setting` | `contacts`, `allowlist`, `denylist`, `customlist`; `is_group_status` `true`; Kind `mentioned_users/to` | `F4H` |
| `origin` | `ctwa`, `group_status`, `general`, plus Meta-AI-Entry-Point-Strings (`favicon`, `chat_list`, `nullstate_*`, `typeahead_*`, ...) | `F6K`, `EnumC14320eI`, `C198208bu` |
| `acp` | `2` für 1:1-Chats unter Flag **36091** (Bedeutung ungeklärt) | `F6K` |
| `view_once` | `true` für View-Once-Typen unter Flag **11282** | `F6K` |
| `sender_intent` | `hosted` | `F6K` |
| `usecase` | `migration` (Nachrichtentyp 108) | `F6K` |
| `share_pn` | `true` (Nachrichtentyp 73) | `F6K` |
| `receiver_account_kind` | `guest` | `F6K` |
| `collection_type` | `document`, `image`, `video`, `mixed` | `F6K` |
| `destination_id`, `conversation_thread_id`, `thread_origin`, `peripheral` | Bot-/Thread-Routing | `F6K` |

### 12.2 Beim Empfang geparst (found)

`<meta>`-Inputs, die der Client liest: `polltype`, `event_type`, `target_id`, `target_sender_jid`, `target_chat_jid`, `target_chat_jid_lid`, `from`, `capi` (nur Gruppenchats), `thread_msg_id`, `message_association_type`, `status_mentioned`, `push_eligible`, `session_scope`, `content_type`, `tm_csat_exp_ts`, `tm_csat_cooldown` (Sekunden, in ms gespeichert), `is_wamo_sub`, `original_msg_t`, `msg_edit_t`, und Kinder `mention_source/to`, `mentioned_users/to`. Newsletter-Metas fügen `admin_profile`, `paid_partnership`, `ai_content` hinzu (aus dem früheren Katalog aufgeführt; hier nicht neu gelesen, unverified). `deprecated_lid_session` ist bestätigt abwesend seit 2.26.45.10: erschöpfendes case-insensitive Grep über den vollständigen decodierten 2.26.45.10-Baum und WA Business 2.26.45.7 fand keinen exakten oder nahen Treffer (`found`); inferred als beabsichtigte Entfernung des Übergangs-PN→LID-Migrationsflags, nicht als Umbenennung (`inferred`).

---

## 13. `<biz>`, `<bot>`

### 13.1 `<biz>` (found, `C34748F5r.CM3`)

```xml
<biz native_flow_name="...">                       <!-- or -->
<biz>
  <interactive type="native_flow">
    <native_flow name="..."/>
  </interactive>
  <buttons/> | <list/>
</biz>
<hsm category="..." tag="..."/>                    <!-- sibling, template classification -->
```

Der Empfänger liest den Flow-Namen (`native_flow_name` oder den verschachtelten `name`), dann klassifiziert er: `buttons` vorhanden, `list` vorhanden, oder Native Flow; mit einem Namen und einem `hsm`-Sibling wird es ein Template. Validierungsfehler heißen `InvalidTemplateMessage`, `InvalidListMessage`, `InvalidButtonMessage`, `InvalidInconsistentFlowName`, `InvalidFlowNotOwned`, `InvalidDeeplyNested`: ein `biz`-Klassifizierer, der dem verschlüsselten Payload widerspricht, ist ein Validierungsfehler, kein anderer Nachrichtentyp. Andere `biz`-Attribute, anderswo gelesen: `campaign_id`, `notification_cta`, `privacy_mode_ts`, `host_storage`, `actual_actors`, `biz_bot`, Kind `quality_control` mit `decision_source`.

### 13.2 `<bot>` (found)

Outgoing (`F6M`): Attribute `type` (`request_welcome`, `prompt`, `command`, `search`, `memu_onboarding`, `memu_invoke`, `voice`, `voice_background`, `text_input`, `live_ai`, `feedback`), `client_thread_id`, `mode_selected`, `persona_type` (`1p`, `ugc`, `3p`), `local_automated_type` (`1p_partial`), `agent_engagement_type`, `is_lid`, Kind `tee_routing` (`tee_routing_token`, `tee_ik_id`). Incoming (`C34747F5q`): `<bot edit="full|...">` Standard `full`, `edit_target_id`, `sender_timestamp_ms`, `type`, `client_thread_id`; ohne `<meta target_id>` wird die Nachricht nicht als Bot-Response behandelt. Details: [WA_META_AI.md](./WA_META_AI.md).

---

## 14. Verwandte Schemata, die nicht Message-Secret sind

### 14.1 Conditional Reveal (zeitgesteuerte Nachrichten)

`conditionalRevealMessage` (Feld **120**) verwendet einen separaten zufälligen Reveal-Key (`<meta type="scheduled_message" st><key rkid>`); der Server kontrolliert das Reveal. Kein HKDF aus `messageSecret`. Reveal-Protokoll-Interna nicht nachverfolgt (unknown).

### 14.2 Reporting-Token

`reportingTokenVersion` (Feld **8**) und der 16-Byte-`<reporting_token>` verwenden den nativen Use-Case-ID-5-Key (3.4), nicht Java-HKDF. Token-Inhalt: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 15. Companion-Support-Verifier (found)

`CompanionSupportVerifier` (`C34757F6a`, nur auf einem Companion, hinter einem Flag): Nicht-`peer`-Nachrichten werden nur akzeptiert, wenn der `type` in `{text, media, reaction, poll, event}` liegt (oder `pay` mit einem Remittance-`transaction`/`pay`-Kind) und jedes direkte Kind in `{registration, enc, device-identity, verified_name, url_text, url_number, padding, biz, meta, automated, multicast, rcat, reporting, bot, hsm}` liegt. Andernfalls loggt es `unsupported child node=` / `unsupported message type=`, und die Nachricht wird auf dem Companion als unsupported klassifiziert. Ein Peer-Broadcast mit `participants` auf einem Companion wird verworfen (`received peer broadcast message on companion-mode, dropping`, Nack 415 / 18). Das neue `cap`-Kind und `tctoken` / `cstoken` sind nicht in der Liste; wo sie vor diesem Check behandelt werden, ist ungeklärt. `unavailable` und `participants` durchlaufen ihre eigenen Pfade.

---

## 16. Feature-Flags (IDs wie an den Call-Sites gelesen; Namen nicht aufgelöst)

| ID | Typ | Steuert |
|----|------|----------|
| **6772** | bool | Poll-Vote: gemeinsamer Helper vs. Legacy-Inline-Verschlüsselung |
| **31593** | bool | Poll-Vote-`metadata`-Stempelung |
| **17811** | bool | `Message Edit`-Use-Case (Senden und Empfangen) |
| **37948**, **35457** | bool | Bedingungen für das Wrapping eigener Message-Edits |
| **24886** | int | Poll-Edit empfangen (0 = abgelehnt, 10016) |
| **25758** | int | Poll Add Option empfangen (0 = abgelehnt, 10017) |
| **15791** | bool | Event-Response-Modifier LID -> PN in 1:1-Chats |
| **3142**-**3146**, **2200**, **11104**, **19303** | bool | Secret-Generierung nach Chat-Klasse |
| **8860** | int | maximale Reporting-Token-Version (Secret-Generierung) |
| **24741** | bool | Secret für Nachrichtentyp 117 |
| **36091** | bool | `meta acp="2"` |
| **11282** | bool | `meta view_once` |
| **16656**, **13537** | bool | `cap`-Kind und sein Wert |
| **8311**, **9209** | bool | Padding |
| **20605**, **20606** | bool / int | `tctoken` aktivieren / Per-Stanza-Cap |

---

## 17. Baileys (`baron-baileys-v2` 1.5.17, Quelle gelesen, nichts getestet)

Nur Fakten, die in `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js` gelesen wurden.

| Thema | Baileys | Android |
|-------|---------|---------|
| Key | `key0 = HMAC-SHA256(key = 0×32, secret)`; `decKey = HMAC-SHA256(key = key0, id ‖ creator ‖ modifier ‖ useCase ‖ 0x01)` | identisch (3.1) |
| Use-Cases | `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option`, plus `Message Schedule` für Enum 3 | gleiche Strings; Wert 3 ist in 2.26.41.6 nicht definiert |
| AAD | `id\0modifier` für Poll und Event, leer für Edit / Comment / Reaction | gleich |
| Identität | probiert PN- und LID-Kandidaten von Creator und Modifier, GCM authentifiziert das richtige Paar | gleiche Idee (7.2) |
| Fehlendes Secret | loggt, emittiert das rohe `encReactionMessage` / `pollUpdateMessage`-Update, kein Decrypt | als Orphan gespeichert |
| Secret-Generierung | `randomBytes(32)` für Poll, Event und wenn `messageContextInfo.messageSecret` fehlt | 2.2 |
| Reporting-Key | `hkdf(secret, 32, { info: id ‖ sender ‖ modifier ‖ 'Report Token' })`; Reporting wird für Reactions, `encReactionMessage`, `encEventResponseMessage`, `pollUpdateMessage` übersprungen | native ID 5 (3.4) |
| Send-Seite | für `pollUpdateMessage`, `encReactionMessage`, `encEventResponseMessage` oder `encCommentMessage` wurde in den gelesenen Dateien kein Sender gefunden | Android sendet alle vier |

Konsequenz aus dem Code gelesen: Baileys kann empfangene Follow-ups entschlüsseln, aber die gelesenen Dateien enthalten keine Verschlüsselung dafür. Ob anderswo ein Send-Helper existiert, wurde nicht durchsucht.

---

## 18. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|-------|-----|
| Fehler 11 | IV nicht 12 Byte oder leerer Payload / fehlendes Feld | `encIv` prüfen (Feld 3, oder 2 für `PollEncValue`) |
| Fehler 51 | falscher Sender-/Target-JID-Namensraum (PN vs. LID), falsche Original-ID | beide Namensräume retry, die originale (unbearbeitete) Nachrichten-ID verwenden |
| Vote für eine bearbeitete Poll schlägt fehl | Key-ID muss die Original-Poll-ID sein, nicht die neueste Edit-ID | Original-Key auflösen |
| Comment von einem PN-Sender schlägt fehl | Comment-Decrypt benötigt einen LID-Sender | die LID verwenden |
| Poll-Edit / Add Option abgelehnt | Flags **24886** / **25758** aus, oder Stanza-`polltype` widerspricht `secretEncType` | passendes `<meta polltype>` und Typ senden |
| Nachricht auf einem Companion ignoriert | unbekannter Kind-Knoten oder `type` | sich an die Allowlist halten (Abschnitt 15) |
| `<biz>`-Nachricht unsupported | Klassifizierer widerspricht dem Payload | Klassifizierer aus dem Payload ableiten |

---

## 19. Wichtige Unterscheidungen

| Dies | Nicht das |
|------|----------|
| `messageSecret` (per Nachricht, zufällig, 32 Byte) | Media-Key, Sender-Key, App-State-Sync-Key, Call-Key |
| Use-Case-Key (HKDF, pro Target / User / Use-Case) | das Secret selbst |
| `secretEncryptedMessage` (umhüllt eine vollständige `Message`) | `encReactionMessage` (umhüllt eine `ReactionMessage`) |
| `Poll Vote` / `Event Response` AAD = ID + NUL + Modifier | Edit / Comment / Reaction mit leerer AAD |
| `targetMessageKey` im äußeren Träger | `ReactionMessage.key` innerhalb des Plaintexts (beim Senden geleert) |
| `meta polltype` / `event_type` (Klassifizierer) | der verschlüsselte Payload (Inhalt) |
| `edit`-Stanza-Attribut | `secretEncType` (Verschlüsselungs-Use-Case) |
| `decrypt-fail="hide"` auf `<enc>` | Retry-Receipt / `retry`-Knoten |

---

## 20. Vollständiger Flow (Poll-Vote, 1:1 oder Gruppe)

```
[Creator]                                            [Server]                      [Voter]
   │ poll creation Message                              │                             │
   │ messageContextInfo.messageSecret = random 32       │                             │
   │ store message_secret[row]                          │                             │
   │ <message type="poll"><meta polltype="creation">────▶────────────────────────────▶ stores secret
   │                                                    │                             │
   │                                                    │      select options (hashes)│
   │                                                    │      secret = store[poll]   │
   │                                                    │      key = HKDF(secret,     │
   │                                                    │        pollId‖creator‖voter │
   │                                                    │        ‖"Poll Vote")        │
   │                                                    │      iv = random 12         │
   │                                                    │      ct = GCM(key, iv,      │
   │                                                    │        PollVoteMessage,     │
   │                                                    │        aad = pollId\0voter) │
   │              <message type="poll"><meta polltype="vote">                         │
   │◀────────────────────────────────────────────────────◀ pollUpdateMessage{key,vote{ct,iv},metadata,ts}
   │ parent found? no -> orphan, keep raw bytes         │                             │
   │ validate end time, enc iv = 12                     │                             │
   │ key = HKDF(secret, pollId‖creator‖voter‖"Poll Vote")                              │
   │ GCM-decrypt, fail -> retry PN/LID pair, else 51    │                             │
   │ check option hashes ⊂ poll options, stamp match    │                             │
   │ apply vote                                         │                             │
```

---

## 21. Ungeklärtes

| Item | Zustand |
|------|-------|
| Exakte Prädikate für `EZN.A01`, `C35201aS.A00`, Flags 3142-3146 | Per-Chat-Klassen-Gating gesehen, nutzersichtbare Menge ungeklärt |
| Native Use-Case-ID-Tabelle (Namen zu IDs außer 5 = Report Token) | nicht gelesen |
| GCM-Tag-Position und AES-Schlüsselgröße | inferred aus Konstanten und Baileys |
| Vollständige Bedingung für das Senden eigener `MESSAGE_EDIT` gewrappt vs. plain (Flags 37948, 35457) | Decompiler verlor Kontrollfluss |
| Bedeutung von `acp="2"`, Serialisierungs-Flag `A09`, zweites Poll-Add-Option-Stanza-Feld | ungeklärt |
| Konsument von `decrypt-fail="hide"` auf dem geparsten Envelope | Flag in den Envelope übernommen, Effekt nicht nachverfolgt |
| Nutzersichtbares Ergebnis eines dauerhaft nicht entschlüsselbaren Add-ons | kein Fallback-Text gefunden |
| `unavailable`, `bypassed` | in 2.26.41.6 nicht neu verifiziert |
| `deprecated_lid_session` | bestätigt abwesend seit 2.26.45.10 (erschöpfendes Grep, sowohl WhatsApp- als auch WA-Business-Baum); Entfernung vs. Umbenennung ist `inferred`, nicht bewiesen |
