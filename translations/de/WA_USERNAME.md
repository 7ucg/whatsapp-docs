<!-- src-sha1: 73855f4f8148d9b0ef853f43cef4adbe0cb996a5 -->
# WhatsApp Benutzername — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-17
**Umfang:** Username check / set / reserve / delete, Username-Key (PIN), LID-Beziehung, Privacy und Visibility, w:mex GraphQL-Operationen (doc_ids, Variablen, Responses), Notifications, USync-Lookup, Validierungsregeln, Feature-Flags, Baileys-Hinweise

---

## 1. Was ein Username technisch ist

Ein Username ist ein serverseitiger Handle, der an einen Account gebunden ist, damit ein Kontakt erreicht werden kann, ohne die Telefonnummer offenzulegen. Alle Aussagen sind statische Analyse der dekompilierten APK. Tier: **found** = im Code oder in Assets gelesen, **inferred** = aus Code abgeleitet, **unknown** = nicht aufgelöst.

Das Feature baut auf drei Schichten auf:

| Schicht | Transport | Verwendet für |
|-------|-----------|----------|
| Self management | `w:mex` IQ, persistiertes GraphQL (config `whatsapp-android-mex`) | check, set / reserve / delete, get, key (PIN) set / delete, multi-check |
| Lookup anderer | USync (`xmlns="usync"`) und die MEX-`UsyncQuery`-Variante | `@username` (+ key) zu einer LID auflösen, Username eines bekannten JID abfragen |
| Push | MEX-Notifications | `UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification` |
| Cross-device | app-state sync (`SyncActionValue`) | `username_chat_start_mode`, `lid_contact_action` (trägt `username`) |

| Entity | Name in 2.26.41.6 | Rolle |
|--------|----------------|------|
| Username-Manager | `C122815Lj` | `UsernameGet`-, `UsernameSet`-Calls, Update des lokalen State, Rate-Limit-Hook |
| Verfügbarkeits-Check | `C67402tT` | `UsernameCheck`-Call + Response-Mapping |
| Multi-Check | `C76333Kg` | `UsernameCheckMulti`, Chunks von 10 |
| Key-API | `MexUsernamePinProtocolApi` | `UsernamePinSet` (set / delete key) |
| Lokaler State / Prefs | `C5Q8` | `username_reservation_state`, `username_pin`, `is_username_revoked` |
| State-Enum | `C4DU` | `UNSET`, `RESERVED`, `ACTIVATED`, `CREATED` |
| Eligibility-Mode | `C224069kP.A00()` -> `C9SR` | `CREATION`, `RESERVATION`, `COMPANION_READ_ONLY`, `DISABLED` |
| Rate-Limit-Store | `C67942uO` | Backoff nach 429 / 503 / 529 |
| Lokaler Validator | `C82003fB.A04`, `C1187754z` | Länge, Zeichensatz, Punkt-Regeln, Regex |
| Key-Validator | `C1176550d` (+ `AbstractC111284pZ`) | Key-Format |
| Key-Entry-VM | `UsernamePinEntryViewModel` | Key für einen fremden Username einreichen |
| USync-Client | `C23638AId` (`querySyncUsernameWithErrorInfo`), `C18670m9` | klassischer usync-Stanza-Builder / -Parser |
| MEX-USync | `C229259vZ`, `O0F` | `UsyncQuery` mit `include_username` |
| Notification-Handler | `C49822Lvi`, `C49821Lvh`, anonym `X.2YG` in `AbstractC20380p4` | set / delete / update |

Naming: der benutzerseitige Name der PIN ist **Username-Key** (Strings "Username key", "Add a username key to control who can contact you"). Auf der Wire- und Code-Ebene heißt es `pin`.

---

## 2. MEX-Operationen (doc_ids)

### 2.1 Wo die doc_ids liegen

doc_ids sind keine Literale in `java_src`. Der Client sendet den Operationsnamen (`"UsernameSet"`, ...) mit dem Config-Namen `"whatsapp-android-mex"` (found, `C16880is`). Die numerische id wird aus `assets/whatsapp-android-mex_client_persist_ids.json` gelesen: `EnumC17010j7.WHATSAPP_ANDROID_MEX` mappt auf diese Datei, `C17040jA.CMg(op)` liefert das Feld `doc_id`, `AGb(op)` das Feld `client_doc_id` (found). Welcher der beiden Accessoren das Attribut `query_id` befüllt, wurde nicht bis zum Ende nachverfolgt (unknown); frühere Captures auf 2.26.26.4 zeigen `query_id` gleich `doc_id`.

Die unten stehenden doc_ids sind im Asset von 2.26.41.6 **found**:

| Operation | doc_id | Typ | Call-Site | Response-Klasse |
|-----------|--------|------|-----------|----------------|
| `UsernameCheck` | `26124072630599518` | query | `C67402tT.A00` | `C2IG` |
| `UsernameCheckMulti` | `27134626522840286` | query | `C76333Kg.A00` | `C2IE` |
| `UsernameGet` | `32618050064506055` | query | `C122815Lj.A02` | `C87173nz` |
| `UsernameSet` | `27108705368767936` | mutation | `C122815Lj.A00` | `C87183o0` |
| `UsernamePinSet` | `25529696019976770` | mutation | `MexUsernamePinProtocolApi.A00` | `C48557LJz` |
| `UsernameGetRecommendationsQuery` | `26077456248616957` | query | keine gefunden | unknown |
| `UsyncQuery` | `38635300486116501` | query | `C229259vZ.A01` | `C2IQ` |

