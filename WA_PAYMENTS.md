# WhatsApp Payments — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-11-01
**Scope:** in-chat payment message types (`sendPaymentMessage`, `requestPaymentMessage`, `declinePaymentRequestMessage`, `cancelPaymentRequestMessage`, split payments, payment invite/reminder) and their proto fields, multi-rail client architecture (India UPI, Brazil Pix, Mexico, Indonesia, generic "UPR" rail), VPA/bank-account linking and UPI onboarding flow, the embedded NPCI "Common Library" (CL) credential/PIN/device-binding layer, transaction-status sync, encryption layering (chat E2E vs NPCI credential blob), GraphQL/MEX payment operations (doc_ids), NPCI OTP auto-read rules, feature flags, decline/error-code handling

---

## 1. What it is (overview)

WhatsApp Android ships one shared in-chat payment protocol (proto message types carried inside the normal E2E `Message`) plus several country-specific payment *rails*, each with its own onboarding UI, GraphQL operations, and (for India) an embedded third-party credential library. All findings are static analysis of the decompiled APK; nothing was captured on the wire. Tiers: **found** = read directly in code/assets, **inferred** = deduced from code, **unknown** = not resolved. Obfuscated names are per-build and were resolved in 2.26.41.6 from stable strings (`FIELD_NUMBER` constants, AIDL interface names, GraphQL operation catalogs, asset file names).

| Layer | 2.26.41.6 name / path | Role |
|-------|------------------------|------|
| Chat message protocol | `DSJ` SendPaymentMessage, `C30605DSz` RequestPaymentMessage, `C30502DPa` DeclinePaymentRequestMessage, `DPZ` CancelPaymentRequestMessage, `DT0`/`C30535DQh` split payment, `C30586DSg` PaymentInviteMessage, `C43112IrN` PaymentReminderMessage, `DTS` PaymentInfo | fields in section 2 |
| Rail packages | `com.whatsapp.payments.{common,indiaupi,brazilpay,mexico,indonesia,globalorder,upr,dcp,remittances,split,paymentkey,productinfra,integrity,phoenix}` | one package per market/rail, section 3 |
| India UPI credential library | `org.npci.upi.security.{services,pinactivitycomponent}` (`CLRemoteService`, `CLRemoteServiceImpl`, `BinderC48420LDc`, `GetCredential`) | embedded NPCI "Common Library" (CL), section 6 |
| OTP auto-read | `assets/npci/npci_otp_rules.json`, consumer `org.npci.upi.security.pinactivitycomponent.C0315u` | section 10 |
| GraphQL/MEX catalog | `assets/whatsapp-android-www_client_persist_ids.json` (schema `whatsapp`), `whatsapp-android-mex_client_persist_ids.json` (schema `whatsapp_mex`) | doc_ids, section 9 |
| Server push handler | `C24410wL` ("PaymentsMessageHandler", log tag `PaymentsMessageHandler`) | `<notification type="pay\|upi\|fbpay\|transaction\|account-recovery\|alert\|...">`, section 8 |
| Transaction object | `F7F` (local transaction row), `DTS` (wire/history-sync PaymentInfo), built by `EKY.A00` | section 8 |

Rails identified from package/class names (found): **India UPI** (`indiaupi`), **Brazil Pix** (`brazilpay`), **Mexico** (`mexico`), **Indonesia** (`indonesia`), plus a rail-agnostic "**UPR**" package (`upr` — onboarding, account management, bubble UI) and a legacy Meta Pay/Novi reference still present in enum/notification code (`FBPAY`, `NOVI`) though those services are long defunct — kept here only because the literal strings still exist in 2.26.41.6. Evidence below is tagged **India/UPI-specific** or **general** per section; do not assume UPI findings apply to Pix/Mexico/Indonesia.

---

## 2. Payment message types and proto fields

### 2.1 Placement in `Message` (found)

All payment message types are direct fields of the top-level `Message` proto (`C30628DTw`, same class documented in `WA_MESSAGE_SECRETS.md`). Most payment sub-messages do **not** expose public `FIELD_NUMBER` constants on `Message` itself; the numbers below were recovered by decoding the class's packed `GeneratedMessageLite` message-info string (a reproducible 2-or-3-char-per-field encoding: field-number char, type-marker char, has-bit-index char; the has-bit index increments by exactly one per entry across the full ~150-field message, which is a strong internal consistency check on the decode).

| Field (Message) | Number | Type |
|---|---|---|
| `sendPaymentMessage` | **16** | `SendPaymentMessage` (`DSJ`) |
| `requestPaymentMessage` | **22** | `RequestPaymentMessage` (`C30605DSz`) |
| `declinePaymentRequestMessage` | **23** | `DeclinePaymentRequestMessage` (`C30502DPa`) |
| `cancelPaymentRequestMessage` | **24** | `CancelPaymentRequestMessage` (`DPZ`) |
| `paymentInviteMessage` | **44** | `PaymentInviteMessage` (`C30586DSg`) |
| `splitPaymentMessage` | not decoded this pass | `SplitPaymentMessage` (`DT0`), `unknown` |
| `splitPaymentUpdateMessage` | not decoded this pass | `SplitPaymentUpdateMessage` (`C30535DQh`), `unknown` |
| `paymentReminderMessage` | not decoded this pass | `PaymentReminderMessage` (`C43112IrN`), `unknown` |

