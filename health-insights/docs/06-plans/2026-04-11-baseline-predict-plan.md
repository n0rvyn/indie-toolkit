---
type: plan
status: active
tags: [baseline, predict, mongodb, aggregation, alerts]
refs: [docs/06-plans/2026-04-11-health-insights-refactor-design.md, docs/11-crystals/2026-04-11-health-insights-refactor-crystal.md]
---

# Baseline + Prediction Pipeline — Implementation Plan

**Goal:** Baselines computed from MongoDB aggregation, prediction rules evaluate against baselines and write alerts to MongoDB.

**Architecture:** baseline.py reads from MongoDB `metrics` collection using aggregation pipeline ($group + $stdDevPop), writes to `baselines` collection with version history. predict.py evaluates rules against MongoDB data, writes triggered alerts to `alerts` collection. Both scripts output structured JSON for the agent to consume. No LLM calls, no file-based vault I/O.

**Tech Stack:** Python 3.13, pymongo, MongoDB aggregation framework

**Design doc:** docs/06-plans/2026-04-11-health-insights-refactor-design.md

**Crystal file:** docs/11-crystals/2026-04-11-health-insights-refactor-crystal.md

**Threat model:** not applicable

---

<!-- section: task-1 keywords: baseline, mongodb, aggregation, stddev -->
### Task 1: Rewrite baseline.py — MongoDB aggregation

Crystal ref: [D-001], [D-003]

**Files:**
- Modify: `scripts/baseline.py` (full rewrite)

**Replaces:** Welford's online algorithm + file-based vault I/O

**Data flow:** MongoDB `metrics` collection → `$match` (date range + metric) → `$group` ($avg, $stdDevPop, $min, $max, $count) → Python trend detection → MongoDB `baselines` collection (insert new doc)

**Steps:**
1. Remove `WelfordStats` class, `compute_baseline()`, `update_baseline()`, `compute_all_baselines()`, `save_baseline()`, `load_baseline()`, `is_leap_year()` — all file-based logic
2. Keep `_infer_unit()` (unit map is still useful)
3. Add `pymongo` import and MongoDB connection setup (same pattern as ingest.py: `--mongo-uri`, `--database` CLI args)
4. New `compute_baseline(db, metric, window_days=90)`:
   ```python
   pipeline = [
       {"$match": {
           "metadata.metric": metric,
           "timestamp": {"$gte": cutoff_date}
       }},
       {"$group": {
           "_id": None,
           "mean": {"$avg": "$value"},
           "std": {"$stdDevPop": "$value"},
           "min": {"$min": "$value"},
           "max": {"$max": "$value"},
           "count": {"$sum": 1},
           "p25": {"$percentile": {"input": "$value", "p": [0.25], "method": "approximate"}},
           "p75": {"$percentile": {"input": "$value", "p": [0.75], "method": "approximate"}},
       }}
   ]
   result = list(db.metrics.aggregate(pipeline))
   ```
   - Skip if count < 30 (min_data_points)
   - Compute trend: two-phase aggregation (first half vs second half of window)
   - Return structured dict

5. New `save_baseline(db, baseline_dict)`:
   - `db.baselines.insert_one(baseline_dict)` — insert (not replace), preserving version history
   - Each doc has `computed_at: datetime.now(UTC)`

6. New `compute_all_baselines(db, window_days=90)`:
   - Discover all distinct metrics: `db.metrics.distinct("metadata.metric")`
   - Compute baseline for each

7. New `detect_drift(db, metric, new_baseline)`:
   - Load previous baseline: `db.baselines.find_one({"metric": metric}, sort=[("computed_at", -1)], skip=1)`
   - Compare means: if abs deviation > 10%, flag drift
   - Return `{"drift_detected": bool, "drift_pct": float}`

8. CLI:
   - `--mongo-uri` (default: `$MDB_MCP_CONNECTION_STRING`)
   - `--database` (default: `health`)
   - `--metric` (specific metric or all)
   - `--window-days` (default: 90)
   - Remove: `--vault-dir`, `--update`, `--baseline`, `--save`
   - Output: JSON to stdout (structured data for agent consumption)

**Verify:**
Run: `python3 scripts/baseline.py --help`
Expected: Shows `--mongo-uri`, `--database`, `--metric`, `--window-days`. No `--vault-dir`.

Run: `grep -c "WelfordStats\|vault_dir\|daily_dir\|\.yaml" scripts/baseline.py`
Expected: `0`
<!-- /section -->

---