Hinweise:
- `UsernameGetRecommendationsQuery`: der Name kommt nur im Asset-JSON vor. Keine Klasse in `java_src` referenziert ihn per String (found). Variablen und Response sind unknown.
- Die drei Notification-Namen (`UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification`) haben keinen Eintrag im Persist-id-Asset. Es sind Notification-Typen, keine Requests (siehe 7).
- Das Asset hat `operation_name_hash`, `operation_text_hash` und `client_doc_id` je Op. Beispiel `UsernameSet`: `client_doc_id` `427995565715419341100134328918` (found).

### 2.2 Envelope

Gebaut in `C19370nI` / `C19310nC` (found):

```xml
<iq to="[server jid]" xmlns="w:mex" type="get" id="...">
  <query query_id="DOC_ID">{"queryId":"DOC_ID","variables":{...}}</query>
</iq>
```

| Feld | Regel (Code) |
|-------|-------------|
| `xmlns` | `w:mex` |
| `type` | `get` für jede Operation, auch Mutations |
| Attribut `query_id` | nur gesetzt, wenn 1 bis 20 Zeichen |
| Body | JSON `{"queryId": ..., "variables": {...}}`, 1 bis 8448000 Bytes |
| null-Variablen | `C16770ig.A03(k, null)` und `A02(k, null)` lassen den Key aus, ein fehlender Wert heißt also, der Key wird nicht gesendet |

Wire-Stanzas aus laufenden Sessions werden hier nicht wiedergegeben; dieser Build wurde nur statisch analysiert.

---

## 3. Operationen im Detail

### 3.1 UsernameCheck

Variablen (found, `C67402tT.A00`):

| Variable | Typ | Bedingung |
|----------|------|-----------|
| `username` | string | immer |
| `include_suggestions` | bool | immer (die UI übergibt `false` im typed-check-Pfad `C64H` Case 21) |
| `source` | string | nur wenn nicht-null |
| `session_id` | string | nur wenn nicht-null |

`source`-Mapping (`AbstractC78993Wd.A0U`): int 1 -> `FB`, 2 -> `IG`, 3 -> `USER_INPUT`, 4 -> `SUGGESTION`, sonst -> null (nicht gesendet).

Response-Pfad (found, `C77183Np` Default-Branch): `data.xwa2_username_check`

| Feld | Typ | Verwendung |
|-------|-----------|---------|
| `result` | Enum `EnumC59782gh` | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `INVALID`, `SUCCESS` |
| `suggestions` | list<string> | nur gelesen bei `INVALID` |
| `rejection_reasons` | Liste von `C4G8` | nur gelesen bei `INVALID` |
| `suggestions_eligible` | bool | defaultet auf `true`, wenn das Feld null ist |

`C4G8`-Werte (found): `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALREADY_TAKEN`, `REQUIRE_FB_ACCOUNT_LINKING`, `REQUIRE_FB_CONSUMER_ACCOUNT_LINKING`, `REQUIRE_IG_ACCOUNT_LINKING`, `REQUIRE_IG_CONSUMER_ACCOUNT_LINKING`.

Mapping: `SUCCESS` -> `C76283Kb` (verfügbar); `INVALID` -> `C76303Kd` (nicht verfügbar, trägt Vorschläge + Gründe); `UNSET` -> kein Branch setzt ein Result (Callback erhält die vorherige/null-Variable; Verhalten unknown). Aktiver lokaler Backoff -> `C76293Kc` (Fehler mit Rate-Limit-Code aus Prefs, siehe 5.3); der Failure-Callback des Requests selbst wurde nicht gelesen.

Rejection reasons treiben den Account-Linking-Text ("This username matches an account on Facebook/Instagram. To use it ... add your accounts to Accounts Center", `C82003fB`). In `C82003fB` löst jeder Grund außer `UNSET` den lokalen Error-Pfad mit Code 40601 aus (`A08(40601L)`); eine leere oder nur-`UNSET`-Liste zeigt "Username isn't allowed." Der genaue Kontrollfluss um die Schleife ist nur teilweise dekompiliert (inferred).

### 3.2 UsernameCheckMulti

| Variable | Typ | Hinweise |
|----------|------|-------|
| `usernames` | **list<string>** | Array über `A00.A0B("usernames", list)`; der doc_id-Katalog typisiert als `str`, der Code sendet eine Liste |

Batching (`C76333Kg.AG5`): die Liste wird in die ersten 10 und den Rest gesplittet; der Rest wird nach einer Verzögerung von Flag **29327** verarbeitet (Default 60, Einheit nicht aufgelöst). Eine leere Liste liefert eine leere Map ohne Request.

Response-Pfad `data.xwa2_username_check_multi.results[]` (found): jedes Item hat `username` und `response.result` (gleiches `EnumC59782gh`). Mapping: `SUCCESS` -> verfügbar, `INVALID` -> nicht verfügbar (keine Vorschläge, `suggestions_eligible=false`), alles andere -> Fehler. Namen, die im Result fehlen, werden als Fehler markiert.

Consumer: `UsernameAvailabilityCache` speichert `EnumC59192fk` (`UNKNOWN`, `AVAILABLE`, `UNAVAILABLE`) je Name. Zweck (Prefetch für Facebook-/Instagram-Username-Vorschläge, String `foa_username_prefetch_cache`) ist inferred.

