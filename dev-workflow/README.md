# dev-workflow

Cross-stack development workflow plugin for Claude Code. Provides a full plan-execute-review lifecycle with model-appropriate task routing.

## Architecture

**Opus thinks, Sonnet does, Opus reviews.** Judgment-intensive steps (planning, fixing) run in main context with Opus and full conversation history. Mechanical execution runs as a dispatched Sonnet agent. Reviews run as dispatched Opus agents for unbiased assessment.

```
run-phase (orchestrator, main context — opus)
  → write plan (main context — opus, full user intent)
  → plan-verifier agent (opus)         → verification report
  → execute-plan agent (sonnet)        → code changes + build/test results
  → feature-spec-writer agent (sonnet) → spec file
  → review agents (parallel — opus)    → consolidated findings
  → fix all issues (main context — opus: execution failures + review gaps)
  → Phase done

finalize (after all phases complete)
  → full test suite (0 fail, 0 skip)
  → cross-phase criteria regression
  → cumulative test coverage audit     → validation report
```

## Workflows

This plugin supports three primary workflows. Pick the one matching the work shape; don't mix.

### Flow A — Multi-phase / large change

For new projects, multi-feature rollouts, or refactors spanning multiple independent units.

```
write-dev-guide                          → docs/04-dev-guide/dev-guide.md (phased task tree)
  ↓ (per phase, repeat until done)
run-phase
  → write-plan         (in run-phase Step 2)
  → verify-plan        (Step 3, dispatches plan-verifier agent)
  → execute-plan       (Step 4, runs Workflow per segment with hard-stop checkpoint gates)
  → test-changes       (Step 5, dispatches test-runner agent)
  → review agents      (Step 6, parallel: ui/design/feature-reviewer when applicable)
  → feature-spec-writer (Step 6, when phase delivers user-facing feature)
  → fix issues         (Step 7, back to main context)
  ↓ (all phases done)
finalize                                 → cross-phase validation report
  ↓
finish-branch                            → merge/PR/discard
```

**When to use**: ≥ 3 independent components, ≥ 2 weeks of work, or work that needs review boundaries between conceptual units.

**When NOT to use**: single-file changes, single-feature additions, bug fixes — use Flow B or C.

### Flow B — Single feature / standalone change

For one feature, refactor, or enhancement that fits within a single review boundary.

```
(optional) brainstorm                    → clarify requirements first
write-plan                               → docs/06-plans/YYYY-MM-DD-<name>-plan.md
verify-plan                              → verification report (catches plan defects before execution)
execute-plan                             → code changes + batch state file
test-changes                             → build/test/lint report
review-before-commit                     → semantic classification + breaking-change detection
commit                                   → conventional commit
```

**When to use**: one feature, one bug class, one refactor scope.

**When NOT to use**: trivial single-line edits (just do it); work spanning multiple independent units (use Flow A).

**Review is automatic here, not optional.** `execute-plan` invokes `review-execution` on finish with `mode: advisory` — findings are presented, nothing is auto-fixed, nothing blocks, the decision stays yours. It used to be a suggestion line at the end of the output, which meant it never actually ran on this flow. Lenses are routed from the diff's shape (correctness / test-coverage / breaking-changes / root-cause-depth always; plan-vs-code because a plan is present; Apple reviewers only for the surfaces they own).

`review-before-commit` stays deliberately outside every flow — it is the manual pre-commit double-check you run when you want one, not a pipeline step.

### Flow C — Bug fix

For reported errors, unexpected behavior, build failures, or batches of issues against a verification surface.

```
fix-bug                                  → start (现状/预期) + finish line (verified on the real path) + known dead ends; the path is the model's call
  ↓ (small, local fix)
  direct edit + verify
  ↓ (multi-file / architectural / replacing a design)
  write-plan with the diagnosis evidence → execute-plan + test-changes
  ↓ (optional, post-fix)
collect-lesson                           → ~/.claude/knowledge/<topic>.md
```

**When to use**: error with stack trace, unexpected behavior, build/test failures, multi-issue batches.

**When NOT to use**: feature additions (use Flow B); explanation-only questions with no defect to fix (answer directly).

**Multi-issue mode**: when input is N issues against a running verification surface (API/CLI/REPL/agent), fix-bug auto-switches to loop mode — diagnoses per issue, bundles into a single plan, dispatches once.

### Skill Index by Role

