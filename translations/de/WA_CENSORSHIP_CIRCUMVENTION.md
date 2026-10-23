<!-- src-sha1: 5428e0461d6ea8f961256e4ead0fe3df30ea4164 -->
# WhatsApp Zensurumgehung — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** Android-Konnektivitäts-Fallbacks bei blockiertem chatd: vom Nutzer konfigurierter WhatsApp Proxy (Settings-UI, Speicherung, Share-Link, Nutzung durch chatd und Media), servergesteuerter Proxy-Service (Psiphon-Tunnel, Voltron-Modul, Region- und VPN-Gates, SOCKS-Tunnel mit PROXY-v2-Header), Fallback-IP-Liste (`<ib><fbip>`, Datei `fbips`), Unblocking-Push (`fbips`, `unblocking_props`, `psl`), DNS-Fallback-Kette, Registrierungs-Relay-Provider und Retry-Strategien, Rollen von Tigon und DGW, Verbindungsstatus-Tracking und Diagnose, Zusammenspiel der Retries, Feature-Flags, fehlende Mechanismen, Vergleich mit Baileys

---

## 1. Was dieser Build enthält

Alle Aussagen stammen aus der statischen Analyse der dekompilierten APK; nichts wurde auf der Leitung mitgeschnitten. Tiers: **found** = in Code oder Ressourcen gelesen, **inferred** = abgeleitet, **unknown** = nicht aufgelöst. Obfuskierte Namen gelten pro Build und wurden in 2.26.41.6 neu aufgelöst. chatd-Transport, Handshake, Host-Leiter und Backoff stehen in [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) und werden hier nicht wiederholt.

| Mechanismus | Zustand | Einstiegspunkte | Tier |
|-------------|---------|-----------------|------|
| WhatsApp Proxy (vom Nutzer konfiguriertes Chat- und Media-Relay) | vorhanden, Nutzer-UI, per Feature-Flag gesteuert | `SettingsUserProxyActivity`, `SettingsSetupUserProxyActivity`, `C12660bX`, `C12690ba`, Schritt 12 der chatd-Sequenz | found |
| Proxy-Service (Psiphon-Tunnel, Voltron-Modul `proxyservice`) | vorhanden, servergesteuert, keine Nutzer-UI | `C12760bh` (Orchestrator), `C42448IfJ` / `S6G`, `ca.psiphon.PsiphonTunnel`, `ProxyServiceBroadcaster` | found; native Bibliothek nicht in der APK |
| Fallback-IP-Liste | vorhanden | `<ib><fbip>` in `C40581l4`, `C36821d6`, Datei `fbips` | found |
| Fest codierte Tabelle Host zu IP, Host-Leiter | vorhanden | `AbstractC47101wK` (18 Hostnamen), `C37151de` | found |
| DNS-Fallback-Kette (Plattform / MNS, UDP zu 8.8.8.8 und 8.8.4.4, fest codiert) | vorhanden | `C36881dC`, `QG1` | found |
| Unblocking-Push (`nt` = `unblocking`) | vorhanden | `CLl`-Parser, `C28139CLl`, `C28912ChD`, `C27946CBo` | found |
| Registrierungs-Relay (Cloud-Function-Provider) und Retry-Strategien | vorhanden, nur Registrierung | `res/raw/domain_fronting_providers.tsv`, `C45421Jrl`, `RetryingHttpClient` | found |
| Tigon / DGW als chatd-Fallback | nicht vorhanden | DGW-Fallback-Konfiguration existiert, wird aber deaktiviert gebaut | found |

Nicht vorhanden in diesem Build (als Abwesenheit im dekompilierten Java, im Manifest und in den Ressourcen gefunden; nativer Code nicht untersucht):

| Fehlt | Beleg |
|-------|-------|
| chatd über WebSocket, HTTP-Long-Poll oder MQTT | kein Literal `wss://` oder `/ws/chat` im Java; `mqtt` nur in Analytics- und DGW-Stream-Labels (siehe Noise-Report Abschnitt 13) |
| Android `VpnService` | kein Service und kein `BIND_VPN_SERVICE` im Manifest; Psiphon läuft im Local-Proxy-Modus |
| Vom Nutzer konfigurierbarer SOCKS- oder HTTP-CONNECT-Proxy für chatd | Schritt 12 baut einen direkten Socket zu `host:chatPort`, kein Proxy-Handshake |
| System-Proxy (`http.proxyHost`, `https.proxyHost`) für chatd | wird von Sequenz und Socket-Code nicht gelesen; nur von Tigon und als Guard gelesen (Abschnitt 4.6) |
| Domain Fronting oder Relay für chatd | die Provider-Liste wird nur vom Registrierungs-Client verwendet (Abschnitt 7) |
| Tor, Snowflake, andere Pluggable Transports | kein Code und keine Ressource gefunden |

Punkte, die den Rest des Reports bestimmen:

- Es gibt zwei unabhängige Proxy-Mechanismen, die nie zusammen laufen: den Nutzer-Proxy (Schritt 12, terminal) und den Psiphon-Proxy-Service (SOCKS-Tunnel, der direkte Verbindungen für eine Teilmenge der Schritte ersetzt). Ist ein Nutzer-Proxy gesetzt, wird die Service-Konfiguration ignoriert (`ConnectionSequence/socketConfigForUserProxy/skipping socks proxy in favor of user proxy`).
- Bei gültigem Nutzer-Proxy hat die Sequenz genau ein Ziel. Schritt 12 geht weiter zu 16 (erschöpft); es gibt keinen Fallback auf direkte Hosts (found, `C37031dS.A0G`).
- `libgojni.so` wird im herunterladbaren Modul ausgeliefert. Die APK enthält nur das Modul-Manifest; Tunnel-Dialing, Protokollwahl und Anti-DPI-Verhalten sind unknown.

---

## 2. Einordnung in die chatd-Verbindungssequenz

Schrittnummern entsprechen Noise-Report Abschnitt 2.2. Quelle: `C37031dS.A0G`, `C37151de`, `C37061dV`.

