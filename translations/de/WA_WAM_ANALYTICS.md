<!-- src-sha1: c6955a2c041a57de36c902dfa247b0b65dc0b530 -->
# WhatsApp WAM Analytics — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** Android-WAM-Telemetrie ("WhatsApp Metrics") — Event-Modell (Event-IDs, Felder, Kanäle REGULAR / REALTIME / PRIVATE / Kanal 3), Java-Logging-Pipeline, Sampling und Gewichte pro Event, nativer Runtime (`libwhatsapp.so`), Common Attributes, Buffer auf dem Datenträger, WAM-Wire-Format, regulärer Upload (`w:stats` IQ), privater Upload (Credential-IQ + separater Transport), `wam_daily` und der tägliche Cron, Private-Stats-IDs und Rotation, Datenschutzbehandlung, Feature-Flags, wichtige Event-Familien, Baileys-Vergleich, was unbekannt bleibt

---

## 1. Was WAM in diesem Build ist

WAM ist eine clientseitige Metrik-Pipeline: Typisierte Events werden in Java erzeugt (oder aus nativen Call-Stats konvertiert), gesampelt, an einen nativen Runtime übergeben, der sie in Binärbuffer unter `files/wam/` serialisiert, und zum Server hochgeladen. Es ist ausschließlich ausgehende Telemetrie. Nichts im Chat-Protokoll hängt davon ab. Alle Aussagen sind statische Analyse des dekompilierten APK (`versionCode 264100600`) sowie der nativen Strings von `libwhatsapp.so` und des Layouts von Bufferdateien aus einem App-Datenverzeichnis dieses Builds. Tiers: **found** = in Code oder in einer Bufferdatei gelesen, **inferred** = abgeleitet, **unknown** = statisch nicht auflösbar. Obfuskierte Namen gelten pro Build und wurden in 2.26.41.6 anhand stabiler Strings neu aufgelöst (Log-Strings, `wam_*`-Eventnamen, IQ-Attributwerte).

| Entität | Name in 2.26.41.6 | Rolle |
|---------|-------------------|-------|
| Event-Basisklasse | `C0Fc` | `code`, `samplingRate`, `bufferChannel`, `psId`; abstrakt `getFieldsMap()` (numerische IDs), `getFieldsMapForFalco()` (Namen), `getEventNameForFalco()`, `validate()` |
| Sampling-Tupel | `C036300x` | Gewichtsstufen; `A00` ist das vom Sampler verwendete Gewicht |
| Sampling-Resolver | `C0Fg` + `C06580Fh` | Gewichts-Override pro Event aus den Prefs `field-stats-events-sampling` |
| Logger (WAM-Runtime-Fassade) | `C06650Fo` (`InterfaceC06640Fn`); `C40098Hdb` verteilt an ihn und an den Java-Falco-Logger `C40099Hdc` | `CNW` Post, `CNI` Post mit Sampling, `CXW` Flush, `CUj` Reset, `CXZ` Flush und Warten (2500 ms); Init in `RunnableC29323CoA` case 33 |
| JNI-Bridge | `com.whatsapp.wamsys.JniBridge` | `jvidispatch*` Java zu nativ, `jnidispatch*` nativ zu Java |
| Common Attributes | `C06590Fi` (`CYl(value, attrId, channel)`), Init in `RunnableC29340CoR` case 0 | globale Attribute pro Kanal |
| AB-Props-Handler | `C28894Cgv` | parst `<props>` inkl. `event_code` / `sampling_weight` |
| Daily-Event | `C0Fp` (`wam_daily`, id 1158) | Geräte- und App-Zustand |
| Daily-Cron | `C28643Ccj` (`WamDailyEventDailyCron`), Alarm in `BEL` (`DailyCronAction`) | baut und postet `C0Fp` |
| Call-Event | `com.whatsapp.fieldstats.events.WamCall` (id 462) | aus nativen Call-Stats erzeugt, gepostet von `C24895Anr` |
| Nativer Runtime | `libwhatsapp.so` (`WAMRuntime`, `WAMBufferStore`, `WAMTransportRegular`, `WAMTransportPrivate`, `WAMPSIDProfile`) | Buffer, IDs, Uploads |

Nicht WAM, nicht verwechseln (siehe 17): der Java-seitige Falco-Shadow-Logger (`C40099Hdc`, `FFLogger`), der Crash- und Log-Uploader mit dem Tag `wam-event/<name>`, ACS-Tokens für andere Projekte und das Wort `fieldstats`, das von nativen Call-Stats verwendet wird (`prepare_wa_call_fieldstats`).

Client-Integritätssignale, die innerhalb von WAM übertragen werden (`is_rooted`, `is_genymotion`, `is_whatsapp_plus_user`, Attribute 6251 und 10255), sind in [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) beschrieben und werden hier nur referenziert.

---

## 2. Event-Modell

### 2.1 Event-Klasse (`C0Fc`)

Jedes Event ist eine generierte Klasse; der Konstruktor ist `super(code, samplingTuple, bufferChannel, psId)`, z. B. `wam_daily`: `super(1158, new C036300x(1, 1, 1, false), 0, -1)`, `getEventNameForFalco() = "wam_daily"`, `internalFalcoMigrationBatchNumber() = 12`.

| Member | Bedeutung | Tier |
|--------|-----------|------|
| `code` | numerische Event-ID (1158 für `wam_daily`, 460 `wam_login`, 462 `wam_call`, 854 `wam_message_send`) | found |
| `samplingRate` | `C036300x(a, b, c, flag)` wird als `A02=a, A01=b, A00=b, A03=c` gespeichert; der Sampler verwendet `A00 = b`. Default `C0Fc.DEFAULT_SAMPLING_RATE = (1, 20, 20)` | found |
| `bufferChannel` | 0..3, siehe 2.2 | found |
| `psId` | `-1` = nicht privat; sonst ein Private-Stats-Key-Hash, siehe 2.3 | found |
| `getFieldsMap()` / `getFieldsMapForFalco()` | numerische Feld-ID auf Wert (an nativ übergeben) / snake_case-Name auf Wert | found |
| `validate()` | Liste von Verstößen (`.nonnull` und ähnliche Regeln), siehe 3.2 | found |
| `serialize(C3T8)` | Body ist `throw new NullPointerException("serialize")`; die Serialisierung ist nativ | found |

Felder verwenden Java-Boxed-Typen (`Boolean`, `Integer`, `Long`, `Double`, `String`). Enums und Timer werden als Integer übertragen (inferred aus dem Attribut-Setter, der nur null / String / Integer / Long / Double / Boolean akzeptiert). `wam_daily` hat 218 numerische Slots und 205 benannte Slots (13 numerische Slots sind nur null), identisch mit der früheren Zählung in 2.26.35.8.

### 2.2 Kanäle

