<!-- src-sha1: 9e1058e3eb76214c55e35cbbb05dda93127364b1 -->
# WhatsApp Username — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-17
**Umfang:** Username Check / Set / Reserve / Delete, Username Key (PIN), LID-Beziehung, Privatsphäre und Sichtbarkeit, w:mex-GraphQL-Operationen (doc_ids, Variablen, Responses), Notifications, USync-Lookup, Validierungsregeln, Feature-Flags, Baileys-Hinweise

---

## 1. Was ein Username ist (technisch)

Ein Username ist ein serverseitiges Handle, das an einen Account gebunden ist und es ermöglicht, einen Kontakt zu erreichen, ohne die Telefonnummer preiszugeben. Alle Aussagen beruhen auf statischer Analyse der dekompilierten APK. Tier: **found** = im Code oder in Assets gelesen, **inferred** = aus dem Code abgeleitet, **unknown** = nicht aufgelöst.

Das Feature besteht aus drei Schichten:

| Schicht | Transport | Verwendet für |
|---------|-----------|---------------|
| Self-Management | `w:mex`-IQ, persistiertes GraphQL (Config `whatsapp-android-mex`) | Check, Set / Reserve / Delete, Get, Key (PIN) Set / Delete, Multi-Check |
| Lookup anderer | USync (`xmlns="usync"`) und die MEX-Variante `UsyncQuery` | `@username` (+ Key) zu einer LID auflösen, den Username einer bekannten JID abrufen |
| Push | MEX-Notifications | `UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification` |
| Geräteübergreifend | App-State-Sync (`SyncActionValue`) | `username_chat_start_mode`, `lid_contact_action` (trägt `username`) |

| Entity | Name in 2.26.41.6 | Rolle |
|--------|-------------------|-------|
| Username-Manager | `C122815Lj` | Aufrufe `UsernameGet`, `UsernameSet`, lokales State-Update, Rate-Limit-Hook |
| Verfügbarkeitsprüfung | `C67402tT` | Aufruf `UsernameCheck` + Response-Mapping |
| Multi Check | `C76333Kg` | `UsernameCheckMulti`, Chunks zu 10 |
| Key-API | `MexUsernamePinProtocolApi` | `UsernamePinSet` (Key setzen / löschen) |
| Lokaler State / Prefs | `C5Q8` | `username_reservation_state`, `username_pin`, `is_username_revoked` |
| State-Enum | `C4DU` | `UNSET`, `RESERVED`, `ACTIVATED`, `CREATED` |
| Eligibility-Modus | `C224069kP.A00()` -> `C9SR` | `CREATION`, `RESERVATION`, `COMPANION_READ_ONLY`, `DISABLED` |
| Rate-Limit-Store | `C67942uO` | Backoff nach 429 / 503 / 529 |
| Lokaler Validator | `C82003fB.A04`, `C1187754z` | Länge, Zeichensatz, Punktregeln, Regex |
| Key-Validator | `C1176550d` (+ `AbstractC111284pZ`) | Key-Format |
| Key-Entry-VM | `UsernamePinEntryViewModel` | Key für einen fremden Username einreichen |
| USync-Client | `C23638AId` (`querySyncUsernameWithErrorInfo`), `C18670m9` | klassischer usync-Stanza-Builder / -Parser |
| MEX USync | `C229259vZ`, `O0F` | `UsyncQuery` mit `include_username` |
| Notification-Handler | `C49822Lvi`, `C49821Lvh`, anonym `X.2YG` in `AbstractC20380p4` | set / delete / update |

Benennung: Der nutzersichtbare Name der PIN ist **Username Key** (Strings "Username key", "Add a username key to control who can contact you"). Wire und Code sagen `pin`.

---

## 2. MEX-Operationen (doc_ids)

### 2.1 Wo die doc_ids liegen

doc_ids sind keine Literale in `java_src`. Der Client sendet den Operationsnamen (`"UsernameSet"`, ...) mit dem Config-Namen `"whatsapp-android-mex"` (found, `C16880is`). Die numerische ID wird aus `assets/whatsapp-android-mex_client_persist_ids.json` gelesen: `EnumC17010j7.WHATSAPP_ANDROID_MEX` bildet auf diese Datei ab, `C17040jA.CMg(op)` liefert das Feld `doc_id`, `AGb(op)` das Feld `client_doc_id` (found). Welcher der beiden Accessoren das Attribut `query_id` füllt, wurde nicht bis zum Ende verfolgt (unknown); frühere Captures auf 2.26.26.4 zeigen `query_id` gleich `doc_id`.

