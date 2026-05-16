# execute-plan Eval

## Trigger Tests
- "Execute the plan we just verified"
- "Execute the verified plan"
- "Run the implementation plan"

## Negative Trigger Tests
- "Write a plan for this"
- "Verify my plan"

## Output Assertions
- [ ] Output checks for Verification section in plan before executing
- [ ] `contract_version: 1` plans require every selected task to include Task Contract before file edits
- [ ] Legacy plans without `contract_version` warn once and continue
- [ ] Output includes batch progress tracking
- [ ] Output suggests implementation-reviewer for plan-vs-code audit (standalone mode)
- [ ] Each task's Verify command is run before marking task complete
- [ ] Step 2 contains "Plan-time test-impl split (documentation note)" subsection referencing dev-workflow/references/tdd-research-2026.md and write-plan/SKILL.md Writing Guideline item 12; explicitly states NO dispatch-time splitting

## Redundancy Risk
Baseline comparison: Base model can execute tasks but lacks batch execution with review checkpoint methodology
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
