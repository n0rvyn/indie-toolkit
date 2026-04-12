---
name: health-analyze-agent
description: |
  Analyzes health trends from MongoDB data. Queries recent metrics via the
  shared-utils mongo_query.py helper and generates structured analyses
  (daily summaries, weekly correlations, trend reports, annual reviews)
  directly in the host session. No external scripts for text generation.

tools: [Read, Glob, Bash, Write]
color: blue
maxTurns: 30
---

# health-analyze-agent

Analyzes health trends from MongoDB metrics data and generates structured analyses.

## Input

```yaml
input:
  action: "daily"           # "daily" | "weekly" | "weekly-digest" | "trend" | "annual"
  date: "2026-04-09"       # YYYY-MM-DD for daily/weekly
  year: null               # for annual action
  topic: null               # for trend action (e.g. "heart_rate")
  mongo_uri: null           # MongoDB connection string (optional, defaults to env)
  database: "health"       # MongoDB database name
```

## Output

```yaml
output:
  action: "daily"
  date: "2026-04-09"
  calendar_context:
    events_found: 3
    categories: {travel: 2, exercise: 1}
    correlation_notes: "出差期间 HRV 下降 18%, 与差旅压力相关"
  summary:
    recovery_score: 82
    deviation_flags:
      - metric: hrv_sdnn
        deviation: -18%
        severity: moderate
  alerts_emitted: []
  notion_trends_record_ids: []    # IDs of Notion Trends DB pages created
```

## Configuration References

Notion database IDs are read from `config/defaults.yaml` at runtime:

| Field | Config key |
|-------|------------|
| Trends DB | `notion_database_ids.trends` |
| Workspace root page | `notion_workspace_page_id` |

## MongoDB Access

All MongoDB reads go through the shared-utils helper (the MongoDB MCP is not used — the shared-utils path is portable across dev and plugin install):

```bash
# Resolve MONGO_URI: caller should set it, else read from plugin config.
MONGO_URI="${MONGO_URI:-$(python3 -c "import yaml,sys; print(yaml.safe_load(open(sys.argv[1])).get('mongo_uri',''))" "${CLAUDE_PLUGIN_ROOT}/config/defaults.yaml")}"

python3 "${CLAUDE_PLUGIN_ROOT}/../shared-utils/scripts/mongo_query.py" \
  --uri "$MONGO_URI" \
  --db "${MONGO_DB:-health}" \
  --collection metrics \
  --filter '{"date": {"$gte": "2026-04-02", "$lte": "2026-04-09"}}' \
  --projection '{"_id": 0}' \
  --sort '[["date", -1]]' \
  --limit 200
```

- The script prints a JSON array on stdout. Pipe to `jq` or parse inline.
- Substitute `--collection` with `baselines`, `alerts`, `lab_reports` as needed.
- Fallback absolute path when `${CLAUDE_PLUGIN_ROOT}` is unset:
  `python3 ~/.claude/plugins/cache/indie-toolkit/shared-utils/scripts/mongo_query.py`
- Requires `shared-utils` plugin installed and `pip3 install pymongo[srv] pyyaml` completed.

## Actions

### `daily`

1. **Calendar context** (optional, graceful fallback if unavailable): query Apple Calendar via:
   ```bash
   osascript -e 'tell application "Calendar" to get {summary, start date} of events of calendars whose start date >= (current date) - 1 * days'
   ```
   Extract categories: travel (出差/flight), exercise (运动/gym/run), overtime (加班/late meeting), social (聚餐/dinner).
   If calendar access fails, skip silently.
2. Query MongoDB for the day's metrics via shared-utils mongo_query.py (see MongoDB Access above)
3. Query baselines from `baselines` collection
4. Compare against baselines, flag deviations
5. Generate structured daily summary inline
6. Return inline to user
7. **Write to Notion Trends DB** via the `notion-with-api` helper (`python3 "${CLAUDE_PLUGIN_ROOT}/../shared-utils/skills/notion-with-api/scripts/notion_api.py" ...`):
   - Create a page in the Trends database with:
     - Date: the analyzed date
     - Metric Type: each metric analyzed
     - Value: the recorded value
     - Source: `apple_health_export`
     - Notes: deviation flags + recovery score
     - Is Baseline Update: `false`
8. **Write Obsidian vault archive**: create `~/Obsidian/HealthVault/daily/{YYYY-MM-DD}/summary.md` with a human-readable daily summary (this is optional downstream archive; Notion is the primary record)

### `weekly-digest`

**Privacy boundary:** summary contains only aggregated values, no raw data, no lab results, no personal identifiers.

1. Query MongoDB for past 7 days of key metrics (heart rate avg, HRV avg, sleep avg, steps avg, active energy avg) via shared-utils mongo_query.py (see MongoDB Access above)
2. Generate a concise Chinese text summary (~200 chars), e.g.: "本周健康摘要: 心率均值72bpm(基线71), HRV 42ms(↓8%), 睡眠6.8h, 步数8200..."
3. **Save to Get笔记**: call `bash ${CLAUDE_PLUGIN_ROOT}/scripts/getnote_digest.sh "<summary_text>" "health-weekly-digest"`
4. **IEF export**: write a markdown insight file to `~/.adam/state/health-insights/ief-exports/`. Use this exact format:
   ```markdown
   ---
   id: "<YYYY-MM-DD>-health-insights-<seq>"
   source: "health-insights"
   url: "notion://<trends_page_id>"
   title: "Weekly Health Insight: <key finding>"
   significance: 3
   tags: [health, <primary_metric>, weekly]
   category: "reference"
   domain: "personal-health"
   date: <YYYY-MM-DD>
   read: false
   ---
   
   <2-3 sentence narrative including metric values, baseline comparison, and recommendation>
   ```
   Use a sequential 3-digit suffix for `<seq>`. pkos `intel-sync` will pick this up via configured `sources.external[].path`.
5. Return inline to user with summary + IEF file path

### `weekly`

1. **Calendar context** (optional, graceful fallback if unavailable): query Apple Calendar via:
   ```bash
   osascript -e 'tell application "Calendar" to get {summary, start date} of events of calendars whose start date >= (current date) - 7 * days'
   ```
   Extract categories: travel (出差/flight), exercise (运动/gym/run), overtime (加班/late meeting), social (聚餐/dinner).
   Include correlation notes in output, e.g.: "本周有2天出差(4/8-4/9), HRV 下降与出差期间睡眠质量下降相关".
   If calendar access fails, skip silently.
2. Query past 7 days of metrics from MongoDB (see MongoDB Access above)
3. Analyze: sleep quality vs HRV, training intensity vs recovery
4. Generate weekly correlation analysis inline
5. Return inline to user
6. **Write to Notion**: create a page under the Health workspace root (not a database page) with the weekly correlation narrative

### `trend`

1. Query requested metric from MongoDB over a 90-day window
2. Identify long-term trend direction
3. Generate trend narrative inline
4. Return inline to user

### `annual`

1. Query all metrics from MongoDB for the requested year
2. Generate annual health narrative inline
3. **Generate heatmap JSON**: call `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/heatmap.py --year <year> --output ~/Obsidian/HealthVault/annual/<year>-heatmap.json` (pure-data aggregation; no LLM). Skip silently if MongoDB is unreachable.
4. Return inline to user (include a note that the heatmap JSON was written if successful)
5. **Write to Notion**: create a page under the Health workspace root with the yearly narrative (include key stats, improvements, regressions, and recommendations)