Die folgenden doc_ids sind im Asset von 2.26.41.6 **found**:

| Operation | doc_id | Typ | Aufrufstelle | Response-Klasse |
|-----------|--------|-----|--------------|-----------------|
| `UsernameCheck` | `26124072630599518` | query | `C67402tT.A00` | `C2IG` |
| `UsernameCheckMulti` | `27134626522840286` | query | `C76333Kg.A00` | `C2IE` |
| `UsernameGet` | `32618050064506055` | query | `C122815Lj.A02` | `C87173nz` |
| `UsernameSet` | `27108705368767936` | mutation | `C122815Lj.A00` | `C87183o0` |
| `UsernamePinSet` | `25529696019976770` | mutation | `MexUsernamePinProtocolApi.A00` | `C48557LJz` |
| `UsernameGetRecommendationsQuery` | `26077456248616957` | query | keine gefunden | unknown |
| `UsyncQuery` | `38635300486116501` | query | `C229259vZ.A01` | `C2IQ` |

Hinweise:
- `UsernameGetRecommendationsQuery`: Der Name kommt nur im Asset-JSON vor. Keine Klasse in `java_src` referenziert ihn per String (found). Variablen und Response sind unknown.
- Die drei Notification-Namen (`UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification`) haben keinen Eintrag im Persist-ID-Asset. Es sind Notification-Typen, keine Requests (siehe 7).
- Das Asset hat pro Op `operation_name_hash`, `operation_text_hash` und `client_doc_id`. Beispiel `UsernameSet`: `client_doc_id` `427995565715419341100134328918` (found).

### 2.2 Envelope

Gebaut in `C19370nI` / `C19310nC` (found):

```xml
<iq to="[server jid]" xmlns="w:mex" type="get" id="...">
  <query query_id="DOC_ID">{"queryId":"DOC_ID","variables":{...}}</query>
</iq>
```

| Feld | Regel (Code) |
|------|--------------|
| `xmlns` | `w:mex` |
| `type` | `get` für jede Operation, auch für Mutations |
| Attribut `query_id` | nur gesetzt, wenn 1 bis 20 Zeichen |
| Body | JSON `{"queryId": ..., "variables": {...}}`, 1 bis 8448000 Bytes |
| Null-Variablen | `C16770ig.A03(k, null)` und `A02(k, null)` überspringen den Key; ein fehlender Wert bedeutet also, dass der Key nicht gesendet wird |

Wire-Stanzas von Live-Sessions werden hier nicht wiedergegeben; dieser Build wurde nur statisch analysiert.

---

## 3. Operationen im Detail

### 3.1 UsernameCheck

Variablen (found, `C67402tT.A00`):

| Variable | Typ | Bedingung |
|----------|-----|-----------|
| `username` | string | immer |
| `include_suggestions` | bool | immer (die UI übergibt `false` im Typed-Check-Pfad `C64H` case 21) |
| `source` | string | nur wenn nicht null |
| `session_id` | string | nur wenn nicht null |

`source`-Mapping (`AbstractC78993Wd.A0U`): int 1 -> `FB`, 2 -> `IG`, 3 -> `USER_INPUT`, 4 -> `SUGGESTION`, sonst -> null (nicht gesendet).

Response-Pfad (found, `C77183Np` Default-Zweig): `data.xwa2_username_check`

| Feld | Typ | Verwendung |
|------|-----|------------|
| `result` | enum `EnumC59782gh` | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `INVALID`, `SUCCESS` |
| `suggestions` | list<string> | nur bei `INVALID` gelesen |
| `rejection_reasons` | Liste von `C4G8` | nur bei `INVALID` gelesen |
| `suggestions_eligible` | bool | Standard `true`, wenn das Feld null ist |

`C4G8`-Werte (found): `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALREADY_TAKEN`, `REQUIRE_FB_ACCOUNT_LINKING`, `REQUIRE_FB_CONSUMER_ACCOUNT_LINKING`, `REQUIRE_IG_ACCOUNT_LINKING`, `REQUIRE_IG_CONSUMER_ACCOUNT_LINKING`.