| Bedingung | Wirkung |
|-----------|---------|
| Debug-Adresse gesetzt | nur Schritt 1 |
| Gültiger Nutzer-Proxy (aktiviert, Host gültig, Flag **2784**) | Schritt 0 geht zu 12, der terminal ist; Psiphon-Konfiguration wird ignoriert |
| Kein Nutzer-Proxy, Psiphon-Konfiguration vorhanden (`C37061dV.A00 != null`) | Schritte 5, 8, 13 bleiben erhalten; 6, 7, 9, 10, 11, 14, 15 werden übersprungen (`ConnectionThread/Skipping sequence N due to active proxy`); 2, 3, 4 werden übersprungen, außer Flag **23630** ist an |
| Kein Nutzer-Proxy, keine Psiphon-Konfiguration | unveränderte Leiter: 2, 3, 4, 5, 8, 9, [15], 13, 14, 6, 10, 7, 11 |

Die Skip-Tabelle ist der Packed-Switch im Bytecode von `C37031dS.A0G` (Schritte 2 bis 15 abgebildet auf behalten / überspringen / flag-abhängig). Schritt 8 baut seine Konfiguration aus einem IP-Literal ohne Proxy-Konfiguration; in einem Lauf mit aktivem Proxy bleibt er daher erhalten, verbindet aber vermutlich direkt (inferred). Die Schritte 5 und 13 lösen über `C37151de.A03` auf: Mit Psiphon-Konfiguration und ohne Nutzer-Proxy trägt die zurückgegebene Socket-Konfiguration die `ProxyServiceConfig` (`C46661vS`) und einen unaufgelösten Hostnamen, sodass DNS am Tunnel-Exit stattfindet (`DNSResolutionMethod` 7 `SOCKS_PROXY`, interner Code 8 in `C37181dh`).

Reihenfolge in Schritt 0, wenn keine Debug-Adresse existiert (found; der dekompilierte Java-Zweig für Schritt 1 liest sich invertiert, der Bytecode bestätigt es): Nutzer-Proxy, dann servergelieferte Override-Einträge (2), dann konfigurierter Host-String (3), dann 5.

---

## 3. WhatsApp Proxy (vom Nutzer konfiguriert)

### 3.1 Settings-Einstieg und Screens (found)

| Screen | Klasse | Inhalt |
|--------|--------|--------|
| Settings > Storage and data > Proxy | `SettingsUserProxyActivity` (Manifest `com.whatsapp.settings.ui.proxy.*`, nicht exportiert) | Schalter `Use proxy`, Host-Zeile, Statuszeilen für Chat und Media, Share-Menüeintrag, Infotext (`Only use a proxy if you're unable to connect to WhatsApp. Your IP address may be visible to the proxy provider…`, Link `whatsapp-proxy`) |
| Set up proxy | `SettingsSetupUserProxyActivity` | Host-Eingabe, `Ports (Optional)` mit `Chat port` (Standard als `Default` für 443 angezeigt), `Media port` (`Default` für 587), `Use TLS`, Speichern-Button |
| Eintrag in der Settings-Suche | `C23869ARc`-Subklasse `C215199Jq` | Schlüssel `proxy` |
| Löschen | Long-Click auf die Host-Zeile (`ViewOnLongClickListenerC46012K9h`, `Delete Proxy?`), Aktion in `KZA` | löscht Host, setzt Media-Port 587 und TLS true zurück, Status 0, `proxy_enabled` false |

Validierung: `K09.A01` (IP-Literal), `K09.A02` (Host mit optionalem `:port`, Regex aus `JRQ.A02` gebaut); Fehler `Enter a valid host`, `Enter a valid port`. IPv6-Parsing existiert in `K09.A00`.

### 3.2 Speicherung (found, `C12660bX`, `C12690ba`)

SharedPreferences-Datei `user_proxy_setting_pref`.

| Key | Typ | Standard | Verwendung |
|-----|-----|----------|------------|
| `proxy_enabled` | bool | false | Schalterzustand; nur wirksam, wenn Flag **2784** an ist (`C12690ba.A03`) |
| `proxy_ip_address` | string | none | `host:chatPort` (`ProxySetting.A04`); Port wird beim Lesen geparst, Standard 443 |
| `proxy_media_port` | int | 587 | Port des Media-Relays |
| `proxy_use_tls` | bool | true | TLS-Wrapper für den Chat-Socket |
| `proxy_connection_status` | int | 0 | in der UI angezeigter Chat-Status (Abschnitt 3.5) |
| `proxy_media_connection_status` | int | 0 | in der UI angezeigter Media-Status |

`ProxySetting` (`C45598Jv6`) = `domain`, `ip`, `chatPort`, `mediaPort`, `useChatTls`; ein Host, der ein IP-Literal ist, landet in `ip`, sonst in `domain`. `C12660bX.A03()` liefert es nur, wenn aktiviert, Flag **2784** an und Host oder IP gültig; dies ist das Objekt, das die Verbindungssequenz erhält.

### 3.3 Share- und Import-Link (found)

Share: Der Menüeintrag baut `https://wa.me/proxy?host=<host>&chatPort=<n>&mediaPort=<n>&chatTLS=<true|false>` mit Betreff `WhatsApp Proxy` und Text `Connect to WhatsApp using proxy. <url>`.

Import: `DeepLinkActivity` (Typ `DEEP_LINK_PROXY`, Log-Präfix `PROXY:`) verlangt Flag **2784**, hat den Ablehnungsgrund `proxy_has_segments` (Bedingung aus dem Namen inferred) und startet dann `SettingsSetupUserProxyActivity` mit den Extras `intent_host_name`, `intent_chat_port`, `intent_media_port`, `intent_use_tls`, `source=deeplink`.

| Query | Parse | Standard |
|-------|-------|----------|
| `host` | string | none |
| `chatPort` | int | 443 |
| `mediaPort` | int | 587 |
| `chatTLS` | fehlend, `true` oder `1` ergibt true; jeder andere Wert false | true |

Der Import füllt nur den Setup-Screen vor; Speichern erfordert weiterhin den Nutzer (found). Der Handler der `DeepLinkActivity` wurde aus dem Bytecode gelesen (er ist nicht zu Java dekompiliert).

### 3.4 Nutzung durch chatd (found)

