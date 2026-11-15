<!-- src-sha1: 03dc5e8e2a1874ff243bbae88accc3b09b397b6f -->
# WhatsApp Consentimiento del Sponsor para Cuentas de Adolescentes — Full RE Report
**Versión:** 2.26.45.10 | **Fecha:** 2026-11-15
**Alcance:** el paquete `com.whatsapp.vpc.sponsor` — una pantalla de revisión para un padre/tutor ("sponsor") sobre la cuenta de WhatsApp de un menor ("teen"), su modelo de navegación, la compuerta de verificación de edad del lado sponsor, las tres pantallas de resultado (aprobado/rechazado/no-se-puede-revisar), la consecuencia `account_deletion_time_ms` al rechazar, qué es y qué no es alcanzable o rastreado en el cable, y la distinción respecto al sistema de supervisión parental de `WA_MANAGED_ACCOUNT.md`

---

## 1. Qué es esto

Nuevo en `2.26.45.10` (ausente de la base `2.26.41.6`): cuatro clases bajo
`com.whatsapp.vpc.sponsor` que implementan una decisión de revisión de una sola vez que un
padre/tutor toma sobre la cuenta de WhatsApp de un menor — aprobarla, rechazarla, o reportar
que no puede revisarla. Esto es estructuralmente distinto del producto existente de supervisión
parental de `WA_MANAGED_ACCOUNT.md` (la sección 8 de abajo detalla la distinción); se lee como
WhatsApp adoptando el mismo patrón de seguridad de cuenta-de-adolescente que Meta ya envía para
Instagram y Facebook: un tutor debe dar el visto bueno a que un menor tenga una cuenta siquiera,
con una consecuencia de eliminación de cuenta en caso de rechazo.

"VPC" no se deletrea en ninguna parte del cliente; "Verified Parent/guardian Consent" es la
lectura más plausible dada la forma de la función — **inferred**, no una expansión de string
encontrada.

| Entidad | Clase | Rol |
|---|---|---|
| Pantalla anfitriona | `VpcSponsorActivity` | no exportada, sin intent-filter — mecanismo de lanzamiento no resuelto (§6) |
| View model | `X/B18` | guarda los argumentos de lanzamiento requeridos, corre la compuerta de edad, conduce la navegación |
| Despachador de nav/resultado | `X/CaB` | clase compartida (también respalda la `ConsentFlowActivity` de verificación de edad no relacionada y `WamoSubActivity`); la rama que maneja los eventos de `VpcSponsorActivity` es lo que rastrea este informe |
| Resultado aprobado | `VpcSponsorApprovedFragment` | se muestra al aprobar |
| Resultado rechazado | `VpcSponsorDeclinedFragment` | se muestra al rechazar; muestra la cuenta regresiva de eliminación |
| Resultado no-se-puede-revisar | `VpcSponsorCannotReviewFragment` | se muestra cuando no se pudo verificar al sponsor para revisar |

Todos los hallazgos son análisis estático de la APK decompilada (decodificación smali de `apktool`;
sin corrida JADX de la APK completa, según la práctica de seguridad de este repositorio para builds
grandes). Nada aquí se capturó en el cable ni se ejercitó en runtime. Niveles de evidencia:
**found** = leído directamente en smali (un literal de string, campo, o clase); **inferred** =
razonado a partir de la estructura del código sin un literal que lo nombre; **unknown** = no
resuelto en esta pasada.

Las mismas cuatro clases existen, sin cambios byte por byte en la disposición de campos/strings, en
`com.whatsapp.w4b` (WhatsApp Business) `2.26.45.7` — **found** por presencia de clase; no
re-rastreado independientemente, se asume que el rastreo del build de consumer de abajo aplica.

---

## 2. Modelo de navegación

La pantalla se conduce por un tipo de destino sellado, `LX/CvW` (found por presencia de clase; la
interfaz en sí no lleva ningún string auto-identificador), con siete implementaciones
identificadas por sus propios literales `toString()` (found):

