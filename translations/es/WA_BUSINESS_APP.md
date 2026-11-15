<!-- src-sha1: 349e8112a4dcc4567ce203cf21c4c37e5bb47173 -->
# WhatsApp App de Empresa — Full RE Report
**Versión:** 2.26.45.7 (Business) vs 2.26.45.10 (consumer) | **Fecha:** 2026-11-15
**Alcance:** diff estructural de la APK de WhatsApp Business (`com.whatsapp.w4b`) contra WhatsApp consumer (`com.whatsapp`) — raíces de paquete exclusivas de Business, el stack de React Native, diff de bibliotecas nativas, asimetría del catálogo de doc_id GraphQL/MEX/`www`/`facebook-schema`, diff de permisos; distinción respecto a la WhatsApp Business API/Cloud API y a Managed Account

---

## 1. Visión general

WhatsApp Business es una app separada (`com.whatsapp.w4b`), no un cambio de modo dentro de WhatsApp consumer. Comparte el núcleo del protocolo Signal, el transporte Noise, y la mayor parte de la UI de chat con WhatsApp consumer, pero envía su propio conjunto de paquetes para funciones exclusivas de negocio y empaqueta una dependencia — un runtime completo de React Native — que consumer no lleva en absoluto.

Este informe cubre solo la **app en sí**, diferenciada como APK contra WhatsApp consumer. Es un eje distinto de otros dos conceptos adyacentes a "negocio" ya documentados en este repositorio:

| Concepto | Qué es | Informe |
|---|---|---|
| **App WhatsApp Business** (este informe) | Una APK de cliente distinta (`com.whatsapp.w4b`) que un negocio instala en un teléfono, con su propia UI para catálogo, etiquetas, mensajes de ausencia, anuncios | aquí |
| **WhatsApp Business API / Cloud API** | Infraestructura del lado servidor que hospeda/relaciona los mensajes de un número de negocio, usada en lugar de o junto con la app Business; señalizada en cualquier cliente solo vía campos del certificado de nombre verificado (`host_storage`, `actual_actors`, prefijo de emisor `smb:`/`ent:`) y banners de coexistencia `business_state_id` | `WA_MANAGED_ACCOUNT.md` §9 |
| **Managed Account** | La propia cuenta consumer de un menor, supervisada por un padre/tutor (`ManagedAccount*`/PAA/PMA/PMTA); no relacionado con ninguno de los dos conceptos de negocio, no existe etiqueta "managed" para el caso de negocio | `WA_MANAGED_ACCOUNT.md` §1-8 |

Un solo negocio puede combinar los tres: correr la app Business en un dispositivo, delegar partes de su tráfico a un proveedor de Cloud API (coexistencia), mientras la cuenta del interlocutor de chat es una cuenta consumer ordinaria. Ver §9 para cómo interactúan estos.

Fuente de evidencia: un diff estático de paquete/asset/manifest entre `WA-Business_2.26.45.7.apk` y `WhatsApp_2.26.45.10.apk` (par de beta actual al momento del diff, no una comparación versión-contra-versión). No se corrió un decompile jadx de la APK completa en ninguno de los dos lados (regla de seguridad dura); todos los hallazgos abajo son a nivel de árbol smali de apktool, JSON de assets, y manifest reconstruido. Los niveles siguen `found`/`inferred`/`unknown` según el contrato de evidencia del brain.

---

## 2. Diff a nivel de paquete — found

Comparando cada directorio bajo `smali*/` en cada árbol de apktool: Business tiene 4,281 directorios de ruta de paquete únicos (15 árboles `smali_classesN`), consumer tiene 3,710 (14 árboles). 853 rutas existen solo en Business, 282 solo en consumer. 45 raíces de paquete `com/whatsapp/*` de nivel superior son exclusivas de Business (el directorio raíz en sí está ausente de consumer, no solo una sub-ruta).

### 2.1 Raíces de paquete exclusivas de Business, por clúster de función

