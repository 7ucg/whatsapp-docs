<!-- src-sha1: 3f456309f1ce11a70a08dd912d84e40193c760ad -->
# WhatsApp Cuenta Administrada — Informe Completo de Ingeniería Inversa
**Versión:** 2.26.41.6 | **Fecha:** 2026-11-01
**Alcance:** el sistema de supervisión parental "cuenta administrada" visible para el cliente (vinculación patrocinador/dependiente, roles, experiencia por edad, PIN, ajustes de privacidad, desvinculación, operaciones w:mex, almacenamiento local, flags de funcionalidad); el conjunto de señales distinto y no relacionado para números de empresa operados por un Business Solution Provider a través de la Cloud API (emisor del certificado de nombre verificado, campos host-storage/actual-actors, UI de coexistencia, tipo de cuenta multi-dispositivo hosted); cómo se distinguen ambos

---

## 1. Qué significa "administrada" en este cliente

Dos sistemas no relacionados en 2.26.41.6 usan un lenguaje que un lector externo llamaría "cuenta administrada" ("managed account"). No comparten código, ni proto, ni esquema w:mex. Todas las afirmaciones son análisis estático del APK decompilado; nada fue capturado en el tráfico. Nivel: **found** (encontrado) = leído en código o assets, **inferred** (inferido) = deducido del código, **unknown** (desconocido) = no resuelto.

| Sistema | Nombre(s) interno(s) en el código | Qué es "administrado" | Dónde | Sección |
|---|---|---|---|---|
| Supervisión parental | `com.whatsapp.managedaccount.*`, `com.whatsapp.pma.*`, `com.whatsapp.pmta.*`; nombres de código internos **PAA**, **PMA**, **PMTA** (encontrados en nombres de paquetes/clases/prefs, nunca desarrollados en cadenas de texto) | la propia cuenta de WhatsApp de un menor ("dependiente"), supervisada por una cuenta de padre/tutor ("patrocinador") | `w:mex`, SQLite/SharedPrefs local | 2-8 |
| Delegación de un número de empresa a un proveedor | ninguna cadena "BSP" o "proveedor técnico" en ningún lugar del cliente; la UI lo llama "un servicio seguro de Meta" u "otras empresas" | el número de WhatsApp de una **empresa**, cuyos mensajes son gestionados/alojados por la infraestructura en la nube de Meta y/o un proveedor externo en lugar del propio dispositivo de la empresa | certificado de nombre verificado (`w:biz`), tipo de cuenta multi-dispositivo "hosted" | 9 |

Los recursos de cadena `str2fc9`/`str3139` ("Managed account"), `str30ae`, `str3109`, `str439d`/`str439f` y la pantalla de ajustes a la que pertenecen son **todos** del sistema parental (sección 2). No existe ninguna etiqueta "Managed account" en ningún lugar del cliente para una empresa operada por un BSP; ese caso se señala únicamente mediante campos del certificado y banners de chat/llamada (sección 9). Esta es la corrección clave antes de usar el término: una nota de ingeniería inversa o un ticket que diga "cuenta administrada" sobre el número de una *empresa* se refiere a la sección 9, no a nada llamado `ManagedAccount*` en el código.

---

## 2. Supervisión parental: roles y relación de cuentas

### 2.1 Roles

`EnumC08540Ng` (found), con una etiqueta de depuración por constante:

| Rol | Etiqueta de depuración | Quién |
|---|---|---|
| `NONE` | "None" | ninguna relación de supervisión |
| `DEPENDENT` | "Dependent" | la propia cuenta del menor |
| `SPONSOR` | "Sponsor" | la cuenta del padre/tutor |
| `SPONSOR_ADMIN` | "Sponsor Admin" | un patrocinador con derechos elevados (derechos extra exactos no rastreados) |

El rol del dispositivo actual se lee del estado local mediante `SharedPreferencesOnSharedPreferenceChangeListenerC08490Nb.A04()` y se cachea en `C08530Nf` ("ManagedAccountStartupPreferences", nombre inferido a partir de su etiqueta de log `ManagedAccountStartupPreferences/...`).

