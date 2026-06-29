---
name: review-before-commit
description: "Use when the user says 'review changes', 'review-before-commit', '审查变更', '检查改动', '提交前审查', 'pre-commit review', or wants a semantic review of uncommitted changes before committing. Classifies changes into enhancements, fixes, refactors, and removals; explains what each does; detects breaking changes; and flags risks interactively. Not when: user only wants to commit (use commit skill); user wants to fix a bug (use fix-bug); user wants multi-lens deep review covering correctness / test-coverage / breaking-changes / depth (use review-execution — that one dispatches 4 parallel reviewer agents, this one is a single semantic classification pass)."
user-invocable: true
argument-hint: "[path or empty — optional path scopes review to matching files]"
allowed-tools: Bash(git diff:*, git status:*, git log:*, grep:*, wc:*, find:*, ls:*, mkdir:*) AskUserQuestion
---

<!-- cost-posture: inherit (judgment — semantic change classification into enhancement/fix/refactor/removal, breaking-change detection, and risk severity grading are judgment calls; pre-commit gate runs over a full uncommitted batch as a single audit pass, not in a tight loop, so Opus-level quality is preferred. do NOT downgrade to sonnet/haiku per dev-workflow Skill Cost Posture rule and per DP-002=A 2026-06-28) -->

## Input

Trigger this skill when:
- User says "review changes", "review-before-commit", "审查变更", "检查改动", "提交前审查", "pre-commit review"
- User wants to understand what uncommitted changes do before committing
- User wants a safety check before pushing

If user provides a path argument: scope review to matching files (append `-- <path>` to all git diff commands).

On trigger:
1. Run `git status` to confirm changes exist
2. If no uncommitted changes (unstaged + staged both empty): inform user and stop
3. If changes exist, proceed with analysis

## Process

### Step 1: Gather Diffs

Step 1a — scope assessment (run first):

```
git diff --stat
git diff --numstat
```

Step 1b — full content (run after depth decision in Step 2):

```
git diff
git diff --staged
```

Track separately: which changes are staged vs unstaged.

### Step 1.5: Task Contract Awareness

If `.claude/dev-workflow-state.json` (or legacy `.yml`) or the current session references a plan file:

1. Read the plan file.
2. If it has `## Impact Map`, extract `Shared surfaces`, `Existing consumers`, `Must remain unchanged`, and task `Touched surface` fields.
3. Compare changed files and removed symbols against the Impact Map.
4. Flag any changed surface that is outside the plan as a risk item unless the diff clearly documents why it is required.

For legacy plans without Impact Map, continue normal review and note that contract comparison was skipped.

### Step 2: Choose Depth Strategy

Run `git diff --numstat | awk '{a+=$1; d+=$2} END {print a+d}'` to get total line count. If staged changes also exist, run `git diff --staged --numstat | awk '{a+=$1; d+=$2} END {print a+d}'` and add both counts. **Do not let AI choose** — apply this rule mechanically:

| Total diff lines | Strategy |
|---|---|
| < 200 lines | **Per-hunk**: read every file's full diff content. Analyze each hunk individually. |
| >= 200 lines | **Layered**: first read `git diff --stat` + file headers only. Identify key files (largest change count, public API surface changes, deleted files, files with `BREAKING` keywords). Then deep-dive only those key files with full diff. Summarize remaining files from stat/header level. |

Record which strategy was used in the report.

### Step 3: Read and Classify

Read the actual diff content by running `git diff` and `git diff --staged` (captured in Step 1b). For layered mode with large diffs, run `git diff <specific-file>` for each key file individually to keep output manageable.

For each logical change group, classify into exactly one category:

| Category | Definition | Key signals |
|---|---|---|
| **Enhancement** (增强) | Adds or improves existing capability | New function/type/feature, expanded API surface, improved behavior |
| **Fix** (修复) | Corrects wrong behavior | Bug fix, incorrect logic, edge case handling, null safety |
| **Refactor** (重构) | Restructures without changing behavior | Rename, extract function, move code, change internals |
| **Removal** (废弃/删除) | Deletes code or features | Deleted functions/files, removed options, dropped support |