| Clúster | Raíces de paquete | Notas |
|---|---|---|
| Mensajería de ausencia / saludo / respuesta rápida | `businessaway`, `businessgreeting`, `businessquickreply`, `businessmissedcallfollowup` | funciones core de auto-respuesta SMB |
| Etiquetas / agentes / asignación de chat | `chatassignment`, `authagent`, `authagentfeaturecontrol`, `smbmultideviceagents`, `businesscontactmanager`, más `lists/smb/labels` (sub-ruta; la raíz `lists` es compartida) | asientos de agente y edición de etiquetas |
| Configuración de perfil / verificación | `businessregistration`, `protectedbusinessaccounts`, `metaverified` | |
| Catálogo/pedidos (lado de gestión) | `ordermanagement` | la navegación/edición de catálogo en sí (`catalog`, `businessproduct`, `businesscollection`) es **compartida** — ver §2.2 |
| Anuncios / integración de Meta Ads | `ads4ads`, `adscreation`, `adcreationinterfaces` | ver §3 para el vínculo con React Native |
| Facturación / suscripciones (tiers de API) | `metabilling`, `metabillingui`, `subscription`, `billingui` | |
| Coexistencia app-a-API | `coexistence`, `connectedaccounts`, `linkedaccounts`, `dynamicaudience` | puentea al lado de Cloud API, §9 |
| Agente de negocio Meta AI | `bizai`, `genai`, `maiba` | |
| Herramientas de negocio / cumplimiento | `businesstools`, `businessinsights`, `rapidfeedbacksurvey`, `reportblocksharing`, `statistics`, `integrityenforcementsinfra`, `eligibilitychecker`, `googleeligibilityapi`, `smb`, `smbauth`, `waloginmbs`, `marketingmessage`, `marketingmessagemanagement`, `mediatemplates`, `bizdatasharing`, `bizgallerypicker`, `bizmedia` | |

### 2.2 Raíces compartidas con subpaquetes exclusivos de Business

Algunas raíces existen en ambas apps porque consumer puede ver/consumir datos del lado negocio, pero los subpaquetes de edición/gestión son solo de Business:

- `com/whatsapp/businessprofile/` — raíz compartida; `businessprofileaddress`, `businessprofilecategory`, `businessprofileedit` (+ `boostmedia`, `businessprofilecompleteness`), `businessvertical`, `businesscompliance/smb/...` son solo de Business. Consumer solo conserva los subpaquetes de vista de perfil del lado lectura.
- `com/whatsapp/lists/` — raíz compartida (modelo de datos/UI de etiquetas, `labelitem` en ambos); el subpaquete de **edición** de etiquetas `lists/smb/labels` es solo de Business.
- `catalog`, `businessproduct` (+ `businessproductlist`), `businesscollection` — raíces compartidas, confirmadas presentes en el árbol smali de consumer como la UI de **navegación** de catálogo/producto mostrada al ver un chat de negocio.

Forma neta: la visualización de catálogo/producto, la visualización de perfil de negocio, y la visualización de etiquetas son compartidas; la edición de catálogo/perfil, la mensajería de ausencia/saludo/respuesta rápida, la edición de etiquetas, la autenticación de agente/multi-dispositivo, la creación de anuncios, y la coexistencia con Cloud API son exclusivas de Business.

### 2.3 Paquetes exclusivos de consumer — found, sin agrupar

282 rutas existen solo en consumer. Una revisión puntual no reveló un clúster temático comparable en tamaño al conjunto exclusivo de Business; la mayoría son hijos anidados de un número menor de raíces exclusivas de consumer. No se profundizó — listado como vacío abierto en §8.

---

## 3. El stack de React Native — found, exclusivo de Business

Hallazgo inesperado: Business empaqueta un stack completo de React Native ausente de consumer a nivel de paquete, no solo un módulo de función adicional.

| Paquete | Business | Consumer |
|---|---|---|
| `com/facebook/react/*` (bridge, fabric, animated, devsupport, turbomodule, …) | 88 dirs | 0 |
| `com/facebook/catalyst/*`, `com/facebook/fbreact/*` (módulos de bridge RN, i18n, safe-area) | presente | ausente |
| `com/facebook/hermes/*` | 3 dirs | 1 dir — solo una referencia suelta, sin `com/facebook/react` para emparejar con ella, es decir, no es un runtime RN funcional |
| `com/caverock/androidsvg`, `com/crossapp/graphql/facebook/*` | presente | ausente |

Corroborado a nivel de biblioteca nativa (§4): `libreactnative.so` (runtime RN), `libappmodules.so` (el cargador nativo del bundle JS de RN), y `libimagepipeline.so` (Fresco, el pipeline de imágenes de RN) son archivos `.so` exclusivos de Business.