Schritt 12 (`C37151de.A02` case 12): Host = `domain` oder `ip`, Port = `chatPort`, TLS-Bit = `useChatTls`. Der Host läuft durch die normale Resolver-Kette (Abschnitt 6). Der Noise-Handshake läuft anschließend über diesen Socket (innerhalb von TLS bei `useChatTls`). Speichern des Proxys oder Umschalten des Schalters ruft `C11380Yq.A0C(...)` auf (erzwungener Reconnect) und löst `wam_user_proxy_set` aus.

Was der Proxy-Host mit dem Stream macht, ist clientseitig nicht sichtbar. Dass ein WhatsApp-Proxy-Relay rohe chatd-Bytes weiterleitet, ist inferred aus dem Fehlen jedes SOCKS- oder CONNECT-Austauschs.

### 3.5 Weitere Verbraucher (found)

| Verbraucher | Verhalten |
|-------------|-----------|
| Media-Upload / -Download | Flag **4073** macht die Media-Authority zu `proxy-host:mediaPort`; Health-Check in [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) |
| WAM-Upload-Routen | nativer Callback `jnidispatchO(0)` liefert `https://<proxy-host>:<mediaPort>/deidentified_telemetry`, wenn Flag **4074** an ist, plus `media_conn`-Hosts, wenn Flag **4020** an ist (siehe [WA_WAM_ANALYTICS.md](WA_WAM_ANALYTICS.md)) |
| Status-UI | `C42103IXl.A00`: 1 `Connecting…`, 2 `Connected`, 3 `Couldn't connect to proxy`, 4 `Disconnected`, 5 `No network`, sonst `Not Set`; Chat-Status gespeist vom Connection-Observer `C28890Cgr` |
| Psiphon-HTTP- und Tigon-Routen | deaktiviert, solange ein Nutzer-Proxy existiert (`C17420jn.A01`, `C12790bk`: `User proxy is set, skipping`) |
| Telemetrie | `WamUserProxySet {connectionSuccess, proxySet}` (`C43286IuN`), gesendet, wenn der Status 2 (true) oder 3 / 4 (false) wird, und bei Proxy-Änderungen |

---

## 4. Proxy-Service (Psiphon)

### 4.1 Modul und Bibliothek (found)

| Element | Wert |
|---------|------|
| Auslieferung | Voltron-Modul `proxyservice` plus ABI-Splits `proxyservice.config.{arm64_v8a,armeabi_v7a,x86,x86_64}` in `assets/app_modules.json`; Modul-Manifest listet `assets/proxyservice/libs.txt`, `assets/proxyservice/voltron_meta_embedded_server_entries` und `lib/<abi>/libgojni.so` pro Split |
| Java-Seite | `ca.psiphon.PsiphonTunnel` (Upstream-Bibliothek, `loadLibrary("gojni")`, `Psi.start`, `importPushPayload`), Host-Service `S6G` / `C42448IfJ`, Orchestrator `C12760bh`, Modul-Loader `C46743KbZ` |
| Modus | lokaler HTTP- und SOCKS-Proxy auf `localhost`; kein `VpnService` |
| Bibliotheksladen | Split-APK-Libs werden an die SoLoader-Quellen angehängt (`proxy_service/Added module SoSource`); der Log-String nennt `libproxyservice.so`, obwohl das Modul-Manifest nur `libgojni.so` enthält |

`libgojni.so` ist nicht in der APK enthalten (wird mit dem Modul ausgeliefert). Ihre Interna (Protokollmenge, Dialing, Verwendung von `AdditionalParameters`) sind unknown.

### 4.2 Konfigurationsressource `res/raw/proxyservice_config.json` (found)

Unverändert seit 2.26.34.4. Gelesen von `C42448IfJ.getPsiphonConfig`; der Format-Platzhalter `ClientVersion` wird mit dem App-versionCode gefüllt (`264100600`).

| Feld | Wert / Verwendung |
|------|-------------------|
| `SponsorId`, `PropagationChannelId`, `ClientPlatform` | opake 16-Hex-IDs; Plattform `meta` |
| `ServerEntrySignaturePublicKey`, `PushPayloadSignaturePublicKey`, `RemoteServerListSignaturePublicKey` | Base64-Keys mit 32 Byte, 32 Byte und 548 Byte (RSA-Größe); Verifikationsrolle aus den Namen inferred |
| `AdditionalParameters` | 5300 Base64-Zeichen (3975 Byte), opak, nicht dekodiert |
| `Emit*` (Client-Adresse, Diagnose-Notices, Netzwerkparameter), `DisableServerEntriesReporter` | alle true; speisen `onClientAddress`, `onDiagnosticMessage` |
| `ConnectionWorkerPoolSize`, `EstablishTunnelTimeoutSeconds` | 30, 0 |
| `TransformHostNameProbability`, `TLSFragmentClientHelloProbability` | 0.9, 0.5 (Anti-DPI-Parameter für die native Engine; Wirkung aus den Namen inferred) |
| `EnableLightProxy`, `LightProxyLimitDestinationAddresses` | true; `g.whatsapp.net` und `g-fallback.whatsapp.net` auf den Ports 80, 443, 5222 |

Laufzeitänderungen: Ein JSON-Objekt aus Flag **23879** (Pre-Login-Flag-Quelle) oder **23846** (reguläre Quelle) wird Key für Key über die Datei gemergt. Der PSL-Import-Modus (`C42448IfJ.A03`) erzwingt `DisableTunnels=true`, `EnableLightProxy=false`. Eingebettete Server-Einträge werden aus `assets/proxyservice/voltron_meta_embedded_server_entries` (oder dem Modul-Zip) gelesen, wenn Flag **23730** / **23731** an ist; Format: Big-Endian-int32-Anzahl, dann Anzahl-mal (int32-Länge, Bytes), jeder Eintrag hex-kodiert, einer pro Zeile (`C45480Jst.A01`).

Die beiden Flag-Quellen wählt `C17280jY.A00`: Kein eingeloggter Account oder nie aktualisierte AB-Props wählen das Pre-Login-Set. Der Service ist daher so ausgelegt, dass er auch vor der Registrierung funktioniert (inferred aus dem Prädikat).

### 4.3 Zustandsautomat (found, `AbstractC17380jj`, `C12760bh.A0B`)

