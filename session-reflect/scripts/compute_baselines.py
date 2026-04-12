#!/usr/bin/env python3
"""Compute session-reflect baseline metrics."""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sessions_db  # noqa: E402
from analyzer_version import ANALYZER_VERSION  # noqa: E402

MIN_INVOCATIONS = 5


def parse_window_spec(window_spec):
    """Parse a window spec like 60d or all."""
    spec = (window_spec or "60d").strip().lower()
    if spec == "all":
        return spec, None
    if spec.endswith("d") and spec[:-1].isdigit():
        return spec, int(spec[:-1])
    raise ValueError(f"Unsupported window spec: {window_spec}")


def compute_bounds(window_spec, now=None):
    """Return ISO bounds for the requested window."""
    spec, days = parse_window_spec(window_spec)
    end_dt = now or datetime.now(timezone.utc)
    end_iso = end_dt.isoformat()
    if days is None:
        return spec, None, end_iso
    start_iso = (end_dt - timedelta(days=days)).isoformat()
    return spec, start_iso, end_iso


def _get_conn(db_path=None):
    if db_path:
        sessions_db.set_db_path(db_path)
    return sqlite3.connect(sessions_db.DB_PATH)


def _load_pairs(conn, start_iso, end_iso, plugin=None):
    query = """
        SELECT pe.plugin, pe.component, COUNT(*) as total_invocations
        FROM plugin_events pe
        JOIN sessions s ON s.session_id = pe.session_id
        WHERE pe.plugin IS NOT NULL
          AND pe.component IS NOT NULL
    """
    params = []
    if start_iso:
        query += " AND s.time_start >= ?"
        params.append(start_iso)
    if end_iso:
        query += " AND s.time_start <= ?"
        params.append(end_iso)
    if plugin:
        query += " AND pe.plugin = ?"
        params.append(plugin)
    query += """
        GROUP BY pe.plugin, pe.component
        HAVING COUNT(*) >= ?
        ORDER BY pe.plugin, pe.component
    """
    return conn.execute(query, params + [MIN_INVOCATIONS]).fetchall()


def _load_commits(conn, plugin, component, start_iso, end_iso):
    query = """
        SELECT commit_hash, commit_date
        FROM plugin_changes
        WHERE plugin = ?
          AND (component = ? OR component IS NULL)
    """
    params = [plugin, component]
    if start_iso:
        query += " AND commit_date >= ?"
        params.append(start_iso)
    if end_iso:
        query += " AND commit_date < ?"
        params.append(end_iso)
    query += " ORDER BY commit_date ASC"
    return conn.execute(query, params).fetchall()


def _build_segments(start_iso, end_iso, commits):
    if not commits:
        return [(start_iso, end_iso)]

    ordered = []
    first_commit_date = commits[0][1]
    if start_iso is None or start_iso < first_commit_date:
        ordered.append((start_iso, first_commit_date))
    for idx, (commit_hash, commit_date) in enumerate(commits):
        next_date = commits[idx + 1][1] if idx + 1 < len(commits) else end_iso
        ordered.append((commit_date, next_date))
    return [segment for segment in ordered if segment[0] != segment[1]]


def _segment_commits(commits, seg_start, seg_end):
    matched = []
    for commit_hash, commit_date in commits:
        if seg_start and commit_date < seg_start:
            continue
        if seg_end and commit_date >= seg_end:
            continue
        matched.append(commit_hash)
    return matched


def _load_events(conn, plugin, component, seg_start, seg_end):
    query = """
        SELECT pe.component_type, pe.result_ok, pe.agent_turns_used, pe.agent_max_turns, pe.post_dispatch_signals
        FROM plugin_events pe
        JOIN sessions s ON s.session_id = pe.session_id
        WHERE pe.plugin = ?
          AND pe.component = ?
    """
    params = [plugin, component]
    if seg_start:
        query += " AND s.time_start >= ?"
        params.append(seg_start)
    if seg_end:
        query += " AND s.time_start < ?"
        params.append(seg_end)
    return conn.execute(query, params).fetchall()


