---
name: review-execution
description: "The single review dispatcher for this marketplace. Use when the user says 'review execution', 'parallel review', 'deep review', 'review my code', 'review after coding', 'execution review', '审查执行', '并行 review', '写完 review 一下', '代码 review 一下', '深度审查', '执行后审查', or wants a fresh-context multi-lens review of uncommitted changes BEFORE commit. Also the callee for run-phase Step 6, execute-plan's standalone finish, and an /afk terminal stop — it routes lenses from the diff's shape, so callers do not each keep their own reviewer list. Dispatches 5 always-on lenses (correctness, test-coverage, breaking-changes, root-cause-depth, secrets-and-transport), adds implementation-reviewer when a plan path is supplied, and adds Apple reviewers by what the diff actually touches. Not when: pre-commit semantic classification only — use review-before-commit (deliberately outside every pipeline, a manual double-check). Not when project is Apple-only and you want only ASC pre-submit review — use /asc-submit-preview."
user-invocable: true
allowed-tools: Bash(git diff:*, git status:*, git log:*, git ls-files:*, find:*, grep:*), Agent, Task
---

## Overview

This skill formalizes the "parallel reviewer dispatch" pattern that consistently produces high-quality post-execution reviews (per 2026-04 — 2026-05 insights report). Five always-on reviewer agents run concurrently in fresh contexts, each focused on one lens, plus whatever the diff's shape routes in. The dispatcher consolidates findings, presents to the user, and STOPS before applying any fix.

**Mode:** REVIEW-ONLY. No source files modified. Output is a structured findings list.

## When To Use

- Before commit on non-trivial changes (>50 changed lines, or any deletion, or public-API change)
- Before a PR / merge to main
- After `execute-plan` completes outside of `run-phase` orchestration
- When the user wants a "second opinion" on uncommitted work
- Apple 项目（自动并行 dispatch ui/design/feature/apple reviewers 与 4-lens 同批次执行）

## When NOT To Use