### 2.2 La relación es de cuenta a cuenta, no de dispositivo a dispositivo

El dependiente tiene **su propio número de teléfono y su propio registro completo de WhatsApp** (su propio dispositivo primario, sus propios dispositivos complementarios multi-dispositivo si los hay). El patrocinador es igualmente una cuenta normal, registrada de forma independiente. Lo que los vincula es un registro del lado del servidor, reflejado localmente como:

```
ManagedAccountConnection(
  connectionLid,      // C14080dr — the dependent's LID, found
  role,                // EnumC08540Ng, found
  linkTs,              // long, link creation time, found
  connectionPnJid,     // PhoneUserJid — the dependent's phone-number JID, found
  graduationState,      // C4DV, section 2.3
  ageExperience)        // EnumC96934Gf, section 2.3
```

(`AnonymousClass586`, found; campos confirmados por su `toString`.) No hay QR de emparejamiento, ni firma ADV, ni intercambio de claves de dispositivo complementario en ninguna parte de este paquete — compárese con el protocolo real de dispositivo complementario en `WA_LINKED_DEVICE_PAIRING.md` sección 5, que no está relacionado. El punto de entrada de la incorporación es un deep link gestionado por `ManagedAccountSponsorOnboardingViewModel` (paquete `managedaccount.deeplink`, found), no un flujo basado en escaneo.

### 2.3 Experiencia por edad y graduación

`EnumC96934Gf` (found): `UNKNOWN`, `U13`, `U16_BR`, `U18_BR`, `U18`, `STANDARD` (Brasil tiene sus propias franjas de edad). `A00()` en este enum devuelve true para `U16_BR`, `U18_BR`, `U18` — los estados que el código trata como "a punto de salir de la supervisión."

`C4DV` (estado de graduación, found): `PRE_GRADUATION`, `GRADUATION`, `PRE_GRADUATION_IMMINENT`, `UNKNOWN`. `ManagedAccountGraduationManager` y su ruta `triggerTeenGraduationEagerly` (found) sacan a un dependiente de la supervisión a medida que se acerca o cruza un umbral de edad; `ManagedAccountPmtaSponsorGraduationNuxActivity` y `ManagedAccountSponsorGraduationNuxActivity` muestran el NUX del lado del patrocinador para esta transición.

`ManagedAccountLinkingRepository.A00` (found) vuelve a obtener la experiencia por edad ante un conflicto HTTP 409 de la llamada de vinculación, es decir, el servidor puede rechazar la vinculación porque la experiencia por edad almacenada está obsoleta y el cliente debe volver a consultar `WaAgeExperienceRepository` antes de reintentar.

---

## 3. Flujo de vinculación y operaciones w:mex

### 3.1 Catálogo de operaciones

Los nueve nombres de operación y valores de `doc_id` siguientes se leyeron directamente de `assets/whatsapp-android-mex_client_persist_ids.json` en esta build (found) — no inferidos de un cliente de terceros. El esquema de las nueve es `whatsapp-android-mex` (clave de asset: `whatsapp_mex`).

| Operación | doc_id | Punto de llamada encontrado | Variables (esta build) |
|---|---|---|---|
| `ManagedAccountInitiateLinkingQuery` | `26671873552498548` | `MexManagedAccountInitiateLinkingApi.A00` | `input:{"dummy": null}` — **no se envía `phone_number`**; una suposición previa de que esta llamada transporta el número del dependiente no se sostiene para este punto de llamada |
| `ManagedAccountQuery` | `27232244463035262` | `ManagedAccountStateSynchronizer.A01` | `input:{"unused": null}` — **no hay `jid`**; la consulta está ligada a la sesión, no parametrizada por JID en este punto de llamada |
| `ManagedAccountValidateLinkingQuery` | `35449808311284430` | referenciada (coincidencia de nombre en assets); variables no rastreadas a un punto de llamada en esta build | desconocido |
| `ManagedAccountAcceptLinkingMutation` | `26708926155457677` | referenciada; variables no rastreadas | desconocido |
| `ManagedAccountCompleteLinkingMutation` | `26866501363013203` | referenciada; variables no rastreadas | desconocido |
| `ManagedAccountRevokeLinkingMutation` | `27435058196100677` | referenciada; variables no rastreadas | desconocido |
| `ManagedAccountSyncActivities` | `26594352680227840` | referenciada; variables no rastreadas | desconocido |
| `ManagedAccountUpdatePinMutation` | `27653949584193082` | referenciada; variables no rastreadas | desconocido |
| `ManagedAccountGetSponsorAgeVerificationInfoQuery` | `26433623289634522` | referenciada; variables no rastreadas | desconocido |

