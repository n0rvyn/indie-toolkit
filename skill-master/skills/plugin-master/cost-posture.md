# Cost Posture for Skills and Agents

Reference doc consumed by `plugin-master` (Create route), `plugin-reviewer` (Dimension 7.5) and `audit-tokens` (recommendations). It decides which `model` / `effort` / `context` frontmatter a skill or agent should carry.

> **Axis note — keep these separate.** This document is the **compute-cost** axis (which `model` / `effort` / `context` tier a skill runs on). It is orthogonal to the **context-cost** axis (prose economy — dead text that loads on every enumeration), which lives in `plugin-reviewer` **D7.6 (deletion test)**. Do not fold one check into the other.

## The rule

1. **Small models only for lookup work, and only through an isolated context.** Searching, reading logs or test output, "where is this defined", wrapping a CLI and returning structured output — put it behind `context: fork` (skill) or an agent definition, then set `model: sonnet` or `model: haiku`.
2. **Everything else stays on the main model.** Judgment, synthesis, orchestration, and any work that writes code or files: no `model:` pin.
3. **When quality or cost is off, change `effort` before changing the model.** See anti-patterns 6–7 for where an `effort:` pin is itself a bug.

## Why

**The old premise is gone.** This file used to say an Opus turn costs ~20× a Sonnet turn. That compared a large main-thread Opus turn with a small subagent Sonnet turn — context size, not model price. At list prices (2026-09) Opus 5.5 vs Sonnet 5 is 2× on input and output, 2× on 1h cache writes, and **equal on cache reads** ($0.20/M), which is the largest line in a long session.

**The savings were small.** Over 60 days of indie-toolkit usage (2026-07-26 → 09-24), every Sonnet/Haiku downgrade together saved ~$103 of ~$7,488 API-equivalent spend (1.4%). Agent/fork pins declared in this repo account for ~$22 of that.

**Inline pins barely work.** Probed on CC 2.1.281: an inline `model: sonnet` (no `context: fork`) switches only when the user types `/skill`; when Claude auto-invokes the skill through the Skill tool it stays on the session model. Inline `model: haiku` did not switch on either path. `context: fork` + `model:` does switch (46/48 forked `commit` runs were on Sonnet). Full record: `~/.claude/knowledge/platform-constraints/2026-09-24-inline-skill-model-switches-only-on-typed.md`.

**A typed inline switch is not free.** Mid-session, the new model has no cache for the conversation and pays the write price on all of it; the output-price saving on one turn rarely covers that.

**Anthropic's own guidance points the same way** ("What a task costs on Opus 5.5", 2026-09): "Raise effort before you change models"; "Move down to Sonnet or Haiku for lookups, not for writing code … Keep judgment calls on the main model."

## Classification

Decide what the skill **does at runtime**, not what it is named.

| Class | Dominant work | Config |
|---|---|---|
| **Lookup / retrieval** | Search a corpus, read logs or output, return snippets or a summary | `context: fork` + `model: sonnet` (add `agent: Explore` when it needs no CLAUDE.md) |
| **Tool wrapper** | Call a CLI/API, return structured output, no judgment | `context: fork` + `model: sonnet` or `haiku` |
| **Mechanical execution that writes** | Applies a verified plan, edits files, runs checks | inherit; no `model:` pin |
| **Judgment** | Finds defects, critiques, infers root cause | inherit; do **not** pin `effort:` |
| **Synthesis** | Writes plans, designs, options | inherit — do not downgrade |
| **Orchestration** | Dispatches skills/agents, coordinates a flow | inherit — do not downgrade |

A subagent a skill dispatches is classified on its own: `execute-plan` (skill) inherits, while the per-task agents its Workflow script spawns are pinned `model: 'sonnet'` in `execute-plan.workflow.js` — that agent-level pin is where the 2026-05 savings actually came from.

## Decision questions (in order)

1. **Does it need the conversation history or AskUserQuestion?** Yes → it must stay inline, so no small-model pin is possible (inline pins do not switch).
2. **Is it lookup work whose output is cheap to check?** Yes → fork + small model. A small model that misreads a search sends the main model after the wrong file; keep it to work where a mistake is easy to spot.
3. **Does it write code/files, judge, design, or coordinate?** Yes → inherit.
4. **Is it visibly lazy or visibly slow?** Adjust `effort`, not `model`, within anti-patterns 6–7.

## Examples in this repo

| Skill / agent | Class | Configured |
|---|---|---|
| `commit` | Tool wrapper (git classification) | `model: sonnet` + `context: fork` — moved off `haiku` after the haiku fork intermittently skipped the skill body |
| `kb` | Lookup | `model: sonnet` + `context: fork` + `agent: Explore` |
| `audit-tokens` | Tool wrapper (scripts do the analysis) | `model: sonnet` + `context: fork` |
| `execute-plan` (skill) | Orchestration of a verified plan | inherit; its Workflow agents are pinned sonnet |
| `test-runner` (agent) | Lookup (filter build/test output) | `model: sonnet` |
| `verify-plan`, `write-plan`, `run-phase`, `fix-bug`, `review-execution` | Judgment / Synthesis / Orchestration | inherit |
| `ui-reviewer`, `design-reviewer`, `feature-reviewer`, `judge` (agents) | Judgment | inherit — moved off `sonnet` on 2026-09-24 |

## Anti-patterns to flag

1. **Inline `model:` without `context: fork`** (skill): a no-op whenever Claude auto-invokes the skill, and a cache rebuild when the user types it. Flag as Minor; fix by removing it, or by adding `context: fork` if the work is lookup that needs no history. The only accepted exception is a `disable-model-invocation: true` skill the owner has deliberately kept pinned.
2. **Small model on judgment / synthesis / orchestration / writing work** (skill or agent): silent quality loss downstream. Flag as Bug.
3. **`context: fork` on a multi-step interactive skill**: the fork cannot reach the user mid-flow. Flag as Logic.
4. **`context: fork` without an actionable prompt in the skill body**: the subagent receives guidelines but no task and returns empty. Flag as Logic.
5. **`model:` set but `effort:` mismatched**: e.g. `model: haiku, effort: high` — Haiku supports no effort level; the field is ignored. Flag as Minor.
6. **Pinned `effort:` on a judgment/review agent**: `effort:` overrides the session level; it is a ceiling, not a floor, and silently caps `/effort xhigh`, `/effort max` and ultracode. Flag as Bug.
7. **Below-default `effort:` on an agent with verification duty** (runs tests, executes a `**Verify:**` step, decides pass/fail): the documented cause of skipped files and unrun tests. Flag as Bug.

**Axis reminder.** `model` = *knowing more* (subtle bugs, unfamiliar domains). `effort` = *trying harder* (files read, checks run). Full reference: `~/.claude/knowledge/api-usage/2026-07-09-skillsubagent-effort-overrides-session-e.md`.

## Constraints on recommendation

- This is a heuristic guide. Recommend, don't enforce.
- Before recommending any downgrade, cite measured usage (turns, cost, failure count), not a prediction.
- Before building a rule on a frontmatter knob, probe that the knob does what it claims (a positive-control run that must switch models).