| Code | Zustand | Gesetzt, wenn |
|------|---------|---------------|
| 0 / 1 / 2 | `uninitialized` / `not_in_region_allowlist` / `initializing` | initial / Region abgelehnt (Grund trägt die Region) / Start akzeptiert |
| 3 / 4 | `disabled` / `downloading_module` | Gate wie `vpn_in_use` / Voltron-Download läuft |
| 5 / 6 / 7 | `connecting` / `connected` / `disconnected` | `onConnecting` / `BmZ` (Ports bereit) / `BpU` |
| 8 / 9 | `download_failed` / `library_load_failed` | Modulinstallation fehlgeschlagen / `UnsatisfiedLinkError` |
| 10 | `shutdown` | `A04(reason)`, zum Beispiel `country_check`, `has_external_connectivity` |

Solange der Zustand 2, 4 oder 5 ist, wartet der HTTP-Stack auf den Proxy: `C17420jn.A05(true)` scharfschaltet einen Latch, dessen Timeout Flag **29362** ist (ms, Standard 0, nur wenn eingeloggt).

### 4.4 Start- und Stopp-Trigger (found)

| Trigger | Pfad |
|---------|------|
| Kaltstart des Message-Handlers | Default-Case von `C1W6` ruft `C12760bh.A03(…, null)` auf |
| App-Resume | `C18980me`, `C28912ChD` rufen `A0A()` auf (Tunnel erneut melden oder neu starten, wenn gestoppt) |
| Unblocking-Push mit `psl` | `C28912ChD.BIb`: `A03(…, C46772Kc2(psl))`; ohne `psl` nur `A0A()`, wenn `C17280jY.A02()` (Flags **28186** / **28189**) |

Start-Gates in `A03`:

1. Geräteregion = SIM-Land, sonst Netzwerkland, sonst Locale-Land (`AbstractC16510i9`); muss in der kleingeschriebenen, kommagetrennten Liste aus Flag **18724** (Pre-Login) / **18725** (`C17280jY.A03`) stehen. Andernfalls Zustand 1.
2. VPN-Check (`C17280jY.A01`, Flags **24068** / **24067** umgehen ihn): aktives VPN ergibt `vpn_in_use`, Zustand 3.
3. Flag **25452** bestimmt die Reihenfolge: an, laufen VPN-Gate und Prober nach dem Modul-Download; aus, davor.
4. Prober (Flag **18875**, `Q53`): HTTP-GET auf die URL aus Flag **18871** (Timeout **18874**, Versuche **18873**, Delay **18872**) über den normalen Stack. Jede HTTP-Antwort zählt als Erfolg (`KUI.CF3`): `Probe succeeded. Removing proxy from http and tigon`, `A0N` (externe Konnektivität) gesetzt, Proxy aus HTTP und Tigon entfernt, Shutdown-Check läuft.
5. Timeout des Start-Markers: Flag **25850** Sekunden (Annotation `init_timed_out`).

Stopp-Bedingungen:

| Bedingung | Ergebnis |
|-----------|----------|
| Von Psiphon gemeldete Client-Region nicht erlaubt (Flag **19067** an) | `country_check`, Shutdown |
| Prober erfolgreich (`A0N`) und gute direkte chatd-Session gemeldet (`A0O`), Flag **19613** an | `has_external_connectivity`, Shutdown |
| Gute direkte chatd-Session (`HandlerThreadC12340b0.A0e`: Service aktiv, Session länger als Flag **19372** (Standard 5, Einheit nicht aufgelöst), Route nicht `SOCKS_PROXY`) | `C12760bh.A09()` plus `C37061dV.A00()`: Proxy-Service wird für die Prozesslebensdauer ignoriert (`good_direct_chatd_session`) |
| Flag **19144** beim Start negativ | wird für die Prozesslebensdauer ignoriert (`abprop_config`) |

### 4.5 Integration mit chatd (found)

`C37061dV` (`ConnectionProxyConfig`) macht aus dem Broadcaster-Zustand die `ProxyServiceConfig`, die die Sequenz verwendet.

| Feld | Quelle |
|------|--------|
| `address` | `localhost`, wenn Heavy-Tunnel oder Light-Proxy oben ist, sonst leer |
| `port` | SOCKS-Port (`ProxyServiceBroadcaster.A01(true)`: heavy oder, wenn erlaubt, light) |
| `proxyServiceClientIP` | `onClientAddress` |
| `httpProxyHost`, `httpProxyPort` | `localhost` und der HTTP-Port, wenn ungleich null |
| `isLightProxy` | `isLightProxy()` (Light-Proxy oben, Heavy-Tunnel nicht verbunden) |

Regeln:

- Die Konfiguration wird verworfen, wenn Adresse oder Port leer ist (`updateProxyServiceConfig`) oder die von Psiphon gemeldete Region nicht erlaubt ist (`dropping due to unsupported client region`).
- `C37061dV.A02` (pro Verbindungsstart aufgerufen) liefert die Konfiguration nur, wenn die Geräteregion erlaubt ist, kein VPN aktiv ist, der Service nicht heruntergefahren ist und das Prozesslebensdauer-Ignore nicht gesetzt ist. Ist Flag **24645** an, wird die gecachte Konfiguration ohne diese Prüfungen verwendet.
- Der Connection-Thread kann bis zu Flag **19144** ms blockieren (`awaitProxyServiceConfig`) und vor Schritt 5 auf die Konfiguration warten, wenn noch keine existiert.
- Eine geänderte Konfiguration setzt das Reset-Flag und verbindet, wenn Flag **36306** an ist, mit dem Grund `proxy_service_update` neu.

Socket (`C37031dS.A01` Else-Zweig, Klasse `C48201yM` = `ConnectionSocketTunnel`):

```java
Socket s = new Socket(new Proxy(Proxy.Type.SOCKS, new InetSocketAddress(cfg.address, cfg.port)));
s.connect(InetSocketAddress.createUnresolved(host, port), 30000);   // g.whatsapp.net / g-fallback.whatsapp.net
c37861f7.A00(out, cfg.proxyServiceClientIP, port);                    // PROXY v2 header, skipped when flag 26334 is on
```

