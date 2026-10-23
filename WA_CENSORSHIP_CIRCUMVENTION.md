# WhatsApp Censorship Circumvention — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-23
**Scope:** Android connectivity fallbacks when chatd is blocked: user-configured WhatsApp Proxy (settings UI, storage, share link, chatd and media use), server-driven proxy service (Psiphon tunnel, Voltron module, region and VPN gates, SOCKS tunnel with PROXY v2 header), fallback IP list (`<ib><fbip>`, `fbips` file), unblocking push (`fbips`, `unblocking_props`, `psl`), DNS fallback chain, registration relay providers and retry strategies, Tigon and DGW roles, connection-state tracking and diagnostics, retry interplay, feature flags, absent mechanisms, Baileys comparison

---

## 1. What is present in this build

All statements come from static analysis of the decompiled APK; nothing was captured on the wire. Tiers: **found** = read in code or resources, **inferred** = deduced, **unknown** = not resolved. Obfuscated names are per-build and were re-resolved in 2.26.41.6. chatd transport, handshake, host ladder and backoff are in [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) and are not repeated here.

| Mechanism | State | Entry points | Tier |
|-----------|-------|--------------|------|
| WhatsApp Proxy (user-configured chat and media relay) | present, user UI, feature-flagged | `SettingsUserProxyActivity`, `SettingsSetupUserProxyActivity`, `C12660bX`, `C12690ba`, step 12 of the chatd sequence | found |
| Proxy service (Psiphon tunnel, Voltron module `proxyservice`) | present, server-driven, no user UI | `C12760bh` (orchestrator), `C42448IfJ` / `S6G`, `ca.psiphon.PsiphonTunnel`, `ProxyServiceBroadcaster` | found; native library not in the APK |
| Fallback IP list | present | `<ib><fbip>` in `C40581l4`, `C36821d6`, file `fbips` | found |
| Hard-coded host to IP table, host ladder | present | `AbstractC47101wK` (18 host names), `C37151de` | found |
| DNS fallback chain (platform / MNS, UDP to 8.8.8.8 and 8.8.4.4, hard-coded) | present | `C36881dC`, `QG1` | found |
| Unblocking push (`nt` = `unblocking`) | present | `CLl` parser, `C28139CLl`, `C28912ChD`, `C27946CBo` | found |
| Registration relay (cloud-function providers) and retry strategies | present, registration only | `res/raw/domain_fronting_providers.tsv`, `C45421Jrl`, `RetryingHttpClient` | found |
| Tigon / DGW as chatd fallback | not present | DGW fallback config exists but is built disabled | found |

Not present in this build (found as absence in the decompiled Java, manifest and resources; native code not inspected):

| Absent | Evidence |
|--------|----------|
| chatd over WebSocket, HTTP long-poll or MQTT | no `wss://` or `/ws/chat` literal in Java; `mqtt` only in analytics and DGW stream labels (see Noise report section 13) |
| Android `VpnService` | no service or `BIND_VPN_SERVICE` in the manifest; Psiphon runs in local-proxy mode |
| User-configurable SOCKS or HTTP-CONNECT proxy for chatd | step 12 builds a direct socket to `host:chatPort`, no proxy handshake |
| System proxy (`http.proxyHost`, `https.proxyHost`) for chatd | not read by the sequence or socket code; read only by Tigon and as a guard (section 4.6) |
| Domain fronting or relay for chatd | the provider list is consumed by the registration client only (section 7) |
| Tor, Snowflake, other pluggable transports | no code or resource found |

Points that decide the rest of the report:

- Two independent proxy mechanisms exist and never run together: the user proxy (step 12, terminal) and the Psiphon proxy service (SOCKS tunnel that replaces direct connects for a subset of steps). With a user proxy set, the service config is ignored (`ConnectionSequence/socketConfigForUserProxy/skipping socks proxy in favor of user proxy`).
- With a valid user proxy the sequence has exactly one target. Step 12 advances to 16 (exhausted); there is no fall back to direct hosts (found, `C37031dS.A0G`).
- `libgojni.so` is delivered inside the downloadable module. The APK holds the module manifest only; tunnel dialing, protocol selection and anti-DPI behaviour are unknown.

---

## 2. Placement in the chatd connection sequence

Step numbers are those of Noise report section 2.2. Source: `C37031dS.A0G`, `C37151de`, `C37061dV`.

| Condition | Effect |
|-----------|--------|
| Debug address set | step 1 only |
| Valid user proxy (enabled, host valid, flag **2784**) | step 0 goes to 12, which is terminal; Psiphon config ignored |
| No user proxy, Psiphon config present (`C37061dV.A00 != null`) | steps 5, 8, 13 are kept; 6, 7, 9, 10, 11, 14, 15 are skipped (`ConnectionThread/Skipping sequence N due to active proxy`); 2, 3, 4 are skipped unless flag **23630** is on |
| No user proxy, no Psiphon config | unmodified ladder: 2, 3, 4, 5, 8, 9, [15], 13, 14, 6, 10, 7, 11 |

