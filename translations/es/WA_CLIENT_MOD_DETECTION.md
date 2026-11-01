<!-- src-sha1: acf9c9e68ca59b17d45a787d66ae2550607b66cc -->
# WhatsApp Detección de Clientes Modificados — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-11-01
**Alcance:** Detección del lado del cliente de clientes Android no oficiales/modificados (repacks de la familia GB WhatsApp, módulos de hook Xposed/LSPosed como WaEnhancer, APKs re-firmados) — la única heurística de detección de mods encontrada (`is_whatsapp_plus_user`), búsqueda de artefactos de frameworks de hooking (Xposed/Frida/Substrate), qué hace el cliente con la telemetría de firma/fuente de instalación/root ya catalogada en `WA_CLIENT_INTEGRITY.md`, el manejo que la UI de baneo WFAC hace de las razones de baneo enviadas por el servidor, y la superficie de ataque que un módulo de hook de terceros (WaEnhancer) es conocido por atacar dentro del proceso anfitrión

---

## 1. Visión general

Este reporte está delimitado a la **detección de mods/manipulación**, no a la atestación de cuenta. La atestación de Keystore, Play Integrity, WASafe, la autoverificación de firma (WAM **6251**) y el flag de fuente de instalación (WAM **10255**) están completamente documentados en [`WA_CLIENT_INTEGRITY.md`](WA_CLIENT_INTEGRITY.md); este reporte solo indica qué aportan a la detección de mods y no repite su mecánica.

| Mecanismo | Detecta | Reportado como | Enforcement encontrado |
|-----------|---------|-----------------|--------------------------|
| `is_whatsapp_plus_user` (sondeo reflectivo de clase) | Un cliente de terceros que incluye la librería de crash-reporting ACRA | campo de telemetría `wam_daily`; string `diagnostic` en contáctanos (`nw-wap`) y reporte de depuración (`NW-WAP-1`) | ninguno |
| Autoverificación de firma de la app (`AbstractC38241gg` / `C27965CCj`) — ver reporte de integridad §5 | APK re-firmado/repackeado (certificado de firma ≠ valor embebido de WhatsApp) | atributo común de WAM **6251** | ninguno |
| Flag de fuente de instalación (`CHH`) — ver reporte de integridad §5.4 | Instalación mediante sideload / no-Play | WAM **10255**, `install_source_official` | solo enrutamiento de descarga de módulos, sin compuerta |
| Flags de root / emulador / ROM personalizada (`C00L`, `Cdt`) — ver reporte de integridad §6 | Dispositivo rooteado o emulado (un habilitador común, no una señal de mod en sí) | `wam_daily` | ninguno |
| Strings de artefactos de frameworks de hooking (Xposed, Frida, Substrate, LSPosed, TracerPid) | — | — | **no encontrado** en esta build (§3) |
| Checksum propio de biblioteca nativa / dex | — | — | **no encontrado** en esta build (§3) |
| UI de baneo WFAC (`WfacBanActivity`) | — | muestra `ban_violation_type` / `ban_violation_source` / `ban_violation_reason` enviados por el servidor | decisión del servidor, opaca para el cliente (§5) |

No se encontró ninguna ruta de código en ningún lugar del cliente decompilado que se niegue a ejecutarse, degrade una función o bloquee una acción debido a cualquiera de los elementos anteriores. Todo mecanismo encontrado es **telemetría**, consistente con la conclusión ya alcanzada para la integridad de cuenta.

---

## 2. La única heurística de mod dedicada: `is_whatsapp_plus_user`

### 2.1 Qué verifica

Tres sitios independientes, cada uno ejecutando el **mismo sondeo reflectivo** en lugar de llamar a un helper compartido:

```smali
; smali_classes7/X/Cdt.smali, method C4k (fills LX/0Fp; = wam_daily event)
const-string v0, "org.acra.ACRA"
invoke-static {v0}, Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;
; ClassNotFoundException -> false, success -> true
iput-object v0, p1, LX/0Fp;->A0W:Ljava/lang/Boolean;   ; -> wam_daily.is_whatsapp_plus_user
```

