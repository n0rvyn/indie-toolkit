#!/usr/bin/env python3
"""Phase 4 tests for baseline aggregation logic."""

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import compute_baselines
import sessions_db


def _insert_session(conn, session_id, time_start):
    conn.execute(
        """
        INSERT INTO sessions (
            session_id, source, project, project_path, branch, model,
            time_start, time_end, duration_min, turns_user, turns_asst,
            tokens_in, tokens_out, cache_read, cache_create, cache_hit_rate,
            analyzer_version, session_dna, task_summary, analyzed_at, outcome
        ) VALUES (?, 'claude-code', 'toolkit', '/tmp/toolkit', 'main', 'claude-opus-4-6',
                  ?, ?, 30.0, 1, 1, 100, 50, 0, 0, 0.0, '2026-04-12-phase4', 'build',
                  'baseline test', ?, 'completed')
        """,
        (session_id, time_start, time_start, time_start),
    )


def _insert_plugin_event(
    conn,
    session_id,
    tool_use_id,
    invoked_at,
    *,
    component="verify-plan",
    component_type="skill",
    result_ok=1,
    adopted=False,
    correction=False,
    abandon=False,
    turns_used=None,
    max_turns=None,
):
    payload = sessions_db.json.dumps(
        {
            "user_correction_within_3_turns": correction,
            "user_abandoned_topic": abandon,
            "user_repeated_manually": False,
            "result_adopted": adopted,
        }
    )
    conn.execute(
        """
        INSERT INTO plugin_events (
            session_id, tool_use_id, component_type, plugin, component, invoked_at,
            input_text, result_text, result_ok, agent_turns_used, agent_max_turns,
            model_override, post_dispatch_signals
        ) VALUES (?, ?, ?, 'dev-workflow', ?, ?, '{}', '{}', ?, ?, ?, NULL, ?)
        """,
        (
            session_id,
            tool_use_id,
            component_type,
            component,
            invoked_at,
            result_ok,
            turns_used,
            max_turns,
            payload,
        ),
    )


