---
type: plan
status: active
tags: [mongodb, ingest, time-series, pymongo, migration]
refs: [docs/06-plans/2026-04-11-health-insights-refactor-design.md, docs/11-crystals/2026-04-11-health-insights-refactor-crystal.md]
---

# MongoDB Foundation + Ingest Pipeline — Implementation Plan

**Goal:** Health metrics flow from Apple Health XML export into MongoDB time-series collections with resumable ingestion and checkpoint persistence. Supports full export (initial ingest) and delta directory (incremental updates).

**Architecture:** SAX streaming parser writes directly to MongoDB via pymongo (batch upsert). Checkpoint stored as MongoDB singleton document for atomic resume. Time-series collection with `granularity: "seconds"` for raw heart rate data. No intermediate .tmp files.

**Tech Stack:** Python 3.13, pymongo, xml.sax, MongoDB Atlas (time-series collections)

**Design doc:** docs/06-plans/2026-04-11-health-insights-refactor-design.md

**Crystal file:** docs/11-crystals/2026-04-11-health-insights-refactor-crystal.md

**Threat model:** not applicable

---

<!-- section: task-1 keywords: pymongo, requirements, venv -->
### Task 1: Python environment + pymongo dependency

Crystal ref: [D-001], [D-007]

**Files:**
- Create: `requirements.txt`

**Steps:**
1. Create `requirements.txt` with pymongo dependency:
   ```
   pymongo[srv]>=4.7,<5
   pyyaml>=6.0
   ```
2. Install into the shared venv:
   ```bash
   pip3 install pymongo[srv] pyyaml
   ```
3. Verify pymongo can connect to Atlas:
   ```bash
   python3 -c "
   import os, pymongo
   client = pymongo.MongoClient(os.environ['MDB_MCP_CONNECTION_STRING'])
   print('Connected:', client.server_info()['version'])
   client.close()
   "
   ```

**Verify:**
Run: `python3 -c "import pymongo; print(pymongo.version)"`
Expected: Version 4.7+ printed

⚠️ No test: pure dependency installation, no logic
<!-- /section -->

---

<!-- section: task-2 keywords: mongodb, collections, time-series, schema -->
### Task 2: Create MongoDB `health` database with 5 collections

Crystal ref: [D-001], [D-004]

**Files:**
- No files created (MongoDB schema via MCP/pymongo)

**Steps:**
1. Create `health` database with time-series collection `metrics`:
   ```python
   db.create_collection("metrics", timeseries={
       "timeField": "timestamp",
       "metaField": "metadata",
       "granularity": "seconds"
   })
   ```
2. Create regular collections: `baselines`, `alerts`, `lab_reports`, `checkpoint`
3. Create indexes:
   - `metrics`: `{ "metadata.metric": 1, "timestamp": -1 }` (compound for metric-specific range queries)
   - `baselines`: `{ "metric": 1, "computed_at": -1 }` (latest baseline per metric)
   - `alerts`: `{ "status": 1, "date": -1 }` (active alerts query)
   - `lab_reports`: `{ "date": -1 }` (recent reports)
   - `checkpoint`: none needed (singleton)

**Verify:**
Run: `python3 -c "import os, pymongo; c=pymongo.MongoClient(os.environ['MDB_MCP_CONNECTION_STRING']); print(c['health'].list_collection_names())"`
Expected: `['metrics', 'baselines', 'alerts', 'lab_reports', 'checkpoint']`
<!-- /section -->

---

<!-- section: task-3 keywords: ingest, sax, pymongo, upsert -->
### Task 3: Rewrite ingest.py — SAX parse to MongoDB upsert

Crystal ref: [D-001], [D-003], [D-004], [D-S01]

**Files:**
- Modify: `scripts/ingest.py` (full rewrite)
- Delete: `scripts/checkpoint.py`

**Replaces:** File-based .tmp append + separate checkpoint.py

**Data flow:** XML file → SAX parser → batch accumulator (in-memory, 1000 records) → pymongo `bulk_write()` with `UpdateOne(upsert=True)` keyed by (timestamp, metadata.metric, value) → `metrics` collection. Checkpoint: pymongo `replace_one(upsert=True)` → `checkpoint` collection. Idempotent: re-running the same file produces no duplicates.

**Steps:**
1. Rewrite `ingest.py` preserving:
   - `TYPE_MAP` constant (all 47+ mappings, unchanged)
   - `normalize_type()` function (unchanged)
   - `HealthRecordHandler` SAX handler (rewrite internals)
   - `IngestEngine` class (rewrite internals)
   - CLI interface (`main()` with argparse)