```java
// C1Z.java (contact-us diagnostics)
try { Class.forName("org.acra.ACRA"); sbA0m.append("nw-wap "); } catch (ClassNotFoundException unused) {}

// C10V.java (debug report builder)
try { Class.forName("org.acra.ACRA"); sb10.append("NW-WAP-1 "); } catch (ClassNotFoundException unused2) {}
```

| Ítem | Valor | Tier |
|------|-------|------|
| Verificación | `Class.forName("org.acra.ACRA")` tiene éxito (la clase está presente en el classpath) | found |
| Nombre del campo | `is_whatsapp_plus_user` (`LX/0Fp;->A0W`), evento `wam_daily` | found |
| Sinks | telemetría `wam_daily`; string `diagnostic` de contáctanos (`nw-wap `); texto de reporte de depuración (`NW-WAP-1 `) | found |
| Justificación | ACRA (`org.acra`) es una librería de crash-reporting de terceros; el WhatsApp original no la incluye. Históricamente incluida por repacks de la familia "WhatsApp Plus" para su propia telemetría de crashes (`inferred`: el nombre del campo es una etiqueta elegida por WhatsApp mismo, no un valor leído del mod) | found (sondeo) / inferred (significado de la etiqueta) |
| Vacío de decompilación | `Cdt.java` mismo no decompiló (solo existe la clase hermana `CDT.java`); la verificación se lee desde smali | found |

### 2.2 Qué NO hace

- No existe ninguna lista blanca/negra de nombres de paquetes de mods (`com.gbwhatsapp`, `com.yowhatsapp`, `com.fmwhatsapp`, `com.wmods.wppenhacer`, …) en ningún lugar del cliente decompilado — ninguno de estos strings aparece en `java_src` ni en `smali*`.
- El sondeo es una única búsqueda reflectiva de clase, no una verificación de firma, hash o comportamiento. Un mod que simplemente no incluya `org.acra.ACRA` (o que oculte/renombre la clase) lo derrota trivialmente; este reporte no afirma lo contrario.
- Los tres sinks son texto de diagnóstico/telemetría y un evento de analítica diario. No se encontró ninguna rama que lea `A0W`/`is_whatsapp_plus_user` y cambie el comportamiento del cliente.

---

## 3. Búsqueda de artefactos de frameworks de hooking y repacks (no encontrado)

Búsqueda en todo el árbol decompilado (`java_src/`, todo `smali*/`) para 2.26.41.6:

| String(s) ancla | Objetivo | Resultado |
|-------------------|--------|--------|
| `Xposed`, `XposedBridge`, `de.robv`, `LSPosed` | Presencia del framework de hooking Xposed/LSPosed | no encontrado |
| `frida`, `Frida`, `re.frida`, `frida-server`, puerto `27042` | Servidor de instrumentación Frida | no encontrado (el único hit del substring `frida` está dentro de un literal de expresión regular de sufijos públicos/TLD, no relacionado) |
| `substrate`, `Substrate` | Framework de hooking Cydia Substrate | no encontrado |
| `TracerPid` | detección clásica de tracer por ptrace vía `/proc/self/status` | no encontrado |
| `GBWhatsApp`, `gbwhatsapp`, `com.gbwhatsapp`, `FMWhatsApp`, `YoWhatsApp`, `OGWhatsApp`, `com.wmods.wppenhacer` | strings de nombres de paquetes de clientes mod | no encontrado |
| `modded`, `unofficial`, `tampered`, `fake whatsapp`, `clone app` | texto/log genérico de detección de mods | no encontrado |
| usos de `CRC32` (10 hits) | checksum propio de dex/assets | todos en carga multidex (`dextricks`) o empaquetado de zip de reporte de crash, ninguno es una autoverificación de manipulación de la app |
| `checkSignatures` (3 hits) | comparación de firmas | todos son verificaciones de confianza IPC/llamador (verificación de firma idéntica del llamador en `FileSharingHelper`, una verificación de confianza de app complementaria de Pixel) no relacionadas con detectar un cliente WhatsApp modificado |
| `isDebuggerConnected` | anti-debug | solo en el detector de ANR (`SigquitBasedANRDetector`) y helpers de crash, no una compuerta de manipulación (confirma `WA_CLIENT_INTEGRITY.md` §6.4) |
| `/proc/self/status` (4 hits, `KGi`/`KGw`/`KH8`/`KGp`) | — | lectores de estadísticas de memoria (probablemente recolección de `VmRSS` para diagnósticos); no se encontró ahí ningún parseo de `TracerPid` |