The stanza-level `<message type="pay">` classifier (shared with other add-on types) is documented in `WA_MESSAGE_SECRETS.md` section on the type chooser (`AbstractC30999De0.A02`); not re-derived here.

### 2.2 SendPaymentMessage (`DSJ`, found)

| Field | Number | Type | Use |
|---|---|---|---|
| `noteMessage` | **2** | `Message` (`C30628DTw`) | the "note" attached to a payment is itself a full `Message` (normally carries only an `extendedTextMessage` or sticker) |
| `requestMessageKey` | **3** | `MessageKey` (`BD5`) | present when this send is a reply to a prior `requestPaymentMessage` |
| `background` | **4** | `PaymentBackground` (`DTJ`) | section 2.7 |
| `transactionData` | **5** | string | opaque; default value in decompiled source is a shared empty-string constant, not a real default |

Field number 1 is unused/reserved (no `FIELD_NUMBER` constant for it).

### 2.3 RequestPaymentMessage (`C30605DSz`, found)

| Field | Number | Type | Use |
|---|---|---|---|
| `currencyCodeIso4217` | **1** | string | ISO 4217 code |
| `amount1000` | **2** | int64 | amount × 1000 (fixed-point, no decimals in the wire value) |
| `requestFrom` | **3** | string | requester identifier (JID string observed in call sites) |
| `noteMessage` | **4** | `Message` | same pattern as 2.2 |
| `expiryTimestamp` | **5** | int64 | unix seconds |
| `amount` | **6** | `Money` (`C30561DRh`) | structured amount, section 2.7 |
| `background` | **7** | `PaymentBackground` (`DTJ`) | section 2.7 |

### 2.4 DeclinePaymentRequestMessage / CancelPaymentRequestMessage (found)

Both messages are minimal — a single field referencing the original request:

| Class | Field | Number | Type |
|---|---|---|---|
| `DeclinePaymentRequestMessage` (`C30502DPa`) | `key` | **1** | `MessageKey` (`BD5`) |
| `CancelPaymentRequestMessage` (`DPZ`) | `key` | **1** | `MessageKey` (`BD5`) |

**Neither message carries a reason/error code field.** Decline and cancel are protocol no-ops beyond "this request (identified by `key`) is declined/cancelled" — any reason text shown in the UI is local only, not part of the wire payload (found: no second field exists on either class; see section 12).

### 2.5 Split payments (found)

`SplitPaymentMessage` (`DT0`):

| Field | Number | Type |
|---|---|---|
| `splitId` | **1** | string |
| `totalAmount` | **2** | `Money` |
| `description` | **3** | string |
| `requesterJid` | **4** | string |
| `participants` | **5** | repeated `SplitPaymentParticipant` (`C30558DRe`) |
| `createdAtMs` | **6** | int64 |
| `contextInfo` | **17** | `MessageContextInfo`-like (`C30617DTl`) |

`SplitPaymentUpdateMessage` (`C30535DQh`): `splitId` (**1**, string), `participantJid` (**2**, string) — a per-participant status ping, no amount/status payload of its own.

### 2.6 PaymentInviteMessage / PaymentReminderMessage (found)

`PaymentInviteMessage` (`C30586DSg`): `serviceType` (**1**, int/enum — ties to the `UPI`/`PIX`/`NOVI`/`FBPAY` service codes seen in section 8), `expiryTimestamp` (**2**, int64), `incentiveEligible` (**3**, bool), `referralId` (**4**, string), `inviteType` (**5**, int/enum).

`PaymentReminderMessage` (`C43112IrN`):

| Field | Number | Type |
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

`payeeVpa` (field 6) is a **literal VPA field in the wire protocol** — direct proto-level confirmation that UPI virtual payment addresses travel inside chat messages, not just through GraphQL side-channels.

### 2.7 Supporting types (found)

| Type | Class | Fields |
|---|---|---|
| `Money` | `C30561DRh` | `value` (**1**, int64), `offset` (**2**, int32 — decimal-point offset), `currencyCode` (**3**, string) |
| `MessageKey` | `BD5` | `remoteJid` (**1**, string), `fromMe` (**2**, bool), `id` (**3**, string), `participant` (**4**, string) |
| `PaymentBackground` | `DTJ` | `id` (**1**, string), `fileLength` (**2**, int64), `width` (**3**, int32), `height` (**4**, int32), `mimetype` (**5**, string), `placeholderArgb` (**6**, int32), `textArgb` (**7**, int32), `subtextArgb` (**8**, int32), `mediaData` (**9**, `MediaData` `C30588DSi`), `type` (**10**, enum) |

### 2.8 PaymentInfo — transaction status object (found)

`DTS` ("PaymentInfo") is **not** a chat message type; it is attached to `WebMessageInfo` (`C30626DTu`, the history-sync/companion carrier documented in `WA_MESSAGE_SECRETS.md`) as `paymentInfo_` and `quotedPaymentInfo_`. It represents the current known status of a payment transaction, built from the local transaction row by `EKY.A00`:

| Field | Number | Type | Note |
|---|---|---|---|
| `currencyDeprecated` | **1** | enum | legacy |
| `amount1000` | **2** | int64 | |
| `receiverJid` | **3** | string | |
| `status` | **4** | enum | coarse status |
| `transactionTimestamp` | **5** | int64 | |
| `requestMessageKey` | **6** | `MessageKey` | |
| `expiryTimestamp` | **7** | int64 | |
| `futureproofed` | **8** | bool | set when the sender's local transaction object has no resolvable currency/amount (schema-evolution escape hatch) |
| `currency` | **9** | string | |
| `txnStatus` | **10** | enum | finer-grained status (NPCI-level), separate enum from `status` |
| `useNoviFiatFormat` | **11** | bool | legacy Meta Pay/Novi display-format flag |
| `primaryAmount` | **12** | `Money` | |
| `exchangeAmount` | **13** | `Money` | cross-currency display |

The `status`/`txnStatus` enum constant **names** are erased by the obfuscator at the javalite-bytecode level (only ordinals + `EnumVerifier` classes remain); their ordinal→label mapping is `unknown` from this pass. `EKY.A00` reads the local transaction object's currency/amount and, when absent, sets `futureproofed=true` instead of guessing — found in code (`f7fA00.A03 == 5 || !f7fA00.A0N()` guard).

---

## 3. Multi-rail client architecture ("payment-common-library")

Payment code is organized as one shared UI/infrastructure package plus one package per market rail (found, from package layout under `com.whatsapp.payments`):

| Package | Rail | Content (found) |
|---|---|---|
| `common` | shared | `p144ui` (generic payment bottom sheets, settings, transaction history, method pickers), `pin` (PIN entry UI shared across rails), `paymentkeys`, `compliance`, `care` (CSAT), `qpl` (quality/perf logging markers) |
| `indiaupi` | India UPI | onboarding, bank/VPA linking, mandates, bill payments, UPI Lite, QR, account recovery — section 4 |
| `brazilpay` | Brazil Pix | Pix key management, biometric/passkey enrollment, CPF |
| `mexico`, `indonesia` | local rails | present as packages; not explored beyond existence in this pass (`unknown` detail) |
| `upr` | rail-agnostic | `nux` (onboarding), `accountmanagement`, `bubble` (in-chat payment-options sheet), `shared` (institution/account-type pickers) — maps to the `GenUprPaymentConfig`/`GenUprPaymentConfigForViewer` GraphQL ops (section 9); "UPR" expansion not spelled out in any string found (`inferred`: "Universal/Unified Payment Rail") |
| `globalorder`, `remittances`, `split`, `paymentkey`, `productinfra`, `integrity`, `dcp`, `phoenix` | mixed | present as packages; `integrity` holds a payment "friction" bottom sheet (risk/step-up UI), `dcp` and `phoenix` had no files resolved under their top two directory levels in this pass (`unknown`) |

Cross-rail GraphQL transport is wrapped by `PaymentsMexGraphQlClient$ApiEventCallBuilder` (`com.whatsapp.payments.indiaupi.common.graphql`, despite the package name it is the shared MEX call wrapper, found) — it decorates every payment MEX call with QPL/event-logging start/success/failure callbacks (`FDA.BYz`) before delegating to the underlying `InterfaceC17070jD` transport. This is the closest match in this build to a "payment common library" at the **client** level: one obfuscated call-wrapper class, reused by India UPI's GraphQL managers (`IndiaUpiChangeMpinGraphqlManager`, `IndiaUpiCheckBalanceGraphqlManager`, `IndiaUpiEnrollIncentiveGraphqlManager`, etc. — found, same package).

Separately, India ships an embedded **third-party** library under the NPCI-owned package `org.npci.upi.security.*` (not `com.whatsapp.*`) — this is the "CL" ("Common Library") referenced by NPCI's own `.properties` assets (`version.properties`, `validation.properties`, `cl-*.properties`) and is covered in section 6. The NPCI assets' own vocabulary (`salt`, `payInfo`, `controls`, `configuration`, `trust`, `keyXmlPayload`, `keyCode`) matches the exact bundle-key strings found in this build's `CLRemoteService.Acc`/`Acf` implementations (section 6) — direct corroboration, in this build, of an earlier assets-only analysis. The literal expansion "Common Library" is still not spelled out anywhere as a string (`inferred`, now corroborated by the `CLRemoteService`/`CLResultReceiver`/`CLRemoteServiceImpl` class names themselves, which is new evidence this pass).

---

## 4. VPA / bank-account linking and UPI onboarding (India-specific)

Activity names recovered from `com.whatsapp.payments.indiaupi.*` (found, class existence and naming only — exact navigation order between them is `inferred` from naming and NOT traced via intent graphs in this pass):

