-- session-reflect SQLite schema
-- 17 tables covering all 15 analysis dimensions

-- Core sessions table
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    source       TEXT NOT NULL,          -- 'claude-code' | 'codex'
    project      TEXT,
    project_path TEXT,
    branch       TEXT,
    model        TEXT,
    time_start   TEXT,
    time_end     TEXT,
    duration_min REAL,
    turns_user   INTEGER,
    turns_asst   INTEGER,
    tokens_in    INTEGER,
    tokens_out   INTEGER,
    cache_read   INTEGER,
    cache_create INTEGER,
    cache_hit_rate REAL,
    session_dna  TEXT,                  -- 'explore'|'build'|'fix'|'chat'|'mixed'
    task_summary TEXT,
    analyzed_at  TEXT,
    outcome      TEXT,                  -- 'completed'|'interrupted'|'failed'
    enrichment_pending INTEGER DEFAULT 1,  -- 1 until LLM dimension enrichment runs via /reflect --enrich
    enriched_at  TEXT                   -- set when the session-parser agent completes LLM enrichment
);

-- tool_calls: tool invocation sequence
CREATE TABLE IF NOT EXISTS tool_calls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    seq_idx     INTEGER NOT NULL,
    tool_name   TEXT NOT NULL,
    file_path   TEXT,                   -- for Read/Edit/Write
    is_error    INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- corrections (dimension 1 of 5 original)
