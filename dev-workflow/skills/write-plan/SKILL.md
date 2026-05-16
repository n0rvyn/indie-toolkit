---
name: write-plan
description: "Use when the user says 'write a plan', 'plan this', 'break this into tasks', '写计划', '拆分任务', or has requirements/specs for a multi-step task before touching code. Creates structured implementation plans with self-contained, verifiable tasks — each task lists files to touch, steps to take, and verification commands. Not when: trivial single-file change (just do it), plan file already exists (use verify-plan), or requirements still unclear (use brainstorm). For phase-driven development, run-phase calls this internally."
---

## Behavior Note

When invoked **standalone** (user runs write-plan directly): this skill automatically chains
to `dev-workflow:verify-plan` at Step 4 — plan writing and verification happen in one flow.

When invoked via **`run-phase`** orchestration: run-phase writes the plan in main context
using the Plan Writing Reference below, and manages verification as a separate explicit step.

## Skill Scope: one plan = one conceptual unit

A plan covers **one** conceptual unit of work — a single feature, a single component refactor, a single migration phase. Review pauses happen *between* plans / phases (each `/run-phase` or `/execute-plan` invocation is a natural checkpoint), not within them.

If the scope spans multiple independent units (e.g., "refactor 6 cards across 4 tabs", "migrate auth across 4 layers"), do **not** write a single multi-unit plan. Stop and invoke `/write-dev-guide` instead — break the work into phases, then `/run-phase` each phase. Each phase has its own plan, its own execute cycle, and an implicit review pause between phases (the user re-invokes `/run-phase`).

Heuristic: if the scope items naturally produce **multiple feature specs** at the end, it's multiple phases. If **one feature spec** covers it, it's one plan.

## Overview

This skill writes an implementation plan directly in the main context, benefiting from full conversation history and user intent.

## Process

### Step 0: Retrieve Prior Context (via `dev-workflow:kb`)

Before gathering context, search for relevant ADRs, architecture decisions, and known pitfalls:

1. Extract 3-5 keywords from the plan goal (component names, technology names, pattern names)
2. Invoke `dev-workflow:kb` skill via the Skill tool, passing the keywords as the query. The kb skill searches `~/.claude/knowledge/` (categories: api-misuse / api-usage / architecture / bug-postmortem / data-research / platform-constraints / workflow) and returns relevant prior context.
3. If results are returned: note them as "Prior context from knowledge base:" for use in Step 2
4. If the kb skill returns no matches, or the knowledge directory is empty: skip silently and continue to Step 1

### Step 1: Gather Context

Collect the following before writing:

1. **Goal** — one sentence describing what the plan achieves (from user request, dev-guide Phase, or conversation context)
2. **Scope items** — list of features/components to implement
3. **Acceptance criteria** — verifiable completion conditions (from dev-guide Phase or user)
4. **Design doc reference** — path to design doc if one exists (search `docs/06-plans/*-design.md`). If found, read it.
5. **Design analysis reference** — path to design analysis if one exists (search `docs/06-plans/*-design-analysis.md`). If found, read it: it contains validated token mappings, platform translations, and UX assertion validation from a visual prototype.
6. **Crystal file reference** — path to crystallized decisions file if one exists (search `docs/11-crystals/*-crystal.md`). If found, read it: it contains settled architectural and UX decisions with machine-readable D-xxx assertions the plan must respect.
7. **Project root** — current working directory
8. **Pre-flight Audit** (when plan modifies existing model field / component API / design token / shared component): grep all callers + scan for legacy/new dual token systems on the same semantic (e.g., `proteinOrange` vs `Macro.protein`) AND scan for module-shape signals per `dev-workflow/references/deep-modules-pattern.md` — shallow modules being further hollowed by this plan, adapters being added where a seam was the right boundary, and weak locality (this plan would scatter related changes across many files when a deep module would consolidate them). **Domain caveat:** the deep-vs-shallow lens is for imperative module boundaries; for declarative UI work (SwiftUI Views, React components), skip the deep-vs-shallow check and apply only the deletion test + locality lenses (see the deep-modules-pattern.md § Declarative-UI caveat). Findings → list under `**Pre-flight risks:**` as one line each; convert to tasks ONLY if the in-scope item cannot complete without addressing the shallow/adapter issue. Greenfield plans (only new files): set `**Pre-flight risks:** none`.
9. **Project Context Contract + Ubiquitous Language** — read `dev-workflow/references/project-context-contract.md`. If `docs/00-AI-CONTEXT.md` exists, read it and use it as the project language/source contract. `CLAUDE.md` and `AGENTS.md` remain rule files. If it is missing, continue and mark `Project context contract: missing`. Do not create `CONTEXT.md`. Additionally, read `docs/02-architecture/ubiquitous-language.md` if present (per `dev-workflow/references/ubiquitous-language-pattern.md`); when present, use its canonical terms in every task's `Expected behavior`, `User interaction`, and `Touched surface` fields. Mismatch between the plan's vocabulary and the ubiquitous-language file is a verifier-flagged issue.
10. **Project Health** — if `dev-workflow/scripts/project_health_scan.py` exists, read `.claude/dev-workflow-health.json` first; if state is missing, has any red signal, or older than 7 days, run scanner full mode with `--check-staleness 7 --max-ms 5000 --reason plan --write-state`; otherwise use cached `last_health`. Include red/yellow signals as `**Project health:**` in the plan header.
11. **Impact Map** — before task generation, write the plan-level Impact Map: user path, data path, shared surfaces, existing consumers, must remain unchanged, and regression checks.
12. **Out-of-scope archive** — list `dev-workflow/.out-of-scope/*.md`. If any scope item the user has provided matches a rejected entry, surface this to the user before writing the plan: "{item} was previously rejected per .out-of-scope/{file} — confirm you want to revisit?". Do not auto-skip; user may have new reasons.

If any of these are unclear, ask the user before writing.

### Step 2: Write Plan

Read relevant source files (design docs, existing code the plan will touch, crystal files) to understand the current state. Then write the plan following the **Plan Writing Reference** below.

Save the plan to `docs/06-plans/YYYY-MM-DD-<feature-name>-plan.md`.

### Step 2.5: Readback Echo (soft — skip if caller is run-phase)

Caller detection:
- If invoked from `dev-workflow:run-phase` orchestration → skip this step entirely
- If invoked from `dev-workflow:next-increment` orchestration → skip
- Else (standalone `/write-plan` or hook-driven) → execute

Execution:

1. Dispatch `readback:intent-echoer` agent via Task tool with:
   - `user_request`: the user's original prompt (full text from this session)
   - `draft_plan`: the just-written plan's Goal + Architecture (first 30 lines of the plan file)
   - `context_terms`: 3-5 project terms from session

2. Capture agent's verbatim output. **Substitute the literal content between the EOF markers with the actual text returned by intent-echoer** — do not modify, escape, or summarize. (If agent output contains the literal string `EOF_AGENT_OUTPUT`, use a unique marker variant for both lines.)

   ```bash
   AGENT_OUTPUT=$(cat <<'EOF_AGENT_OUTPUT'
   {paste intent-echoer's literal output here; do not modify}
   EOF_AGENT_OUTPUT
   )
   ```

3. Write `.claude/readback-state.json`:
   ```bash
   mkdir -p .claude
   jq -n \
     --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     --arg text "$AGENT_OUTPUT" \
     '{
       created_at: $ts,
       session_id: null,
       skill: "write-plan",
       readback_done: true,
       readback_text: $text,
       user_confirmed: false,
       confirmed_at: null,
       correction_count: 0
     }' > .claude/readback-state.json
   ```

4. Present agent output VERBATIM to user. Stop. Do not proceed to Step 3 (Decision Points / verify-plan).

5. Wait for user response:
   - "go" / "OK" / correction acknowledged → update state:
     ```bash
     jq --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
       '.user_confirmed = true | .confirmed_at = $ts' \
       .claude/readback-state.json > .claude/readback-state.json.tmp \
       && mv .claude/readback-state.json.tmp .claude/readback-state.json
     ```
     Then continue to Step 3.
   - Correction → re-dispatch intent-echoer with the correction, capture new `AGENT_OUTPUT`, then update state with incremented `correction_count`:
     ```bash
     jq --arg text "$AGENT_OUTPUT" \
       '.readback_text = $text | .correction_count += 1' \
       .claude/readback-state.json > .claude/readback-state.json.tmp \
       && mv .claude/readback-state.json.tmp .claude/readback-state.json
     ```
     Present new agent output verbatim. If `correction_count` reaches 2, suggest `/dev-workflow:brainstorm` (alignment broken upstream).

