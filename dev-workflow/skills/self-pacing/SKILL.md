---
name: self-pacing
description: "Use when the user wants verified, already-planned work driven to green autonomously while they are away (AFK) — runs to green without a timer, suppressing routine pacing pauses, stopping ONLY for critical (blocking) decisions or severe failures; each stop writes a thin handoff card and ends the turn so the user is notified and can resume cheaply. TWO MODES: bare '/self-pacing' drives the WHOLE dev-guide across all phases to the end (phase seams do not pause it); '/self-pacing phase' (aliases: 'in-phase', 'single', 'one') drives ONE phase or one standalone plan, then stops at the seam for review. Triggers: '/self-pacing', 'self-pace', 'run it to green', 'autonomous run', \"don't stop at every checkpoint\", '自定速', '自己跑完', '少停几次', '一撸到底', '一口气跑到绿'. Not when: no verified plan / dev-guide exists (run write-plan → verify-plan, or write-dev-guide → run-phase first); the work is divergent design / exploration (use brainstorm); plan tasks lack executable `Automated verify` lines (no red/green signal to converge on)."
disable-model-invocation: true
---

<!-- cost-posture: inherit (judgment + orchestration — severity classification, decision auto-resolution, and loop control are judgment calls; do NOT downgrade to sonnet/haiku per dev-workflow Skill Cost Posture rule) -->

> ## ⚠️ Superseded by `dev-workflow:afk`
>
> **Use `/afk` for unattended runs.** This skill requires a verified plan or dev-guide before it will start — that requirement is exactly what `/afk` drops, and it is why this skill went unused.
>
> Measured over the 30 days to 2026-09-04, across this account's whole transcript corpus: the user typed `/self-pacing` **0 times**; the model attempted to invoke it twice and was blocked by `disable-model-invocation`; meanwhile the raw pacing paragraph this skill was built from was pasted by hand **63 times across 41 sessions in 9 projects**. Separately, 271 of 283 sessions (96%) shipped real work without invoking `write-plan` / `verify-plan` / `execute-plan` at all. The demand is real; the plan precondition is what nobody wanted.
>
> Kept, not deleted, because its `DESIGN.md` invariants 1 / 2 / 6 (a stop is a complete handoff; run log ≠ handoff card; the card locates, the doc transfers) were paid for in real failures and are inherited by `/afk`. Read them before changing stop or handoff behavior anywhere.
>
> Still valid for one case: driving an **already-verified** multi-phase dev-guide across phase seams, which `/afk` deliberately does not do.

## What this is

`self-pacing` is an **AFK autonomous driver** for already-planned work. It runs to green without a timer, without scheduling, and without the user at the keyboard. The lifecycle is:

1. **Drive to green** — suppress pacing pauses; honor every severity gate. Auto-resolve low-severity decisions to their recommended option.
2. **Every stop drops a thin handoff card** — at any terminal enumerated in `## The Stop Policy` (severity gates *and* cannot-proceed terminals; that table is the single list, never restated elsewhere), it writes a thin card (`Stopped at` / `Why` / `Next action` / `Pointers` / `Resume with`) at `.claude/self-pacing/<target-slug>-handoff.md`, then **ends the turn** so the user gets a CC idle notification.
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
| **Stop card** | `self-pacing` (auto) | `.claude/self-pacing/<target-slug>-handoff.md` | thin stop-delta + pointers — **not** a context dump | written / refreshed on every STOP, then the turn ends |
| **Handoff doc** | `dev-workflow:handoff` (invoked by `self-pacing`) | `docs/06-plans/HANDOFF-YYYY-MM-DD-HHMM.md` | full context transfer: decisions, reversals, traps, what only the user can verify | at terminal STOPs only — see the mode table below |

### Thin handoff doctrine

The card is **thin by design**. Its job is to let a cold-start session locate the stop in <30 seconds, not to re-explain the project. Thin ≠ lossy — the *full* context already lives in the artifacts above; the card just indexes them.

⚠️ "Thin card" is a rule about the **card**, not about the **stop**. A terminal stop produces a card *and* a handoff doc — see `Two-tier handoff` below. Reading this section alone is how 13 of 43 real cards ended up carrying a full handoff inside them (`DESIGN.md` invariant 6).