### 3.3 UsernameSet (anlegen / ändern / reservieren / löschen)

Variablen (found, `C122815Lj.A00`):

| Variable | Typ | Bedingung |
|----------|------|-----------|
| `username` | string | ausgelassen, wenn null (**Löschen**) |
| `reserved` | bool | immer gesendet |
| `session_id` | string | nur wenn nicht leer (`C1YW.A08`) |
| `source` | string | nur wenn der source-int nicht null ist (siehe 3.1) |
| `pin` | string | nur wenn nicht null |

`reserved` wird berechnet, nicht konstant (found). Argument `z` (force) = true liefert `false`. Sonst: aktueller State `ACTIVATED` oder `CREATED` liefert `false`; State `RESERVED` oder Eligibility-Mode `RESERVATION` liefert `true`; alle anderen Fälle liefern `false`. `reserved:true` wird also nur für Accounts im Reservation-Mode oder solche mit bestehender Reservierung gesendet.

Löschen ist ein Modus derselben Operation: `username == null` -> Log-Tag `delete`, sonst `set` (ebenso in `MexUsernamePinProtocolApi` für den Key). Bei null-Username ist der Key `username` nicht in den Variablen enthalten (found).

Client-seitiger Guard: vor dem Senden, falls der Rate-Limit-Store einen aktiven Backoff meldet, schlägt der Call lokal fehl mit `username_creation_rate_limit_error_code` und dem Text "rate limit expiration time not reached" (found, `C122815Lj.A03`).

Success-Handling (`C122815Lj.A01`, found):

| Bedingung | Lokal geschriebener State (`username_reservation_state`) |
|-----------|----------------------------------------------------|
| username null oder leer | `UNSET`, Key-Pref wird gelöscht |
| `reserved` war true | `RESERVED` |
| Activate-Flag | `ACTIVATED` |
| sonst | `ACTIVATED`, wenn State `ACTIVATED` war und der Name dem gespeicherten entspricht, sonst `CREATED` |
| `source`-int ist 1 oder 2 | Pref `username_set_via_account_linking` = (int == 2) |
| `pin` gesendet | Pref `username_pin` aktualisiert |
| Teen-Flag | Pref `is_teen_account` = true |

Pref-Write ist `Voip.REJECT_REASON_DECLINED`, was in diesem Build der leere String `""` ist (found).

Error-Handling (`C138725uA` Case 2):

| HTTP-ähnlicher Code | Client-Aktion |
|----------------|---------------|
| 429, 503, 529 | Backoff gespeichert (5.3) |
| 304 | als Erfolg behandelt ("not modified"), lokaler State wird trotzdem aktualisiert |
| keine Verbindung (`C213639Bb`) | `C4BO` "no network"-Result |
| sonst | `C4BN(code, message)` |

### 3.4 UsernameGet

Variablen: keine (der Call baut ein leeres Variablen-Set, found, `C122815Lj.A02`). Markiert `@Deprecated`, ersetzt durch eine Suspend-Variante.

Response (found, `C138815uJ` Case 34): `data.xwa2_username_get.username_info`

| Feld | Verwendung |
|-------|-----|
| `username` | gespeichert; leerer String, wenn nicht vorhanden |
| `state` | `C4FC`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `RESERVED` |
| `pin` | **der Key wird im Klartext zurückgegeben und im Pref `username_pin` gespeichert**; leerer String, wenn nicht vorhanden |

State-Mapping: `RESERVED` -> `C4DU.RESERVED`; `ACTIVE` -> `ACTIVATED`, wenn der gespeicherte Username dem zurückgegebenen entspricht und der lokale State `RESERVED` oder `ACTIVATED` war, sonst `CREATED`; null-State oder null-`username_info` -> `UNSET`.

Error-Fall 404 vom Server löscht den lokalen Username, Key und State (Log `clearSelfUsernameData NOT_FOUND`).

Ob der Call als Heartbeat verwendet wird, ist unknown; die alte Notiz "polling heartbeat" wird vom Code dieses Builds nicht gestützt.

### 3.5 UsernamePinSet (Username-Key)

Variablen (found): `pin` (string), ausgelassen, wenn null.

| Aktion | Variablen |
|--------|-----------|
| Key setzen | `{"pin": "<key>"}` |
| Key löschen | `{}` (`A02` ruft `A00(null)` auf) |

Der Operationsname ist für beide `UsernamePinSet`; es gibt keine separate Verify-Operation. Die Verifikation eines fremden Keys erfolgt über USync (4). Nicht verbunden: liefert `C213639Bb("UsernamePinSet")` ohne Request.

Der Key kann auch im `UsernameSet` mitreisen (`pin`-Variable). `C81793ej.A0x` nutzt `UsernameSet` mit dem bestehenden Username und dem neuen `pin`, wenn lokal bereits ein Username gespeichert ist (`A00 != null`), sonst `UsernamePinSet` (found).

Die Response-Klasse `C48557LJz` hat in den gelesenen Dateien keinen Field-Access. Die Response-Form ist unknown.

---

## 4. Lookup anderer Nutzer

### 4.1 Klassisches USync per Username (Key-Flow)

Gebaut in `C18670m9.A06` (jadx scheiterte an dieser Methode, aus Smali `X/0m9.smali` gelesen). Pro `C222649hm`-Request-Eintrag: Feld `A0C` = Username, `A0D` = Key, `A05` = LID.

