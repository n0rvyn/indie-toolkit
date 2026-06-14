---
name: self-pacing
description: "Use when the user wants verified work driven to green autonomously — stopping ONLY for critical decisions or severe failures, auto-resolving low-severity decisions to their recommended option, and accumulating everything into a final review. TWO MODES: bare '/self-pacing' drives the WHOLE dev-guide across all phases to the end (phase seams do not pause it); '/self-pacing phase' (aliases: 'in-phase', 'single', 'one') drives ONE phase or one standalone plan, then stops at the seam for review. Triggers: '/self-pacing', 'self-pace', 'run it to green', 'autonomous run', \"don't stop at every checkpoint\", '自定速', '自己跑完', '少停几次', '一撸到底', '一口气跑到绿'. Prompt-only driver: REUSES execute-plan's segmented mechanics (compute_checkpoints.py + execute-plan.workflow.js), test-changes, and the review agents WITHOUT modifying any of them; the only difference is the stop-policy applied between segments and between phases. Not when: no verified plan / dev-guide exists (run write-plan → verify-plan, or write-dev-guide → run-phase, first); the work is divergent design / exploration (use brainstorm); the plan tasks lack executable `Automated verify` lines (no red/green signal to converge on)."
disable-model-invocation: true
---

<!-- cost-posture: inherit (judgment + orchestration — severity classification, decision auto-resolution, and loop control are judgment calls; do NOT downgrade to sonnet/haiku per dev-workflow Skill Cost Posture rule) -->

## What this is

`self-pacing` drives already-planned work to green **without pausing for routine review**. It stops only when it hits something that genuinely needs a human — a critical decision or a severe failure — and rolls everything else into a single review.

It invents nothing. The whole skill is this prompt plus a **stop-policy** layered over execution machinery that already exists. It does not modify, replace, or require changes to any other skill.

**The one thing it changes vs. the normal flow:** the normal flow (run-phase / execute-plan) pauses at every batch hard-stop and (in run-phase) at every phase boundary, waiting for you to say "continue". Those are *pacing* pauses — they fire because of position, not because anything is wrong. `self-pacing` suppresses pacing pauses and gates only on *severity*.

## Modes

| Invocation | Scope | Stops at phase seams? |
|---|---|---|
| `/self-pacing` | **guide** — the whole dev-guide, all remaining phases, to the end | No — auto-advances phase→phase while green |
| `/self-pacing phase` (aliases `in-phase` / `single` / `one`) | **phase** — one phase, or one standalone plan | Yes — stops at the seam for the final review |

Both modes suppress *segment-level* pacing pauses and honor every *severity* gate. The only difference is whether a clean phase boundary pauses (phase mode) or auto-advances (guide mode).

**guide mode is not unguarded.** Each phase still runs `test-changes` + the review agents; a `must-fix` finding, a severe failure, a `blocking` decision, or an explicit `<!-- checkpoint -->` halts the train. Only the *clean* phase boundary stops being a pause.

## When NOT to use

- **No verified plan / dev-guide yet** → the divergent work has to happen first. Send the user to `write-plan` → `verify-plan` (single unit) or `write-dev-guide` → `run-phase` (phased). `self-pacing` is a driver, not a planner.
- **Divergent / generative work** (design exploration, UX shaping, "what should we build") → `brainstorm`. A self-paced loop has no red/green signal to converge on here and will produce confident-sounding drift.
- **Plan tasks have no executable `Automated verify`** → there is no green to drive toward. Back to `write-plan`.

## How it relates to the existing flow (governing-prompt principle)

`self-pacing` is the **governing context** while it runs. When it reuses lower-level machinery, its stop-policy takes precedence over that machinery's default pacing behavior:

- **Execution** reuses the same segmented mechanics as `execute-plan`: `compute_checkpoints.py` for batches + hard-stops, and `execute-plan.workflow.js` (the Workflow script — it dispatches one sonnet agent per task and *cannot itself pause*) for per-task dispatch. `self-pacing` owns the loop *between* segments and *between* phases, and applies the stop-policy there.
- **Per-phase work** (when a phase has no plan yet, in guide mode) reuses the Plan Writing Reference in `${CLAUDE_PLUGIN_ROOT}/skills/write-plan/SKILL.md`, then `verify-plan`, exactly as run-phase Step 2–3 do — but without run-phase's per-phase scope-confirmation pause (the upfront dev-guide confirmation is the authorization; see Step 2).
- **Severity tags are read, not invented.** Decision severity (`blocking` / `recommended`), verify verdicts (`must-revise`), and review findings (`must-fix` / `nice-to-have`) already exist in the plan / verify report / review reports. `self-pacing` honors those tags.
- **Downstream quality gates stay fully intact:** `test-changes`, the review agents, the `verify-agent-output.py` hook, and the per-unit completion gate all still run. `self-pacing` removes only the *pacing* pauses, never the *severity* gates.

