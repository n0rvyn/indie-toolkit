---
name: collab-health
description: "Use when the user says 'health', 'collaboration health', 'health score', 'how am I working with AI', or wants to see a score measuring AI collaboration quality."
user_invocable: true
model: haiku
---

## Overview

Show a 0-100 collaboration health score combining efficiency, quality, collaboration, and growth dimensions. Includes actionable recommendations for improvement.

## Arguments

- `--days N`: Time window (default: 7)
- `--from DATE`: Custom start date (ISO)
- `--to DATE`: Custom end date (ISO)
- `--project NAME`: Filter by project
- `--recommend`: Generate actionable recommendations (dispatches health-advisor agent)

## Process

### Step A: Check/Build Index

Same pattern as other session-intel skills:
1. Check `~/.claude/session-intel/index.json` freshness
2. If stale or missing: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build_index.py --days {max(days, 30)}`

### Step B: Aggregate by Day

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/aggregate.py \
  --index ~/.claude/session-intel/index.json \
  --days {days} \
  {--from-date DATE if specified} \
  {--to-date DATE if specified}
```

Save output to temp file.

### Step C: Check Data Sufficiency

- If 0 days: "No session data found. Run `/retro` first."
- If <3 days: Warn but proceed (growth scoring uses 50 as neutral)

### Step D: Compute Health Score

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/health_scorer.py --input {temp_aggregate_file}
```

Parse JSON output.

### Step E: Render Score Display

**Header:**
```
## Collaboration Health — Last {days} Days

### Overall Score: {score}/100

[████████████████░░░░░░░░ {score}] {status}
```

Status thresholds: 80-100 "Excellent", 60-79 "Good", 40-59 "Needs Attention", 0-39 "Critical"

**Dimension Breakdown:**

| Dimension | Score | Status | Key Metric |
|-----------|-------|--------|------------|
| Efficiency | {e}/100 | {status} | {turns} turns/session, {cache}% cache |
| Quality | {q}/100 | {status} | {build}% first-pass, {error}% error rate |
| Collaboration | {c}/100 | {status} | {corr} corrections/session |
| Growth | {g}/100 | {status} | {decay}% correction decay |

### Step F: Recommendations (if --recommend)

1. Read project CLAUDE.md (from current working directory or --project path)
2. Dispatch `session-intel:health-advisor` agent with:
   - Health score results
   - Daily aggregates
   - CLAUDE.md content (or "No CLAUDE.md found")
3. Append recommendations under "## Recommendations"

### Step G: Footer

```
Run with --recommend for detailed improvement suggestions.
Use --days 30 for more accurate growth scoring.
```

## Error Handling

- No index: "No session data. Run `/retro` or `/trends --days 30` first."
- Insufficient data: "Not enough data for meaningful score ({n} days). Try --days 30."
- health_scorer failure: "Failed to compute health score: {error}"
- health-advisor failure: Show score only, skip recommendations
- No CLAUDE.md: Continue without rule compliance, note in output
