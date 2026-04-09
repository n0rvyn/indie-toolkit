---
name: health
description: "Use when the user says 'health', 'health insights', '我的健康', 'analyze my health data', '健康报告', or wants to interact with their personal health intelligence system. Unified entry point for status, ingest, baseline, analyze, predict, and report."
user-invocable: true
model: sonnet
---

# Health Insights — Unified Entry Point

Plugin for personal health data ingestion, baseline establishment, trend analysis, and insight generation. Feeds into an independent Obsidian vault (HealthVault) and Notion workspace (Health).

**All other health-insights skills are internal** (triggered by Adam scheduling or agents, not directly by users).

## Arguments

Parse from user input (natural language routing):

| User says | Route to | Description |
|-----------|----------|-------------|
| `/health` or `/health status` | `health-ingest-agent` (lightweight) | Check iCloud watch folder + last sync state |
| `/health ingest` | `health-ingest-agent` | Adam trigger: parse XML delta → write vault |
| `/health baseline` | `health-baseline-agent` | Compute/update personal baselines |
| `/health analyze <topic>` | `health-analyze-agent` | Generate trend insights |
| `/health analyze --weekly` | `health-analyze-agent` | Generate weekly correlation analysis |
| `/health predict` | `health-predict-agent` | Run early warning evaluation |
| `/health report <file>` | `health-report-agent` | Parse体检报告/lab report |
| `/health trends <type>` | `health-analyze-agent` | Query specific metric trends |
| `/health annual <year>` | `health-analyze-agent` | Generate annual health report |
| `/health --help` | — | Show this routing table |

## Routes

### Route: Status (default)

Collect in parallel:

1. Check `~/.adam/state/health-insights/processing_state.yaml` for last sync time
2. Glob `~/Obsidian/HealthVault/daily/` for latest 3 daily entries
3. Check if Notion Trends DB has recent entries

Return a compact status:

```
Health Insights Status
  Last sync: 2026-04-09 08:00
  Vault: 2024-03-15 → 2026-04-09 (2.1 years)
  Recent: 3 daily entries this week
  Notion Trends: 1,247 records
  Alerts: 2 active
```

### Route: Ingest

Trigger: Adam watch folder event or manual `ingest` arg.

Dispatch `health-ingest-agent` with:
```yaml
input:
  source: "{path to XML file or iCloud delta directory}"
  resume_from_byte: 0
  processing_state: {}
```

### Route: Baseline

Trigger: `/health baseline` or Adam daily schedule.

Dispatch `health-baseline-agent`:
```yaml
input:
  action: "compute"   # or "update" for incremental
  metric_type: null    # null = all metrics
```

### Route: Analyze

Trigger: `/health analyze <topic>`.

Dispatch `health-analyze-agent`:
```yaml
input:
  action: "daily"   # or "weekly", "trend", "annual"
  date: "{YYYY-MM-DD}"
  topic: "{metric type or null}"
  year: null        # for annual
```

### Route: Predict

Trigger: `/health predict` or Adam evening schedule.

Dispatch `health-predict-agent`:
```yaml
input:
  action: "evaluate"   # or "acknowledge"
  alert_id: null
```

### Route: Report

Trigger: `/health report <file path>`.

Dispatch `health-report-agent`:
```yaml
input:
  file_path: "/path/to/lab-report.pdf"
  file_type: "pdf"   # or "image", "text"
```

## Vault Location

All health data is stored in `~/Obsidian/HealthVault/` (configurable in `config/defaults.yaml`).

## Agent I/O Convention

All agents receive YAML input and return YAML output via their tool definitions. The entry skill handles natural language → YAML routing.