No file under any other skill is edited by this skill.

## The Stop Policy (the core of the skill)

| Situation | Maps to existing tag | Action (both modes) |
|---|---|---|
| **Critical decision** | a `blocking` DP (plan / verify report) | **STOP** — present via AskUserQuestion, wait |
| **Severe failure** | a task's `Automated verify` fails after its steps, `verify-plan` returns `must-revise`, build breaks, a prior-green check regresses, or a review `must-fix` | **STOP** — surface evidence; no blind retry (run the `multi-issue-loop` postmortem question) |
| **Low-severity decision** | a `recommended` DP (carries its own `**Recommendation:**`) | **CONTINUE** — adopt the recommended option, record in the run log |
| **Low-severity finding** | a `nice-to-have` review item | **CONTINUE** — defer to the run log |
| **Routine pacing pause** | `compute_checkpoints.py` hard-stop from batch 0 or a green dependency-hub batch | **CONTINUE** — auto-advance to next segment |
| **Author-declared seam** | an explicit `<!-- checkpoint -->` marker in the plan body | **STOP** — author placed it deliberately; skipping it is a forbidden silent downgrade |

Phase boundary is the **only** mode-dependent row:

| Phase boundary (phase done, green, no must-fix) | phase mode | guide mode |
|---|---|---|
| | **STOP** → final review | **CONTINUE** → next phase (log the seam crossing) |

**Conservative default (load-bearing):** `self-pacing` leans entirely on upstream severity tags being correct. If a decision's severity is ambiguous, or a finding could plausibly be critical, **treat it as `blocking` and STOP.** Auto-resolving something that should have stopped is the expensive failure mode; an unnecessary stop is cheap. When in doubt, stop.

**Every auto-decision is visible.** A `recommended` DP adopted, a `nice-to-have` deferred, or a phase seam auto-crossed, without it appearing in the final review, is the "confident mess" failure mode. Every CONTINUE that resolved a decision, deferred a finding, or crossed a phase MUST land in the run log and appear in the final review.

## Process

### Step 1: Parse mode and resolve the target

1. **Parse mode** from the invocation argument:
   - no arg → **guide mode**
   - `phase` / `in-phase` / `single` / `one` → **phase mode**
2. **Resolve the target:**
   - **guide mode:** find the current dev-guide (`docs/06-plans/*-dev-guide.md`, prefer `current: true`). The unit list = all phases whose acceptance criteria are not yet all checked, in order. If no dev-guide exists, tell the user "guide mode needs a dev-guide — run `/write-dev-guide`, or use `/self-pacing phase` on a plan." and stop.
   - **phase mode:** resolve, in order — an explicit plan file the user named; the in-progress phase from `.claude/dev-workflow-state.json`; otherwise ask which phase / plan. If nothing resolves, send to `write-plan` / `run-phase`.
3. **Verification is mandatory** (the run will not pause per-segment for human review, so plan quality matters more, not less): for any plan about to run, require `## Verification` `Verdict: Approved` (or a verify report). If absent, invoke `dev-workflow:verify-plan`; `must-revise` is a severe gate → STOP. For phases without a plan yet (guide mode), the plan is written + verified inside the per-phase loop (Step 3) before execution.
4. Confirm tasks have executable `Automated verify` (or annotated `N/A — trivial`). A non-trivial task with no verify line → STOP, send to `write-plan`.

### Step 2: Authorize autonomous mode (the one upfront gate)

Autonomous, gate-suppressing execution must be a deliberate, explicit choice — never auto-entered. Present the policy, mode-aware, and get a single go-ahead.

**phase mode:**
```
self-pacing (phase) will run {target} to green on its own, then stop at the seam
for one review. It stops early only for: blocking decisions, severe failures, and
any explicit <!-- checkpoint --> you placed. It will take the recommended option on
low-severity decisions and defer nice-to-haves. Proceed? (yes / no)
```

**guide mode (extra loud — this crosses phase boundaries):**
```
⚠️ self-pacing (guide) will run ALL {N} remaining phases of {dev-guide} straight to
the end. It will NOT pause between phases. Each phase is still tested + reviewed, and
it WILL stop if it hits: a blocking decision, a severe/must-fix failure, or an explicit
<!-- checkpoint -->. Low-severity decisions take their recommended option; nice-to-haves
are deferred. You get ONE consolidated review at the very end (or wherever it stops).

Run all {N} phases to the end? (yes / no, I'll do them one at a time with /self-pacing phase)
```

Only an explicit yes proceeds. Start the run log at `.claude/self-pacing/<target-slug>.md`.

### Step 3: The run loop

**phase mode** runs the per-unit loop once. **guide mode** runs it per phase, in order, auto-advancing while green.

Per unit (one plan / one phase):

