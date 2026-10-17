<!-- src-sha1: 4ca6293d8bc9da2aebc5db6f104c88b12dce1bd0 -->
# WhatsApp Client Integrity — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-17
**Umfang:** Android-Client-Integrität und -Attestierung — Keystore Key Attestation ("blacknoise"), Play Integrity (Java-Standard-API und native Classic-API), native WASafe-Token-Bibliothek, `integrity_payload`-/`keystore_attestation`-Stanzas, Registrierungsparameter `gpia`, App-Signatur-Selbstprüfung, Install-Source-Flag, Root-/Emulator-/Modded-Client-Telemetrie (`wam_daily`), was gegated und was nur gemeldet wird, was unknown bleibt

---

## 1. Was "Client Integrity" in diesem Build ist

Es gibt kein einzelnes Gate. Der Client erzeugt mehrere unabhängige Nachweise und Signale; jedes davon wird auf dem Gerät erzeugt und an den Server gesendet. Es wurde kein clientseitiger Code gefunden, der sich weigert, auf einem modifizierten, gerooteten oder neu signierten Client zu laufen. Alle Aussagen beruhen auf statischer Analyse des dekompilierten APK (`versionCode 264100600`). Stufen: **found** = im Code gelesen, **inferred** = abgeleitet, **unknown** = statisch nicht auflösbar.

Obfuskierte Namen gelten je Build und wurden in 2.26.41.6 anhand stabiler Strings neu aufgelöst.

| Mechanismus | Erzeugt | Gesendet als | Server-Nutzung |
|-----------|----------|---------|-----------|
| Keystore Key Attestation, interner Log-Tag `blacknoise` (`C25730yT`) | DER-Zertifikatskette eines `AndroidKeyStore`-EC-Keys mit Attestation Challenge | `<ib><keystore_attestation>`-Stanza; Übergabe an Native zur Registrierungszeit; Passkey- und Companion-Pairing-Pfade | unknown (nicht beobachtbar) |
| Play Integrity, Java-Standard-API (`C45007Jkc`) | Standard-Integrity-Token (`gpia`) | HTTP-Registrierungsparameter `gpia`; Companion-Pairing ("md-pairing")-Token | unknown |
| Play Integrity, native Classic-API (`libwhatsapp.so`, `WAJIntegrityGpiaStatusRequest`) | Classic-Integrity-Token über JNI | `<ib><integrity_payload>` (Java-Sink found; Verbindung zum nativen Producer inferred) | unknown |
| WASafe (`libwasafe.so`, `libwasafedeps.so`) | ECIES-artiger verschlüsselter Blob vom Aufrufer gelieferter Daten, base64 | unknown Sink | unknown |
| App-Signatur-Selbstprüfung (`AbstractC38241gg`, `C27965CCj`) | 0/1-Wert | WAM-Common-Attribut **6251** | unknown |
| Install-Source-Flag (`CHH`) | Boolean `com.android.vending`-Installer | WAM-Attribute `install_source_official`, **10255** | unknown |
| Device-State-Flags (`Cdt` → `C0Fp`) | `is_rooted`, `is_genymotion`, `is_monkeyrunner_running`, `is_using_custom_rom`, `is_whatsapp_plus_user` | WAM-Event `wam_daily` | unknown |
| Support-Diagnostik (`C00L.A0F`) | "rted"-Tag | Contact-us- / Debug-Report-Strings | nur Support |

Keine Integrity-Attestierung, nicht verwechseln (siehe 11): `com.whatsapp.integrityai` (On-Device-Scam-Erkennung), `bizintegritysignals`, WFAC-Ban-UI (`com.whatsapp.waffle.wfac`), Account-Linking (`com.whatsapp.waffle`).

| Entität | Name in 2.26.41.6 | Rolle |
|--------|----------------|------|
| Keystore-Attestation | `C25730yT` | Schlüsselpaar, Zertifikatskette, Signieren (`A00`/`A01` Alias, `A02` generieren, `A03` Kette, `A07` signieren) |
| Attestation-Mode-Enum | `C02U` | `C02U.A00` = dynamic, `C02U.A01` = static |
| Stanza-Sender-Runnable | `RunnableC48591z1` case 3 über `C41141ly` | sendet `keystore_attestation` |
| Connected-Handler | `A01` im Connection-Handler (`smali/X/0Yq`) | plant `sendKeystoreAttestation` |
| Arbeit zur Registrierungszeit | `C25810yb`, `KZ2` case 39, `K49.A0s` | statische Attestierung an Native, Tag `regtime_ka` |
| Companion-Pre-Warm | `H1K` (Attestierung), `H1J` (Play Integrity) | Kette / Token für Pairing cachen |
| Play-Integrity-Wrapper | `C45007Jkc` | Standard-API Prepare + Request |
| Registrierungs-HTTP | `K49` | fügt `gpia` zu den Request-Parametern hinzu |
| JNI-Bridge | `com.whatsapp.wamsys.JniBridge` | `sendAttestationResult`, `jnidispatch*`-Callbacks, `wsafeplatform_context` |
| Signatur-Gate | `AbstractC38241gg` | Versionsfenster + SHA-1 des Signing-Zertifikats |
| Signatur-Verifier | `C27965CCj` | Paketname + SHA-256 des Signing-Zertifikats gegen eingebettete Werte |
| Install-Source-Future | `CHH` | `install_source_official` |
| WAM-Daily-Event | `C0Fp` (`getEventNameForFalco()` = `wam_daily`) | Device-Flags |
| WAM-Flag-Filler | `Cdt` (smali) | füllt `C0Fp`-Booleans |
| Root-/Emulator-Helfer | `C00L` | `A0F` Root, `A0C` Emulator, `A0B` Custom ROM, `A0D` Test-Automation |

