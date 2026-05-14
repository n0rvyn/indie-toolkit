---
name: code-audit
description: "Use when the user says 'code audit', 'audit code', '代码审计', 'report card', 'security scan', or wants a comprehensive code quality assessment. Scans for security issues, concurrency safety, accessibility gaps, performance anti-patterns, and SwiftUI anti-patterns in iOS/macOS Swift projects."
compatibility: Requires macOS and Xcode
---

# Code Audit

Comprehensive code quality audit for iOS/macOS Swift projects across 5 categories.

## Process

### Step 1: Determine Scope

Ask user or auto-detect:
- **Specified files/directories**: audit those
- **No specification**: audit all `.swift` files under project root

**Exclude**: `Pods/`, `.build/`, `DerivedData/`, `*.generated.swift`, test targets (unless user requests test audit).

Record file count for final summary.

### Step 2: Security Scan

#### 2.1 Hardcoded Secrets

Grep for patterns:
- `"sk-[a-zA-Z0-9]{20,}"` — API keys
- `password\s*[:=]\s*"[^"]{8,}"` — hardcoded passwords (exclude test fixtures and placeholders like `"password123"` in test targets)
- `AKIA[0-9A-Z]{16}` — AWS access keys
- `-----BEGIN.*PRIVATE KEY-----` — embedded private keys
- `api[_-]?key\s*[:=]\s*"[^"]{8,}"` — generic API keys

```
[2.1] Hardcoded secrets — 🔴 {pattern} at {file:line} / ✅ none
```

#### 2.2 Insecure Network

Grep for:
- `http://` in URL strings (excluding `localhost`, `127.0.0.1`, `0.0.0.0`)
- `allowsArbitraryLoads.*true` in Info.plist
- `ServerTrust` without certificate pinning
- `URLSession` custom configurations without TLS minimum version

```
[2.2] Network security — 🔴/🟡 {issue} at {file:line} / ✅ clean
```

#### 2.3 Input Validation

Grep for:
- SQL string interpolation: `"\(.*)"` near `SELECT|INSERT|UPDATE|DELETE`
- `NSPredicate(format:` with `\(` interpolation (should use `%@` arguments)
- `WKWebView` loading user-provided URLs without scheme validation

```
[2.3] Input validation — 🔴 {issue} at {file:line} / ✅ clean
```

#### 2.4 Sensitive Data Storage

Check storage patterns:
- `UserDefaults` storing tokens/passwords/keys → 🔴 (should use Keychain)
- Verify Keychain wrapper usage exists (`SecItem`, `KeychainAccess`, or custom)

```
[2.4] Sensitive storage — 🔴 UserDefaults for secrets at {file:line} / ✅ Keychain used
```

### Step 3: Concurrency Safety

#### 3.1 Sendable Compliance

Grep for:
- Classes crossing actor boundaries without `Sendable` conformance
- `@unchecked Sendable` usage → 🟡 flag for manual review
- Mutable `var` properties in `Sendable` types without synchronization

```
[3.1] Sendable — 🟡 @unchecked Sendable at {file:line} / 🔴 non-Sendable crossing at {file:line} / ✅ clean
```

#### 3.2 Actor Isolation

Grep for:
- `DispatchQueue.main.async` in SwiftUI context (should use `@MainActor`)
- ViewModels without `@MainActor` that update UI-bound properties
- `nonisolated` on properties that access mutable state

```
[3.2] Actor isolation — 🟡/🔴 {issue} at {file:line} / ✅ clean
```

#### 3.3 Data Races

Grep for:
- `var` properties on non-actor classes accessed from multiple `Task {}` blocks
- `Task.detached` capturing mutable variables
- Shared mutable state without synchronization primitives

```
[3.3] Data races — 🔴 {issue} at {file:line} / ✅ none detected
```

### Step 4: Accessibility

#### 4.1 Missing Labels

Grep for:
- `Image(` without `.accessibilityLabel` (unless `.accessibilityHidden(true)`)
- Custom interactive views (`.onTapGesture`, `.gesture(TapGesture`) without accessibility traits
- Icon-only buttons without labels

```
[4.1] Accessibility labels — 🟡 missing label at {file:line} / ✅ covered
```

#### 4.2 VoiceOver Support

Check for:
- `.accessibilityElement(children: .combine)` on logical groups
- `.accessibilityAction` for custom gestures
- `.accessibilityValue` for stateful controls (toggles, sliders, steppers)

```
[4.2] VoiceOver — 🟡 {issue} at {file:line} / ✅ adequate
```

#### 4.3 Dynamic Type

Grep for:
- `.font(.system(size:` — hardcoded font sizes break Dynamic Type → 🟡
- Fixed `.frame(height:` on text containers → 🟡
- Missing `.minimumScaleFactor` on critical text

```
[4.3] Dynamic Type — 🟡 fixed font size at {file:line} / ✅ dynamic fonts used
```

### Step 5: Performance Anti-patterns

#### 5.1 Main Thread Blocking

Grep for:
- `DispatchQueue.main.sync` — deadlock risk → 🔴
- `Thread.sleep` / `usleep` on main thread → 🔴
- Synchronous file I/O (`Data(contentsOf:)`, `String(contentsOfFile:)`) in `body` or `@MainActor` context

