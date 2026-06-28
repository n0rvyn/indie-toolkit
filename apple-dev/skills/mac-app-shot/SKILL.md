---
name: mac-app-shot
model: sonnet
compatibility: Requires macOS and Xcode
description: "Use when you need to VISUALLY verify a running macOS GUI app from the CLI: capture just ONE app window (not the whole screen) by its window id, optionally drive the app via clicks + keystrokes, and read the PNG with the Read tool to check layout / style / behavior empirically. Covers the edit → rebuild → relaunch → screenshot loop for verifying UI or code changes, and a fallback for snapshotting a single SwiftUI view in a sandboxed app (ImageRenderer + base64-over-stdout). Triggers: 'screenshot the app', 'verify the UI', 'check the layout/style', 'screenshot-verify', visual QA of a Mac app, '截图验证', '看一下界面', '对着图改', '取 app 的截图'. NOT for: full-screen captures, web pages (use a browser/WebFetch tool), or unit/logic tests (those never show layout)."
---

## What this is

A loop for verifying a **running macOS app's actual rendered UI** — the only way to catch "the editor is a gradient block", "the buttons render as centered pills", "this row is clipped at the bottom" that `BUILD SUCCEEDED` + green unit tests never reveal. Builds and tests pass while the UI is broken; **read the pixels.**

Core moves: (1) capture one window **by id**, (2) **Read** the PNG, (3) **drive** the app with clicks/keystrokes when you need a specific state, (4) **iterate**: edit code → rebuild → relaunch → capture → review.

## Prerequisites (one-time, per machine)

- The controlling terminal needs **Accessibility** (osascript System-Events keystrokes + clicks) and **Screen Recording** (so `screencapture` sees window *content*, not a black/desktop image). If a capture comes back blank or shows only the desktop, grant Screen Recording to the terminal in System Settings → Privacy & Security.
- `swift` available (Xcode) — the window-list + click helpers use CoreGraphics; the system `python3` lacks the `Quartz` module.

## 1. Capture a specific window (works even when occluded)

`${CLAUDE_PLUGIN_ROOT}/skills/mac-app-shot/scripts/winlist.swift <AppOwnerName>` prints `<id> layer=<n> <W>x<H> <owner>` per on-screen window. Take the main one (`layer=0`, largest):

```
id=$(swift ${CLAUDE_PLUGIN_ROOT}/skills/mac-app-shot/scripts/winlist.swift Halcyon | awk '$2=="layer=0"{print $1; exit}')
screencapture -x -o -l "$id" out.png      # -l = by window id · -o no shadow · -x silent
```
Then `Read out.png`. **`-l <id>` captures THAT window even when other windows cover it** — unlike `-R x,y,w,h`, which grabs the screen region (= whatever is frontmost there; you'll capture your own terminal).

## 2. Drive the app (clicks + keystrokes)

- Window bounds (for click math): `osascript -e 'tell application "System Events" to tell process "<App>" to get {position, size} of front window'` → `x, y, w, h` (points). A point `(px,py)` inside the window is screen `(x+px, y+py)`.
- Click: `swift ${CLAUDE_PLUGIN_ROOT}/skills/mac-app-shot/scripts/click.swift <screenX> <screenY>` (posts a CGEvent left click).
- Type: `osascript -e 'tell application "System Events" to keystroke "text"'`. Special keys: `key code 125 using command down` (⌘↓ = end of document), `keystroke "l" using {command down, shift down}`, etc.
- **Focus a text view by clicking ON the text, not the margin.** Verify focus by typing a marker and re-capturing before trusting a long type.
- **After a navigating click (opens a list/menu/card wall), screenshot + Read BEFORE the next click** — positions shift (e.g. project/card walls re-sort by recency, so the same slot is a different item).
- Foreground `sleep` may be blocked; wait with `osascript -e 'delay N'`.
- `cliclick` (if installed) is a fine alternative clicker/typer: `cliclick c:<x>,<y>` (click), `cliclick t:"ascii"` (type), `cliclick kd:cmd t:v ku:cmd` (⌘V). Coordinates are screen **points**, same as `click.swift`.

### 2a. Precise coordinates & robust input (hard-won — small targets need this)

Eyeballing a target's location from a downscaled full screenshot misses small buttons. Two reliable techniques:

- **Retina math.** A `-l <id>` capture is at the display's backing scale (commonly **2×**). Confirm: `scale = capturePNGwidth / windowPointWidth`. Then a feature at PNG pixel `(px,py)` is screen point `= (windowOriginX + px/scale, windowOriginY + py/scale)`. (Window origin from §2's `position`.)
- **Crop-and-zoom to read exact pixels.** For a small/ambiguous target, crop the full-res PNG to a tight region and Read THAT (zoomed), instead of guessing from the whole frame:
  ```python
  from PIL import Image
  Image.open('out.png').crop((x0,y0,x1,y1)).resize((W*2,H*2)).save('crop.png')   # then Read crop.png
  ```
  Read the target's pixel inside the crop, add back the crop origin, then apply Retina math. This turned "my clicks keep missing" into one-shot hits.
