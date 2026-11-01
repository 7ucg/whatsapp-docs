<!-- src-sha1: 1fe6d8278b8f0a0adfe50041466f968ec368a2e2 -->
# WhatsApp Pagos — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-11-01
**Alcance:** tipos de mensajes de pago dentro del chat (`sendPaymentMessage`, `requestPaymentMessage`, `declinePaymentRequestMessage`, `cancelPaymentRequestMessage`, pagos divididos, invitación/recordatorio de pago) y sus campos proto, arquitectura multi-rail del cliente (UPI de India, Pix de Brasil, México, Indonesia, rail genérico "UPR"), vinculación de VPA/cuenta bancaria y flujo de onboarding UPI, la capa embebida de credencial/PIN/vinculación de dispositivo "Common Library" (CL) de NPCI, sincronización de estado de transacción, capas de cifrado (E2E del chat vs. blob de credencial NPCI), operaciones GraphQL/MEX de pagos (doc_ids), reglas de lectura automática de OTP de NPCI, flags de funcionalidad, manejo de códigos de rechazo/error

---

## 1. Qué es (resumen)

WhatsApp Android incluye un protocolo de pago dentro del chat compartido (tipos de mensaje proto incluidos dentro del `Message` E2E normal) más varios *rails* de pago específicos de cada país, cada uno con su propia UI de onboarding, operaciones GraphQL y (para India) una biblioteca de credenciales de terceros embebida. Todos los hallazgos son análisis estático del APK descompilado; nada fue capturado en el cable. Niveles: **found** = leído directamente en código/assets, **inferred** = deducido del código, **unknown** = no resuelto. Los nombres obfuscados son por build y se resolvieron en 2.26.41.6 a partir de strings estables (constantes `FIELD_NUMBER`, nombres de interfaz AIDL, catálogos de operaciones GraphQL, nombres de archivos de assets).

| Capa | Nombre/ruta en 2.26.41.6 | Rol |
|-------|------------------------|------|
| Protocolo de mensaje de chat | `DSJ` SendPaymentMessage, `C30605DSz` RequestPaymentMessage, `C30502DPa` DeclinePaymentRequestMessage, `DPZ` CancelPaymentRequestMessage, `DT0`/`C30535DQh` pago dividido, `C30586DSg` PaymentInviteMessage, `C43112IrN` PaymentReminderMessage, `DTS` PaymentInfo | campos en la sección 2 |
| Paquetes de rail | `com.whatsapp.payments.{common,indiaupi,brazilpay,mexico,indonesia,globalorder,upr,dcp,remittances,split,paymentkey,productinfra,integrity,phoenix}` | un paquete por mercado/rail, sección 3 |
| Biblioteca de credenciales UPI de India | `org.npci.upi.security.{services,pinactivitycomponent}` (`CLRemoteService`, `CLRemoteServiceImpl`, `BinderC48420LDc`, `GetCredential`) | "Common Library" (CL) embebida de NPCI, sección 6 |
| Lectura automática de OTP | `assets/npci/npci_otp_rules.json`, consumidor `org.npci.upi.security.pinactivitycomponent.C0315u` | sección 10 |
| Catálogo GraphQL/MEX | `assets/whatsapp-android-www_client_persist_ids.json` (esquema `whatsapp`), `whatsapp-android-mex_client_persist_ids.json` (esquema `whatsapp_mex`) | doc_ids, sección 9 |
| Manejador de push del servidor | `C24410wL` ("PaymentsMessageHandler", log tag `PaymentsMessageHandler`) | `<notification type="pay\|upi\|fbpay\|transaction\|account-recovery\|alert\|...">`, sección 8 |
| Objeto de transacción | `F7F` (fila de transacción local), `DTS` (PaymentInfo de wire/history-sync), construido por `EKY.A00` | sección 8 |

Rails identificados a partir de nombres de paquetes/clases (found): **UPI de India** (`indiaupi`), **Pix de Brasil** (`brazilpay`), **México** (`mexico`), **Indonesia** (`indonesia`), más un paquete agnóstico de rail "**UPR**" (`upr` — onboarding, gestión de cuenta, UI de burbuja) y una referencia heredada a Meta Pay/Novi que aún está presente en el código de enum/notificación (`FBPAY`, `NOVI`) aunque esos servicios están descontinuados hace tiempo — se mantienen aquí solo porque los strings literales todavía existen en 2.26.41.6. La evidencia abajo está etiquetada **específica de India/UPI** o **general** por sección; no asumir que los hallazgos de UPI aplican a Pix/México/Indonesia.

---

## 2. Tipos de mensaje de pago y campos proto

### 2.1 Ubicación en `Message` (found)

Todos los tipos de mensaje de pago son campos directos del proto `Message` de nivel superior (`C30628DTw`, la misma clase documentada en `WA_MESSAGE_SECRETS.md`). La mayoría de los submensajes de pago **no** exponen constantes `FIELD_NUMBER` públicas en `Message` mismo; los números abajo se recuperaron decodificando el string de información de mensaje empaquetado (`GeneratedMessageLite`) de la clase (una codificación reproducible de 2 o 3 caracteres por campo: carácter de número de campo, carácter de marcador de tipo, carácter de índice has-bit; el índice has-bit se incrementa exactamente en uno por entrada a lo largo del mensaje completo de ~150 campos, lo cual es una fuerte verificación de consistencia interna sobre la decodificación).

| Campo (Message) | Número | Tipo |
|---|---|---|
| `sendPaymentMessage` | **16** | `SendPaymentMessage` (`DSJ`) |
| `requestPaymentMessage` | **22** | `RequestPaymentMessage` (`C30605DSz`) |
| `declinePaymentRequestMessage` | **23** | `DeclinePaymentRequestMessage` (`C30502DPa`) |
| `cancelPaymentRequestMessage` | **24** | `CancelPaymentRequestMessage` (`DPZ`) |
| `paymentInviteMessage` | **44** | `PaymentInviteMessage` (`C30586DSg`) |
| `splitPaymentMessage` | no decodificado en esta pasada | `SplitPaymentMessage` (`DT0`), `unknown` |
| `splitPaymentUpdateMessage` | no decodificado en esta pasada | `SplitPaymentUpdateMessage` (`C30535DQh`), `unknown` |
| `paymentReminderMessage` | no decodificado en esta pasada | `PaymentReminderMessage` (`C43112IrN`), `unknown` |

