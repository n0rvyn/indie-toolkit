#!/usr/bin/env python3
"""Phase 4 tests for baseline query rendering and targeted rebaseline."""

import os
import sqlite3
import subprocess
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
                  'query test', ?, 'completed')
        """,
        (session_id, time_start, time_start, time_start),
    )


def _insert_plugin_event(conn, session_id, tool_use_id, plugin, component, invoked_at, adopted=False):
    conn.execute(
        """
        INSERT INTO plugin_events (
            session_id, tool_use_id, component_type, plugin, component, invoked_at,
            input_text, result_text, result_ok, agent_turns_used, agent_max_turns,
            model_override, post_dispatch_signals
        ) VALUES (?, ?, 'skill', ?, ?, ?, '{}', '{}', 1, NULL, NULL, NULL, ?)
        """,
        (
            session_id,
            tool_use_id,
            plugin,
            component,
            invoked_at,
            sessions_db.json.dumps(
                {
                    "user_correction_within_3_turns": False,
                    "user_abandoned_topic": False,
                    "user_repeated_manually": False,
                    "result_adopted": adopted,
                }
            ),
        ),
    )


class TestPhase4ReflectQueries(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "sessions.db")
        self.original_db_path = sessions_db.DB_PATH
        sessions_db.set_db_path(self.db_path)
        sessions_db.init_db()

    def tearDown(self):
        sessions_db.set_db_path(self.original_db_path)
        self.tmpdir.cleanup()

    def _seed_plugin(self, plugin, component, prefix, adopted_every=2):
        conn = sqlite3.connect(self.db_path)
        for index in range(5):
            session_id = f"{prefix}-{index}"
            timestamp = f"2026-04-0{index + 1}T10:00:00+00:00"
            _insert_session(conn, session_id, timestamp)
            _insert_plugin_event(
                conn,
                session_id,
                f"tool-{session_id}",
                plugin,
                component,
                timestamp,
                adopted=(index % adopted_every == 0),
            )
        conn.commit()
        conn.close()

    def test_format_baselines_markdown(self):
        self._seed_plugin("dev-workflow", "verify-plan", "dev")
        compute_baselines.compute_baselines(
            db_path=self.db_path,
            window_spec="60d",
            now=datetime(2026, 4, 12, tzinfo=timezone.utc),
        )
        rows = sessions_db.query_baselines(window_spec="60d", plugin="dev-workflow")
        markdown = sessions_db.format_baselines_markdown(rows)
        self.assertIn("| plugin | component | metric | value | sample | window | commits |", markdown)
        self.assertIn("| dev-workflow | verify-plan | correction_rate |", markdown)

    def test_targeted_rebaseline_preserves_other_plugins(self):
        self._seed_plugin("dev-workflow", "verify-plan", "dev")
        self._seed_plugin("session-reflect", "reflect", "reflect")

        compute_baselines.compute_baselines(
            db_path=self.db_path,
            window_spec="60d",
            now=datetime(2026, 4, 12, tzinfo=timezone.utc),
        )
        before_dev = sessions_db.query_baselines(window_spec="60d", plugin="dev-workflow", latest_only=False)
        before_reflect = sessions_db.query_baselines(window_spec="60d", plugin="session-reflect", latest_only=False)

        compute_baselines.compute_baselines(
            db_path=self.db_path,
            window_spec="60d",
            plugin="dev-workflow",
            now=datetime(2026, 4, 13, tzinfo=timezone.utc),
            replace_existing=True,
        )
        after_dev = sessions_db.query_baselines(window_spec="60d", plugin="dev-workflow", latest_only=False)
        after_reflect = sessions_db.query_baselines(window_spec="60d", plugin="session-reflect", latest_only=False)

        self.assertEqual(len(after_reflect), len(before_reflect))
        self.assertEqual(len(after_dev), len(before_dev))
        dev_timestamps = {row["computed_at"] for row in after_dev}
        reflect_timestamps = {row["computed_at"] for row in after_reflect}
        self.assertEqual(len(dev_timestamps), 1)
        self.assertEqual(len(reflect_timestamps), 1)
        self.assertNotEqual(next(iter(dev_timestamps)), next(iter(reflect_timestamps)))

    def test_cli_baselines_defaults_to_60d(self):
        self._seed_plugin("dev-workflow", "verify-plan", "dev")
        compute_baselines.compute_baselines(
            db_path=self.db_path,
            window_spec="60d",
            now=datetime(2026, 4, 12, tzinfo=timezone.utc),
        )
        result = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "..", "scripts", "sessions_db.py"),
                "--sqlite-db",
                self.db_path,
                "--query",
                "baselines",
                "--plugin",
                "dev-workflow",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn('"window_spec": "60d"', result.stdout)


if __name__ == "__main__":
    unittest.main()