The skip table is the packed switch in the `C37031dS.A0G` bytecode (steps 2 to 15 mapped to keep / skip / flag-dependent). Step 8 builds its config from an IP literal without the proxy config, so inside a proxy-active run it is kept but presumably connects directly (inferred). Steps 5 and 13 resolve through `C37151de.A03`: with a Psiphon config and no user proxy the returned socket config carries the `ProxyServiceConfig` (`C46661vS`) and an unresolved host name, so DNS happens at the tunnel exit (`DNSResolutionMethod` 7 `SOCKS_PROXY`, internal code 8 in `C37181dh`).

Step 0 order when no debug address exists (found; the decompiled Java branch for step 1 reads inverted, the bytecode confirms): user proxy, then server-supplied override entries (2), then configured host string (3), then 5.

---

## 3. WhatsApp Proxy (user-configured)

### 3.1 Settings entry and screens (found)

| Screen | Class | Content |
|--------|-------|---------|
| Settings > Storage and data > Proxy | `SettingsUserProxyActivity` (manifest `com.whatsapp.settings.ui.proxy.*`, not exported) | switch `Use proxy`, host line, chat and media status rows, share menu item, info text (`Only use a proxy if you're unable to connect to WhatsApp. Your IP address may be visible to the proxy provider…`, link `whatsapp-proxy`) |
| Set up proxy | `SettingsSetupUserProxyActivity` | host input, `Ports (Optional)` with `Chat port` (default shown as `Default` for 443), `Media port` (`Default` for 587), `Use TLS`, save button |
| Settings search entry | `C23869ARc` subclass `C215199Jq` | key `proxy` |
| Delete | long-click on the host row (`ViewOnLongClickListenerC46012K9h`, `Delete Proxy?`), action in `KZA` | clears host, resets media port 587 and TLS true, statuses 0, `proxy_enabled` false |

Validation: `K09.A01` (IP literal), `K09.A02` (host with optional `:port`, regex built from `JRQ.A02`); errors `Enter a valid host`, `Enter a valid port`. IPv6 parsing exists in `K09.A00`.

### 3.2 Storage (found, `C12660bX`, `C12690ba`)

SharedPreferences file `user_proxy_setting_pref`.

| Key | Type | Default | Use |
|-----|------|---------|-----|
| `proxy_enabled` | bool | false | switch state; effective only when flag **2784** is on (`C12690ba.A03`) |
| `proxy_ip_address` | string | none | `host:chatPort` (`ProxySetting.A04`); port parsed on read, default 443 |
| `proxy_media_port` | int | 587 | media relay port |
| `proxy_use_tls` | bool | true | TLS wrapper for the chat socket |
| `proxy_connection_status` | int | 0 | chat status shown in UI (section 3.5) |
| `proxy_media_connection_status` | int | 0 | media status shown in UI |

`ProxySetting` (`C45598Jv6`) = `domain`, `ip`, `chatPort`, `mediaPort`, `useChatTls`; a host that is an IP literal goes to `ip`, otherwise to `domain`. `C12660bX.A03()` returns it only when enabled, flag **2784** on and host or IP valid; this is the object the connection sequence receives.

### 3.3 Share and import link (found)

Share: menu item builds `https://wa.me/proxy?host=<host>&chatPort=<n>&mediaPort=<n>&chatTLS=<true|false>` with subject `WhatsApp Proxy` and text `Connect to WhatsApp using proxy. <url>`.

Import: `DeepLinkActivity` (type `DEEP_LINK_PROXY`, log prefix `PROXY:`) requires flag **2784**, has a rejection reason `proxy_has_segments` (condition inferred from the name), then starts `SettingsSetupUserProxyActivity` with extras `intent_host_name`, `intent_chat_port`, `intent_media_port`, `intent_use_tls`, `source=deeplink`.

| Query | Parse | Default |
|-------|-------|---------|
| `host` | string | none |
| `chatPort` | int | 443 |
| `mediaPort` | int | 587 |
| `chatTLS` | absent, `true` or `1` gives true; any other value false | true |

The import only pre-fills the setup screen; saving still needs the user (found). The `DeepLinkActivity` handler was read from bytecode (it is not decompiled to Java).

### 3.4 Use by chatd (found)

Step 12 (`C37151de.A02` case 12): host = `domain` or `ip`, port = `chatPort`, TLS bit = `useChatTls`. The host goes through the normal resolver chain (section 6). The Noise handshake then runs over this socket (inside TLS when `useChatTls`). Saving the proxy or toggling the switch calls `C11380Yq.A0C(...)` (forced reconnect) and fires `wam_user_proxy_set`.