Mapping: `SUCCESS` -> `C76283Kb` (verfügbar); `INVALID` -> `C76303Kd` (nicht verfügbar, trägt Suggestions + Reasons); `UNSET` -> kein Zweig weist ein Result zu (Callback erhält die vorherige/null-Variable; Verhalten unknown). Aktiver lokaler Backoff -> `C76293Kc` (Fehler mit Rate-Limit-Code aus den Prefs, siehe 5.3); der Failure-Callback des Requests selbst wurde nicht gelesen.

Rejection Reasons steuern den Account-Linking-Text ("This username matches an account on Facebook/Instagram. To use it ... add your accounts to Accounts Center", `C82003fB`). In `C82003fB` löst jeder Reason außer `UNSET` den lokalen Fehlerpfad mit Code 40601 aus (`A08(40601L)`); eine leere oder nur aus `UNSET` bestehende Liste zeigt "Username isn't allowed." Der genaue Kontrollfluss um die Schleife ist nur teilweise dekompiliert (inferred).

### 3.2 UsernameCheckMulti

| Variable | Typ | Hinweise |
|----------|-----|----------|
| `usernames` | **list<string>** | Array über `A00.A0B("usernames", list)`; der doc_id-Katalog typisiert es als `str`, der Code sendet eine Liste |

Batching (`C76333Kg.AG5`): Die Liste wird in die ersten 10 und den Rest geteilt; der Rest wird nach einer Verzögerung von Flag **29327** verarbeitet (Standard 60, Einheit nicht aufgelöst). Eine leere Liste liefert ohne Request eine leere Map.

Response-Pfad `data.xwa2_username_check_multi.results[]` (found): Jedes Item hat `username` und `response.result` (gleiches `EnumC59782gh`). Mapping: `SUCCESS` -> verfügbar, `INVALID` -> nicht verfügbar (keine Suggestions, `suggestions_eligible=false`), alles andere -> Fehler. Im Result fehlende Namen werden als Fehler markiert.

Konsument: `UsernameAvailabilityCache` speichert `EnumC59192fk` (`UNKNOWN`, `AVAILABLE`, `UNAVAILABLE`) pro Name. Der Zweck (Prefetch für Facebook-/Instagram-Username-Suggestions, String `foa_username_prefetch_cache`) ist inferred.

### 3.3 UsernameSet (anlegen / ändern / reservieren / löschen)

Variablen (found, `C122815Lj.A00`):

| Variable | Typ | Bedingung |
|----------|-----|-----------|
| `username` | string | weggelassen, wenn null (**Delete**) |
| `reserved` | bool | immer gesendet |
| `session_id` | string | nur wenn nicht leer (`C1YW.A08`) |
| `source` | string | nur wenn der Source-Int nicht null ist (siehe 3.1) |
| `pin` | string | nur wenn nicht null |

`reserved` wird berechnet, ist nicht konstant (found). Argument `z` (force) = true ergibt `false`. Sonst: aktueller State `ACTIVATED` oder `CREATED` ergibt `false`; aktueller State `RESERVED` oder Eligibility-Modus `RESERVATION` ergibt `true`; alle anderen Fälle ergeben `false`. `reserved:true` wird also nur für Accounts im Reservation-Modus oder mit bereits bestehender Reservierung gesendet.

Delete ist ein Modus derselben Operation: `username == null` -> Log-Tag `delete`, sonst `set` (auch in `MexUsernamePinProtocolApi` für den Key). Bei null-Username ist der Key `username` nicht in den Variablen (found).

Client-seitiger Guard: Meldet der Rate-Limit-Store vor dem Senden einen aktiven Backoff, schlägt der Aufruf lokal mit `username_creation_rate_limit_error_code` und dem Text "rate limit expiration time not reached" fehl (found, `C122815Lj.A03`).

Erfolgsbehandlung (`C122815Lj.A01`, found):

| Bedingung | Geschriebener lokaler State (`username_reservation_state`) |
|-----------|-----------------------------------------------------------|
| Username null oder leer | `UNSET`, Key-Pref gelöscht |
| `reserved` war true | `RESERVED` |
| Activate-Flag | `ACTIVATED` |
| sonst | `ACTIVATED`, wenn der State `ACTIVATED` war und der Name dem gespeicherten Namen entspricht, andernfalls `CREATED` |
| `source`-Int ist 1 oder 2 | Pref `username_set_via_account_linking` = (int == 2) |
| `pin` gesendet | Pref `username_pin` aktualisiert |
| Teen-Flag | Pref `is_teen_account` = true |