Los cuerpos de respuesta más allá de los envoltorios genéricos de éxito/error no se leyeron para ninguna de las nueve; el resultado de éxito de `ManagedAccountInitiateLinkingQuery` (`C135065o7`, `toString()` literalmente `"PAA Initiate Linking Success"`, found) transporta dos strings y un int cuyos nombres de campo no están resueltos — casi con certeza un token/URL de deep link de vinculación y una expiración, pero eso es inferido, no leído de un campo con nombre.

Existe una ruta separada, no-mex: `C14E.java` (`PaaAcceptLinkingIBHandler`) analiza una stanza/notificación entrante que transporta un atributo `sponsor_jid` (found) — esto es un push del servidor que activa la UI, no la propia solicitud de `AcceptLinkingMutation`.

### 3.2 Reintento ante fallo de entrega

`MexManagedAccountInitiateLinkingApi.A01` reintenta la llamada de inicio hasta un número de veces indicado por el llamador en caso de error con código **471** ("delivery failure"), registrando `MexManagedAccountInitiateLinkingApi/requestSponsorLinkingMaterial delivery failure, retrying` (found).

---

## 4. Modelo de dispositivo/sesión

No existe **ningún vínculo de dispositivo de tipo complementario** entre patrocinador y dependiente, ni entre ninguna de las cuentas y ninguna infraestructura operada por WhatsApp. Cada lado es una cuenta de WhatsApp ordinaria, registrada de forma independiente (su propio número de teléfono, su propio dispositivo primario, sus propios dispositivos vinculados opcionales bajo el sistema normal multi-dispositivo descrito en `WA_LINKED_DEVICE_PAIRING.md`). La relación de supervisión es un registro del lado del servidor indexado por el LID y el JID de número de teléfono del dependiente (sección 2.2), sincronizado a ambos lados mediante `w:mex`, no una nueva sesión, emparejamiento o identidad ADV.

Esta es una diferencia estructural respecto al caso BSP/Cloud API de la sección 9, donde el "dispositivo" del número de empresa no es en absoluto un teléfono — véase la sección 9.3 sobre cómo se representa eso en el modelo multi-dispositivo existente.

---

## 5. Ajustes y permisos

### 5.1 Pantalla de privacidad del lado del dependiente

`DependentAccountPrivacyActivity` (found) agrupa los ajustes en tres secciones mediante el enum `C9SE`:

| Sección | Constante `C9SE` | Contenido |
|---|---|---|
| Visibilidad | `VISIBILITY` (0) | quién puede ver la información de perfil del dependiente |
| Contacto | `CONTACT` (1) | quién puede contactar al dependiente |
| Control del patrocinador | `SPONSOR_CONTROL` (2) | ajustes que controla el patrocinador, no el dependiente |

La pantalla enlaza a "controles parentales" mediante la cadena `str2fc8`: *"Your account is managed by your parent or guardian. They can make changes in parental controls."* Existe una barrera de preferencia local para uno de estos controles: `privacy_dependent_account_messages` (int, valor predeterminado `1`), leída por `C08520Ne.A06()` y consultada únicamente cuando la cuenta es un patrocinador (found) — es decir, quién puede escribirle al dependiente es algo que el estado de la app del **patrocinador** controla, no un valor que el dependiente establezca.

### 5.2 Controles del lado del patrocinador

