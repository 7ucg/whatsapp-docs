<!-- src-sha1: 4762669c756eee4725aaf5af56633f2b59edd479 -->
# WhatsApp AB Props — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** AB Props / Feature-Flags auf Android: numerische Flag-IDs und typisierte Default-Tabellen, typisierte Reader und Read-Optionen, MobileConfig-Schicht (Stable IDs, Unit-Typen, `params_map_v4_u*`, `MetaConfigFetchMutation`), Props-Sync-IQ (`xmlns="abt"`: hash, refresh, refresh_id, delta, Expo-Keys, Sampling-Gewichte), Props auf Gruppenebene, Props vor der Registrierung, On-Device-(Offline-)Experimente, Speicherung auf dem Gerät, Exposure-Logging, Override- und Debug-Pfade, Bezug zu den Flag-IDs aus anderen Reports, Flag-Katalog nach Bereichen, Vergleich mit Baileys

---

## 1. Was es ist (technisch)

AB Props sind die serverseitig gesteuerten Feature-Flags des Clients. Jedes Flag wird nur über einen numerischen **config code** identifiziert (z. B. `20548`); im APK existiert kein Flag-Name. Der Client liefert pro Code eine typisierte Default-Tabelle mit, fragt den Server per IQ nach Overrides, speichert die Antwort in SharedPreferences und liest sie über eine abstrakte Reader-Klasse. Daneben läuft eine zweite, von Meta abgeleitete Schicht (MobileConfig), die zur Source of Truth werden kann. Alle Aussagen stammen aus statischer Analyse des dekompilierten APK; nichts wurde auf der Leitung mitgeschnitten. Tiers: **found** = im Code oder in Daten gelesen, **inferred** = abgeleitet, **unknown** = nicht aufgelöst. Obfuskierte Namen gelten pro Build und wurden in 2.26.41.6 neu aufgelöst.

| Schicht | Name in 2.26.41.6 | Rolle |
|---------|-------------------|-------|
| Reader-Basis | `C00D` (abstract) | typisierte Accessoren, Caches, Exposure, MobileConfig-Umschaltung |
| Haupt-Store | `C08J` (`extends C00D`, Prefs `ab-props`) | hält die fünf Default-Maps, liest alle normalen Flags |
| Pre-chatd-Store | `C0D9` (Prefs `ab-prechatd-props`) | Flags, die per HTTP geholt werden, bevor der Account verbunden ist |
| Private Store | `C0ER` (Prefs `ab-private-abprop`) | Werte der On-Device-Experimente, dieselben Defaults wie `C08J` |
| Read-Optionen | `C00F` (`AbPropsOptions`) | Exposure-Modus + First-Access-Pinning |
| Typisierte Deskriptoren | `C054909t` ABPropBoolean, `C055109v` ABPropInt, `C1OT` ABPropFloat, `C055009u` ABPropString, `C055209w` ABPropJson | ID + Call-Site-Default |
| Sync-Manager | `C0D2` (`ABPropsManager`) | Speicherung, Hash, Refresh, Backup, Pre-chatd-Update |
| Request / Response | `C27646BzW` (Request), `C28894Cgv` (Response + Fehler) | `<iq xmlns="abt">` |
| Trigger | `RunnableC48591z1` Default-Branch (Log `MessageHandler/maybeGetNewAbProps`), `C1S0` Handler von `<... abprops/>` | wann ein Fetch gesendet wird |
| Gruppen-Props | `C41861nA` (`GroupAbPropsManager`), `C502324k` (Trigger), `C28900Ch1` (Response) | Werte pro Gruppe |
| MobileConfig | `C053409d` (Factory), `C054709r` (`InterfaceC054609q`), `C06510El` (Stable-ID-Tabelle), `C34081Wt` / `C34091Wu` (typisierte Lambdas), `C06460Eg`, `C053809h` (Overrides-Tabelle), `CQN` + `C29448CqB` (Fetcher), `C41251mA` (Fetch-Koordinator) | nativ gestützte Engine, MEX-Fetch |
| Exposure | `C42831om`, `BxP`, `C27952CBv`, WAM-Event `C44051qo` (5504) | Exposure-Keys |
| Offline AB | `C24976ApB`, `C27629BzE`, `C60839RQl`, `ON0` / `ON1` / `C53973OMy`, `ConfigVariable` | lokale Experiment-Zuweisung |
| Observer | `C0NE` (3 Callbacks), 46 Implementierer, z. B. `CY8` | reagieren auf geänderte Werte |

Entscheidende Punkte:

- Der Flag-ID-Raum ist ein einziger numerischer Raum (maximale ID **39140**, 21.424 IDs mit Default). `C05Z.A00(n)`, `C1XG.A0I(n)`, IQ-Typ-Ints und WAM-IDs sind andere Zahlenräume (Abschnitt 12).
- Namen erreichen den Client nie. Weder in den Default-Tabellen, noch in der Sync-Response (nur `config_code`), noch in einer Resource.
- Es gibt drei parallele Sync-Pfade: die `abt`-IQ (Nutzerebene), die `abt`-IQ mit `group=` (Gruppenebene) und den MobileConfig-MEX-Fetch (Abschnitt 4).

---

## 2. Flag-Modell

### 2.1 Typen und Default-Tabellen (found, `C08J`)

Fünf unveränderliche Maps werden im `C08J`-Konstruktor gebaut (`buildKeepingLast`, doppelte Puts im Decompile sind daher harmlos). Die Zahlen sind eindeutige IDs pro Map:

| Typ | Map | Accessoren auf `C00D` | IDs | Beispiel |
|-----|-----|-----------------------|-----|----------|
| bool | `A1A()` | `A15(id)`, `A18(ABPropBoolean)`, `A0E(...)` | 16.668 (1.237 mit Default `true`) | `9667` true |
| int | `A1C()` | `A0b(id)`, `A0f(ABPropInt)`, `A02(...)` | 3.530 | `996` 604800 |
| float | `A1B()` | `A0Z(id)`, `A0a(ABPropFloat)`, `A00(...)` | 177 | `31535` 0.0 |
| string | `A1E()` | `A0j(id)`, `A0n(ABPropString)`, `A08(...)` | 867 | `34350` regex |
| JSON | `A1D()` | `A0p(id)`, `A0r(ABPropJson)`, `A09(...)` | 182 | `21995` `{}` |

Keine ID steht in zwei Maps. Statische Literal-Reads (`A15(n)`, `A0b(n)`, `A0j(n)`, `A0Z(n)`, `A0p(n)`): 16.355 Call-Sites in `p000X` und `com`; Deskriptor-Reads kommen hinzu (Konstruktionsstellen: 492 ABPropBoolean, davon 482 verschieden, 259 ABPropInt, 30 ABPropFloat, 66 ABPropString, 12 ABPropJson).

Default-Auflösung (found, `C00D.A0D`, `A01`):

