---
name: repo-reprioritize
description: "Use when the system must decide what to focus on next across multiple projects. Converts recent signals into portfolio decisions with blockers and next actions."
---

## Overview

`repo-reprioritize` turns recent project signals into portfolio decisions:
- `focus`
- `maintain`
- `freeze`
- `stop`

It is decision-oriented. Use it after or alongside `portfolio-scan` and `project-progress-pulse`, not instead of them.

## Inputs

```json
{
  "intent": "repo_reprioritize",
  "project_root": "~/Code",
  "targets": [],
  "window_days": 14,
  "mode": "summary",
  "save_report": true,
  "sync_notion": false
}
```

Optional inputs:
- prior signal note paths
- prior verdict note paths
- explicit candidate project list

## Process

### Step 1: Gather Current Inputs

Collect:
- latest exchange artifacts or PKOS note paths, if supplied
- fresh repo facts via `repo-activity-scanner` when current evidence is missing
- recent progress states from `project-progress-pulse` if available

### Step 2: Evaluate Portfolio Priority

For each project, judge:
- coherence of recent work
- evidence of shipping or validation movement
- risk of continued investment
- opportunity cost versus other active repos

Allowed decisions:
- `focus`
- `maintain`
- `freeze`
- `stop`

### Step 3: Explain the Priority Change

For each project include:
- current decision
- biggest blocker
- one or two next actions

When the evidence is thin, bias toward:
- `maintain`
- `freeze`

not toward overly confident `focus`.

### Step 4: Publish Exchange Artifacts

Dispatch `ingress-publisher` with:
- `intent = repo_reprioritize`
- per-project verdicts
- blockers
- next actions

Command shape:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/publish_exchange.py \
  --intent repo_reprioritize \
  --project-root ~/Code \
  --target ~/Code/AppA \
  --project AppA \
  --decision focus \
  --confidence medium \
  --risk "Demand evidence still lags implementation speed." \
  --reason "Recent work remains coherent around one core workflow." \
  --action "Run a narrow demand validation experiment." \
  --evidence ~/Code/AppA/README.md \
  --exchange-root ~/Obsidian/PKOS/.exchange/product-lens
```

Exchange target:

```text
~/Obsidian/PKOS/.exchange/product-lens/reprioritize/
```

### Step 5: Return Summary

Return the machine-readable envelope first, then a Markdown digest:

```markdown
# Repo Reprioritization

## Focus
- ...

## Maintain
- ...

## Freeze / Stop
- ...

## Next Actions
- ...
```

## Rules

1. Do not turn neutral comparisons into hard priority calls unless the request is explicitly about focus.
2. Tie every decision to concrete blockers or recent evidence.
3. Prefer smaller decisive actions over broad portfolio advice.