| `bufferChannel` | Events (geparst) | Name (Labels inferred; Java verwendet einfache ints) | Tier |
|-----------------|------------------|------|------|
| 0 | 824 | REGULAR | found |
| 1 | 8 | REALTIME | found |
| 2 | 168 | PRIVATE (benötigt eine Private-Stats-ID, siehe 2.3) | found |
| 3 | 8 | anonymes Realtime-Private-Stats, "RTPS" in nativen Log-Strings (Label inferred) | found / inferred |

Insgesamt geparst: 1.008 Event-Klassen mit unterschiedlichen IDs. Die Zuordnung wird unverändert an nativ übergeben (`jvidispatchIIIIIOO` Kanalargument 0..3). Jeder andere Wert wirft `IllegalArgumentException("Unsupported channel type")`.

REALTIME-Events (IDs): 2098 `wam_ui_action_real_time`, 5504 `wam_wefr_client_exposure`, 5278 `wam_android_test_realtime`, 6640 `wam_wefr_group_client_exposure`, 6088 `wam_restore_contacts_realtime_event`, 4290 `wam_wa_fs_chat_transfer`, 2872 `wam_xplatform_migration_export`, 6266 `wam_cac_client_event` (found).

Kanal-3-Events: 5164 `wam_wam_test_anonymous_realtime`, 7312 `wam_mm_signal_undisclosed`, 7352 `wam_mm_signal_realtime`, 6160 `wam_wamo_video_event`, 6158 `wam_wamo_ctwa_1pd_conversion`, 7956 `wam_wamo_promo_pog_impression`, 5712 `wam_wamo_promo_reporting_events`, 7350 `wam_wamo_alv2_link_click` (found). `C06650Fo.A01` verwirft ein Kanal-3-Event, sofern sein Code nicht in zwei hartcodierten Arrays steht (`AbstractC38512Gog.A00` 3 IDs, `A01` 5 IDs). Diese 8 IDs sind exakt die 8 Kanal-3-Events, sodass die Prüfung in diesem Build nichts verwirft (inferred aus den ID-Mengen).

### 2.3 Private-Stats-IDs (`psId`)

| `psId` (int) | Key-String in der nativen Profildatei | Rotation (Tage) | Events | Tier |
|--------------|---------------------------------------|-----------------|--------|------|
| `-1` | keiner (nicht privat) | – | 832 (regular + realtime) | found |
| `0` | `none` (Buffer-Global 6005 enthält den String `none`) | – | 94 (86 privat + 8 Kanal 3) | found; Zuordnung "none" inferred |
| `113760892` | `default_ps_id` | nie (`-1`) | 66 | found |
| `56300709` | `id_pre_metrics` | nie (`-1`) | 1 (`wam_ps_app_launch`) | found |
| `248614979` | `id_ttl_daily` | 1 | 4 | found |
| `42196056` / `191000728` | `id_ttl_weekly` / `id_ttl_monthly` | 7 / 30 | 0 | found |
| `37887164` | `id_ttl_90_days` | 90 | 1 (`wam_clock_skew_difference_t`) | found |
| `152546501` | `group_exit_experience_id` | 30 | 4 | found |
| `216763284` | `group_safety_check_id` | 30 | 6 | found |

Key-Strings und Rotationstage wurden aus den acht `WAMMetadataPSIDProfile-*`-Dateien gelesen (siehe 6.3), die Event-Zahlen aus den Event-Klassen.

### 2.4 Gewichte über den Katalog

Effektives Schema-Gewicht `A00` pro Event (das Event wird mit Wahrscheinlichkeit 1/Gewicht behalten und das Gewicht wird mit dem Event gespeichert):

| Gewicht | Events | Typische Vertreter |
|---------|--------|--------------------|
| 1 (immer) | 826 | `wam_daily`, `wam_registration_complete`, `wam_blocking_funnel` |
| 5 / 10 | 6 / 12 | `wam_message_send` (5), `wam_message_context_menu_actions` (10), `wam_ui_action_real_time` (10) |
| 20 | 135 | `wam_message_delete_actions`, `wam_message_high_retry_count`, alle Events mit `DEFAULT_SAMPLING_RATE` (81) |
| 100 / 200 | 4 / 2 | `wam_login_stage_reliability` (100) |
| 1000 | 17 | `wam_message_stanza_receive`, `wam_call_stanza_receive`, `wam_status_stanza_receive`, `wam_iq_send`, `wam_push_latency`, `wam_db_perf` |
| 10000 | 4 | `wam_receipt_stanza_receive`, `wam_android_profilo_usage`, `wam_android_message_target_perf`, `wam_notification_highlight_result` |

Das Gewicht ist kein Feature-Schalter: Der Server kann es pro Event überschreiben (8.2). Ein Event mit build-konstantem Gewicht wurde nicht eingeordnet.

---

## 3. Java-Logging-Pipeline

### 3.1 Post-Pfad

`CNW` = `CNI(event, null, false)`: Gewicht auflösen (8.1), die Kanal-3-Allowlist (`A01`) ausführen, dann das Runnable `X.1Fc` auf dem WAM-Executor (`C06600Fj.A01`) ausführen:

| Schritt | Verhalten | Tier |
|---------|-----------|------|
| Runtime-Latch | `C06650Fo.A0K` (`CountDownLatch`) blockiert den Executor, bis die Common Attributes initialisiert sind ("wamruntime/initializeCommonAttributes: runtime initialized") | found |
| Validierung | `event.validate()` läuft nur für die Kanäle 0 und 1 (nicht für die Validierungs-Event-Klasse `C40251kT`). Jeder Verstoß wird zu einem `wam_wam_validation_error_event` (id 5560) mit dem Event-Code des betroffenen Events, einem zufälligen Session-Wert und mit `;` verbundenen Regelteilen | found |
| Logger-Modi (`A04`) | `3`: schreibt für Codes in einer konfigurierten Menge `traceIdInt` (zufällig, 64 Bit) per Reflection ins Event; `10`: schreibt für Events, die `C06630Fm` passieren (Falco-Migrationsbatch 1..16, nicht auf einer Deny-Liste), `dedupKey` (zufällig, 64 Bit); `1` / `3`: posten zusätzlich ein Falco-Event (`_test$<name>` / `<name>_shadow`) | found |
| Dispatch | `jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fieldsMap)`, nachdem sichergestellt wurde, dass die Bibliothek geladen ist | found |
| Log-Upload-Trigger | AB-String-Prop **31314** enthält `"code:N;code:M"`; wenn `Random.nextInt(N)==0` für den gepostetem Code, wird der Crash- und Log-Reporter aufgefordert, Geräte-Logs mit dem Tag `wam-event/<falco name>` hochzuladen. Das lädt Logs hoch, nicht den WAM-Buffer | found |

`dedup_key` und `trace_id_int` sind Felder des Event-Schemas (vorhanden in `wam_login`, `wam_app_launch`, `wam_message_send`); sie sind pro Event zufällig und keine Nutzerkennungen (inferred aus dem Generator).

### 3.2 Validierungsregeln

In `C0Fp` (`wam_daily`) wird das Feld `ai_widget_installed` immer als Verstoß gemeldet, weil kein Java-Member es abdeckt (Regel `daily .nonnull`), und `default_after_read_enabled`, wenn sein Member null ist. Folge (inferred): Jedes Daily-Event auf Kanal 0 erzeugt auch Validierungs-Events (id 5560).