Attribute des Contact-Childs (found in Smali): `username` immer; `lid`, wenn eine LID lokal bekannt ist; `pin`, wenn ein Key gesetzt ist. Die zusätzlichen Attribute sind durch Flag **12402** gegattert (Default `false`): wenn das Flag aus ist, wird nur `username` geschrieben (found). Der Node-Name `contact` ist aus dem Response-Parser inferiert, der ein Child `contact` und dessen Attribut `username` liest (`C18670m9` Zeilen ~969-975).

```xml
<iq xmlns="usync" to="[server]" type="get">
  <usync mode="query" context="interactive" sid="..." index="0" last="true">
    <list>
      <user><contact username="name" lid="LID" pin="KEY"/></user>
    </list>
    <query><contact/> ... </query>
  </usync>
</iq>
```

Entry-Point: `C23638AId.A0G(username, key)` (`querySyncUsernameWithErrorInfo`), aufgerufen von `submitPinForUsername`. Sync-Typ `EnumC21760rz.A0J`, Timeout 32000 ms. Das Attribut-Set `contact`, `pin`, `username` ist in den Log-Redaction-Sets von `AbstractC40921lc` (found).

Lokales Pre-Resolve: `A0M.Aol(username)` sucht `lid_row_id` in der Tabelle `lid_display_name` wo `UPPER(username) = UPPER(?)`, neueste Zeile zuerst (found, `C1S0`). Die LID, falls bekannt, geht ins Attribut `lid`.

### 4.2 Auswertung des Ergebnisses (Key-Eingabe)

`UsernamePinEntryViewModel$submitPinForUsername$1` (found):

| Ergebnis | Bedingung |
|---------|-----------|
| korrekter Key | Resultat `UserJid` ist eine LID (`C14080dr`) |
| falscher Key | Resultat hat keine LID: Log "[un-pin] incorrect PIN", Fehlertext "Wrong key entered" |
| kein Netzwerk | `C9qA` Code 1 |
| allgemeiner Infra-Fehler | `C9qA` Code 2 |
| Rate-Limit beim Anfragenden | `C225769os.A01` true: "Too many attempts made. Try later." |
| Rate-Limit beim Angefragten | `C225769os.A00` true: "This account can't be reached with their key right now..." |

Die client-seitig gecachte Rate-Limit-Prüfung läuft zuerst, wenn Flag **16033** an ist und JSON-Config **21995** `enable_key_rate_limit` true hat (Default true): `C30P.A00` gegen die eigene LID und gegen den Ziel-Username. Der Username wird von `@` gestript (`C0CX.A0i(username, '@')`).

Bei Erfolg ist das Ergebnis eine **LID**, der Chat wird dann an die LID adressiert (inferiert aus dem `C14080dr`-Check; der Chat-öffnen-Schritt wurde nicht nachverfolgt).

### 4.3 Username einer bekannten LID abrufen

`C23638AId` (Zeile ~600-650) baut ein usync mit `<list><user jid="LID"/></list><query><contact/><username/></query>`, mode/context aus `EnumC21760rz.A0J` (found). Der Parser liest `username` als Child des `<usync>`-Results (`C18670m9` Zeile 586, nur wenn der Request es angefordert hat).

### 4.4 MEX-USync (`UsyncQuery`)

`C229259vZ.A01` baut `UsyncQuery` (doc_id oben). Relevante Teile (found):

| Variable | Verwendung |
|----------|-----|
| `query_input[]` | ein Eintrag je Nutzer: JID (`C493020r.A0C`), optional `client_known_username` (nur wenn Username angefordert und nicht leer) |
| `include_username` | bool, gesetzt, wenn irgendein Eintrag den Username anfordert |
| `include_lid` | bool, fordert `lid_info` an |
| `telemetry.context` | lowercased USync-Context |

Response pro Nutzer: `jid`, `username_info`, `lid_info` (`O0F`). `username_info` ist polymorph nach Type-Hash: ein Value-Typ mit `username`, oder ein Status-Typ mit `status` von `EnumC216389Tz`: `EMPTY`, `NOT_ALLOWED`, `NO_CHANGE` (+ unset). `NOT_ALLOWED` wird geloggt als "username not allowed to be queried" und löscht den gespeicherten Username; `NO_CHANGE` behält ihn. `lid_info.lid_jid` trägt die LID.

Gate: `ContactSyncHelper` verweigert den MEX-Pfad mit dem Log "cantUseMex as username ab prop is off", außer Flag **8421** ist an, wenn ein Username angefordert wird (found; Default `false`).

---

## 5. Validierung, Limits, Fehler

### 5.1 Username-Format (lokal)

Validator `C82003fB.A04` (found), prüft in dieser Reihenfolge:

| Reihenfolge | Check | Error-id (`C02U`) | Nachrichtentext |
|-------|-------|-------------------|----------------|
| 1 | jedes Zeichen in `[A-Za-z0-9_.]` | 2 | "must start with a letter and can only contain letters, digits, periods and underscores" |
| 2 | Länge >= min (Flag **20494**, Default 3) | 0 | "Use between %1$d-%2$d characters" |
| 3 | Länge <= max (Flag **20459**, Default 35) | 1 | gleicher Text |
| 4 | kein führender `.`, kein abschließender `.`, kein `..` | 3 | "can't start or end with a period or have 2 periods in a row" |
| 5 | mindestens ein ASCII-Buchstabe | 4 | "Choose a username with at least one letter" |
| 6 | Regex (unten) | passt oder scheitert mit 2 | n/a |

