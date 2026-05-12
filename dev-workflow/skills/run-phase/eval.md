# run-phase Eval

## Trigger Tests
- "run phase 2"
- "start phase 1"
- "next phase"

## Negative Trigger Tests
- "write a plan"
- "execute this task"

## Output Assertions
- [ ] Output updates state file before each step
- [ ] Project Health preflight runs before planning when state is missing, stale, or red
- [ ] Plan context includes Impact Map and Task Contract requirements
- [ ] Output writes plan in main context (not dispatched to agent)
- [ ] Output invokes verify-plan before execute-plan
- [ ] Output continues through verify-plan, execute-plan, test-changes, and implementation-reviewer review after reading Project Health
- [ ] Apple review/testing skills are selected through internal route terms when Swift/iOS/macOS surfaces changed
- [ ] Phase completion report generated with next phase info

## Redundancy Risk
Baseline comparison: Base model can execute tasks sequentially but lacks structured phase orchestration with state persistence
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
