# Apple Dev Plugin

Complete iOS/macOS/iPadOS development workflow plugin.

## Self-Contained

This plugin is fully self-contained and does not depend on `vabole/apple-skills`. All external vendor content has been absorbed into `references/external/`. If you previously installed the `apple-skills` plugin, you may uninstall it:

```bash
claude plugin uninstall apple-skills@apple-skills
```

## Install

```bash
/plugin install apple-dev@indie-toolkit
```

For Codex/OpenCode: see `.codex/INSTALL.md` or `.opencode/INSTALL.md`.

## Daily entry points

| Skill | Trigger | Description |
|-------|---------|-------------|
| project-kickoff | `/project-kickoff` | New project feasibility + requirements |
| design-parity-build | `/design-parity-build` | Audit Claude Design ↔ iOS parity, produce classified Gap List, hand off to /write-dev-guide |
| asc-submit-preview | `/asc-submit-preview` | App Review Guidelines pre-check |
| asc-listing | `/asc-listing` | ASC submission material check |

## Called by dev-workflow

These capabilities are usually called by dev-workflow after a plan, phase, or changed surface makes them relevant.

| Skill | Preferred caller | Description |
|-------|------------------|-------------|
| apple-swift-context | Swift/iOS/macOS work | Loads platform-specific rules from reference docs |
| ui-review | dev-workflow review step | SwiftUI UI + interaction compliance review |
| design-review | dev-workflow review step | Visual hierarchy, color, spacing quality review |
| feature-review | dev-workflow review step | Product + UX completeness from user journey perspective |
| code-audit | run-phase / implementation-reviewer | Code quality + security assessment (5 categories) |
| validate-design-tokens | dev-workflow review step | Design token compliance check |
| testing-guide | write-plan / fix-bug / test-changes | Interactive testing guidance |
| profiling | write-plan / fix-bug / test-changes | Performance profiling guidance |
| xc-ui-test | write-plan / test-changes | Advanced XCUITest guidance |

## Full Capability Inventory (23)

| Skill | Route | Description |
|-------|---------|-------------|
| apple-swift-context | Auto (Swift files) | Loads platform-specific rules from reference docs |
| ui-review | dev-workflow review step | SwiftUI UI + interaction compliance review |
| design-review | dev-workflow review step | Visual hierarchy, color, spacing quality review |
| feature-review | dev-workflow review step | Product + UX completeness from user journey perspective |
| audit-finishing-touches | internal route | Mechanical §17–§20 polish-gap scan (border / default-style / undecorated card / hero) |
| code-audit | run-phase / implementation-reviewer | Code quality and security assessment (5 categories) — internal only, not user-invocable |
| validate-design-tokens | dev-workflow review step | Design token compliance check |
| characterization-test | internal route | Behavior-locking tests before refactoring |
| asc-submit-preview | `/asc-submit-preview` | App Review Guidelines pre-check |
| asc-listing | `/asc-listing` | ASC submission material check |
| testing-guide | write-plan / fix-bug / test-changes | Interactive testing guidance |
| profiling | write-plan / fix-bug / test-changes | Performance profiling guidance |
| xc-ui-test | write-plan / test-changes | Advanced XCUITest guidance |
| swiftdata-patterns | internal route | SwiftData best practices guidance |
| localization-setup | internal route | String Catalogs + localization guidance |
| fetch-swift-api-updates | internal route | Fetch latest WWDC API changes |
| generate-design-system | internal route | Generate SwiftUI design system from tokens |
| sync-design-md | internal route | Bidirectional sync between Stitch DESIGN.md and DesignSystem.swift |
| design-parity-build | `/design-parity-build` | Audit Claude Design ↔ iOS parity, produce classified Gap List, hand off to /write-dev-guide |
| generate-stitch-prompts | internal route | Generate UI prompts from requirements |
| project-kickoff | `/project-kickoff` | New project feasibility + requirements |
| setup-ci-cd | `/setup-ci-cd` | Fastlane + GitHub Actions for TestFlight |
| update-asc-docs | `/update-asc-docs` | Audit and update ASC legal/marketing documents |

## Agents (4)

| Agent | Description |
|-------|-------------|
| apple-reviewer | Code review for iOS/macOS Swift projects |
| ui-reviewer | UI + UX compliance review (fresh context) |
| design-reviewer | Visual quality review (fresh context) |
| feature-reviewer | Product completeness review (fresh context) |