PROXY-v2-Header (`C37861f7`, Log `ProxyHeaderWriter`): 12-Byte-Signatur `0D 0A 0D 0A 00 0D 0A 51 55 49 54 0A`, `21`, Familie `11` (IPv4) oder `21` (IPv6), 16-Bit-Länge, Quelladresse (die Client-IP, Nulladresse, wenn sie nicht parst), Zieladresse null, Quellport 0, Zielport = Zielport, dann ein TLV `E8 00 01 50`. Die Bedeutung des TLV ist unknown. Ob der Edge den Header akzeptiert oder verlangt, ist allein aus seinem Vorhandensein inferred.

Verbindungs-Timing-Records pro Versuch verwenden die Stages `DNS`, `SOCKET`, `TLS` und die Stacks `PLATFORM`, `MNS`, `SOCKS_PROXY` (`C37811f2`, `EnumC37801f1`, `EnumC37821f3`).

### 4.6 Weitere Verbraucher des lokalen Proxys (found)

| Verbraucher | Klasse | Verhalten |
|-------------|--------|-----------|
| WA-HTTP-Stack | `C17420jn` (`WaHttpUrlConnectionWithProxyService`) | `Proxy(HTTP, localhost:httpPort)`; für Hosts, die auf `.whatsapp.net`, `.whatsapp.com`, `.fbcdn.net`, `.facebook.com`, `.instagram.com`, `.cdninstagram.com`, `.fbsbx.com` enden, werden `X-Forwarded-For: <client IP>` und `using-wa-proxy-service: 1` ergänzt |
| Tigon-(MNS-)Clients | `C12790bk` (`WATigonProxyObserver`) | `setInAppProxyHostAndPort`; übersprungen, wenn die Flags **26734** / **26735** (Tigon) oder **19905** / **19906** (WA-Proxy) an sind, ein Nutzer-Proxy existiert, `http.proxyHost` / `https.proxyHost` gesetzt ist oder der Probe schon erfolgreich war |
| VoIP | `CQO`, `JNIUtils.socksProxyPort` | `Voip.updateProxy(socksPort)`, wenn Flag **34525** es erlaubt (zweites Gate **36980** in `Buh()`) |
| WebView | `C39826HXw` | `PROXY_OVERRIDE`-Regel für die Domains in Flag **25539** |
| Network-Info-Log | `C12500bH` | `network_info_socks_proxy_active[...]`, `socks_proxy_connected` / `socks_proxy_disconnected` |

Tigon liest die System-Proxy-Properties auch selbst (`TigonHttpClientBase.setSystemProxyHostAndPort`) mit einem Direct-Fallback-Schalter; das ist unabhängig vom Service.

### 4.7 Diagnose (found)

`C42448IfJ.onDiagnosticMessage` parst `ConnectedServer:{json}` zu `candidate_number`, `protocol`, `client_replay_type` (`bootstrap`, `replay`, `non-replay`), `server_entry_source`. Marker 79499422 (Start), 79496324 (Connect), 79501264 (Prober, annotiert mit `has_vpn`, `has_system_http_proxy`).

---

## 5. Fallback-Endpunkte und Unblocking-Push

### 5.1 `<ib><fbip>` (found, `C40581l4`, `C36821d6.A02`)

`<ib><fbip>text</fbip></ib>`: Der Text wird an `,` gesplittet. Ein einzelner Eintrag `CLEAR` löscht die Datei. Jeder Eintrag hat sechs durch `|` getrennte Felder:

```
ip|port|ts|ttl|secure|override       exp = (ts + ttl) * 1000
```

| Feld | Verwendung |
|------|------------|
| `ip`, `port` | Endpunkt; Resolver-Code 4 (`FALLBACK`) |
| `ts`, `ttl` | Ablauf in ms; abgelaufene Einträge werden beim Laden entfernt |
| `secure` | TLS-Wrapper-Bit für den Endpunkt |
| `override` | Einträge mit true gehen zu Schritt 2 (vor `g.whatsapp.net` versucht), Einträge mit false zu Schritt 8 (nach `:80`) |

Persistenz: Datei `fbips` im Files-Verzeichnis der App, JSON `{"fbips":[{"ip","port","exp","secure","override","resolver"}]}` (`C36821d6.A00`). Ladefehler werden als `fallback-manager/load-error`, `save-error` gemeldet.

### 5.2 Fest codierte Tabelle (found)

`AbstractC47101wK`: 18 Hostnamen (`e1` bis `e16`, `g`, `v` unter `.whatsapp.net`, einfache Form und Form mit abschließendem Punkt), jeweils mit mehreren IPv4-Adressen. Verwendet von den Schritten 6 / 10 und vom fest codierten Resolver. Der Eintrag `v.whatsapp.net` wird in diesem Build von keinem Resolver verwendet (sein Resolver-Stub liefert null).

### 5.3 Unblocking-Push (found)

Push-Parsing (`CLl`, `PushPayloadParser/fromJSON`): `nt`-Werte `pre_reg`, `post_reg`, `voip_call_offer_1on1`, `voip_call_offer_group`, `call_terminate`, `message`, `group_message`, `wfac_ban`, `unblocking`. Geloggte Transporte: `ADM`, `GCM`, `FBNS`. Der Payload wird entschlüsselt (`PushEncryptionHelper`, Felder `payload`, `IV`, `tag`, Key aus `push:push_pkey_data`; Cipher AES-GCM aus den Feldnamen inferred).

`nt` = `unblocking` trägt (`UnblockingPushPayload`, `BQY`):

| JSON-Key | Feld | Behandlung |
|----------|------|------------|
| `fbips` | `fbips` | an `,` gesplittet, an `C36821d6.A02` übergeben (gleiches Format wie 5.1) |
| `unblocking_props` | `unblockingProps` | `version\|a\|b`; Version über 0 wird ignoriert; zwei Maps `id=value;id=value` geparst von `C27946CBo.A00`; `processPreChatdProps` wendet `config_code` / `config_value`-Paare an, `processPostChatdProps` die zweite Map (Zuordnung der Maps zu Phasen teilweise inferred) |
| `psl` | `proxyServerList` | Base64, mit `importPushPayload` in Psiphon importiert (`C46772Kc2`) |