Note: this is soft mode (no `PreToolUse` hook enforcement — the readback plugin's hook only blocks when `skill: "fix-bug"`). The intent is alignment, not blocking. Standalone `/write-plan` callers benefit from the echo; `/run-phase`-driven invocations skip it because run-phase already handles confirmation at its own boundary.

### Step 3: Present and Verify

After writing the plan:

1. Present a summary to the user:
   - Plan file path
   - Number of tasks
   - Key files to be created/modified

2. **Decision Points:** Check the `## Decisions` section of the plan file.
   - If Decisions > 0:
     - First time this session: Read `${CLAUDE_PLUGIN_ROOT}/references/decision-points.md`
     - Apply the rules with parameters:
       - Source file: the plan file
       - Mode: `full`
       - Recording: `default`
3. Invoke `dev-workflow:verify-plan` to validate the plan before execution

## Completion Criteria

- Plan file written to `docs/06-plans/`
- Verification invoked and plan approved (or user chose to proceed with noted issues)

---

## Plan Writing Reference

This section contains the plan document format, scope guards, and writing guidelines. Referenced by both this skill and `run-phase` Step 2.

### Core Principle

Write plans assuming the implementing engineer has zero context. Document everything: files to touch, code snippets, commands, expected output.

### Scope Guards

1. **Absence != deletion**: If the current codebase has functionality X that is not mentioned in the scope items, X's status is "unchanged" (keep as-is). Only create deletion/removal tasks when the scope explicitly says "remove", "delete", "移除", or "删除" for that functionality. Design docs showing a target state without feature X does NOT authorize removing X — that's a UX change requiring explicit user instruction in the scope. Exception: if a crystal `[D-xxx]` decision explicitly calls for removal/replacement, that decision overrides this guard (D-xxx decisions represent user-confirmed intent).

2. **Scope boundary compliance** (when crystal file has `## Scope Boundaries`):
   - IN items: plan tasks should cover these
   - OUT items: plan tasks must NOT touch these areas. If a task would need to modify an OUT item to complete an IN item, add a `**Scope conflicts:**` subsection after `**Crystal file:**` in the plan header: `IN: {item} requires modifying OUT: {item} — {why}`. Do not create the conflicting task; let the verifier and user resolve it.

3. **No scope inference**: Decomposing a scope item into implementation steps is expected (e.g., "migrate color tokens" → one task per token category). But adding work that addresses a DIFFERENT concern not in the scope items is prohibited, even if it seems like a natural extension (e.g., scope says "migrate color tokens" → adding a font migration task is scope inference). If you believe additional work is necessary, note it in the plan header as "Recommended additions (not in scope)" — do not create tasks for it.
   - **Exception — Pre-flight Audit findings**: dependency risks that would cause the in-scope item to fail or visibly drift are scope completion (in scope, create tasks). Risks that merely surface unrelated debt are out of scope (recommend only).

4. **Quality fidelity** — If the design doc specifies a concrete approach for a feature (e.g., "LLM analysis", "Bree cron scheduler", "WordPiece tokenizer"), the plan task MUST implement that exact approach. If the specified approach is not feasible in this phase (missing dependency, API not available, infrastructure not ready), the task must:
   - Mark the task title with `⚠️ SIMPLIFIED:`
   - Add a `**Simplification:**` field explaining what was changed and why
   - Add a `**Design approach:**` field stating the original design's approach
   - Add a `**Blocking dependency:**` field if the simplification is due to a dependency not yet available (informational for human reviewers; not consumed by automated verification)
   Silently replacing a design-specified approach with a simpler alternative (heuristic, placeholder, stub) without these annotations is prohibited.

### Plan Document Format

```markdown
---
type: plan
status: active
contract_version: 2
tags: [tag1, tag2]
refs: []
---

# [Feature Name] Implementation Plan

**Goal:** [One sentence]

**Architecture:** [2-3 sentences on approach and key decisions]

**Tech Stack:** [Key technologies and frameworks]

**Design doc:** [path to design doc, if one exists — links to verify-plan DF strategy]

**Design analysis:** [path to design analysis, if one exists]

**Crystal file:** [path to crystal file, if one exists — links to verify-plan CF strategy]

**Threat model:** [included / not applicable]

**Pre-flight risks:** [list any dual-token systems, missed callers, optional-field fallback gaps, or design coverage gaps found in Step 1 item 8 — one per line; OR `none` if Pre-flight Audit was not applicable]

---

## Impact Map

**User path:** [user-visible flow affected]
**Data path:** [source → transform → destination]
**Shared surfaces:** [shared modules, APIs, docs, hooks, agents, or skills affected]
**Existing consumers:** [known callers/readers/users of changed surfaces]
**Must remain unchanged:** [out-of-scope adjacent behavior]
**Regression checks:** [checks that prove adjacent behavior remains intact]
```

### Task Structure

Each task should be a coherent unit of work. Don't force artificial granularity — a task can be small or substantial as long as it's self-contained and verifiable.

```markdown
<!-- section: task-N keywords: keyword1, keyword2 -->
### Task N: [Component/Feature Name]

**Maps to Impact Map:** [list which Impact Map rows this task touches: User path / Data path / Shared surfaces / Existing consumers / Must remain unchanged / Regression checks]

**Files:**
- Create: `exact/path/to/file.ext`
- Modify: `exact/path/to/existing.ext:line-range`
- Test: `tests/exact/path/to/test.ext`

**Expected outcome:** [concrete behavior after this task]

**Non-goals:**
- [explicitly unchanged behavior]

**Touched surface:** [files/APIs/data/UI/hooks/docs changed]

**Regression shield:** [guard against adjacent damage]

**Task Contract:**
- Expected behavior: [user-visible result in 1–3 sentences, no technical jargon — what does the user see/feel after this task?]
- Automated verify: [deterministic command or fixture — write this FIRST, then make Steps satisfy it (vertical slice per Pocock TDD)]
- Real path verify: [real user/API/tool path, or explicit reason it's impossible with manual fallback]
- Manual/device verify: [manual step, or none]

**Steps:**
Implementation steps that make `Task Contract.Automated verify` pass — and that deliver the user-observable outcome stated in `Task Contract.Expected behavior`. Do not write Steps before Expected behavior is filled in.

1. [Clear instruction with code snippet if needed]
2. [Next step]
3. [Verification step with exact command and expected output]

**Verify:**
Run: `<exact command>`
Expected: <what success looks like>
<!-- /section -->
```

> **On the verify-first ordering** (`Automated verify: write this FIRST`):
> This rule comes from Pocock's TDD framing and is reinforced by 2026 research — see `dev-workflow/references/tdd-research-2026.md` for failure modes (implementation-first bias, test tampering, context pollution, verification gap) and mitigation patterns (plan-time test-impl split, committed-test checkpoint).
> Practical implications when writing the plan:
> - The `Automated verify` line must be a command/fixture that can run BEFORE the implementation exists and FAIL (no false-pass via missing-file errors etc.). State the expected FAIL signal explicitly in Steps if non-obvious.
> - If the conceptual task would naturally produce BOTH test files and implementation files in its `**Files:**` list, follow the plan-time split rule in Writing Guidelines (item 12) — generate two tasks (`### Task N-tests:` and `### Task N-impl:`) instead of one combined task. This achieves the 2026 multi-agent isolation pattern via plan structure rather than runtime routing (see `references/tdd-research-2026.md` § 2026 mitigation stack subsection (a) for the rationale).
> - For trivial edits (typo, log line, rename) where TDD adds friction without value, the task may use `**Automated verify:** N/A — trivial edit; verified via <command>` and state the alternative verification. This matches Anthropic's 2026 guidance to skip TDD for trivial edits.

### Optional Design Anchor Fields

When a task implements part of a design document, add these fields to help execution stay faithful:

```markdown
**Design ref:** [design-doc.md § Section Name]
**Expected values:** [key concrete values from design that must appear in code]
**Replaces:** [what existing code/pattern this replaces, if any]
**Data flow:** [source → transform → destination]
**Quality markers:** [specific acceptance criteria beyond "it works"]
**Verify after:** [verification specific to design faithfulness]
**UX ref:** [UX-NNN from design doc's UX Assertions table — which assertion(s) this task fulfills]
**User interaction:** [what the user sees and does — derived from User Journeys, not invented]
```

These fields are optional per-task. Use them when the task has design-critical details that could drift during implementation.

### Writing Guidelines

1. **Complete file paths** — always absolute from project root
2. **Actual code** — not pseudocode, not "implement X here"
3. **Exact commands** — copy-pasteable verification commands with expected output
   - **Task-level `Verify:` scope**: each task's Verify should contain only that task's specific checks (grep for expected strings, type-check a single file, run a single test file). Full build/test suite execution is handled by the `test-changes` skill after plan execution completes; do not include full-suite commands (`npm run build`, `npm test`, `swift build`, `xcodebuild test`, or equivalent) in any plan task.
4. **Dependencies explicit** — if Task 3 depends on Task 1, say so
5. **Test coverage required, ordering flexible** — every plan must include tests for logic and user journeys (see item 10). Test-first vs test-after is the author's choice; test absence is not
6. **Reasonable task size** — self-contained and independently verifiable; not artificially split
7. **Task section markers:** Each `### Task N:` block is wrapped in `<!-- section: task-N keywords: {kw1}, {kw2} -->` ... `<!-- /section -->`. Keywords are derived from the task's `**Files:**` paths and the technologies/APIs the task touches. Use the leaf file name (without extension) and key technology names. 2-4 keywords per task.
8. **UX-aware tasks** — when the design doc has a `## UX Assertions` section: read the User Journeys and UX Assertions table before writing any UI task. Each task that implements user-visible behavior must include `UX ref:` pointing to the assertion ID(s) it fulfills, and a brief `User interaction:` line describing what the user sees and does (derived from the User Journeys, not invented). Tasks that touch UI but don't map to any UX assertion should be flagged with `⚠️ No UX ref: [reason]`
9. **Frontmatter fields:** `type` is always `plan`. `status` is always `active` when first written. `tags` — derive 2-5 keywords from the feature name and key technologies in the tasks (e.g., tasks touching SwiftData and sync → `[swiftdata, sync, offline]`). `refs` — list the design doc path and crystal file path from the plan header (if set to a real path, not "none").
10. **Mandatory test assessment** — evaluate and assign tests based on code type (enforces item 5):
    - **Business logic** (algorithms, data transformations, validation): **requires** Unit Tests
    - **User journeys** (end-to-end flows, API integrations): **requires** E2E Tests — only when the Phase has a complete user journey (UI + logic + data flow). Infrastructure-only Phases with no user-facing flow require UT only
    - **Performance-critical** (rendering, data processing, large datasets): recommends Performance Tests
    - **UI components** (views, controls, animations): recommends Snapshot Tests or UI Tests
    - When a task involves any of these code types, either:
      a. Create a separate test task with appropriate test type, OR
      b. Embed test verification steps in the functional task's `**Verify:**` section
    - **Skip conditions:** tasks that are pure config (editing .md/.yml/.json with no logic), style-only (CSS/layout with no conditional logic), or transparent pass-through to a third-party API may skip tests. Skipped tasks MUST annotate `⚠️ No test: {reason}` in the task body. plan-verifier will audit the reason
    - Platform-specific test implementations can reference apple-dev plugin skills:
      - UT/Mock/TDD → `apple-dev:testing-guide`
      - E2E/Snapshot/A11y → `apple-dev:xc-ui-test`
      - Performance → `apple-dev:profiling`
    - Plans missing UT for business logic tasks or E2E for user journey tasks will be flagged as **must-revise** by plan-verifier
11. **No final verification task** — Plans do NOT include a final "run everything" task. The `test-changes` skill handles full build/test/lint execution as a separate step after plan execution completes. Plans still include test-writing tasks (per guideline 10) — tests are written as code during execution, then run by test-changes afterward. Per-task `**Verify:**` commands remain lightweight: type-check (`tsc --noEmit`, `swift build`), grep for expected strings, or single-file compilation only. **Backward compatibility:** Old plans with a `### Task N: Full verification` task still execute correctly — execute-plan runs all tasks literally. The suite runs twice (once in plan, once in test-changes); redundant but not harmful.

12. **Plan-time test-impl split** (per `dev-workflow/references/tdd-research-2026.md` § 2026 mitigation stack subsection on plan-time test-impl split). When a conceptual task would naturally produce BOTH test files AND non-test files **containing executable logic** (source code, not config/data) in its `**Files:**` list, generate it as TWO tasks instead of one:

    - **Task N-tests** — heading exactly `### Task N-tests: [name]` (the `-tests` suffix is load-bearing; downstream tools — `execute-plan` task counter, `plan-verifier` iterator, and `implementation-reviewer` Test-Fidelity Audit pair detection — match on this shape). `**Files:**` contains only the test files (`Create:` or `Modify:`). `Task Contract.Automated verify` asserts tests compile AND FAIL (e.g., `npm test -- foo.test.ts` exits non-zero with "ReferenceError: foo is not defined" or equivalent). `Task Contract.Expected behavior` describes the test cases' user-observable expectations, not how the implementation will look.
    - **Task N-impl** — heading exactly `### Task N-impl: [name]` (same downstream-tool dependency on the `-impl` suffix). `**Files:**` contains only the non-test files (`Create:` or `Modify:`). `Task Contract.Automated verify` asserts tests now PASS (e.g., `npm test -- foo.test.ts` exits 0). `Task Contract.Expected behavior` reuses the same user-observable expectations as N-tests (the two tasks together deliver one user-visible outcome). Add `**Regression shield:**` line: "Do not modify the test files written in Task N-tests (changes to tests during this task are test tampering)."
    - Dependency: Task N-impl includes `**Depends on:** Task N-tests` to enforce sequential execution.
    - **Why split**: per 2026 research (see reference), single-context TDD has documented failure modes (context pollution, test tampering, overfitting). Splitting at plan-time isolates the test-writer agent's context from the implementer's via the plan structure itself — `execute-plan` dispatches each task to a fresh agent context.
    - **Mixed-content rule** (pure config bundled with logic): pure config additions/edits (`.yml`/`.json`/`.toml`/`.md`/`.env`) bundled alongside test-covered logic do NOT by themselves trigger the split. The split applies to the logic half; the config edit attaches to whichever half is more natural (typically N-impl). Example: a task with `Create: src/utils/parseISO8601.ts`, `Create: tests/utils/parseISO8601.test.ts`, `Modify: lint-rules.yml` → split into Task N-tests (just the .test.ts file) and Task N-impl (parseISO8601.ts + lint-rules.yml).
    - **When NOT to split**:
      - Trivial edits (typo, rename, log line) where the Task Contract's `Automated verify` is N/A.
      - Tasks where the test files are `Modify:` only (existing tests already exist and pass; this is test modification, not test-first TDD — splitting would cause Task N-tests' "tests must FAIL" verify to incorrectly fail because existing tests already pass).
      - Tasks where the plan author has explicitly written them combined and added `<!-- no-split: <reason> -->` immediately after the `### Task N:` heading. Downstream tools (Test-Fidelity Audit) respect this annotation and skip pair detection for that task.
      - **Refactors with no net-new behavior** — apply the decision rubric: does `Task Contract.Expected behavior` describe a NET-NEW user-visible outcome (split applies) or the SAME outcome before-and-after with only internal structure change (no split — tests should pass before AND after; the verify-first ordering doesn't apply because there is no failing state to start from)? Pure refactors fall in the second bucket and skip the split.

### Security Assessment

When the plan goal, task descriptions, or scope items contain any of these security-signal keywords — `sandbox`, `permission`, `auth`, `RBAC`, `deny`, `allow`, `isolation`, `encrypt`, `token`, `credential`, `secret`, `certificate`, `injection`, `escape`, `validate` — the plan MUST include a `## Threat Model` section after the plan header and before Task 1. Set the header field `**Threat model:** included`. When none of these keywords appear, set `**Threat model:** not applicable` and omit the section.

The Threat Model section contains four subsections:

1. **Attack surface** — For each controlled input that could be attacker-influenced, identify the input source and attack class. Example: user-supplied file paths → path traversal/injection; user-supplied regex → ReDoS; user-supplied template strings → template injection.

2. **Failure modes** — For each new security component introduced by the plan (permission check, sandbox profile, auth gate, validation layer), document what happens when it fails silently. Acceptable answers: deny-all (safe default), allow-all (unsafe — must justify), crash/abort (acceptable for dev tooling, not for user-facing). Unspecified failure mode = gap the verifier will flag.

3. **Resource lifecycle** — For each task that creates temp files, spawns child processes, opens file handles, or opens sockets: document who cleans up on success, on error (catch/finally), and on signal/crash (SIGTERM/SIGINT handler or equivalent). All three triggers must be addressed; missing any one is a gap.

4. **Input validation requirements** — For each task that embeds external input into a structured format (SQL, shell commands, SBPL profiles, regex, template strings, URL parameters), document what characters must be validated or escaped and where in the code the validation occurs.

### Crystal File Integration

When a crystal file is provided: ensure every `[D-xxx]` decision is reflected in at least one plan task. Rejected alternatives in the crystal must not appear as plan tasks. Add `Crystal ref: [D-xxx]` to task headers that implement specific decisions.

### Design Analysis Integration

When a design analysis is provided: read it and incorporate token mappings, platform translations, and UX assertion validations into the relevant plan tasks.

### Decisions

If any planning finding requires a user choice before execution can proceed, output a `## Decisions` section in the plan document. If no decisions needed, output `## Decisions\nNone.`

**Decision Point Necessity Gate** (apply before writing any DP-xxx):

A decision point is only valid when **all** of these hold:

1. The plan cannot proceed without the user picking an option (choice gates execution)
2. **Code, config, brief, design doc, and crystal file together do not determine the answer** — if they do, you must state the chosen approach inline with a one-line rationale citing the source, not as a DP
3. There are **2+ genuinely distinct options** with different trade-offs (different cost, risk, downstream impact, or user-visible behavior)

**Forbidden patterns** (these are not decisions, do not write them as DPs):

- ❌ **Single-option DP**: Options A only, or A vs "skip A" with no reason to skip
- ❌ **Pseudo-choice with obvious recommendation**: Three options where two are strictly worse on every axis. If you would recommend the same option in 95%+ of contexts, it is not a decision — state it as a choice with rationale.
- ❌ **Implementation-detail DP**: Internal variable naming, file split granularity, code structure that doesn't affect user/architecture
- ❌ **Re-asking a settled question**: A `**Chosen:**` entry already exists, or a crystal `[D-xxx]` covers it

**Self-check before writing each DP**:

Remove the `**Recommendation:**` line. If a competent reader can determine the answer by reading only the code/brief/design references in `**Context:**`, this is not a DP — convert to inline statement of the form:

> Chose {approach} ({reason in one line, citing file:line or brief section}).

**Concrete anti-pattern from past sessions**: a plan once shipped DP-008 with three options that were really one — same architecture, same files touched, only naming differed. User reported this as wasted attention. Avoid.

Format per decision:

```
### [DP-001] {title} ({blocking / recommended})

**Context:** {why this decision is needed, 1-2 sentences}
**Options:**
- A: {description} — {trade-off}
- B: {description} — {trade-off}
**Recommendation:** {option} — {reason, 1 sentence}
```

**Recommendation quality rule:**
- Recommendations must cite code evidence (file:line or structural reasoning grounded in specific code). Example: "Option A; `Router.swift:42` shows routes are registered centrally, extending that pattern is lower-risk"
- If code evidence is unavailable (decision about a new pattern with no existing precedent): use `**Recommendation (unverified):**` instead of `**Recommendation:**`, and state why evidence is absent
- Self-check: remove the recommendation. Can a reader reach the same conclusion by following the cited evidence? If not, the evidence is insufficient

Priority levels:
- `blocking` — must be resolved before plan execution; the dispatcher will ask the user via AskUserQuestion
- `recommended` — has a sensible default but user should confirm; dispatcher presents as batch

Common decision triggers for plan writing:
- Scope conflicts detected (IN item conflicts with OUT item) → resolve or exclude (blocking)
- Recommended additions identified (needed but not in scope) → add to scope or defer (recommended)
- `**Replaces:**` patterns where old code removal is non-trivial → confirm removal (blocking)
