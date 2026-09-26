# Cost Posture for Skills and Agents

Reference doc consumed by `plugin-master` (Create route), `plugin-reviewer` (Dimension 7.5) and `audit-tokens` (recommendations). It decides which `model` / `effort` / `context` frontmatter a skill or agent should carry.

> **Axis note — keep these separate.** This document is the **compute-cost** axis (which `model` / `effort` / `context` tier a skill runs on). It is orthogonal to the **context-cost** axis (prose economy — dead text that loads on every enumeration), which lives in `plugin-reviewer` **D7.6 (deletion test)**. Do not fold one check into the other.

## The rule

1. **Small models only for lookup work, and only through an isolated context.** Searching, reading logs or test output, "where is this defined", wrapping a CLI and returning structured output — put it behind `context: fork` (skill) or an agent definition, then set `model: sonnet` or `model: haiku`.
2. **Everything else stays on the main model.** Judgment, synthesis, orchestration, and any work that writes code or files: no `model:` pin.
3. **Every skill and agent pins `effort:` to what its task needs.** The pin is the task's right size, in both directions: `low` on a lookup while the session runs `high` saves verification turns it has no use for; `high` on a reviewer while the session runs `xhigh` saves effort that task cannot use. Session `/effort` is for the main conversation, not for a skill's task. When quality or cost is off, change `effort` before changing the model.

## Why

**The old premise is gone.** This file used to say an Opus turn costs ~20× a Sonnet turn. That compared a large main-thread Opus turn with a small subagent Sonnet turn — context size, not model price. At list prices (2026-09) Opus 5.5 vs Sonnet 5 is 2× on input and output, 2× on 1h cache writes, and **equal on cache reads** ($0.20/M), which is the largest line in a long session.

**The savings were small.** Over 60 days of indie-toolkit usage (2026-07-26 → 09-24), every Sonnet/Haiku downgrade together saved ~$103 of ~$7,488 API-equivalent spend (1.4%). Agent/fork pins declared in this repo account for ~$22 of that.

**Inline pins barely work.** Probed on CC 2.1.281: an inline `model: sonnet` (no `context: fork`) switches only when the user types `/skill`; when Claude auto-invokes the skill through the Skill tool it stays on the session model. Inline `model: haiku` did not switch on either path. `context: fork` + `model:` does switch (46/48 forked `commit` runs were on Sonnet). Full record: `~/.claude/knowledge/platform-constraints/2026-09-24-inline-skill-model-switches-only-on-typed.md`.

**A typed inline switch is not free.** Mid-session, the new model has no cache for the conversation and pays the write price on all of it; the output-price saving on one turn rarely covers that.

**Effort levels** (from "Spending your effort", claude.dev blog, 2026-09):

| Level | Use for |
|---|---|
| `low` | Quick, in-the-loop, mechanical: lookups, CLI wrappers, brainstorming or sketching the user steers step by step |
| `medium` | Regular engineering: plans, specs, docs, code written from a clear brief |
| `high` | Verification matters or edge cases hide: review, pass/fail judging, brownfield bug fixing, security, irreversible or outward-facing actions |
| `xhigh` | Fully autonomous end-to-end runs (build + verify with no human in the loop) |
| `max` | Reserved; needs a measured reason |

The blog's workflow — implement at a lower effort, verify at `high` — maps onto this repo as implementer pins below reviewer pins.

**Where the pin takes effect** (probed on Claude Code 2.1.283, 2026-09-26, headless `claude -p --effort <session>`, reading `$CLAUDE_EFFORT` from Bash inside the skill/agent):

| Path | Session | Pin | Observed | Takes effect? |
|---|---|---|---|---|
| Agent (`effort:` in agent file) | high | low | low | yes |
| Forked skill (`context: fork`) | high | low | low | yes |
| Inline skill, user types `/skill` | high / medium | low / xhigh | low / xhigh | yes, both directions |
| Inline skill, Claude auto-invokes via Skill tool | high / medium | low / xhigh | session value | **no** |

Same shape as the inline `model:` finding: on the auto-invoke path the harness resolves the pin (`${CLAUDE_EFFORT}` in the skill body renders `low`) but the turn keeps the session effort. Keep the pin on inline skills anyway — it applies on typed invocation and records the task's size — but do not count on it when Claude routes to the skill itself. Work that must run at a fixed effort belongs in an agent or a forked skill. Never fork a skill that needs the conversation; instead keep the conversation inline and move the fixed-effort judgment into an agent the skill dispatches with explicit inputs (see the "Inline shell + pinned agent" row below). A Workflow script's `agent(prompt, {effort})` takes it per call. Haiku supports no effort level.

**Anthropic's own guidance points the same way** ("What a task costs on Opus 5.5", 2026-09): "Raise effort before you change models"; "Move down to Sonnet or Haiku for lookups, not for writing code … Keep judgment calls on the main model."

## Classification

Decide what the skill **does at runtime**, not what it is named.