Regex gebaut von `C1187754z.A02()` (found):

```
^(?!.*\.\.)(?=.*[a-zA-Z])[a-zA-Z0-9_][a-zA-Z0-9_.]{MIN-1,MAX-1}(?<![.])$
```

Groß-/Kleinschreibung wird vom Validator nicht normalisiert; der lokale Lookup `Aol` vergleicht mit `UPPER()`, das lokale Matching ist also case-insensitiv (found). Ob der Server Namen case-insensitiv behandelt, ist unknown. Ein führender Unterstrich ist laut Regex erlaubt; der UI-Text sagt "start with a letter", was strenger ist als die Regex (found, Mismatch).

Die UI lehnt außerdem Web-Links ab: "Enter only your username, not a web link" (String vorhanden, Check nicht nachverfolgt).

### 5.2 Format des Username-Keys

`C1176550d.A00` (found): Flag **34350** ist ein Regex-String, Default `^([0-9]{4}|[A-Z0-9]{6})$`. Ist der Flag-String leer, ist der Fallback genau vier Ziffern. Ungültige Regex loggt `[un-pin] invalid username_key_regex` und akzeptiert alles. Die Längengrenzen-Flags **34347** (min, 4) und **34348** (max, 6) fließen nur in den Error-Message-Pfad in `UsernamePinEntryViewModel.A0w`. Server-seitige Regeln sind unknown.

Die alte Notiz "4-digit PIN" ist also unvollständig: der ausgelieferte Default akzeptiert vier Ziffern oder sechs großgeschriebene alphanumerische Zeichen.

### 5.3 Rate Limits und Backoff

`C67942uO` (found), aktiv nur mit Flag **28678** (Default `false`):

| Item | Wert |
|------|-------|
| Trigger | `UsernameSet`-Error 429, 503 oder 529 |
| Dauer | `Retry-After`-ähnlicher String als int-Sekunden geparst (`C23680AJt.A00`), sonst Flag **28127** (Default 30) Sekunden |
| Speicherung | Prefs `username_creation_rate_limit_backoff_expiry` (ms), `username_creation_rate_limit_error_code` |
| Effekt | `UsernameCheck`, `UsernameCheckMulti`, `UsernameSet` schlagen lokal fehl bis zum Ablauf |

### 5.4 Error-Code zu Nachricht (`C82003fB.A02`, found)

| Code | Nachricht |
|------|---------|
| 400 | "Couldn't save your username. Try again." |
| 403, 404, 429 | "Couldn't complete your request. Try again." |
| 500, 529 | "We couldn't complete your request. Try again later." |
| 503 | "... Please try again later." |
| 406, 40601 | "This username is not available." |
| 40602 | "You can't make more changes to your username. Try again later." |
| 40603 | "You can't make changes to your username right now. Try again later." |
| sonst | "We couldn't complete your request. Try again." |

40601 bis 40603 sind im erlaubten Set `AbstractC111104pH.A01` (nur 40603 im gelesenen Code sichtbar). Ihre Server-Semantik ist über den Client-Text hinaus unknown.

---

## 6. LID-Beziehung

Alles found, sofern nicht anders markiert.

| Fakt | Beleg |
|------|------|
| Username-Lookups lösen zu einer **LID** auf, nicht zu einem Phone-JID | Key-Success-Test `userJid instanceof C14080dr` (LID-Klasse); `lid_info.lid_jid` im MEX-usync |
| Lokale Map Username -> LID | Tabelle `lid_display_name` (Spalten `username`, `lid_row_id`), Query in `C1S0` |
| Notifications identifizieren den Nutzer per LID | Set-/Delete-Handler parsen `LidUserJid` (Fehlertext "Failed to parse LidUserJid") |
| Delete-Notification kann einen Phone-JID tragen | Handler prüft `isPnPresent`; mit PN wird ein PN-JID gecastet und gehandelt, ohne PN wird returned |
| Contact-Sync-Action | `ContactAction` hat `username` (6) neben `lid_jid` (3), `pn_jid` (5); außerdem `LidContactAction` (`lid_contact`, SyncActionValue-Feld 61) |
| Chat-Start-Mode | SyncActionValue-Feld **59** `username_chat_start_mode`, Enum `EnumC50053M6w`: `LID` = 1, `PN` = 2. Nur der Sync-Codec wurde gefunden; kein Consumer im UI-Code (unknown) |
| Companion-Feature-String | beim Linken eines Companions fügt der Primary `username_supported` (Flag 4745 oder 20189), `username_reservation_only_mode` (nur 20189), `username_account_linking_enabled` (Flag 21199) seiner Feature-Liste hinzu (`C25056AqU`) |

Inferred: ein Nutzer, der nur als Username existiert, ist nur über die LID erreichbar, bis der Owner die Telefonnummer teilt; die Strings "If you continue, your phone number will show in existing username chats and calls" (Delete-Dialog) stützen das, aber der PN-Exposure-Pfad wurde nicht nachverfolgt.

---

## 7. Notifications

Handler erweitern `AbstractC23194A0r` und sind in `AbstractC20380p4` registriert (found):