**Corrección al enfoque de una nota de investigación anterior:** una nota de análisis estático previa describe a WaEnhancer como "exactamente el tipo de cliente modded/no oficial que el sistema de integridad de la app original tiene como objetivo" pero no afirma que la app original lo detecte por nombre — esa lectura se confirma aquí: no existe código de detección específico para WaEnhancer, para GB, ni para Xposed en 2.26.41.6. La única señal del lado del cliente que se activaría con una instalación de WaEnhancer es el sondeo genérico ACRA de `is_whatsapp_plus_user`, y solo si el módulo (o una dependencia incluida) resulta incluir esa clase — no verificado en ningún sentido para WaEnhancer específicamente (`unknown`).

Esto extiende `WA_CLIENT_INTEGRITY.md` §6.4, que marcó el CRC de dex/assets como "no buscado exhaustivamente" — ahora se buscó y sigue sin encontrarse.

---

## 4. Consecuencias del lado del servidor visibles del lado del cliente

### 4.1 UI de baneo WFAC

`WfacBanActivity` (`com.whatsapp.waffle.wfac.p191ui`) lee tres extras suministrados por el servidor y los renderiza; no calcula una razón:

```java
int violationType   = getIntent().getIntExtra("ban_violation_type", -1);
String violationReason = getIntent().getStringExtra("ban_violation_reason");
int violationSource  = getIntent().getIntExtra("ban_violation_source", -1);
```

| Ítem | Tier |
|------|------|
| `ban_violation_type` / `ban_violation_source` son enteros opacos; no se encontró ningún enum del lado del cliente que los resuelva a causas nombradas (p. ej. "cliente modificado") | found (ausencia) |
| `ban_violation_reason` es un string de texto libre, presumiblemente plantillado por el servidor | found |
| No se encontró ninguna ruta de código que conecte ninguna de las señales de detección de §1–§3 (`is_whatsapp_plus_user`, discrepancia de firma, root, fuente de instalación) con un valor `ban_violation_*` | found (ausencia) |

La máquina de estados de baneo completa, GraphQL (`BizIntegrityQuery`), niveles de confianza y stanzas de fallo XMPP están en [`WA_BAN_SYSTEM_DEEP_EN.md`](WA_BAN_SYSTEM_DEEP_EN.md); este reporte no repite ese contenido. Si el servidor usa alguna de la telemetría de §1 (discrepancia de firma, `is_whatsapp_plus_user`, root) como input de baneo/confianza es **unknown** — es del lado del servidor y no observable estáticamente, la misma conclusión que `WA_CLIENT_INTEGRITY.md` §13.

### 4.2 Restricción de funciones

No se encontró ninguna rama del lado del cliente que deshabilite una función basándose en las señales de §1. La única "restricción" observada en toda la superficie de integridad/mod es el throttling de las propias solicitudes de atestación/token (ab-props, documentado en el reporte de integridad) — no una respuesta a detectar un mod.

---

## 5. Superficie de ataque: qué ataca un módulo de hook (WaEnhancer, `com.wmods.wppenhacer`)

Esta sección describe el otro lado de la frontera — qué hookea dentro del proceso anfitrión un módulo Xposed/LSPosed representativo — para enmarcar lo que la detección del lado del cliente (en su mayoría ausente) necesitaría cubrir. Fuente de evidencia: artefactos que dejó una instalación modificada con WaEnhancer en un directorio de prueba `wa-data-root/` capturado (`Protocols/waenhancer-mod/info.md`), no análisis estático del propio APK de WhatsApp. Tiers según se registraron ahí.

