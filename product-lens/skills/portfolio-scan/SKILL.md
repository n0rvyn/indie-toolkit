---
name: portfolio-scan
description: "Use for periodic scans over a project root such as ~/Code. Builds a root-level picture of active projects, current risks, and PKOS exchange artifacts for downstream ingestion."
---

## Overview

`portfolio-scan` is the root AI-facing periodic skill for `product-lens`.

It answers:
- what projects exist under a root directory
- which ones are active
- which ones appear stalled or drifting
- which ones deserve follow-up scans or reprioritization

It does not produce fake completion percentages. It records observable facts first, then emits a compact portfolio summary and exchange artifacts for PKOS.

## Inputs

Expected structured input:

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

## Process

### Step 1: Resolve Candidate Repositories

Use `targets` if provided.

Otherwise discover repositories under `project_root` using lightweight indicators:
- `.git/`
- `.xcodeproj` or `.xcworkspace`
- `Package.swift`
- `package.json`
- `pubspec.yaml`
- `README.md`

Ignore obvious non-project directories such as:
- `node_modules`
- `.build`
- `DerivedData`
- `dist`
- `build`

### Step 2: Gather Repo Facts

Dispatch `repo-activity-scanner` for each candidate repository.

The agent should return facts only:
- repo identity
- recent activity markers
- presence of docs, tests, monetization, launch assets, TODO/FIXME density
- confidence penalties when evidence is sparse

### Step 3: Build Portfolio Signals

For each repository, summarize:
- activity state
- delivery posture
- drift indicators
- biggest current risk
- whether the repo should be watched more closely

Allowed portfolio-scan decision values:
- `focus`
- `maintain`
- `freeze`
- `stop`
- `watch`

When evidence is weak, prefer:
- lower confidence
- `watch`

Do not force a hard verdict when the repo lacks enough signal.

### Step 4: Publish Exchange Artifacts

Dispatch `ingress-publisher` with:
- `intent = portfolio_scan`
- the portfolio-level summary
- per-project signal summaries
- requested persistence flags

Command shape:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/publish_exchange.py \
  --intent portfolio_scan \
  --project-root ~/Code \
  --decision watch \
  --confidence medium \
  --risk "Evidence is still sparse across most repos." \
  --reason "Only a subset of repos show coherent recent product movement." \
  --action "Run project_progress_pulse on the top active repos." \
  --evidence ~/Code \
  --exchange-root ~/Obsidian/PKOS/.exchange/product-lens
```

Artifact target:

```text
~/Obsidian/PKOS/.exchange/product-lens/portfolio-scan/
```

Do not select final PKOS vault destinations here.

### Step 5: Return Summary

Return the machine-readable summary first:

```json
{
  "decision": "watch",
  "confidence": "medium",
  "why": ["reason 1", "reason 2"],
  "biggest_risk": "one-line risk",
  "next_actions": ["action 1", "action 2"],
  "source_note_paths": ["exchange artifact paths"]
}
```

Then return a Markdown digest:

```markdown
# Portfolio Scan

## Focus Candidates
- ...

## At Risk
- ...

## Follow-up
- ...
```

## Rules

1. Facts first. Activity and status claims must come from observable repo signals.
2. No fake percentages. Never output "70% done" or similar.
3. Sparse evidence means low confidence, not confident prose.
4. Exchange artifacts come before PKOS ingestion; preserve the boundary.