| Schritt | Regel |
|---------|-------|
| 1 | im Speicher gecachter Wert für diesen Prozess |
| 2 | gespeicherter Serverwert in den Prefs `ab-props` unter dem Key `String.valueOf(id)` |
| 3 | Default aus der Map des ID-Typs |
| 4 | Call-Site-Default eines ABPropX-Deskriptors (nur wenn die Map keinen Eintrag hat) |
| 5 | keiner: `IllegalArgumentException("Unknown BooleanField: <id>")` (int: `Unknown IntField`) |

Für alle 482 verschiedenen ABPropBoolean-Deskriptoren existiert die ID in der Map, und der Produktions-Default des Deskriptors entspricht dem Map-Default. `debugDefaultValue` von ABPropBoolean weicht in 182 davon vom Produktions-Default ab, wird aber nirgends gelesen außer in `equals` / `hashCode` / `toString` (Smali: das Feld `A02` wird nur innerhalb von `09t` referenziert; die Accessoren nutzen nur ID und Produktions-Default). In diesem Build hat es keine Laufzeitwirkung.

### 2.2 Wert-Parsing beim Speichern (found, `C0D2.A00`)

| Map der ID | Gespeichert als | Parse |
|------------|-----------------|-------|
| bool | `putBoolean` | `Integer.parseInt(config_value) != 0` (Wire-Form `"1"` / `"0"`) |
| int | `putInt` | `Integer.parseInt` |
| float | `putFloat` | `Float.parseFloat` |
| string | `putString` | unverändert |
| JSON | `putString` | validiert mit `new JSONObject(...)`; bei Fehler loggt es `ABPropsManager/invalid format for config; configCode=...` und das Prop wird nicht gespeichert |
| ID in keiner Map | `putString` | als String gespeichert; ein typisierter Read einer solchen ID hat keinen Default und wirft (2.1 Schritt 5) |

Anders als in der WA-Web-Tabelle (unbekannte Codes werden verworfen) behält Android unbekannte Codes als Strings (found).

### 2.3 Read-Optionen (found, `C00F` = `AbPropsOptions`)

| Konstante | exposureOptions | firstAccessValue | Verwendet als |
|-----------|-----------------|------------------|---------------|
| `A03` | WITH_EXPOSURE_LOGGING (1) | false | Default für alle einfachen Reads (`A15`, `A0b`, ...) |
| `A02` | WITH_EXPOSURE_LOGGING | true | `A19(...)`, `A16`, MobileConfig-Bootstrap-Reads |
| `A06` / `A05` | WITHOUT_EXPOSURE_LOGGING (0) | false / true | `A00()` leitet sie ab |
| `A04` | WITH_URGENT_EXPOSURE_LOGGING (2) | false | Pre-chatd-Store, wenn Flag **24317** an ist |

`firstAccessValue = true` pinnt den ersten im Prozess gelesenen Wert in `C00D.A07` (ConcurrentHashMap); spätere Reads dieser ID liefern den gepinnten Wert, auch nach einem Sync (found, `C00D.A0D`, `A0i`). Einfache Reads nutzen den Cache `A0P`, den `A0s()` nach jedem Sync leert.

### 2.4 Read-Pfad und Source of Truth (found, `C00D.A07` Smali; Namen der Schalter aus der Verwendung inferred)

```
read(id)
  ├─ A14() true  (A0E && A0b && !A0S)  and A08 set  and MobileConfig context present
  │      └─► MobileConfig value via C34081Wt/C34091Wu  (Stable ID lookup, C054709r.B6F)
  └─ else
         ├─ legacy value: cache A0P ► prefs "ab-props" ► default map
         └─ if A0E && A0G (shadow): also read MobileConfig and compare (A0C)
```

| Feld | Quelle | Bedeutung (inferred) |
|------|--------|----------------------|
| `A0F` | Pref `23048` (bool), nur `C08J` | MobileConfig für diesen Account initialisiert |
| `A0E` | `A0F` oder Pref `27668` (int) > 0 | MobileConfig aktiv (nur `C08J`; false für `C0D9`, `C0ER`) |
| `A0b` | Pref `24896` | MobileConfig ist Source of Truth |
| `A0S` | Pref `25403`, neu gelesen in `A0s()` | Override zurück auf den Legacy-Pfad |
| `A0G` | Pref `22646` | Shadow-Vergleich an |
| `A0c` | Pref `38895` == 1 | Per-Read-Cache `A0d` für MobileConfig-Werte |
| `A08` | AtomicBoolean, gesetzt in `C054709r.BN4` (MobileConfig-Init) | MobileConfig bereit; nur dann wird der MobileConfig-Pfad genommen (found); im Konstruktor auf false zurückgesetzt |

Alle sechs sind selbst AB Props und werden bei der Konstruktion direkt aus der Prefs-Datei gelesen (found). Der Shadow-Modus baut einen Vergleichsdatensatz `N25` und sendet ein Field-Stats-Event (`C56612Vl`, Wert `mobile_config_inconsistent_value`), gesampelt 1 zu Flag **22647** (Default 10) (found). Wenn MobileConfig die Quelle ist und eine ID keine Stable ID hat, liefert das typisierte Lambda `false` / `0` / `""` mit der Value-Source `INVALID_SPECIFIER_MISSING_IN_WA_LOOKUP_MAP`, nicht den Wert aus der Default-Map (found in `C34081Wt`; Wirkung auf die 70 Default-only-IDs inferred).

---

## 3. MobileConfig-Schicht

### 3.1 Stable IDs (found, `C06510El.A0J`)

`long[39141]`, indiziert nach Config Code, 21.380 Einträge ungleich null. `C054709r.B6F(id)` liefert den Eintrag (0 = keiner). 21.354 IDs existieren sowohl in den Default-Maps als auch in dieser Tabelle; 70 IDs sind nur im Default, 26 nur als Stable ID vorhanden.

| Bits | Feld | Evidenz |
|------|------|---------|
| 0-15 | Slot-Index | `C053809h.A00`: `j & 65535`; Bedeutung inferred |
| 32-47 | Config-Index, `0..20780`, einer pro Eintrag in ID-Reihenfolge | `C06460Eg.A00`: `(j >>> 32) & 65535`, `C053409d.A08(int)` |
| 48-53 | Werttyp: 1 bool, 2 int, 3 string oder JSON, 4 float | Kreuztabelle gegen die Default-Maps, keine Ausnahme |
| 54-59 | Unit-Typ: 1 SESSIONLESS (564 IDs), 2 SESSIONBASED (20.781), 6 GROUP (35) | Kreuztabelle; Abschnitt 3.2 |
| 60-63 | Wert `2` genau dann, wenn der Bool-Default `true` ist | 1.231 von 1.231 IDs; 6 IDs mit Default true haben keine Stable ID |

### 3.2 Unit-Typen und `params_map_v4_u*` (found)