`psl`-Import: Tunnel aktiv, direkt importiert; Tunnel inaktiv, ein temporäres Tunnel-Objekt startet im PSL-Import-Modus (`DisableTunnels`), importiert, stoppt (`Cold-importing push payload`). Übersprungen, wenn der Zustand `not_in_region_allowlist` ist. Die Auflösung von PSL als "push server list" ist inferred aus dem Key und dem Feld `PushPayloadSignaturePublicKey`.

---

## 6. DNS-Fallback-Kette (found)

`C36881dC.A03` befragt zuerst einen Cache (gespeist aus `fbips`, Einträge mit Ablauf; per Flag gesteuert) und geht dann vier Resolver der Reihe nach durch:

| # | Resolver | Resolver-Code | Hinweise |
|---|----------|---------------|----------|
| 0 | Stub für `v.whatsapp.net` | none | liefert null |
| 1 | Plattform- / MNS-DNS (`DnsCache/resolveViaMnsDns`) | 5 / 6 / 7 | ein Retry (`primary dns resolver failed, retrying...`) |
| 2 | sekundär: von Hand gebautes UDP-DNS zu 8.8.8.8 und 8.8.4.4 Port 53 (`QG1`) | 1 `GOOGLE` | reines UDP, kein DoH oder DoT |
| 3 | fest codierte Tabelle | 2 `HARDCODED` | `no hardcoded ips found for <host>`, wenn nichts vorhanden |

Flag **13545** (string) maskiert Resolver: `secondary` schaltet Hardcoded aus, `hardcoded` schaltet den UDP-Resolver aus, `none` schaltet beide aus (Bit-Logik in `C37151de.A01`). `EPERM`-Fehler werden erneut geworfen, wenn ein flag-gesteuerter Schalter gesetzt ist. Resolver-Codes erreichen `ClientPayload.dnsSource` (Noise-Report Abschnitt 6.5).

---

## 7. Registrierungs-Relay (found)

Umfang: Registrierungs-HTTP (`RegistrationHttpManager` = `K49`, `KotlinRegistrationBridge`, `RetryingHttpClient`) zu `https://v.whatsapp.net`. Es berührt chatd nicht.

### 7.1 Provider-Liste

Ressource `res/raw/domain_fronting_providers.tsv`, Spalten `name`, `url template`, `host`:

| Name | Template | Host |
|------|----------|------|
| `amazon` | `https://y9yrsygcg6.execute-api.us-east-1.amazonaws.com/s/s?_={PATH}&{QS}` | `y9yrsygcg6.execute-api.us-east-1.amazonaws.com` |
| `google` | `https://us-central1-propane-fusion-170222.cloudfunctions.net/s?_={PATH}&{QS}` | `us-central1-propane-fusion-170222.cloudfunctions.net` |

`C45421Jrl` lädt sie (Zeilen mit weniger als 3 Tokens loggen `domain-fronting-providers/load/bad-line`) und führt drei Listen: erreichbar (`A05`), ungetestet (`A06`), unerreichbar (`A04`). `K49.A0K` reicht sie in dieser Reihenfolge an jeden Registrierungsaufruf weiter.

### 7.2 Probe

`EULA.onCreate` startet den Probe höchstens alle 900000 ms (übersprungen, wenn `C06810Gk(930).A07()`, Bedeutung unaufgelöst): `https://v.whatsapp.net` öffnen; bei `IOException` (`DomainFrontingManager/probe-regd/cant connect to regd`) Provider mischen und jedes Template per GET mit `{PATH}=/` und leerem `{QS}` abrufen, 60 s Connect- und Read-Timeout, Header `Host` = Provider-Host und der App-User-Agent. HTTP 200 verschiebt einen Provider in die Liste der erreichbaren, jeder Fehler in die Liste der unerreichbaren (`domainFrontingProvider/cant reach`).

### 7.3 Versuchsstrategien (`RetryingHttpClient`, `C44407JaE`, `C44975Jk4`)

| Strategie | Request | Zustand in 2.26.41.6 |
|-----------|---------|----------------------|
| `ORIGINAL` | normale URL | immer Versuch 1 |
| `HOST` | gleiche URL mit einer gegebenen IP | Liste ist in diesem Build leer |
| `PROXY` | über eine gegebene Proxy-IP | Liste ist in diesem Build leer |
| `DOMAIN_FRONTING` | Template, bei dem `{PATH}` und `{QS}` durch den Original-Pfad und die rohe Query ersetzt sind; Header `Host` = Provider-Host, `X-Forwarded-Host` = Original-Host | bis zur Provider-Liste |

Reihenfolge: ORIGINAL, HOST-Einträge, PROXY-Einträge, Provider; höchstens 4 Versuche. URL-Host und `Host`-Header sind in beiden Templates gleich, daher ist es ein Cloud-Function-Relay (Request wird vom Provider an `X-Forwarded-Host` weitergeleitet, inferred) und kein klassisches SNI- / Host-Fronting.

Retry-Regel: Ergebnis-Codes 2, 5, 7, 12 sind nicht wiederholbar (`non-retryable error`), jeder andere Fehler setzt fort (`failed attempt N ... reason`); Code-Bedeutungen sind unaufgelöst. Verzögerung vor Versuch `n` > 1:

```
delay = clamp(r * (n*n - 1) * 4 * 1000, 0, 60000) ms      // r from a random double, assumed uniform in [0,1)
```

`RetryingHttpClient/executePostWithRetry/applying backoff`, `all retries exhausted`. Flags für Endpoint-Attestation-Payloads pro Pfad stehen in `AbstractC44143JQf` und haben mit dem Relaying nichts zu tun.

---

## 8. Tigon und DGW

| Element | Zustand | Tier |
|---------|---------|------|
| Tigon-HTTP (`TigonHttpClient`, MNS-Clients) | HTTP(S)-Client; übernimmt den Psiphon-HTTP-Proxy und die System-Proxy-Properties (Abschnitt 4.6); kein chatd-Transport | found |
| DGW-Client (`AbstractC20460pC`) | gebaut mit Domain `gateway.facebook.com`, Fallback-Konfiguration `null`, Personalization-Konfiguration `null` | found |
| `DGWFallbackConfig` | `isFallbackEnabled`, `fallbackDomain`, `numFailuresForFallback`, `fallbackReasons`, `isHardcodedIpFallbackEnabled`; null ergibt alles aus; der Java-Builder aktiviert es nie, native Defaults unbekannt | found / unknown |
| DGW-Nutzer | nur `WaFalcoStreamingRegistration` (Telemetrie-Streaming); siehe Noise-Report Abschnitt 13 | found |

