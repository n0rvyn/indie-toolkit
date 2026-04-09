---
name: health-analyze-agent
description: |
  Generates daily health summaries (Haiku), narrative reports (Sonnet), weekly correlation analyses,
  and specific metric trend queries. Reads from HealthVault and writes summaries back to vault.

model: sonnet
tools: [Read, Glob, Bash, Write]
color: blue
maxTurns: 30
---

# health-analyze-agent

Generates structured summaries (Haiku), narrative reports (Sonnet), and trend analyses.

## Input

```yaml
input:
  action: "daily"           # "daily" | "weekly" | "trend" | "annual"
  date: "2026-04-09"       # YYYY-MM-DD for daily/weekly
  year: null               # for annual action
  topic: null               # for trend action (e.g. "heart_rate")
  vault_dir: "~/Obsidian/HealthVault"
```

## Output

```yaml
output:
  action: "daily"
  date: "2026-04-09"
  summary_written: "daily/2026-04-09/summary.yaml"
  narrative_written: "daily/2026-04-09/summary.md"
  recovery_score: 82
  deviation_flags:
    - metric: hrv_sdnn
      deviation: -18%
      severity: moderate
  alerts_emitted: []
```

## Actions

### `daily`

1. Call `summarize.py --date {date} --vault-dir {vault} --output /tmp/summary-context.yaml`
2. Call `narrate.py --date {date} --vault-dir {vault} --output /tmp/daily-context.yaml`
3. Read both context files
4. Use Sonnet to generate the narrative from the prompts in the context files
5. Write `daily/{date}/summary.yaml` (structured context)
6. Write `daily/{date}/summary.md` (narrative from Sonnet)
7. Sync key metrics to Notion Trends DB

### `weekly`

1. Call `narrate.py --date {date} --vault-dir {vault} --weekly --output /tmp/weekly-context.yaml`
2. Read the context file to get the correlation prompt
3. Use Sonnet to generate the weekly correlation analysis
4. Write `insights/YYYY-MM-DD-correlation-week-N.md`
5. Analyze: sleep quality vs HRV, training intensity vs recovery

### `trend`

1. Call `narrate.py --trend {topic} --vault-dir {vault} --output /tmp/trend-context.yaml`
2. Read the context file to get the trend prompt
3. Use Sonnet to generate a trend narrative
4. Write `trends/{topic}/summary.md`
5. Return inline to user

### `annual`

1. Call `annual_report.py --year {year} --vault-dir {vault}`
2. Read the generated `annual/{year}-context.yaml`
3. Use Sonnet to generate the annual narrative from the context
4. Write `annual/{year}.md` (narrative from Sonnet)
5. Write `annual/{year}-heatmap.json` (monthly averages per metric, from script)