- Semantic change classification only (use `review-before-commit` — enhancement / fix / refactor / removal categorization; it sits outside every pipeline on purpose, as a manual pre-commit double-check)
- Mid-execution / mid-plan checkpoints (use the orchestrator's own checkpoint gate)

Plan-vs-code audit is **no longer** a reason to go elsewhere: pass `plan_path` and this skill dispatches `implementation-reviewer` alongside the lenses.

## Inputs (all optional — absent means the standalone path)

| Input | Effect when supplied |
|---|---|
| `plan_path` | Dispatches `dev-workflow:implementation-reviewer` as an additional lens (plan-vs-code audit). **Not** merged into Lens A — "does the code do what the plan said" is a different question from "is the code correct", and collapsing them loses the first. Also pass `design_doc_path` if the caller has one. |
| `scope_files` | Restricts every lens to these paths instead of the whole working tree. **Callers with a narrower unit than the diff MUST pass this.** `run-phase` reviews one Phase; the working tree can hold unrelated changes, and reviewing them silently widens the caller's contract. |
| `mode` | `gated` (default for `run-phase`): must-fix findings block and go into the caller's fix loop. `advisory` (default when absent, and for `execute-plan` / `/afk`): findings are presented, nothing blocks, the user decides. |

**Why one dispatcher.** Until now `run-phase` kept its own reviewer list and dispatched the same Apple agents by Phase-completion signals while this skill dispatched them by git-diff signals. Running both dispatched the same agents twice with different scopes — documented as intentional in `run-phase`, and it still cost a duplicate. The routing lives here now; callers pass inputs, not agent lists.

## Process

### Step 1: Gather Context

1. Run: `git status` — confirm uncommitted changes exist. If none, STOP: "无 uncommitted changes — review-execution 无对象。"
2. Run: `git diff --stat` + `git diff --staged --stat` — get scope. **If `scope_files` was supplied, intersect with it and use the intersection everywhere below**; if the intersection is empty, STOP and say so rather than falling back to the whole tree (a silent widening is exactly what passing `scope_files` was meant to prevent).
3. Identify project root and primary language(s) for the lens-prompts.
4. Detect project type using shell:
   - Run `find . -maxdepth 3 \( -name "*.xcodeproj" -o -name "*.xcworkspace" -o -name "Package.swift" \) -print -quit`
   - If output is non-empty → mark project as Apple (use this flag in Step 2)
   - Else → mark as non-Apple
5. Compute the routing flags from **what the diff actually touches**. Each flag exists to give exactly one reviewer something the others cannot see; a flag that fires on everything is not routing:
   - `HAS_VIEW_MODIFIED`: `git diff --name-only HEAD | grep -q 'View\.swift$'`
   - `HAS_NEW_VIEW`: `git diff --name-only --diff-filter=A HEAD | grep -q 'View\.swift$'`
   - `HAS_APPLE_NONSWIFT`: `git diff --name-only HEAD | grep -qE '\.(plist|entitlements|xcassets|xcconfig)|Package\.swift|\.pbxproj'`
   - `SPANS_LAYERS`: the diff touches ≥3 of {View, ViewModel/Store/Presenter, Model/Service/Repository} — judge from paths and type names
   - `HAS_FEATURE_SPEC`: `ls docs/05-features/*.md 2>/dev/null` is non-empty

   ⛔ **Do not reintroduce a bare `HAS_SWIFT`.** It fires on pure logic changes, which is how `ui-reviewer` ended up reviewing a state-machine bug — and why, on one measured run, three of seven reviewers returned the same finding. The redundancy was a routing defect, not a sign there were too many lenses.

### Step 2: Dispatch Reviewers (Single Parallel Batch)

Use the Agent tool to dispatch ALL applicable reviewers in a SINGLE message (parallel execution).

**Always dispatched (5-lens):**

**Lens A — Correctness (subagent_type: general-purpose, model: opus):**
```
You are a code-correctness reviewer. Review uncommitted changes in {project_root} via `git diff` and `git diff --staged`. Focus only on logical correctness:
- Off-by-one, null/undefined access, missing await/error handling
- Incorrect conditionals, wrong operators
- Type mismatches that escape the type-checker (any/unknown/casts)
- Missing branches in exhaustive checks

For each finding emit:
`[Correctness/{severity:must-fix|nice-to-have}] {file}:{line} — {one-line description}`

Do NOT comment on style, naming, or testing. Report-only; do not modify files.
```

**Lens B — Test Coverage (subagent_type: general-purpose, model: sonnet):**
```
You are a test-coverage gap finder. Review uncommitted changes in {project_root}. For each new or modified function/method:
- Is there a test that exercises it?
- Are edge cases (empty input, error path, boundary) covered?

For each gap emit:
`[TestGap/{severity}] {file}:{symbol} — missing test for {scenario}`

Do NOT write tests. Report-only.
```

**Lens C — Breaking Changes (subagent_type: general-purpose, model: sonnet):**
```
You are a breaking-change auditor. Review uncommitted changes in {project_root}:
- Function signature changes (param added/removed, return type changed)
- Type/interface changes (field removed, type changed)
- Public marker changes (public → private, removed export)
- Config key changes (renamed/removed)
- Default value changes

For each detection emit:
`[Breaking/{severity}] {file}:{line} — {what changed} — {downstream impact}`

Cross-reference: grep the codebase for callers of any removed/renamed symbols and list them.
```

**Lens D — Root-Cause Depth (subagent_type: general-purpose, model: opus):**
```
You are a root-cause-depth grader. For each fix-style change in the uncommitted diff, judge whether it addresses the root cause or is a surface-level patch:
- Hardcoded vendor flag vs reading from config
- Adding null check vs fixing the producer that returned null
- Try/catch swallowing vs fixing the throwing code
- Adding guardrail vs fixing the actual condition

For each finding emit:
`[Depth/{severity}] {file}:{line} — surface-level: {symptom} | root-cause would be: {what}`

Skip enhancement / refactor / removal changes — only grade fixes.
```

**Lens F — Secrets & Transport (subagent_type: general-purpose, model: sonnet):**
```
You are a security scanner. Scan ONLY the added/modified lines of the uncommitted diff for the four classes below. Report file:line and the matched text (redact the secret's tail: show at most the first 6 characters).

1. Hardcoded secrets
   - `sk-[a-zA-Z0-9]{20,}` (API keys), `AKIA[0-9A-Z]{16}` (AWS)
   - `password\s*[:=]\s*"[^"]{8,}"`, `api[_-]?key\s*[:=]\s*"[^"]{8,}"`
   - `-----BEGIN.*PRIVATE KEY-----`
   Exclude test targets and obvious placeholders ("password123", "changeme", "xxx").
2. Insecure transport
   - `http://` in URL strings, excluding localhost / 127.0.0.1 / 0.0.0.0
   - `NSAllowsArbitraryLoads` true in a plist
   - custom `URLSession` / ServerTrust handling that skips validation or sets no TLS minimum
3. Injection-shaped input handling
   - string interpolation inside SQL (`\(` near SELECT/INSERT/UPDATE/DELETE)
   - `NSPredicate(format:` with `\(` interpolation instead of `%@` arguments
   - `WKWebView` loading a user-supplied URL with no scheme check
4. Sensitive data at rest
   - `UserDefaults` storing a token / password / key → should be Keychain
   - (report only; do not judge an existing Keychain wrapper's quality)

For each finding emit:
`[Sec/{severity}] {file}:{line} — {class}: {what} | fix: {what to do instead}`

Report nothing for classes with no hit. Do not speculate about code outside the diff.
```

⛔ **This lens is always-on, not routed.** Every other conditional lens keys off a path pattern (`*View.swift`, `.plist`, …), and a secret does not live at a predictable path — a leaked key lands in whatever file the author was editing. A path-shaped route here would be a route that misses exactly the case it exists for. The cost is bounded: it is a sonnet grep pass over the diff only.

Provenance: these four checks were `apple-dev:code-audit` Step 2, a `user-invocable: false` skill that nothing dispatched. The other four `code-audit` categories (concurrency, accessibility, performance, SwiftUI anti-patterns) were NOT moved here — `apple-reviewer` and `ui-reviewer` already cover them. See `docs/12-retired/code-audit.md`.

**Lens E — Plan-vs-code (only when `plan_path` was supplied):**

Dispatch `dev-workflow:implementation-reviewer`, passing `plan_path`, the project root, and `design_doc_path` (or "none"). It answers a question no other lens asks: *did the code do what the plan said it would* — not whether the code is correct, which is Lens A's job. Without `plan_path` there is nothing to audit against, so skip it silently.

**Additionally dispatched in the SAME batch when project is Apple AND apple-dev plugin is installed:**

First verify apple-dev availability: `ls ~/.claude/plugins/cache/*/apple-dev/ 2>/dev/null`. If no output, skip ALL four reviewers below and add to the Step 3 summary table: "apple-dev not installed — Apple-platform review coverage skipped for this run". If installed:

- `apple-dev:ui-reviewer` — if `HAS_VIEW_MODIFIED` — pass the modified `*View.swift` files
- `apple-dev:design-reviewer` — if `HAS_NEW_VIEW` — pass the new View files
- `apple-dev:feature-reviewer` — if `HAS_FEATURE_SPEC` **or** `SPANS_LAYERS` — pass the spec path and the touched layers
- `apple-dev:apple-reviewer` — if `HAS_APPLE_NONSWIFT` — pass the non-Swift Apple-surface files

⛔ **`apple-reviewer` is no longer "always when Apple".** "Always" is not a route: on a Swift diff it duplicated `ui-reviewer` outright. Its own charter is the non-Swift Apple surface (.plist, entitlements, Package.swift, asset catalogs, project file) — give it exactly that and the overlap disappears.

⛔ **`feature-reviewer` no longer routes on the user's wording.** Keying a dispatch off phrases in the request means the same diff reviews differently depending on how it was asked for. Route on the diff's shape.

Critical: every applicable reviewer (5 always-on lenses A–D + F, plus Lens E and the conditional Apple set) must be in ONE Agent batch — do NOT split into a follow-up sequential dispatch.

If the project is Apple and apple-dev IS installed but no Apple flag fired, still emit the Apple section saying which flags were checked and came back false — a reader needs to tell "assessed, nothing applied" apart from "never looked". If the project is non-Apple OR apple-dev is not installed, do not mention Apple at all.

### Step 3: Consolidate

Wait for all agents to return. Parse their outputs into a single table:

```
## Review Findings — {date}

### Must-fix ({N})
1. [Lens] {file}:{line} — {finding}
...

### Nice-to-have ({M})
1. [Lens] {file}:{line} — {finding}
...

### Coverage notes
- Lens A (correctness) returned: {count} findings
- Lens B (test-coverage) returned: {count} findings
- Lens C (breaking) returned: {count} findings
- Lens D (depth) returned: {count} findings
- Lens F (secrets & transport) returned: {count} findings
- Lens E (plan-vs-code): {count} findings, or "skipped — no plan_path supplied"
- Scope: {"whole working tree" / "restricted to N files from scope_files"}
- Apple coverage: {"not applicable — non-Apple project" / list of dispatched Apple reviewers / "Apple project, apple-dev installed, no flag fired — checked: HAS_VIEW_MODIFIED, HAS_NEW_VIEW, HAS_FEATURE_SPEC, SPANS_LAYERS, HAS_APPLE_NONSWIFT"}
- Any agent that errored: {list, or "none"}

### Per-reviewer passthrough
{For each dispatched reviewer that returned a structured section, reproduce it verbatim under the reviewer's name.}
```

**The passthrough is load-bearing, not padding.** Callers parse specific sections that only one reviewer produces — `ui-reviewer`'s `### Part C: 人工验证清单`, `design-reviewer`'s `### Part B: 设备验证清单` and its 🔴 items, `feature-reviewer`'s `### Part C: 设备验证清单`, `implementation-reviewer`'s `Tests:` line. Flattening everything into must-fix / nice-to-have destroys them, and the caller then has to go hunting for per-agent report files — which is the coupling this consolidation exists to remove. Reproduce the sections; do not summarize them.

### Step 3b: Hand back according to `mode`

| `mode` | What happens next |
|---|---|
| `gated` | Return the must-fix list to the caller and stop. The caller owns the fix loop; this skill still modifies no source files. |
| `advisory` (default) | Present the findings and **stop without blocking**. Say plainly that nothing is being fixed and the decision is the user's. Do not re-dispatch to "confirm" a finding. |

**`advisory` from an `/afk` terminal stop carries one extra obligation: write the handoff.** The user was away; findings presented only in a live turn reach nobody. And the session they would return to is the expensive one — Claude Code's own prompt cache has expired by then, so continuing the old session hours later costs more than a cold start from a handoff doc. Invoke `dev-workflow:handoff` with the findings before ending the turn. ⛔ Do not drop this step as redundant with the on-screen summary; the on-screen summary is what expires.

**No review-report file.** Findings go in the return value and the handoff doc. Writing `.claude/reviews/*.md` was measured at ~6 writes per read-back; the copies that reached a human reached them through the agent's returned text, not the file.

Sort must-fix by file path; group by lens within each section.

**Only when at least one Apple reviewer actually ran in Step 2**, prepend their findings under '## Apple-Specific Findings' section before the 4-lens consolidated table. If no Apple reviewer ran (non-Apple project or none of the conditions matched), do NOT add this section header.

### Step 4: Present and STOP

Present the consolidated table to the user. Add the tail:

```
下一步建议（不会自动执行）：
- 让我 apply 哪些 must-fix？(列编号或 "全部")
- 跳过哪些？说明理由（可选）
- Nice-to-have 是否需要补充任务？
```

STOP. Do not apply any fix. Do not invoke commit. The user must explicitly direct the next action.

## Completion Criteria

- All four agents dispatched and returned (or marked errored)
- Consolidated findings presented to user
- No source file modified
- No commit made

## Naming Note

This skill is named `review-execution` (full form) intentionally — built-in `review` skill (PR review) already exists in Anthropic's default skill list. Do not abbreviate to `/review`.