| Clase | `toString()` | Qué hace |
|---|---|---|
| `X/CSM` | `"AgeCollectionScreen"` | desvía hacia el flujo compartido de verificación de edad cross-app de Meta |
| `X/CSO` | `"ConsentNoticeScreen"` | el prompt real de aprobar/rechazar — **no renderizado en ningún lugar de este paquete**, ver §4 |
| `X/CSN` | `"ApprovedScreen"` | muestra `VpcSponsorApprovedFragment` |
| `X/CSS` | `"DeclinedScreen(accountDeletionTimeMs=...)"` | muestra `VpcSponsorDeclinedFragment`; lleva una marca de tiempo `long` de eliminación |
| `X/CSR` | `"CannotReviewScreen(teenName=...)"` | muestra `VpcSponsorCannotReviewFragment`; lleva el nombre visible del adolescente |
| `X/CSP` | `"ErrorExit"` | muestra el diálogo con tag `vpc_sponsor_error_exit_dialog`, finaliza la activity al descartarse |
| `X/CSQ` | `"Exit"` | finaliza la activity inmediatamente |

---

## 3. Argumentos de lanzamiento requeridos y la compuerta de edad del sponsor

El constructor de `X/B18` (found) lee tres claves de los argumentos de estado guardado/navegación
de la activity, dos de ellas requeridas — un valor faltante lanza `IllegalStateException("Required
value was null.")`:

| Clave | Tipo | Notas |
|---|---|---|
| `vpc_teen_name` | `String` | requerida; el nombre visible del adolescente, copiado después al bundle de la pantalla de no-se-puede-revisar como `teen_name` plano |
| `vpc_account_deletion_time_ms` | número boxeado (`.longValue()`) | presencia requerida, pero el valor leído aquí se **descarta** — confirmado leyendo el bytecode del constructor, el local nunca se almacena en un campo. El número que la pantalla de rechazo realmente muestra viene de un campo separado `X/CSS.A00` fijado después, cuando el resultado de la revisión produce un destino `DeclinedScreen` |
| `navigation` | nullable, comparado contra `X/CSM.A00` | si está presente y no es `AgeCollectionScreen`, siembra el destino inicial directamente (p. ej. un flujo reanudado/reiniciado) |

Si no se siembra ningún destino inicial, `B18` llama a
`Lcom/whatsapp/dobverification/ContextualAgeCollectionRepository;->A06()Ljava/lang/Boolean;` — un
booleano **nullable** (found):

- **`null`** → navega a `AgeCollectionScreen`. El despachador compartido `X/CaB` lanza una
  **pantalla de verificación de edad Bloks** para este estado — la misma ruta de código que usa la
  `ConsentFlowActivity` no relacionada para los chequeos de edad al momento del registro (línea de
  log `"ConsentFlowActivity/navigate/launch Bloks age verification screen"`, encontrada en la clase
  compartida, no específica de vpc, pero la rama que alcanza el estado `AgeCollectionScreen` de
  vpc-sponsor).
- **`true`** → navega a `ConsentNoticeScreen`.
- **`false`** → navega a `CannotReviewScreen(teenName)`.

La pantalla Bloks reporta de vuelta a través de
`VpcSponsorActivity.onAgeCollectionResult(ContextualAgeCollectionUsecaseApi$CACResult)` (found,
firma exacta), re-corriendo la misma decisión de tres vías desde el subtipo `CACResult` en lugar de
un booleano plano: un resultado que lleva un booleano re-entra en las ramas `true`/`false` de
arriba; un resultado descartado/bloqueado enruta a `Exit`; un resultado de edad-no-disponible o
fallido enruta a `ErrorExit`.

**Interpretación (inferred, no nombrada en el cliente):** el *sponsor* — no el adolescente — debe
pasar el chequeo compartido de verificación de edad cross-app de Meta antes de que se le muestre el
prompt de aprobar/rechazar. Un sponsor que no puede o no quiere completarlo nunca llega a la
decisión de consentimiento real; se le enruta a `CannotReviewScreen`, `Exit`, o `ErrorExit` según
cómo se resolvió el chequeo de edad.

