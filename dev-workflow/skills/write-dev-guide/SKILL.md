---
name: write-dev-guide
description: "Use when starting a new project's development after design is approved, or the user says 'write dev guide', 'break down this project into phases', or '写开发指南'. Creates a phased, project-level development guide that serves as the cornerstone document for all subsequent /write-plan and /run-phase cycles. Not for single-feature plans (use write-plan) or design exploration (use brainstorm)."
---

## Overview

This skill dispatches the `dev-workflow:dev-guide-writer` agent to create a phased development guide in a separate context so it starts with a fresh, unbiased perspective.

## Not This Skill

- Single feature plan → use `dev-workflow:write-plan`
- Per-phase implementation details → use `/write-plan`
- Design exploration → use `dev-workflow:brainstorm`

## Process

### Step 1: Gather Context

Collect the following before dispatching:

1. **Project root** — current working directory
2. **Design doc path** — search `docs/06-plans/*-design.md`
3. **Project brief path** — check `docs/01-discovery/project-brief.md`
4. **Architecture docs path** — check `docs/02-architecture/`

If no project-brief or design doc exists, inform the user and suggest running the corresponding workflow first. Do not dispatch without these inputs.

### Step 1.5: Check for Existing Dev-Guide

Before dispatching the agent, check if a dev-guide already exists:

1. Glob `docs/06-plans/*-dev-guide.md`
2. If one or more files found: record them as `existing_dev_guides`
3. If no files found: skip to Step 2

### Step 2: Dispatch Agent

Use the Task tool to launch the `dev-workflow:dev-guide-writer` agent with all gathered context. Structure the task prompt as:

```
Create a phased development guide with the following inputs:

Project root: {path}
Design doc: {path}
Project brief: {path or "none"}
Architecture docs: {path or "none"}
```

When the agent returns: note the dev-guide file path from the agent's summary.

### Step 2.5: Mark Old Dev-Guide as Superseded

After the agent writes the new dev-guide:

1. If `existing_dev_guides` is empty: skip this step
2. For each path in `existing_dev_guides`:
   a. Read the file
   b. Check if it starts with YAML frontmatter (first line is `---`)
   c. If frontmatter exists: find the `current:` field and change its value to `false`
   d. If no frontmatter exists (older file without frontmatter): skip this file (do not add frontmatter to files that weren't written with it)
   e. Write the updated file back
3. Report: "Marked {N} existing dev-guide(s) as `current: false`: {paths}"

### Step 2.7: Quality Verification

After the dev-guide is written and old guides are superseded:

1. Dispatch the `dev-workflow:dev-guide-verifier` agent with:
   - Dev-guide file path (noted from Step 2 agent return summary)
   - Design doc path (from Step 1)
   - Project brief path (from Step 1)
   - Architecture docs path (from Step 1)
   - Project root
   - Previously resolved decisions: none (decisions are resolved in Step 3, after verification)

2. Read the agent's compact summary.

3. If verdict is `approved`:
   - Report: "Quality verification passed."
   - Proceed to Step 3.

4. If verdict is `must-revise`:
   a. **V7 (Structural) issues**: directly Edit the dev-guide file to fix (frontmatter fields, missing sections, section markers — mechanical fixes only)
   b. **V1-V6 issues**: collect all revision items into a revision instruction block
   c. Re-dispatch `dev-workflow:dev-guide-writer` agent with the original prompt + revision instructions from the verifier. Max 1 revision cycle.
   d. After revision: re-run V7 check only (structural, in main context — verify frontmatter fields, required sections, section markers) to confirm mechanical fixes. Do NOT re-dispatch the verifier agent.
   e. If V1-V6 issues persist after the single revision cycle: note the unresolved items and present them to the user in Step 3 alongside the Phase outline, so the user can decide whether to accept or manually adjust.
   f. If the verifier produced Decisions (DP-xxx entries): carry them forward to Step 3, where they will be presented alongside the dev-guide's own decisions.

### Step 3: Structural Review

When the agent completes (and Step 2.7 passes or revision is done):

1. Read the dev-guide file the agent created
2. Extract the Phase outline and present as an overview table:

| Phase | Goal | Dependencies |
|-------|------|-------------|
| Phase 1 | {goal} | None |
| Phase 2 | {goal} | Phase 1 |
| ... | ... | ... |

3. **Decision Points:**
   **Ordering constraint:** The Phase outline table (step 2 above) must be presented to the user BEFORE any decision points. Do not reorder.
   - Collect decisions from two sources:
     a. Read the `## Decisions` section from the dev-guide file
     b. If Step 2.7 produced verifier Decisions, include those as well (prefix verifier DPs with `[V]` to distinguish source)
   - If both sources have `None.` content, skip to step 4. Otherwise, merge all `### [DP-xxx]` entries. Present blocking decisions first (regardless of source), then recommended.
   - Process each `### [DP-xxx]` entry:
   - **Comparison table** (all decisions): extract from the decision's `**Options:**` lines, keeping each option's `{description} — {trade-off}` as-is in one column:

     ### [DP-xxx] {title}

     **Context:** {from decision}

     | 方案 | 描述与代价 |
     |------|-----------|
     | A | {description} — {trade-off} |
     | B | {description} — {trade-off} |

   - **Recommendation line**: only for `recommended` decisions, append `**推荐:** {option} — {reason}` after the table. For `blocking` decisions, omit this line.
   - **AskUserQuestion**: for `recommended` decisions, mark the recommended option with "(推荐)" in the label. For `blocking` decisions, do not pre-select any option.
   - Record user choices: edit the dev-guide file, replace the `**Recommendation:**` or `**Recommendation (unverified):**` line with `**Chosen:** {user's choice}`
4. Ask user (AskUserQuestion): **确认结构** / **调整结构**（reorder, merge, split）
5. If user chooses「调整结构」:
   - Re-dispatch the agent with structural revision instructions appended to the original prompt
   - Re-read output, re-present table, repeat until user confirms

### Step 4: Phase Details Review

Display all Phase details in one block, then confirm once.

1. For each Phase i = 1..N, present a detail table:

**Phase {i}: {goal}**

| 维度 | 内容 |
|------|------|
| 前置依赖 | {dependencies} |
| 范围项 | {scope items, bulleted} |
| 用户可见的变化 | {from dev-guide, or "无 — 纯基建阶段"} |
| 关键文件/组件 | {key files and components} |
| 待定架构决策 | {architecture decisions to resolve, or "无"} |
| 验收标准 | {acceptance criteria} |

2. After ALL Phase tables are displayed, ask user (AskUserQuestion): **整体确认** / **指定调整**
3. If user chooses「指定调整」:
   - User specifies which Phase(s) to change and what to change (scope, visual expectations, architecture decisions, or any combination)
   - **Content adjustments** (move scope items between Phases, edit visual expectations, resolve architecture decisions, adjust acceptance criteria): directly Edit the dev-guide file in main context. After editing, sync acceptance criteria if scope changed (same logic as run-phase Step 1.5: flag criteria referencing removed items, flag new items lacking criteria)
   - **Structural changes** (merge Phases, split a Phase, add/remove a Phase): re-dispatch the agent with revision instructions. Re-read output and re-present all Phases from step 1
   - After content adjustments, re-present only the modified Phase table(s) for confirmation, not the full list
   - Max 2 adjustment cycles; after that, proceed with last-confirmed content
4. User confirms → proceed to Step 5.

### Step 4.5: Mark Confirmation Timestamp

After user confirms in Step 4, update the dev-guide file's YAML frontmatter:

1. Read the dev-guide file's first lines (frontmatter block between `---` markers)
2. If a `confirmed_at:` field exists: update its value to current ISO timestamp
3. If no `confirmed_at:` field: add `confirmed_at: YYYY-MM-DDTHH:MM:SS` after the `current:` field
4. Write back the file

This timestamp is consumed by run-phase Step 1.5 to avoid redundant scope confirmation.

### Step 5: Next Steps

After user confirms:

> Development guide saved. Use `/run-phase` to start the Phase 1 development cycle (plan → execute → review).

## Completion Criteria

- Dev-guide file saved to `docs/06-plans/`
- Quality verification passed or revision completed (Step 2.7)
- Structure confirmed by user (Step 3)
- Phase details reviewed and confirmed by user (Step 4)
- Previous dev-guide(s) marked `current: false` (Step 2.5)
- Next step (run-phase) communicated