2. `HealthRecordHandler` changes:
   - Remove: `buffer_dir`, `_handles`, `_get_handle`, `_close_all_handles`, `_flush_bucket`, file I/O
   - Add: `batch` list (accumulator), `batch_size` (default 1000), `db` (pymongo database reference)
   - `startElement()`: parse Record attributes → build MongoDB document → append to `batch` → when `len(batch) >= batch_size`, call `_flush_batch()`
   - `_flush_batch()`: build `UpdateOne` ops keyed by `{"timestamp": ts, "metadata.metric": metric, "value": val}` with `upsert=True` → `db.metrics.bulk_write(ops, ordered=False)` → clear batch → update checkpoint. This ensures idempotency on re-run.
   - `endDocument()`: call `_flush_batch()` to flush any remaining partial batch (< batch_size)
   - MongoDB document format per record:
     ```python
     {
         "timestamp": datetime.fromisoformat(start_date),
         "metadata": {
             "metric": rec_type,       # from TYPE_MAP
             "source": source_name,    # extracted from sourceName attr
             "unit": sanitized_unit
         },
         "value": float(value),
         "device": device_short,       # extract model from device string
         "end_date": datetime.fromisoformat(end_date) if end_date else None
     }
     ```

3. `IngestEngine` changes:
   - Remove: `vault_dir`, `buffer_dir`, `checkpoint_dir`, `finalize()` method
   - Remove: `from checkpoint import CheckpointManager`
   - Add: `mongo_uri` parameter, `pymongo.MongoClient` connection
   - Checkpoint via MongoDB: `db.checkpoint.replace_one({"_id": "ingest_checkpoint"}, {...}, upsert=True)`
   - Resume: `db.checkpoint.find_one({"_id": "ingest_checkpoint"})`
   - `ingest_file()`: same SAX streaming logic, but handler writes to MongoDB not files
   - `ingest_directory()`: same glob logic
   - Remove `finalize()` entirely (no .tmp → YAML conversion needed)

4. CLI changes:
   - Remove: `--checkpoint-dir`, `--vault-dir`, `--finalize`
   - Add: `--mongo-uri` (default: `$MDB_MCP_CONNECTION_STRING`), `--database` (default: `health`), `--batch-size` (default: 1000), `--start-date YYYY-MM-DD` (optional, filter records), `--end-date YYYY-MM-DD` (optional, filter records)
   - Keep: `--source`, `--resume`, `--chunk-size-mb`
   - Date filtering: when `--start-date`/`--end-date` provided, SAX handler skips records outside the range (compare parsed date before building MongoDB document)

5. Delete `scripts/checkpoint.py`

**Verify:**
Run: `python3 scripts/ingest.py --help`
Expected: Shows `--mongo-uri`, `--database`, `--batch-size` flags. No `--vault-dir` or `--finalize` flags.

Run: `grep -c "build_.*prompt\|haiku\|sonnet\|from checkpoint" scripts/ingest.py`
Expected: `0` (no LLM references, no checkpoint.py import)
<!-- /section -->

---

<!-- section: task-4 keywords: ingest, test, unit-test -->
### Task 4: Unit tests for refactored ingest.py

**Files:**
- Create: `scripts/test_ingest.py`

**Steps:**
1. Write unit tests covering:
   - `normalize_type()`: known HK types map correctly, unknown types fall through
   - `HealthRecordHandler.startElement()`: builds correct MongoDB document from XML attributes
   - `HealthRecordHandler._flush_batch()`: calls `insert_many` with accumulated batch (mock pymongo)
   - Unit sanitization: `"mmol<180.155>/L"` → `"mmol/L"`
   - Checkpoint round-trip: save → load → resume from byte offset
   - Date parsing: ISO 8601 with timezone variations
   - Idempotency: same record ingested twice → single document in MongoDB (bulk_write upsert dedup)
   - Partial batch flush: handler with 3 records (< batch_size) → `endDocument()` flushes all 3

2. Use `unittest.mock` to mock `pymongo.MongoClient` and `pymongo.collection.Collection`

**Verify:**
Run: `cd /Users/norvyn/Code/Skills/indie-toolkit/health-insights && python3 -m pytest scripts/test_ingest.py -v`
Expected: All tests pass
<!-- /section -->

---

<!-- section: task-5 keywords: ingest, xml, export, run -->
### Task 5: Run initial full ingest (normal user flow)

Crystal ref: [D-004]

**Depends on:** Task 3, Task 4

**Files:**
- No new files (uses refactored ingest.py from Task 3)

**Steps:**
1. This is the standard user flow: user exports from iPhone Health app → gets `export.zip` → unzips → directory contains `export.xml` (~5GB).
   
   Run ingest against the export directory. Per DP-001, limit to 1 year for Atlas free tier test:
   ```bash
   python3 scripts/ingest.py \
     --source ~/Downloads/apple_health_export/export.xml \
     --start-date 2025-04-01 \
     --end-date 2026-03-30
   ```

2. Monitor progress (ingest.py prints every 10K records). The 5GB XML will take several minutes to stream-parse.

3. Verify data in MongoDB:
   - Total record count
   - Spot-check: query heart_rate for a recent date, verify reasonable count (~27K/day)
   - Check checkpoint document shows completed status

4. Test resume: interrupt mid-ingest (Ctrl+C), then resume:
   ```bash
   python3 scripts/ingest.py --resume
   ```
   Verify it picks up from the last checkpoint byte offset, not from the beginning.

**Verify:**
Run: `python3 -c "import os, pymongo; c=pymongo.MongoClient(os.environ['MDB_MCP_CONNECTION_STRING']); print('Total metrics:', c['health']['metrics'].count_documents({}))"`
Expected: Total metrics count > 0 (expected ~10M+ records for 1 year with raw heart rate)

