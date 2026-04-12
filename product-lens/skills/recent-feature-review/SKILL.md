---
name: recent-feature-review
description: "Use when the system needs to judge recently built features or recent commit slices. Reviews whether recent work strengthens the core loop or creates drift."
---

## Overview

`recent-feature-review` answers:
- what likely feature slices changed recently
- whether those slices strengthen the core product loop
- whether the recent work should be doubled down on, polished, simplified, rethought, or dropped

Use this only for already-built or recently changed work.
If the question is still "should we build this feature?", route to `feature-assess`.

## Inputs

```json
{
  "intent": "recent_feature_review",
  "project_root": "~/Code",
  "targets": ["~/Code/AppA"],
  "window_days": 14,
  "mode": "summary",
  "save_report": true,
  "sync_notion": false
}
```

Optional:
- `feature` when the caller wants to constrain the review to one recent slice

## Process

### Step 1: Resolve Target Repositories

Use explicit `targets`.
If missing, derive candidates from `project_root`.

### Step 2: Gather Recent Change Context

For each target repository:
- inspect recent commit windows
- identify changed paths around user-visible flows, docs, tests, and monetization surfaces
- prepare a recent-change summary for clustering

### Step 3: Cluster Likely Feature Slices

Dispatch `feature-change-clusterer`.

The clusterer should group recent changes into likely feature slices using:
- path affinity
- commit-message affinity
- shared docs/tests/config movement

### Step 4: Review Each Slice

For each slice, judge:
- what user problem it appears to address
- whether it strengthens the core loop or creates a side branch
- whether the implementation footprint is getting too heavy
- whether more investment is justified

Allowed decision values:
- `double_down`
- `polish`
- `simplify`
- `rethink`
- `drop`

### Step 5: Publish Exchange Artifacts

Use `ingress-publisher` with:
- `intent = recent_feature_review`
- one artifact per project run or per feature slice
- slice label
- recommendation
- evidence bullets

Command shape:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/publish_exchange.py \
  --intent recent_feature_review \
  --project-root ~/Code \
  --target ~/Code/AppA \
  --project AppA \
  --feature "tagging system" \
  --window-days 14 \
  --decision polish \
  --confidence medium \
  --risk "The feature is coherent, but it may expand too quickly into side workflows." \
  --reason "Tagging strengthens note retrieval in the main workflow." \
  --action "Polish the current tagging flow before adding automation." \
  --evidence ~/Code/AppA/Sources/TaggingView.swift \
  --exchange-root ~/Obsidian/PKOS/.exchange/product-lens
```

Exchange target:

```text
~/Obsidian/PKOS/.exchange/product-lens/recent-feature-review/
```

### Step 6: Return Summary

Return the machine envelope first, then a compact report:

```markdown
# Recent Feature Review

## Feature Slices
- Tagging — polish
- AI sidebar — rethink

## Core Loop Impact
- ...

## Recommended Follow-up
- ...
```

## Rules

1. Judge what was built, not what was proposed.
2. Side branches should be called out directly.
3. Keep recommendation vocabulary normalized; put prose in reasons, not in decision values.
