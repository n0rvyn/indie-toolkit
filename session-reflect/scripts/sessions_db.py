#!/usr/bin/env python3
"""
session-reflect sessions.db management script.
Zero dependencies (uses Python's built-in sqlite3 module).
"""

import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path("~/.claude/session-reflect/sessions.db").expanduser()


def set_db_path(path):
    """Override the global sqlite DB path for scripts/tests."""
    global DB_PATH
    DB_PATH = Path(path).expanduser()


def migrate_schema():
    """Apply additive schema migrations (idempotent). Run after init_db()."""
    conn = sqlite3.connect(DB_PATH)
    try:
        # Phase 1: Add analyzer_version column to sessions table
        cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "analyzer_version" not in cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN analyzer_version TEXT DEFAULT 'pre-2026-04-12'")
        # Backfill default for any NULL rows (rows created via INSERT OR IGNORE before migration)
        conn.execute("UPDATE sessions SET analyzer_version = 'pre-2026-04-12' WHERE analyzer_version IS NULL")

        baseline_cols = {row[1] for row in conn.execute("PRAGMA table_info(baselines)").fetchall()}
        if baseline_cols and "window_spec" not in baseline_cols:
            conn.execute("ALTER TABLE baselines ADD COLUMN window_spec TEXT DEFAULT 'legacy'")
            conn.execute("UPDATE baselines SET window_spec = 'legacy' WHERE window_spec IS NULL")
        # Architecture C: track LLM enrichment state on sessions rows
        if "enrichment_pending" not in cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN enrichment_pending INTEGER DEFAULT 1")
        if "enriched_at" not in cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN enriched_at TEXT")
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create all tables if not exist. Run on first use."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    schema_path = Path(__file__).parent / "sessions-schema.sql"
    conn = sqlite3.connect(DB_PATH)
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.close()
    migrate_schema()


def _get_conn(read_only=False):
    """Get a database connection. For read-only access during active sessions,
    use file:{path}?mode=ro URI to prevent locking. For writes use regular connect."""
    if read_only:
        return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    return sqlite3.connect(DB_PATH)


def upsert_session(session_id: str, session_data: dict):
    """Insert or update a parsed session row.

    Preserves enrichment lifecycle columns (``enrichment_pending``, ``enriched_at``)
    on conflict. Re-parsing an already-enriched session (via --force-all backfill
    or analyzer-version bump) must not wipe the enrichment state and silently
    re-queue LLM work.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO sessions (
            session_id, source, project, project_path, branch, model,
            time_start, time_end, duration_min, turns_user, turns_asst,
            tokens_in, tokens_out, cache_read, cache_create, cache_hit_rate,
            analyzer_version, session_dna, task_summary, analyzed_at, outcome
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            source          = excluded.source,
            project         = excluded.project,
            project_path    = excluded.project_path,
            branch          = excluded.branch,
            model           = excluded.model,
            time_start      = excluded.time_start,
            time_end        = excluded.time_end,
            duration_min    = excluded.duration_min,
            turns_user      = excluded.turns_user,
            turns_asst      = excluded.turns_asst,
            tokens_in       = excluded.tokens_in,
            tokens_out      = excluded.tokens_out,
            cache_read      = excluded.cache_read,
            cache_create    = excluded.cache_create,
            cache_hit_rate  = excluded.cache_hit_rate,
            analyzer_version= excluded.analyzer_version,
            session_dna     = excluded.session_dna,
            task_summary    = excluded.task_summary,
            analyzed_at     = excluded.analyzed_at,
            outcome         = excluded.outcome
            -- enrichment_pending and enriched_at deliberately NOT updated
    """, (
        session_id,
        session_data.get("source"),
        session_data.get("project"),
        session_data.get("project_path"),
        session_data.get("branch"),
        session_data.get("model"),
        session_data.get("time_start"),
        session_data.get("time_end"),
        session_data.get("duration_min"),
        session_data.get("turns_user"),
        session_data.get("turns_asst"),
        session_data.get("tokens_in"),
        session_data.get("tokens_out"),
        session_data.get("cache_read"),
        session_data.get("cache_create"),
        session_data.get("cache_hit_rate"),
        session_data.get("analyzer_version"),
        session_data.get("session_dna"),
        session_data.get("task_summary"),
        session_data.get("analyzed_at") or datetime.now().isoformat(),
        session_data.get("outcome"),
    ))
    conn.commit()
    conn.close()


def update_session_dna(session_id: str, session_dna: str):
    """Update session_dna for an existing session after enrichment."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE sessions SET session_dna = ? WHERE session_id = ?",
            (session_dna, session_id),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_tool_calls(session_id: str, tool_calls: list):
    """Insert tool call sequence into tool_calls table."""
    conn = sqlite3.connect(DB_PATH)
    # Delete existing tool calls for this session (upsert behavior)
    conn.execute("DELETE FROM tool_calls WHERE session_id = ?", (session_id,))
    for idx, tc in enumerate(tool_calls):
        conn.execute("""
            INSERT INTO tool_calls (session_id, seq_idx, tool_name, file_path, is_error)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session_id,
            idx,
            tc.get("tool_name"),
            tc.get("file_path"),
            tc.get("is_error", 0),
        ))
    conn.commit()
    conn.close()