| Class | Dominant work | Config |
|---|---|---|
| **Lookup / retrieval** | Search a corpus, read logs or output, return snippets or a summary | `context: fork` + `model: sonnet` (add `agent: Explore` when it needs no CLAUDE.md) + `effort: low` |
| **Tool wrapper** | Call a CLI/API, return structured output, no judgment | `context: fork` + `model: sonnet` + `effort: low`, or `model: haiku` (no effort) |
| **Mechanical execution that writes** | Applies a verified plan, edits files, runs checks | inherit model; `effort: medium`, `high` if it decides pass/fail |
| **Judgment** | Finds defects, critiques, infers root cause | inherit model; `effort: high` |
| **Synthesis** | Writes plans, designs, options | inherit model; `effort: medium` (`low` when the user steers each step) |
| **Orchestration** | Dispatches skills/agents, coordinates a flow | inherit model; `effort: xhigh` when fully autonomous, else by its own work — the agents it dispatches carry their own pins |

A subagent a skill dispatches is classified on its own: `execute-plan` (skill) inherits, while the per-task agents its Workflow script spawns are pinned `model: 'sonnet'` in `execute-plan.workflow.js` — that agent-level pin is where the 2026-05 savings actually came from.

## Decision questions (in order)

1. **Does it need the conversation history or AskUserQuestion?** Yes → it must stay inline, so no small-model pin is possible (inline pins do not switch).
2. **Is it lookup work whose output is cheap to check?** Yes → fork + small model. A small model that misreads a search sends the main model after the wrong file; keep it to work where a mistake is easy to spot.
3. **Does it write code/files, judge, design, or coordinate?** Yes → inherit.
4. **Which effort does the task need?** Pick from the levels table. Visibly lazy → raise it; visibly slow on simple work → lower it. Adjust `effort`, not `model`.

## Examples in this repo

| Skill / agent | Class | Configured |
|---|---|---|
| `commit` | Tool wrapper (git classification) | `model: sonnet` + `context: fork` + `effort: medium` (secrets gate) — moved off `haiku` after the haiku fork intermittently skipped the skill body |
| `kb` | Lookup | `model: sonnet` + `context: fork` + `agent: Explore` + `effort: low` |
| `audit-tokens` | Tool wrapper (scripts do the analysis) | `model: sonnet` + `context: fork` + `effort: low` |
| `execute-plan` (skill) | Orchestration of a verified plan | inherit, `effort: medium`; its Workflow agents are pinned sonnet + `effort: 'high'` (they run Verify) |
| `test-runner` (agent) | Lookup (filter build/test output) | `model: sonnet` + `effort: high` (decides pass/fail) |
| `verify-plan`, `write-plan`, `run-phase`, `fix-bug`, `review-execution` | Judgment / Synthesis / Orchestration | inherit |
| `ui-reviewer`, `design-reviewer`, `feature-reviewer`, `judge` (agents) | Judgment | inherit — moved off `sonnet` on 2026-09-24; `effort: high` |
| `afk`, `runtime-feature-verify` | Autonomous end-to-end | inherit, `effort: xhigh` (`afk` is `disable-model-invocation`, so its pin always applies) |
| `fix-bug`, `asc-submit-preview`, `asc-listing`, `swiftui-visual-audit`, `design-parity-build`, `review-before-commit` | Inline shell + pinned agent | Skill `effort: medium`/`high` for its own inline work; the high judgment runs in `bug-diagnoser`, `app-review-auditor`, `render-auditor`, `design-parity-auditor`, `change-classifier` (all `effort: high`) so it holds even when Claude auto-invokes the skill |

## Anti-patterns to flag

1. **Inline `model:` without `context: fork`** (skill): a no-op whenever Claude auto-invokes the skill, and a cache rebuild when the user types it. Flag as Minor; fix by removing it, or by adding `context: fork` if the work is lookup that needs no history. The only accepted exception is a `disable-model-invocation: true` skill the owner has deliberately kept pinned.
2. **Small model on judgment / synthesis / orchestration / writing work** (skill or agent): silent quality loss downstream. Flag as Bug.
3. **`context: fork` on a multi-step interactive skill**: the fork cannot reach the user mid-flow. Flag as Logic.
4. **`context: fork` without an actionable prompt in the skill body**: the subagent receives guidelines but no task and returns empty. Flag as Logic.
5. **`model:` set but `effort:` mismatched**: e.g. `model: haiku, effort: high` — Haiku supports no effort level; the field is ignored. Flag as Minor.
6. **Missing or mismatched `effort:`**: `effort:` overrides the session level in both directions, which is the point — the pin is the task's right size. No pin means the task runs at whatever the session happens to be (a lookup at `xhigh`, a review at `low`): flag as Minor. A pin that contradicts the class (e.g. `high` on a lookup, `xhigh` on a single review) — flag as Bug. (Until 2026-09-26 this entry called any pin on review work a Bug because it "caps `/effort max`"; retired — if a review needs more than `high`, the pin is wrong, not the fact of pinning.)
7. **Below-default `effort:` on an agent with verification duty** (runs tests, executes a `**Verify:**` step, decides pass/fail): the documented cause of skipped files and unrun tests. Flag as Bug.

**Axis reminder.** `model` = *knowing more* (subtle bugs, unfamiliar domains). `effort` = *trying harder* (files read, checks run). Full reference: `~/.claude/knowledge/api-usage/2026-07-09-skillsubagent-effort-overrides-session-e.md`.

## Constraints on recommendation

- This is a heuristic guide. Recommend, don't enforce.
- Before recommending any downgrade, cite measured usage (turns, cost, failure count), not a prediction.
- Before building a rule on a frontmatter knob, probe that the knob does what it claims (a positive-control run that must switch models).
