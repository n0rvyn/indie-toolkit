---
name: health-predict-agent
description: |
  Evaluates personal health rule-based early warning system.
  Checks recent data against baselines and emits alerts for: HRV depression, resting heart rate
  elevation, sleep debt accumulation, blood glucose spikes.
  Syncs alerts to Notion Alerts DB.

tools: [Read, Glob, Bash, Write]
color: blue
maxTurns: 20
---

# health-predict-agent

Runs the early warning rule engine against recent health data and personal baselines stored in MongoDB.

## Input

```yaml
input:
  action: "evaluate"         # "evaluate" or "acknowledge"
  alert_id: null            # for acknowledgement
  mongo_uri: null           # defaults to $MDB_MCP_CONNECTION_STRING
  database: "health"
  notion_alerts_db_id: null  # from config/defaults.yaml
```

## Output

```yaml
output:
  action: "evaluate"
  alerts_triggered: 1
  alerts:
    - id: hrv_low_3d_20260409
      notion_record_id: "abc123"   # present if Notion write succeeded
      rule_id: hrv_low_3d
      severity: moderate
      message: "心血管恢复压力持续偏高，建议减少训练强度或休息"
      triggered_by:
        metric: hrv_sdnn
        current: 38
        baseline: 58
        deviation: -34%
      days_above_threshold: 3
      status: active
  alerts_acknowledged: []
```

## Notion Integration

Use the `notion-with-api` helper shipped with the `shared-utils` plugin:

```bash
NOTION_API="${CLAUDE_PLUGIN_ROOT}/../shared-utils/skills/notion-with-api/scripts/notion_api.py"
# Fallback: NOTION_API="$HOME/.claude/plugins/cache/indie-toolkit/shared-utils/skills/notion-with-api/scripts/notion_api.py"
```

Create an alert row:
```bash
NO_PROXY="*" python3 "$NOTION_API" \
  create-db-item <alerts_db_id> "<title>" --props '{...}'
```

Update an existing alert (acknowledge):
```bash
NO_PROXY="*" python3 "$NOTION_API" \
  update-db-item-properties <page_id> --props '{"Status":"acknowledged"}'
```

Alerts DB ID comes from `config/defaults.yaml`: `notion_database_ids.alerts`

## Alert Rules

| Rule ID | Condition | Severity | Message |
|---------|-----------|----------|---------|
| `hrv_low_3d` | HRV < baseline -30% for 3+ days | moderate | 心血管恢复压力持续偏高，建议减少训练强度或休息 |
| `resting_hr_high` | Resting HR > baseline +15% | moderate | 静息心率异常升高，排除睡眠债因素后建议就医 |
| `sleep_debt_5d` | Sleep < 6h for 5+ days | mild | 持续睡眠债累积，认知表现和免疫功能可能受影响 |
| `blood_glucose_high` | Post-meal glucose > 11 mmol/L for 3+ days | severe | 血糖控制需关注，建议复查并调整饮食 |

## MongoDB Access

All MongoDB reads go through the shared-utils helper (the MongoDB MCP is not used — portable across dev and plugin install):

```bash
# Resolve MONGO_URI: caller should set it, else read from plugin config
MONGO_URI="${MONGO_URI:-$(python3 -c "import yaml,sys; print(yaml.safe_load(open(sys.argv[1])).get('mongo_uri',''))" "${CLAUDE_PLUGIN_ROOT}/config/defaults.yaml")}"

# Read baselines
python3 "${CLAUDE_PLUGIN_ROOT}/../shared-utils/scripts/mongo_query.py" \
  --uri "$MONGO_URI" --db "${MONGO_DB:-health}" --collection baselines \
  --filter '{}' --projection '{"_id": 0}' --limit 100

# Read past 14 days of daily averages from metrics
python3 "${CLAUDE_PLUGIN_ROOT}/../shared-utils/scripts/mongo_query.py" \
  --uri "$MONGO_URI" --db "${MONGO_DB:-health}" --collection metrics \
  --filter '{"date": {"$gte": "<today-14d>"}}' \
  --projection '{"_id": 0, "date": 1, "metadata.metric": 1, "value": 1}' \
  --sort '[["date", 1]]' --limit 1000

# Insert triggered alerts
echo '[{"date": "...", "rule_id": "...", "severity": "...", "message": "...", "status": "active"}]' | \
python3 "${CLAUDE_PLUGIN_ROOT}/../shared-utils/scripts/mongo_insert.py" \
  --uri "$MONGO_URI" --db "${MONGO_DB:-health}" --collection alerts --stdin
```

For alert acknowledgement (updating a single record), there is no shared-utils helper yet — use an ad-hoc Python one-liner:

```bash
python3 -c "
from pymongo import MongoClient
import sys
client = MongoClient('$MONGO_URI')
client['${MONGO_DB:-health}'].alerts.update_one({'_id': sys.argv[1]}, {'\$set': {'status': 'acknowledged'}})
" "$ALERT_ID"
```

Fallback absolute path when `${CLAUDE_PLUGIN_ROOT}` is unset:
`python3 ~/.claude/plugins/cache/indie-toolkit/shared-utils/scripts/mongo_query.py`

## Behavior

1. Evaluate (`action: evaluate`):
   - Load latest baseline for each metric from `db.baselines` (see MongoDB Access)
   - Query past 14 days of daily averages from `db.metrics` (see MongoDB Access)
   - Evaluate each rule: consecutive days check, deviation comparison
   - Insert triggered alerts into `db.alerts` (see MongoDB Access)
   - **Write to Notion Alerts DB**: for each triggered alert, create a page with:
     - Date: today
     - Alert Type: from `rule_id` (mapped to select options)
     - Severity: from severity field
     - Triggered By: "{metric} {current} vs baseline {baseline} ({deviation}%) for {days} consecutive days"
     - Status: `active`
   - Output structured JSON with all alerts (including `notion_record_id` if write succeeded)

2. Acknowledge (`action: acknowledge`):
   - Update `db.alerts` record to `status: acknowledged` (see MongoDB Access for the ad-hoc update pattern)
   - **Update Notion Alerts DB record**: update the record's Status property to `acknowledged` via the `notion-with-api` helper (`update-db-item-properties`)
   - Include `notion_record_id` in acknowledgement output
