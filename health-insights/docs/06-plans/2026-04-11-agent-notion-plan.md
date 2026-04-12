---
type: plan
status: active
tags: [agents, notion, mcp, pdf, analyze, report]
refs: [docs/06-plans/2026-04-11-health-insights-refactor-design.md, docs/11-crystals/2026-04-11-health-insights-refactor-crystal.md]
---

# Agent Layer Refactor + Notion Integration — Implementation Plan

**Goal:** All 5 agents refactored to use MCP tools (MongoDB query, Notion write, Claude Code Read). Notion Health workspace created with 4 databases and views.

**Architecture:** Agent markdown files define behavior for the host Claude Code session. Agents query MongoDB via MongoDB MCP tools, write to Notion via Notion MCP tools, read PDFs via Claude Code Read tool. No Python scripts for text generation, Notion sync, or PDF parsing. Scripts only remain for data processing (ingest, baseline computation, rule evaluation).

**Tech Stack:** Notion MCP (create-database, create-pages, create-view), MongoDB MCP (aggregate, find), Claude Code Read tool (PDF)

**Design doc:** docs/06-plans/2026-04-11-health-insights-refactor-design.md

**Crystal file:** docs/11-crystals/2026-04-11-health-insights-refactor-crystal.md

**Threat model:** not applicable

---

<!-- section: task-1 keywords: notion, database, create, mcp -->
### Task 1: Create Notion Health workspace with 4 databases

Crystal ref: [D-005], [D-007]

**Files:**
- Modify: `notion/schema.md` (add database IDs after creation)
- Modify: `config/defaults.yaml` (populate notion_database_ids)

**Steps:**
1. Create a Notion page "Health" as the workspace root (via `notion-create-pages` MCP tool)
2. Create 4 databases under the Health page using `notion-create-database` MCP tool, matching `notion/schema.md`:

   **Trends DB:**
   ```sql
   CREATE TABLE (
     "Date" DATE,
     "Metric Type" SELECT('heart_rate', 'hrv_sdnn', 'vo2max', 'resting_heart_rate', 'walking_heart_rate_avg', 'sleep_duration', 'sleep_quality', 'step_count', 'active_energy', 'basal_energy', 'distance', 'blood_glucose_fasting', 'blood_glucose_post', 'bp_sys', 'bp_dia', 'spo2', 'resp_rate', 'body_mass', 'bmi', 'body_fat_pct'),
     "Value" NUMBER,
     "Unit" RICH_TEXT,
     "Source" SELECT('apple_health_export', 'icloud_delta', 'manual_entry', 'lab_report'),
     "Notes" RICH_TEXT,
     "Is Baseline Update" CHECKBOX
   )
   ```

   **Alerts DB:**
   ```sql
   CREATE TABLE (
     "Date" DATE,
     "Alert Type" SELECT('hrv_low':red, 'resting_hr_high':red, 'sleep_debt':yellow, 'blood_glucose_high':red, 'overtraining':orange, 'weight_anomaly':yellow),
     "Severity" SELECT('mild':green, 'moderate':yellow, 'severe':red),
     "Triggered By" RICH_TEXT,
     "Status" SELECT('active':red, 'acknowledged':yellow, 'resolved':green),
     "Action Taken" RICH_TEXT,
     "Vault Link" URL
   )
   ```

   **Reports DB:**
   ```sql
   CREATE TABLE (
     "Date" DATE,
     "Hospital" RICH_TEXT,
     "Report Type" SELECT('annual', 'quarterly', 'specialty', 'emergency', 'other'),
     "Key Metrics" RICH_TEXT,
     "Status" SELECT('pending_review':yellow, 'reviewed':green, 'follow_up_required':red),
     "Follow-up Date" DATE,
     "Vault Link" URL
   )
   ```

   **Lab Results DB:**
   ```sql
   CREATE TABLE (
     "Date" DATE,
     "Test Type" SELECT('blood_glucose', 'lipid_panel', 'liver_function', 'thyroid', 'blood_count', 'vitamin_d', 'iron'),
     "Subtype" RICH_TEXT,
     "Value" NUMBER,
     "Unit" RICH_TEXT,
     "Reference Range" RICH_TEXT,
     "Context" SELECT('fasting', 'post_meal', 'morning', 'evening', 'random'),
     "Status" SELECT('normal':green, 'borderline':yellow, 'abnormal':red),
     "Source" SELECT('manual_entry', 'lab_report'),
     "Report ID" RICH_TEXT
   )
   ```

3. Record the database IDs and data source IDs returned by MCP
4. Update `notion/schema.md` with actual database IDs
5. Update `config/defaults.yaml` `notion_database_ids` with the IDs

**Verify:**
Run: `grep "notion_database_ids" config/defaults.yaml -A 5`
Expected: 4 non-null database IDs populated
<!-- /section -->

