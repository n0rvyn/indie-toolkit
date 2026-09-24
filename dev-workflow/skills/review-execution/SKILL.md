---
name: review-execution
description: "The single review dispatcher for this marketplace. Use when the user says 'review execution', 'parallel review', 'deep review', 'review my code', 'review after coding', 'execution review', '审查执行', '并行 review', '写完 review 一下', '代码 review 一下', '深度代码审查', '执行后审查', or wants a fresh-context multi-lens review of uncommitted changes BEFORE commit. Also the callee for run-phase Step 6, execute-plan's standalone finish, and an /afk terminal stop — it routes lenses from the diff's shape, so callers do not each keep their own reviewer list. Dispatches 5 always-on lenses (correctness, test-coverage, breaking-changes, root-cause-depth, secrets-and-transport), adds implementation-reviewer when a plan path is supplied, and adds Apple reviewers by what the diff actually touches. Not when: pre-commit semantic classification only — use review-before-commit (deliberately outside every pipeline, a manual double-check). Not when project is Apple-only and you want only ASC pre-submit review — use /asc-submit-preview. Not when auditing a plugin/skill/agent as an ARTIFACT (trigger quality, dispatch wiring, eval coverage) rather than reviewing a diff — use skill-master:plugin-master; in a plugin monorepo the diff IS plugin content, so say which question you are asking."
user-invocable: true
allowed-tools: Bash(git diff:*, git status:*, git log:*, git ls-files:*, find:*, grep:*, python3:*), Agent, Task, Workflow
---

## Overview

This skill formalizes the "parallel reviewer dispatch" pattern that consistently produces high-quality post-execution reviews (per 2026-04 — 2026-05 insights report). Five always-on reviewer agents run concurrently in fresh contexts, each focused on one lens, plus whatever the diff's shape routes in. The dispatcher consolidates findings, presents to the user, and STOPS before applying any fix.

**Mode:** REVIEW-ONLY. No source files modified. Output is a structured findings list.

## When To Use

- Before commit on non-trivial changes (>50 changed lines, or any deletion, or public-API change)
- Before a PR / merge to main
- After `execute-plan` completes outside of `run-phase` orchestration
- When the user wants a "second opinion" on uncommitted work
- Apple 项目（自动并行 dispatch ui/design/feature/apple reviewers 与 5 个常驻 lens 同批次执行）

## When NOT To Use

