# Storage Tradeoff: Single sessions.db

Date: 2026-04-12
Decision source: Phase 1 dev-guide DP-001 (Chosen: A)

## Current choice: extend existing sessions.db

The dual-loop architecture adds 8 new tables (plugin_events, plugin_changes,
analysis_checkpoints, baselines, knowledge_distilled, session_links, pre_brief_hints,
ai_behavior_audit) into the existing `~/.claude/session-reflect/sessions.db`.

Rationale:
- Single source of truth — every JOIN across sessions/dimensions/telemetry/baselines
  works without cross-database queries
- Backup, vacuum, and migration tooling all operate on one file
- SQLite handles the projected scale (10K-50K sessions × 8 telemetry rows + 8 audit rows
  per session = ~1M rows total) comfortably for years
- Zero-dependency stdlib `sqlite3` already in use

Tradeoff accepted:
- Single failure domain — corruption affects all data
- Backup file size grows monotonically
- Some tables (plugin_events, ai_behavior_audit) grow much faster than core sessions table

## Split triggers (when to migrate)

When ANY of the following becomes true, split telemetry tables into a separate
`plugin-analytics.db`:

| Trigger | Threshold | Why |
|---------|-----------|-----|
| File size | sessions.db > 2 GB | SQLite vacuum/backup ergonomics degrade; backup snapshots become slow |
| Query latency | median /reflect query > 500 ms | User-facing interactive boundary; below this users perceive instant |

Either trigger is sufficient. If both are crossed simultaneously, prioritize the
file-size split first (it usually unblocks the latency too).

## What to split first

When the trigger fires, move the high-volume telemetry tables:
1. `plugin_events` (full-text Skill/Agent capture; biggest projected size)
2. `ai_behavior_audit` (full CLAUDE.md rule coverage; many rows per session)

Keep in sessions.db (low volume, frequently joined):
- sessions, tool_calls, corrections, emotion_signals, prompt_assessments, process_gaps
- session_features, session_outcomes, token_audit, rhythm_stats
- analysis_checkpoints, baselines, session_links, knowledge_distilled, pre_brief_hints

## Migration mechanics (when needed)

1. Add `~/.claude/session-reflect/plugin-analytics.db` with new schema
2. ATTACH DATABASE in queries that need cross-DB JOINs
3. Move plugin_events + ai_behavior_audit rows in a single transaction (ATTACH + INSERT INTO new SELECT FROM old)
4. Drop old tables, vacuum sessions.db
5. Update `sessions_db.py` to route those table operations to the new DB

This is a future migration. Do not implement preemptively.
