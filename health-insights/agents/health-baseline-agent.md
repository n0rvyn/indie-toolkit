---
name: health-baseline-agent
description: |
  Computes personal health baselines from MongoDB aggregation.
  First run computes baselines from all available history; subsequent runs do rolling window updates.
  Syncs baseline updates and drift alerts to Notion Trends DB and Alerts DB.

tools: [Read, Glob, Bash, Write]
color: blue
maxTurns: 20
---

# health-baseline-agent

Computes statistical baselines from MongoDB metrics data using aggregation pipelines.

## Input

```yaml
input:
  action: "compute"              # "compute" (first ever) or "update" (incremental)
  metric_type: null             # null = all metrics; specific type = single metric
  mongo_uri: null                # defaults to $MDB_MCP_CONNECTION_STRING
  database: "health"
  window_days: 90
  notion_trends_db_id: null      # from config/defaults.yaml
  notion_alerts_db_id: null     # from config/defaults.yaml
```

## Output

```yaml
output:
  action: "compute"
  baselines_computed: 24
  baselines:
    - metric: heart_rate
      status: updated
      data_points: 2740
      mean: 63
      std: 8.2
      min: 48
      max: 85
      trend: stable
      drift_detected: false
    - metric: hrv_sdnn
      status: updated
      data_points: 2610
      mean: 44
      trend: increasing
      drift_detected: true    # > 10% shift from previous baseline
  errors: []
  notion_trends_record_ids: []  # IDs of Notion Trends DB pages with Is Baseline Update: true
  notion_alerts_record_ids: []  # IDs of Notion Alerts DB pages for drift events
```

## Notion Integration

Use the `notion-with-api` helper shipped with the `shared-utils` plugin:

```bash
NOTION_API="${CLAUDE_PLUGIN_ROOT}/../shared-utils/skills/notion-with-api/scripts/notion_api.py"
# Fallback if ${CLAUDE_PLUGIN_ROOT} is unset:
#   NOTION_API="$HOME/.claude/plugins/cache/indie-toolkit/shared-utils/skills/notion-with-api/scripts/notion_api.py"

NO_PROXY="*" python3 "$NOTION_API" \
  create-db-item <db_id> "<title>" --props '{...}'

NO_PROXY="*" python3 "$NOTION_API" \
  update-db-item-properties <page_id> --props '{...}'
```

Database IDs come from `config/defaults.yaml`:
- Trends DB: `notion_database_ids.trends`
- Alerts DB: `notion_database_ids.alerts`

## MongoDB Access

All MongoDB reads use the shared-utils helper. Aggregation pipelines are not covered by `mongo_query.py` (which is `find`-only); for `$group` aggregations, use an inline `python3` block with `pymongo`:

```bash
MONGO_URI="${MONGO_URI:-$(python3 -c "import yaml,sys; print(yaml.safe_load(open(sys.argv[1])).get('mongo_uri',''))" "${CLAUDE_PLUGIN_ROOT}/config/defaults.yaml")}"

# Distinct metric discovery (find with projection, then dedupe in Python)
python3 -c "
from pymongo import MongoClient
import json, sys
client = MongoClient(sys.argv[1])
metrics = client[sys.argv[2]].metrics.distinct('metadata.metric')
print(json.dumps(metrics))
" "$MONGO_URI" "${MONGO_DB:-health}"

# Baseline aggregation (mean / stdDev / min / max / count over a window)
python3 -c "
from pymongo import MongoClient
import json, sys
client = MongoClient(sys.argv[1])
pipeline = [
  {'\$match': {'metadata.metric': sys.argv[3], 'date': {'\$gte': sys.argv[4]}}},
  {'\$group': {
    '_id': None,
    'mean': {'\$avg': '\$value'},
    'std': {'\$stdDevPop': '\$value'},
    'min': {'\$min': '\$value'},
    'max': {'\$max': '\$value'},
    'count': {'\$sum': 1},
  }},
]
print(json.dumps(list(client[sys.argv[2]].metrics.aggregate(pipeline)), default=str))
" "$MONGO_URI" "${MONGO_DB:-health}" "<metric>" "<iso_date_lower_bound>"

# Insert computed baselines
python3 "${CLAUDE_PLUGIN_ROOT}/../shared-utils/scripts/mongo_insert.py" \
  --uri "$MONGO_URI" --db "${MONGO_DB:-health}" --collection baselines \
  --file /tmp/baselines.json
```

## Behavior

### Compute (`action: compute`)

1. Discover all distinct metrics in `db.metrics` using the distinct pattern above
2. For each metric with >= 30 records in the window:
   - Run MongoDB aggregation (`$match` → `$group`) using the aggregation pattern above
   - Run two-phase trend detection (first half vs second half)
   - Insert result into `db.baselines` via `mongo_insert.py`
3. Run drift detection against previous baseline
4. **Sync to Notion Trends DB**: for each baseline updated, create a Trends DB record with `Is Baseline Update: true`
5. **Sync to Notion Alerts DB**: for each baseline with `drift_detected: true`, create an Alerts DB record with:
   - Date: today
   - Alert Type: `hrv_low` or `resting_hr_high` based on metric
   - Severity: `mild` (drift 10-20%), `moderate` (20-30%), `severe` (>30%)
   - Triggered By: `{metric} baseline shifted from {old_mean} to {new_mean} ({drift_pct}%)`
   - Status: `active`
6. Return structured JSON output

### Update (`action: update`)

1. For each metric in `db.baselines`:
   - Re-compute rolling window baseline
   - Run drift detection against the previous baseline
   - Insert new baseline doc (preserving version history)
   - If `drift_detected: true`: create Notion Alerts DB record (same as step 5 above)
2. **Sync to Notion Trends DB**: create/update baseline records with `Is Baseline Update: true`
3. Return structured JSON output

### Drift Detection

- Compares current mean against previous baseline mean
- Flags as drift if deviation > 10%
- Drift severity:
  - 10-20%: `mild`
  - 20-30%: `moderate`
  - >30%: `severe`

### Requirements

- Minimum 30 data points required before computing any baseline
- MongoDB `$stdDevPop` for population standard deviation
- Baselines stored as documents in `db.baselines` collection with `computed_at` timestamps
- Version history preserved (insert-only, no replace)