def query_sessions(project=None, days=None, dimension=None, limit=100):
    """OLAP query across sessions. Returns list of session dicts."""
    conn = _get_conn(read_only=True)
    query = "SELECT * FROM sessions WHERE 1=1"
    params = []

    if project:
        query += " AND project = ?"
        params.append(project)

    if days:
        cutoff = datetime.now().timestamp() - (days * 86400)
        query += " AND analyzed_at >= ?"
        params.append(datetime.fromtimestamp(cutoff).isoformat())

    query += f" LIMIT {limit}"

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    cols = [desc[0] for desc in cursor.description] if rows else []
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def query_sessions_by_dimension(dimension, threshold=None, project=None, days=None, limit=50):
    """OLAP query across sessions by dimension."""
    conn = _get_conn(read_only=True)
    dim_table_map = {
        "token_audit": ("token_audit", "ta", "ta.total_tokens, ta.cache_hit_rate, ta.efficiency_score"),
        "session_outcomes": ("session_outcomes", "so", "so.outcome, so.end_trigger, so.last_tool"),
        "session_features": ("session_features", "sf", "sf.dna, sf.tool_density, sf.project_complexity"),
        "context_gaps": ("context_gaps", "cg", "COUNT(*) as gap_count"),
        "rhythm_stats": ("rhythm_stats", "rs", "rs.avg_response_interval_s, rs.long_pause_count"),
        "skill_invocations": ("skill_invocations", "si", "si.skill_name, si.invoked"),
        "corrections": ("corrections", "c", "COUNT(*) as correction_count"),
    }
    if dimension not in dim_table_map:
        conn.close()
        return []
    table, alias, select_cols = dim_table_map[dimension]
    query = f"""
        SELECT s.session_id, s.project, s.time_start, s.duration_min,
               s.session_dna, s.outcome, {select_cols}
        FROM sessions s
        JOIN {table} {alias} ON s.session_id = {alias}.session_id
        WHERE 1=1
    """
    params = []
    if project:
        query += " AND s.project = ?"
        params.append(project)
    if days:
        cutoff = datetime.now().timestamp() - (days * 86400)
        query += " AND s.analyzed_at >= ?"
        params.append(datetime.fromtimestamp(cutoff).isoformat())
    if threshold is not None and dimension in ("token_audit", "session_features"):
        query += f" AND {alias}.efficiency_score >= ?"
        params.append(threshold)
    query += f" LIMIT {limit}"
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    cols = [desc[0] for desc in cursor.description] if rows else []
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def query_sessions_by_outcome(outcome, project=None, days=None, limit=50):
    """Query sessions by outcome field."""
    conn = _get_conn(read_only=True)
    query = """
        SELECT s.session_id, s.project, s.time_start, s.duration_min,
               s.session_dna, s.outcome, s.model,
               so.end_trigger, so.last_tool, so.satisfaction_signal
        FROM sessions s
        LEFT JOIN session_outcomes so ON s.session_id = so.session_id
        WHERE s.outcome = ?
    """
    params = [outcome]
    if project:
        query += " AND s.project = ?"
        params.append(project)
    if days:
        cutoff = datetime.now().timestamp() - (days * 86400)
        query += " AND s.analyzed_at >= ?"
        params.append(datetime.fromtimestamp(cutoff).isoformat())
    query += f" LIMIT {limit}"
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    cols = [desc[0] for desc in cursor.description] if rows else []
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def query_sessions_by_complexity(op, value, project=None, days=None, limit=50):
    """Query sessions by project_complexity with operator."""
    ops = {"gt": ">", "lt": "<", "eq": "="}
    if op not in ops:
        return []
    conn = _get_conn(read_only=True)
    query = f"""
        SELECT s.session_id, s.project, s.time_start, s.duration_min,
               s.session_dna, s.outcome,
               sf.project_complexity, sf.tool_density, sf.token_per_turn
        FROM sessions s
        LEFT JOIN session_features sf ON s.session_id = sf.session_id
        WHERE sf.project_complexity IS NOT NULL AND sf.project_complexity {ops[op]} ?
    """
    params = [value]
    if project:
        query += " AND s.project = ?"
        params.append(project)
    if days:
        cutoff = datetime.now().timestamp() - (days * 86400)
        query += " AND s.analyzed_at >= ?"
        params.append(datetime.fromtimestamp(cutoff).isoformat())
    query += f" ORDER BY sf.project_complexity DESC LIMIT {limit}"
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    cols = [desc[0] for desc in cursor.description] if rows else []
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def query_significance_above(threshold, project=None, days=None, limit=50):
    """Query sessions with significance (analysis_meta.parsed_fields) >= threshold."""
    conn = _get_conn(read_only=True)
    query = """
        SELECT s.session_id, s.project, s.time_start, s.session_dna,
               s.outcome, am.parsed_fields as significance
        FROM sessions s
        JOIN analysis_meta am ON s.session_id = am.session_id
        WHERE COALESCE(am.parsed_fields, 0) >= ?
    """
    params = [threshold]
    if project:
        query += " AND s.project = ?"
        params.append(project)
    if days:
        cutoff = datetime.now().timestamp() - (days * 86400)
        query += " AND s.analyzed_at >= ?"
        params.append(datetime.fromtimestamp(cutoff).isoformat())
    query += " ORDER BY am.parsed_fields DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    cols = [desc[0] for desc in conn.cursor().description] if rows else []
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def get_sessions_for_linking(project_branch_pairs=None):
    """Return sessions eligible for cross-session linking."""
    conn = _get_conn(read_only=True)
    try:
        cursor = conn.execute("""
            SELECT session_id, project, branch, time_start, time_end, task_summary, outcome
            FROM sessions
            WHERE time_start IS NOT NULL
            ORDER BY time_start ASC
        """)
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
    finally:
        conn.close()

    sessions = [dict(zip(cols, row)) for row in rows]
    if not project_branch_pairs:
        return sessions
    allowed = set(project_branch_pairs)
    return [
        row for row in sessions
        if (row.get("project"), row.get("branch")) in allowed
    ]


def get_tool_sequences(session_ids=None):
    """Return ordered tool name sequences keyed by session_id."""
    conn = _get_conn(read_only=True)
    try:
        query = """
            SELECT session_id, tool_name
            FROM tool_calls
        """
        params = []
        if session_ids:
            placeholders = ",".join("?" for _ in session_ids)
            query += f" WHERE session_id IN ({placeholders})"
            params.extend(session_ids)
        query += " ORDER BY session_id, seq_idx ASC"
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    sequences = {}
    for session_id, tool_name in rows:
        sequences.setdefault(session_id, []).append(tool_name)
    return sequences


