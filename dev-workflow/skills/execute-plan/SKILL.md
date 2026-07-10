---
name: execute-plan
description: "Use when the user says 'execute the plan', 'run the plan', 'implement the plan', '执行计划', '跑计划', or has a verified plan file ready for execution. Executes plan tasks in segments via the Workflow tool, with explicit hard-stop checkpoint gates (batch 1 always; any batch with a dependency hub; any batch with an explicit `<!-- checkpoint -->` marker) — at each hard-stop the skill presents the segment summary and waits for the user to say 'continue'. Cross-session resume is authoritative via the on-disk checkpoint file `.claude/execute-plan-checkpoint.json` (`completed` map). Reports blocked/failed tasks for the user to fix — does not attempt fixes itself. Not when: plan has not been verified (run verify-plan first). Also invoked by run-phase at Step 4."
model: sonnet
---

## Overview

This skill orchestrates plan execution in three layers:

1. **Main agent (this skill)** — owns ALL bookkeeping file I/O: parse plan, run `compute_checkpoints.py`, and is the **SOLE writer of BOTH** the checkpoint file (`completed` map + segment metadata) **and** `execution-report.md`, written per-segment from the Workflow's schema-validated results array. Owns ALL user gating at hard-stops. Invokes the Workflow tool **once per segment**.

2. **Workflow script** (`${CLAUDE_PLUGIN_ROOT}/skills/execute-plan/execute-plan.workflow.js`) — owns the deterministic per-segment loop. Receives a segment payload via `args`, dispatches one `agent()` per task with `model:'sonnet'` and the `{task_id, status, files_written, evidence}` schema, honors dependency-skip, returns the per-task results array. Has no filesystem access; cannot pause for user input. **One Workflow invocation = one segment** (a segment runs from the current position up to and including the next hard-stop batch, or the end).

3. **Task-executor agent** (`dev-workflow:execute-plan`, model=sonnet) — invoked by the Workflow script for each task. Makes the task's code/file changes, runs its `**Verify:**`, and returns the structured `{task_id, status, files_written, evidence}` result. **Writes NO bookkeeping files** — not the checkpoint, not the report. (This is the single-writer model: delegating mutation of the shared resume-critical JSON to per-task agents produced inconsistent shapes, so the main agent records everything from the reliable schema-validated return.)

**A hard-stop is a natural Workflow return point** — the script returns at the end of a hard-stop batch, the main agent presents the segment summary, and waits for "continue" before invoking the next segment.

**Workflow opt-in note:** The Workflow tool requires a sanctioned trigger — a skill whose instructions tell it to call Workflow. This skill IS that sanctioned trigger; calling `Workflow({scriptPath, args})` from this skill is the authorized entry point, not "ultracode".

**Cross-session resume:** `Workflow({resumeFromRunId})` is **same-session only**. The on-disk `.claude/execute-plan-checkpoint.json` is the **sole cross-session source of truth**. `resumeFromRunId` is treated as a same-session cache optimization; if it disagrees with the checkpoint's `completed` map, the checkpoint wins. Only ids absent from `completed` are passed to the workflow.

The plan's final verification task is no longer required — full test suite execution is handled separately by `dev-workflow:test-changes`.

## Process

### Step 1: Pre-checks

1. Read the plan file
2. **Verification pre-check**: Look for a `## Verification` section with `Verdict: Approved` in the plan file
   - If found: verification is done, continue
   - If not found: invoke `dev-workflow:verify-plan` before proceeding. If verify-plan returns "must-revise", apply revisions and re-verify before continuing
3. **Task Contract pre-check**:
   - If plan frontmatter has `contract_version: 1` or later, every task in the execution range must include `**Task Contract:**`.
   - If any selected task lacks `Task Contract`, collect its id into a `contract_failed` list (do NOT write the checkpoint here — it does not exist until Step 2.3). These ids are recorded as `failed` during the post-segment reconciliation (Step 2.4, "Reconcile") once the file exists, and are passed in `failed_or_blocked` so their dependents are skipped. Never dispatch a contract-failed task.
   - If `contract_version` is missing, treat the plan as legacy mode: warn once in the execution report and continue.