`SponsorControlsHubActivity` (found) es el panel del patrocinador, que lista a los dependientes (fragmento/etiqueta de log `"sponsor-controls-dependents"`) con un adaptador de foto de contacto por dependiente. `SponsorControlsDependentInfoActivity` abre el detalle de un dependiente. `ManageNotificationsActivity` / `ManageNotificationsFragment` y `ActivityAlertsFragment` / `ManagedAccountDependentActivityAlertHandler` configuran y entregan **alertas de actividad** — notificaciones al patrocinador sobre la actividad del dependiente en la app (`ManagedAccountSyncActivities`, sección 3.1, es la fuente de datos, controlada por el flag **31562** en `ManagedAccountAlertInfoActivity`, found).

### 5.3 PIN

`SponsorPinSetupFragment`, `SponsorPinConfirmFragment`, `ManagedAccountChangePinActivity`/`ManagedAccountChangePinFragment`/`ManagedAccountConfirmChangePinFragment` (found, por presencia de clase) implementan la creación y el cambio del PIN establecido por el patrocinador; la mutación es `ManagedAccountUpdatePinMutation` (sección 3.1; los nombres exactos de campo `old_pin`/`new_pin` no están confirmados en esta build — desconocido). Una sincronización del lado del dependiente puede fallar específicamente por falta de PIN: `ManagedAccountStateSynchronizer` registra `"ManagedAccountStateSynchronizer/fetchAndSync missing sponsor PIN for child user"` y devuelve un resultado de error cuando el tipo de servidor/respuesta es `C135095oA` (found) — la sincronización de estado del dependiente depende de que el patrocinador tenga el PIN establecido.

### 5.4 Desvinculación

`ManagedAccountUnlinkAccountSettingsActivity` (found) muestra uno de varios textos de confirmación según los flags transportados en los argumentos del fragmento: `is_pmta` (una subvariante "PMTA" distinta), `is_teen_dependent`, y si el dependiente tiene o no un nombre público — cadenas `str49cb`…`str49d3`, por ejemplo *"Your account will no longer be managed by %1$s"* / *"...by your parent"*. `ManagedAccountRevokeLinkingMutation` (sección 3.1) es la operación de red que se infiere respalda esta acción; no se rastreó a la propia activity invocándola directamente en esta pasada.

### 5.5 Barrera de reautenticación

`ManagedAccountAuthInterstitialActivity` alberga `PmaAuthInterstitialFragment` (paquete `com.whatsapp.pma.product.dependent.fragments`, found) y se lanza con una cadena `extra_auth_entry_point` — un paso de reautenticación que controla la entrada a las pantallas de cuenta administrada desde un punto de entrada dado. El mecanismo exacto de autenticación (PIN del dispositivo, biometría, contraseña de la cuenta) no fue rastreado.

### 5.6 Superficies de depuración

`ManagedAccountDebugConnectionActivity` y `ManagedAccountDebugPinAuthActivity` existen en esta build (found). Nada en esta pasada establece si son alcanzables desde la UI de producción o solo desde un flag de build interno/de depuración (inferido: solo depuración, por convención de nombres y por la ausencia de cualquier ruta de lanzamiento descubierta desde las pantallas de producción).

---

## 6. Almacenamiento

| Almacén | Claves / columnas | Contenido |
|---|---|---|
| Registro local de relación | `connectionLid`, `role`, `linkTs`, `connectionPnJid`, `graduationState`, `ageExperience` (sección 2.2) | una fila por conexión patrocinador↔dependiente |
| SharedPrefs | `paa_graduation_nux_pending`, `paa_sponsor_blocked`, `paa_nux_education_banner_dismissed`, `paa_nux_education_banner_start_timestamp`, `paa_review_privacy_settings_banner_dismissed_dependent_<lid>`, `privacy_dependent_account_messages` | estado de descarte de NUX/banner, flag de patrocinador bloqueado, la única barrera confirmada de mensajería al dependiente |

Todas las claves encontradas textualmente en `C08530Nf`, `ManagedAccountBannerManager`, `C08520Ne`.

---

## 7. Cadenas de indicador de UI