**Inferred**, no confirmado: alguna superficie exclusiva de Business — más plausiblemente la creación de anuncios (`adscreation/lwi/react/*` tiene un subpaquete `react` directamente dentro de `lwi`), Meta-billing, o el onboarding de coexistencia — se implementa como pantallas de React Native embebidas en lugar de UI nativa de Android. Qué función(es) específica(s) usan el stack RN no está confirmado solo a partir de nombres de paquete; necesitaría un decompile acotado de las clases `adscreation/lwi/react/activity`. Esta es la "dependencia sorprendente" más clara que queda: una app de mensajería de negocio embebe un runtime de UI JS multiplataforma, aparentemente solo para una o pocas pantallas (la creación de anuncios es la coincidencia de nombres más fuerte).

---

## 4. Diff de biblioteca nativa — found

Se comparó `superpack_index.csv` (el manifest propio de biblioteca del contenedor SUPERPACK_OB) entre los resultados de reconstrucción de ambas apps:

| | Conteo |
|---|---|
| Bibliotecas indexadas de consumer | 84 |
| Bibliotecas indexadas de Business | 89 |

**Exclusivas de Business (5):** `libappmodules.so`, `libimagepipeline.so`, `libreactnative.so`, `libwacomponents.so` (el nombre sugiere una biblioteca de componentes puente RN de autoría de WhatsApp, no RN de fábrica), `libzstddecoder.so` (probablemente descompresión de bundle/asset de RN).

**Exclusivas de consumer:** ninguna — todos los nombres de biblioteca de consumer también aparecen en el índice de Business.

Las 6 bibliotecas decompiladas por oráculo de dispositivo compartidas por ambas apps (`libwhatsapp.so`, `libwhatsappmerged.so`, `libwasafe.so`, `libvoprf-ed25519.so`, `libohai.so`, `libcurve25519.so`) son idénticas entre ambas apps (mismos tamaños, mismos conteos de símbolo/export) — el núcleo de protocolo Signal/atestación/integridad de cliente no se toca en el build de Business. El stack de React Native + Fresco es exclusivo de Business tanto a nivel de paquete Java/Kotlin como a nivel de biblioteca nativa — un hallazgo consistente de dos capas.

---

## 5. Diff del catálogo de doc_id GraphQL / MEX / `www` / `facebook-schema` — found

Cada app envía su propio catálogo de doc_id `assets/whatsapp-android-<schema>_client_persist_ids.json`, leído directamente del árbol de assets decodificado por apktool (sin necesidad de decompile).

| Schema | Ops de Business | Ops de consumer | Solo Business | Solo consumer |
|---|---|---|---|---|
| `mex` | 242 | 242 | 0 | 0 — conjunto idéntico |
| `wamo` | 22 | 22 | 0 | 0 — conjunto idéntico |
| `www` | 237 | 244 | 4 | 11 |
| `facebook-schema` | 224 | 17 | 215 | 7 |

### 5.1 `mex` y `wamo` — idénticos entre apps

Ambos catálogos tienen exactamente los mismos nombres de operación en ambas APKs (la diferencia de conjunto está vacía, no solo igual en cantidad). Business no lleva ninguna superficie MEX/GraphQL específica de Business a este nivel de schema — comparte el catálogo de consumer en su totalidad.

### 5.2 `www` — asimetría pequeña

- Solo Business (4): `BPAccessTokenAndSessionCookiesMutation`, `CatkitTypeaheadProxy`, `WACreateEnforcementAppeal`, `WAGetEnforcementAppealStatus`.
- Solo consumer (11): `WaAutofillAcknowledgeWalletTerms`, `WaAutofillFetchContactData`, `WaAutofillFetchSettings`, `WaAutofillSaveContactData`, `WaAutofillUpdateNegativeInteraction`, `WaAutofillUpdateSaveCvv`, `WaCreateLabyrinthBackupMutation`, `WaDeleteLabyrinthAccountMutation`, `WaDeleteLabyrinthThreadsMutation`, `WaRotateLabyrinthEpochMutation`, `WaUploadLabyrinthMessagesMutation`.

Consumer lleva sus propias ops de pagos personales/autofill (`WaAutofill*`) y de backup de chat E2E (`WaCreateLabyrinthBackupMutation` etc. — el sistema de backup de chat de WhatsApp, "Labyrinth" internamente) que Business no tiene; Business lleva un par de ops de apelación de cumplimiento de cuenta y de sesión/typeahead que consumer no necesita.

