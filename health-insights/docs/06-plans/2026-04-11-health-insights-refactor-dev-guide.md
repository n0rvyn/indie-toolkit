---
type: dev-guide
status: active
tags: [health-insights, mongodb, plugin-refactor, visualization, cross-plugin]
refs: [docs/06-plans/2026-04-11-health-insights-refactor-design.md, docs/11-crystals/2026-04-11-health-insights-refactor-crystal.md]
current: true
confirmed_at: 2026-04-11T12:20:00
---

# Health-Insights Plugin Refactor — Development Guide

**Design doc:** docs/06-plans/2026-04-11-health-insights-refactor-design.md
**Crystal:** docs/11-crystals/2026-04-11-health-insights-refactor-crystal.md

## Global Constraints

- Claude Code plugin: scripts/ output structured data, agents/ do reasoning, skills/ do routing (D-003, D-009)
- MongoDB connection string via `MDB_MCP_CONNECTION_STRING` env var (already configured)
- Notion MCP tools for all Notion operations (no custom Python API wrapper)
- MongoDB MCP tools for agent-layer queries
- pymongo for script-layer writes
- Atlas Free Tier for testing (1 year data); self-hosted MongoDB if capacity exceeded
- No external LLM API calls from scripts (D-003)
- Health data privacy: raw data stays in MongoDB/Notion (self-controlled); Get笔记 receives aggregates only (D-S02)

---

<!-- section: phase-1 keywords: mongodb, collections, ingest, migration, pymongo -->
## Phase 1: MongoDB Foundation + Ingest Pipeline

**Goal:** Health metrics flow from Apple Health XML into MongoDB time-series collections with resumable ingestion and checkpoint persistence.
**Depends on:** None
**Scope:**
- Create MongoDB database `health` with 5 collections (metrics, baselines, alerts, lab_reports, checkpoint)
- Rewrite `ingest.py`: SAX parse → pymongo batch upsert (eliminate .tmp intermediate files)
- Checkpoint stored as MongoDB singleton document (atomic update, no file dependency)
- Migrate existing .tmp data (20GB buffer) into MongoDB
- Delete `checkpoint.py` (absorbed into ingest.py)
- Delete .ingest_buffer/ after successful migration (reclaim 20GB disk)
- Update `config/defaults.yaml` with MongoDB config section

**用户可见的变化:**
- `/health ingest` writes data to MongoDB instead of .tmp files
- `/health status` shows MongoDB record counts and ingest progress
- 20GB disk space reclaimed

**Architecture decisions:**
- Time-series collection granularity setting (seconds vs minutes) for heart rate
- Batch insert size for migration (balance memory vs speed)
- Whether to deduplicate records during migration (same date+metric+timestamp+value)

**Acceptance criteria:**
- [ ] MongoDB `health` database created with all 5 collections
- [ ] `metrics` collection is time-series type with correct timeField/metaField/granularity
- [ ] `ingest.py` processes Apple Health XML and upserts to MongoDB (no .tmp files created)
- [ ] Checkpoint persists in MongoDB; interrupted ingest resumes from last byte offset
- [ ] Existing .tmp data migrated to MongoDB (record count verified per date)
- [ ] .ingest_buffer/ deleted, 20GB reclaimed
- [ ] `config/defaults.yaml` updated with `mongodb` section
- [ ] UT pass for ingest.py (mock pymongo, test SAX parsing + type normalization)

**Review checklist:**
- [ ] /execution-review
<!-- /section -->

---

<!-- section: phase-2 keywords: baseline, predict, alerts, aggregation -->
## Phase 2: Baseline + Prediction Pipeline

**Goal:** Baselines computed from MongoDB aggregation, prediction rules evaluate against baselines and write alerts to MongoDB.
**Depends on:** Phase 1
**Scope:**
- Rewrite `baseline.py`: MongoDB aggregation pipeline ($group + $stdDevPop) replaces Welford algorithm
- Baselines stored in `baselines` collection with version history (insert new doc per computation)
- Drift detection (deviation > 10%) triggers alert
- Rewrite `predict.py`: evaluate rules against MongoDB data, write to `alerts` collection
- Delete `summarize.py` (LLM prompt builder — agent does this now)
- Delete `narrate.py` (LLM prompt builder — agent does this now)
- Update `health-baseline-agent.md`: calls refactored baseline.py, reports drift via structured output
- Update `health-predict-agent.md`: calls refactored predict.py, formats alerts in host session

