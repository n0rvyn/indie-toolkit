# fetch-swift-api-updates Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Fetch the latest SwiftUI API changes from WWDC 2025"
- "Check what new APIs were announced this year"
- "Update the Swift API references"
- "获取最新的 Swift API 变化"
- "What's new in iOS 26?"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Write a plan for this feature"
- "Review my Swift code"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output extracts target year from invocation and maps to iOS version
- [ ] Output runs WebSearch queries for WWDC session notes and API changes
- [ ] Output fetches from priority sources (GitHub > technical blogs > WWDC notes > Apple docs)
- [ ] Output extracts API name, type, usage pattern, and common mistakes for each new API
- [ ] Output appends new sections to swift-api-changes-{iosVersion}.md reference file
- [ ] Output handles fetch failures gracefully with search snippet fallback

## Redundancy Risk
Baseline comparison: Base model cannot fetch real-time WWDC updates; this skill provides automated research and reference updates
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