Der Pref-Write ist `Voip.REJECT_REASON_DECLINED`, in diesem Build der leere String `""` (found).

Fehlerbehandlung (`C138725uA` case 2):

| HTTP-ähnlicher Code | Client-Aktion |
|---------------------|---------------|
| 429, 503, 529 | Backoff gespeichert (5.3) |
| 304 | als Erfolg behandelt ("not modified"), lokaler State wird dennoch aktualisiert |
| keine Verbindung (`C213639Bb`) | `C4BO`-Result "no network" |
| andere | `C4BN(code, message)` |

### 3.4 UsernameGet

Variablen: keine (der Aufruf baut ein leeres Variablenset, found, `C122815Lj.A02`). Als `@Deprecated` markiert, ersetzt durch eine Suspend-Variante.

Response (found, `C138815uJ` case 34): `data.xwa2_username_get.username_info`

| Feld | Verwendung |
|------|------------|
| `username` | gespeichert; leerer String, wenn nicht vorhanden |
| `state` | `C4FC`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `RESERVED` |
| `pin` | **der Key wird im Klartext zurückgegeben und im Pref `username_pin` gespeichert**; leerer String, wenn nicht vorhanden |

State-Mapping: `RESERVED` -> `C4DU.RESERVED`; `ACTIVE` -> `ACTIVATED`, wenn der gespeicherte Username dem zurückgegebenen entspricht und der lokale State `RESERVED` oder `ACTIVATED` war, sonst `CREATED`; State null oder `username_info` null -> `UNSET`.

Der Fehlerfall 404 vom Server löscht den lokalen Username, Key und State (Log `clearSelfUsernameData NOT_FOUND`).

Ob der Aufruf als Heartbeat genutzt wird, ist unknown; die alte Notiz "polling heartbeat" wird vom Code dieses Builds nicht gestützt.

### 3.5 UsernamePinSet (Username Key)

Variablen (found): `pin` (string), weggelassen wenn null.

| Aktion | Variablen |
|--------|-----------|
| Key setzen | `{"pin": "<key>"}` |
| Key löschen | `{}` (`A02` ruft `A00(null)` auf) |

Der Operationsname ist für beides `UsernamePinSet`; es gibt keine separate Verify-Operation. Die Verifikation eines fremden Keys erfolgt in USync (4). Nicht verbunden: liefert `C213639Bb("UsernamePinSet")` ohne Request.

Der Key kann auch in `UsernameSet` mitfahren (Variable `pin`). `C81793ej.A0x` nutzt `UsernameSet` mit dem vorhandenen Username und dem neuen `pin`, wenn lokal bereits ein Username gespeichert ist (`A00 != null`), sonst `UsernamePinSet` (found).

Die Response-Klasse `C48557LJz` hat in den gelesenen Dateien keinen Feldzugriff; die Response-Form ist unknown.

---

## 4. Lookup anderer Nutzer

### 4.1 Klassisches USync per Username (Key-Flow)

Gebaut in `C18670m9.A06` (jadx scheiterte an dieser Methode, aus Smali `X/0m9.smali` gelesen). Pro `C222649hm`-Request-Eintrag: Feld `A0C` = Username, `A0D` = Key, `A05` = LID.

Attribute des Contact-Childs (found in Smali): `username` immer; `lid`, wenn lokal eine LID bekannt ist; `pin`, wenn ein Key gesetzt ist. Die zusätzlichen Attribute werden durch Flag **12402** (Standard `false`) gesteuert: Ist das Flag aus, wird nur `username` geschrieben (found). Der Node-Name `contact` ist inferred aus dem Response-Parser, der das Child `contact` und sein Attribut `username` liest (`C18670m9` Zeilen ~969-975).

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

Einstiegspunkt: `C23638AId.A0G(username, key)` (`querySyncUsernameWithErrorInfo`), aufgerufen von `submitPinForUsername`. Sync-Typ `EnumC21760rz.A0J`, Timeout 32000 ms. Die Attributmenge `contact`, `pin`, `username` steht in den Log-Redaction-Sets von `AbstractC40921lc` (found).

Lokale Vorauflösung: `A0M.Aol(username)` schlägt `lid_row_id` in der Tabelle `lid_display_name` nach, wo `UPPER(username) = UPPER(?)`, neueste Zeile zuerst (found, `C1S0`). Die LID, falls bekannt, geht in das Attribut `lid`.

### 4.2 Ergebnisbewertung (Key-Eingabe)