What the proxy host does with the stream is not visible client-side. A WhatsApp Proxy relay forwarding raw chatd bytes is inferred from the absence of any SOCKS or CONNECT exchange.

### 3.5 Other consumers (found)

| Consumer | Behaviour |
|----------|-----------|
| Media upload / download | flag **4073** makes the media authority `proxy-host:mediaPort`; health check in [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) |
| WAM upload routes | native callback `jnidispatchO(0)` returns `https://<proxy-host>:<mediaPort>/deidentified_telemetry` when flag **4074** is on, plus `media_conn` hosts when flag **4020** is on (see [WA_WAM_ANALYTICS.md](WA_WAM_ANALYTICS.md)) |
| Status UI | `C42103IXl.A00`: 1 `Connecting…`, 2 `Connected`, 3 `Couldn't connect to proxy`, 4 `Disconnected`, 5 `No network`, other `Not Set`; chat status fed by connection observer `C28890Cgr` |
| Psiphon HTTP and Tigon routes | disabled while a user proxy exists (`C17420jn.A01`, `C12790bk`: `User proxy is set, skipping`) |
| Telemetry | `WamUserProxySet {connectionSuccess, proxySet}` (`C43286IuN`) sent when the status becomes 2 (true) or 3 / 4 (false) and on proxy changes |

---

## 4. Proxy service (Psiphon)

### 4.1 Module and library (found)

| Item | Value |
|------|-------|
| Delivery | Voltron module `proxyservice` plus per-ABI splits `proxyservice.config.{arm64_v8a,armeabi_v7a,x86,x86_64}` in `assets/app_modules.json`; module manifest lists `assets/proxyservice/libs.txt`, `assets/proxyservice/voltron_meta_embedded_server_entries`, and `lib/<abi>/libgojni.so` per split |
| Java side | `ca.psiphon.PsiphonTunnel` (upstream library, `loadLibrary("gojni")`, `Psi.start`, `importPushPayload`), host service `S6G` / `C42448IfJ`, orchestrator `C12760bh`, module loader `C46743KbZ` |
| Mode | local HTTP and SOCKS proxy on `localhost`; no `VpnService` |
| Library load | split APK libs appended to SoLoader sources (`proxy_service/Added module SoSource`); log string names `libproxyservice.so` although the module manifest has only `libgojni.so` |

`libgojni.so` is not present in the APK (delivered with the module). Its internals (protocol set, dialing, how `AdditionalParameters` is used) are unknown.

### 4.2 Config resource `res/raw/proxyservice_config.json` (found)

Unchanged since 2.26.34.4. Read by `C42448IfJ.getPsiphonConfig`; `ClientVersion` format placeholder is filled with the app versionCode (`264100600`).

| Field | Value / use |
|-------|-------------|
| `SponsorId`, `PropagationChannelId`, `ClientPlatform` | opaque 16-hex ids; platform `meta` |
| `ServerEntrySignaturePublicKey`, `PushPayloadSignaturePublicKey`, `RemoteServerListSignaturePublicKey` | 32-byte, 32-byte and 548-byte (RSA-sized) base64 keys; verification role inferred from names |
| `AdditionalParameters` | 5300 base64 chars (3975 bytes), opaque, not decoded |
| `Emit*` (client address, diagnostic notices, network parameters), `DisableServerEntriesReporter` | all true; feed `onClientAddress`, `onDiagnosticMessage` |
| `ConnectionWorkerPoolSize`, `EstablishTunnelTimeoutSeconds` | 30, 0 |
| `TransformHostNameProbability`, `TLSFragmentClientHelloProbability` | 0.9, 0.5 (anti-DPI knobs for the native engine; effect inferred from names) |
| `EnableLightProxy`, `LightProxyLimitDestinationAddresses` | true; `g.whatsapp.net` and `g-fallback.whatsapp.net` on ports 80, 443, 5222 |

Runtime changes: a JSON object from flag **23879** (pre-login flag source) or **23846** (regular source) is merged key by key over the file. PSL import mode (`C42448IfJ.A03`) forces `DisableTunnels=true`, `EnableLightProxy=false`. Embedded server entries are read from `assets/proxyservice/voltron_meta_embedded_server_entries` (or the module zip) when flag **23730** / **23731** is on; format: big-endian int32 count, then count times (int32 length, bytes), each entry hex-encoded one per line (`C45480Jst.A01`).

The two flag sources are chosen by `C17280jY.A00`: no logged-in account, or AB props never refreshed, selects the pre-login set. The service is therefore designed to work before registration too (inferred from the predicate).

