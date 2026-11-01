# WhatsApp View-Once — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-11-01
**Scope:** `viewOnceMessage` / `viewOnceMessageV2` / `viewOnceMessageV2Extension` wrapper vs. the inline `viewOnce` field on `ImageMessage` / `VideoMessage` / `AudioMessage` / `ExtendedTextMessage`, the generic message-wrapper unwrap mechanism shared with disappearing messages, message types and the common marker interface, client-side enforcement (screenshot/screen-recording block, forward/share/save restriction, sender self-view block, quoted-media stripping), local storage and state machine (`message_view_once_media`, deletion job), media-key lifecycle (linked, not repeated), the `unavailable[type="view_once"]` wire case and cross-device read/write tokens, feature flags, Baileys comparison

---

## 1. What it is

View-once is a per-message attribute, not a separate message type: any image, video, voice message, or (on recent builds) text can be marked so the recipient's client deletes the local copy after it is opened once, and the client additionally blocks screenshots/screen-recording and hides forward/share/save while it is open. All statements are static analysis of the decompiled APK; nothing was captured on the wire. Tiers: **found** = read in code, **inferred** = deduced from code, **unknown** = not resolved. Names were resolved in 2.26.41.6 from stable strings and log tags (`AppDataManager/contributeMetaAppData`, `ConversationRowViewOnceMedia/`, `EphemeralUpdateRunnable/`, `ViewOnceMessageStore/`, UI string ids).

| Entity | 2.26.41.6 name | Role |
|--------|-----------------|------|
| Wrapper message (one field, `message` **1**) | `BD2` | body of `viewOnceMessage` **37**, `viewOnceMessageV2` **55**, `viewOnceMessageV2Extension` **59** on `Message` (`C30628DTw`) |
| Inline flag per media type | `ImageMessage.viewOnce` **25**, `VideoMessage.viewOnce` **20**, `AudioMessage.viewOnce` **21**, `ExtendedTextMessage.viewOnce` **30** | set directly on the media/text message, no wrapper |
| Wrapper-vs-inline switch | flag **8784** | on: inline field only; off: wrapper + inline field both set (6.3) |
| View-once image handler | `C34670F2r` ("FMessageViewOnceImageProtobuf") | builds/reads `DdP`, message type **42** |
| View-once video handler | `C34671F2s` ("FMessageViewOnceVideoProtobuf") | builds/reads `C30972DdZ`, message type **43** |
| View-once text handler | `F33` ("FMessageViewOnceTextProtobuf") | builds/reads `C31208Dhd`, message type **78** |
| View-once audio handler | `C34669F2q` ("FMessageViewOnceAudioProtobuf") | builds/reads `C30963DdH`, message type **82** |
| Marker interface | `InterfaceC24513Ahd` | implemented by all four FMessage classes above; used to gate UI/menu behaviour generically |
| Local state table | `message_view_once_media` | columns `message_row_id`, `state` |
| State accessor | `C199158dT` ("ViewOnceMessageStore") | get/insert/update `state` |
| Deletion job | `EphemeralUpdateRunnable` (anonymous class in `C199218dZ`), job type **3** | "`ViewOnceMessageStore/getViewOnceMessagesToDelete`" |
| Screen-capture block helper | `C66572s0` | `window.addFlags(8192)` = `FLAG_SECURE` |
| View-once gate for the media viewer | `C1ZB.A0O(i)` | `i == 42 \|\| i == 43` |
| Dedicated viewer (text/audio) | `ViewOnceViewerActivity`, `ViewOnceTextFragment`, `ViewOnceAudioFragment` | separate Activity, always `FLAG_SECURE` |
| Shared viewer (image/video) | `MediaViewFragment` / `MediaViewMenu` | normal media viewer, `FLAG_SECURE` only when `C1ZB.A0O` is true |
| Education sheets | `ViewOnceNuxBottomSheet`, `ViewOnceSecondaryNuxBottomSheet` | one-time explainer shown to sender/receiver |
| Quoted-media stripper | `F43` ("QuotedMediaCleanupSerializationPostProcessor") | removes media bytes from a quote of a view-once message, flag **25572** |

---

## 2. Proto marking

### 2.1 Inline field (found)