def replace_session_links(source_session_ids, links, conn=None):
    """Replace all session_links rows for the provided source sessions."""
    if not source_session_ids:
        return
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        placeholders = ",".join("?" for _ in source_session_ids)
        _conn.execute(
            f"DELETE FROM session_links WHERE source_session_id IN ({placeholders})",
            list(source_session_ids),
        )
        for link in links:
            _conn.execute("""
                INSERT INTO session_links (
                    source_session_id, target_session_id, link_type, confidence, detected_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                link.get("source_session_id"),
                link.get("target_session_id"),
                link.get("link_type"),
                link.get("confidence"),
                link.get("detected_at") or datetime.now().isoformat(),
            ))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def get_task_trace(session_id):
    """Return the connected task chain around a session via session_links."""
    conn = _get_conn(read_only=True)
    try:
        edges = conn.execute("""
            SELECT source_session_id, target_session_id, link_type, confidence
            FROM session_links
        """).fetchall()
        if not edges:
            row = conn.execute("""
                SELECT session_id, project, outcome, time_start, time_end
                FROM sessions
                WHERE session_id = ?
            """, (session_id,)).fetchone()
            if not row:
                return []
            return [{
                "session_id": row[0],
                "project": row[1],
                "outcome": row[2],
                "time_start": row[3],
                "time_end": row[4],
                "link_type": "anchor",
                "confidence": 1.0,
                "is_anchor": 1,
            }]

        adjacency = {}
        for source_id, target_id, link_type, confidence in edges:
            adjacency.setdefault(source_id, []).append((target_id, link_type, confidence))
            adjacency.setdefault(target_id, []).append((source_id, link_type, confidence))

        visited = set()
        queue = [session_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for neighbor_id, _, _ in adjacency.get(current, []):
                if neighbor_id not in visited:
                    queue.append(neighbor_id)

        placeholders = ",".join("?" for _ in visited)
        cursor = conn.execute(f"""
            SELECT session_id, project, outcome, time_start, time_end
            FROM sessions
            WHERE session_id IN ({placeholders})
            ORDER BY time_start ASC, session_id ASC
        """, list(visited))
        rows = cursor.fetchall()
        trace = []
        for row in rows:
            sid = row[0]
            edge_meta = adjacency.get(sid, [])
            link_type = "anchor" if sid == session_id else (edge_meta[0][1] if edge_meta else None)
            confidence = 1.0 if sid == session_id else (edge_meta[0][2] if edge_meta else None)
            trace.append({
                "session_id": sid,
                "project": row[1],
                "outcome": row[2],
                "time_start": row[3],
                "time_end": row[4],
                "link_type": link_type,
                "confidence": confidence,
                "is_anchor": 1 if sid == session_id else 0,
            })
        return trace
    finally:
        conn.close()


def get_previous_unfinished_session(session_id):
    """Return the newest prior linked session whose outcome is not completed."""
    trace = get_task_trace(session_id)
    anchor = next((row for row in trace if row.get("session_id") == session_id), None)
    if not anchor:
        return None
    anchor_time = anchor.get("time_start")
    unfinished = [
        row for row in trace
        if row.get("session_id") != session_id
        and row.get("outcome") in {"interrupted", "failed"}
        and row.get("time_start")
        and (not anchor_time or row.get("time_start") < anchor_time)
    ]
    if not unfinished:
        return None
    unfinished.sort(key=lambda row: row.get("time_start"))
    return unfinished[-1]


def format_task_trace_markdown(rows):
    """Format task-trace rows as a markdown table."""
    if not rows:
        return "| session_id | project | outcome | time |\n| --- | --- | --- | --- |"
    lines = [
        "| session_id | project | outcome | time |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('session_id')} | {row.get('project') or ''} | {row.get('outcome') or ''} | {row.get('time_start') or ''} |"
        )
    return "\n".join(lines)


def format_baselines_markdown(rows):
    """Format baseline rows as a markdown table."""
    if not rows:
        return "| plugin | component | metric | value | sample | window | commits |\n| --- | --- | --- | --- | --- | --- | --- |"
    lines = [
        "| plugin | component | metric | value | sample | window | commits |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        value = "" if row.get("metric_value") is None else f"{row.get('metric_value'):.4f}"
        window = row.get("window_spec") or ""
        if row.get("window_start") or row.get("window_end"):
            window = f"{window} {row.get('window_start') or ''} -> {row.get('window_end') or ''}".strip()
        lines.append(
            f"| {row.get('plugin') or ''} | {row.get('component') or ''} | {row.get('metric_name') or ''} | "
            f"{value} | {row.get('sample_size') or 0} | {window} | {row.get('commit_window') or ''} |"
        )
    return "\n".join(lines)


def format_unfinished_hint(row):
    """Render a short unfinished-session hint."""
    if not row:
        return None
    return (
        f"Previous unfinished linked session: {row.get('session_id')} "
        f"({row.get('outcome')}) at {row.get('time_start')}"
    )


def query_plugin_changes(plugin=None, component=None, since=None, limit=50):
    """Query plugin_changes rows."""
    conn = _get_conn(read_only=True)
    try:
        query = """
            SELECT plugin, component, commit_hash, commit_date, change_type, summary
            FROM plugin_changes
            WHERE 1=1
        """
        params = []
        if plugin:
            query += " AND plugin = ?"
            params.append(plugin)
        if component:
            query += " AND component = ?"
            params.append(component)
        if since:
            query += " AND commit_date >= ?"
            params.append(since)
        query += " ORDER BY commit_date DESC LIMIT ?"
        params.append(limit)
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description] if rows else []
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def before_after_metric(plugin, component, commit_hash, metric_name, window_days):
    """Return metric snapshots before and after a plugin/component commit."""
    if metric_name not in {"correction_rate", "abandonment_rate", "adoption_rate", "agent_efficiency_avg"}:
        raise ValueError(f"Unsupported metric: {metric_name}")

    conn = _get_conn(read_only=True)
    try:
        commit_row = conn.execute("""
            SELECT commit_hash, commit_date
            FROM plugin_changes
            WHERE commit_hash = ? OR commit_hash LIKE ?
            ORDER BY LENGTH(commit_hash) ASC
            LIMIT 1
        """, (commit_hash, f"{commit_hash}%")).fetchone()
        if not commit_row:
            return None

        commit_hash_full, commit_date = commit_row
        commit_dt = datetime.fromisoformat(commit_date.replace("Z", "+00:00"))
        before_start = (commit_dt - timedelta(days=window_days)).isoformat()
        after_end = (commit_dt + timedelta(days=window_days)).isoformat()

        def _load_rows(start, end):
            query = """
                SELECT pe.post_dispatch_signals, pe.agent_turns_used, pe.agent_max_turns
                FROM plugin_events pe
                JOIN sessions s ON s.session_id = pe.session_id
                WHERE pe.plugin = ?
                  AND s.time_start >= ?
                  AND s.time_start < ?
            """
            params = [plugin, start, end]
            if component:
                query += " AND pe.component = ?"
                params.append(component)
            return conn.execute(query, params).fetchall()

        def _compute(rows):
            sample_size = len(rows)
            if sample_size == 0:
                return {
                    "sample_size": 0,
                    "metric_value": None,
                }
            if metric_name == "agent_efficiency_avg":
                ratios = []
                for _, used, maximum in rows:
                    if used is None or maximum in (None, 0):
                        continue
                    ratios.append(used / maximum)
                return {
                    "sample_size": len(ratios),
                    "metric_value": round(sum(ratios) / len(ratios), 4) if ratios else None,
                }

            signal_key = {
                "correction_rate": "user_correction_within_3_turns",
                "abandonment_rate": "user_abandoned_topic",
                "adoption_rate": "result_adopted",
            }[metric_name]
            hits = 0
            for payload, _, _ in rows:
                data = json.loads(payload) if payload else {}
                if data.get(signal_key):
                    hits += 1
            return {
                "sample_size": sample_size,
                "metric_value": round(hits / sample_size, 4),
            }

        before_rows = _load_rows(before_start, commit_dt.isoformat())
        after_rows = _load_rows(commit_dt.isoformat(), after_end)
        return {
            "plugin": plugin,
            "component": component,
            "metric_name": metric_name,
            "window_days": window_days,
            "commit_hash": commit_hash_full,
            "commit_date": commit_date,
            "before": {
                "window_start": before_start,
                "window_end": commit_dt.isoformat(),
                **_compute(before_rows),
            },
            "after": {
                "window_start": commit_dt.isoformat(),
                "window_end": after_end,
                **_compute(after_rows),
            },
        }
    finally:
        conn.close()


def query_baselines(window_spec=None, plugin=None, component=None, metric_name=None, latest_only=True, limit=200):
    """Query computed baseline rows."""
    conn = _get_conn(read_only=True)
    try:
        filters = ["1=1"]
        params = []
        if window_spec:
            filters.append("b.window_spec = ?")
            params.append(window_spec)
        if plugin:
            filters.append("b.plugin = ?")
            params.append(plugin)
        if component:
            filters.append("b.component = ?")
            params.append(component)
        if metric_name:
            filters.append("b.metric_name = ?")
            params.append(metric_name)
        where = " AND ".join(filters)
        if latest_only:
            query = f"""
                SELECT b.plugin, b.component, b.metric_name, b.metric_value, b.sample_size,
                       b.window_start, b.window_end, b.window_spec, b.analyzer_version,
                       b.commit_window, b.computed_at
                FROM baselines b
                JOIN (
                    SELECT plugin, component, metric_name, window_start, window_end, window_spec,
                           MAX(computed_at) AS latest_computed_at
                    FROM baselines
                    GROUP BY plugin, component, metric_name, window_start, window_end, window_spec
                ) latest
                  ON b.plugin = latest.plugin
                 AND COALESCE(b.component, '') = COALESCE(latest.component, '')
                 AND b.metric_name = latest.metric_name
                 AND COALESCE(b.window_start, '') = COALESCE(latest.window_start, '')
                 AND COALESCE(b.window_end, '') = COALESCE(latest.window_end, '')
                 AND COALESCE(b.window_spec, '') = COALESCE(latest.window_spec, '')
                 AND b.computed_at = latest.latest_computed_at
                WHERE {where}
                ORDER BY b.plugin, b.component, b.metric_name, b.window_start
                LIMIT ?
            """
        else:
            query = f"""
                SELECT b.plugin, b.component, b.metric_name, b.metric_value, b.sample_size,
                       b.window_start, b.window_end, b.window_spec, b.analyzer_version,
                       b.commit_window, b.computed_at
                FROM baselines b
                WHERE {where}
                ORDER BY b.computed_at DESC, b.plugin, b.component, b.metric_name
                LIMIT ?
            """
        cursor = conn.execute(query, params + [limit])
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description] if rows else []
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def delete_baselines(plugin=None, component=None, window_spec=None, conn=None):
    """Delete baseline rows matching the provided filters."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        query = "DELETE FROM baselines WHERE 1=1"
        params = []
        if plugin:
            query += " AND plugin = ?"
            params.append(plugin)
        if component:
            query += " AND component = ?"
            params.append(component)
        if window_spec:
            query += " AND window_spec = ?"
            params.append(window_spec)
        cursor = _conn.execute(query, params)
        if _close:
            _conn.commit()
        return cursor.rowcount
    finally:
        if _close:
            _conn.close()


def get_backfill_anomalies(session_ids):
    """Return anomaly records for sessions missing required dense rows or fields."""
    if not session_ids:
        return []
    conn = _get_conn(read_only=True)
    try:
        anomalies = []
        for session_id in session_ids:
            missing = []
            invalid = []

            analysis_meta = conn.execute(
                "SELECT analyzer_version, parsed_fields FROM analysis_meta WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not analysis_meta:
                missing.append("analysis_meta")
            elif analysis_meta[0] is None or analysis_meta[1] is None:
                invalid.append("analysis_meta")

            session_features = conn.execute(
                "SELECT dna, project_complexity FROM session_features WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not session_features:
                missing.append("session_features")
            elif session_features[0] is None or session_features[1] is None:
                invalid.append("session_features")

            token_audit = conn.execute(
                "SELECT total_tokens, efficiency_score FROM token_audit WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not token_audit:
                missing.append("token_audit")
            elif token_audit[0] is None or token_audit[1] is None:
                invalid.append("token_audit")

            session_outcomes = conn.execute(
                "SELECT outcome FROM session_outcomes WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not session_outcomes:
                missing.append("session_outcomes")
            elif session_outcomes[0] is None:
                invalid.append("session_outcomes")

            rhythm_stats = conn.execute(
                "SELECT avg_response_interval_s, turn_count FROM rhythm_stats WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not rhythm_stats:
                missing.append("rhythm_stats")
            elif rhythm_stats[0] is None or rhythm_stats[1] is None:
                invalid.append("rhythm_stats")

            audit_count = conn.execute(
                "SELECT COUNT(*) FROM ai_behavior_audit WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]
            if audit_count <= 0:
                missing.append("ai_behavior_audit")

            expected_plugin_events = conn.execute(
                "SELECT COUNT(*) FROM tool_calls WHERE session_id = ? AND tool_name IN ('Skill', 'Agent')",
                (session_id,),
            ).fetchone()[0]
            plugin_event_rows = conn.execute(
                """
                SELECT tool_use_id, component_type, component, invoked_at
                FROM plugin_events
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchall()
            if expected_plugin_events > 0 and not plugin_event_rows:
                missing.append("plugin_events")
            elif any(
                row[0] is None or row[1] is None or row[2] is None or row[3] is None
                for row in plugin_event_rows
            ):
                invalid.append("plugin_events")

            context_gap_rows = conn.execute(
                "SELECT gap_turn, missing_info FROM context_gaps WHERE session_id = ?",
                (session_id,),
            ).fetchall()
            if any(row[0] is None or row[1] is None for row in context_gap_rows):
                invalid.append("context_gaps")

            if missing or invalid:
                anomalies.append({
                    "session_id": session_id,
                    "missing": missing,
                    "invalid": invalid,
                })
        return anomalies
    finally:
        conn.close()


def get_session_ids(exclude_analyzed=False):
    """Return all session_ids currently in db."""
    conn = _get_conn(read_only=True)
    rows = conn.execute("SELECT session_id FROM sessions").fetchall()
    conn.close()
    return [r[0] for r in rows]


def mark_analyzed(session_ids: list):
    """Mark sessions as analyzed (idempotent)."""
    conn = sqlite3.connect(DB_PATH)
    for sid in session_ids:
        conn.execute("""
            INSERT OR IGNORE INTO sessions (session_id, analyzed_at)
            VALUES (?, ?)
        """, (sid, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_ief_insights(significance_min=3, limit=20, session_ids=None):
    """Query sessions with significance >= threshold for IEF export."""
    conn = _get_conn(read_only=True)
    if session_ids:
        placeholders = ",".join("?" * len(session_ids))
        query = f"""
            SELECT s.session_id, s.project, s.session_dna, s.outcome,
                   sf.dna, sf.tool_density, sf.correction_ratio,
                   sf.token_per_turn, sf.project_complexity,
                   am.parsed_fields as significance, am.analyzer_version
            FROM sessions s
            LEFT JOIN session_features sf ON s.session_id = sf.session_id
            LEFT JOIN analysis_meta am ON s.session_id = am.session_id
            WHERE COALESCE(am.parsed_fields, 0) >= ? AND s.session_id IN ({placeholders})
            ORDER BY am.parsed_fields DESC
            LIMIT ?
        """
        rows = conn.execute(query, [significance_min] + list(session_ids) + [limit]).fetchall()
    else:
        query = """
            SELECT s.session_id, s.project, s.session_dna, s.outcome,
                   sf.dna, sf.tool_density, sf.correction_ratio,
                   sf.token_per_turn, sf.project_complexity,
                   am.parsed_fields as significance, am.analyzer_version
            FROM sessions s
            LEFT JOIN session_features sf ON s.session_id = sf.session_id
            LEFT JOIN analysis_meta am ON s.session_id = am.session_id
            WHERE COALESCE(am.parsed_fields, 0) >= ?
            ORDER BY am.parsed_fields DESC
            LIMIT ?
        """
        rows = conn.execute(query, [significance_min, limit]).fetchall()
    conn.close()
    cols = ["session_id", "project", "session_dna", "outcome",
            "dna", "tool_density", "correction_ratio", "token_per_turn",
            "project_complexity", "significance", "analyzer_version"]
    return [dict(zip(cols, row)) for row in rows]


def migrate_from_analyzed_sessions():
    """One-time migration: read analyzed_sessions.json and upsert all sessions into sessions.db."""
    json_path = Path("~/.claude/session-reflect/analyzed_sessions.json")
    if not json_path.exists():
        return 0, "skipped"
    with open(json_path) as f:
        data = json.load(f)  # {session_id: "YYYY-MM-DD", ...}
    if not data:
        return 0, "empty"
    count = 0
    for session_id, date_str in data.items():
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT OR IGNORE INTO sessions (session_id, analyzed_at)
            VALUES (?, ?)
        """, (session_id, date_str))
        conn.commit()
        count += 1
    conn.close()
    return count, None


def upsert_session_features(session_id: str, data: dict, conn=None):
    """Upsert per-session feature snapshot. significance stored in analysis_meta."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        _conn.execute("""
            INSERT OR REPLACE INTO session_features
                (session_id, dna, tool_density, correction_ratio, token_per_turn, project_complexity, predicted_outcome, actual_outcome)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            data.get("dna"),
            data.get("tool_density"),
            data.get("correction_ratio"),
            data.get("token_per_turn"),
            data.get("project_complexity"),
            data.get("predicted_outcome"),
            data.get("actual_outcome"),
        ))
        # Store significance in analysis_meta (parsed_fields carries significance as integer bitmask)
        significance = data.get("significance", 0)
        version = data.get("analyzer_version", "1.0")
        _conn.execute("""
            INSERT OR REPLACE INTO analysis_meta (session_id, analyzer_version, parsed_fields)
            VALUES (?, ?, ?)
        """, (session_id, version, significance))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def upsert_context_gaps(session_id: str, gaps: list, conn=None):
    """Delete existing then insert new context gaps for a session."""
    if not gaps:
        return
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        _conn.execute("DELETE FROM context_gaps WHERE session_id = ?", (session_id,))
        for g in gaps:
            _conn.execute("""
                INSERT INTO context_gaps (session_id, gap_turn, missing_info, described_turn)
                VALUES (?, ?, ?, ?)
            """, (session_id, g.get("gap_turn"), g.get("missing_info"), g.get("described_turn")))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def upsert_token_audit(session_id: str, data: dict, conn=None):
    """Upsert token efficiency audit for a session."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        _conn.execute("""
            INSERT OR REPLACE INTO token_audit (session_id, total_tokens, cache_hit_rate, wasted_tokens, efficiency_score)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session_id,
            data.get("total_tokens"),
            data.get("cache_hit_rate"),
            data.get("wasted_tokens"),
            data.get("efficiency_score"),
        ))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def upsert_session_outcomes(session_id: str, data: dict, conn=None):
    """Upsert session outcome record."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        _conn.execute("""
            INSERT OR REPLACE INTO session_outcomes (session_id, outcome, end_trigger, last_tool, satisfaction_signal)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session_id,
            data.get("outcome"),
            data.get("end_trigger"),
            data.get("last_tool"),
            data.get("satisfaction_signal"),
        ))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def upsert_skill_invocations(session_id: str, invocations: list, conn=None):
    """Delete existing then insert skill invocation records."""
    if not invocations:
        return
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        _conn.execute("DELETE FROM skill_invocations WHERE session_id = ?", (session_id,))
        for inv in invocations:
            _conn.execute("""
                INSERT INTO skill_invocations (session_id, skill_name, invoked)
                VALUES (?, ?, ?)
            """, (session_id, inv.get("skill_name"), inv.get("invoked")))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def upsert_error_patterns(data: dict, conn=None):
    """Upsert a global error pattern entry. Called once per unique pattern."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        _conn.execute("""
            INSERT OR REPLACE INTO error_patterns (pattern_id, description, bash_sample, resolution, frequency, projects, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("pattern_id"),
            data.get("description"),
            data.get("bash_sample"),
            data.get("resolution"),
            data.get("frequency", 1),
            data.get("projects"),
            data.get("last_seen"),
        ))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def upsert_file_graph(entries: list, conn=None):
    """Upsert file graph entries. Uses ON CONFLICT DO UPDATE for incremental counts."""
    if not entries:
        return
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        for e in entries:
            _conn.execute("""
                INSERT INTO file_graph (file_path, read_count, edit_count, last_session_id, project, last_read_at, last_edited_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    read_count = read_count + excluded.read_count,
                    edit_count = edit_count + excluded.edit_count,
                    last_session_id = excluded.last_session_id,
                    last_read_at = COALESCE(excluded.last_read_at, file_graph.last_read_at),
                    last_edited_at = COALESCE(excluded.last_edited_at, file_graph.last_edited_at)
            """, (
                e.get("file_path"),
                e.get("read_count", 0),
                e.get("edit_count", 0),
                e.get("last_session_id"),
                e.get("project"),
                e.get("last_read_at"),
                e.get("last_edited_at"),
            ))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def upsert_rhythm_stats(session_id: str, data: dict, conn=None):
    """Upsert session rhythm statistics."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        _conn.execute("""
            INSERT OR REPLACE INTO rhythm_stats (session_id, avg_response_interval_s, long_pause_count, turn_count)
            VALUES (?, ?, ?, ?)
        """, (
            session_id,
            data.get("avg_response_interval_s"),
            data.get("long_pause_count"),
            data.get("turn_count"),
        ))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def enrich_session(session_id: str, enrichment: dict):
    """Bulk upsert all dimension data for a session in a single transaction. Call after upsert_session."""
    conn = sqlite3.connect(DB_PATH)
    try:
        if "session_features" in enrichment:
            _d = dict(enrichment["session_features"])
            _d["significance"] = enrichment.get("significance", 0)
            _d["analyzer_version"] = enrichment.get("analyzer_version")
            upsert_session_features(session_id, _d, conn=conn)
        if "context_gaps" in enrichment:
            upsert_context_gaps(session_id, enrichment["context_gaps"], conn=conn)
        if "token_audit" in enrichment:
            upsert_token_audit(session_id, enrichment["token_audit"], conn=conn)
        if "session_outcomes" in enrichment:
            upsert_session_outcomes(session_id, enrichment["session_outcomes"], conn=conn)
        if "skill_invocations" in enrichment:
            upsert_skill_invocations(session_id, enrichment["skill_invocations"], conn=conn)
        if "error_patterns" in enrichment:
            for ep in enrichment["error_patterns"]:
                upsert_error_patterns(ep, conn=conn)
        if "file_graph" in enrichment:
            upsert_file_graph(enrichment["file_graph"], conn=conn)
        if "rhythm_stats" in enrichment:
            upsert_rhythm_stats(session_id, enrichment["rhythm_stats"], conn=conn)
        conn.commit()
    finally:
        conn.close()


# ===== Phase 1 dual-loop helpers =====

def upsert_plugin_event(event: dict, conn=None):
    """Insert a plugin_events row. Idempotent on (session_id, tool_use_id) — replaces if exists."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        # Idempotent: delete existing row for same (session_id, tool_use_id) before insert
        _conn.execute(
            "DELETE FROM plugin_events WHERE session_id = ? AND tool_use_id = ?",
            (event.get("session_id"), event.get("tool_use_id")),
        )
        _conn.execute("""
            INSERT INTO plugin_events (
                session_id, tool_use_id, component_type, plugin, component,
                invoked_at, input_text, result_text, result_ok,
                agent_turns_used, agent_max_turns, model_override, post_dispatch_signals
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.get("session_id"),
            event.get("tool_use_id"),
            event.get("component_type"),
            event.get("plugin"),
            event.get("component"),
            event.get("invoked_at"),
            event.get("input_text"),
            event.get("result_text"),
            event.get("result_ok", 1),
            event.get("agent_turns_used"),
            event.get("agent_max_turns"),
            event.get("model_override"),
            json.dumps(event.get("post_dispatch_signals")) if event.get("post_dispatch_signals") else None,
        ))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def upsert_plugin_change(change: dict, conn=None):
    """Insert a plugin_changes row. Idempotent on commit_hash + component."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        _conn.execute(
            "DELETE FROM plugin_changes WHERE commit_hash = ? AND COALESCE(component, '') = COALESCE(?, '')",
            (change.get("commit_hash"), change.get("component")),
        )
        _conn.execute("""
            INSERT INTO plugin_changes (plugin, component, commit_hash, commit_date, change_type, summary)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            change.get("plugin"),
            change.get("component"),
            change.get("commit_hash"),
            change.get("commit_date"),
            change.get("change_type"),
            change.get("summary"),
        ))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def upsert_checkpoint(session_id: str, analyzer_version: str, conn=None):
    """Record successful analysis of a session. Clears re_analyze_pending."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        _conn.execute("""
            INSERT OR REPLACE INTO analysis_checkpoints (session_id, analyzer_version, last_processed_at, re_analyze_pending)
            VALUES (?, ?, ?, 0)
        """, (session_id, analyzer_version, datetime.now().isoformat()))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def mark_re_analyze_pending(current_version: str):
    """Mark all checkpoints whose analyzer_version != current_version as re_analyze_pending=1.
    Called after analyzer version bump."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            "UPDATE analysis_checkpoints SET re_analyze_pending = 1 WHERE analyzer_version != ?",
            (current_version,),
        )
        n = cursor.rowcount
        conn.commit()
        return n
    finally:
        conn.close()