### 4.3 State machine (found, `AbstractC17380jj`, `C12760bh.A0B`)

| Code | State | Set when |
|------|-------|----------|
| 0 / 1 / 2 | `uninitialized` / `not_in_region_allowlist` / `initializing` | initial / region rejected (reason carries the region) / start accepted |
| 3 / 4 | `disabled` / `downloading_module` | gate such as `vpn_in_use` / Voltron download running |
| 5 / 6 / 7 | `connecting` / `connected` / `disconnected` | `onConnecting` / `BmZ` (ports ready) / `BpU` |
| 8 / 9 | `download_failed` / `library_load_failed` | module install failure / `UnsatisfiedLinkError` |
| 10 | `shutdown` | `A04(reason)`, for example `country_check`, `has_external_connectivity` |

While the state is 2, 4 or 5 the HTTP stack waits for the proxy: `C17420jn.A05(true)` arms a latch whose timeout is flag **29362** (ms, default 0, only when logged in).

### 4.4 Start and stop triggers (found)

| Trigger | Path |
|---------|------|
| Cold start of the message handler | `C1W6` default case calls `C12760bh.A03(…, null)` |
| App resume | `C18980me`, `C28912ChD` call `A0A()` (re-notify tunnel, or restart when stopped) |
| Unblocking push with `psl` | `C28912ChD.BIb`: `A03(…, C46772Kc2(psl))`; without `psl`, only `A0A()` when `C17280jY.A02()` (flags **28186** / **28189**) |

Start gates in `A03`:

1. Device region = SIM country, else network country, else locale country (`AbstractC16510i9`); must be in the lower-case comma list from flag **18724** (pre-login) / **18725** (`C17280jY.A03`). Otherwise state 1.
2. VPN check (`C17280jY.A01`, flags **24068** / **24067** bypass it): VPN active gives `vpn_in_use`, state 3.
3. Flag **25452** decides ordering: on, the VPN gate and prober run after the module is downloaded; off, before.
4. Prober (flag **18875**, `Q53`): HTTP GET of the URL in flag **18871** (timeout **18874**, attempts **18873**, delay **18872**) over the normal stack. Any HTTP response counts as success (`KUI.CF3`): `Probe succeeded. Removing proxy from http and tigon`, `A0N` (external connectivity) set, proxy cleared from HTTP and Tigon, shutdown check runs.
5. Start-marker timeout: flag **25850** seconds (`init_timed_out` annotation).

Stop conditions:

| Condition | Result |
|-----------|--------|
| Psiphon-reported client region not allowed (flag **19067** on) | `country_check`, shutdown |
| Prober succeeded (`A0N`) and a good direct chatd session reported (`A0O`), flag **19613** on | `has_external_connectivity`, shutdown |
| Good direct chatd session (`HandlerThreadC12340b0.A0e`: service active, session longer than flag **19372** (default 5, unit unresolved), route not `SOCKS_PROXY`) | `C12760bh.A09()` plus `C37061dV.A00()`: proxy service ignored for the process lifetime (`good_direct_chatd_session`) |
| Flag **19144** negative at start | ignored for the process lifetime (`abprop_config`) |

### 4.5 Integration with chatd (found)

`C37061dV` (`ConnectionProxyConfig`) turns broadcaster state into the `ProxyServiceConfig` the sequence uses.

| Field | Source |
|-------|--------|
| `address` | `localhost` when heavy tunnel or light proxy is up, else empty |
| `port` | SOCKS port (`ProxyServiceBroadcaster.A01(true)`: heavy, or light when allowed) |
| `proxyServiceClientIP` | `onClientAddress` |
| `httpProxyHost`, `httpProxyPort` | `localhost` and the HTTP port when non-zero |
| `isLightProxy` | `isLightProxy()` (light proxy up, heavy tunnel not connected) |

Rules:

- Config is dropped when address or port is empty (`updateProxyServiceConfig`), or the Psiphon-reported region is not allowed (`dropping due to unsupported client region`).
- `C37061dV.A02` (called per connection start) returns the config only when the device region is allowed, no VPN is active, the service is not shut down and the process-lifetime ignore is unset. When flag **24645** is on the cached config is used without these checks.
- The connection thread may block for flag **19144** ms (`awaitProxyServiceConfig`) waiting for the config before step 5 when no config exists yet.
- A changed config sets the reset flag and, when flag **36306** is on, reconnects with reason `proxy_service_update`.

Socket (`C37031dS.A01` else-branch, class `C48201yM` = `ConnectionSocketTunnel`):

```java
Socket s = new Socket(new Proxy(Proxy.Type.SOCKS, new InetSocketAddress(cfg.address, cfg.port)));
s.connect(InetSocketAddress.createUnresolved(host, port), 30000);   // g.whatsapp.net / g-fallback.whatsapp.net
c37861f7.A00(out, cfg.proxyServiceClientIP, port);                    // PROXY v2 header, skipped when flag 26334 is on
```