`assets/params_map_v4_u<N>.txt` wird von `N3E` geladen, mit `N` = MobileConfig-Unit-Typ (`AbstractC24817AmY.A00`): 0 NULL_VALUE, 1 SESSIONLESS, 2 SESSIONBASED, 3 PAGEID, 4 ADMINID, 6 GROUP, 7 FAMILY_DEVICE_ID, 8 FRLID, 9 AD_ACCOUNT_ID, 10 WEARABLE_DEVICE_OWNER_ID. Das Suffix ist der Unit-Typ, keine Wertbreite. Die native Bibliothek trägt denselben Format-String `params_map_v4_u%d.txt` (`libmobileconfig-jni.so`).

| Datei | Unit | Einträge | Version-Key | IDs im WA-Code-Bereich |
|-------|------|----------|-------------|------------------------|
| `u1` | SESSIONLESS (vor dem Login nutzbar) | 575 | 565 | 564 |
| `u2` | SESSIONBASED | 20.844 | 20785 | 20.781 |
| `u4` | ADMINID | 72 | 2 | 0 (IDs 112607..121623) |
| `u6` | GROUP | 35 | 35 | 35 |

Eintrag (8 Bytes, zwei Little-Endian-u32, Header-Layout wie in der Datei: Magic `v4`, `0x7fff`-Check, Version-Key, Anzahl, 32-stelliger Hash):

| Feld | Befund |
|------|--------|
| `int2 >> 12` | der WA Config Code: für `u1`/`u2`/`u6` deckt er sich mit der Stable-ID-Tabelle (564 / 20.781 / 35 Treffer) und den Default-Maps; die unteren 12 Bits sind bei allen bis auf wenige Einträge 0 |
| `int1` untere 16 Bits | Werttyp-Maske: `0x881` bool, `0x1001` int, `0x1801` string/JSON, `0x2001` float (`u2`); Bit 15 ist genau bei Bool-Defaults `true` gesetzt (25 + 1.206 = 1.231) |
| `int1 >> 16` | laufende Slot-Nummer (inferred) |
| `u4`-IDs | außerhalb des WA-Code-Bereichs; Zweck unbekannt |

Die unteren 9 Bits von `int1` sind nur 1 oder 129; sie sind keine Parameter-ID.

Die 35 GROUP-IDs (found): 18205, 23245, 23246, 23397, 23398, 24075, 26013, 26269, 26270, 26862, 27009, 27025, 27247, 28357, 28358, 29275, 30905, 30906, 31456, 32501, 33673, 34075, 34277, 34333, 35211, 35227, 35639, 35772, 36156, 36504, 36505, 37523, 37524, 38082, 38083. Flag **18205** wird pro Gruppe von `GroupAbPropsManager` gelesen (Abschnitt 4.7).

### 3.3 MobileConfig-Fetch über MEX (found, `CQN`, `C29448CqB`)

MEX-Mutation `MetaConfigFetchMutation`, Schema `whatsapp-android-www`, doc_id **28207206725568030**, Root-Feld `xwa2_mobile_config_fetch`. In `CQN` gesetzte Input-Felder: `api_version`, `fetch_type`, `unit_type`, `unit_id`, `device_id`, `query_hash`, `query_string`, `bln_queries`, `mc_debug_id`, `mobile_app_universe_type`; in den gelesenen Pfaden immer null: `batch_size`, `bln_li_hashes`, `bool_opt_policy`, `contact_point`. Log: `WAMobileConfigFetcher/fetchWwwConfigs/request unit_type=...`. Response: ein Config-Blob, der an den nativen Manager übergeben wird (`onComplete(true, blob)`), plus `ep_refresh_id` und `ab_key`. `ab_key` wird als `mc_expo:sys:ab_key` gespeichert.

`C41251mA` (`MobileConfigFetchCoordinatorImpl`) entscheidet, wann dieser Fetch nach einem AB-Props-Fetch läuft: ABPropInt **36185** (Default 0) wählt die Option: Wert 2 wartet auf Offline-Resume (`waiting for offline resume`), jeder andere Wert fetcht sofort; Wert 1 prüft eine gespeicherte Fetch-Version pro Unit gegen die `abprops`-Version (`C054709r.A01`), ein Delta-Request vergleicht die App-Version des neuesten Handles mit `2.26.41.6`. `C054709r.CpO` ruft `updateConfigs` auf, Callback-Log `WAMobileConfigFetcher/updateConfigs() callback: succeeded=`; bei Erfolg wird `last_full_fetch_ms:<unit>:<key>` gespeichert.

Die `<success>`-Stanza des Logins trägt neben `props` und `abprops` auch `mc_ep_version` (Emergency-Push-Version von MobileConfig) (found, `HandlerThreadC12340b0`); Verbraucher nicht verfolgt.

---

## 4. Props-Sync

### 4.1 Request (found, `C27646BzW.A00(boolean force, boolean delta, int refreshId)`)

```xml
<iq to="s.whatsapp.net" type="get" id="..." xmlns="abt">
  <props protocol="1" hash="<stored config_hash | empty>" [refresh_id="<last_version>"]/>
</iq>
```

| Attribut | Regel |
|----------|-------|
| `protocol` | Konstante `1` |
| `hash` | gespeicherter `ab_props:sys:config_hash`; leerer String, wenn `force` oder `delta` gesetzt ist oder nichts gespeichert ist |
| `refresh_id` | nur wenn `delta` gesetzt und `refreshId > 0`; Wert = gespeicherter `ab_props:sys:last_version` |
| Senden | `MessageClient.A0W(callback, node, id, 220, 32000L)`: IQ-Request-Typ-Int 220, Timeout 32.000 ms |

### 4.2 Response (found, `C28894Cgv.CFS`)

```xml
<iq type="result"><props ab_key="..." hash="..." refresh="86400" refresh_id="N" [delta_update="true"]>
  <prop config_code="20548" config_value="1" config_expo_key="..."/>     <!-- one per changed flag -->
  <prop event_code="1094" sampling_weight="N"/>                         <!-- event sampling, no config_code -->
</props><erid>...</erid></iq>
```