def get_pending_session_ids(limit=None):
    """Return list of session_ids with re_analyze_pending=1 OR no checkpoint row.
    These are the sessions backfill should process next."""
    conn = _get_conn(read_only=True)
    try:
        query = """
            SELECT s.session_id
            FROM sessions s
            LEFT JOIN analysis_checkpoints c ON s.session_id = c.session_id
            WHERE c.session_id IS NULL OR c.re_analyze_pending = 1
        """
        if limit:
            query += f" LIMIT {limit}"
        return [r[0] for r in conn.execute(query).fetchall()]
    finally:
        conn.close()


def set_enrichment_pending(session_id: str, pending: int = 1, conn=None):
    """Set the LLM-enrichment pending flag for a session row."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        _conn.execute(
            "UPDATE sessions SET enrichment_pending = ? WHERE session_id = ?",
            (pending, session_id),
        )
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def query_pending_enrichment(limit: int = 50):
    """Return session rows awaiting LLM enrichment (enrichment_pending=1).

    Ordered newest-first so recent sessions enrich first when users run /reflect --enrich.
    """
    conn = _get_conn(read_only=True)
    try:
        cursor = conn.execute(
            """
            SELECT session_id, source, project, time_start, time_end
            FROM sessions
            WHERE enrichment_pending = 1
            ORDER BY COALESCE(time_end, time_start) DESC
            LIMIT ?
            """,
            (limit,),
        )
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def count_pending_enrichment() -> int:
    """Return the count of sessions awaiting LLM enrichment."""
    conn = _get_conn(read_only=True)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE enrichment_pending = 1"
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def mark_enriched(session_id: str, dimensions: dict = None, audit_rows: list = None, session_dna: str = None, task_summary: str = None):
    """Persist LLM-enrichment results and clear enrichment_pending.

    Called after /reflect --enrich dispatches the session-parser agent and
    receives structured JSON back. Writes dimension tables, audit rows, and
    sets enriched_at.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        if session_dna is not None:
            conn.execute(
                "UPDATE sessions SET session_dna = ? WHERE session_id = ?",
                (session_dna, session_id),
            )
        if task_summary is not None:
            conn.execute(
                "UPDATE sessions SET task_summary = ? WHERE session_id = ?",
                (task_summary, session_id),
            )
        conn.execute(
            "UPDATE sessions SET enrichment_pending = 0, enriched_at = ? WHERE session_id = ?",
            (datetime.now().isoformat(), session_id),
        )
        conn.commit()
    finally:
        conn.close()

    if dimensions:
        enrich_session(session_id, dimensions)
    if audit_rows is not None:
        upsert_ai_behavior_audit(session_id, audit_rows)