```text
ImageMessage.viewOnce         = 25  (bool)
VideoMessage.viewOnce         = 20  (bool)
AudioMessage.viewOnce         = 21  (bool)
ExtendedTextMessage.viewOnce  = 30  (bool, VIEW_ONCE_FIELD_NUMBER)
```

Each is a plain boolean on the normal media/text message; no separate container is required to carry it. Confirmed by reading the generated field tables of `C30612DTg` (Image), `C30614DTi` (Video), `DTX` (Audio), `C30613DTh` (ExtendedText).

### 2.2 Wrapper message (found)

`viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**) and `viewOnceMessageV2Extension` (**59**) on `Message` are all typed `BD2`, and `BD2` has exactly one field, `message` **1**, itself a `Message`. All three field names decompile to the identical class — they are the same wrapper shape used three times for three protocol generations:

```java
public final class BD2 extends GeneratedMessageLite {
    public static final int MESSAGE_FIELD_NUMBER = 1;
    public C30628DTw message_;   // a full nested Message
}
```

### 2.3 Inline vs. wrapper: flag 8784 (found)

Every per-type handler (`C34670F2r` image, `C34671F2s` video, `F33` text, `C34669F2q` audio) builds the same thing twice and picks one on a flag:

```java
boolean zA15 = this.A00.A15(8784);
...
if (zA15) {
    dp5.A0R(c30612DTg);                 // inline viewOnce=true directly on the outer Message
    return;
}
dp5A0f.A0R(c30612DTg);                  // same media message, but inside the BD2 wrapper
BD2 bd2A0Q = ...;
c30628DTwA0j.viewOnceMessageV2_ = bd2A0Q;
```

With the flag on, 2.26.41.6 never emits a wrapper for a locally composed view-once message; the recipient-side `CM7` (receive) handlers in the same classes only look at the inline flag (`c30612DTg.bitField0_ & ... && c30612DTg.viewOnce_`), not at the wrapper fields — unwrapping a wrapper down to the inline shape is a separate, generic step (2.4).

### 2.4 Generic wrapper unwrap (found)

A static table (`AbstractC33204EdH.A00`, 35 entries) pairs a "has this wrapper" predicate with a "get the inner `Message`" extractor for every forward-compatibility wrapper the client knows, including `ephemeralMessage` (disappearing-messages wrapper), `viewOnceMessage`, `viewOnceMessageV2`, `viewOnceMessageV2Extension`, `editedMessage`, `documentWithCaptionMessage`, `botInvokeMessage`, `groupStatusMessage`, and others. `C34748F5r` (native-flow/`<biz>` validation, `AbstractC33204EdH.A00`) recurses through this table up to depth 10 to find the classifiable content regardless of how many wrappers surround it:

```java
for (EQR eqr : AbstractC33204EdH.A00) {
    if (hasWrapper(c30628DTw, eqr) &&
        A00(..., unwrap(c30628DTw, eqr), i + 1) != C02U.A00) {
        return result;
    }
}
```

`ephemeralMessage` and the three view-once wrappers are peer entries in this table — structurally the same mechanism, so a view-once message can in principle be nested inside, or alongside, a disappearing-messages wrapper (section 7). This mirrors Baileys's own `getFutureProofMessage()` list in `message-inspect.js`, which enumerates the identical set of wrapper field names.

---

## 3. Message types and the marker interface

| Type | Media class | Handler | Fragment/Activity |
|------|-------------|---------|--------------------|
| **42** | `DdP` (image) | `C34670F2r` | `MediaViewFragment` (shared image/video viewer) |
| **43** | `C30972DdZ` (video) | `C34671F2s` | `MediaViewFragment` |
| **78** | `C31208Dhd` (text) | `F33` | `ViewOnceTextFragment` inside `ViewOnceViewerActivity` |
| **82** | `C30963DdH` (audio/ptt) | `C34669F2q` | `ViewOnceAudioFragment` inside `ViewOnceViewerActivity` |

All four classes implement `InterfaceC24513Ahd`, the single marker the rest of the client tests for ("is this a view-once message") instead of repeating the four-type check everywhere. `C1ZB.A0O(i)` (`i==42 || i==43`) is the narrower image/video-only test used where the shared `MediaViewFragment` needs to distinguish view-once image/video from everything else it also renders.

The type-set `{42,43,78,82}` recurs verbatim at several independent call sites found in this build: the `<meta view_once="true">` producer (section 6.1), the type-name lookup table (`AbstractC32316E9h`: `"viewOnceImage"`=42, `"viewOnceVideo"`=43, `"viewOnceAudio"`=82), and `C1ZB` helper methods for save/display gating.

---

## 4. Client-side enforcement

### 4.1 Screenshot / screen-recording block (found)

`C66572s0.A00(Window)` is a one-line helper:

```java
public final void A00(Window window) {
    if (window != null) {
        window.addFlags(8192);   // WindowManager.LayoutParams.FLAG_SECURE
    }
}
```

`8192` (`0x2000`) is the raw value of `FLAG_SECURE`; the decompiled sources use the numeric constant, not the symbolic name, so a text search for `FLAG_SECURE` finds nothing — the constant must be matched by value. `FLAG_SECURE` blacks out the window in screenshots, in the recent-apps thumbnail, and during screen recording/casting at the OS level; it is not WhatsApp-specific detection, it is the standard Android secure-window flag.

Two call sites:

| Call site | Condition | Scope |
|-----------|-----------|-------|
| `MediaViewFragment` (generic media viewer) | `C1ZB.A0O(i)` i.e. `i==42 \|\| i==43` | applied only when the message being shown is view-once image/video; otherwise the normal media viewer is not secured |
| `ViewOnceViewerActivity.onCreate` | unconditional | this Activity is only ever launched for view-once text (78) or audio (82), so every instance of it is secured |

Net effect: opening any of the four view-once types sets `FLAG_SECURE` on the hosting window for as long as it is open; closing the viewer (the fragment/activity being torn down) removes the window, which drops the flag with it. No evidence of a screenshot *detection* mechanism (e.g. a `FileObserver` on `Pictures/Screenshots` or a `MediaStore` content-observer) was found; the protection is OS-level prevention, not after-the-fact detection.

### 4.2 No forward / share / save (found)

`ViewOnceViewerActivity.onCreateOptionsMenu` builds exactly four menu entries — info, transcribe (audio only), delete, report — and no others; there is no forward, share, save, or copy entry in that menu at all. In the shared `MediaViewMenu` (used for view-once image/video through the normal media viewer), several boolean menu-visibility locals are computed with an explicit `instanceof InterfaceC24513Ahd` exclusion, e.g.:

```java
if (i6 == 2 && !c36911dGA1I21.element && ... && !(abstractC34931a2 instanceof InterfaceC24513Ahd)) {
    z14 = !C0DZ.A0X(c0df);     // forward-related menu flag, left false (hidden) for view-once
}
...
z16 = abstractC34931a2 instanceof InterfaceC24513Ahd;
if (!z16) {
    z17 = !AbstractC24760wu.A07(c0df);   // another gated flag, defaults false for view-once
}
```

Because every flag defaults to `false` and is only assigned a usable value in the non-view-once branch, the corresponding menu items stay hidden for `InterfaceC24513Ahd` messages. The restriction is enforced in the UI layer (menu construction), not by removing the underlying media from local disk before the viewer opens it.

### 4.3 Sender cannot reopen own media (found)

`DYM` (conversation-row component for view-once media) asserts:

```java
C00K.A0C(false, "ConversationRowViewOnceMedia/senders can not view their own media");
```

on the path a sender's own sent view-once row would use to re-open the content — i.e. the invariant "a sender never gets a working open-handler for their own view-once message" is enforced as a hard assertion rather than a conditional UI hide.

### 4.4 Quoting strips the media (found)

`F43` ("QuotedMediaCleanupSerializationPostProcessor", gated by flag **25572**) rewrites a quoted message's `imageMessage` / `videoMessage` / `documentMessage` / `audioMessage` before it is attached as `contextInfo.quotedMessage` to a *new* outgoing message: it copies non-content fields (mimetype, caption, dimensions, thumbnail, the `viewOnce` bit itself) but drops `mediaKey`, `fileSha256`/`fileEncSha256`, and `directPath`. Quoting a view-once message therefore cannot smuggle the original media key into a reply; the quote shows metadata only.

### 4.5 Education sheets (found)

`ViewOnceNuxBottomSheet` is shown once per role (sender/receiver — tracked by UXCam keys `ephemeral_view_once` / `ephemeral_view_once_receiver`) the first time each side sends/receives a view-once message, with copy pulled straight from `res/values/strings.xml`:

| String id | Text |
|-----------|------|
| `str4e56` | "View once messages give you more privacy" |
| `str4e55` | "For added privacy, the recipient can't share, forward, copy, save, or take a screenshot of it." |
| `str4e68` / `str4e5d` / `str4e7b` | per-type variants: "This is a view once photo/message/video so it's more private" |
| `str4e69` / `str4e6a` / `str4e5c` | "Also, you can't share, forward, copy, save, or take a screenshot of it." |
| `str4e63` / `str4e64` | "View once photo, expired" / "View once photo, opened" (same pattern for video/audio/text) |

The "expired"/"opened" string pairs per type (image, video, audio, text) are the user-visible face of the local `state` column (section 5).

---

## 5. Local storage and state machine

### 5.1 Table (found, `C199158dT`)

```sql
-- message_view_once_media(message_row_id, state)
SELECT state FROM message_view_once_media WHERE message_row_id = ?     -- GET_VIEW_ONCE_STATE_BY_MESSAGE_ROW_ID_SQL
UPDATE message_view_once_media SET state = ? WHERE message_row_id = ?  -- UPDATE_VIEW_ONCE_SQL
INSERT INTO message_view_once_media (message_row_id, state) VALUES (?, ?)  -- INSERT_VIEW_ONCE_SQL
```

One row per view-once message, independent of the generic `message` and `message_media` tables (which still hold the row/media-file bookkeeping shared with ordinary messages).

### 5.2 States (found row values, name mapping partly inferred)

| Transition | Code | Trigger |
|------------|------|---------|
| Row created | `A02` (`BDk()` on the FMessage, value at creation) | message sent/received; initial value is whatever the FMessage reports — consistent with "0 = unopened" but no named constant was found |
| Marked opened | `A03`: `state = 1` | message status (`B6u()`) reaches **8**, **9**, or **10** (download/read-related status codes; exact names not resolved) |
| Read with no row | fallback `i = 2` in `A01` | `GET_VIEW_ONCE_STATE...` returns no row; the code treats this as if the message had already expired |

So **1** = confirmed "opened" (named call site); **2** is the no-record/expired fallback; an initial/"unopened" value exists but was not pinned to a literal in this build.

### 5.3 Deletion (found)

The same `EphemeralUpdateRunnable` class that expires disappearing messages (job type 0, table `message_ephemeral`) and message-secret add-ons (job type 4, table `message_add_on`) also runs job type **3**, logged as `ViewOnceMessageStore/getViewOnceMessagesToDelete`:

```sql
SELECT message.* FROM message_view_once_media AS view_once
  JOIN message AS message ON view_once.message_row_id = message._id
  JOIN message_media AS message_media ON message_media.message_row_id = message._id