El clasificador a nivel de stanza `<message type="pay">` (compartido con otros tipos add-on) está documentado en `WA_MESSAGE_SECRETS.md` en la sección sobre el selector de tipo (`AbstractC30999De0.A02`); no se re-derivó aquí.

### 2.2 SendPaymentMessage (`DSJ`, found)

| Campo | Número | Tipo | Uso |
|---|---|---|---|
| `noteMessage` | **2** | `Message` (`C30628DTw`) | la "nota" adjunta a un pago es en sí un `Message` completo (normalmente solo lleva un `extendedTextMessage` o sticker) |
| `requestMessageKey` | **3** | `MessageKey` (`BD5`) | presente cuando este envío es una respuesta a un `requestPaymentMessage` previo |
| `background` | **4** | `PaymentBackground` (`DTJ`) | sección 2.7 |
| `transactionData` | **5** | string | opaco; el valor por defecto en el código fuente descompilado es una constante de string vacío compartida, no un default real |

El número de campo 1 no se usa/está reservado (no hay constante `FIELD_NUMBER` para él).

### 2.3 RequestPaymentMessage (`C30605DSz`, found)

| Campo | Número | Tipo | Uso |
|---|---|---|---|
| `currencyCodeIso4217` | **1** | string | código ISO 4217 |
| `amount1000` | **2** | int64 | monto × 1000 (punto fijo, sin decimales en el valor del wire) |
| `requestFrom` | **3** | string | identificador del solicitante (string JID observado en los call sites) |
| `noteMessage` | **4** | `Message` | mismo patrón que 2.2 |
| `expiryTimestamp` | **5** | int64 | segundos unix |
| `amount` | **6** | `Money` (`C30561DRh`) | monto estructurado, sección 2.7 |
| `background` | **7** | `PaymentBackground` (`DTJ`) | sección 2.7 |

### 2.4 DeclinePaymentRequestMessage / CancelPaymentRequestMessage (found)

Ambos mensajes son mínimos — un único campo que referencia la solicitud original:

| Clase | Campo | Número | Tipo |
|---|---|---|---|
| `DeclinePaymentRequestMessage` (`C30502DPa`) | `key` | **1** | `MessageKey` (`BD5`) |
| `CancelPaymentRequestMessage` (`DPZ`) | `key` | **1** | `MessageKey` (`BD5`) |

**Ninguno de los dos mensajes lleva un campo de razón/código de error.** Decline y cancel son no-ops de protocolo más allá de "esta solicitud (identificada por `key`) está rechazada/cancelada" — cualquier texto de razón mostrado en la UI es solo local, no forma parte del payload del wire (found: no existe un segundo campo en ninguna de las dos clases; ver sección 12).

### 2.5 Pagos divididos (found)

`SplitPaymentMessage` (`DT0`):

| Campo | Número | Tipo |
|---|---|---|
| `splitId` | **1** | string |
| `totalAmount` | **2** | `Money` |
| `description` | **3** | string |
| `requesterJid` | **4** | string |
| `participants` | **5** | repeated `SplitPaymentParticipant` (`C30558DRe`) |
| `createdAtMs` | **6** | int64 |
| `contextInfo` | **17** | tipo similar a `MessageContextInfo` (`C30617DTl`) |

`SplitPaymentUpdateMessage` (`C30535DQh`): `splitId` (**1**, string), `participantJid` (**2**, string) — un ping de estado por participante, sin payload de monto/estado propio.

### 2.6 PaymentInviteMessage / PaymentReminderMessage (found)

`PaymentInviteMessage` (`C30586DSg`): `serviceType` (**1**, int/enum — vinculado a los códigos de servicio `UPI`/`PIX`/`NOVI`/`FBPAY` vistos en la sección 8), `expiryTimestamp` (**2**, int64), `incentiveEligible` (**3**, bool), `referralId` (**4**, string), `inviteType` (**5**, int/enum).

`PaymentReminderMessage` (`C43112IrN`):

| Campo | Número | Tipo |
|---|---|---|
| `reminderId` | **1** | string |
| `instanceId` | **2** | string |
| `description` | **3** | string |
| `frequency` | **4** | int/enum |
| `status` | **5** | int/enum |
| `payeeVpa` | **6** | string |
| `payeeJid` | **7** | string |
| `payerJid` | **8** | string |
| `amount` | **9** | `Money` |

`payeeVpa` (campo 6) es un **campo VPA literal en el protocolo de wire** — confirmación directa a nivel proto de que las direcciones de pago virtuales (VPA) de UPI viajan dentro de los mensajes de chat, no solo a través de canales laterales de GraphQL.

### 2.7 Tipos de soporte (found)

| Tipo | Clase | Campos |
|---|---|---|
| `Money` | `C30561DRh` | `value` (**1**, int64), `offset` (**2**, int32 — desplazamiento del punto decimal), `currencyCode` (**3**, string) |
| `MessageKey` | `BD5` | `remoteJid` (**1**, string), `fromMe` (**2**, bool), `id` (**3**, string), `participant` (**4**, string) |
| `PaymentBackground` | `DTJ` | `id` (**1**, string), `fileLength` (**2**, int64), `width` (**3**, int32), `height` (**4**, int32), `mimetype` (**5**, string), `placeholderArgb` (**6**, int32), `textArgb` (**7**, int32), `subtextArgb` (**8**, int32), `mediaData` (**9**, `MediaData` `C30588DSi`), `type` (**10**, enum) |

### 2.8 PaymentInfo — objeto de estado de transacción (found)

`DTS` ("PaymentInfo") **no** es un tipo de mensaje de chat; se adjunta a `WebMessageInfo` (`C30626DTu`, el portador de history-sync/companion documentado en `WA_MESSAGE_SECRETS.md`) como `paymentInfo_` y `quotedPaymentInfo_`. Representa el estado actual conocido de una transacción de pago, construido a partir de la fila de transacción local por `EKY.A00`:

| Campo | Número | Tipo | Nota |
|---|---|---|---|
| `currencyDeprecated` | **1** | enum | heredado |
| `amount1000` | **2** | int64 | |
| `receiverJid` | **3** | string | |
| `status` | **4** | enum | estado grueso |
| `transactionTimestamp` | **5** | int64 | |
| `requestMessageKey` | **6** | `MessageKey` | |
| `expiryTimestamp` | **7** | int64 | |
| `futureproofed` | **8** | bool | se establece cuando el objeto de transacción local del remitente no tiene moneda/monto resolubles (válvula de escape por evolución de esquema) |
| `currency` | **9** | string | |
| `txnStatus` | **10** | enum | estado más fino (a nivel NPCI), enum separado de `status` |
| `useNoviFiatFormat` | **11** | bool | flag heredado de formato de visualización de Meta Pay/Novi |
| `primaryAmount` | **12** | `Money` | |
| `exchangeAmount` | **13** | `Money` | visualización entre monedas |