PROXY v2 header (`C37861f7`, log `ProxyHeaderWriter`): 12-byte signature `0D 0A 0D 0A 00 0D 0A 51 55 49 54 0A`, `21`, family `11` (IPv4) or `21` (IPv6), 16-bit length, source address (the client IP, zero address when it does not parse), zero destination address, source port 0, destination port = target port, then one TLV `E8 00 01 50`. The TLV meaning is unknown. Whether the edge accepts or requires the header is inferred from its presence only.

Connection timing records per attempt use stages `DNS`, `SOCKET`, `TLS` and stacks `PLATFORM`, `MNS`, `SOCKS_PROXY` (`C37811f2`, `EnumC37801f1`, `EnumC37821f3`).

### 4.6 Other consumers of the local proxy (found)

| Consumer | Class | Behaviour |
|----------|-------|-----------|
| WA HTTP stack | `C17420jn` (`WaHttpUrlConnectionWithProxyService`) | `Proxy(HTTP, localhost:httpPort)`; for hosts ending `.whatsapp.net`, `.whatsapp.com`, `.fbcdn.net`, `.facebook.com`, `.instagram.com`, `.cdninstagram.com`, `.fbsbx.com` adds `X-Forwarded-For: <client IP>` and `using-wa-proxy-service: 1` |
| Tigon (MNS) clients | `C12790bk` (`WATigonProxyObserver`) | `setInAppProxyHostAndPort`; skipped when flags **26734** / **26735** (Tigon) or **19905** / **19906** (WA proxy) are on, a user proxy exists, `http.proxyHost` / `https.proxyHost` is set, or the probe already succeeded |
| VoIP | `CQO`, `JNIUtils.socksProxyPort` | `Voip.updateProxy(socksPort)` when flag **34525** allows (second gate **36980** in `Buh()`) |
| WebView | `C39826HXw` | `PROXY_OVERRIDE` rule for the domains in flag **25539** |
| Network info log | `C12500bH` | `network_info_socks_proxy_active[...]`, `socks_proxy_connected` / `socks_proxy_disconnected` |

Tigon also reads the system proxy properties itself (`TigonHttpClientBase.setSystemProxyHostAndPort`) with a direct-fallback switch; this is independent of the service.

### 4.7 Diagnostics (found)

`C42448IfJ.onDiagnosticMessage` parses `ConnectedServer:{json}` into `candidate_number`, `protocol`, `client_replay_type` (`bootstrap`, `replay`, `non-replay`), `server_entry_source`. Markers 79499422 (start), 79496324 (connect), 79501264 (prober, annotated `has_vpn`, `has_system_http_proxy`).

---

## 5. Fallback endpoints and unblocking push

### 5.1 `<ib><fbip>` (found, `C40581l4`, `C36821d6.A02`)

`<ib><fbip>text</fbip></ib>`: text is split on `,`. A single entry `CLEAR` deletes the file. Each entry is six `|`-separated fields:

```
ip|port|ts|ttl|secure|override       exp = (ts + ttl) * 1000
```

| Field | Use |
|-------|-----|
| `ip`, `port` | endpoint; resolver code 4 (`FALLBACK`) |
| `ts`, `ttl` | expiry in ms; expired entries are removed on load |
| `secure` | TLS wrapper bit for the endpoint |
| `override` | true entries go to step 2 (tried before `g.whatsapp.net`), false entries to step 8 (after `:80`) |

Persistence: file `fbips` in the app files dir, JSON `{"fbips":[{"ip","port","exp","secure","override","resolver"}]}` (`C36821d6.A00`). Load errors are reported as `fallback-manager/load-error`, `save-error`.

### 5.2 Hard-coded table (found)

`AbstractC47101wK`: 18 host names (`e1` to `e16`, `g`, `v` under `.whatsapp.net`, plain and trailing-dot forms), each with several IPv4 addresses. Used by steps 6 / 10 and the hard-coded resolver. The `v.whatsapp.net` entry is not used by any resolver in this build (its resolver stub returns null).

### 5.3 Unblocking push (found)

Push parsing (`CLl`, `PushPayloadParser/fromJSON`): `nt` values `pre_reg`, `post_reg`, `voip_call_offer_1on1`, `voip_call_offer_group`, `call_terminate`, `message`, `group_message`, `wfac_ban`, `unblocking`. Transports logged: `ADM`, `GCM`, `FBNS`. The payload is decrypted (`PushEncryptionHelper`, fields `payload`, `IV`, `tag`, key from `push:push_pkey_data`; cipher inferred AES-GCM from the field names).

