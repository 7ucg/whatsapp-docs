# WhatsApp Client Integrity — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-17
**Scope:** Android client integrity and attestation — Keystore key attestation ("blacknoise"), Play Integrity (Java standard API and native classic API), WASafe native token library, `integrity_payload` / `keystore_attestation` stanzas, registration `gpia` parameter, app-signature self-check, install-source flag, root / emulator / modded-client telemetry (`wam_daily`), what is gated vs only reported, what stays unknown

---

## 1. What "client integrity" is in this build

No single gate exists. The client produces several independent proofs and signals; every one of them is created on the device and sent to the server. No client-side code was found that refuses to run on a modified, rooted or re-signed client. All statements are static analysis of the decompiled APK (`versionCode 264100600`). Tiers: **found** = read in code, **inferred** = deduced, **unknown** = not resolvable statically.

Obfuscated names are per build and were re-resolved from stable strings in 2.26.41.6.

| Mechanism | Produces | Sent as | Server use |
|-----------|----------|---------|-----------|
| Keystore key attestation, internal log tag `blacknoise` (`C25730yT`) | DER certificate chain of an `AndroidKeyStore` EC key with attestation challenge | `<ib><keystore_attestation>` stanza; registration-time hand-off to native; passkey and companion-pairing paths | unknown (not observable) |
| Play Integrity, Java standard API (`C45007Jkc`) | Standard Integrity token (`gpia`) | HTTP registration param `gpia`; companion pairing ("md-pairing") token | unknown |
| Play Integrity, native classic API (`libwhatsapp.so`, `WAJIntegrityGpiaStatusRequest`) | Classic Integrity token via JNI | `<ib><integrity_payload>` (Java sink found; link to native producer inferred) | unknown |
| WASafe (`libwasafe.so`, `libwasafedeps.so`) | ECIES-style encrypted blob of caller-supplied data, base64 | unknown sink | unknown |
| App signature self-check (`AbstractC38241gg`, `C27965CCj`) | 0/1 value | WAM common attribute **6251** | unknown |
| Install source flag (`CHH`) | boolean `com.android.vending` installer | WAM attributes `install_source_official`, **10255** | unknown |
| Device-state flags (`Cdt` → `C0Fp`) | `is_rooted`, `is_genymotion`, `is_monkeyrunner_running`, `is_using_custom_rom`, `is_whatsapp_plus_user` | WAM event `wam_daily` | unknown |
| Support diagnostics (`C00L.A0F`) | "rted" tag | contact-us / debug report strings | support only |

Not integrity attestation, do not confuse (see 11): `com.whatsapp.integrityai` (on-device scam detection), `bizintegritysignals`, WFAC ban UI (`com.whatsapp.waffle.wfac`), account linking (`com.whatsapp.waffle`).

| Entity | 2.26.41.6 name | Role |
|--------|----------------|------|
| Keystore attestation | `C25730yT` | key pair, cert chain, signing (`A00`/`A01` alias, `A02` generate, `A03` chain, `A07` sign) |
| Attestation mode enum | `C02U` | `C02U.A00` = dynamic, `C02U.A01` = static |
| Stanza sender runnable | `RunnableC48591z1` case 3 via `C41141ly` | sends `keystore_attestation` |
| Connected handler | `A01` in the connection handler (`smali/X/0Yq`) | schedules `sendKeystoreAttestation` |
| Registration-time work | `C25810yb`, `KZ2` case 39, `K49.A0s` | static attestation to native, tag `regtime_ka` |
| Companion pre-warm | `H1K` (attestation), `H1J` (Play Integrity) | cache chain / token for pairing |
| Play Integrity wrapper | `C45007Jkc` | standard-API prepare + request |
| Registration HTTP | `K49` | adds `gpia` to request params |
| JNI bridge | `com.whatsapp.wamsys.JniBridge` | `sendAttestationResult`, `jnidispatch*` callbacks, `wsafeplatform_context` |
| Signature gate | `AbstractC38241gg` | version window + SHA-1 of signing cert |
| Signature verifier | `C27965CCj` | package name + SHA-256 of signing cert vs embedded values |
| Install-source future | `CHH` | `install_source_official` |
| WAM daily event | `C0Fp` (`getEventNameForFalco()` = `wam_daily`) | device flags |
| WAM flag filler | `Cdt` (smali) | fills `C0Fp` booleans |
| Root / emulator helpers | `C00L` | `A0F` root, `A0C` emulator, `A0B` custom ROM, `A0D` test-automation |

