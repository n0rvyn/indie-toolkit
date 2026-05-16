---
name: review-execution
description: "Use when the user says 'review execution', 'parallel review', 'deep review', 'review my code', 'review after coding', 'execution review', '审查执行', '并行 review', '写完 review 一下', '代码 review 一下', '深度审查', '执行后审查', or wants a fresh-context multi-lens review of uncommitted changes BEFORE commit. Dispatches 4 parallel reviewer agents (correctness, test-coverage, breaking-changes, root-cause-depth) and consolidates findings into must-fix / nice-to-have. Standalone — does NOT require a plan or dev-guide. Not when: a plan exists and you want plan-vs-code audit — use implementation-reviewer. Not when: pre-commit semantic classification only — use review-before-commit. Not when project is Apple-only and you want only ASC pre-submit review — use /asc-submit-preview. Not when user says '代码审计' (the 4-char compound triggers apple-dev:code-audit internal scan; this skill matches '代码审' as a verb phrase, not '代码审计' as a noun)."
user-invocable: true
allowed-tools: Bash(git diff:*, git status:*, git log:*, git ls-files:*, find:*, grep:*), Task
---

## Overview

This skill formalizes the "parallel reviewer dispatch" pattern that consistently produces high-quality post-execution reviews (per 2026-04 — 2026-05 insights report). Four reviewer agents run concurrently in fresh contexts, each focused on one lens. The dispatcher consolidates findings, presents to the user, and STOPS before applying any fix.

**Mode:** REVIEW-ONLY. No source files modified. Output is a structured findings list.

## When To Use

- Before commit on non-trivial changes (>50 changed lines, or any deletion, or public-API change)
- Before a PR / merge to main
- After `execute-plan` completes outside of `run-phase` orchestration
- When the user wants a "second opinion" on uncommitted work
- Apple 项目（自动并行 dispatch ui/design/feature/apple reviewers 与 4-lens 同批次执行）

## When NOT To Use

- Plan-vs-code audit (use `implementation-reviewer` — it knows about the plan)
- Semantic change classification only (use `review-before-commit` — enhancement / fix / refactor / removal categorization)
- Mid-execution / mid-plan checkpoints (use the orchestrator's review step)

## Process

### Step 1: Gather Context

1. Run: `git status` — confirm uncommitted changes exist. If none, STOP: "无 uncommitted changes — review-execution 无对象。"
2. Run: `git diff --stat` + `git diff --staged --stat` — get scope.
3. Identify project root and primary language(s) for the lens-prompts.
4. Detect project type using shell:
   - Run `find . -maxdepth 3 \( -name "*.xcodeproj" -o -name "*.xcworkspace" -o -name "Package.swift" \) -print -quit`
   - If output is non-empty → mark project as Apple (use this flag in Step 2)
   - Else → mark as non-Apple
5. Identify modified file kinds (only used when project is Apple):
   - `HAS_SWIFT`: shell expression `git diff --name-only HEAD | grep -q '\.swift$'`
   - `HAS_NEW_VIEW`: shell expression `git diff --name-only --diff-filter=A HEAD | grep -q 'View\.swift$'`

### Step 2: Dispatch Reviewers (Single Parallel Batch)

Use the Task tool to dispatch ALL applicable reviewers in a SINGLE message (parallel execution).

**Always dispatched (4-lens):**

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

**Additionally dispatched in the SAME batch when project is Apple:**
- `apple-dev:apple-reviewer` — always when Apple project is detected (covers non-Swift diffs too: .plist, Package.swift, entitlements, asset catalogs)
- `apple-dev:ui-reviewer` — if HAS_SWIFT
- `apple-dev:design-reviewer` — if HAS_NEW_VIEW
- `apple-dev:feature-reviewer` — if user message contains "user journey" / "feature 完成" / "完整流程"

Critical: all applicable reviewers (4 lenses + conditional Apple) must be in ONE Task batch — do NOT split into a follow-up sequential dispatch.

If project is Apple but ONLY apple-reviewer applies (no Swift / new View / user journey signals), still emit the Apple section in the report so the user knows Apple coverage was assessed; if project is non-Apple, do not mention Apple at all.

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
- Apple coverage: {one of: "not applicable — non-Apple project" / "apple-reviewer + ui-reviewer + ..." (list dispatched) / "Apple project detected but no Apple reviewer applied (reason: {no Swift / no new View / no user journey signal})"}
- Any agent that errored: {list, or "none"}
```

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