| Element | Behandlung |
|---------|------------|
| `config_code` + `config_value` | typisierte Speicherung nach 2.2, Key `String.valueOf(code)` |
| `config_expo_key` | gespeichert als `<code>_expo_key`, wenn nicht leer und der Wert gespeichert wurde (Exposure-Key des Experiments / der Gruppe, in der der Account sitzt; Format des Keys unbekannt) |
| `ab_key` | gespeichert als `ab_props:sys:config_key`; als WAM-Attribut **4473** gesetzt (beide Kanäle), wenn MobileConfig nicht die Quelle ist |
| `hash` | Content-Hash des gesamten Sets; gespeichert als `ab_props:sys:config_hash`; eine Response ohne Hash und ohne `delta_update` ändert keine Werte |
| `refresh` | Sekunden, Default 86400; gespeichert x 1000 ms in `ab_props:sys:refresh`, Untergrenze 600.000 ms; wird durch ein Delta nicht aktualisiert |
| `refresh_id` | Version des Sets; gespeichert als `ab_props:sys:last_version` (auch nach einem Delta) |
| `delta_update="true"` | Merge in die bestehenden Prefs; Hash, Key, Refresh und `last_refresh_time` bleiben unangetastet |
| Hash vorhanden | vorherige Prefs werden nach `ab-props-backup` kopiert (vorher geleert) |
| Vollständiges Update (Hash vorhanden, kein Delta) | Store geleert (`refresh` und `last_exposure_keys` bleiben), alle Props geschrieben |
| `event_code` + `sampling_weight` | Zeilen ohne `config_code`; umgeschrieben in die Prefs `field-stats-events-sampling` (Key = Event-Code, Wert = Gewicht); Code **1094** setzt zusätzlich `app_launch_event_sampling_weight` |
| `<erid>` | verschlüsselte rid: bei aktivem Flag **3664** wird sie gelöscht, bei aktivem **6084** und geändertem Wert als `encrypted_rid` gespeichert |

Nach einem erfolgreichen vollständigen Update: `last_refresh_time` = jetzt (ms), `fetch_app_version` = `2.26.41.6`, Fehlerzähler zurückgesetzt, Observer benachrichtigt (4.8).

### 4.3 Trigger (found, sofern nicht anders markiert)

| Trigger | Bedingung |
|---------|-----------|
| Login `<success abprops="N">` (auch `props`, `mc_ep_version`) | Version `N` > gespeicherte `last_version`: Request mit `force` + `delta` + `refresh_id`; Modus DELTA (Log `versionMismatch`) |
| gleicher Pfad | `last_refresh_time + refresh < now`, oder `now < last_refresh_time` (Uhr zurückgestellt; Branch im Smali gelesen, der Decompile lässt den else-Zweig aus): normaler Request mit gespeichertem Hash; Modus FULL (Log `AB Props too old`) |
| eingehendes `<... abprops/>`-Child (geroutet mit den Children `log` und `push-config`; Parent `ib` inferred) | `forceFetchABPropsAndMobileConfig`: `A00(true, false, 0)` (leerer Hash, vollständig), wenn der Nachrichtenversand bereit ist; danach MobileConfig `BMu` + `CpO` |
| Registrierung | Pre-chatd-Fetch (4.6); Offline-Zuweisung (6) |

### 4.4 Refresh-Intervall und Fehler (found)

| Element | Wert |
|---------|------|
| Default-Intervall | `ab_props:sys:refresh` Default 86.400.000 ms |
| Server-`refresh` | Sekunden, x 1000, Untergrenze 600.000 ms |
| gezählte Fehlercodes | 207, 304, 400-503 (`C28894Cgv.Brt`); andere Codes loggen nur `unknown error code` |
| Retry-Buchführung | `fetch_attemp_count` +1 pro Fehler; bei 3 wird `last_refresh_time` = jetzt gesetzt und der Zähler zurückgesetzt, sodass der nächste Versuch ein Intervall wartet |
| letzter Fehler | `ab_props:sys:last_error_code`, bei Erfolg gelöscht |
| Zustellfehler (`Bog`) | No-op |

### 4.5 Reads während des Fetch-Fensters

`<props>` kann eintreffen, nachdem die ersten Screens Flags gelesen haben. Der erste Read einer ID, bevor Daten existieren, nutzt den Default; mit `firstAccessValue`-Pinning (2.3) bleibt der gepinnte Default für den Prozess bestehen (found); Registrierungs-Screens warten mit Timeout auf Online-Props (Log-Strings `RegisterPhoneViewModel/cancelOnlineAbPropsTimeout`, `OnlineAbpropsAsyncStatus`, found; genaue Wartezeit unbekannt).

### 4.6 Pre-chatd-Props (found, `C44707Jfc`, `C43414Iwr`, `K49`, `C0D2.A08`)

Bevor der Account verbunden ist, ruft der HTTP-Client der Registrierung `checkPreChatdABProps` (`reg-onboard-abprop-request`) mit `ab_hash` auf (Pref `pref_pre_chatd_ab_hash`). Das Ergebnis enthält einen neuen Hash, ein `expConfigs`-JSON-Array aus `{config_code, config_value, config_expo_key}`, einen `ab_key` und eine Verzögerung bis zum nächsten Fetch (`pref_pre_chatd_ab_next_fetch_time` = jetzt + Verzögerung). `C0D2.A08` leert den Pre-chatd-Store (`A04`) und schreibt ihn mit denselben Typisierungsregeln (2.2) in die Prefs `ab-prechatd-props` neu. Exposure wird in `pref_expo_keys` gehalten (JSON-Array aus `<expo_key>,<timestamp>`) und über das Registration-Funnel-Log gesendet (`abprop_exposure` / `ab_prechatd_exposure`, mit `ab_key` aus `pref_pre_chatd_ab_key`), nicht über WAM 5504. Pre-chatd-Reads nutzen die Optionen `A04` (urgent), wenn Flag **24317** an ist, sonst `A03`.

### 4.7 Props auf Gruppenebene (found, `C41861nA`, `C502324k`, `C28900Ch1`)

```xml
<iq to="s.whatsapp.net" type="get" xmlns="abt"><props group="<group jid>" hash="<cached | empty>"/></iq>
```

Gleicher Typ 220 und 32.000 ms wie in 4.1. Das Request-Attribut-Array hat zwei Einträge: `group` und `hash` (Smali). Gate: Flag **16206** (Master) und eine geöffnete Gruppenkonversation (`COK` / `Bnc`); übersprungen mit `reason=cacheValid` bis `_nextRefreshTimeInSeconds`, oder mit `reason=disabled`. Response: `hash`, `refresh` auf 600..604.800 s begrenzt (Default 86.400), `refresh_id`, `<prop config_code config_value config_expo_key>`, typisiert über dieselben Default-Maps (bool, int, float, sonst string). Die IDs liegen im gemeinsamen ID-Raum; der Unit-Typ GROUP (3.2) markiert die 35 dafür vorgesehenen IDs, und der Flag-Read für eine Gruppe ist `A04(groupJid, id)`. Reads liefern `null`, wenn die Gruppe keinen gespeicherten Wert hat (der Aufrufer fällt dann zurück, nicht verfolgt). Keys in den Gruppen-Prefs (`groupAbProps`, Name aus `C00E` inferred): `<jid>_<id>_value`, `<jid>_<id>_exposureKey`, `<jid>_exposureKeysSet`, `<jid>_nextRefreshTimeInSeconds`, `<jid>_lastRefreshHash`. Kein JSON-Typ für Gruppenwerte.

### 4.8 Observer (found)