def upsert_baseline(baseline: dict, conn=None):
    """Append a baselines row (history kept; query latest by computed_at DESC)."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        _conn.execute("""
            INSERT INTO baselines (
                plugin, component, metric_name, metric_value, sample_size,
                window_start, window_end, window_spec, analyzer_version, commit_window, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            baseline.get("plugin"),
            baseline.get("component"),
            baseline.get("metric_name"),
            baseline.get("metric_value"),
            baseline.get("sample_size"),
            baseline.get("window_start"),
            baseline.get("window_end"),
            baseline.get("window_spec"),
            baseline.get("analyzer_version"),
            baseline.get("commit_window"),
            baseline.get("computed_at") or datetime.now().isoformat(),
        ))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def upsert_knowledge_distilled(entry: dict, conn=None):
    """Idempotent on content_hash. Merges session_ids array if duplicate hash found."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        existing = _conn.execute(
            "SELECT session_ids FROM knowledge_distilled WHERE content_hash = ?",
            (entry.get("content_hash"),),
        ).fetchone()
        if existing:
            old_ids = json.loads(existing[0]) if existing[0] else []
            new_ids = entry.get("session_ids", [])
            merged = sorted(set(old_ids + new_ids))
            _conn.execute(
                "UPDATE knowledge_distilled SET session_ids = ? WHERE content_hash = ?",
                (json.dumps(merged), entry.get("content_hash")),
            )
        else:
            _conn.execute("""
                INSERT INTO knowledge_distilled (
                    content_hash, sub_type, title, content, session_ids,
                    significance, distilled_at, ief_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.get("content_hash"),
                entry.get("sub_type"),
                entry.get("title"),
                entry.get("content"),
                json.dumps(entry.get("session_ids", [])),
                entry.get("significance"),
                entry.get("distilled_at") or datetime.now().isoformat(),
                entry.get("ief_path"),
            ))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def upsert_session_link(link: dict, conn=None):
    """Insert a session link edge. Idempotent on (source, target, link_type)."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        _conn.execute(
            "DELETE FROM session_links WHERE source_session_id = ? AND target_session_id = ? AND link_type = ?",
            (link.get("source_session_id"), link.get("target_session_id"), link.get("link_type")),
        )
        _conn.execute("""
            INSERT INTO session_links (
                source_session_id, target_session_id, link_type, confidence, detected_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            link.get("source_session_id"),
            link.get("target_session_id"),
            link.get("link_type"),
            link.get("confidence"),
            link.get("detected_at") or datetime.now().isoformat(),
        ))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def upsert_pre_brief_hint(hint: dict, conn=None):
    """Insert or update a pre_brief_hint. Identity = (plugin, component, pattern_text)."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        existing = _conn.execute(
            "SELECT id FROM pre_brief_hints WHERE COALESCE(plugin,'')=COALESCE(?, '') AND COALESCE(component,'')=COALESCE(?, '') AND pattern_text = ?",
            (hint.get("plugin"), hint.get("component"), hint.get("pattern_text")),
        ).fetchone()
        if existing:
            _conn.execute("""
                UPDATE pre_brief_hints SET
                    significance = ?, weight = ?, silenced = ?, source = ?,
                    source_session_ids = ?, last_triggered_at = ?
                WHERE id = ?
            """, (
                hint.get("significance"),
                hint.get("weight", 1.0),
                hint.get("silenced", 0),
                hint.get("source"),
                json.dumps(hint.get("source_session_ids", [])),
                hint.get("last_triggered_at"),
                existing[0],
            ))
        else:
            _conn.execute("""
                INSERT INTO pre_brief_hints (
                    plugin, component, pattern_text, significance, weight, silenced,
                    source, source_session_ids, created_at, last_triggered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                hint.get("plugin"),
                hint.get("component"),
                hint.get("pattern_text"),
                hint.get("significance"),
                hint.get("weight", 1.0),
                hint.get("silenced", 0),
                hint.get("source"),
                json.dumps(hint.get("source_session_ids", [])),
                hint.get("created_at") or datetime.now().isoformat(),
                hint.get("last_triggered_at"),
            ))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