<!-- Inline short-form DP handling. Full ruleset at ${CLAUDE_PLUGIN_ROOT}/references/decision-points.md §"Note on inline variant" — sync on rule changes. -->
4. **Decision Points:** If the plan file contains a `## Decisions` section with unresolved decisions (no `**Chosen:**` line), present them before dispatching:
   - For each DP, write a short-form translation in the `question` field: one-line summary of what the decision controls + each option prefixed with its original `A:` / `B:` / `C:` label describing what concretely happens. Do NOT paste the full DP block (Context / Options / Recommendation headings) verbatim. The plan file's DP body stays unchanged.
   - For each `blocking` decision: present via AskUserQuestion (one call per DP).
   - For `recommended` decisions: batch via a single AskUserQuestion; all content inside the `question` field, DPs separated by `\n---\n`, ending with `\n\n全部接受推荐，还是逐个审查？`.
   - If the user does NOT choose to accept all: present each DP individually via separate AskUserQuestion calls. Do not assume any DP is accepted until the user explicitly confirms it.
   - Record user choices: edit the plan file, replace `**Recommendation:**` or `**Recommendation (unverified):**` with `**Chosen:** {Option A | B | C}` using the original label.

### Behavior Note: Plan-time test-impl split pattern

Some plans contain task pairs like `Task N-tests` and `Task N-impl` — a single conceptual unit split across two tasks. The pair is treated as a single unit for batch grouping by `compute_checkpoints.py` (pair-keep rule: a batch may run one over `batch_size` to keep a `-tests`/`-impl` pair intact, so no batch boundary — and therefore no hard-stop — lands mid-pair). Each pair member is dispatched to the task-executor agent as a normal sequential task; the second agent reads the now-committed test files as input and is constrained by `Task N-impl`'s `Regression shield:` to not modify them.

If you encounter a single task whose Files list includes BOTH test and non-test files (i.e., the plan was hand-written without the split), execute it as-is — do not attempt to split at dispatch time (that would require agent contract changes not implemented in this codebase).

### Step 2: Initialize and Dispatch (segmented)

