# compare Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Compare these apps: Notion, Bear, and Obsidian"
- "Which product should I focus on?"
- "比较这几个产品的市场潜力"
- "Evaluate and compare my app with competitors"
- "Create a scoring matrix for these products"
- "Do a deliberate comparison of these named products"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Evaluate this single product"
- "Teardown the moat dimension"
- "Fix this bug"
- "Run a weekly scan of everything under ~/Code"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output accepts mixed target list (local paths + external app names)
- [ ] Output confirms target list with user before proceeding
- [ ] Output resolves reference paths (_calibration.md, _scoring.md, 6 dimensions, 5 modules)
- [ ] Output dispatches market-scanner for each target in parallel
- [ ] Output dispatches dimension-evaluator agents for all targets x 6 dimensions in parallel
- [ ] Output validates dimension results and re-dispatches failing dimensions once
- [ ] Output generates extras (kill criteria, feature audit, elevator pitch, pivot directions) in parallel
- [ ] Output produces comparison matrix with scores and recommendations
- [ ] Output remains a deliberate comparison workflow, not a periodic portfolio monitoring substitute

## Redundancy Risk
Baseline comparison: Base model can compare products but lacks systematic 6-dimension scoring with calibrated anchors and parallel evaluation pipeline
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