## Hooks

| Hook | Event | Purpose |
|------|-------|---------|
| protect-pbxproj | PreToolUse | Prevents direct editing of `.xcodeproj/project.pbxproj` files |

## References (14)

Platform-specific sections are tagged with `platform: iOS` or `platform: macOS`. Sections without a tag apply to both platforms.

| File | Content |
|------|---------|
| apple-swift-rules.md | Swift dev rules (build cycle, concurrency, UI, macOS patterns) |
| apple-ui-checklist.md | UI code compliance checklist (iOS + macOS sections) |
| ui-design-principles.md | Professional UI design principles |
| apple-hig-design-tokens.md | Parameterizable design token system |
| swift-coding-standards.md | Swift naming and code organization |
| swiftdata-guide.md | SwiftData best practices |
| testing-guide.md | Unit test, UI test, TDD |
| profiling-guide.md | OSSignposter, MetricKit, XCTMetric, anti-patterns, Instruments |
| xc-ui-test-guide.md | Advanced XCUITest (flow tests, network stub, snapshot, a11y, CI) |
| localization-guide.md | String Catalogs, pluralization |
| app-review-guidelines.md | Apple App Review Guidelines |
| macos-distribution-guide.md | Notarization, sandboxing, Sparkle |
| swift-api-changes-ios18.md | iOS 18 / WWDC 2024 APIs |
| swift-api-changes-ios26.md | iOS 26 / WWDC 2025 APIs |

## External Vendored References

The following references are vendored from [vabole/apple-skills](https://github.com/vabole/apple-skills) v1.0.10 (MIT License, Copyright 2026 Ilia Abolhasani, vendored 2026-05-14). Full attribution manifest: `references/external/ATTRIBUTION.md`

| Path | Source skill | Content |
|------|-------------|---------|
| `references/external/ios-liquid-glass/` | `skills/ios-liquid-glass/` | 17 files: Liquid Glass API reference, design principles, token patterns |
| `references/external/hig/` | `skills/hig/` | 5 files: HIG layout, typography, color, materials, accessibility |
| `references/external/swiftui-ui-patterns/` | `skills/guide-swiftui-ui-patterns/` | 38 files: SwiftUI UI patterns with Page Object, wait strategy, state holder patterns |
| `references/external/swiftui-view-refactor.md` | `skills/guide-swiftui-view-refactor/` | SwiftUI view refactoring patterns |
| `references/external/swiftui-performance-audit.md` | `skills/guide-swiftui-performance-audit/` | SwiftUI runtime performance audit guide |
| `references/external/swiftui-api/` | `skills/swiftui/` | 13 files: SwiftUI API reference (state, binding, observation, environment, navigation, sheet, list, scroll, chart, form, textfield, picker) |
| `references/external/swift-concurrency-api/` | `skills/swift-concurrency/` | 7 files: Swift Concurrency API reference |
| `references/external/swift-concurrency-patterns.md` | `skills/guide-swift-concurrency/` | Swift Concurrency patterns and best practices |
| `references/external/swift-testing-api/` | `skills/swift-testing/` | 7 files: Swift Testing API reference |
| `references/external/swift-testing-patterns.md` | `skills/guide-swift-testing/` | Swift Testing patterns and agent guidance |
| `references/external/swiftdata-api/` | `skills/swiftdata/` | 4 files: SwiftData API reference |
| `references/external/tipkit/` | `skills/tipkit/` | TipKit API reference |
| `references/external/widgetkit/` | `skills/widgetkit/` | WidgetKit API reference |
| `references/external/usernotifications/` | `skills/usernotifications/` | UserNotifications API reference |
| `references/external/photosui/` | `skills/photosui/` | PhotosUI API reference |
| `references/external/macos-spm-packaging.md` | `skills/guide-macos-spm-packaging/` | macOS SPM packaging guide |
| `references/external/simulator-cheatsheet.md` | `skills/simulator-utils/` | Simulator command cheatsheet |
| `references/external/ios-design-consultant.md` | `skills/ios-design-consultant/` | iOS Design Consultant — Liquid Glass UX |
| `references/external/swiftui-animations.md` | `skills/guide-swiftui-animations/` | SwiftUI animations guide |
| `references/external/swiftui-charts.md` | `skills/guide-swiftui-charts/` | SwiftUI Charts guide |
| `references/aso-guide.md` | `skills/apple-aso/` | ASO (App Store Optimization) guide |