`nt` = `unblocking` carries (`UnblockingPushPayload`, `BQY`):

| JSON key | Field | Handling |
|----------|-------|----------|
| `fbips` | `fbips` | split on `,`, passed to `C36821d6.A02` (same format as 5.1) |
| `unblocking_props` | `unblockingProps` | `version\|a\|b`; version above 0 is ignored; two `id=value;id=value` maps parsed by `C27946CBo.A00`; `processPreChatdProps` applies `config_code` / `config_value` pairs, `processPostChatdProps` the second map (assignment of maps to phases partly inferred) |
| `psl` | `proxyServerList` | base64, imported into Psiphon with `importPushPayload` (`C46772Kc2`) |

`psl` import: tunnel active, imported directly; tunnel inactive, a temporary tunnel object starts in PSL import mode (`DisableTunnels`), imports, stops (`Cold-importing push payload`). Skipped when the state is `not_in_region_allowlist`. Expansion of PSL as "push server list" is inferred from the key and the `PushPayloadSignaturePublicKey` field.

---

## 6. DNS fallback chain (found)

`C36881dC.A03` first consults a cache (fed by `fbips`, entries with expiry; gated by a flag), then walks four resolvers in order:

| # | Resolver | Resolver code | Notes |
|---|----------|---------------|-------|
| 0 | stub for `v.whatsapp.net` | none | returns null |
| 1 | platform / MNS DNS (`DnsCache/resolveViaMnsDns`) | 5 / 6 / 7 | retries once (`primary dns resolver failed, retrying...`) |
| 2 | secondary: hand-built UDP DNS to 8.8.8.8 and 8.8.4.4 port 53 (`QG1`) | 1 `GOOGLE` | plain UDP, no DoH or DoT |
| 3 | hard-coded table | 2 `HARDCODED` | `no hardcoded ips found for <host>` when missing |

Flag **13545** (string) masks resolvers: `secondary` turns hard-coded off, `hardcoded` turns the UDP resolver off, `none` turns both off (bit logic in `C37151de.A01`). `EPERM` errors are rethrown when a flag-controlled switch is set. Resolver codes reach `ClientPayload.dnsSource` (Noise report section 6.5).

---

## 7. Registration relay (found)

Scope: registration HTTP (`RegistrationHttpManager` = `K49`, `KotlinRegistrationBridge`, `RetryingHttpClient`) to `https://v.whatsapp.net`. It does not touch chatd.

### 7.1 Provider list

Resource `res/raw/domain_fronting_providers.tsv`, columns `name`, `url template`, `host`:

| Name | Template | Host |
|------|----------|------|
| `amazon` | `https://y9yrsygcg6.execute-api.us-east-1.amazonaws.com/s/s?_={PATH}&{QS}` | `y9yrsygcg6.execute-api.us-east-1.amazonaws.com` |
| `google` | `https://us-central1-propane-fusion-170222.cloudfunctions.net/s?_={PATH}&{QS}` | `us-central1-propane-fusion-170222.cloudfunctions.net` |

`C45421Jrl` loads it (lines with fewer than 3 tokens log `domain-fronting-providers/load/bad-line`) and keeps three lists: reachable (`A05`), untested (`A06`), unreachable (`A04`). `K49.A0K` hands them to every registration call in that order.

### 7.2 Probe

`EULA.onCreate` starts the probe at most every 900000 ms (skipped when `C06810Gk(930).A07()`, meaning unresolved): open `https://v.whatsapp.net`; on `IOException` (`DomainFrontingManager/probe-regd/cant connect to regd`) shuffle providers and GET each template with `{PATH}=/` and `{QS}` empty, 60 s connect and read timeout, headers `Host` = provider host and the app user agent. HTTP 200 moves a provider to the reachable list, any failure to the unreachable list (`domainFrontingProvider/cant reach`).

### 7.3 Attempt strategies (`RetryingHttpClient`, `C44407JaE`, `C44975Jk4`)

| Strategy | Request | State in 2.26.41.6 |
|----------|---------|--------------------|
| `ORIGINAL` | normal URL | always attempt 1 |
| `HOST` | same URL with a given IP | list is empty in this build |
| `PROXY` | via a given proxy IP | list is empty in this build |
| `DOMAIN_FRONTING` | template with `{PATH}` and `{QS}` replaced by the original path and raw query; headers `Host` = provider host, `X-Forwarded-Host` = original host | up to the provider list |

Order: ORIGINAL, HOST entries, PROXY entries, providers; at most 4 attempts. The URL host and the `Host` header are equal in both templates, so this is a cloud-function relay (request forwarded by the provider to `X-Forwarded-Host`, inferred) rather than classic SNI / Host fronting.

