---
name: running-phase
description: "Use when the user says 'run phase', 'start phase N', 'next phase', or when continuing development guided by a dev-guide. Orchestrates the plan-execute-review cycle for one phase of a development guide."
---

## Overview

This skill orchestrates one iteration of the development cycle:

```
Locate Phase → /plan → [user approves] → execute → review → fix gaps → Phase done
```

It does not do the work itself. It coordinates the sequence and ensures nothing is skipped.

## Process

### Step 1: Locate Current Phase

1. Find the dev-guide: `docs/06-plans/*-dev-guide.md` (if multiple, ask user which one)
2. Read the document and check each Phase's acceptance criteria
3. Phases with all criteria checked = completed
4. Identify the first incomplete Phase
5. Present Phase summary:
   - Goal
   - Scope
   - Architecture decisions to make
   - Acceptance criteria
6. Ask: "Start Phase N?"

If the user specifies a different Phase number, use that instead.

### Step 2: Enter /plan Mode

This is the only step requiring manual user action.

Prompt the user:

> Phase N scope and acceptance criteria are clear. Enter `/plan` mode now.
>
> Context for the plan: "Based on `docs/06-plans/<project>-dev-guide.md` Phase N, plan the implementation. Scope: [list from Phase]. Acceptance criteria: [list from Phase]."

Wait for the user to approve the plan and for Claude to execute it.

When execution is complete (user confirms or the plan's tasks are done), proceed to Step 3.

### Step 3: Run Reviews

Based on the Phase's Review checklist, run reviews in sequence:

1. **Always:** `/execution-review`
2. **If Phase modified UI files:** `/ui-review`
3. **If Phase created new pages/components:** `/design-review`
4. **If Phase completed a full user journey:** `/feature-review`
5. **If this is the submission prep Phase:** `/submission-preview`

For each review:
- Invoke the command
- Collect the output
- Continue to the next review

After all reviews complete, present a consolidated summary of all findings.

### Step 4: Fix Gaps

If any review found issues:

1. List all gaps sorted by severity (red first, then yellow)
2. Ask the user: "Fix these gaps before moving on, or mark as known issues?"
3. If fixing: address the gaps, then re-run only the reviews that had failures
4. If skipping: note the known issues and proceed

### Step 5: Phase Completion

1. Update the dev-guide: check off this Phase's acceptance criteria
2. Remind the user to update project docs:
   - `docs/05-features/` — document completed features
   - `docs/07-changelog/` — record changes
   - `docs/03-decisions/` — if architectural decisions were made
3. Report:
   > Phase N complete.
   > Next: Phase N+1 — [name]: [goal].
   > Run `/run-phase` to continue, or `/commit` to save progress first.

## Rules

- **Never skip Step 3.** Reviews are not optional.
- **Never auto-approve the plan.** Step 2 requires explicit user action.
- **Phase order matters.** Don't start Phase N+1 if Phase N has unchecked acceptance criteria (unless user explicitly overrides).
- **Consolidate review output.** Don't dump 4 separate reports — merge into one summary with sections.
