#!/usr/bin/env python3
"""Phase 2 contract tests for ai_behavior_audit rule-based enrichment.

Architecture C (2026-04-12): apply_enrichment no longer spawns `claude -p`.
These tests validate:
- the Phase 2 rule reference is intact
- build_system_prompt embeds the rule reference (used by /reflect --enrich when
  dispatching the session-parser agent via the Task tool in the host session)
- run_rule_based_audit detects style + tool-sequence heuristic rules locally
- apply_enrichment writes audit rows to the DB and marks enrichment_pending=1
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from analyzer_version import ANALYZER_VERSION  # noqa: E402
from parse_claude_session import parse_claude_session  # noqa: E402
from session_enrichment import (  # noqa: E402
    apply_enrichment,
    build_system_prompt,
    run_rule_based_audit,
)

TEST_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = TEST_ROOT / "tests" / "data" / "claude-plugin-sample.jsonl"


class TestPhase2AuditContract(unittest.TestCase):
    def test_rule_reference_has_expected_categories(self):
        text = (TEST_ROOT / "references" / "claude-md-rule-enumeration.md").read_text()
        for category in ("core", "behavior", "debug", "gate", "decision", "forbidden", "style"):
            self.assertIn(f"| {category} |", text)

    def test_schema_docs_reference_phase2_fields(self):
        schema = (TEST_ROOT / "references" / "session-schema.md").read_text()
        self.assertIn("plugin_events", schema)
        self.assertIn("assistant_turns", schema)
        self.assertIn("ai_behavior_audit", schema)

    def test_prompt_includes_rule_reference(self):
        prompt = build_system_prompt()
        self.assertIn("AI Behavior Audit Rule Reference", prompt)
        self.assertIn("core-2-verify-before-conclusion", prompt)
        self.assertIn("style-no-opening-agreement", prompt)


class TestRuleBasedAudit(unittest.TestCase):
    def _session(self, **overrides):
        base = {
            "session_id": "test-session",
            "assistant_turns": [],
            "tools": {"sequence": []},
            "turns": {"user": 0, "assistant": 0},
        }
        base.update(overrides)
        return base

    def test_detects_zh_banword(self):
        session = self._session(assistant_turns=[
            {"turn": 1, "text": "这个方案可能需要重新调整，抓手是性能。"}
        ])
        audit = run_rule_based_audit(session)
        rule_ids = {row["rule_id"] for row in audit}
        self.assertIn("style-zh-banwords", rule_ids)

    def test_detects_opening_agreement(self):
        session = self._session(assistant_turns=[
            {"turn": 1, "text": "你说得对，我来修改。"}
        ])
        audit = run_rule_based_audit(session)
        self.assertTrue(any(row["rule_id"] == "style-no-opening-agreement" for row in audit))

    def test_detects_en_banword_and_filler(self):
        session = self._session(assistant_turns=[
            {"turn": 1, "text": "Let me utilize this robust approach. Hope this helps!"}
        ])
        audit = run_rule_based_audit(session)
        hit_ids = [row["rule_id"] for row in audit]
        self.assertIn("style-en-banwords", hit_ids)

    def test_detects_read_heavy_session(self):
        session = self._session(
            tools={"sequence": ["Read"] * 6},
            turns={"user": 3, "assistant": 3},
            assistant_turns=[],
        )
        audit = run_rule_based_audit(session)
        self.assertTrue(any(row["rule_id"] == "behavior-no-ask-what-code-can-answer" for row in audit))

    def test_clean_session_produces_no_rows(self):
        session = self._session(
            tools={"sequence": ["Read", "Edit", "Bash"]},
            turns={"user": 2, "assistant": 2},
            assistant_turns=[
                {"turn": 1, "text": "Edited file and ran tests."}
            ],
        )
        audit = run_rule_based_audit(session)
        self.assertEqual(audit, [])


class TestApplyEnrichmentDB(unittest.TestCase):
    def setUp(self):
        self.result = parse_claude_session(str(FIXTURE))
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "sessions.db"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _seed_session_row(self):
        import sessions_db
        original = sessions_db.DB_PATH
        sessions_db.DB_PATH = self.db_path
        try:
            sessions_db.init_db()
            sessions_db.upsert_session(self.result["session_id"], {
                "source": self.result.get("source", "claude-code"),
                "project": "test",
                "analyzer_version": ANALYZER_VERSION,
            })
        finally:
            sessions_db.DB_PATH = original

    def test_apply_enrichment_writes_audit_and_marks_pending(self):
        self._seed_session_row()
        enriched, warning = apply_enrichment(self.result, db_path=self.db_path)
        self.assertIsNone(warning)
        self.assertEqual(enriched["analyzer_version"], ANALYZER_VERSION)
        self.assertEqual(enriched["enrichment_pending"], 1)
        self.assertIsInstance(enriched["ai_behavior_audit"], list)

        conn = sqlite3.connect(self.db_path)
        pending = conn.execute(
            "SELECT enrichment_pending FROM sessions WHERE session_id = ?",
            (enriched["session_id"],),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(pending)
        self.assertEqual(pending[0], 1)

    def test_apply_enrichment_never_spawns_claude_cli(self):
        # Regression guard for architecture C: make sure the module does not
        # import `subprocess` (or at least does not invoke claude CLI).
        import session_enrichment
        src = Path(session_enrichment.__file__).read_text()
        self.assertNotIn("\"claude\"", src)
        self.assertNotIn("'claude'", src)
        self.assertNotIn("subprocess.run", src)


if __name__ == "__main__":
    unittest.main()
