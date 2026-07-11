# fix-bug Eval

## Trigger Tests

**Single-bug mode:**
- "I'm getting this error: [stack trace]"
- "The app crashes when I tap save, here's a screenshot"
- "Build fails with 'ambiguous reference' after my changes"

**Multi-issue loop mode** (must route to `dev-workflow/references/multi-issue-loop.md`):
- "Fix #12, #15, and #17 and verify each via the API"
- "Dogfood this batch of 4 bugs against the running platform"
- "修一批 issue 并通过平台自验证"
- "Here are 3 user-visible bugs in the chat agent — fix them and replay through ChatManager"

## Negative Trigger Tests

**Should NOT trigger fix-bug:**
- "Add a new feature to export data" (feature, use brainstorm)
- "Refactor this code to be cleaner" (refactor, use write-plan)

**Should trigger fix-bug single-bug mode, NOT loop mode:**
- "Fix these 2 bugs in this pure-function library" (2+ issues but no end-to-end verification surface — falls back to single-bug flow per issue)
- "Two failing unit tests in math.test.ts" (unit-test scope only, no runtime surface)

## Output Assertions
- [ ] Skill Step 0.9 must contain a compact Level/Signal table covering all 10 levels AND a pointer to `dev-workflow/references/feedback-loop-ladder.md` for long-form rationale.
- [ ] Skill must require [Feedback Loop] declaration before Step 3 (output schema present + Step 3 cross-reference rule).
- [ ] `dev-workflow/references/feedback-loop-ladder.md` exists and defines all 10 levels (numbered 1 through 10 with descriptions).
- [ ] Skill Step 0.9 body (between `## Step 0.9:` header and the line starting with `1. Reproduce first`) remains ≤ 35 lines (re-bloat guard: if a future maintainer re-inlines the full prose ladder alongside the pointer, this fails).
- [ ] Step 7 (Plan the fix) must contain "Expectation Gate" sub-block requiring [Expected behavior] and [Verifiable steps] before the Task Contract block.
- [ ] No code edits occur before expected behavior, current behavior, verification method, and regression shield are written
- [ ] Step 7 gate: both Simple and Complex branches invoke `dev-workflow:write-plan` (skill identifier form, not `/write-plan` slash); Simple expects a 1–2 task plan. `EnterPlanMode` must NOT appear as a required action (global CLAUDE.md forbids native plan mode for planning)
- [ ] Step 7 Complex branch invocation prompt's first non-empty line is the literal `Caller: dev-workflow:fix-bug` marker (single source of truth for write-plan's caller detection — gates both Step 1 item 12 Bug-diagnosis population AND Step 2.5 echo-only mode)
- [ ] Step 7 Complex branch emits a 4-item structured diagnosis bundle (confirmed assertions / `[值域检查]` table / `[路径检查]` table / `[Consumer Impact]` list), with explicit Readback continuity declaration covering caller marker + 30-min freshness + no-new-requirements + conservative-default-on-doubt, AND a session-freshness caveat for cross-session resume
- [ ] No assertion confirmation gate blocks diagnosis (Step 3 flows directly to Step 4)
- [ ] Output includes Step 10 tradeoff report for the proposed fix
- [ ] Root cause includes code evidence (file:line references)
- [ ] Step 0.5 invokes `dev-workflow:kb` skill (not a non-existent `search()` tool)
- [ ] Steps 0.5/0.7/0.8 issued as parallel tool calls (single message, not three sequential)
- [ ] Step 5 value-domain trace prefers `LSP findReferences` when an LSP server is available; grep as fallback
- [ ] Step 7 Consumer Impact uses `LSP findReferences` to enumerate callers (LSP-available languages)
- [ ] Agent dispatch verification gate present: after every Agent return, claimed file writes are verified against disk state before advancing
- [ ] Mode Detection block exists between `## Input` and `## Hard Gate`, with all three conditions enumerated (2+ issues / verification surface present / surface-level verification expected); routes to `dev-workflow/references/multi-issue-loop.md` when all three hold
- [ ] Step 0.8 reads `docs/02-architecture/ubiquitous-language.md` if present (in addition to AI-CONTEXT.md), per `dev-workflow/references/ubiquitous-language-pattern.md`
- [ ] `dev-workflow/references/multi-issue-loop.md` exists and defines steps L0 through L5, including L4.0 "route through fix-bug Steps 1-6 for diagnostic"

## Redundancy Risk
Baseline comparison: Base model can diagnose errors but lacks systematic value-domain tracing and parallel path detection methodology
Last tested model: Opus 4.7 (1M context)
Last tested date: 2026-05-14
Verdict: essential
