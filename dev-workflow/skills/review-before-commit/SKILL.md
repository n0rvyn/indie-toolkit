---
name: review-before-commit
description: "Use when the user says 'review changes', 'review-before-commit', '审查变更', '检查改动', '提交前审查', 'pre-commit review', or wants a semantic review of uncommitted changes before committing. Classifies changes into enhancements, fixes, refactors, and removals; explains what each does; detects breaking changes; and flags risks interactively. Not when: user only wants to commit (use commit skill); user wants to fix a bug (use fix-bug); user wants multi-lens deep review covering correctness / test-coverage / breaking-changes / depth (use review-execution — that one dispatches 5 always-on lenses plus reviewers routed by the diff, this one is a single semantic classification pass)."
user-invocable: true
argument-hint: "[path or empty — optional path scopes review to matching files]"
allowed-tools: Read Glob Grep WebSearch WebFetch Bash(git diff:*, git status:*, git log:*, grep:*, wc:*, find:*, ls:*, mkdir:*, python3:*, date:*, git rev-parse:*) AskUserQuestion Agent Edit(*/.claude/reviews/*)
effort: medium
---

<!-- cost-posture: inherit, effort medium (orchestration, targeted evidence verification and user interaction). Full diff classification and proposed risk grading stay in change-classifier (effort: high). No model: pin; never add context: fork. -->

## Input

Trigger this skill when:
- User says "review changes", "review-before-commit", "审查变更", "检查改动", "提交前审查", "pre-commit review"
- User wants to understand what uncommitted changes do before committing
- User wants a safety check before pushing

If user provides a path argument: scope review to matching files (pass it to the agent as `Path scope`; it appends `-- <path>` to every git diff command).

On trigger:
1. Run `git status` to confirm changes exist
2. If no uncommitted changes (unstaged + staged both empty): inform user and stop
3. If changes exist, proceed to Step 1

## Process

### Step 1: Resolve Inputs (inline)

The analysis runs in the `dev-workflow:change-classifier` agent, which does **not** see this conversation. Resolve everything it needs here:

1. **Repo root**: `git rev-parse --show-toplevel`.
2. **Change source** from the `git status` above: `staged`, `unstaged`, or `mixed`.
3. **Path scope**: the user's path argument, or none.
4. **Plan file** (Task Contract Awareness): if the current session references a plan file, use its absolute path. Otherwise run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py status`; if it reports `exists:true` with a non-null `state.plan_file`, use that. Otherwise `none`. A plan that exists only in this conversation is lost unless you pass its path here.
5. **Timestamp**: `date +%Y-%m-%d-%H%M%S`.
6. **Verification context**: pass any user-supplied evidence paths, official sources, constraints or prior corrections relevant to the risks. The agent cannot recover these from conversation history.

### Step 2: Dispatch change-classifier

Call the Agent tool with `subagent_type: "dev-workflow:change-classifier"` and a prompt containing:

```
Repo root: <absolute path>
Path scope: <path or none>
Change source: staged | unstaged | mixed
Plan file: <absolute path or none>
Lens C source: ${CLAUDE_PLUGIN_ROOT}/skills/review-execution/review.workflow.js
Timestamp: <YYYY-MM-DD-HHmmss>
Verification context: <relevant evidence paths, sources and constraints, or none>
```

The agent applies the mechanical 200-line depth rule, classifies change groups (enhancement / fix / refactor / removal), runs breaking-change detection (review-execution's Lens C checklist plus residual-caller grep), compares against the plan's Impact Map, grades risks, and writes `.claude/reviews/review-before-commit-{timestamp}.md`. It returns a `## Change Classifier Result` block with `Status`, `Report`, `Depth strategy`, `Totals`, `Counts`, `Contract comparison`, `Breaking-change check`, `Breaking changes`, a `### Risks` table (`id | severity | description | recommendation`) and `### Verdict`.

**If the dispatch fails, errors, times out, or returns `Status: failed` or no `## Change Classifier Result` block:** tell the user "Pre-commit review did NOT run — change-classifier failed: <reason>." and stop. Do not analyze the diff yourself as a fallback, do not report "no risks", and do not ask "Proceed with `/commit`?".

If the return says `Breaking-change check: NOT RUN (...)`, repeat that line verbatim in the summary — breaking changes were not checked, which is not the same as none found.

### Step 2.5: Verify Risk Evidence (inline)

Read the report and `${CLAUDE_SKILL_DIR}/references/risk-evidence.md`. The agent's findings are proposals. Verify every proposed high/medium risk's decisive premise before asking the user to accept it; also check any platform or policy premise used to claim a breaking change. Re-read the cited code and affected consumer, and use a safe focused check where it distinguishes failure from an unsupported inference. This is targeted verification, not another full diff review.

For evolving platform capabilities, limits or policies, read the current official documentation and record its URL, relevant version/date and what it actually establishes. Repository rules and old probes are evidence about their own scope, not proof of current platform incompatibility. If the agent could not access an official source, use the available browsing tools here. A failed first access is not a finding about the platform; try a supported alternative within authorization.

Update the existing report with a verification entry for each checked risk: stable risk ID, `file:line`, risk kind, trigger condition, concrete consequence, evidence/source, verification status, and proposed → final severity with reason. Use `confirmed`, `unverified` or `contradicted`. Correct or retract unsupported claims while preserving the original proposal and the reason for the change. A confirmed local-rule violation remains visible as such. Do not automatically demote every finding: retain high/medium severity where demonstrated impact warrants it.

Use the verified report for the Risks table, totals, breaking-change count and verdict. Retain evidence-supported breaking changes; correct an unsupported detection and record why. Never erase or turn `Breaking-change check: NOT RUN (...)` into a clean result.

When a decisive premise remains unverified after available safe checks, keep its proposed severity and the missing evidence in the report. Exclude it from acceptance choices: the user cannot verify a factual claim by acknowledging it. Report the incomplete check and the smallest missing input if user intervention is actually required. Do not report a clean verdict while material verification remains incomplete; continue independent checks and show any confirmed risks normally.

### Step 3: Interactive Risk Confirmation

This step runs **only if the verified report contains confirmed high/medium risks.** Informational, contradicted and unverified findings remain in the report without acceptance questions.

Collect confirmed risks with final severity `high` or `medium` (up to 4; if more than 4, take the top 4 by severity and note the rest in the report). Explain the kind, trigger and consequence in plain language, with the supporting evidence available in the report.

Present them in a **single** AskUserQuestion call with one question per risk. Use a shared header like "Risk audit" and multiSelect: false for each question:

```
Question: "#{N} [{severity}] {description}"
Options:
- "Fix now" — pause review, fix the issue, then re-run review
- "Acknowledged (intentional)" — mark as acknowledged, proceed
- "Ignore for now" — leave in report, continue
```

After receiving answers, update the `Resolution` column of the report file named in `Report:` (Edit):
- "Fix now" risks: mark as "→ Fix required" in report
- "Acknowledged (intentional)" risks: mark as "Acknowledged — intentional"
- "Ignore for now" risks: leave as-is in report

If any risk was marked "Fix now", pause and tell the user: "Fix the marked risks, then re-run `/dev-workflow:review-before-commit`."

## Output Format

After completing the review, present a compact summary to the user. Take change counts and classification from the agent; take risk counts, breaking changes and verdict from the verified report:

```
Pre-commit review complete.

Changes: {N} files, +{A} -{D} lines
Enhancements: {N} | Fixes: {N} | Refactors: {N} | Removals: {N}

Risks: {N} (🔴 {high} / 🟡 {medium} / 🟢 {info})
Breaking changes: {N}

Report: .claude/reviews/review-before-commit-{timestamp}.md
Verdict: ✅ Clean / ⚠️ {N} risks need attention / ❌ {N} breaking changes
```

If verification is incomplete, add `Verification incomplete: <risk IDs and missing evidence>` and use a warning verdict. Separate confirmed risks from unverified proposals; do not count unverified proposals as confirmed faults.

Then ask: "Proceed with `/commit`?"

## Edge Cases

**No changes:** Inform user: "Nothing to review — working tree and staging area are clean."

**Only staged / only unstaged / mixed changes:** pass the matching `Change source`; the agent reviews that source and labels groups by source when mixed.

**Binary files, huge diffs (>2000 lines), no extractable symbols:** handled inside `change-classifier` (size-only listing; at most 10 deep-dived files; "Breaking change check skipped — no extractable symbols").

**Merge commits in progress:** If `git status` shows merge conflict state, inform user: "Merge in progress — resolve conflicts before reviewing."

## Rules

- **Classify once, verify before disposition.** Depth rule, classification, breaking-change grep and proposed risk grading are `dev-workflow:change-classifier`'s job. The caller verifies decisive premises and corrects evidence, severity and summary in Step 2.5 without repeating the full review.
- **Failure is not a clean result.** A failed dispatch means the review did NOT run — say so and stop.
- **Report is durable.** The agent writes the full report to `.claude/reviews/`; the caller records evidence verification, final risk grading and resolutions there. Source files and staging remain untouched.
- **Confirmed risk interaction is blocking.** Don't proceed past Step 3 until the confirmed high/medium risks presented there have a disposition. Unverified material proposals remain incomplete checks, not user acceptance choices.
- **Pure review, no commit.** This skill does not commit, does not suggest commit messages, does not group for commit. That's the `commit` skill's job.

## Completion Criteria

- change-classifier returned `Status: complete` with a report path (diffs classified, breaking-change grep run, risks graded, report written to `.claude/reviews/`)
- Decisive premises for proposed high/medium risks checked; final grading and verification evidence recorded, with incomplete checks explicitly named
- Confirmed high/medium risks handled interactively (or none found); unverified factual claims never presented as acceptance choices
- Summary displayed to user
