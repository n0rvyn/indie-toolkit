---
name: verdict-refresh
description: "Use when prior product-lens conclusions need to be checked against new evidence. Produces delta-oriented judgments instead of full re-evaluations."
---

## Overview

`verdict-refresh` checks whether an earlier conclusion still holds after new evidence appears.

It answers:
- what the previous verdict was
- what new evidence changed
- whether the conclusion is unchanged, upgraded, downgraded, or reversed

Use this when prior verdict notes or reports exist.

## Inputs

```json
{
  "intent": "verdict_refresh",
  "project_root": "~/Code",
  "targets": ["~/Code/AppA"],
  "evidence_paths": [
    "~/Obsidian/PKOS/30-Projects/AppA/Verdicts/2026-04-01-AppA-verdict.md"
  ],
  "window_days": 14,
  "mode": "summary",
  "save_report": true,
  "sync_notion": false
}
```

## Process

### Step 1: Resolve Prior Verdict Inputs

Read explicit `evidence_paths` when provided.

If missing:
- search for the latest relevant verdict note or saved report for each target
- stop with a clear message when no prior verdict exists

### Step 2: Gather New Evidence

Collect new evidence from:
- recent repo facts via `repo-activity-scanner`
- recent feature reviews when available
- newer reports or notes referenced by the caller

### Step 3: Compare Old and New

Dispatch `verdict-delta-analyzer` with:
- prior verdict text
- old reasons
- new evidence bundle

Allowed decision values:
- `unchanged`
- `upgraded`
- `downgraded`
- `reversed`

### Step 4: Publish Exchange Artifacts

Use `ingress-publisher` with:
- `intent = verdict_refresh`
- prior verdict reference
- changed reasons
- updated next actions

Command shape:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/publish_exchange.py \
  --intent verdict_refresh \
  --project-root ~/Code \
  --target ~/Code/AppA \
  --project AppA \
  --window-days 14 \
  --decision upgraded \
  --confidence medium \
  --risk "Retention evidence is still unresolved." \
  --reason "The new evidence supports the earlier execution thesis." \
  --action "Re-check the verdict after the next validation cycle." \
  --evidence ~/Obsidian/PKOS/30-Projects/AppA/Verdicts/2026-04-01-AppA-verdict.md \
  --exchange-root ~/Obsidian/PKOS/.exchange/product-lens
```

Exchange target:

```text
~/Obsidian/PKOS/.exchange/product-lens/verdict-refresh/
```

### Step 5: Return Summary

Return the machine envelope first, then a delta report:

```markdown
# Verdict Refresh

## Previous Verdict
- ...

## New Evidence
- ...

## What Changed
- ...

## Updated Actions
- ...
```

## Rules

1. Compare against prior reasoning, not just prior label.
2. When the evidence barely moved, prefer `unchanged` with lower confidence.
3. Use refresh reports for deltas; use `evaluate` for full resets.
