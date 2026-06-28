---
name: self-pacing
description: "Use when the user wants verified, already-planned work driven to green autonomously while they are away (AFK) — runs to green without a timer, suppressing routine pacing pauses, stopping ONLY for critical (blocking) decisions or severe failures; each stop writes a thin handoff card and ends the turn so the user is notified and can resume cheaply. TWO MODES: bare '/self-pacing' drives the WHOLE dev-guide across all phases to the end (phase seams do not pause it); '/self-pacing phase' (aliases: 'in-phase', 'single', 'one') drives ONE phase or one standalone plan, then stops at the seam for review. Triggers: '/self-pacing', 'self-pace', 'run it to green', 'autonomous run', \"don't stop at every checkpoint\", '自定速', '自己跑完', '少停几次', '一撸到底', '一口气跑到绿'. Not when: no verified plan / dev-guide exists (run write-plan → verify-plan, or write-dev-guide → run-phase first); the work is divergent design / exploration (use brainstorm); plan tasks lack executable `Automated verify` lines (no red/green signal to converge on)."
disable-model-invocation: true
---

<!-- cost-posture: inherit (judgment + orchestration — severity classification, decision auto-resolution, and loop control are judgment calls; do NOT downgrade to sonnet/haiku per dev-workflow Skill Cost Posture rule) -->

## What this is

`self-pacing` is an **AFK autonomous driver** for already-planned work. It runs to green without a timer, without scheduling, and without the user at the keyboard. The lifecycle is:

1. **Drive to green** — suppress pacing pauses; honor every severity gate. Auto-resolve low-severity decisions to their recommended option.
2. **Every stop drops a thin handoff card** — when the run hits a critical decision, a severe failure, or an explicit `<!-- checkpoint -->`, it writes a thin card (`Stopped at` / `Why` / `Next action` / `Pointers` / `Resume with`) at `.claude/self-pacing/<target-slug>-handoff.md`, then **ends the turn** so the user gets a CC idle notification.
3. **You come back (hot resume in the same session, or cold resume in a new one)** — read the handoff card to locate the stop, then follow the `Pointers` to the crystal / run-log / checkpoint / state / plan files to pick up.
4. **Closure** — when the run reaches green (or halts at a severity gate), emit a final HTML report via `shared-utils:html-report`, with the run log + crystal as source of truth.

User decisions (blocking DPs) lock into crystals via `crystallize`; automatic actions (auto-resolved decisions, deferrals, seam crossings, stops) accumulate in the run log. The handoff card is **thin by design** — it carries pointers + stop-delta, not full context. Source of truth stays on disk (code, state files, crystal, run log).

It invents nothing — the whole skill is this prompt plus a **stop-policy** layered over execution machinery that already exists.

**The one thing it changes vs. the normal flow:** the normal flow (run-phase / execute-plan) pauses at every batch hard-stop and (in run-phase) at every phase boundary, waiting for you to say "continue". Those are *pacing* pauses — they fire because of position, not because anything is wrong. `self-pacing` suppresses pacing pauses and gates only on *severity*.

## Artifacts & the resume model

`self-pacing` runs AFK, so every fact has to live on disk in a place a cold-start session can find it cheaply. The handoff card is the cheapest hand-off — it's a pointer card, not a context dump. The run log and the crystal are the durable record.

### Artifact layering

| Artifact | Owner | Path | What's in it | Written when |
|---|---|---|---|---|
| **Code** | repo | (the repo) | actual implementation; ultimate truth | normal edits |
| **Crystal** | `crystallize` (user-confirmed) | `docs/11-crystals/<date>-<topic>-crystal.md` (ONE file, all swept DPs bundled) | user decisions locked in (option + reason) | only when `≥1` blocking DP is resolved at authorization (Step 2); zero blocking DP → no crystal produced |
| **Run log** | `self-pacing` (auto) | `.claude/self-pacing/<target-slug>.md` | every auto-resolved decision, every deferral, every seam crossing, every stop, every auto-action | incrementally during the run |
| **Checkpoint** | `execute-plan` (shared writer — single-writer rule) | `.claude/execute-plan-checkpoint.json` | `completed: {task_id: status}` map for the current unit | per task |
| **Dev-workflow state** | `run-phase` (shared writer) | `.claude/dev-workflow-state.json` | current phase pointer in guide mode | per phase |
| **Handoff card** | `self-pacing` (auto) | `.claude/self-pacing/<target-slug>-handoff.md` | thin stop-delta + pointers — **not** a context dump | written / refreshed on every STOP, then the turn ends |

