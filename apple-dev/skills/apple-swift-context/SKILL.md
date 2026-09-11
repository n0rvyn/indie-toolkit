---
name: apple-swift-context
description: "Internal context loader for Apple development rules — build cycle, concurrency, UI patterns, plan-execution principles — read section-targeted from references/apple-swift-rules.md. Not user-invocable; loaded when another skill calls it explicitly (dev-workflow:fix-bug does, for Swift/iOS bugs). NOTE: `paths:` below is a LIMITER, not a trigger — per the official frontmatter reference it only narrows when auto-loading is permitted; relevance routing still decides whether it loads. Measured 2026-08-16: it did not self-trigger on Read, Edit, or Write of a .swift file in 6 headless runs. Write-time rule delivery is handled by the hooks/swift-rule-detectors.py PreToolUse hook instead."
compatibility: Requires macOS and Xcode
user-invocable: false
model: sonnet
context: fork
agent: Explore
paths: ["**/*.swift", "**/Package.swift", "**/*.xcodeproj/**", "**/*.xcworkspace/**"]
---

## Purpose

This is a context loader, not a daily user entry. `dev-workflow` should call it internally when Swift, iOS, macOS, iPadOS, SwiftUI, or SwiftData file markers are present.

Load the relevant sections of `references/apple-swift-rules.md` based on the current task. Do not read the entire file unless the task requires rules from every section.

## Section-Targeted Reading Process

### Step 1: Identify relevant sections

Grep for section markers in the file:

```
Grep("<!-- section:", "references/apple-swift-rules.md")
```

This returns lines like:
```
3:<!-- section: Build-Check-Fix Cycle keywords: build, xcodebuild, check, fix -->
```

### Step 2: Match sections to current task

From the current task description, identify which keyword sets are relevant:

| Task involves | Read section(s) |
|---|---|
| Running builds, checking errors | Build-Check-Fix Cycle |
| Any Swift code (always apply) | 通用约束 |
| async/await, actors, @Model, Sendable | Swift 6 并发原则 |
| Existing foregroundColor calls | .foregroundColor 迁移策略 |
| Creating new UI, layout changes | iOS UI 规则（分层生效） |
| New triggers, data paths, schedulers | 计划阶段架构审查（条件触发） |
| Plan with ≥3 file changes | 计划自检（M&M 测试） |
| Writing a plan | 计划编写原则 |
| Starting execution of a plan | 计划执行原则 |
| Interruption during execution | 计划执行中断处理（必须遵守） |
| User reported a behavior bug | 错误修复原则 |
| Deleting code or variables | 删除代码原则, 死代码/未接入代码处置原则 |
| Working with iOS 18 APIs (@Entry, Tab, MeshGradient, @Previewable) | swift-api-changes-ios18 |
| Working with iOS 26 APIs (glassEffect, FoundationModels) | swift-api-changes-ios26 |
| Seeing deprecation warnings in Xcode | swift-api-changes-ios18 (migration) |
| Using TabView | swift-api-changes-ios18 → TabView Architecture |
| Adding LLM/AI features | swift-api-changes-ios26 → Foundation Models |
| Working with iOS 27 APIs (PKStrokeRecognizer, MetricManager, StateReporting, ContentBuilder) | swift-api-changes-ios27 |
| App fails to launch on iOS 27 / scene life cycle migration | swift-api-changes-ios27 → UIKit |
| Reading any device sensor (光照/气压/磁场/运动/深度/UWB/NFC), or asking "能不能拿到某个物理量" | device-sensor-apis |
| Which Info.plist usage key or entitlement a capability needs | device-sensor-apis → SensorPermissionKeys / SensorGateLadder |
| Enumerating what an API surface offers from local SDK headers | device-sensor-apis → SDKVersionBoundsWhatYouSee |
| Deciding whether an API is available on a platform (any `API_AVAILABLE` / `API_UNAVAILABLE` question) | device-sensor-apis → AvailabilityByCompiler |
| Anything on Apple Watch / watchOS (sensor, HealthKit, complication, workout) | watchos-sensor-apis |
| "这个功能能在表上后台跑多久", WKExtendedRuntimeSession, HKWorkoutSession, 连续采样 | watchos-sensor-apis → WatchSessionBudget |
| High-rate motion on Watch, CMBatchedSensorManager, 800 Hz | watchos-sensor-apis → WatchBatchedSensor |
| Water depth / dive / CMWaterSubmersionManager / Shallow Depth and Pressure | watchos-sensor-apis → WatchSubmersion |
| Digital Crown, double tap, WKHapticType, wrist location, always-on | watchos-sensor-apis → WatchInputOutput |
| "表上有没有 X"（camera, Vision, Speech, NFC, BLE peripheral, BGTaskScheduler） | watchos-sensor-apis → WatchAbsentFrameworks |
| Which Apple Watch model has which sensor | watchos-sensor-apis → WatchModelMatrix |
| Working with watchOS 27 APIs (Vision on Watch, FoundationModels on Watch, HKWorkoutZoneGroup) | watchos-sensor-apis → WatchOS27Delta |
| macOS window, WindowGroup, MenuBarExtra, Settings scene | macOS Window Management |
| macOS menu, commands, CommandMenu, toolbar customization | macOS Menu & Toolbar |
| Keyboard shortcut on macOS, keyboardShortcut | macOS Keyboard Shortcuts |
| NSViewRepresentable, macOS SwiftUI, pasteboard, onHover | macOS SwiftUI Patterns |
| macOS distribution, notarization, Developer ID | macos-distribution-guide |
| macOS sandbox, entitlements, file access permissions | macos-distribution-guide → Sandboxing & Entitlements |
| macOS auto-update, Sparkle | macos-distribution-guide → Auto-Update |

