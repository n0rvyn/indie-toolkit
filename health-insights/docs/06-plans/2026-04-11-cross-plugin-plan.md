---
type: plan
status: active
tags: [cross-plugin, getnote, pkos, ief, delivery, wechat, calendar]
refs: [docs/06-plans/2026-04-11-health-insights-refactor-design.md, docs/11-crystals/2026-04-11-health-insights-refactor-crystal.md]
---

# Cross-Plugin Integration + Delivery — Implementation Plan

**Goal:** Health-insights produces outputs consumed by Get笔记, pkos, and Adam delivery rules for WeChat push.

**Architecture:** Agent markdown defines cross-plugin behavior. Get笔记 integration via existing `getnote.sh` bash API. pkos integration via IEF file format. Adam delivery via task template + delivery rule configuration. Calendar enrichment via mactools plugin calendar query. All integrations are agent-layer (markdown instructions), not code.

**Tech Stack:** getnote.sh (bash API), IEF markdown format, Adam REST API (delivery rules, task templates)

**Design doc:** docs/06-plans/2026-04-11-health-insights-refactor-design.md

**Crystal file:** docs/11-crystals/2026-04-11-health-insights-refactor-crystal.md

**Threat model:** not applicable

---

<!-- section: task-1 keywords: getnote, digest, weekly -->
### Task 1: Get笔记 weekly health digest

Crystal ref: [D-008], [D-S02]

**Files:**
- Modify: `agents/health-analyze-agent.md`
- Create: `scripts/getnote_digest.sh` (thin wrapper calling getnote.sh)

**Steps:**
1. Add `weekly-digest` action to `health-analyze-agent.md`:
   - Agent queries MongoDB MCP for past 7 days of key metrics (heart rate avg, HRV avg, sleep avg, steps avg, active energy avg)
   - Agent generates a concise Chinese text summary (~200 chars): "本周健康摘要: 心率均值72bpm(基线71), HRV 42ms(↓8%), 睡眠6.8h, 步数8200..."
   - **Privacy boundary**: summary contains only aggregated values, no raw data, no lab results, no personal identifiers
   - Agent calls: `bash scripts/getnote_digest.sh "<summary_text>" "health-weekly-digest"`

2. Create `scripts/getnote_digest.sh`:
   ```bash
   #!/bin/bash
   # Thin wrapper: save health digest to Get笔记
   # Usage: getnote_digest.sh "<content>" "<tag>"
   SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
   GETNOTE_SH="${GETNOTE_SH:-/Users/norvyn/Code/Skills/indie-toolkit/pkos/skills/getnote/scripts/getnote.sh}"
   
   TITLE="健康周报 $(date +%Y-%m-%d)"
   CONTENT="$1"
   TAG="${2:-health-weekly-digest}"
   
   "$GETNOTE_SH" save_note "$TITLE" "$CONTENT" "$TAG"
   ```

3. Add `/health digest` route to SKILL.md routing table

**Verify:**
Run: `bash scripts/getnote_digest.sh "测试健康摘要" "test-health"`
Expected: Note created in Get笔记 (check via `getnote.sh list_notes`)

⚠️ No test: shell script wrapper, integration test only
<!-- /section -->

---

<!-- section: task-2 keywords: ief, pkos, export -->
### Task 2: pkos IEF export

Crystal ref: [D-008]

**Files:**
- Modify: `agents/health-analyze-agent.md`
- Create: `vault/insights/` directory structure (IEF export target)

**Steps:**
1. Add IEF export step to `health-analyze-agent.md` `weekly` action:
   - After generating weekly analysis, produce an IEF markdown file:
   ```markdown
   ---
   id: "2026-04-11-health-insights-001"
   source: "health-insights"
   url: "notion://health-dashboard"
   title: "Weekly Health Insight: HRV declining trend"
   significance: 3
   tags: [health, hrv, recovery, weekly]
   category: "reference"
   domain: "personal-health"
   date: 2026-04-11
   read: false
   ---
   
   HRV shows declining trend over past 2 weeks (42ms → 36ms, -14%).
   Correlated with increased work hours (calendar shows 3 late nights).
   Recommend: reduce training intensity this week, prioritize sleep.
   ```
   - Write to `~/.adam/state/health-insights/ief-exports/` directory
   - pkos `intel-sync` will pick this up via configured `sources.external[].path`

2. Create export directory: `mkdir -p ~/.adam/state/health-insights/ief-exports/`

3. Document the IEF export path in agent instructions so pkos can be configured to read from it

**Verify:**
Run: `ls ~/.adam/state/health-insights/ief-exports/`
Expected: Directory exists (empty until first weekly run)

⚠️ No test: IEF is a markdown file format, no logic
<!-- /section -->

---

<!-- section: task-3 keywords: calendar, mactools, context -->
### Task 3: Calendar context enrichment

Crystal ref: [D-008]

**Files:**
- Modify: `agents/health-analyze-agent.md`

