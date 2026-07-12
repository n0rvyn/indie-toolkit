---
name: swiftui-visual-audit
model: sonnet
compatibility: Requires macOS and Xcode
description: "Systematically screenshot EVERY View / Sheet / Modal / sub-view of a SwiftUI app — macOS AND iOS (incl. iPad on the simulator or a real device) — in BOTH light and dark via a throwaway XCUITest harness, then score each render against a general UI rubric (pairs with the refactoring-ui skill) to produce a gap-by-View list + a gap-driven fix plan. Use when the user wants to: 'audit the whole UI with screenshots', 'screenshot every screen/View', 'screenshot every iOS screen in light/dark on device', 'force dark with -appearanceMode and audit', '截图审计每个界面', '逐 View 看图对标', '每个 View 都 XCTest 看图', 'iPad 真机逐屏 light/dark 截图', '用 -appearanceMode 强制外观做暗色审计'. Catches the bug class that BUILD-green + unit tests structurally CANNOT: untranslated raw localization keys, dead controls, layout truncation, and crashes in panes no test ever opens. NOT for design fidelity — it has no design contract and no reference image, so it cannot tell you whether a screen matches its design; for that, use apple-dev:design-parity-build with the design-detectors. NOT for: capturing/driving ONE window or screen (use mac-app-shot); the rubric/standard itself (use refactoring-ui); pure logic tests."
---

# SwiftUI Visual Audit — every View, light + dark (macOS + iOS)

A repeatable workflow to **render-verify an entire SwiftUI app** against a UI standard, on **either platform**. It sits on top of two primitives: **`mac-app-shot`** (how to capture a window / drive a macOS app) and **`refactoring-ui`** (the quantified rubric to score against). This skill is the orchestration neither covers: *systematic per-View capture in both appearances → score → gap-by-View → gap-driven fix plan.*

**Why it earns its keep:** a green build and passing unit tests cannot see a `layout.panel.header` raw key rendered as text, a Color-scheme picker that does nothing, a status bar truncated to `0 c…`, or a crash in Settings → Sync that no test ever navigates to. The only way to catch these is to open every View and read the pixels. In one real run this surfaced **2 shipping-blocker crashes + ~31 raw localization keys + 2 dead controls** that 12 phases of code review and a full E2E suite had missed.

## Step 0: Detect platform — pick a profile BEFORE writing the harness

The pipeline below is platform-agnostic; the **capture surface, appearance forcing, navigation model, run destination, and crash diagnosis differ by platform**. Decide first:

- `xcodebuild -showdestinations -scheme <X>` (or check the target's `SUPPORTED_PLATFORMS` / the `.xcodeproj` SDK).
- macOS destination → use **`### macOS`** profile.
- iOS destination → use **`### iOS`** profile. Within iOS, pick **simulator** (fast, codesign-free) or **real device** (when the project's test SOP requires it, or you're auditing device-only behavior); the iOS profile covers both.
- **Multiplatform / Catalyst** (both macOS + iOS listed): do NOT guess — ask the user which platform to audit (or run both and emit one gap list each).

## Workflow (platform-agnostic)

1. **Inventory** every `struct: View` (+ `.sheet`/`.popover`/`.alert`/sub-views). Group by the runtime STATE each needs (which content type/project, which mode/tab) — these groups become test "areas".
2. **Throwaway XCUITest harness** (`AuditShotTests`) — one test method per area. For each View: navigate by accessibility id, take a screenshot via the **profile's capture call** (macOS = window element; iOS = `app.screenshot()`) → `XCTAttachment(.keepAlways)` with a descriptive name. Loop appearances.
3. **Extract**: `xcrun xcresulttool export attachments --path <newest .xcresult> --output-path <dir>`; the `manifest.json` maps `suggestedHumanReadableName` → hashed file. Rename + **Read** the PNGs. (Same on both platforms.)
4. **Score** each render against the rubric (refactoring-ui Part B: H/S/T/C/D/F). Record a gap list **ordered by View**, severity-tagged. For large sets (~60+ shots), dispatch reader sub-agents over batches to keep main context lean — then spot-verify any high-density finding yourself (agent claim ≠ fact).
5. **Gap-driven fix plan**: when the audit finds most Views already compliant (common after a code pass), do **not** write one no-op phase per View — write **one phase per real gap cluster** + a final re-screenshot verify phase. (Don't manufacture empty phases; don't shrink scope either — every gap gets fixed.)

### Navigation primitives (both platforms)
- Navigate by `.accessibilityIdentifier`. Add ids to the real navigation handles (tab buttons, card triggers, sheet openers, onboarding next/option). **Keep these ids in the production Views** after the audit — only the `AuditShotTests` harness is throwaway.
- A11y ids can resolve to **multiple elements** → `.firstMatch`. A tall panel / long scroll can push a target **out of hit-range** → guard `.isHittable`, **skip-don't-abort** so one missing element doesn't kill the run (or the other appearance).
- **Capturing populated vs idle states**: a mock/stub provider populates *some* result cards (e.g. draft variants) but not *structured* ones (findings/claims need real JSON). Capture idle/empty states now; defer populated overlays (inline-AI menus, staged edits, margin cards) to targeted-state runs. (App-domain, not platform-specific.)

## Forcing light/dark (platform-neutral core + per-platform note)

**Core mechanism (both platforms):** add a tiny **env-gated `.preferredColorScheme`** hook on every scene root (`WindowGroup` + `Settings` + any aux `Window`):
```swift
static var auditColorScheme: ColorScheme? {
  switch ProcessInfo.processInfo.environment["AUDIT_APPEARANCE"]?.lowercased() {
  case "light": return .light; case "dark": return .dark; default: return nil } }
```
Drive it from the test's `launchEnvironment`. Zero effect on normal runs. **If the app ALREADY has an appearance setting** (e.g. `@AppStorage("appearanceMode")` driving `.preferredColorScheme`), you don't need a new hook — inject its key via `launchArguments` (`-appearanceMode dark`, parsed into UserDefaults via NSArgumentDomain). **Bonus:** wiring the audit through the app's real Color-scheme setting also exercises (and can fix) a dead control. **Precedence:** the audit override must win over the user setting (audit env first, else user setting).

- **macOS note:** `-AppleInterfaceStyle Light` is a **NO-OP** (only `Dark` forces dark; `Light` falls through to system) — you MUST use the env-gated `.preferredColorScheme` hook above.
- **iOS note:** the `@AppStorage` + `launchArguments` route works directly; no `-AppleInterfaceStyle` needed. Watch orientation (see iOS profile — iPad defaults landscape and rotates screenshots).

## Platform profiles

### macOS

Harness shape (adapt the navigation per app):
```swift
final class AuditShotTests: XCTestCase {
    let appearances = ["Dark", "Light"]
    func launch(_ mode: String) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchEnvironment = ["HL_USE_MOCK_AI": "1", "AUDIT_APPEARANCE": mode]   // see Forcing light/dark
        app.launchArguments = ["-uiTestFreshLaunch", "1", "-ApplePersistenceIgnoreState", "YES"]
        app.launch(); _ = app.windows.firstMatch.waitForExistence(timeout: 20); return app
    }
    func shoot(_ app: XCUIApplication, _ name: String) {
        let a = XCTAttachment(screenshot: app.windows.firstMatch.screenshot())   // WINDOW element, not screen
        a.name = name; a.lifetime = .keepAlways; add(a)
    }
    func el(_ app: XCUIApplication, _ id: String) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: "identifier == %@", id)).firstMatch
    }
    // one method per area; loop `appearances`; navigate by id; shoot() at each View.
}
```
Run: `xcodebuild test -scheme <X> -destination 'platform=macOS' -only-testing:<UITests>/AuditShotTests -parallel-testing-enabled NO`. (UI tests need a live Aqua/GUI session; they time out headless.)

macOS gotchas:
- **Settings / separate-scene windows:**
  - The toolbar-style Settings window **resizes per pane** → never identify it by width.
  - `app.windows.element(boundBy: 0)` = the frontmost (Settings) window while it's open. `XCUIScreen.main.screenshot()` grabs the **wrong display** (often your terminal) — always screenshot a **window element**, never the screen.
  - **Navigating** between settings panes can trip a flaky SwiftUI window-activation **SIGILL** (`_assertionFailure` deep in SwiftUICore, no app frames). Fix: add an env-gated **initial-section** hook (`@State private var selected = SettingsSection(rawValue: env) ?? .default`) and launch **once per pane** to open it DIRECTLY — no navigation, no crash.
- **Crash root cause is in STDERR, not the `.ips`**: the SwiftUI `fatalError` reason (e.g. `No Observable object of type WorkspaceState found` — a missing `@Environment` injection) is printed to stderr. Reproduce by launching the **binary** with `2>/tmp/err.log` and grep it. The `.ips` only has the (often app-frame-less) stack + signal.

### iOS

Hard-won on iPad real-device (works on simulator too). Harness shape:
```swift
final class AuditShotTests: XCTestCase {
    let appearances = ["dark", "light"]
    func launch(_ mode: String) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchEnvironment = ["UITEST_MODE": "1" /* + app's seed/userId env */]
        app.launchArguments = ["-appearanceMode", mode,            // app's @AppStorage appearance key
                               "-ApplePersistenceIgnoreState", "YES"]
        app.launch()
        XCUIDevice.shared.orientation = .portrait                  // iPad defaults landscape → else screenshots rotate 90°
        return app
    }
    func shoot(_ app: XCUIApplication, _ name: String) {
        let a = XCTAttachment(screenshot: app.screenshot())        // WHOLE SCREEN (single window), not a window element
        a.name = name; a.lifetime = .keepAlways; add(a)
    }
}
```
Run — pick destination:
- Simulator: `xcodebuild test -scheme <X> -destination 'platform=iOS Simulator,id=<UDID>' -only-testing:<UITests>/AuditShotTests`
- Real device (when SOP requires): `... -destination 'platform=iOS,id=<UDID>' -allowProvisioningUpdates`. Get the hardware UDID from `xcrun xctrace list devices`.

iOS gotchas:
- **Force portrait** (above) for phone-first designs — without it iPad runs land in landscape and every screenshot is rotated 90°.
- **Real-device relaunch instability**: rapid `terminate`/relaunch trips a `devicectl diagnose` stall mid-run. For deep pages that need a fresh nav path, use **one fresh `launch()` per screen + a `sleep(2)` settle between launches** (let the new `XCUIApplication().launch()` auto-terminate the previous; don't chain `goBack` across many screens in one method).
- **Deep-scroll `isHittable` false-positive**: XCUITest reports an off-screen, deeply-scrolled card as `isHittable` → a tap "lands" but does nothing, and you capture the parent screen instead of the pushed page. Fix: in your tap helper, **drop the coordinate-fallback** (it mis-taps), `swipeUp` to reveal then tap **only if `isHittable`**; if still flaky, fall back to **label navigation** (`label CONTAINS "…"` predicate + swipe-until-hittable — proven to reach deep cards).
- **Back / pop fragility**: a custom tab bar may pop its NavigationStack only on specific re-taps (e.g. re-tapping the Home tab posts `.resetHomeTab`; other tabs don't pop). Screens that hide the nav bar have no system back button. Prefer **fresh launch per screen** over `goBack` to avoid this entirely.
- **Crash diagnosis (real device)**: pull crash reports with `idevicecrashreport -e -k /tmp/crashes`, then read the `.ips` **triggered-thread stack** (JSON 2nd line → `threads[].triggered` frames). This shows e.g. `<Repository>.<method>` ← `closure #N in <caller>` ← `completeTaskWithClosure`, pinpointing a leaked async call. (Contrast macOS: read stderr.) Get the stack BEFORE forming a hypothesis.

## Clean-up
The `AuditShotTests` harness is throwaway — regenerate it per app from the matching profile. Delete the test file when the audit closes. **Keep** the env hooks gated and harmless (or strip them) — but **keep** any appearance/accent hook you wired through to a real setting, AND **keep** the `.accessibilityIdentifier`s you added to production Views (later UITests reuse them).