### 3.3 Flush- und Lifecycle-Trigger

| Trigger | Aufruf | Native Op | Tier |
|---------|--------|-----------|------|
| Connection-Handler verbunden | `C0A4.BvO` -> `CKt(0)` | `jvidispatchIIO(4, 0, ctx)` | found |
| Verbindet / getrennt | `BvP`, `BvQ` -> `CKt(1)` | `jvidispatchIIO(4, 1, ctx)` | found |
| Offline-Nachrichtenverarbeitung abgeschlossen (`XmppStateManager/offlineProcessComplete`, löscht auch `C0A2.A07`) | `BvR` -> `CXW(false)` nur bei AB-Prop **9654** | `jvidispatchIO(10, ctx)` (aktive Buffer flushen) | found |
| Expliziter Flush | `Bba()` -> `CXW(true)`; `CXZ()` flusht und wartet bis zu 2500 ms | `jvidispatchIO(10, ctx)` | found |
| Anrufende | `C24895Anr.A02` postet `WamCall`, dann `Bba()`, wenn der Anruf markiert ist oder AB-Prop **16047** | Flush | found |
| Neuregistrierung / Kontoentfernung | `C25100xS` ("RegistrationManager/reregister/rm-me") -> `CUj()` | `jvidispatchIO(12, ctx)` ("wamruntime/resetruntime") | found |

Das State-Argument 0/1 ist der XMPP-Verbindungszustand, der in die nativen Transports gespiegelt wird (Log-String "wameta/transport/status - %d"). Die Bedeutung 0 = verbunden wird aus dem Callback-Mapping gelesen, nicht aus nativem Code (inferred). `C0A2.A04`-Zustände: 1 verbindet, 2 verbunden, 3 getrennt, 4 gestoppt; `A07` ist ab dem Verbinden wahr, bis die Offline-Verarbeitung abgeschlossen ist, sodass `A0N()` "verbunden und leert noch Offline-Nachrichten" bedeutet.

### 3.4 JNI-Oberfläche

| Richtung | Signatur | Zweck | Tier |
|----------|----------|-------|------|
| Java zu nativ | `jvidispatchIOOOO(0, path, networkSession, ctx, config)` | Runtime initialisieren (Log "WAJContextInitWAMRuntime"), siehe 4 | found |
| Java zu nativ | `jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fields)` | Event loggen | found |
| Java zu nativ | `jvidispatchIIIOO(0, channel, attrId, String, ctx)` / `jvidispatchIIIO(4, channel, attrId, ctx)` / `jvidispatchIIIIO(1, channel, attrId, bool, ctx)` / `jvidispatchIIIDO` / int-, long-Varianten | Common Attribute setzen (null, String, Boolean, Double, Integer) | found |
| Java zu nativ | `jvidispatchIIO(4, state, ctx)` / `jvidispatchIO(10, ctx)` / `jvidispatchIO(12, ctx)` | Verbindungszustand / Flush / Reset | found |
| Java zu nativ | `jvidispatchIOOOO(4, ctx, signedCredential, acsPublicKey, configId)` | Ergebnis des Credential-IQ (bei Fehler alles null) | found |
| Nativ zu Java | `jnidispatchIO(6, byte[])` | einen regulären Buffer als `w:stats` IQ senden, gibt bei `result` 1 zurück | found |
| Nativ zu Java | `jnidispatchIO(7, byte[32])` | die `privatestats`-Credential-Anfrage senden | found |

---

## 4. Runtime-Initialisierung

`RunnableC29323CoA` case 33 baut eine Config-Map und ruft nativ einmal Init auf. Pfad ist `<filesDir>/wam`.

| Config-Key | AB-Prop | Typ | Wahrscheinliche Bedeutung | Tier |
|------------|---------|-----|---------------------------|------|
| `platform_code` | – | int `2` | Android-Plattform-ID | found |
| `beacon_probability` | **6977** | int | Wahrscheinlichkeit für den nativen "Beaconing"-Status pro Event (`WAMBeacon`) | found; Bedeutung inferred |
| `storage_size` | **9822** (x 1024) | long | Obergrenze des Buffer-Speichers (KiB zu Bytes); nativ loggt "no-enough-storage" und verwirft Events | found; Einheit inferred |
| `buffer_timeout` | **12399** | int | Timer der Buffer-Rotation | found; Bedeutung inferred |
| `throttling_percentage` / `throttling_exempt` | **9457** / **9456** | int / string | Upload-Throttling und Ausnahmeliste | found; Bedeutung inferred, Format unknown |
| `enable_extra_logging` | **14310** | bool | ausführliches natives Logging | found |
| `enable_ps_upload_v2` | **15205** | bool (nur wenn an) | natives "beginning upload v2 logic" auf dem privaten Transport | found |
| `enable_aggregation` / `aggregation_config` | **11981** / **11982** | bool (nur wenn an) / string | aktiviert `WAGAggregation` mit seinen Regeln | found; Format unknown |

Derselbe Aufruf erhält ein von `C25810yb` erzeugtes `networkSession`-Objekt; seine Verwendung durch die nativen HTTP-Wrapper ist inferred. Die Defaults der AB-Props werden vom Server geliefert und wurden nicht aufgelöst.

---

## 5. Common (globale) Attribute

Globale Attribute werden von `RunnableC29340CoR` case 0 über `C06590Fi.CYl(value, attrId, channel)` mit den Kanälen 0..3 geschrieben. Ein Helper setzt alle vier Kanäle gleichzeitig; andere setzen nur 0 und 1. Private Kanäle (2, 3) erhalten daher einen reduzierten Satz.