`UsernamePinEntryViewModel$submitPinForUsername$1` (found):

| Ergebnis | Bedingung |
|----------|-----------|
| korrekter Key | Result-`UserJid` ist eine LID (`C14080dr`) |
| falscher Key | Result hat keine LID: Log `[un-pin] incorrect PIN`, Fehlertext "Wrong key entered" |
| kein Netzwerk | `C9qA` Code 1 |
| generischer Infra-Fehler | `C9qA` Code 2 |
| Requestor-Rate-Limit | `C225769os.A01` true: "Too many attempts made. Try later." |
| Requestee-Rate-Limit | `C225769os.A00` true: "This account can't be reached with their key right now..." |

Die clientseitige gecachte Rate-Limit-Prüfung läuft zuerst, wenn Flag **16033** an ist und die JSON-Config **21995** `enable_key_rate_limit` true hat (Standard true): `C30P.A00` gegen die eigene LID und gegen den Ziel-Username. Der Username wird von `@` befreit (`C0CX.A0i(username, '@')`).

Bei Erfolg ist das Result eine **LID**, der Chat wird dann an die LID adressiert (inferred aus der `C14080dr`-Prüfung; der Chat-Öffnen-Schritt wurde nicht verfolgt).

### 4.3 Username einer bekannten LID abrufen

`C23638AId` (Zeile ~600-650) baut ein usync mit `<list><user jid="LID"/></list><query><contact/><username/></query>`, Mode/Context aus `EnumC21760rz.A0J` (found). Der Parser liest `username` als Child des `<usync>`-Results (`C18670m9` Zeile 586, nur wenn der Request es angefordert hat).

### 4.4 MEX USync (`UsyncQuery`)

`C229259vZ.A01` baut `UsyncQuery` (doc_id oben). Relevante Teile (found):

| Variable | Verwendung |
|----------|------------|
| `query_input[]` | ein Eintrag pro Nutzer: JID (`C493020r.A0C`), optional `client_known_username` (nur wenn Username angefordert und nicht leer) |
| `include_username` | bool, gesetzt, wenn ein Eintrag den Username anfordert |
| `include_lid` | bool, fordert `lid_info` an |
| `telemetry.context` | kleingeschriebener USync-Context |

Response pro Nutzer: `jid`, `username_info`, `lid_info` (`O0F`). `username_info` ist per Type-Hash polymorph: ein Value-Typ mit `username`, oder ein Status-Typ mit `status` aus `EnumC216389Tz`: `EMPTY`, `NOT_ALLOWED`, `NO_CHANGE` (+ unset). `NOT_ALLOWED` wird als "username not allowed to be queried" geloggt und löscht den gespeicherten Username; `NO_CHANGE` behält ihn. `lid_info.lid_jid` trägt die LID.

Gate: `ContactSyncHelper` verweigert den MEX-Pfad mit dem Log "cantUseMex as username ab prop is off", sofern bei angefordertem Username nicht Flag **8421** an ist (found; Standard `false`).

---

## 5. Validierung, Limits, Fehler

### 5.1 Username-Format (lokal)

Validator `C82003fB.A04` (found), Prüfungen in dieser Reihenfolge:

| Reihenfolge | Prüfung | Fehler-ID (`C02U`) | Meldungstext |
|-------------|---------|--------------------|--------------|
| 1 | jedes Zeichen in `[A-Za-z0-9_.]` | 2 | "must start with a letter and can only contain letters, digits, periods and underscores" |
| 2 | Länge >= min (Flag **20494**, Standard 3) | 0 | "Use between %1$d-%2$d characters" |
| 3 | Länge <= max (Flag **20459**, Standard 35) | 1 | derselbe String |
| 4 | kein führender `.`, kein abschließender `.`, kein `..` | 3 | "can't start or end with a period or have 2 periods in a row" |
| 5 | mindestens ein ASCII-Buchstabe | 4 | "Choose a username with at least one letter" |
| 6 | Regex (unten) | besteht oder scheitert mit 2 | n/a |

Von `C1187754z.A02()` gebauter Regex (found):

```
^(?!.*\.\.)(?=.*[a-zA-Z])[a-zA-Z0-9_][a-zA-Z0-9_.]{MIN-1,MAX-1}(?<![.])$
```