| Capacidad | Mecanismo | Tier |
|------------|-----------|------|
| Entrega | Módulo Xposed/LSPosed ejecutándose **dentro** del proceso `com.whatsapp` (no una app separada, no un repack) | found |
| Manejo de ofuscación | "Unobfuscator" en tiempo de ejecución: resuelve los nombres ofuscados de clases/métodos de WhatsApp al iniciar el módulo y cachea los handles resueltos (`UnobfuscatorCache.xml`, `UnobfuscatorCacheStrings.xml`), asociados a la versión propia de WhatsApp de forma que la caché se invalida con la actualización de cualquiera de los dos lados | found |
| Ocultamiento de presencia ("ghost mode") | Hookea métodos relacionados con presencia; el ajuste se guarda en `WaGlobal.xml` (`ghostmode`) | found (artefacto) |
| Anti-revocación / anti-confirmación de lectura | Intercepta las rutas de código de eliminar-para-todos y confirmación de lectura; mantiene copias sombra en sus propios almacenes (`com_waenhancer_message_history.db`, y un `MessageHistory.db` basado en Room — WhatsApp mismo no usa Room para el almacenamiento de mensajes) | found |
| Visibilidad del protocolo en crudo | `StanzaLogger.logStanza(...)` escribe las stanzas XMPP entrantes/salientes en un archivo en texto plano (`wae_stanzas.txt`) — es decir, el módulo intercepta la propia ruta de envío/recepción de stanzas del cliente después de que la capa Noise/E2E ya las descifró | found |
| Registro contable de hooks | Logging de diagnóstico por ejecución de un conteo de hooks (`devtrace_logs/*.jsonl`, `eventType:"hook_config_loaded"`, `payload.hookCount`) | found |
| Límite de alcance | Hookea solo la capa Java/UI; no parece reemplazar la cripto nativa ni el transporte Noise/chatd (store axolotl/Signal, prekeys post-cuánticas, keystore, nativos OHAI/OPAQUE/WAFFLE sin tocar) | inferred |

Leído junto con §3: el cliente original no tiene código que enumere los módulos Xposed/LSPosed cargados, escanee su propia memoria de proceso en busca de trampolines de hook, ni verifique `TracerPid`/`/proc/self/maps` en busca de bibliotecas inyectadas. Lo único que se encuentra entre esta superficie de ataque y la detección es el único sondeo genérico de clase `is_whatsapp_plus_user` (§2), que apunta a una librería de crash-reporting, no a un framework de hooking.

---

## 6. Casos de error / gotchas

| Síntoma | Causa | Nota |
|---------|-------|------|
| `is_whatsapp_plus_user = true` en `wam_daily` sin ningún efecto adicional en el cliente | `org.acra.ACRA` resoluble en el classpath | solo telemetría, por diseño |
| `diagnostic` contiene `nw-wap` / `NW-WAP-1` en contáctanos o reportes de depuración | mismo sondeo ACRA, sink distinto | texto del flujo de soporte, no una compuerta |
| Ninguna razón en la pantalla de baneo WFAC más allá de un código numérico | `ban_violation_type`/`ban_violation_source` no tienen enum del lado del cliente | controlado por el servidor, no se puede resolver estáticamente |
| Buscar "Xposed"/"Frida" no arroja nada | correcto — esta build no contiene detección de frameworks de hooking | no es un vacío de decompilación para estos strings específicos (búsqueda en todo el árbol) |
| Una instalación de WaEnhancer cambia el comportamiento de mensajes/confirmación de lectura sin ningún log del lado de WhatsApp | WaEnhancer hookea la capa Java antes de que la telemetría propia de WhatsApp pueda observar la llamada original | esperado dado el alcance de §5 |

---

## 7. Distinciones clave