---

## 2. Keystore key attestation ("blacknoise")

### 2.1 Key generation (`C25730yT.A02`)

All gated by ab-prop **1934** (`A06()`, default `true`).

| Item | Value | Tier |
|------|-------|------|
| Keystore | `AndroidKeyStore` | found |
| Key purpose | `4` (`PURPOSE_SIGN`), digests `SHA-256`, `SHA-512`, user auth not required | found |
| Algorithm | ab-prop **2076**, default `"EC"`; `"RSA"` adds `PKCS1` padding | found |
| Signature algorithm | ab-prop **2075**, default `"SHA256withECDSA"` | found |
| Alias base | ab-prop **2074**, default `the_well_of_wishes_awaits_in_the_crypt_of_decay`; hardcoded fallback `my_personal_mini_pony` when the prop is null | found |
| Alias | dynamic: `<base>[_<suffix>]`; static: `<base>_static[_<suffix>]`; suffix = random UUID stored in prefs `ka_key_store_dynamic_alias_suffix` / `ka_key_store_static_alias_suffix`, rotated when a regeneration finds an existing suffix | found |
| Certificate validity | now + ab-prop **2079** seconds (default 86400) | found |
| Attestation challenge | set only on SDK >= 24 | found |
| Device-properties attestation | `setDevicePropertiesAttestationIncluded(true)` on SDK >= 31; on `ProviderException` retried without (log `blacknoise/disbabling device ids att`) | found |

Attestation challenge layout (found):

```
challenge = BE64(unix_seconds) ‖ 0x1F ‖ nonce
nonce     = caller-supplied bytes, else SecureRandom(ab-prop 2078 bytes, default 32)
```

### 2.2 Refresh and throttle

| Pref / prop | Meaning | Default | Tier |
|-------------|---------|---------|------|
| `ka_refresh_ts` + ab-prop **2079** | dynamic key re-created when older than this | 86400 s | found |
| `ka_static_refresh_ts` + ab-prop **4878** | static key refresh | 600 s | found |
| `ka_retried_ts` + ab-prop **2427** | dynamic: regeneration attempted too soon -> log `regeneration attempted too soon, waiting` | 600 s | found |
| `A04()` | deletes both aliases and zeroes all `ka_*` prefs | – | found |

### 2.3 Certificate chain (`C25730yT.A03`)

`keyStore.getCertificateChain(alias)`, each certificate `getEncoded()` (DER), concatenated in reverse order (root first, leaf last) into one byte array. Empty chain logs `empty list of certificates found`. Failures are reported to the error reporter as `attestation-creation`, `attestation-nocertchain`, `attestation-nosign` (found). Timing is logged as `att-gen` / `att-sign` (found).

### 2.4 Signing (`C25730yT.A07`)

`Signature.getInstance(prop 2075)` over a caller payload with the static key. Missing key entry -> `attestation-nosign` "cannot sign payload, att pair missing". Callers of `A07` were not found in the decompiled code (decompile gaps possible); where a signature would be sent is unknown.

### 2.5 Four consumers of the chain

