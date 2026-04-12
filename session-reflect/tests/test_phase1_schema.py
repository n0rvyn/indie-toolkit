#!/usr/bin/env python3
"""Phase 1: sessions.db schema extension tests."""

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestSchemaExtension(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "sessions.db"
        # Patch DB_PATH so init_db writes to our temp location
        import sessions_db
        self._orig_db_path = sessions_db.DB_PATH
        sessions_db.DB_PATH = self.db_path
        self.sessions_db = sessions_db

    def tearDown(self):
        self.sessions_db.DB_PATH = self._orig_db_path
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_creates_all_tables(self):
        self.sessions_db.init_db()
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        conn.close()
        names = {r[0] for r in rows}
        # 17 existing + 8 new
        expected_new = {
            "plugin_events", "plugin_changes", "analysis_checkpoints",
            "baselines", "knowledge_distilled", "session_links",
            "pre_brief_hints", "ai_behavior_audit",
        }
        self.assertTrue(expected_new.issubset(names),
                        f"Missing new tables: {expected_new - names}")

    def test_init_is_idempotent(self):
        self.sessions_db.init_db()
        # Second call should not raise
        self.sessions_db.init_db()
        # Should still have all tables
        conn = sqlite3.connect(self.db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        conn.close()
        self.assertGreaterEqual(count, 25)

    def test_analyzer_version_column_added(self):
        self.sessions_db.init_db()
        conn = sqlite3.connect(self.db_path)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        conn.close()
        self.assertIn("analyzer_version", cols)

    def test_analyzer_version_default_for_existing_rows(self):
        # Simulate: existing session row inserted before migration (no analyzer_version)
        # then migration runs and backfills the default
        Path(self.tmpdir).mkdir(parents=True, exist_ok=True)
        # Create initial schema WITHOUT analyzer_version
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE sessions (session_id TEXT PRIMARY KEY, source TEXT)")
        conn.execute("INSERT INTO sessions (session_id, source) VALUES ('legacy-1', 'claude-code')")
        conn.commit()
        conn.close()
        # Run migration
        self.sessions_db.migrate_schema()

        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT analyzer_version FROM sessions WHERE session_id = 'legacy-1'"
        ).fetchone()
        conn.close()
        self.assertEqual(row[0], "pre-2026-04-12")

    def test_new_table_indexes_present(self):
        self.sessions_db.init_db()
        conn = sqlite3.connect(self.db_path)
        idx_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        ).fetchall()
        conn.close()
        names = {r[0] for r in idx_rows}
        expected_idx = {
            "idx_plugin_events_session", "idx_plugin_events_component",
            "idx_plugin_changes_plugin", "idx_baselines_lookup",
            "idx_knowledge_distilled_hash", "idx_session_links_source",
            "idx_session_links_target", "idx_ai_behavior_audit_session",
            "idx_ai_behavior_audit_rule", "idx_pre_brief_hints_plugin",
            "idx_analysis_checkpoints_pending",
        }
        self.assertTrue(expected_idx.issubset(names),
                        f"Missing indexes: {expected_idx - names}")

    def test_helper_functions_round_trip(self):
        self.sessions_db.init_db()
        # Insert a session first to satisfy FK constraint
        self.sessions_db.upsert_session(
            "s-1",
            {
                "source": "claude-code",
                "project": "demo",
                "project_path": "/tmp/demo",
                "analyzer_version": "phase2-test",
            },
        )
        conn = sqlite3.connect(self.db_path)
        stored_version = conn.execute(
            "SELECT analyzer_version FROM sessions WHERE session_id = 's-1'"
        ).fetchone()[0]
        self.assertEqual(stored_version, "phase2-test")

        # plugin_events
        self.sessions_db.upsert_plugin_event({
            "session_id": "s-1",
            "tool_use_id": "tu-1",
            "component_type": "skill",
            "plugin": "dev-workflow",
            "component": "verify-plan",
            "invoked_at": "2026-04-12T10:00:00",
            "input_text": "verify the plan",
            "result_text": "OK",
            "result_ok": 1,
            "post_dispatch_signals": {"user_correction_within_3_turns": False},
        })
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT component, plugin, result_ok FROM plugin_events WHERE tool_use_id='tu-1'"
        ).fetchone()
        self.assertEqual(row, ("verify-plan", "dev-workflow", 1))

        # checkpoint + pending
        self.sessions_db.upsert_checkpoint("s-1", "v1.0.0")
        n = self.sessions_db.mark_re_analyze_pending("v2.0.0")
        self.assertEqual(n, 1)
        pending = self.sessions_db.get_pending_session_ids()
        self.assertIn("s-1", pending)
        conn.close()

    def test_plugin_event_idempotent_on_tool_use_id(self):
        self.sessions_db.init_db()
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO sessions (session_id, source) VALUES ('s-1', 'claude-code')")
        conn.commit()
        conn.close()

        # Insert twice with same tool_use_id
        for _ in range(2):
            self.sessions_db.upsert_plugin_event({
                "session_id": "s-1",
                "tool_use_id": "tu-dup",
                "component_type": "agent",
                "plugin": "dev-workflow",
                "component": "plan-verifier",
            })
        conn = sqlite3.connect(self.db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM plugin_events WHERE tool_use_id='tu-dup'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(count, 1, "upsert_plugin_event should be idempotent on tool_use_id")

    def test_knowledge_distilled_dedup_merges_session_ids(self):
        self.sessions_db.init_db()
        # First insert
        self.sessions_db.upsert_knowledge_distilled({
            "content_hash": "h1",
            "sub_type": "solution",
            "title": "Use X for Y",
            "content": "...",
            "session_ids": ["s-1"],
            "significance": 4,
        })
        # Second insert with same hash, different session
        self.sessions_db.upsert_knowledge_distilled({
            "content_hash": "h1",
            "sub_type": "solution",
            "title": "Use X for Y",
            "content": "...",
            "session_ids": ["s-2"],
            "significance": 4,
        })
        import json
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT session_ids FROM knowledge_distilled WHERE content_hash='h1'"
        ).fetchone()
        count = conn.execute("SELECT COUNT(*) FROM knowledge_distilled").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1, "duplicate content_hash should merge, not insert new row")
        ids = json.loads(row[0])
        self.assertEqual(sorted(ids), ["s-1", "s-2"])


if __name__ == "__main__":
    unittest.main()
