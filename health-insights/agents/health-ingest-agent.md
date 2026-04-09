---
name: health-ingest-agent
description: |
  Parses Apple Health XML export files and writes structured health data to the HealthVault.
  Handles single-file full ingestion (resumable) and directory-based incremental delta ingestion.
  Invoked by the /health ingest route or Adam watch folder triggers.

model: sonnet
tools: [Read, Glob, Bash, Write]
color: blue
maxTurns: 20
---

# health-ingest-agent

Parses Apple Health XML (or iCloud delta XML files) and writes structured daily YAML to the HealthVault.

## Input

```yaml
input:
  source: "/path/to/export.xml"              # or "/path/to/icloud-delta-dir/"
  resume_from_byte: 0                        # for resumable full ingestion
  processing_state:
    last_processed_file: null
    last_processed_byte: 0
    ingest_status: idle                      # idle | running | completed | interrupted
```

## Output

```yaml
output:
  ingest_status: completed
  records_processed: 1523
  daily_buckets_created: ["2024-03-15", "2024-03-16"]
  errors: []
  next_resume_byte: null                     # null if completed
  new_data_types_encountered: ["heart_rate", "sleep"]
```

## Behavior

1. **Single file mode** (`source` ends in `.xml`):
   - If `resume_from_byte > 0`: seek to that byte and resume
   - Else: process from beginning
   - Call `ingest.py --source <file> --checkpoint-dir <state>/checkpoints --vault-dir <vault> --finalize`

2. **Directory mode** (`source` is a directory):
   - Glob `*.xml` files in the directory
   - Process each in order (by filename timestamp)
   - Write each to vault incrementally

3. **After completion**: update `processing_state.yaml` with new `last_processed_file` and `ingest_status: completed`

4. **On error**: set `ingest_status: interrupted`, save checkpoint, return error list

## Record Type Normalization

| Apple Health Type | Vault File |
|-------------------|-------------|
| HKQuantityTypeIdentifierHeartRate | heart_rate |
| HKCategoryTypeIdentifierSleepAnalysis | sleep |
| HKQuantityTypeIdentifierStepCount | step_count |
| HKQuantityTypeIdentifierDistanceWalkingRunning | distance |
| HKQuantityTypeIdentifierActiveEnergyBurned | active_energy |
| HKQuantityTypeIdentifierBasalEnergyBurned | basal_energy |
| ... | ... |

(All 90+ supported types are listed in `scripts/ingest.py` TYPE_MAP constant)

## Natural Language Support

The agent also accepts natural language:
> "parse my health export from ~/Downloads"

Extracts the path and routes to single-file mode.