### 5.3 `facebook-schema` — el hallazgo principal: 215 ops exclusivas de Business

Aquí es donde vive la verdadera superficie GraphQL específica de Business — no `mex`/`wamo`, que son byte-idénticos entre ambas apps. Business lleva 224 ops en este schema contra las 17 de consumer; las 17 de consumer son ops de pago personal/nonce de comercio no relacionadas (`AcDcCreateCanonicalDigitalCommerceNonce`, `WaAutofillAddPayCreditCard`, `WaGetServerEncryptionKey`, etc.) que Business no lleva.

Las 215 ops exclusivas de Business, agrupadas por nombre (agrupación descriptiva, derivada de análisis estático, no una taxonomía funcional confirmada):

| Clúster | Ops de ejemplo |
|---|---|
| Base de conocimiento / respuesta-IA / simulación ("coach") | `FetchAIAbilities`, `KnowledgeRepoFetchV2`, `UpdateAIKnowledge`, `DeleteAIKnowledge`, `CoachSimulationMessage`, `CoachSuggestedReply`, `StartSimulation`, `SubmitSimulationFeedback`, `FetchSuggestedReply`, `MarkSuggestedReplyUsed` |
| Agente de negocio Meta AI / MAIBA | `MAIBAOnboarding`, `MAIBACompleteParallelOnboarding`, `Maiba1pCalendarEvents`, `MaibaGetCurrentCatalog`, `MaibaDownloadLeadGenFlow`, `MetaAIBizAgentWAAIHome`, `MetaAIBizAgentWACoachingMutation` |
| Lead-gen / citas | `CreateLeadGenFlow`, `GetLeadGenFlowLeads`, `UpdateLeadStages`, `CreateAppointmentFlow`, `GetAppointmentPrefill`, `GetDefaultAvailability` |
| Agente de autenticación / multi-agente SMB / login | `AuthAgentCompanyInfoQuery`, `AuthAgentFeaturePolicyQuery`, `AddSmbAgentAndCoexQr`, `SmbRegistrationInit`, `WALoginClaimAuthChallenge`, `WALoginConfirmAuthChallenge` |
| Coexistencia app-a-Cloud-API | `CoexUnifiedOnboarding`, `CoexMultiAppEligiblity`, `CoexAppsAndServicesOffboardProduct`, `CoexCompanionPairingStatusCallback`, `CoexistenceQRCodeFetch` |
| Anuncios Click-to-WhatsApp (CTWA) | `CTWACreateLookAlikeAudienceMutation`, `CTWAPreviousAdsRecommendationQuery`, `CtwaLinkedMediaQuery`, `CtwaNativeUploadAdMediaMutation` |
| Cuenta de anuncios / elegibilidad | `AdAccountEligibilityCheckerQuery`, `OnboardToWhatsAppAdAccount`, `WhatsAppBizFetchAdDefaults`, `WhatsAppBizGetEstimatedAdReach` |
| Gestión de catálogo (lado de escritura) | `WhatsAppCatalogAddProduct`, `WhatsAppCatalogEditProduct`, `WhatsAppCatalogDeleteProduct`, `WhatsAppCatalogCreateCollections`, `WhatsAppCatalogProductVisibilityUpdate` |
| Difusión de mensajes de marketing ("Pro") | `BusinessBroadcastProCampaignContent`, `BusinessBroadcastProCustomAudiencesQuery`, `BusinessBroadcastProInsights`, `WAMarketingMessagesCustomAudienceCreateMutation` |
| Gestor de contactos / perfiles de cliente | `BizContactManagerProfiles`, `ContactManagerAccessState`, `WACustomerProfiles`, `UpsertWACustomerProfiles`, `DeleteWACustomerProfile` |
| Facturación / suscripción (tiers facturados por Meta) | `FetchSubscriptionState`, `FetchSubscriptionStateV2`, `WaSmbMetaOneTierPaymentPrefetchTargetQuery`, `AcceptBizAiPaymentTerms` |
| Exportación de historial de chat / integración 3P (GDrive) | `FetchChatHistoryExportStatus`, `GDriveGetFiles`, `UploadHistoricalMetadata`, `Disconnect3PPartners` |
| Cuenta IG/FB vinculada | `SetIGDisplayContactInfoMutation`, `WAFBPageProfileImportGet`, `WhatsAppBusinessLinkedAccountsQuery` |
| Plomería de QE/feature-flag (lado negocio) | `CheckQEBool`, `WaFetchQEBool`, `WaFetchQEString`, `WhatsAppGraphQLCheckQE` |

