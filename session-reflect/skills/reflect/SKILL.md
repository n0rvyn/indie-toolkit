---
name: reflect
description: "Use when the user says 'reflect', 'reflection', '反思', '复盘', 'coaching', 'coach me', or wants to review and improve their AI collaboration patterns. Analyzes recent sessions and produces coaching feedback with specific improvement suggestions."
user_invocable: true
model: haiku
---

## Overview

Analyze recent AI coding sessions to produce coaching feedback on prompt quality, process maturity, correction patterns, and growth over time. Single entry point for all session-reflect capabilities.

## Arguments

Parse from user input:
- `--days N`: Number of days to look back (default: 1)
- `--project NAME`: Filter by project name (optional)
- `--profile`: Output/update user collaboration profile instead of coaching feedback
- `--auto`: (Reserved for future scheduled execution — not implemented yet, note if user tries it)
- `--backfill`: Run full historical backfill via the standalone orchestrator (`scripts/backfill.py`). When present, skips Steps 1-9 and dispatches to backfill mode (see new section below).
- `--full`: When combined with `--backfill`, force all-time discovery (`/reflect --backfill --full`).
- `--dry-run`: When combined with `--backfill`, only reports session count + cost estimate without analyzing.
- `--limit N`: When combined with `--backfill`, process at most N sessions in this invocation.
- `--force-all`: When combined with `--backfill`, re-analyze every discovered session ignoring checkpoints.
- `--task-trace SESSION_ID`: Return the linked multi-session task chain for one session instead of coaching feedback.
- `--baselines`: Query current plugin/component baseline rows instead of coaching feedback.
- `--rebaseline`: Recompute baseline rows without re-running parse/backfill.
- `--window SPEC`: When combined with `--rebaseline`, choose the baseline window (`30d`, `60d`, `all`; default `60d`).
- `--enrich`: Finish LLM-based enrichment on sessions marked `enrichment_pending=1` by backfill/parse. Dispatches the `session-reflect:session-parser` agent in the host session (no CLI subprocess). Skip coaching output.
- `--enrich-limit N`: When combined with `--enrich`, cap the number of sessions enriched this invocation (default 20). Keeps per-run cost bounded.

Also check `~/.claude/session-reflect.local.md` for configuration overrides (YAML frontmatter with `default_days`, `include_codex`, `projects` fields). If file doesn't exist, use defaults.

## Arguments (query mode)

Query mode is triggered when any of these flags are present:
- `--dimension DIMENSION`: Query by dimension (token_audit, session_outcomes, session_features, context_gaps, rhythm_stats, skill_invocations, corrections)
- `--min-significance N`: Return sessions with significance >= N
- `--outcome VALUE`: Return sessions with specific outcome (completed, interrupted, failed)
- `--project-complexity OP:VALUE`: Return sessions by complexity threshold (e.g., gt:0.8, lt:0.3, eq:0.5)
- `--task-trace SESSION_ID`: Return the linked task chain and show each session's outcome/time
- `--baselines`: Return baseline rows as a markdown table

When query flags are present, Steps 1-7 are skipped and the skill goes directly to Step 9 (Query Execution).

## Query Mode Routing

If any query flag is present (`--dimension`, `--min-significance`, `--outcome`, `--project-complexity`, `--task-trace`, `--baselines`):
Skip to Step 9 (Query Execution)

## Backfill Mode Routing

If `--backfill` flag is present:
- Skip all standard process steps
- Dispatch to the Backfill Mode section below
- Only backfill-supported args are forwarded to backfill.py (`--days`, `--full`, `--dry-run`, `--limit`, `--force-all`)

## Rebaseline Mode Routing

If `--rebaseline` flag is present:
- Skip all standard process steps
- Run `scripts/compute_baselines.py` directly
- Forward only rebaseline-supported args (`--window`, `--plugin`)

## Enrich Mode Routing

If `--enrich` flag is present:
- Skip all standard process steps
- Dispatch to the Enrich Mode section below
- Only `--enrich-limit` is honored here

## Backfill Mode

Invoke the standalone backfill orchestrator. The skill is a thin wrapper — actual work runs in `scripts/backfill.py` so that the same engine works under cron/launchd/external scheduler.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/backfill.py \
  {--days N if specified} \
  {--full if specified} \
  {--dry-run if specified} \
  {--limit N if specified} \
  {--force-all if specified}
```

Stream the script's stdout to the user; do not transform.

If `--dry-run` was used: present a confirmation prompt before suggesting the user re-run without `--dry-run`. Do not auto-proceed — backfill on a 6-month corpus is multi-hour and multi-dollar.

After completion (non-dry-run): suggest the user run `/reflect --rebaseline` next (Phase 4 capability; if not yet implemented, note this and skip).

## Rebaseline Mode

Run baseline recomputation without re-running session parse:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compute_baselines.py \
  --window {window or 60d} \
  {--plugin NAME if specified} \
  --replace-existing
```