Los **nombres** de constantes del enum `status`/`txnStatus` fueron eliminados por el obfuscador a nivel de bytecode javalite (solo quedan ordinales + clases `EnumVerifier`); su mapeo ordinal→etiqueta es `unknown` en esta pasada. `EKY.A00` lee la moneda/monto del objeto de transacción local y, cuando están ausentes, establece `futureproofed=true` en lugar de adivinar — found en código (guarda `f7fA00.A03 == 5 || !f7fA00.A0N()`).

---

## 3. Arquitectura de cliente multi-rail ("payment-common-library")

El código de pagos está organizado como un paquete de UI/infraestructura compartido más un paquete por rail de mercado (found, a partir de la disposición de paquetes bajo `com.whatsapp.payments`):

| Paquete | Rail | Contenido (found) |
|---|---|---|
| `common` | compartido | `p144ui` (hojas inferiores genéricas de pago, ajustes, historial de transacciones, selectores de método), `pin` (UI de entrada de PIN compartida entre rails), `paymentkeys`, `compliance`, `care` (CSAT), `qpl` (marcadores de logging de calidad/rendimiento) |
| `indiaupi` | UPI de India | onboarding, vinculación de banco/VPA, mandatos, pago de facturas, UPI Lite, QR, recuperación de cuenta — sección 4 |
| `brazilpay` | Pix de Brasil | gestión de claves Pix, enrolamiento biométrico/passkey, CPF |
| `mexico`, `indonesia` | rails locales | presentes como paquetes; no explorados más allá de su existencia en esta pasada (detalle `unknown`) |
| `upr` | agnóstico de rail | `nux` (onboarding), `accountmanagement`, `bubble` (hoja de opciones de pago en el chat), `shared` (selectores de institución/tipo de cuenta) — se mapea a las operaciones GraphQL `GenUprPaymentConfig`/`GenUprPaymentConfigForViewer` (sección 9); la expansión de "UPR" no está explicitada en ningún string encontrado (`inferred`: "Universal/Unified Payment Rail") |
| `globalorder`, `remittances`, `split`, `paymentkey`, `productinfra`, `integrity`, `dcp`, `phoenix` | mixto | presentes como paquetes; `integrity` contiene una hoja inferior de "fricción" de pago (UI de riesgo/step-up), `dcp` y `phoenix` no tuvieron archivos resueltos bajo sus dos primeros niveles de directorio en esta pasada (`unknown`) |

El transporte GraphQL entre rails está envuelto por `PaymentsMexGraphQlClient$ApiEventCallBuilder` (`com.whatsapp.payments.indiaupi.common.graphql`, a pesar del nombre del paquete es el wrapper compartido de llamadas MEX, found) — decora cada llamada MEX de pago con callbacks de inicio/éxito/fallo de logging QPL/eventos (`FDA.BYz`) antes de delegar al transporte subyacente `InterfaceC17070jD`. Esto es lo más cercano en este build a una "biblioteca de pagos común" a nivel de **cliente**: una clase obfuscada de envoltura de llamada, reutilizada por los gestores GraphQL de UPI de India (`IndiaUpiChangeMpinGraphqlManager`, `IndiaUpiCheckBalanceGraphqlManager`, `IndiaUpiEnrollIncentiveGraphqlManager`, etc. — found, mismo paquete).

Por separado, India incluye una biblioteca de **terceros** embebida bajo el paquete propiedad de NPCI `org.npci.upi.security.*` (no `com.whatsapp.*`) — esta es la "CL" ("Common Library") referenciada por los propios assets `.properties` de NPCI (`version.properties`, `validation.properties`, `cl-*.properties`) y se cubre en la sección 6. El propio vocabulario de los assets de NPCI (`salt`, `payInfo`, `controls`, `configuration`, `trust`, `keyXmlPayload`, `keyCode`) coincide exactamente con las claves de string del bundle encontradas en las implementaciones `CLRemoteService.Acc`/`Acf` de este build (sección 6) — corroboración directa, en este build, de un análisis previo basado solo en assets. La expansión literal "Common Library" aún no está explicitada en ningún string (`inferred`, ahora corroborada por los propios nombres de clase `CLRemoteService`/`CLResultReceiver`/`CLRemoteServiceImpl`, lo cual es evidencia nueva en esta pasada).

---

## 4. Vinculación de VPA/cuenta bancaria y onboarding UPI (específico de India)

Nombres de actividad recuperados de `com.whatsapp.payments.indiaupi.*` (found, solo existencia y nomenclatura de clases — el orden exacto de navegación entre ellas es `inferred` a partir de la nomenclatura y NO se rastreó mediante grafos de intents en esta pasada):

| Paso | Activity/Fragment |
|---|---|
| Entrada / propuesta de valor | `IndiaUpiPaymentsValuePropsActivity`, `IndiaUpiPaymentsValuePropsBottomSheetActivity`, `IndiaUpiPaymentsTosActivity` |
| Verificación de SIM | `IndiaUpiSimPickerDialogFragment`, `IndiaUpiSimVerificationActivity` |
| Selección de banco | `IndiaUpiBankPickerActivity` (paquete `onboarding`), `IndiaUpiBankAccountPickerActivity` |
| Verificación de identidad/tarjeta | `IndiaUpiDebitCardVerificationActivity`, `IndiaUpiAadhaarCardVerificationActivity`, `IndiaUpiDobPickerActivity` |
| Vinculación de dispositivo | `IndiaUpiDeviceBindStepActivity` (ver sección 6 para la criptografía detrás de este paso) |
| Configuración de PIN | `IndiaUpiPinPrimerDialogFragment` / `...FullSheetActivity`, `IndiaUpiPinHandlerActivity`, `IndiaUpiPinSetUpCompletedActivity`, `IndiaUpiChangePinActivity`, `IndiaUpiForgotPinDialogFragment` |
| Finalización | `IndiaUpiBankAccountAddedLandingActivity`, `IndiaUpiPaymentsAccountSetupActivity` |
| Mapeador número-a-VPA | `IndiaUpiMapperValuePropsActivity` → `IndiaUpiMapperLinkActivity` → `IndiaUpiMapperPendingActivity` → `IndiaUpiMapperConfirmationActivity`; `IndiaUpiCreateCustomNumberActivity` para un número móvil no predeterminado |
| Resolución de contacto VPA | `IndiaUpiVpaContactInfoActivity`, `IndiaUpiSendPaymentToVpaFragment` |