Retry rule: result codes 2, 5, 7, 12 are non-retryable (`non-retryable error`), every other failure continues (`failed attempt N ... reason`); code meanings are unresolved. Delay before attempt `n` > 1:

```
delay = clamp(r * (n*n - 1) * 4 * 1000, 0, 60000) ms      // r from a random double, assumed uniform in [0,1)
```

`RetryingHttpClient/executePostWithRetry/applying backoff`, `all retries exhausted`. Endpoint attestation payload flags per path are in `AbstractC44143JQf` and are unrelated to relaying.

---

## 8. Tigon and DGW

| Item | State | Tier |
|------|-------|------|
| Tigon HTTP (`TigonHttpClient`, MNS clients) | HTTP(S) client; takes the Psiphon HTTP proxy and the system proxy properties (section 4.6); not a chatd transport | found |
| DGW client (`AbstractC20460pC`) | built with domain `gateway.facebook.com`, fallback config `null`, personalization config `null` | found |
| `DGWFallbackConfig` | `isFallbackEnabled`, `fallbackDomain`, `numFailuresForFallback`, `fallbackReasons`, `isHardcodedIpFallbackEnabled`; null yields all-off; the Java builder never enables it, native defaults unknown | found / unknown |
| DGW users | `WaFalcoStreamingRegistration` (telemetry streaming) only; see Noise report section 13 | found |

Native strings (`distribgw_tigon_tunnel`, `DGW_MQTTBYPASS`, throttling and zero-rating labels) describe DGW internals. Nothing links DGW to blocked-chatd recovery (inferred from absence).

---

## 9. Connection-state tracking and diagnostics

| Item | Where | Content |
|------|-------|---------|
| Sequence persistence | prefs `connection_sequence_state`, `connection_sequence_attempts`, `last_successful_connection_step`, `_host`, `_port` | resume point, HISTORY step (Noise report 2.2) |
| Per-attempt records | `C37811f2` | stage `DNS` / `SOCKET` / `TLS`, stack `PLATFORM` / `MNS` / `SOCKS_PROXY`, timing, error |
| Payload | `ClientPayload.dnsSource`, `connectAttemptCount` | resolver or route that produced the socket |
| Proxy service | `C12760bh.A06()`, `A08()` | state code (4.3); `A08()` returns `both`, `heavy`, `light` or null |
| User proxy | `user_proxy_setting_pref` statuses, `wam_user_proxy_set` | UI and analytics |
| Network info log | `C12500bH` | `network_info_is_vpn`, `_is_airplane`, `_is_data_saver`, `_is_cellular_enabled`, `_socks_proxy_active`, `socks_proxy_connected` / `_disconnected` |
| Log tags | `proxy_service/`, `ConnectionProxyConfig/`, `WaConnectivityProber/`, `WATigonProxyObserver/`, `ConnectionThread/Skipping sequence` | gates and state changes |

---

## 10. Retry and backoff interplay

Backoff itself (Fibonacci units, 15-minute clamp, alarms) is in Noise report section 10. This feature adds:

| Interaction | Effect |
|-------------|--------|
| User proxy saved, toggled, deleted | forced reconnect (`C11380Yq.A0C(...)`) |
| Proxy-service config changes | sequence reset; reconnect `proxy_service_update` when flag **36306** is on |
| User proxy set | one-step sequence; every failed attempt returns to the whole-connect backoff |
| Config wait / HTTP wait | connection thread blocks up to flag **19144** ms before step 5; HTTP stack up to flag **29362** ms while the service starts |
| Registration | own limit of 4 attempts and quadratic delay (section 7.3), not shared with chatd |

---

## 11. Feature flags (ids as read in code; values are server-side)

| Id | Type | Controls |
|----|------|----------|
| **2784** | bool | user proxy feature (enabled state, deep link) |
| **4020**, **4073**, **4074** | bool | media_conn hosts to native; media via user proxy; telemetry route via user proxy |
| **18875** | bool | connectivity prober |
| **18871**-**18874** | string, ints | probe URL, delay, attempts, timeout |
| **18724**, **18725** | string | allowed regions (pre-login / regular source) |
| **19067** | bool | region re-check on connect |
| **19613** | bool | shutdown on external connectivity |
| **19144** | int | config wait ms; negative ignores service for the process |
| **19372** | int | good-session threshold (default 5) |
| **19905**, **19906**, **26734**, **26735** | bool | disable WA proxy for HTTP / Tigon (pre-login / regular) |
| **23630** | bool | steps 2-4 allowed under proxy (declared on by default, inferred) |
| **23730**, **23731** | bool | embedded server entries (pre-login / regular) |
| **23846**, **23879** | JSON | Psiphon config override (regular / pre-login) |
| **24067**, **24068** | bool | allow service while a VPN is active |
| **24645** | bool | use cached service config without gates |
| **25452** | bool | order of VPN gate and prober relative to module download |
| **25539** | string | WebView proxy domain allowlist |
| **25850** | int | start-marker timeout in seconds |
| **26334** | bool | skip PROXY v2 header |
| **28186**, **28189** | bool | resume service on push without `psl` |
| **29362** | int | HTTP wait-for-proxy ms |
| **34525**, **36980** | bool | pass SOCKS port to VoIP |
| **36306** | bool | reconnect on proxy-service update |
| **13545** | string | DNS resolver mask |