---

## 4. El prompt de aprobar/rechazar no se renderiza por este paquete

Leyendo la rama `ConsentNoticeScreen` de `X/CaB` (found, bytecode exacto): al llegar a este estado,
el código re-verifica el valor *actual* del `StateFlow` de navegación contra `ConsentNoticeScreen`
de nuevo — y si todavía coincide, enruta inmediatamente a `ErrorExit` en lugar de renderizar nada.
Ningún fragment, activity, o lanzamiento Bloks está conectado a este estado en ninguna parte de
`com.whatsapp.vpc.sponsor` ni de la rama rastreada de `X/CaB`.

**Conclusión (inferred):** la UI real de aprobar/rechazar sobre la que actúa el sponsor no es
código nativo alcanzable desde este paquete. La explicación más consistente, dado que la compuerta
de edad también es conducida por Bloks, es una pantalla Bloks renderizada del lado servidor
lanzada *antes* de que inicie `VpcSponsorActivity`, con esta activity recibiendo solo el
**resultado** — aprobado, rechazado, o no-se-puede-revisar — para mostrar el fragment terminal
correspondiente. No se encontró en esta pasada ningún nombre de operación GraphQL/MEX ni id de
pantalla Bloks para el envío de aprobar/rechazar en sí. **Unknown.**

---

## 5. Pantallas de resultado terminal

| Pantalla | Lee | Muestra | Llamada de red en el fragment en sí |
|---|---|---|---|
| `VpcSponsorApprovedFragment` | nada de sus propios args | imagen de encabezado, texto de titular/cuerpo, un span clicable con tag `"manage"` dentro del cuerpo, un botón `"Done"` | ninguna encontrada |
| `VpcSponsorDeclinedFragment` | `account_deletion_time_ms` (long, bundle de Fragment-arg, fijado desde `CSS.A00`) | imagen de encabezado, titular, texto de cuerpo con el tiempo de eliminación **formateado como string relativo/de duración** (vía `LX/0Fg;->A05(LX/0Fc;J)Ljava/lang/String;`, no una marca de tiempo plana), un botón `"Done"` | ninguna encontrada |
| `VpcSponsorCannotReviewFragment` | `teen_name` (String, bundle de Fragment-arg, fijado desde `CSR.A00`) | imagen de encabezado, titular que interpola el nombre del adolescente, texto de cuerpo, un botón `"OK"` que descarta | ninguna encontrada |

**Qué significa `account_deletion_time_ms` en la práctica:** la pantalla de rechazo formatea este
valor a través de un formateador de duración relativa y lo muestra como "tiempo restante", es
decir, se presenta al observador como una **cuenta regresiva**, no un aviso de que la eliminación
ya ocurrió — found, a partir de la llamada al formateador. Si rechazar realmente *programa* la
eliminación del lado servidor, frente a que la eliminación ya esté en marcha para cuando se
renderiza esta pantalla, es **unknown**: ningún fragment de este paquete hace una llamada de red
propia; el valor simplemente llega como un argumento de lanzamiento/navegación que la pantalla
muestra.

Todo el texto del cuerpo para estas tres pantallas (`str5e24`-`str5e2c` en el `res/values/strings.xml`
de este build) es texto placeholder Lorem-ipsum literal — este es un build beta; el layout y el
data-binding son found, el texto final de envío es **unknown**.

---

## 6. Punto de entrada — no resuelto

`VpcSponsorActivity` está declarada `android:exported="false"` sin ningún `<intent-filter>` en el
manifest (found). Una búsqueda en todo el repositorio de las claves de argumento de navegación
literal (`vpc_teen_name`, `vpc_account_deletion_time_ms`) y de cualquier construcción de
`VpcSponsorActivity` fuera de sus propias cuatro clases y las clases auxiliares de
plomería/navegación compartidas de `X/CaB` no devuelve **ningún resultado en ninguna parte del
árbol smali decodificado** — un resultado negativo, found.