| Attr-ID | Wertquelle | Kanäle | Tier |
|---------|------------|--------|------|
| 3 / 5 | MNC / MCC, geparst aus `TelephonyManager.getNetworkOperator()` (5 oder 6 Ziffern, nur GSM) | 0 1 2 3 | found |
| 11 / 1659 / 1657 | Plattform-Code `2` / Plattform-Code `2` / Konstante `3` | 0 1 2 3 | found |
| 13 / 15 / 17 / 21 | `Build.MODEL-Build.MANUFACTURER` / `Build.VERSION.RELEASE` (übersprungen mit AB-Prop **12637**) / App-Version `2.26.41.6` / `true` (Beta-Flag inferred; in diesem Beta-APK hartcodiert) | 0 1 2 3 | found |
| 287 / 289 / 495 | `Build.MANUFACTURER` / `Build.MODEL` / ein Geräte-String (nicht aufgelöst) | 0 1 | found |
| 655 / 689 / 2617 | Gerätespeicher- und Geräteklassen-Metriken (`C38271gj`, `IJJ.A02/1048576`, `C38261gi`) | 0 1 2 3 | found; Namen inferred |
| 4473 | AB-Config-Key (`ab_key` aus der letzten `<props>`-Antwort, bei jedem AB-Update neu gesetzt) | 0 1 | found |
| 5029 | kommagetrennte AB-Experiment-Exposure-IDs (`BxP`); mit AB-Prop **31830** eine zusammengeführte Map aus `ab-props` und `ab-private-abprop` | 0 1; auch in einem privaten Buffer (Kanal 2) vorhanden | found |
| 6251 / 10255 | App-Signaturprüfung / Play-Installer-Flag | 6251: 0 1 2 3; 10255: 0 1 | found, siehe [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) |
| 12017, 12027, 14507, 15265, 15611, 23, 707, 7335, 13293, 23043 | verschiedene App-Zustandswerte (12027 Boolean aus dem Account-State-Objekt, 707 `primary_platform_name` nur wenn 12027 wahr ist, 13293 = AB-Prop **3664**, 15611 WASafe-Konstante (siehe [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md)), 7335 `true`, sobald die Init-Hooks gelaufen sind) | meist 0 1; 13293 alle vier | found; Bedeutungen inferred oder unknown |
| 47 | Commit-Zeit, int32 Sekunden, nativ hinzugefügt | alle | found (Bufferdatei) |
| 6005 | Private-Stats-ID-Wert (UUID-String oder `none`), nativ hinzugefügt | private Buffer | found (Bufferdatei) |
| 2795, 105 / 6833 | nativ hinzugefügt, nur reguläre Buffer / Wert aus `C21730rv`, nur Kanäle 2 und 3 | 0 / 2 3 | found; Bedeutungen unknown |

Keine Telefonnummer, JID oder Account-ID gehört zu den von Java geschriebenen Common Attributes. Der reguläre Transport ist über die authentifizierte Verbindung, über die er gesendet wird, an den Account gebunden (inferred, siehe 9).

---

## 6. Nativer Speicher

Strings aus `libwhatsapp.so` (`WAMBufferStoreImpl`, `WAMPSIDProfileStoreImpl`, `WAMPrivateCredentialStoreImpl`, `WAMMetadataStoreImpl`) und die Dateien eines installierten 2.26.41.6-Datenverzeichnisses stimmen überein.

### 6.1 Verzeichnis `files/wam/`

| Datei | Inhalt | Tier |
|-------|--------|------|
| `wamt-a-<channel>-0-<seq>` | aktiver Buffer, 65.559 Bytes (vorab allokiert, mit Nullen aufgefüllt); ein nativer String `wamt-o` deutet auf rotierte Buffer hin (inferred) | found |
| `wam-metadata` | `MTD`-v4-Container mit Zählern pro Kanal; die gespeicherte nächste Sequenz für Kanal 0 entspricht der höchsten Dateisequenz plus eins | found; Layout inferred |
| `WAMMetadataPSIDProfile-<n>-<keyHash>` | ein Private-Stats-Profil pro Key-Hash (8 Dateien gesehen) | found |
| `WAMMetadataPrivateCredential-<n>` | gespeichertes Credential für den privaten Transport (`signed_credential`, Key, Config-ID; v2, ca. 120 Bytes) | found; Layout inferred |

Die dritte Zahl im Dateinamen ist eine Stream-ID (Log "wameta/buffer/rotated stream id: %d, channel: %d, buffer sequenceNumber: %d"; im Sample immer `0`), die letzte ist die Buffer-Sequenz.

### 6.2 Layout der Bufferdatei

```
off  0   "WMT" 03                      container magic, version 3
off  4   u32 LE  used length           = (end of used data) - 31   (checked in 2 files)
off  8   u32 LE  ?                     counter, meaning unknown
off 12   u32 LE  event count           equals the number of event markers decoded
off 16   u32 LE  ?                     close to the used length (+4, +6, +31 in samples)
off 20   u32     ?                     check value (inferred), algorithm unknown
off 24   "WAM" 05                      WAM header: magic + protocol version 5
off 28   u8  0                         flag byte (0 in all samples)
off 29   u16 LE  buffer sequence       equals the number in the file name
off 31   u8  channel                   0 regular, 2 private in samples
off 32   TLV entries                   globals first, then events
```

Für jedes aufgeführte Byte mit einem Wert gilt found; mit "?" markierte Felder sind unknown.

### 6.3 Private-Stats-Profil

`WAMMetadataPSIDProfile-<n>-<keyHash>` (78 bis 90 Bytes), Layout aus allen acht Dateien gelesen:

```
u8 version(2) │ i32 LE keyHash │ i32 LE rotationDays │ u8 ? │ float64 LE (timestamp, inferred) │ u32 ? (1) │
u32 keyLen │ u32 uuidLen(36) │ key string (e.g. "id_ttl_daily") │ UUID string
```

Aus den Dateien gelesene Rotationstage: -1 (`default_ps_id`, `id_pre_metrics`), 1, 7, 30, 30, 30, 90 (siehe 2.3). Native Strings benennen die Operationen `WAMPSIDProfileRotatePSID`, "psid delegated rotation was not persisted" und Korruptionsprüfungen (`invalid rotationInDays`). Die UUID ist das, was in Global 6005 privater Buffer geschrieben wird. Ob die Rotation durch lokale Zeit oder vom Server gesteuert wird, ist unknown.

---

## 7. WAM-Wire-Format

Auf echten Buffern bestätigt: Ein nach dem unten stehenden Tag-Schema geschriebener Decoder hat Globals und Events zweier Buffer (regulär und privat) ohne Reste geparst.

### 7.1 Entry-Kodierung

Jeder Entry ist `[tag][field id][payload]`.

| Teil | Kodierung | Tier |
|------|-----------|------|
| Tag-Low-Nibble | Rolle: `0` global, `1` Event-Marker, `2` Feld; ODER `0x04` letztes in der Gruppe; ODER `0x08` Feld-ID ist `u16 LE` statt `u8` | found |
| Tag-High-Nibble | Werttyp: `0x00` null, `0x10` int 0, `0x20` int 1, `0x30` int8, `0x40` int16 LE, `0x50` int32 LE, `0x60` int64 LE, `0x70` float64 LE, `0x80` String (u8-Länge), `0x90` String (u16-LE-Länge), `0xA0` String (u32-LE-Länge) | found für int 0/1, int8, int16, int32, String u8 und u16 (alle aus Buffern dekodiert); die übrigen sind aus dem Schema und dem Baileys-Encoder inferred |
| Integer, Strings, Byte-Reihenfolge | kleinste Integer-Form (0 und 1 stecken im Tag); UTF-8-Strings; überall Little-Endian (der Stanza-Codec ist Big-Endian) | found |

### 7.2 Event-Marker

Ein Event-Marker ist Rolle `1` mit der Event-ID als Feld-ID. Sein Wert ist das Sampling-Gewicht, in den Buffern positiv gespeichert: Events mit Schema-Gewicht 20 (`wam_secure_file_usage`, `wam_whatsapp_quick_promotion_client_eligibility_waterfall`) tragen 20, Events mit Gewicht 1 tragen 1 (found). Felder folgen mit Rolle `2` (das Last-Field-Flag `0x04` wurde nicht geprüft). Ein Global-Block (Rolle `0`) wird geschrieben, wenn sich Attribute ändern, sodass sich Globals zwischen Events wiederholen (Commit-Zeit 47 wird oft neu geschrieben, found).