Native Strings (`distribgw_tigon_tunnel`, `DGW_MQTTBYPASS`, Throttling- und Zero-Rating-Labels) beschreiben DGW-Interna. Nichts verbindet DGW mit der Wiederherstellung bei blockiertem chatd (inferred aus der Abwesenheit).

---

## 9. Verbindungsstatus-Tracking und Diagnose

| Element | Wo | Inhalt |
|---------|----|--------|
| Sequenz-Persistenz | Prefs `connection_sequence_state`, `connection_sequence_attempts`, `last_successful_connection_step`, `_host`, `_port` | Wiederaufsetzpunkt, HISTORY-Schritt (Noise-Report 2.2) |
| Records pro Versuch | `C37811f2` | Stage `DNS` / `SOCKET` / `TLS`, Stack `PLATFORM` / `MNS` / `SOCKS_PROXY`, Timing, Fehler |
| Payload | `ClientPayload.dnsSource`, `connectAttemptCount` | Resolver oder Route, die den Socket erzeugt hat |
| Proxy-Service | `C12760bh.A06()`, `A08()` | Zustandscode (4.3); `A08()` liefert `both`, `heavy`, `light` oder null |
| Nutzer-Proxy | `user_proxy_setting_pref`-Status, `wam_user_proxy_set` | UI und Analytics |
| Network-Info-Log | `C12500bH` | `network_info_is_vpn`, `_is_airplane`, `_is_data_saver`, `_is_cellular_enabled`, `_socks_proxy_active`, `socks_proxy_connected` / `_disconnected` |
| Log-Tags | `proxy_service/`, `ConnectionProxyConfig/`, `WaConnectivityProber/`, `WATigonProxyObserver/`, `ConnectionThread/Skipping sequence` | Gates und Zustandswechsel |

---

## 10. Zusammenspiel von Retry und Backoff

Der Backoff selbst (Fibonacci-Einheiten, 15-Minuten-Clamp, Alarme) steht in Noise-Report Abschnitt 10. Dieses Feature ergänzt:

| Wechselwirkung | Wirkung |
|----------------|---------|
| Nutzer-Proxy gespeichert, umgeschaltet, gelöscht | erzwungener Reconnect (`C11380Yq.A0C(...)`) |
| Proxy-Service-Konfiguration ändert sich | Sequenz-Reset; Reconnect `proxy_service_update`, wenn Flag **36306** an ist |
| Nutzer-Proxy gesetzt | einstufige Sequenz; jeder fehlgeschlagene Versuch kehrt zum Backoff des gesamten Connects zurück |
| Config-Wait / HTTP-Wait | Connection-Thread blockiert bis zu Flag **19144** ms vor Schritt 5; HTTP-Stack bis zu Flag **29362** ms, während der Service startet |
| Registrierung | eigenes Limit von 4 Versuchen und quadratische Verzögerung (Abschnitt 7.3), nicht mit chatd geteilt |

---

## 11. Feature-Flags (IDs wie im Code gelesen; Werte sind serverseitig)

| Id | Typ | Steuert |
|----|-----|---------|
| **2784** | bool | Nutzer-Proxy-Feature (Aktiviert-Zustand, Deep Link) |
| **4020**, **4073**, **4074** | bool | media_conn-Hosts an Native; Media über Nutzer-Proxy; Telemetrie-Route über Nutzer-Proxy |
| **18875** | bool | Konnektivitäts-Prober |
| **18871**-**18874** | string, ints | Probe-URL, Delay, Versuche, Timeout |
| **18724**, **18725** | string | erlaubte Regionen (Pre-Login- / reguläre Quelle) |
| **19067** | bool | Region-Re-Check beim Connect |
| **19613** | bool | Shutdown bei externer Konnektivität |
| **19144** | int | Config-Wait in ms; negativ ignoriert den Service für den Prozess |
| **19372** | int | Schwellwert für gute Session (Standard 5) |
| **19905**, **19906**, **26734**, **26735** | bool | WA-Proxy für HTTP / Tigon deaktivieren (Pre-Login / regulär) |
| **23630** | bool | Schritte 2-4 unter Proxy erlaubt (standardmäßig an deklariert, inferred) |
| **23730**, **23731** | bool | eingebettete Server-Einträge (Pre-Login / regulär) |
| **23846**, **23879** | JSON | Psiphon-Konfigurations-Override (regulär / Pre-Login) |
| **24067**, **24068** | bool | Service bei aktivem VPN erlauben |
| **24645** | bool | gecachte Service-Konfiguration ohne Gates verwenden |
| **25452** | bool | Reihenfolge von VPN-Gate und Prober relativ zum Modul-Download |
| **25539** | string | WebView-Proxy-Domain-Allowlist |
| **25850** | int | Timeout des Start-Markers in Sekunden |
| **26334** | bool | PROXY-v2-Header überspringen |
| **28186**, **28189** | bool | Service bei Push ohne `psl` fortsetzen |
| **29362** | int | HTTP-Wait-for-Proxy in ms |
| **34525**, **36980** | bool | SOCKS-Port an VoIP übergeben |
| **36306** | bool | Reconnect bei Proxy-Service-Update |
| **13545** | string | DNS-Resolver-Maske |

Flags für Chatd-Leiter und Keepalive (**20801**, **22916**, **30712**, **33512**, **7831**-**7834**, **15103**) stehen in Noise-Report Abschnitt 12.

---

## 12. Baileys (`baron-baileys-v2`, gegen den Quellcode geprüft)

| Aspekt | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| Transport | `ws`-WebSocket zu `wss://web.whatsapp.com/ws/chat` (`waWebSocketUrl`) | rohes TCP-Noise |
| Proxy | `config.agent` wird an `new WebSocket(url, { agent })` übergeben; Uploads verwenden `fetchAgent` | WhatsApp-Proxy-Relay, Psiphon-Tunnel |
| Fallback-Hosts | eine konfigurierbare URL | Leiter aus `g`, `g-fallback`, `eN`, Ports 443 / 5222 / 80 |
| `<ib><fbip>`, Unblocking-Push | nicht behandelt | behandelt |

