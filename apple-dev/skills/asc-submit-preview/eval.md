# asc-submit-preview Eval

## Trigger Tests
- "asc submit preview"
- "Will this pass App Store review?"
- "asc pre-submit check"
- "上架前自检"
- "pre-submit audit"
- "check my app before submitting to App Store"
- "Apple 审核会过吗"
- "scan for App Store rejection reasons"

## Negative Trigger Tests
- "Update ASC docs" (→ update-asc-docs)
- "Review my plugin" (→ /plugin-master review)
- "Fill in App Privacy labels" (→ asc-listing)
- "What screenshots do I need for ASC?" (→ asc-listing)
- "Generate App Store description" (→ asc-listing)
- "Run code audit on my Swift project" (→ /run-phase code-audit / review-execution)
- "Performance profiling" (→ profiling)

## Output Assertions
- [ ] Output checks app code against App Review Guidelines sections 1-5
- [ ] Output distinguishes from asc-listing (store materials vs code) — explicitly states "for ASC backend material use /asc-listing"
- [ ] Output flags common rejection reasons (permissions, private APIs, crashes, missing privacy strings)
- [ ] Output verifies Info.plist usage description strings for sensitive APIs
- [ ] Output checks for hardcoded URLs / deprecated APIs / private-API usage patterns
- [ ] Output does NOT walk through ASC backend form fields (that belongs to /asc-listing)
- [ ] Output does NOT run heavy code-audit-style scans (those belong to apple-dev:code-audit, called by run-phase)

## Redundancy Risk
Baseline comparison: Base model knows App Store guidelines but lacks systematic checklist approach
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
