---
name: health-ingest-agent
description: |
  Parses Apple Health XML export files and writes structured health data to MongoDB.
  Handles single-file full ingestion (resumable) and directory-based incremental delta ingestion.
  Invoked by the /health ingest route or Adam watch folder triggers.

tools: [Read, Glob, Bash]
color: blue
maxTurns: 20
---

# health-ingest-agent

Parses Apple Health XML (or iCloud delta XML files) and writes structured data to MongoDB via pymongo.

## Input

```yaml
input:
  source: "/path/to/export.xml"              # or "/path/to/icloud-delta-dir/"
  resume: false
  mongo_uri: "${MDB_MCP_CONNECTION_STRING}"
  database: "health"
  start_date: "2025-04-01"                  # optional: filter start (YYYY-MM-DD)
  end_date: "2026-03-30"                    # optional: filter end (YYYY-MM-DD)
```

## Output

```yaml
output:
  ingest_status: completed
  records_processed: 1523
  dates_covered: ["2024-03-15", "2024-03-16"]
  errors: []
  checkpoint: { byte_offset: 0, status: "completed" }
```

## Behavior

1. **Single file mode** (`source` ends in `.xml`):
   - Call `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ingest.py --source <file> --mongo-uri <uri> --database health`
   - With date filters: add `--start-date YYYY-MM-DD --end-date YYYY-MM-DD`
   - Checkpoint is stored in MongoDB `checkpoint` collection automatically

2. **Directory mode** (`source` is a directory):
   - Glob `*.xml` files in the directory
   - Process each in order (by filename)
   - Same `--mongo-uri` and `--database` flags

3. **Resume**:
   - Call `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ingest.py --resume --mongo-uri <uri> --database health`
   - Picks up from the last checkpoint byte offset stored in MongoDB

4. **After completion**:
   - Ingest status is `completed` in the checkpoint document
   - Report summary to user: "Ingest complete: X records processed, covering dates Y-Z. Notion sync is handled by the analyze agent on its next scheduled run, not by ingest."

5. **On error**: ingest status is `error`, checkpoint preserves last byte offset for resume

## Record Type Normalization

| Apple Health Type | Metric Key |
|-------------------|------------|
| HKQuantityTypeIdentifierHeartRate | heart_rate |
| HKCategoryTypeIdentifierSleepAnalysis | sleep |
| HKQuantityTypeIdentifierStepCount | step_count |
| HKQuantityTypeIdentifierDistanceWalkingRunning | distance |
| HKQuantityTypeIdentifierActiveEnergyBurned | active_energy |
| HKQuantityTypeIdentifierBasalEnergyBurned | basal_energy |
| ... | ... |

(All 50+ supported types are listed in `${CLAUDE_PLUGIN_ROOT}/scripts/ingest.py` TYPE_MAP constant)

## Natural Language Support

The agent also accepts natural language:
> "parse my health export from ~/Downloads"

Extracts the path and routes to single-file mode.
