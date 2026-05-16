"""
Tests for preflight.py — dependency checks before running /master insights.

Run with:
    cd skill-master && python3 -m unittest tests.test_preflight -v
"""

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestDbMissing(unittest.TestCase):
    def test_db_missing_raises_actionable(self):
        from scripts.preflight import check_db
        with self.assertRaises(FileNotFoundError) as ctx:
            check_db("/nonexistent/path/sessions.db")
        self.assertIn("install personal-os/session-reflect", str(ctx.exception).lower())


class TestSchemaOutdated(unittest.TestCase):
    def _make_minimal_db_without_column(self) -> str:
        """Create a DB with plugin_events table missing invocation_trigger."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        conn.execute("""
            CREATE TABLE plugin_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                tool_use_id TEXT NOT NULL,
                component_type TEXT NOT NULL,
                plugin TEXT,
                component TEXT NOT NULL,
                invoked_at TEXT,
                result_ok INTEGER DEFAULT 1
            )
        """)
        conn.commit()
        conn.close()
        return tmp.name

    def test_schema_outdated_raises_actionable(self):
        from scripts.preflight import check_schema
        db_path = self._make_minimal_db_without_column()
        try:
            with self.assertRaises(RuntimeError) as ctx:
                check_schema(db_path)
            msg = str(ctx.exception).lower()
            self.assertIn("run migrate_schema in personal-os phase 1", msg)
        finally:
            os.unlink(db_path)


class TestMarketplaceJsonMissing(unittest.TestCase):
    def test_marketplace_json_missing(self):
        from scripts.preflight import check_marketplace
        with tempfile.TemporaryDirectory() as tmpdir:
            # No .claude-plugin/marketplace.json in tmpdir
            with self.assertRaises((FileNotFoundError, RuntimeError)) as ctx:
                check_marketplace(tmpdir)
            self.assertIn("marketplace.json", str(ctx.exception))


class TestGhUnavailable(unittest.TestCase):
    def test_gh_unavailable(self):
        from scripts.preflight import check_gh
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            with self.assertRaises(RuntimeError) as ctx:
                check_gh()
            msg = str(ctx.exception).lower()
            self.assertIn("install gh cli", msg)


if __name__ == "__main__":
    unittest.main()