class TestPhase4ComputeBaselines(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "sessions.db")
        self.original_db_path = sessions_db.DB_PATH
        sessions_db.set_db_path(self.db_path)
        sessions_db.init_db()

    def tearDown(self):
        sessions_db.set_db_path(self.original_db_path)
        self.tmpdir.cleanup()

    def test_commit_windows_and_metric_values(self):
        conn = sqlite3.connect(self.db_path)
        before_times = [
            "2026-04-01T10:00:00+00:00",
            "2026-04-01T11:00:00+00:00",
            "2026-04-02T10:00:00+00:00",
            "2026-04-03T10:00:00+00:00",
            "2026-04-04T10:00:00+00:00",
        ]
        after_times = [
            "2026-04-06T10:00:00+00:00",
            "2026-04-07T10:00:00+00:00",
            "2026-04-08T10:00:00+00:00",
            "2026-04-09T10:00:00+00:00",
            "2026-04-10T10:00:00+00:00",
        ]
        for index, time_start in enumerate(before_times, start=1):
            sid = f"before-{index}"
            _insert_session(conn, sid, time_start)
        for index, time_start in enumerate(after_times, start=1):
            sid = f"after-{index}"
            _insert_session(conn, sid, time_start)

        _insert_plugin_event(conn, "before-1", "tool-before-1", before_times[0], correction=True, adopted=True, result_ok=1)
        _insert_plugin_event(conn, "before-2", "tool-before-2", before_times[1], correction=True, result_ok=0)
        _insert_plugin_event(conn, "before-3", "tool-before-3", before_times[2], abandon=True, adopted=True, result_ok=1)
        _insert_plugin_event(conn, "before-4", "tool-before-4", before_times[3], component_type="agent", adopted=True, turns_used=5, max_turns=10)
        _insert_plugin_event(conn, "before-5", "tool-before-5", before_times[4], component_type="agent", result_ok=1, turns_used=8, max_turns=10)

        _insert_plugin_event(conn, "after-1", "tool-after-1", after_times[0], correction=True, adopted=True, result_ok=1)
        _insert_plugin_event(conn, "after-2", "tool-after-2", after_times[1], adopted=True, result_ok=1)
        _insert_plugin_event(conn, "after-3", "tool-after-3", after_times[2], adopted=True, result_ok=1)
        _insert_plugin_event(conn, "after-4", "tool-after-4", after_times[3], component_type="agent", adopted=True, result_ok=1, turns_used=4, max_turns=10)
        _insert_plugin_event(conn, "after-5", "tool-after-5", after_times[4], component_type="agent", result_ok=1, turns_used=6, max_turns=10)
        conn.commit()
        conn.close()

        sessions_db.upsert_plugin_change(
            {
                "plugin": "dev-workflow",
                "component": "verify-plan",
                "commit_hash": "abc1234567890",
                "commit_date": "2026-04-05T00:00:00+00:00",
                "change_type": "fix",
                "summary": "tighten verify-plan",
            }
        )

        summary = compute_baselines.compute_baselines(
            db_path=self.db_path,
            window_spec="all",
            now=datetime(2026, 4, 12, tzinfo=timezone.utc),
        )
        self.assertEqual(summary["rows_written"], 8)

        rows = sessions_db.query_baselines(window_spec="all", plugin="dev-workflow", component="verify-plan", latest_only=False)
        by_metric_and_window = {
            (row["metric_name"], row["window_start"], row["window_end"]): row for row in rows
        }

        before_key = ("correction_rate", None, "2026-04-05T00:00:00+00:00")
        after_key = ("correction_rate", "2026-04-05T00:00:00+00:00", "2026-04-12T00:00:00+00:00")
        self.assertEqual(by_metric_and_window[before_key]["metric_value"], 0.4)
        self.assertEqual(by_metric_and_window[after_key]["metric_value"], 0.2)

        before_adoption = by_metric_and_window[("adoption_rate", None, "2026-04-05T00:00:00+00:00")]
        after_adoption = by_metric_and_window[("adoption_rate", "2026-04-05T00:00:00+00:00", "2026-04-12T00:00:00+00:00")]
        self.assertEqual(before_adoption["metric_value"], 0.75)
        self.assertEqual(before_adoption["sample_size"], 4)
        self.assertEqual(after_adoption["metric_value"], 0.8)
        self.assertEqual(after_adoption["sample_size"], 5)

        before_efficiency = by_metric_and_window[("agent_efficiency_avg", None, "2026-04-05T00:00:00+00:00")]
        after_efficiency = by_metric_and_window[("agent_efficiency_avg", "2026-04-05T00:00:00+00:00", "2026-04-12T00:00:00+00:00")]
        self.assertEqual(before_efficiency["metric_value"], 0.65)
        self.assertEqual(before_efficiency["sample_size"], 2)
        self.assertEqual(after_efficiency["metric_value"], 0.5)
        self.assertEqual(after_efficiency["sample_size"], 2)

    def test_skips_segments_below_minimum_invocations(self):
        conn = sqlite3.connect(self.db_path)
        times = [
            "2026-04-01T10:00:00+00:00",
            "2026-04-02T10:00:00+00:00",
            "2026-04-03T10:00:00+00:00",
            "2026-04-04T10:00:00+00:00",
            "2026-04-06T10:00:00+00:00",
        ]
        for index, time_start in enumerate(times, start=1):
            sid = f"sparse-{index}"
            _insert_session(conn, sid, time_start)
            _insert_plugin_event(conn, sid, f"tool-sparse-{index}", time_start, component="review-plan", adopted=True)
        conn.commit()
        conn.close()
        sessions_db.upsert_plugin_change(
            {
                "plugin": "dev-workflow",
                "component": "review-plan",
                "commit_hash": "def4567890123",
                "commit_date": "2026-04-05T00:00:00+00:00",
                "change_type": "fix",
                "summary": "split sparse windows",
            }
        )

        summary = compute_baselines.compute_baselines(
            db_path=self.db_path,
            window_spec="all",
            now=datetime(2026, 4, 12, tzinfo=timezone.utc),
        )
        self.assertEqual(summary["rows_written"], 0)
        rows = sessions_db.query_baselines(window_spec="all", plugin="dev-workflow", component="review-plan", latest_only=False)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
