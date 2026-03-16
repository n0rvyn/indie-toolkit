---
name: cost-report
description: "Use when the user says 'cost', 'token cost', 'spend', 'cost report', 'token breakdown', or wants to see AI spending by project or model."
user_invocable: true
model: haiku
---

## Overview

Show token cost breakdown by project, model, and time period. Includes ROI correlation with git output.

## Arguments

- `--days N`: Time window (default: 7)
- `--project NAME`: Filter by project
- `--model NAME`: Filter by model
- `--breakdown TYPE`: project | model | all (default: all)

## Process

### Step A: Check/Build Index

Same as /session-search and /trends:
1. Check `~/.claude/session-intel/index.json` freshness
2. If stale or missing: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build_index.py --days {max(days, 30)}`

### Step B: Calculate Costs

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cost_calculator.py \
  --index ~/.claude/session-intel/index.json \
  --days {days} \
  {--project NAME if specified} \
  {--model NAME if specified}
```

Parse JSON output.

### Step C: Git Correlation (ROI)

For sessions with project_path:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/git_correlate.py \
  --sessions {temp file with session JSONs}
```

For each session with commits, get diff stats:
```bash
git -C {project_path} diff --stat {commit}^..{commit} 2>/dev/null
```

Compute ROI: cost per commit, cost per line changed.

If git correlation fails, skip ROI section.

### Step D: Render Report

**Section 1: Total Spend**
```
## Cost Report — Last {days} Days

Total: ${total_cost}
Sessions: {count} | Input: {input_tokens} | Output: {output_tokens} | Cache: {cache_read_tokens}
```

**Section 2: By Project** (if --breakdown project or all)
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/chart_utils.py \
  --data '{by_project as label=name, value=total_cost}' \
  --title "Cost by Project" --format currency
```

Also show table:
```
| Project | Sessions | Input | Output | Cache | Total |
|---------|----------|-------|--------|-------|-------|
| {name} | {n} | ${input_cost} | ${output_cost} | ${cache_cost} | ${total} |
```

**Section 3: By Model** (if --breakdown model or all)
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/chart_utils.py \
  --data '{by_model as label=model, value=total_cost}' \
  --title "Cost by Model" --format currency
```

**Section 4: Top Sessions** (always)
Show top 5 highest-cost sessions:
```
| # | Session | Project | Model | Duration | Cost |
|---|---------|---------|-------|----------|------|
| 1 | {id[:8]} | {project} | {model} | {duration} | ${cost} |
```

**Section 5: ROI** (if git data available)
```
| Project | Token Cost | Commits | Lines Changed | Cost/Commit |
|---------|-----------|---------|---------------|-------------|
| {name} | ${cost} | {n} | +{add}/-{del} | ${per_commit} |
```

## Error Handling

- No index: "No session data. Run `/retro` or `/trends --days 30` first."
- Zero cost: "No token data found in sessions for this period."
- No pricing for model: Use $0 and note "No pricing configured for model '{name}'"
- Git correlation failure: Skip ROI, show cost sections only