`C0NE` hat drei Callbacks: `BhX` vor dem Schreiben der neuen Werte (Event 34), `Bfk` und `C2K` danach (Events 33, 32). Beispiel `CY8` (`PQKeysUploadABPropsObserver`): merkt sich Flag **21198** in `BhX`; wenn es in `Bfk` von `true` auf `false` gewechselt ist, loggt er `PQ_KEYS_UPLOAD_CODE changed from true to false, deleting all kyber prekeys` und reiht `DeleteKyberPreKeysJob` ein. 46 Klassen implementieren `C0NE` (grep-Zählung).

---

## 5. Speicherung auf dem Gerät

| Prefs-Datei / Key | Inhalt |
|-------------------|--------|
| `ab-props` (`C08J`, `C0D2.A00`) | `<id>`-Wert, `<id>_expo_key` und die unten genannten `ab_props:sys:*`-Keys |
| `ab_props:sys:config_hash`, `config_key`, `last_version`, `refresh`, `last_refresh_time`, `fetch_app_version`, `fetch_attemp_count`, `last_error_code` | Sync-Zustand |
| `ab_props:sys:last_exposure_keys` (String-Set), `last_daily_expo_key_update` | Exposure-Zustand |
| `ab_props:sys:private_experimentation_id` | Zufalls-ID für On-Device-Experimente (6) |
| `ab_offline_props:offline_exposure_strings`, `ab_offline_props:offline_exposure_hash_strings` | Exposure der Offline-Experimente (in `ab-props`) |
| `ab-props-backup` | Kopie des vorherigen Stores, bei jedem vollständigen Update neu geschrieben |
| `ab-prechatd-props` | Pre-chatd-Werte plus `pref_expo_keys` |
| `ab-private-abprop` | `last_read_time_ms` (höchstens stündlich aktualisiert) und private Werte |
| `mc_expo:sys:ab_key`, `mc_expo:sys:last_exposure_keys`, `mc_expo:sys:last_exposure_keys_without_logging` | MobileConfig-seitiger Exposure-Zustand |
| `field-stats-events-sampling` | Event-Code auf Sampling-Gewicht |
| `groupAbProps` | Gruppenwerte (4.7) |
| `<dataDir>/mobileconfig/mc_overrides.json`, `id_name_mapping.json` | MobileConfig-Override-Tabelle, ID-Namen-Map (Dateinamen in `C053409d` gefunden; im APK nicht vorhanden) |
| `pref_pre_chatd_ab_hash`, `pref_pre_chatd_ab_key`, `pref_pre_chatd_ab_next_fetch_time`, `pref_is_blocking_prechatd_exposure` | Pre-chatd-Zustand (Registrierungs-Prefs) |

Alle Dateien werden über `C00S.A05(name)` geöffnet (ein `SharedPreferences`-Handle im app-privaten Datenverzeichnis); ob diese Factory Verschlüsselung oder Obfuskierung hinzufügt, wurde nicht geprüft (unknown).

---

## 6. Exposure, Experimente, Gruppen

### 6.1 Exposure-Logging (found)

| Schritt | Detail |
|---------|--------|
| 1 | ein Read mit Exposure-Logging (2.3) ruft `A0B(options, this, "<id>_expo_key")` -> `A12` auf |
| 2 | nicht leerer Expo-Key, der noch nicht in `last_exposure_keys` steht: hinzugefügt und persistiert |
| 3 | Haupt-Store: `C42831om.A01` postet das WAM-Event **5504** `WamWefrClientExposure` (`wam_wefr_client_exposure`), debounced auf mindestens 1 s; `BxP` ruft die WAM-Runtime auf (`C0D6.CYl(value, 5029, ...)`; "Attribut" aus der Aufrufform inferred) mit den kommagetrennten Keys (Merge pro Quelle, wenn Flag **31830** an ist) |
| 4 | nach einem vollständigen Sync bleiben nur Keys im Set, die die neue Response noch trägt |
| 5 | täglicher Resend: beim Foreground-Callback `A0A0.BvR`, wenn seit `last_daily_expo_key_update` mehr als 24 h vergangen sind (`sent_with_daily` = true) |
| 6 | Pre-chatd: der `C27952CBv`-Pulse-Thread sendet das Funnel-Log (4.6); der URGENT-Modus löst es sofort aus |

WAM-5504-Felder (Falco-Namen): `dedup_key`, `device_exp_id`, `exposure_key`, `from_metaconfig`, `sent_with_daily`. `device_exp_id` ist ein String, abgeleitet vom Device-Identity-Objekt (`C09E.A0J().A03()`); Ableitung nicht verfolgt (unknown).

### 6.2 Experiment- und Gruppen-IDs

| ID | Wo | Bedeutung |
|----|----|-----------|
| `config_expo_key` | pro `<prop>` | Exposure-Key des Experiment-Arms; für den Client opak, wird nur verglichen und geloggt |
| `ab_key` | `<props>`-Attribut | Key des gesamten zugewiesenen Sets; WAM-Attribut 4473 |
| `refresh_id` | `<props>`-Attribut | Version des Sets; wird mit `abprops` aus dem Login-`<success>` verglichen |
| `hash` | `<props>`-Attribut | Content-Hash, der für "keine Änderung" genutzt wird |
| `private_experimentation_id` | lokal | Zufalls-ID, die als Unit für On-Device-Experimente dient |
| `device_id`, `unit_id` | MEX-Fetch | MobileConfig-Unit-Identität |

Serverseitiges Targeting (Land, Kohorte, Prozentsatz) ist nicht sichtbar; der Client sieht nur die resultierenden Werte (unknown).

### 6.3 Sampling-Gewichte (found)

Die Zeilen `<prop event_code sampling_weight>` speisen den Field-Stats-Logger: pro Event ein 1-zu-N-Sampling-Gewicht. Event **1094** (App-Start) wird nach `app_launch_event_sampling_weight` gespiegelt. Der Key ist ein WAM-Event-Code, keine Flag-ID.

---

## 7. Lokale Auswertung, Overrides, Debug-Pfade

### 7.1 Offline AB (found, `C24976ApB`, `C27629BzE`, `C60839RQl`)

In das APK einkompilierte Experimente (`C60839RQl.A00`, Liste aus `ON0` -> `ON1` -> `C53973OMy` -> `ConfigVariable{id, name, value, type}`) werden gegen eine lokale User-Info-Map ausgewertet und mit denselben Typisierungsregeln in den `ab-props`-Store geschrieben. Bedingungen (`RM2`-Baum) dürfen nur die Properties `platform`, `app_version`, `app_build`, `release_channel`, `os_version` verwenden (`C0ER.A0B`). User-Info-Keys: `device_id`, `app_build`, `release_channel`, `app_version`, `os_version`, `platform`, `country` (SIM-Land), `private_experimentation_id`. In dieser Beta sind `app_build` und `release_channel` die Konstante `beta`. Bei einer Zuweisung werden die Sync-Keys (`config_hash`, `last_refresh_time`, `fetch_app_version`, `last_version`) entfernt, damit der nächste Online-Fetch vollständig ist, und ein kritisches Log `abprops-offline-assigned-after-registration-verified` feuert, wenn die Zuweisung bei `registration_state == 3` erfolgt. Die Experiment-Definitionen werden hier nicht aufgezählt (unknown).