**`run-log ≠ crystal` (load-bearing).** They are not interchangeable:
- `crystal` = a user decision, locked, requires the user to be at the keyboard to authorize. Authoritative on *what to do*.
- `run-log` = an automatic action, driver-chosen, no user confirmation. Authoritative on *what happened*.

Mixing them is the most expensive failure mode: if the run log gets treated as a decision source, the driver starts re-justifying choices the user already made; if a crystal gets treated as an auto-log, the driver starts deferring user decisions. Both directions break the resume.

### Thin handoff card schema

Every terminal in `## The Stop Policy` — every severity-gate STOP **and** every cannot-proceed terminal — writes or refreshes a card at `.claude/self-pacing/<target-slug>-handoff.md` before ending the turn. That table is the only enumeration; this section does not restate it (three drifting copies of the stop list is how terminals went undocumented in the first place). The schema:

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

### Two-tier handoff: the card locates, the doc transfers

A STOP needs two different things at once, and one artifact cannot be both. The card is a **locator** — cheap, written at every stop, read in <30 seconds. `dev-workflow:handoff` produces a **context transfer** — the 8-section doc that teaches a cold session the decisions, the reversals, the traps. Giving the run only the card is what made 13 of 43 real cards grow into full handoffs in the card's own file (see `DESIGN.md` invariant 6).

**Which stops get the doc — enumerated by mode, never judged:**

| Stop | guide mode | phase mode |
|---|---|---|
| any STOP | card **+ doc** | card |
| severe failure / exhausted revision loop / cannot-proceed terminal / seam-done | card **+ doc** | card **+ doc** |
| blocking DP / author-declared `<!-- checkpoint -->` | card **+ doc** | card only |

`guide` mode is session-terminal **by construction** — the user authorized an unattended run across all phases, so they are not at the keyboard when it stops. `phase` mode's blocking-DP and checkpoint stops expect a hot resume (invariant 1) and the card alone is enough.

⛔ Do **not** replace this table with a judged criterion like "does resuming need context re-established" — that is the unfalsifiable shape invariant 4(b) bans; every stop can be narrated as needing context, and the rule drifts to "always write the doc".

**When the doc is written:** invoke `dev-workflow:handoff` (it reads this run's disk artifacts, not chat — see that skill's `## self-pacing 模式`), then put the doc's absolute path in the card's `Next action`. The doc's §6 carries the back-pointers to run-log / checkpoint / crystal, so either artifact reaches the other.

**Card cap — a field list, not an adjective.** The card is exactly the five schema fields, plus at most one `## ⛔ 别再跑一遍的` block. Anything else — what was delivered, what got reversed, what only the user can verify, what the next session will trip on — belongs in the doc. "Keep it thin" does not catch a card that dropped the schema entirely; a field list does.

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
| **First red on a check** | a task's `Automated verify` fails after its steps, build / test / lint goes red, or a prior-green check regresses | **RE-RUN ONCE** — the byte-identical command, changing no files. Green on the second run → append `flake: <command>` to the run log (it surfaces in the final review; a flake recorded is not a flake masked) and **CONTINUE**. Red again → the row below. Exactly one re-run; never a third. |
| **Severe failure** | the same check red **twice**, or a review `must-fix` whose fix would touch a file outside the plan's declared `**Files:**` | **STOP** — write/refresh handoff card with the failing command + relevant output excerpt; surface evidence; **do NOT invoke `fix-bug`, do NOT auto-fix** (out of scope; fix requires the user at the keyboard) |
| **In-scope `must-fix`** | a review `must-fix` repairable entirely within the plan's declared `**Files:**` — the blast radius the user authorized at Step 2 | **REPAIR ONCE** — apply the fix, re-run `test-changes`, re-dispatch the review. Clean → CONTINUE. Still `must-fix`, or the repair would need a file outside the declared set → **STOP** (severe row). One cycle, never two. Log the finding, the fix, and the re-review verdict — all three appear in the final review. |
| **Plan fails verification** | `verify-plan` returns `must-revise` | **CONTINUE into verify-plan's own revision loop** — apply the revision items to the **plan text only** (never source files), re-dispatch the verifier, max 2 cycles (verify-plan Step 3's contract). Log each cycle to the run log. **STOP** only when: still `must-revise` after cycle 2, **or** any revision item requires a `blocking` decision (that DP takes the blocking row above). |
| **Low-severity decision** | a `recommended` DP (carries its own `**Recommendation:**`) | **CONTINUE** — adopt the recommended option, record in the run log |
| **Low-severity finding** | a `nice-to-have` review item | **CONTINUE** — defer to the run log |
| **Routine pacing pause** | `compute_checkpoints.py` hard-stop from batch 0 or a green dependency-hub batch | **CONTINUE** — auto-advance to next segment |
| **Author-declared seam** | an explicit `<!-- checkpoint -->` marker in the plan body | **STOP** — author placed it deliberately; skipping it is a forbidden silent downgrade |