### Step 2.5: Platform-aware section filtering

Section markers may include a `platform:` attribute (e.g., `platform: iOS`, `platform: macOS`). Sections without a `platform:` tag apply to all platforms (shared).

The target platform is determined by which rows matched in Step 2:

- If Step 2 matched any **macOS keyword row** (rows 50-56: WindowGroup, MenuBarExtra, CommandMenu, keyboardShortcut, NSViewRepresentable, notarization, Sparkle) → the task involves macOS. When grepping `apple-swift-rules.md`, also include sections with `platform: macOS`.
- If Step 2 matched any **iOS keyword row** (rows 45-48: iOS 18/26 APIs, TabView, glassEffect) → the task involves iOS. When grepping reference files, also include sections with `platform: iOS`.
- If Step 2 matched any **watchOS keyword row** (any row routing to `watchos-sensor-apis`, or the task mentions Apple Watch / watchOS / complication / workout session / Digital Crown) → the task involves watchOS. When grepping reference files, also include sections with `platform: watchOS`.
- If Step 2 matched **only shared rows** (rows 33-44: build cycle, concurrency, plan rules, bug fix) → load only sections without a `platform:` tag.
- Platforms can be active simultaneously (e.g., a multiplatform project, or a Watch app with an iPhone companion — that one is iOS + watchOS).

⚠️ **watchOS is not a subset of iOS.** Never answer a watchOS question from `platform: iOS` sections: the same
framework has different availability, different permission keys, and different background rules on the two
platforms. `device-sensor-apis.md` is iOS-scoped by its own first line; `watchos-sensor-apis.md` is the
watchOS counterpart. The one section that applies to **both** is `AvailabilityByCompiler` (untagged) —
platform availability is decided by `swiftc -typecheck`, never by reading `API_AVAILABLE` annotations.

### Step 3: Read only the matched sections

For each matched section in `apple-swift-rules.md`, use the line number from the Grep result as
`offset` and read until the next section marker or approximately 60 lines (whichever comes first):

```
Read("references/apple-swift-rules.md", offset=<section_line>, limit=<next_section_line - section_line>)
```

For `swift-api-changes-*` and `macos-distribution-guide.md` files: search for the specific section
keyword rather than reading the entire file. Example:

```
Grep("glassEffect", "references/swift-api-changes-ios26.md")
→ Read("references/swift-api-changes-ios26.md", offset=<section_line>, limit=<lines_to_next_section>)

Grep("notarytool", "references/macos-distribution-guide.md")
→ Read("references/macos-distribution-guide.md", offset=<section_line>, limit=<lines_to_next_section>)
```

If the task is not clearly scoped (e.g., the task description is very broad or covers the whole codebase), read `通用约束` and `Swift 6 并发原则` at minimum — these two sections apply to all Swift work.