### Thin handoff doctrine

The card is **thin by design**. Its job is to let a cold-start session locate the stop in <30 seconds, not to re-explain the project. Thin ≠ lossy — the *full* context already lives in the artifacts above; the card just indexes them.

**`run-log ≠ crystal` (load-bearing).** They are not interchangeable:
- `crystal` = a user decision, locked, requires the user to be at the keyboard to authorize. Authoritative on *what to do*.
- `run-log` = an automatic action, driver-chosen, no user confirmation. Authoritative on *what happened*.

Mixing them is the most expensive failure mode: if the run log gets treated as a decision source, the driver starts re-justifying choices the user already made; if a crystal gets treated as an auto-log, the driver starts deferring user decisions. Both directions break the resume.

### Thin handoff card schema

Every STOP (blocking DP / severe failure / explicit `<!-- checkpoint -->` / phase seam in phase mode) writes or refreshes a card at `.claude/self-pacing/<target-slug>-handoff.md` before ending the turn. The schema:

```
# self-pacing handoff — <target-slug>

- **Stopped at:** {task_id or phase boundary or checkpoint marker}
- **Why:** {blocking DP question verbatim, OR failing command + relevant output excerpt, OR checkpoint marker context}
- **Next action:** {the one thing the next session must do to resume}
- **Pointers:**
  - crystal: docs/11-crystals/*-crystal.md (the file crystallize wrote, if any)
  - run-log: .claude/self-pacing/<target-slug>.md
  - checkpoint: .claude/execute-plan-checkpoint.json
  - dev-workflow-state: .claude/dev-workflow-state.json (if guide mode)
  - plan: docs/06-plans/<plan-file>.md
- **Resume with:** {literal command or short prose, e.g. "yes" / "/self-pacing" / "/self-pacing phase"}
```

### Why self-pacing writes its own thin card

`dev-workflow:handoff` is the human-to-human full-context handoff (it assumes the writer is summarizing the whole project for a person who has never seen it). `self-pacing`'s resume audience is itself — a cold-start session of the same skill, with the artifacts already on disk. Calling the heavy `handoff` skill would duplicate what's already in the run log + crystal + checkpoint, and would re-create context the next session doesn't need. **self-pacing writes its own thin card; it does not call `dev-workflow:handoff`.**

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
- **Plan tasks have no executable `Automated verify`** — split by task shape, not treated as one undifferentiated case:
  - **Logical task (code, algorithms, refactors, migrations, anything that changes behavior)** with no executable verify → there is no red/green signal to converge on. Back to `write-plan` so the plan gets real `Automated verify` lines.
  - **Presentational / UI task (layout, styling, visual components — only tsc / build passes, no behavioral test)** → the build IS the signal. Run it to build-clean, capture a screenshot of the rendered output, and stop for **visual sign-off** (the user confirms the screenshot matches intent). The screenshot path lands in the run log under "Presentational screenshots" and is fed into the final HTML report in Step 4. Do not bounce presentational work back to `write-plan` just because there is no executable verify line — that path is intentionally different.

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
| **Severe failure** | a task's `Automated verify` fails after its steps, `verify-plan` returns `must-revise`, build breaks, a prior-green check regresses, or a review `must-fix` | **STOP** — write/refresh handoff card with the failing command + relevant output excerpt; surface evidence; **do NOT invoke `fix-bug`, do NOT auto-fix** (out of scope; fix requires the user at the keyboard) |
| **Low-severity decision** | a `recommended` DP (carries its own `**Recommendation:**`) | **CONTINUE** — adopt the recommended option, record in the run log |
| **Low-severity finding** | a `nice-to-have` review item | **CONTINUE** — defer to the run log |
| **Routine pacing pause** | `compute_checkpoints.py` hard-stop from batch 0 or a green dependency-hub batch | **CONTINUE** — auto-advance to next segment |
| **Author-declared seam** | an explicit `<!-- checkpoint -->` marker in the plan body | **STOP** — author placed it deliberately; skipping it is a forbidden silent downgrade |

