# feature-assess Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Should I add AI chat to my app?"
- "Evaluate whether to build this feature"
- "分析这个功能是否值得做"
- "Feature assessment for password manager sync"
- "GO/DEFER/KILL verdict for this feature"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Evaluate my entire product"
- "Compare these products"
- "Fix this bug"
- "Review the recent features we already built"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output requires local project path (not external app name) — skill needs code access
- [ ] Output parses feature description from quoted string or asks user if not provided
- [ ] Output detects platform from project files (iOS/Web/Flutter/Android)
- [ ] Output resolves reference paths (_calibration.md, _verdict.md, 4 dimensions, 2 modules)
- [ ] Output dispatches app-context-scanner and market-scanner in parallel
- [ ] Output evaluates 4 dimensions: demand-fit, journey-contribution, build-cost, strategic-value
- [ ] Output produces GO/DEFER/KILL verdict with integration map (GO) or alternative directions (DEFER/KILL)
- [ ] Output is for proposed features, not recent-feature-review of already-built slices

## Redundancy Risk
Baseline comparison: Base model can discuss features but lacks systematic 4-dimension evaluation with build cost analysis from actual code and GO/DEFER/KILL verdict framework
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