Der IQ-Payload ist 4 bis 126.976 Bytes (9). Dass er dem Buffer ab Offset 24 (dem `WAM`-Header an) entspricht, wird vom Code nicht gezeigt; es ist aus dem Layout und daraus inferred, dass Baileys denselben Header sendet (15).

---

## 8. Sampling und Gewichte pro Event

### 8.1 Auflösung (`C0Fg.A00`, vereinfacht)

```
override = prefs(code == 1094 ? "app_launch_event_sampling_weight" : "field-stats-events-sampling"[code], 0)
weight   = override != 0 ? override : schema.A00         // sampler becomes (|w|,|w|,|w|,|w|) for an override
keep     = random.nextInt(sampler.A00) == 0              // 1-in-N; null return = "(dropped)"
```

| Element | Wert | Tier |
|---------|------|------|
| Lokale Overrides | Prefs-Datei `field-stats-events-sampling` (Key = Event-Code) und `app_launch_event_sampling_weight` (Event 1094); Gewicht 1 wird immer behalten | found |
| Nativer Guard | "wameta/logger event weight exceeds max, dropped"; das Limit ist nativ | found; Wert unknown |
| Sampling pro Anruf | `WamCall`: das Feld `logSampleRatio` (id 1120) des Events bestimmt das Gewicht, `new C036300x(i, i)` | found |

### 8.2 Server-Auslieferung (AB-Props-Antwort)

`C28894Cgv.CFS` verarbeitet das AB-Props-Ergebnis (`<props>`-Node). Jedes `<prop>`-Kind ist entweder eine Config-Prop oder ein Event-Sampling-Eintrag:

```
<props ab_key hash refresh refresh_id delta_update>
  <prop config_code config_value config_expo_key/>    -> ab-props
  <prop event_code="854" sampling_weight="5"/>        -> field-stats-events-sampling
</props>
```

Wenn `hash` nicht leer ist, werden die Sampling-Prefs gelöscht und aus allen `event_code`/`sampling_weight`-Paaren neu geschrieben; Eintrag 1094 schreibt zusätzlich `app_launch_event_sampling_weight` (und entfernt es, wenn er fehlt). Der Server steuert also die Gewichte pro Event, und die Gewichte werden mit jedem Event zurückgesendet, damit der Server Zählungen skalieren kann (inferred daraus, dass das Feld mit dem Event reist; Verwendung durch den Server unknown).

Der Server formt WAM daher über AB-Props, Sampling-Gewichte und das private Credential; auf dem Upload-IQ selbst wird nichts gepusht (das IQ erhält nur `result`).

---

## 9. Regulärer Upload (`w:stats`)

Nativ ruft `JniBridge.jnidispatchIO(6, bytes)` auf. Java baut und sendet:

```
<iq xmlns="w:stats" to="s.whatsapp.net" type="set" id="..">
  <add t="<unix seconds>">[binary: WAM buffer]</add>
</iq>
```

| Element | Wert | Tier |
|---------|------|------|
| Transport | der normale authentifizierte Chat-Stream (`C10140Tq`), wie jedes IQ | found |
| `t`, Grenzen, Timeout | `t` = aktuelle Unix-Sekunden (nur innerhalb 1.577.865.600..4.102.473.600 hinzugefügt); Payload gegen 4..126.976 Bytes geprüft; IQ-Timeout 32.000 ms (synchrones Warten) | found |
| Erfolg | Antwortattribut `type == "result"` -> Accounting `C0VI.A02(len, 32)`, gibt 1 zurück | found |
| Fehler | anderer Typ oder Interrupt -> Log "FieldStatsXmppImpl/error sending fieldstats IQ", gibt 0 zurück (nativ entscheidet über Retries; "_WAMTransportManagerUploadFailedPermanently" existiert) | found |
| Zurückgestellt während eines Anrufs | gibt 0 zurück mit Log "WamJniBridge/upload postponed", wenn ein Anruf aktiv ist, außer AB-Prop **15507** ist an oder der Anruf ist ein Gruppenanruf und AB-Prop **468** ist an | found (Decompiler-Fluss, Default des Gruppen-Flags als false angenommen) |
| Zurückgestellt während der Offline-Verarbeitung | gibt 0 zurück, wenn `C0A2.A0N()` (verbunden und Offline-Nachrichten noch nicht geleert) und AB-Prop **9654** an ist; bei 9654 aus wird das IQ gesendet | found |
| Account-Verknüpfung / Kompression | keine Account-ID im Payload, der Server sieht die authentifizierte Session; keine Kompression auf dem Java-Pfad | inferred / found |

Dieselbe Prop 9654 aktiviert den Flush bei `offlineProcessComplete` (3.3). Zusammen: Mit 9654 an warten Uploads, bis die Offline-Nachrichtenwarteschlange geleert ist und in diesem Moment ein Flush läuft (inferred aus den beiden Aufrufstellen; das Retry-Timing nach einem zurückgestellten Versuch ist nativ und unknown).

---

## 10. Privater Upload

Private Kanäle (2 und 3) werden nicht als `w:stats` gesendet. Das native `WAMTransportPrivate` lädt über einen separaten HTTP-Transport (`WCIHTTPImpl`) mit einem anonymen Credential hoch. Alles Folgende stammt aus nativen Log-Strings und dem Java-Credential-Handler.

### 10.1 Credential-Anfrage

```
<iq xmlns="privatestats" to="s.whatsapp.net" type="get" id="..">
  <sign_credential version="1">
    <blinded_credential>[32 bytes]</blinded_credential>
  </sign_credential>
</iq>
```

| Teil | Detail | Tier |
|------|--------|------|
| Sender | `JniBridge.jnidispatchIO(7, byte[32])`; Fehlercode im IQ-Tracker ist 239, Timeout 32.000 ms | found |
| Antwort (`KRL.CFS`) | `<sign_credential t=..><signed_credential/><acs_public_key/><config_id/></sign_credential>`; die drei Byte-Arrays werden mit `jvidispatchIOOOO(4, ctx, ...)` an nativ übergeben; bei Fehler oder ohne Antwort erhält nativ Nullen | found |
| Telemetrie | Event 2242 `wam_sign_credential` (regulärer Kanal) mit Status 3 = Fehler, 1 = Erfolg, und verstrichener Zeit | found |
| Verifikation und Speicherung | native Strings "Invalid signature received from server", "fails validation" (der Client validiert die Signatur); gespeichert in `WAMMetadataPrivateCredential-<n>`, erneuert bei 401 ("send failed, renew credentials") | found |
| Schema | geblindete Anfrage, signierte Antwort, ACS-Public-Key: ein anonymes Credential, sodass das Credential private Uploads nicht mit dem Account verknüpft | inferred |

