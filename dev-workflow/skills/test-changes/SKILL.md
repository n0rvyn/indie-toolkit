---
name: test-changes
description: "Use when the user says 'test changes', 'run tests', 'test the build', or after execute-plan completes in a run-phase. Dispatches a sonnet agent to run the project's build/test/lint suite and returns a filtered report with errors only."
---

## Overview

This skill dispatches the `dev-workflow:test-runner` agent (sonnet) to run the project's full build, test, and lint suite. The agent detects the project type automatically or reads `.claude/test-config.yml` for custom commands. Output is filtered to errors with context lines, summary, and return codes — full logs stay out of main context.

## Process

### Step 1: Dispatch Agent

Use the Agent tool to dispatch the `dev-workflow:test-runner` agent:

```
Run the project's build, test, and lint suite.

Project root: {project root}
Plan file: {plan file path, or "none" if standalone}
```

### Step 2: Process Results

When the agent returns:

1. Read the report file from the agent's `Report written to:` path
   - If no path in return message: search `.claude/test-reports/test-run-*.md`, use the most recent file
   - If no report file found: fall back to parsing the agent's return message
2. Present summary to user:
   - Build: PASS/FAIL
   - Tests: X/Y passed (Z failed)
   - Lint: PASS/FAIL/SKIPPED
3. If any failures: show the filtered error output from the report (already filtered by the agent — do not re-filter)

**Standalone mode** (not within run-phase):
- If all pass: "All build, test, and lint checks pass."
- If failures: present errors and suggest fixing in main context

## State Integration

When running within a phase orchestrated by `run-phase`:

If `.claude/dev-workflow-state.yml` exists:
- After agent returns, do NOT update `phase_step` (orchestrator owns state transitions)
- Output the report path for run-phase to read
- Output: "Test run complete. Returning to run-phase."

## Completion Criteria

- Test runner agent dispatched and returned
- Report reviewed and summary presented to user
- When in run-phase context: report path output for orchestrator
- When standalone: results and suggestions presented