Die Groß-/Kleinschreibung wird vom Validator nicht normalisiert; der lokale Lookup `Aol` vergleicht mit `UPPER()`, lokal ist der Abgleich also case-insensitive (found). Ob der Server Namen case-insensitive behandelt, ist unknown. Ein führender Unterstrich ist laut Regex erlaubt; der UI-Text sagt "start with a letter", was strenger ist als der Regex (found, Widerspruch).

Die UI lehnt außerdem Weblinks ab: "Enter only your username, not a web link" (String vorhanden, Prüfung nicht verfolgt).

### 5.2 Username-Key-Format

`C1176550d.A00` (found): Flag **34350** ist ein Regex-String, Standard `^([0-9]{4}|[A-Z0-9]{6})$`. Ist der Flag-String leer, ist der Fallback genau vier Ziffern. Ein ungültiger Regex loggt `[un-pin] invalid username_key_regex` und akzeptiert alles. Die Längengrenzen Flags **34347** (min, 4) und **34348** (max, 6) speisen nur den Fehlermeldungspfad in `UsernamePinEntryViewModel.A0w`. Serverseitige Regeln sind unknown.

Die alte Notiz "4-digit PIN" ist also unvollständig: Der ausgelieferte Standard akzeptiert vier Ziffern oder sechs alphanumerische Großbuchstaben bzw. Ziffern.

### 5.3 Rate Limits und Backoff

`C67942uO` (found), nur aktiv mit Flag **28678** (Standard `false`):

| Element | Wert |
|---------|------|
| Auslöser | `UsernameSet`-Fehler 429, 503 oder 529 |
| Dauer | `Retry-After`-ähnlicher String, als Int-Sekunden geparst (`C23680AJt.A00`), sonst Flag **28127** (Standard 30) Sekunden |
| Speicherung | Prefs `username_creation_rate_limit_backoff_expiry` (ms), `username_creation_rate_limit_error_code` |
| Wirkung | `UsernameCheck`, `UsernameCheckMulti`, `UsernameSet` schlagen bis zum Ablauf lokal fehl |

### 5.4 Fehlercode zu Meldung (`C82003fB.A02`, found)

| Code | Meldung |
|------|---------|
| 400 | "Couldn't save your username. Try again." |
| 403, 404, 429 | "Couldn't complete your request. Try again." |
| 500, 529 | "We couldn't complete your request. Try again later." |
| 503 | "... Please try again later." |
| 406, 40601 | "This username is not available." |
| 40602 | "You can't make more changes to your username. Try again later." |
| 40603 | "You can't make changes to your username right now. Try again later." |
| andere | "We couldn't complete your request. Try again." |

40601 bis 40603 stehen im erlaubten Set `AbstractC111104pH.A01` (im gelesenen Code nur 40603 sichtbar). Ihre Server-Semantik ist über den Client-Text hinaus unknown.

---

## 6. LID-Beziehung

Alles found, sofern nicht anders markiert.

| Fakt | Beleg |
|------|-------|
| Username-Lookups lösen zu einer **LID** auf, nicht zu einer Telefon-JID | Key-Erfolgstest `userJid instanceof C14080dr` (LID-Klasse); `lid_info.lid_jid` in MEX usync |
| Lokale Map Username -> LID | Tabelle `lid_display_name` (Spalten `username`, `lid_row_id`), Query in `C1S0` |
| Notifications identifizieren den Nutzer per LID | Set-/Delete-Handler parsen `LidUserJid` (Fehlertext "Failed to parse LidUserJid") |
| Delete-Notification kann eine Telefon-JID tragen | Handler prüft `isPnPresent`; mit PN castet er eine PN-JID und handelt, ohne PN kehrt er zurück |
| Contact-Sync-Action | `ContactAction` hat `username` (6) neben `lid_jid` (3), `pn_jid` (5); außerdem `LidContactAction` (`lid_contact`, SyncActionValue-Feld 61) |
| Chat-Start-Modus | SyncActionValue-Feld **59** `username_chat_start_mode`, Enum `EnumC50053M6w`: `LID` = 1, `PN` = 2. Nur der Sync-Codec wurde gefunden; kein Konsument im UI-Code (unknown) |
| Companion-Feature-String | Beim Verknüpfen eines Companions fügt das Primärgerät `username_supported` (Flag 4745 oder 20189), `username_reservation_only_mode` (nur 20189), `username_account_linking_enabled` (Flag 21199) zu seiner Feature-Liste hinzu (`C25056AqU`) |

