# Cost Posture for Skills and Agents

Reference doc consumed by `plugin-master` (Create route) and `plugin-reviewer` (Dimension 7.5). Classifies a skill/agent by the kind of work it does, then maps that class to a recommended `model` / `effort` / `context` frontmatter configuration.

> **Axis note — keep these separate.** This document is the **compute-cost** axis (which `model` / `effort` / `context` tier a skill runs on). It is orthogonal to the **context-cost** axis (prose economy — dead text that loads on every enumeration), which lives in `plugin-reviewer` **D7.6 (deletion test)**. A skill can sit on the right model yet carry deletable filler, and vice versa. Do not fold one check into the other.

## Why this exists

Each turn that runs on Opus costs roughly 20× a Sonnet turn (per real usage data: $0.59/turn vs $0.03/turn at the prevailing context sizes). Default session model is typically Opus, so any skill that does NOT set `model:` inherits Opus — even if the work is mechanical and Sonnet handles it correctly.

`commit` (in dev-workflow) already proves the pattern: `model: haiku` + `context: fork` for over a hundred turns of git classification work with no failures.

The risk runs both directions: under-spec'd cheap models silently produce worse output that costs more downstream (re-runs, debugging, rollbacks); over-spec'd expensive models burn money on work that doesn't need them. The classification below targets the second failure mode, which is more common in practice.

## Classification heuristic

Decide what a skill **does at runtime**, not what it's named. Ask: when the skill is invoked, what is the dominant work?

| Class | Dominant work | Recommended config | Reason |
|---|---|---|---|
| **Mechanical execution** | Follows already-written instructions, applies edits, runs commands, collects output | `model: sonnet` | Plan/spec exists. The skill executes; it does not judge. Sonnet has plenty of headroom. |
| **Retrieval + extract** | Searches a corpus, filters matches, returns relevant snippets | `model: sonnet` + `context: fork agent: Explore` | Read-only work in isolated context. CLAUDE.md not needed. |
| **Tool wrapper** | Wraps a CLI / API call, formats structured output | `model: haiku` + `context: fork` | Pure I/O. No reasoning. |
| **Judgment** | Finds defects, critiques quality, infers root cause | inherit (default Opus); do **not** pin `effort:` | Catching subtle problems requires deep reasoning. A pinned `effort:` is a *ceiling* on the session, not a floor — see anti-pattern 6. |
| **Synthesis** | Writes new plans, designs solutions, brainstorms options | inherit (default Opus) — **do not downgrade** | Creative output. Quality compounds downstream. |
| **Orchestration** | Dispatches multiple skills/agents and coordinates a multi-step flow | inherit (default Opus) — **do not downgrade** | Routing errors at this layer cascade; the orchestrator is the most expensive thing to get wrong. |

## Decision questions (in order)

1. **Does this skill write the spec, or follow one?**
   - Writes/designs → Synthesis or Judgment class
   - Follows → Mechanical class

2. **Is the output of this skill consumed by another skill/agent, or returned to the user as the final word?**
   - Consumed downstream → quality matters proportionally to fan-out → favor higher model
   - Returned as-is → user can correct → lower model acceptable

3. **Does the skill require knowledge from CLAUDE.md or conversation history?**
   - No → consider `context: fork` (saves context loading)
   - Yes → keep inline

4. **What's the failure cost?**
   - Silent wrong output that affects downstream → bias toward higher model
   - Visible error that user catches → lower model fine

## Examples grounded in dev-workflow

| skill | Class | Configured | Notes |
|---|---|---|---|
| `commit` | Tool wrapper (git classification) | `model: haiku, context: fork` | Already done |
| `execute-plan` | Mechanical execution | `model: sonnet` | Added in 2026-05 — plan is pre-verified, this just applies it |
| `test-changes` | Mechanical execution (parse output) | `model: sonnet` | Added in 2026-05 |
| `kb` | Retrieval + extract | `model: sonnet` | Added in 2026-05; could later add `context: fork agent: Explore` |
| `verify-plan` | Judgment (find plan defects) | inherit | Do not downgrade |
| `write-plan` | Synthesis | inherit | Do not downgrade |
| `run-phase` | Orchestration | inherit | Do not downgrade — coordinates write-plan/verify-plan/execute-plan/test-changes |
| `fix-bug` (diagnosis phase) | Judgment | inherit | Root cause reasoning |

## Anti-patterns to flag

1. **Mechanical skill on inherit (= Opus by default)**: every turn pays Opus premium for work Sonnet handles. Flag as Minor.
2. **`model: haiku` on judgment/synthesis work**: Haiku misses subtle defects; downstream cost > savings. Flag as Bug.
3. **`context: fork` on multi-step interactive skill**: the forked context loses conversation state mid-flow. Flag as Logic.
4. **`context: fork` without an actionable prompt in skill body**: the subagent receives guidelines but no task; returns empty. Flag as Logic.
5. **`model:` set but `effort:` mismatched**: e.g. `model: haiku, effort: high` — Haiku supports *no* effort level at all; the field is silently ignored. Flag as Minor.
6. **Pinned `effort:` on a judgment/review agent**: `effort:` **overrides the session effort level** (docs: "Overrides the session effort level. Default: inherits from session"). It is a ceiling, not a floor. `effort: high` looks inert because `high` is the default on Opus 4.8 / Sonnet 5 / Fable 5, but it silently caps `/effort xhigh`, `/effort max`, and ultracode back down to `high` — precisely in the deep sessions where depth was requested. Flag as Bug.
7. **Below-default `effort:` on an agent with verification duty**: `effort: medium` on anything that must run tests, execute a `**Verify:**` step, or decide pass/fail. Below-default effort is the documented cause of "skipping a file, not running the tests, not double-checking." Below-default effort is only legitimate for agents with no verification duty (pure generation, extraction, classification). Flag as Bug.

**Axis reminder.** `model:` and `effort:` are orthogonal. `model` = *knowing more* (capability; raise for subtle bugs, unfamiliar domains, architecture calls). `effort` = *trying harder* (how many files read, how much verified; raise when the failure was visibly lazy). A fixed-rubric checker is a *specific instruction set* and belongs on Sonnet; open-ended defect discovery is *ambiguity* and belongs on Opus. Full reference: `~/.claude/knowledge/api-usage/2026-07-09-skillsubagent-effort-overrides-session-e.md`.

## Constraints on recommendation

- This document is a **heuristic guide**, not a hard rule. Edge cases exist (a "mechanical" skill that needs to read 50 large files may benefit from larger context Opus). Recommend, don't enforce.
- When recommending a downgrade for an existing skill, **cite real usage evidence** if available (e.g. "Sonnet has handled 3000+ turns of this skill successfully") rather than pure prediction.
- For brand-new skills with no usage history, the recommendation is a starting posture, not a verdict — first runs may show that judgment was misclassified.