### Step 4: Apply the loaded rules

Follow the rules from the loaded sections strictly. Do not infer rules from memory about sections that were not read.

## SwiftUI Correctness Checklist

When reviewing SwiftUI code, run the checklist below. Violations are always bugs.

- [ ] `@State` properties are `private`
- [ ] `@Binding` only where a child needs to mutate parent state
- [ ] Values passed in are never declared as `@State` — they silently ignore updates
- [ ] Use `@State` with `@Observable` classes — not `@StateObject` or `ObservableObject`
- [ ] Use `@Bindable` for injected observables that need bindings
- [ ] `ForEach` uses stable identity — never `.indices` on dynamic content
- [ ] Each `ForEach` element produces a constant number of views
- [ ] `.animation(_:value:)` always includes the `value:` parameter
- [ ] `@FocusState` properties are `private`
- [ ] `@Observable` classes are `@MainActor` — Swift 6 strict concurrency requires it
- [ ] Property wrappers (`@AppStorage`, `@SceneStorage`, `@Query`) inside `@Observable` classes are marked `@ObservationIgnored`
- [ ] No business logic in `body` — use `.task`, `.onChange`, or methods
- [ ] No `AnyView` unless truly unavoidable — fix with better composition

Source: `references/apple-swift-rules.md` → SwiftUI Correctness Checklist

## Topic Router (Local References)

For Apple framework API details NOT covered by `references/apple-swift-rules.md`, grep the matching local reference under `apple-dev/references/external/` first. If unsure which reference applies, read `apple-dev/references/apple-swift-rules.md` → SwiftUI Correctness Checklist and Topic Router.

| Topic | Guide | API Reference |
|---|---|---|
| State management | `external/swiftui-ui-patterns/` | `external/swiftui-api/state.md`, `binding.md`, `observation.md`, `environment.md` |
| View composition | `external/swiftui-view-refactor.md` | — |
| Performance | `external/swiftui-performance-audit.md`, `profiling-guide.md` (os_signpost / MetricKit / Instruments / XCTMetric) | — |
| Navigation | `external/swiftui-ui-patterns/` | `external/swiftui-api/navigationstack.md`, `navigationsplitview.md` |
| Sheets & modals | `external/swiftui-ui-patterns/` | `external/swiftui-api/sheet.md` |
| Lists & ForEach | `external/swiftui-ui-patterns/` | `external/swiftui-api/list.md` |
| ScrollView | `external/swiftui-ui-patterns/` | `external/swiftui-api/scrollview.md` |
| Forms & input | — | `external/swiftui-api/form.md`, `textfield.md`, `picker.md` |
| Charts | `external/swiftui-charts.md` | `external/swiftui-api/chart.md` |
| Animations | `external/swiftui-animations.md` | — |
| Liquid Glass | `external/ios-design-consultant.md` | `external/ios-liquid-glass/` |
| Visual design | `external/ios-design-consultant.md`, `ui-design-principles.md` (§17 深度层级 / §18 图片 / §19 收尾打磨 / §20 层级战术) | `external/hig/` |
| Accessibility | — | `external/hig/accessibility.md` |
| macOS apps | `external/macos-spm-packaging.md` | — |
| Data persistence | `swiftdata-guide.md` (含 Community Patterns 节) | `external/swiftdata-api/` |
| Testing | `external/swift-testing-patterns.md`, `testing-guide.md` (UT/UI 模式、Page Object、等待策略、mock、覆盖率) | `external/swift-testing-api/`, `xc-ui-test-guide.md` (E2E / 打桩 / 快照回归 / a11y 审计 / CI) |
| Localization | `localization-guide.md` (String Catalogs / 复数规则 / 变量处理) | — |
| Concurrency | `external/swift-concurrency-patterns.md` | `external/swift-concurrency-api/` |
| Widgets | — | `external/widgetkit/` |
| Tips | — | `external/tipkit/` |
| Notifications | — | `external/usernotifications/` |
| Photos | — | `external/photosui/` |
| App Store metadata | `aso-guide.md` | — |
| Simulator commands | `external/simulator-cheatsheet.md` | — |

For dropped topics (UIKit, Combine, MapKit, HealthKit, StoreKit, etc.): grep Apple online documentation at https://developer.apple.com/documentation or use WebSearch.
