export const meta = {
  name: 'execute-plan',
  description: 'Execute one segment of an execute-plan: dispatch one agent() per not-yet-completed task (model=sonnet) with a structured-output schema, honor dependency-skip, return the per-task results array. Segments end at hard-stop batches; the main agent invokes this script once per segment and presents the summary at hard-stops.',
  phases: [
    { title: 'Execute Segment', detail: "Iterate the segment's batches, dispatch one agent() per not-yet-done task, collect structured results." },
  ],
}

// Runtime characteristics (observed from the live Workflow runtime, not assumed):
//   * This script has NO filesystem access and NO Node.js built-ins. The only
//     way to read project files is to dispatch an agent() that does the read.
//   * This script CANNOT pause for user input. Hard-stops are handled by the
//     main agent returning between segments (one Workflow invocation = one
//     segment, not a full run).
//   * `resumeFromRunId` is same-session only. Cross-session resume is
//     authoritative via the disk-based checkpoint file
//     `.claude/execute-plan-checkpoint.json` (read by the main agent, NOT here).
//   * This script can only be integration-tested through the Workflow runtime —
//     `node --check` validates syntax only.

// Schema for each task's structured return. The dispatched agent must echo
// `task_id` verbatim (Architecture invariant 1 — no reformatting).
const RESULT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['task_id', 'status', 'files_written', 'evidence'],
  properties: {
    task_id: {
      type: 'string',
      description: 'Canonical task id echoed verbatim from input: "<N>" / "<N>-tests" / "<N>-impl".',
    },
    status: {
      type: 'string',
      enum: ['done', 'failed', 'blocked'],
      description: 'done = task complete and verified; failed = task attempted but verify failed; blocked = a dependency failed/blocked so this task was skipped.',
    },
    files_written: {
      type: 'array',
      items: { type: 'string' },
      description: 'Absolute paths of files this task created or modified (empty array if none).',
    },
    evidence: {
      type: 'string',
      description: 'One-line summary of the verify outcome (e.g. "exit=0, all 11 tests pass").',
    },
  },
}

// Established before the guard below so `log()` and any throw always run inside
// a phase, whatever the runtime's rule about phase-less output is.
phase('Execute Segment')

// The Workflow tool passes `args` through verbatim. A caller that JSON-stringifies
// the payload therefore hands this script a string, every `args.x` deref yields
// undefined, the loop runs zero times, and the segment "succeeds" with `[]` —
// no agents, no journal, no code written. Normalize, then reject any shape that
// cannot produce a batch loop. `batches` is the load-bearing field: a segment
// whose tasks are all dependency-blocked still has an array here (and correctly
// dispatches zero agents), so key the guard on shape, never on dispatch count.
//
// Every throw here fires before the first agent() dispatch, so a failed guard
// means zero tasks ran and zero state changed — the caller can fix the payload
// and re-invoke with nothing to reconcile.
let input = args
if (typeof input === 'string') {
  try {
    input = JSON.parse(input)
  } catch (err) {
    throw new Error(
      `execute-plan: args arrived as a string and is not valid JSON (${err.message}). ` +
      `Pass the segment payload as a JSON object, not a stringified one.`
    )
  }
  log('args arrived as a JSON string; parsed it. Callers should pass an object.')
}
if (!input || typeof input !== 'object' || Array.isArray(input)) {
  throw new Error(
    `execute-plan: args must be a JSON object (got ${input === null ? 'null' : Array.isArray(input) ? 'array' : typeof input}). ` +
    `Pass the segment payload as a JSON object, not a stringified one.`
  )
}
if (!Array.isArray(input.batches)) {
  throw new Error(
    `execute-plan: args.batches must be an array (got ${typeof input.batches}; ` +
    `payload keys: ${Object.keys(input).join(', ') || 'none'}).`
  )
}

