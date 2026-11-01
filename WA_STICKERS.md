# WhatsApp Stickers — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-11-01
**Scope:** `Message.StickerMessage` proto (image/Lottie metadata, avatar/AI/premium flags, `emojis`, `accessibilityLabel`), embedded sound stickers (`StickerMessage.audioMessage`), `lottieStickerMessage` / `audioStickerMessage` generic wrappers, `stickerPackMessage` (pack sharing), sticker pack local storage and the `.was`/Lottie ZIP format, `stickerSyncRmrMessage` (confirmed absent), third-party sticker pack intents and content-provider contract, built-in AI sticker generation provider, local sticker search, feature flags; media crypto is not repeated (see [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md))

---

## 1. Overview

A "sticker" on Android is one of several wire message types plus a large first-party app subsystem (store, local recents, search, AI generation) and a public third-party integration surface (intents + content providers). All media bytes (sticker image, pack ZIP, thumbnails) travel through the same encrypted media pipeline as any other attachment — see [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) section 3 for the `MmsType` rows (`sticker`, `sticker-pack`, `thumbnail-sticker-pack`, `newsletter-sticker`, `newsletter-sticker-pack`).

| Entity | `Message` field | Wire type | Role |
|--------|------------------|-----------|------|
| Single sticker | `stickerMessage` | **26**, `StickerMessage` (`C30611DTf`) | one sticker image/animation sent in a chat |
| Sound sticker (embedded) | `StickerMessage.audioMessage` | **26** of `StickerMessage`, `oneof audio` → `AudioMessage` | a short voice clip attached to a sticker send |
| Lottie wrapper | `lottieStickerMessage` | **74**, `FutureProofMessage` (`BD2`) | generic envelope, name implies a Lottie-specific payload; nested content unresolved |
| Audio-sticker wrapper | `audioStickerMessage` | **134**, `FutureProofMessage` (`BD2`) | same generic envelope pattern, new in this build; nested content unresolved |
| Sticker pack | `stickerPackMessage` | **86**, `StickerPackMessage` (`C30610DTe`) | shares/installs a pack (ZIP of stickers) |
| Sticker-sync request | `stickerSyncRmrMessage` | **47** (older builds) | **absent** from the `Message` proto in 2.26.41.6 (see section 7) |
| Status sticker reaction | `statusStickerInteractionMessage` | **110**, `StatusStickerInteractionMessage` (`C30560DRg`) | reaction sticker on a status post; out of scope here beyond this pointer |
| Third-party add-pack | Android `Intent` | `com.whatsapp.intent.action.ENABLE_STICKER_PACK` | external app asks WhatsApp to import a pack it hosts |
| Third-party send | Android `Intent` | `com.whatsapp.intent.action.SEND_STICKER` | external app hands a single WebP sticker to WhatsApp's picker |
| Pack content contract | `ContentProvider` (external app's own) | `content://<authority>/metadata`, `/stickers`, `/stickers_asset` | how WhatsApp reads a third-party pack |
| AI sticker generation | `ContentProvider` (WhatsApp's own) | `content://com.whatsapp.provider.sticker_command/generate` | in-app GenAI sticker creation, consumed via content-provider calls, not a chat message |

Tiers follow `IMPORTANT.md`: **found** = read directly in decompiled code/strings/manifest, **inferred** = deduced from code shape, **unknown** = not resolved. All evidence here is static (decompiled APK + manifest); nothing was captured on the wire.

---

## 2. `Message.StickerMessage` (field 26)

### 2.1 Fields (found, `C30611DTf`)

| Field | # | Type | Use |
|-------|---|------|-----|
| `url` | 1 | string | legacy full URL |
| `fileSha256` | 2 | bytes | plaintext hash |
| `fileEncSha256` | 3 | bytes | ciphertext+MAC hash, also the upload path hash |
| `mediaKey` | 4 | bytes | 32-byte key, HKDF info `WhatsApp Image Keys` (media pipeline, not repeated here) |
| `mimetype` | 5 | string | `image/webp` for ordinary stickers |
| `height` / `width` | 6 / 7 | uint32 | pixel dimensions |
| `directPath` | 8 | string | download path |
| `fileLength` | 9 | uint64 | ciphertext length |
| `mediaKeyTimestamp` | 10 | int64 | seconds |
| `firstFrameLength` / `firstFrameSidecar` | 11 / 12 | uint32 / bytes | sidecar for the first animation frame (see [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) section 7) |
| `isAnimated` | 13 | bool | animated WebP |
| `pngThumbnail` | 16 | bytes | inline thumbnail |
| `contextInfo` | 17 | `ContextInfo` | quote/reply/ad metadata |
| `stickerSentTs` | 18 | int64 | send timestamp |
| `isAvatar` | 19 | bool | avatar sticker |
| `isAiSticker` | 20 | bool | AI-generated sticker |
| `isLottie` | 21 | bool | the sticker payload is a Lottie animation, not a plain WebP (see section 4) |
| `accessibilityLabel` | 22 | string | screen-reader text |
| `premium` | 24 | int32 | unresolved (no consumer found) |
| `emojis` | 25 | string | **found use**: local search tag, see section 9 |
| `audioMessage` | 26 | `AudioMessage` (`oneof audio`) | embedded sound-sticker clip, see section 3 |

Field-number gaps 14, 15, 23: no defined field; prior use unknown. This corrects the starting `Messages/stickerMessage` note, which lists `emojis` (25) as the last field and does not carry field 26 (`audioMessage`) at all — confirmed present in `C30611DTf` in 2.26.41.6 (`AUDIO_MESSAGE_FIELD_NUMBER = 26`) and matches the `oneof audio` block in the current `baron-baileys-v2` proto.

### 2.2 Message-type-string classification (found)

Observed type strings tied to a `StickerMessage`/`StickerPackMessage` send, collected from analytics dispatch (`C21880sC`) and the sticker-type helper: `sticker`, `avatar_sticker`, `genai_sticker`, `1p_sticker`, `user_created_sticker`, `sticker_pack`. `avatar_sticker` and `genai_sticker` come from `isAvatar`/`isAiSticker`; `1p_sticker` and `user_created_sticker` line up with the `StickerPackOrigin` enum (section 5) but the exact decision function that picks between `sticker`, `1p_sticker` and `user_created_sticker` was not isolated in this pass (unknown precedence). Baileys (`messages-send.js`) checks `isLottie` before `isAvatar` when deriving this string client-side; whether Android does the same was not confirmed.

### 2.3 `emojis` and `accessibilityLabel` (found, upgraded from the starting material)

- `emojis` (25): consumed by `EmojiGroupMapper`/`StickerSearchManager` as the local search tag string — confirms its purpose beyond the field name (section 9). Not server-queried.
- `accessibilityLabel` on a *sent sticker* and `sticker_accessibility_text` on a *third-party pack sticker* (`StickerContentProviderFetcher`, section 8) both cap at **125** characters for a static sticker and **250** for an animated one (`ThirdPartyStickerFetcher`, literal ints 125/250; JADX mis-displays the 125 branch as an unrelated field `C30628DTw.SPLIT_PAYMENT_MESSAGE_FIELD_NUMBER` because that field happens to also hold the value 125 — a decompiler naming artifact, the numeric value itself is read directly from bytecode).

---

## 3. Sound stickers: `StickerMessage.audioMessage` and `audioStickerMessage` (134)

Two distinct, found mechanisms, do not conflate them:

| Mechanism | Field | Evidence |
|-----------|-------|----------|
| Embedded clip | `StickerMessage.audioMessage` (26, `oneof audio`) | present in `C30611DTf`; matches `baron-baileys-v2`'s `WAProto.proto` exactly (`oneof audio { Message.AudioMessage audioMessage = 26; }`) |
| Standalone wrapper | `Message.audioStickerMessage` (134, `FutureProofMessage`/`BD2`) | new field in `C30628DTw` for 2.26.41.6, not present in the `Messages/` starting material; same generic-envelope pattern as `lottieStickerMessage` (section 1), nested content unknown |

Client support package `com.whatsapp.stickers.sound` confirms a "sound sticker" authoring feature: `StickerOpusEncoder` (`nativeEncode(short[] pcm, String outPath)`, native Opus encode of a recorded clip) and `SoundStickerAudioDownloader` (ensures the attached audio is fetched before playback, routes through the ordinary media pipeline). This is consistent with embedding a short voice note via field 26 rather than (or alongside) the newer field-134 wrapper.

---

## 4. Sticker file formats

### 4.1 Plain and animated WebP (found)

`mimetype = image/webp`; `isAnimated` flags an animated WebP. Decode goes through `libstatic-webp.so`'s sandboxed libwebp (see [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) section 15).

### 4.2 Lottie stickers — `.was` ZIP container (found, `LottieStickerZipEntrySaver` / `C161836tL`)

When `isLottie` is set, the sticker's media file is not a WebP: it is a ZIP archive, saved and read through a `LottieStickerZipEntrySaver`, that must contain:

| Entry | Role |
|-------|------|
| `animation/animation.json` | the Lottie (bodymovin) JSON animation, primary |
| `animation/animation.json.trust_token` | companion trust/signature token for the JSON |
| `animation/animation_secondary.json` + `.trust_token` | optional secondary animation variant |

A generic pack-level extractor (`C161826tK`, log tag `StickerPackZipEntrySaver`, base class name `SafeZipEntrySaver`) additionally allow-lists extracted file extensions to `png`, `webp`, and `was` — i.e. the public `.was` ("WhatsApp Animated Sticker") file extension is the on-disk/ZIP-entry marker for this Lottie container, checked against claimed MIME (`application/was`) via a content sniffer before acceptance.

### 4.3 Pack ZIP extraction limits (found, `C161826tK` constructor)

| Limit | Value |
|-------|-------|
| Max entries per pack ZIP | **65** (hard-coded) |
| Max bytes per entry | dictionary token (flag id **1900**, KB) × 1024 |
| Max total bytes per pack | same token × 1024 × 65 |
| Path traversal | each entry's target path is canonicalized and must resolve inside the pack's own directory ("Zip entry is attempting to save outside of current directory") before any byte is written — zip-slip guard |
| Rejected entry | deleted after a failed content-type sniff, logged `StickerPackZipEntrySaver/file in zip is not valid` |

This corroborates and extends the `Messages/stickerPackMessage` starting note (which cited "ZIP extraction and file validation" and "validates sticker files reside within extracted ZIP boundaries" from 2.26.34.4 only as a log-reference, without the limits).

---

## 5. `Message.StickerPackMessage` (field 86)

### 5.1 Fields (found, `C30610DTe`) — matches the starting material and `baron-baileys-v2` exactly

| Field | # | Type |
|-------|---|------|
| `stickerPackId` | 1 | string |
| `name` | 2 | string |
| `publisher` | 3 | string |
| `stickers` | 4 | repeated `Sticker` |
| `fileLength` / `fileSha256` / `fileEncSha256` / `mediaKey` / `directPath` / `mediaKeyTimestamp` | 5, 6, 7, 8, 9, 13 | pack ZIP media reference (`MmsType` `sticker-pack`, HKDF info `WhatsApp Sticker Pack Keys`) |
| `caption` | 10 | string |
| `contextInfo` | 11 | `ContextInfo` |
| `packDescription` | 12 | string |
| `trayIconFileName` | 14 | string |
| `thumbnailDirectPath` / `thumbnailSha256` / `thumbnailEncSha256` / `thumbnailHeight` / `thumbnailWidth` | 15–19 | pack thumbnail (`MmsType` `thumbnail-sticker-pack`) |
| `imageDataHash` | 20 | string |
| `stickerPackSize` | 21 | uint64 |
| `stickerPackOrigin` | 22 | enum `StickerPackOrigin` |

Nested `Sticker`: `fileName` (1), `isAnimated` (2), `emojis` (3, repeated), `accessibilityLabel` (4), `isLottie` (5), `mimetype` (6), `premium` (7).

`StickerPackOrigin`: `FIRST_PARTY` = 0, `THIRD_PARTY` = 1, `USER_CREATED` = 2.

### 5.2 Local storage (found, `AbstractC149676Ty.java`, `C1888782f.java`, `C0R5.java`)

| Table | Columns |
|-------|---------|
| `message_sticker_pack` | `message_row_id`, `sticker_pack_id`, `pack_name`, `pack_description`, `publisher`, `tray_icon_file_name`, `image_data_hash`, `sticker_pack_size`, `sticker_pack_origin`; indexed on `pack_name` and `publisher` |
| `message_sticker_pack_stickers` | `_id`, `message_row_id`, `file_name`, `is_animated`, `emojis`, `accessibility_label`, `is_lottie`, `mimetype` |

This replaces the starting material's version-2.26.34.4 pointer (`StickerPackMessageMapper` / `message_sticker_pack`, cited only by log string) with the concrete 2.26.41.6 column list.

---

## 6. `stickerSyncRmrMessage` — confirmed absent in 2.26.41.6

Field 47 (`StickerSyncRMRMessage`: `filehash` repeated string, `rmrSource` string, `requestTimestamp` int64) does **not** appear in `C30628DTw` (the `Message` container) for 2.26.41.6: no field number 47 maps to it, and no class or string containing `StickerSyncRMR`/`stickerSyncRmr` exists anywhere in the decompiled tree. This matches and extends the starting material's own observation that the field was already absent in 2.26.36.1 — it remains absent five builds later. Per the evidence contract this is an **observed absence**, not a confirmed removal: whether it was renamed, moved to a different proto, or dropped outright is unknown.

A `filehash`-keyed table still exists, but for an unrelated purpose: `RecentStickerDBStorage` (`C6VB`, `C17460jr`, `C6V8`) tracks locally-sent/received stickers by file hash for the recents tray — this is local bookkeeping, not the wire sync message, and must not be confused with it.

---

## 7. Third-party sticker pack API

This is a public, documented-by-convention integration surface (`com.whatsapp.sticker.READ` permission family); all of the following is found in `AndroidManifest.xml` and the backing classes.

### 7.1 Manifest surface

| Component | Declaration |
|-----------|-------------|
| Permission | `com.whatsapp.sticker.READ` — required `android:readPermission` on a third-party app's own content provider before WhatsApp will query it |
| Add-pack activity | `com.whatsapp.stickers.ui.thirdpartystickers.AddThirdPartyStickerPackActivity`, `exported="true"`, intent-filter `action com.whatsapp.intent.action.ENABLE_STICKER_PACK` + `category DEFAULT` |
| Add-pack legacy alias | `activity-alias` `com.whatsapp.stickers.thirdpartystickers.AddThirdPartyStickerPackActivity` → same target (kept for apps built against the pre-refactor package name) |
| Send-single-sticker activity | `com.whatsapp.stickers.command.send.SendStickerCommandActivity`, `exported="true"`, intent-filter `action com.whatsapp.intent.action.SEND_STICKER` + `category DEFAULT` + `data mimeType="image/webp"` |
| Whitelist-check provider | `com.whatsapp.provider.sticker_whitelist_check` → `WhitelistPackQueryContentProvider`, `exported="true"` |
| Deep link | `whatsapp://stickerpack` (`<data android:host="stickerpack" android:scheme="whatsapp"/>`); target activity/routing for this specific host not isolated in this pass (unknown) |

### 7.2 `ENABLE_STICKER_PACK` intent contract (found, `AddThirdPartyStickerPackActivity`)

Request extras (`String`): `sticker_pack_id`, `sticker_pack_authority`, `sticker_pack_name`.

Validation before anything is fetched:
1. `getCallingActivity()` must be non-null (the intent must come from `startActivityForResult`, not a bare broadcast-style launch).
2. `PackageManager.resolveContentProvider(sticker_pack_authority, …)` must resolve to a provider.
3. The resolved provider's package must equal the calling activity's package — **an app can only vouch for authorities it itself owns**.

Result extras on the returned `Intent` (one of): `add_successful=true`, `already_added=true`, `validation_error=<string>`, or `CancelReason.USER_CANCELLED=true` (user dismissed the add dialog).

### 7.3 Pack content-provider contract (found, `StickerContentProviderFetcher`/`C179697lN`, `C175327dG`)

WhatsApp reads a third-party pack by querying the *calling app's own* provider at the given authority, gated by `readPermission == "com.whatsapp.sticker.READ"` on that provider:

| URI | Columns returned |
|-----|-------------------|
| `content://<authority>/metadata/<identifier>` | `sticker_pack_identifier`, `sticker_pack_name`, `sticker_pack_publisher`, `sticker_pack_icon`, `android_play_store_link`, `ios_app_download_link`, `image_data_version`, `whatsapp_will_not_cache_stickers`, `animated_sticker_pack` |
| `content://<authority>/stickers/<identifier>` | `sticker_file_name`, `sticker_emoji`, `sticker_accessibility_text` |
| `content://<authority>/stickers_asset/<identifier>/<filename>` | openable stream (tray icon or individual sticker file) |

Validation found in the fetcher: `authority`/`identifier` reject invalid characters; `identifier` ≤ 128 chars; returned `sticker_pack_identifier` must echo the requested identifier; `sticker_pack_icon` filename ≤ 128 chars; `android_play_store_link` must contain `play.google.com`, `ios_app_download_link` must contain `itunes.apple.com` or `apps.apple.com`; `publisher`/`name` non-empty and ≤ 128 chars; `tray` id non-empty; sticker count must fall within `[flag 17124, flag 17327]` inclusive (dictionary-token bounds, numeric values not resolved in this pass); each fetched sticker asset is capped at **~103424 bytes (101 KB)** for a static pack or **~512512 bytes (500.5 KB)** for an animated pack (`Math.min(animated ? 500 : 100, 1024) + 1) * 1024`; oversized or unreadable streams are dropped with the file set to null rather than aborting the whole pack. A matching `app may have been deleted` / `third_party_sticker_app_deleted` path handles the provider's package disappearing mid-fetch.

A separate boolean flag (**13081**) controls whether an already-whitelisted pack is still re-fetched from the content provider or served from cache, and flag **22198** switches between an older synchronous dialog-driven add flow and routing straight to the sticker-pack preview screen; flag **13711** selects between two internal install variants (`C175327dG.A00` vs `A01`) when installing via the content-provider shortcut path (section 7.5) instead of the activity.

### 7.4 `SEND_STICKER` intent contract (found, `SendStickerCommandActivity`)

Data: a `content://` URI, from the calling app's own provider, whose authority must resolve to that same calling package. The referenced file must decode as exactly **512×512** WebP and be ≤ **500000 bytes**; the client restamps it through the normal sticker pipeline (hash, store, attach) and attaches these `Intent` extras as `Sticker` pack metadata if present: `sticker_accessibility_text`, `sticker_pack_id`, `sticker_pack_name`, `sticker_pack_publisher`, `sticker_pack_ios_store_link`, `sticker_pack_play_store_link` (the two store links are validated with the same domain checks as section 7.3).

### 7.5 Whitelist-check provider (found, `WhitelistPackQueryContentProvider`)

`content://com.whatsapp.provider.sticker_whitelist_check/<match>?authority=<pkg-authority>&identifier=<pack-id>` — single-row, single-column (`result`, `0`/`1`) cursor answering "is this pack already added". Caller validation mirrors 7.2: the calling package must equal the package that owns the queried `authority`. MIME type returned by `getType()`: `vnd.android.cursor.item/vnd.com.whatsapp.provider.sticker_whitelist_check.is_whitelisted`.

### 7.6 Internal sticker-command provider (found, `StickerCommandProvider`, `com.whatsapp.provider.sticker_command`, `exported="true"`)

Not part of the third-party contract above — this is WhatsApp's own provider, queried by WhatsApp's own UI/assistant surfaces, with URI last-path-segment dispatch:

| Path | Behaviour |
|------|-----------|
| `installPack?authority=&identifier=` | installs a pack via the same `C175327dG` fetch/validate path as section 7.3, bypassing the activity UI |
| `removePack?authority=&identifier=` | uninstalls a previously-added pack |
| `generate?prompt=` | AI sticker generation (section 8); prompt length must be 3–200 chars after trim |
| `availability` | returns `{available, consent_required}` for AI sticker generation |
| `image/<token>` (via `openFile`) | streams a generated sticker PNG/WebP back by opaque token, MIME `image/webp` |

---

## 8. AI-generated stickers (found, `AiStickerCommands`, `StickerCommandProvider`)

`isAiSticker` (field 20) flags a `StickerMessage` as AI-generated; the type string is `genai_sticker` (section 2.2). Generation itself is local-UI-triggered through the `generate` provider path (7.6): eligibility (`C174467bs.A00`) and consent (`A02`) gates are checked before any generation call; results come back as a list of opaque `token`s later resolved through `image/<token>`. The actual generation backend (on-device vs. server-side model) is unknown from this code path — only the client-side eligibility/consent/token plumbing was resolved.

---

## 9. Sticker search (found, `StickerSearchManager`, `EmojiGroupMapper`, contextual-suggestion package)

Entirely local, not a server query. `StickerSearchManager.A00` takes a free-text query, resolves it to a set of emoji characters via `EmojiGroupMapper`, joins them into a space-separated string, and matches that string against the **locally stored** `emojis` field of each `StickerMessage`/pack `Sticker` (section 2.3) plus recently-used/featured candidates, splitting results into "exact emoji match" vs. "other" buckets and truncating to a dictionary-token result limit (flag **22573**). An `includeAvatarResults` flag separately gates whether avatar stickers participate, gated behind its own eligibility check. This confirms — and upgrades from "may contain… unknown" to found — that the proto's `emojis` string field is the client-side search index key, not a display-only tag.

---

## 10. Media encryption (link, not repeated)

Every sticker-bearing media reference (`stickerMessage`, `stickerPackMessage`, their thumbnails) goes through the identical media pipeline documented in [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md): 32-byte random media key, HKDF-80 (`WhatsApp Image Keys` for `sticker`, `WhatsApp Sticker Pack Keys` for `sticker-pack`, `WhatsApp Sticker Pack Thumbnail Keys` for the pack thumbnail, `WhatsApp Image Thumbnail Keys`-style handling is not used here — sticker and pack thumbnails have their own dedicated info strings), AES-CBC + 10-byte truncated HMAC-SHA256, `fileSha256`/`fileEncSha256`, `media_conn`-issued hosts, and the `/mms/<type>/<hash>` upload URL shape. Nothing sticker-specific changes any of that; see sections 2–9 of that report for the full derivation, retry, and error-code tables.

---

## 11. Feature flags (ids as read at call sites; names unresolved)

| Flag | Where | Controls |
|------|-------|----------|
| **1900** | `C161826tK` ctor | per-entry and aggregate pack-ZIP extraction size budget (KB) |
| **13081** | `AddThirdPartyStickerPackActivity` | re-fetch vs. cache for an already-whitelisted third-party pack |
| **13711** | `StickerCommandProvider`, `AddThirdPartyStickerPackActivity` | selects install-path variant (`C175327dG.A00` vs `A01`) |
| **17124** / **17327** | `StickerContentProviderFetcher` | min / max sticker count accepted from a third-party pack |
| **22198** | `AddThirdPartyStickerPackActivity` | async dialog-driven add flow vs. direct preview-screen routing |
| **22573** | `StickerSearchManager` | local search result limit |

---

## 12. Baileys (`baron-baileys-v2`, source read, nothing tested)

| Aspect | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| `Message.StickerMessage` fields | identical field set including `audioMessage` (26, `oneof audio`) — the proto source matches the decompiled 2.26.41.6 layout field-for-field | same (section 2.1) |
| `Message.StickerPackMessage` fields | identical field set (1–22) | same (section 5.1) |
| Sending a sticker | `prepareWAMessageMedia({ sticker })` builds `stickerMessage` through the generic media-prep path (`MmsType` `sticker`, Image HKDF info); `stickerAudio` option attaches a prepared `audioMessage` onto `m.stickerMessage.audioMessage` | same media pipeline per [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) section 17 |
| Sending a pack | `stickerPackMessage`/`stickerPack` input is passed through `StickerPackMessage.fromObject` with no extra validation | client additionally validates via the ZIP extractor and DB constraints (section 5, 6) before accepting a pack it builds itself |
| Decoding | `decode-wa-message.js` maps `isAvatar`→`avatar_sticker`, `isAiSticker`/`isGenAI`→`genai_sticker`; `messages-send.js` maps `isLottie`→`1p_sticker` ahead of `isAvatar`/plain `sticker` when deriving the outgoing type string | same three message-type strings found in Android analytics dispatch (`avatar_sticker`, `genai_sticker`, plus `1p_sticker`/`user_created_sticker`); exact Android precedence order unconfirmed (section 2.2) |
| Third-party pack intents/providers | not implemented — Baileys has no Android `Intent`/`ContentProvider` surface | full surface, section 7 |
| `lottieStickerMessage` / `audioStickerMessage` wrappers | present as a bare `FutureProofMessage` field in the proto only; no dedicated encoder/decoder path found | same bare envelope, no field-specific handling found either (section 3) |

---

## 13. Error cases

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ENABLE_STICKER_PACK` returns `validation_error` "cannot find the provider for authority" | third-party app's `authority` string doesn't resolve to any installed provider | the sticker-pack-publishing app must declare and export its provider under that exact authority |
| `ENABLE_STICKER_PACK` returns "does not own authority" | calling package differs from the resolved provider's package | an app may only vouch for authorities inside its own package |
| Pack add silently fails with "sticker count should be between X and Y" | pack's `stickers` query returned a row count outside `[flag 17124, flag 17327]` | keep the third-party `/stickers/<id>` cursor within the server-configured bounds |
| `SafeZipEntrySaver: File being unzipped is too big` / "Too many files to unzip" | pack ZIP exceeds the per-entry/aggregate byte budget or the 65-entry cap | shrink the pack or split stickers across packs |
| `tray image name invalid` / name length error | third-party `sticker_pack_icon` contains invalid characters or exceeds 128 chars | sanitize and shorten the tray filename |
| `StickerPackZipEntrySaver/file in zip is not valid` | an extracted entry's sniffed content type doesn't match its claimed extension/MIME | ship entries whose bytes actually match `png`/`webp`/`was` |
| `the sticker is not a 512px WebP` (`SEND_STICKER`) | single-sticker intent's image isn't exactly 512×512 | resize before sending the intent |

---

## 14. Key distinctions

| Do not confuse | Fact |
|----------------|------|
| `StickerMessage.audioMessage` (field 26) vs. `Message.audioStickerMessage` (field 134) | former is a confirmed embedded `AudioMessage` inside a sticker send; latter is a separate, still-opaque top-level wrapper field new to this build |
| `isLottie` (per-sticker flag) vs. `Message.lottieStickerMessage` (field 74 wrapper) | the flag is tied to a concrete found file format (`.was` ZIP with `animation/animation.json`); the wrapper field's nested payload is still unresolved — they are not shown to be the same mechanism |
| `stickerSyncRmrMessage` (wire message, absent) vs. `RecentStickerDBStorage` (`filehash`-keyed local table) | the former no longer exists on the wire in this build; the latter is unrelated local bookkeeping that happens to also key by file hash |
| Third-party pack contract (sections 7.2–7.5, external app's provider) vs. `StickerCommandProvider` (section 7.6, WhatsApp's own provider) | both can "install a pack by authority+identifier", but the first is WhatsApp *reading another app's* provider, the second is WhatsApp's internal shortcut around its own activity UI |
| AI sticker generation (`isAiSticker`, local GenAI flow) vs. third-party AI/sticker apps | the former is WhatsApp's own in-app feature behind `StickerCommandProvider`; it has nothing to do with the third-party content-provider contract |

---

## 15. Flow: adding a third-party sticker pack

```
[Third-party app]  exports ContentProvider at authority X, readPermission=com.whatsapp.sticker.READ
     │  startActivityForResult(ACTION_ENABLE_STICKER_PACK, extras: sticker_pack_id, sticker_pack_authority=X, sticker_pack_name)
     ▼
[AddThirdPartyStickerPackActivity]  getCallingActivity() != null?
     │  resolveContentProvider(X) exists?  calling package == provider's package?
     ▼  (all pass)
[StickerContentProviderFetcher]  query content://X/metadata/<id>
     │  validate identifier echo, name/publisher length, tray icon name, store links
     ▼
[StickerContentProviderFetcher]  query content://X/stickers/<id>  (sticker_file_name, sticker_emoji, sticker_accessibility_text)
     │  validate count in [flag 17124, flag 17327], accessibility text ≤ 125/250 chars
     ▼
[StickerContentProviderFetcher]  openInputStream content://X/stickers_asset/<id>/<file>  per sticker + tray icon
     │  cap ~101 KB (static) / ~500.5 KB (animated) per asset
     ▼
[Client]  store pack + stickers, mark whitelisted (ThirdPartyWhitelistedPacksStore)
     │
     ▼
[AddThirdPartyStickerPackActivity]  result Intent: add_successful=true | already_added=true | validation_error=<reason>
     │
     ▼
[Third-party app]  onActivityResult()
```

---

## 16. Unknowns

| Item | Status |
|------|--------|
| Nested payload of `lottieStickerMessage` (74) and `audioStickerMessage` (134) | field exists, generic `FutureProofMessage` wrapper, contents unresolved |
| Exact Android precedence for `sticker` vs. `1p_sticker` vs. `user_created_sticker` type strings | only the analytics byte-code mapping was found, not the selecting function |
| `premium` field (24) on `StickerMessage`/`Sticker` | no consumer located |
| Numeric values behind dictionary-token flags 1900, 17124, 17327, 22573 | token ids found, live values not resolved statically |
| `whatsapp://stickerpack` deep-link target activity | host declared in the manifest's generic deep-link intent-filter; which internal screen consumes it was not isolated |
| AI sticker generation backend (on-device vs. server) | only client eligibility/consent/token plumbing resolved |
| Whether the server enforces its own pack size/count limits beyond the client's | server-side, unknown |
| `stickerSyncRmrMessage`'s fate (renamed, moved, or dropped) | confirmed absent from the wire proto in 2.26.36.1 through 2.26.41.6; removal not confirmed |
| Traffic | nothing captured; no dynamic test |
