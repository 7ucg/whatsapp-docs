<!-- src-sha1: 7a4b50013c0f196c95c57808469516becf9a34b7 -->
# WhatsApp Message Secrets — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** `messageSecret` pro Nachricht (Erzeugung, `MessageContextInfo`, lokaler Store, History Sync), Schlüsselableitung pro Use Case (HKDF), AES-GCM-IV / AAD, verschlüsselte Add-ons (`encReactionMessage`, `pollUpdateMessage`, `encEventResponseMessage`, `encCommentMessage`, `secretEncryptedMessage`-Edits), Identitätsbindung von Sender / Ziel und LID- / PN-Retry, Orphans und Fallbacks bei fehlendem Secret, Erweiterungen der `<message>`-Stanza (Attribute, `<enc>`-Attribute, `<meta>`, `<biz>`, `<bot>`, `<hsm>`, `<reporting>`, `<cap>`, Padding, Companion-Support-Prüfung), Feature-Flags, Vergleich mit Baileys

---

## 1. Was es ist (technisch)

Jede Nachricht, die später einen verschlüsselten Folge-Eintrag erhalten kann, trägt in ihrem eigenen Ende-zu-Ende-verschlüsselten Payload ein zufälliges 32-Byte-Secret (`MessageContextInfo.messageSecret`). Ein Folge-Eintrag (Reaction, Poll-Vote, Event-Response, Kommentar, Edit) wird mit einem Schlüssel verschlüsselt, der aus diesem Secret, der ID der Originalnachricht, dem ursprünglichen Sender und dem Modifier abgeleitet wird. Der Server leitet den Folge-Eintrag wie eine gewöhnliche E2E-Nachricht weiter, kann ihn aber weder lesen noch auf ein anderes Ziel, einen anderen Nutzer oder Use Case umlegen, ohne die GCM-Authentifizierung zu brechen. Alle Aussagen stammen aus statischer Analyse des dekompilierten APK; nichts wurde auf der Leitung mitgeschnitten. Tiers: **found** = im Code gelesen, **inferred** = aus dem Code abgeleitet, **unknown** = nicht aufgelöst. Obfuskierte Namen wurden in 2.26.41.6 anhand stabiler Strings neu aufgelöst (`MessageSecretCryptoHelper/`, `MessageEncUtils/`, Use-Case-Strings, `FMessage*Protobuf/`, `SecretEncryptedMessagePreProcessor/`, `CompanionSupportVerifier/`).

Dieselbe Version definiert auch die Erweiterungen der `<message>`-Stanza (ab Abschnitt 10): Attribute und Child Nodes, die eine Nachricht klassifizieren und routen, aber nicht ihren Inhalt tragen. Sie sind hier zusammengefasst, weil `<meta polltype>` / `<meta event_type>` mit dem secret-verschlüsselten Payload übereinstimmen müssen (7.4).

| Entität | Name in 2.26.41.6 | Rolle |
|--------|----------------|------|
| Crypto-Helper (`MessageSecretCryptoHelper`) | `C33285Eeb` | `A03` verschlüsseln, `A04` entschlüsseln (Identity-Retry), `A02` Ziel-Key auflösen |
| Parameter-Carrier für Encrypt / Decrypt | `C32833ETl` / `C32854EUg` | Daten, Sender, Ziel-Key, Use Case / IV, Payload, Keys, Sender |
| Schlüsselableitung | `AbstractC33322EfC.A02` + `AbstractC38961i0.A00` | HKDF-SHA256, Nullsalt |
| AES-GCM | `JniBridge.WCIAPIGcmAesCreateEncryptedCiphertext`, `AbstractC32243E6m.A00` (`MessageEncUtils`) | nativ, 16-Byte-Tag |
| AAD-Provider | `FXU`: `C34633F1g` (Poll Vote), `C34632F1f` (Event Response), `C34634F1h` (WASA), `C34631F1e` (keine) | Additional Data |
| Secret-Generator | `AbstractC33322EfC.A01` | `SecureRandom`, 32 Byte |
| Secret-Store (`MessageSecretStore`) / In-Memory-Extra | `C35311ad` (Tabelle `message_secret`) / `C35171aP` an der Nachricht `C13G` | persistieren und mitführen |
| Original-Key-Mapper (`ReferentialKeyUtil`) | `C43661qB.A03` | Key der unbearbeiteten Originalnachricht |
| Reaction-Handler | `DU8` (Senden), `F2P`-Zweig (Empfangen) | `reactionMessage` / `encReactionMessage` |
| Poll-Vote / Event-Response / Kommentar | `DUA` / `DU9` / `F3W` | `pollUpdateMessage` / `encEventResponseMessage` / `encCommentMessage` |
| Secret-verschlüsselte Edits (`SecretEncryptedMessagePreProcessor`) | `F3Y`, Enum `E2Q` | `secretEncryptedMessage` |
| Poll- / Event-Erstellung (Secret wird beim Empfang übernommen) | `F2N` / `F2M` | liest `messageSecret` in die FMessage |
| Proto: Context / Message / Key | `C30624DTs` / `C30628DTw` / `BD5` | `MessageContextInfo` / `Message` / `MessageKey` |
| Auswahl des Stanza-`type` | `AbstractC30999De0.A02` | `text media reaction poll event pay medianotify scheduled-call` |
| Ausgehende Stanza-Contributor | `InterfaceC35538FaZ`: `F6K` (meta), `F6M` (bot), `F68` Flags, `F69` cap, `F6H` Padding, `F6L` / `F6C` reporting, `F6G` cstoken, `F6I` tctoken, `F6B` device-identity, `F6X` hsm | bauen Children von `<message>` |
| `<meta>`-Akkumulator | `EZV` (Attribute `A01`, Children `A00`) | ein `<meta>`-Node |
| `<enc>`-Attribut-Builder | `AbstractC33466EhY.A09` | `v type count mediatype ...` |
| Companion-Support-Prüfung | `C34757F6a` + `AbstractC32927EXc` | Allowlist für Typ und Children |
| Eingehende Spec-Parser | `C33474Ehg` (Status / regulär), `C23206A1f` (Newsletter), `C34747F5q` (Bot), `C34748F5r` (Biz) | Extraktion von Attributen und Children |
| WAM-Fehler-Event | `DZ7` / `C273212s` | `wam_message_secret_errors` |

---

## 2. Das Secret pro Nachricht

### 2.1 Wo es liegt (found)

`MessageContextInfo` (`C30624DTs`) ist Feld **35** von `Message` (`C30628DTw`). Relevante Felder:

| Feld | Nummer | Typ | Verwendung |
|-------|--------|------|-----|
| `deviceListMetadata` / `deviceListMetadataVersion` | **1** / **2** | message / int | Device-List-Hinweis (ohne Bezug zum Secret) |
| `messageSecret` | **3** | bytes (32) | Secret pro Nachricht |
| `paddingBytes` | **4** | bytes | Padding |
| `messageAddOnDurationInSecs` | **5** | uint32 | Lebensdauer des Add-ons (Pin: muss für Unpin 0 sein) |
| `botMessageSecret` | **6** | bytes (32) | Bot-Variante des Secrets |
| `botMetadata` | **7** | message | Bot-Kontext |
| `reportingTokenVersion` | **8** | uint32 | Version des Reporting-Tokens dieser Nachricht |
| `messageAddOnExpiryType` | **9** | enum | Ablauf des Add-ons |
| `messageAssociation` | **10** | message | Association |

Der History-Sync-Carrier `WebMessageInfo` (`C30626DTu`) hat ein eigenes Feld `messageSecret` **49** (found), das beim Export von Nachrichten an einen neuen Companion verwendet wird (Abschnitt 2.4).

### 2.2 Erzeugung (found, Bedingungen teils inferred)

Das Secret ist `SecureRandom.nextBytes(byte[32])` (`AbstractC33322EfC.A01`). Es wird vor der Serialisierung der Nachricht angehängt:

| Stelle | Bedingung |
|-------|-----------|
| `C33166Ecf.A06` (Senden vorbereiten) | Nachricht hat kein Secret und mindestens eines von: Poll-Klasse `C13J`; `EZN.A01(msg)` (Bot- / Add-on-Klasse, mit Chat-Typ-Flags **2200**, **11104**, **19303**); Chat-Klassen-Gates: Gruppe mit Flag **3143**, Broadcast-Liste mit **3144**, Status mit **3145**, Klassen-Gate **3146**; `C35201aS.A00` (Flag **3142**, Self- / Bot-Chat); Event-Nachricht `C213509Ao` |
| `AJ0` (Send-Prozessor) | Reporting-Token-Version `C35241aW.A05()` (AB-Int **8860**, begrenzt durch `AbstractC35301ac.A00`) ist ungleich null und die Nachrichtenklasse ist nicht durch `C35241aW.A02` ausgeschlossen (Status, Newsletter, ausgewählte Add-on-Klassen) |
| `C72h`, `C34455Exe`, `EPA` | Status-Objekte (`AbstractC34478Ey1.A0R`) erhalten bei der Erstellung ein frisches Secret |
| `C33437Eh4` | Bot-Nachricht "request welcome", nur wenn der Aufrufer es verlangt |
| `C9mW` | Nachrichtentyp 117, Flag **24741**, wenn keines vorhanden ist |

Die Prädikate hinter `EZN.A01`, `C35201aS.A00` und den `3142`..`3146`-Gates wurden nicht vollständig aufgelöst; die Liste oben sagt, was der Code prüft, nicht welche für Nutzer sichtbaren Nachrichten sich qualifizieren. Nachrichten ohne Secret können von diesem Client keine verschlüsselten Add-ons erhalten (Abschnitt 9).

### 2.3 Lokale Speicherung (found)

`C35311ad` schreibt `message_secret(message_row_id, message_secret)` mit Replace-Semantik (`MessageSecretStore/insertMessageSecret`) und liest die letzte Zeile zu einer `message_row_id`. Die FMessage hält es als Extra `C35171aP` (`A0L` setzen, `A0c` lesen, `A0Q` = nicht leer). Zwei Prozessoren in `AbstractC17240jU` (`C35161aO` und ein anonymer) schreiben es, wenn das Extra dirty ist und sich der Chat qualifiziert.

### 2.4 Validierung und Transfer beim Empfang (found)

| Schritt | Verhalten |
|------|-----------|
| Proto-Validator `C33475Ehh.A0V` | `message_secret` muss exakt **32** Byte lang sein, Fehlercode **67**; die Bot-Variante (`bot_message_secret`, Gruppe `whatsapp_security`) wird genauso validiert |
| Poll-Erstellung `F2N` | kopiert `messageSecret_` in die neue FMessage (`A0L`) |
| Antworten auf Status-Fragen `C34838F9e` | dieselbe Kopie für `statusQuestionAnswerMessage` |
| History-Sync-Export `C34388EwZ.A00` | schreibt das gespeicherte Secret in `WebMessageInfo.messageSecret` (49) |
| History-Sync-Import `C34388EwZ.C59` | kopiert es zurück (`A0L`) |
| Kommentare `C34387EwY` | baut aus `WebMessageInfo.messageSecret` einen `MessageContextInfo` für den Kommentar-Thread neu auf |

`wam_message_secret_errors` (`DZ7`, `C273212s.A00`) loggt `message_secret_error` **0** = fehlt (entspricht Fehlercode 66) oder **1** = ungültige Länge (67) bei Nachrichten, die ein Secret benötigen (`AbstractC33322EfC.A00`: hat das Flag und ist nicht Klasse `C35281aa`).

---

## 3. Schlüsselableitung pro Use Case

### 3.1 Formel (found, `AbstractC33322EfC.A02`)

```text
info = UTF8(originalMessageId) ‖ UTF8(targetSender.rawString) ‖ UTF8(modifier.rawString) ‖ UTF8(useCase)
prk  = HMAC-SHA256(key = 32 × 0x00, data = messageSecret)          // HKDF extract
key  = HMAC-SHA256(key = prk, data = info ‖ 0x01)                  // HKDF expand, L = 32, one block
```

`AbstractC38961i0.A00(secret, info, 32)` = Extract mit einem 32-Byte-Nullsalt (`AbstractC38971i1.A00(ikm, salt)`), danach die Expand-Schleife nach RFC 5869. HKDF-Grundlagen: [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md) Abschnitt 5.1. Die 32-Byte-Ausgabe wird als AES-256-Key verwendet (inferred aus der Länge; der native Aufruf nimmt den Key als `byte[]`).

Eingaben:

| Eingabe | Quelle | Hinweise |
|-------|--------|-------|
| `originalMessageId` | Key-ID des Ziels nach `ReferentialKeyUtil` (`C43661qB.A03`) beim Verschlüsseln; Key-ID aus dem Proto `targetMessageKey` beim Entschlüsseln | bei einem bearbeiteten Ziel ist das die **ursprüngliche** Nachrichten-ID (Log `getOriginalKey`) |
| `targetSender` | Autor der Originalnachricht: gespeicherter Sender (`C12300aw.A01`) | `UserJid`, also ohne Device-Suffix (auf Typebene; die String-Form `user@server` ist inferred) |
| `modifier` | Autor des Add-ons: eigene Konto-JID (`C09A.A0G`, eine LID, geliefert von `CUC()` / `Ash()`) beim Senden, die Sender-JID des Envelope beim Empfangen | |
| `useCase` | String aus 3.2 | kein Trennzeichen zwischen den vier Komponenten |

