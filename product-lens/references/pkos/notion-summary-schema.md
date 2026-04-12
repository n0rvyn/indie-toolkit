# Product Lens Notion Summary Schema

This document defines the management-view contract for syncing `product-lens` outputs into Notion.

## Source of Truth

- Local Markdown notes remain the source of truth.
- Notion is a summary projection for status tracking, sorting, and dashboards.
- Notion rows must always link back to the Markdown note path that produced them.

## Database Scope

V1 uses two logical row shapes:
- project-level summary rows
- feature-level summary rows

These can live in one database with a `row_type` property, or in two separate databases with the same shared fields.

## Shared Fields

| Field | Type | Meaning |
|---|---|---|
| `Title` | title | Human-readable row title |
| `source_note_id` | rich_text | Stable PKOS note identifier or filename slug used for re-sync |
| `row_type` | select | `project` or `feature` |
| `project` | rich_text or relation | Project name |
| `decision` | select | Normalized verdict value from the AI contract |
| `confidence` | select | `high`, `medium`, `low` |
| `priority` | select | Optional management priority such as `now`, `next`, `later` |
| `biggest_risk` | rich_text | One-line primary downside |
| `next_actions` | rich_text | Compact action list or joined string |
| `source_note_path` | url or rich_text | Absolute or vault-relative Markdown source path |
| `source_note_type` | select | `signal`, `verdict`, `feature-review`, `crystal` |
| `updated_at` | date | Last time the row was refreshed |
| `sync_status` | select | `current`, `stale`, `failed`, `pending` |

Required identity rule:
- `source_note_id` + `source_note_path` must uniquely identify the Markdown source
- Notion rows are replaceable projections, not independent records

## Project-Level Fields

Use when `row_type = project`.

| Field | Type | Meaning |
|---|---|---|
| `project_state` | select | `focus`, `maintain`, `freeze`, `stop`, `watch`, `steady`, `stalled`, etc. |
| `window_days` | number | Activity window used for the judgment |
| `project_root` | rich_text | Root path used during the scan |
| `producer_intent` | select | `portfolio_scan`, `project_progress_pulse`, `repo_reprioritize`, `verdict_refresh` |

## Feature-Level Fields

Use when `row_type = feature`.

| Field | Type | Meaning |
|---|---|---|
| `feature_name` | rich_text | Reviewed feature or feature slice |
| `feature_state` | select | `double_down`, `polish`, `simplify`, `rethink`, `drop` |
| `commit_window_days` | number | Recent commit window used during review |
| `producer_intent` | select | `recent_feature_review` |

## Mapping Rules

### From `signal`

- Populate `decision`, `confidence`, `biggest_risk`, `next_actions`
- Mark `source_note_type = signal`
- Use `sync_status = current` only if the row reflects the latest signal for that project

### From `verdict`

- Populate the same shared fields
- Mark `source_note_type = verdict`
- Prefer verdict rows over signal rows when both exist for the same project and timeframe

### From `feature-review`

- Set `row_type = feature`
- Populate `feature_name`, `feature_state`, `commit_window_days`
- Mark `source_note_type = feature-review`

### From `crystal`

- Only sync when a stable strategic decision should appear in management views
- Mark `source_note_type = crystal`
- Use `sync_status = current` until a newer verdict supersedes it

## Sync Status Semantics

| Value | Meaning |
|---|---|
| `current` | Row reflects the latest known Markdown note |
| `stale` | Markdown changed after the last successful sync |
| `pending` | Sync requested but not completed yet |
| `failed` | A sync attempt failed; Markdown remains authoritative |

## Failure Handling

- If Notion update fails, do not delete or rewrite Markdown notes.
- Mark the corresponding sync record as `failed` or leave the previous row `stale`.
- Never let Notion become the only surviving copy of a verdict.

## Minimal Row Example

```json
{
  "Title": "AppA weekly verdict",
  "source_note_id": "2026-04-12-AppA-verdict",
  "row_type": "project",
  "project": "AppA",
  "decision": "focus",
  "confidence": "medium",
  "biggest_risk": "Demand evidence still trails implementation speed.",
  "next_actions": "Run a targeted demand test; avoid side-branch features",
  "source_note_path": "~/Obsidian/PKOS/30-Projects/AppA/Verdicts/2026-04-12-AppA-verdict.md",
  "source_note_type": "verdict",
  "updated_at": "2026-04-12",
  "sync_status": "current"
}
```

## Projection Rules

- `product-lens` may request a Notion sync, but it does not write the row directly.
- PKOS note content stays authoritative even when `sync_status = failed` or `stale`.
- A row refresh must read the latest Markdown note path first, then update Notion fields.