### 7.2 MobileConfig-Overrides (found, Wirkung inferred)

`C053809h` lädt `mc_overrides.json` (`hasOverridesFile`, `boolOverrideForParam`, `intOverrideForParam`, `stringOverrideForParam`, `doubleOverrideForParam`, Key ist die gepackte 64-Bit-Stable-ID), `C053409d.getOrCreateOverridesTable` gibt sie an die Engine zurück. Overrides gelten nur für den MobileConfig-Pfad, nicht für den Legacy-Prefs-Pfad. Ob die Engine die Tabelle in einem Release-Build befragt, ist unbekannt; es gibt keinen Hinweis auf einen Laufzeittest.

### 7.3 `override-abprops`-Deep-Link (found)

Manifest-Host `whatsapp-consumer://override-abprops` (exportierter `DeepLinkActivity`-Alias). `IJB` bildet ihn auf die Destination-ID 154 ab. `DeepLinkActivity.A0w` parst das Pfadsegment `bugbash` und die Query-Parameter `feature_name`, `feature_id`, `category`, `min_app_version`, `ready_to_test_time` und `variants` (Base64-JSON-Array aus `{label, abprops:[{abprop_key, abprop_value}]}`) zu `BugBashSession` / `BugBashVariant`. Ein Fehlergrund `abprop_override_not_allowed` existiert. Es wurde kein Code gefunden, der `abprop_key` / `abprop_value` in einen Prop-Store schreibt: `BugBashVariant` wird nur vom Parser und seinem Serializer referenziert, und `bugbash_session` wird nur gelesen (`C51723Mxj`). Gate-Bedingung und Apply-Pfad sind unbekannt.

### 7.4 Sonstiges

| Pfad | Detail |
|------|--------|
| ABPropBoolean `debugDefaultValue` | deklariert (182 weichen ab), nie gelesen (2.1) |
| Debug-UI | `com.whatsapp.backup.debugscreen.BackupAbPropsUiState` (nur Klassenname, Backup-Debug-Screen) |
| Per-Read-Profiler | Prefs `31165` (int) und `32010` (bool) speisen `C00D.A0H/A0I/A0J` und eine Zählerklasse (`Pr8`); Zweck nicht aufgelöst |

---

## 8. In anderen Reports zitierte Flag-IDs (verifiziert in 2.26.41.6)

Jede ID wurde in den Default-Maps und der Stable-ID-Tabelle nachgeschlagen. Typen sind die Map-Typen.

| Report | Ergebnis |
|--------|----------|
| `WA_BAN_SYSTEM_DEEP_EN.md` | 11061, 11064, 11065 (int 86400), 12709, 16349, 19793, 19893, 26697, 27269, 14837, 25631 vorhanden, bool Default false; 12840 und 20278 sind **JSON**-Maps (Defaults stimmen überein); 31535 / 31536 sind **float**, Default 0.0. **34166 ist kein Flag**: kein Default, keine Stable ID; `ContactInfoActivity.A0K = C1XG.A0I(34166)` ist eine Injection-ID (die Nachbarn 34165, 34168, 34169 sind von derselben Art). 2923 fehlt (wie berichtet) |
| `WA_TCTOKEN_CSTOKEN.md` | alle 16 IDs vorhanden; Defaults: 996 / 865 / 26897 = 604800, 997 / 909 = 4, 3802 / 22012 = 26, 4063 = 0, 20606 = 2000, alle Bool-IDs false. `299` ist der IQ-Request-Typ-Int der Privacy-Token-IQ, kein Flag |
| `WA_META_AI.md` | 25119, 26189, 27083, 37227, 37852, 37054 bool false; **26190 ist JSON**, Default `""` |
| `WA_USERNAME.md` | alle 18 vorhanden mit den dokumentierten Defaults; **34350 ist ein String-Map-Eintrag** (Regex), **21995 ein JSON-Map-Eintrag** |
| `WA_USYNC.md` | alle 21 Flag-IDs vorhanden mit den dokumentierten Defaults (730 = 35, 471 = 1140, 9667 / 33609 / 20988 = true) |

Derselbe Code-Raum taucht auf WA Web auf: Für 11 aus der öffentlichen WA-Web-Prop-Tabelle bekannte Prop-Namen hat der Android-Eintrag denselben Code, Typ und Default (z. B. 22797 JSON `{}`, 32276 string `info_card, list_card`, 26270 int 1209600, 35639 int -1, 12539 bool true, 25071 / 1133 / 23245 / 28357 / 27009 / 6939 bool false) (found für die Android-Seite, inferred für "gleiches Prop"). Web-only-IDs (3042, 30590, 24037, 25322) haben keinen Android-Default. 12 der 16 Web-Gruppenebenen-IDs sind die Android-GROUP-Unit-IDs (3.2).

---

## 9. Benennung und Kategorien

| Thema | Befund |
|-------|--------|
| Namen | keine lesbare Namenstabelle in dex oder assets gefunden (eine Suche nach zwei bekannten Legacy-Flag-Namen traf nur Log-Strings); `id_name_mapping.json` ist nur ein Laufzeit-Dateiname in `C053409d` |
| Namen in Logs | einige Log-Strings verwenden Namen wieder: `PQ_KEYS_UPLOAD_CODE` (21198), `abprop_override_not_allowed`; Namen aus älteren Builds oder von WA Web sind der einzige Weg zur Semantik |
| Kategorien | kein Kategorie-Feld. Struktur ergibt sich aus Unit-Typ (SESSIONLESS 564, SESSIONBASED 20.781, GROUP 35) und Werttyp |
| Am häufigsten gelesen | die am häufigsten gelesenen Literal-IDs: **20548** (bool true, 511 Stellen), **9970** (false, 312), **1107** (false, 151), **12267** (true, 147), **1600** (string `{"allowed_product_type":"none"}`, 146), **27008** (false, 104), **13989** (int 7, 87). Semantik ungelöst |

---

## 10. Flag-Katalog nach Bereichen (Defaults in `C08J` gefunden; Verwendung aus den anderen Reports übernommen und hier erneut geprüft)

### 10.1 Sync- und MobileConfig-Infrastruktur