La lista completa de 215 nombres es reproducible a partir de los archivos de assets de las dos apps citados arriba; no se reproduce textualmente aquí. Los **valores** de doc_id de `www`/`facebook-schema` (no solo los nombres de op) no se diferenciaron — un nombre de op compartido podría en principio llevar aún un doc_id distinto entre las dos apps; no se verificó.

---

## 6. Diff de permisos — found

Del inventario de manifest de cada app:

| | Exclusivo de Business | Exclusivo de consumer |
|---|---|---|
| Permiso | `com.whatsapp.permission.MIGRATION_CONTENT_PROVIDER` | `android.permission.RECEIVE_SMS` |

Ambas apps además solicitan permisos propios de self-broadcast/maps bajo sus respectivos nombres de paquete (`com.whatsapp.w4b.*` vs `com.whatsapp.*`) — estos son equivalentes con nombre de paquete alterado entre sí, no funcionalmente nuevos, y no se cuentan arriba.

Business no solicita recepción de SMS. **Inferred**, no confirmado por código: consistente con que las cuentas de Business se registran más a menudo vía una ruta de Cloud/Business API en lugar de depender de la lectura automática de SMS en el dispositivo para el OTP — pero este razonamiento no está verificado contra ningún código de flujo de registro en esta pasada.

---

## 7. Nota Baileys / velowa

Casi nada de la superficie de este informe es alcanzable desde un cliente vanilla de WhatsApp Web (velowa o cualquier implementación del protocolo Noise/multi-dispositivo):

- Los catálogos `mex`/`wamo` son **idénticos** a los de consumer — nada específico de Business que añadir ahí; cualquier cliente de WA Web ya tiene los mismos doc_ids.
- Las 215 ops de `facebook-schema` (§5.3) son la verdadera superficie GraphQL específica de Business, pero son flujos conducidos por la UI de la app **Business** (edición de catálogo, creación de anuncios, coaching/MAIBA, onboarding de coexistencia, autenticación de agente) con compuerta detrás del propio estado de cuenta de la app Business y, en varios clústeres, enteramente detrás del lado servidor de la WhatsApp Business API/Cloud API (coexistencia, facturación, cuentas de anuncios). Un cliente de WA Web que hable el protocolo multi-dispositivo ordinario no tiene ninguna ruta hacia la mayoría de estas — no son funciones de protocolo de cable en absoluto, son llamadas REST/GraphQL que hace la propia UI de la app Business contra el backend de la plataforma de negocio de Meta.
- La superficie de creación de anuncios en React Native (§3) es solo UI de la app Android (pantallas JS embebidas renderizadas por `libreactnative.so`); nada de ella viaja sobre el protocolo de cable del chat.
- La única área con alguna relevancia de protocolo multi-dispositivo es la coexistencia (`coexistence`/`connectedaccounts`/`linkedaccounts`), cuya representación de dispositivo/sesión está cubierta por la documentación existente en `WA_MANAGED_ACCOUNT.md` §9.3 y `WA_LINKED_DEVICE_PAIRING.md` (tipo de cuenta `HOSTED`, id de dispositivo 99, `platformType` 23/25-27) — esa parte ya es tan lejos como puede llegar una vista solo del lado cliente.

En resumen: este informe es útil para entender qué *contiene* la APK de Business, no como fuente de nueva superficie de protocolo de cable para velowa.

---

## 8. Lo que este informe NO ha verificado

