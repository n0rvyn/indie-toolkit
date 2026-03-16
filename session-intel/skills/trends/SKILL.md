---
name: trends
description: "Use when the user says 'trends', 'show trends', 'metrics over time', 'efficiency trends', or wants to see historical AI collaboration patterns and metric changes."
user_invocable: true
model: haiku
---

## Overview

Show cross-session trends with ASCII charts for efficiency, quality, and collaboration metrics over time.

## Arguments

- `--days N`: Time window (default: 7; common: 7, 30, 90)
- `--from DATE`: Custom start date (ISO)
- `--to DATE`: Custom end date (ISO)
- `--metric TYPE`: Focus on specific category: efficiency | quality | collaboration | all (default: all)
- `--project NAME`: Filter by project name
- `--analyze`: Enable LLM trend analysis (dispatches trend-analyzer agent)

## Process

### Step A: Check/Build Index

Same pattern as /session-search:
1. Check if `~/.claude/session-intel/index.json` exists and is recent
2. If stale or missing:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build_index.py --days {max(days, 30)}
   ```
3. Load index sessions

### Step B: Aggregate by Day

Run aggregation:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/aggregate.py --index ~/.claude/session-intel/index.json --days {days}
```

Parse the JSON output into daily aggregates.

### Step C: Check Data Sufficiency

- If 0 days of data: "No session data found. Run `/retro` first to start tracking sessions."
- If 1-2 days: "Not enough data for trends ({n} days found). Need at least 3 days. Try `--days 30` for wider range."
- If 3+ days: proceed to chart rendering

### Step D: Render Charts

Render all requested charts in a single script call:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_trends.py \
  --input {temp_aggregate_file} \
  --metric {metric}
```

This renders sessions/day, duration, cache hit rate, build pass rate, bash errors, corrections, and DNA distribution table — all in one call. Present the output directly.

### Step E: LLM Analysis (if --analyze)

Dispatch `session-intel:trend-analyzer` agent with:
- The daily aggregates array
- Time range info
- Project filter (if any)

Agent returns trends, anomalies, and recommendations. Append to output under "## Trend Analysis" header.

## Error Handling

- No index: "No session data found. Run `/retro` first to start tracking sessions."
- Insufficient data: "Not enough data for trends ({n} days). Need at least 3 days."
- chart_utils failure: Fall back to simple text table
- trend-analyzer failure: Skip analysis section, show charts only
- No sessions for project: "No sessions found for project '{name}' in the last {days} days."
