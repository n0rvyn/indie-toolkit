---
name: apple-swift-context
description: "Internal context loader auto-injected when editing Swift / iOS / macOS / iPadOS / SwiftUI / SwiftData files (paths trigger). Provides Apple development rules — build cycle, concurrency, UI patterns, plan-execution principles — loaded section-targeted by current task. Not user-invocable (called by dev-workflow:fix-bug, run-phase, etc.)."
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
| Seeing deprecation warnings in Xcode | swift-api-changes-ios18 (migration), validate-design-tokens |
| Using TabView | swift-api-changes-ios18 → TabView Architecture |
| Adding LLM/AI features | swift-api-changes-ios26 → Foundation Models |
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
- If Step 2 matched **only shared rows** (rows 33-44: build cycle, concurrency, plan rules, bug fix) → load only sections without a `platform:` tag.
- Both platforms can be active simultaneously (e.g., a multiplatform project).

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
| Performance | `external/swiftui-performance-audit.md` | — |
| Navigation | `external/swiftui-ui-patterns/` | `external/swiftui-api/navigationstack.md`, `navigationsplitview.md` |
| Sheets & modals | `external/swiftui-ui-patterns/` | `external/swiftui-api/sheet.md` |
| Lists & ForEach | `external/swiftui-ui-patterns/` | `external/swiftui-api/list.md` |
| ScrollView | `external/swiftui-ui-patterns/` | `external/swiftui-api/scrollview.md` |
| Forms & input | — | `external/swiftui-api/form.md`, `textfield.md`, `picker.md` |
| Charts | `external/swiftui-charts.md` | `external/swiftui-api/chart.md` |
| Animations | `external/swiftui-animations.md` | — |
| Liquid Glass | `external/ios-design-consultant.md` | `external/ios-liquid-glass/` |
| Visual design | `external/ios-design-consultant.md` | `external/hig/` |
| Accessibility | — | `external/hig/accessibility.md` |
| macOS apps | `external/macos-spm-packaging.md` | — |
| Data persistence | `swiftdata-guide.md` (含 Community Patterns 节) | `external/swiftdata-api/` |
| Testing | `external/swift-testing-patterns.md` | `external/swift-testing-api/`, `xc-ui-test-guide.md` |
| Concurrency | `external/swift-concurrency-patterns.md` | `external/swift-concurrency-api/` |
| Widgets | — | `external/widgetkit/` |
| Tips | — | `external/tipkit/` |
| Notifications | — | `external/usernotifications/` |
| Photos | — | `external/photosui/` |
| App Store metadata | `aso-guide.md` | — |
| Simulator commands | `external/simulator-cheatsheet.md` | — |

For dropped topics (UIKit, Combine, MapKit, HealthKit, StoreKit, etc.): grep Apple online documentation at https://developer.apple.com/documentation or use WebSearch.
