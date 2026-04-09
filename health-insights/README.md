# Health Insights

Personal health intelligence plugin for Claude Code.

Ingests Apple Health data, establishes personal baselines, and generates AI-driven narrative insights. Data flows into an independent Obsidian vault (HealthVault) and Notion workspace (Health).

## Installation

```bash
/plugin install health-insights@indie-toolkit
```

## Usage

```
/health                    — Status dashboard
/health ingest            — Ingest health data (Adam-triggered or manual)
/health baseline          — Compute/update personal baselines
/health analyze <topic>   — Generate trend insights
/health predict           — Run early warning evaluation
/health report <file>     — Parse体检报告 or lab report
/health trends <type>     — Query specific metric trends
/health annual <year>     — Generate annual health report
```

## Architecture

```
/health (entry skill, routes to agents)
    │
    ├── health-ingest-agent      — SaxParser XML → vault daily/ YAML
    ├── health-baseline-agent    — Statistical baseline computation
    ├── health-analyze-agent     — Haiku summaries + Sonnet narratives
    ├── health-predict-agent     — Rule-based early warning
    └── health-report-agent     — PDF/image OCR → structured metrics

Vault: ~/Obsidian/HealthVault/
    ├── daily/YYYY-MM-DD/       — Daily aggregated metrics
    ├── baselines/              — Personal baseline statistics
    ├── trends/{metric}/       — Metric history over time
    ├── alerts/                — Early warning events
    ├── reports/               — Parsed体检报告
    └── insights/              — AI-generated deep insights

Notion: "Health" workspace
    ├── Trends DB
    ├── Alerts DB
    ├── Reports DB
    └── Lab Results DB
```

## Configuration

Edit `config/defaults.yaml` or create `~/.adam/config/health-insights.yaml` to override defaults.

Key settings:
- `vault_path` — Obsidian HealthVault directory
- `icloud_watch_folder` — iCloud delta directory
- `notion_api_key` — from `NOTION_API_KEY` env var

## Dependencies

- Python 3.10+
- `pdftotext` (poppler) — PDF text extraction
- `tesseract` — OCR for image reports
- Notion API key — for Notion workspace sync
- Adam daemon (Mac mini) — for scheduled runs

## Adam Integration

Add to `~/.adam/config/health.yaml`:

```yaml
tasks:
  health-daily:
    schedule: "0 7 * * *"
    template: health-daily
    description: "Daily health analysis + baseline update"
  health-predict:
    schedule: "0 21 * * *"
    template: health-predict
    description: "Evening recovery/overtraining check"
watch_folders:
  health_delta:
    path: "~/Library/Mobile Documents/com~apple~CloudDocs/HealthSync/delta/"
    events: ["create", "modify"]
    action: health-ingest
    debounce_seconds: 30
```

## Data Sources

- Apple Health export.xml (full, one-time)
- iCloud HealthSync delta files (ongoing, from iOS app)
- Manual lab report uploads (PDF/image/text)

## Supported Metrics

90+ Apple Health record types including:
- Heart rate, HRV, VO2Max, resting heart rate
- Sleep duration and stages
- Steps, distance, flights climbed
- Active/basal energy burned
- Cycling power, speed, cadence
- Blood glucose, blood pressure, SpO2
- All dietary metrics (macros, micronutrients)
- And more...