**Inferred:** nada en este cliente construye estáticamente el `Intent` de lanzamiento. La
explicación más plausible, consistente con cómo se sabe que funciona la navegación conducida por
push en otras partes de esta app, es una acción de notificación conducida por servidor que resuelve
la activity objetivo y sus extras a partir de datos de payload de push en runtime en lugar de un
call site hardcodeado — pero no se identificó tal despachador en esta pasada. **Unknown** cómo se
notifica y enruta realmente a un sponsor hacia esta pantalla.

---

## 7. Superficie de red

No se encontró en ninguna parte de este paquete ningún nombre de operación GraphQL/MEX, id de
pantalla Bloks, o `xmlns` de stanza binaria para ningún paso del flujo: ni para notificar a un
sponsor que una revisión está pendiente, ni para la compuerta de edad (Bloks inferido, sin id de
pantalla capturado), ni para el envío de aprobar/rechazar en sí (§4), ni para lo que realmente
dispara la cuenta regresiva de eliminación de cuenta al rechazar. Todo lo que tiene forma de red en
este flujo se infiere que viaja sobre Bloks en lugar de una query GraphQL/MEX nombrada y
persistida — consistente con cómo funciona el resto de las herramientas de verificación de edad
cross-app de Meta en este cliente — pero no se capturó ningún identificador de operación o pantalla
para ninguna parte de ello.

---

## 8. Distinciones clave

### 8.1 vs. `WA_MANAGED_ACCOUNT.md` ("Managed account")

| `vpc.sponsor` (este informe) | `managedaccount.*` / PAA / PMA / PMTA (`WA_MANAGED_ACCOUNT.md` §2-8) |
|---|---|
| Una **decisión de revisión de una sola vez**: aprobar, rechazar, o reportar incapacidad de revisar la cuenta específica de un menor | Una **relación de supervisión continua** entre dos cuentas registradas independientemente |
| Ninguna operación `w:mex` encontrada; Bloks inferido, sin id de op/pantalla capturado | Nueve operaciones `w:mex` `ManagedAccount*` nombradas con doc_ids, schema `whatsapp-android-mex` |
| Ningún registro de relación local encontrado en este paquete | Fila `ManagedAccountConnection` local (`connectionLid`, `role`, `linkTs`, `connectionPnJid`, ...) |
| Rechazar produce una consecuencia `account_deletion_time_ms` para la **propia cuenta del adolescente** | Desvincular (`ManagedAccountRevokeLinkingMutation`) termina la supervisión; ninguna de las dos cuentas se elimina |
| Sin enum de roles; el sponsor es simplemente "el revisor" | `EnumC08540Ng`: `NONE`/`DEPENDENT`/`SPONSOR`/`SPONSOR_ADMIN` |
| Punto de entrada no resuelto; activity no exportada, sin deep link | El punto de entrada es un deep link dentro de la app (`ManagedAccountSponsorOnboardingViewModel`) |
| No comparte ninguna clase, paquete, o string con `managedaccount.*`/`pma.*`/`pmta.*` | — |

Ningún código en ninguno de los dos paquetes referencia al otro por clase o string. Si una
aprobación de `vpc.sponsor` posteriormente crea o interactúa con una relación `managedaccount.*`
no fue rastreado; **unknown**.

### 8.2 vs. creación de cuenta normal

El registro normal de WhatsApp (`WA_ACCOUNT_LESS_SURFACE.md` / el flujo estándar de OTP por
SMS/email) no tiene ningún paso de revisión de tutor en absoluto; una cuenta se vuelve activa una
vez que su propio dueño completa el registro. `vpc.sponsor` inserta una compuerta de aprobación
externa — en manos de otra persona, en otro dispositivo — entre algún disparador (no resuelto, §6)
y la existencia continuada de la cuenta, con el rechazo llevando una consecuencia de eliminación.
Qué específicamente causa que una cuenta sea enrutada a este estado de revisión de tutor en primer
lugar (edad al momento del registro, una señal de edad en el dispositivo, una reclasificación
posterior) no se encontró en este paquete y es **unknown**.