Classification rules:
- If a change both fixes AND adds capability → Enhancement (the primary effect)
- If a change restructures AND fixes a bug → Fix (the bug was the motivation)
- If unsure between Enhancement and Refactor → read the surrounding context; if behavior changes → Enhancement
- Deleted code that was already dead (no callers) → Removal (cleanup)
- Deleted code that had callers → Removal + flag as risk

For each group, extract:
- **What changed**: concrete description from the diff (function signatures, logic changes, added/deleted code)
- **Why** (infer from code patterns — e.g., null check added → "prevent crash on nil input"; config value changed → "update default timeout")

### Step 4: Breaking Change Detection

Run these checks on every change group:

**4a. API surface scan (from diff)**

Scan added/removed lines for:
- Function signature changes: parameter added/removed, return type changed
- Type/interface changes: field removed, field type changed, enum case removed
- Public marker changes: `public` → `internal`/`private`, `export` removed
- Config key changes: renamed or removed keys
- Default value changes: changed defaults in function parameters or config

**4b. Residual caller grep (for removals and signature changes)**

For each removed or renamed symbol (function, type, enum case, exported constant):

1. Extract the symbol name from the deletion line
2. Grep the project for that symbol: `grep -rn "<symbol>" --include="<extensions>" . --exclude-dir=node_modules --exclude-dir=.git`
3. If grep returns hits outside the changed file → **breaking change**: list each caller file and line
4. If grep returns hits only in the changed file → not breaking (internal change)

Symbol extraction patterns by language:
- Swift: `func name(`, `class Name`, `struct Name`, `enum Name`, `case .name`, `var name:`, `let name:`
- TypeScript/JavaScript: `function name(`, `class Name`, `const name =`, `export`, `interface Name`
- Python: `def name(`, `class Name:`, `NAME =`
- Go: `func Name(`, `type Name`, `const Name`
- Rust: `fn name(`, `struct Name`, `enum Name`, `pub`, `const NAME`

**4c. Log findings**

Each breaking change found is a **risk item**. Record:
- Symbol removed/changed
- Caller files (with line numbers)
- Whether a migration path exists (new symbol replacing old? adapter? docs?)

### Step 5: Risk Assessment

Flag these patterns as risks (regardless of classification):

| Risk pattern | Check | Severity |
|---|---|---|
| Orphaned caller | Step 4b grep found callers of deleted symbol | 🔴 High |
| Incomplete rename | File A renamed symbol but file B still uses old name | 🔴 High |
| Silent behavior change | Logic changed without corresponding test change | 🟡 Medium |
| Dead code added | New code that appears unreachable or uncalled | 🟡 Medium |
| TODO/FIXME left in | Diff contains new TODO/FIXME/HACK | 🟡 Medium |
| Inconsistent pattern | Same kind of change applied to some files but not others that need it | 🟡 Medium |
| Test-only changes | Only test files changed, no source changes | 🟢 Info |

### Step 6: Generate Report

Run `mkdir -p .claude/reviews`, then write the report to `.claude/reviews/review-before-commit-{YYYY-MM-DD-HHmmss}.md`.

**Report template:**

```markdown
# Pre-Commit Review

**Date:** {timestamp}
**Branch:** {branch name}
**Depth strategy:** per-hunk | layered
**Total changes:** {N} files, +{A} -{D} lines

## Summary

| Category | Groups | Files |
|---|---|---|
| 🆕 Enhancement | {N} | file list |
| 🐛 Fix | {N} | file list |
| ♻️ Refactor | {N} | file list |
| 🗑️ Removal | {N} | file list |

## Detailed Analysis

### 🆕 Enhancements

#### 1. {title}
- **Files:** a.swift, b.ts
- **What changed:** {concrete description from diff}
- **What was enhanced:** {capability added or improved}
- **How:** {mechanism of enhancement}

(repeat for each enhancement group)

### 🐛 Fixes

#### 1. {title}
- **Files:** ...
- **What changed:** ...
- **What was fixed:** {the bug / incorrect behavior}
- **Root cause:** {inferred cause}

(repeat for each fix group)

### ♻️ Refactors

#### 1. {title}
- **Files:** ...
- **What changed:** ...
- **Behavior impact:** none / minimal (explain if minimal)

(repeat for each refactor group)

### 🗑️ Removals

#### 1. {title}
- **Files:** ...
- **What was removed:** ...
- **Replaced by:** {replacement, or "not replaced"}
- **Reason:** {unnecessary? superseded? why?}

(repeat for each removal group)

## ⚠️ Risk Items

{If no risks: "No risks detected."}

{If risks: list each with severity, description, and recommendation}

| # | Severity | Description | Recommendation |
|---|---|---|---|
| 1 | 🔴 High | ... | ... |
| 2 | 🟡 Medium | ... | ... |

## Breaking Changes

{If none: "No breaking changes detected."}

{If breaking: list each with affected callers and migration path}
```