- Semantic change classification only (use `review-before-commit` — enhancement / fix / refactor / removal categorization; it sits outside every pipeline on purpose, as a manual pre-commit double-check)
- Mid-execution / mid-plan checkpoints (use the orchestrator's own checkpoint gate)

Plan-vs-code audit is **no longer** a reason to go elsewhere: pass `plan_path` and this skill dispatches `implementation-reviewer` alongside the lenses.

## Inputs (all optional — absent means the standalone path)

| Input | Effect when supplied |
|---|---|
| `plan_path` | Dispatches `dev-workflow:implementation-reviewer` as an additional lens (plan-vs-code audit). **Not** merged into Lens A — "does the code do what the plan said" is a different question from "is the code correct", and collapsing them loses the first. Also pass `design_doc_path` if the caller has one. |
| `design_doc_path` | Passed through to Lens E alongside `plan_path`, for the design-vs-code fidelity half of that audit. Ignored without `plan_path`. |
| `scope_files` | Restricts every lens to these paths instead of the whole working tree. **Callers with a narrower unit than the diff MUST pass this.** `run-phase` reviews one Phase; the working tree can hold unrelated changes, and reviewing them silently widens the caller's contract. |
| `mode` | `gated` (default for `run-phase`): must-fix findings block and go into the caller's fix loop. `advisory` (default when absent, and for `execute-plan` / `/afk`): findings are presented, nothing blocks, the user decides. |

**Why one dispatcher.** Until now `run-phase` kept its own reviewer list and dispatched the same Apple agents by Phase-completion signals while this skill dispatched them by git-diff signals. Running both dispatched the same agents twice with different scopes — documented as intentional in `run-phase`, and it still cost a duplicate. The routing lives here now; callers pass inputs, not agent lists.

> `Agent` and `Task` in `allowed-tools` are **one tool under two names** — `Task` is the historical name, still printed by cached plugin copies. Both are listed on purpose: dropping either risks a runtime that resolves the other losing dispatch silently, with no frontmatter check to catch it.

## Process

### Step 1: Gather Context and Build Args

1. Run: `git status` — confirm uncommitted changes exist. If none, STOP: "无 uncommitted changes — review-execution 无对象。"
2. Run: `git diff --stat` + `git diff --staged --stat` — get scope. **If `scope_files` was supplied, intersect with it and use the intersection everywhere below**; if the intersection is empty, STOP and say so rather than falling back to the whole tree (a silent widening is exactly what passing `scope_files` was meant to prevent).
3. Identify project root.
4. Compute the routing from **what the diff actually touches** with the script, not by running the checks yourself:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/route.py" --root . [--scope-file <path> ...]
   ```

   Pass every `scope_files` entry as `--scope-file`. It prints one JSON object:
   - `stop` present → STOP and say its text (no changes, or the `scope_files` intersection is empty).
   - `apple_project`, `apple_dev_installed` → carry into the args object below verbatim.
   - `flags`: `HAS_VIEW_MODIFIED`, `HAS_NEW_VIEW` (untracked new files count as new), `HAS_APPLE_NONSWIFT`, `HAS_FEATURE_SPEC` — informational; the routing decision that matters is `apple_reviewers`.
   - `apple_reviewers`: the Apple agents to dispatch, each with the files to pass. `apple-dev:feature-reviewer` carries `when`: `always`, or `only if SPANS_LAYERS`. **Pass this array through to `args.apple_reviewers` verbatim — do not recompute or filter it.**

   Each flag exists to give exactly one reviewer something the others cannot see; a flag that fires on everything is not routing. The script's tests (`scripts/test_route.py`) pin these routes.
5. Judge the one flag the script cannot compute: `SPANS_LAYERS` — the diff touches ≥3 of {View, ViewModel/Store/Presenter, Model/Service/Repository}, judged from paths and type names. It only matters for the `feature-reviewer` entry marked `only if SPANS_LAYERS`. Also write down which layers were touched as a short string (e.g. `"View, ViewModel, Model"`) — this becomes `args.layers`, and is what `feature-reviewer`'s prompt sees as "touched layers", since the Workflow script cannot make this judgment itself.

   ⛔ **Do not reintroduce a bare `HAS_SWIFT`.** It fires on pure logic changes, which is how `ui-reviewer` ended up reviewing a state-machine bug — and why, on one measured run, three of seven reviewers returned the same finding. The redundancy was a routing defect, not a sign there were too many lenses.
6. Build the args object:

   ```js
   {
     project_root: "<absolute path>",
     scope_files: [/* the intersection from step 2, or [] for the whole diff */],
     plan_path: "<path>" | null,
     design_doc_path: "<path>" | null,
     mode: "gated" | "advisory",
     apple: true | false,               // route.py's apple_project, as a real boolean — NOT the string "false"
     apple_dev_installed: true | false, // route.py's apple_dev_installed, as a real boolean
     apple_reviewers: [ /* route.py's apple_reviewers array, verbatim — not re-typed, not stringified */ ],
     spans_layers: true | false,        // step 5's SPANS_LAYERS judgment, as a real boolean
     layers: "<step 5's touched-layers string>",
     date: "YYYY-MM-DD"                 // today; the script cannot call Date (the Workflow runtime forbids it)
   }
   ```

   ⛔ **Pass real JSON types, not quoted placeholders — every key above except `layers`, `mode` and `date` is required and typed.** `apple: "false"` is a non-empty string, which is truthy; unchecked it would silently flip the Apple-coverage line and the `feature-reviewer` gate (same failure class as passing the whole `args` payload as a JSON string). The script's entry guard therefore throws before any dispatch unless `apple`, `apple_dev_installed`, `spans_layers` are booleans, `scope_files` is an array of strings, `apple_reviewers` is an array of objects each with a string `agent`, `plan_path` / `design_doc_path` are a string or `null` (not absent), and `date`, if present, is a string. A thrown guard is a Workflow failure — see Step 2.

### Step 2: Dispatch Reviewers via Workflow (Single Parallel Batch)

**Workflow opt-in note:** The Workflow tool requires a sanctioned trigger — a skill whose instructions tell it to call Workflow. This skill IS that sanctioned trigger; calling `Workflow({scriptPath, args})` from this skill is the authorized entry point, not "ultracode".

Invoke the Workflow tool once, passing the args object built in Step 1 as a JSON **object** (not a JSON string):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/skills/review-execution/review.workflow.js",
  args: { ... the Step 1 args object ... }
})
```

The script (`review.workflow.js`) dispatches every applicable reviewer — the 5 always-on lenses (A–D + F), Lens E (`dev-workflow:implementation-reviewer`) when `plan_path` was supplied, and every entry of `args.apple_reviewers` whose `when` gate passes — in ONE parallel batch, each with a StructuredOutput schema whose required fields are that reviewer's contract sections (see `review.workflow.js`'s `CONTRACT` for exactly which fields belong to which reviewer). Await the Workflow call's task notification before reading the return; do not attempt to read it synchronously.