| Id de cadena | Texto | Dónde se usa |
|---|---|---|
| `str2629` | "Create a parent-managed account" | entrada de incorporación |
| `str2fc9` / `str3139` | "Managed account" | insignia/etiqueta |
| `str30ae` | "Managed accounts can't see this message. Learn why" | contenido restringido |
| `str3109` | "This is a managed account. Learn more" | aviso de chat/perfil |
| `str3751` / `str3752` / `str3754` | mensajes de inelegibilidad ("isn't eligible for a parent-managed account", "Couldn't create parent-managed account") | fallo de incorporación |
| `str439d` / `str439f` | "Settings for managed accounts" / "View activity and choose settings for managed accounts" | punto de entrada a ajustes |
| `str2fc8` | "Your account is managed by your parent or guardian..." | `DependentAccountPrivacyActivity` |
| `str49cb`-`str49d3` | variantes de confirmación de desvinculación | `ManagedAccountUnlinkAccountSettingsActivity` |

`ManagedAccountNotAvailableActivity` y `ManagedAccountAgeUnknownActivity` (found por nombre de clase) respaldan dos estados más — que la función no se ofrezca, y que la edad de la cuenta no esté determinada — texto exacto no resuelto.

---

## 8. Flags de funcionalidad

| ID | Dónde | Controla |
|---|---|---|
| **30174** | `C08520Ne.A02`, `ManagedAccountSponsorUpsellActivity` | elegibilidad del upsell de patrocinador |
| **31562** | `ManagedAccountAlertInfoActivity` | barrera de la funcionalidad de alertas de actividad |
| **34268** | `C08520Ne.A01` | una comprobación de permiso adicional (rol no resuelto más allá de la propia barrera) |
| **16763** | `C08520Ne.A04` | barrera booleana no resuelta |
| **33355** | `C08520Ne.A05` | barrera booleana no resuelta, condicionada al dependiente o a una interfaz secundaria |

---

## 9. Números de empresa delegados a un proveedor (Cloud API / BSP)

Este es el sistema que realmente corresponde a "una cuenta de empresa operada en nombre de por un proveedor." No comparte clase, proto ni esquema w:mex con las secciones 2-8. Ninguna cadena en esta build dice "BSP," "tech provider," "Business Solution Provider," "on-premises API," ni "Cloud API" al usuario; la señal es estructural.

### 9.1 Certificado de nombre verificado: prefijo del emisor y `PrivacyMode`

El cliente almacena un registro local de certificado de nombre verificado por JID de empresa con columnas (found, `AbstractC218419al`): `verified_name`, `industry`, `city`, `country`, `verified_level`, `cert_blob`, `identity_unconfirmed_since`, `host_storage`, `actual_actors`, `privacy_mode_ts`. Estos tres últimos campos se extraen de un hijo con estilo `<biz host_storage="" actual_actors="" privacy_mode_ts=""/>` de una stanza `w:biz` (found, múltiples puntos de llamada, por ejemplo `O0F.java`, `C18670m9.java`, `AbstractC24816AmW.java`) hacia `AnonymousClass118` ("`PrivacyMode`" según su propio `toString()`), cuyos dos campos enteros son:

| Campo | Valores vistos en el código | Significado |
|---|---|---|
| `hostStorage` | 0 (predeterminado/no establecido), 1, 2 | qué infraestructura almacena/retransmite los mensajes de la empresa; mapeo **inferido** a los términos públicos de WhatsApp Business Platform on-premises (autoalojado) vs. alojado por Meta (Cloud API) vs. un tercer estado, dual/transicional — el cliente no tiene constantes con nombre para estos tres valores |
| `actualActors` | 0 (predeterminado/no establecido), 1, 2 | quién opera realmente la cuenta día a día; mapeo **inferido** a autooperado vs. operado por un proveedor — de nuevo, sin constantes con nombre en este cliente |

Una segunda señal, encontrada de forma independiente en el mismo envoltorio de certificado (`AnonymousClass119.A02()`/`A03()`), lee la **cadena del emisor** del certificado (campo `A07`) y la clasifica por prefijo (found, código exacto):

```java
public boolean A01() { return this.A01 == 2; }        // hostStorage == 2
public boolean A02() { return this.A07 != null && this.A07.startsWith("ent:"); }
public boolean A03() { return this.A07 != null && this.A07.startsWith("smb:"); }
```

