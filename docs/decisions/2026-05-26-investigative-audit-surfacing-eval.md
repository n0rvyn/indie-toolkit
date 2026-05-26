# Investigative-Audit Surfacing Evaluation

**Date:** 2026-05-26
**Plan:** 2026-05-26-skill-consolidation-plan.md
**Context:** Group 4 input — for each "investigative audit" skill, decide: output/entry/hook/delete.

---

## Evaluation Table

| Skill | Current state | Invocation signal | Surfacing option | Proposed action | Specific trigger |
|---|---|---|---|---|---|
| `design-drift` | user-invocable: true; design-analyzer agent (not a skill) exists; design-drift-auditor agent exists | User says "check design drift" or similar | hook nudge when design docs change | **hook** — add nudge to suggest-skills.sh when design docs (`*.md` in `docs/`) were modified in last N commits | `git log -n 10 --format="%H" -- 'docs/**/*.md'` returns ≥1 AND file matches design doc patterns (docs/04-dev-guide, docs/05-architecture, etc.) |
| `audit-rules` | user-invocable: true; dispatches rules-auditor agent | User says "audit CLAUDE.md rules" or similar | hook nudge when CLAUDE.md changed | **hook** — add nudge to suggest-skills.sh when CLAUDE.md modified in last N commits (per Task 15) | `git log -n 10 --format="%H" -- CLAUDE.md` returns ≥1 |
| `validate-design-tokens` (apple-dev) | user-invocable: true; validates token consistency in Swift code vs design spec | Apple project; user says "validate design tokens" or similar | output inside another skill | **output/entry — demote to output** in `design-parity-build`; remove from user-invocable menu. Apple projects can access it via design-parity-build's run. Standalone invocation is rare enough to justify removal. | N/A (no hook; output in design-parity-build) |
| `audit-finishing-touches` (apple-dev) | user-invocable: true; post-review UI polish check | Apple project; user says "finishing touches audit" or similar | hook nudge on specific context | **hook** — add nudge to suggest-skills.sh when user is near phase completion (prompt mentions "done", "finish", "polish", "review done", "test passed") AND project has apple-dev plugin | User prompt matches `done|finish|polish|完成了|收尾|end` AND `ls ~/.claude/plugins/cache/*/apple-dev/` succeeds |

---

## Recommendation Summary

**Add these hook nudges (Group 4 Tasks 15-17):**

1. **audit-rules nudge** (Task 15) — fires when CLAUDE.md modified in last 10 commits. High value: catches rule conflicts before they propagate. Low false-positive risk: only fires in repos that edit CLAUDE.md frequently.

2. **finish-branch nudge** (Task 16) — fires when current branch is ≥5 commits ahead of main. High value: reminds users to integrate and close feature branches. Low false-positive risk: main branch silently skips.

3. **audit-tokens cadence nudge** (Task 17) — fires when `~/.claude/last-audit-tokens-run` is missing or ≥14 days old. High value: encourages periodic token hygiene. Bootstrap path (no file = fires every prompt) is acceptable for initial rollout; follow-up task should wire audit-tokens to write the timestamp file.

**Defer to follow-up (not in Group 4):**

- `design-drift` hook nudge — add once design-drift itself is confirmed as a working skill (not just an agent). Currently the skill exists but its invocation signal is vague; recommend clarifying design-drift's activation phrase before wiring the hook.
- `validate-design-tokens` output conversion — requires verifying design-parity-build has capacity to host the validation output without scope creep. File as separate issue.
- `audit-finishing-touches` hook nudge — "done/finish/polish" prompt detection is noisy (common language). Require additional Apple-project guard (plugin installed + Swift file present) before wiring.

**Delete (not recommended for this plan, requires separate authorization):**

- `validate-design-tokens` as standalone — recommend demoting to output in design-parity-build rather than deleting entirely (some users may invoke directly).
- `audit-finishing-touches` — keep as-is (apple-dev long-tail skill). The hook nudge is low-priority.