Phase boundary is the **only** mode-dependent row:

| Phase boundary (phase done, green, no must-fix) | phase mode | guide mode |
|---|---|---|
| | **STOP** → final review | **CONTINUE** → next phase (log the seam crossing) |

### Cannot-proceed terminals

These end the run too, and they belong in the enumeration — a terminal that lives only in prose is a terminal the run cannot check itself against. They are **not** severity gates and carry no judgment: the run physically cannot continue without a human, so there is nothing to weigh.

| Terminal | Fires when | Card variant |
|---|---|---|
| **No target resolved** | guide mode has no dev-guide and the user declined both offered options (Step 1.2), or phase mode resolves no plan/phase (Step 1.3) | "no target resolved — {which branch}"; `Next action` = the resolution the user must pick |
| **No derivable verify signal** | a non-trivial task has no `Automated verify` **and** one cannot be derived from the task's own steps (Step 1.4) | the task id + why no signal is derivable; `Next action` = `write-plan` for that task |
| **Awaiting visual sign-off** | a presentational / UI unit reached build-clean and its screenshot needs human eyes (`## When NOT to use` presentational branch) | screenshot path + what to confirm; `Resume with` = "looks right" / the correction |

**The distinguishing test is reversibility, not confidence.** A cannot-proceed terminal is one where no amount of additional model effort produces the missing input — a human preference, a human eye, an authorization. "A process document told me to stop" is **not** one of these; that is a rule conflict, resolved by precedence, not a block. Do not add rows here for anything the run could have worked out itself.

**Why `must-revise` is not a severe failure.** The no-auto-fix rule exists because silently mutating the repo while the user is AFK is an unauthorized change, and AFK auto-diagnosis is confidently wrong. Neither applies to revising a plan: the plan file is text under `docs/06-plans/`, changing it alters no product behavior; the loop is bounded at 2 cycles with a defined exit; and any revision item that genuinely needs the user shows up as a `blocking` DP, which its own row already stops on. Treating `must-revise` as severe means a run that writes its own phase plan (Step 3.1) halts before a single line of code is written — the plan-authoring inner loop mistaken for a run failure.

**Conservative default (load-bearing), and what it does NOT cover.** `self-pacing` leans entirely on upstream severity tags being correct. If a decision's severity is ambiguous, or a finding could plausibly be critical, **treat it as `blocking` and STOP.** Auto-resolving something that should have stopped is the expensive failure mode; an unnecessary stop is cheap.

This default is scoped to **severity classification of something that already happened** — a failure that fired, a decision that surfaced. It is **not** a general bias toward stopping, and it never answers "should I keep working". There is no doubt-default for continuing: if no row of this table fires, the run continues. Read together with the four-gate check in `## Hard Rules`, which is the counterweight — a STOP still has to pass it.

**Every terminal writes (or refreshes) the handoff card before the turn ends.** Every row above whose Action is STOP, plus every cannot-proceed terminal, must write or refresh `.claude/self-pacing/<target-slug>-handoff.md` first, *then* end the turn so CC idle notifies the user. What the card carries is the `Card variant` of the row that fired — the failing command + relevant output for a severe failure, the blocking DP question verbatim for a blocking decision, the still-open revision items after cycle 2 for an exhausted revision loop, the checkpoint context for an author-declared seam — plus the schema fields described in `## Artifacts & the resume model`.

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
3. **Verification is mandatory** (the run will not pause per-segment for human review, so plan quality matters more, not less): for any plan about to run, require `## Verification` `Verdict: Approved` (or a verify report). If absent, invoke `dev-workflow:verify-plan`; a `must-revise` verdict takes the **Plan fails verification** row of the Stop Policy — revise the plan text and re-verify (≤2 cycles), and STOP only when that loop is exhausted or a revision item needs a blocking decision. For phases without a plan yet (guide mode), the plan is written + verified inside the per-phase loop (Step 3) before execution.
4. Confirm tasks have executable `Automated verify` (or annotated `N/A — trivial`). A non-trivial task with no verify line is a **plan-text defect, not a run failure** — same class as `must-revise`: first try to derive the verify line from the task's own `**Steps:**` and `**Files:**` (the command that would show the task worked), write it into the plan, and log the derivation. Only when no signal is derivable from the task as written does this become the **No derivable verify signal** cannot-proceed terminal. For presentational / UI tasks (build + visual sign-off only), the presentational branch in `## When NOT to use` applies instead — see that section's acceptance path.

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