---

<!-- section: task-2 keywords: notion, views, chart, dashboard -->
### Task 2: Create Notion chart views and dashboard page

Crystal ref: [D-005]

**Depends on:** Task 1

**Files:**
- No code files (Notion MCP operations only)

**Steps:**
1. For each database, create views using `notion-create-view` MCP tool:

   **Trends DB views:**
   - Table view "All Trends" (default, sorted by Date DESC)
   - Chart view "Metric Trends": `CHART line AGGREGATE avg; SORT BY "Date" ASC`

   **Alerts DB views:**
   - Board view "Alert Board": `GROUP BY "Status"`
   - Table view "Alert History": `SORT BY "Date" DESC`

   **Reports DB views:**
   - Table view "Pending Review": `FILTER "Status" = "pending_review"; SORT BY "Date" DESC`
   - Timeline view "Report Timeline": `TIMELINE BY "Date" TO "Follow-up Date"`

   **Lab Results DB views:**
   - Table view "All Results": `SORT BY "Date" DESC`
   - Table view "By Test Type": `GROUP BY "Test Type"`

2. Create a dashboard page "Health Dashboard" under the Health workspace root via `notion-create-pages`:
   - Content includes linked database references to all 4 DBs
   - Page icon: 🏥

**Verify:**
Fetch the Health Dashboard page via `notion-fetch` and verify it contains links to all 4 databases.

⚠️ No test: Notion MCP operations, no logic code
<!-- /section -->

---

<!-- section: task-3 keywords: agent, analyze, report, refactor -->
### Task 3: Refactor health-analyze-agent.md and health-report-agent.md

Crystal ref: [D-003], [D-006], [D-007], [D-009]

**Files:**
- Modify: `agents/health-analyze-agent.md`
- Modify: `agents/health-report-agent.md`

**Steps:**
1. `health-analyze-agent.md` — already partially updated in Phase 2. Complete the refactor:
   - Add Notion MCP write instructions for each action:
     - `daily`: after generating analysis, create Notion page in Trends DB with key metrics + deviation flags
     - `weekly`: create Notion page under Health workspace with correlation analysis
     - `annual`: create Notion page with yearly narrative
   - Add Obsidian vault write instructions:
     - `daily`: write `~/Obsidian/HealthVault/daily/{date}/summary.md` (human-readable archive)
   - Ensure all MongoDB queries use MongoDB MCP tools (`mcp__plugin_mongodb_mongodb__aggregate`, `mcp__plugin_mongodb_mongodb__find`)
   - Add Notion database IDs as config references (from config/defaults.yaml)

2. `health-report-agent.md` — full refactor:
   - Remove `model: sonnet` from frontmatter
   - Remove `vault_dir` from Input, add `mongo_uri`, `database`
   - Update Behavior:
     a. Detect file type from extension
     b. **Read PDF**: use Claude Code `Read` tool directly. If Read fails (unsupported format), fallback to `python3 -c "import subprocess; subprocess.run(['pdftotext', '-layout', '<file>', '-'])"` via Bash
     c. **Read Image**: use Claude Code `Read` tool (multimodal). If Read fails, note: "Image OCR requires Claude Code Read tool multimodal support"
     d. **Extract structured data**: agent reasons about the extracted text in host session — no external LLM API call
     e. For each extracted metric: query MongoDB baselines collection via MCP, compute deviation
     f. Write to MongoDB `lab_reports` collection via MCP (`mcp__plugin_mongodb_mongodb__insert-many`)
     g. Write to Notion Reports DB and Lab Results DB via Notion MCP
   - Remove all references to `parse_report.py` scripts for text extraction (agent handles this directly)
   - Remove vault file writes (reports/YYYY-MM-DD-*.md — Notion is primary, vault is optional downstream)
   - Update Output YAML spec block: remove `file_path` and `yaml_written` vault references, add `notion_reports_record_id` and `notion_lab_results_record_ids` fields

**Verify:**
Run: `grep -c "summarize\|narrate\|sonnet\|haiku\|parse_report\|pdftotext.*required\|vault_dir" agents/health-analyze-agent.md agents/health-report-agent.md`
Expected: `0` for each (except pdftotext as fallback in report agent)
<!-- /section -->

---

<!-- section: task-4 keywords: agent, ingest, baseline, predict, finalize -->
### Task 4: Finalize ingest + baseline + predict agents for Notion sync

Crystal ref: [D-007]

**Depends on:** Task 1 (Notion DB IDs needed)

**Files:**
- Modify: `agents/health-ingest-agent.md`
- Modify: `agents/health-baseline-agent.md`
- Modify: `agents/health-predict-agent.md`