<!-- section: task-2 keywords: predict, alerts, mongodb, rules -->
### Task 2: Rewrite predict.py — MongoDB-backed rule evaluation

Crystal ref: [D-001], [D-003]

**Files:**
- Modify: `scripts/predict.py` (full rewrite)

**Replaces:** File-based vault I/O + markdown alert generation

**Data flow:** MongoDB `baselines` collection (latest per metric) + MongoDB `metrics` collection (recent 14 days) → rule evaluation → MongoDB `alerts` collection (insert)

**Steps:**
1. Remove `load_baseline()`, `load_recent_values()`, `save_alert()` — all file-based
2. Keep `ALERT_RULES` dict (4 rules, unchanged)
3. Keep `evaluate_rule()` logic but change data source:
   
   New `load_baseline(db, metric)`:
   ```python
   return db.baselines.find_one(
       {"metric": metric},
       sort=[("computed_at", pymongo.DESCENDING)]
   )
   ```
   
   New `load_recent_values(db, metric, days=14)`:
   ```python
   pipeline = [
       {"$match": {
           "metadata.metric": metric,
           "timestamp": {"$gte": cutoff}
       }},
       {"$group": {
           "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
           "avg_value": {"$avg": "$value"}
       }},
       {"$sort": {"_id": 1}}
   ]
   ```

4. New `save_alert(db, alert)`:
   - `db.alerts.insert_one(alert)` — structured MongoDB document
   - No markdown file generation (agent does that)

5. New `acknowledge_alert(db, alert_id)`:
   - `db.alerts.update_one({"_id": alert_id}, {"$set": {"status": "acknowledged", "acknowledged_at": now}})`

6. CLI:
   - `--mongo-uri`, `--database`
   - `--evaluate` / `--acknowledge`
   - `--rules` (filter to specific rule IDs)
   - `--alert-id` (for acknowledge)
   - Remove: `--vault-dir`
   - Output: JSON to stdout

**Verify:**
Run: `python3 scripts/predict.py --help`
Expected: Shows `--mongo-uri`, `--database`. No `--vault-dir`.

Run: `grep -c "vault_dir\|\.yaml\|\.md\|alerts_dir" scripts/predict.py`
Expected: `0`
<!-- /section -->

---

<!-- section: task-3 keywords: delete, summarize, narrate, cleanup -->
### Task 3: Delete summarize.py and narrate.py

Crystal ref: [D-003], [D-009]

**Files:**
- Delete: `scripts/summarize.py`
- Delete: `scripts/narrate.py`

**Steps:**
1. Delete both files
2. Verify no other script imports them:
   ```bash
   grep -r "summarize\|narrate" scripts/ --include="*.py"
   ```
3. Verify no agent references them:
   ```bash
   grep -r "summarize.py\|narrate.py" agents/
   ```

**Verify:**
Run: `ls scripts/summarize.py scripts/narrate.py 2>/dev/null && echo "EXISTS" || echo "DELETED"`
Expected: `DELETED`

Run: `grep -r "summarize\|narrate" scripts/ agents/ --include="*.py" --include="*.md" | grep -v "test_" | wc -l`
Expected: `0`

⚠️ No test: file deletion, no logic
<!-- /section -->

---

<!-- section: task-4 keywords: agent, analyze-agent, skill, routing -->
### Task 4: Update health-analyze-agent.md and skills/health/SKILL.md

Crystal ref: [D-003], [D-009]

**Files:**
- Modify: `agents/health-analyze-agent.md`
- Modify: `skills/health/SKILL.md`

**Steps:**
1. `health-analyze-agent.md`:
   - Remove all references to `summarize.py` and `narrate.py` (lines 48-49, 58, 66 in current file)
   - Remove `model: sonnet` from frontmatter
   - Update Behavior to state: "Agent queries MongoDB MCP for metrics data and reasons about it directly in the host session. No external scripts for text generation."
   - Keep the action routing (daily/weekly/trend/annual) but change data source from vault files to MongoDB MCP queries
   - Note: full agent refactor is Phase 3; this task only removes broken references to deleted scripts

2. `skills/health/SKILL.md`:
   - Update baseline route dispatch to include `mongo_uri` and `database` parameters
   - Update predict route dispatch to include `mongo_uri` and `database` parameters
   - Remove references to vault as primary storage (line ~112); update to state MongoDB is primary, vault is downstream archive
   - Update status route to query MongoDB (record count, last ingest date) instead of vault file glob

**Verify:**
Run: `grep -c "summarize.py\|narrate.py\|vault.*primary" agents/health-analyze-agent.md skills/health/SKILL.md`
Expected: `0` for each file

