# review-execution Eval

## Trigger Tests

**Should trigger (direct):**
- "review execution" / "深度审查" / "写完 review 一下" / "并行 review"
- "review my code" before a commit on non-trivial changes

**Should trigger (as callee — no user phrase involved):**
- `run-phase` Step 6
- `execute-plan` standalone finish
- `/afk` dev-guide mode's per-phase gate
- an `/afk` terminal stop

**Should NOT trigger:**
- Semantic change classification only (→ `review-before-commit`, which is deliberately outside every pipeline)
- ASC pre-submit compliance only (→ `/asc-submit-preview`)
- No uncommitted changes present (STOP with the "无 uncommitted changes" message)

## Output Assertions

**Inputs:**
- [ ] All three inputs are optional and independently honored: `plan_path`, `scope_files`, `mode`
- [ ] `plan_path` present → dispatches `dev-workflow:implementation-reviewer` as Lens E; absent → skipped silently
- [ ] Lens E is NOT merged into Lens A — "did the code do what the plan said" and "is the code correct" are separate questions and separate agents
- [ ] `scope_files` present → every lens is restricted to the intersection with the diff
- [ ] ⛔ The restriction reaches the lens **prompts** as an explicit scope line, not just Step 1's prose. Grep `review.workflow.js`'s `scopeLineFor()`: a `Restrict every check to these files ONLY` block must be prepended to every lens and Apple-reviewer prompt it builds. Computing an intersection in SKILL.md that never enters `args.scope_files` leaves the subagents running `git diff` on the whole tree while `coverage.scope` reports a narrower scope
- [ ] Intersection empty → **STOP and say so**; does NOT fall back to the whole working tree (a silent widening defeats the input's purpose)
- [ ] `mode` defaults to `advisory` when absent

**Routing — computed from the diff, never from the user's wording:**
- [ ] Step 1 computes the routing by running `scripts/route.py`, not by asking the model to run `find` / `grep` / `ls` checks. Which reviewer fires on which diff (`*View.swift` → ui-reviewer, new View incl. untracked → design-reviewer, .plist/entitlements/xcassets/xcconfig/Package.swift/.pbxproj → apple-reviewer, feature spec → feature-reviewer always, logic-only change → no UI reviewer, apple-dev missing → none, empty scope intersection → stop) is pinned by `scripts/test_route.py`, not here
- [ ] ⛔ No bare `HAS_SWIFT` flag exists anywhere in the file — it fires on pure logic changes, which is how a state-machine bug reached the UI reviewer
- [ ] `feature-reviewer` without a feature spec dispatches only when the model judges `SPANS_LAYERS`, **not** on phrases in the user's message
- [ ] Five base lenses (correctness / test-coverage / breaking-changes / root-cause-depth / secrets-and-transport) always dispatch
- [ ] Lens F (secrets & transport) is always-on and NOT path-routed — a leaked key has no predictable path, so a path-shaped route would miss its own use case
- [ ] All applicable reviewers go out in ONE Workflow call (`review.workflow.js` dispatches them in a single `parallel(...)` batch), never a sequential follow-up
- [ ] apple-dev not installed → all Apple reviewers skipped with an explicit coverage note
- [ ] Apple project + apple-dev installed + no flag fired → still emits the Apple section naming which flags were checked, so "assessed, nothing applied" is distinguishable from "never looked"

**Output contract:**
- [ ] The Workflow return carries `must_fix` / `nice_to_have` / `coverage` as object fields, plus a `rendered` markdown block
- [ ] `coverage` names Lens E's status (`coverage.lens_e`) and the scope actually used (`coverage.scope`)
- [ ] The Workflow return's `passthrough` object reproduces each reviewer's structured sections **verbatim**, keyed by field name — `passthrough['apple-dev:ui-reviewer'].part_c_human_verification`, `passthrough['apple-dev:design-reviewer'].part_a_red` + `.part_b_device_verification`, `passthrough['apple-dev:feature-reviewer'].part_c_device_verification`, `passthrough['dev-workflow:implementation-reviewer'].tests_line`
- [ ] ⛔ Those fields must be **required** in that reviewer's StructuredOutput schema (`review.workflow.js`'s `namedReviewerSchema`, driven by `CONTRACT`), not only present in its `.claude/reviews/*.md` report — a reviewer that leaves one out fails schema validation at the agent, not two hops later at run-phase. A contract that returns only `设备验证项: {N}` makes this passthrough structurally unsatisfiable — which is what it did until 2026-09-04
- [ ] ⛔ Passthrough fields are reproduced, not summarized — callers read them directly (`passthrough[agentType][field]`), and flattening sends the caller back to hunting per-agent report files, which is the coupling this consolidation removed
- [ ] Writes NO `.claude/reviews/*.md` file (measured at ~6 writes per read-back; findings reached humans through returned text, not files)
- [ ] Modifies no source files in any mode
- [ ] A reviewer whose agent dies (schema violation) or returns null (user-skip) appears in `status.errored` and `status.missing` (and in `rendered`'s "Any agent that errored" line) — never silently absent; every other reviewer's result still arrives
- [ ] The return carries an explicit `status: {ok, arrived, missing, errored}`; `status.ok` is `false` when any dispatched reviewer errored/returned null or nothing arrived. An errored lens reads `errored` in `coverage.lenses` and renders `Lens X (...): errored — <msg>`, never `returned: 0 findings`
- [ ] If the Workflow call errors, is unavailable, or is refused, the skill STOPs and surfaces the error — it never falls back to a direct Agent dispatch of the reviewers
- [ ] ⛔ "Workflow failure = review failure" fires on `status.ok === false` (plus `agent_count` 0 from the task notification) — not on "`coverage.dispatched` shorter than the routed set", which can never fire because the script builds `dispatched` from the very list it routed. Under `advisory` a failed review is presented plainly as failed, not as a normal result with a footnote

**Mode behavior:**
- [ ] `gated` → returns the WHOLE object (`must_fix`, `nice_to_have`, `coverage`, `passthrough`, `status`, `rendered`) to the caller for its fix loop; still fixes nothing itself
- [ ] ⛔ `gated` does NOT trim the return to must-fix. `run-phase` runs in this mode and reads `status.ok` as its dispatch-gate signal and `passthrough` fields in three separate steps — a trimmed return re-creates the device-verification blindness one layer above the agents
- [ ] `gated` → Step 4 is SKIPPED entirely; the user is asked which fixes to apply by the caller, once, not by both
- [ ] `advisory` → presents and stops; states plainly that nothing is being fixed; does not re-dispatch to "confirm" a finding
- [ ] `advisory` from an `/afk` terminal stop → findings also go into `dev-workflow:handoff` before the turn ends. ⛔ On-screen only is a failure: the user was away, and the prompt cache has expired by the time they return, so the old session costs more to resume than a cold start from the doc

**Caller closure (these live in other files but break if this contract changes):**
- [ ] `run-phase` Step 6 makes one call and keeps no reviewer list
- [ ] `execute-plan` finish **invokes** rather than suggests
- [ ] `/afk` dev-guide mode's per-phase gate calls it rather than naming agents
- [ ] `/afk` terminal calls it without `plan_path`
- [ ] No caller dispatches `implementation-reviewer` or an apple-dev reviewer directly. Verify with: `python3 .claude/skills/call-graph/scripts/call_graph.py --plugin dev-workflow`

## Redundancy Risk

Baseline: without a dispatcher, each caller kept its own reviewer list. `run-phase` and this skill dispatched the same apple-dev agents by different signals — documented as intentional, and it still meant a duplicate dispatch with mismatched scopes whenever both ran. Consolidation removes that by construction rather than by discipline.

The dimensions themselves are not redundant: on the one fully measured 7-reviewer run, the three real defects came from three different lenses (a state flag never reset → correctness; a core state machine with zero unit coverage → test-coverage; a refactor leaving background sampling alive → breaking-change). Three of seven reviewers did converge on one finding, but that was a routing defect — reviewers dispatched onto code outside their lens — not evidence of too many lenses. Collapsing dimensions would have removed two real findings to fix a routing bug.

Last tested model: —
Last tested date: —
Verdict: pending first real run under the new contract