Stream stdout to the user and then suggest `/reflect --baselines`.

## Enrich Mode

Incrementally finish LLM-based enrichment on sessions marked `enrichment_pending=1`
by prior backfill/parse runs. This is the deferred half of the two-stage backfill
architecture: scripts populate structured data and run heuristic audit; this mode
dispatches the `session-reflect:session-parser` agent to fill in LLM-classified
dimensions, `task_summary`, and remaining `ai_behavior_audit` rules.

Steps:

1. Query pending count and the next batch:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sessions_db.py --query pending-enrichment --limit {enrich_limit or 20}
   ```
   If the returned list is empty, print "No sessions awaiting enrichment." and stop.

2. For each session in the batch, load the parsed JSON (re-parse if no cached JSON file exists) and dispatch the agent via the Task tool:
   - `subagent_type`: `session-reflect:session-parser`
   - `description`: brief, e.g. "Enrich session {short_id}"
   - `prompt`: the parsed session JSON plus an instruction to return the schema documented in `${CLAUDE_PLUGIN_ROOT}/agents/session-parser.md` (`session_dna`, `task_summary`, `corrections`, `emotion_signals`, `prompt_assessments`, `process_gaps`, `ai_behavior_audit`, `dimensions`, `significance`).

3. Parse each agent response. If valid JSON matching the expected shape, persist via:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sessions_db.py --mark-enriched --session-id {id} --payload {json}
   ```
   (pipe JSON via stdin if the CLI supports `--payload -`). On failure, leave the session `enrichment_pending=1` and log the error line.

4. Report progress: total enriched, remaining pending. Suggest re-running `/reflect --enrich` until the pending count reaches zero.

Do not spawn `claude -p` or any CLI; all LLM work happens in the current Claude Code session via the agent dispatch mechanism.

## Process

### Step 1: Discover Sessions

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/extract-sessions.py --days {days} {--project NAME if specified} --source all --format json
```

If no sessions found: output "No sessions found for the last {days} day(s). Try `--days 7` for a wider range." and stop.

Count sessions. If more than 30, suggest narrowing with `--project`.

### Step 2: Filter Already-Analyzed Sessions

Query `~/.claude/session-reflect/sessions.db` for already-analyzed session IDs:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sessions_db.py --query-ids
```

- For `--days 1` (default): **skip filtering** — always re-analyze today's sessions for fresh feedback
- For `--days >1`: filter out session IDs already in sessions.db, unless `--profile` flag is set (profile benefits from full history)
- If all sessions filtered out: "All sessions in this range have been analyzed. Use `--days {larger N}` for more sessions, or re-run with `--days 1` for today."

If sessions.db doesn't exist yet, proceed with all discovered sessions (sessions_db.py --init will create it on first use).

### Step 3: Parse Each Session

For each discovered session, run the appropriate parser based on `source` field:

```bash
# For claude-code sessions:
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/parse_claude_session.py --input {file_path} --sqlite-db ~/.claude/session-reflect/sessions.db --enrich

# For codex sessions:
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/parse_codex_session.py --input {file_path} --sqlite-db ~/.claude/session-reflect/sessions.db --enrich
```

Collect all parsed JSON results. Each parser run writes the base session row, plugin telemetry (when present), and enrichment/audit data in one path. If a parser fails on a session, log the error and continue.

### Step 3b: Merge /insights Facets (optional)

For each parsed session, check if /insights has facets data:

```bash
cat ~/.claude/usage-data/facets/{session_id}.json 2>/dev/null
```

If found: add `insights_facets` field to the parsed session JSON. This gives session-parser additional signals (outcome, friction, response times).

If not found: proceed without it. This is not an error.

### Step 4: Enrichment behavior

`parse_claude_session.py` and `parse_codex_session.py` with `--enrich` run local
**rule-based** audit only (style bannwords, tool-sequence heuristics). They do
NOT call any LLM or the `claude` CLI. Each processed session is stored with
`enrichment_pending = 1`.

For the current `/reflect` flow this is enough to produce coaching feedback on
recent sessions. LLM-classified dimensions arrive later, after the user runs
`/reflect --enrich` which dispatches the `session-reflect:session-parser` agent
for each pending session.

**Failure handling**: if the audit step fails, keep the base parse result and
continue. Empty arrays/defaults are acceptable for:
- `ai_behavior_audit`
- `corrections`
- `emotion_signals`
- `prompt_assessments`
- `process_gaps`

### Step 5: Route by Mode

#### Default mode (coaching feedback):

