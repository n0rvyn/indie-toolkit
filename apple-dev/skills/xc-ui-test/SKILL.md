---
name: xc-ui-test
description: "Internal reference loader auto-injected on advanced XCUITest work (paths trigger). Provides E2E patterns, multi-screen journey tests, network stubbing, snapshot/visual regression, performAccessibilityAudit, CI integration from the XCUITest reference. Not user-invocable (called by dev-workflow:fix-bug, run-phase, etc. when XCUITest context is needed)."
compatibility: Requires macOS and Xcode
user-invocable: false
model: sonnet
context: fork
agent: Explore
paths: ["**/*.swift", "**/Package.swift", "**/*.xcodeproj/**", "**/*.xcworkspace/**"]
---

# XC UI Test Skill

Provide interactive guidance on advanced XCUITest patterns based on `references/xc-ui-test-guide.md`.

Preferred caller: expert reference surfaced by `write-plan` or `test-changes`.

## When to Use

- User asks about E2E or end-to-end UI testing
- Multi-screen user journey / flow testing
- Network stubbing for UI tests (URLProtocol, mock scenarios)
- Test data factories and state isolation
- Snapshot / visual regression testing
- Accessibility testing (performAccessibilityAudit)
- CI integration for UI tests (xcodebuild, parallel, result bundles)

## Process

### 1. Identify Testing Scenario

Determine what the user needs:
- Multi-screen flow testing
- Network layer stubbing
- Test data setup
- Visual regression testing
- Accessibility compliance testing
- CI pipeline setup

### 2. Read Relevant Section of Reference Guide

Grep for section markers:

```
Grep("<!-- section:", "references/xc-ui-test-guide.md")
```

Read only the section matching the user's scenario:

```
Read("references/xc-ui-test-guide.md", offset=<marker_line + 1>, limit=<lines_to_next_marker>)
```

Section-to-need mapping:
- Multi-screen / flow / user journey / deep link → section "1. 多屏幕用户旅程"
- Network stub / URLProtocol / mock API / fixture → section "2. 网络层 Stub"
- Test data / builder / factory / state isolation / permissions → section "3. 测试数据工厂"
- Snapshot / visual regression / screenshot comparison → section "4. Snapshot / 视觉回归测试"
- Accessibility / audit / VoiceOver / a11y → section "5. 无障碍测试"
- CI / xcodebuild / parallel / result bundle / retry → section "6. CI 集成与优化"

### 3. Provide Contextual Guidance

Based on user's specific scenario:

**For Multi-Screen Flow Testing**:
- Show Flow Object pattern from guide Section 1
- Demonstrate LaunchArguments/LaunchEnvironment for state control
- Show deep link testing with XCUIApplication.open(URL)
- Explain app state waiting with wait(for:timeout:)

**For Network Stubbing**:
- Show URLProtocol subclass from guide Section 2
- Demonstrate mock scenario switching via LaunchEnvironment
- Show JSON fixture organization
- Guide error scenario simulation (timeout, 4xx, 5xx, offline)

**For Test Data Setup**:
- Show Builder pattern from guide Section 3
- Demonstrate SwiftData in-memory container for integration tests
- Show resetAuthorizationStatus for permission testing
- Explain app state isolation (--reset-state pattern)

**For Snapshot Testing**:
- Show swift-snapshot-testing setup from guide Section 4
- Demonstrate multi-device matrix testing
- Show Dynamic Type and Dark/Light mode matrices
- Explain tolerance config and CI snapshot update workflow

**For Accessibility Testing**:
- Show performAccessibilityAudit from guide Section 5
- Demonstrate audit type selection and issue filtering
- Show accessibilityIdentifier naming strategy
- Provide VoiceOver manual testing checklist

**For CI Integration**:
- Show xcodebuild test commands from guide Section 6
- Demonstrate parallel testing configuration
- Show result bundle parsing with xcresulttool
- Explain retry strategy and Simulator management

### 4. Provide Code Examples

Extract relevant patterns from the guide and adapt to user's existing test structure, Page Objects, and project naming conventions.

### 5. Common XCUITest Mistakes

- Tests that depend on each other's state (not isolated)
- Using sleep() instead of waitForExistence() or wait(for:timeout:)
- Hard-coding accessibility identifiers as strings (use enum constants)
- Not resetting app state between tests
- Running snapshot tests on different OS versions without updating baselines
- UI tests that are too fine-grained (test journeys, not individual taps)

## Success Criteria

- User can write multi-screen user journey tests
- Network scenarios (success/error/offline) are properly stubbed
- Visual regression testing catches unintended UI changes
- Accessibility audit runs in CI and catches issues
- Test suite runs efficiently in CI with parallel execution

## 串联提示

**本仓 skill**：
- `testing-guide` — Unit Test、Mock/DI、TDD 基础、Page Object 入门
- `profiling` — 性能测试（XCTMetric、XCTOSSignpostMetric、hitch 检测）

**本仓 references**：
- XCUITest API ref → `apple-dev/references/xc-ui-test-guide.md` 的 XCUITest API Reference 节（element queries / waiting patterns / Swift 6 @MainActor / launch arguments / screenshots）
- Simulator 截图与设备管理 → `apple-dev/references/external/simulator-cheatsheet.md`（CI 截图工作流可参考）