Ein separater generischer Sender `C1N8` verwendet denselben Namespace mit `<sign_credential version="2">` und `project_name` für andere ACS-Projekte (Prefs `acs_token_*`); er ist nicht der WAM-Pfad.

### 10.2 Upload

| Element | Detail | Tier |
|---------|--------|------|
| Endpoints | native Logs "url/received", "fetch_endpoints/custom_endpoints - got endpoints: %d", "invalid_ps_endpoint, ignoring"; kein URL-Literal in Java oder `libwhatsapp.so` | found; Quelle der Liste unknown |
| Fehlerbehandlung und Timer | "try next endpoint", "have next credentials", "401, no more endpoints"; Transport-Timer ("timer/started - interval: %.1f seconds") gestartet bei "connection_ready", gestoppt bei "connection_unavailable" | found; Intervall unknown |
| Realtime privat | Buffer pro Event: "create_buffer/realtime/buffer-created ... event id", "sendsingleeventimpl/realtime" | found |
| Header, Body-Framing, Kompression | nicht sichtbar | unknown |

Der Falco-Logger `C40099Hdc` mit Modus 9 verwirft Events mit Kanal 2 oder 3 oder einer psId aus seinem eigenen Pfad und zählt sie als `wa:dropped_private_stats` (found), sodass private Events nicht in diesen Logger dupliziert werden (inferred).

---

## 11. `wam_daily` und periodische Events

Event-ID 1158, Falco-Name `wam_daily`, Kanal 0, Gewicht 1, 218 numerische / 205 benannte Felder. Für die Felder zu Root, Emulator, Custom-ROM und Mod-Client siehe [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md); hier wird nur die Plumbing festgehalten.

### 11.1 Scheduling (found)

| Baustein | Detail |
|----------|--------|
| Alarm | `BEL.A01`: nächste lokale Mitternacht + zufälliger Jitter `nextInt(AB prop 5529)` (Einheit umgerechnet durch `C20D.A02`), Action `com.whatsapp.action.DAILY_CRON` |
| Catch-up | Action `com.whatsapp.action.DAILY_CATCHUP_CRON`, alle 15 Minuten wiederholt, solange "last_daily_cron" nicht von heute ist |
| Guard | überspringt mit "too frequent", wenn der Cron heute bereits lief (Pref `last_daily_cron`); überspringt alle Crons, solange ein Chat-Transfer läuft; Crons, die den Message-Store benötigen, werden übersprungen, wenn er nicht bereit ist |
| Executor | iteriert eine DI-Menge von `InterfaceC29983D2n`-Crons (`Bo5`); `C28643Ccj` (Tag `WamDailyEventDailyCron`) läuft nur, wenn `anonymousClass091.BS3()` (Account-Zustand, Bedeutung nicht aufgelöst) |

### 11.2 Befüllung

`C28643Ccj.Bo5` erzeugt `new C0Fp()`, ruft `C4k(C0Fp)` auf jedem Populator in einer DI-Menge auf (28 Dateien definieren einen `C4k(C0Fp)`-Populator), dann `CNW(c0Fp)` mit dem Standard-Schema-Gewicht. Der Geräte-Flag-Populator existiert in diesem Build nur als Smali (`smali_classes7/X/Cdt.smali`; der Decompiler scheitert daran) und liest und schreibt die Pref `last_daily_event` (Wanduhrzeit in ms) und weist `time_delta_since_last_event` zu. Der dekompilierte Zweig ändert das Delta nur von 0 auf 1, daher wird keine Aussage zu Einheit oder Kadenz dieses Felds gemacht. `last_daily_event` ist nicht der Scheduler (das ist der Alarm in 11.1).

Derselbe Cron sendet ein reines Falco-Event `wam_daily_permission` (gesampelt): Status der Kontakte-Berechtigung, Galerie-Berechtigung, Kamera- / Audioaufnahme- / grobe und genaue Standort-Freigaben, OS-Benachrichtigungseinstellung, Adressbuchgrößen, optionale Thread-Zahlen (AB-Prop **25576**) und `profile_photo_is_set` (AB-Prop **34207**), `os_version` (found).

### 11.3 Weitere periodische Events

Weitere App-Start- und periodische Events: 1094 `wam_app_launch` (Gewicht durch `app_launch_event_sampling_weight` überschreibbar), 3300 `wam_ps_app_launch` (privat, `id_pre_metrics`), 3178 `wam_clock_skew_difference_t` (privat, `id_ttl_90_days`), die `*_daily`-Familie (5798 `wam_reaction_daily`, 3680 `wam_polls_daily_stats`; Trigger inferred).

---

## 12. Datenschutzbehandlung

| Aspekt | Befund | Tier |
|--------|--------|------|
| Stabile IDs in Batches | keine JID oder Telefonnummer in von Java geschriebenen Common Attributes; `dedup_key` und `trace_id_int` sind pro Event zufällig; der reguläre Kanal wird durch den Stream authentifiziert, über den er läuft | found / inferred |
| Private-Stats-IDs | UUID pro Key in `WAMMetadataPSIDProfile-*`, Global 6005 in privaten Buffern; Rotation 1, 7, 30, 90 Tage oder nie | found |
| Anonymes Credential | geblindetes, vom Server signiertes Token für private Uploads (10.1) | found; Unverknüpfbarkeit inferred |
| Gehashte und Klartext-IDs | Felder mit gehashten IDs existieren (`hashed_blocked_conversation_jids`, `hashed_reported_conversation_jids`, `message_key_hash`, `invited_user_hash`; Hashfunktion nicht nachverfolgt); JID-typisierte Strings existieren ebenfalls (`reported_jid`, `e2e_sender_jid`; Hashing vor dem Logging nicht nachverfolgt) | found (Namen), unknown |
| Reset | Kontoentfernung und Neuregistrierung rufen den nativen Reset auf (`jvidispatchIO(12)`); ein Reset der PSID-Profile dadurch wird nicht gezeigt | found / unknown |
| Nutzer-Opt-out | keine Einstellung, kein String und kein Flag gefunden, das WAM deaktiviert; der einzige zustimmungsartige String in den Ressourcen betrifft Support-Diagnosen. Eine Einstellung kann in nicht durchsuchten Codepfaden existieren | unknown |
| Server-Steuerung | Gewichte pro Event (8.2), AB-Props (13), `throttling_*`- und `beacon_probability`-Config (4); die Algorithmen sind nativ | found; unknown |

---

## 13. Feature-Flags (AB-Props, wie in den obigen Codepfaden gelesen)