---

## 2. Keystore Key Attestation ("blacknoise")

### 2.1 Schlüsselerzeugung (`C25730yT.A02`)

Alles gegated durch ab-prop **1934** (`A06()`, Default `true`).

| Punkt | Wert | Stufe |
|------|-------|------|
| Keystore | `AndroidKeyStore` | found |
| Key Purpose | `4` (`PURPOSE_SIGN`), Digests `SHA-256`, `SHA-512`, User-Authentifizierung nicht erforderlich | found |
| Algorithmus | ab-prop **2076**, Default `"EC"`; `"RSA"` fügt `PKCS1`-Padding hinzu | found |
| Signaturalgorithmus | ab-prop **2075**, Default `"SHA256withECDSA"` | found |
| Alias-Basis | ab-prop **2074**, Default `the_well_of_wishes_awaits_in_the_crypt_of_decay`; hartcodierter Fallback `my_personal_mini_pony`, wenn die Prop null ist | found |
| Alias | dynamic: `<base>[_<suffix>]`; static: `<base>_static[_<suffix>]`; Suffix = zufällige UUID, gespeichert in den Prefs `ka_key_store_dynamic_alias_suffix` / `ka_key_store_static_alias_suffix`, rotiert, wenn eine Neuerzeugung einen vorhandenen Suffix findet | found |
| Zertifikatsgültigkeit | now + ab-prop **2079** Sekunden (Default 86400) | found |
| Attestation Challenge | nur bei SDK >= 24 gesetzt | found |
| Device-Properties-Attestierung | `setDevicePropertiesAttestationIncluded(true)` bei SDK >= 31; bei `ProviderException` ohne erneut versucht (Log `blacknoise/disbabling device ids att`) | found |

Aufbau der Attestation Challenge (found):

```
challenge = BE64(unix_seconds) ‖ 0x1F ‖ nonce
nonce     = caller-supplied bytes, else SecureRandom(ab-prop 2078 bytes, default 32)
```

### 2.2 Refresh und Throttle

| Pref / Prop | Bedeutung | Default | Stufe |
|-------------|---------|---------|------|
| `ka_refresh_ts` + ab-prop **2079** | dynamischer Key wird neu erzeugt, wenn älter als dies | 86400 s | found |
| `ka_static_refresh_ts` + ab-prop **4878** | Refresh des statischen Keys | 600 s | found |
| `ka_retried_ts` + ab-prop **2427** | dynamic: Neuerzeugung zu früh versucht -> Log `regeneration attempted too soon, waiting` | 600 s | found |
| `A04()` | löscht beide Aliase und setzt alle `ka_*`-Prefs auf null | – | found |

### 2.3 Zertifikatskette (`C25730yT.A03`)

`keyStore.getCertificateChain(alias)`, jedes Zertifikat `getEncoded()` (DER), in umgekehrter Reihenfolge (Root zuerst, Leaf zuletzt) zu einem Byte-Array konkateniert. Eine leere Kette loggt `empty list of certificates found`. Fehler werden dem Error-Reporter als `attestation-creation`, `attestation-nocertchain`, `attestation-nosign` gemeldet (found). Die Zeitmessung wird als `att-gen` / `att-sign` geloggt (found).

### 2.4 Signieren (`C25730yT.A07`)

`Signature.getInstance(prop 2075)` über einen Aufrufer-Payload mit dem statischen Key. Fehlender Key-Eintrag -> `attestation-nosign` "cannot sign payload, att pair missing". Aufrufer von `A07` wurden im dekompilierten Code nicht gefunden (Decompile-Lücken möglich); wohin eine Signatur gesendet würde, ist unknown.

### 2.5 Vier Consumer der Kette

