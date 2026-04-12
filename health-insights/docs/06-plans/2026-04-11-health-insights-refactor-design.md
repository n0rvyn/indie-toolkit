---
type: design
status: active
tags: [health-insights, mongodb, plugin-refactor, visualization]
refs: [docs/11-crystals/2026-04-11-health-insights-refactor-crystal.md]
---

# Health-Insights Plugin Refactor — Design Document

Date: 2026-04-11

## Problem Statement

The health-insights plugin has 3 fundamental architecture flaws that render the entire pipeline non-functional:

1. **Storage layer broken**: ingest writes 20GB of .tmp files to Role workspace (wrong path), finalize never executes, downstream pipeline has zero usable data
2. **LLM API anti-pattern**: scripts build prompts and call external LLM APIs (Haiku/Sonnet), but this is a Claude Code plugin — the host session IS the LLM
3. **File-based storage unsuitable**: no time-range queries, no aggregation pipeline, unbounded growth with no capacity control

The server crashed (ENOSPC) due to flaw #1 filling the disk.

## Target Architecture

```
Apple Health XML / iCloud Delta
        │
        ▼
   ingest.py (SAX parse → pymongo upsert)
        │
        ├──▶ MongoDB (Time-Series Collections)     ◄── primary storage + query
        │         │
        │         ├──▶ Notion Health DBs             ◄── structured reports + chart views
        │         │     (via Notion MCP tools)
        │         │
        │         ├──▶ Grafana Cloud                 ◄── time-series dashboards
        │         │     (MongoDB data source)
        │         │
        │         ├──▶ Get笔记                       ◄── weekly digest → semantic recall
        │         │     (via getnote.sh save_note)
        │         │
        │         ├──▶ Obsidian HealthVault          ◄── daily markdown archive
        │         │     (downstream consumer only)
        │         │
        │         └──▶ Adam Delivery Rules           ◄── WeChat push (alerts + summaries)
        │
        └──▶ MongoDB checkpoint doc (singleton, atomic)
```

### Layer Responsibilities

| Layer | Responsibility | Tools |
|-------|---------------|-------|
| scripts/ | Data I/O: parse, transform, aggregate, MongoDB write | pymongo, SAX parser, Python stdlib |
| agents/ | Reasoning: analysis, narration, prediction, report generation | MongoDB MCP (query), Notion MCP (write/visualize), Claude Code Read (PDF) |
| skills/ | Routing: user entry, parameter parsing, dispatch to agents | SKILL.md routing table |

**Key principle**: scripts do not know LLM exists. All `build_*_prompt()` and model-name references are removed. Agents receive structured data from scripts and do reasoning in the host Claude Code session.

## Data Model — MongoDB Collections

### Database: `health`

#### 1. `metrics` (Time-Series Collection)

Stores all health metric readings including raw per-record data.

```javascript
// Time-Series config
{
  timeseries: {
    timeField: "timestamp",
    metaField: "metadata",
    granularity: "seconds"   // heart rate is per-second granularity
  }
}

// Document schema
{
  timestamp: ISODate("2026-03-30T00:24:31+08:00"),
  metadata: {
    metric: "heart_rate",     // from TYPE_MAP normalization
    source: "apple_watch",    // apple_watch | icloud_delta | manual | lab_report
    unit: "bpm"
  },
  value: 48,
  // Optional fields (present when available from source)
  device: "Watch7,5",
  end_date: ISODate("...")   // for duration-based metrics (sleep, workout)
}
```

**Indexes**:
- Time-series default (timestamp + metadata)
- `{ "metadata.metric": 1, timestamp: -1 }` — metric-specific range queries

**Storage estimate (1 year, Atlas Free Tier test)**:
- Heart rate: 27K records/day × 365 × ~30 bytes (bucketed) ≈ 290 MB
- Other 11 metrics: ~20 MB
- Total: ~310 MB (fits in 512 MB free tier)