| No confundir | Hecho |
|-----------------|------|
| `is_whatsapp_plus_user` vs una lista blanca de clientes mod | un sondeo reflectivo para una clase de librería de terceros; no existe ninguna lista de nombres de paquetes de mods |
| Detección de mods/manipulación (este reporte) vs atestación de cuenta (`WA_CLIENT_INTEGRITY.md`) | problemas distintos: este reporte trata sobre detectar un *binario/runtime de cliente modificado*; el reporte de integridad trata sobre *atestar un dispositivo/clave genuino* ante el servidor — solo se superponen en que ambos son telemetría, no enforcement |
| UI de baneo WFAC (`WfacBanActivity`) vs lógica de decisión de baneo | la activity renderiza códigos/strings suministrados por el servidor; no decide ni calcula una razón de baneo |
| El tap de `StanzaLogger` de WaEnhancer vs romper el cifrado E2E | el módulo lee las stanzas dentro del proceso del cliente ya descifradas; no ataca la criptografía Signal/Noise en sí |
| Telemetría de `safety-net-attestation` / firma / fuente de instalación | estas existen y están documentadas en `WA_CLIENT_INTEGRITY.md`; este reporte no agrega mecánica nueva para ellas, solo indica que ninguna restringe nada |
| "No encontrado" en este reporte | significa ausente del Java/smali/strings decompilados de esta build específica (2.26.41.6); no es una afirmación sobre detección del lado del servidor, que no es observable estáticamente |

---

## 8. Flujo de extremo a extremo

```
[Device boots WhatsApp, possibly under a hook module or with a bundled crash-reporter lib]
    │
    ▼
[Cdt.C4k / C1Z / C10V]  Class.forName("org.acra.ACRA")
    │  success ──► is_whatsapp_plus_user = true ─► wam_daily
    │  success ──► "nw-wap" / "NW-WAP-1" ─► contact-us / debug-report text
    │  (no further branch — nothing reacts to this value in the client)
    ▼
[AbstractC38241gg / C27965CCj]  signature self-check → WAM 6251   (see WA_CLIENT_INTEGRITY.md §5)
[CHH]                           install-source flag  → WAM 10255  (see WA_CLIENT_INTEGRITY.md §5.4)
[C00L / Cdt]                    root / emulator / custom-ROM     → wam_daily  (see WA_CLIENT_INTEGRITY.md §6)
    │
    ▼
[WA telemetry backend]  (server-side use of all of the above: unknown, not observable)
    │
    ▼
[If the server bans the account]
    │  ban_violation_type / ban_violation_source / ban_violation_reason sent as intent extras
    ▼
[WfacBanActivity]  displays the server's values verbatim — no client-side cause mapping
```

```
[Attack surface, other side of the boundary — not WhatsApp code]
[Xposed/LSPosed host process: com.whatsapp]
    │
    ▼
[WaEnhancer module loads] ─ Unobfuscator resolves WhatsApp's classes at runtime
    │
    ├─► hooks presence methods ──────► ghost mode (WaGlobal.xml)
    ├─► hooks delete/read-receipt ───► shadow stores (MessageHistory.db, com_waenhancer_message_history.db)
    └─► taps stanza send/receive ────► wae_stanzas.txt (post-decryption plaintext)
```

---

## 9. Desconocidos

| Pregunta | Por qué es desconocido |
|----------|-------------|
| Si el servidor usa `is_whatsapp_plus_user`, la discrepancia de firma (6251), la fuente de instalación (10255) o los flags de root como inputs de baneo/puntaje de confianza | del lado del servidor, sin tráfico observado |
| Si `org.acra.ACRA` está realmente presente en una build actual de WaEnhancer/GB WhatsApp (es decir, si la única heurística que existe siquiera se activaría con él) | no verificado contra una build de mod en vivo en este pase |
| Mapeo nombrado de razones de baneo para los valores de `ban_violation_type` / `ban_violation_source` | sin enum resuelto del lado del cliente; definido por el servidor |
| Si algún código nativo (`libwhatsapp.so`, `libwasafe.so`) realiza detección de hooks/manipulación más allá de lo que `WA_CLIENT_INTEGRITY.md` ya encontró ausente | las bibliotecas nativas stripped no se retrazaron exhaustivamente para este reporte más allá de la búsqueda de strings en §3 |
| Manejo del lado del servidor de una visibilidad tipo `wae_stanzas.txt` interceptada por WaEnhancer (es decir, si el servidor puede distinguir un cliente hookeado de uno genuino a nivel de protocolo) | no observable estáticamente |