Chatd ladder and keepalive flags (**20801**, **22916**, **30712**, **33512**, **7831**-**7834**, **15103**) are in Noise report section 12.

---

## 12. Baileys (`baron-baileys-v2`, checked against its source)

| Aspect | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| Transport | `ws` WebSocket to `wss://web.whatsapp.com/ws/chat` (`waWebSocketUrl`) | raw TCP Noise |
| Proxy | `config.agent` passed to `new WebSocket(url, { agent })`; uploads use `fetchAgent` | WhatsApp Proxy relay, Psiphon tunnel |
| Fallback hosts | one configurable URL | ladder of `g`, `g-fallback`, `eN`, ports 443 / 5222 / 80 |
| `<ib><fbip>`, unblocking push | not handled | handled |

```ts
const sock = makeWASocket({ agent: new SocksProxyAgent(proxyUrl), fetchAgent: new SocksProxyAgent(proxyUrl) })
```

| Why it fails | Cause | Fix |
|--------------|-------|-----|
| An Android WhatsApp Proxy host rejects Baileys | the relay speaks raw TCP Noise on the chat port (inferred); Baileys sends a WebSocket upgrade | use an HTTP or SOCKS proxy that reaches `web.whatsapp.com` |
| No recovery after a block | no `fbip` handling, no push channel | supply a new `agent` or URL |

---

## 13. Error cases

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Couldn't connect to proxy` | user proxy host unreachable or wrong TLS setting | check host, `Chat port`, `Use TLS`; the sequence has no direct fallback |
| `Enter a valid host` / `Enter a valid port` | validation in `K09` | correct input |
| Proxy link does nothing | flag **2784** off, or extra path segments (`proxy_has_segments`) | none client-side |
| `proxy_service/Proxy service detected user region not in region allowlist.` | Psiphon-reported region rejected by flag **18724** / **18725** list | none client-side |
| State `disabled`, reason `vpn_in_use` | VPN active, flags **24067** / **24068** off | disable VPN or flag |
| `RetryingHttpClient/executePostWithRetry/all retries exhausted` | all attempts failed | wait; limit is 4 |

---

## 14. Key distinctions

| Do not confuse | Detail |
|----------------|--------|
| User proxy vs proxy service | user proxy = chosen host, step 12, terminal, share link; proxy service = server-driven Psiphon SOCKS tunnel for steps 5 and 13; they exclude each other |
| `C48201yM` vs step 12 | `C48201yM` is the SOCKS tunnel socket of the proxy service; step 12 is the user proxy and uses a plain or TLS socket |
| Light proxy vs heavy tunnel | light proxy is limited to the six listed `g` / `g-fallback` destinations; heavy tunnel is the full Psiphon session |
| `fbip` vs `fbips` push vs `fallback_*` | `<ib><fbip>` and push `fbips` give chatd fallback IPs; `fallback_hostname` / `fallback_ip*` are `media_conn` attributes (Noise report section 16) |
| Registration relay vs chatd | the provider list never feeds the chat sequence |
| WhatsApp Proxy vs system proxy | the system proxy is not read for chatd |

---

## 15. Complete flow

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

## 16. Unknowns

| Item | Status |
|------|--------|
| Any wire behaviour (tunnel, PROXY v2 acceptance, relay response, WhatsApp Proxy forwarding) | nothing captured; no item is `tested` |
| `libgojni.so` internals, protocols, `AdditionalParameters`, embedded entries content | native module not in the APK |
| Allowed-region list contents, probe URL, all flag values | server-side |
| TLV `E8 00 01 50` meaning in the PROXY v2 header | unknown |
| Mapping of the two `unblocking_props` maps to pre and post chatd phases, push cipher | partly inferred |
| Unit of flag **19372**, code meanings in registration retry (2, 5, 7, 12), predicate behind `C06810Gk(930).A07()` | unresolved |
| Inbound `wa.me/proxy` routing before `DeepLinkActivity` (manifest filters cover `wa.me`) | not traced beyond the activity |
| Whether the Java-side DGW fallback config stays off natively, and any native-only fallback | unknown |
| Behaviour of step 8 entries inside a Psiphon-active run | inferred direct |
