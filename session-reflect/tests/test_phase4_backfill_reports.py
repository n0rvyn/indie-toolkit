#!/usr/bin/env python3
"""Phase 4 tests for backfill report generation and anomaly capture."""

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import sessions_db


def _load_backfill():
    spec = importlib.util.spec_from_file_location("backfill", SCRIPT_DIR / "backfill.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
                  'backfill test', ?, 'completed')
        """,
        (session_id, time_start, time_start, time_start),
    )


class TestPhase4BackfillReports(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "sessions.db")
        self.original_db_path = sessions_db.DB_PATH
        sessions_db.set_db_path(self.db_path)
        sessions_db.init_db()
        self.backfill = _load_backfill()

    def tearDown(self):
        sessions_db.set_db_path(self.original_db_path)
        self.tmpdir.cleanup()

    def test_build_report_and_write_file(self):
        summary = {
            "report_date": "2026-04-12",
            "analyzer_version": "2026-04-12-phase4",
            "discovered": 10,
            "pending": 8,
            "succeeded": 7,
            "failed": 1,
            "links_written": 3,
            "baseline_rows_written": 12,
            "baseline_window": "60d",
            "failures": [{"session_id": "bad-1", "error": "parser failed"}],
            "anomalies": [{"session_id": "warn-1", "missing": ["analysis_meta"], "invalid": ["plugin_events"]}],
            "duration_min": 1.25,
        }
        markdown = self.backfill.build_backfill_report(summary)
        self.assertIn("- discovered: 10", markdown)
        self.assertIn("- bad-1: parser failed", markdown)
        self.assertIn("- warn-1: missing=analysis_meta; invalid=plugin_events", markdown)

        report_path = self.backfill.write_backfill_report(
            summary,
            report_root=self.tmpdir.name,
            now=datetime(2026, 4, 12, 12, 0, 0),
        )
        self.assertTrue(report_path.exists())
        self.assertIn("backfill report", report_path.read_text())

    def test_resolve_discovery_days_full_overrides_days(self):
        self.assertIsNone(self.backfill.resolve_discovery_days(days=30, full=True))
        self.assertEqual(self.backfill.resolve_discovery_days(days=30, full=False), 30)

    def test_backfill_anomalies_include_missing_dense_rows_and_invalid_plugin_events(self):
        conn = sqlite3.connect(self.db_path)
        _insert_session(conn, "session-a", "2026-04-10T10:00:00+00:00")
        conn.execute(
            "INSERT INTO tool_calls (session_id, seq_idx, tool_name, file_path, is_error) VALUES ('session-a', 1, 'Skill', NULL, 0)"
        )
        conn.execute(
            """
            INSERT INTO plugin_events (
                session_id, tool_use_id, component_type, plugin, component, invoked_at,
                input_text, result_text, result_ok, agent_turns_used, agent_max_turns,
                model_override, post_dispatch_signals
            ) VALUES ('session-a', 'tool-a', 'skill', 'dev-workflow', 'verify-plan', NULL, '{}', '{}', 1, NULL, NULL, NULL, '{}')
            """
        )
        conn.execute(
            """
            INSERT INTO analysis_meta (session_id, analyzer_version, parsed_fields)
            VALUES ('session-a', '2026-04-12-phase4', NULL)
            """
        )
        conn.commit()
        conn.close()

        anomalies = sessions_db.get_backfill_anomalies(["session-a"])
        self.assertEqual(len(anomalies), 1)
        anomaly = anomalies[0]
        self.assertIn("analysis_meta", anomaly["invalid"])
        self.assertIn("plugin_events", anomaly["invalid"])
        self.assertIn("session_features", anomaly["missing"])
        self.assertIn("token_audit", anomaly["missing"])
        self.assertIn("session_outcomes", anomaly["missing"])
        self.assertIn("rhythm_stats", anomaly["missing"])
        self.assertIn("ai_behavior_audit", anomaly["missing"])

    def test_backfill_main_writes_report(self):
        session_meta = {
            "session_id": "live-1",
            "source": "claude-code",
            "file_path": "/tmp/live-1.jsonl",
        }

        def fake_parse_one(meta):
            conn = sqlite3.connect(self.db_path)
            _insert_session(conn, meta["session_id"], "2026-04-10T10:00:00+00:00")
            conn.execute(
                """
                INSERT INTO analysis_meta (session_id, analyzer_version, parsed_fields)
                VALUES ('live-1', '2026-04-12-phase4', 4)
                """
            )
            conn.execute(
                """
                INSERT INTO session_features (
                    session_id, dna, tool_density, correction_ratio, token_per_turn,
                    project_complexity, predicted_outcome, actual_outcome
                ) VALUES ('live-1', 'build', 0.1, 0.0, 50.0, 0.5, 'completed', 'completed')
                """
            )
            conn.execute(
                """
                INSERT INTO token_audit (session_id, total_tokens, cache_hit_rate, wasted_tokens, efficiency_score)
                VALUES ('live-1', 150, 0.0, 0, 0.8)
                """
            )
            conn.execute(
                """
                INSERT INTO session_outcomes (session_id, outcome, end_trigger, last_tool, satisfaction_signal)
                VALUES ('live-1', 'completed', 'done', 'Skill', 'positive')
                """
            )
            conn.execute(
                """
                INSERT INTO rhythm_stats (session_id, avg_response_interval_s, long_pause_count, turn_count)
                VALUES ('live-1', 3.0, 0, 2)
                """
            )
            conn.execute(
                """
                INSERT INTO ai_behavior_audit (session_id, turn, rule_category, rule_id, hit, evidence)
                VALUES ('live-1', 1, 'core', 'core-1', 0, 'ok')
                """
            )
            conn.execute(
                """
                INSERT INTO plugin_events (
                    session_id, tool_use_id, component_type, plugin, component, invoked_at,
                    input_text, result_text, result_ok, agent_turns_used, agent_max_turns,
                    model_override, post_dispatch_signals
                ) VALUES
                ('live-1', 'tool-1', 'skill', 'dev-workflow', 'verify-plan', '2026-04-10T10:00:00+00:00', '{}', '{}', 1, NULL, NULL, NULL, '{}'),
                ('live-1', 'tool-2', 'skill', 'dev-workflow', 'verify-plan', '2026-04-10T10:01:00+00:00', '{}', '{}', 1, NULL, NULL, NULL, '{}'),
                ('live-1', 'tool-3', 'skill', 'dev-workflow', 'verify-plan', '2026-04-10T10:02:00+00:00', '{}', '{}', 1, NULL, NULL, NULL, '{}'),
                ('live-1', 'tool-4', 'skill', 'dev-workflow', 'verify-plan', '2026-04-10T10:03:00+00:00', '{}', '{}', 1, NULL, NULL, NULL, '{}'),
                ('live-1', 'tool-5', 'skill', 'dev-workflow', 'verify-plan', '2026-04-10T10:04:00+00:00', '{}', '{}', 1, NULL, NULL, NULL, '{}')
                """
            )
            conn.commit()
            conn.close()
            return True, None

        with mock.patch.object(self.backfill, "discover_all", return_value=[session_meta]), \
             mock.patch.object(self.backfill, "filter_to_pending", return_value=[session_meta]), \
             mock.patch.object(self.backfill, "parse_one", side_effect=fake_parse_one), \
             mock.patch.object(self.backfill, "write_backfill_report") as mock_write_report:
            self.backfill.sessions_db.set_db_path(self.db_path)
            with mock.patch.object(sys, "argv", ["backfill.py", "--full"]):
                self.backfill.main()

        mock_write_report.assert_called_once()
        summary = mock_write_report.call_args[0][0]
        self.assertEqual(summary["discovered"], 1)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["succeeded"], 1)
        self.assertEqual(summary["failed"], 0)


if __name__ == "__main__":
    unittest.main()