WHERE message_media.file_size IS NOT NULL
  AND message_media.file_size IS NOT 0
  AND message.from_me = 0
  AND view_once.state IN (1, 2)
LIMIT ?
```
<sub>(simplified column list; `GET_EXPIRED_VIEW_ONCE_MESSAGES_SQL`)</sub>

Read literally: the job only ever targets *received* view-once media (`from_me = 0`) that still has a file on disk (`file_size` present and non-zero) and whose state is `1` (opened) or `2` (the same fallback value used for "no row"/expired). The job frees the local media file for rows matching that query; it does not delete the message row itself (the row survives, carrying the "opened"/"expired" UI label from 4.5). **Sent** view-once media (`from_me = 1`) is not covered by this query — consistent with the sender never being allowed to re-open it (4.3), but no corresponding cleanup for the sender's own copy was found; its retention/deletion is **unknown**.

### 5.4 Media key / crypto lifecycle (linked, not repeated)

View-once media uses the ordinary media pipeline end to end — same `MmsType` table, same HKDF-80 key derivation, same AES-CBC+HMAC envelope, same upload/download URLs; there is no separate "view-once" `MmsType` row. See [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) sections 3-5 for the crypto, and section 12 of that report for the view-once-specific notes (sender-cannot-view assertion, thumbnail deletion log tag). Whether the server independently deletes or marks the uploaded object after first download is **unknown** from this static analysis — the client-side guarantee is the local-file deletion in 5.3, not a server contract the client can observe.

---

## 6. "View once unavailable" / cross-device signalling

### 6.1 `unavailable[type="view_once"]` stanza (correction to an earlier research note)

An earlier research note (2.26.35.2) traced the outbound literal pair `view_once`/`true` to a method logged as `AppDataManager/contributeMetaAppData` and left open whether that method built a complete node or only contributed metadata. In 2.26.41.6 the same log tag (`"AppDataManager/contributeMetaAppData type="`) is **not** the `view_once` producer: it belongs to a different, unrelated branch of `F6K` (the generic `<meta>`-node builder) that stamps a free-form `appdata` attribute for bot/add-on messages (`FZF.AVN()`). The actual `view_once` attribute in this build is built a few lines earlier in the *same* `F6K` method, independently of that log line:

```java
if (c08j2.A15(11282) && (i == 42 || i == 43 || i == 82 || i == 78)) {
    EZV.A00(ezv, "view_once", "true");
}
```

This emits `<meta view_once="true">` as a child/attribute of the outgoing `<message>` stanza's `<meta>` node (not the `<unavailable type="view_once">` child the research note and Baileys/whatsmeow describe). Both can be true at once: `<meta view_once="true">` is the sender's own-stanza marker that this message is view-once; `<unavailable type="view_once">` is a *different* node, observed only on the receiving/Web side when no ciphertext was fanned out to that device. Static analysis of the Android APK (which has no Web/linked-device role here) cannot show which side assembles that second node; this report does not change the earlier medium-high-confidence conclusion that it is server-produced or server-normalized from the sender's fanout state. Baileys corroborates the receive side with a *more specific* literal than the generic one: `src/Socket/messages-recv.js` checks `unavailableType === 'view_once_unavailable_fanout'` (alongside `bot_unavailable_fanout`, `hosted_unavailable_fanout`) to decide whether to skip an on-demand placeholder-resend request, while `src/Utils/decode-wa-message.js` separately matches the plain `attrs.type === 'view_once'` on an `<unavailable>` child to set `isViewOnce`/`StubType.VIEWED_ONCE`. These are two different code paths for what the earlier research note treated as one string.

### 6.2 `view_once="read"`/`"write"` tokens (found token, consumer unresolved)

The literals `view_once_read` and `view_once_write` are present in the Android client's binary-stanza dictionary table (`AbstractC40911lb`, the fixed wire-vocabulary list used for compact token encoding) — the same kind of table that carries `unavailable`, `enc`, `polltype`, etc. Baileys's `decode-wa-message.js` reads an `attrs.view_once` value of `'read'` or `'write'` on `<enc>`-level attributes and stores it as `fullMessage.viewOnceType`. Taken together this is consistent with a per-own-device "already opened" sync signal riding along with the message envelope — plausibly how a user's other linked devices learn that the view-once content was already opened on one device — but no Android call site that *sets* or *consumes* this attribute was located in 2.26.41.6; it is recorded here as a found wire token with an unresolved Android consumer (**unknown**).

---

## 7. Interplay with disappearing messages

View-once and disappearing messages (per-chat message TTL) are independent, orthogonal flags that can both be set on the same message:

- They use separate local tables: `message_ephemeral` (disappearing, keyed by `expire_timestamp`) vs. `message_view_once_media` (view-once, keyed by `state`).
- Both are expired by jobs on the *same* `EphemeralUpdateRunnable` worker (job type 0 for disappearing, job type 3 for view-once, job type 4 for message-secret add-ons) — a shared scheduling/execution path, distinct per-feature state and SQL.
- At the proto level, `ephemeralMessage` is a peer entry in the exact same generic wrapper-unwrap table as the three view-once wrappers (section 2.4): a message can be wrapped as `ephemeralMessage{message: viewOnceMessage{message: imageMessage{...}}}` or the reverse nesting, and the recursive unwrap in `C34748F5r` and Baileys's `getFutureProofMessage()` both walk through either order.
- Disappearing-message deletion removes the whole message after the chat's TTL regardless of whether it was opened; view-once deletion removes only the *media file* once the message was opened (or falls into the state-2 fallback), and leaves the message row (now shown as "opened"/"expired") in place. A view-once photo inside a disappearing chat is therefore still subject to the chat's TTL on top of its own one-open-then-wipe media rule.

---

## 8. Feature flags (ids as read at call sites; names unresolved)

| ID | Type | Controls |
|----|------|----------|
| **8784** | bool | send view-once media with the inline field only (on) vs. inline field + legacy wrapper (off) |
| **11282** | bool | emit `<meta view_once="true">` for message types 42/43/78/82 |
| **25572** | bool | strip media fields from a quoted view-once message (`F43`) |

(Flags governing the shared media pipeline — HKDF, upload/download, retry — are listed in [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) section 16 and are not repeated here.)

---

## 9. Baileys (`baron-baileys-v2`, source read, nothing tested)

| Topic | Baileys | Android 2.26.41.6 |
|-------|---------|---------------------|
| Send-side marking | always wraps: `{ viewOnceMessage \| viewOnceMessageV2 \| viewOnceMessageV2Extension: { message } }` depending on a `viewOnceVersion` option (`src/Utils/messages.js`) | wraps only when flag 8784 is off; the default (8784 on) sets the inline `viewOnce` field on the media/text message directly, no wrapper |
| Wrapper also used for non-media | `viewOnceMessage` is additionally used to futureproof `buttonsMessage`/`templateMessage`/`listMessage`/`interactiveMessage` sends (`src/Socket/messages-send.js`, `requiresViewOnce`) — unrelated to self-destructing privacy | same wrapper type (`BD2`) is reused by the generic unwrap table for `botInvokeMessage`, `editedMessage`, etc. — same "generic envelope" role confirmed independently (2.4) |
| Generic unwrap list | `getFutureProofMessage()` in `message-inspect.js`: `ephemeralMessage`, `viewOnceMessage`, `documentWithCaptionMessage`, `viewOnceMessageV2`, `viewOnceMessageV2Extension`, `editedMessage`, `groupMentionedMessage`, `botInvokeMessage`, ... | `AbstractC33204EdH.A00` (35 entries) — same wrapper field names |
| `unavailable` receive handling | two distinct literal checks: `attrs.type === 'view_once'` (sets `isViewOnce`) and `unavailableType === 'view_once_unavailable_fanout'` (skips placeholder resend) | client-side `<meta view_once>` producer only (6.1); the `<unavailable>` node itself is receive-path/Web-side, not traced here |
| `view_once` read/write token | decodes `attrs.view_once === 'read' \| 'write'` on `<enc>` attributes into `viewOnceType` | tokens present in the client's wire dictionary; no Android consumer located (6.2) |
| Analytics | `WAM/constants.js`: `viewOnceMessagesSent` (16), `viewOnceMessagesReceived` (17), `viewOnceMessagesOpened` (18) | not traced in this report; see [WA_WAM_ANALYTICS.md](./WA_WAM_ANALYTICS.md) for the WAM mechanism in general |
| Screenshot/forward blocking | not implemented — Baileys is a backend library with no UI, no window, no menu to restrict | `FLAG_SECURE` + menu-item omission (4.1-4.2); not reproducible outside an Android UI |
| Local deletion after open | not applicable — Baileys has no persistent media-viewer state machine; callers are responsible for their own storage | `message_view_once_media.state` + `EphemeralUpdateRunnable` job type 3 (5.1-5.3) |

---

## 10. Error cases / gotchas

| Symptom | Cause | Note |
|---------|-------|------|
| View-once media is gone when the viewer is reopened | normal: `state` reached 1 (opened) or the row was absent (fallback 2), and the deletion job already freed the file | not a bug; this is the intended one-open-then-wipe behaviour |
| Sender's own view-once media never opens from the conversation row | `DYM` hard assertion `senders can not view their own media` | by design, not an error path |
| Quoted view-once reply shows no media | `F43` strips `mediaKey`/hashes/`directPath` from the quote, keeping only caption/dimensions/thumbnail/the `viewOnce` bit | expected; quoting cannot be used to re-extract the media |
| View-once image/video viewer lets screenshots through on some builds but not others | `FLAG_SECURE` is only applied via `C1ZB.A0O(i)` (types 42/43); any regression in that gate (e.g. a code path that opens the shared viewer for a view-once item without going through the gated call) would silently drop the protection | gate location documented at `MediaViewFragment` line ~3120 (this build) |
| A linked device shows a view-once message as already opened without the user opening it there | plausible cross-device sync via `view_once="read"/"write"` wire tokens (6.2) | mechanism not confirmed on the Android side; recorded as unknown |

---

## 11. Key distinctions

| This | Not this |
|------|----------|
| `viewOnce` boolean field on `ImageMessage`/`VideoMessage`/`AudioMessage`/`ExtendedTextMessage` | the legacy `viewOnceMessage`/`viewOnceMessageV2`/`viewOnceMessageV2Extension` wrapper around the same message |
| `viewOnceMessage` (`BD2`) used for privacy (self-destruct) | the same `BD2` wrapper type reused as a generic futureproofing envelope for buttons/template/list/interactive sends (Baileys) and for `botInvokeMessage`/`editedMessage` on Android |
| `message_view_once_media.state` (local, per message, open/expire tracking) | `message_ephemeral.expire_timestamp` (local, per message, disappearing-chat TTL) — independent tables, independent jobs, same runner |
| `<meta view_once="true">` — sender-side classifier on the outgoing stanza | `<unavailable type="view_once">` — a different node seen on the receive/Web side when no ciphertext reached that device |
| `FLAG_SECURE` on the viewer window (screenshot/recording *prevention*) | a screenshot *detection* callback — no such mechanism was found |
| Deletion of the local media *file* after opening | deletion of the message *row* — the row survives, labelled "opened"/"expired" |
| View-once (media wipes after one open) | disappearing messages (whole message removed after a chat-level TTL) — orthogonal, can combine |

---

## 12. Complete flow (view-once photo, 1:1 chat)

```
[Sender]
   │ pick photo, mark "view once" in composer
   │ ImageMessage.viewOnce = true          (flag 8784 on: inline only)
   │ upload via normal media pipeline (WA_MEDIA_UPLOAD.md)
   │ flag 11282 on, type==42 → <meta view_once="true">
   ▼