Skills are categorized by how they enter the runtime. This governs `user-invocable` frontmatter and how each skill appears (or doesn't) when users type `/`.

| Role | Frontmatter | Skills |
|---|---|---|
| **Flow entry** (user types or model routes) | `user-invocable: true` | write-dev-guide, run-phase, write-plan, verify-plan, fix-bug, brainstorm, commit, review-before-commit, review-execution, finalize, finish-branch, issue, kb, crystallize, collect-lesson, handoff, fork-this, audit-tokens |
| **Inline only** (dispatched by other skills, never user-typed) | `user-invocable: false` | execute-plan, test-changes, feature-spec-writer (agent), design-analyzer (agent), reviewer agents (ui/design/feature/apple-reviewer) |
| **Long-tail / on-demand** (rarely needed, kept for the case when needed) | `user-invocable: true` | next-increment, distill-discussion, generate-bases-views, design-parity-build (apple-dev), characterization-test (apple-dev) |
| **Guide / reference** (advisory pattern doc, not executable workflow) | should be a reference, not a skill | parallel-agents (now at references/parallel-agents.md); use EnterWorktree tool directly for worktree operations |

**Adding a new skill?** Decide its role first. Flow-entry skills must map to A/B/C or justify a new flow. Inline-only skills must have a named driver (another skill that dispatches them). Long-tail skills must have a stated trigger condition (typically "when user mentions X" or "when N commits since Y"). Guide-type entries should be reference files under `references/`, not SKILL.md files.

**Why this matters**: every SKILL.md with `user-invocable: true` consumes system-prompt bytes in every session for routing-model triggering. Adding skills indiscriminately taxes cache without proportional value. Inline-only and reference moves keep the `/` menu lean.

## Agent Dispatch Guidelines

### Explore-Intent Dispatch

When dispatching a subagent (via Agent tool) for exploration/understanding purposes, include this instruction in the dispatch prompt:

> Return your findings as:
> 1. Summary (3-5 sentences): what you found, key patterns, notable concerns
> 2. Key files (5-10): `{file_path} — {one-line relevance}`
> 3. Do NOT paste full file contents into your response.

The main context reads specific files as needed based on the returned list.

This pattern applies to "understand X" / "explore Y" dispatches. Verification agents ("verify X" / "audit Y") should continue returning inline evidence.

## Agents

| Agent | Model | Tools | Purpose |
|-------|-------|-------|---------|
| execute-plan | sonnet | Glob, Grep, Read, Write, Edit, Bash, LSP | Per-task plan executor — invoked by the execute-plan Workflow, runs one task + Verify, returns a structured result. Writes no bookkeeping files; the main agent is sole writer of the checkpoint and execution report |
| test-runner | sonnet | Glob, Grep, Read, Write, Bash | Runs build/test/lint suite, filters output to errors + summary, writes structured report |
| design-analyzer | opus | Glob, Grep, Read, Write | Multi-modal design prototype analysis (dual-channel image+code) |
| flow-tracer | opus | Glob, Grep, Read | End-to-end call chain tracing with break detection (read-only) |
| implementation-reviewer | opus | Glob, Grep, Read, Bash, Write | Plan-vs-code verification and design fidelity audit |
| plan-verifier | opus | Glob, Grep, Read, Bash, Write | Verification-first plan validation (S1/S2/U1/DF/CF/AR) |
| dev-guide-verifier | opus | Glob, Grep, Read, Bash, Write | Dev-guide quality verification (coverage, dependencies, data flow, code overlap, terms, criteria, structure) |
| feature-spec-writer | sonnet | Glob, Grep, Read, Write | Design-vs-implementation feature spec generation |
| distill-discussion-reader | sonnet | Read, Glob, Grep | Discussion file classification and structured extraction (read-only) |

## Skills

### Daily entry points

| Skill | Type | Description |
|-------|------|-------------|
| run-phase | orchestrator | Phase lifecycle: plan → verify → execute (segmented, checkpoint-gated) → test → review → fix → done. State + dev-guide parsing owned by `scripts/phase.py`, the sole writer of `.claude/dev-workflow-state.json` |
| review-execution | dispatcher | **The single review dispatcher for this marketplace.** 5 always-on lenses (correctness / test-coverage / breaking-changes / root-cause-depth / secrets-and-transport) + `implementation-reviewer` when given a plan + Apple reviewers routed by what the diff touches. Inputs: `plan_path`, `scope_files`, `mode` (`gated` \| `advisory`). Callers pass inputs, not agent lists — `run-phase` Step 6, `execute-plan`'s standalone finish, `/afk` dev-guide mode's per-phase gate and `/afk`'s terminal stop all route through it |
| fix-bug | interactive | Bug fixing by outcome: plain-language 现状/预期, verified on the user's real path, known dead ends ruled out |
| write-plan | interactive | Writes implementation plan with Impact Map and Task Contract |
| write-dev-guide | interactive | Writes phased dev-guide for multi-unit work |
| commit | fork (sonnet) | Conventional commit analysis and execution |
| review-before-commit | interactive | Pre-commit semantic review: classify changes, detect breaking changes, interactive risk confirmation |
| issue | interactive | GitHub Issue unified entry point |
| finish-branch | interactive | Test, document, merge/PR/discard |

### Advanced / internally routed capabilities

| Skill | Type | Description |
|-------|------|-------------|
| execute-plan | dispatcher | Segmented plan execution — Workflow per segment with hard-stop checkpoint gates + cross-session resume |
| afk | setup for native `/goal` (manual entry, inherit) | Two entry points: goal mode (below) and **dev-guide mode**, which drives an already-verified, already-planned multi-phase dev-guide across phase seams — the one case goal mode does not cover; a stopped dev-guide run resumes when the user types `/afk` again (it picks up `.claude/dev-workflow-state.json` and hands back a fresh `/goal` line), and its fixed parts (resume branch, DP sweep over plans and verify-plan reports, stop rows, `**Chosen:**` write-back, stop card, goal line) live in the tested `afk/scripts/guide.py`. **Setup, not a loop** — Claude Code's own [`/goal`](https://code.claude.com/docs/en/goal) already runs the loop with an independent evaluator, so this skill does not reimplement it. It does the four things that must happen *before* the user leaves: distill `[范围]` once plus a `[目标 N]`/`[判据 N]`/`[分辨力 N]` block for **every** goal handed over (silently picking one is a defect, and all of them still fold into a single `/goal` line — `/goal` holds one goal per session); **run each judge twice with nothing changed between, on top of whatever prior readings `.claude/afk/logs/` already holds for it** (a check nobody has seen fail is not a check; a check whose own noise spans the threshold is a coin — one red reading cannot tell those apart, and every threshold carries a mechanism line naming where its headroom comes from); clear the human-required unblocks that kill unattended Apple runs (device auto-lock first — AFK *causes* the lock — then wired transport, then a real UI-test probe for the on-device trust dialog, never an xctrunner reinstall); then hand back a ready-to-paste `/goal` line whose second branch is an **artifact** (a `## 终止：` section in the run log), never a turn count — an intention-shaped escape clause gets refused, and only the user can `/goal clear`. Routes by two write-it-down tests, not by judgment: end state writable + route known → the plan pipeline; end state writable + route unknown → here; end state not writable → the user stays. Two mechanical gates during the run — a done-claim carries freshly-run raw output (which is also what the transcript-only evaluator needs), and no prose hand-back once the model already holds a view |
| self-pacing | pointer stub | A pointer to `/afk` dev-guide mode, which absorbed the one case this skill covered: driving an already-verified multi-phase dev-guide across phase seams. `afk/DESIGN-dev-guide-mode.md` holds the moved invariants. `phase` / one-plan requests route to `/execute-plan` instead |
| test-changes | dispatcher | Dispatches test-runner agent for build/test/lint suite execution |
| brainstorm | interactive | Design exploration before implementation |
| design-decision | interactive | Trade-off analysis with essential/accidental complexity |
| handoff | main session (inherit) | Full context transfer for cross-day/cross-person session hand-off; the callee `/afk` invokes at **every** stop (its only handoff outlet); in dev-guide mode the card is written by `guide.py card`, not this skill. **Not forked** — `context: fork` was dropped in `2ea667f`, and a fork would break both consumers: a forked agent cannot see the live session, and it runs in the background so the doc would not exist on disk before the calling turn ends |
| generate-design-prompt | interactive | Cross-platform design tool prompt generation (iOS/macOS → Stitch DSL; Web → Figma placeholder); supports initial and refinement modes |
| understand-design | dispatcher | Dual-channel design prototype analysis, token extraction, platform translation |
| verify-plan | dispatcher | Gathers context, dispatches plan-verifier agent |
| next-increment | interactive | Proposes 3-5 archetype-diverse next-step candidates for mature codebases, writes mini-spec for chosen one |
| write-feature-spec | dispatcher | Gathers context, dispatches feature-spec-writer agent |
| audit-tokens | fork (sonnet) | Multi-dimensional Claude Code token consumption analysis with self-contained HTML report; auto cost-posture recommendations; auto-invokes its own scripts/diagnose.py for root-cause attribution |
| fork-this | fork (sonnet) | Mid-session orthogonal split: when topic A's discussion surfaces problem B, generate minimal seed prompt for B in a new session WITHOUT polluting current A context |
| crystallize | interactive | Lock settled decisions from current session into a persistent crystal file |
| collect-lesson | interactive | Capture development lessons learned; decides whether a new lesson supersedes, corrects, or only narrows an existing entry, and records `verified_on` for platform constraints |
| kb | interactive | Cross-project knowledge base search; picks candidates from a title/keyword catalog (semantic, mixed Chinese/English) plus a literal pass, confirmed by reading; hides superseded entries behind their successor and flags platform entries verified on an older Claude Code version |
| distill-discussion | interactive | Extract structured outputs (crystals, lessons) from raw discussion files |
| generate-bases-views | interactive | Generate Obsidian Bases (.base) views over crystals, lessons, and vault notes |
| finalize | interactive | Cross-phase validation: full test suite, acceptance criteria regression, cumulative coverage audit |

## Hooks

| Event | Script | Purpose |
|-------|--------|---------|
| SessionStart | check-workflow-state.sh | Detects in-progress phase, prompts resume |
| PreToolUse | bug-fix-gate.py | Enforces the fix-bug flow's **现状: / 预期:** statement before a fix edit lands |
| PreToolUse (Bash, `git *`) | scan-secrets.sh | Intercepts git commit (incl. `git -C <path> commit`, `--git-dir`, `cd <dir> && git commit`), blocks if secrets detected in the target repo's staged content |
| PreToolUse (Edit / Write / MultiEdit / NotebookEdit, Bash) | guard-state-file.py | Denies hand writes of `.claude/dev-workflow-state.json` / `.yml` — file-tool edits, and shell writes (`>`, `tee`, `sed -i`, `cp`/`mv` onto it, interpreter one-liners); `phase.py` is the only writer |

> **2026-09-05 迁出。** 九个 hook 移到了 `~/.claude/hooks/`（注册改在 `settings.json`）：
> `backup-before-checkout.py` / `nudge-named-source.py` / `design-sync-guard.py` / `kb-tripwire.py` /
> `cost-hint.sh`（原 `suggest-agent-dispatch.sh`） / `suggest-read-routing.sh` / `verify-agent-output.py` /
> `lint-claude-md.py` / `check-repeated-edit.py`。
>
> 判据是**规则源在哪**：这九个执行的都是全局 `~/.claude/CLAUDE.md` 里定义的规则（成本路由 / Read 路由 /
> 用户原文指定的信息源 / sub-agent 报告是 claim 不是 fact / 开局先查知识库 / Claude Design 访问 /
> `git checkout` 前备份 / Edit 前陈述预期），或以全局 CLAUDE.md 本身为作用对象（`lint-claude-md` 扫的是
> 这台机器上**所有** plugin 的 skill 目录），不是本插件任何 skill 的规则。
>
> 留下的四个反过来——各自绑着本插件的 skill 或状态文件：`bug-fix-gate` ↔ `/fix-bug` 模板、
> `check-workflow-state` 与 `guard-state-file` ↔ `dev-workflow-state.json`（后者 2026-09-24 随 `phase.py` 新增）、
> `scan-secrets` ↔ `/commit` 流程（且失效代价是密钥泄漏，不为归属整洁去动它）。
> 改规则时该同时改哪个 hook，按这条判据找。

## Workflow State

`run-phase` persists progress to `.claude/dev-workflow-state.json` via `run-phase/scripts/phase.py` — the sole reader/writer, and the sole dev-guide parser, shared by `finalize`, `execute-plan`, `review-before-commit` and `/afk` dev-guide mode (legacy `.yml` is auto-migrated via `phase.py migrate` on first encounter), enabling cross-session resume. The SessionStart hook detects this file (through `phase.py status --hook`) and prompts the user to continue.

## Design Principles

- **Opus thinks, Sonnet does, Opus reviews** — model routing based on task type, not context conservation
- Bug fix, plan verification, and design decision skills use universal methodology (value domain tracing, reverse reasoning, entry point uniqueness, complexity analysis) that works across tech stacks
- iOS-specific checks (Design Token consistency, Swift concurrency) are provided by the `apple-dev` plugin's references
- Review agents run in separate contexts for unbiased assessment; writing tasks run in main context to benefit from full conversation history

## Companion commands

After installing, run `/less-permission-prompts` (built into Claude Code 2.1.111+) to scan your recent transcripts and generate a read-only Bash/MCP allowlist tailored to your usage — reduces permission prompts when running this plugin's dispatchers.