| Prop | Typ | Steuert |
|------|-----|---------|
| **9654** | bool | Flush bei abgeschlossener Offline-Verarbeitung (3.3); Upload zurückgestellt, während Offline-Nachrichten geleert werden (9) |
| **15507** / **468** / **16047** | bool | Upload nicht zurückgestellt während eines Anrufs / während eines Gruppenanrufs / Flush nach Call-Events |
| **6977**, **9822**, **12399**, **9457**, **9456**, **14310**, **15205**, **11981**, **11982** | gemischt | Config-Keys der Runtime-Init (Abschnitt 4) |
| **31314** | string | `"code:N;..."` Rate des Log-Upload-Triggers pro Event-Code |
| **5529** | int | Jitter des Daily-Cron |
| **12637** | bool | überspringt OS-Version-, Hersteller- und Companion-Attribute (15, 287, 21, 12027, 707) |
| **31830** / **25576** / **34207** | bool | zusammengeführte private AB-Liste in Attribut 5029 / optionale Felder von `wam_daily_permission` |
| **34494..34507, 35169, 35170** | – | Array in `AbstractC38513Goh.A01` (16 IDs, gleiche Anzahl wie die Falco-Migrationsbatches 1..16); Verwendung inferred |

Alle Werte werden vom Server zugewiesen; Defaults wurden nicht aufgelöst.

---

## 14. Wichtige Event-Familien

Namen sind Falco-Namen; IDs und Kanäle stammen aus den Event-Klassen. Feldlisten sind die benannten Felder von `getFieldsMapForFalco()`.

### 14.1 Nachrichten

| Event | id | Ch / Gewicht | Wichtige Felder |
|-------|----|--------------|-----------------|
| `wam_message_send` | 854 | 0 / 5 | 89 Felder: `message_send_result`, `message_send_t`, `message_type_str`, `e2e_ciphertext_type`, `e2e_ciphertext_version`, `is_pq`, `is_lid`, `retry_count`, `resend_count`, `message_is_forward`, `message_is_fanout`, `message_distribution_type`, `participant_count`, `device_count`, `message_key_hash`, `is_view_once`, Ephemeralität, Edit/Revoke, Bot- und Private-AI-Felder |
| `wam_message_receive` | 450 | 0 / 20 | 58 Felder: `message_receive_t0..t2`, `message_queue_time`, `message_is_offline`, `offline_count`, `stanza_process_count`, `padding_bytes_size`, `message_addressing_mode`, `server_addressing_mode`, `session_scope`, Sticker- und Kontaktkarten-Felder |
| `wam_e2e_message_send` / `_recv` | 476 / 478 | 0 / 20 | `e2e_successful`, `e2e_failure_reason`, `e2e_destination`, `group_encryption_state`, `enc_retry_count`, `pq_receive_gate_state` |
| `wam_e2e_message_decrypt_fail_sender` | 3524 | privat (ps `none`) | `e2e_sender_jid`, `e2e_failure_reason`, `retry_count` |

### 14.2 Anrufe

`WamCall` (id 462, Kanal 0) wird aus nativen Stats erzeugt (`ConvertFieldStats`, "can not construct com/whatsapp/fieldstats/events/WamCall") und hat etwa 1.700 benannte Felder (1.716 `put`-Stellen in der Falco-Map). `WamJoinableCall` ist id 2572. Das Sampling ist `logSampleRatio` (Feld 1120), und das Event wird am Anrufende geflusht (3.3). Weitere Call-Events: 2582 `wam_call_stanza_receive` (Gewicht 1000), 3452 `wam_call_critical_events`, 4568 `wam_call_user_journey`. Die Call-Signalisierung selbst steht in [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md).

### 14.3 Login und Registrierung

| Event | id | Felder |
|-------|----|--------|
| `wam_login` | 460 | `login_result`, `login_t`, `connection_origin`, `connection_t`, `login_dns_resolver`, `login_ip_source`, `login_port`, `login_resolved_pop`, `login_socket_provider`, `noise_protocol_version`, `retry_count`, `server_error_code`, `passive`, `long_connect`, `network_is_vpn`, `android_keystore_state`, `pending_acks_count`, `unprocessed_message_count` (30 Slots); siehe [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) |
| `wam_reg_init` / `wam_registration_complete` | 2046 / 1342 | Init-Timings (`contacts_sync_t`, `groups_init_t`, `total_t`); 30 Felder inkl. `registration_t`, `addressbook_size`, `contacts_permission_authorization_status`, `device_identifier`, `google_account_list_hashed_reg`, `invited_user_hash`, `is_new_jid`, Profilbild- und Berechtigungsfelder |
| `wam_account_encryption_attestation` | 8164 | der Name legt ein Attestierungsergebnis nahe (inferred); siehe [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) |

### 14.4 Spam, Report, Block

Die Flows stehen in [WA_REPORTING.md](WA_REPORTING.md) und [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) (`wam_wfacp_ban_action`, id 5028); WAM-Seite:

| Event | id | Kanal | Felder |
|-------|----|-------|--------|
| `wam_spam_report_perf` | 6310 | 0 | `report_spam_flow`, `report_status`, `report_attempt_count`, `report_duration_ms`, `report_error_code` |
| `wam_report_conversation_context` | 4608 | 0 | `reported_jid`, `spam_flow`, `estimated_num_messages_sent/received`, `is_chat_maybe_suspicious`, `is_in_addressbook`, `first_entry_point`, `num_call_msgs_to_report` |
| `wam_blocking_funnel` / `wam_reporting_funnel` | 4920 / 4924 | 0 | `block_flow_action`, `hashed_blocked_conversation_jids`, `hashed_reported_conversation_jids` |
| `wam_reporting_token_validation_failure` | 5466 | 0 | `reporting_token_validation_failure_reason`, `reporting_token_version`, `is_part_of_group_history` |
| `wam_reporting_token_validation_failure_sender`, `wam_reporting_token_additional_client_validation` | 6094, 6702 | 2 (`default_ps_id`) | Varianten auf Senderseite |
| `wam_message_template_blocks` | 3002 | 2 (`default_ps_id`) | Blockierungsgründe für Business-Templates |

### 14.5 Experimente

`wam_wefr_client_exposure` (id 5504, realtime) loggt die Exposure mit `exposure_key`, `device_exp_id`, `user_lid`, `guest_id`, `is_canonical_ent_present`, `sent_with_daily`. Es trägt ein User-LID-Feld (found; Verwendung durch den Server unknown). `wam_ui_action_real_time` (2098, Gewicht 10) trägt nur `chatd_internet_connectivity` und `dedup_key`.

---

## 15. Baileys (`baron-baileys-v2`, gegen dessen Quellcode verglichen)

Baileys sendet WAM-Buffer mit demselben IQ wie der Android-Client.

| Aspekt | Baileys (`src/Socket/socket.js`, `src/WAM/encode.js`) | Android 2.26.41.6 | Tier |
|--------|--------------------------------------------------------|-------------------|------|
| Upload-Stanza | `<iq to=s.whatsapp.net xmlns="w:stats" type="set"><add t=…>buffer</add></iq>` | gleich | found beide |
| Header | `"WAM"`, Versionsbyte 5, Byte 4 = `1`, `u16 BE` Sequenz bei 5, Kanal `0` bei 7 | `"WAM"`, Version 5, Byte 4 = `0`, `u16 LE` Sequenz bei 29, Kanal bei 31 (in der Datei mit einem `WMT`-Container davor) | found beide |
| Wertkodierung | `0/1` im Tag, int8, int16/int32 LE, float64 LE, Strings mit u8/u16-LE/u32-LE-Länge, Wide-ID-Flag `0x08` | gleiche Bits | found beide |
| Event-Gewicht | geschrieben als `-weight` | in Bufferdateien positiv gespeichert | found beide |
| Kanäle, Flush | nur regulär; Flush alle 30 s und nach dem Login, Fehler werden nur geloggt | 0..3; native Rotation und Transports | found |