Die eigene JID ist eine LID-Konto-JID (`C14080dr`, Server `lid`, Prüfung "Invalid LID"). Sowohl `AnonymousClass091.Ash()` als auch `CUC()` liefern dasselbe Feld.

### 3.2 Use-Case-Strings (found)

| Use Case | Carrier | AAD | Java-Literal in 2.26.41.6 |
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
| `Report Token` | Key des Reporting-Tokens | nativ | kein Java-Literal; in `libwhatsapp.so` vorhanden, nativ abgeleitet (3.4) |

### 3.3 Bot- / WASA-Variante (found, Details inferred)

Für den Use Case `WASA` hat die Ableitung zwei Stufen und in der zweiten keinen Use-Case-String:

```text
k1  = HKDF-SHA256(secret, salt = 0×32, info = "Bot Message", L = 32)      // AbstractC33322EfC.A00
key = HKDF-SHA256(k1,     salt = 0×32, info = id ‖ jidA.raw ‖ jidB.raw, L = 32)
AAD = UTF8(keyId) ‖ 0x00 ‖ UTF8(modifier.raw)                              // C34634F1h
```

`jidA` ist der Modifier und `jidB` die Remote- (Chat-) JID, die eine `UserJid` sein muss (`WASA info jid must be a UserJid (hatch_jid)`); die ID ist der aktuelle Message-Key, falls vorhanden, sonst der Ziel-Key (Lambda `C33285Eeb.A03`). Natives Gegenstück: `WcmBotMessageSecretAPICreateWithMessageSecret`. Meta-AI-Kontext: [WA_META_AI.md](./WA_META_AI.md).

### 3.4 Key des Reporting-Tokens (found / inferred)

`C33364Efs.A06` und `C33421Ego` rufen `JniBridge.WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)` auf: Das native Objekt leitet den Key für Use-Case-ID **5** ab; die Java-Seite reicht nur JID-Raw-Strings durch. Der String `Report Token` existiert in der nativen Bibliothek; die Zuordnung von ID 5 zu diesem String ist inferred. Token und Upload: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 4. AEAD-Layout

| Element | Wert | Tier |
|------|-------|------|
| Cipher | AES-GCM, nativ (`WCIAPIGcmAesCreateEncryptedCiphertext(key, iv, plaintext, aad, 16)`; Decrypt `jvidispatchOIOOOOO(6, 16L, ctx, key, iv, ciphertext, aad)`) | found |
| Key | 32 Byte aus Abschnitt 3 | found |
| IV | **12** zufällige Byte pro Verschlüsselung (`SecureRandom`); Decrypt lehnt jede andere Größe ab | found |
| Tag | 16 Byte; die Konstante 16 wird bei beiden Aufrufen übergeben; Position (an den Ciphertext angehängt) aus dem Baileys-Decrypt inferred | found / inferred |
| AAD | pro Use Case (3.2); `null`, wenn der Provider `C34631F1e` ist | found |
| Plaintext | das serialisierte innere Proto (Tabelle 5) | found |
| Ausgabe | Tripel `(encIv, encPayload, targetMessageKey)` (`C53966OMp`) | found |
| Leeres Ergebnis | Log `encryption values are invalid`, Fehler `Encryption using iJniBridge failed` | found |

Poll-Vote-Retry: Hält der Vote bereits IV und Payload (`C30957Dd6.A03` / `A04`), wird derselbe Ciphertext erneut gesendet, statt neu zu verschlüsseln (found, Legacy-Zweig in `DUA`).

---

## 5. Carrier und Plaintexts