| # | Trigger | Modus | Nonce | Sink | Stufe |
|---|---------|------|-------|------|------|
| 1 | Server verbunden (`handleConnected` im Connection-Handler, Jobname `sendKeystoreAttestation`) | dynamic (`C02U.A00`) | statischer (Noise) Public Key des Clients (`C25710yR.A0H()`) | `<ib><keystore_attestation>chain</keystore_attestation></ib>` über `C10140Tq.A0X(node, 6)` | found |
| 2 | Registrierung (`K49.A0s`, Job `regtime_ka`, Runnable `KZ2` case 39) | static (`C02U.A01`) | statischer Public Key des Clients | `JniBridge.jvidispatchIOO(1, ctx, chain)` in Native, mit Retry/Backoff (ab-props **2863** 1000 ms, **2864** 5 Versuche); `K49.A0s` wartet bis zu ab-prop **4696** (1880 ms), wenn dazu aufgefordert | found (Native-Nutzung unknown) |
| 3 | Companion-Registrierungsstart (`C0YS` `startcompanionreg` -> `H1K.A00`) | dynamic | statischer Public Key des Clients | in `H1K` gecacht (Feld `A02`), aufgefrischt durch einen Helfer im Stil von `KeyAttestationLifetimeManager`; gegated durch ab-props **6430** (Default `true`), **7217** (Bucket), Intervall **6431** (600000 ms), Retries **6433**/**6434** | found (Cache); Consumer der gecachten Bytes nicht aufgelöst: unknown |
| 4 | Passkey-Server-API (`I16` case 18, `PasskeyServerApiImpl`) | dynamic | vom Server bereitgestellte Bytes | an den Passkey-Aufrufer zurückgegeben | found (was der Aufrufer tut, ist unknown) |

Stanza-Gate für #1: `A06()` und ab-prop **1935** (Default `true`), und höchstens einmal pro ab-prop **2067** Sekunden (Default 86400), gespeichert in Pref `ka_stanza_sent_ts`. Eine null-Kette loggt `blacknoise: got null attestation chain in custom stanza` und sendet nichts (found).

Stanza-Form (found):

```
<ib>
  <keystore_attestation>[binary: DER certs, root first]</keystore_attestation>
</ib>
```

`keystore_attestation` ist außerdem ein Dictionary-Token (zweites Dictionary, `AbstractC40911lb.A01[0]`), wird also auf der Leitung als Token kodiert (found).

Bindung: Da die Nonce in #1 bis #3 der eigene statische Noise-Public-Key des Clients ist, trägt die Challenge-Extension der Zertifikatskette den Identity Key und bindet so den Hardware-Key an den statischen Key des Accounts (inferred aus der Nonce-Wahl; Server-Prüfung unknown).

---

## 3. Play Integrity

### 3.1 Java-Standard-API (`C45007Jkc`)

| Punkt | Wert | Stufe |
|------|-------|------|
| API | `IntegrityManagerFactory.createStandard` -> `StandardIntegrityManager` | found |
| Cloud-Projektnummer | `293955441834` (`PrepareIntegrityTokenRequest.setCloudProjectNumber`) | found |
| Prepare (`A00(callback, tag)`) | mit Tag beschriftet; übersprungen, wenn bereits ein Token-Provider existiert; verweigert ohne Netzwerk; max. 5 Prepares pro 60 s (Pref `pref_gpia_prepare_call_count_in_last_interval`) | found |
| Request (`A01(callback, nonce, tag)`) | `StandardIntegrityTokenRequest.setRequestHash(nonce)`; schlägt mit 1003 fehl, wenn kein Provider | found |
| Interne Fehlercodes (`JCX`) | 1001 kein Netzwerk, 1002 zu viele Prepare-Aufrufe, 1003 nicht vorbereitet, 1004 Timeout (`C47238Kk7`), 1005 kein statischer Key (`Kmc`) | found |
| Error-Reporter-Events (`GKY`) | `ka_at_md_generate_attestation`, `gpia_at_md_prepare`, `gpia_at_md_generate_attestation` | found |

Prepare-Aufrufstellen (found): `RegisterPhone` (Tag `register_phone`), `VerifyPhoneNumber` (Tag `verify_phone`), Companion-Pairing (Tag `md-pairing`, `H1J`), plus ein Retry-Pfad in `C41354Hz3`.

### 3.2 Registrierungs-HTTP-Parameter `gpia`

`K49.A0V` fügt der Registrierungs-HTTP-Request-Map ein Feld hinzu:

```java
if (!flag(3753)) return;               // default false
nonce = Base64(static_public_key, NO_PADDING|NO_WRAP);   // C47343Kmc case 48
token = request(nonce, tag="reg");     // timeout ab-prop 4263, default 1800
map.put("gpia", token);
```

| Punkt | Wert | Stufe |
|------|-------|------|
| Gate | ab-prop **3753**, Default `false` | found |
| Nonce | base64 (Flags 3) des statischen Public Keys des Clients (`C25710yR.A0H()`); null-Key -> Fehler 1005 | found |
| Hinzugefügt in | `checkIfExists` (zwei Codepfade), `verifySecurityCode` | found |
| Andere Requests (Code-Request, finales Register) | `A0V` wird dort im dekompilierten Code nicht aufgerufen | found (Abwesenheit im Decompile) |
| Timing-Metrik | `gpia-param-prepare` | found |

Default `false` bedeutet, dass der Parameter nur gesendet wird, wenn der Server Prop 3753 aktiviert. Ob der Registrierungsserver ihn verlangt: unknown.

### 3.3 Companion-Pairing-Token

`H1J` (gegated durch `A07(...)`, Prop **7006** Default `false`, Intervall **7007** = 21600000 ms) bereitet vor ("md-pairing") und `I16` case 3 fordert einen Token an mit Nonce = base64(static public key, Flags 3), Timeout Prop **7010** (1000 ms). Fehler werden als `gpia_at_md_prepare` / `gpia_at_md_generate_attestation` geloggt. Der Consumer des Tokens ist nicht aufgelöst (unknown).

### 3.4 Native Classic-API und `integrity_payload`

Strings in `libwhatsapp.so` (found): `WAJIntegrityGpiaStatusRequest`, `WAJIntegrityGpiaStatusRequestAttributes`, `_WAJIntegrityTriggerGPIAWithRequestAttributes`, `_WAJIntegritySendResponseOrRetry`, `_WCAAPIGenerateGPIAParamOnMain`, sowie JNI-Signaturen für `IntegrityManagerFactory.create(Context)`, `IntegrityTokenRequest.Builder` (`setNonce`, `setCloudProjectNumber`), `IntegrityManager.requestIntegrityToken`. Der native Code steuert Play Integrity (Classic-Request) also selbst über JNI.

Java-Sink (found):

```java
// JniBridge.jnidispatch... case 3  (callback "sendAttestationResult")
node = <ib><integrity_payload>{string}</integrity_payload></ib>   // C10140Tq.A0X(node, 194)
metric type "safety-net-attestation", result "success"/"failed"
```

Der Metrik-Typ-String `safety-net-attestation` ist ein Legacy-Label; es wird keine SafetyNet-API verwendet (siehe 10). Die Aussage "natives `WAJIntegrityGpiaStatusRequest` erzeugt den `integrity_payload`-String" ist **inferred** aus Namen; die Aufrufkette im gestrippten nativen Code wurde nicht verfolgt. Was einen nativen Status-Request auslöst (Client-Zeitplan vs. Server-Anfrage), ist unknown.

Native liest ab-props über `jnidispatchIII(feature, kind)`; zugeordnete IDs (found): kind 0: 12->13178, 13->13456, 15->22925, 16->24048; kind 1: 13->13455. `jnidispatchO(1)` liefert den ab-prop-String **10266** (Default leer). Zweck dieser Props ist unknown.

### 3.5 Weitere Play-Integrity-Nutzer

| Klasse | Verwendung | Stufe |
|-------|-----|------|
| `JK4`, `KM0`-Familie | reCAPTCHA-Enterprise-SDK (`recaptcha.net`) mit eigenem `StandardIntegrityManager`; Ergebnis geht in den HTTP-Parameter `recaptcha` (`K49.A0Z`), wenn vorhanden | found |
| `KLL`, `KLN`, `C42885In8`… | gebündelte Play-Core-Integrity-Implementierung (Bibliothekscode) | found |

---

## 4. Native WASafe-Bibliothek

### 4.1 Java-Seite

| Hook | Verhalten | Stufe |
|------|-----------|------|
| `jnidispatchI(4)` | lädt `libwasafe.so` (`"wasafe"`), loggt `WCAAPIEnsureSafeLibraryLoaded libwasafe.so load failed` bei `UnsatisfiedLinkError` | found |
| `jnidispatchI(5)` | liefert Pref `runtime_override` aus den SharedPreferences `wsafeplatform_context`, sonst Konstante `1090327562` | found |
| WAM-Attribut **15611** | dieselbe Konstante, als String `1090327562` in den Common Attributes geschrieben | found |

Die Bedeutung von `1090327562` ist unknown (Kandidat: WASafe-Runtime- / Detection-Type-Wert, nicht verifiziert).

### 4.2 `libwasafe.so` (14480 Bytes, arm64, gestrippt)

Exporte: `WASafeSignalsCreate`, `WASafeSignalsConfigure`, `WASafeSignalsPrepare`, `WASafeSignalsGetBase64EncodedData`, `WASafeSignalsRelease`, `WASafeStatus`. Importe: libc (`stat`, `rand`, `srand`, `gettimeofday`, `malloc`…) und `WASafeDepsCrypto*` aus `libwasafedeps.so`.

| Funktion | Dekompiliertes Verhalten | Stufe |
|----------|---------------------|------|
| `WASafeSignalsConfigure(x)` | speichert `x` (Detection Type) in einem Global, löscht ein zweites Global | found |
| `WASafeSignalsPrepare()` | schreibt die Statuskonstante `0x1092` in ein Global; keine weitere Arbeit | found |
| `WASafeSignalsGetBase64EncodedData()` | leitet die Daten/Länge des Contexts durch Encrypt+Base64 (`sub_6a00`) und liefert `{ptr, len}` | found |

Dieser Build von `libwasafe.so` enthält keine Signal-Sammlung: keine Root-, Debugger-, Hook-, Emulator- oder Dateipfad-Strings, und der einzige Dateisystem-Import ist `stat`. `libwhatsapp.so` enthält außerdem einen `WASafeSignalsStub`-String und `WAIntegrityPrepareSafeSignals(WASafeDetectionType)` mit den Log-Tags `safesignals/prepare` und `safesignals/generate` (found). Woher die zu verschlüsselnden Daten stammen, ist unknown.

### 4.3 `libwasafedeps.so`

Exportiert `WASafeDepsCryptoInputCreate`, `...SetServerPublicKey`, `...SetData`, `...EncryptBase64`, `...ResultGetData/GetLength/Release`; importiert mbedtls (`ctr_drbg`, `entropy`, `gcm_setkey`, `gcm_crypt_and_tag`). Struktur (found aus Importen und Namen): zufälliger ephemerer Key, Shared Secret mit einem Server-Public-Key, AES-GCM, base64. Die genaue Kurve und KDF wurden für diesen Build nicht erneut dekompiliert; eine Konstruktion aus Curve25519-ECDH + AES-GCM ist **inferred**. Wert und Rotation des Server-Public-Keys: unknown.

---

## 5. App-Signatur-Selbstprüfung und Install Source

### 5.1 Gate (`AbstractC38241gg.A00`)

```java
long vc = versionCode;
if (vc < 264100600 || vc > 264100608) return 0;          // outside window
sha1 = Base64(SHA-1(signatures[0]), 11);
return "OKD31QX-GP7GT780Psqq8xDb15k".equals(sha1) ? 1 : 0;
```

Das Versionsfenster beginnt beim `versionCode` dieses Builds (264100600). Das Ergebnis wird in einem Static gecacht.

### 5.2 Verifier (`C27965CCj.A00(pkg, certBytes)`)

| Schritt | Verhalten | Stufe |
|------|-----------|------|
| 1 | Paketname mit einem 5-Byte-Key XOR-maskiert und mit zwei eingebetteten Byte-Arrays verglichen, die zu `com.whatsapp` und `com.whatsapp.w4b` dekodieren | found |
| 2 | Ist das Paket keines von beiden: liefert sofort `true` | found |
| 3 | Sonst SHA-256 der Cert-Bytes, XOR-maskiert und mit zwei eingebetteten 32-Byte-Werten verglichen; Treffer -> `false`, kein Treffer -> `true` | found |

Der Decompile dieser Methode ist fehlgeschlagen; die Schritte wurden aus dem Instruction-Dump gelesen.

### 5.3 Consumer

Innerhalb von WAM `initializeCommonAttributes` (Runnable `RunnableC29340CoR`):

```java
long r = AbstractC38241gg.A00(ctx);          // 1 only when version window + SHA-1 match
if (r == 1) r = verifier(pkg, cert) ? 0 : 1;
common attribute 6251 = r;                   // 1 = both checks passed, 0 = otherwise
```

**6251 = 1** bedeutet also "Signing-Zertifikat entspricht den eingebetteten Werten von WhatsApp" (found); 0 bedeutet Abweichung oder Build außerhalb des Fensters (found). Der Wert wird nur in der Telemetrie gemeldet. Nichts im Client reagiert darauf (kein Codepfad gefunden, der das Ergebnis liest, um zu blockieren oder zu degradieren). Server-Nutzung: unknown.

### 5.4 Install Source

`getInstallSourceInfo().getInstallingPackageName()` (SDK >= 30, sonst `getInstallerPackageName`) verglichen mit `com.android.vending` (`C18970md`, `RunnableC29340CoR`): gespeichert im `CHH.A01`-Future. Gemeldet als WAM-Attribut **10255** und als `install_source_official` in Logging-Attributsets (`HO4`, `C08650Nr`, `AbstractC35718FdU`). Außerdem `C0Fp`-Feld `install_source` (`wam_daily`). Separate Verwendungen desselben Vergleichs wählen den Voltron-Modul-Installer (`AbstractC12860bs`) (found). Das Ergebnis ist Telemetrie plus Routing des Modul-Downloads; keine Durchsetzung gefunden.

---

## 6. Root-, Emulator- und Modded-Client-Signale

### 6.1 `wam_daily`-Device-Flags

`C0Fp` ist das `wam_daily`-Event (`getEventNameForFalco()`); seine unten genannten Felder werden in `Cdt` (smali) gefüllt. Gemeldet, nicht durchgesetzt (found).

| Feld | Quelle | Stufe |
|-------|--------|------|
| `is_rooted` | `C00L.A0F(telephony helper)` | found |
| `is_using_custom_rom` | `C00L.A0B()` (Kernel-/Hersteller-/Display-Strings: cyanogen, debug, Darky, XDAndroid, MIUI…) | found |
| `is_whatsapp_plus_user` | `Class.forName("org.acra.ACRA")` gelingt (Klasse in diesem APK nicht vorhanden; typischerweise von Drittanbieter-Clients gebündelt) | found (Check); "typischerweise gebündelt" inferred |
| `is_genymotion` | Package-Probe für den Bereich `com.genymotion.superuser` in `Cdt`; genaue Bedingung teilweise verfolgt | found (Probe), Logik inferred |
| `is_monkeyrunner_running` | Quelle nicht aufgelöst | unknown |
| `google_play_services_available`, `google_play_services_version`, `install_source` | im selben Event vorhanden | found |

### 6.2 `C00L.A0F`-Root-Heuristik

Als Static gecacht. True, wenn eines der folgenden zutrifft: `Build.TAGS` enthält `test-keys`; `/system/app/Superuser.apk` existiert; ausführbares `su` unter `/system/bin/su` oder `/system/xbin/su` (`canExecute`), mit zusätzlichem Logging `app/dly`; emulatorähnliches Product/Model/Manufacturer (`sdk`) oder keine SIM/Telephonie (das `z`-Flag wird nur für das Log-Suffix verwendet, found). Verwandte Helfer: `A0C` Emulator (`generic` Brand/Device, `goldfish`, `ranchu`, `google_sdk`, `Emulator`, `Android SDK built for x86`, `Genymotion`), `A0D` Test-Automation (System-Property `fb.running_sapienz`).

### 6.3 Wo `A0F` verwendet wird

| Consumer | Verwendung | Stufe |
|----------|-----|------|
| `C10V` Debug-Report-Builder | hängt `DC-RTED` (Root) und `DC-BACRM` (Custom ROM) an den Diagnosetext an | found |
| `C1Z` Contact-us-Diagnose-Map | Key `diagnostic` = `rted ` (und `nw-wap `, falls `org.acra.ACRA` vorhanden) | found |
| `C28049CFz` (Verifikations-Flow-State) | Contact-us-Kontext `register-phone-rtd` auf dem Telefonnummern-Screen | found |
| `Cdt` | `wam_daily.is_rooted` | found |
| `KH2` (Crash-Reporter `lacrima`) | `ExtraDeviceInfoCollector` schreibt das Root-Flag (`test-keys`, `Superuser.apk`, `su` im `PATH`) in Crash-Reports | found |

Nichts davon blockiert Registrierung oder Messaging (found: kein Branch beendet den Flow anhand dieser Booleans). Ob der Server `wam_daily`-Flags gewichtet: unknown.

### 6.4 Nicht gefunden

| Check | Ergebnis |
|-------|--------|
| Magisk-, Xposed- (`de.robv`), Substrate-, Frida-Strings im WhatsApp-Code (`libwhatsapp.so`, Java) | nicht gefunden |
| `ro.kernel.qemu`, `FLAG_DEBUGGABLE`-Selbstprüfung | nicht gefunden |
| Banned-Package-Liste für benannte Mod-Clients (GB, FM, Plus) | nicht gefunden |
| dex- / Asset-CRC-Selbstprüfung | in diesem Durchlauf nicht gefunden (nicht erschöpfend gesucht) |
| Hardware-backed-Key-Check (`KeyInfo.isInsideSecureHardware`) im eigenen Attestierungscode von WhatsApp | nicht gefunden (nur in Bibliotheksklassen `BinderC48420LDc`, `C51962N8y`) |
| `FetchIntegritySignals`, `IntegrityChallengeResponse`, `relax_integrity_constraints_for_bb_wa_tenured_accounts` | nirgends im APK gefunden (Java, smali, Assets, Native) |
| `SafetyNet`-API | nicht gefunden |

`isDebuggerConnected` kommt nur im ANR-Detektor (`SigquitBasedANRDetector`) und in Crash-Helfern vor.

---

## 7. Feature-Flags und ab-props

| ID | Wert / Default | Steuert |
|----|-----------------|----------|
| **1934** | `true` | Master-Gate von blacknoise (`C25730yT.A06`) |
| **1935** | `true` | `keystore_attestation`-Stanza nach dem Connect senden |
| **2067** | 86400 | Min. Sekunden zwischen Stanza-Sends |
| **2074** | `the_well_of_wishes_awaits_in_the_crypt_of_decay` | Key-Alias-Basis |
| **2075** | `SHA256withECDSA` | Signaturalgorithmus |
| **2076** | `EC` | Key-Algorithmus |
| **2078** | 32 | Länge der Zufallsnonce |
| **2079** | 86400 | Zertifikatsgültigkeit und dynamische Refresh-Sekunden |
| **2427** | 600 | Min. Sekunden zwischen dynamischen Neuerzeugungen |
| **4878** | 600 | Refresh-Sekunden des statischen Keys |
| **2863** / **2864** | 1000 / 5 | Backoff-Basis (ms) / Versuche zur Registrierungszeit |
| **4696** | 1880 | Registrierung wartet auf Attestierung (ms) |
| **3753** | `false` | Registrierungsparameter `gpia` |
| **4263** | 1800 | Timeout des `gpia`-Requests |
| **6430** | `true` | Companion-Attestation-Pre-Warm (`H1K`) |
| **6431** | 600000 | Cache-Alter der Companion-Attestation (ms) |
| **6433** / **6434** | 5 / 1000 | Versuche / Timeout des Lifetime-Managers der Companion-Attestation |
| **7217** | 1 | Bucket-Modulus der Companion-Attestation |
| **7006** | `false` | Companion-Play-Integrity-Pre-Warm (`H1J`) |
| **7007** | 21600000 | Cache-Alter des Companion-Tokens (ms) |
| **7009** / **7010** | 5 / 1000 | Versuche / Timeout von Companion-Play-Integrity |
| **10266** | leerer String | über `jnidispatchO(1)` an Native übergebener String |
| **26215** | `false` | alternativer verifySecurityCode-Pfad in `K49` (nicht integritätsspezifisch) |

Defaults sind die einkompilierten Werte; der Server kann ab-props überschreiben (found: Prop-Tabelle; Server-Werte unknown).

---

## 8. Fehlerfälle

| Symptom | Ursache | Behebung / Hinweis |
|---------|-------|-----------|
| Keine `keystore_attestation`-Stanza | Prop 1934 oder 1935 false; innerhalb der letzten 2067 s gesendet; null-Kette | by design |
| `attestation-creation`-Error-Report | Schlüsselerzeugung fehlgeschlagen (`ProviderException`, kein TEE) | später erneut versucht, gedrosselt durch 2427 |
| `attestation-nocertchain` | `getCertificateChain` fehlgeschlagen oder leer | – |
| `attestation-nosign` | `A07` ohne Eintrag für den statischen Key aufgerufen | – |
| `blacknoise/regeneration attempted too soon, waiting` | `ka_retried_ts` innerhalb von 600 s | warten |
| `blacknoise: not boostrapped for reg` | `C25810yb.A00` zur Registrierungszeit false | Attestierung für diese Registrierung übersprungen |
| Play Integrity 1001 / 1002 / 1003 / 1004 / 1005 | kein Netzwerk / > 5 Prepares pro 60 s / nicht vorbereitet / Timeout / kein statischer Key | interne Codes (`JCX`) |
| `gpia` fehlt im Registrierungs-Request | Prop 3753 false oder Request fehlgeschlagen (null-Ergebnis als leer eingesetzt) | siehe 3.2 |
| `libwasafe.so load failed` | `UnsatisfiedLinkError` | nur geloggt |
| Signatur-Attribut 6251 = 0 | neu signiertes APK, anderes Zertifikat oder Build außerhalb von `264100600..264100608` | nur Telemetrie |

---

## 9. Baileys / Protokoll-Clients

| Punkt | Aussage | Stufe |
|------|-----------|------|
| App-seitige Checks | Ein reiner Protokoll-Client führt nichts vom obigen Code aus | found (per Definition) |
| `keystore_attestation`- / `integrity_payload`-Stanzas | Ein Client, der sie weglässt, sendet sie schlicht nicht; ob der Server solche Accounts ablehnt, limitiert oder markiert: unknown | unknown |
| `gpia`-Registrierungsparameter | Standardmäßig optional (Prop 3753 `false`); serverseitige Durchsetzung je Region/Account: unknown | unknown |
| Fälschen der Attestierung | Kette muss in Hardware-/Google-Roots wurzeln und die Challenge tragen; kein Client-Secret zum Kopieren, die Validierung liegt auf dem Server | inferred |
| Bekanntes Risiko | Server-seitige Policy hängt von Daten ab, die dieser Report nicht beobachten kann (Verhalten, Account-Alter) | unknown |

Fix: statisch nicht ableitbar. Das Senden erfundener Werte wird von keinem hier gefundenen Beleg gestützt.

---

## 10. Wichtige Unterscheidungen

| Nicht verwechseln | Fakt |
|----------------|------|
| Metrik-String `safety-net-attestation` vs SafetyNet | nur Label; der Payload stammt von Play Integrity; im Code existiert keine SafetyNet-API |
| `keystore_attestation` vs `integrity_payload` | verschiedene Stanzas: DER-Zertifikatskette (Bytes) vs Play-Integrity-Token-String; verschiedene Producer (Java/Keystore vs Native/Play) |
| Java-`gpia` (Standard-API, Request Hash) vs native Classic-GPIA | verschiedene APIs und Sinks (HTTP-Parameter vs `<ib>`); Nonce-Konstruktion der nativen Variante nicht verfolgt |
| Static vs dynamic Attestierung | statischer Alias `..._static` (Registrierung), dynamischer Alias (nach dem Connect, Companion, Passkey) |
| Nonce | statischer Public Key des Clients in drei Consumern; Server-Bytes im Passkey-Consumer |
| `blacknoise` vs WASafe | Keystore-Attestierung (Java) vs native Bibliothek für verschlüsselte Blobs |
| WASafe vs "Signals" | `libwasafe.so` dieses Builds sammelt nichts; der Name impliziert Signale, der Code nicht |
| 6251 vs 10255 | Signaturabgleich vs Play-Installer |
| `is_whatsapp_plus_user` vs eine Mod-Client-Allowlist | eine reflektive Klassen-Probe; es existiert keine Allowlist |
| `integrityai`, `bizintegritysignals` | Content- / Business-Safety-Features (Scam-Erkennung, Business-Signal-UI), keine Client-Attestierung |
| WFAC / `waffle` | Ban-UI und Account-Linking, keine Attestierungskomponente |
| Reporting vs Durchsetzung | alle gefundenen Ergebnisse zu Root, Emulator, Signatur und Installer sind Telemetrie oder Support-Text |

---

## 11. Verwandte Komponenten, die keine Client-Attestierung sind

| Komponente | Fakten | Stufe |
|-----------|-------|------|
| `com.whatsapp.integrityai` | `IntegrityAiOrchestrator`, `ScamDetectorImpl`, Modell-Download (`IntegrityAiModelDownloadCoordinator`, Device Tier), Opt-in-UI `ScamDetectionSettingsActivity`; Result-Store-Tag `IntegrityAi/ScamDetectionResultStore`; ein nativer Klassifikator namens `kaleidoscope` wurde in diesem Build nicht erneut verifiziert | found (Struktur); nativer Teil unknown |
| `com.whatsapp.bizintegritysignals` | GraphQL-Fetcher und Manager für Business-Integrity-Signale, die in der UI angezeigt werden | found |
| `com.whatsapp.waffle.wfac` | Ban-Entscheidungs-UI (`WfacBanActivity`, `WfacBanDecisionFragment`, `WfacUnbanDecisionFragment`) | found |
| `com.whatsapp.waffle.accountlinking` und Geschwister | Account-Linking, SSO, Crossposting, Altersprüfung | found |

---

## 12. End-to-End-Flow

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

| Frage | Warum unknown |
|----------|-------------|
| Serverseitige Validierung und Durchsetzung jedes Tokens | Serverseite, kein Traffic beobachtet |
| Was das native `WAJIntegrityGpiaStatusRequest` auslöst und wie die Nonce gebaut wird | gestrippter nativer Code nicht verfolgt (Decompiler für die große Bibliothek hier nicht verfügbar) |
| Woher die WASafe-Eingabedaten stammen und was `1090327562` bedeutet | kein Producer in den gestrippten Natives gefunden |
| Native Nutzung der Attestierungs-Bytes zur Registrierungszeit | nur der JNI-Einstieg (`jvidispatchIOO(1)`) ist sichtbar |
| Consumer der gecachten `H1K`-Kette und des `H1J`-Tokens | Aufrufstellen im dekompilierten Code nicht aufgelöst |
| Bedeutung von ab-prop 10266 und der `jnidispatchIII`-Feature-IDs | nur Werte |
| Quelle von `is_monkeyrunner_running`, genaue `is_genymotion`-Bedingung | nicht verfolgt |
| Aufrufer von `C25730yT.A07` (Signieren) | keine gefunden; Decompile-Lücken möglich |
| Ob für die Telemetrie-Flags irgendeine Durchsetzung existiert | kein Client-Branch gefunden; Server unknown |