- **Locate a control by COLOR** (distinctive primary/accent/✓/✗ buttons): scan the PNG for the button's RGB signature and take the blob centroid → screen point.
  ```python
  # purple primary button: high R&B, low G; tight search band to avoid same-color TEXT/underlines
  for Y in range(y0,y1):
    for X in range(x0,x1):
      r,g,b = im.getpixel((X,Y))
      if b>150 and r>110 and g<r-15 and b>g+40: ...  # collect, then centroid
  ```
  Watch out: same-color text/underlines contaminate the bbox — constrain the search band and verify with a tight crop before clicking.
- **CJK / non-ASCII input: paste, don't type.** `cliclick t:` and synthetic keystrokes mangle CJK. Set the clipboard then paste: `printf '%s' "中文内容" | pbcopy` → click the field → `cliclick kd:cmd t:v ku:cmd`.
- **Submit often needs the button, not Return.** Chat/compose fields frequently ignore `Return` (it inserts a newline) — click the send/submit control. Verify text landed by cropping the field before submitting.
- **Verify a clipboard-copy worked with `pbpaste`** (set a sentinel first: `printf SENTINEL | pbcopy`, click Copy, then `pbpaste` ≠ SENTINEL).

## 3. The edit → rebuild → relaunch → screenshot loop

`${CLAUDE_PLUGIN_ROOT}/skills/mac-app-shot/scripts/shoot.sh <AppPath.app> <out.png> [ENV=val ...]` quits the app, relaunches the **binary** (so launch env vars apply — e.g. a mock provider), activates it, captures the main window. Run `xcodebuild build` first so the relaunched `.app` has your change.

Relaunch the **binary directly**, not `open`: a single-instance app just reactivates the stale copy, and `open` can't pass env vars. Example: `zsh ${CLAUDE_PLUGIN_ROOT}/skills/mac-app-shot/scripts/shoot.sh /path/MyApp.app shot.png HL_USE_MOCK_AI=1`.

## 4. Fallback: snapshot ONE SwiftUI view (sandboxed app)

When the app is sandboxed and you only need one view rendered (not the live app), add a temporary `@MainActor @Test` that builds the view with mock data, renders it via `ImageRenderer` (`renderer.nsImage` → PNG), and **base64-prints the PNG to stdout** (the sandbox blocks writing anywhere external tools can read, including `/tmp` and its own container). Decode outside (`base64 -d` / `python3 base64`), Read it, then delete the harness.

⚠️ `ImageRenderer` can NOT rasterize `List` / `NavigationSplitView` / `HSplitView` / `VSplitView` (AppKit NSView-backed) — it emits a "missing content" placeholder. Use the live-app capture (§1–3) for those.

## 5. MOST reliable for driving + populating: XCUITest

When the app has accessibility identifiers and a `*UITests` target, prefer XCUITest over §2 clicks/keystrokes — it finds elements by **id** (no pixel guessing), types into fields, and clicks buttons robustly. A throwaway `XCTestCase` can create projects, type content, navigate, and screenshot each view:
- Drive: `app.buttons["toolbar.new"].firstMatch.click()`, `app.textFields["id"].typeText(...)`, `app.descendants(matching: .any).matching(NSPredicate(format: "identifier == %@", id)).firstMatch`. **Use `.firstMatch` everywhere** — ids often resolve to multiple elements (a bare `.click()` errors "Multiple matching elements").
- Window-only shot: `app.windows.firstMatch.screenshot()` — `app.screenshot()` grabs the WHOLE screen on macOS.
- Capture via **attachment**, not a file: `let a = XCTAttachment(screenshot: s); a.name = "01-view"; a.lifetime = .keepAlways; add(a)`. The sandboxed test runner can't write where the host reads (its `/tmp` is denied; its container is TCC-locked), so writing PNGs silently fails — attach instead.
- Run: `xcodebuild test -only-testing:<Target>/<Class>[/<method>]`. **UI tests need a live GUI session** (they hang/timeout headless — that's the usual "UI E2E gated").
- Extract on the host: `xcrun xcresulttool export attachments --path <newest .xcresult under DerivedData/.../Logs/Test> --output-path <dir>`, then Read the PNGs (`manifest.json` maps hashed filenames → your `attachment.name`).
- Known limits: applying formatting via toolbar buttons (e.g. H1) may not take even with the line selected — content stays plain; markdown auto-shortcuts never fire on synthetic input. Delete the throwaway test after.

## Hard rules
- Capture by **window id** (`-l`), never `-R`, for a specific app window.
- **Read the PNG** — never assume from a green build.
- One click → one screenshot when navigating; don't chain blind clicks.
- Clean up temp PNGs + any throwaway test harness when done.
