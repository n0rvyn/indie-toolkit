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
- [ ] State file uses JSON format (`.claude/dev-workflow-state.json`) with legacy YAML migration on first encounter
- [ ] Agent dispatch verification gate present: Step 4/5/6 verify report files on disk before advancing `phase_step`
- [ ] PushNotification emitted at the three checkpoints: plan decisions pending, reviews complete, phase done
- [ ] Step 1 uses explicit Bash tool invocation (not legacy `!`cat\`` shorthand)

## Redundancy Risk
Baseline comparison: Base model can execute tasks sequentially but lacks structured phase orchestration with state persistence
Last tested model: Opus 4.7 (1M context)
Last tested date: 2026-05-14
Verdict: essential