"Mapper" es el término propio de NPCI para el servicio de directorio número de teléfono↔VPA; las cuatro actividades `mapper.register.*` implementan ese sub-flujo de registro específico (found: ruta de paquete `indiaupi.p148ui.mapper.register`).

Operaciones GraphQL relevantes para la vinculación con variables verificadas en call-site (found, de `com.whatsapp.payments.indiaupi.common.graphql.*` y clases `X/*` relacionadas; ver sección 9 para el catálogo completo):

| Operación | doc_id | Variables (found) |
|---|---|---|
| `GetUpiBankList` | `27764018976534565` | `account_type`, `provider_type`, `request` |
| `GetUpiAccounts` | `25691302307224710` | `bank_code`, `device_id`, `provider_type`, `account_type` |
| `GetUpiToken` | `25639185495767704` | `challenge`, `device_id`, `token_type`, `provider_type` |
| `GenCreatePaymentKey` | `24662763616751127` | `add_bank`, `account_holder_name`, `display_name`, `payment_method_type`, `payment_account`, … (superconjunto ruidoso, caller compartido entre varias ops — ver advertencia en sección 9) |
| `SetUpiChangeMpin` | `27149786891388216` | `credential_fbid`, `device_id`, `new_mpin`, `old_mpin`, `seq_no`, `upi_bank_info`, `vpa` |

---

## 5. Configuración/onboarding de pago (general, entre rails)

El paquete `upr` implementa una capa de onboarding agnóstica de rail: `UprOnboardingActivity` → `UprOnboardingFragment` → `UprAccountTypePickerBottomSheet` → `AddPaymentMethodFragment` / `UprInstitutionPickerBottomSheet` (found, solo nombres de clase; orden del flujo `inferred`). La gestión de cuenta después de la configuración pasa por `UprAccountManagementActivity`/`UprAccountManagementListFragment`, y el disparador de pago dentro del chat aparece vía `UprPaymentOptionsBottomSheet`/`UprPaymentAccountDetailBottomSheet` (paquete "bubble" — la hoja flotante de opciones de pago abierta desde un chat).

La configuración del lado del servidor para esta capa se obtiene vía `GenUprPaymentConfig` (doc_id `26905963415743456`) y `GenUprPaymentConfigForViewer` (doc_id `37307071662269517`) — found en el catálogo de doc_ids, no verificado independientemente por call-site en esta pasada (variables `unknown`).

---

## 6. "Common Library" (CL) de NPCI: credencial, PIN y vinculación de dispositivo (específico de India/UPI)

### 6.1 Arquitectura (found)

La entrada de PIN y el manejo de credenciales bancarias de UPI de India se delegan a un servicio Android AIDL embebido, propiedad de NPCI, completamente separado del propio código `com.whatsapp.*` de WhatsApp:

```
org.npci.upi.security.services.CLRemoteService      <- AIDL interface
org.npci.upi.security.services.CLResultReceiver     <- AIDL callback interface
org.npci.upi.security.pinactivitycomponent.CLRemoteServiceImpl  <- Android Service, binds the AIDL
org.npci.upi.security.pinactivitycomponent.BinderC48420LDc      <- Binder implementation of CLRemoteService
org.npci.upi.security.pinactivitycomponent.GetCredential        <- PIN-entry Activity launched by the binder
org.npci.upi.security.pinactivitycomponent.Keypad               <- on-screen keypad widget
```

Métodos de `CLRemoteService` (found, firmas de interfaz): `AQR(otpResultJson)`, `AZO(mode, nonce)` (desafío/respuesta de vinculación de dispositivo, sección 6.2), `Acc(...)`/`Acf(...)` (lanzan la activity de PIN con un bundle de credencial), `BBj(...)` (lectura de saldo), `BVz/CRh/CRi(...)` (certificado de dispositivo/validación de estado), `BW1()` (verificación de integridad del dispositivo).

### 6.2 Vinculación de dispositivo e intercambio de credenciales (found)

`BinderC48420LDc.AZO(mode, nonce)`:
- modo "initial": construye `deviceId|randomHex|nonce`, cifra con RSA contra un certificado NPCI empaquetado (`MYU.A00`), codifica en base64, devuelve `"2.3-v1.8|" + ciphertext`. El prefijo `2.3-v1.8` es una etiqueta de versión de protocolo CL embebida en el código (literal found).
- modo subsiguiente: deriva una clave AES a partir del registro de credencial almacenado, cifra con AES/GCM el mismo triplete `deviceId|randomHex|nonce` con un IV aleatorio fresco, devuelve `ciphertext|iv` bajo el mismo prefijo de versión.

`BinderC48420LDc.Acc`/`Acf` construyen un `Bundle` con las claves `keyCode`, `keyXmlPayload`, `controls`, `configuration`, `salt`, `payInfo`, `trust`, `languagePref` y arrancan la activity `GetCredential` con él (found, claves de string literales) — este es el vocabulario exacto que un análisis previo basado solo en assets de `version.properties`/`validation.properties` infirió que el esquema "CL" usaría (`salt`, `payInfo`); el código de este build confirma que son claves de bundle reales en tiempo de ejecución, no solo marcadores de archivos de assets.

`C51962N8y` (helper criptográfico usado en todo el binder):
- `A00`: genera un **par de claves RSA-2048 dentro del Android KeyStore**, `CN=NPCI_CERT`, SHA-512/PSS, requiere hardware seguro (`isInsideSecureHardware()`, lanza excepción en caso contrario) y (según el SDK) autenticación de usuario dentro de una ventana de validez corta — esta es la clave de vinculación de dispositivo.
- `A03`/`A04`: AES/GCM-NoPadding, tag de 128 bits, clave e IV suministrados explícitamente por el caller — cifrado/descifrado a nivel de sesión.
- `A02`: digest SHA-256 (hash de desafío).
- `A01`: descifra un string con forma `ciphertext|iv` usando una clave AES almacenada — emparejado con el formato de salida de `AZO` arriba.

`BinderC48420LDc.BW1()` ejecuta una verificación de root/tamper (build tags, rutas comunes del binario `su`, sondeo `which su`) **y** verifica que la clave RSA recién generada esté respaldada por StrongBox/TEE; una verificación fallida hace que `BW1()` devuelva `false`, lo cual bloquea la ruta de emisión de credencial más arriba (found: valor de retorno booleano consumido por rutas lógicas de `CRh`/`CRi`, no rastreado independientemente hasta un mensaje de UI).