| Flag | Typ | Default | Steuert |
|------|-----|---------|---------|
| **23048** | bool | false | MobileConfig initialisiert (`A0F`) |
| **27668** | int | 0 | `AbstractC06100Cm.A0E`; > 0 aktiviert MobileConfig (`A0E`) |
| **24896** | bool | false | MobileConfig ist Source of Truth (inferred) |
| **25403** | bool | false | zurück zur Legacy-Quelle (inferred) |
| **22646** | bool | false | Shadow-Vergleich |
| **22647** | int | 10 | Shadow-Log-Sampling |
| **38895** | int | 0 | `== 1`: Per-Read-MobileConfig-Cache |
| **26524**, **28443**, **30441**, **30556** | bool | false | MobileConfig-Factory-Optionen (`CbW`, `BMu`) |
| **26525** | int | 600 | MobileConfig-Factory-Option (`CbW`), Einheit ungelöst |
| **26640** | bool | false | MobileConfig-Init-Parameter (`BN4`) |
| **35778** / **36185** | int | 0 | Init-Phase / Fetch-Timing-Option (`C054709r.APn`, `C41251mA.A00`) |
| **24317** | bool (SESSIONLESS) | false | Pre-chatd-Reads nutzen Urgent-Exposure |
| **31830** | bool | false | Merge pro Quelle des Exposure-Attributs 5029 |
| **16206** | bool | false | Master-Gate der Gruppen-Props |
| **18205** | bool (GROUP) | false | Per-Gruppe-Read in `GroupAbPropsManager` |
| **3664** / **6084** | bool | false | `encrypted_rid` löschen / setzen |
| **21198** | bool | false | `PQ_KEYS_UPLOAD`: Kyber-Prekey-Upload; `true` auf `false` löscht sie |

### 10.2 Ban und Integrität (`WA_BAN_SYSTEM_DEEP_EN.md`)

11061, 11064, 11065 (int 86400), 12709, 16349, 19793, 19893, 26697, 27269, 14837, 25631 (bool false); 12840 (JSON `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}`); 20278 (JSON `{"max_messages": 10000, "farthest_time_days": 30}`); 31535 / 31536 (float 0.0).

### 10.3 Privacy-Token und cstoken (`WA_TCTOKEN_CSTOKEN.md`)

| Flag | Typ | Default |
|------|-----|---------|
| **996** / **997** | int | 604800 / 4 |
| **865** / **909** | int | 604800 / 4 |
| **4063** | int | 0 |
| **3802** / **22012** | int | 26 / 26 |
| **20605** / **14303** / **15491** | bool | false |
| **20606** | int | 2000 |
| **24915** / **24941** / **18639** / **25253** | bool | false |
| **26897** | int | 604800 |

### 10.4 Meta AI, Username, USync

| Report | Flags (Default) |
|--------|-----------------|
| `WA_META_AI.md` | **26189**, **27083**, **25119** (kein Reader), **37227**, **37852**, **37054**: bool false; **26190** JSON `""` |
| `WA_USERNAME.md` | **4745**, **20189**, **23817**, **21199**, **16033**, **8421**, **12402**, **28678**: bool false; **21995** JSON `{}`; **20494** 3, **20459** 35, **34347** 4, **34348** 6, **28127** 30, **29327** 60; **34350** string `^([0-9]{4}\|[A-Z0-9]{6})$` |
| `WA_USYNC.md` | **5751**, **5839**, **20798**, **29769**-**29771**, **9732**, **33432**, **14565**, **26739**, **31261**: bool false; **9667**, **33609**, **20988**: true; **730** 35, **471** 1140, **37780** 0 |

### 10.5 Gruppenebene (Unit GROUP, 35 IDs)

Bool false: 18205, 23245, 23246, 26013, 26269, 26862, 27009, 27025, 28357, 28358, 29275, 30905, 30906, 31456, 32501, 34075, 35211, 35772, 36156, 36504, 36505, 38082, 38083. Int: 26270 (1209600 s = 14 Tage), 27247 (0), 23397 / 23398 / 24075 / 34277 / 34333 / 35227 / 35639 / 37523 / 37524 (-1). String: 33673 (`none`). Namen für 26270, 23245, 23246, 26269, 30905, 30906, 28357, 28358, 27009, 27025, 35639, 35772 stammen von WA Web (Gruppenverlauf und Umfrage-Einstellungen; inferred).

---

## 11. Baileys (`baron-baileys-v2`, `src/Socket/chats.js`)

| Thema | Baileys | Android 2.26.41.6 |
|-------|---------|-------------------|
| User-Request | `fetchABProps(protocol='1', hash, refreshId)`: `<props protocol hash? refresh_id?>` in `xmlns="abt"` | gleiche Form; `hash` immer vorhanden (leer bei Force), `refresh_id` nur mit Delta |
| Gruppen-Request | nur `{ group }` | `group` + `hash` (Smali-Array mit 2 Einträgen) |
| Response-Keys | `reduceBinaryNodeToDictionary(props, 'prop')`: Dictionary `config_code` -> `config_value` | typisierter Store; `config_expo_key`, `event_code`-Zeilen, `hash`, `refresh`, `refresh_id`, `delta_update` werden alle verwendet |
| Lookup | nach Flag-Name (`abProps['stella_interop_enabled']`) | nur nach numerischem Code |
| Legacy-Props | `fetchProps`: `xmlns="w"` `<props protocol="2" hash>` benannte Props | kein Builder gefunden; Namen tauchen nur im Stanza-Token-Wörterbuch auf (`AbstractC40911lb`) |
| Refresh | keiner (einmal pro Verbindung) | Intervall + Versionsprüfung + Push |

| Symptom | Ursache | Fix |
|---------|---------|-----|
| `abProps['<name>']` ist `undefined` | die `abt`-Response trägt nur `config_code` | nach Code indizieren; der Code-Raum ist der aus Abschnitt 8 |
| ein Key `undefined` erscheint im Dictionary | `event_code`- / `sampling_weight`-Zeilen haben keinen `config_code` | Zeilen ohne `config_code` überspringen |
| veraltete Werte | keine Behandlung von hash / refresh / `refresh_id`, kein Delta | `hash`, `refresh`, `refresh_id` speichern; `hash` und `refresh_id` im nächsten Request senden |
| Bool wird als truthy String gelesen | `config_value` ist `"1"` / `"0"` | nach Typ parsen (`!= 0`) |

---