1. Read the plan file and count total tasks (count `### Task N:` / `### Task N-tests:` / `### Task N-impl:` headings; canonical ids are `"<N>"` / `"<N>-tests"` / `"<N>-impl"`).
2. Run `compute_checkpoints.py` against the plan file to obtain the batch plan:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/execute-plan/scripts/compute_checkpoints.py <plan_file> --k 3 --batch-size 5
   ```
   Parse the JSON output: `{batch_size, total, batches, dependents, hard_stops, tasks}`. The `tasks` array is `[{id, depends_on}]` — the per-task dependency edges the workflow needs for dependency-skip. (Forward it in the args payload; do NOT re-derive deps from the plan by hand.) Note: `depends_on` captures one `**Depends on:**` ref per task (the canonical plan form), not multiple.
3. **Initialize / resume checkpoint file** at `.claude/execute-plan-checkpoint.json`:
   - If exists and `status` is `in_progress`: resume — read `completed` map; only ids NOT in `completed` with status `done` are pending.
     - **Plan-edit reconciliation** (always run on resume): if `actual_total != state.total`: update `state.total = actual_total` and surface "ℹ️ Plan now has {N} tasks (was {M}); resuming with updated total."
   - If exists and `status` is `complete`: skip execution, proceed to Step 3.
   - If does not exist: create with initial state:
     ```json
     {
       "plan_file": "<plan file path>",
       "total": <N>,
       "batch_size": <from compute_checkpoints.py>,
       "k": <from compute_checkpoints.py>,
       "hard_stops": [<from compute_checkpoints.py>],
       "completed": {},
       "status": "in_progress"
     }
     ```
   **Writer discipline (single-writer model):** The **main agent is the SOLE writer** of the checkpoint file (both `completed` and segment metadata) AND `execution-report.md`. The task-executor agents write neither — they only make code changes and return the schema-validated `{task_id, status, files_written, evidence}` result. After each Workflow segment returns, the main agent records `completed` + the report from that results array (Step 2.4 Record). Rationale: per-task agents mutating the shared resume-critical JSON produced inconsistent shapes (a list instead of an `{id:status}` map, losing the failed status); the schema-validated return is the only reliable structured source, so all bookkeeping flows from it.

4. **Segment loop** — repeat until no **pending** tasks remain. **Pending = ids absent from `completed`.** Once an id is in `completed` with ANY status (`done`/`failed`/`blocked`) it is **terminal for this run** and is never re-dispatched — a failed task is surfaced for the fix pass, not retried in the same loop (that would just fail again). The loop exits when every id is in `completed`.
   a. **Build the next segment.** Take the pending ids (absent from `completed`), group them into the batches from `compute_checkpoints.py`'s output, and slice up to and including the **next hard-stop batch** (or the last batch if no more hard-stops). The first batch in a segment is always a hard-stop (batch 0), so the first segment always ends at the first batch. Drop any `contract_failed` ids from the dispatch set (they are recorded as failed in Reconcile, not run).
   b. **Invoke the Workflow tool** with the segment payload:
      ```
      Workflow({
        scriptPath: "${CLAUDE_PLUGIN_ROOT}/skills/execute-plan/execute-plan.workflow.js",
        args: {
          plan_file: <plan file path>,
          checkpoint_file: ".claude/execute-plan-checkpoint.json",
          project_root: <project root>,
          tasks: <the `tasks` array from compute_checkpoints.py — [{id, depends_on}]>,
          batches: <sliced segment batches>,
          failed_or_blocked: <ids already in `completed` as failed/blocked, PLUS contract_failed ids>,
        }
      })
      ```
      `args` MUST be a JSON **object**, not a JSON string. The Workflow tool passes `args` through verbatim, so a stringified payload used to reach the script as a string, make every `args.x` read `undefined`, and return `[]` in ~50ms having dispatched nothing — a silent no-op that looks like success. The script now normalizes at entry: a stringified payload that parses to a valid object is parsed and run (emitting a `log` warning). Anything that cannot drive the batch loop throws with a diagnostic message — an unparseable string, a payload that parses to a non-object (scalar, array, `null`), or an object with no `batches` array. Pass an object anyway — the recovery is a net, not a license.

      Await the Workflow call's completion and read its returned results array. (`failed_or_blocked` seeds the workflow's in-run dependency tracker so a dependency that failed in an EARLIER segment, or pre-flight, still blocks its dependents here.)

      **Sanity check the return:** if the results array is empty but you dispatched a non-empty segment, the segment did NOT run. Do not record it as complete — investigate before proceeding. (One legitimate exception: a segment whose ids were ALL dropped as `contract_failed` dispatches nothing and correctly returns `[]`; those ids are recorded as failed in Reconcile, not run. An all-dependency-blocked segment is NOT an exception — it returns non-empty `blocked` entries.)

      **If the Workflow call itself errors or throws** (no results array comes back), the script's entry guard rejected the payload **before any task was dispatched** — zero tasks ran and zero state changed. Fix the args shape and re-invoke; there is nothing to reconcile. Do NOT record the segment, and do NOT emit `Execution complete:` — surface the error to the user.
   c. **Spot-check claimed files.** For each result, verify every path in `files_written` exists on disk. (The dev-workflow `verify-agent-output.py` hook surfaces mismatches at agent return time, but spot-check here is a defense-in-depth.)
   d. **Record `completed` from the return array (authoritative).** For **every** result in the returned array, write `completed[task_id] = {status, files_written, evidence}` to the checkpoint. Also write any `contract_failed` ids as `{status:"failed", evidence:"missing Task Contract"}`. This is the single source of `completed` — the agents wrote nothing, so the array is authoritative and the `{id:status}` shape is guaranteed. (If a resumed checkpoint's `completed` is ever a malformed shape from an older run, normalize it to the `{id:{status}}` map here.)
   e. **Write `execution-report.md` from the return array.** If the report doesn't exist or lacks a section for this plan, create it with the header (`## Execution Report` / `**Plan:** <path>` / `**Status:** in-progress` / `**Tasks:** …` / `### Task Results`). Append one row per result (`- Task {id}: {title} ✅/❌/⏭️ — {evidence}`) and update this plan's header counters (completed/blocked/failed). All scoped to THIS plan's section (the report is a shared append-log).
   f. **Hard-stop gate** — if the segment ended on a hard-stop batch AND there are still pending tasks: present the segment summary + verification, then **STOP and wait for the user to say "continue"** before invoking the next segment. A hard-stop is NOT completion; do NOT emit the "execution complete" signal here.
   g. If no pending tasks remain (every id in `completed`): exit the segment loop and proceed to Terminal-write.

