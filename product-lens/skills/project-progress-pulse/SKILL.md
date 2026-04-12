---
name: project-progress-pulse
description: "Use when the system needs observable progress facts for one or more projects. Reports acceleration, stalls, and drift without claiming fake completion percentages."
---

## Overview

`project-progress-pulse` answers:
- how one or more projects are progressing
- whether momentum is increasing, steady, stalled, or drifting
- what concrete evidence supports that reading

It is narrower than `portfolio-scan` and more factual than `repo-reprioritize`.

## Inputs

```json
{
  "intent": "project_progress_pulse",
  "project_root": "~/Code",
  "targets": ["~/Code/AppA", "~/Code/AppB"],
  "window_days": 14,
  "mode": "summary",
  "save_report": true,
  "sync_notion": false
}
```

## Process

### Step 1: Resolve Target Projects

Prefer explicit `targets`.

If `targets` is empty:
- scan `project_root`
- keep only repositories with product markers
- stop if no candidates are found

### Step 2: Scan Observable Progress Indicators

Dispatch `repo-activity-scanner` per target and gather:
- recent file churn around user-visible areas
- test movement
- docs or launch-asset movement
- TODO/FIXME creation or reduction
- presence of monetization or distribution work

### Step 3: Classify Progress State

Allowed decision values:
- `accelerating`
- `steady`
- `stalled`
- `drifting`

Definitions:
- `accelerating`: multiple aligned progress signals on the same product direction
- `steady`: active, coherent movement without strong acceleration
- `stalled`: weak recent movement or mostly maintenance noise
- `drifting`: active changes exist, but they fragment focus or avoid core progress

### Step 4: Publish Exchange Artifacts

Use `ingress-publisher` with:
- `intent = project_progress_pulse`
- per-project pulse classification
- evidence bullets

Command shape:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/publish_exchange.py \
  --intent project_progress_pulse \
  --project-root ~/Code \
  --target ~/Code/AppA \
  --project AppA \
  --window-days 14 \
  --decision steady \
  --confidence medium \
  --risk "Shipping motion is visible, but monetization evidence is still weak." \
  --reason "Product files and docs moved in the same recent window." \
  --action "Check whether the next change set targets shipping readiness." \
  --evidence ~/Code/AppA/README.md \
  --exchange-root ~/Obsidian/PKOS/.exchange/product-lens
```

Exchange target:

```text
~/Obsidian/PKOS/.exchange/product-lens/progress-pulse/
```

### Step 5: Return Summary

Return the machine-readable envelope first, then a short Markdown report:

```markdown
# Project Progress Pulse

## Progress States
- AppA — accelerating
- AppB — drifting

## Evidence
- ...

## Suggested Follow-up
- ...
```

## Rules

1. Use progress states, not percent complete claims.
2. A noisy commit stream is not progress unless it strengthens a coherent direction.
3. If signals conflict, lower confidence instead of inventing certainty.