1. Dispatch `session-reflect:coach` agent with all enriched sessions
2. Agent returns coaching feedback as Markdown
3. Save feedback to `~/.claude/session-reflect/reflections/{YYYY-MM-DD}.md`:
   - Create directory if it doesn't exist: `mkdir -p ~/.claude/session-reflect/reflections`
   - If file already exists for today, append with `---` separator
4. Upsert all analyzed sessions into sessions.db:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/parse_claude_session.py --input {file_path} --sqlite-db ~/.claude/session-reflect/sessions.db --enrich
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/parse_codex_session.py --input {file_path} --sqlite-db ~/.claude/session-reflect/sessions.db --enrich
   ```
5. Present coaching feedback to user
6. Before presenting the final coaching feedback, look up the newest analyzed session:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sessions_db.py --query unfinished --session-id {latest_session_id}
   ```
   - If a row is returned: prepend one short line such as `Previous unfinished linked session: {session_id} ({outcome}) at {time_start}` before the coaching bullets
   - If the query returns `null`: skip silently

#### --profile mode:

1. Read existing profile: `cat ~/.claude/session-reflect/profile.yaml 2>/dev/null` (or "No existing profile")
2. Dispatch `session-reflect:profiler` agent with all enriched sessions + existing profile
3. Agent returns updated profile as YAML
4. Write to `~/.claude/session-reflect/profile.yaml`:
   - Create directory if needed: `mkdir -p ~/.claude/session-reflect`
5. Present profile summary to user

### Step 6: Growth Check

After Step 5 (default mode only), check if growth tracking is possible:

1. List reflection files: `ls ~/.claude/session-reflect/reflections/*.md 2>/dev/null | sort | tail -4`
2. If 3+ files exist (including today's):
   - Read the 2-3 most recent previous reflections (not today's)
   - Read profile if exists: `cat ~/.claude/session-reflect/profile.yaml 2>/dev/null`
   - Dispatch `session-reflect:growth-tracker` agent with current reflection + previous reflections + profile
   - Append growth observations to the output
3. If <3 files: append note "Growth tracking will activate after 3+ reflections."

### Step 7: Routing

If any query flag is present:
Skip to Step 9

Otherwise:
Continue to Step 8 (Insight Export)

### Step 8: Insight Export

After coaching feedback is saved, export high-significance sessions as IEF for PKOS.

1. Query sessions.db for insights from the analyzed set:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sessions_db.py --query-insights --min-significance 3 --limit 20
   ```

2. If insights are returned (non-empty list):
   - Dispatch `session-reflect:insight-exporter` agent with the insights JSON
   - Agent writes IEF files to `~/.claude/session-reflect/insights/{YYYY-MM}/`
   - Report: "Exported {N} insights to PKOS intel queue."

3. If no insights (empty list): skip silently.

### Step 9: Query Execution

When query flags are present (bypass Steps 1-7):

1. Determine query type from flags:
   - `--dimension`: call `sessions_db.py --query dimension --dimension {dim}`
   - `--min-significance`: call `sessions_db.py --query significance --min-significance {N}`
   - `--outcome`: call `sessions_db.py --query outcomes --outcome {val}`
   - `--project-complexity gt:0.8`: call `sessions_db.py --query complexity --op gt --value 0.8`
   - `--task-trace SESSION_ID`: call `sessions_db.py --query task-trace --session-id {id}`
   - `--baselines`: call `sessions_db.py --query baselines {--plugin} {--component} {--window-days 60 if unspecified}`

2. Build and execute the sessions_db.py command:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sessions_db.py --query {type} [filters]
   ```

3. Parse JSON results and format as readable data table:
   - For `--dimension`: group by dimension field, show session_id, project, date, key metric
   - For `--outcome`: show session list with outcome details
   - For `--project-complexity`: sort by complexity descending, show top sessions
   - For `--min-significance`: show sessions with significance scores
   - For `--task-trace`: render a markdown table with `session_id | project | outcome | time`
   - For `--baselines`: render a markdown table with `plugin | component | metric | value | sample | window | commits`

4. Present formatted table to user. No coaching feedback in query mode.

## Error Handling

- **No sessions**: clear message with `--days` suggestion
- **Parser failure on a session**: skip, note in footer
- **session-parser agent failure**: use placeholder values, note in footer
- **coach/profiler agent failure**: show raw parsed session summaries as fallback
- **growth-tracker failure**: skip growth section, show coaching feedback only
- **/insights facets missing**: silent (not an error)
- **profile.yaml missing**: profiler creates from scratch
- **sessions.db missing**: sessions_db.py --init auto-creates on first upsert

## Completion Criteria

- Coaching feedback (or profile) generated and displayed
- Reflection saved to `~/.claude/session-reflect/reflections/{date}.md` (default mode)
- sessions.db updated with newly analyzed sessions via parse script upsert (default mode)