**用户可见的变化:**
- `/health baseline` shows computed baselines from MongoDB data
- `/health predict` evaluates alert rules and reports triggered alerts with severity
- Baseline drift notifications in agent output

**Architecture decisions:**
- Baseline window size (fixed 90 days or configurable per metric)
- Alert rule storage (hardcoded in predict.py or configurable in MongoDB)

**Acceptance criteria:**
- [ ] `baseline.py` reads from MongoDB, computes baselines via aggregation pipeline, writes to `baselines` collection
- [ ] Baseline versioning: each computation inserts a new document, previous versions preserved
- [ ] `predict.py` evaluates 4+ rules against MongoDB data and writes alerts to `alerts` collection
- [ ] `summarize.py` and `narrate.py` deleted
- [ ] Agent markdown files updated: no references to external LLM models or prompt-building scripts
- [ ] UT pass for baseline.py and predict.py

**Review checklist:**
- [ ] /execution-review
<!-- /section -->

---

<!-- section: phase-3 keywords: agents, analyze, report, pdf, notion -->
## Phase 3: Agent Layer Refactor + Notion Integration

**Goal:** All 5 agents refactored to use MCP tools (MongoDB query, Notion write, Claude Code Read). Notion Health workspace created with 4 databases and views.
**Depends on:** Phase 2
**Scope:**
- Create Notion Health workspace with 4 databases (Trends, Alerts, Reports, Lab Results) via Notion MCP
- Create Notion chart views and dashboard page via Notion MCP
- Refactor `health-analyze-agent.md`: query MongoDB MCP, reason in host session, write Notion MCP + Obsidian daily markdown
- Refactor `health-predict-agent.md`: read alerts from MongoDB MCP, write to Notion Alerts DB
- Refactor `health-report-agent.md`: use Claude Code `Read` tool for PDF, write to MongoDB + Notion MCP
- Simplify `parse_report.py`: primary path uses Claude Code `Read` tool for PDF; fallback to pdftotext when Read fails (D-006); remove tesseract dependency
- Delete `annual_report.py` (agent queries MongoDB yearly aggregation directly)
- Delete `notion_sync.py` (replaced by Notion MCP tools)
- Update `health-ingest-agent.md`: pymongo calls, no .tmp/finalize
- Update `health-baseline-agent.md`: finalize integration with Notion sync

**用户可见的变化:**
- `/health analyze` produces narrative analysis based on MongoDB data, synced to Notion Trends DB
- `/health analyze --weekly` produces weekly correlation analysis in Notion
- `/health report <file>` reads PDF directly and extracts structured lab results to Notion
- `/health annual <year>` generates yearly summary from MongoDB aggregation
- Notion Health dashboard accessible with chart views across all 4 databases

**Architecture decisions:**
- Notion database property schemas (confirm schema.md alignment with actual Notion MCP create syntax)
- Dashboard layout (which linked views, what chart configurations)

**Acceptance criteria:**
- [ ] Notion Health workspace created with 4 databases matching schema.md
- [ ] Chart views created: line chart (Trends), board (Alerts), timeline (Reports)
- [ ] Dashboard page with linked views from all 4 DBs
- [ ] All 5 agents use MongoDB MCP for queries and Notion MCP for writes
- [ ] No agent references to external LLM model names (haiku, sonnet)
- [ ] `notion_sync.py`, `annual_report.py` deleted
- [ ] `parse_report.py` simplified (no pdftotext/tesseract)
- [ ] `/health report` successfully reads a PDF via Claude Code Read tool
- [ ] UT pass for any remaining scripts; agent integration verified via `/health` commands

**Review checklist:**
- [ ] /execution-review
- [ ] /feature-review (complete user journey: ingest → analyze → view in Notion)
<!-- /section -->

---

<!-- section: phase-4 keywords: grafana, visualization, heatmap, dashboard -->
## Phase 4: Grafana Cloud Visualization

**Goal:** Grafana Cloud connected to MongoDB Atlas with time-series dashboards for real-time health monitoring.
**Depends on:** Phase 1, Phase 3 (Notion pages for Grafana panel embeds)
**Scope:**
- Set up Grafana Cloud account and MongoDB data source
- Create 5 core panels: Heart Rate (7d), HRV Trend (30d), Sleep Heatmap, Deviation Gauge, Active Alerts
- Configure Grafana alerting rules (replicate predict.py rules for real-time monitoring)
- Embed Grafana panel links in Notion annual report pages

