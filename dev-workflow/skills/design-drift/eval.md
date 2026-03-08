# design-drift Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Check if the code still matches the design docs"
- "Run a design drift audit"
- "Has the implementation drifted from the project brief?"
- "检查设计漂移"
- "Audit docs vs code alignment"
- "Verify the feature matches the spec"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Write a design document"
- "Create a plan for implementing this feature"
- "Review my code for quality"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output includes drift report with ✅ aligned / ❌ drifted / ⚠️ partial status per assertion
- [ ] Output includes summary statistics (total checked, aligned, drifted, stale, unresolved counts)
- [ ] Output includes flow-trace results for items marked [needs-flow-trace]
- [ ] Output provides fix recommendations for drifted items (doc update / code fix / decision needed)
- [ ] Output presents Decision Points via AskUserQuestion if any blocking decisions exist

## Redundancy Risk
Baseline comparison: Base model can compare docs vs code manually but lacks systematic assertion extraction and flow-trace integration
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