Phase boundary is the **only** mode-dependent row:

| Phase boundary (phase done, green, no must-fix) | phase mode | guide mode |
|---|---|---|
| | **STOP** → final review | **CONTINUE** → next phase (log the seam crossing) |

**Conservative default (load-bearing):** `self-pacing` leans entirely on upstream severity tags being correct. If a decision's severity is ambiguous, or a finding could plausibly be critical, **treat it as `blocking` and STOP.** Auto-resolving something that should have stopped is the expensive failure mode; an unnecessary stop is cheap. When in doubt, stop.

**Every STOP writes (or refreshes) the handoff card before the turn ends.** Any row above whose Action is STOP — blocking DP, severe failure, explicit `<!-- checkpoint -->`, phase seam in phase mode — must write or refresh `.claude/self-pacing/<target-slug>-handoff.md` first, *then* end the turn so CC idle notifies the user. The card carries the failing command + relevant output (for severe failures), the blocking DP question verbatim (for blocking decisions), or the checkpoint context (for author-declared seams), plus the schema fields described in `## Artifacts & the resume model`.

**Every auto-decision is visible.** A `recommended` DP adopted, a `nice-to-have` deferred, or a phase seam auto-crossed, without it appearing in the final review, is the "confident mess" failure mode. Every CONTINUE that resolved a decision, deferred a finding, or crossed a phase MUST land in the run log and appear in the final review.

## Process

### Step 1: Parse mode and resolve the target

1. **Parse mode** from the invocation argument:
   - no arg → **guide mode**
   - `phase` / `in-phase` / `single` / `one` → **phase mode**
2. **Resolve the target:**
   - **guide mode:** find the current dev-guide (`docs/06-plans/*-dev-guide.md`, prefer `current: true`). The unit list = all phases whose acceptance criteria are not yet all checked, in order.
     - **If no dev-guide exists, do NOT silently downgrade.** Present an AskUserQuestion gate with the two real options:
       - **A. write-dev-guide first** — invoke `dev-workflow:write-dev-guide`, then resume guide mode after the guide is approved.
       - **B. phase mode on a single plan** — if a verified standalone plan exists (or can be quickly written + verified), switch to `/self-pacing phase <plan-file>` for just that unit.
     - If the user picks neither (declines both), end the turn (write a thin handoff card recording "no target resolved — user declined both options", per `## Artifacts & the resume model`).
   - **phase mode:** resolve, in order — an explicit plan file the user named; the in-progress phase from `.claude/dev-workflow-state.json`; otherwise ask which phase / plan. If nothing resolves, send to `write-plan` / `run-phase`.
3. **Verification is mandatory** (the run will not pause per-segment for human review, so plan quality matters more, not less): for any plan about to run, require `## Verification` `Verdict: Approved` (or a verify report). If absent, invoke `dev-workflow:verify-plan`; `must-revise` is a severe gate → STOP. For phases without a plan yet (guide mode), the plan is written + verified inside the per-phase loop (Step 3) before execution.
4. Confirm tasks have executable `Automated verify` (or annotated `N/A — trivial`). A non-trivial task with no verify line → STOP, send to `write-plan`. For presentational / UI tasks (build + visual sign-off only), the presentational branch in `## When NOT to use` applies instead — see that section's acceptance path.

### Step 2: Authorize autonomous mode (the one upfront gate)

Autonomous, gate-suppressing execution must be a deliberate, explicit choice — never auto-entered. Present the policy, mode-aware, and get a single go-ahead.

**phase mode:**
```
self-pacing (phase) will run {target} to green on its own, then stop at the seam
for one review. It stops early only for: blocking decisions, severe failures, and
any explicit <!-- checkpoint --> you placed. It will take the recommended option on
low-severity decisions and defer nice-to-haves. Every stop drops a thin handoff
card (Stopped at / Why / Next action / Pointers / Resume with) and ends the turn;
the final review arrives as an HTML report over the run log + crystal as source
of truth. Proceed? (yes / no)
```