**Steps:**
1. Add calendar query step to `health-analyze-agent.md` `daily` and `weekly` actions:
   - Before generating analysis, query mactools calendar for events in the analysis date range
   - Use `/calendar` skill or direct AppleScript via Bash:
     ```bash
     osascript -e 'tell application "Calendar" to get {summary, start date} of events of calendars whose start date >= (current date) - 7 * days'
     ```
   - Extract event categories: travel (出差/flight), exercise (运动/gym/run), overtime (加班/late meeting), social (聚餐/dinner)
   - Inject as context into the analysis narrative: "本周有2天出差(4/8-4/9), HRV 下降与出差期间睡眠质量下降相关"

2. Add calendar context as optional section in agent output:
   ```yaml
   calendar_context:
     events_found: 3
     categories: {travel: 2, exercise: 1}
     correlation_notes: "出差期间 HRV 下降 18%, 与差旅压力相关"
   ```

3. Agent should gracefully handle missing calendar access (mactools not available or no calendar events)

**Verify:**
Run: `grep "calendar\|Calendar\|osascript" agents/health-analyze-agent.md`
Expected: Calendar query instructions present

⚠️ No test: agent behavior, verified by markdown content
<!-- /section -->

---

<!-- section: task-4 keywords: adam, delivery, wechat, alert -->
### Task 4: Adam delivery rules for WeChat push

Crystal ref: [D-008]

**Files:**
- Create: `config/adam-task-templates.yaml` (health-specific Adam cron templates)

**Steps:**
1. Create `config/adam-task-templates.yaml` with health task templates:
   ```yaml
   templates:
     - name: "health-daily-analyze"
       description: "Daily health analysis and Notion sync"
       schedule: "0 7 * * *"  # 7am daily
       prompt: "/health analyze --daily"
       roleId: null  # uses 钟南山 role
       enabled: true
       
     - name: "health-weekly-digest"
       description: "Weekly health digest to Get笔记 + IEF export"
       schedule: "0 9 * * 1"  # 9am Monday
       prompt: "/health digest"
       roleId: null
       enabled: true
       
     - name: "health-predict"
       description: "Daily alert evaluation"
       schedule: "30 7 * * *"  # 7:30am daily (after analyze)
       prompt: "/health predict"
       roleId: null
       enabled: true
       
     - name: "health-baseline-update"
       description: "Weekly baseline recomputation"
       schedule: "0 8 * * 0"  # 8am Sunday
       prompt: "/health baseline"
       roleId: null
       enabled: true
   ```

2. Document Adam delivery rule configuration for health alerts:
   - Event: `task_complete` where `templateId` matches `health-predict`
   - Target: WeChat channel (same channel as existing delivery rules)
   - `skipOriginChannel: false` (always deliver, even if triggered from same channel)
   
   Note: Actual delivery rule creation requires Adam server API call (`POST /delivery-rules`). This template documents the configuration; the user creates the rule via Adam Web UI or API.

3. Document delivery rule for daily summary:
   - Event: `task_complete` where `templateId` matches `health-daily-analyze`
   - Target: WeChat channel
   - `skipOriginChannel: true` (don't echo back if triggered from WeChat)

**Verify:**
Run: `cat config/adam-task-templates.yaml`
Expected: 4 templates defined with correct schedules

⚠️ No test: YAML configuration file
<!-- /section -->

---

<!-- section: task-5 keywords: skill, routing, commands -->
### Task 5: Update SKILL.md routing

Crystal ref: [D-009]

**Files:**
- Modify: `skills/health/SKILL.md`

**Steps:**
1. Add new routes:
   - `/health digest` → health-analyze-agent with `action: weekly-digest` (Get笔记 + IEF export)
   - `/health setup-delivery` → prints Adam delivery rule setup instructions
2. Update existing routes:
   - `/health analyze` → add note: "includes calendar context enrichment when mactools available"
   - `/health predict` → add note: "triggered daily by Adam cron; alerts delivered to WeChat"
3. Add cross-plugin documentation section:
   ```markdown
   ## Cross-Plugin Integration
   
   | Target | Mechanism | Frequency | Data |
   |--------|-----------|-----------|------|
   | Get笔记 | getnote.sh save_note | Weekly (Monday 9am) | Aggregate health summary |
   | pkos | IEF file export | Weekly | Health insight → intel-sync |
   | WeChat | Adam delivery rule | Daily + on alert | Summary + alerts |
   | Calendar | mactools query | On analyze | Event context enrichment |
   ```

**Verify:**
Run: `grep -c "digest\|delivery\|calendar\|cross-plugin\|Get笔记\|IEF" skills/health/SKILL.md`
Expected: > 5 references

⚠️ No test: markdown documentation
<!-- /section -->

---

<!-- section: task-6 keywords: verification, full -->
### Task 6: Full verification

**Depends on:** All previous tasks

**Verify:**
Run: `python3 -m pytest scripts/ -v`
Expected: All tests pass (49+)

Run: `bash scripts/getnote_digest.sh --help 2>&1 || head -3 scripts/getnote_digest.sh`
Expected: Script exists and is executable

Run: `ls ~/.adam/state/health-insights/ief-exports/ && echo "EXISTS"`
Expected: Directory exists

Run: `cat config/adam-task-templates.yaml | grep "name:" | wc -l`
Expected: `4` (4 templates)

Run: `grep "digest" skills/health/SKILL.md`
Expected: Digest route present
<!-- /section -->

## Decisions

None.
