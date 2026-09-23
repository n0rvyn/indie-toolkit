# Project Health Scanner

`dev-workflow/scripts/project_health_scan.py` gives high-frequency skills a bounded project health profile.

## Modes

- `light`: fast hook-safe checks; dirty count, context/rule files, workflow state, and prior scanner state.
- `full`: adds doc drift, large module detection, feedback-loop hints, source/test pressure, and active churn.

## Signals

| Signal | Meaning |
|---|---|
| `doc_drift` | Conflicting or missing project context/rule documents |
| `module_size` | Large source files that raise change risk (note: this measures size, not Ousterhout's "deep modules" concept where deep = good) |
| `feedback_loop` | Test and workflow state health |
| `test_pressure` | Source/test ratio pressure |
| `active_churn` | Dirty worktree and changed-file pressure |

## State Contract

`--write-state` writes only to:

```text
{project_root}/.claude/dev-workflow-health.json
```

Corrupt state is ignored and reported as a warning. Scanner default mode is read-only.