`"ent:"` y `"smb:"` son los dos prefijos de emisor que este cliente distingue (found, cadenas literales). `smb:` corresponde a un certificado emitido para la app WhatsApp Business normal, autooperada; `ent:` corresponde a un certificado emitido para una ruta empresarial/integrada por API — este es el equivalente más próximo a nivel de código, de primera parte, a "cuenta de empresa autogestionada" vs. "cuenta de empresa gestionada por BSP/Cloud API" (el mapeo de los prefijos a esas dos categorías del mundo real es **inferido** a partir de los propios prefijos y de cómo se consumen en `AbstractC198638cc.A00`, no de ninguna cadena de documentación propia del cliente).

`AbstractC198638cc.A00` combina la comprobación del emisor y un booleano separado (`A09`, significado no resuelto — posiblemente "certificado ausente/revocado," coherente con el texto de cara al usuario "ya no es una cuenta de empresa oficial" de la sección 9.2) en un código de "cliente" de 4 valores (found):

```java
public static final int A00(AnonymousClass119 c) {
    if (c != null) {
        if (c.A09) return 4;
        if (c.A03()) return 2;   // smb: issuer
        if (c.A02()) return 3;   // ent: issuer
    }
    return 1;                    // default / no certificate
}
```

### 9.2 Banners de coexistencia y `business_state_id`

`C198628cb` ("`BusinessState`" según su `toString()`) combina el `PrivacyMode` del certificado (9.1), el código de "cliente" de 4 valores, y un booleano `isVerified` en un único entero aplanado que la UI llama `business_state_id` (found, establecido desde `c198628cb.A02()` en `EncryptionChangeDialogFragment` y leído de la misma forma en `PrivacyInfoBottomSheet`/`ContactInfoActivity`). La función de mapeo hace pattern-matching de 18 tuplas explícitas `(client, actualActors, hostStorage, flag)` a los ids **0-17**; la tabla completa no pudo reconstruirse (JADX reporta un error de region-overflow en este método específico, y varias ramas quedan fusionadas por el decompilador), pero lo siguiente está establecido directamente a partir del código:

- el id **15** se alcanza siempre que el código de "cliente" es igual a 4 (certificado ausente/revocado), independientemente de los demás campos.
- los ids **5, 6, 9, 10** son los únicos alcanzables cuando un método de barrera secundaria `A05()` (una comprobación de tipo bloqueo/silencio no relacionada, sobre el chat) es verdadero, y también son alcanzables a través de la ruta normal cuando `hostStorage == 2` — estos conducen de forma consistente a las cadenas simples *"This business uses a secure service from Meta to manage this chat/call"* (`str080d`/`str080f`/`str0c9c`/`str0f5a`, found, puntos de llamada verificados por id de recurso en `C23324A5w`/`ContactInfoActivity`).
- los ids **16** y **17** son los casos residuales (ni una tupla conocida ni el id 15) y conducen a la familia de cadenas "multiple tools" / "no longer an official business account" (`str38ef`-`str38fb`, `str08b3`-`str08c7`): *"This business has chosen to use multiple tools to chat with its customers... Chats between only you and this business are managed by a secure service from Meta... this business is using the WhatsApp Business app"* — es decir, el estado de **coexistencia**, en el que el número es alcanzable tanto a través de la app Business en un dispositivo como a través de una ruta alojada por API al mismo tiempo, controlado por los flags **12729**, **18047**, **23933**, **7131**, **29343** (found, en `PrivacyInfoBottomSheet`/`ContactInfoActivity`, cada uno seleccionando entre un par de cadenas antiguo y uno nuevo para el mismo estado).

El resultado IQ de `remove-companion-device` en el flujo multi-dispositivo no relacionado puede transportar un hijo `coex_token` (`WA_LINKED_DEVICE_PAIRING.md` §7.1) — el mismo concepto de "coexistencia", consumidor no rastreado tampoco desde ese lado.

### 9.3 Modelo de dispositivo/sesión para un número alojado por un proveedor