| Notification | Handler | Verhalten |
|--------------|---------|-----------|
| `UsernameSetNotification` | `C49822Lvi` | Payload `xwa2_notify_username_on_change`: liest LID (Feld-Hash 107143) und Username; speichert über `InterfaceC11470Yz.BNU(lid, username)`; existiert der Kontakt und ist von passender Art, wird der Kontakt refreshed (`C12440bB.A0W`) |
| `UsernameDeleteNotification` | `C49821Lvh` | Payload `xwa2_notify_username_delete`: liest LID und PN (Hash -983979708); mit PN wird das Delete-Update ausgeführt (`C53594Nzh`) |
| `UsernameUpdateNotification` | anonym `X.2YG` | liest einen Base64-Hash aus dem Payload, baut einen USync-Request mit Grund `USERNAME_UPDATE_NOTIFICATION` und `EnumC21760rz.A0Q` (Context `NOTIFICATION_SIDELIST`, Mode `query`; siehe WA_USYNC.md), Log "usync triggered for hash" |

Dem Nutzer gezeigter Text: "Your username has changed", "WhatsApp has assigned you a new username (%1$s)", d.h. der Server kann einen Username neu zuweisen (Revocation, Pref `is_username_revoked`, `revocation_banner_dismissed_<username>`).

---

## 8. Feature-Flags

Flag-IDs sind AB-prop-ids, gelesen über `C08J` (Defaults aus `C08J`-Tabellen). Alle Defaults unten wurden aus diesem Build gelesen.

| Flag | Typ | Default | Steuert |
|------|------|---------|----------|
| **4745** | bool | false | Primary: Username-Erstellung (Mode `CREATION`); außerdem als `username_supported` beworben |
| **20189** | bool | false | Primary: Reservation-only-Mode (`RESERVATION`); `username_supported` |
| **23817** | bool | false | Companion: Username-Features überhaupt (sonst `DISABLED`) |
| **21199** | bool | false | Account-Linking (FB / IG) aktiviert, beworben als `username_account_linking_enabled` |
| **16033** | bool | false | Master-Gate für Key-Features (`C79343Xx.A00`): Key-Rate-Limit, Key-Upsell, WABI-Username-View |
| **21995** | JSON | `{}` | `enable_key_rate_limit`, `enable_key_upsell_flows`, `enable_wabi_username_view` (alle Default true, wenn der JSON-Key fehlt) |
| **8421** | bool | false | erlaubt MEX-`UsyncQuery` für Username-Requests |
| **12402** | bool | false | fügt die Attribute `lid` und `pin` zum usync-Node `contact` hinzu |
| **20494** / **20459** | int | 3 / 35 | min / max Username-Länge |
| **34350** | string | `^([0-9]{4}\|[A-Z0-9]{6})$` | Key-Regex |
| **34347** / **34348** | int | 4 / 6 | Key-Längengrenzen (Fehlermeldung) |
| **28678** | bool | false | aktiviert den Rate-Limit-Backoff-Store |
| **28127** | int | 30 | Default-Backoff-Sekunden |
| **29327** | int | 60 | Verzögerung vor dem zweiten Batch von `UsernameCheckMulti` |

Companion-Eligibility (`C224069kP.A00`, auf Bytecode-Ebene gelesen):

```
companion (identity of the A02 check inferred from the "open WhatsApp on your primary device" strings):
  23817 off, or pref username_reservation_creation_supported_on_primary false  -> DISABLED
  pref username_account_linking_enabled_on_primary true                         -> COMPANION_READ_ONLY
  state RESERVED                                                                -> COMPANION_READ_ONLY
  state not UNSET                                                               -> CREATION
  state UNSET and pref username_reservation_only_mode_on_primary true           -> COMPANION_READ_ONLY
  state UNSET otherwise                                                         -> CREATION
primary:
  4745 on -> CREATION;  else 20189 on -> RESERVATION;  else DISABLED
```

Die drei `*_on_primary`-Prefs werden nur hier gelesen; wo sie geschrieben werden, wurde nicht gefunden (unknown).

---

## 9. Privacy und Visibility

| Aspekt | Befund | Tier |
|--------|---------|------|
| Zweck | "Keep your phone number private with a username"; Personen, die die Nummer nicht gespeichert haben, sehen stattdessen den Username | found (Strings) |
| Erster Kontakt | bei gesetztem Key müssen Personen, "mit denen man noch nicht interagiert hat", den Key eingeben, bevor sie den Username kontaktieren können | found (Strings) |
| Key-Sharing | Username-Share-Action kann den Key enthalten (Pref `username_share_include_pin`, migriert weg in `C138535tr`); Strings "Share your username and key" | found |
| Wo die Nummer versteckt wird | Community-Admins und Channel-Admins sehen die Nummer, außer ein Username ist gesetzt; Channel-Follower sehen keines von beiden | found (Strings) |
| Group-/Thread-Telemetrie | Felder `has_username`, `has_username_pin`, `is_username_thread` in der Message-Send-Telemetrie (`DZ1`, `RQG`) | found |
| Key at rest | der eigene Key wird von `UsernameGet` zurückgegeben und im Klartext-Pref `username_pin` gespeichert | found |
| Chats mit Dritten | "Usernames and contacts added to third-party chats will not save to your phone" | found (String) |
| Business | "This username is only available on WhatsApp Business" erscheint als Rejection-Text | found (String) |
| Wer abfragen darf | der MEX-usync-Status `NOT_ALLOWED` zeigt, dass der Server die Username-Offenlegung je Anfragendem verweigern kann | found (Enum), Regel unknown |
| Minderjährige | Pref `is_teen_account`; Eltern-Texte "Your child created the username ..." | found |

