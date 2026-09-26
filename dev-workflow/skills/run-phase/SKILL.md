---
name: run-phase
description: "Use when the user says 'run phase', 'start phase N', 'next phase', '继续开发', '跑下一阶段', '开始第N阶段', or when continuing development guided by a dev-guide. Orchestrates the plan-execute-review cycle for one phase of a development guide: write-plan → verify-plan → execute-plan → test-changes → review agents in parallel → fix issues. Produces: phase completion report + updated workflow state (via scripts/phase.py, the sole writer of .claude/dev-workflow-state.json). Not when: no dev-guide exists — run write-dev-guide first."
effort: high
---

## Overview

This skill orchestrates one iteration of the development cycle. The main context handles orchestration, user gates, plan writing (at `write-plan`'s own pin) and applying fixes. Judgment that needs high effort runs in dispatched agents whose `effort:` pin always applies: plan verification, the reviewers, and root-cause diagnosis of execution and test failures (`dev-workflow:bug-diagnoser`, Step 7). Sonnet handles mechanical execution as a dispatched agent.

```
Locate/Resume Phase
  → scope confirmation checkpoint (main context — opus)
  → write plan (main context — opus, full conversation context)
  → UX review checkpoint (main context — if design has UX Assertions)
  → verify plan (dispatch opus agent — unbiased review)
  → execute plan (dispatch sonnet agent — segmented via Workflow, hard-stop checkpoints)
  → test changes (dispatch sonnet agent — build/test/lint suite)
  → visual feedback loop (main context — render #Preview, diff vs design, fix ≤3x; skipped if non-UI or no design ref)
  → dispatch feature-spec + review agents in parallel (separate contexts)
  → diagnose execution + test failures (dispatch bug-diagnoser agents in parallel, read-only) → fix all issues (main context)
  → Phase done
```

## State File

Location: `.claude/dev-workflow-state.json`. `${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py` is the only writer — never hand-edit it (a `PreToolUse` guard hook enforces this). For anything that doesn't fit an owned key, use `phase.py note "<text>"` — that is the sanctioned place for what used to become an invented key.

Subcommands (each prints one JSON object on stdout; exit 0 success, exit 3 refused/invalid, never a traceback):

- `status [--hook]` — read + validate; `--hook` prints the one-line SessionStart text (or nothing)
- `init --phase N --name S --dev-guide P [--project S] [--force]` — start a phase (refuses unless current step is `done`/`finalized`)
- `step TARGET [--reason S] [--override]` — move `phase_step` along the transition graph; a refused transition is a stop, not something to work around
- `set KEY=VALUE ...` — write an owned key (not `phase_step`)
- `note TEXT` — append a free-text note
- `migrate` — legacy `.yml` → `.json` (or archive the leftover when both exist)
- `quarantine [--target PATH]` — rename an unreadable state file out of the way so `init` can proceed
- `guide` / `phases --dev-guide P` / `locate --dev-guide P` / `check-off --dev-guide P --phase N` / `scope-mode --dev-guide P` — dev-guide operations (Step 1, Step 1.5, Step 8)
- `plan-facts --plan P [--design-doc P] [--crystal P]` / `ux-map --plan P --design-doc P` / `visual-facts --plan P [--design-analysis P] [--design-doc P]` / `complete-gate` — the rule-based gates (Steps 2, 2.5, 3, 5.5, 8.0)

Every call takes `--root DIR` (default cwd) where relevant.

## Agent Dispatch Verification Gate

This skill dispatches sub-agents at multiple steps (Step 4 execute-plan, Step 5 test-changes, Step 6 feature-spec + 4 review agents). The `~/.claude/hooks/verify-agent-output.py` hook intercepts every Agent return and surfaces "files NOT on disk" when a sub-agent's stdout claims it wrote files that don't actually exist.

**Treat agent stdout as a claim, not a fact**:
- After every Agent return in Step 4/5/6, before recording the report path into state, verify the claimed report file actually exists on disk (`ls` or `Read`). If missing: do NOT advance `phase_step`; either re-dispatch the agent with explicit Write tool requirement, or surface the failure to the user.
- For execute-plan (Step 4): the Workflow returns per-task structured results; spot-check by verifying every path in each result's `files_written` array exists on disk (defense-in-depth — the `~/.claude/hooks/verify-agent-output.py` hook also intercepts at agent return time). The execute-plan skill itself owns the segment loop and the checkpoint file, but the run-phase orchestrator should not blindly trust the final summary.
- For test-changes (Step 5): its report file (`docs/06-plans/execution-report.md`, `.claude/test-reports/*.md`) must exist before the next step.
- For review (Step 6): **do NOT check for `.claude/reviews/*.md`.** `review-execution` returns one consolidated object and this skill no longer hunts for per-agent report files (Step 6.4). The success signal is `status.ok === true` on the return object. `status.ok === false` means the review **failed** (a dispatched reviewer threw or returned null, or nothing arrived): surface `status.errored` and never treat the run as clean. Do not infer success from the presence of `coverage` — the script always returns it, including on a failed run. Checking for files here would block on artifacts the contract does not promise the dispatcher ever sees.

This gate is non-negotiable: we have a confirmed past case of a sub-agent reporting file writes that never persisted, caught only because the verify-agent-output hook fired.

## User-Visible Notifications

Long phases (30-60 min from plan → done) can outlast the user's attention. At three checkpoints, emit a `PushNotification` so the user is pulled back when they walked away:

1. **Plan ready for approval** (end of Step 2): when decision points need answering.
2. **All agents returned** (end of Step 6): when consolidated review summary is ready and Step 7 fix-or-skip decision is needed.
3. **Phase done** (end of Step 8): when the phase completes (success or with documented known issues).

Skip notifications when the user has been actively responding within the last minute (heuristic — when in doubt, send). Keep messages short (under 80 chars), lead with the decision needed.

## Process

### Step 1: Resume or Locate Phase

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py status`.
   - `exists:false` → proceed to step 2 (starting fresh).
   - `ok:false` → the state file exists but is unusable. Pick the branch by what `errors` says:
     - **The file itself cannot be used** — `unparseable: …` (JSON or legacy `.yml` syntax error, or not UTF-8), `duplicate keys: …`, or `state is not an object`: show the error to the user and ask which of two they want: (a) they fix the file by hand, then re-run this step; or (b) run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py quarantine` (moves the file it failed on aside as `dev-workflow-state.broken-<timestamp>.<ext>`) and start the phase again with `init` (step 2 below). Do not repair the file yourself — the guard hook denies direct edits and shell rewrites of it.
     - **A field has the wrong type** — `current_phase is not an int`, `gaps_remaining is not an int`, `review_reports is not a list`, `review_findings is not an object`: show the error, ask the user for the correct value, and repair with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py set KEY=VALUE` (e.g. `set current_phase=3`, `set 'review_reports=[]'`). A `set` that reduces the errors is accepted even while other errors remain; its `remaining_errors` lists what is left.
     - **Unknown/off-enum `phase_step`** (`unknown step '<value>'`, or `phase_step is not a string`): show the error and ask which step to resume; repair with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step <chosen-step> --reason "repair: off-enum value was '<old value>'"`, then continue as if that step had been the current one.
     - Several errors at once: repair field types with `set` first, then the step with `step --reason`, then re-run `status`.
   - `ok:true` and `source:"yaml"` (only the legacy `.yml` exists): run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py migrate` and tell the user "ℹ️ Migrated dev-workflow state file from legacy YAML to JSON format". If its output carries `validation_errors`, the legacy data was carried over as-is — repair it as in the `ok:false` branches above before continuing, unless `step` is `done`/`finalized` (then skip the repair and go to step 2: nothing is in progress and `init` replaces those keys).
   - `ok:true` with `warnings` (only when `step` is `done`/`finalized`): the finished state has a bad field (e.g. a letter `current_phase`). Nothing is in progress — carry on to step 2; `init` replaces every owned key.
   - `ok:true` with `legacy_alias_applied:true`: the on-disk `phase_step` was `spec` or `build-test` (legacy); `step` already reports the aliased value (`review`/`test`) — proceed with that.
   - `ok:true` and `legacy_leftover:true` (both `.json` and `.yml` exist): run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py migrate` (archives the leftover `.yml`) before continuing.
   - `ok:true` and `step` is not `done`/`finalized`:
     - Present: "Phase {current_phase} ({phase_name}) in progress — step: {step}. Resume?"
     - If user accepts:
       - **Scope drift check** (only when `step` is `plan` AND `state.plan_file` is not null): Read the Phase's current scope from the dev-guide and compare with the plan file's `Scope:` section. If they differ: "Dev-guide scope has changed since the plan was written. Re-run scope confirmation (Step 1.5)?" If user accepts: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step plan --reason "scope drift — re-confirming"` and `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py set plan_file=null`, then run Step 1.5. If user declines: proceed with existing plan. For steps after `plan` (verify/execute/review/fix): no check needed — the plan is the working document.
       - Skip to the step indicated by `step`
     - If user declines: ask which Phase to start
2. If no state file or starting fresh:
   - `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py guide` — picks `docs/06-plans/*-dev-guide.md` (`current: true` in frontmatter breaks ties). `ok:false` with `candidates` → ask the user which one.
   - `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py locate --dev-guide <path>` — the first Phase with `complete:false`. `all_complete:true` → all Phases are done; tell the user and stop.
   - Read the dev-guide's Goal, Scope, Architecture decisions, Acceptance criteria for that Phase (judgment: presenting this well is not `phases`' job, it only counts checkboxes).
   - Present Phase summary: Goal, Scope, Architecture decisions, Acceptance criteria
   - Ask: "Start Phase N?"
3. Initialize state: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py init --phase <N> --name "<Phase name>" --dev-guide <path> --project "<from dev-guide title>"`.

If the user specifies a different Phase number, use that instead.

### Step 1.4: Project Health Preflight

Before Step 1.5, read `.claude/dev-workflow-health.json` if present.

- If state is missing, OR `last_health` has any red signal, OR state's `updated_at` is older than 7 days, run `${CLAUDE_PLUGIN_ROOT}/scripts/project_health_scan.py --mode full --reason plan --check-staleness 7 --max-ms 5000 --format markdown --write-state` and use the fresh report.
- Otherwise reuse cached `last_health` from state (no scan invocation).
- Summarize red/yellow Project Health signals before planning.
- Feed those signals into the write-plan context so the plan header includes `**Project health:**`.
- Do not change orchestration order: Project Health adds context only; it cannot skip scope confirmation, verify-plan, execute-plan, test-changes, or review.

The generated plan must still include `## Impact Map` and per-task `Task Contract` fields when `contract_version: 1` is used.

### Step 1.5: Scope & Visual Expectation Confirmation

Before writing the plan, present the Phase scope and visual expectations for explicit user confirmation.

**Skip condition:** When resuming from state file with `phase_step` not `plan`, skip this step — scope was already confirmed in a prior session.

**Freshness check:** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py scope-mode --dev-guide <path>`. `mode:"lightweight"` (frontmatter `confirmed_at` within 60 minutes of now) → step 1b. `mode:"full"` → step 1a.

**1a. Full mode** (default):

Read the Phase's scope items and `**用户可见的变化:**` section from the dev-guide. Present to the user:

```
Phase {N} — confirm before planning:

范围：
1. {scope item 1}
2. {scope item 2}
...

用户可见的变化：
- {visual expectation 1, from dev-guide}
- {visual expectation 2}
（如果有需要补充的布局、交互细节，请在这一步告诉我）

确认以上内容，或补充/修正后继续。
```

If `**用户可见的变化:**` starts with "无" (infrastructure Phase, e.g., "无" or "无 — 纯基建阶段"), present scope only (omit the visual section).

**1b. Lightweight mode** (confirmed_at within 60 min):

```
Phase {N} 范围已在 dev-guide 中确认。
有新增视觉/交互细节要补充吗？没有则直接开始规划。
```

User responds:
- No additions → proceed to Step 2 (skip steps 3-4 below)
- Adds visual/interaction details → proceed to step 4 (auto-crystal), same as full mode

3. Wait for user response (full mode only):
   - User confirms without additions → proceed to Step 2
   - User corrects scope → edit the Phase's `**Scope:**` bulleted list in the dev-guide file to match user's corrections, then check acceptance criteria sync (see below), re-present for confirmation
   - User adds visual/interaction details → proceed to step 4 (auto-crystal)
   - Max 2 correction cycles; after that, ask via AskUserQuestion (three options: proceed with last-confirmed content / one more correction round / switch to `/dev-workflow:brainstorm` to re-align). Do NOT proceed unilaterally — global CLAUDE.md: any "先这样" moment must ask. If brainstorm is chosen: re-enter this Step after brainstorm concludes; do not advance `phase_step`.

   **Acceptance criteria sync** (after scope correction): Compare the Phase's `**Acceptance criteria:**` with the updated scope:
   - If any criterion references a removed scope item → flag: "验收标准 '{criterion}' 对应的范围项已移除，是否同步删除？"
   - If new scope items lack corresponding criteria → flag: "新增范围项 '{item}' 无验收标准，是否补充？"
   - Present flags to user. Apply user's decisions (delete/add criteria) to the dev-guide before re-presenting the Phase.
   - If no mismatches found, skip silently.

4. **Auto-crystal** (conditional): If the user's response contains any new visual/interaction detail not already in the dev-guide's `用户可见的变化` section, treat as "adds details" regardless of whether they also said "confirmed."

   **4a. Assemble decisions:** Extract from the user's input:
   - Each confirmed visual/interaction detail → `[D-xxx]` in imperative form
   - Each explicitly rejected approach → `## Rejected Alternatives` + `## Constraints`
   - If no alternatives were discussed or rejected, write `None.` for those sections

   **4b. Confirm with user:** Present the assembled decisions in-line:
   ```
   以下视觉/交互决策将记录供后续规划使用：
   - [D-001] {detail}
   - [D-002] {detail}
   约束：{constraints, or "无"}

   确认记录，或修改后继续。
   ```
   Apply user edits if any, then proceed to write.

   **4c. Write crystal file:**
   - First, search `docs/11-crystals/*-crystal.md` for an existing crystal file
   - **If an existing crystal file is found:** append the visual decisions to it — add new `[D-xxx]` entries (continuing the existing numbering) to `## Decisions (machine-readable)`, merge new items into `## Constraints` and `## Scope Boundaries`. Do not overwrite existing content.
   - **If no existing crystal file:** create `docs/11-crystals/YYYY-MM-DD-phase-{N}-visual-crystal.md` using this format:

   ```markdown
   # Decision Crystal: Phase {N} Visual Expectations

   Date: YYYY-MM-DD

   ## Initial Idea
   {User's original visual description, denoised but not rewritten}

   ## Discussion Points
   {Any back-and-forth from the confirmation, if applicable}

   ## Rejected Alternatives
   {Approaches the user explicitly rejected, or "None."}

   ## Decisions (machine-readable)
   - [D-001] {confirmed visual/interaction detail in imperative form}
   - [D-002] {detail}

   ## Constraints
   {Explicitly rejected visual approaches, or "None."}

   ## Scope Boundaries
   - IN: {items from user's visual additions}

   ## Source Context
   - Design doc: {path or "none"}
   - Dev-guide: {dev-guide path} Phase {N}
   ```

   - Do NOT invoke /crystallize as a separate skill — write the file directly

This checkpoint catches scope pollution and aligns visual expectations before writing the plan.

### Step 2: Plan (main context)

1. Update state: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step plan`
2. Gather Phase context from dev-guide:
   - Goal: Phase N's goal
   - Scope: Phase N's scope items
   - Acceptance criteria: Phase N's acceptance criteria
   - Design doc reference: from dev-guide header (if exists)
   - Design analysis reference: search `docs/06-plans/*-design-analysis.md`; if exactly 1 file, use it; if multiple, use the one whose filename matches the Phase's feature topic; if still ambiguous, ask the user; if none, set to "none"
   - Crystal file reference: search `docs/11-crystals/*-crystal.md`; if exactly 1 file, use it; if multiple, ask the user which one applies; if none, set to "none"
   - If no crystal file found AND the Phase has architecture decisions marked as "resolved" in the dev-guide: suggest `/crystallize` to capture these decisions before planning. Do not block — user can decline and proceed without a crystal file.
3. If a design doc path exists: read the design doc and check for a `## UX Assertions` section. Note the result — it controls Step 2.5.
4. **Preload relevant lessons:**
   - Extract keywords from Phase scope items and goal (component names, technology terms, domain terms)
   - Search `docs/09-lessons-learned/` for entries matching these keywords:
     `Grep(pattern="<keyword1>|<keyword2>|<keyword3>", path="docs/09-lessons-learned/", output_mode="content", context=5)`
   - If matches found: note the matching lesson entries for reference during plan writing
   - If no matches or directory does not exist: skip silently
5. **Read source files:** Read the design doc, design analysis, crystal file (if any), and key codebase files relevant to the Phase scope. This grounds the plan in actual code state.
6. **Write the plan** following the Plan Writing Reference in `${CLAUDE_PLUGIN_ROOT}/skills/write-plan/SKILL.md`. Use the gathered Phase context as inputs. Save to `docs/06-plans/YYYY-MM-DD-<feature-name>-plan.md`.
7. Update state: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py set plan_file=<path>`
8. Present plan summary to user (task count, key files)
9. **Decision Points:** Check the `## Decisions` section of the plan file.
   - If Decisions > 0:
     - First time this session: Read `${CLAUDE_PLUGIN_ROOT}/references/decision-points.md`
     - Apply the rules with parameters:
       - Source file: the plan file
       - Mode: `full`
       - Recording: `default`
10. `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py plan-facts --plan <path> --design-doc <path-or-none> --crystal <path-or-none>` reports `tasks`, `fast` and `auto_approve`. `fast:true` → mark `--fast` for Step 3 (use Sonnet for verification). `fast:false` → no flag (use Opus default).
11. **PushNotification checkpoint 1**: if the plan's `## Decisions` section has > 0 unresolved DPs, emit a `PushNotification` with message like `Phase {N} plan ready — {K} decisions await your input` (see "## User-Visible Notifications" above).

### Step 2.5: UX Review (conditional)

**Trigger condition:** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py ux-map --plan <path> --design-doc <path>` reports `triggered:true` when the design doc has a `## UX Assertions` table with ≥1 data row. `triggered:false` → skip to Step 3.

1. Update state: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step ux-review`
2. Read the generated plan file
3. Read the design doc's `## User Journeys` section (`ux-map`'s `rows` already carries the assertion ↔ task ↔ user-interaction mapping; only the journeys section still needs a read)
4. `ux-map`'s output is the mapping table: `rows` (`{ux_id, assertion, tasks, user_interaction, mapped}`) and `unmapped_ui_tasks`.

5. Present to user:

```
UX Assertion Coverage:

| UX ID | Assertion | Plan Task(s) | User Interaction | Status |
|-------|-----------|-------------|-----------------|--------|
| UX-001 | {assertion text} | Task 3, Task 5 | {from task's User interaction: line, or "—"} | ✅ Mapped |
| UX-002 | {assertion text} | — | — | ❌ No task |
| UX-003 | {assertion text} | Task 7 | {from task} | ✅ Mapped |

Unmapped UI tasks (no UX ref):
- Task 4: {task title} — {reason or "needs UX assertion?"}

Confirm this mapping is correct, or provide corrections.
```

6. Wait for user response:
   - **User confirms**: proceed to Step 3
   - **User provides corrections**:
     - For minor fixes (add/correct `UX ref:` lines, adjust `User interaction:` text): edit the plan file directly
     - For structural changes (add missing tasks, redesign task scope): revise the plan directly in main context
     - Re-present the mapping for confirmation after corrections
   - Max 2 correction cycles; after that, ask via AskUserQuestion (three options: proceed with noted gaps / one more correction round / switch to `/dev-workflow:brainstorm` to re-align). Do NOT proceed unilaterally — the noted gaps are UX-mapping gaps, exactly the "先这样" case global CLAUDE.md forbids deciding alone. If brainstorm is chosen: re-enter this Step after brainstorm concludes; do not advance `phase_step`.

7. No further state write here — `step ux-review` in item 1 already recorded this step; corrections in this step land in the plan file, not the state file.

### Step 3: Verify

**Auto-approve condition:** `plan-facts.auto_approve` from Step 2 item 10 (≤3 tasks, no design doc, no crystal file).

When `auto_approve:true`, skip full agent verification. Instead:
1. `plan-facts.lint` (already computed in Step 2 item 10) is the sanity check — it reports what `write-plan/scripts/lint_plan.py` finds (each task has `**Files:**`/`**Steps:**`, no obvious gaps). Note any findings.
2. Update state: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step verify` then `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py set verification_report="auto-approved (small plan)"`
3. Skip to Step 4

**Otherwise:** proceed with full verification below.

1. Update state: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step verify`
2. Invoke `dev-workflow:verify-plan` with the plan from Step 2 (pass `--fast` flag if set in Step 2)
3. Update state: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py set verification_report="<summary>"`

**If "Must revise" and a blocking item cannot be revised in the plan** (it needs a decision or information you do not have):
Present the remaining issues to the user:
> "Plan verification left blocking items I cannot resolve in the plan. Remaining issues:
> [list specific issues from verifier output]
>
> Options:
> A. Stop and manually revise the plan, then re-run this step
> B. Proceed with imperfect plan (issues noted in execution — treat as extra caution points)"

Wait for user choice. If A: stop. If B: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py set verification_report="partial"` and continue.

### Step 4: Execute (segmented sonnet agent dispatch via Workflow)

1. Update state: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step execute`
2. Invoke `dev-workflow:execute-plan` to handle execution. The skill manages the full segmented dispatch lifecycle:
   - Runs `compute_checkpoints.py` to derive batches + hard_stops
   - Creates `.claude/execute-plan-checkpoint.json` (segment metadata: `plan_file`, `total`, `batch_size`, `k`, `hard_stops`, `status`; plus the `completed` map owned by the task agents)
   - For each segment: invokes `Workflow({scriptPath, args})` with the segment's batches, awaits completion, spot-checks `files_written`, then either auto-continues to the next segment or pauses at a hard-stop for the user to say "continue"
   - Cross-session resume: the on-disk checkpoint file's `completed` map is authoritative; `Workflow({resumeFromRunId})` is same-session only
   - Returns an explicit completion signal (the Terminal-write step): `Execution complete: complete` or `Execution complete: completed_with_failures`, or `Paused at hard-stop: waiting for "continue"` — never a silent return
   - On `complete`: deletes the checkpoint file; on `completed_with_failures`: retains it with `status: "completed_with_failures"` (the cross-session source for the fix pass)
3. **Completion detection — trust execute-plan's explicit return (in-context), not a file grep.** execute-plan runs as the same main agent following nested instructions, so its return is available directly:
   - `Execution complete: complete` or `completed_with_failures` → execution finished; proceed (route failures to Step 7). Read the report at `docs/06-plans/execution-report.md` for the summary.
   - `Paused at hard-stop: waiting for "continue"` → NOT finished (see item 4).
   - Durable backup only (cross-session / truncated return): the report's `**Status:**` line **under this plan's `**Plan:** <path>` section** — `complete`/`completed_with_failures` = done, `in-progress` = interrupted. (Scope to the plan section; the report is a shared append-log with one Status line per plan.)
4. **Do NOT advance to Step 5 while execution is paused at a hard-stop.** If execute-plan returns `Paused at hard-stop`, execution did NOT complete — surface to the user that it is waiting for "continue"; do not advance to Step 5 and do not route to Step 7. Only a `completed_with_failures` return routes failed/blocked tasks to Step 7 (Fix).
5. Present summary: completed/blocked/failed task counts
6. If blocked or failed tasks exist: note them for Step 7 (Fix)
7. No further state write here — item 1's `step execute` already recorded this step; task outcomes are read from execute-plan's return and the execution report, not stored in state.

### Step 5: Test Changes (sonnet agent dispatch)

1. Update state: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step test`
2. Invoke `dev-workflow:test-changes` with:
   - Project root
   - Plan file path (from state `plan_file`)
3. When the skill returns: read the test report path from its output
4. Present test summary: Build (pass/fail), Tests (X/Y passed), Lint (pass/fail)
5. If test failures exist: note them for Step 7 (Fix)
6. Update state: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py set test_report=<report path>`

### Step 5.5: Visual Feedback Loop (main context — opus)

This step closes the visual gap between implemented UI and design reference before human review (D-010: 把界面拉到八九不离十，最后一公里人工；非全自动像素级). It runs after test-changes and before the review agents, so reviewers see visually-corrected code.

⚠️ 需项目验证：真机 iOS 项目里实跑该 step（渲染→diff→修→收敛/交人）本仓无法验证。

1. Update state: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step visual`

2. **Gates ① and ②, and the `#Preview` filter — one call:** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py visual-facts --plan <path> --design-analysis <path-or-omit> --design-doc <path-or-omit>`. It reports `apple_dev_installed`, `views` (modified SwiftUI view files, by the same `*View`/`*Card`/`*Row`/`*Cell`/`*Tab`/`*Screen`/`*Sheet`/`*Banner` suffix OR `#Preview`/`: View` content rule — do NOT narrow this to `*View.swift` only, SwiftUI views are frequently named `Card`/`Row`/`Tab`/`Screen`), `preview_views` (the subset with a `#Preview` block), `design_image` (first existing of `/tmp/design-screenshot-*.png`, the design-analysis doc's first referenced image, the design doc's first referenced image), and `skip_reason` (`apple-dev not installed` | `non-UI phase` | `no design reference image` | `no #Preview blocks`, or `null`).
   - `skip_reason` not null → skip this entire step: log `Visual step skipped: {skip_reason}`, `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step review`, proceed to Step 6.
   - Optional cross-check: `git diff --name-only` against the phase's starting commit (only if a baseline ref was recorded), filtered by the same view-detection rule
   - Note: Step 6 no longer computes a ui-reviewer condition itself — it hands `scope_files` to `review-execution`, which routes on `HAS_VIEW_MODIFIED` from the diff. This step still derives its own list because it runs first and needs one before any review exists. The two can differ: `visual-facts`' view-detection deliberately catches `*Card` / `*Row` / `*Screen` names that a `*View.swift` match misses, and its own fixes may touch further files. Expected, not a defect — but do not "unify" them by narrowing this one to `*View.swift`.

3. `visual-facts`' `design_image` field is Gate ②'s result — do NOT attempt self-evaluation without a reference image (already enforced by `skip_reason`).

4. **Render-diff-fix loop** (`skip_reason` is null) — iterate `preview_views` from `visual-facts`. For each such view:

   a. Invoke `apple-dev:render-preview` via the Skill tool, passing `swiftFile: <absolute path to this view's .swift file>`, `outputDir: <a caller-controlled dir under the repo, e.g. .claude/visual-phase{N}/>` (REQUIRED; do NOT omit, because render-preview's default system-temp dir is non-deterministic to this caller), and `previewId` when the file has multiple `#Preview` blocks. render-preview is `context: fork`, so its returned message is summarized; do NOT parse the returned message for the path. Instead read the authoritative result file it writes at `<outputDir>/<name>.result.json` (`<name>` = the `.swift` basename, plus `-{previewId}` when set) and parse `{channel, pngPath, downsampled, error}` from that file.
      - If the result file is missing OR `error` is not null: log `Render failed for {ViewName}: {error or "no result file"}` and skip this view; continue to next.
   b. Read `pngPath` (the value from the result file) in main context. Compare rendered output against the design reference image: identify visual differences (spacing, layer hierarchy, color, text truncation, overflow).
   c. If differences are **material**: fix the corresponding SwiftUI code in main context, then return to step (a) to re-render.
   d. **Iteration cap: ≤3 rounds per view.** If cap reached with remaining differences, stop and record them.

5. **Hand-off** — after the loop:
   - Collect all remaining differences (cap-reached or skipped views) into a plain-language list using spatial language (screen position and appearance — no code identifiers).
   - Present as **informational items** (do NOT use AskUserQuestion — same nature as Step 6 human-verification items):
     > 视觉仍有差异（需真机/人工定夺）：
     > - [ ] {item, spatial language}
   - Emit a `PushNotification` (< 80 chars, follow run-phase notification style), e.g.: `Phase {N} visual loop done — {N} diffs remain for human review`

6. `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step review`, proceed to Step 6.

### Step 6: Document Features & Reviews (parallel agent dispatch)

1. Update state (a no-op if item 6 above already advanced it): `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step review`

2. **Determine agents to dispatch:**

   **Feature spec agents (conditional):**
   - Check the Phase scope for completed user journeys (a user journey is "completed" when all its acceptance criteria in the dev-guide are checked off)
   - If this is NOT an infrastructure-only Phase: confirm feature name and scope with the user, then prepare `dev-workflow:feature-spec-writer` dispatch for each completed feature
   - If infrastructure-only (no user journeys): no feature-spec-writer dispatch

   **Review — one call, not a reviewer list:**

   Invoke `dev-workflow:review-execution`, passing:
   - `plan_path` — this Phase's plan file (this is what adds the plan-vs-code lens; without it that lens is skipped)
   - `design_doc_path` — from state or the dev-guide, or "none"
   - `scope_files` — **the files this Phase touched**, not the whole working tree
   - `mode: gated` — must-fix findings block and come back for the fix loop below

   `scope_files` is not optional here. The working tree can hold changes from outside this Phase; reviewing them would silently widen what this Phase is accountable for.

   `review-execution` owns which reviewers apply and routes them from the diff's shape — including the apple-dev reviewers and the apple-dev-installed check. **Do not keep a reviewer list here.** Until now this step named its own agents and dispatched the same apple-dev reviewers that `review-execution` dispatched, by different signals; running both sent the same agents out twice with different scopes. One dispatcher removes that by construction.

   - **If this is the submission prep Phase:** invoke `/asc-submit-preview` skill after the review returns (requires apple-dev installed; if not, note in summary and skip)

3. **Dispatch ALL agents in parallel** using the Agent tool in a single message:

   For feature-spec-writer (if applicable):
   ```
   Generate a feature spec with the following inputs:

   Feature name: {name}
   Feature scope: {scope}
   Design doc paths:
   {relevant design doc paths and sections}
   Dev-guide: {dev-guide path} Phase {N}
   Key implementation files:
   {list of key files}
   Project root: {project root}
   ```

   For review: the single `dev-workflow:review-execution` call described above. It dispatches every applicable reviewer in one batch itself — do not add per-agent dispatches here.

   Each agent receives a fresh context — they have no memory of how the code was written.
   This removes confirmation bias from self-review.

4. **When they return:** `review-execution` returns one consolidated object — read that, not per-agent report files:
   - `must_fix` / `nice_to_have` — arrays of `{lens, agentType, file, line, text}`
   - `coverage` — per-lens counts (`'errored'` for a lens that died), `lens_e`, `scope`, `apple`, `dispatched`, `contract_warnings`
   - `passthrough` — keyed by agentType, each reviewer's `verdict`, `report_path` and its contract fields (items 5, 7, 8 and Step 7 read these)
   - `status` — `{ok, arrived, missing, errored}`, the success signal
   - `rendered` — the markdown block to show the user as-is

   ⛔ **Gate on `status.ok` before anything below.** `status.ok === true` → continue. `status.ok === false` → the review **failed**, it is not a clean result: show `rendered` (it opens with a `⚠️ Review incomplete` line) and every `status.errored` entry (`label`, `agentType`, `error`), then ask the user whether to re-run the review or accept the partial coverage. Still run item 7 (its dispatched-vs-arrived check is exactly what names the missing device items on a failed run), but do not reach item 9 until the user has answered — item 9's sentinel is what lets Step 8.0's gate pass, so writing it after a failed review records a review that did not happen. Do not retry review agents on your own (their output is informational, and a retry doubles the cost of the most expensive step in this phase).

   `feature-spec-writer` still returns on its own and is handled as before.

5. Present a consolidated summary table:

| Agent | Verdict | Issues |
|-------|---------|--------|
| Feature Spec: {name} | ✅/❌ | {user story counts} |
| Implementation | ✅/❌ | {gap counts from `passthrough['dev-workflow:implementation-reviewer'].gaps_line`}, {pre-existing count from `passthrough['dev-workflow:implementation-reviewer'].pre_existing_line`} — Tests: {required}/{exist}/{covered} from `passthrough['dev-workflow:implementation-reviewer'].tests_line` |
| UI | ✅/❌ | {counts} |
| Design | ✅/⚠️ | {counts} |
| Feature Review | ✅/❌ | {counts} |

**Verdict legend:** ✅ = `pass` · ❌ = `fail` · ⚠️ = `needs-attention`. `design-reviewer` emits `needs-attention`, never `fail` — every check it runs is a judgment, and a judgment that blocks a merge gets argued with and eventually ignored, taking the load-bearing findings with it. ⚠️ ranks the report; it does not gate Step 8.

⛔ **No `Report/Spec` path column.** `review-execution` returns findings, not paths (Step 6.4), so the column could only render empty — and an empty path column invites exactly the per-agent file hunt this consolidation removed.

6. **Feature spec decision points:** If feature-spec-writer was dispatched, check its return for `Decisions:` count.
   - If Decisions > 0:
     - First time this session: Read `${CLAUDE_PLUGIN_ROOT}/references/decision-points.md`
     - Apply the rules with parameters:
       - Source file: the spec file
       - Mode: `full`
       - Recording: `default`

7. **Surface human verification items:** read them from the review return's `passthrough` object — not from per-agent report files, which this step no longer hunts for. Extract these fields when present:
     - `passthrough['apple-dev:ui-reviewer'].part_c_human_verification`
     - `passthrough['apple-dev:design-reviewer'].part_b_device_verification` (its 🔴 lines arrive separately, in `passthrough['apple-dev:design-reviewer'].part_a_red`)
     - `passthrough['apple-dev:feature-reviewer'].part_c_device_verification`
   - Consolidate, deduplicate, and present in plain language below the summary table:

   > 以下需要在设备上确认（来自 review 报告）：
   > - [ ] {item, translated to spatial language — use screen position and appearance, NO code identifiers}
   > - [ ] {item}
   > - [ ] ⚠️ 需真机：{animation/transition items}

   This is informational — do not block with AskUserQuestion. The user can raise issues during Step 7 (Fix Gaps).

   - ⛔ **Before moving on, cross-check dispatched-vs-arrived.** Read two lists from the review return, and print one ⚠️ line per entry — never a summary count, never nothing:
     - `status.missing` — every dispatched reviewer that did not arrive. Named reviewers appear by agentType (the same key `passthrough` uses); the five plain lenses appear as `lens:A`…`lens:F`. Skip the `lens:*` entries here (they carry no `passthrough` fields, and the item-4 gate already surfaced them via `status.errored`). For each remaining entry print:

       > ⚠️ {agentType} 跑过了，但它的字段没有出现在 `passthrough` 里 —— 设备验证项这一轮是缺的，不是没有。报告文件：`.claude/reviews/{reviewer}-*.md`

     - `coverage.contract_warnings` — a reviewer that arrived but in a broken shape: `kind: 'count_mismatch'` (the counts-only shape — it declared N items and the field does not hold N lines) or `kind: 'empty'` (the empty-field shape — a line that always carries a count, such as implementation-reviewer's `Tests:`, came back empty). For each entry print:

       > ⚠️ {agentType}.{field} 的内容和它自己报的不一致（{declared_count} 声明 / {actual_lines} 实际，或为空）—— 这一项不能当成「没有」。

     On a healthy run both lists are empty and nothing is printed — every `passthrough` key is in `status.arrived`, so this check raises no false warnings.

     **Why this line has to exist:** the failure mode of this chain is silence. If a reviewer returns only counts, or the dispatcher trims the handback, this step prints nothing and the phase looks clean — which is exactly how the device-verification items went missing before 2026-09-04. A dispatched reviewer with no arriving `passthrough` entry is a broken contract, not an empty result; the two must be distinguishable on screen. Same distinction `review-execution` already makes for its routing flags: "assessed, nothing applied" is not "never looked".

8. **Surface test coverage summary:** If the review return's `passthrough['dev-workflow:implementation-reviewer'].tests_line` is present:
   - Extract: required, exist, pass, shell counts
   - If shell > 0 or pass < required: present warning below the human verification items:
     > ⚠️ 测试覆盖不完整：{N} 个计划要求的测试中，{M} 个为空壳或未覆盖核心路径

9. Update state, with N = `must_fix.length` and M = `nice_to_have.length` from the review return (only after `status.ok === true`, or after the user accepted a failed review's partial coverage at item 4): `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py set 'review_reports=["review-execution:consolidated"]' 'review_findings={"must_fix": <N>, "nice_to_have": <M>}'`

   ⛔ **Do not write report file paths here.** `review-execution` returns findings, not paths — recording `[]` and then hitting the Step 8.0 gate below produces a false "no test or review reports found" block on a phase that was actually reviewed. The sentinel records *that review ran*; the counts record *what it found*.
10. **PushNotification checkpoint 2**: emit `PushNotification` with message like `Phase {N} reviews complete — {N} gaps, {M} verifications need device` (see "## User-Visible Notifications" above). Skip if all agents passed with zero issues AND the user has been responding within the last minute.

### Step 7: Fix Issues

If any of the following have issues: execution report (blocked/failed tasks), test report (build/test/lint failures), or review reports (gaps):

1. Update state: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step fix`
2. Collect all issues from three sources:
   a. **Execution failures** (from Step 4): blocked/failed tasks from the execute-plan agent report
   b. **Test failures** (from Step 5): build errors, test failures, lint errors from the test-changes report
   c. **Review gaps** (from Step 6): `passthrough['dev-workflow:implementation-reviewer'].gaps_line` (plan-vs-code gaps), `passthrough['dev-workflow:implementation-reviewer'].pre_existing_line` (pre-existing issues)
   Read the relevant report files for full details. Skip entries that are not file paths (e.g. the `"user-override"` and `"review-execution:consolidated"` sentinels — the latter means the findings are in the consolidated return, not on disk).
3. List all issues sorted by severity (critical first, then warnings)
   Separate by origin:
   - **执行阻塞（{N} 个）：**
   > - {blocked/failed tasks with reasons}
   - **测试失败（{N} 个）：**
   > - Build: {errors if any}
   > - Tests: {failing test names + assertion messages}
   > - Lint: {errors if any}
   - **Review 问题（{N} 个）：**
   > - {`passthrough['dev-workflow:implementation-reviewer'].gaps_line`}
   - **已有问题（{M} 个）：**
   > - {`passthrough['dev-workflow:implementation-reviewer'].pre_existing_line`}

4. Ask the user: "Fix these issues before moving on, or mark as known issues?"
5. If fixing:
   a. **Separate design issues from code issues.** If the review return's `passthrough['apple-dev:design-reviewer']` is present:
      - Extract all 🔴 items from `passthrough['apple-dev:design-reviewer'].part_a_red`
      - Group by category: Hierarchy (A1, A11, A15), Spacing (A3, A12), Consistency (A5, A6), Color (A2), Polish (A13, A14, A16)
      - Present design issues separately from other review issues:
        > 设计问题（{N} 个必须修复）：
        > - {category}: {count}
        > 代码/UI 问题（{M} 个）：
        > - {summary}
   b. **Diagnose execution and test failures before fixing.** For each failed/blocked task (2a) and each failing test or build error (2b), dispatch `Agent(subagent_type: "dev-workflow:bug-diagnoser")`. Send all of them in one message so they run in parallel, one agent per failure; group only failures that share an obvious single cause (e.g. one build error cascading into many test failures). Review gaps (2c) already carry file:line and skip this. Pass each agent:
      - the absolute project root
      - Symptom: the task id plus its failure/blocked reason from the execute-plan return, or the failing test name plus its assertion message (or the build/lint error text), verbatim
      - Evidence paths: `docs/06-plans/execution-report.md` and/or the test report path (state `test_report`), the plan file (state `plan_file`), and the task's scope files
      - "Read the reports; do not rerun tests or xcodebuild." The test report is the evidence. Apple builds must stay serialized in the main session.
      Use each `## Diagnosis` return this way. `confirmed` / `probable`: fix at `Cause` and at every `Same-Cause Sites` entry, and check `Consumers`. `need-experiment`: run the experiment in the main context, then fix or re-dispatch. `Design Verdict: design`: don't patch it silently; present it to the user with the agent's evidence before changing the behavior. `unknown` / `insufficient-input`: list it as unresolved in the fix summary.
      **If a dispatch fails** (error, timeout, no `## Diagnosis` block), say that diagnosis did NOT run for that failure. Don't count it as diagnosed. Don't read the failure as "no findings". Any fix you make for it anyway is marked "undiagnosed" in the fix summary.
   c. Fix all issues (design + code), then re-run test-changes if it had failures. To re-review, call `review-execution` again with the same inputs — it re-dispatches only what the current diff routes to, so a narrowed fix naturally narrows the re-review; there is no per-agent re-run to assemble here.
   d. **Design re-verification limit**: If design-reviewer still fails after 1 fix cycle,
      report remaining design issues and proceed — do not loop.
      Other reviewers (implementation, UI, feature) follow existing behavior.
6. If skipping: note the known issues and proceed
7. Update state: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py set gaps_remaining=<count>`
8. **Decision Points:** Check `passthrough['dev-workflow:implementation-reviewer'].decisions_line` for a Decisions count.
   - If Decisions > 0:
     - First time this session: Read `${CLAUDE_PLUGIN_ROOT}/references/decision-points.md`
     - Apply the rules with parameters:
       - Source file: `passthrough['dev-workflow:implementation-reviewer'].report_path`
       - Mode: `mixed`
       - Recording: `default`
   - Then proceed to Step 8

### Step 8: Phase Completion

0. **Pre-completion gate** (structural enforcement): `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py complete-gate`.
   - `ok:true` → proceed to item 1 with a plain `step done` (no `--override`).
   - `block:"no-reports"` (`review_reports` empty AND `test_report` null — neither step ran):
     **BLOCK**: "Cannot complete phase: no test or review reports found. Run Step 5 and Step 6 before marking phase as done."
     Do NOT proceed. Use AskUserQuestion:
     - Option A: "Run Step 5 now" → return to Step 5
     - Option B: "Skip test and review, complete phase" → proceed to item 1 with `step done --override --reason "user chose to skip test/review"` (writes the `user-override` sentinels into `review_reports`/`test_report`)
   - `block:"gaps"` (review findings carry `must_fix > 0` AND `gaps_remaining > 0`):
     **BLOCK**: "Cannot complete phase: {gaps_remaining} unresolved gaps."
     Do NOT proceed. Use AskUserQuestion:
     - Option A: "Fix gaps (Step 7)" → return to Step 7
     - Option B: "Mark as known issues and complete" → proceed to item 1 with `step done --override --reason "gaps accepted as known issues"` (writes a `notes` entry only — real report values are never overwritten)

1. Update state as decided in item 0: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step done [--override --reason "<reason>"]`
2. Update the dev-guide: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py check-off --dev-guide <path> --phase <N>` ticks this Phase's acceptance criteria and inserts `**Status:** ✅ Completed — <date>`. Its return carries `all_phases_complete`, used in item 5 below.
3. **Issue archival** (conditional): If Step 6 has items marked as "known issues" or skipped gaps:
   - Ask: "Create GitHub Issues for {N} deferred items?"
   - If yes:
     - Check label existence: `gh label list --json name -q '.[].name'`
     - If `deferred` label doesn't exist, create it: `gh label create "deferred" --color "FBCA04" --description "Deferred from phase review"`
     - If `phase-{N}` label doesn't exist, create it: `gh label create "phase-{N}" --color "0E8A16" --description "Phase {N}"`
     - For each deferred item, run `gh issue create` with labels `deferred` and `phase-{current phase number}`. Use the item description as issue body under `### Symptom`.
   - Display all created issue URLs.
4. Remind the user to update project docs:
   - `docs/07-changelog/` — record changes
   - `docs/03-decisions/` — if architectural decisions were made
5. Report:

   **Detect if this is the last phase:** item 2's `check-off` return already carries `all_phases_complete` — no re-read needed.

   **If more phases remain:**
   > Phase N complete.
   > Next: Phase N+1 — [name]: [goal].
   > Run `/run-phase` to continue, or `/commit` to save progress first.

   **If all phases are complete:**
   > Phase N complete. All phases done.
   > Run `/finalize` for cross-phase validation, or `/commit` to save progress.

6. **PushNotification checkpoint 3**: emit `PushNotification` with message like `Phase {N} done — {next-action}` where next-action is either `next phase N+1 ready` or `all phases complete — run /finalize`. Always send this one (phase completion is a high-signal event regardless of activity).

## Rules

- **Never skip Step 5 or Step 6.** Testing and reviews are not optional.
- **Never skip verification.** Step 3 must run before Step 4.
- **Phase order matters.** Don't start Phase N+1 if Phase N has unchecked acceptance criteria (unless user explicitly overrides).
- **Consolidate review output.** Merge all review results into one summary with sections.
- **State before action.** Call `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step <next>` before starting a step, not after. A refused transition is a stop, not something to work around — read the `errors` field and follow the repair path it names (`--reason` for going back or repairing an off-enum step, `--override --reason` for skipping a step forward, `set KEY=VALUE` for a mistyped field, `quarantine` for an unreadable file), never hand-edit the state file to route around a refusal.
- Visual feedback (Step 5.5) is conditional — skipped for non-UI phases or when no design reference exists; it never blocks (remaining diffs surface as informational human-verification items).

## Completion Criteria

- Phase acceptance criteria checked off in dev-guide (Step 8)
- State file `phase_step` set to `done`
- Next phase communicated to user
