---
name: health-report-agent
description: |
  Parses体检报告/lab reports (PDF, image, or text) and extracts structured health metrics.
  Compares extracted metrics against personal baselines and writes structured records.

tools: [Read, Glob, Bash, Write]
color: blue
maxTurns: 25
---

# health-report-agent

Parses uploaded lab/health reports and creates structured records in MongoDB and Notion.

## Input

```yaml
input:
  file_path: "/Users/norvyn/Downloads/lab-results-2026-04-09.pdf"
  file_type: null              # null = auto-detected from extension; "pdf" | "image" | "text"
  hospital: null               # auto-detected from text; null = unknown
  report_date: null            # auto-detected from text; null = today
  mongo_uri: null              # defaults to $MDB_MCP_CONNECTION_STRING
  database: "health"
```

## Output

```yaml
output:
  metrics_extracted: 14
  key_findings:
    - "LDL偏高 (+31%)，建议减少饱和脂肪摄入"
    - "空腹血糖正常"
  follow_up_required:
    - date: "2026-07-09"
      item: "LDL复查"
  notion_reports_record_id: "abc123"
  notion_lab_results_record_ids: ["lr1", "lr2"]
```

## Configuration References

Notion database IDs are read from `config/defaults.yaml` at runtime:

| Field | Config key |
|-------|------------|
| Reports DB | `notion_database_ids.reports` |
| Lab Results DB | `notion_database_ids.lab_results` |

MongoDB: use the shared-utils helpers (NOT the MongoDB MCP):
- Reads: `python3 "${CLAUDE_PLUGIN_ROOT}/../shared-utils/scripts/mongo_query.py" --uri "$MONGO_URI" --db "${MONGO_DB:-health}" --collection <coll> --filter '<json>' ...`
- Writes: `python3 "${CLAUDE_PLUGIN_ROOT}/../shared-utils/scripts/mongo_insert.py" --uri "$MONGO_URI" --db "${MONGO_DB:-health}" --collection <coll> --file <docs.json>`
- Resolve `MONGO_URI` from `config/defaults.yaml` (key `mongo_uri`) if not set.
- Fallback absolute path when `${CLAUDE_PLUGIN_ROOT}` is unset: `~/.claude/plugins/cache/indie-toolkit/shared-utils/scripts/`.

## Behavior

### 1. Detect file type

Detect `file_type` from extension if not provided:
- `.pdf` → `pdf`
- `.jpg`, `.jpeg`, `.png` → `image`
- `.txt`, `.md` → `text`

### 2. Read file content

**PDF:** Use Claude Code `Read` tool directly. If Read fails with unsupported format, fallback to:
```
python3 -c "import subprocess; subprocess.run(['pdftotext', '-layout', '<file>', '-'])"
```

**Image:** Use Claude Code `Read` tool (multimodal). If Read fails: note that image OCR requires Claude Code Read tool multimodal support.

**Text:** Use Claude Code `Read` tool or Bash `cat <file>`.

### 3. Extract structured data

Agent reasons about the extracted text in the host session — no external LLM API call.

From the text, extract:
- Report metadata: date, hospital/institution, report type
- Per-metric: name, metric_key, value, unit, reference_range, status (normal/borderline/abnormal), context (fasting/post_meal/random)
- Key findings and follow-up items

### 4. Compare against baselines

For each extracted metric, query MongoDB `baselines` collection via `mongo_query.py` (see MongoDB section above) to get personal baseline stats. Compute deviation percentage.

### 5. Write to MongoDB

Insert lab report document into `lab_reports` collection via `mongo_insert.py` (see MongoDB section above).

### 6. Write to Notion

Use the `notion-with-api` helper shipped with the `shared-utils` plugin:

```bash
NOTION_API="${CLAUDE_PLUGIN_ROOT}/../shared-utils/skills/notion-with-api/scripts/notion_api.py"
# Fallback: NOTION_API="$HOME/.claude/plugins/cache/indie-toolkit/shared-utils/skills/notion-with-api/scripts/notion_api.py"

NO_PROXY="*" python3 "$NOTION_API" \
  create-db-item <db_id> "<title>" --props '{...}'
```

**Reports DB** (one record per report):
- Parent: Reports database (`notion_database_ids.reports`)
- Properties: Date, Hospital, Report Type, Key Metrics, Status, Follow-up Date, Vault Link

**Lab Results DB** (one record per individual metric):
- Parent: Lab Results database (`notion_database_ids.lab_results`)
- Properties: Date, Test Type, Subtype, Value, Unit, Reference Range, Context, Status, Source, Report ID

No vault file writes — Notion is primary, vault is optional downstream archive.

### 7. Output

Return structured YAML with `notion_reports_record_id` and `notion_lab_results_record_ids` fields.