Un número de empresa completamente alojado por Meta (el caso Cloud API sin ningún dispositivo físico) se representa dentro del sistema multi-dispositivo **existente**, no uno nuevo:

- el tipo de cuenta `HOSTED` (`EnumC32116E1o`, valor 1) y el id de dispositivo **99** están reservados para este caso (`WA_LINKED_DEVICE_PAIRING.md` §5.1, §9.2).
- la enumeración `companion-props.platformType` que el primario almacena para sus propios dispositivos vinculados incluye el valor **23 = `CLOUD_API`** (`WA_LINKED_DEVICE_PAIRING.md` §6.2), junto con **27 = `BUSINESS_BACK_OFFICE`** y **25/26 = `WAIL`/`WASS`** — todos tipos de plataforma de infraestructura de empresa en el mismo enum que los teléfonos/escritorios/web ordinarios.
- la build de consumidor de este informe **se niega** activamente a emparejar un dispositivo hosted desde el lado primario (código de error local **-10**, `WA_LINKED_DEVICE_PAIRING.md` §3.2) — el aprovisionamiento hosted/Cloud API no es algo que este cliente inicie; solo observa el tipo de cuenta y los marcadores de plataforma resultantes en cuentas que ya lo tienen.

No se encontró ningún flujo de emparejamiento, firma ADV o clave de dispositivo complementario para la propia relación BSP/Cloud API en ninguna parte de este APK; la maquinaria de usuario canónico/contraseña de la seguridad de cuenta (`WA_ACCOUNT_SECURITY.md`) y la maquinaria de identidad multi-dispositivo no están relacionadas con cómo un BSP llega a operar un número — ese aprovisionamiento ocurre enteramente del lado del servidor / en la plataforma de empresa de Meta y no deja rastro en este cliente más allá de los marcadores anteriores.

### 9.4 Telemetría

El evento de registro `wam_ts_navigation` (`C1EO`, found) transporta tres booleanos de contexto de empresa independientes por navegación registrada: `is_cloudapi`, `is_onpremises`, `is_smb`, además de `is_canonical_ent_present` e `is_meta_ai_thread`. `ChatDescription` (`com.whatsapp.gapenforcement.dto`) transporta por separado `isEnterpriseBusiness`. Ninguna de las dos clases expone cómo se calculan estos booleanos más allá de lo que ya describen las secciones 9.1/9.2; son solo de reporte y no controlan ningún comportamiento visible para el usuario en los archivos leídos.

---

## 10. Distinciones clave

| A | B |
|---|---|
| "Cuenta administrada" (`ManagedAccount*`, PAA/PMA/PMTA) — **la propia cuenta de un menor**, supervisada por un padre | un número de empresa **operado por un proveedor** a través de Cloud API — ninguna cadena "managed account" en ningún lugar para este caso |
| Vínculo patrocinador/dependiente: dos cuentas de WhatsApp independientes, registradas normalmente, sin emparejamiento de dispositivo | número de empresa hosted: una sola cuenta, `accountType=HOSTED`, id de dispositivo 99, sin ningún dispositivo complementario |
| Operaciones w:mex `ManagedAccount*`, esquema `whatsapp-android-mex` (sección 3.1) | campos de certificado de nombre verificado sobre `w:biz` (`host_storage`, `actual_actors`) — stanza distinta, esquema distinto |
| Banners de coexistencia de `business_state_id` (app Business autogestionada **y** hosted por API a la vez) | una empresa puramente autogestionada (app WhatsApp Business normal en su propio dispositivo, prefijo de emisor `smb:`) |
| Flag de telemetría `is_smb` (empresa pequeña/mediana que usa la app Business) | flags de telemetría `is_cloudapi` / `is_onpremises` (alojamiento del lado de la API) |
| `ManagedAccountRevokeLinkingMutation` (termina la supervisión parental) | `remove-companion-device` (no relacionado: elimina un dispositivo vinculado; véase `WA_LINKED_DEVICE_PAIRING.md` §7) |

---

## 11. Flujos completos

### 11.1 Supervisión parental: vinculación de un dependiente

