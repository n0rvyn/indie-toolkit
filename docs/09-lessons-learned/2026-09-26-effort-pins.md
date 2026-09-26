# Effort pins: from "don't pin" to "pin to the task" — Lessons

**Date:** 2026-09-26
**Branch:** `claude/blissful-heisenberg-hvqszs`
**Status:** Complete; two skills waiting on a harness fix (see Pending)

> Review note: this file collects three things that may belong elsewhere. Move §1 to the lessons KB, §2 to `~/.claude/knowledge/platform-constraints/2026-09-26-inline-skill-effort-ignored-on-auto-invoke.md` (next to the 2026-09-24 inline-`model:` note), and keep §3 here or in an issue.

---

## 1. Lesson: rules vs principles, and how to disagree with either

**What happened.** Asked to audit effort settings against "Spending your effort", I (1) recommended a table without reading the repo's authoritative `cost-posture.md`; (2) on reading it, flipped and deferred to its anti-pattern 6 ("pinning `effort:` on review work is a Bug — it caps `/effort max`"); (3) flipped back when the user argued from the task: a pin that overrides the session in both directions is the *point* — session effort is for the main context, not for every skill. Only after that did I probe whether the knob even works (§2). The end state was right; the order was wrong: two flips on authority, evidence last.

**User's framing (adopted):**
- A **rule** is a constraint distilled from known paths. It can stop applying, or be wrong from the start. Doubt it and argue against it — but with sufficient reasons, thinking outside its frame, so it neither misleads the judgment nor makes the reasoning drift.
- A **principle** is a preference. Best if an eval can quantify it; if not, ask what its premise is and in which scenarios it holds.

**Refinement (mine):**
- Rules have premises too. Anti-pattern 6's hidden premise was "the session's effort is the right size for every skill". Checking the premise is the same move for rules and principles; it is what exposed this one.
- "Sufficient reasons" means evidence or a premise check, never a stronger voice. That includes the repo doc *and* the user: flipping because either said so is the drift the framing warns about. Order: read the rule → name its premise → test it (probe, eval, counter-example) → then keep or overturn, and write down why.
- Effort choice itself is quantifiable later: pass rate × cost per level on a skill's own evals.

## 2. Platform constraint: inline skill `effort:` ignored on auto-invoke

Probed on Claude Code 2.1.283, headless `claude -p --effort <session>`, reading `$CLAUDE_EFFORT` from Bash inside the skill/agent (the harness documents it as the turn's active effort).

| Path | Session | Pin | Observed | Applies? |
|---|---|---|---|---|
| Agent file `effort:` | high | low | low | yes |
| Skill with `context: fork` | high | low | low | yes |
| Inline skill, user types `/skill` | high / medium | low / xhigh | low / xhigh | yes, both directions |
| Inline skill, Claude invokes via Skill tool | high / medium | low / xhigh | session value | **no** |
| Workflow `agent(prompt, {effort})` | — | — | parsed per call | (not probed) |

On the ❌ path `${CLAUDE_EFFORT}` in the skill body renders the pinned value, so the harness resolves the pin but does not apply it to the turn. Same shape as the inline `model:` finding (2026-09-24). Reported to Anthropic via `/bug`.

Repro: `.claude/skills/probe-low/SKILL.md` with `effort: low` and body "Run `echo TURN=$CLAUDE_EFFORT`"; compare `claude -p '/probe-low' --effort high` with `claude -p 'Invoke the Skill tool with skill "probe-low" and follow it' --effort high`.

**Design consequence:** never fork a skill that needs the conversation. Keep the conversation inline and move fixed-effort judgment into an agent the skill dispatches with explicit inputs ("inline shell + pinned agent"). Done for fix-bug / run-phase (`bug-diagnoser`), review-before-commit (`change-classifier`), asc-submit-preview / asc-listing (`app-review-auditor`), design-parity-build (`design-parity-auditor`), swiftui-visual-audit (`render-auditor`).

## 3. Pending / known gaps

- ⏳ **Waiting on harness fix** — `runtime-feature-verify` (xhigh) and `disk-reclaim` (high) keep high judgment inline; marked `PENDING-HARNESS-FIX`. When fixed: re-run the §2 probe, delete the markers and the paragraph in `cost-posture.md`.
- **Not yet run for real:** `bug-diagnoser`, `app-review-auditor`, `design-parity-auditor`, `render-auditor` (wiring checked by grep; `change-classifier` passed a real auto-invoked run).
- **Drift risk:** `render-auditor` embeds refactoring-ui Part B; edits to `dev-workflow/references/refactoring-ui.md` must be copied by hand.
- **Stale refs:** `docs/12-retired/sync-design-md.md:36` (thresholds now only in `design-contract-schema.md` §2); run-phase flow diagram still labels some steps "opus".