The lens prompt **bodies** (Correctness, Test Coverage, Breaking Changes, Root-Cause Depth, Secrets & Transport) and the Apple-reviewer prompt builders live in the script now, not here — see `review.workflow.js`'s `LENS_A_BODY`…`LENS_F_BODY` and `buildApplePrompt`. Each lens still opens with the scope line (whole-diff or restricted-to-`scope_files`), computed in the script from `args.scope_files`. Named reviewers (implementation-reviewer, all `apple-dev:*`) are dispatched with **no** `model` key, so each agent's own frontmatter model applies; the 5 lenses get `model: opus` (A, D) or `model: sonnet` (B, C, F).

**Always dispatched (5-lens) — what each one checks, not the prompt text itself:**

- **Lens A — Correctness** (`model: opus`): off-by-one, null/undefined access, missing await/error handling, incorrect conditionals, type mismatches that escape the type-checker, missing branches in exhaustive checks. Style/naming/testing are out of scope for this lens.
- **Lens B — Test Coverage** (`model: sonnet`): for each new or modified function/method, is there a test that exercises it, and are edge cases (empty input, error path, boundary) covered. Report-only — does not write tests.
- **Lens C — Breaking Changes** (`model: sonnet`): signature/type/interface changes, public→private markers, config key renames, default-value changes; cross-references callers of any removed/renamed symbol.
- **Lens D — Root-Cause Depth** (`model: opus`): for fix-style changes only, judges surface-level patch vs root cause (hardcoded flag vs config, null-check vs fixing the producer, try/catch swallowing vs fixing the throw, guardrail vs the actual condition). Skips enhancement/refactor/removal changes.
- **Lens F — Secrets & Transport** (`model: sonnet`): hardcoded secrets, insecure transport (`http://`, `NSAllowsArbitraryLoads`, unvalidated `URLSession`), injection-shaped input handling (SQL/`NSPredicate`/`WKWebView` interpolation), sensitive data at rest outside Keychain. Reports nothing for classes with no hit.

  ⛔ **This lens is always-on, not routed.** Every other conditional lens keys off a path pattern (`*View.swift`, `.plist`, …), and a secret does not live at a predictable path — a leaked key lands in whatever file the author was editing. A path-shaped route here would be a route that misses exactly the case it exists for. The cost is bounded: it is a sonnet grep pass over the diff only.

  Provenance: these four checks were `apple-dev:code-audit` Step 2, a `user-invocable: false` skill that nothing dispatched. The other four `code-audit` categories (concurrency, accessibility, performance, SwiftUI anti-patterns) were NOT moved here — `apple-reviewer` and `ui-reviewer` already cover them. See `docs/12-retired/code-audit.md`.

**Lens E — Plan-vs-code** (only when `plan_path` was supplied, dispatched with no `model` key): answers a question no other lens asks — *did the code do what the plan said it would* — not whether the code is correct, which is Lens A's job. Without `plan_path` there is nothing to audit against, so the script skips it silently.