| Step | Activity/Fragment |
|---|---|
| Entry / value props | `IndiaUpiPaymentsValuePropsActivity`, `IndiaUpiPaymentsValuePropsBottomSheetActivity`, `IndiaUpiPaymentsTosActivity` |
| SIM verification | `IndiaUpiSimPickerDialogFragment`, `IndiaUpiSimVerificationActivity` |
| Bank selection | `IndiaUpiBankPickerActivity` (`onboarding` package), `IndiaUpiBankAccountPickerActivity` |
| Identity/card verification | `IndiaUpiDebitCardVerificationActivity`, `IndiaUpiAadhaarCardVerificationActivity`, `IndiaUpiDobPickerActivity` |
| Device binding | `IndiaUpiDeviceBindStepActivity` (see section 6 for the crypto behind this step) |
| PIN set-up | `IndiaUpiPinPrimerDialogFragment` / `...FullSheetActivity`, `IndiaUpiPinHandlerActivity`, `IndiaUpiPinSetUpCompletedActivity`, `IndiaUpiChangePinActivity`, `IndiaUpiForgotPinDialogFragment` |
| Completion | `IndiaUpiBankAccountAddedLandingActivity`, `IndiaUpiPaymentsAccountSetupActivity` |
| Number-to-VPA mapper | `IndiaUpiMapperValuePropsActivity` → `IndiaUpiMapperLinkActivity` → `IndiaUpiMapperPendingActivity` → `IndiaUpiMapperConfirmationActivity`; `IndiaUpiCreateCustomNumberActivity` for a non-default mobile number |
| VPA contact resolution | `IndiaUpiVpaContactInfoActivity`, `IndiaUpiSendPaymentToVpaFragment` |

"Mapper" here is NPCI's own term for the phone-number↔VPA directory service; the four `mapper.register.*` activities implement that specific registration sub-flow (found: package path `indiaupi.p148ui.mapper.register`).

Linking-relevant GraphQL operations with call-site-verified variables (found, from `com.whatsapp.payments.indiaupi.common.graphql.*` and related `X/*` classes; see section 9 for the full catalog):

| Operation | doc_id | Variables (found) |
|---|---|---|
| `GetUpiBankList` | `27764018976534565` | `account_type`, `provider_type`, `request` |
| `GetUpiAccounts` | `25691302307224710` | `bank_code`, `device_id`, `provider_type`, `account_type` |
| `GetUpiToken` | `25639185495767704` | `challenge`, `device_id`, `token_type`, `provider_type` |
| `GenCreatePaymentKey` | `24662763616751127` | `add_bank`, `account_holder_name`, `display_name`, `payment_method_type`, `payment_account`, … (noisy superset, caller shared across several ops — see section 9 caveat) |
| `SetUpiChangeMpin` | `27149786891388216` | `credential_fbid`, `device_id`, `new_mpin`, `old_mpin`, `seq_no`, `upi_bank_info`, `vpa` |

---

## 5. Payment setup / onboarding (general, cross-rail)

The `upr` package implements a rail-agnostic onboarding shell: `UprOnboardingActivity` → `UprOnboardingFragment` → `UprAccountTypePickerBottomSheet` → `AddPaymentMethodFragment` / `UprInstitutionPickerBottomSheet` (found, class names only; flow order `inferred`). Account management after setup goes through `UprAccountManagementActivity`/`UprAccountManagementListFragment`, and the in-chat payment trigger surfaces via `UprPaymentOptionsBottomSheet`/`UprPaymentAccountDetailBottomSheet` ("bubble" package — the floating payment-options sheet opened from a chat).

Server-side configuration for this shell is fetched via `GenUprPaymentConfig` (doc_id `26905963415743456`) and `GenUprPaymentConfigForViewer` (doc_id `37307071662269517`) — found in the doc_id catalog, not independently call-site-verified this pass (`unknown` variables).

---

## 6. NPCI "Common Library" (CL): credential, PIN and device binding (India/UPI-specific)

### 6.1 Architecture (found)

India UPI PIN entry and bank-credential handling is delegated to an embedded, NPCI-owned Android AIDL service, entirely separate from WhatsApp's own `com.whatsapp.*` code:

```
org.npci.upi.security.services.CLRemoteService      <- AIDL interface
org.npci.upi.security.services.CLResultReceiver     <- AIDL callback interface
org.npci.upi.security.pinactivitycomponent.CLRemoteServiceImpl  <- Android Service, binds the AIDL
org.npci.upi.security.pinactivitycomponent.BinderC48420LDc      <- Binder implementation of CLRemoteService
org.npci.upi.security.pinactivitycomponent.GetCredential        <- PIN-entry Activity launched by the binder
org.npci.upi.security.pinactivitycomponent.Keypad               <- on-screen keypad widget
```

`CLRemoteService` methods (found, interface signatures): `AQR(otpResultJson)`, `AZO(mode, nonce)` (device-binding challenge/response, section 6.2), `Acc(...)`/`Acf(...)` (launch the PIN activity with a credential bundle), `BBj(...)` (balance read), `BVz/CRh/CRi(...)` (device-cert / state validation), `BW1()` (device integrity check).

### 6.2 Device binding and credential exchange (found)

`BinderC48420LDc.AZO(mode, nonce)`:
- "initial" mode: builds `deviceId|randomHex|nonce`, RSA-encrypts it against a bundled NPCI certificate (`MYU.A00`), base64-encodes, returns `"2.3-v1.8|" + ciphertext`. The `2.3-v1.8` prefix is a hardcoded CL protocol-version tag (found literal).
- subsequent mode: derives an AES key from the stored credential record, AES/GCM-encrypts the same `deviceId|randomHex|nonce` triple with a fresh random IV, returns `ciphertext|iv` under the same version prefix.

