---
name: runtime-feature-verify
model: sonnet
compatibility: Requires macOS and Xcode
description: "Use to verify a running app's FEATURES actually WORK end-to-end — drive each feature's real action and judge it by a REAL (non-mock) signal (clipboard / on-screen result / state change / persistence-after-reopen / real-LLM output / app log), then produce a feature→judge→evidence→verdict table. This is the BEHAVIOR/FUNCTION counterpart to swiftui-visual-audit (which is per-View RENDER). Use when the user wants: 'verify each feature actually works at runtime', 'real e2e, not mock', 'does the app actually do X', 'prove the features work end-to-end', 'verify it works for real not mock', '逐 feature 验一遍', '运行时验功能不是 mock', 'real runtime e2e 验证是否 work', '一个个功能验过去'. Catches the bug class that green tests + mocks structurally HIDE: silent network/entitlement failures, the wrong model/param sent to a provider, parse/encode that only breaks on real data, an accept that updates the count but not the view. NOT for: per-View look/render audit (use swiftui-visual-audit), capturing/driving ONE window (use mac-app-shot), code/diff review (dev-workflow reviewers), or pure logic unit tests."
---

# Runtime Feature Verify — does each feature actually WORK (not just render, not just mock)

The **behavior/function** sibling of `swiftui-visual-audit`. Two orthogonal axes of verification — don't conflate them:

| | **look** (render) | **behavior** (function) |
|---|---|---|
| per **View** | `swiftui-visual-audit` (screenshot every View, score vs rubric) | — |
| per **Feature** | — | **this skill** |
| one window (primitive) | `mac-app-shot` (capture + drive one window) | ← this skill borrows its driving |

**Why it earns its keep:** `BUILD SUCCEEDED` + green unit tests + a clean screenshot can ALL pass while a feature is silently broken — because the mock replaces the exact thing that fails. Real cases this caught (one app, one run): a sandbox missing a network entitlement so EVERY real provider call failed silently (mock-only tests stayed green); a Settings "Test connection" button hard-coding the wrong model so it 400'd on every non-default provider; an "Accept AI draft" that updated the word count but never re-rendered the editor. A screenshot can't judge any of these — you must **drive the real action and check a real RESULT**.

## The core move: per feature, pick a JUDGE SIGNAL a screenshot can't fake

A render audit asks "does it look right?" — eyeball the pixels. A behavior audit asks "did it DO the right thing?" — and for most features the answer lives in a signal the screenshot can't show. Before driving anything, map each feature to its judge:

| Feature shape | Real judge signal (how you prove it WORKED) |
|---|---|
| Copy / export to clipboard | `pbpaste` returns the expected payload (set a sentinel first; assert it changed) |
| Save / persist | reopen the app (or switch+return to the item) → data is there |
| AI / network round-trip | streamed text appears on screen **AND** an app call-log / network entry; a real-LLM reply that the **mock can't produce** (e.g. mock returns English "mock reply" → a Chinese reply proves the live model) |
| Accept / reject / stage-not-commit | the content actually lands (count + the rendered text) / reverts; not just that a button was clicked |
| Counter / metric / status | crop the status bar and read the number; compare before/after the action |
| Routing / config respected | the call actually went to the configured target (log entry / endpoint), not the default |
| Write that should be visible | drive the action, then `⌘A` (select-all) — if nothing selects, the text isn't really in the editable surface even when a count says it is |

If a feature's only available judge is "the unit test passes", that's **logic-verified, not runtime-verified** — say so (see taxonomy). The user asked for *not mock*; honor it.

## Workflow

1. **Inventory MAIN features** (exclude trivial theming/color toggles). Group into batches by the state each needs (which content type / mode / screen). Delegating the inventory to a read-only sub-agent is fine; spot-verify its identifiers/flags before relying on them.
2. **Foundation-gate FIRST** (the real-dependency rule). Before trusting ANY verdict in a dependency class (AI, network, DB, IPC), prove **one** real round-trip end-to-end through the *running* app. If that fails, every feature in that class is a false negative and fixing the dependency is the real first task — don't audit on top of a broken floor.
3. **Map each feature → judge signal** (table above). This is the design step; do it before driving.
4. **Drive + verify in batches** (`mac-app-shot` for the how). Inject real dependencies, not mocks (env hooks like `HL_E2E_REAL_PROVIDER`/key/host). Capture the judge evidence per feature.
5. **Honest verdict table** — `feature | how judged | evidence | verdict`, with the taxonomy below. Don't let "logic-verified" masquerade as "it works."
6. **On any bug where the screen shows wrong data: run the discriminator** (below) before you report severity.