```ts
const sock = makeWASocket({ agent: new SocksProxyAgent(proxyUrl), fetchAgent: new SocksProxyAgent(proxyUrl) })
```

| Warum es scheitert | Ursache | Fix |
|--------------------|---------|-----|
| Ein Android-WhatsApp-Proxy-Host weist Baileys ab | das Relay spricht rohes TCP-Noise auf dem Chat-Port (inferred); Baileys sendet ein WebSocket-Upgrade | HTTP- oder SOCKS-Proxy verwenden, der `web.whatsapp.com` erreicht |
| Keine Wiederherstellung nach einem Block | keine `fbip`-Behandlung, kein Push-Kanal | neuen `agent` oder neue URL liefern |

---

## 13. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|---------|-----|
| `Couldn't connect to proxy` | Nutzer-Proxy-Host nicht erreichbar oder falsche TLS-Einstellung | Host, `Chat port`, `Use TLS` prüfen; die Sequenz hat keinen direkten Fallback |
| `Enter a valid host` / `Enter a valid port` | Validierung in `K09` | Eingabe korrigieren |
| Proxy-Link tut nichts | Flag **2784** aus oder zusätzliche Pfadsegmente (`proxy_has_segments`) | clientseitig keiner |
| `proxy_service/Proxy service detected user region not in region allowlist.` | von Psiphon gemeldete Region durch die Liste aus Flag **18724** / **18725** abgelehnt | clientseitig keiner |
| Zustand `disabled`, Grund `vpn_in_use` | VPN aktiv, Flags **24067** / **24068** aus | VPN oder Flag deaktivieren |
| `RetryingHttpClient/executePostWithRetry/all retries exhausted` | alle Versuche fehlgeschlagen | warten; das Limit ist 4 |

---

## 14. Wichtige Unterscheidungen

| Nicht verwechseln | Detail |
|-------------------|--------|
| Nutzer-Proxy vs Proxy-Service | Nutzer-Proxy = gewählter Host, Schritt 12, terminal, Share-Link; Proxy-Service = servergesteuerter Psiphon-SOCKS-Tunnel für die Schritte 5 und 13; sie schließen sich gegenseitig aus |
| `C48201yM` vs Schritt 12 | `C48201yM` ist der SOCKS-Tunnel-Socket des Proxy-Service; Schritt 12 ist der Nutzer-Proxy und verwendet einen einfachen oder TLS-Socket |
| Light-Proxy vs Heavy-Tunnel | Light-Proxy ist auf die sechs aufgelisteten `g` / `g-fallback`-Ziele beschränkt; Heavy-Tunnel ist die volle Psiphon-Session |
| `fbip` vs `fbips`-Push vs `fallback_*` | `<ib><fbip>` und Push-`fbips` liefern chatd-Fallback-IPs; `fallback_hostname` / `fallback_ip*` sind `media_conn`-Attribute (Noise-Report Abschnitt 16) |
| Registrierungs-Relay vs chatd | die Provider-Liste speist nie die Chat-Sequenz |
| WhatsApp Proxy vs System-Proxy | der System-Proxy wird für chatd nicht gelesen |

---

## 15. Kompletter Ablauf

```
[Operator]  push nt=unblocking {fbips, unblocking_props, psl}   or   <ib><fbip>...</fbip></ib>
     │  fbips file updated ; props applied ; psl imported (temporary tunnel if inactive)
     ▼
[Client]  C12760bh gates: region (SIM > network > locale), no VPN, flags ; Voltron proxyservice download
     │  PsiphonTunnel.startTunneling(embedded entries) ─► localhost SOCKS + HTTP ports ─► state 6
     ▼
[ProxyServiceBroadcaster]  C37061dV builds ProxyServiceConfig ─► sequence reset ("proxy_service_update")
     │
     ├── user proxy set ─► step 12 only: host:chatPort (+TLS) ─► Noise ─► end (no direct fallback)
     ▼
[ConnectionThread]  steps 5, 13 (2-4 if flag 23630) ─► SOCKS CONNECT g / g-fallback (unresolved host)
     │  PROXY v2 header (client IP) ─► Noise handshake (Noise report section 4)
     ▼
[Server]  login success; session > threshold and route != SOCKS_PROXY ─► proxy ignored for the process
     ▼
[Failure]  timeout / socket error ─► next step ─► exhausted ─► Fibonacci backoff (Noise report section 10)

[Registration]  v.whatsapp.net ─► ORIGINAL ─► relay providers (Host + X-Forwarded-Host) ─► <= 4 attempts
```

---

## 16. Unbekanntes

| Element | Status |
|---------|--------|
| Jegliches Wire-Verhalten (Tunnel, Akzeptanz des PROXY v2, Relay-Antwort, Weiterleitung durch den WhatsApp Proxy) | nichts mitgeschnitten; kein Element ist `tested` |
| Interna von `libgojni.so`, Protokolle, `AdditionalParameters`, Inhalt der eingebetteten Einträge | natives Modul nicht in der APK |
| Inhalt der Liste erlaubter Regionen, Probe-URL, alle Flag-Werte | serverseitig |
| Bedeutung des TLV `E8 00 01 50` im PROXY-v2-Header | unknown |
| Zuordnung der beiden `unblocking_props`-Maps zu Pre- und Post-chatd-Phasen, Push-Cipher | teilweise inferred |
| Einheit von Flag **19372**, Code-Bedeutungen im Registrierungs-Retry (2, 5, 7, 12), Prädikat hinter `C06810Gk(930).A07()` | unaufgelöst |
| Eingehendes Routing von `wa.me/proxy` vor `DeepLinkActivity` (Manifest-Filter decken `wa.me` ab) | nicht über die Activity hinaus verfolgt |
| Ob die Java-seitige DGW-Fallback-Konfiguration nativ aus bleibt, und jeder rein native Fallback | unknown |
| Verhalten von Schritt-8-Einträgen in einem Lauf mit aktivem Psiphon | inferred direkt |