### 6.3 Qué significa esto para el contenido del mensaje

El MPIN de UPI en sí nunca aparece en un mensaje de chat ni en los campos proto de la sección 2 de este reporte — se maneja completamente dentro de la activity `GetCredential` y se intercambia con el banco emisor/switch de NPCI a través de la capa RSA/AES anterior, produciendo un *blob de credencial* opaco que es lo que finalmente llega a variables GraphQL como `new_mpin`/`old_mpin`/`mpin` en `SetUpiChangeMpin`/`CheckUpiBalance` (sección 9). Que el string que una variable GraphQL realmente lleva ya esté cifrado por NPCI (en lugar de texto plano del cliente protegido solo por TLS) es **inferred** a partir del propósito del flujo CL que la precede, no confirmado independientemente leyendo el contenido en bytes del call site de GraphQL.

---

## 7. Capas de cifrado: E2E del chat vs. blob de credencial NPCI

Hay dos capas de cifrado independientes involucradas en un pago, y no deben confundirse (sección 13):

| Capa | Protege | Mecanismo | Evidencia |
|---|---|---|---|
| E2E del mensaje de chat | todo el proto `Message`, incluyendo cada campo de la sección 2 (monto, nota, VPA en `payeeVpa`, JIDs, referencias `MessageKey`) | cifrado de sesión estándar de WhatsApp (protocolo Signal/Noise) — fuera de alcance de este reporte, ver otros reportes RE para esa capa | no re-derivado aquí |
| Blob de credencial/vinculación de dispositivo NPCI | MPIN, desafío/respuesta de vinculación de dispositivo, payloads de verificación de riesgo intercambiados con el banco emisor vía NPCI | RSA-2048 (KeyStore, respaldado por TEE, `CN=NPCI_CERT`) para vinculación de dispositivo; AES/GCM-128 con IV explícito para datos de sesión; SHA-256 para hash de desafío | sección 6.2, found |

La segunda capa es **específica de India/UPI** y corre por debajo/antes de la llamada GraphQL, nunca dentro del proto `Message` del chat. No se encontró una capa AES/RSA específica de pagos para Pix de Brasil o México en esta pasada (`unknown` — no explorado).

---

## 8. Sincronización de estado de transacción

### 8.1 Objeto local e history sync (found)

`F7F` es el objeto de transacción de pago local/en memoria (obtenido vía `D8X.A00(c13g)` desde la fila de mensaje genérica `C13G`). `EKY.A00` lo convierte en el `PaymentInfo` de nivel de wire (`DTS`, sección 2.8) adjunto a `WebMessageInfo.paymentInfo_`/`quotedPaymentInfo_` para exportación por history-sync/companion.

### 8.2 Actualizaciones de estado enviadas por el servidor (found, `C24410wL` "PaymentsMessageHandler")

El canal de push de cara al cliente es una stanza `<notification>` con un atributo `type` despachado por `PaymentsMessageHandler.A0A`. Valores `type` observados y su manejo:

| `type` | Manejo |
|---|---|
| `pay` (con `hash`) | hash en base64 decodificado, encolado como un refresh USync de lista lateral (`EnumC21760rz.A0Q`, conjunto de protocolo `C21820s6.A0N`) — reutiliza el mecanismo USync documentado en `WA_USYNC.md` en lugar de llevar el estado en sí |
| `transaction` | analiza la transacción vía `C24880x6.A07`, registra `onPaymentTransactionStatusUpdate`, actualiza el `F7F` local, muestra un string de error de transacción a cualquier UI adjunta (`InterfaceC35566Fb1.BIp`), y (condicionado por los flags **1746** + **5049**) puede construir una tarjeta "custom item" de resumen de orden para un empujón educativo post-pago |
| `upi` | `consumer_status{value,dhash}` → `onPaymentConsumerStatusUpdate` (ping de elegibilidad de consumidor específico de India, distinto del estado de transacción) |
| `fbpay` | ping de elegibilidad heredado de Meta Pay, misma ruta de manejador que `upi` con una clave de mapa de oferta diferente |
| `account-recovery` | `service=UPI` o `service=BR`; impulsa los flujos de recuperación de cuenta de India/Brasil, condicionado por los flags **1644**/**2000** |
| `alert`, `step_up`, `merchant_status`, `merchant-update`, `account`, `kyc-state`, `invite`, `alias`, `age_verification_update`, `document_verification_status` | empujones de UI/actualizaciones de cumplimiento varios, no estado de transacción |

### 8.3 Contabilidad de sincronización (found, claves de preferencia en string)

`payments_all_transactions_last_sync_time`, `payments_block_list_last_sync_time`, `payments_error_map_last_sync_time_millis` — existen sincronizaciones periódicas de lista completa y de mapa de errores (clases consumidoras no rastreadas completamente en esta pasada; cadencia `unknown`).

---

## 9. Operaciones GraphQL/MEX de pagos

### 9.1 Dos transportes, dos esquemas (found)

| Esquema | Transporte | Cantidad (este build) |
|---|---|---|
| `whatsapp` (catálogo `www`) | POST GraphQL de doc_id persistido, mecanismo de transporte en sí `inferred` (no rastreado hasta un call site HTTP/IQ en esta pasada) | 81 operaciones etiquetadas como de pago |
| `whatsapp_mex` (catálogo `mex`) | IQ `w:mex` sobre la conexión de stanza existente (`xmlns="w:mex"`) | 1 operación etiquetada como de pago: `PaymentsIsAccountRecoverable` (doc_id `27351347491148282`) |

Fuente: `assets/whatsapp-android-www_client_persist_ids.json` y `assets/whatsapp-android-mex_client_persist_ids.json`, ambos assets declarativos propios leídos en tiempo de ejecución (found, el nivel más fuerte salvo una captura de tráfico — los valores de doc_id en sí no están "tested", solo confirmados presentes en el asset distribuido).

### 9.2 Operaciones representativas con variables verificadas por call-site (found)

| Operación | doc_id | Tipo | Variables |
|---|---|---|---|
| `GetUpiAccounts` | `25691302307224710` | Query | `bank_code`, `device_id`, `provider_type`, `account_type` |
| `CheckUpiBalance` | `37205951525662520` | Query | `credential_fbid`, `device_id`, `mpin`, `seq_no`, `upi_bank_info`, `vpa`, `cl_version`, `device_ssid`, `request` |
| `SetUpiChangeMpin` | `27149786891388216` | Mutation | `credential_fbid`, `device_id`, `new_mpin`, `old_mpin`, `seq_no`, `upi_bank_info`, `vpa` |
| `GetUpiBankList` | `27764018976534565` | Query | `account_type`, `provider_type`, `request` |
| `GetUpiToken` | `25639185495767704` | Query | `challenge`, `device_id`, `token_type`, `provider_type` |
| `UpiCreateMandate` / `UpiAcceptMandate` | `26775212245448044` / `26786867597629452` | Mutation | caller compartido (`C42562IuV`): `frequency_rule`, `mandate_no`, `purpose_code`, `recurrence_day`, `recurring_rule`, `ref_id`, `device_id`, `top_up_amount`, `provider_type`, `upi_banks`, `is_revocable`, … |
| `CreateEnrollment` | `34570903025891763` | Mutation | `participant_id`, `device_id` |
| `GenRaisePaymentComplaint` | `27569318002686860` | Query | `complaint_type`, `reason`, `transaction_ref_id`, `user_description` |
| `PaymentsIsAccountRecoverable` (MEX) | `27351347491148282` | Query | ninguna encontrada (probablemente `{}`) |

La presencia de una variable `mpin` en `CheckUpiBalance`, leída junto a `cl_version`, es consistente con la sección 6.3: el nombre de la variable por sí solo no prueba que el contenido esté pre-cifrado, pero viaja junto a un string explícito de versión de protocolo CL, lo cual solo tiene sentido si el valor se originó en el intercambio CL.

**Advertencia (found como limitación, no como hallazgo sobre WhatsApp):** `GenCreatePaymentKey`, `RevokeEnrollment` y `BrSaveCPF` resuelven todas a las *mismas* clases caller compartidas (`C42325Iq9`/`C42327IqB`, `RunnableC42211IoJ`) en el catálogo fuente, lo cual devuelve cada literal de string cercano a ese caller como "variables" para las tres ops — esto sobre-recolecta (p. ej., campos específicos de Pix como `pix_key` aparecen bajo una op con nombre de UPI). Tratar las listas de variables largas para esas tres operaciones específicas como un superconjunto ruidoso, no un esquema confirmado por operación.

El resto de las operaciones en el catálogo de 81 entradas (lista completa: `UpiPauseMandate`, `UpiResumeMandate`, `UpiRevokeMandate`, `UpiRejectMandate`, `UpiExecuteMandate`, `GetUpiLiteDetails`, `GetUpiP2mConfig`, `GetUpiPurposeLimitingKey`, `GetUpiSmsContentAndVmn`, `PaymentReminderCreate/Get/Cancel/Stop`, `GetBillReceipt`, `GetBillerPlans`, Pix de Brasil (`GetPixInfo`, `GetPixBankList`, `GetMerchantPixInfo`, `CompletePixTransaction`, `GenPayWithPixPrecheck`), biométrico/passkey (`Br*Passkey*`, `BrAuthorizeBiometricPayment`), y las ops de suscripción/promo `Wamo*`) están catalogadas con sus doc_ids pero no fueron re-verificadas individualmente contra un call site en esta pasada — tratar su presencia como `found` (son entradas literales en el asset de 2.26.41.6) y su forma de solicitud exacta como `unknown` salvo que se liste arriba.

---

## 10. Reglas de lectura automática de OTP de NPCI (específico de India/UPI)

`assets/npci/npci_otp_rules.json` (found, 5 reglas) es consumido por `org.npci.upi.security.pinactivitycomponent.C0315u` para extraer automáticamente un OTP de 6 dígitos de un SMS entrante del banco/NPCI durante un flujo UPI, puramente como conveniencia de tipeo — no genera, valida ni transmite el OTP. Las 5 reglas comparten `sender: ["[a-zA-Z]+"]` (código corto alfabético) y `otp: "\d{6}"`; solo la frase disparadora difiere (`"is your OTP"`, `"OTP is"`, `"one time password is"`, `"is your one time password"`, `".*OTP for Aadhaar.*"`). El caller puede sobrescribir en tiempo de ejecución la regex de cantidad de dígitos del OTP (`\d{` + `i` + `}`) cuando pasa una longitud distinta de cero. Un cuerpo que contiene `"Aadhaar"`/`"AADHAAR"` se cachea bajo la clave de SharedPreferences `otp_type_aadhaar`, de lo contrario `otp_type_bank`.

Este asset y su clase consumidora no cambiaron en tipo respecto a un análisis previo de `2.26.34.4`; no re-diferenciado byte a byte independientemente contra 2.26.41.6 en esta pasada (continuidad `inferred`, no re-verificada).

---

## 11. Flags de funcionalidad

IDs de AB-prop leídos directamente en `PaymentsMessageHandler` (`C24410wL`, call sites found) salvo que se indique lo contrario. No se encontraron IDs de flag numéricos que condicionen los campos proto de la sección 2 en sí (esos son incondicionales en el wire); todos los flags encontrados en esta pasada condicionan el *manejo* de pushes del servidor o empujones de UI.

| Flag | Controla |
|---|---|
| **1458** | elimina un alias UPI de pago cacheado localmente una vez que el servidor lo reporta como `deregistered` |
| **1644** | elegibilidad de recuperación de cuenta UPI (`payments-enabled:account-recovery-enabled`) |
| **2000** | elegibilidad de recuperación de cuenta de Pix de Brasil (compuerta equivalente para `service=BR`) |
| **1746** + **5049** (ambos requeridos) | tarjeta educativa post-transacción "custom item"/resumen de orden mostrada después de un pago completado (empujón educativo BIP) |
| **12214** | ruta de creación de usuario FB durante la recuperación de cuenta UPI (vs. llamada de recuperación directa) |
| **423** | seguimiento de uso de invitación de pagos, ruta antigua |
| **544** | seguimiento de uso de invitación de pagos, ruta adicional (verificado junto con 423 vía OR) |
| **20869** | verificación de lista de PSP permitidos durante el manejo de notificación de recuperación de cuenta; pref de string emparejada `32353` (lista de PSP opt-in separada por comas, leída vía una AB prop con valor de string, no un flag numérico) |

No se encontraron IDs de feature flag que condicionen específicamente la secuencia de activities de onboarding de UPI de India (sección 4) o la ruta de vinculación de dispositivo CL de NPCI (sección 6) en esta pasada — `unknown`, no rastreado más allá de la clase manejadora arriba.

---

## 12. Códigos de rechazo/error

### 12.1 Rechazo/cancelación dentro del protocolo (found)

Como se estableció en la sección 2.4, `declinePaymentRequestMessage`/`cancelPaymentRequestMessage` llevan **solo** una referencia `MessageKey` a la solicitud original — ningún enum de razón, ningún campo de texto libre. Un cliente que muestra "rechazado: fondos insuficientes" o similar lo hace a partir de estado **local** (la propia copia de UI del remitente, o un estado `transaction`/`PaymentInfo` correlacionado posterior, sección 8), no a partir de nada que el mensaje decline/cancel transmita en sí.

### 12.2 Campos de estado de PaymentInfo (existencia found, mapeo unknown)

`DTS.status_` (campo 4) y `DTS.txnStatus_` (campo 10) son campos de tipo enum separados (sección 2.8). Su mapeo ordinal→etiqueta no pudo recuperarse solo a partir del bytecode javalite (los nombres de constante de enum fueron eliminados por la obfuscación del build de las clases `Internal.EnumVerifier`) — `unknown`. `futureproofed` (campo 8, bool) es una válvula de escape deliberada que se establece cuando el objeto local del remitente no tiene monto/moneda resolubles, permitiendo que un receptor en un cliente más nuevo renderice un estado que de otro modo no podría analizar.

### 12.3 Mapa de errores enviado por el servidor (claves de pref found, consumidor no rastreado completamente)

Las claves de preferencia `payments_error_code`, `payments_error_text`, `payments_error_title`, `payments_error_map_tag`, `payments_error_map_last_sync_time_millis` indican que los códigos de error se resuelven contra un **mapa sincronizado con el servidor** (código → título/texto), no un enum o tabla de strings fijo del lado del cliente. Esto significa que el *texto* de rechazo/error mostrado a un usuario puede cambiar con el tiempo/región sin una actualización de la app. La clase que realiza esta sincronización no fue identificada en esta pasada (`unknown`).

### 12.4 Fallos de la capa CL de NPCI (found, sin código estructurado)

`BinderC48420LDc.BW1()` (verificación de integridad del dispositivo), `CRH`/`CRh`/`CRi` (validación de certificado de dispositivo/estado) fallan todos **silenciosamente** — devuelven `false`/lanzan excepción, sin código de error expuesto a través del límite AIDL más allá del booleano. Cualquier mensaje visible para el usuario ante un fallo de la capa CL se construye entonces enteramente del lado de WhatsApp a partir del resultado booleano, no a partir de un código suministrado por NPCI (`inferred`, consistente con que la forma de la interfaz AIDL de la sección 6.1 no tiene métodos de retorno de código de error).

---

## 13. Específico de India/UPI vs. general — división explícita

| Hallazgo | Alcance |
|---|---|
| Campos proto de `sendPaymentMessage`/`requestPaymentMessage`/`declinePaymentRequestMessage`/`cancelPaymentRequestMessage`/pago dividido/`PaymentInviteMessage`/`PaymentReminderMessage` (sección 2) | **general** — los mismos campos proto de `Message` sin importar el rail; `payeeVpa` (sección 2.6) es el único nombre de campo con sabor UPI pero el campo en sí está presente incondicionalmente en el esquema |
| Objeto de estado de transacción `PaymentInfo` (`DTS`) (sección 2.8, 8) | estructura **general**; `useNoviFiatFormat` y los códigos de servicio heredados `FBPAY`/`NOVI`/`PIX`/`UPI` muestran que el mismo objeto/ruta de notificación se comparte entre todos los rails |
| Paquetes de rail `indiaupi`, `brazilpay`, `mexico`, `indonesia`, `upr` (sección 3) | divididos explícitamente por paquete; `upr`/`common` son agnósticos de rail, el resto son de un solo país |
| Vinculación de VPA, flujo de mapper UPI, activities de onboarding (sección 4) | **solo India/UPI** |
| Biblioteca "CL" de credenciales/vinculación de dispositivo de NPCI, criptografía RSA/AES, lectura automática de OTP (secciones 6, 7, 10) | **solo India/UPI** — esta capa entera está ausente para Pix/México/Indonesia en el código explorado |
| Catálogo de doc_id de GraphQL (sección 9) | mixto — el catálogo en sí abarca operaciones de UPI, Pix, biométrico/passkey (Brasil), y agnósticas de rail (`Wamo*`, `Gen*`) bajo un esquema; el alcance de cada op sigue su propio nombre/prefijo (`Br*` = Brasil, `Upi*`/`GetUpi*`/`SetUpi*` = India) |
| Tipos de notificación de `PaymentsMessageHandler` (sección 8.2) | mixto — los tipos estilo `pay`/`transaction`/`alert`/`step_up`/`account` son genéricos; el tipo `upi` y las ramas `service=UPI` son específicas de India, las ramas `service=BR` son específicas de Brasil |

---

## 14. Nota sobre Baileys

Clientes estilo Baileys pueden construir y analizar los tipos de mensaje de la sección 2 (son campos protobuf comunes del `Message` estándar), y en principio pueden llamar a los doc_ids GraphQL de `whatsapp`/`whatsapp_mex` con variables armadas a mano. **No pueden** completar significativamente un pago UPI: el intercambio de MPIN/vinculación de dispositivo de la sección 6 corre a través de un componente Android nativo embebido, firmado por NPCI, vinculado a una relación de confianza real con un backend bancario/NPCI (clave RSA respaldada por TEE, `CN=NPCI_CERT`) que no tiene equivalente fuera de la app oficial. Un `sendPaymentMessage` de Baileys es por lo tanto un mensaje correcto a nivel de protocolo pero funcionalmente inerte a menos que se empareje con una transacción que fue realmente autorizada a través del flujo NPCI real.

---

## 15. Casos de error/detalles a tener en cuenta

| Síntoma | Causa | Arreglo/nota |
|---|---|---|
| El mensaje de rechazo/cancelación no tiene razón visible en el wire | diseño de protocolo (sección 2.4) — solo existe una referencia `MessageKey` | no esperar un código de razón del mensaje en sí; correlacionar con una notificación `transaction` posterior o estado local |
| Una operación de credencial condicionada por `BW1()` falla sin texto de error | el dispositivo no tiene StrongBox/TEE, o está rooteado | expuesto solo como un fallo booleano del lado de WhatsApp; no se puede distinguir de otros fallos de CL sin logging adicional |
| Las variables GraphQL `mpin`/`new_mpin`/`old_mpin` parecen texto plano en un dump de call site descompilado | son producidas por el intercambio CL (sección 6.3), no tipeadas directamente en la llamada GraphQL | no asumir transmisión de PIN en texto plano sin rastrear los bytes reales en tiempo de ejecución — este reporte no afirma haberlo hecho |
| `GenCreatePaymentKey`/`RevokeEnrollment`/`BrSaveCPF` muestran listas enormes de variables con sabor Pix | sobre-recolección de clase caller compartida en la extracción del catálogo de doc_id (sección 9.2) | tratar como ruidoso, verificar por campo antes de confiar en ello |
| Los valores de enum `txnStatus`/`status` no se pueden nombrar | el `EnumVerifier` obfuscado elimina los nombres de constante | requiere correlación de strings en tiempo de ejecución (strings de recursos de UI mapeados a ordinales), no hecho en esta pasada |

---

## 16. Distinciones clave

| No confundir | Detalle |
|---|---|
| E2E del mensaje de chat vs. blob de credencial NPCI (sección 7) | dos capas criptográficas separadas; la segunda es solo India/UPI y se sitúa completamente fuera del proto `Message` |
| `DTS` PaymentInfo vs. los cuatro tipos de mensaje de pago del chat | `DTS` es un objeto de history-sync/estado (`WebMessageInfo.paymentInfo_`), nunca un mensaje de chat enviable de forma independiente |
| `status` vs. `txnStatus` en `DTS` | dos enums independientes, granularidad diferente, ambos opacos a nivel de ordinal en este build |
| Esquema `www`/`whatsapp` vs. esquema `mex`/`whatsapp_mex` de doc_ids | transporte diferente (POST GraphQL de doc_id persistido vs. IQ `w:mex`); casi todas las ops de pago están del lado `www`/`whatsapp` en este build |
| Onboarding agnóstico de rail "UPR" vs. onboarding de UPI de India | UPR (`com.whatsapp.payments.upr`) es una capa genérica más nueva; las activities de onboarding específicas de `indiaupi` (sección 4) son un flujo separado, más antiguo y mucho más grande, aún presente lado a lado en 2.26.41.6 |
| "Common Library" de NPCI (`org.npci.upi.*`) vs. el propio código `com.whatsapp.payments.*` de WhatsApp | el primero es un componente de terceros embebido con su propia superficie AIDL; el código de WhatsApp solo lo lanza y lee de vuelta un string/bundle opaco |

---

## 17. Flujo completo (UPI de India, caso de envío de dinero)

```
[Payer chat]                 [WhatsApp client]                    [NPCI CL component]            [NPCI / Issuer bank]
     │ tap "Pay"                    │                                      │                             │
     ▼                              ▼                                      │                             │
 open IndiaUpiSendPaymentActivity → IndiaUpiSendPaymentToVpaFragment       │                             │
     │                              │ amount/VPA/note entered              │                             │
     │                              ▼                                      │                             │
     │                     CLRemoteService.Acc(keyCode, keyXmlPayload,     │                             │
     │                       controls, configuration, salt, payInfo, …) ──►│                             │
     │                              │                                GetCredential activity (PIN pad)    │
     │                              │                                      │ user enters MPIN            │
     │                              │                             AZO(): RSA/AES challenge-response ────►│
     │                              │                                      │◄──── signed/verified ────── │
     │                              │◄──── opaque credential blob ─────────│                             │
     │                              │                                      │                             │
     │                     build RequestPaymentMessage / SendPaymentMessage (section 2)                  │
     │                              │ amount, note, requestMessageKey, background                        │
     │                              ▼                                                                     │
     │                     chat E2E encrypt, send as normal <message>                                    │
     │                              │                                                                     │
     │                     CheckUpiBalance / SetUpiChangeMpin / mandate GraphQL op ─────────────────────► │
     │                              │          (credential_fbid, device_id, mpin blob, vpa, seq_no)       │
     │                              │◄──────────────── result / error (section 12.3 error map) ────────── │
     ▼                              ▼                                                                     │
[Payee chat]            server pushes <notification type="transaction"> ──────────────────────────────── │
     │                              │  PaymentsMessageHandler.A0A updates local F7F,                      │
     │                              │  EKY.A00 builds PaymentInfo (DTS) for history sync                  │
     ▼                              ▼
 status shown in chat        transaction row updated, payments_all_transactions_last_sync_time bumped
```

---

## 18. Desconocidos

| Tema | Razón |
|---|---|
| Números de campo de `Message` de nivel superior para `splitPaymentMessage`, `splitPaymentUpdateMessage`, `paymentReminderMessage` | la decodificación del string de información no se llevó lo suficientemente lejos en esta pasada; los propios campos del submensaje (sección 2.5/2.6) no se ven afectados |
| Mapeo de etiquetas de enum `DTS.status_`/`txnStatus_` | `EnumVerifier` obfuscado, nombres de constante eliminados |
| Mecanismo de transporte exacto para las llamadas GraphQL de doc_id persistido del esquema `whatsapp` (`www`) | no rastreado hasta un call site HTTP/IQ en esta pasada; marcado `inferred` en todo el reporte |
| Clase(s) consumidora(s) para el mapa de errores sincronizado con el servidor `payments_error_map_*` | claves de pref encontradas, clase de lectura/escritura no identificada |
| Contenido de los paquetes `mexico`/`indonesia`/`dcp`/`phoenix` | existencia del paquete confirmada, contenido no explorado |
| Si las variables GraphQL `mpin`/`new_mpin`/`old_mpin` llevan un blob ya cifrado por NPCI o si se aplica protección adicional solo a nivel TLS | inferred a partir del propósito del flujo CL, no confirmado inspeccionando el contenido real en bytes en tiempo de ejecución |
| IDs de feature flag (si los hay) que condicionen la secuencia de onboarding de UPI de India o la propia ruta de vinculación de dispositivo CL | ninguno encontrado en las clases exploradas |
| Continuidad byte a byte de `npci_otp_rules.json` y los assets `.properties` de CL entre `2.26.34.4` (un análisis previo) y `2.26.41.6` | no re-diferenciado; las clases consumidoras y el vocabulario de claves de bundle en tiempo de ejecución se re-confirmaron independientemente en 2.26.41.6, los bytes del asset en sí no |
| Comportamiento real de tráfico/transacción en vivo | solo análisis estático, sin captura de tráfico, sin transacción en vivo realizada |
</content>
