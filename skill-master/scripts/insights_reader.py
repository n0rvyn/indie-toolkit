"""
insights_reader.py — Read-only SQLite queries for /master insights.

All SQL uses parameterized queries (?). Never writes to the DB.
Default DB path: ~/.claude/session-reflect/sessions.db
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DB = Path("~/.claude/session-reflect/sessions.db").expanduser()
_DEFAULT_PROJECTS = Path("~/.claude/projects").expanduser()


# ── helpers ────────────────────────────────────────────────────────────────────

def _open_db(path: str | Path) -> sqlite3.Connection:
    """Open DB read-only; raise FileNotFoundError if missing."""
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(
            f"Database not found: {p}\n"
            "Install personal-os/session-reflect first: "
            "see https://github.com/your-org/personal-os"
        )
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    # Verify required Phase 1 column exists
    cols = {row[1] for row in conn.execute("PRAGMA table_info(plugin_events)")}
    if "invocation_trigger" not in cols:
        conn.close()
        raise RuntimeError(
            "schema missing column: invocation_trigger\n"
            "Run migrate_schema in personal-os Phase 1 to update the schema."
        )
    return conn


def _compute_lag_warning(
    db_path: str | Path,
    projects_path: str | Path | None = None,
) -> str | None:
    """
    Compare max(invoked_at) in plugin_events with the most recently modified
    .jsonl file under ~/.claude/projects. If the gap > 24h, return a warning string.
    """
    pp = Path(projects_path).expanduser() if projects_path else _DEFAULT_PROJECTS
    try:
        conn = sqlite3.connect(str(Path(db_path).expanduser()))
        row = conn.execute("SELECT MAX(invoked_at) FROM plugin_events").fetchone()
        conn.close()
        max_invoked_at_str = row[0] if row else None
        if not max_invoked_at_str:
            return None

        max_invoked_at = datetime.fromisoformat(max_invoked_at_str).replace(
            tzinfo=timezone.utc
        )

        jsonl_files = list(pp.rglob("*.jsonl")) if pp.exists() else []
        if not jsonl_files:
            return None

        latest_jsonl_mtime = max(f.stat().st_mtime for f in jsonl_files)
        latest_jsonl_dt = datetime.fromtimestamp(
            latest_jsonl_mtime, tz=timezone.utc
        )

        lag_seconds = (latest_jsonl_dt - max_invoked_at).total_seconds()
        if lag_seconds > 24 * 3600:
            lag_h = int(lag_seconds // 3600)
            return (
                f"Session-reflect data has {lag_h}h lag; "
                "the latest analysis window may be incomplete."
            )
    except Exception:
        pass
    return None


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


# ── Q1: invocation frequency + error rate ─────────────────────────────────────

def freq_and_error_rate(
    window_days: int,
    db_path: str | Path | None = None,
    plugin_filter: str | None = None,
    projects_path: str | Path | None = None,
) -> dict:
    """
    Q1: per (plugin, component) aggregated invocations + errors.

    Returns:
        {
            "rows": [{"plugin": ..., "component": ..., "invocations": int,
                       "errors": int, "error_rate": float}, ...],
            "lag_warning": str | None
        }
    """
    db = db_path or _DEFAULT_DB
    with _open_db(db) as conn:
        params: list = [window_days]
        plugin_clause = ""
        if plugin_filter:
            plugin_clause = " AND plugin = ?"
            params.append(plugin_filter)

        sql = f"""
            SELECT
                plugin,
                component,
                COUNT(*) AS invocations,
                SUM(CASE WHEN result_ok = 0 THEN 1 ELSE 0 END) AS errors,
                CAST(SUM(CASE WHEN result_ok = 0 THEN 1 ELSE 0 END) AS REAL)
                    / COUNT(*) AS error_rate
            FROM plugin_events
            WHERE invoked_at >= datetime('now', '-' || ? || ' days')
            {plugin_clause}
            GROUP BY plugin, component
            ORDER BY invocations DESC
        """
        rows = _rows_to_dicts(conn.execute(sql, params).fetchall())

    return {
        "rows": rows,
        "lag_warning": _compute_lag_warning(db, projects_path),
    }


# ── Q2: description misfires (claude-proactive + triggered_correctly=0) ───────

def description_misfires(
    window_days: int,
    db_path: str | Path | None = None,
    projects_path: str | Path | None = None,
) -> dict:
    """
    Q2: skill invocations where Claude proactively triggered but was wrong.

    Returns:
        {
            "rows": [{"plugin": ..., "component": ..., "invocation_trigger": ...,
                       "plugin_event_id": int, "triggered_correctly": int}, ...],
            "lag_warning": str | None
        }
    """
    db = db_path or _DEFAULT_DB
    with _open_db(db) as conn:
        sql = """
            SELECT
                pe.plugin,
                pe.component,
                pe.invocation_trigger,
                spt.plugin_event_id,
                spt.triggered_correctly
            FROM plugin_events pe
            JOIN skill_proactive_triggers spt ON spt.plugin_event_id = pe.id
            WHERE pe.invoked_at >= datetime('now', '-' || ? || ' days')
              AND pe.invocation_trigger = 'claude-proactive'
              AND spt.triggered_correctly = 0
            ORDER BY pe.invoked_at DESC
        """
        rows = _rows_to_dicts(conn.execute(sql, [window_days]).fetchall())

    return {
        "rows": rows,
        "lag_warning": _compute_lag_warning(db, projects_path),
    }


# ── Q3: agent efficiency (turns used / max turns ratio) ───────────────────────

def agent_efficiency(
    window_days: int,
    db_path: str | Path | None = None,
    projects_path: str | Path | None = None,
) -> dict:
    """
    Q3: per (plugin, component) average agent turns ratio.

    Returns:
        {
            "rows": [{"plugin": ..., "component": ..., "avg_turns_ratio": float,
                       "sample_count": int}, ...],
            "lag_warning": str | None
        }
    """
    db = db_path or _DEFAULT_DB
    with _open_db(db) as conn:
        sql = """
            SELECT
                plugin,
                component,
                AVG(CAST(agent_turns_used AS REAL) / agent_max_turns) AS avg_turns_ratio,
                COUNT(*) AS sample_count
            FROM plugin_events
            WHERE component_type = 'agent'
              AND agent_max_turns IS NOT NULL
              AND agent_turns_used IS NOT NULL
              AND invoked_at >= datetime('now', '-' || ? || ' days')
            GROUP BY plugin, component
            ORDER BY avg_turns_ratio DESC
        """
        rows = _rows_to_dicts(conn.execute(sql, [window_days]).fetchall())

    return {
        "rows": rows,
        "lag_warning": _compute_lag_warning(db, projects_path),
    }


# ── Q4: agent↔skill choreography (nested via parent_tool_use_id) ──────────────

def agent_skill_choreography(
    window_days: int,
    db_path: str | Path | None = None,
    projects_path: str | Path | None = None,
) -> dict:
    """
    Q4: nested skill calls — which agents invoke which skills.

    Uses parent_tool_use_id self-join on plugin_events.

    Returns:
        {
            "rows": [{"parent_component": ..., "child_component": ...,
                       "call_count": int}, ...],
            "lag_warning": str | None
        }
    """
    db = db_path or _DEFAULT_DB
    with _open_db(db) as conn:
        sql = """
            SELECT
                parent.component AS parent_component,
                child.component  AS child_component,
                COUNT(*)         AS call_count
            FROM plugin_events child
            JOIN plugin_events parent
                ON child.parent_tool_use_id = parent.tool_use_id
            WHERE child.invoked_at >= datetime('now', '-' || ? || ' days')
              AND child.parent_tool_use_id IS NOT NULL
            GROUP BY parent.component, child.component
            ORDER BY call_count DESC
        """
        rows = _rows_to_dicts(conn.execute(sql, [window_days]).fetchall())

    return {
        "rows": rows,
        "lag_warning": _compute_lag_warning(db, projects_path),
    }


# ── Q5: post-commit anomalies ──────────────────────────────────────────────────

def post_commit_anomalies(
    plugin: str,
    component: str,
    db_path: str | Path | None = None,
    window_days: int = 7,
    projects_path: str | Path | None = None,
) -> dict:
    """
    Q5: for a given (plugin, component), find plugin_changes commits and compute
    delta_invocations = events in [commit_date, commit_date + window_days) minus
    events in [commit_date - window_days, commit_date).

    Returns:
        {
            "rows": [{"commit_hash": ..., "commit_date": ...,
                       "delta_invocations": int, "change_type": ..., "summary": ...}, ...],
            "lag_warning": str | None
        }
    """
    db = db_path or _DEFAULT_DB
    with _open_db(db) as conn:
        sql = """
            SELECT
                pc.commit_hash,
                pc.commit_date,
                pc.change_type,
                pc.summary,
                (
                    SELECT COUNT(*) FROM plugin_events
                    WHERE plugin = pc.plugin
                      AND component = pc.component
                      AND invoked_at >= pc.commit_date
                      AND invoked_at < datetime(pc.commit_date, '+' || ? || ' days')
                ) -
                (
                    SELECT COUNT(*) FROM plugin_events
                    WHERE plugin = pc.plugin
                      AND component = pc.component
                      AND invoked_at >= datetime(pc.commit_date, '-' || ? || ' days')
                      AND invoked_at < pc.commit_date
                ) AS delta_invocations
            FROM plugin_changes pc
            WHERE pc.plugin = ?
              AND (pc.component = ? OR pc.component IS NULL)
            ORDER BY pc.commit_date DESC
        """
        rows = _rows_to_dicts(
            conn.execute(sql, [window_days, window_days, plugin, component]).fetchall()
        )

    return {
        "rows": rows,
        "lag_warning": _compute_lag_warning(db, projects_path),
    }