CREATE TABLE IF NOT EXISTS corrections (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn       INTEGER,
    type       TEXT NOT NULL,           -- 'scope'|'direction'|'approach'|'factual'
    text       TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- emotion_signals (dimension 2 of 5 original)
CREATE TABLE IF NOT EXISTS emotion_signals (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn       INTEGER,
    type       TEXT NOT NULL,           -- 'frustration'|'impatience'|'satisfaction'|'resignation'|'sarcasm'
    trigger    TEXT,
    text       TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- prompt_assessments (dimension 3 of 5 original)
CREATE TABLE IF NOT EXISTS prompt_assessments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    turn            INTEGER,
    original        TEXT,
    issues          TEXT,               -- JSON array stored as text
    rewrite         TEXT,
    improvement_note TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- process_gaps (dimension 4 of 5 original)
CREATE TABLE IF NOT EXISTS process_gaps (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    type       TEXT NOT NULL,           -- 'skipped_exploration'|'no_verification'|'excessive_correction_loop'|'blind_acceptance'|'context_drip_feeding'
    evidence   TEXT,
    suggestion TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- project_stats (dimension 6: aggregated per project)
CREATE TABLE IF NOT EXISTS project_stats (
    project           TEXT PRIMARY KEY,
    avg_duration_min  REAL,
    total_sessions    INTEGER,
    avg_tool_count    REAL,
    build_failure_rate REAL,
    avg_corrections   REAL,
    last_session_at   TEXT
);

-- tool_mastery (dimension 7: aggregated per tool)
CREATE TABLE IF NOT EXISTS tool_mastery (
    tool_name          TEXT PRIMARY KEY,
    total_calls        INTEGER,
    error_count        INTEGER,
    error_rate         REAL,
    last_used          TEXT,
    recent_avg_daily_calls REAL  -- rolling 30-day average
);

-- session_features (dimension 8: per-session feature snapshot)
CREATE TABLE IF NOT EXISTS session_features (
    session_id         TEXT PRIMARY KEY,
    dna                TEXT,
    tool_density       REAL,
    correction_ratio   REAL,
    token_per_turn     REAL,
    project_complexity REAL,
    predicted_outcome  TEXT,
    actual_outcome     TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- context_gaps (dimension 9)
CREATE TABLE IF NOT EXISTS context_gaps (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL,
    gap_turn       INTEGER,
    missing_info   TEXT,                  -- 'error_msg'|'file_context'|'goal_detail'|'constraint'
    described_turn INTEGER,               -- turn where info was provided
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- token_audit (dimension 10)
CREATE TABLE IF NOT EXISTS token_audit (
    session_id        TEXT PRIMARY KEY,
    total_tokens      INTEGER,
    cache_hit_rate    REAL,
    wasted_tokens     INTEGER,            -- estimated from repeated context
    efficiency_score  REAL,               -- 0-1 computed score
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- session_outcomes (dimension 11)
CREATE TABLE IF NOT EXISTS session_outcomes (
    session_id          TEXT PRIMARY KEY,
    outcome             TEXT NOT NULL,   -- 'completed'|'interrupted'|'failed'
    end_trigger         TEXT,            -- 'user_abrupt'|'goal_achieved'|'build_failure_loop'|'max_turns'
    last_tool           TEXT,
    satisfaction_signal INTEGER,         -- 1 if satisfaction emotion detected
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- skill_invocations (dimension 12)
CREATE TABLE IF NOT EXISTS skill_invocations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    skill_name  TEXT,
    invoked     INTEGER NOT NULL,         -- 1 if skill was used, 0 if direct tool used instead
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- error_patterns (dimension 13: global shared table)
CREATE TABLE IF NOT EXISTS error_patterns (
    pattern_id   TEXT PRIMARY KEY,
    description  TEXT,
    bash_sample  TEXT,                   -- sample error text
    resolution   TEXT,                   -- common fix
    frequency    INTEGER,
    projects     TEXT,                   -- comma-separated affected projects
    last_seen    TEXT
);

-- file_graph (dimension 14)
CREATE TABLE IF NOT EXISTS file_graph (
    file_path       TEXT PRIMARY KEY,
    read_count      INTEGER,
    edit_count      INTEGER,
    last_session_id TEXT,
    project         TEXT,
    last_read_at    TEXT,
    last_edited_at  TEXT
);

-- rhythm_stats (dimension 15)
CREATE TABLE IF NOT EXISTS rhythm_stats (
    session_id              TEXT PRIMARY KEY,
    avg_response_interval_s REAL,        -- avg seconds between user turns
    long_pause_count        INTEGER,    -- pauses >60s
    turn_count              INTEGER,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- analysis_meta (metadata table)
CREATE TABLE IF NOT EXISTS analysis_meta (
    session_id        TEXT PRIMARY KEY,
    analyzer_version  TEXT,             -- e.g. '2.1.0'
    parsed_fields     INTEGER,          -- significance score (3-5), pre-computed by session-parser
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- ===== Phase 1 dual-loop extensions =====

-- plugin_events (full-text Skill/Agent invocation telemetry, populated in Phase 2)
CREATE TABLE IF NOT EXISTS plugin_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    tool_use_id       TEXT NOT NULL,                  -- unique per Skill/Agent invocation
    component_type    TEXT NOT NULL,                  -- 'skill' | 'agent'
    plugin            TEXT,                           -- e.g. 'dev-workflow' (parsed from skill_name/agent_type)
    component         TEXT NOT NULL,                  -- skill_name or agent_type leaf, e.g. 'verify-plan'
    invoked_at        TEXT,                           -- ISO timestamp at tool_use
    input_text        TEXT,                           -- full input text (Skill args / Agent prompt)
    result_text       TEXT,                           -- full result text (tool_result content)
    result_ok         INTEGER DEFAULT 1,              -- 0 if tool_result.is_error
    agent_turns_used  INTEGER,                        -- agents only: turns reported in result
    agent_max_turns   INTEGER,                        -- agents only: from agent definition (NULL if unknown)
    model_override    TEXT,                           -- agents only: input.model if set
    post_dispatch_signals TEXT,                       -- JSON: {user_correction_within_3_turns, user_abandoned_topic, user_repeated_manually, result_adopted}
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- plugin_changes (git log of plugin commits, populated in Phase 3)
CREATE TABLE IF NOT EXISTS plugin_changes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin       TEXT NOT NULL,                       -- e.g. 'dev-workflow' (from conventional commit scope)
    component    TEXT,                                -- skill or agent name (NULL if commit covers whole plugin)
    commit_hash  TEXT NOT NULL,
    commit_date  TEXT NOT NULL,                       -- ISO timestamp
    change_type  TEXT,                                -- 'feat' | 'fix' | 'refactor' | 'perf' | 'docs' | 'chore'
    summary      TEXT
);

-- analysis_checkpoints (resumable backfill state, version-aware re-analysis tracking)
CREATE TABLE IF NOT EXISTS analysis_checkpoints (
    session_id          TEXT PRIMARY KEY,
    analyzer_version    TEXT NOT NULL,                -- version of parser+session-parser when this session was processed
    last_processed_at   TEXT NOT NULL,                -- ISO timestamp
    re_analyze_pending  INTEGER DEFAULT 0,            -- 1 if analyzer version bumped since last_processed
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- baselines (per-plugin per-component metric baselines, populated in Phase 4)
CREATE TABLE IF NOT EXISTS baselines (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin            TEXT NOT NULL,
    component         TEXT NOT NULL,
    metric_name       TEXT NOT NULL,                  -- 'correction_rate' | 'abandonment_rate' | 'agent_efficiency_avg' | 'adoption_rate'
    metric_value      REAL,
    sample_size       INTEGER,
    window_start      TEXT,                           -- ISO timestamp
    window_end        TEXT,                           -- ISO timestamp
    window_spec       TEXT,                           -- '30d' | '60d' | 'all'
    analyzer_version  TEXT,                           -- which analyzer produced the underlying data
    commit_window     TEXT,                           -- comma-separated plugin_changes commit hashes covering this window (NULL if no plugin_changes split applies)
    computed_at       TEXT
);

-- knowledge_distilled (extracted reusable knowledge, populated in Phase 6)
CREATE TABLE IF NOT EXISTS knowledge_distilled (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash    TEXT NOT NULL UNIQUE,             -- SHA-256 of normalized content for dedup
    sub_type        TEXT NOT NULL,                    -- 'solution' | 'api_discovery' | 'pattern_template'
    title           TEXT,
    content         TEXT,                             -- full distilled content (markdown)
    session_ids     TEXT,                             -- JSON array of session_ids that contributed
    significance    INTEGER,                          -- 3-5 score
    distilled_at    TEXT,
    ief_path        TEXT                              -- path to IEF file written for pkos consumption
);

-- session_links (cross-session task chain edges, populated in Phase 3)
CREATE TABLE IF NOT EXISTS session_links (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source_session_id   TEXT NOT NULL,
    target_session_id   TEXT NOT NULL,
    link_type           TEXT NOT NULL,                -- 'continuation' | 'related'
    confidence          REAL,                         -- 0-1 from BM25 similarity
    detected_at         TEXT,
    FOREIGN KEY (source_session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (target_session_id) REFERENCES sessions(session_id)
);

-- pre_brief_hints (Pre-Brief and intervention pattern library, populated in Phase 5; intervention weights in Phase 8)
CREATE TABLE IF NOT EXISTS pre_brief_hints (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin          TEXT,                             -- NULL for personal-mode hints (cross-plugin)
    component       TEXT,                             -- NULL if hint applies plugin-wide
    pattern_text    TEXT NOT NULL,                    -- the hint text shown to user
    significance    INTEGER NOT NULL,                 -- 3-5; only sig >= 4 used by intervention hooks
    weight          REAL DEFAULT 1.0,                 -- 0-1; -0.2 per false-positive correction; <0.3 silences
    silenced        INTEGER DEFAULT 0,                -- 1 if weight dropped below threshold
    source          TEXT,                             -- 'manual' | 'suggested' | 'auto'
    source_session_ids TEXT,                          -- JSON array; provenance for --explain mode
    created_at      TEXT,
    last_triggered_at TEXT
);

-- ai_behavior_audit (CLAUDE.md rule compliance signals, populated in Phase 2 with full coverage per DP-003=C)
CREATE TABLE IF NOT EXISTS ai_behavior_audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    turn            INTEGER,                          -- assistant turn index
    rule_category   TEXT NOT NULL,                    -- 'core' | 'behavior' | 'debug' | 'gate' | 'decision' | 'forbidden' | 'style'
    rule_id         TEXT NOT NULL,                    -- e.g. 'core-7-edit-statement', 'style-zhongwen-banword'
    hit             INTEGER NOT NULL,                 -- 1 if rule was violated, 0 if rule was followed
    evidence        TEXT,                             -- text excerpt or signal description
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- analyzer_version column on sessions table (additive ALTER for migration)
-- Note: SQLite ALTER TABLE handled in sessions_db.py migration logic, not in initial schema

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id);
CREATE INDEX IF NOT EXISTS idx_corrections_session ON corrections(session_id);
CREATE INDEX IF NOT EXISTS idx_emotion_signals_session ON emotion_signals(session_id);
CREATE INDEX IF NOT EXISTS idx_prompt_assessments_session ON prompt_assessments(session_id);
CREATE INDEX IF NOT EXISTS idx_process_gaps_session ON process_gaps(session_id);
CREATE INDEX IF NOT EXISTS idx_context_gaps_session ON context_gaps(session_id);
CREATE INDEX IF NOT EXISTS idx_skill_invocations_session ON skill_invocations(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_analyzed_at ON sessions(analyzed_at);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);
CREATE INDEX IF NOT EXISTS idx_sessions_outcome ON sessions(outcome);
CREATE INDEX IF NOT EXISTS idx_plugin_events_session ON plugin_events(session_id);
CREATE INDEX IF NOT EXISTS idx_plugin_events_component ON plugin_events(plugin, component);
CREATE INDEX IF NOT EXISTS idx_plugin_changes_plugin ON plugin_changes(plugin, component);
CREATE INDEX IF NOT EXISTS idx_baselines_lookup ON baselines(plugin, component, metric_name);
CREATE INDEX IF NOT EXISTS idx_knowledge_distilled_hash ON knowledge_distilled(content_hash);
CREATE INDEX IF NOT EXISTS idx_session_links_source ON session_links(source_session_id);
CREATE INDEX IF NOT EXISTS idx_session_links_target ON session_links(target_session_id);
CREATE INDEX IF NOT EXISTS idx_ai_behavior_audit_session ON ai_behavior_audit(session_id);
CREATE INDEX IF NOT EXISTS idx_ai_behavior_audit_rule ON ai_behavior_audit(rule_id);
CREATE INDEX IF NOT EXISTS idx_pre_brief_hints_plugin ON pre_brief_hints(plugin, component);
CREATE INDEX IF NOT EXISTS idx_analysis_checkpoints_pending ON analysis_checkpoints(re_analyze_pending);