```
[5.1] Main thread — 🔴 blocking at {file:line} / ✅ clean
```

#### 5.2 Excessive Redraws

Grep for:
- `@ObservedObject` used where `@StateObject` is appropriate (object recreated every parent redraw)
- `@State` initialized with expensive computation (runs every view init)
- Views with large `body` that could benefit from extraction

```
[5.2] Redraws — 🟡 {issue} at {file:line} / ✅ clean
```

#### 5.3 Memory Leaks

Grep for:
- Closures capturing `self` strongly in long-lived contexts (`NotificationCenter.addObserver`, `Timer.scheduledTimer`, stored closures)
- Missing `[weak self]` in escaping closures stored as properties
- `Timer.publish` without cancellation in `onDisappear`/`task`

```
[5.3] Memory leaks — 🔴 strong self in {context} at {file:line} / ✅ clean
```

### Step 6: SwiftUI Anti-patterns

#### 6.1 Task Cancellation

Grep for:
- `.onAppear` used for async work → 🟡 (should use `.task` for auto-cancellation)
- `.task { }` with network calls that don't check `Task.isCancelled` → 🟡

```
[6.1] Task cancellation — 🟡 .onAppear async at {file:line} / ✅ .task used
```

#### 6.2 Property Wrapper Usage

Check for:
- `@ObservedObject` for owned objects → should be `@StateObject`
- `@StateObject` in non-View types → invalid
- `@State` for reference types without `@Observable`
- `@EnvironmentObject` without `.environmentObject()` in preview providers

```
[6.2] Property wrappers — 🟡 {issue} at {file:line} / ✅ correct
```

#### 6.3 Navigation Patterns

Check for:
- `NavigationView` (deprecated) → use `NavigationStack` → 🟡
- Programmatic navigation without `NavigationPath`
- Deep sheet-in-sheet nesting (> 2 levels)

```
[6.3] Navigation — 🟡 deprecated NavigationView at {file:line} / ✅ modern patterns
```

### Step 7: Output Report

Write report to `.claude/reviews/audit-{YYYY-MM-DD}.md`:

```markdown
# Code Audit Report

**Date**: {YYYY-MM-DD}
**Scope**: {N} files audited
**Commit**: {HEAD SHA short}

## 🔴 Critical ({N})

- [{category}] {issue}
  File: {file:line}
  Evidence: {code snippet}
  Fix: {specific recommendation}

## 🟡 Warning ({N})

- [{category}] {issue}
  File: {file:line}
  Evidence: {code snippet}
  Fix: {specific recommendation}

## 🟢 Clean ({N} categories)

- {category}: {summary}

## Summary

| Category | 🔴 | 🟡 | 🟢 |
|----------|-----|-----|-----|
| Security | X | Y | Z |
| Concurrency | X | Y | Z |
| Accessibility | X | Y | Z |
| Performance | X | Y | Z |
| SwiftUI | X | Y | Z |
| **Total** | **X** | **Y** | **Z** |
```

### Step 8: Record Audit Marker

After report is written:

```bash
git rev-parse HEAD > .claude/last-audit-commit
```

This enables the staleness reminder in `dev-workflow/hooks/suggest-skills.sh`. After 20+ commits, users running `/commit`, `/write-plan`, or `/write-dev-guide` will see a reminder to re-run `/code-audit`.

## Principles

1. **Evidence required**: every finding must include `file:line` and a code snippet. No vague warnings.
2. **Actionable fixes**: every finding must include a specific fix recommendation, not just "consider improving".
3. **No false positives over completeness**: skip ambiguous patterns rather than flag noise. Developers ignore noisy audit reports.
4. **Severity means impact**: 🔴 = security vulnerability or crash risk; 🟡 = code quality or maintainability issue; 🟢 = category passed.

## 串联提示

Code audit complete. For issues found in specific categories, use the following local references for deeper investigation:

**Concurrency issues** (Section 3 findings):
- grep `apple-dev/references/external/swift-concurrency-patterns.md` for actor / structured concurrency / cancellation / GCD migration / strict-concurrency diagnostics / common bug patterns
- grep `apple-dev/references/external/swift-concurrency-api/` for async/await/Task/Actor API reference

**Performance issues** (Section 5 findings):
- grep `apple-dev/references/external/swiftui-performance-audit.md` for SwiftUI runtime performance diagnostics and fixes
- `profiling` skill (OSSignposter, MetricKit, XCTMetric instrumentation; routed automatically by run-phase / fix-bug / write-plan)

**SwiftUI anti-patterns** (Section 6 findings):
- grep `apple-dev/references/apple-swift-rules.md` → SwiftUI Correctness Checklist for the 13 hard rules
- grep `apple-dev/references/external/swiftui-ui-patterns/` for navigation / state / sheet / list / component patterns
- grep `apple-dev/references/external/swiftui-view-refactor.md` for view extraction and long body refactoring

**API reference** (uncertain about an API signature):
- See `apple-swift-context` skill's Topic Router (auto-loaded when editing Swift files)

## Completion Criteria

- All 5 audit categories scanned with grep-based evidence
- Report written to `.claude/reviews/audit-{date}.md`
- `.claude/last-audit-commit` updated with current HEAD SHA
- Summary table shows counts per category per severity
- Each 🔴/🟡 finding includes file:line and fix recommendation
