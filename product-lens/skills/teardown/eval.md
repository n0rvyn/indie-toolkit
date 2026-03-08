# teardown Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Teardown the moat for this product"
- "Deep dive into execution quality"
- "分析护城河维度"
- "Evaluate demand authenticity in detail"
- "Journey completeness teardown"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Evaluate my entire product"
- "Compare these products"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output accepts dimension in English or Chinese (demand/journey/market/business/moat/execution)
- [ ] Output accepts aliases (need/jtbd → demand, loop/flow/ux → journey, defensibility → moat, etc.)
- [ ] Output lists available dimensions if argument doesn't match any
- [ ] Output determines target (local path or external app name)
- [ ] Output detects platform and resolves reference paths (_calibration.md + single dimension file)
- [ ] Output pre-merges universal + platform-specific sub-questions
- [ ] Output gathers market context if applicable
- [ ] Output provides deep-dive analysis on single dimension rather than full evaluation

## Redundancy Risk
Baseline comparison: Base model can analyze product dimensions but lacks structured deep-dive with calibrated sub-questions and scoring anchors from reference files
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