| Carrier (Feld in `Message`) | Klasse | Felder | Entschlüsselter Plaintext |
|------------------------------|-------|--------|---------------------|
| `encReactionMessage` **56** | `DRO` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `ReactionMessage` (`DSH`): `key` **1** (vor dem Verschlüsseln gelöscht), `text` **2**, `groupingKey` **3**, `senderTimestampMs` **4** |
| `pollUpdateMessage` **50** | `DSG` | `pollCreationMessageKey` **1**, `vote` **2** (`PollEncValue` `C30530DQc`: `encPayload` **1**, `encIv` **2**), `metadata` **3** (`C30532DQe`: `pollNameHash` **1**, `lastEditStanzaId` **2**), `senderTimestampMs` **4** | `PollVoteMessage` (`DPF`): `selectedOptions` **1** (repeated bytes, Option-Hashes) |
| `encEventResponseMessage` **76** | `DRN` | `eventCreationMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `EventResponseMessage` (`DRP`): `response` **1** (`E2D`: 0 unknown, 1 going, 2 not going, 3 maybe), `timestampMs` **2**, `extraGuestCount` **3** |
| `encCommentMessage` **71** | `DRM` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | vollständige `Message` (der Kommentartext); die Plaintext-Form ist `commentMessage` **77** (`DQV`: `message` **1**, `targetMessageKey` **2**) |
| `secretEncryptedMessage` **82** | `DSI` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3**, `secretEncType` **4** | vollständige `Message` |
| `reactionMessage` **46** | `DSH` | Plaintext-Form | einfache Reaction |
| `conditionalRevealMessage` **120** | n/a | nicht das Message-Secret-Schema (Abschnitt 14.1) | geplante Nachrichten |

`SecretEncType` (`E2Q`): `UNKNOWN` 0, `EVENT_EDIT` **1**, `MESSAGE_EDIT` **2**, `POLL_EDIT` **4**, `POLL_ADD_OPTION` **5**. Der Wert 3 existiert in diesem Build nicht (`forNumber(3)` liefert null, wird als unknown behandelt und abgelehnt).

`MessageKey` (`BD5`): `remoteJid` **1**, `fromMe` **2**, `id` **3**, `participant` **4**.

---

## 6. Sender-Seite

### 6.1 Gemeinsamer Pfad (found, `C33285Eeb.A03`)

1. Ziel-FMessage per Key auflösen (`target message not found. Cannot proceed further` -> Fehler 71).
2. Das Secret aus `message_secret` lesen; null oder Länge != 32 -> `message secret missing or invalid` (66).
3. Original-Key über `C43661qB.A03` (null -> Fehler 0). Ziel-Sender über `C12300aw.A01`.
4. In einem 1:1-Chat (`C0DZ.A0k(chat)`) wird der Ziel-Sender in den Namespace des Modifiers umgerechnet: Modifier LID und Ziel PN -> Ziel von PN auf LID gemappt; Modifier PN und Ziel LID -> Ziel von LID auf PN gemappt. In Gruppen keine Konvertierung.
5. Nur Event Response: Flag **15791**, 1:1-Chat und ein Modifier vom Typ Konto -> Modifier wird in PN umgerechnet.
6. Zufälliger 12-Byte-IV, Key ableiten (3.1), AES-GCM mit der AAD des Use Case.
7. Den äußeren `MessageKey` aus Ziel-Sender und Original-Key bauen (`C32717EOy.A01`); der Carrier enthält `targetMessageKey`, `encIv`, `encPayload`.

### 6.2 Pro Carrier (found)

| Carrier | Gate beim Senden |
|---------|--------------|
| Reaction (`DU8.ADr`) | verschlüsselt **nur**, wenn der Chat eine Gruppe (`C0DZ.A0l`) mit `group_type == 3` ist (`C0GQ.A0A`; gesetzt in `CMP` aus `isDefaultSubgroup_`, also ein Default-Subgroup einer Community, Interpretation inferred) und das Serialization-Context-Flag `A09` false ist. In jedem anderen Chat wird die einfache `reactionMessage` gesendet. `ReactionMessage.key` wird vor dem Verschlüsseln auf null gesetzt (der Key wandert in den äußeren `targetMessageKey`) |
| Poll-Vote (`DUA.ADr`) | Flag **6772** an: gemeinsamer Helper, immer verschlüsselt; aus: Legacy-Inline-Zweig mit derselben Ableitung und AAD (Ziel-Sender = eigene LID bei eigenen Polls, sonst die aus dem Ziel-Key des Votes abgeleitete JID; Modifier = eigene LID). `metadata` (`pollNameHash`, optional `lastEditStanzaId`) wird gesetzt, wenn Flag **31593** an ist |
| Event-Response (`DU9.ADr`) | immer verschlüsselt; der Plaintext `EventResponseMessage` hat `response`, `timestampMs`, `extraGuestCount` |
| Kommentar (`F3W.ADr`) | immer verschlüsselt; der Plaintext ist die gesamte Kommentar-`Message`; das Ziel ist der Parent-Key von `CommentMessageInfo` |
| Secret-verschlüsselter Edit (`F3Y.C5S`) | nur wenn die Nachricht Edit-Info vom Typ `E2Q` hat und der Serialization Context nicht forwarded / orphan ist; `MESSAGE_EDIT` braucht zusätzlich Flag **17811** (sonst wirft `getUseCase`). Bei Edits eigener Nachrichten zeigen zwei Logzeilen (`sending the Message Yourself edit unwrapped`, `sending the agent reply edit unwrapped`) Fälle, die als einfache Edits gesendet werden; die vollständige Bedingung (Flags **37948**, **35457**) ging bei der Dekompilierung verloren |

Verschachtelte secret-verschlüsselte Payloads werden auf beiden Seiten abgelehnt (`nested_secret_encrypted_message`).

---

## 7. Empfänger-Seite

### 7.1 Decrypt (found, `C33285Eeb.A04`)

```text
target key  = A02(remoteSender, messageKey, proto.targetMessageKey)       // perspective flip, Ddz.A00
parent      = message store lookup (ReferentialKeyUtil)
secret      = message_secret[parent.row]                                   // null -> 66, len != 32 -> 67
checks      = IV == 12 bytes, payload non-empty (else 11), senderUserJid != null, targetSender != null
key, aad    = section 3 / 4
plaintext   = AES-GCM-decrypt(key, iv, payload, aad)                       // fail -> identity retry
```

`senderUserJid` (Modifier) pro Carrier: eigene LID, wenn der Envelope von mir stammt; Poll: Sender-JID (`c0df` oder `B4g()`); Event-Response: Chat-User im 1:1, sonst Envelope-User; Kommentar: nur LID (`C0DZ.A0Y`: Typen 18, 19, 25), ein PN-Sender scheitert mit Fehler 0; Reaction: Envelope-Sender nur, wenn er eine LID ist, sonst null.

### 7.2 LID- / PN-Identity-Retry (found Struktur, Ende inferred)

Der erste Versuch verwendet die JIDs wie übergeben. Bei einem Fehlschlag mappt der Helper beide JIDs in den jeweils anderen Namespace (`C0YH.A0I` LID->PN, `A0F` PN->LID) und versucht es einmal erneut; waren beide bereits LID oder fehlt das Mapping, lautet das Ergebnis Fehler **51** (Decrypt fehlgeschlagen). Das dekompilierte Ende des Retry ist teilweise verloren, daher ist die genaue Menge der versuchten Paare inferred. Die Prüfung ist die GCM-Authentifizierung: Ein falsches Paar scheitert, das richtige entschlüsselt.

### 7.3 Parent fehlt: Orphans (found)

| Carrier | Verhalten, wenn der Parent nicht gefunden wird oder ein Placeholder ist |
|---------|-----------------------------------------------------------|
| Reaction | FMessage Typ **56** wird mit den rohen `Message`-Bytes gespeichert (`DdA(key, 56, ts).A02`); Decrypt wird aufgeschoben |
| Poll-Vote | `C30957Dd6.A02 = Message.toByteArray()`; unentschlüsselt gespeichert |
| Event-Response | `Dd7(key, target, bytes, ts)` unentschlüsselt gespeichert |
| Kommentar | Placeholder `C34671Zb` mit Parent-Key und Row `-1` |
| Secret-verschlüsselter Edit | `DeD(MessageOrphan)` mit Orphan-Typ **5**, Grund **1** (Parent fehlt) oder **2** (Placeholder) |

Ein Replay beim Eintreffen des Parents ist zu erwarten (Orphans werden mit den rohen Bytes persistiert), der Replay-Trigger wurde aber nicht nachverfolgt (inferred).

### 7.4 Validierung nach dem Decrypt (found)

| Fall | Prüfung | Fehlschlag |
|------|-------|---------|
| Stanza `type=poll` + `<meta polltype="edit">` | `secretEncType` muss `POLL_EDIT` sein | `poll_edit_message_stanza_invalid` (76) |
| `polltype="add_option"` | Typ `POLL_ADD_OPTION` und ein zweites Stanza-Feld gleich `poll_add_option` (Feld unaufgelöst) | `poll_add_option_stanza_invalid` (76) |
| Event-Edit | innerer Nachrichtentyp 92, resultierender Key gleich dem äußeren Key | `invalid secret encrypted message` (76) / `the resulting message key does not match outer key` |
| Poll-Edit | innerer Typ 66, beide Nachrichten Polls, gleiche Endzeit und Flags, Option-Edits konsistent mit den gespeicherten Optionen, Timestamp nicht nach der Endzeit | `poll_edit_invalid_edits`, `poll_edit_invalid_option_edits`, `poll_edit_invalid_time` |
| Poll Add Option | innerer Typ 137, Parent ist ein Poll, Ziel-Key gleich dem äußeren Key, nicht nach der Endzeit | `poll_add_option_past_end_time` |
| Poll-Edit empfangen | AB-Int **24886** muss ungleich null sein | Fehler 10016 ("futureproofing") |
| Poll Add Option empfangen | AB **25758** muss ungleich null sein | Fehler 10017 |
| Poll-Vote | Auswahl muss für den Poll gültig sein (`AbstractC33199EdC.A02`); Vote-Timestamp nicht nach der Poll-Endzeit | `poll_update_past_end_time`, `invalid poll vote selection` |
| Poll-Vote-Metadata | `pollNameHash` + `lastEditStanzaId` werden gegen den gespeicherten Poll geprüft (`C32977EZa.A01`); "unstamped", wenn nicht vorhanden; bei Abweichung wird der Vote verworfen | `poll_update_tc_drop` |
| Form des Poll-Votes | IV genau 12 (`poll_update_invalid_vote_enc_iv`), Payload vorhanden, Sender-Timestamp vorhanden | Fehler 11 |
| Event-Response | Key, IV (12), Payload vorhanden; der Parent muss ein Event oder eine Sender-Revoke-Nachricht sein | `parent message is not event message nor sender revoke` |

---

## 8. Bindung von Sender / Ziel

| Durch den Key gebunden | Wirkung |
|------------------|--------|
| ID der Originalnachricht | ein Ciphertext kann nicht für eine andere Nachricht wiederverwendet werden |
| JID des Ziel-Senders | kann keinem anderen ursprünglichen Autor zugeschrieben werden |
| JID des Modifiers | kann nicht als Add-on eines anderen Nutzers wiedereingespielt werden |
| Use-Case-String | ein Reaction-Ciphertext entschlüsselt sich nicht als Vote, Kommentar oder Edit |
| AAD (Poll-Vote, Event-Response) | bindet zusätzlich `targetId` und Modifier in den Tag ein |

Nicht gebunden: Chat-JID, Timestamp, Position des Ciphertexts im Thread, Anzahl früherer Add-ons. Das `participant` / `from` des Envelope verwendet der Empfänger als Modifier; es wird durch die E2E-Session authentifiziert, nicht durch das Secret. Jeder, der das Original-Secret besitzt (in einer Gruppe jeder Teilnehmer, der die Originalnachricht erhalten hat), kann Keys für beliebige Modifier ableiten; das Schema verhindert ein Retargeting auf Relay-Seite, nicht aber Impersonation durch Gruppenmitglieder (inferred aus der Konstruktion).

---

## 9. Fallbacks bei fehlendem Secret (found, sofern nicht anders markiert)

| Situation | Sender | Empfänger |
|-----------|--------|-----------|
| Original hat kein Secret | Verschlüsselung schlägt fehl (66); Poll-Legacy-Pfad: `invalid message_secret secretSize` | Parent vorhanden, Secret null: Fehler **66**, an den Error Reporter geloggt mit `parentMsgRowId`, `parentType`, `parentHasSecret`; `wam_message_secret_errors` Code 0 |
| Secret nicht 32 Byte | Verschlüsselung abgelehnt | Fehler **67**, WAM-Code 1 |
| Parent nicht gefunden | Encrypt-Fehler 71 | als Orphan gespeichert (7.3) |
| Reaction in einem Chat, der keine Default-Subgroup ist | stattdessen wird die einfache `reactionMessage` gesendet (kein Secret nötig) | vom einfachen Zweig behandelt |
| Message-Edit ohne Flag 17811 | `getUseCase` wirft (`unknown message secret encrypted type`, Code 0); ob der Sender den Typ bei ausgeschaltetem Flag vermeidet, ist unaufgelöst | derselbe Throw |
| Add-on-Decrypt schlägt fehl | n/a | Add-on bleibt versteckt / nicht verfügbar; kein sichtbarer Fallback-Text gefunden (unknown) |
| Neuer Companion ohne das Original | n/a | der History Sync trägt das Secret in `WebMessageInfo.messageSecret` (2.4) |
| `<enc decrypt-fail="hide">` | gesetzt bei Nachrichten mit Edit-Info (12.3) | weist den Empfänger an, keinen Fehler-Placeholder anzuzeigen; Konsument des Flags unaufgelöst |

---

## 10. `<message>`-Stanza: was der Client hinzufügt

Ausgehende Children werden von unabhängigen Contributors (`InterfaceC35538FaZ`) gebaut, die an den Stanza-Builder `C33150EcP` anhängen.

### 10.1 Attribute (found)

| Attribut | Producer / Consumer | Werte / Bedeutung |
|-----------|--------------------|-------------------|
| `type` | `AbstractC30999De0.A02` | `text`, `media`, `reaction`, `poll`, `event`, `pay`, `medianotify`, `scheduled-call` (aus dem Proto): `secretEncryptedMessage` mit `EVENT_EDIT` -> `event`, mit `POLL_EDIT` / `POLL_ADD_OPTION` -> `poll`; `MESSAGE_EDIT` fällt durch auf `text` / `media`; Reaction-Felder (einfach oder enc) -> `reaction`; Poll-Update / -Erstellung -> `poll`; `encEventResponseMessage` und Event -> `event` |
| `edit` | Receive-Specs `C33474Ehg` (erfordert Node-Tag `status`; sein Verhältnis zur einfachen `<message>`-Stanza ist unaufgelöst), `C23206A1f` (Newsletter); Acks `AbstractC33465EhX.A05` | `1`, `7`, `8` in `C33474Ehg`; `3` und `8` in der Newsletter-Spec; Acks spiegeln es, außer bei `0` / leer; siehe 10.2 |
| `category` | Stanza, Acks, Retry-Receipts | `peer` wählt den Peer-Message-Pfad |
| `device_fanout` | `F6M` | `"false"` bei gezielten 1:1-Retries |
| `addressing_mode`, `participant`, `recipient`, `expiration`, `offline`, `dhash`, `sts` | Transport | Identität / Lifecycle, nicht Inhalt |
| `peer_recipient_pn`, `peer_recipient_lid`, `peer_recipient_username`, `recipient_latest_lid`, `participant_username`, `sender_account_kind`, `sender_country_code`, `eph_setting` | Identity-Parser (`AbstractC33466EhY`, `C34763F6g`) | PN- / LID- / Username-Aliase |

### 10.2 `edit`-Werte

| Wert | Kontext | Tier |
|-------|---------|------|
| `1` | Edit einer gesendeten Nachricht (geparst in `C33474Ehg.A0L`) | found |
| `2` | Pin im Chat: der Receive-Pfad verlangt interne Edit-Version 2 (`Invalid edited version`) | inferred Zuordnung zum Attribut |
| `3` | Edit einer Newsletter-Nachricht: nur in der Newsletter-Spec geparst (`C23206A1f.A0G`), und `EWW.A01` setzt Edit-Version 3, wenn der Chat ein Newsletter ist (JID-Typ 21, Server `newsletter`) | found (löst das frühere "unknown 3" auf) |
| `7` | Revoke durch den Sender (`C33474Ehg.A0M`) | found |
| `8` | Admin-Delete (`C33474Ehg.A0S`, Newsletter-Spec `A0H`) | found |
| `0` / leer | normale Nachricht; in Acks weggelassen | found |

Die interne Edit-Version (`EWW.A01`) ist `1` für normale Chats und `3` für Newsletter; Edits in normalen Chats setzen außerdem das Hide-Flag `decrypt-fail` (12.3).

### 10.3 Direkte Children (found)

| Child | Producer | Bedeutung |
|-------|----------|---------|
| `enc` | Verschlüsselungsschicht | Ciphertext, siehe Abschnitt 11 |
| `participants` / `to` | `F6E` und Fanout | Ciphertexts pro Device |
| `device-identity` | `F6B` | signierte Device-Identity |
| `registration` | Parser `C33474Ehg.A04` | exakt 4 Byte |
| `tctoken` | `F6I`, `AbstractC33466EhY.A01` | höchstens AB-Int **20606** pro Stanza, aktiviert durch **20605** |
| `cstoken` | `F6G` | Cold-Contact-Token |
| `padding` | `F6H` | Zufallsbytes, `retryCount × 1571` lang, Flags **8311**, **9209** (`ta_pad` ebenfalls vorhanden) |
| `reporting` | `F6L` / `F6C` | `<reporting><reporting_token v>` (16-Byte-HMAC), siehe [WA_REPORTING.md](./WA_REPORTING.md) |
| `meta` | `F6K` | Abschnitt 12 |
| `bot` | `F6M` | 13.2 |
| `hsm` | `F6X` | `category`: `OTP`, `TRANSACTIONAL`, `NON_TRANSACTIONAL`, `OTHER`; `tag`: `AUTHENTICATION`, `UTILITY`, `MARKETING` |
| `biz` | Business-Prozessor `C34748F5r` | 13.1 |
| `automated`, `multicast`, `url_text`, `url_number` | `F68` | leere Flag-Nodes aus einer Bitmaske im Builder: `2` url_text, `4` url_number, `64` multicast, `128` automated |
| `rcat` | Parser | opake binäre Kategorie (Status) |
| `cap` | `F69` | `<cap client_capping_ready="true|false">` bei Sends an JID-Typ 3 (Broadcast-Liste, inferred), Flags **16656** (ausgeben) und **13537** (Wert) |
| `verified_name` | Business | Zertifikat des verifizierten Business |
| `unavailable`, `bypassed` | Parser | Marker-Nodes; das Literal `unavailable` wurde in 2.26.41.6 nicht gefunden (konstantenbasiert), Semantik hier nicht verifiziert |

---

## 11. `<enc>`-Node

### 11.1 Attribute (found, `AbstractC33466EhY.A09`)

| Attribut | Wert | Bedingung |
|-----------|-------|-----------|
| `v` | `2` oder `3` | Ciphertext-Version (der Receive-Parser akzeptiert `EncVersion2`, `EncVersion3`, futureproof) |
| `type` | `msg`, `pkmsg`, `skmsg`, `frskmsg`, `msmsg`, `none` | Signal-Message, Prekey-Message, Sender Key, `frskmsg`, Bot-`msmsg`, Plaintext-Marker |
| `count` | Retry-Zähler | weggelassen bei 0 |
| `mediatype` | siehe 11.2 | Klassifikation Media / interaktiv |
| `native_flow_name` | Flow-Name | Native-Flow-Nachrichten |
| `duration` | int >= 0 | Live-Standort |
| `decrypt-fail` | `hide` | Nachricht als versteckbar markiert (12.3) |
| `state` | `false` | `pkmsg`-Sends unter einem Flag im Ciphertext-Carrier |
| `session_type` | `pq` | Carrier-Flag für Post-Quantum-Session |
| `bucket` | String | wenn am Ciphertext-Carrier gesetzt |

Prüfungen beim Empfang (`C33013EaB`): Zwei `<enc>`-Nodes in einer Nachricht müssen bei Retry-Zähler und Ciphertext-Version übereinstimmen; `enc` an einem Newsletter wird abgelehnt (`Received enc message for newsletters`); `decrypt-fail=hide` wird nur beachtet, wenn die Kategorie nicht `peer` ist und das Chat-Prädikat `C1ZB.A0L` false ist.

### 11.2 Von der Spec akzeptierte `mediatype`-Werte (found, 37 Einträge)

`audio`, `avatar_sticker`, `buttons_response`, `cataloglink`, `collection`, `contact`, `contact_array`, `document`, `feed_reshare`, `genai_sticker`, `gif`, `group_history`, `history`, `image`, `instant_image`, `list_response`, `location`, `motion_photo`, `motion_video`, `music`, `native_flow_response`, `order`, `product`, `productlink`, `ptt`, `ptv`, `request_location`, `request_location_update`, `sticker`, `sticker_pack`, `story_reply`, `url`, `user_created_sticker`, `vcard`, `video`, `xma`, `1p_sticker`. `native_flow_name`-Enum (8 Einträge): `a2ui_reply_action`, `account_authentication_request`, `address_message`, `api_signup`, `call_permission_request`, `form_message`, `galaxy_message`, `menu_options`. `sticker_type`: `avatar`.

---

## 12. `<meta>`-Node

Alle Attribute und Children werden in `EZV` von den Handlern gesammelt, die `F6K` aufruft (pro Nachrichtenklasse `FXq.AAl`, pro Add-on `FZH.AAl`), und als ein `<meta>` ausgegeben (`C33150EcP.A00`). Ein leerer Akkumulator gibt nichts aus.

### 12.1 Operations-Klassifikatoren (found)

| Attribut | Werte | Producer |
|-----------|--------|----------|
| `polltype` | `creation`, `edit` (`F2N`), `vote` (`DUA`), `add_option` (`F2L`, `F4E`) | Poll-Handler |
| `event_type` | `creation`, `edit` (`F2M`), **`response`** (`DU9`) | Event-Handler |
| `content_type` | `add_on` für die Add-on-Klasse `AbstractC35181aQ` (enthält Reactions; Votes / Responses inferred) in Chats, in denen `C0DZ.A0U` false ist; `status_notify` / `add_on` für Status-Benachrichtigungen | `F6K` |
| `type` | `scheduled_message` mit `st` (Sekunden, bei der Unschedule-Nachrichtenklasse weggelassen) und Child `<key rkid="...">` (Key-Bytes bei dieser Klasse weggelassen) | `F6K`, Conditional Reveal |
| `appdata` | freier String aus `FZF.AVN()`; das Bearbeiten von appdata wird abgelehnt | `F6K` |
| `tag_reason` | `user_update`, `new_member`, `rereg_recovery_request`, `rereg_recovery_response`, `user_delete` | Member-Tag-Nachricht `F3F` |
| `context_source` | `channels_invitation`, `event_invitation` (und weitere) | `AJR` |
| `message_association_type` | Association-Token, dazu `hd_image_dual_upload`, `hevc_video_dual_upload`, `av1_video_dual_upload` bei Status-Uploads | `F4G`, `F4H` |
| `premium_type` | `1` | `F4F` |
| `thread_msg_id`, `thread_msg_sender_jid` | Parent-ID / -JID | `AJT` |
| `is_status_mention` / `is_group_status_mention` | `true` | `AJS` |
| `status_setting` | `contacts`, `allowlist`, `denylist`, `customlist`; `is_group_status` `true`; Child `mentioned_users/to` | `F4H` |
| `origin` | `ctwa`, `group_status`, `general`, dazu Meta-AI-Entry-Point-Strings (`favicon`, `chat_list`, `nullstate_*`, `typeahead_*`, ...) | `F6K`, `EnumC14320eI`, `C198208bu` |
| `acp` | `2` für 1:1-Chats unter Flag **36091** (Bedeutung unaufgelöst) | `F6K` |
| `view_once` | `true` für View-Once-Typen unter Flag **11282** | `F6K` |
| `sender_intent` | `hosted` | `F6K` |
| `usecase` | `migration` (Nachrichtentyp 108) | `F6K` |
| `share_pn` | `true` (Nachrichtentyp 73) | `F6K` |
| `receiver_account_kind` | `guest` | `F6K` |
| `collection_type` | `document`, `image`, `video`, `mixed` | `F6K` |
| `destination_id`, `conversation_thread_id`, `thread_origin`, `peripheral` | Bot- / Thread-Routing | `F6K` |

### 12.2 Beim Empfang geparst (found)

`<meta>`-Eingaben, die der Client liest: `polltype`, `event_type`, `target_id`, `target_sender_jid`, `target_chat_jid`, `target_chat_jid_lid`, `from`, `capi` (nur Gruppenchats), `thread_msg_id`, `message_association_type`, `status_mentioned`, `push_eligible`, `session_scope`, `content_type`, `tm_csat_exp_ts`, `tm_csat_cooldown` (Sekunden, in ms gespeichert), `is_wamo_sub`, `original_msg_t`, `msg_edit_t` sowie die Children `mention_source/to`, `mentioned_users/to`. Newsletter-Metas ergänzen `admin_profile`, `paid_partnership`, `ai_content` (aus dem früheren Katalog übernommen; hier nicht erneut gelesen, unverifiziert). `deprecated_lid_session` wurde in 2.26.41.6 nicht gefunden.

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

Der Empfänger liest den Flow-Namen (`native_flow_name` oder das verschachtelte `name`) und klassifiziert dann: `buttons` vorhanden, `list` vorhanden oder Native Flow; mit einem Namen und einem `hsm`-Sibling wird es zu einem Template. Validierungsfehler heißen `InvalidTemplateMessage`, `InvalidListMessage`, `InvalidButtonMessage`, `InvalidInconsistentFlowName`, `InvalidFlowNotOwned`, `InvalidDeeplyNested`: Ein `biz`-Klassifikator, der dem verschlüsselten Payload widerspricht, ist ein Validierungsfehler, kein anderer Nachrichtentyp. Weitere `biz`-Attribute, die an anderer Stelle gelesen werden: `campaign_id`, `notification_cta`, `privacy_mode_ts`, `host_storage`, `actual_actors`, `biz_bot`, Child `quality_control` mit `decision_source`.

### 13.2 `<bot>` (found)

Ausgehend (`F6M`): Attribute `type` (`request_welcome`, `prompt`, `command`, `search`, `memu_onboarding`, `memu_invoke`, `voice`, `voice_background`, `text_input`, `live_ai`, `feedback`), `client_thread_id`, `mode_selected`, `persona_type` (`1p`, `ugc`, `3p`), `local_automated_type` (`1p_partial`), `agent_engagement_type`, `is_lid`, Child `tee_routing` (`tee_routing_token`, `tee_ik_id`). Eingehend (`C34747F5q`): `<bot edit="full|...">` Default `full`, `edit_target_id`, `sender_timestamp_ms`, `type`, `client_thread_id`; ohne `<meta target_id>` wird die Nachricht nicht als Bot-Antwort behandelt. Details: [WA_META_AI.md](./WA_META_AI.md).

---

## 14. Verwandte Schemata, die nicht Message-Secret sind

### 14.1 Conditional Reveal (geplante Nachrichten)

`conditionalRevealMessage` (Feld **120**) verwendet einen separaten zufälligen Reveal-Key (`<meta type="scheduled_message" st><key rkid>`); der Server steuert das Reveal. Kein HKDF aus `messageSecret`. Interna des Reveal-Protokolls nicht nachverfolgt (unknown).

### 14.2 Reporting-Token

`reportingTokenVersion` (Feld **8**) und das 16-Byte-`<reporting_token>` verwenden den Key der nativen Use-Case-ID 5 (3.4), nicht Java-HKDF. Token-Inhalt: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 15. Companion-Support-Verifier (found)

`CompanionSupportVerifier` (`C34757F6a`, nur auf einem Companion, hinter einem Flag): Nicht-`peer`-Nachrichten werden nur akzeptiert, wenn der `type` in `{text, media, reaction, poll, event}` liegt (oder `pay` mit einem Remittance-Child `transaction` / `pay`) und jedes direkte Child in `{registration, enc, device-identity, verified_name, url_text, url_number, padding, biz, meta, automated, multicast, rcat, reporting, bot, hsm}` liegt. Andernfalls loggt er `unsupported child node=` / `unsupported message type=`, und die Nachricht wird auf dem Companion als nicht unterstützt klassifiziert. Ein Peer-Broadcast mit `participants` auf einem Companion wird verworfen (`received peer broadcast message on companion-mode, dropping`, Nack 415 / 18). Das neue Child `cap` sowie `tctoken` / `cstoken` stehen nicht in der Liste; wo sie vor dieser Prüfung behandelt werden, ist unaufgelöst. `unavailable` und `participants` laufen über eigene Pfade.

---

## 16. Feature-Flags (IDs wie an den Call Sites gelesen; Namen unaufgelöst)

| ID | Typ | Steuert |
|----|------|----------|
| **6772** | bool | Poll-Vote: gemeinsamer Helper vs. Legacy-Inline-Verschlüsselung |
| **31593** | bool | Setzen von `metadata` beim Poll-Vote |
| **17811** | bool | Use Case `Message Edit` (Senden und Empfangen) |
| **37948**, **35457** | bool | Bedingungen für das Wrappen eigener Nachrichten-Edits |
| **24886** | int | Empfang von Poll-Edits (0 = abgelehnt, 10016) |
| **25758** | int | Empfang von Poll Add Option (0 = abgelehnt, 10017) |
| **15791** | bool | Modifier der Event-Response LID -> PN in 1:1-Chats |
| **3142**-**3146**, **2200**, **11104**, **19303** | bool | Secret-Erzeugung nach Chat-Klasse |
| **8860** | int | maximale Version des Reporting-Tokens (Secret-Erzeugung) |
| **24741** | bool | Secret für Nachrichtentyp 117 |
| **36091** | bool | `meta acp="2"` |
| **11282** | bool | `meta view_once` |
| **16656**, **13537** | bool | `cap`-Child und sein Wert |
| **8311**, **9209** | bool | Padding |
| **20605**, **20606** | bool / int | `tctoken` aktivieren / Obergrenze pro Stanza |

---

## 17. Baileys (`baron-baileys-v2` 1.5.17, Quellcode gelesen, nichts getestet)

Nur Fakten, die in `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js` gelesen wurden.

| Thema | Baileys | Android |
|-------|---------|---------|
| Key | `key0 = HMAC-SHA256(key = 0×32, secret)`; `decKey = HMAC-SHA256(key = key0, id ‖ creator ‖ modifier ‖ useCase ‖ 0x01)` | identisch (3.1) |
| Use Cases | `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option`, dazu `Message Schedule` für Enum 3 | dieselben Strings; der Wert 3 ist in 2.26.41.6 nicht definiert |
| AAD | `id\0modifier` für Poll und Event, leer für Edit / Kommentar / Reaction | gleich |
| Identity | probiert PN- und LID-Kandidaten von Creator und Modifier, GCM authentifiziert das richtige Paar | gleiche Idee (7.2) |
| Fehlendes Secret | loggt, gibt das rohe Update `encReactionMessage` / `pollUpdateMessage` aus, kein Decrypt | als Orphan gespeichert |
| Secret-Erzeugung | `randomBytes(32)` für Poll, Event und wenn `messageContextInfo.messageSecret` fehlt | 2.2 |
| Reporting-Key | `hkdf(secret, 32, { info: id ‖ sender ‖ modifier ‖ 'Report Token' })`; Reporting wird übersprungen für Reactions, `encReactionMessage`, `encEventResponseMessage`, `pollUpdateMessage` | nativ, ID 5 (3.4) |
| Send-Seite | in den gelesenen Dateien wurde kein Sender für `pollUpdateMessage`, `encReactionMessage`, `encEventResponseMessage` oder `encCommentMessage` gefunden | Android sendet alle vier |

Aus dem Code gelesene Konsequenz: Baileys kann empfangene Folge-Einträge entschlüsseln, aber die gelesenen Dateien enthalten keine Verschlüsselung für sie. Ob anderswo ein Send-Helper existiert, wurde nicht gesucht.

---

## 18. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|-------|-----|
| Fehler 11 | IV nicht 12 Byte oder leerer Payload / fehlendes Feld | `encIv` prüfen (Feld 3, bei `PollEncValue` Feld 2) |
| Fehler 51 | falscher Namespace der Sender- / Ziel-JID (PN vs. LID), falsche Original-ID | beide Namespaces probieren, die ID der ursprünglichen (unbearbeiteten) Nachricht verwenden |
| Vote für einen bearbeiteten Poll scheitert | die Key-ID muss die ursprüngliche Poll-ID sein, nicht die ID des letzten Edits | den Original-Key auflösen |
| Kommentar eines PN-Senders scheitert | Kommentar-Decrypt erfordert einen LID-Sender | die LID verwenden |
| Poll-Edit / Add Option abgelehnt | Flags **24886** / **25758** aus, oder Stanza-`polltype` widerspricht `secretEncType` | passendes `<meta polltype>` und passenden Typ senden |
| Nachricht auf einem Companion ignoriert | unbekannter Child Node oder `type` | an die Allowlist halten (Abschnitt 15) |
| `<biz>`-Nachricht nicht unterstützt | Klassifikator widerspricht dem Payload | Klassifikator aus dem Payload ableiten |

---

## 19. Wichtige Abgrenzungen

| Das | Nicht das |
|------|----------|
| `messageSecret` (pro Nachricht, zufällig, 32 Byte) | Media Key, Sender Key, App-State-Sync-Key, Call Key |
| Use-Case-Key (HKDF, pro Ziel / Nutzer / Use Case) | das Secret selbst |
| `secretEncryptedMessage` (wrappt eine vollständige `Message`) | `encReactionMessage` (wrappt eine `ReactionMessage`) |
| AAD bei `Poll Vote` / `Event Response` = ID + NUL + Modifier | Edit / Kommentar / Reaction mit leerer AAD |
| `targetMessageKey` im äußeren Carrier | `ReactionMessage.key` im Plaintext (beim Senden gelöscht) |
| `meta polltype` / `event_type` (Klassifikator) | der verschlüsselte Payload (Inhalt) |
| Stanza-Attribut `edit` | `secretEncType` (Use Case der Verschlüsselung) |
| `decrypt-fail="hide"` an `<enc>` | Retry-Receipt / `retry`-Node |

---

## 20. Vollständiger Ablauf (Poll-Vote, 1:1 oder Gruppe)

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

## 21. Unbekanntes

| Punkt | Stand |
|------|-------|
| Genaue Prädikate für `EZN.A01`, `C35201aS.A00`, Flags 3142-3146 | Gating pro Chat-Klasse gesehen, für Nutzer sichtbare Menge unaufgelöst |
| Native Use-Case-ID-Tabelle (Namen zu anderen IDs als 5 = Report Token) | nicht gelesen |
| Position des GCM-Tags und AES-Key-Größe | aus Konstanten und Baileys inferred |
| Vollständige Bedingung, ob ein eigener `MESSAGE_EDIT` gewrappt oder einfach gesendet wird (Flags 37948, 35457) | Decompiler hat den Kontrollfluss verloren |
| Bedeutung von `acp="2"`, Serialization-Flag `A09`, zweites Stanza-Feld bei Poll Add Option | unaufgelöst |
| Konsument von `decrypt-fail="hide"` am geparsten Envelope | Flag wird in den Envelope übernommen, Wirkung nicht nachverfolgt |
| Für Nutzer sichtbares Ergebnis eines dauerhaft nicht entschlüsselbaren Add-ons | kein Fallback-Text gefunden |
| `unavailable`, `bypassed`, `deprecated_lid_session` | in 2.26.41.6 nicht erneut verifiziert |