**STOP discipline (load-bearing — applies to every STOP below):** Any time any terminal in `## The Stop Policy` fires — severity gate or cannot-proceed terminal, per that table's `Card variant` column — `self-pacing` MUST write or refresh `.claude/self-pacing/<target-slug>-handoff.md` per the schema in `## Artifacts & the resume model` **before** ending the turn. The card carries the failing command + relevant output excerpt (severe), the blocking DP verbatim (blocking decision), the still-open revision items after cycle 2 (exhausted revision loop), or the checkpoint context (author-declared seam). Then the turn ends so CC idle notifies the user. Do NOT skip the card. Do NOT batch multiple stops into one card at session end — each stop gets its own fresh card so a cold-start reader sees the most recent state.

**Terminal STOPs also write the handoff doc**, per the mode table in `Two-tier handoff` (under `## Artifacts & the resume model`): invoke `dev-workflow:handoff` (main session, not forked — the doc must exist on disk before this turn ends), then write the doc's absolute path into the card's `Next action`. Order matters: doc first, then the card, so the card can name it. Everything that does not fit the card's five fields goes in the doc — that is what the doc is for, and stuffing it into the card instead is the failure this rule exists to stop.

**Run-log discipline:** Every auto-action lands in `.claude/self-pacing/<target-slug>.md` **incrementally**, in the same turn it happens. A final-batch write at session end risks losing the log to a context reset mid-run. The log entries — auto-resolved decisions, deferrals, seam crossings, screenshot paths, stops — are also the source of truth for the final HTML report (Step 4).

Per unit (one plan / one phase):