Der Unterschied bei Sequenz-Byte-Reihenfolge und Gewichtsvorzeichen ist kein von diesem Report bewiesener Fehler: Android-Dateien auf dem Datenträger müssen nicht den Bytes entsprechen, die der native Transport hochlädt, und der Parser des Servers wurde nicht beobachtet. Nichts in den hier gelesenen Chat-Codepfaden wartet auf WAM-Zustand; ob der Server auf einen fehlenden oder ungewöhnlichen Upload reagiert, ist unknown (19).

---

## 16. Fehlerfälle

| Symptom | Ursache | Fix / Hinweis |
|---------|---------|---------------|
| Event fehlt in Buffern | Gewichtswurf fehlgeschlagen (1-in-N), Kanal-3-Allowlist, Speicherobergrenze, nativ "weight exceeds max", "have to drop event" | Gewicht 2.4 und AB-Props 8.2, 4 prüfen |
| Daily-Event erzeugt Validierungs-Events | die Regel `ai_widget_installed` schlägt für jedes `wam_daily` fehl (3.2) | in diesem Build erwartet |
| "WamJniBridge/upload postponed" | Anruf aktiv ohne 15507 / 468, oder Offline-Warteschlange wird noch geleert bei 9654 | vorübergehend; nativ wiederholt (inferred) |
| "FieldStatsXmppImpl/error sending fieldstats IQ" | IQ-Fehler, Timeout (32 s) oder Interrupt | nativer Retry- / Permanent-Failure-Pfad |
| "Cannot log before WAM runtime is initialized" / "after ... terminated" | Reihenfolge des nativen Lifecycles | Java wartet auf `A0K`; Terminate ist ein nativer Zustand |
| Privater Upload scheitert mit 401 | Credential abgelehnt | über `privatestats`-IQ erneuern (10.1) |

---

## 17. Wichtige Unterscheidungen

| Paar | Unterschied |
|------|-------------|
| WAM vs Falco | WAM-Events laufen durch den nativen Runtime und Buffer; der Java-Falco-Logger (`C40099Hdc`, `FFLogger`) ist ein paralleler Pfad, der dieselben Event-Klassen über den Falco-Namen wiederverwendet. Der Falco-Migrationsbatch 1..16 gilt pro Event (`internalFalcoMigrationBatchNumber`) |
| Event-Gewicht vs Feature-Flag | Gewicht = 1-in-N-Sampling und ein mit dem Event gesendeter Multiplikator; Flags steuern nur das Transportverhalten |
| Regulärer vs privater Upload | regulär = `w:stats` IQ auf dem Chat-Stream; privat = separater HTTP-Transport mit einem geblindeten Credential |
| `psId` vs Global 6005 | `psId` ist ein statischer Key-Hash auf der Event-Klasse; 6005 ist eine rotierende UUID, die nativ in private Buffer geschrieben wird |
| Feld-ID vs Global-ID | die numerischen Räume überlappen (47 ist ein Global; Feld 47 eines Events ist etwas anderes); die Tag-Rolle unterscheidet sie |
| `wam-event/<name>` vs WAM-Upload | Ersteres lädt Geräte-Logs über den Crash-Reporter hoch, Letzteres lädt Metrik-Buffer hoch |
| Buffer auf dem Datenträger vs Wire-Payload | die Datei hat einen `WMT`-Container und Padding; das Layout des IQ-Payloads ist inferred |

---

## 18. Kompletter Flow

```
[App code / native call stats]  new Event(...) / ConvertFieldStats -> WamCall
    ▼
[C06650Fo.CNW / CNI]  weight = override (prefs) or schema A00, keep 1-in-N ; validate (ch 0,1) -> event 5560
    ▼
[WAM executor]  jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fields)
    ▼
[libwhatsapp.so WAMRuntime]  encode TLV (LE), add globals (47 commit time, 6005 psId UUID, common attrs)
    ▼
[files/wam/wamt-a-<channel>-0-<seq>]  "WMT" container + "WAM" 5 header, 64 KiB
    │  rotate (buffer_timeout) / flush (offline-complete with 9654, Bba, call end, CXZ)
    ├── channel 0, 1 ─────────────────────────────┬── channel 2, 3 ───────────────────────────────┐
    ▼                                             ▼                                              
jnidispatchIO(6, bytes)                       jnidispatchIO(7, 32 bytes blinded token)
    │  postponed in calls / offline drain          │  <iq xmlns="privatestats" type="get">
    ▼                                             ▼
<iq xmlns="w:stats" type="set"><add t=..>     [WA server] signed_credential, acs_public_key, config_id
  bytes</add></iq>  on the chat stream              │  stored, renewed on 401
    ▼                                             ▼
[WA server] type="result" -> return 1         HTTP upload, endpoint list source unknown -> [private-stats backend]

[WA server] <props> response: event_code -> sampling_weight, config_code -> AB props  ──►  prefs (8.2)
[DailyCronAction alarm: next local midnight + jitter(5529)] -> C28643Ccj populates C0Fp (wam_daily 1158) -> CNW (same path, channel 0)
```

---

## 19. Unbekanntes

| Frage | Warum unknown |
|-------|---------------|
| Exakte Bytes des Upload-Payloads gegenüber der Bufferdatei | nativer Transport nicht disassembliert; nur IQ-Grenzen gesehen |
| Kompression und Header-Framing privater Uploads, Quelle der Endpoint-Liste | kein Literal in Java oder Strings; nativer HTTP-Pfad nicht nachverfolgt |
| Native Rotationsintervall, Retry-Zeitplan, Gewichtsmaximum, Drop-Regeln, Beaconing-Algorithmus | gestrippter nativer Code, hier kein Decompiler für die große Bibliothek verwendet |
| Bedeutung der Attribute 495, 6833, 2795, 105 und mehrerer Flag-Attribute; `WMT`-Felder bei Offsets 8, 16, 20; `MTD`-Felder | Quellen nicht aufgelöst, nur Werte |
| Ob irgendein Serververhalten von fehlendem oder ungewöhnlichem WAM abhängt | Serverseite |
| Hashing der `*_jid`-Felder; Vorhandensein eines nutzerseitigen Opt-out | nicht pro Event nachverfolgt / nicht gefunden (Abwesenheit ist kein Beweis) |
| Natives Retry-Timing, Trigger der PSID-Rotation (Client-Zeit oder Server-Anweisung), AB-Prop-Defaults | native Logik nicht nachverfolgt; Defaults stammen aus der Server-Config |
| Trigger anderer Daily-Crons als `wam_daily` | nur die Cron-Registry und der `wam_daily`-Cron wurden gelesen |