**Scaling path**: If data exceeds free tier, user deploys self-hosted MongoDB (connection string swap, no code change).

#### 2. `baselines`

```javascript
{
  metric: "heart_rate",
  computed_at: ISODate("2026-04-11"),
  window_days: 90,
  stats: {
    mean: 71.2,
    std: 8.4,
    min: 52,
    max: 158,
    count: 2430,
    p25: 64,
    p75: 82
  },
  trend: "stable",        // rising | falling | stable
  trend_pct: -1.2,
  unit: "bpm"
}
```

**Index**: `{ metric: 1, computed_at: -1 }` — latest baseline per metric

#### 3. `alerts`

```javascript
{
  date: ISODate("2026-04-11"),
  rule_id: "hrv_low_3d",
  severity: "moderate",      // mild | moderate | severe
  status: "active",          // active | acknowledged | resolved
  trigger_values: [28, 31, 29],
  baseline_mean: 42,
  deviation_pct: -33,
  acknowledged_at: null,
  resolved_at: null
}
```

**Index**: `{ status: 1, date: -1 }`

#### 4. `lab_reports`

```javascript
{
  date: ISODate("2026-04-11"),
  hospital: "和睦家",
  report_type: "annual",     // annual | quarterly | specialty | emergency
  metrics: [
    {
      name: "HbA1c",
      key: "hba1c",
      value: 5.8,
      unit: "%",
      reference_range: "4.0-6.0",
      status: "normal",       // normal | borderline | abnormal
      context: "fasting"      // fasting | post_meal | morning | evening | random
    }
  ],
  summary: "...",             // agent-generated summary
  follow_up_required: false,
  vault_link: "reports/2026-04-11-和睦家.md"
}
```

#### 5. `checkpoint` (singleton)

```javascript
{
  _id: "ingest_checkpoint",
  file: "export.xml",
  byte_offset: 1234567890,
  last_record_date: "2026-03-30",
  records_processed: 47000,
  status: "in_progress",      // idle | in_progress | completed | error
  started_at: ISODate("..."),
  updated_at: ISODate("...")
}
```

## Script Refactor Map

| Current Script | Action | New Behavior |
|---------------|--------|-------------|
| `ingest.py` | **Rewrite** | SAX parse → pymongo upsert (eliminate .tmp files entirely). Checkpoint in MongoDB. Resume from byte offset |
| `checkpoint.py` | **Delete** | Checkpoint logic absorbed into ingest.py (MongoDB singleton) |
| `baseline.py` | **Rewrite** | Read from MongoDB aggregation pipeline (`$group` + `$stdDevPop`). Write to `baselines` collection. Remove Welford (MongoDB does the math) |
| `summarize.py` | **Delete** | `build_haiku_prompt()` removed. Agent reads MongoDB aggregation output directly and reasons about it |
| `narrate.py` | **Delete** | `build_daily_context()` / `build_weekly_context()` removed. Agent builds narrative from structured MongoDB query results |
| `predict.py` | **Rewrite** | Evaluate rules against MongoDB data. Write alerts to `alerts` collection. No markdown generation (agent does that) |
| `annual_report.py` | **Delete** | Agent queries MongoDB for yearly aggregation directly. Heatmap JSON can be generated by a script if needed |
| `notion_sync.py` | **Delete** | Agent uses Notion MCP tools directly (create-pages, create-view, update-page) |
| `parse_report.py` | **Simplify** | Remove pdftotext/tesseract. Agent uses Claude Code `Read` tool for PDF. Script only handles text post-processing if needed |

**Scripts retained** (data processing only): `ingest.py`, `baseline.py`, `predict.py`
**Scripts deleted** (LLM work or replaced by MCP): `checkpoint.py`, `summarize.py`, `narrate.py`, `annual_report.py`, `notion_sync.py`
**Scripts simplified**: `parse_report.py`

## Agent Refactor Map