1. **Plan (guide mode, phase without a plan only):** write the phase's plan via the Plan Writing Reference, then `verify-plan`. Skip run-phase's scope-confirmation pause. A `must-revise` takes the **Plan fails verification** row: apply the revision items to the plan text, re-dispatch the verifier, ≤2 cycles, logging each cycle. Only an exhausted loop (still `must-revise` after cycle 2) or a revision item that needs a `blocking` decision escalates to STOP (writes handoff card, ends turn).
2. **Resolve decisions up front — but skip any already resolved.** Read `## Decisions`. **A DP that already carries `**Chosen:**` is resolved; do NOT re-ask it** — it was answered at the Step 2 sweep or auto-adopted earlier. Re-prompting it would double-ask an AFK user the exact decision just made, defeating the sweep. Only *genuinely unresolved* DPs reach the policy below — in practice those in a phase plan written fresh at Step 3.1 (guide mode), since Step 2 already swept every pre-existing plan. For an unresolved `blocking` → STOP + write/refresh handoff card (blocking DP card variant) + AskUserQuestion (per `${CLAUDE_PLUGIN_ROOT}/references/decision-points.md`), record `**Chosen:**`. Unresolved `recommended` → adopt its `**Recommendation:**`, write `**Chosen:**`, append to run log under "Auto-resolved decisions" (same turn). (Conservative default applies.)
3. **Compute segments:** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/execute-plan/scripts/compute_checkpoints.py <plan_file> --k 3 --batch-size 5`; parse `{batches, hard_stops, tasks, ...}`.
4. **Init / resume** `.claude/execute-plan-checkpoint.json` exactly as `execute-plan` defines it (single-writer; `self-pacing` is the sole writer of the checkpoint and `execution-report.md` during its run).
5. **Segment loop:** for each segment, `Workflow({scriptPath: "${CLAUDE_PLUGIN_ROOT}/skills/execute-plan/execute-plan.workflow.js", args: {...}})` (this skill is a sanctioned Workflow trigger). Spot-check `files_written`, record `completed` + report from the returned array. Then apply the stop-policy at the boundary:
   - all `done` AND pacing boundary (batch 0 / green hub) → **auto-continue**, log "auto-continued past pacing checkpoint" (incremental).
   - boundary batch has an explicit `<!-- checkpoint -->` → **STOP**, write/refresh handoff card (checkpoint context variant), present summary, wait for "continue".
   - any task `failed` / `blocked` → **First red on a check** row: re-run that task's `Automated verify` byte-identically, once, changing no files. Green → log `flake: <command>` and continue. Red again → **STOP** (severe), write/refresh handoff card (failing command + both runs' relevant output), surface evidence + postmortem question; **do NOT invoke `fix-bug` and do NOT auto-fix** — diagnosis is out of scope and requires the user at the keyboard.
6. **Test + review (the per-unit quality gate, runs in BOTH modes):** `dev-workflow:test-changes` — a build/test/lint failure takes the **First red on a check** row (one byte-identical re-run; still red → severe → STOP with card). Then the applicable review agents (`implementation-reviewer` always; apple-dev reviewers when UI + apple-dev installed, same conditions as run-phase Step 6). Triage each finding:
   - `must-fix` **repairable inside the plan's declared `**Files:**`** → **In-scope `must-fix`** row: fix it, re-run `test-changes`, re-dispatch the review. Clean → continue. Still `must-fix` after that one cycle → severe → STOP. Before applying, confirm every file the repair touches is in the declared set; if not, do not start — STOP instead.
   - `must-fix` needing a file outside the declared set → severe → STOP (write/refresh handoff card). The plan's `**Files:**` is the blast radius the user authorized at Step 2; outside it there is no authorization to repair.
   - `nice-to-have` / device items → defer to run log (incremental).
   - Log every repair attempt (finding, files touched, re-review verdict) to the run log in the same turn — a silent self-repair is the "confident mess" failure mode.
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
- **Severity gates are never suppressed** — only pacing pauses are. A blocking DP and an explicit `<!-- checkpoint -->` stop immediately, in both modes. Three gates stop only *after* their bounded loop is exhausted, and the exhausted loop is itself the gate — suppressing the gate is still forbidden, shortening the loop is not the same thing:

  | Gate | Bounded loop first | Stops when |
  |---|---|---|
  | `must-revise` from verify-plan | revise plan text + re-verify, ≤2 cycles | still `must-revise` after cycle 2, or an item needs a blocking decision |
  | failed verify / build break / regression | one byte-identical re-run, no file changes | red the second time |
  | review `must-fix` | one repair confined to the plan's declared `**Files:**` | still `must-fix`, or the repair needs a file outside that set |
- **Per-unit test + review always runs**, even in guide mode. A clean phase boundary auto-advances; a dirty one (must-fix/severe) stops.
- **Stopping is enumerated, not judged** (inherited from the user-wide CLAUDE.md 禁止行为 →「把还在跑的验证写成「未完成 / 待办 / 下轮再看」交回用户」: run it 「**跑到出结论（通过 / 失败 / 一个具体的阻塞点）**」, and a real block must state 「阻塞在哪一步、解除条件是什么」). Here that means: the run ends at green, or at a row of the Stop Policy table — which *is* the concrete blocking point, and the handoff card's `Why` + `Next action` *is* the where-it-blocked + what-unblocks-it. If no row fires, **continue** — there is no default stop. "This is the best state reachable in this session" / "good enough for a handoff" is **not** a terminal condition and must never be written as one; it is model self-assessment, unfalsifiable and always available as an excuse. That CLAUDE.md rule already outranks this skill (禁止行为 > … > 计划细节), so this line is inheritance, not a local invention — do not reword it away from the upstream phrasing.
- **Context occupancy is not a terminal, and not a reason to move to a new session.** The run never stops, and a fresh session is never proposed, on context-remaining grounds — not mid-run, and not at the Step 2 authorization gate. 「这轮上下文已经很满，6 个 phase 的自主跑放在新会话里更稳」 is the same error one step earlier, before the Stop Policy would even apply, which is why this rule is stated here rather than as a table row. Three reasons, in the order that makes it a rule and not a preference:
  1. **The model has no token counter.** "This session feels long" is not a measurement. Measured instances sat at 28% / 57% / 73% occupancy while being described as full or nearly exhausted.
  2. **Only a measured figure counts, and its absence is not a licence.** Where the environment surfaces a measured occupancy number to the run, that number is the only admissible evidence for any claim about remaining context — and CLAUDE.md 行为约束 →「资源不授权跳步」 already forbids pausing or splitting live work on context-consumption grounds, whatever the stated motive ("更稳" / "怕撞墙" / "放新会话里更干净" are not exits). Where no measured figure reaches the run, the claim is simply unavailable: no number, no assertion, and the run continues. (Owners who want this enforced mechanically: DESIGN.md invariant 4(b) describes one way to close it.)
  3. **Hitting the wall does not lose work.** The harness takes over near the limit — it clears old tool outputs first, then summarizes (official `how-claude-code-works`). Switching sessions ahead of it buys nothing the architecture does not already provide.

  This is invariant 4(b) with a specific face: 「上下文快满了」 is exactly the unfalsifiable, always-available self-assessment that section bans, and it is inherited from CLAUDE.md, not invented here (same status as the 4(c) inheritance note).
- **Pass the four-gate check before every STOP.** Before ending a turn at a `blocking` DP or an ambiguous-severity call, answer: (1) what problem is actually being solved, (2) **is stopping aimed at that problem**, (3) **is there an obviously better option than stopping**, (4) **are the candidates N workarounds around one obstacle?** AFK the failure mode is stopping, not asking — the user is not there to answer either way, so a stop is not a cheap question, it is the end of the run. Failing any gate means the threshold was not met → take the better option, keep running, and record it in the run log. Do not package a decision with an obvious answer as an N-way choice for a user who cannot answer it.
  - **Gate 4, in full.** If the options you are about to present all circle the same obstacle, or all rest on one premise nobody verified ("these two can't be done in the same pass", "A must precede B"), the question is not "which one" — it is a report that the work is sitting one layer too low. Falsify the shared premise; the choice usually disappears and the run continues. Verifying a premise costs one command; a STOP costs the rest of the run.
  - **Scope — this gate qualifies a *question*, never a *failure*.** It applies only where a stop is a judgment call: a `blocking` DP and an ambiguous-severity classification. It does **not** apply to the severe-failure row, the exhausted-loop rows, or any cannot-proceed terminal — those stop unconditionally by enumeration, and there is no question there to qualify. ⛔ It is emphatically **not** a licence to diagnose a red check or re-architect around it: `no-auto-fix` is untouched, `self-pacing` still never invokes `fix-bug`, and AFK diagnosis stays out of scope (see `DESIGN.md` rejected-ideas list). Gate 4 asks whether a *decision to hand the user* is real; it never asks whether a *failure* can be worked around.
- **When you do ask, ask everything at once.** Step 2's up-front sweep already batches every pre-existing `blocking` DP into one AskUserQuestion. The same discipline binds the *in-loop* decisions of Step 3.2, which the sweep cannot reach: before stopping on one blocking DP, scan the rest of the current unit's `## Decisions` and any already-surfaced open question, and put them in the same batch. AFK, drip-feeding is not merely annoying — each extra stop is a separate card, a separate turn ending, and in guide mode a separate `dev-workflow:handoff` doc; the user comes back to three artifacts asking three questions that fit in one. If a later decision genuinely cannot be known until an earlier one is answered, say so in the card's `Why` rather than pretending the sequence was unavoidable.
- **When in doubt, stop — scoped, and scoped by reversibility.** This default governs *how severe an already-occurring failure or decision is* (ambiguous severity → treat as blocking). It does **not** govern "should I keep working"; that question has no doubt-defaults, only the enumerated terminals above. Where severity itself is genuinely ambiguous, resolve it on **reversibility, not confidence**: ambiguity about something that would mutate source files or ship user-visible behavior → stop; ambiguity confined to plan text, process ordering, or two equivalent approaches → continue and log. Confidence is unfalsifiable; reversibility is checkable.
  - **The one class that is always the user's, however reversible: a difference they can directly perceive** — a default value, wording, an interaction shape, a layout — where technical fact does not resolve it to a single answer. There the run has no basis to pick, so it stops (this is CLAUDE.md 决策权归属 applied locally, not a new rule).
  - ⛔ **Closing the escape hatch that opens:** "option A performs better, so the experience is better" is **not** a perceivable-difference call. It is a technical fact, and a technical fact resolves to one answer — rank it yourself and continue. Nearly every implementation choice can be narrated as eventually reaching the user; if that narration were enough, this clause would readmit every stop the four-gate check just excluded. The test is whether the *difference itself* is what the user perceives, not whether some consequence of it eventually is.