```
[Sponsor]                                  [Server]                         [Dependent]
   │ deep link / in-app entry                  │                                 │
   ▼                                            │                                 │
ManagedAccountInitiateLinkingQuery (no vars) ──►│
   │◄── linking material (token/URL, expiry)    │
   │  share with dependent (deep link / code)   │
   │                                            │                                 │
   │                                            │◄── dependent opens link ───────│
   │                                            │   ManagedAccountValidateLinkingQuery {linking_token, sponsor_jid} (assets; call site not traced)
   │                                            │   ManagedAccountAcceptLinkingMutation {linking_token} (assets; call site not traced)
   │◄── notification: sponsor_jid (PaaAcceptLinkingIBHandler) ────────────────────│
   │                                            │   ManagedAccountCompleteLinkingMutation {linking_token} (assets; call site not traced)
   ▼                                            │                                 ▼
local ManagedAccountConnection row created on both sides (role=SPONSOR / DEPENDENT, connectionLid, connectionPnJid, linkTs)
   │                                            │                                 │
   ▼                                            │                                 ▼
periodic ManagedAccountQuery (no vars) + ManagedAccountSyncActivities ──────────► sponsor controls hub / activity alerts
```

### 11.2 Número de empresa delegado a un proveedor: lo que ve el cliente del interlocutor

```
[Peer opens a chat/profile/call with the business number]
   │
   ▼
local verified-name cert for that JID: host_storage, actual_actors, privacy_mode_ts, issuer (smb:/ent:)
   │
   ▼
C198628cb.A02() → business_state_id (0-17)
   │
   ├─ id 15 (certificate missing/revoked)          → "no longer an official business account" (str08b3 family)
   ├─ ids 5/6/9/10 (hostStorage==2, or chat-gated)  → "uses a secure service from Meta to manage this chat/call" (str080d/f family)
   └─ ids 16/17 (coexistence residual states)       → "uses multiple tools... Business app AND a secure service from Meta" (str38ef-fb family)
```

---

## 12. Desconocidos

| Tema | Razón |
|---|---|
| Tabla completa tupla→`business_state_id` (los 18 valores) | error de region-overflow del decompilador en `C198628cb.A02()`; varias ramas fusionadas |
| Significado numérico exacto de `hostStorage`/`actualActors` más allá del proxy de prefijo de emisor `smb:`/`ent:` | sin constantes con nombre en este cliente; el mapeo a los términos on-premises/Cloud API/BSP es inferido a partir de la terminología pública de Business Platform, no leído del código |
| Variables/campos de respuesta de `ManagedAccountValidateLinkingQuery`, `AcceptLinkingMutation`, `CompleteLinkingMutation`, `RevokeLinkingMutation`, `SyncActivities`, `UpdatePinMutation`, `GetSponsorAgeVerificationInfoQuery` | doc_ids confirmados en assets; no se encontró ningún punto de llamada con nombres de variable en esta build |
| Significado del booleano `A09` que alimenta el código de "cliente" 4 | consumido solo como barrera; sin nombre ni comentario |
| Derechos extra de `SPONSOR_ADMIN` frente a `SPONSOR` | el rol existe; el comportamiento diferenciado no fue rastreado |
| Desarrollo de los nombres de código PAA / PMA / PMTA | nunca explicitado en cadenas o comentarios; solo contexto de uso |
| Alcanzabilidad de `ManagedAccountDebugConnectionActivity`/`DebugPinAuthActivity` desde builds de producción | el nombre sugiere solo depuración; no se encontró ruta de lanzamiento en ningún sentido |
| Aprovisionamiento del lado del servidor de un número hosted por Cloud API (sección 9.3) | enteramente del lado del servidor; este cliente nunca lo inicia y solo observa los marcadores resultantes |
| Si algún código del cliente puede distinguir "operado directamente por Meta" de "operado por un BSP externo a través de la Cloud API de Meta" | ambos parecen colapsar en las mismas señales de `hostStorage`/`actualActors`/tipo de plataforma; no se encontró ningún campo identificador de BSP separado |
| Tráfico real | solo análisis estático |