**Steps:**
1. `health-ingest-agent.md`:
   - Add post-ingest step: "After successful ingest, report summary to user. Notion sync is handled by the analyze agent on its next scheduled run, not by ingest."
   - Verify no stale references remain from Phase 1 refactor

2. `health-baseline-agent.md`:
   - Add Notion sync step: after computing baselines, create/update Trends DB records with `Is Baseline Update: true` via Notion MCP
   - Add drift notification: if drift detected, create Alerts DB record via Notion MCP

3. `health-predict-agent.md`:
   - Add Notion sync step: for each triggered alert, create Alerts DB record via Notion MCP
   - Include alert severity, trigger details, and baseline comparison in Notion record
   - Add acknowledge action: update Notion Alerts DB record status to "acknowledged"

**Verify:**
Run: `grep "Notion\|notion" agents/health-ingest-agent.md agents/health-baseline-agent.md agents/health-predict-agent.md`
Expected: Notion references found in baseline and predict agents
<!-- /section -->

---

<!-- section: task-5 keywords: delete, cleanup, scripts -->
### Task 5: Delete deprecated scripts

Crystal ref: [D-003]

**Files:**
- Delete: `scripts/annual_report.py`
- Delete: `scripts/notion_sync.py`
- Simplify: `scripts/parse_report.py` (keep only text post-processing utilities if any are needed by other scripts; if nothing references it, delete entirely)

**Steps:**
1. Check if any agent or script references `parse_report.py`:
   ```bash
   grep -r "parse_report" scripts/ agents/ skills/ --include="*.py" --include="*.md"
   ```
2. If no references: delete `parse_report.py`
3. If references exist: simplify to remove pdftotext/tesseract calls, keep only utility functions
4. Delete `annual_report.py` and `notion_sync.py`
5. Verify no imports broken:
   ```bash
   grep -r "annual_report\|notion_sync" scripts/ agents/ skills/
   ```

**Verify:**
Run: `ls scripts/annual_report.py scripts/notion_sync.py 2>/dev/null && echo "EXISTS" || echo "DELETED"`
Expected: `DELETED`
<!-- /section -->

---

<!-- section: task-6 keywords: skill, routing, update -->
### Task 6: Update skills/health/SKILL.md routing

Crystal ref: [D-007], [D-009]

**Depends on:** Task 1 (DB IDs), Task 3 (agent refactors)

**Files:**
- Modify: `skills/health/SKILL.md`

**Steps:**
1. Update all dispatch blocks to include Notion DB IDs from config:
   - analyze route: add `notion_trends_db_id`, `notion_workspace_page_id`
   - predict route: add `notion_alerts_db_id`
   - report route: add `notion_reports_db_id`, `notion_lab_results_db_id`
   - baseline route: add `notion_trends_db_id`, `notion_alerts_db_id`
2. Update status route:
   - Query MongoDB for metrics count and last ingest date
   - Query Notion for recent dashboard activity
   - Remove any vault file glob references
3. Add annual route if not present:
   - Routes to health-analyze-agent with `action: annual`
4. Remove `model: sonnet` from SKILL.md frontmatter if present (Crystal D-003/D-009)
5. Ensure no references to deleted scripts (summarize, narrate, annual_report, notion_sync)

**Verify:**
Run: `grep -c "summarize\|narrate\|annual_report\|notion_sync\|vault.*primary" skills/health/SKILL.md`
Expected: `0`
<!-- /section -->

---

<!-- section: task-7 keywords: verification, test, full -->
### Task 7: Full verification

**Depends on:** All previous tasks

**Verify:**
Run: `python3 -m pytest scripts/ -v`
Expected: All tests pass (49+ from Phase 1+2)

Run: `ls scripts/annual_report.py scripts/notion_sync.py scripts/summarize.py scripts/narrate.py 2>/dev/null && echo "EXISTS" || echo "ALL DELETED"`
Expected: `ALL DELETED`

Run: `grep -r "model: sonnet\|model: haiku\|build_.*prompt\|pdftotext.*required\|tesseract.*required" agents/ | grep -v "fallback\|#" | wc -l`
Expected: `0`

Run: `grep -c "notion" agents/health-analyze-agent.md agents/health-baseline-agent.md agents/health-predict-agent.md agents/health-report-agent.md`
Expected: Non-zero counts for all 4 agents (Notion integration present)
<!-- /section -->

## Decisions

### [DP-001] parse_report.py: simplify or delete? (recommended)

**Context:** Phase 3 moves PDF reading to Claude Code Read tool (agent layer). parse_report.py currently does pdftotext/tesseract calls + hospital detection + date extraction. Agent can do all of this directly.
**Options:**
- A: Delete entirely — agent handles everything via Read tool + reasoning
- B: Keep hospital/date regex detection as utility, delete pdftotext/tesseract functions
**Chosen:** A — Delete parse_report.py entirely. Agent handles PDF reading + structured extraction directly.