Inferred: Ein Nutzer, der nur als Username existiert, ist nur über die LID erreichbar, bis der Inhaber die Telefonnummer teilt; die Strings "If you continue, your phone number will show in existing username chats and calls" (Delete-Dialog) stützen das, der PN-Exposure-Pfad wurde aber nicht verfolgt.

---

## 7. Notifications

Handler erweitern `AbstractC23194A0r` und sind in `AbstractC20380p4` registriert (found):

| Notification | Handler | Verhalten |
|--------------|---------|-----------|
| `UsernameSetNotification` | `C49822Lvi` | Payload `xwa2_notify_username_on_change`: liest LID (Feld-Hash 107143) und Username; speichert über `InterfaceC11470Yz.BNU(lid, username)`; existiert der Kontakt und ist von passender Art, wird der Kontakt aktualisiert (`C12440bB.A0W`) |
| `UsernameDeleteNotification` | `C49821Lvh` | Payload `xwa2_notify_username_delete`: liest LID und PN (Hash -983979708); mit vorhandener PN läuft das Delete-Update (`C53594Nzh`) |
| `UsernameUpdateNotification` | anonym `X.2YG` | liest einen base64-Hash aus der Payload, baut einen USync-Request mit Reason `USERNAME_UPDATE_NOTIFICATION` und `EnumC21760rz.A0Q` (Delta-artiger Sync, inferred), Log `usync triggered for hash` |

Dem Nutzer gezeigter Text: "Your username has changed", "WhatsApp has assigned you a new username (%1$s)", d. h. der Server kann einen Username neu zuweisen (Widerruf, Pref `is_username_revoked`, `revocation_banner_dismissed_<username>`).

---

## 8. Feature-Flags

Flag-IDs sind AB-Prop-IDs, gelesen über `C08J` (Standardwerte aus `C08J`-Tabellen). Alle Standardwerte unten wurden aus diesem Build gelesen.

| Flag | Typ | Standard | Steuert |
|------|-----|----------|---------|
| **4745** | bool | false | Primärgerät: Username-Erstellung (`CREATION`-Modus); wird auch als `username_supported` beworben |
| **20189** | bool | false | Primärgerät: Reservation-only-Modus (`RESERVATION`); `username_supported` |
| **23817** | bool | false | Companion: Username-Features überhaupt (sonst `DISABLED`) |
| **21199** | bool | false | Account Linking (FB / IG) aktiviert, beworben als `username_account_linking_enabled` |
| **16033** | bool | false | Master-Gate für Key-Features (`C79343Xx.A00`): Key-Rate-Limit, Key-Upsell, WABI-Username-View |
| **21995** | JSON | `{}` | `enable_key_rate_limit`, `enable_key_upsell_flows`, `enable_wabi_username_view` (alle standardmäßig true, wenn der JSON-Key fehlt) |
| **8421** | bool | false | erlaubt MEX-`UsyncQuery` für Username-Requests |
| **12402** | bool | false | fügt dem usync-`contact`-Node die Attribute `lid` und `pin` hinzu |
| **20494** / **20459** | int | 3 / 35 | min. / max. Username-Länge |
| **34350** | string | `^([0-9]{4}\|[A-Z0-9]{6})$` | Key-Regex |
| **34347** / **34348** | int | 4 / 6 | Key-Längengrenzen (Fehlermeldung) |
| **28678** | bool | false | aktiviert den Rate-Limit-Backoff-Store |
| **28127** | int | 30 | Standard-Backoff-Sekunden |
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

## 9. Privatsphäre und Sichtbarkeit

| Aspekt | Befund | Tier |
|--------|--------|------|
| Zweck | "Keep your phone number private with a username"; Leute, die die Nummer nicht gespeichert haben, sehen stattdessen den Username | found (Strings) |
| Erstkontakt | bei gesetztem Key müssen Leute, mit denen "you haven't interacted", den Key eingeben, bevor sie den Username kontaktieren | found (Strings) |
| Key-Sharing | die Username-Share-Aktion kann den Key enthalten (Pref `username_share_include_pin`, in `C138535tr` wegmigriert); Strings "Share your username and key" | found |
| Wo die Nummer verborgen wird | Community-Admins und Channel-Admins sehen die Nummer, solange kein Username gesetzt ist; Channel-Follower sehen keines von beiden | found (Strings) |
| Gruppen-/Thread-Telemetrie | Felder `has_username`, `has_username_pin`, `is_username_thread` in der Message-Send-Telemetrie (`DZ1`, `RQG`) | found |
| Key at rest | der eigene Key wird von `UsernameGet` zurückgegeben und in den Klartext-Prefs `username_pin` gespeichert | found |
| Chats Dritter | "Usernames and contacts added to third-party chats will not save to your phone" | found (String) |
| Business | "This username is only available on WhatsApp Business" erscheint als Rejection-Text | found (String) |
| Wer abfragen darf | der MEX-usync-Status `NOT_ALLOWED` zeigt, dass der Server die Username-Offenlegung pro Anfragendem verweigern kann | found (Enum), Regel unknown |
| Minderjährige | Pref `is_teen_account`; Eltern-Texte "Your child created the username ..." | found |

