#!/usr/bin/env python3
"""Phase 3 tests for task-trace queries and unfinished hints."""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import sessions_db


def _insert_session(conn, session_id, outcome, time_start):
    conn.execute("""
        INSERT INTO sessions (
            session_id, source, project, project_path, branch, model,
            time_start, time_end, duration_min, turns_user, turns_asst,
            tokens_in, tokens_out, cache_read, cache_create, cache_hit_rate,
            analyzer_version, session_dna, task_summary, analyzed_at, outcome
        ) VALUES (?, 'claude-code', 'alpha', '/tmp/alpha', 'main', 'claude-opus-4-6',
                  ?, ?, 30.0, 1, 1, 100, 50, 0, 0, 0.0, '2026-04-12-phase2', 'build',
                  'trace test', ?, ?)
    """, (session_id, time_start, time_start, time_start, outcome))


class TestPhase3TaskTrace(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "sessions.db")
        self.original_db_path = sessions_db.DB_PATH
        sessions_db.set_db_path(self.db_path)
        sessions_db.init_db()
        conn = sqlite3.connect(self.db_path)
        _insert_session(conn, "trace-1", "failed", "2026-04-10T10:00:00+00:00")
        _insert_session(conn, "trace-2", "interrupted", "2026-04-10T11:00:00+00:00")
        _insert_session(conn, "trace-3", "completed", "2026-04-10T12:00:00+00:00")
        conn.execute("""
            INSERT INTO session_links (source_session_id, target_session_id, link_type, confidence, detected_at)
            VALUES
            ('trace-1', 'trace-2', 'continuation', 0.81, '2026-04-10T12:30:00+00:00'),
            ('trace-2', 'trace-3', 'continuation', 0.88, '2026-04-10T12:31:00+00:00')
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        sessions_db.set_db_path(self.original_db_path)
        self.tmpdir.cleanup()

    def test_task_trace_walks_both_directions(self):
        rows = sessions_db.get_task_trace("trace-2")
        self.assertEqual([row["session_id"] for row in rows], ["trace-1", "trace-2", "trace-3"])

    def test_previous_unfinished_session(self):
        row = sessions_db.get_previous_unfinished_session("trace-3")
        self.assertEqual(row["session_id"], "trace-2")
        hint = sessions_db.format_unfinished_hint(row)
        self.assertIn("Previous unfinished linked session: trace-2", hint)

    def test_task_trace_markdown_format(self):
        markdown = sessions_db.format_task_trace_markdown(sessions_db.get_task_trace("trace-2"))
        self.assertIn("| session_id | project | outcome | time |", markdown)
        self.assertIn("| trace-2 | alpha | interrupted | 2026-04-10T11:00:00+00:00 |", markdown)

    def test_cli_task_trace_uses_sqlite_override(self):
        result = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "..", "scripts", "sessions_db.py"),
                "--sqlite-db",
                self.db_path,
                "--query",
                "task-trace",
                "--session-id",
                "trace-2",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        rows = json.loads(result.stdout)
        self.assertEqual([row["session_id"] for row in rows], ["trace-1", "trace-2", "trace-3"])


if __name__ == "__main__":
    unittest.main()
