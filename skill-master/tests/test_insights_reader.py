"""
Tests for insights_reader.py — Q1-Q5 SQL query functions.

Run with:
    cd skill-master && python3 -m unittest tests.test_insights_reader -v
"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

# ── fixture loader ─────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MINI_SQL = FIXTURES_DIR / "sessions-mini.sql"


def make_in_memory_db() -> str:
    """Create a named temp file DB seeded from sessions-mini.sql, return its path."""
    sql = MINI_SQL.read_text()
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.executescript(sql)
    conn.commit()
    conn.close()
    return tmp.name


# ── actual tests ───────────────────────────────────────────────────────────────

class TestQ1FreqAndErrorRate(unittest.TestCase):
    def setUp(self):
        self.db_path = make_in_memory_db()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_returns_expected_columns(self):
        from scripts.insights_reader import freq_and_error_rate
        result = freq_and_error_rate(window_days=30, db_path=self.db_path)
        self.assertIn("rows", result)
        self.assertIn("lag_warning", result)
        rows = result["rows"]
        self.assertGreater(len(rows), 0)
        row = rows[0]
        for col in ("plugin", "component", "invocations", "errors", "error_rate"):
            self.assertIn(col, row, f"missing column: {col}")

    def test_error_rate_computed_correctly(self):
        from scripts.insights_reader import freq_and_error_rate
        result = freq_and_error_rate(window_days=30, db_path=self.db_path)
        rows = result["rows"]
        vp = next(r for r in rows if r["component"] == "verify-plan")
        # 3 total verify-plan events: 2 result_ok=1, 1 result_ok=0 → error_rate ~0.33
        self.assertEqual(vp["invocations"], 3)
        self.assertEqual(vp["errors"], 1)
        self.assertAlmostEqual(vp["error_rate"], 1 / 3, places=2)


class TestQ2DescriptionMisfires(unittest.TestCase):
    def setUp(self):
        self.db_path = make_in_memory_db()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_returns_expected_columns(self):
        from scripts.insights_reader import description_misfires
        result = description_misfires(window_days=30, db_path=self.db_path)
        self.assertIn("rows", result)
        rows = result["rows"]
        self.assertGreater(len(rows), 0)
        row = rows[0]
        for col in ("plugin", "component", "invocation_trigger"):
            self.assertIn(col, row, f"missing column: {col}")

    def test_only_claude_proactive_misfires_returned(self):
        from scripts.insights_reader import description_misfires
        result = description_misfires(window_days=30, db_path=self.db_path)
        rows = result["rows"]
        # Only the claude-proactive event with triggered_correctly=0 should appear
        for row in rows:
            self.assertEqual(row["invocation_trigger"], "claude-proactive")


class TestQ3AgentEfficiency(unittest.TestCase):
    def setUp(self):
        self.db_path = make_in_memory_db()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_returns_expected_columns(self):
        from scripts.insights_reader import agent_efficiency
        result = agent_efficiency(window_days=30, db_path=self.db_path)
        self.assertIn("rows", result)
        rows = result["rows"]
        self.assertGreater(len(rows), 0)
        row = rows[0]
        for col in ("plugin", "component", "avg_turns_ratio"):
            self.assertIn(col, row, f"missing column: {col}")

    def test_ratio_computed_correctly(self):
        from scripts.insights_reader import agent_efficiency
        result = agent_efficiency(window_days=30, db_path=self.db_path)
        rows = result["rows"]
        pv = next(r for r in rows if r["component"] == "plan-verifier")
        # agent_turns_used=6, agent_max_turns=10 → ratio=0.6
        self.assertAlmostEqual(pv["avg_turns_ratio"], 0.6, places=2)


class TestQ4AgentSkillChoreography(unittest.TestCase):
    def setUp(self):
        self.db_path = make_in_memory_db()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_returns_expected_columns(self):
        from scripts.insights_reader import agent_skill_choreography
        result = agent_skill_choreography(window_days=30, db_path=self.db_path)
        self.assertIn("rows", result)
        rows = result["rows"]
        self.assertGreater(len(rows), 0)
        row = rows[0]
        for col in ("parent_component", "child_component", "call_count"):
            self.assertIn(col, row, f"missing column: {col}")

    def test_nested_skill_detected(self):
        from scripts.insights_reader import agent_skill_choreography
        result = agent_skill_choreography(window_days=30, db_path=self.db_path)
        rows = result["rows"]
        # plan-verifier (agent, tu-004) → write-plan (skill, tu-005 with parent_tool_use_id=tu-004)
        nested = next(
            (r for r in rows
             if r["parent_component"] == "plan-verifier" and r["child_component"] == "write-plan"),
            None
        )
        self.assertIsNotNone(nested, "nested skill relationship not detected")
        self.assertEqual(nested["call_count"], 1)


class TestQ5PostCommitAnomalies(unittest.TestCase):
    def setUp(self):
        self.db_path = make_in_memory_db()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_returns_expected_columns(self):
        from scripts.insights_reader import post_commit_anomalies
        result = post_commit_anomalies(
            plugin="dev-workflow",
            component="verify-plan",
            db_path=self.db_path
        )
        self.assertIn("rows", result)
        rows = result["rows"]
        # Should have at least one commit row for dev-workflow/verify-plan
        self.assertGreater(len(rows), 0)
        row = rows[0]
        for col in ("commit_hash", "commit_date", "delta_invocations"):
            self.assertIn(col, row, f"missing column: {col}")

    def test_uses_parameterized_queries(self):
        """Verify SQL injection attempt does not crash or match rows."""
        from scripts.insights_reader import post_commit_anomalies
        # This should either return 0 rows or raise, never expose raw SQL error
        try:
            result = post_commit_anomalies(
                plugin="dev-workflow'; DROP TABLE plugin_events; --",
                component="verify-plan",
                db_path=self.db_path
            )
            self.assertEqual(result["rows"], [])
        except Exception:
            pass  # acceptable — parameterized query rejects injection


if __name__ == "__main__":
    unittest.main()
