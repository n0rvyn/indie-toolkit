# Product Lens AI Entry Contract

This document defines how `product-lens` should be invoked by humans and by other AI systems.

## Human Entry

Humans should enter through natural-language product questions. The router is responsible for intent detection.

Examples:
- "Is this idea worth pursuing?"
- "Should I build this feature?"
- "Which project should I focus on?"
- "I got new evidence; should I change my decision?"

## AI Entry

AI systems should use a stable structured contract instead of free-form phrasing.

### Input Envelope

```json
{
  "intent": "portfolio_scan",
  "project_root": "~/Code",
  "targets": [],
  "window_days": 14,
  "mode": "summary",
  "save_report": true,
  "sync_notion": false
}
```

### Required Fields

| Field | Type | Meaning |
|---|---|---|
| `intent` | string | Which `product-lens` capability to run |
| `project_root` | string | Root directory used for repository discovery or relative path resolution |
| `mode` | string | `summary` or `full_report` |
| `save_report` | boolean | Whether to persist Markdown outputs |
| `sync_notion` | boolean | Whether downstream systems should attempt Notion summary sync |

### Optional Fields

| Field | Type | Meaning |
|---|---|---|
| `targets` | array | Explicit project paths, app names, feature names, or note paths |
| `window_days` | integer | Activity window for scans, feature reviews, and verdict refresh |
| `feature` | string | Proposed or recently built feature description |
| `evidence_paths` | array | Markdown or report files to compare during verdict refresh |
| `platform` | string | Optional platform override when auto-detection is ambiguous |

## Allowed AI Intents

### `portfolio_scan`

Use when the system needs a root-level picture of active projects under a directory.

Trigger when:
- multiple repositories need a current-state snapshot
- a periodic job wants fresh portfolio signals
- no single project or feature is the only focus

Do not trigger when:
- the user is asking to build or fix code
- there is only one clearly specified project and the task is feature-level

### `project_progress_pulse`

Use when the system needs observable progress facts for one or more projects.

Trigger when:
- the question is "how are these projects progressing?"
- the output should focus on recent activity, test movement, TODO movement, or shipping readiness

Do not trigger when:
- the task is about market demand or app-store positioning only

### `repo_reprioritize`

Use when the system needs a fresh portfolio priority ordering.

Trigger when:
- the question is "what should I focus on next?"
- multiple projects compete for attention
- previous verdicts may no longer match recent evidence

Do not trigger when:
- the user wants a neutral comparison without decisions

### `recent_feature_review`

Use when the system should evaluate recently implemented or recently changed features.

Trigger when:
- the question mentions "recent features", "recent commits", or "what did we just build?"
- there is a recent-commit window to inspect

Do not trigger when:
- the feature has not been built yet and the question is still "should we build it?"

### `verdict_refresh`

Use when the system should compare old conclusions with new evidence.

Trigger when:
- prior reports or verdict notes exist
- the question mentions "new evidence", "still true?", or "should I change the decision?"

Do not trigger when:
- there is no prior verdict to refresh

## Output Envelope

All AI-facing skills should emit this machine-readable summary before any long-form Markdown report:

```json
{
  "decision": "focus",
  "confidence": "medium",
  "why": [
    "Recent activity is concentrated in one coherent product area",
    "The latest feature work reinforces the core loop",
    "Business validation remains weaker than execution progress"
  ],
  "biggest_risk": "Demand evidence still trails implementation speed.",
  "next_actions": [
    "Run a targeted demand validation test for the current focus project",
    "Avoid adding side-branch features in the next 14 days"
  ],
  "source_note_paths": [
    "~/Obsidian/PKOS/30-Projects/AppA/Signals/2026-04-12-progress.md"
  ]
}
```

### Output Field Rules

| Field | Type | Rule |
|---|---|---|
| `decision` | string | Stable normalized verdict keyword, not prose |
| `confidence` | string | `high`, `medium`, or `low` |
| `why` | array | 1-3 concise reasons grounded in evidence |
| `biggest_risk` | string | The most important unresolved downside |
| `next_actions` | array | 1-3 concrete follow-up actions |
| `source_note_paths` | array | Markdown fact notes produced or consulted by the run |

## Decision Vocabulary

Use these normalized decision values:

| Intent | Allowed Decisions |
|---|---|
| `portfolio_scan` | `focus`, `maintain`, `freeze`, `stop`, `watch` |
| `project_progress_pulse` | `accelerating`, `steady`, `stalled`, `drifting` |
| `repo_reprioritize` | `focus`, `maintain`, `freeze`, `stop` |
| `recent_feature_review` | `double_down`, `polish`, `simplify`, `rethink`, `drop` |
| `verdict_refresh` | `unchanged`, `upgraded`, `downgraded`, `reversed` |

## Mode Rules

- `summary`: return the output envelope first, then a short Markdown digest
- `full_report`: return the output envelope first, then the full report body and note paths

## Persistence Rules

- `product-lens` does not write directly to final PKOS vault note destinations.
- It writes structured exchange artifacts for PKOS ingestion.
- PKOS remains responsible for canonical tagging, final note placement, deduplication, and downstream sync handling.