### Step 7: Interactive Risk Confirmation

This step runs **only if risk items were found** in Step 5.

Collect all risk items with severity 🔴 High or 🟡 Medium (up to 4; if more than 4, take the top 4 by severity and note the rest in the report).

Present them in a **single** AskUserQuestion call with one question per risk. Use a shared header like "Risk audit" and multiSelect: false for each question:

```
Question: "#{N} [{severity}] {description}"
Options:
- "Fix now" — pause review, fix the issue, then re-run review
- "Acknowledged (intentional)" — mark as acknowledged, proceed
- "Ignore for now" — leave in report, continue
```

After receiving answers, update the report:
- "Fix now" risks: mark as "→ Fix required" in report
- "Acknowledged (intentional)" risks: mark as "Acknowledged — intentional"
- "Ignore for now" risks: leave as-is in report

If any risk was marked "Fix now", pause and tell the user: "Fix the marked risks, then re-run `/dev-workflow:review-before-commit`."

## Output Format

After completing the review, present a compact summary to the user:

```
Pre-commit review complete.

Changes: {N} files, +{A} -{D} lines
Enhancements: {N} | Fixes: {N} | Refactors: {N} | Removals: {N}

Risks: {N} (🔴 {high} / 🟡 {medium} / 🟢 {info})
Breaking changes: {N}

Report: .claude/reviews/review-before-commit-{timestamp}.md
Verdict: ✅ Clean / ⚠️ {N} risks need attention / ❌ {N} breaking changes
```

Then ask: "Proceed with `/commit`?"

## Edge Cases

**No changes:** Inform user: "Nothing to review — working tree and staging area are clean."

**Only staged changes:** Review staged only. Note in report: "All changes are staged."

**Only unstaged changes:** Review unstaged only. Note: "All changes are unstaged."

**Mixed staged/unstaged:** Review both. Label each change group with its source (staged/unstaged).

**Binary files:** Skip content analysis for binary files. Note them in the summary with size only.

**Merge commits in progress:** If `git status` shows merge conflict state, inform user: "Merge in progress — resolve conflicts before reviewing."

**Huge diff (>2000 lines):** After layered overview, select at most 10 key files for deep-dive. Note in report how many files were summary-only.

**No recognizable symbols for grep (Step 4):** Skip breaking change grep for that change group. Note: "Breaking change check skipped — no extractable symbols."

## Rules

- **Depth strategy is mechanical, not judgmental.** Apply the 200-line rule from Step 2 exactly. Never override based on "this looks important."
- **Don't guess intent.** Infer from code patterns, not from assumptions about what the developer "probably meant."
- **Grep before claiming breaking.** Never claim a change is breaking without grep evidence of residual callers.
- **Report is durable.** Always write the full report to `.claude/reviews/`. The terminal summary is a preview, not a substitute.
- **Risk interaction is blocking.** Don't proceed past Step 7 until all high/medium risks are resolved.
- **Pure review, no commit.** This skill does not commit, does not suggest commit messages, does not group for commit. That's the `commit` skill's job.

## Completion Criteria

- All diffs read and classified
- Breaking change grep executed for all removed/renamed symbols
- Risk items identified and assessed
- Full report written to `.claude/reviews/`
- All high/medium risks confirmed interactively (or none found)
- Summary displayed to user
