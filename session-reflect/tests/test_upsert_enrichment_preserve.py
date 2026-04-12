#!/usr/bin/env python3
"""Regression test: upsert_session must preserve enrichment_pending and enriched_at.

Bug: prior INSERT OR REPLACE wiped those two columns on every re-parse, silently
re-queueing LLM enrichment work. Fix: ON CONFLICT DO UPDATE with explicit column
list omitting enrichment_pending and enriched_at.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestUpsertPreservesEnrichment(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "sessions.db"
        import sessions_db
        self._orig_db_path = sessions_db.DB_PATH
        sessions_db.DB_PATH = self.db_path
        self.sessions_db = sessions_db
        self.sessions_db.init_db()

    def tearDown(self):
        self.sessions_db.DB_PATH = self._orig_db_path
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_session(self, session_id="sess-001"):
        return {
            "source": "claude",
            "project": "demo",
            "project_path": "/tmp/demo",
            "branch": "main",
            "model": "claude-opus-4-6",
            "time_start": "2026-04-12T10:00:00",
            "time_end": "2026-04-12T10:30:00",
            "duration_min": 30,
            "turns_user": 5,
            "turns_asst": 5,
            "tokens_in": 1000,
            "tokens_out": 2000,
            "cache_read": 0,
            "cache_create": 0,
            "cache_hit_rate": 0.0,
            "analyzer_version": "2026-04-12",
            "session_dna": None,
            "task_summary": None,
            "analyzed_at": "2026-04-12T10:31:00",
            "outcome": "complete",
        }

    def _get_enrichment_columns(self, session_id):
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT enrichment_pending, enriched_at FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return row
        finally:
            conn.close()

    def test_first_upsert_defaults_to_pending(self):
        """Fresh insert leaves enrichment_pending=1 (default) and enriched_at=NULL."""
        self.sessions_db.upsert_session("sess-001", self._make_session())
        pending, enriched_at = self._get_enrichment_columns("sess-001")
        self.assertEqual(pending, 1)
        self.assertIsNone(enriched_at)

    def test_reupsert_preserves_enriched_state(self):
        """Re-upserting an already-enriched session must NOT reset enrichment state."""
        self.sessions_db.upsert_session("sess-001", self._make_session())
        # Simulate enrichment completion
        self.sessions_db.mark_enriched(
            "sess-001",
            dimensions=None,
            audit_rows=None,
            session_dna="explorer",
            task_summary="demo task",
        )
        pending_before, enriched_at_before = self._get_enrichment_columns("sess-001")
        self.assertEqual(pending_before, 0)
        self.assertIsNotNone(enriched_at_before)

        # Re-parse scenario (e.g. --force-all backfill or analyzer-version bump)
        updated = self._make_session()
        updated["duration_min"] = 45  # simulate re-parse updating a parsing field
        self.sessions_db.upsert_session("sess-001", updated)

        pending_after, enriched_at_after = self._get_enrichment_columns("sess-001")
        self.assertEqual(pending_after, 0, "enrichment_pending must stay 0 after re-upsert")
        self.assertEqual(
            enriched_at_after, enriched_at_before,
            "enriched_at must be preserved across re-upsert",
        )

        # Parsing fields should still update
        conn = sqlite3.connect(self.db_path)
        try:
            duration = conn.execute(
                "SELECT duration_min FROM sessions WHERE session_id = ?",
                ("sess-001",),
            ).fetchone()[0]
            self.assertEqual(duration, 45)
        finally:
            conn.close()

    def test_reupsert_preserves_pending_when_still_pending(self):
        """Re-upsert on a still-pending session also preserves pending=1."""
        self.sessions_db.upsert_session("sess-002", self._make_session(session_id="sess-002"))
        pending_before, _ = self._get_enrichment_columns("sess-002")
        self.assertEqual(pending_before, 1)

        self.sessions_db.upsert_session("sess-002", self._make_session(session_id="sess-002"))
        pending_after, _ = self._get_enrichment_columns("sess-002")
        self.assertEqual(pending_after, 1)


if __name__ == "__main__":
    unittest.main()
