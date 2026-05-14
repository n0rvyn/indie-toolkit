# fix-bug Eval

## Trigger Tests
- "I'm getting this error: [stack trace]"
- "The app crashes when I tap save, here's a screenshot"
- "Build fails with 'ambiguous reference' after my changes"

## Negative Trigger Tests
- "Add a new feature to export data"
- "Refactor this code to be cleaner"

## Output Assertions
- [ ] Skill Step 0.9 must contain a compact Level/Signal table covering all 10 levels AND a pointer to `dev-workflow/references/feedback-loop-ladder.md` for long-form rationale.
- [ ] Skill must require [Feedback Loop] declaration before Step 3 (output schema present + Step 3 cross-reference rule).
- [ ] `dev-workflow/references/feedback-loop-ladder.md` exists and defines all 10 levels (numbered 1 through 10 with descriptions).
- [ ] Skill Step 0.9 body (between `## Step 0.9:` header and the line starting with `1. Reproduce first`) remains ≤ 35 lines (re-bloat guard: if a future maintainer re-inlines the full prose ladder alongside the pointer, this fails).
- [ ] Step 7 (Plan the fix) must contain "Expectation Gate" sub-block requiring [Expected behavior] and [Verifiable steps] before the Task Contract block.
- [ ] No code edits occur before expected behavior, current behavior, verification method, and regression shield are written
- [ ] Step 7 gate: simple fix enters native plan mode (EnterPlanMode), complex fix invokes /write-plan
- [ ] No assertion confirmation gate blocks diagnosis (Step 3 flows directly to Step 4)
- [ ] Output includes Step 10 tradeoff report for the proposed fix
- [ ] Root cause includes code evidence (file:line references)
- [ ] Step 0.5 invokes `dev-workflow:kb` skill (not a non-existent `search()` tool)
- [ ] Steps 0.5/0.7/0.8 issued as parallel tool calls (single message, not three sequential)
- [ ] Step 5 value-domain trace prefers `LSP findReferences` when an LSP server is available; grep as fallback
- [ ] Step 7 Consumer Impact uses `LSP findReferences` to enumerate callers (LSP-available languages)
- [ ] Agent dispatch verification gate present: after every Agent return, claimed file writes are verified against disk state before advancing

## Redundancy Risk
Baseline comparison: Base model can diagnose errors but lacks systematic value-domain tracing and parallel path detection methodology
Last tested model: Opus 4.7 (1M context)
Last tested date: 2026-05-14
Verdict: essential
