---
name: health
description: "Use when the user says 'health', 'health insights', '我的健康', 'analyze my health data', '健康报告', or wants to interact with their personal health intelligence system. Unified entry point for status, ingest, baseline, analyze, predict, and report."
user-invocable: true
---

# Health Insights — Unified Entry Point

Plugin for personal health data ingestion, baseline establishment, trend analysis, and insight generation. Feeds into MongoDB (primary store) and optionally an Obsidian vault (downstream archive).

**All other health-insights skills are internal** (triggered by Adam scheduling or agents, not directly by users).

## Arguments

Parse from user input (natural language routing):

| User says | Route to | Description |
|-----------|----------|-------------|
| `/health` or `/health status` | health-ingest-agent (lightweight) | Check last sync state |
| `/health ingest` | health-ingest-agent | Adam trigger: parse XML delta to MongoDB |
| `/health baseline` | health-baseline-agent | Compute/update personal baselines |
| `/health analyze <topic>` | health-analyze-agent | Generate trend insights (includes calendar context enrichment when mactools available) |
| `/health analyze --weekly` | health-analyze-agent | Generate weekly correlation analysis |
| `/health digest` | health-analyze-agent | Weekly digest: Get笔记 save + IEF export + calendar context |
| `/health predict` | health-predict-agent | Run early warning evaluation (triggered daily by Adam cron; alerts delivered to WeChat) |
| `/health report <file>` | health-report-agent | Parse lab report |
| `/health trends <type>` | health-analyze-agent | Query specific metric trends |
| `/health annual <year>` | health-analyze-agent | Generate annual health report |
| `/health setup-delivery` | — | Print Adam delivery rule setup instructions |
| `/health --help` | — | Show this routing table |

## Routes

### Route: Status (default)

Query MongoDB for current state:
1. `db.metrics.count_documents({})` for total record count
2. `db.metrics.find_one(sort=[("timestamp", -1)])` for last ingest timestamp
3. `db.baselines.count_documents({})` for baseline count
4. `db.alerts.count_documents({"status": "active"})` for active alert count

Return a compact status:

```
Health Insights Status
  Records: 3,247,891
  Date range: 2024-03-15 → 2026-04-09
  Baselines: 24 computed
  Active alerts: 2
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
  mongo_uri: null      # defaults to $MDB_MCP_CONNECTION_STRING
  database: "health"
  notion_trends_db_id: "<notion_database_ids.trends from config>"
  notion_alerts_db_id: "<notion_database_ids.alerts from config>"
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
  mongo_uri: null
  database: "health"
  notion_trends_db_id: "<notion_database_ids.trends from config>"
  notion_workspace_page_id: "<notion_workspace_page_id from config>"
  # Note: calendar context enrichment is applied automatically when mactools is available
```

### Route: Predict

Trigger: `/health predict` or Adam evening schedule.

Dispatch `health-predict-agent`:
```yaml
input:
  action: "evaluate"   # or "acknowledge"
  alert_id: null
  mongo_uri: null
  database: "health"
  notion_alerts_db_id: "<notion_database_ids.alerts from config>"
```

### Route: Report

Trigger: `/health report <file path>`.

Dispatch `health-report-agent`:
```yaml
input:
  file_path: "/path/to/lab-report.pdf"
  file_type: null   # null = auto-detected from extension; "pdf" | "image" | "text"
  notion_reports_db_id: "<notion_database_ids.reports from config>"
  notion_lab_results_db_id: "<notion_database_ids.lab_results from config>"
```

### Route: Annual

Trigger: `/health annual <year>`.

Dispatch `health-analyze-agent`:
```yaml
input:
  action: "annual"
  year: "{YYYY}"
  notion_workspace_page_id: "<notion_workspace_page_id from config>"
```

### Route: Digest

Trigger: `/health digest`.

Dispatches the `weekly-digest` action which saves a health summary to Get笔记 and exports an IEF insight file for pkos.

Dispatch `health-analyze-agent`:
```yaml
input:
  action: "weekly-digest"
  database: "health"
  notion_trends_db_id: "<notion_database_ids.trends from config>"
```

### Route: Setup-Delivery

Trigger: `/health setup-delivery`.

Prints these setup instructions:

```
=== Adam Delivery Rule Setup ===
Health Insights uses Adam task templates (config/adam-task-templates.yaml) and
delivery rules to push summaries and alerts to WeChat.

1. Import templates: copy config/adam-task-templates.yaml to Adam's config dir
2. Create delivery rules via Adam Web UI or API:
   POST /delivery-rules

   Rule A — Daily summary to WeChat:
     name: health-daily-summary
     event: task_complete
     matchCriteria: { templateId: "health-daily-analyze" }
     targetChannel: <your_wechat_channel_id>
     skipOriginChannel: true

   Rule B — Alert push to WeChat:
     name: health-alert-to-wechat
     event: task_complete
     matchCriteria: { templateId: "health-predict" }
     targetChannel: <your_wechat_channel_id>
     skipOriginChannel: false

See: config/adam-task-templates.yaml for full API examples.
```

## Data Storage

Primary store: MongoDB `health` database (`metrics`, `baselines`, `alerts`, `lab_reports`, `checkpoint` collections).

Primary insights archive: Notion Health workspace (Trends DB, Alerts DB, Reports DB, Lab Results DB).

Optional downstream archive: Obsidian vault at `~/Obsidian/HealthVault/` (not required for operation; Notion is the primary record for analyzed data).

## Cross-Plugin Integration

| Target | Mechanism | Frequency | Data |
|--------|-----------|-----------|------|
| Get笔记 | getnote.sh save_note (via getnote_digest.sh) | Weekly (Monday 9am) | Aggregate health summary (~200 chars) |
| pkos | IEF markdown file export to `~/.adam/state/health-insights/ief-exports/` | Weekly | Health insight narrative; pkos intel-sync reads from that path |
| WeChat | Adam delivery rule (task_complete event) | Daily + on alert | Summary + alert text |
| Calendar | osascript query to Apple Calendar | On analyze | Event context for correlation (travel, exercise, overtime, social) |

## Agent I/O Convention

All agents receive YAML input and return YAML output via their tool definitions. The entry skill handles natural language → YAML routing.