**Apple reviewers — dispatched from `args.apple_reviewers` (route.py's routing, passed through verbatim; the script does not re-check `apple_project`/`apple_dev_installed` with `ls`/`find` — a permission-denied check returns no output, which once read as "not installed" and silently skipped every Apple reviewer):**

- `apple-dev:ui-reviewer` — routed when `HAS_VIEW_MODIFIED` — reviews the modified `*View.swift` files
- `apple-dev:design-reviewer` — routed when `HAS_NEW_VIEW` — reviews the new View files
- `apple-dev:feature-reviewer` — `when: always` (a feature spec exists) or `when: only if SPANS_LAYERS` (Step 1 item 5's judgment) — reviews the spec paths and the touched layers
- `apple-dev:apple-reviewer` — routed when `HAS_APPLE_NONSWIFT` — reviews the non-Swift Apple-surface files

⛔ **`apple-reviewer` is no longer "always when Apple".** "Always" is not a route: on a Swift diff it duplicated `ui-reviewer` outright. Its own charter is the non-Swift Apple surface (.plist, entitlements, Package.swift, asset catalogs, project file) — give it exactly that and the overlap disappears.

⛔ **`feature-reviewer` no longer routes on the user's wording.** Keying a dispatch off phrases in the request means the same diff reviews differently depending on how it was asked for. Route on the diff's shape.

⛔ **Workflow failure = review failure.** If the Workflow call errors, is unavailable, or is refused, STOP and surface the error to the user — never fall back to a direct Agent dispatch of the reviewers (same precedent as `execute-plan/SKILL.md`: a failed entry guard means zero agents ran and there is nothing to reconcile). If the return's `status.ok` is `false` (a dispatched reviewer threw or returned null, or nothing arrived), or the Workflow's task notification reports `agent_count` 0, the review **failed** — it is not clean. `advisory`: present `rendered` (it opens with a `⚠️ Review incomplete` line) and name every `status.errored` entry plainly as a failed review, not as a normal result with a coverage footnote. `gated`: return the whole object as usual; the caller gates on `status.ok` (run-phase Step 6 item 4, `/afk` dev-guide item 6).

If the project is Apple and apple-dev IS installed but no Apple flag fired, the script's `rendered` block still names which flags were checked and came back false — this distinguishes "assessed, nothing applied" from "never looked" without any extra step here. If the project is non-Apple OR apple-dev is not installed, the script's Apple coverage line already says so; do not add anything.

### Step 3: Read the Returned Object

The Workflow call returns `{must_fix, nice_to_have, coverage, passthrough, status, rendered}`:

- `must_fix` / `nice_to_have` — arrays of `{lens, agentType, file, line, text}`, sorted by file then grouped by lens.
- `status` — `{ok, arrived, missing, errored}`, **the success signal**. `ok` is `false` when any dispatched reviewer threw or returned null (a dead schema agent or a user-skip), or when nothing arrived. `arrived` / `missing` name each dispatched reviewer — named reviewers (Lens E, every `apple-dev:*`) by agentType, the same key `passthrough` uses; the five plain lenses by label (`lens:A`…). `errored` is `[{label, agentType, error}]`. A missing reviewer's passthrough entry is absent, but every other reviewer's result still arrived.
- `coverage` — `{lenses: {A,B,C,D,F: count | 'errored'}, lens_e, scope, apple, dispatched, errored, contract_warnings}`. `dispatched` is the label list this run attempted; `errored` is the same failures as `status.errored`, as `"<label>: <msg>"` display strings. An errored Apple reviewer still appears on the `apple` line, marked `(errored)`. `contract_warnings` lists reviewers that arrived in a broken shape: `kind: 'count_mismatch'` (declared N items, field holds a different number of lines — the counts-only shape) or `kind: 'empty'` (a field with no `_count` sibling, e.g. implementation-reviewer's `Tests:` line, came back empty).
- `passthrough` — keyed by `agentType` (e.g. `passthrough['apple-dev:ui-reviewer']`), holding `verdict`, `report_path`, and that reviewer's CONTRACT fields (e.g. `part_c_human_verification`) — findings from named reviewers go into `must_fix`/`nice_to_have`, not into `passthrough`. **This is load-bearing, not padding** — callers read specific fields that only one reviewer produces: `ui-reviewer`'s `part_c_human_verification`, `design-reviewer`'s `part_a_red` and `part_b_device_verification`, `feature-reviewer`'s `part_c_device_verification`, `implementation-reviewer`'s `tests_line`/`decisions_line`/`pre_existing_line`/`gaps_line`. Reading past this object into per-agent report files is the coupling this consolidation exists to remove.
- `rendered` — a markdown string reproducing all of the above (`## Apple-Specific Findings` when applicable, `### Must-fix (N)`, `### Nice-to-have (M)`, `### Coverage notes`, `### Per-reviewer passthrough` with the verbatim original headings) — this is what gets shown to a human; **do not build your own markdown from the fields**, present `rendered` as-is.

**This dispatcher writes no review-report file.** (The reviewer agents still write their own — see their Output Contracts. What changed is that this skill neither writes one nor reads theirs; their findings reach the caller through the return object.)

**Why:** Findings go in the return value and the handoff doc. Writing `.claude/reviews/*.md` was measured at ~6 writes per read-back; the copies that reached a human reached them through the agent's returned text, not the file.

### Step 3b: Hand back according to `mode`

**Both modes carry the ENTIRE returned object** — `must_fix`, `nice_to_have`, `coverage`, `passthrough`, `status`, `rendered`. `mode` decides who acts on it and whether the user is prompted; it does not decide how much of it comes back.

| `mode` | What happens next |
|---|---|
| `gated` | Return the whole object (and `rendered`) to the caller and stop. The caller owns the fix loop; this skill still modifies no source files. |
| `advisory` (default) | Present `rendered` to the user and **stop without blocking**. Say plainly that nothing is being fixed and the decision is the user's. Do not re-dispatch to "confirm" a finding. |

⛔ **Do not hand back must-fix alone under `gated`.** That is the mode `run-phase` uses, and `run-phase` reads `status.ok` as its success signal (its dispatch gate), `status.missing` + `coverage.contract_warnings` for its dispatched-vs-arrived check, plus `passthrough` fields in three separate steps — human-verification items, the `tests_line`, and design-reviewer's `part_a_red` grouping. Trimming the return to must-fix restores, one layer up, exactly the device-verification blindness this consolidation was fixing at the agent layer.

**`advisory` from an `/afk` terminal stop carries one extra obligation: write the handoff.** The user was away; findings presented only in a live turn reach nobody. And the session they would return to is the expensive one — Claude Code's own prompt cache has expired by then, so continuing the old session hours later costs more than a cold start from a handoff doc. Invoke `dev-workflow:handoff` with the findings before ending the turn. ⛔ Do not drop this step as redundant with the on-screen summary; the on-screen summary is what expires.

### Step 4: Present and STOP — `advisory` only

⛔ **Skip this entire step when `mode` is `gated`.** Step 3b already returned the whole object to the caller, and the caller owns the fix loop (`run-phase` asks at its own Step 6; `/afk` dev-guide mode at its per-phase gate). Running Step 4 as well asks the user to pick fixes twice for one review.

Present `rendered` to the user. Add the tail:

```
下一步建议（不会自动执行）：
- 让我 apply 哪些 must-fix？(列编号或 "全部")
- 跳过哪些？说明理由（可选）
- Nice-to-have 是否需要补充任务？
```

STOP. Do not apply any fix. Do not invoke commit. The user must explicitly direct the next action.

## Completion Criteria

- All applicable agents dispatched and returned, or marked errored (5 always-on lenses A–D + F; Lens E when `plan_path` was supplied; each Apple reviewer whose flag fired) — and a run with any errored reviewer is reported as `status.ok: false`, never as clean
- Consolidated findings presented to user
- No source file modified
- No commit made

## Naming Note

This skill is named `review-execution` (full form) intentionally — built-in `review` skill (PR review) already exists in Anthropic's default skill list. Do not abbreviate to `/review`.