| # | Trigger | Mode | Nonce | Sink | Tier |
|---|---------|------|-------|------|------|
| 1 | Server connected (`handleConnected` in connection handler, job name `sendKeystoreAttestation`) | dynamic (`C02U.A00`) | client static (Noise) public key (`C25710yR.A0H()`) | `<ib><keystore_attestation>chain</keystore_attestation></ib>` via `C10140Tq.A0X(node, 6)` | found |
| 2 | Registration (`K49.A0s`, job `regtime_ka`, runnable `KZ2` case 39) | static (`C02U.A01`) | client static public key | `JniBridge.jvidispatchIOO(1, ctx, chain)` into native, with retry/backoff (ab-props **2863** 1000 ms, **2864** 5 tries); `K49.A0s` waits up to ab-prop **4696** (1880 ms) when asked to | found (native use unknown) |
| 3 | Companion registration start (`C0YS` `startcompanionreg` -> `H1K.A00`) | dynamic | client static public key | cached in `H1K` (field `A02`), refreshed by `KeyAttestationLifetimeManager`-style helper; gated by ab-props **6430** (default `true`), **7217** (bucket), interval **6431** (600000 ms), retries **6433**/**6434** | found (cache); consumer of the cached bytes not resolved: unknown |
| 4 | Passkey server API (`I16` case 18, `PasskeyServerApiImpl`) | dynamic | server-provided bytes | returned to the passkey caller | found (what the caller does is unknown) |

Stanza gate for #1: `A06()` and ab-prop **1935** (default `true`), and at most once per ab-prop **2067** seconds (default 86400), stored in pref `ka_stanza_sent_ts`. A null chain logs `blacknoise: got null attestation chain in custom stanza` and sends nothing (found).

Stanza shape (found):

```
<ib>
  <keystore_attestation>[binary: DER certs, root first]</keystore_attestation>
</ib>
```

`keystore_attestation` is also a dictionary token (second dictionary, `AbstractC40911lb.A01[0]`), so it is encoded as a token on the wire (found).

Binding: because the nonce in #1 to #3 is the client's own Noise static public key, the certificate chain's challenge extension carries the identity key, tying the hardware key to the account's static key (inferred from nonce choice; server check unknown).

---

## 3. Play Integrity

### 3.1 Java standard API (`C45007Jkc`)

| Item | Value | Tier |
|------|-------|------|
| API | `IntegrityManagerFactory.createStandard` -> `StandardIntegrityManager` | found |
| Cloud project number | `293955441834` (`PrepareIntegrityTokenRequest.setCloudProjectNumber`) | found |
| Prepare (`A00(callback, tag)`) | tag-labelled; skipped if a token provider already exists; refuses without network; max 5 prepares per 60 s (pref `pref_gpia_prepare_call_count_in_last_interval`) | found |
| Request (`A01(callback, nonce, tag)`) | `StandardIntegrityTokenRequest.setRequestHash(nonce)`; fails with 1003 if no provider | found |
| Internal error codes (`JCX`) | 1001 no network, 1002 too many prepare calls, 1003 not prepared, 1004 timeout (`C47238Kk7`), 1005 no static key (`Kmc`) | found |
| Error reporter events (`GKY`) | `ka_at_md_generate_attestation`, `gpia_at_md_prepare`, `gpia_at_md_generate_attestation` | found |

Prepare call sites (found): `RegisterPhone` (tag `register_phone`), `VerifyPhoneNumber` (tag `verify_phone`), companion pairing (tag `md-pairing`, `H1J`), plus a retry path in `C41354Hz3`.

### 3.2 Registration HTTP parameter `gpia`

`K49.A0V` adds one field to the registration HTTP request map:

```java
if (!flag(3753)) return;               // default false
nonce = Base64(static_public_key, NO_PADDING|NO_WRAP);   // C47343Kmc case 48
token = request(nonce, tag="reg");     // timeout ab-prop 4263, default 1800
map.put("gpia", token);
```

| Item | Value | Tier |
|------|-------|------|
| Gate | ab-prop **3753**, default `false` | found |
| Nonce | base64 (flags 3) of client static public key (`C25710yR.A0H()`); null key -> error 1005 | found |
| Added in | `checkIfExists` (two code paths), `verifySecurityCode` | found |
| Other requests (code request, final register) | `A0V` not called there in the decompiled code | found (absence in decompile) |
| Timing metric | `gpia-param-prepare` | found |

Default `false` means the parameter is only sent when the server enables prop 3753. Whether the registration server requires it: unknown.

### 3.3 Companion pairing token

`H1J` (gated by `A07(...)`, prop **7006** default `false`, interval **7007** = 21600000 ms) prepares ("md-pairing") and `I16` case 3 requests a token with nonce = base64(static public key, flags 3), timeout prop **7010** (1000 ms). Failures logged as `gpia_at_md_prepare` / `gpia_at_md_generate_attestation`. The consumer of the token is not resolved (unknown).

### 3.4 Native classic API and `integrity_payload`

Strings in `libwhatsapp.so` (found): `WAJIntegrityGpiaStatusRequest`, `WAJIntegrityGpiaStatusRequestAttributes`, `_WAJIntegrityTriggerGPIAWithRequestAttributes`, `_WAJIntegritySendResponseOrRetry`, `_WCAAPIGenerateGPIAParamOnMain`, and JNI signatures for `IntegrityManagerFactory.create(Context)`, `IntegrityTokenRequest.Builder` (`setNonce`, `setCloudProjectNumber`), `IntegrityManager.requestIntegrityToken`. The native code therefore drives Play Integrity (classic request) through JNI itself.

Java sink (found):

```java
// JniBridge.jnidispatch... case 3  (callback "sendAttestationResult")
node = <ib><integrity_payload>{string}</integrity_payload></ib>   // C10140Tq.A0X(node, 194)
metric type "safety-net-attestation", result "success"/"failed"
```

The metric type string `safety-net-attestation` is a legacy label; no SafetyNet API is used (see 10). The statement "native `WAJIntegrityGpiaStatusRequest` produces the `integrity_payload` string" is **inferred** from names; the call chain inside the stripped native code was not traced. What triggers a native status request (client schedule vs server request) is unknown.

Native reads ab-props through `jnidispatchIII(feature, kind)`; mapped IDs (found): kind 0: 12->13178, 13->13456, 15->22925, 16->24048; kind 1: 13->13455. `jnidispatchO(1)` returns ab-prop string **10266** (default empty). Purpose of these props is unknown.

### 3.5 Other Play Integrity users

| Class | Use | Tier |
|-------|-----|------|
| `JK4`, `KM0` family | reCAPTCHA Enterprise SDK (`recaptcha.net`) with its own `StandardIntegrityManager`; result goes into HTTP param `recaptcha` (`K49.A0Z`) when present | found |
| `KLL`, `KLN`, `C42885In8`… | bundled Play Core integrity implementation (library code) | found |

---

## 4. WASafe native library

### 4.1 Java side

| Hook | Behaviour | Tier |
|------|-----------|------|
| `jnidispatchI(4)` | loads `libwasafe.so` (`"wasafe"`), logs `WCAAPIEnsureSafeLibraryLoaded libwasafe.so load failed` on `UnsatisfiedLinkError` | found |
| `jnidispatchI(5)` | returns pref `runtime_override` from SharedPreferences `wsafeplatform_context`, else constant `1090327562` | found |
| WAM attribute **15611** | the same constant, written as string `1090327562` in common attributes | found |

The meaning of `1090327562` is unknown (candidate: WASafe runtime / detection-type value, not verified).

### 4.2 `libwasafe.so` (14480 bytes, arm64, stripped)

Exports: `WASafeSignalsCreate`, `WASafeSignalsConfigure`, `WASafeSignalsPrepare`, `WASafeSignalsGetBase64EncodedData`, `WASafeSignalsRelease`, `WASafeStatus`. Imports: libc (`stat`, `rand`, `srand`, `gettimeofday`, `malloc`…) and `WASafeDepsCrypto*` from `libwasafedeps.so`.

| Function | Decompiled behaviour | Tier |
|----------|---------------------|------|
| `WASafeSignalsConfigure(x)` | stores `x` (detection type) in a global, clears a second global | found |
| `WASafeSignalsPrepare()` | writes status constant `0x1092` into a global; no other work | found |
| `WASafeSignalsGetBase64EncodedData()` | passes the context's data/length through encrypt+base64 (`sub_6a00`) and returns `{ptr, len}` | found |

This build of `libwasafe.so` contains no signal collection: no root, debugger, hook, emulator or file-path strings, and the only filesystem import is `stat`. `libwhatsapp.so` also contains a `WASafeSignalsStub` string and `WAIntegrityPrepareSafeSignals(WASafeDetectionType)` with log tags `safesignals/prepare` and `safesignals/generate` (found). Where the data that gets encrypted comes from is unknown.

### 4.3 `libwasafedeps.so`

Exports `WASafeDepsCryptoInputCreate`, `...SetServerPublicKey`, `...SetData`, `...EncryptBase64`, `...ResultGetData/GetLength/Release`; imports mbedtls (`ctr_drbg`, `entropy`, `gcm_setkey`, `gcm_crypt_and_tag`). Structure (found from imports and names): random ephemeral key, shared secret with a server public key, AES-GCM, base64. The exact curve and KDF were not re-decompiled for this build; a Curve25519 ECDH + AES-GCM construction is **inferred**. Server public key value and rotation: unknown.

---

## 5. App signature self-check and install source

### 5.1 Gate (`AbstractC38241gg.A00`)

```java
long vc = versionCode;
if (vc < 264100600 || vc > 264100608) return 0;          // outside window
sha1 = Base64(SHA-1(signatures[0]), 11);
return "OKD31QX-GP7GT780Psqq8xDb15k".equals(sha1) ? 1 : 0;
```

The version window starts at this build's `versionCode` (264100600). Result is cached in a static.

### 5.2 Verifier (`C27965CCj.A00(pkg, certBytes)`)

| Step | Behaviour | Tier |
|------|-----------|------|
| 1 | Package name XOR-masked with a 5-byte key and compared with two embedded byte arrays that decode to `com.whatsapp` and `com.whatsapp.w4b` | found |
| 2 | If the package is neither: returns `true` immediately | found |
| 3 | Else SHA-256 of the cert bytes, XOR-masked and compared with two embedded 32-byte values; match -> `false`, mismatch -> `true` | found |

Decompile of this method failed; steps read from the instruction dump.

### 5.3 Consumer

Inside WAM `initializeCommonAttributes` (runnable `RunnableC29340CoR`):

```java
long r = AbstractC38241gg.A00(ctx);          // 1 only when version window + SHA-1 match
if (r == 1) r = verifier(pkg, cert) ? 0 : 1;
common attribute 6251 = r;                   // 1 = both checks passed, 0 = otherwise
```

So **6251 = 1** means "signing cert matches WhatsApp's embedded values" (found); 0 means mismatch or build outside the window (found). The value is only reported in telemetry. Nothing in the client reacts to it (no code path found that reads the result to block or degrade). Server use: unknown.

### 5.4 Install source

`getInstallSourceInfo().getInstallingPackageName()` (SDK >= 30, else `getInstallerPackageName`) compared with `com.android.vending` (`C18970md`, `RunnableC29340CoR`): stored in `CHH.A01` future. Reported as WAM attribute **10255** and as `install_source_official` in logging attribute sets (`HO4`, `C08650Nr`, `AbstractC35718FdU`). Also `C0Fp` field `install_source` (`wam_daily`). Separate uses of the same comparison select the Voltron module installer (`AbstractC12860bs`) (found). The result is telemetry plus module-download routing; no enforcement found.

---

## 6. Root, emulator and modded-client signals

### 6.1 `wam_daily` device flags

`C0Fp` is the `wam_daily` event (`getEventNameForFalco()`); its fields below are filled in `Cdt` (smali). Reported, not enforced (found).

| Field | Source | Tier |
|-------|--------|------|
| `is_rooted` | `C00L.A0F(telephony helper)` | found |
| `is_using_custom_rom` | `C00L.A0B()` (kernel/manufacturer/display strings: cyanogen, debug, Darky, XDAndroid, MIUI…) | found |
| `is_whatsapp_plus_user` | `Class.forName("org.acra.ACRA")` succeeds (class absent from this APK; typically bundled by third-party clients) | found (check); "typically bundled" inferred |
| `is_genymotion` | package probe for `com.genymotion.superuser` region in `Cdt`; exact condition partly traced | found (probe), logic inferred |
| `is_monkeyrunner_running` | source not resolved | unknown |
| `google_play_services_available`, `google_play_services_version`, `install_source` | present in the same event | found |

### 6.2 `C00L.A0F` root heuristic

Cached static. True when any of: `Build.TAGS` contains `test-keys`; `/system/app/Superuser.apk` exists; `su` executable at `/system/bin/su` or `/system/xbin/su` (`canExecute`), with extra logging `app/dly`; emulator-like product/model/manufacturer (`sdk`) or no SIM/telephony (`z` flag is only used for the log suffix, found). Related helpers: `A0C` emulator (`generic` brand/device, `goldfish`, `ranchu`, `google_sdk`, `Emulator`, `Android SDK built for x86`, `Genymotion`), `A0D` test automation (`fb.running_sapienz` system property).

### 6.3 Where `A0F` is consumed

| Consumer | Use | Tier |
|----------|-----|------|
| `C10V` debug-report builder | appends `DC-RTED` (root) and `DC-BACRM` (custom ROM) to diagnostics text | found |
| `C1Z` contact-us diagnostics map | key `diagnostic` = `rted ` (and `nw-wap ` if `org.acra.ACRA` is present) | found |
| `C28049CFz` (verification flow state) | contact-us context `register-phone-rtd` on the phone-number screen | found |
| `Cdt` | `wam_daily.is_rooted` | found |
| `KH2` (crash reporter `lacrima`) | `ExtraDeviceInfoCollector` writes root flag (`test-keys`, `Superuser.apk`, `su` on `PATH`) into crash reports | found |

None of these blocks registration or messaging (found: no branch ends the flow on these booleans). Whether the server weighs `wam_daily` flags: unknown.

### 6.4 Not found

| Check | Result |
|-------|--------|
| Magisk, Xposed (`de.robv`), Substrate, Frida strings in WhatsApp code (`libwhatsapp.so`, Java) | not found |
| `ro.kernel.qemu`, `FLAG_DEBUGGABLE` self-check | not found |
| Banned-package list for named mod clients (GB, FM, Plus) | not found |
| dex / asset CRC self-check | not found in this pass (not exhaustively searched) |
| Hardware-backed key check (`KeyInfo.isInsideSecureHardware`) in WhatsApp's own attestation code | not found (only in library classes `BinderC48420LDc`, `C51962N8y`) |
| `FetchIntegritySignals`, `IntegrityChallengeResponse`, `relax_integrity_constraints_for_bb_wa_tenured_accounts` | not found anywhere in the APK (Java, smali, assets, native) |
| `SafetyNet` API | not found |

`isDebuggerConnected` appears only in the ANR detector (`SigquitBasedANRDetector`) and crash helpers.

---

## 7. Feature flags and ab-props

| ID | Value / default | Controls |
|----|-----------------|----------|
| **1934** | `true` | master gate of blacknoise (`C25730yT.A06`) |
| **1935** | `true` | send `keystore_attestation` stanza after connect |
| **2067** | 86400 | min seconds between stanza sends |
| **2074** | `the_well_of_wishes_awaits_in_the_crypt_of_decay` | key alias base |
| **2075** | `SHA256withECDSA` | signature algorithm |
| **2076** | `EC` | key algorithm |
| **2078** | 32 | random nonce length |
| **2079** | 86400 | cert validity and dynamic refresh seconds |
| **2427** | 600 | min seconds between dynamic regenerations |
| **4878** | 600 | static refresh seconds |
| **2863** / **2864** | 1000 / 5 | registration-time backoff base (ms) / tries |
| **4696** | 1880 | registration wait for attestation (ms) |
| **3753** | `false` | registration `gpia` parameter |
| **4263** | 1800 | `gpia` request timeout |
| **6430** | `true` | companion attestation pre-warm (`H1K`) |
| **6431** | 600000 | companion attestation cache age (ms) |
| **6433** / **6434** | 5 / 1000 | companion attestation lifetime-manager tries / timeout |
| **7217** | 1 | companion attestation bucket modulus |
| **7006** | `false` | companion Play Integrity pre-warm (`H1J`) |
| **7007** | 21600000 | companion token cache age (ms) |
| **7009** / **7010** | 5 / 1000 | companion Play Integrity tries / timeout |
| **10266** | empty string | string handed to native via `jnidispatchO(1)` |
| **26215** | `false` | alternative verifySecurityCode path in `K49` (not integrity specific) |

Defaults are the compiled-in values; the server can override ab-props (found: prop table; server values unknown).

---

## 8. Error cases

| Symptom | Cause | Fix / note |
|---------|-------|-----------|
| No `keystore_attestation` stanza | prop 1934 or 1935 false; sent within the last 2067 s; null chain | by design |
| `attestation-creation` error report | key generation failed (`ProviderException`, no TEE) | retried later, throttled by 2427 |
| `attestation-nocertchain` | `getCertificateChain` failed or empty | – |
| `attestation-nosign` | `A07` called without static key entry | – |
| `blacknoise/regeneration attempted too soon, waiting` | `ka_retried_ts` within 600 s | wait |
| `blacknoise: not boostrapped for reg` | `C25810yb.A00` false at registration time | attestation skipped for that registration |
| Play Integrity 1001 / 1002 / 1003 / 1004 / 1005 | no network / > 5 prepare per 60 s / not prepared / timeout / no static key | internal codes (`JCX`) |
| `gpia` missing in registration request | prop 3753 false or request failed (null result put as empty) | see 3.2 |
| `libwasafe.so load failed` | `UnsatisfiedLinkError` | logged only |
| Signature attribute 6251 = 0 | re-signed APK, different cert, or build outside `264100600..264100608` | telemetry only |

---

## 9. Baileys / protocol clients

| Item | Statement | Tier |
|------|-----------|------|
| App-side checks | A pure-protocol client never runs any of the code above | found (by definition) |
| `keystore_attestation` / `integrity_payload` stanzas | A client that omits them simply does not send them; whether the server rejects, limits or flags such accounts: unknown | unknown |
| `gpia` registration param | Optional by default (prop 3753 `false`); server-side enforcement per region/account: unknown | unknown |
| Forging attestation | Chain must be rooted in hardware/Google roots and carry the challenge; no client secret to copy, validation lives on the server | inferred |
| Known risk | Server-side policy depends on data this report cannot observe (behaviour, account age) | unknown |

Fix: none statically derivable. Sending fabricated values is not supported by any evidence found here.

---

## 10. Key distinctions

| Do not confuse | Fact |
|----------------|------|
| `safety-net-attestation` metric string vs SafetyNet | label only; the payload comes from Play Integrity; no SafetyNet API exists in the code |
| `keystore_attestation` vs `integrity_payload` | different stanzas: DER cert chain (bytes) vs Play Integrity token string; different producers (Java/Keystore vs native/Play) |
| Java `gpia` (standard API, request hash) vs native classic GPIA | different APIs and sinks (HTTP param vs `<ib>`); nonce construction of the native variant not traced |
| Static vs dynamic attestation | static alias `..._static` (registration), dynamic alias (post-connect, companion, passkey) |
| Nonce | client static public key in three consumers; server bytes in the passkey consumer |
| `blacknoise` vs WASafe | Keystore attestation (Java) vs native encrypted-blob library |
| WASafe vs "signals" | this build's `libwasafe.so` collects nothing; the name implies signals, the code does not |
| 6251 vs 10255 | signature match vs Play installer |
| `is_whatsapp_plus_user` vs a mod-client allowlist | one reflective class probe; no allowlist exists |
| `integrityai`, `bizintegritysignals` | content / business safety features (scam detection, business signals UI), not client attestation |
| WFAC / `waffle` | ban UI and account linking, not an attestation component |
| Reporting vs enforcement | all root, emulator, signature and installer results found are telemetry or support text |

---

## 11. Related components that are not client attestation

| Component | Facts | Tier |
|-----------|-------|------|
| `com.whatsapp.integrityai` | `IntegrityAiOrchestrator`, `ScamDetectorImpl`, model download (`IntegrityAiModelDownloadCoordinator`, device tier), opt-in UI `ScamDetectionSettingsActivity`; result store tag `IntegrityAi/ScamDetectionResultStore`; a native classifier named `kaleidoscope` was not re-verified in this build | found (structure); native part unknown |
| `com.whatsapp.bizintegritysignals` | GraphQL fetcher and manager for business integrity signals shown in UI | found |
| `com.whatsapp.waffle.wfac` | ban decision UI (`WfacBanActivity`, `WfacBanDecisionFragment`, `WfacUnbanDecisionFragment`) | found |
| `com.whatsapp.waffle.accountlinking` and siblings | account linking, SSO, crossposting, age check | found |

---

## 12. End-to-end flow

```
[Registration screens: RegisterPhone / VerifyPhoneNumber]
    │  C45007Jkc.A00  prepareIntegrityToken (cloud project 293955441834, tag register_phone / verify_phone)
    │  K49.A0s  "regtime_ka": C25730yT.A03(static)  nonce = static pubkey
    │      └── JniBridge.jvidispatchIOO(1, ctx, chain)  ──►  [native wamsys]  (use unknown)
    ▼
[K49 HTTP: exist / verifySecurityCode]
    │  if ab-prop 3753:  gpia = standard-API token, requestHash = b64(static pubkey)
    ▼
[WA registration server]  (validation not observed)

[Connected session]
    │  handleConnected ─► job "sendKeystoreAttestation"
    │  ab-props 1934 && 1935, once per 86400 s
    │  C25730yT.A03(dynamic, nonce = static pubkey) ─ AndroidKeyStore EC key, challenge = ts ‖ 0x1F ‖ nonce
    ▼
<ib><keystore_attestation>DER chain, root first</keystore_attestation></ib>
    ▼
[WA server]  (use unknown)

[Native libwhatsapp]  WAJIntegrityGpiaStatusRequest ─► classic IntegrityManager via JNI   (inferred link)
    │  JniBridge callback sendAttestationResult
    ▼
<ib><integrity_payload>token</integrity_payload></ib>   (node code 194)
    ▼
[WA server]  (use unknown)

[Companion pairing]
    │  C0YS startcompanionreg ─► H1K (chain cache) + H1J (GPIA token, tag md-pairing)
    ▼  consumer of cached bytes/token: unknown

[Telemetry, daily and common attributes]
    │  6251 signature match, 10255 Play installer, 15611 wasafe constant
    │  wam_daily: is_rooted, is_genymotion, is_using_custom_rom, is_whatsapp_plus_user, install_source
    ▼
[WA server]  (use unknown)
```

---

## 13. Unknowns

| Question | Why unknown |
|----------|-------------|
| Server validation and enforcement of any token | server side, no traffic observed |
| What triggers native `WAJIntegrityGpiaStatusRequest` and how the nonce is built | stripped native code not traced (decompiler for the large library unavailable here) |
| Where WASafe input data originates and what `1090327562` means | no producer found in stripped natives |
| Native use of the registration-time attestation bytes | only the JNI entry (`jvidispatchIOO(1)`) is visible |
| Consumers of `H1K` cached chain and `H1J` token | call sites not resolved in the decompiled code |
| Meaning of ab-prop 10266 and the `jnidispatchIII` feature IDs | values only |
| `is_monkeyrunner_running` source, exact `is_genymotion` condition | not traced |
| Callers of `C25730yT.A07` (signing) | none found; decompile gaps possible |
| Whether any enforcement exists for the telemetry flags | no client branch found; server unknown |