**用户可见的变化:**
- Grafana dashboard URL accessible for interactive health data exploration
- Heatmap, correlation charts, and time-series panels for all key metrics
- Alert notifications from Grafana when thresholds exceeded

**Architecture decisions:**
- Grafana Cloud free tier vs self-hosted Grafana
- Which Grafana alerting rules duplicate vs complement predict.py rules
- Dashboard organization (single dashboard vs per-metric dashboards)

**Acceptance criteria:**
- [ ] Grafana Cloud account configured with MongoDB data source
- [ ] 5 core panels rendering data from MongoDB `metrics` collection
- [ ] At least 1 Grafana alert rule active and triggering correctly
- [ ] Dashboard URL documented in README.md

**Review checklist:**
- [ ] /execution-review
<!-- /section -->

---

<!-- section: phase-5 keywords: cross-plugin, getnote, pkos, ief, delivery, wechat -->
## Phase 5: Cross-Plugin Integration + Delivery

**Goal:** Health-insights produces outputs consumed by Get笔记, pkos, and Adam delivery rules for WeChat push.
**Depends on:** Phase 3
**Scope:**
- Get笔记 weekly digest: agent generates aggregate health summary, writes via `getnote.sh save_note`
- pkos IEF export: health insights produce IEF files for pkos intel-sync consumption
- mactools calendar enrichment: analyze agent queries calendar events to annotate health data context
- Adam delivery rules: configure `task_complete` rules to push alerts (immediate) and daily summaries to WeChat
- Update skill routing (`skills/health/SKILL.md`) to include new commands and cross-plugin flows

**用户可见的变化:**
- Weekly health digest appears in Get笔记, searchable via semantic recall
- Health insights appear in pkos MOC via ripple-compiler
- Daily health summary and alerts pushed to WeChat via Adam
- `/health analyze` context enriched with calendar events (travel, exercise, overtime)

**Architecture decisions:**
- IEF format for health insights (which fields, significance scoring)
- Get笔记 topic mapping (which topic receives health digests)
- Adam delivery rule configuration (which events trigger which channels)
- WeChat message format for health alerts vs summaries

**Acceptance criteria:**
- [ ] Get笔记 weekly digest created via `getnote.sh save_note` with aggregate health data
- [ ] IEF file produced and consumable by pkos intel-sync
- [ ] Adam delivery rule configured for health alerts → WeChat
- [ ] Calendar event context appears in analyze agent output
- [ ] `skills/health/SKILL.md` routing table updated with all new commands
- [ ] Privacy boundary enforced: Get笔记 receives only aggregates, no raw data or lab results

**Review checklist:**
- [ ] /execution-review
- [ ] /feature-review (cross-plugin data flow: health → Get笔记 → ripple-compiler)
<!-- /section -->

---

<!-- section: phase-6 keywords: cleanup, config, testing, documentation -->
## Phase 6: Cleanup + Documentation

**Goal:** All deprecated files removed, configuration unified, README updated, test coverage complete.
**Depends on:** Phase 4, Phase 5
**Scope:**
- Remove all deprecated scripts: `checkpoint.py`, `summarize.py`, `narrate.py`, `annual_report.py`, `notion_sync.py`
- Remove `test_baseline.py` (replace with tests for new baseline.py)
- Clean up `config/defaults.yaml` (remove haiku_model, sonnet_model, adam_state_dir, adam_tmp_dir, chunk_size_mb)
- Update `config/schema.yaml` to match new config structure
- Update `notion/schema.md` with actual Notion DB IDs
- Update `README.md` with new architecture, commands, and setup instructions
- Write integration tests for full pipeline (ingest → baseline → analyze → predict → report)
- Verify all eval.md skill stubs are either populated or removed

**用户可见的变化:**
- 无 — 纯清理阶段

**Architecture decisions:**
- None

**Acceptance criteria:**
- [ ] No references to deleted scripts in agent markdown files
- [ ] `config/defaults.yaml` has no deprecated fields
- [ ] README.md documents new setup: MongoDB connection, Notion MCP config, Grafana setup, and step-by-step plugin initialization guide for first-time users
- [ ] Integration test covers ingest → baseline → predict flow
- [ ] All files in scripts/ are actively used (no orphaned scripts)

**Review checklist:**
- [ ] /execution-review
<!-- /section -->

## Decisions

None.
