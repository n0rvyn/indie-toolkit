#!/usr/bin/env python3
"""Phase 3 tests for plugin_changes ingest and before/after metrics."""

import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import sessions_db
from scan_plugin_changes import parse_commit_subject


def _insert_session(conn, session_id, time_start):
    conn.execute("""
        INSERT INTO sessions (
            session_id, source, project, project_path, branch, model,
            time_start, time_end, duration_min, turns_user, turns_asst,
            tokens_in, tokens_out, cache_read, cache_create, cache_hit_rate,
            analyzer_version, session_dna, task_summary, analyzed_at, outcome
        ) VALUES (?, 'claude-code', 'toolkit', '/tmp/toolkit', 'main', 'claude-opus-4-6',
                  ?, ?, 30.0, 1, 1, 100, 50, 0, 0, 0.0, '2026-04-12-phase2', 'build',
                  'metric test', ?, 'completed')
    """, (session_id, time_start, time_start, time_start))


def _insert_plugin_event(conn, session_id, correction=False, abandon=False, adopted=False, used=None, maximum=None):
    conn.execute("""
        INSERT INTO plugin_events (
            session_id, tool_use_id, component_type, plugin, component, invoked_at,
            input_text, result_text, result_ok, agent_turns_used, agent_max_turns,
            model_override, post_dispatch_signals
        ) VALUES (?, ?, 'skill', 'dev-workflow', 'verify-plan', ?, '{}', '{}', 1, ?, ?, NULL, ?)
    """, (
        session_id,
        f"tool-{session_id}",
        "2026-04-08T00:00:00+00:00",
        used,
        maximum,
        sessions_db.json.dumps({
            "user_correction_within_3_turns": correction,
            "user_abandoned_topic": abandon,
            "user_repeated_manually": False,
            "result_adopted": adopted,
        }),
    ))


class TestPhase3PluginChanges(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "sessions.db")
        self.original_db_path = sessions_db.DB_PATH
        sessions_db.set_db_path(self.db_path)
        sessions_db.init_db()

    def tearDown(self):
        sessions_db.set_db_path(self.original_db_path)
        self.tmpdir.cleanup()

    def test_parse_commit_subject(self):
        parsed = parse_commit_subject("fix(dev-workflow/verify-plan): tighten verifier output")
        self.assertEqual(parsed["plugin"], "dev-workflow")
        self.assertEqual(parsed["component"], "verify-plan")
        self.assertEqual(parsed["change_type"], "fix")
        self.assertEqual(parsed["summary"], "tighten verifier output")
        self.assertIsNone(parse_commit_subject("docs: update readme"))

    def test_query_plugin_changes_and_before_after_metric(self):
        conn = sqlite3.connect(self.db_path)
        _insert_session(conn, "before-1", "2026-04-07T12:00:00+00:00")
        _insert_session(conn, "before-2", "2026-04-07T18:00:00+00:00")
        _insert_session(conn, "after-1", "2026-04-09T12:00:00+00:00")
        _insert_session(conn, "after-2", "2026-04-09T18:00:00+00:00")
        _insert_plugin_event(conn, "before-1", correction=True, used=8, maximum=10)
        _insert_plugin_event(conn, "before-2", correction=False, used=7, maximum=10)
        _insert_plugin_event(conn, "after-1", correction=False, adopted=True, used=4, maximum=10)
        _insert_plugin_event(conn, "after-2", correction=False, adopted=True, used=5, maximum=10)
        conn.commit()
        conn.close()

        sessions_db.upsert_plugin_change({
            "plugin": "dev-workflow",
            "component": "verify-plan",
            "commit_hash": "9f885328d820a6e62b7a227042e4661b2b5e59b4",
            "commit_date": "2026-04-08T16:30:26+08:00",
            "change_type": "fix",
            "summary": "add truncation resilience and fix contract gaps in skills",
        })

        rows = sessions_db.query_plugin_changes(plugin="dev-workflow", component="verify-plan")
        self.assertEqual(len(rows), 1)
        metric = sessions_db.before_after_metric(
            plugin="dev-workflow",
            component="verify-plan",
            commit_hash="9f88532",
            metric_name="correction_rate",
            window_days=2,
        )
        self.assertEqual(metric["before"]["sample_size"], 2)
        self.assertEqual(metric["after"]["sample_size"], 2)
        self.assertEqual(metric["before"]["metric_value"], 0.5)
        self.assertEqual(metric["after"]["metric_value"], 0.0)

        efficiency = sessions_db.before_after_metric(
            plugin="dev-workflow",
            component="verify-plan",
            commit_hash="9f88532",
            metric_name="agent_efficiency_avg",
            window_days=2,
        )
        self.assertEqual(efficiency["before"]["metric_value"], 0.75)
        self.assertEqual(efficiency["after"]["metric_value"], 0.45)


if __name__ == "__main__":
    unittest.main()