⚠️ No test: operational ingest run, not logic change
<!-- /section -->

---

<!-- section: task-6 keywords: config, defaults, yaml -->
### Task 6: Update config/defaults.yaml

Crystal ref: [D-001]

**Files:**
- Modify: `config/defaults.yaml`
- Modify: `config/schema.yaml`

**Steps:**
1. Add MongoDB config section to `defaults.yaml`:
   ```yaml
   # MongoDB Atlas
   mongodb:
     connection_string: "${MDB_MCP_CONNECTION_STRING}"
     database: "health"
     batch_size: 1000
   ```

2. Remove deprecated fields:
   - `adam_state_dir` (checkpoint now in MongoDB)
   - `adam_tmp_dir` (no temp files)
   - `chunk_size_mb` (pymongo handles batching)
   - `haiku_model` (no external LLM calls — Phase 2 will remove remaining)
   - `sonnet_model` (same)

3. Update `config/schema.yaml`:
   - Add `mongodb` section schema (connection_string: string, database: string, batch_size: integer)
   - Remove deprecated field definitions: `adam_state_dir`, `adam_tmp_dir`, `chunk_size_mb`, `haiku_model`, `sonnet_model`

4. Keep unchanged in defaults.yaml:
   - `vault_path` (still used as downstream archive in Phase 3)
   - `notion_workspace`, `notion_database_ids` (Phase 3)
   - `icloud_watch_folder` (future use)
   - `baseline_*`, `alert_rules` (Phase 2)

**Verify:**
Run: `grep -c "adam_state_dir\|adam_tmp_dir\|chunk_size_mb\|haiku_model\|sonnet_model" config/defaults.yaml`
Expected: `0`

Run: `grep "mongodb:" config/defaults.yaml`
Expected: `mongodb:` found

⚠️ No test: pure config file edit, no logic
<!-- /section -->

---

<!-- section: task-7 keywords: agent, ingest-agent, markdown -->
### Task 7: Update health-ingest-agent.md

Crystal ref: [D-003], [D-009]

**Files:**
- Modify: `agents/health-ingest-agent.md`

**Steps:**
1. Update agent description: references MongoDB instead of HealthVault
2. Update Input schema:
   ```yaml
   input:
     source: "/path/to/export.xml"
     resume: false
     mongo_uri: "${MDB_MCP_CONNECTION_STRING}"
     database: "health"
   ```
3. Update Output schema:
   ```yaml
   output:
     ingest_status: completed
     records_processed: 1523
     dates_covered: ["2024-03-15", "2024-03-16"]
     errors: []
     checkpoint: { byte_offset: 0, status: "completed" }
   ```
4. Update Behavior section:
   - Single file mode: `python3 scripts/ingest.py --source <file> --mongo-uri <uri> --database health`
   - Directory mode: same with directory path
   - Resume: `python3 scripts/ingest.py --resume --mongo-uri <uri> --database health`
   - Remove all references to `--checkpoint-dir`, `--vault-dir`, `--finalize`
   - Remove references to `processing_state.yaml`
5. Remove model name from frontmatter if present (agent runs in host session)

**Verify:**
Run: `grep -c "vault\|finalize\|checkpoint-dir\|processing_state" agents/health-ingest-agent.md`
Expected: `0`

Run: `grep "mongo" agents/health-ingest-agent.md | head -3`
Expected: MongoDB references found

⚠️ No test: markdown documentation update, no logic
<!-- /section -->

---

<!-- section: task-8 keywords: verification, build, test -->
### Task 8: Full verification

**Depends on:** All previous tasks

**Verify:**
Run: `cd /Users/norvyn/Code/Skills/indie-toolkit/health-insights && python3 -m pytest scripts/ -v`
Expected: All tests pass with zero failures

Run: `python3 scripts/ingest.py --help`
Expected: CLI shows MongoDB-based flags, no file-based flags

Run: `python3 -c "import os, pymongo; c=pymongo.MongoClient(os.environ['MDB_MCP_CONNECTION_STRING']); db=c['health']; print('Collections:', db.list_collection_names()); print('Metrics count:', db.metrics.count_documents({})); print('Checkpoint:', db.checkpoint.find_one({'_id': 'ingest_checkpoint'}))"`
Expected: 5 collections listed, metrics count > 0, checkpoint document present or null (if no ingest run yet)
<!-- /section -->

## Decisions

### [DP-001] Migration scope: full 10 years or 1 year subset? (recommended)

**Context:** Atlas free tier has 512MB. Full 10-year raw data (3900 days, ~100M heart rate records) will exceed free tier. User said "use free tier and 1 year data to test."
**Options:**
- A: Migrate only 2025-04-01 to 2026-03-30 (1 year) — fits in free tier (~310MB), migrate rest when self-hosted MongoDB is ready
- B: Migrate all, let Atlas reject when full — wastes migration time, unclear failure mode
**Chosen:** A — Migrate 1 year (2025-04 to 2026-03), add --start-date and --end-date flags to migrate_tmp.py