## Verdict taxonomy (be honest about what's actually PROVEN)

- **✅ runtime** — drove the real action, a real judge signal confirmed it (screenshot of result / clipboard / state / persistence).
- **✅ real-dep** — confirmed against the live dependency (real LLM / real API), not a mock.
- **🟩 logic-only** — a real (non-mock) unit test proves the *logic*, but the runtime GUI/dep path was not exercised. **Fine for pure-logic features** (encoders, formatters, scanners) — do NOT screenshot-verify those. NOT fine as the sole evidence for a GUI or AI feature (that's the mock the user distrusts).
- **⚪ not-reached** — couldn't drive it this run (e.g. a control synthetic input can't reach). State it; don't imply coverage.

The whole point is that the gap between "🟩 logic-only" and "✅ runtime" is exactly where mock-masked bugs live.

## Severity discriminator (don't headline the scarier reading)

When the screen shows wrong data after an action (e.g. count says 115 words but the editor looks empty), you have two very different bugs and must distinguish them BEFORE reporting:
- **(a) view didn't refresh — data SAFE**: force a reload (switch to another item and back / reopen) → if the data appears, it's a view-refresh bug. Note: clicking the *already-active* item does NOT force a reload — switch away and back.
- **(b) data lost**: still gone after a real reload.
Run the decisive check; report (a) as medium/data-safe, (b) as high. Add caveats for anything non-clean in the repro (test affordance used, confused model reply, multiple clicks).

## Gotchas (hard-won)

1. **Mock masks the failure you're hunting.** If a feature is verified only with the mock provider/stub, you have NOT verified the thing that breaks in production. Inject the real dependency.
2. **XCUITest "automation mode" can be TCC-blocked** (`Timed out while enabling automation mode`) on a headless/CLI session — a one-time GUI permission grant fixes it. When it's blocked, fall back to `mac-app-shot` CLI driving (`screencapture -l` + clicks); when it's granted, the journey suites + `swiftui-visual-audit` are the higher-fidelity path. **Note both up front so the user can unblock it.**
3. **Synthetic input can't reach every control.** New-project *cards* and toolbar-style *tabs* (SwiftUI/AppKit) often ignore `cliclick`/synthetic keystrokes — they need real-HID or XCUITest AX actions. Don't burn attempts; add a **test-only, env-gated navigation affordance** that reaches the state via the SAME production function the UI uses (e.g. `HL_E2E_NEW_PROJECT_TEMPLATE=<type>` → call the real `create(...)`). Pure navigation (reach the state), never behavior-stubbing.
4. **Reasoning/streaming models manufacture false negatives.** A reasoning LLM emits an empty stream while thinking, then the answer; a screenshot on a short fixed timer (or a tiny `max_tokens`) reads as "broken." Poll for the post-reasoning result; give adequate tokens.
5. **A green suite with a couple of reds — classify, don't hand-wave.** For each red: caused by your change (fix it) / pre-existing in your blast radius (fix or file) / pre-existing outside it (keep, cite file:line). "flaky/pre-existing" without evidence is how real regressions ship.
6. **Extract harness screenshots from `.xcresult`**: `xcrun xcresulttool export attachments --path <newest .xcresult> --output-path <dir>`; `manifest.json` maps `suggestedHumanReadableName` → hashed file.

## Cross-platform
The axis (per-Feature × behavior) and the judge-signal discipline are platform-agnostic; only the driving surface differs (macOS CLI capture+drive vs iOS simulator XCUITest). Pair with `mac-app-shot` (driving) and `swiftui-visual-audit` (the render-axis counterpart).

## Deliverable
A `feature → how-judged → evidence → verdict` table (markdown), evidence screenshots/log snippets saved durably, and — when the literal tool the user named doesn't fit (e.g. `/write-dev-guide` for verifying an already-built app) — say so and run the verification campaign instead, rather than silently swapping.
