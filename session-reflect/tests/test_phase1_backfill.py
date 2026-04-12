#!/usr/bin/env python3
"""Phase 1: backfill.py orchestrator tests (checkpoint, dry-run, idempotent)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


class TestBackfillCheckpoints(unittest.TestCase):
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

    def test_pending_includes_unseen_sessions(self):
        # No sessions in db at all → discovered candidates are all pending
        candidates = [
            {"session_id": "new-1", "source": "claude-code", "file_path": "/tmp/fake1.jsonl"},
            {"session_id": "new-2", "source": "claude-code", "file_path": "/tmp/fake2.jsonl"},
        ]
        # Import via module spec since backfill.py contains a hyphen-incompatible context
        import importlib.util
        spec = importlib.util.spec_from_file_location("backfill", SCRIPT_DIR / "backfill.py")
        backfill = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backfill)

        pending = backfill.filter_to_pending(candidates)
        self.assertEqual({s["session_id"] for s in pending}, {"new-1", "new-2"})

    def test_pending_skips_completed_sessions(self):
        # Insert a session with completed checkpoint
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO sessions (session_id, source) VALUES ('done-1', 'claude-code')")
        conn.commit()
        conn.close()
        self.sessions_db.upsert_checkpoint("done-1", "v1")

        candidates = [
            {"session_id": "done-1", "source": "claude-code", "file_path": "/tmp/done1.jsonl"},
            {"session_id": "new-1", "source": "claude-code", "file_path": "/tmp/new1.jsonl"},
        ]
        import importlib.util
        spec = importlib.util.spec_from_file_location("backfill", SCRIPT_DIR / "backfill.py")
        backfill = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backfill)

        pending = backfill.filter_to_pending(candidates)
        self.assertEqual({s["session_id"] for s in pending}, {"new-1"})

    def test_pending_includes_re_analyze_flagged(self):
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO sessions (session_id, source) VALUES ('re-1', 'claude-code')")
        conn.commit()
        conn.close()
        self.sessions_db.upsert_checkpoint("re-1", "v1")
        # Bump version → marks re-1 as re_analyze_pending
        n = self.sessions_db.mark_re_analyze_pending("v2")
        self.assertEqual(n, 1)

        candidates = [
            {"session_id": "re-1", "source": "claude-code", "file_path": "/tmp/re1.jsonl"},
        ]
        import importlib.util
        spec = importlib.util.spec_from_file_location("backfill", SCRIPT_DIR / "backfill.py")
        backfill = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backfill)

        pending = backfill.filter_to_pending(candidates)
        self.assertEqual({s["session_id"] for s in pending}, {"re-1"})

    def test_resume_only_returns_sessions_without_checkpoints(self):
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO sessions (session_id, source) VALUES ('done-1', 'claude-code')")
        conn.execute("INSERT INTO sessions (session_id, source) VALUES ('done-2', 'claude-code')")
        conn.execute("INSERT INTO sessions (session_id, source) VALUES ('pending-1', 'claude-code')")
        conn.commit()
        conn.close()
        self.sessions_db.upsert_checkpoint("done-1", "v1")
        self.sessions_db.upsert_checkpoint("done-2", "v1")

        candidates = [
            {"session_id": "done-1", "source": "claude-code", "file_path": "/tmp/done1.jsonl"},
            {"session_id": "done-2", "source": "claude-code", "file_path": "/tmp/done2.jsonl"},
            {"session_id": "pending-1", "source": "claude-code", "file_path": "/tmp/pending1.jsonl"},
        ]
        import importlib.util
        spec = importlib.util.spec_from_file_location("backfill", SCRIPT_DIR / "backfill.py")
        backfill = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backfill)

        pending = backfill.filter_to_pending(candidates)
        self.assertEqual(
            {s["session_id"] for s in pending},
            {"pending-1"},
            "resume should skip checkpointed sessions and continue with only pending work",
        )


class TestBackfillCLI(unittest.TestCase):
    def test_help_lists_all_flags(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "backfill.py"), "--help"],
            capture_output=True, text=True, check=True,
        )
        for flag in ("--days", "--dry-run", "--resume", "--force-all", "--limit", "--bump-version"):
            self.assertIn(flag, result.stdout, f"Missing flag in --help: {flag}")

    def test_load_config_uses_default_adam_exclusion(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("backfill", SCRIPT_DIR / "backfill.py")
        backfill = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backfill)

        excluded, legacy = backfill._load_config()
        self.assertIn(".adam", excluded)
        self.assertEqual(legacy, [])

    def test_backfill_uses_shared_analyzer_version(self):
        import importlib.util
        from analyzer_version import ANALYZER_VERSION

        spec = importlib.util.spec_from_file_location("backfill", SCRIPT_DIR / "backfill.py")
        backfill = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backfill)
        self.assertEqual(backfill.ANALYZER_VERSION, ANALYZER_VERSION)


if __name__ == "__main__":
    unittest.main()