Serverseitig durchgesetzte Visibility-Regeln (wer einen Username auflösen darf, Key-Rate-Limits, Neuzuweisung) sind vom Client aus unknown.

### 9a. Audience-Steuerung für das Teilen der Telefonnummer (neu in 2.26.45.10, found)

Ein separates Package `com.whatsapp.pnsharing` steuert, wer die Telefonnummer des Accounts sehen kann, unabhängig von den eigenen Visibility-Regeln des Usernames in 9. Zwei neue `whatsapp-android-mex`-Operationen, beide **found** aus reinen `const-string`-Literalen in Smali (kein Decompile nötig, `PnSharingAudienceUpdater.smali` / `PnSharingListFetcher.smali` / `PnSharingListUpdater.smali`):

| Operation | doc_id | Typ |
|-----------|--------|------|
| `UsernamePhoneNumberPrivacyUpdateMutation` | `28835748819379698` | mutation |
| `UsernamePhoneNumberPrivacyGetQuery` | `29264643203229836` | query |

Die Audience-Einstellung ist einer von 4 Werten des geteilten, nicht pnsharing-spezifischen Enums `LX/BWW` (13 Member insgesamt, nur diese 4 sind über diesen Call-Pfad erreichbar):

| Ordinal | `LX/BWW`-Member | `setting`-Wert |
|---|---|---|
| 0 | `A02` | `ALL` |
| 1 | `A07` | `MYCONTACTS` |
| 2 | `A08` | `MYCONTACTSEXCEPT` |
| 3 | `A09` | `NONE` |

**`UsernamePhoneNumberPrivacyUpdateMutation` ist inkrementell, kein Full-Replace.** Zwei Call-Sites füttern sie:

- `PnSharingAudienceUpdater.A00` — nur Änderung der Top-Level-Einstellung, keine Listen-Einträge.
- `PnSharingListUpdater.A01` — Add/Remove je Eintrag gegen eine der drei Audience-Listen.

Top-Level-Felder (found):

| Feld | Typ | Bedeutung |
|-------|-----|-------------|
| `setting` | string | `ALL` / `MYCONTACTS` / `MYCONTACTSEXCEPT` / `NONE`, siehe Tabelle oben |
| `input` | object | verschachtelter Payload, siehe unten |

`input`-Felder (found, verschachtelt unter `allow_list` / `contact_exclude_list` / `deny_list`, je nachdem welche der 3 Non-`MYCONTACTS`-Settings aktiv ist — `MYCONTACTS` sendet keinen Listen-Key):

| Feld | Typ | Bedeutung |
|-------|-----|-------------|
| `dhash` | string | Content-Hash der Audience-Liste, verwendet für Cache-Invalidierung / Conflict-Detection (Log-String "...changed since it was read" direkt daneben) |
| `entries` | Liste von Objekten | inkrementelle ADD/DEL-Einträge, keine vollständige Listen-Ersetzung |

`entries[]`-Item-Felder (found, gebaut von `PnSharingListUpdater.A00(Integer, Integer)`):

| Feld | Typ | Bedeutung |
|-------|-----|-------------|
| `entry_type` | string | `USER` oder `GROUP` |
| `operation` | string | `ADD` oder `DEL` |
| `group_jid` | string, nullable | nur gesetzt, wenn `entry_type=GROUP` |
| `pn_jid` | string, nullable | gesetzt, wenn der Eintrag eine blanke Telefonnummer ist (`PhoneUserJid`) |
| `user_jid` | string, nullable | gesetzt, wenn der Eintrag ein aufgelöster Kontakt-`Jid` ist |
| `username` | string, nullable | Feld existiert im Schema, aber keine beobachtete Call-Site befüllt es; `inferred` Zweck: Paarung einer noch-nicht-Kontakt-Telefonnummer mit einem Anzeigenamen, konsistent mit `UsernameSet`-artigen Ausnahmen — `unknown`, ob irgendein Caller es tatsächlich setzt |

Pro Eintrag ist genau eines von `group_jid` / `pn_jid` / `user_jid` befüllt (found); die anderen beiden bleiben null.

`UsernamePhoneNumberPrivacyGetQuery` ist das Gegenstück auf der Lese-Seite (found, `PnSharingListFetcher.smali`): ein einzelner gebatchter Roundtrip, der alle 3 Audience-Listen gleichzeitig abruft, jede mit eigenem `dhash` (lokal gecachter Hash, oder der Literal-String `"none"`, falls nicht vorhanden) zur Cache-Validierung.

**Ungelöste doc_id:** der persistierte Query-Katalog listet außerdem `PnSharingPhoneNumberFetch` (doc_id `29229648029980096`, Typ query). Das Grepping des vollständig dekodierten 2.26.45.10-Smali-Baums (alle Shards, nicht nur `com/whatsapp/pnsharing/`) nach diesem Literal findet keine Call-Site — nur das ausgelieferte Asset `whatsapp-android-mex_client_persist_ids.json` referenziert es. Was sie aufruft und was sie sendet, ist **unknown**. Wahrscheinlicher Kandidat nur nach Namen (**inferred**, nicht mehr): ein Fetch der Telefonnummer-Visibility pro Kontakt/pro Gruppe, also das Einzel-Item-Gegenstück zur gebatchten 3-Listen-Query oben — nicht bestätigt.

---

## 10. Baileys-Hinweise

