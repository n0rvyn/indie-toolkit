# review-execution Eval

## Trigger Tests

**Should trigger (direct):**
- "review execution" / "深度审查" / "写完 review 一下" / "并行 review"
- "review my code" before a commit on non-trivial changes

**Should trigger (as callee — no user phrase involved):**
- `run-phase` Step 6
- `execute-plan` standalone finish
- `self-pacing` per-unit quality gate
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
- [ ] ⛔ The restriction reaches the lens **prompts** as an explicit scope line, not just Step 1's prose. Grep Step 2: a `Restrict every check to these files ONLY` block must precede the lens templates. Computing an intersection that never enters the prompt leaves the subagents running `git diff` on the whole tree while the Coverage note reports a narrower scope
- [ ] Intersection empty → **STOP and say so**; does NOT fall back to the whole working tree (a silent widening defeats the input's purpose)
- [ ] `mode` defaults to `advisory` when absent

**Routing — computed from the diff, never from the user's wording:**
- [ ] `ui-reviewer` fires on `HAS_VIEW_MODIFIED` (`*View.swift` in the diff), **not** on any `.swift`
- [ ] ⛔ No bare `HAS_SWIFT` flag exists anywhere in the file — it fires on pure logic changes, which is how a state-machine bug reached the UI reviewer
- [ ] `apple-reviewer` fires on `HAS_APPLE_NONSWIFT` (.plist / entitlements / xcassets / xcconfig / Package.swift / .pbxproj), **not** on "project is Apple" — "always" is not a route
- [ ] `feature-reviewer` fires on `HAS_FEATURE_SPEC` or `SPANS_LAYERS`, **not** on phrases in the user's message
- [ ] `design-reviewer` fires on `HAS_NEW_VIEW`
- [ ] `HAS_FEATURE_SPEC` and the apple-dev availability probe use `find`, never `ls` — `ls` is absent from `allowed-tools`, and its permission denial is indistinguishable from "not found"
- [ ] Five base lenses (correctness / test-coverage / breaking-changes / root-cause-depth / secrets-and-transport) always dispatch
- [ ] Lens F (secrets & transport) is always-on and NOT path-routed — a leaked key has no predictable path, so a path-shaped route would miss its own use case
- [ ] All applicable reviewers go out in ONE Agent batch, never a sequential follow-up
- [ ] apple-dev not installed → all Apple reviewers skipped with an explicit coverage note
- [ ] Apple project + apple-dev installed + no flag fired → still emits the Apple section naming which flags were checked, so "assessed, nothing applied" is distinguishable from "never looked"

**Output contract:**
- [ ] Returns must-fix / nice-to-have / coverage notes
- [ ] Coverage notes name Lens E's status and the scope actually used
- [ ] Emits `### Per-reviewer passthrough` reproducing each reviewer's structured sections **verbatim** — `ui-reviewer` `### Part C: 人工验证清单`, `design-reviewer` `### Part A 🔴 项` + `### Part B: 设备验证清单`, `feature-reviewer` `### Part C: 设备验证清单`, `implementation-reviewer` `Tests:` line
- [ ] ⛔ Those sections must be present in each agent's **return value**, not only in its `.claude/reviews/*.md` report. Verify at the source: each of the three apple-dev reviewers' Output Contract step 4 reproduces the list INLINE. A contract that returns only `设备验证项: {N}` makes this passthrough structurally unsatisfiable — which is what it did until 2026-09-04
- [ ] ⛔ Passthrough sections are reproduced, not summarized — callers parse them, and flattening sends the caller back to hunting per-agent report files, which is the coupling this consolidation removed
- [ ] Writes NO `.claude/reviews/*.md` file (measured at ~6 writes per read-back; findings reached humans through returned text, not files)
- [ ] Modifies no source files in any mode

**Mode behavior:**
- [ ] `gated` → returns the WHOLE Step 3 block (must-fix + nice-to-have + `### Coverage notes` + `### Per-reviewer passthrough`) to the caller for its fix loop; still fixes nothing itself
- [ ] ⛔ `gated` does NOT trim the return to must-fix. `run-phase` runs in this mode and reads Coverage notes as its dispatch-gate signal and the passthrough in three separate steps — a trimmed return re-creates the device-verification blindness one layer above the agents
- [ ] `gated` → Step 4 is SKIPPED entirely; the user is asked which fixes to apply by the caller, once, not by both
- [ ] `advisory` → presents and stops; states plainly that nothing is being fixed; does not re-dispatch to "confirm" a finding
- [ ] `advisory` from an `/afk` terminal stop → findings also go into `dev-workflow:handoff` before the turn ends. ⛔ On-screen only is a failure: the user was away, and the prompt cache has expired by the time they return, so the old session costs more to resume than a cold start from the doc

**Caller closure (these live in other files but break if this contract changes):**
- [ ] `run-phase` Step 6 makes one call and keeps no reviewer list
- [ ] `execute-plan` finish **invokes** rather than suggests
- [ ] `self-pacing` per-unit gate calls it rather than naming agents
- [ ] `/afk` terminal calls it without `plan_path`
- [ ] No caller dispatches `implementation-reviewer` or an apple-dev reviewer directly. Verify with: `python3 .claude/skills/call-graph/scripts/call_graph.py --plugin dev-workflow`

## Redundancy Risk

Baseline: without a dispatcher, each caller kept its own reviewer list. `run-phase` and this skill dispatched the same apple-dev agents by different signals — documented as intentional, and it still meant a duplicate dispatch with mismatched scopes whenever both ran. Consolidation removes that by construction rather than by discipline.

The dimensions themselves are not redundant: on the one fully measured 7-reviewer run, the three real defects came from three different lenses (a state flag never reset → correctness; a core state machine with zero unit coverage → test-coverage; a refactor leaving background sampling alive → breaking-change). Three of seven reviewers did converge on one finding, but that was a routing defect — reviewers dispatched onto code outside their lens — not evidence of too many lenses. Collapsing dimensions would have removed two real findings to fix a routing bug.

Last tested model: —
Last tested date: —
Verdict: pending first real run under the new contract