## 12. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|---------|-----|
| `ABPropsManager/onABPropError; unknown error code: N` | Fehler außerhalb von 207 / 304 / 400-503 | keiner; Zähler wird nicht erhöht |
| 3 fehlgeschlagene Fetches, einen Tag lang kein Retry | `fetch_attemp_count` hat 3 erreicht, `last_refresh_time` = jetzt | ein Intervall warten oder eine Erhöhung der Login-`abprops`-Version |
| `AbPropProtocolHelper/onReceiveABProps failed to parse response` (`C49828Lvo`) | fehlerhaftes `<props>` | Exception wird erneut geworfen, Store unangetastet |
| `ABPropsManager/invalid format for config; configCode=N; value=V` | nicht numerischer int/float oder ungültiges JSON | dieses Prop wird übersprungen |
| `IllegalArgumentException: Unknown BooleanField: N` | typisierter Read einer ID ohne Map-Default und ohne Deskriptor-Default | Default ergänzen; `N` ist ein Config Code |
| MobileConfig-Read liefert `false` / `0` / `""` | ID hat keine Stable ID (`INVALID_SPECIFIER_MISSING_IN_WA_LOOKUP_MAP`) | über den Legacy-Pfad lesen |
| `WAMCEvaluation/invalid json format; key=N` | JSON-Flag-Wert auf dem MobileConfig-Pfad nicht parsebar | leeres `JSONObject` wird zurückgegeben |
| `GroupAbPropsClient/malformedResponse ... noPropsChild` / `parseFailed` | Gruppen-Response ohne `<props>` oder fehlerhaftes Parsing | kein Gruppenwert gespeichert |
| `GroupAbProps/fetchSkip reason=cacheValid` / `disabled` | vor `_nextRefreshTimeInSeconds` / Flag 16206 aus | keiner |
| `ABPreChatdProps/exception ... error add expo key` | beschädigtes `pref_expo_keys`-JSON | Key nicht hinzugefügt |

---

## 13. Wichtige Unterscheidungen

| Nicht verwechseln | Detail |
|-------------------|--------|
| Config Code vs. Injection-ID | `A15(20548)` ist ein Flag; `C05Z.A00(66)`, `C1XG.A0I(34166)`, `C00C.A02(61)` sind Dependency-IDs |
| Config Code vs. IQ-Request-Typ | `A0W(..., 220, 32000L)` (220 hier, 299 in der Privacy-Token-IQ) ist ein Request-Typ-Int |
| Config Code vs. WAM-IDs | 5504 ist ein Event, 5029 und 4473 sind WAM-Attribute, 1094 ist ein Event-Code in den Sampling-Zeilen |
| Config Code vs. Stable ID | der Code (<= 39140) indiziert die Tabelle; die Stable ID ist ein 64-Bit-MobileConfig-Specifier |
| `abt`-IQ vs. `w`-Props vs. DB-Tabelle `props` | `abt` = numerische AB Props; Legacy-`w`-Props = benannte Server-Props; die SQL-Tabelle `props` = lokaler Key-Value-Store |
| User-Props vs. Gruppen-Props | gleicher ID-Raum, gleiche Maps; Gruppenwerte liegen in `groupAbProps`, Key ist die Gruppen-JID, Unit GROUP |
| `ab_key` vs. `config_expo_key` vs. `hash` vs. `refresh_id` | Key des Sets / Experiment-Key pro Prop / Content-Hash / Version |
| Login-`abprops` vs. `<props refresh_id>` | aktuelle Version des Servers vs. die aus der letzten Antwort gespeicherte Version |
| MEX `MetaConfigFetchMutation` vs. `abt` | MobileConfig-Blob vs. numerische Legacy-Props; beide laufen, wenn MobileConfig aktiv ist |
| Produktions-Default vs. Debug-Default | nur der Produktions-Default wird gelesen |
| First-Access-Pinning vs. normaler Cache | gepinnte Werte überleben Syncs bis zum Prozessende |
| Offline-Zuweisung vs. online | Offline-Experimente schreiben in denselben Store und erzwingen dann einen vollständigen Online-Fetch |

---

## 14. Kompletter Ablauf

```
[Server]            [Login]                 [C0D2 / C27646BzW]               [C08J reads]         [WAM]
   │ <success abprops=N props mc_ep_version>   │                                   │                 │
   ├──────────────────►│ N > last_version? or  │                                   │                 │
   │                   │ last_refresh+refresh<now                                  │                 │
   │                   ├──────────────────────►│ <iq xmlns=abt>                    │                 │
   │◄───────────────────────────────────────── │  <props protocol=1 hash [refresh_id]>             │
   │ <props ab_key hash refresh refresh_id [delta_update]>                          │                 │
   │   <prop config_code config_value config_expo_key/> ... <prop event_code sampling_weight/>      │
   ├──────────────────────────────────────────►│ typed store per id (bool/int/float/string/JSON)   │
   │                                           │ backup, hash, refresh, last_version, ab_key       │
   │                                           ├─ observers BhX ► write ► Bfk / C2K ──────────────►│
   │                                           │ A0s(): clear read cache                           │
   │                                           │                                   │                 │
   │ <ib><abprops/>  (force, empty hash) ─────►│                                   │                 │
   │                                           │                                   │                 │
   │                                      A15(id) / A0b(id) / A0j(id)...           │                 │
   │                                           │          cache ► prefs ► default map ► (descriptor)│
   │                                           │          MobileConfig path if A0E && A0b && !A0S   │
   │                                           │                                   ├ first read ────►│ 5504 exposure
   │                                           │                                   │ + 24 h resend   │ 5029, 4473
   │                                           │                                   │                 │
   │ MEX MetaConfigFetchMutation ◄─────────────┼── C41251mA (option 36185) ────────┤                 │
   │ xwa2_mobile_config_fetch {blob, ep_refresh_id, ab_key} ───► native MobileConfig, Stable IDs    │
   │                                           │                                   │                 │
   │ <iq xmlns=abt><props group hash> (group opened, flag 16206) ► groupAbProps ► A04(groupJid,id)   │
```

---

## 15. Unbekanntes

| Thema | Grund |
|-------|-------|
| Flag-Semantik | keine Namen; Semantik nur dort, wo eine Call-Site oder ein anderer Report sie auflöst |
| Serverseitige Zuweisung | Targeting, Rollout-Prozentsätze, Experiment-Definitionen sind nicht im Client |
| Parent-Stanza des `abprops`-Push-Childs | Handler unter Message-Code 235 registriert; `ib` inferred |
| Verbindung zwischen Login-`abprops` und dem Versionsargument des Triggers | der Trigger nimmt ein `Integer`; das Login-Parsing setzt eine `AtomicReference`; Verbindung inferred |
| MobileConfig `mc_overrides.json` in Release-Builds | Tabellen-Code existiert; kein Hinweis, dass sie befragt oder vom App-Nutzer beschreibbar ist |
| Gate und Apply-Pfad von `override-abprops` | Grund `abprop_override_not_allowed` existiert; kein Writer in einen Prop-Store gefunden |
| Ableitung von `device_exp_id`, Format von `config_expo_key` | nicht verfolgt |
| Stable-ID-Bits 0-15, `u4`-Unit-Einträge, `int1 >> 16` | Bedeutung nicht aufgelöst |
| Prefs `31165`, `32010`, Flag `35778`, `36185` Werte 1 / 2 | teilweise gelesen (`Pr8`, Koordinator) |
| Verhalten der 70 Default-only-IDs unter MobileConfig | typisiertes Lambda liefert Nullwerte (found); Wirkung auf Features nicht verfolgt |
| Delta-Semantik serverseitig | welche Props ein Delta trägt |
| Tatsächlicher Traffic und live ausgelieferte Werte | nur statische Analyse |