Der Envelope in 2.2 ist generisch; ein Baileys-Client kann ihn bauen. Das ist **inferred**, hier nicht getestet.

```ts
const variables = { username: 'name', include_suggestions: false, source: 'USER_INPUT', session_id: uuid }
await sock.query({
  tag: 'iq',
  attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '26124072630599518' },
    content: Buffer.from(JSON.stringify({ queryId: '26124072630599518', variables })) }]
})
```

| Risiko | Grund |
|------|--------|
| doc_id-Drift | ids gehören zum Asset dieses Builds; andere Builds können abweichen (unknown) |
| `session_id` | der Code sendet sie, wenn vorhanden; ob der Server den gleichen Wert für check und set verlangt, ist unknown |
| Key-Attribute | `lid` / `pin` auf `contact` sind hinter Flag 12402; der Server ignoriert sie bei Clients ohne das Flag möglicherweise (unknown) |
| lokale Regeln | Länge, Zeichensatz und Punkt-Regeln sind client-seitig; die Server-Regeln sind unknown |

---

## 11. Abgrenzungen

| Nicht verwechseln | Unterschied |
|----------------|------------|
| Username-Key vs. Account-PIN / 2FA | Der Username-Key (`pin` in `UsernamePinSet`, Pref `username_pin`) sperrt den ersten Kontakt über den Username. Er hat nichts mit der Registrierungs-2FA zu tun |
| `reserved`-Variable vs. `UsernamePinSet` | `reserved` gehört zu `UsernameSet` und markiert eine Reservierung; der Key hat seine eigene Op |
| State `RESERVED` | lokal `C4DU.RESERVED` / Server `state=RESERVED` ist ein gehaltener, noch nicht nutzbarer Name; `ACTIVATED` und `CREATED` sind nutzbar |
| Löschen | es gibt keine Delete-Op; `UsernameSet` ohne `username` löscht; Key-Delete ist `UsernamePinSet` mit `{}` |
| Check-Result `INVALID` | deckt vergeben, Linking-erforderlich und Format-Probleme ab; das Detail steht in `rejection_reasons` |
| Username vs. LID | der Username ist ein Handle; die Adressierungs-Identität ist die LID |
| `source`-Ints | 1 `FB`, 2 `IG`, 3 `USER_INPUT`, 4 `SUGGESTION`; nicht dieselben Ints wie die `C02U`-Error-ids |
| doc_id vs. `client_doc_id` | beide stehen im Asset; die erfassten ids entsprechen `doc_id` |
| Notifications vs. Ops | die drei `Username*Notification`-Typen sind Push-Handler, keine Requests |
| Cross-repo-Labels | `25975613018777537` fehlt im Persist-id-Asset dieses Builds; `25741205615468935` ist in diesem Build `GetTextStatusList`. Keiner von beiden ist hier eine Username-Operation |

---

## 12. End-to-End-Flow

```
[User]                [Client]                              [Server]
  │ type name           │                                      │
  ▼                     │                                      │
 local validate ────────┤ charset, 3..35, dots, regex (5.1)    │
  │ ok                  ▼                                      │
  │              UsernameCheck {username, include_suggestions,  │
  │                             source, session_id}  ─────────►│
  │                     │◄──── xwa2_username_check {result,    │
  │                     │       suggestions, rejection_reasons}│
  │ SUCCESS             │                                      │
  ▼                     ▼                                      │
 confirm ─────────► UsernameSet {username, reserved,           │
                      session_id, source, [pin]} ─────────────►│
                        │◄──── ok | 304 | 40601..40603 | 429/503/529
                        ▼                                      │
                  write prefs: state, username_pin             │
                  429/503/529 -> backoff (flag 28678)          │
                                                               │
 [Owner sets key] ► UsernamePinSet {pin} | {} (delete) ───────►│

 [Other user, first contact]
  │ enter @name + key
  ▼
 validate key (flag 34350) ► usync contact{username,[lid],[pin]} ──►[Server]
                        │◄──── user jid (LID) | no LID | rate-limit flags
                        ▼
              LID  = open chat addressed to the LID
              none = "Wrong key entered"
              limit = "Too many attempts" / "can't be reached"

 [Server push]
   UsernameSetNotification (lid, username)  -> update local map
   UsernameDeleteNotification (lid, pn)     -> update contact
   UsernameUpdateNotification (hash)        -> usync delta
```

---

## 13. Unknowns

| Thema | Grund |
|-------|-------|
| Genauer Accessor, der `query_id` befüllt | Consumer von `doc_id` vs. `client_doc_id` nicht bis zum IQ-Builder nachverfolgt |
| Response-Form von `UsernamePinSet`, `UsernameSet` | Response-Klassen haben im gelesenen Code keinen Field-Access |
| `UsernameGetRecommendationsQuery` | keine Call-Site, keine Variablen |
| Serverseitige Username- und Key-Regeln | Client validiert nur lokal |
| Bedeutung von 40601-40603 serverseitig | nur Client-Strings gefunden |
| Ursprung der `*_on_primary`-Prefs | kein Writer gefunden |
| Effekt von `username_chat_start_mode` | kein Consumer gefunden |
| Nutzungsmuster von `UsernameGet` (Heartbeat) | vom gelesenen Code nicht gestützt |
| Chat-öffnen-Schritt nach korrektem Key | nicht über den LID-Check hinaus nachverfolgt |
| Realer Traffic | nur statische Analyse |