// `input` is the segment payload passed from the main agent:
//   {
//     plan_file: string,
//     checkpoint_file: string,
//     project_root: string,
//     tasks: [{id, depends_on}, ...],   // ALL remaining tasks (with their depends_on ids)
//     batches: [[id, id, ...], ...],    // batches in order, sliced up to and including the next hard-stop
//     failed_or_blocked: [id, ...],     // ids already terminal-failed/blocked in `completed`
//                                       // (earlier segments + pre-flight contract failures) so a
//                                       // dependent in THIS segment is skipped even though its
//                                       // dependency ran in a prior Workflow invocation.
//   }
//
// In-run dependency tracking — record the final status of each dispatched task
// in this invocation so we can skip tasks whose dependency failed/blocked.
// Seed with cross-segment failures the main agent already knows about, so a
// dependency that failed in an EARLIER segment still blocks its dependents here
// (inRunStatus would otherwise be empty at the start of each invocation).
const inRunStatus = {} // taskId -> 'done' | 'failed' | 'blocked'
for (const id of (input.failed_or_blocked || [])) {
  inRunStatus[id] = 'failed'
}
const results = []

// Build a taskId -> {id, depends_on[]} lookup from input.tasks for the IDs we
// might dispatch in this segment.
const taskMeta = {}
for (const t of (input.tasks || [])) {
  taskMeta[t.id] = t
}

for (const batch of (input.batches || [])) {
  for (const taskId of batch) {
    const meta = taskMeta[taskId]
    const deps = (meta && meta.depends_on) || []

    // Dependency-skip: if any of this task's dependencies failed or blocked
    // in this run, mark this one blocked and continue (do not dispatch).
    const blockedBy = deps.find(depId => {
      const s = inRunStatus[depId]
      return s === 'failed' || s === 'blocked'
    })
    if (blockedBy) {
      inRunStatus[taskId] = 'blocked'
      // We still want a structured entry for aggregation, but we cannot return
      // a full RESULT_SCHEMA here because we never dispatched the agent. Return
      // a minimal placeholder matching the schema — the main agent will see
      // status='blocked' and report it.
      results.push({
        task_id: taskId,
        status: 'blocked',
        files_written: [],
        evidence: `skipped: dependency ${blockedBy} failed or blocked in this run`,
      })
      continue
    }

    // Dispatch the task-executor agent for this single task.
    const prompt = [
      `Execute task ${taskId} of the implementation plan.`,
      ``,
      `Plan file: ${input.plan_file}`,
      `Project root: ${input.project_root}`,
      `Checkpoint file: ${input.checkpoint_file}`,
      ``,
      `Workflow context: you are being dispatched by execute-plan.workflow.js for one task of a segment.`,
      `Process: read the task, make its code/file changes, run its **Verify:**.`,
      `Do NOT write the execution report or the checkpoint file — the main agent records both from your return.`,
      `Return a structured object matching: {task_id, status: "done"|"failed"|"blocked", files_written, evidence}.`,
      `Echo task_id verbatim (do not reformat). Put the verify outcome (and any blocker/evidence) in the evidence field.`,
    ].join('\n')

    let result
    try {
      result = await agent(prompt, {
        label: `task:${taskId}`,
        phase: 'Execute Segment',
        model: 'sonnet',
        agentType: 'dev-workflow:execute-plan',
        schema: RESULT_SCHEMA,
      })
    } catch (err) {
      // Dispatch error — treat as failed and continue to the next task in
      // this segment (do not abort the whole segment for one bad dispatch).
      inRunStatus[taskId] = 'failed'
      results.push({
        task_id: taskId,
        status: 'failed',
        files_written: [],
        evidence: `agent dispatch error: ${err && err.message ? err.message : String(err)}`,
      })
      continue
    }

    // Schema sanity guard — if the agent returned something malformed, treat
    // as failed (the main agent will see the evidence and surface it).
    if (!result || typeof result !== 'object' || !result.task_id) {
      inRunStatus[taskId] = 'failed'
      results.push({
        task_id: taskId,
        status: 'failed',
        files_written: [],
        evidence: 'agent returned no structured result (schema mismatch)',
      })
      continue
    }

    const status = result.status || 'failed'
    inRunStatus[taskId] = status
    results.push({
      task_id: result.task_id,
      status,
      files_written: Array.isArray(result.files_written) ? result.files_written : [],
      evidence: result.evidence || '',
    })
  }
}

return results