`BinderC48420LDc.Acc`/`Acf` build a `Bundle` with keys `keyCode`, `keyXmlPayload`, `controls`, `configuration`, `salt`, `payInfo`, `trust`, `languagePref` and start the `GetCredential` activity with it (found, literal string keys) — this is the exact vocabulary an earlier assets-only analysis of `version.properties`/`validation.properties` inferred the "CL" scheme would use (`salt`, `payInfo`); this build's code confirms those are real runtime bundle keys, not just asset-file placeholders.

`C51962N8y` (crypto helper used throughout the binder):
- `A00`: generates an **RSA-2048 keypair inside the Android KeyStore**, `CN=NPCI_CERT`, SHA-512/PSS, requires secure hardware (`isInsideSecureHardware()`, throws otherwise) and (SDK-dependent) user authentication within a short validity window — this is the device-binding key.
- `A03`/`A04`: AES/GCM-NoPadding, 128-bit tag, explicit caller-supplied key and IV — session-level encrypt/decrypt.
- `A02`: SHA-256 digest (challenge hashing).
- `A01`: decrypts a `ciphertext|iv`-shaped string using a stored AES key — paired with `AZO`'s output format above.

`BinderC48420LDc.BW1()` runs a root/tamper check (build tags, common `su` binary paths, `which su` probe) **and** verifies the RSA key just generated is StrongBox/TEE-backed; a failed check causes `BW1()` to return `false`, which gates the credential-issuance path upstream (found: boolean return consumed by `CRh`/`CRi` logic paths, not independently traced to a UI message).

### 6.3 What this means for message content

The UPI MPIN itself never appears in a chat message or in this report's section-2 proto fields — it is handled entirely inside the `GetCredential` activity and exchanged with the issuer bank/NPCI switch through the RSA/AES layer above, producing an opaque *credential blob* that is what eventually reaches GraphQL variables such as `new_mpin`/`old_mpin`/`mpin` in `SetUpiChangeMpin`/`CheckUpiBalance` (section 9). That the string a GraphQL variable actually carries is already NPCI-encrypted (rather than client-plaintext protected only by TLS) is **inferred** from the purpose of the CL flow that precedes the call, not independently confirmed by reading the GraphQL call site's byte content.

---

## 7. Encryption layering: chat E2E vs NPCI credential blob

Two independent encryption layers are involved in a payment, and they must not be confused (section 13):

| Layer | Protects | Mechanism | Evidence |
|---|---|---|---|
| Chat message E2E | the whole `Message` proto, including every field in section 2 (amount, note, VPA in `payeeVpa`, JIDs, `MessageKey` references) | WhatsApp's standard Signal-protocol/Noise session encryption — out of scope for this report, see other RE reports for that layer | not re-derived here |
| NPCI credential/device-binding blob | MPIN, device-binding challenge/response, risk-check payloads exchanged with the issuer bank via NPCI | RSA-2048 (KeyStore, TEE-bound, `CN=NPCI_CERT`) for device binding; AES/GCM-128 with explicit IV for session data; SHA-256 for challenge hashing | section 6.2, found |

The second layer is **India/UPI-specific** and runs underneath / before the GraphQL call, never inside the chat `Message` proto. There is no payment-specific AES/RSA layer found for Brazil Pix or Mexico in this pass (`unknown` — not explored).

---

## 8. Transaction status sync

### 8.1 Local object and history sync (found)

`F7F` is the in-memory/local payment-transaction object (fetched via `D8X.A00(c13g)` from the generic message row `C13G`). `EKY.A00` converts it into the wire-level `PaymentInfo` (`DTS`, section 2.8) attached to `WebMessageInfo.paymentInfo_`/`quotedPaymentInfo_` for history-sync/companion export.

### 8.2 Server-pushed status updates (found, `C24410wL` "PaymentsMessageHandler")

The client-facing push channel is a `<notification>` stanza with a `type` attribute dispatched by `PaymentsMessageHandler.A0A`. Observed `type` values and their handling:

| `type` | Handling |
|---|---|
| `pay` (with `hash`) | base64 hash decoded, queued as a side-list USync refresh (`EnumC21760rz.A0Q`, `C21820s6.A0N` protocol set) — reuses the USync mechanism documented in `WA_USYNC.md` rather than carrying the status itself |
| `transaction` | parses the transaction via `C24880x6.A07`, logs `onPaymentTransactionStatusUpdate`, updates the local `F7F`, surfaces a transaction error string to any attached UI (`InterfaceC35566Fb1.BIp`), and (gated by flags **1746** + **5049**) can build an order-summary "custom item" card for a post-payment education nudge |
| `upi` | `consumer_status{value,dhash}` → `onPaymentConsumerStatusUpdate` (India-specific consumer-eligibility ping, distinct from transaction status) |
| `fbpay` | legacy Meta Pay eligibility ping, same handler path as `upi` with a different offer-map key |
| `account-recovery` | `service=UPI` or `service=BR`; drives the India/Brazil account-recovery flows, gated by flags **1644**/**2000** |
| `alert`, `step_up`, `merchant_status`, `merchant-update`, `account`, `kyc-state`, `invite`, `alias`, `age_verification_update`, `document_verification_status` | assorted UI nudges/compliance updates, not transaction status |

### 8.3 Sync bookkeeping (found, preference-key strings)

`payments_all_transactions_last_sync_time`, `payments_block_list_last_sync_time`, `payments_error_map_last_sync_time_millis` — periodic full-list and error-map syncs exist (consumer classes not fully traced this pass; `unknown` cadence).

---

## 9. GraphQL / MEX payment operations

### 9.1 Two transports, two schemas (found)

| Schema | Transport | Count (this build) |
|---|---|---|
| `whatsapp` (`www` catalog) | persisted-doc_id GraphQL POST, transport mechanism itself `inferred` (not traced to an HTTP/IQ call site in this pass) | 81 payment-tagged operations |
| `whatsapp_mex` (`mex` catalog) | `w:mex` IQ over the existing stanza connection (`xmlns="w:mex"`) | 1 payment-tagged operation: `PaymentsIsAccountRecoverable` (doc_id `27351347491148282`) |

Source: `assets/whatsapp-android-www_client_persist_ids.json` and `assets/whatsapp-android-mex_client_persist_ids.json`, both first-party declarative assets read at runtime (found, strongest tier short of a traffic capture — the doc_id values themselves are not "tested", only confirmed present in the shipped asset).

### 9.2 Representative operations with call-site-verified variables (found)

| Operation | doc_id | Type | Variables |
|---|---|---|---|
| `GetUpiAccounts` | `25691302307224710` | Query | `bank_code`, `device_id`, `provider_type`, `account_type` |
| `CheckUpiBalance` | `37205951525662520` | Query | `credential_fbid`, `device_id`, `mpin`, `seq_no`, `upi_bank_info`, `vpa`, `cl_version`, `device_ssid`, `request` |
| `SetUpiChangeMpin` | `27149786891388216` | Mutation | `credential_fbid`, `device_id`, `new_mpin`, `old_mpin`, `seq_no`, `upi_bank_info`, `vpa` |
| `GetUpiBankList` | `27764018976534565` | Query | `account_type`, `provider_type`, `request` |
| `GetUpiToken` | `25639185495767704` | Query | `challenge`, `device_id`, `token_type`, `provider_type` |
| `UpiCreateMandate` / `UpiAcceptMandate` | `26775212245448044` / `26786867597629452` | Mutation | shared caller (`C42562IuV`): `frequency_rule`, `mandate_no`, `purpose_code`, `recurrence_day`, `recurring_rule`, `ref_id`, `device_id`, `top_up_amount`, `provider_type`, `upi_banks`, `is_revocable`, … |
| `CreateEnrollment` | `34570903025891763` | Mutation | `participant_id`, `device_id` |
| `GenRaisePaymentComplaint` | `27569318002686860` | Query | `complaint_type`, `reason`, `transaction_ref_id`, `user_description` |
| `PaymentsIsAccountRecoverable` (MEX) | `27351347491148282` | Query | none found (likely `{}`) |

`CheckUpiBalance`'s presence of an `mpin` variable, read next to `cl_version`, is consistent with section 6.3: the variable name alone does not prove the content is pre-encrypted, but it travels alongside an explicit CL protocol-version string, which only makes sense if the value originated from the CL exchange.

**Caveat (found as a limitation, not a finding about WhatsApp):** `GenCreatePaymentKey`, `RevokeEnrollment`, and `BrSaveCPF` all resolve to the *same* shared caller classes (`C42325Iq9`/`C42327IqB`, `RunnableC42211IoJ`) in the source catalog, which returns every string literal near that caller as "variables" for all three ops — this over-collects (e.g. Pix-specific fields like `pix_key` show up under a UPI-named op). Treat the long variable lists for those three specific operations as a noisy superset, not a confirmed per-operation schema.

The remaining operations in the 81-entry catalog (full list: `UpiPauseMandate`, `UpiResumeMandate`, `UpiRevokeMandate`, `UpiRejectMandate`, `UpiExecuteMandate`, `GetUpiLiteDetails`, `GetUpiP2mConfig`, `GetUpiPurposeLimitingKey`, `GetUpiSmsContentAndVmn`, `PaymentReminderCreate/Get/Cancel/Stop`, `GetBillReceipt`, `GetBillerPlans`, Brazil Pix (`GetPixInfo`, `GetPixBankList`, `GetMerchantPixInfo`, `CompletePixTransaction`, `GenPayWithPixPrecheck`), biometric/passkey (`Br*Passkey*`, `BrAuthorizeBiometricPayment`), and the `Wamo*` subscription/promo ops) are catalogued with their doc_ids but were not individually re-verified against a call site in this pass — treat their presence as `found` (they are literal entries in the 2.26.41.6 asset) and their exact request shape as `unknown` unless listed above.

---

## 10. NPCI OTP auto-read rules (India/UPI-specific)

`assets/npci/npci_otp_rules.json` (found, 5 rules) is consumed by `org.npci.upi.security.pinactivitycomponent.C0315u` to auto-extract a 6-digit OTP from an incoming bank/NPCI SMS during a UPI flow, purely as typing convenience — it does not generate, validate, or transmit the OTP. All 5 rules share `sender: ["[a-zA-Z]+"]` (alphabetic short-code) and `otp: "\d{6}"`; only the trigger phrase differs (`"is your OTP"`, `"OTP is"`, `"one time password is"`, `"is your one time password"`, `".*OTP for Aadhaar.*"`). The caller can override the OTP digit-count regex at runtime (`\d{` + `i` + `}`) when it passes a non-zero length. A body containing `"Aadhaar"`/`"AADHAAR"` is cached under SharedPreferences key `otp_type_aadhaar`, otherwise `otp_type_bank`.

This asset and consumer class are unchanged in kind from a prior `2.26.34.4` analysis; not independently re-diffed byte-for-byte against 2.26.41.6 in this pass (`inferred` continuity, not re-verified).

---

## 11. Feature flags

AB-prop ids as read directly in `PaymentsMessageHandler` (`C24410wL`, found call sites) unless noted. No numeric flag ids were found gating the section-2 proto fields themselves (those are unconditional on the wire); all flags found this pass gate *handling* of server pushes or UI nudges.

| Flag | Controls |
|---|---|
| **1458** | removes a locally cached UPI payment alias once the server reports it `deregistered` |
| **1644** | UPI account-recovery eligibility (`payments-enabled:account-recovery-enabled`) |
| **2000** | Brazil Pix account-recovery eligibility (equivalent gate for `service=BR`) |
| **1746** + **5049** (both required) | post-transaction "custom item"/order-summary education card shown after a completed payment (BIP education nudge) |
| **12214** | create-FB-user path during UPI account recovery (vs. direct recovery call) |
| **423** | payments invite-used tracking, older path |
| **544** | payments invite-used tracking, additional path (checked together with 423 via OR) |
| **20869** | PSP allow-list check during account-recovery notification handling; paired string pref `32353` (comma-separated opted-in PSP list, read via a string-valued AB prop, not a numeric flag) |

No feature-flag IDs were found specifically gating the India-UPI onboarding activity sequence (section 4) or the NPCI CL device-binding path (section 6) in this pass — `unknown`, not traced beyond the handler class above.

---

## 12. Error / decline reason codes

### 12.1 In-protocol decline/cancel (found)

As established in section 2.4, `declinePaymentRequestMessage`/`cancelPaymentRequestMessage` carry **only** a `MessageKey` reference to the original request — no reason enum, no free-text field. A client showing "declined: insufficient funds" or similar is doing so from **local** state (the sender's own UI copy, or a correlated later `transaction`/`PaymentInfo` status, section 8), not from anything the decline/cancel message itself transmits.

### 12.2 PaymentInfo status fields (found existence, unknown mapping)

`DTS.status_` (field 4) and `DTS.txnStatus_` (field 10) are separate enum-typed fields (section 2.8). Their ordinal→label mapping could not be recovered from the javalite bytecode alone (enum constant names are erased by the build's obfuscation of the `Internal.EnumVerifier` classes) — `unknown`. `futureproofed` (field 8, bool) is a deliberate escape hatch set when the sender's local object has no resolvable amount/currency, letting a receiver on a newer client render a status it otherwise couldn't parse.

### 12.3 Server-pushed error map (found pref keys, consumer not fully traced)

Preference keys `payments_error_code`, `payments_error_text`, `payments_error_title`, `payments_error_map_tag`, `payments_error_map_last_sync_time_millis` indicate error codes are resolved against a **server-synced map** (code → title/text), not a fixed client-side enum or string table. This means decline/error *text* shown to a user can change over time/region without an app update. The class that performs this sync was not identified in this pass (`unknown`).

### 12.4 NPCI CL layer failures (found, no structured code)

`BinderC48420LDc.BW1()` (device-integrity check), `CRH`/`CRh`/`CRi` (device-cert/state validation) all fail **silently** — they return `false`/throw, with no error code surfaced across the AIDL boundary beyond the boolean. Any user-visible message for a CL-layer failure is therefore constructed entirely on the WhatsApp side from the boolean result, not from an NPCI-supplied code (`inferred`, consistent with the AIDL interface shape in section 6.1 having no error-code-return methods).

---

## 13. India/UPI-specific vs general — explicit split

| Finding | Scope |
|---|---|
| `sendPaymentMessage`/`requestPaymentMessage`/`declinePaymentRequestMessage`/`cancelPaymentRequestMessage`/split payment/`PaymentInviteMessage`/`PaymentReminderMessage` proto fields (section 2) | **general** — same `Message` proto fields regardless of rail; `payeeVpa` (section 2.6) is the one field name that is UPI-flavored but the field itself is unconditionally present in the schema |
| `PaymentInfo` (`DTS`) transaction-status object (section 2.8, 8) | **general** structure; `useNoviFiatFormat` and the legacy `FBPAY`/`NOVI`/`PIX`/`UPI` service codes show the same object/notification path is shared across all rails |
| Rail packages `indiaupi`, `brazilpay`, `mexico`, `indonesia`, `upr` (section 3) | split explicitly by package; `upr`/`common` are rail-agnostic, the rest are single-country |
| VPA linking, UPI mapper flow, onboarding activities (section 4) | **India/UPI-only** |
| NPCI "CL" credential/device-binding library, RSA/AES crypto, OTP auto-read (sections 6, 7, 10) | **India/UPI-only** — this entire layer is absent for Pix/Mexico/Indonesia in the code explored |
| GraphQL doc_id catalog (section 9) | mixed — catalog itself spans UPI, Pix, biometric/passkey (Brazil), and rail-agnostic (`Wamo*`, `Gen*`) operations under one schema; each op's own scope follows its name/prefix (`Br*` = Brazil, `Upi*`/`GetUpi*`/`SetUpi*` = India) |
| `PaymentsMessageHandler` notification types (section 8.2) | mixed — `pay`/`transaction`/`alert`/`step_up`/`account` style types are generic; `upi` type and `service=UPI` branches are India-specific, `service=BR` branches are Brazil-specific |

---

## 14. Baileys note

Baileys-style clients can construct and parse the section-2 message types (they are plain protobuf fields on the standard `Message`), and can in principle call the `whatsapp`/`whatsapp_mex` GraphQL doc_ids with hand-built variables. They **cannot** meaningfully complete a UPI payment: the MPIN/device-binding exchange in section 6 runs through an embedded, NPCI-signed native Android component bound to a real bank/NPCI backend trust relationship (TEE-backed RSA key, `CN=NPCI_CERT`) that has no equivalent outside the official app. A Baileys `sendPaymentMessage` is therefore a protocol-correct but functionally inert message unless paired with a transaction that was actually authorized through the real NPCI flow.

---

## 15. Error cases / gotchas

| Symptom | Cause | Fix / note |
|---|---|---|
| Decline/cancel message has no visible reason on the wire | protocol design (section 2.4) — only a `MessageKey` back-reference exists | do not expect a reason code from the message itself; correlate with a later `transaction` notification or local state |
| `BW1()`-gated credential operation fails with no error text | device lacks StrongBox/TEE, or is rooted | surfaced only as a boolean failure to the WhatsApp side; cannot be distinguished from other CL failures without additional logging |
| `mpin`/`new_mpin`/`old_mpin` GraphQL variables look like plaintext in a decompiled call-site dump | they are produced by the CL exchange (section 6.3), not typed directly into the GraphQL call | do not assume plaintext PIN transmission without tracing the actual bytes at runtime — this report does not claim to have done so |
| `GenCreatePaymentKey`/`RevokeEnrollment`/`BrSaveCPF` show enormous, Pix-flavored variable lists | shared caller class over-collection in the doc_id catalog extraction (section 9.2) | treat as noisy, verify per-field before relying on it |
| `txnStatus`/`status` enum values can't be named | obfuscated `EnumVerifier` erases constant names | requires runtime string correlation (UI resource strings mapped to ordinals), not done in this pass |

---

## 16. Key distinctions

| Do not confuse | Detail |
|---|---|
| chat-message E2E vs NPCI credential blob (section 7) | two separate crypto layers; the second is India/UPI-only and sits entirely outside the `Message` proto |
| `DTS` PaymentInfo vs the four chat payment message types | `DTS` is a history-sync/status object (`WebMessageInfo.paymentInfo_`), never a standalone sendable chat message |
| `status` vs `txnStatus` on `DTS` | two independent enums, different granularity, both opaque at the ordinal level in this build |
| `www`/`whatsapp` schema vs `mex`/`whatsapp_mex` schema doc_ids | different transport (persisted-doc_id GraphQL POST vs `w:mex` IQ); almost all payment ops are on the `www`/`whatsapp` side in this build |
| "UPR" rail-agnostic onboarding vs India UPI onboarding | UPR (`com.whatsapp.payments.upr`) is a newer, generic shell; the India-specific `indiaupi` onboarding activities (section 4) are a separate, older, much larger flow still present side-by-side in 2.26.41.6 |
| NPCI "Common Library" (`org.npci.upi.*`) vs WhatsApp's own `com.whatsapp.payments.*` code | the former is a third-party embedded component with its own AIDL surface; WhatsApp code only launches it and reads back an opaque string/bundle |

---

## 17. Complete flow (India UPI, send-money case)

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

## 18. Unknowns

| Topic | Reason |
|---|---|
| Top-level `Message` field numbers for `splitPaymentMessage`, `splitPaymentUpdateMessage`, `paymentReminderMessage` | info-string decode not carried far enough in this pass; the sub-message's own fields (section 2.5/2.6) are unaffected |
| `DTS.status_`/`txnStatus_` enum label mapping | obfuscated `EnumVerifier`, constant names erased |
| Exact transport mechanism for `whatsapp`-schema (`www`) persisted-doc_id GraphQL calls | not traced to an HTTP/IQ call site in this pass; marked `inferred` throughout |
| Consumer class(es) for the `payments_error_map_*` server-synced error map | pref keys found, reading/writing class not identified |
| `mexico`/`indonesia`/`dcp`/`phoenix` package contents | package existence confirmed, contents not explored |
| Whether GraphQL `mpin`/`new_mpin`/`old_mpin` variables carry an already-NPCI-encrypted blob or additional protection is applied only at TLS level | inferred from CL flow purpose, not confirmed by inspecting actual runtime byte content |
| Feature-flag IDs (if any) gating the India-UPI onboarding sequence or the CL device-binding path itself | none found in the classes explored |
| Byte-for-byte continuity of `npci_otp_rules.json` and the `.properties` CL assets between `2.26.34.4` (a prior analysis) and `2.26.41.6` | not re-diffed; the consuming classes and runtime bundle-key vocabulary were independently re-confirmed in 2.26.41.6, the asset bytes themselves were not |
| Actual traffic / live transaction behavior | static analysis only, no traffic capture, no live transaction performed |