**guide mode (extra loud — this crosses phase boundaries):**
```
⚠️ self-pacing (guide) will run ALL {N} remaining phases of {dev-guide} straight to
the end. It will NOT pause between phases. Each phase is still tested + reviewed, and
it WILL stop if it hits: a blocking decision, a severe/must-fix failure, or an explicit
<!-- checkpoint -->. Low-severity decisions take their recommended option; nice-to-haves
are deferred. You get ONE consolidated review at the very end (or wherever it stops).
Every stop drops a thin handoff card (Stopped at / Why / Next action / Pointers /
Resume with) and ends the turn; the final review arrives as an HTML report over
the run log + crystal as source of truth.

Run all {N} phases to the end? (yes / no, I'll do them one at a time with /self-pacing phase)
```

Only an explicit yes proceeds.

**Sweep blocking DPs across the entire target, then resolve them up front.** Scan **every** plan in the resolved target (all phase plans in guide mode; the single plan in phase mode) for `blocking` DPs in their `## Decisions` sections (entries with no `**Chosen:**`). Collect every blocking DP into one batch. This is the **one** opportunity to ask the user up front — once the run starts, only per-plan decisions can be re-prompted, and only if the plan reaches them.

- **If ≥1 blocking DP is collected:**
  1. **Resolve each via AskUserQuestion** (per `${CLAUDE_PLUGIN_ROOT}/references/decision-points.md`) — present the DP, capture the user's chosen option + one-line reason. `crystallize` does **not** resolve open DPs; it only extracts decisions the user has *already* made, so the answering must happen here first.
  2. **Write `**Chosen:**` into each plan file** (replacing that DP's `**Recommendation:**`), so `execute-plan` and the crystal both have the decision.
  3. **Then invoke `dev-workflow:crystallize`** while the user is still at the keyboard. It extracts the just-made decisions into ONE crystal file, `docs/11-crystals/<date>-<topic>-crystal.md` (all swept DPs bundled in that single file, per crystallize Step 4). This is a *separate* turn from the AskUserQuestion batch — do not promise it as one turn.
- **If zero blocking DP is collected, skip both the resolution batch and `crystallize`.** Crystallize's contract is Exit-without-file when it has no signal; calling it with nothing produces no file and wastes a turn.

Start the run log at `.claude/self-pacing/<target-slug>.md` once authorization + the up-front decisions are recorded.

### Step 3: The run loop

**phase mode** runs the per-unit loop once. **guide mode** runs it per phase, in order, auto-advancing while green.

**STOP discipline (load-bearing — applies to every STOP below):** Any time a STOP fires — blocking DP, severe failure, explicit `<!-- checkpoint -->`, phase seam in phase mode, must-fix finding — `self-pacing` MUST write or refresh `.claude/self-pacing/<target-slug>-handoff.md` per the schema in `## Artifacts & the resume model` **before** ending the turn. The card carries the failing command + relevant output excerpt (severe), the blocking DP verbatim (blocking decision), or the checkpoint context (author-declared seam). Then the turn ends so CC idle notifies the user. Do NOT skip the card. Do NOT batch multiple stops into one card at session end — each stop gets its own fresh card so a cold-start reader sees the most recent state.

**Run-log discipline:** Every auto-action lands in `.claude/self-pacing/<target-slug>.md` **incrementally**, in the same turn it happens. A final-batch write at session end risks losing the log to a context reset mid-run. The log entries — auto-resolved decisions, deferrals, seam crossings, screenshot paths, stops — are also the source of truth for the final HTML report (Step 4).

Per unit (one plan / one phase):

1. **Plan (guide mode, phase without a plan only):** write the phase's plan via the Plan Writing Reference, then `verify-plan`. Skip run-phase's scope-confirmation pause. A `must-revise` is severe → STOP (writes handoff card, ends turn).
2. **Resolve decisions up front — but skip any already resolved.** Read `## Decisions`. **A DP that already carries `**Chosen:**` is resolved; do NOT re-ask it** — it was answered at the Step 2 sweep or auto-adopted earlier. Re-prompting it would double-ask an AFK user the exact decision just made, defeating the sweep. Only *genuinely unresolved* DPs reach the policy below — in practice those in a phase plan written fresh at Step 3.1 (guide mode), since Step 2 already swept every pre-existing plan. For an unresolved `blocking` → STOP + write/refresh handoff card (blocking DP card variant) + AskUserQuestion (per `${CLAUDE_PLUGIN_ROOT}/references/decision-points.md`), record `**Chosen:**`. Unresolved `recommended` → adopt its `**Recommendation:**`, write `**Chosen:**`, append to run log under "Auto-resolved decisions" (same turn). (Conservative default applies.)
3. **Compute segments:** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/execute-plan/scripts/compute_checkpoints.py <plan_file> --k 3 --batch-size 5`; parse `{batches, hard_stops, tasks, ...}`.
4. **Init / resume** `.claude/execute-plan-checkpoint.json` exactly as `execute-plan` defines it (single-writer; `self-pacing` is the sole writer of the checkpoint and `execution-report.md` during its run).
5. **Segment loop:** for each segment, `Workflow({scriptPath: "${CLAUDE_PLUGIN_ROOT}/skills/execute-plan/execute-plan.workflow.js", args: {...}})` (this skill is a sanctioned Workflow trigger). Spot-check `files_written`, record `completed` + report from the returned array. Then apply the stop-policy at the boundary:
   - all `done` AND pacing boundary (batch 0 / green hub) → **auto-continue**, log "auto-continued past pacing checkpoint" (incremental).
   - boundary batch has an explicit `<!-- checkpoint -->` → **STOP**, write/refresh handoff card (checkpoint context variant), present summary, wait for "continue".
   - any task `failed` / `blocked` → **STOP** (severe), write/refresh handoff card (failing command + relevant output excerpt), surface evidence + postmortem question; no blind retry; **do NOT invoke `fix-bug` and do NOT auto-fix** — diagnosis/fix is out of scope and requires the user at the keyboard.
6. **Test + review (the per-unit quality gate, runs in BOTH modes):** `dev-workflow:test-changes` (build/test/lint failure = severe → STOP, write/refresh handoff card); then the applicable review agents (`implementation-reviewer` always; apple-dev reviewers when UI + apple-dev installed, same conditions as run-phase Step 6). Triage: `must-fix` → severe → STOP (write/refresh handoff card); `nice-to-have` / device items → defer to run log (incremental).
   - **Presentational / UI tasks** (the `When NOT to use` presentational branch — only build + visual sign-off, no executable `Automated verify`): the build pass replaces the test signal; record the screenshot path under "Presentational screenshots" in the run log and include it in the final HTML. Visual sign-off is the user-side gate; do not invent it.
7. **Phase boundary:**
   - **phase mode** → write/refresh handoff card (seam variant) + go to Step 4 (final review).
   - **guide mode** → if the unit is green with no open `must-fix`: check off the phase's acceptance criteria in the dev-guide, log "crossed phase {N} seam" (incremental), and loop to the next phase (back to step 1). If no phases remain → Step 4.

### Step 4: Final consolidated review (the promised single review)

**Invoke `shared-utils:html-report`** to render the consolidated review. Constraints (these are non-negotiable — violating them breaks resume + source-of-truth):

- **Source of truth: run log + crystal.** The HTML report reads from `.claude/self-pacing/<target-slug>.md` (every auto-decision, deferral, seam crossing, screenshot path, stop) and `docs/11-crystals/*-crystal.md` (user-locked decisions). No narrative reconstruction from chat history — chat is not authoritative; the run log + crystal are.
- **Main session, not forked.** Invoke `shared-utils:html-report` in this session. Do NOT use `context: fork` for it — a forked agent cannot see this session's chat context (and on cold-start resume, the session context is empty anyway). The report must be produced by a renderer that reads disk artifacts, not by an agent that reconstructs them from memory.

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
- **No blind retry on failure.** A severe failure stops and surfaces; diagnosis/fix is the user's, not a silent re-run. Fix is out of scope — `self-pacing` does not invoke `fix-bug` and does not auto-fix (a silent auto-fix while the user is AFK would mutate the repo without authorization; the Stop Policy table, Step 3, and this rule all agree on this).
- **Every STOP writes the thin handoff card first.** Pointers + stop-delta only — never re-copy crystal / run-log / plan contents into the card. The card is an index, not a context dump (see `## Artifacts & the resume model`).
- **`run-log ≠ crystal`, never mix.** User decisions resolved at the Step 2 up-front sweep → `docs/11-crystals/*-crystal.md` via `crystallize`. Blocking decisions hit *in-loop* (Step 3.2, after the run started) are recorded as `**Chosen:**` in the plan file only — recoverable via the plan Pointer on the handoff card, not re-crystallized. Auto-actions → `.claude/self-pacing/<target-slug>.md` incrementally. Treating a crystal/Chosen decision as an auto-log, or vice versa, breaks resume.
- **No timer, no background scheduling.** `self-pacing` ends the turn after every STOP (CC idle notifies the user); it does not use ScheduleWakeup, cron, or any auto-resume mechanism. The user comes back hot (same session) or cold (new session reading the handoff card) — that's the entire resume surface. (Maintainers: rationale for why this is architectural, not a tunable, is in `DESIGN.md` — read it before adding any timer/wait/budget.)
- **No other skill is modified.** Execution, testing, and review reuse existing assets as-is.

## State & Resume

- Task progress: `.claude/execute-plan-checkpoint.json` (shared with execute-plan; on-disk `completed` map authoritative across sessions).
- Phase progress (guide mode): the dev-guide's checked acceptance criteria + `.claude/dev-workflow-state.json` if present.
- Run log (auto-decisions + deferrals + seam crossings + stops): `.claude/self-pacing/<target-slug>.md`, written incrementally so the final review survives a context reset.
- Crystal (user-locked decisions, only when ≥1 blocking DP was resolved at authorization): `docs/11-crystals/<date>-<topic>-crystal.md` (one file; glob `docs/11-crystals/*-crystal.md` to find it). Zero blocking DPs at sweep → no crystal produced; this is by design, not a missing artifact.
- Handoff card (thin index written on every STOP): `.claude/self-pacing/<target-slug>-handoff.md`. The card carries `Stopped at` / `Why` / `Next action` / `Pointers` / `Resume with` only.

**Cold-start resume procedure** (this is the read side of the thin card doctrine — without it, the card has no consumer):

1. **Read the handoff card first.** `.claude/self-pacing/<target-slug>-handoff.md` gives `Stopped at` + `Next action` + `Resume with` in one read. The card tells you where you are.
2. **Follow the card's `Pointers`** to load the full context, in this order:
   - `docs/11-crystals/*-crystal.md` — locked user decisions (what to do).
   - `.claude/self-pacing/<target-slug>.md` — auto-actions, deferrals, seam crossings, screenshot paths (what happened).
   - `.claude/execute-plan-checkpoint.json` — task-level completion map.
   - `.claude/dev-workflow-state.json` (guide mode) — phase pointer.
   - `docs/06-plans/<plan-file>.md` — the plan being executed.
3. **Resume with the literal command** from `Resume with` (e.g. `/self-pacing`, `/self-pacing phase`, or `yes` for an in-progress STOP).

Do not skip the card and read the artifacts directly — they answer "what" without telling you "where the run stopped" or "what the next action is". The card is the locator; the artifacts are the context.

## Completion Criteria

- Autonomous mode was explicitly authorized for the chosen mode (Step 2).
- phase mode: the unit reached green (or halted at a severity gate); final review presented.
- guide mode: all phases' acceptance criteria checked (or halted at a severity gate); final review presented, including every auto-crossed seam.
- test-changes + applicable reviews ran per unit; results are in the final review.
- Every auto-decision and deferral appears in the final review.
- **If ≥1 blocking DP was resolved at the Step 2 sweep**, the corresponding crystal exists at `docs/11-crystals/<date>-<topic>-crystal.md` (one file, written by Step 2's `crystallize` invocation after the user answered the DPs). If zero blocking DPs were collected, this criterion does not apply — the run is complete without a crystal by design.
- Every STOP that fired during the run has a handoff card on disk (`.claude/self-pacing/<target-slug>-handoff.md`); the final card reflects the most recent stop, not a stale one.
- The final consolidated review was emitted as HTML via `shared-utils:html-report` (Step 4), with run-log + crystal as source of truth.