1. **Plan (guide mode, phase without a plan only):** write the phase's plan via the Plan Writing Reference, then `verify-plan`. Skip run-phase's scope-confirmation pause. A `must-revise` is severe → STOP.
2. **Resolve decisions up front.** Read `## Decisions`. `blocking` → STOP + AskUserQuestion (per `${CLAUDE_PLUGIN_ROOT}/references/decision-points.md`), record `**Chosen:**`. `recommended` → adopt its `**Recommendation:**`, write `**Chosen:**`, append to run log under "Auto-resolved decisions". (Conservative default applies.)
3. **Compute segments:** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/execute-plan/scripts/compute_checkpoints.py <plan_file> --k 3 --batch-size 5`; parse `{batches, hard_stops, tasks, ...}`.
4. **Init / resume** `.claude/execute-plan-checkpoint.json` exactly as `execute-plan` defines it (single-writer; `self-pacing` is the sole writer of the checkpoint and `execution-report.md` during its run).
5. **Segment loop:** for each segment, `Workflow({scriptPath: "${CLAUDE_PLUGIN_ROOT}/skills/execute-plan/execute-plan.workflow.js", args: {...}})` (this skill is a sanctioned Workflow trigger). Spot-check `files_written`, record `completed` + report from the returned array. Then apply the stop-policy at the boundary:
   - all `done` AND pacing boundary (batch 0 / green hub) → **auto-continue**, log "auto-continued past pacing checkpoint".
   - boundary batch has an explicit `<!-- checkpoint -->` → **STOP**, present summary, wait for "continue".
   - any task `failed` / `blocked` → **STOP** (severe), surface evidence + postmortem question; no blind retry.
6. **Test + review (the per-unit quality gate, runs in BOTH modes):** `dev-workflow:test-changes` (build/test/lint failure = severe → STOP); then the applicable review agents (`implementation-reviewer` always; apple-dev reviewers when UI + apple-dev installed, same conditions as run-phase Step 6). Triage: `must-fix` → severe → STOP; `nice-to-have` / device items → defer to run log.
7. **Phase boundary:**
   - **phase mode** → go to Step 4 (final review).
   - **guide mode** → if the unit is green with no open `must-fix`: check off the phase's acceptance criteria in the dev-guide, log "crossed phase {N} seam", and loop to the next phase (back to step 1). If no phases remain → Step 4.

### Step 4: Final consolidated review (the promised single review)

Present at the stop point (phase mode: the seam; guide mode: end of all phases, or wherever it halted):

- **Done:** phases / tasks completed, key files.
- **What I decided on my own:** every auto-resolved `recommended` DP — option taken + one-line reason (from run log).
- **Phases I auto-crossed (guide mode):** each seam crossed, with its test/review verdict.
- **What I deferred:** every `nice-to-have` finding + informational human/device-verification items.
- **Quality gates:** per-unit test-changes + review verdicts; any open `must-fix`.
- **Stops that happened:** blocking DPs / severe failures / explicit checkpoints that interrupted the run, and how they resolved.

Then ask how to proceed: fix open `must-fix` now, accept deferrals as known issues, or (if it halted mid-guide) resume.

## Hard Rules

- **Autonomous mode is opt-in, every time** (Step 2); guide mode's authorization names the phase count explicitly. Never enter by inference.
- **Severity gates are never suppressed** — only pacing pauses are. blocking DP, `must-revise`, failed verify, build break, regression, `must-fix`, and explicit `<!-- checkpoint -->` always stop, in both modes.
- **Per-unit test + review always runs**, even in guide mode. A clean phase boundary auto-advances; a dirty one (must-fix/severe) stops.
- **When in doubt, stop.** Ambiguous severity defaults to blocking.
- **No invisible auto-decisions.** Everything resolved, deferred, or auto-crossed appears in the final review.
- **No blind retry on failure.** A severe failure stops and surfaces; diagnosis/fix is the user's (or a follow-up `fix-bug`), not a silent re-run.
- **No other skill is modified.** Execution, testing, and review reuse existing assets as-is.

## State & Resume

- Task progress: `.claude/execute-plan-checkpoint.json` (shared with execute-plan; on-disk `completed` map authoritative across sessions).
- Phase progress (guide mode): the dev-guide's checked acceptance criteria + `.claude/dev-workflow-state.json` if present.
- Run log (auto-decisions + deferrals + seam crossings + stops): `.claude/self-pacing/<target-slug>.md`, written incrementally so the final review survives a context reset.
- On resume: read all of the above; only pending tasks / unfinished phases are driven; the run log already holds prior auto-decisions for the final review.

## Completion Criteria

- Autonomous mode was explicitly authorized for the chosen mode (Step 2).
- phase mode: the unit reached green (or halted at a severity gate); final review presented.
- guide mode: all phases' acceptance criteria checked (or halted at a severity gate); final review presented, including every auto-crossed seam.
- test-changes + applicable reviews ran per unit; results are in the final review.
- Every auto-decision and deferral appears in the final review.
