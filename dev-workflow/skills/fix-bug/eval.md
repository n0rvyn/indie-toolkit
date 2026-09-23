# fix-bug Eval

Runnable cases live in `dev-workflow/evals/fix-bug/`. They grade outcomes (cause found, sibling site fixed, plain-language before/after), not steps, so they still apply after the 2026-09-23 rewrite. The suite is archived; see its `FINDINGS.md` before rerunning. Before/after baselines: `docs/99-references/fix-bug-baseline/`.

## Trigger Tests

**Single-bug mode:**
- "I'm getting this error: [stack trace]"
- "The app crashes when I tap save, here's a screenshot"
- "Build fails with 'ambiguous reference' after my changes"

**Multi-issue loop mode** (must route to `dev-workflow/references/multi-issue-loop.md`):
- "Fix #12, #15, and #17 and verify each via the API"
- "Dogfood this batch of 4 bugs against the running platform"
- "修一批 issue 并通过平台自验证"

## Negative Trigger Tests

**Should NOT trigger fix-bug:**
- "Add a new feature to export data" (feature, use brainstorm)
- "Refactor this code to be cleaner" (refactor, use write-plan)

**Should trigger single-bug handling, NOT loop mode:**
- "Fix these 2 bugs in this pure-function library" (no end-to-end verification surface)

## Output Assertions
- [ ] The `**现状**:` / `**预期**:` block (or `**Current**:` / `**Expected**:`) appears before the first code edit, in user-visible terms
- [ ] A clear bug report does not stop for confirmation; the flow stops only when the report has two readings that lead to different work
- [ ] The fix is verified on the user's real path, or the unverified part is named with concrete steps
- [ ] Other sites with the same cause are fixed in the same pass
- [ ] The closing message states before / after / how verified in plain language
- [ ] No dispatch of `readback:intent-echoer` and no `.claude/readback-state.json` writes (retired 2026-09-23)
- [ ] A small local fix is made without invoking write-plan; a multi-file or design-replacing fix invokes `dev-workflow:write-plan` with the `Caller: dev-workflow:fix-bug` first line and waits for approval

## Redundancy Risk
Baseline comparison: on small, clear bugs the base model fixes as well (FINDINGS.md); the measured edge is the plain-language before/after statement
Last tested model: Opus 5 (archived suite, pre-rewrite)
Last tested date: 2026-09-12
Verdict: marginal — kept for the before/after anchor and the known-trap list