| Vacío | Por qué | Seguimiento necesario |
|---|---|---|
| Diff de proto/wire-schema entre las dos apps | `unknown`, no inferred-same. La etapa proto del pipeline de reconstrucción no corrió para ninguno de los dos builds (`protoc_ok=False` en ambos lados); la extracción proto más profunda usada en otra parte de esta pasada de actualización de versión (1089 mensajes, salida 0 de `protoc`) corrió solo contra el decompile jadx preexistente de consumer — no existe un decompile equivalente para `com.whatsapp.w4b` en este workspace. Producir uno necesita una corrida jadx de APK completa, prohibida por la regla de seguridad dura de esta sesión (bloqueó previamente la máquina de análisis). Evidencia ausente no es evidencia de ausencia. | Una extracción jadx de una sola clase o un solo DEX acotada solo a las clases de mensaje/proto (no un decompile de APK completa) |
| Qué función(es) se renderizan a través del stack de React Native exclusivo de Business | Solo correlación de nombre de paquete/biblioteca (`adscreation/lwi/react/*` es la coincidencia de nombres más fuerte, pero no confirmada) | Decompile acotado de las clases `com/whatsapp/adscreation/lwi/react/*` |
| Clúster de paquetes exclusivo de consumer (282 rutas) | No agrupado temáticamente en esta pasada — prioridad menor dado el encuadre de la tarea en la superficie exclusiva de Business | Una pasada dedicada sobre el diff de las 282 rutas |
| **Valores** de doc_id de `www`/`facebook-schema` | Solo se diferenciaron los **nombres** de op; un nombre compartido podría llevar un doc_id distinto por app | Diff a nivel de valor de ambos JSON de assets |
| Lista completa de 215 ops / variables / formas de respuesta de `facebook-schema` | La agrupación es solo por palabra clave de nombre; no se intentó recuperación de call site ni de campo de respuesta | Rastreo de call site dirigido por clúster, como se hizo para las ops MEX de otros informes |

---

## 9. Distinciones clave

| A | B |
|---|---|
| **App** WhatsApp Business (`com.whatsapp.w4b`) — una APK distinta con su propio conjunto de paquetes, este informe | **API / Cloud API** de WhatsApp Business — hospedaje/relevo del lado servidor de los mensajes de un número de negocio; sin APK de cliente dedicada, señalizada en cualquier cliente vía campos de certificado de nombre verificado (`WA_MANAGED_ACCOUNT.md` §9) |
| Paquetes `coexistence`/`connectedaccounts`/`linkedaccounts` de la app Business — la propia UI de la app para puentear hacia un proveedor de Cloud API | Banners de coexistencia `business_state_id` vistos por el cliente de un **interlocutor** (consumer o Business) cuando un número de negocio corre tanto la app como la API a la vez (`WA_MANAGED_ACCOUNT.md` §9.2) |
| Managed Account (`ManagedAccount*`, PAA/PMA/PMTA) — la propia cuenta **consumer** de un menor bajo supervisión parental | App Business — la cuenta de un negocio, concepto enteramente no relacionado, sin superposición de código/schema |
| Catálogos de doc_id `mex`/`wamo` — conjuntos de nombres de op byte-idénticos en ambas apps | Catálogo de doc_id `facebook-schema` — 215 ops existen solo en Business; aquí es donde realmente vive la superficie GraphQL específica de Business |
| **Visualización** de catálogo/perfil/etiquetas — raíces de paquete compartidas, presentes también en consumer (así un usuario consumer puede navegar el catálogo de un negocio) | **Edición** de catálogo/perfil/etiquetas — raíces de paquete exclusivas de Business (el lado de escritura al que solo el negocio mismo puede llegar) |

---

## 10. Resumen

Confirma la forma esperada de entrada — catálogo, perfil de negocio/verificación, etiquetas, respuestas rápidas/saludo/mensajería de ausencia, el clúster de autenticación de agente/multi-dispositivo en código exclusivo de Business, con la mitad de visualización/display de cada uno compartida con consumer — y añade dos hallazgos no anticipados:

1. **`facebook-schema` es donde realmente vive la superficie GraphQL específica de Business** (215 ops exclusivas de Business: coach IA/base de conocimiento, MAIBA, lead-gen, agente de autenticación, coexistencia, anuncios CTWA, ops de escritura de catálogo, difusión de marketing, facturación), no los catálogos principales `mex`/`wamo`, que son conjuntos de nombres de op byte-idénticos entre las dos apps.
2. **Business empaqueta un stack completo de React Native + Fresco** (`com.facebook.react.*`, `libreactnative.so`, `libimagepipeline.so`, `libwacomponents.so`) enteramente ausente de consumer, tanto a nivel de paquete como de biblioteca nativa — más plausiblemente respaldando las pantallas de creación de anuncios, pero el límite exacto de la función no está confirmado sin un decompile acotado.

El diff de proto/wire-schema no se pudo hacer en esta pasada (§8) y se registra como unknown, no inferred-same.