Vom Server durchgesetzte Sichtbarkeitsregeln (wer einen Username auflösen darf, Key-Rate-Limits, Neuzuweisung) sind vom Client aus unknown.

---

## 10. Baileys-Hinweise

Das Envelope in 2.2 ist generisch; ein Baileys-Client kann es bauen. Das ist **inferred**, hier nicht getestet.

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
|--------|-------|
| doc_id-Drift | die IDs gehören zum Asset dieses Builds; andere Builds können abweichen (unknown) |
| `session_id` | der Code sendet sie, wenn vorhanden; ob der Server für Check und Set denselben Wert verlangt, ist unknown |
| Key-Attribute | `lid` / `pin` am `contact` stehen hinter Flag 12402; der Server ignoriert sie für Clients ohne das Flag möglicherweise (unknown) |
| lokale Regeln | Länge, Zeichensatz und Punktregeln sind clientseitig; die Serverregeln sind unknown |

---

## 11. Wichtige Unterscheidungen

| Nicht verwechseln | Unterschied |
|-------------------|-------------|
| Username Key vs. Account-PIN / 2FA | Der Username Key (`pin` in `UsernamePinSet`, Pref `username_pin`) steuert den Erstkontakt über den Username. Er hat nichts mit der Registrierungs-2FA zu tun |
| Variable `reserved` vs. `UsernamePinSet` | `reserved` gehört zu `UsernameSet` und markiert eine Reservierung; der Key hat eine eigene Op |
| State `RESERVED` | lokal `C4DU.RESERVED` / Server `state=RESERVED` ist ein gehaltener, noch nicht nutzbarer Name; `ACTIVATED` und `CREATED` sind nutzbar |
| Delete | es gibt keine Delete-Op; `UsernameSet` ohne `username` löscht; Key-Delete ist `UsernamePinSet` mit `{}` |
| Check-Result `INVALID` | deckt vergeben, Linking erforderlich und Formatprobleme ab; das Detail steht in `rejection_reasons` |
| Username vs. LID | der Username ist ein Handle; die Adressierungsidentität ist die LID |
| `source`-Ints | 1 `FB`, 2 `IG`, 3 `USER_INPUT`, 4 `SUGGESTION`; nicht dieselben Ints wie die `C02U`-Fehler-IDs |
| doc_id vs. `client_doc_id` | beide stehen im Asset; die erfassten IDs entsprechen `doc_id` |
| Notifications vs. Ops | die drei `Username*Notification`-Typen sind Push-Handler, keine Requests |
| Cross-Repo-Labels | `25975613018777537` fehlt im Persist-ID-Asset dieses Builds; `25741205615468935` ist in diesem Build `GetTextStatusList`. Keines von beiden ist hier eine Username-Operation |

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
| Genauer Accessor, der `query_id` speist | Konsument von `doc_id` vs. `client_doc_id` nicht bis zum IQ-Builder verfolgt |
| Response-Form von `UsernamePinSet`, `UsernameSet` | Response-Klassen haben im gelesenen Code keinen Feldzugriff |
| `UsernameGetRecommendationsQuery` | keine Aufrufstelle, keine Variablen |
| Serverseitige Username- und Key-Regeln | der Client validiert nur lokal |
| Bedeutung von 40601-40603 auf dem Server | nur Client-Strings gefunden |
| Herkunft der `*_on_primary`-Prefs | kein Writer gefunden |
| Wirkung von `username_chat_start_mode` | kein Konsument gefunden |
| Nutzungsmuster von `UsernameGet` (Heartbeat) | vom gelesenen Code nicht gestützt |
| Chat-Öffnen-Schritt nach korrektem Key | nicht über die LID-Prüfung hinaus verfolgt |
| Tatsächlicher Traffic | nur statische Analyse |