| Current Agent | Changes |
|--------------|---------|
| `health-ingest-agent` | Calls refactored `ingest.py` (pymongo). No more .tmp/finalize. Monitors checkpoint status |
| `health-baseline-agent` | Calls refactored `baseline.py` (MongoDB read/write). Drift detection triggers Notion + alert |
| `health-analyze-agent` | No longer delegates to summarize.py/narrate.py. Queries MongoDB MCP directly, reasons about results, writes Notion pages via MCP, writes Obsidian daily markdown |
| `health-predict-agent` | Calls refactored `predict.py` (MongoDB read). Agent formats alerts and writes to Notion MCP |
| `health-report-agent` | Uses Claude Code `Read` to read PDF directly. Structures extracted data, writes to MongoDB `lab_reports`, writes Notion MCP |

## Notion Health Workspace

4 databases (schema from `notion/schema.md`, created via Notion MCP `notion-create-database`):

| DB | Primary View | Chart Views |
|----|-------------|-------------|
| Trends | Table (sortable by date + metric) | Line chart: metric value over time, grouped by metric type |
| Alerts | Board (grouped by status: active/acknowledged/resolved) | Bar chart: alert count by severity over months |
| Reports | Table (filtered by status: pending_review) | Timeline: reports on date axis |
| Lab Results | Table (grouped by test type) | Line chart: specific test value over time (e.g., HbA1c trend) |

**Dashboard page**: Notion page with linked database views from all 4 DBs, providing a single overview.

## Grafana Cloud Integration

MongoDB Atlas as data source. Key panels:

| Panel | Type | Query |
|-------|------|-------|
| Heart Rate (7d) | Time series | `metrics` where metric=heart_rate, last 7 days |
| HRV Trend (30d) | Time series | `metrics` where metric=hrv_sdnn, last 30 days |
| Sleep Duration Heatmap | Heatmap | `metrics` where metric=sleep_duration, by weekday×hour |
| Metric vs Baseline Deviation | Gauge | Latest value vs latest baseline, per metric |
| Active Alerts | Stat | `alerts` where status=active, count |

## Cross-Plugin Integration

| Flow | Mechanism | Data | Frequency | Privacy |
|------|-----------|------|-----------|---------|
| health → Get笔记 | `getnote.sh save_note` | Weekly aggregate summary (text, no raw data) | Weekly | Aggregates only |
| health → pkos | IEF file export | Health insight → pkos intel-sync | Weekly | Aggregates only |
| mactools calendar → health | `getnote.sh recall` + calendar query | Event metadata (travel/exercise/overtime) → MongoDB enrichment | On analyze |  Calendar data only |
| health → Adam delivery | Adam delivery rules | Alert (immediate) + daily summary → WeChat | Event-driven + daily | Via existing Adam pipeline |

## Configuration

```yaml
# config/defaults.yaml updates
mongodb:
  connection_string: "${MDB_MCP_CONNECTION_STRING}"
  database: "health"

vault_path: "~/Obsidian/HealthVault"          # downgraded to downstream archive
notion_workspace: "Health"

# Remove: haiku_model, sonnet_model (no longer calling LLM APIs)
# Remove: adam_state_dir, adam_tmp_dir (no file-based state)
# Remove: chunk_size_mb (pymongo handles batching)
```

## Migration Plan

1. Create MongoDB collections (time-series + regular)
2. Parse existing .tmp files → insert into MongoDB (one-time migration)
3. Verify data completeness (record count per date matches .tmp line count)
4. Delete .ingest_buffer/ (reclaim 20GB)
5. Rewrite scripts + agents
6. Create Notion databases via MCP
7. Configure Grafana Cloud
8. Set up cross-plugin flows

## Open Questions

1. **Grafana Cloud account**: Does the user have a Grafana Cloud account, or should we set one up?
2. **Adam cron schedule**: What schedule for daily analysis, weekly digest, baseline update?
3. **Alert delivery urgency**: Should severe alerts trigger immediate WeChat push, or batch with daily summary?
