# Health Insights

Personal health intelligence plugin for Claude Code.

Ingests Apple Health data into MongoDB, computes personal baselines, evaluates early warning rules, and generates AI-driven analysis. Data stored in MongoDB Atlas (primary), synced to Notion (dashboards), and optionally archived in Obsidian HealthVault.

## Quick Start

### 1. Install

```bash
/plugin install health-insights@indie-toolkit
```

### 2. Configure MongoDB

Set the MongoDB Atlas connection string in your shell profile:

```bash
export MDB_MCP_CONNECTION_STRING="mongodb+srv://user:pass@cluster.mongodb.net/?appName=HealthMetrics"
```

Install the MongoDB MCP plugin for Claude Code:

```bash
/plugin install mongodb@claude-plugins-official
```

Install Python dependencies:

```bash
pip3 install pymongo[srv] pyyaml
```

### 3. Configure Notion (optional)

Authenticate the Notion MCP plugin:

```bash
/mcp  # authenticate plugin:Notion:notion
```

Notion databases are pre-created. IDs are in `config/defaults.yaml`.

### 4. Initial Data Ingest

Export from iPhone: Health app > Profile > Export All Health Data > share export.zip

```bash
unzip export.zip -d ~/Downloads/apple_health_export/
/health ingest ~/Downloads/apple_health_export/export.xml
```

For large exports (5GB+), use date range filtering:

```bash
python3 scripts/ingest.py --source ~/Downloads/apple_health_export/export.xml --start-date 2025-04-01 --end-date 2026-03-30
```

### 5. Compute Baselines

```bash
/health baseline
```

Requires at least 30 data points per metric.

## Usage

```
/health                    — Check MongoDB record counts and ingest status
/health ingest <path>     — Ingest Apple Health XML export to MongoDB
/health baseline          — Compute/update personal baselines (90-day window)
/health analyze           — Daily health analysis (MongoDB query + AI narrative)
/health analyze --weekly  — Weekly correlation analysis (sleep vs HRV, etc.)
/health predict           — Evaluate early warning rules against baselines
/health report <file>     — Parse体检报告/lab report (PDF via Claude Code Read)
/health trends <type>     — Query specific metric trends
/health annual <year>     — Annual health narrative from MongoDB aggregation
/health digest            — Weekly summary to Get笔记 + IEF export
/health --help            — Show all routes
```

## Architecture

```
Apple Health XML
    │
    ▼
ingest.py (SAX → pymongo batch upsert)
    │
    ├──▶ MongoDB Atlas (Time-Series Collections)    ◄── primary store
    │         │
    │         ├──▶ Notion Health DBs (4 databases)  ◄── dashboards + reports
    │         ├──▶ Get笔记 (weekly digest)           ◄── knowledge graph
    │         ├──▶ pkos IEF (weekly insight)          ◄── cross-plugin intel
    │         └──▶ Obsidian HealthVault (optional)   ◄── daily markdown archive
    │
    └──▶ MongoDB checkpoint (resumable ingest)

Agents (Claude Code plugin agents, run in host session):
    ├── health-ingest-agent      — Calls ingest.py (pymongo)
    ├── health-baseline-agent    — Calls baseline.py (MongoDB $group + $stdDevPop)
    ├── health-analyze-agent     — Queries MongoDB MCP, writes Notion MCP
    ├── health-predict-agent     — Calls predict.py (MongoDB rules), writes Notion Alerts
    └── health-report-agent      — Reads PDF via Claude Code Read tool, writes MongoDB + Notion
```

### MongoDB access: two layers, one connection string

Scripts and agents both access MongoDB, but through different tools:

| Layer | Tool | Why |
|-------|------|-----|
| **scripts/** (Python) | **pymongo** (direct driver) | Batch writes, streaming parse, aggregation pipelines; data processing is script-layer responsibility |
| **agents/** (Claude Code) | **MongoDB MCP** tools | Ad-hoc queries, interactive exploration; agent-layer responsibility |

Both read the same `MDB_MCP_CONNECTION_STRING` env var. The variable name comes from the MongoDB MCP plugin (which requires it); our Python scripts reuse it to avoid maintaining two connection strings. Scripts do NOT use MCP protocol; they connect to MongoDB directly via pymongo.

## File Structure

```
health-insights/
├── .claude-plugin/plugin.json     # Plugin manifest
├── skills/health/SKILL.md         # User entry point (/health command routing)
├── agents/                        # Agent definitions (run in host Claude Code session)
│   ├── health-ingest-agent.md     # Apple Health XML → MongoDB
│   ├── health-baseline-agent.md   # MongoDB aggregation → baselines
│   ├── health-analyze-agent.md    # Daily/weekly/annual analysis → Notion
│   ├── health-predict-agent.md    # Rule evaluation → alerts → Notion
│   └── health-report-agent.md     # PDF lab report → MongoDB + Notion
├── scripts/                       # Python data processing (pymongo direct, no LLM calls, no MCP)
│   ├── ingest.py                  # SAX XML parser → pymongo batch upsert
│   ├── baseline.py                # MongoDB $group + $stdDevPop → baselines
│   ├── predict.py                 # Rule engine → alerts collection
│   ├── getnote_digest.sh          # Get笔记 weekly summary wrapper
│   ├── test_ingest.py             # Unit tests (30)
│   ├── test_baseline.py           # Unit tests (12)
│   ├── test_predict.py            # Unit tests (7)
│   └── test_integration.py        # Pipeline integration tests (4)
├── config/
│   ├── defaults.yaml              # MongoDB URIs, Notion DB IDs, thresholds
│   ├── schema.yaml                # Config field type definitions
│   └── adam-task-templates.yaml   # Adam cron schedules for automated runs
├── notion/schema.md               # Notion database schemas + IDs
└── docs/                          # Design docs, crystals, setup guides
```

## Script CLI Reference

```bash
# Ingest Apple Health XML to MongoDB
python3 scripts/ingest.py --source <file.xml> [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
python3 scripts/ingest.py --source <directory/>   # process all XMLs in dir
python3 scripts/ingest.py --resume                 # resume from MongoDB checkpoint

# Compute baselines
python3 scripts/baseline.py --metric heart_rate    # single metric
python3 scripts/baseline.py                        # all metrics with 30+ data points

# Evaluate prediction rules
python3 scripts/predict.py --evaluate              # all rules
python3 scripts/predict.py --evaluate --rules hrv_low_3d sleep_debt_5d  # specific rules
python3 scripts/predict.py --acknowledge --alert-id <id>

# Grafana dashboard management
python3 scripts/grafana_dashboard.py --list           # list all metrics from MongoDB
python3 scripts/grafana_dashboard.py --deploy          # auto-discover all metrics, deploy full dashboard
python3 scripts/grafana_dashboard.py --dry-run         # preview without deploying

# All scripts connect to MongoDB via pymongo (direct driver, not MCP).
# Default connection: MDB_MCP_CONNECTION_STRING env var (shared with MongoDB MCP plugin).
# Override with --mongo-uri and --database flags.
```

### Environment Variables

| Variable | Required | Used By | Description |
|----------|----------|---------|-------------|
| `MDB_MCP_CONNECTION_STRING` | Yes | All scripts + MongoDB MCP plugin | MongoDB Atlas connection string |
| `GRAFANA_URL` | For Grafana | `grafana_dashboard.py` | Grafana instance URL (e.g. `https://norvyn.grafana.net`) |
| `GRAFANA_API_KEY` | For Grafana | `grafana_dashboard.py` | Grafana service account token |
| `GRAFANA_DS_UID` | For Grafana | `grafana_dashboard.py` | MongoDB datasource UID in Grafana |

Add to your shell profile (`~/.bash_profile` or `~/.zshrc`):

```bash
export MDB_MCP_CONNECTION_STRING="mongodb+srv://user:pass@cluster.mongodb.net/?appName=HealthMetrics"
export GRAFANA_URL="https://your-stack.grafana.net"
export GRAFANA_API_KEY="glsa_..."
export GRAFANA_DS_UID="your-datasource-uid"
```

## MongoDB Collections

| Collection | Type | Purpose |
|-----------|------|---------|
| `metrics` | Time-Series | All health metric readings (raw per-record data) |
| `baselines` | Regular | Computed baselines with version history |
| `alerts` | Regular | Triggered early warning events |
| `lab_reports` | Regular | Parsed体检报告 with extracted metrics |
| `checkpoint` | Regular | Ingest state for resumable processing |
| `ingest_log` | Regular | Cross-run idempotency (tracks processed chunks) |

## Notion Health Workspace

4 databases under the Health workspace page:

| DB | Views | Purpose |
|----|-------|---------|
| Trends | All Trends (table), Metric Trends (chart) | Time-series health metrics |
| Alerts | Alert Board (board by status), Alert History (table) | Early warning events |
| Reports | Pending Review (filtered), Report Timeline | Parsed lab reports |
| Lab Results | All Results (table), By Test Type (board) | Individual test results |

Dashboard: [Health Dashboard](https://www.notion.so/33f1bde4ddac81cc8140f6b5820531bb)

## Grafana Dashboard

Auto-generated from MongoDB metrics. `grafana_dashboard.py` discovers all metrics and creates one panel per metric, grouped by category (Cardiac, Activity, Running, Walking, Respiratory, Body, Nutrition, Environment, Sleep).

```bash
# First deploy (creates all panels):
python3 scripts/grafana_dashboard.py --deploy

# Then customize in Grafana UI: delete panels you don't need, rearrange, save.
# Re-running --deploy will overwrite your customizations.
```

Current panels: 49 metrics across 9 categories. Dashboard URL: https://norvyn.grafana.net/d/no59jnc/health-insights

Setup guide with manual Grafana configuration: `docs/04-guides/grafana-setup.md`

## Known Limitations

- **Workout data not yet ingested**: Apple Health `<Workout>` elements (workout routes, GPS tracks, workout statistics, swim laps) are not parsed by `ingest.py` (only `<Record>` elements). This is an enhancement for a future version.
- **Grafana Cloud PDC latency**: Aggregation queries across large datasets (heart rate: 780K+ records) may timeout through Grafana Cloud's Private Data Connect tunnel. Queries use `$limit` to stay within timeout. Self-hosted Grafana connecting directly to MongoDB avoids this.

## Cross-Plugin Integration

| Target | Mechanism | Frequency | Data |
|--------|-----------|-----------|------|
| Get笔记 | `getnote.sh save_note` | Weekly (Monday 9am) | Aggregate health summary |
| pkos | IEF file export | Weekly | Health insight for intel-sync |
| WeChat | Adam delivery rule | Daily + on alert | Summary + alerts |
| Calendar | mactools osascript | On analyze | Event context enrichment |

## Configuration

Edit `config/defaults.yaml`:

```yaml
mongodb:
  connection_string: "${MDB_MCP_CONNECTION_STRING}"
  database: "health"
  batch_size: 1000

vault_path: "~/Obsidian/HealthVault"    # downstream archive (optional)
notion_workspace: "Health"

baseline_window_days: 90
min_data_points_required: 30
drift_threshold_pct: 10
```

Notion DB IDs and Adam task templates are in `config/defaults.yaml` and `config/adam-task-templates.yaml`.

## Dependencies

- Python 3.10+ with `pymongo[srv]`, `pyyaml`
- MongoDB Atlas account (free tier M0 for testing)
- MongoDB MCP plugin (`mongodb@claude-plugins-official`)
- Notion MCP plugin (optional, for dashboard sync)
- Adam daemon (optional, for scheduled analysis)

## Supported Metrics

47+ Apple Health record types including heart rate, HRV, VO2Max, sleep, steps, distance, energy, blood glucose, blood pressure, SpO2, respiratory rate, body composition, dietary metrics, cycling/running metrics, and more. Full list in `scripts/ingest.py` TYPE_MAP.