---

## 9. Nota de alcanzabilidad Baileys / velowa

Nada en este flujo es alcanzable para un cliente de terceros solo-de-cable. La decisión misma de
aprobar/rechazar se infiere que es una pantalla Bloks renderizada del lado servidor que el propio
cliente de primera parte del sponsor renderiza (§4) — no un mensaje, IQ, o mutación GraphQL/MEX
nombrada que velowa pudiera enviar u observar. La compuerta de verificación de edad del lado
sponsor (§3) está igualmente conducida por Bloks. No existe ningún doc_id, nombre de operación MEX,
o `xmlns` de nodo binario para ninguna parte de este flujo en los catálogos de este build. No hay
nada aquí que implementar; esta sección existe para registrar eso explícitamente en lugar de
dejarlo implícito.

---

## 10. Incógnitas

| Tema | Razón |
|---|---|
| Expansión de "VPC" | nunca deletreada en el cliente; inferida como Verified Parent/guardian Consent |
| Qué lanza `VpcSponsorActivity` y fija sus argumentos de navegación | no se encontró ningún call site estático en ninguna parte del árbol decodificado; no exportada, sin intent-filter |
| El envío de aprobar/rechazar en sí (operación de red, id de pantalla) | no implementado en este paquete; Bloks inferido, sin identificador capturado |
| Si rechazar programa la eliminación del lado servidor, o la cuenta regresiva es puramente informativa | ninguna llamada de red en `VpcSponsorDeclinedFragment`; se asume que la eliminación ya fue iniciada del lado servidor para cuando esta pantalla se renderiza |
| Qué enruta la cuenta de un adolescente hacia la revisión de tutor en primer lugar | no rastreado; no se encontró ninguna condición de disparo en este paquete |
| Relación, si existe alguna, con `managedaccount.*` | no se encontró ninguna referencia cruzada en ninguna dirección |
| Texto final de envío de todos los strings de `vpc.sponsor` | este build beta envía texto placeholder Lorem-ipsum |
| Semántica exacta de los estados null/true/false de `ContextualAgeCollectionRepository.A06()` más allá de "desconocido/suficiente/insuficiente" | inferido solo del flujo de control; no se encontraron nombres de campo o enum |
| Tráfico real | solo análisis estático; nada capturado o ejercitado en runtime |

---

## 11. Flujo (hasta donde alcanza la evidencia)

```
[Server / push — mechanism unresolved]
   │
   ▼
[VpcSponsorActivity starts] (launch args: vpc_teen_name, vpc_account_deletion_time_ms, navigation)
   │
   ▼
ContextualAgeCollectionRepository.A06() : Boolean?
   │
   ├─ null  ──► [Bloks age-verification screen] ──► onAgeCollectionResult(CACResult)
   │                                                     │
   │                                     ┌───────────────┼───────────────────┐
   │                                     ▼               ▼                   ▼
   │                             boolean payload   dismissed/blocked   no-age / failed
   │                             (re-enter below)      Exit               ErrorExit
   │
   ├─ true  ──► ConsentNoticeScreen
   │                 │
   │                 ▼
   │      [approve/decline prompt — not native to this package; inferred Bloks, unknown op]
   │                 │
   │      ┌──────────┼──────────────────┐
   │      ▼          ▼                  ▼
   │  ApprovedScreen  DeclinedScreen      (re-check of current state == ConsentNoticeScreen
   │      │          (accountDeletionTimeMs)   with no result yet falls to ErrorExit)
   │      ▼                 ▼
   │  VpcSponsorApproved  VpcSponsorDeclined
   │  Fragment ("Done")   Fragment (countdown text, "Done")
   │
   └─ false ──► CannotReviewScreen(teenName) ──► VpcSponsorCannotReviewFragment ("OK")
```