- **No invisible auto-decisions.** Everything resolved, deferred, or auto-crossed appears in the final review.
- **Bounded retry, never blind retry.** Exactly two bounded loops exist, each capped at one cycle and each fully logged: one byte-identical **re-run** of a red check (mutates nothing) and one **in-scope repair** of a `must-fix` confined to the plan's declared `**Files:**`. Neither is silent: the flake, the finding, the fix, and the re-review verdict all land in the run log and the final review. Everything beyond them stops — a second red, a repair reaching outside the declared files, or any unfamiliar failure. `self-pacing` still never invokes `fix-bug` and never diagnoses; diagnosis requires the user at the keyboard.
  - **Why these two and nothing more — the line is authorization, not confidence.** A re-run changes no bytes. An in-scope repair changes only files the user authorized when they approved this plan at Step 2. Reaching past the declared `**Files:**`, or into diagnosis, mutates the repo outside anything the user agreed to — that is what the no-auto-fix rule protects, and it is untouched.
  - **Scope:** "fix" here means source files. Revising a *plan* under the bounded verify-plan loop is not a fix — see the `Plan fails verification` row and `DESIGN.md` invariant 4(a).
- **Every STOP writes the stop card; terminal STOPs also write the handoff doc.** The card is pointers + stop-delta only — five schema fields plus at most one `## ⛔ 别再跑一遍的` block, never a re-copy of crystal / run-log / plan contents. Which stops get a doc is enumerated by mode in `Two-tier handoff` and is **not** a judgment call. A card that has grown a "what I delivered / what got reversed / what only you can verify" section is a doc that was written into the wrong file — invoke `dev-workflow:handoff` instead.
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