[Server]  relays the E2E-encrypted stanza; cannot read viewOnce (it's inside the ciphertext)
   │
   ▼
[Receiver]
   │ decrypt → ImageMessage.viewOnce == true, message type 42 (DdP)
   │ INSERT message_view_once_media(message_row_id, state=<initial>)
   │ thumbnail shown in the conversation row; sender-side row asserts "can not view own media"
   │
   ├── user taps to open ──► MediaViewFragment, C1ZB.A0O(42) == true
   │                          → window.addFlags(FLAG_SECURE)
   │                          → forward/share/save menu items hidden (InterfaceC24513Ahd)
   │                          → status reaches 8/9/10 → state = 1 ("opened")
   │                          → window closed, FLAG_SECURE drops with it
   │
   ▼
[EphemeralUpdateRunnable, job type 3]
   │ SELECT ... FROM message_view_once_media JOIN message_media
   │   WHERE from_me=0 AND file_size IS NOT NULL AND state IN (1,2)
   ▼
local media file deleted; row kept, UI shows "View once photo, opened"
```

---

## 13. Unknowns

| Item | State |
|------|-------|
| Named constants for `state` 0 (initial) and the exact meaning shared between 2 (no-row fallback) and "expired" | only 1 ("opened") has a named call site; the rest is inferred from the fallback value and UI strings |
| Status codes 8/9/10 consumed by `C199158dT.A03` to trigger "opened" | not resolved to named constants |
| Retention/cleanup of the **sender's own** copy of sent view-once media | deletion job only targets `from_me = 0`; no corresponding sender-side cleanup found |
| Server-side deletion/marking of the uploaded object after first download | cannot be observed from static client analysis |
| Construction of the `<unavailable type="view_once">` node (client placeholder vs. server-built) | unresolved; carried over from earlier research, not newly resolved here |
| Android consumer of the `view_once="read"/"write"` wire tokens | token presence confirmed in the dictionary table; no call site located |
| Whether `FLAG_SECURE` is applied on every code path that can present view-once content (e.g. notification previews, widget, Wear) | only the `MediaViewFragment` and `ViewOnceViewerActivity` paths were checked |