def upsert_ai_behavior_audit(session_id: str, audits: list, conn=None):
    """Replace all audit rows for a session. audits = list of {turn, rule_category, rule_id, hit, evidence}."""
    _conn = conn if conn else sqlite3.connect(DB_PATH)
    _close = not bool(conn)
    try:
        _conn.execute("DELETE FROM ai_behavior_audit WHERE session_id = ?", (session_id,))
        for a in audits:
            _conn.execute("""
                INSERT INTO ai_behavior_audit (session_id, turn, rule_category, rule_id, hit, evidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                a.get("turn"),
                a.get("rule_category"),
                a.get("rule_id"),
                a.get("hit", 0),
                a.get("evidence"),
            ))
        if _close:
            _conn.commit()
    finally:
        if _close:
            _conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="session-reflect sessions.db management")
    parser.add_argument("--sqlite-db", default=None, help="Override sessions.db path")
    parser.add_argument("--init", action="store_true", help="Initialize sessions.db schema")
    parser.add_argument("--migrate-schema", action="store_true", help="Apply additive schema migrations (run after --init)")
    parser.add_argument("--migrate", action="store_true", help="Migrate from analyzed_sessions.json")
    parser.add_argument("--query-ids", action="store_true", help="List all session IDs in db")
    parser.add_argument("--query-insights", action="store_true", help="Query high-significance sessions for IEF export")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument("--query", choices=["dimension", "outcomes", "complexity", "significance", "task-trace", "unfinished", "plugin-changes", "before-after", "baselines", "pending-enrichment"], help="OLAP query mode")
    parser.add_argument("--mark-enriched", action="store_true", help="Persist enrichment payload for a session (pair with --session-id and --payload)")
    parser.add_argument("--payload", help="JSON enrichment payload (or '-' to read from stdin)")
    parser.add_argument("--dimension", help="Dimension to query (token_audit, session_outcomes, session_features, context_gaps, rhythm_stats, skill_invocations, corrections)")
    parser.add_argument("--outcome", help="Outcome value (completed|interrupted|failed)")
    parser.add_argument("--op", choices=["gt", "lt", "eq"], help="Comparison operator for complexity query")
    parser.add_argument("--value", type=float, help="Threshold value")
    parser.add_argument("--min-sig", "--min-significance", type=int, default=3, dest="min_sig", help="Minimum significance")
    parser.add_argument("--project", help="Filter by project name")
    parser.add_argument("--plugin", help="Filter by plugin name")
    parser.add_argument("--component", help="Filter by component name")
    parser.add_argument("--session-id", help="Session ID for task-trace / unfinished queries")
    parser.add_argument("--since", help="ISO date filter for plugin_changes")
    parser.add_argument("--commit-hash", help="Commit hash or prefix for before-after queries")
    parser.add_argument("--metric-name", help="Metric name for before-after query")
    parser.add_argument("--window-days", type=int, default=None, help="Window size in days")
    parser.add_argument("--window-spec", help="Window spec for baselines query (30d|60d|all)")
    parser.add_argument("--days", type=int, help="Lookback in days")
    args = parser.parse_args()

    if args.sqlite_db:
        set_db_path(args.sqlite_db)

    if args.init:
        init_db()
        print("sessions.db initialized")
    elif args.migrate_schema:
        migrate_schema()
        print("Schema migration applied")
    elif args.migrate:
        n, reason = migrate_from_analyzed_sessions()
        if reason:
            print(f"Migration {reason}: {n} sessions")
        else:
            print(f"Migrated {n} sessions")
    elif args.query_ids:
        ids = get_session_ids()
        print("\n".join(ids))
    elif args.query_insights:
        insights = get_ief_insights(significance_min=args.min_sig, limit=args.limit)
        print(json.dumps(insights, indent=2))
    elif args.query == "dimension":
        if not args.dimension:
            print("--dimension required for dimension query", file=sys.stderr)
            sys.exit(1)
        rows = query_sessions_by_dimension(args.dimension, project=args.project, days=args.days)
        print(json.dumps(rows, indent=2, default=str))
    elif args.query == "outcomes":
        outcome = args.outcome or "interrupted"
        rows = query_sessions_by_outcome(outcome, project=args.project, days=args.days)
        print(json.dumps(rows, indent=2, default=str))
    elif args.query == "complexity":
        if not args.op or args.value is None:
            print("--op and --value required for complexity query", file=sys.stderr)
            sys.exit(1)
        rows = query_sessions_by_complexity(args.op, args.value, project=args.project, days=args.days)
        print(json.dumps(rows, indent=2, default=str))
    elif args.query == "significance":
        rows = query_significance_above(args.min_sig, project=args.project, days=args.days)
        print(json.dumps(rows, indent=2, default=str))
    elif args.query == "task-trace":
        if not args.session_id:
            print("--session-id required for task-trace query", file=sys.stderr)
            sys.exit(1)
        rows = get_task_trace(args.session_id)
        print(json.dumps(rows, indent=2, default=str))
    elif args.query == "unfinished":
        if not args.session_id:
            print("--session-id required for unfinished query", file=sys.stderr)
            sys.exit(1)
        row = get_previous_unfinished_session(args.session_id)
        print(json.dumps(row, indent=2, default=str))
    elif args.query == "plugin-changes":
        rows = query_plugin_changes(plugin=args.plugin, component=args.component, since=args.since, limit=args.limit)
        print(json.dumps(rows, indent=2, default=str))
    elif args.query == "before-after":
        if not args.plugin or not args.commit_hash or not args.metric_name:
            print("--plugin, --commit-hash, and --metric-name required for before-after query", file=sys.stderr)
            sys.exit(1)
        rows = before_after_metric(
            plugin=args.plugin,
            component=args.component,
            commit_hash=args.commit_hash,
            metric_name=args.metric_name,
            window_days=args.window_days or 14,
        )
        print(json.dumps(rows, indent=2, default=str))
    elif args.query == "baselines":
        rows = query_baselines(
            window_spec=args.window_spec or (f"{args.window_days}d" if args.window_days else "60d"),
            plugin=args.plugin,
            component=args.component,
            metric_name=args.metric_name,
        )
        print(json.dumps(rows, indent=2, default=str))
    elif args.query == "pending-enrichment":
        rows = query_pending_enrichment(limit=args.limit)
        print(json.dumps({
            "pending_total": count_pending_enrichment(),
            "batch": rows,
        }, indent=2, default=str))
    elif args.mark_enriched:
        if not args.session_id or args.payload is None:
            print("--mark-enriched requires --session-id and --payload", file=sys.stderr)
            sys.exit(1)
        raw = sys.stdin.read() if args.payload == "-" else args.payload
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"--payload is not valid JSON: {exc}", file=sys.stderr)
            sys.exit(1)
        mark_enriched(
            args.session_id,
            dimensions=payload.get("dimensions"),
            audit_rows=payload.get("ai_behavior_audit"),
            session_dna=payload.get("session_dna"),
            task_summary=payload.get("task_summary"),
        )
        print(f"marked enriched: {args.session_id}")
    else:
        parser.print_help()