Run: `grep "mongo" skills/health/SKILL.md | head -3`
Expected: MongoDB references found in dispatch blocks

⚠️ No test: markdown documentation update
<!-- /section -->

---

<!-- section: task-5 keywords: test, baseline, predict, unit-test -->
### Task 5: Unit tests for baseline.py and predict.py

**Files:**
- Create: `scripts/test_baseline.py` (replace existing which tests old Welford-based code)
- Create: `scripts/test_predict.py`

**Steps:**
1. `test_baseline.py` — mock pymongo, test:
   - `compute_baseline()`: aggregation pipeline returns stats → correct baseline dict
   - `compute_baseline()` with < 30 records → returns None
   - `compute_all_baselines()`: discovers 3 metrics → computes 3 baselines
   - `detect_drift()`: mean shift > 10% → drift_detected=True
   - `detect_drift()`: mean shift < 10% → drift_detected=False
   - Trend detection: first-half mean < second-half → "increasing"
   - `_infer_unit()`: known metrics return correct units

2. `test_predict.py` — mock pymongo, test:
   - `evaluate_rule()` with `deviation_below_pct`: 3 consecutive days below → alert triggered
   - `evaluate_rule()` with `deviation_below_pct`: 2 days below, 1 above → no alert (reset)
   - `evaluate_rule()` with `below_value`: sleep < 6h for 5 days → alert
   - `evaluate_rule()` with `above_value`: glucose > 11 for 3 days → alert
   - `evaluate_all_rules()`: 4 rules, 1 triggers → returns 1 alert
   - `save_alert()`: inserts document with correct fields
   - `acknowledge_alert()`: updates status to "acknowledged"

**Verify:**
Run: `python3 -m pytest scripts/test_baseline.py scripts/test_predict.py -v`
Expected: All tests pass
<!-- /section -->

---

<!-- section: task-6 keywords: agent, baseline-agent, predict-agent, markdown -->
### Task 6: Update baseline + predict agent markdown files

Crystal ref: [D-003], [D-009]

**Files:**
- Modify: `agents/health-baseline-agent.md`
- Modify: `agents/health-predict-agent.md`

**Steps:**
1. `health-baseline-agent.md`:
   - Remove `model: sonnet` from frontmatter (runs in host session)
   - Update description: "Computes baselines from MongoDB aggregation"
   - Update Input: `mongo_uri`, `database`, `action: compute|update`, `metric_type`
   - Update Output: structured baseline results with drift detection
   - Update Behavior:
     - Compute: `python3 scripts/baseline.py --metric <type>` (or all)
     - Agent reads JSON output and reports to user
     - No references to `vault_dir`, `baselines/{metric}.yaml`, or Welford
   - Remove Requirements section mentioning Welford

2. `health-predict-agent.md`:
   - Remove `model: sonnet` from frontmatter
   - Update description: "Evaluates alert rules against MongoDB data"
   - Update Input: `mongo_uri`, `database`, `action: evaluate|acknowledge`
   - Update Output: structured alerts with trigger details
   - Update Behavior:
     - Evaluate: `python3 scripts/predict.py --evaluate`
     - Agent reads JSON output, formats human-readable alert messages
     - Acknowledge: `python3 scripts/predict.py --acknowledge --alert-id <id>`
     - No references to `vault_dir`, `alerts/`, markdown file generation, or Notion sync (Phase 3)

**Verify:**
Run: `grep -c "vault\|\.yaml\|sonnet\|haiku\|narrate\|summarize" agents/health-baseline-agent.md agents/health-predict-agent.md`
Expected: `0` for each file

⚠️ No test: markdown documentation update
<!-- /section -->

---

<!-- section: task-7 keywords: verification, test, full -->
### Task 7: Full verification

**Depends on:** All previous tasks

**Verify:**
Run: `python3 -m pytest scripts/ -v`
Expected: All tests pass with zero failures

Run: `ls scripts/summarize.py scripts/narrate.py 2>/dev/null && echo "EXISTS" || echo "DELETED"`
Expected: `DELETED`

Run: `grep -r "WelfordStats\|build_haiku_prompt\|build_daily_context\|vault_dir" scripts/baseline.py scripts/predict.py 2>/dev/null | wc -l`
Expected: `0`

Run: `python3 scripts/baseline.py --help && python3 scripts/predict.py --help`
Expected: Both show `--mongo-uri`, `--database`. Neither shows `--vault-dir`.
<!-- /section -->

## Decisions

None.
