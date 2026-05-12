# Apple Dev Plugin

Complete iOS/macOS/iPadOS development workflow plugin.

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
| submission-preview | `/submission-preview` | App Review Guidelines pre-check |
| appstoreconnect-review | `/appstoreconnect-review` | ASC submission material check |
| code-audit | `/code-audit` | Code quality and security assessment |

## Called by dev-workflow

These capabilities are usually called by dev-workflow after a plan, phase, or changed surface makes them relevant.

| Skill | Preferred caller | Description |
|-------|------------------|-------------|
| apple-swift-context | Swift/iOS/macOS work | Loads platform-specific rules from reference docs |
| ui-review | dev-workflow review step | SwiftUI UI + interaction compliance review |
| design-review | dev-workflow review step | Visual hierarchy, color, spacing quality review |
| feature-review | dev-workflow review step | Product + UX completeness from user journey perspective |
| execution-review | called by dev-workflow | Plan-vs-code verification + Swift code scan |
| validate-design-tokens | dev-workflow review step | Design token compliance check |
| testing-guide | write-plan / fix-bug / test-changes | Interactive testing guidance |
| profiling | write-plan / fix-bug / test-changes | Performance profiling guidance |
| xc-ui-test | write-plan / test-changes | Advanced XCUITest guidance |

## Full Capability Inventory (22)

| Skill | Route | Description |
|-------|---------|-------------|
| apple-swift-context | Auto (Swift files) | Loads platform-specific rules from reference docs |
| ui-review | dev-workflow review step | SwiftUI UI + interaction compliance review |
| design-review | dev-workflow review step | Visual hierarchy, color, spacing quality review |
| feature-review | dev-workflow review step | Product + UX completeness from user journey perspective |
| audit-finishing-touches | internal route | Mechanical §17–§20 polish-gap scan (border / default-style / undecorated card / hero) |
| execution-review | called by dev-workflow | Plan-vs-code verification + Swift code scan |
| validate-design-tokens | dev-workflow review step | Design token compliance check |
| submission-preview | `/submission-preview` | App Review Guidelines pre-check |
| appstoreconnect-review | `/appstoreconnect-review` | ASC submission material check |
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
