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
- [ ] Standalone mode **invokes** `dev-workflow:review-execution` (not "suggests") with `plan_path`, `scope_files`, and `mode: advisory` — a prose suggestion here is why review never ran on this chain
- [ ] `test-changes` and `finish-branch` remain suggestions, not invocations
- [ ] Each task's Verify command is run before marking task complete
- [ ] `### Behavior Note: Plan-time test-impl split pattern` is present between Step 1 and Step 2, and explicitly states NO dispatch-time splitting (the split is the plan author's job, per write-plan Writing Guideline 12)

## Redundancy Risk
Baseline comparison: Base model can execute tasks but lacks batch execution with review checkpoint methodology
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