def _compute_metric_rows(plugin, component, window_spec, seg_start, seg_end, segment_commit_hashes, rows, computed_at):
    total = len(rows)
    if total == 0:
        return []
    correction_hits = 0
    abandonment_hits = 0
    adoption_hits = 0
    successful = 0
    efficiency_values = []
    for component_type, result_ok, turns_used, max_turns, payload in rows:
        signals = json.loads(payload) if payload else {}
        if signals.get("user_correction_within_3_turns"):
            correction_hits += 1
        if signals.get("user_abandoned_topic"):
            abandonment_hits += 1
        if result_ok:
            successful += 1
            if signals.get("result_adopted"):
                adoption_hits += 1
        if component_type == "agent" and turns_used is not None and max_turns not in (None, 0):
            efficiency_values.append(turns_used / max_turns)

    commit_window = ",".join(segment_commit_hashes) if segment_commit_hashes else None
    return [
        {
            "plugin": plugin,
            "component": component,
            "metric_name": "correction_rate",
            "metric_value": round(correction_hits / total, 4),
            "sample_size": total,
            "window_start": seg_start,
            "window_end": seg_end,
            "window_spec": window_spec,
            "analyzer_version": ANALYZER_VERSION,
            "commit_window": commit_window,
            "computed_at": computed_at,
        },
        {
            "plugin": plugin,
            "component": component,
            "metric_name": "abandonment_rate",
            "metric_value": round(abandonment_hits / total, 4),
            "sample_size": total,
            "window_start": seg_start,
            "window_end": seg_end,
            "window_spec": window_spec,
            "analyzer_version": ANALYZER_VERSION,
            "commit_window": commit_window,
            "computed_at": computed_at,
        },
        {
            "plugin": plugin,
            "component": component,
            "metric_name": "agent_efficiency_avg",
            "metric_value": round(sum(efficiency_values) / len(efficiency_values), 4) if efficiency_values else None,
            "sample_size": len(efficiency_values),
            "window_start": seg_start,
            "window_end": seg_end,
            "window_spec": window_spec,
            "analyzer_version": ANALYZER_VERSION,
            "commit_window": commit_window,
            "computed_at": computed_at,
        },
        {
            "plugin": plugin,
            "component": component,
            "metric_name": "adoption_rate",
            "metric_value": round(adoption_hits / successful, 4) if successful else None,
            "sample_size": successful,
            "window_start": seg_start,
            "window_end": seg_end,
            "window_spec": window_spec,
            "analyzer_version": ANALYZER_VERSION,
            "commit_window": commit_window,
            "computed_at": computed_at,
        },
    ]


def compute_baselines(db_path=None, window_spec="60d", plugin=None, now=None, replace_existing=False):
    """Compute and persist baselines. Returns a summary dict."""
    spec, start_iso, end_iso = compute_bounds(window_spec, now=now)
    computed_at = (now or datetime.now(timezone.utc)).isoformat()

    conn = _get_conn(db_path)
    try:
        rows_deleted = 0
        if replace_existing:
            rows_deleted = sessions_db.delete_baselines(
                plugin=plugin,
                window_spec=spec,
                conn=conn,
            )
        pairs = _load_pairs(conn, start_iso, end_iso, plugin=plugin)
        rows_written = 0
        plugins_touched = set()
        components_touched = set()
        for plugin_name, component_name, _ in pairs:
            commits = _load_commits(conn, plugin_name, component_name, start_iso, end_iso)
            segments = _build_segments(start_iso, end_iso, commits)
            if not segments:
                segments = [(start_iso, end_iso)]
            for seg_start, seg_end in segments:
                events = _load_events(conn, plugin_name, component_name, seg_start, seg_end)
                if len(events) < MIN_INVOCATIONS:
                    continue
                metric_rows = _compute_metric_rows(
                    plugin=plugin_name,
                    component=component_name,
                    window_spec=spec,
                    seg_start=seg_start,
                    seg_end=seg_end,
                    segment_commit_hashes=_segment_commits(commits, seg_start, seg_end),
                    rows=events,
                    computed_at=computed_at,
                )
                for baseline in metric_rows:
                    sessions_db.upsert_baseline(baseline, conn=conn)
                    rows_written += 1
                if metric_rows:
                    plugins_touched.add(plugin_name)
                    components_touched.add((plugin_name, component_name))
        conn.commit()
        return {
            "window_spec": spec,
            "window_start": start_iso,
            "window_end": end_iso,
            "pairs_considered": len(pairs),
            "plugins_touched": len(plugins_touched),
            "components_touched": len(components_touched),
            "rows_written": rows_written,
            "rows_deleted": rows_deleted,
            "computed_at": computed_at,
        }
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Compute session-reflect baselines")
    parser.add_argument("--sqlite-db", default=None, help="Target sessions.db path")
    parser.add_argument("--window", default="60d", help="Window spec: 30d, 60d, or all")
    parser.add_argument("--plugin", default=None, help="Restrict to one plugin")
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Delete existing rows for the same plugin/window before recomputing",
    )
    args = parser.parse_args()

    summary = compute_baselines(
        db_path=args.sqlite_db,
        window_spec=args.window,
        plugin=args.plugin,
        replace_existing=args.replace_existing,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