1. **Read the stop card first.** `.claude/self-pacing/<target-slug>-handoff.md` gives `Stopped at` + `Next action` + `Resume with` in one read. The card tells you where you are.
2. **If the card's `Next action` names a `docs/06-plans/HANDOFF-*.md`, read that next** — it is the context transfer for this stop (its §0 tells you what to do before touching anything). The card locates; the doc explains.
3. **Follow the card's `Pointers`** to load the full context, in this order:
   - `docs/11-crystals/*-crystal.md` — locked user decisions (what to do).
   - `.claude/self-pacing/<target-slug>.md` — auto-actions, deferrals, seam crossings, screenshot paths (what happened).
   - `.claude/execute-plan-checkpoint.json` — task-level completion map.
   - `.claude/dev-workflow-state.json` (guide mode) — phase pointer.
   - `docs/06-plans/<plan-file>.md` — the plan being executed.
4. **Resume with the literal command** from `Resume with` (e.g. `/self-pacing`, `/self-pacing phase`, or `yes` for an in-progress STOP).

Do not skip the card and read the artifacts directly — they answer "what" without telling you "where the run stopped" or "what the next action is". The card is the locator; the artifacts are the context.

## Completion Criteria

- Autonomous mode was explicitly authorized for the chosen mode (Step 2).
- phase mode: the unit reached green (or halted at a severity gate); final review presented.
- guide mode: all phases' acceptance criteria checked (or halted at a severity gate); final review presented, including every auto-crossed seam.
- test-changes + applicable reviews ran per unit; results are in the final review.
- Every auto-decision and deferral appears in the final review.
- **If ≥1 blocking DP was resolved at the Step 2 sweep**, the corresponding crystal exists at `docs/11-crystals/<date>-<topic>-crystal.md` (one file, written by Step 2's `crystallize` invocation after the user answered the DPs). If zero blocking DPs were collected, this criterion does not apply — the run is complete without a crystal by design.
- Every STOP that fired during the run has a stop card on disk (`.claude/self-pacing/<target-slug>-handoff.md`); the final card reflects the most recent stop, not a stale one.
- Every **terminal** STOP (per the `Two-tier handoff` mode table) also has a `docs/06-plans/HANDOFF-YYYY-MM-DD-HHMM.md` on disk, hooked into the project `CLAUDE.md`, and the card's `Next action` names it by absolute path.
- The final consolidated review was emitted as HTML via `shared-utils:html-report` (Step 4), with run-log + crystal as source of truth.
