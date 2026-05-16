-- sessions-mini.sql: in-memory DB seed for insights_reader tests
-- Uses full Phase 1 schema (base schema + Phase 5 additive columns inline)

CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
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
    session_dna  TEXT,
    task_summary TEXT,
    analyzed_at  TEXT,
    outcome      TEXT,
    enrichment_pending INTEGER DEFAULT 1,
    enriched_at  TEXT,
    analyzer_version TEXT DEFAULT 'pre-2026-04-12',
    effort_level TEXT
);

CREATE TABLE IF NOT EXISTS plugin_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    tool_use_id       TEXT NOT NULL,
    component_type    TEXT NOT NULL,
    plugin            TEXT,
    component         TEXT NOT NULL,
    invoked_at        TEXT,
    input_text        TEXT,
    result_text       TEXT,
    result_ok         INTEGER DEFAULT 1,
    agent_turns_used  INTEGER,
    agent_max_turns   INTEGER,
    model_override    TEXT,
    post_dispatch_signals TEXT,
    invocation_trigger TEXT,
    duration_ms        INTEGER,
    parent_tool_use_id TEXT,
    cwd                TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS corrections (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn       INTEGER,
    type       TEXT NOT NULL,
    text       TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS skill_proactive_triggers (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_event_id             INTEGER NOT NULL,
    user_prompt_excerpt         TEXT,
    skill_description_snapshot  TEXT,
    triggered_correctly         INTEGER,
    FOREIGN KEY (plugin_event_id) REFERENCES plugin_events(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plugin_changes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin       TEXT NOT NULL,
    component    TEXT,
    commit_hash  TEXT NOT NULL,
    commit_date  TEXT NOT NULL,
    change_type  TEXT,
    summary      TEXT
);

-- Seed data

-- 3 sessions
INSERT INTO sessions (session_id, source, project, analyzed_at, outcome) VALUES
    ('sess-001', 'claude-code', 'indie-toolkit', datetime('now', '-3 days'), 'completed'),
    ('sess-002', 'claude-code', 'indie-toolkit', datetime('now', '-2 days'), 'completed'),
    ('sess-003', 'claude-code', 'indie-toolkit', datetime('now', '-1 days'), 'completed');

-- 3 plugin_events for dev-workflow (2 user-slash, 1 claude-proactive); 2 of them result_ok=1, 1 result_ok=0
-- Event 1: user-slash, success, skill
INSERT INTO plugin_events
    (session_id, tool_use_id, component_type, plugin, component, invoked_at, result_ok, agent_turns_used, agent_max_turns, invocation_trigger, parent_tool_use_id)
VALUES
    ('sess-001', 'tu-001', 'skill', 'dev-workflow', 'verify-plan',
     datetime('now', '-3 days'), 1, NULL, NULL, 'user-slash', NULL);

-- Event 2: user-slash, error, skill
INSERT INTO plugin_events
    (session_id, tool_use_id, component_type, plugin, component, invoked_at, result_ok, agent_turns_used, agent_max_turns, invocation_trigger, parent_tool_use_id)
VALUES
    ('sess-002', 'tu-002', 'skill', 'dev-workflow', 'verify-plan',
     datetime('now', '-2 days'), 0, NULL, NULL, 'user-slash', NULL);

-- Event 3: claude-proactive, success, skill (description-misfire candidate)
INSERT INTO plugin_events
    (session_id, tool_use_id, component_type, plugin, component, invoked_at, result_ok, agent_turns_used, agent_max_turns, invocation_trigger, parent_tool_use_id)
VALUES
    ('sess-003', 'tu-003', 'skill', 'dev-workflow', 'verify-plan',
     datetime('now', '-1 days'), 1, NULL, NULL, 'claude-proactive', NULL);

-- Event 4: agent type with turns (for Q3 agent efficiency)
INSERT INTO plugin_events
    (session_id, tool_use_id, component_type, plugin, component, invoked_at, result_ok, agent_turns_used, agent_max_turns, invocation_trigger, parent_tool_use_id)
VALUES
    ('sess-001', 'tu-004', 'agent', 'dev-workflow', 'plan-verifier',
     datetime('now', '-3 days'), 1, 6, 10, 'user-slash', NULL);

-- Event 5: nested skill (agent_skill_choreography - child has parent_tool_use_id = tu-004)
INSERT INTO plugin_events
    (session_id, tool_use_id, component_type, plugin, component, invoked_at, result_ok, agent_turns_used, agent_max_turns, invocation_trigger, parent_tool_use_id)
VALUES
    ('sess-001', 'tu-005', 'skill', 'dev-workflow', 'write-plan',
     datetime('now', '-3 days'), 1, NULL, NULL, 'nested-skill', 'tu-004');

-- 2 corrections
INSERT INTO corrections (session_id, turn, type, text) VALUES
    ('sess-001', 3, 'scope', 'skip this step'),
    ('sess-002', 5, 'direction', 'not what I wanted');

-- 1 skill_proactive_trigger with triggered_correctly=0 (misfire)
INSERT INTO skill_proactive_triggers (plugin_event_id, user_prompt_excerpt, triggered_correctly) VALUES
    (3, 'user asked about something else', 0);

-- 3 plugin_changes (git log simulation)
INSERT INTO plugin_changes (plugin, component, commit_hash, commit_date, change_type, summary) VALUES
    ('dev-workflow', 'verify-plan', 'abc1234', datetime('now', '-10 days'), 'feat', 'improve verification logic'),
    ('dev-workflow', 'verify-plan', 'def5678', datetime('now', '-5 days'), 'fix', 'fix edge case'),
    ('dev-workflow', 'write-plan', 'ghi9012', datetime('now', '-2 days'), 'docs', 'update examples');
