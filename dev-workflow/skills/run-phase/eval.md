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
- [ ] Step 6 makes ONE `dev-workflow:review-execution` call with `plan_path` + `scope_files` (the Phase's files, not the whole tree) + `mode: gated` — and keeps NO reviewer list of its own
- [ ] Human-verification items, the `Tests:` line, and design-reviewer 🔴 items are read from the review return's `### Per-reviewer passthrough`, not from per-agent report files
- [ ] That assertion is only satisfiable if the apple-dev reviewers return those sections inline — check their Output Contract step 4, not just this skill
- [ ] Step 6.7 cross-checks dispatched-vs-arrived: a reviewer named in `### Coverage notes` whose section is missing from the passthrough produces a visible ⚠️ line, not silence. ⛔ Silence here is indistinguishable from "no items found", which is how this payload went missing once already
- [ ] Output continues through verify-plan, execute-plan, test-changes, and the review call after reading Project Health
- [ ] Apple review/testing skills are selected through internal route terms when Swift/iOS/macOS surfaces changed
- [ ] Phase completion report generated with next phase info
- [ ] State file uses JSON format (`.claude/dev-workflow-state.json`) with legacy YAML migration on first encounter
- [ ] Agent dispatch verification gate present: Step 4/5 verify report files on disk before advancing `phase_step`
- [ ] ⛔ The gate does NOT require `.claude/reviews/*.md` for Step 6 — `review-execution` returns a consolidated block and promises no file. The Step 6 signal is a return containing `### Coverage notes`
- [ ] Step 6.9 records `review_reports: ["review-execution:consolidated"]` + finding counts, never report paths; the Step 8.0 gate therefore never false-blocks a phase that was reviewed
- [ ] PushNotification emitted at the three checkpoints: plan decisions pending, reviews complete, phase done
- [ ] Step 1 uses explicit Bash tool invocation (not legacy `!`cat\`` shorthand)
- [ ] UI phase + design reference present → Step 5.5 triggers: renders #Preview views, diffs vs design ref, fixes up to 3 rounds, surfaces remaining diffs as informational items, sets phase_step: review
- [ ] Non-UI phase (no SwiftUI view files modified) OR no design reference → Step 5.5 skips entirely with logged reason, sets phase_step: review, proceeds to Step 6
- [ ] UI phase + design reference present BUT modified views contain no #Preview block → Step 5.5 skips with reason `no #Preview blocks in modified views`, sets phase_step: review, proceeds to Step 6
- [ ] render-preview returns error / no result file for a view → that view is logged as a render failure and skipped, the loop continues to the next view (one failed render does not abort Step 5.5)

## Redundancy Risk
Baseline comparison: Base model can execute tasks sequentially but lacks structured phase orchestration with state persistence
Last tested model: Opus 4.7 (1M context)
Last tested date: 2026-05-14
Verdict: essential
