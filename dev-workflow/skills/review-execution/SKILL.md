---
name: review-execution
description: "Use when the user says 'review execution', 'parallel review', '审查执行', '并行 review', or wants a fresh-context multi-lens review of uncommitted changes BEFORE commit. Dispatches 4 parallel reviewer agents (correctness, test-coverage, breaking-changes, root-cause-depth) and consolidates findings into must-fix / nice-to-have. Standalone — does NOT require a plan or dev-guide. Not when: a plan exists and you want plan-vs-code audit — use implementation-reviewer. Not when: pre-commit semantic classification only — use review-before-commit."
user-invocable: true
allowed-tools: Bash(git diff:*, git status:*, git log:*, git ls-files:*), Task
---

## Overview

This skill formalizes the "parallel reviewer dispatch" pattern that consistently produces high-quality post-execution reviews (per 2026-04 — 2026-05 insights report). Four reviewer agents run concurrently in fresh contexts, each focused on one lens. The dispatcher consolidates findings, presents to the user, and STOPS before applying any fix.

**Mode:** REVIEW-ONLY. No source files modified. Output is a structured findings list.

## When To Use

- Before commit on non-trivial changes (>50 changed lines, or any deletion, or public-API change)
- Before a PR / merge to main
- After `execute-plan` completes outside of `run-phase` orchestration
- When the user wants a "second opinion" on uncommitted work

## When NOT To Use

- Plan-vs-code audit (use `implementation-reviewer` — it knows about the plan)
- Semantic change classification only (use `review-before-commit` — enhancement / fix / refactor / removal categorization)
- Mid-execution / mid-plan checkpoints (use the orchestrator's review step)

## Process

### Step 1: Gather Context

1. Run: `git status` — confirm uncommitted changes exist. If none, STOP: "无 uncommitted changes — review-execution 无对象。"
2. Run: `git diff --stat` + `git diff --staged --stat` — get scope.
3. Identify project root and primary language(s) for the lens-prompts.

### Step 2: Dispatch Four Parallel Reviewers

Use the Task tool to dispatch all four in a SINGLE message (parallel execution):

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

### Step 3: Consolidate

Wait for all four agents to return. Parse their outputs into a single table:

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
- Any agent that errored: {list, or "none"}
```

Sort must-fix by file path; group by lens within each section.

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
