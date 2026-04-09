#!/usr/bin/env python3
"""
session-reflect sessions.db management script.
Zero dependencies (uses Python's built-in sqlite3 module).
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path("~/.claude/session-reflect/sessions.db").expanduser()


def init_db():
    """Create all tables if not exist. Run on first use."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    schema_path = Path(__file__).parent / "sessions-schema.sql"
    conn = sqlite3.connect(DB_PATH)
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.close()


def _get_conn(read_only=False):
    """Get a database connection. For read-only access during active sessions,
    use file:{path}?mode=ro URI to prevent locking. For writes use regular connect."""
    if read_only:
        return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    return sqlite3.connect(DB_PATH)


def upsert_session(session_id: str, session_data: dict):
    """Insert or replace a parsed+enriched session into sessions.db."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR REPLACE INTO sessions (
            session_id, source, project, project_path, branch, model,
            time_start, time_end, duration_min, turns_user, turns_asst,
            tokens_in, tokens_out, cache_read, cache_create, cache_hit_rate,
            session_dna, task_summary, analyzed_at, outcome
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        session_data.get("session_dna"),
        session_data.get("task_summary"),
        session_data.get("analyzed_at") or datetime.now().isoformat(),
        session_data.get("outcome"),
    ))
    conn.commit()
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

    rows = conn.execute(query, params).fetchall()
    conn.close()
    cols = [desc[0] for desc in conn.cursor().description] if rows else []
    return [dict(zip(cols, row)) for row in rows]


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


def get_ief_insights(significance_min=3, limit=20):
    """Query sessions with significance >= threshold for IEF export."""
    conn = _get_conn(read_only=True)
    # significance is stored in session_features; sessions with no entry have significance 0
    rows = conn.execute("""
        SELECT s.session_id, s.project, s.session_dna, s.outcome,
               sf.dna, sf.tool_density, sf.correction_ratio,
               sf.token_per_turn, sf.project_complexity
        FROM sessions s
        LEFT JOIN session_features sf ON s.session_id = sf.session_id
        WHERE sf.project_complexity IS NOT NULL
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    cols = ["session_id", "project", "session_dna", "outcome",
            "dna", "tool_density", "correction_ratio", "token_per_turn", "project_complexity"]
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="session-reflect sessions.db management")
    parser.add_argument("--init", action="store_true", help="Initialize sessions.db schema")
    parser.add_argument("--migrate", action="store_true", help="Migrate from analyzed_sessions.json")
    parser.add_argument("--query-ids", action="store_true", help="List all session IDs in db")
    args = parser.parse_args()

    if args.init:
        init_db()
        print("sessions.db initialized")
    elif args.migrate:
        n, reason = migrate_from_analyzed_sessions()
        if reason:
            print(f"Migration {reason}: {n} sessions")
        else:
            print(f"Migrated {n} sessions")
    elif args.query_ids:
        ids = get_session_ids()
        print("\n".join(ids))
    else:
        parser.print_help()