5. **Terminal-write (the completion signal — fixes the run-phase handshake).** When the loop exits with every id in `completed`:
   a. Compute terminal status: `complete` if every `completed[id].status == "done"`, else `completed_with_failures`.
   b. Write the checkpoint `status: "<terminal>"` FIRST.
   c. Flip `execution-report.md`'s `**Status:** in-progress` → `**Status:** <terminal>` — **scoped to THIS plan's section** (locate the `**Plan:** <this plan path>` heading and flip the Status line under it; `execution-report.md` is a shared append-log with one Status line per plan, so never do a global replace).
   d. **Cleanup:** if terminal is `complete`, delete `.claude/execute-plan-checkpoint.json`. If `completed_with_failures`, KEEP it — it is the cross-session source for the fix pass and for re-running failed tasks. Delete only AFTER the terminal signal is written (b+c), never as the success-detection mechanism itself.
   e. The skill's explicit return is the **primary** completion signal (run-phase reads it in-context); the report `**Status:**` line is the **durable cross-session backup**. Resume (Step 2.3, `status: complete` → skip) relies on the backup.

   **Retrying a failed task across sessions:** because pending = "absent from `completed`", a `failed`/`blocked` task is NOT re-run on resume. To retry one after fixing it, the fixer (run-phase Step 7 / standalone Step 3) must **clear that id's `completed` entry** (or delete the whole checkpoint) — otherwise the loop sees it terminal and exits without retrying.

### Step 3: Process Results

When execution completes (all tasks have a `completed` entry):

1. Read the report file at `docs/06-plans/execution-report.md`
   - If the agent's return message contains `Report written to:`, use that path
   - If the file does not exist: fall back to parsing the agent's return message
2. Present summary to the user: completed/blocked/failed counts
3. If blocked or failed tasks exist: list them with reasons

**Standalone mode** (not within run-phase):
- If failures: fix in main context (opus)
- Suggest `dev-workflow:test-changes` to run the full test suite
- Suggest `dev-workflow:implementation-reviewer` for plan-vs-code audit
- Suggest `dev-workflow:finish-branch` for branch integration

## State Integration

When running within a phase orchestrated by `run-phase`:

If `.claude/dev-workflow-state.json` exists and `phase_step` is `execute`:
- After the Terminal-write step (every id in `completed`, terminal status written), return an **explicit completion signal** to run-phase: `Execution complete: <complete | completed_with_failures>` with the report path. `phase_step` is owned by the orchestrator (do NOT mutate it from this skill). run-phase reads this return **in-context** (it is the same main agent) — this is the primary signal; the report `**Status:**` line is the durable backup. Do NOT rely on the checkpoint `status` for the run-phase handshake — on `complete` the checkpoint is deleted.
- A hard-stop pause is NOT completion: return `Paused at hard-stop: waiting for "continue"` instead, and do NOT emit the completion signal. run-phase must not advance to Step 5 on a pause return.

## Completion Criteria

- All plan tasks have a `completed` entry in `.claude/execute-plan-checkpoint.json`
- Execution report reviewed and presented to user
- State file cleaned up (deleted) if all `completed` entries are `done`; otherwise retained with `status: "completed_with_failures"`
- When in run-phase context: handoff signal output (only after full completion, never at a hard-stop pause)
- When standalone: wrap-up suggestions presented
