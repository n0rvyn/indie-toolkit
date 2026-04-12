#!/usr/bin/env python3
"""Phase 2 parser tests for plugin_events and assistant_turn audit context."""

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from analyzer_version import ANALYZER_VERSION
from parse_claude_session import parse_claude_session
from parse_codex_session import parse_codex_session

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CLAUDE_PLUGIN_SAMPLE = os.path.join(TEST_DATA_DIR, "claude-plugin-sample.jsonl")
CODEX_SAMPLE = os.path.join(TEST_DATA_DIR, "codex-sample.jsonl")


class TestClaudePluginEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = parse_claude_session(CLAUDE_PLUGIN_SAMPLE)

    def test_plugin_events_extracted(self):
        self.assertEqual(len(self.result["plugin_events"]), 2)

        skill_event = self.result["plugin_events"][0]
        self.assertEqual(skill_event["component_type"], "skill")
        self.assertEqual(skill_event["plugin"], "dev-workflow")
        self.assertEqual(skill_event["component"], "verify-plan")
        self.assertIn("verify-plan", skill_event["input_text"])
        self.assertIn("Verification complete", skill_event["result_text"])

        agent_event = self.result["plugin_events"][1]
        self.assertEqual(agent_event["component_type"], "agent")
        self.assertEqual(agent_event["plugin"], "dev-workflow")
        self.assertEqual(agent_event["component"], "implementation-reviewer")
        self.assertEqual(agent_event["agent_turns_used"], 6)
        self.assertEqual(agent_event["agent_max_turns"], 12)
        self.assertEqual(agent_event["model_override"], "sonnet")

    def test_post_dispatch_signals(self):
        skill_signals = self.result["plugin_events"][0]["post_dispatch_signals"]
        self.assertTrue(skill_signals["user_correction_within_3_turns"])
        self.assertFalse(skill_signals["user_abandoned_topic"])

        agent_signals = self.result["plugin_events"][1]["post_dispatch_signals"]
        self.assertTrue(agent_signals["user_abandoned_topic"])
        self.assertTrue(agent_signals["user_repeated_manually"])
        self.assertFalse(agent_signals["result_adopted"])

    def test_assistant_turns_grouped(self):
        self.assertEqual(len(self.result["assistant_turns"]), 2)
        first_turn = self.result["assistant_turns"][0]
        self.assertEqual(first_turn["turn"], 1)
        self.assertIn("I already fixed it", first_turn["text"])
        self.assertEqual(first_turn["tool_uses"][0]["name"], "Skill")

    def test_analyzer_version_present(self):
        self.assertEqual(self.result["analyzer_version"], ANALYZER_VERSION)

    def test_sqlite_upsert_writes_plugin_events(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "sessions.db")
        try:
            subprocess.run(
                [
                    sys.executable,
                    os.path.join(os.path.dirname(__file__), "..", "scripts", "parse_claude_session.py"),
                    "--input",
                    CLAUDE_PLUGIN_SAMPLE,
                    "--sqlite-db",
                    db_path,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            conn = sqlite3.connect(db_path)
            event_count = conn.execute("SELECT COUNT(*) FROM plugin_events").fetchone()[0]
            version = conn.execute(
                "SELECT analyzer_version FROM sessions WHERE session_id = 'phase2-plugin-001'"
            ).fetchone()[0]
            conn.close()
            self.assertEqual(event_count, 2)
            self.assertEqual(version, ANALYZER_VERSION)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestCodexPhase2Defaults(unittest.TestCase):
    def test_codex_phase2_defaults(self):
        result = parse_codex_session(CODEX_SAMPLE)
        self.assertEqual(result["assistant_turns"], [])
        self.assertEqual(result["plugin_events"], [])
        self.assertEqual(result["ai_behavior_audit"], [])
        self.assertEqual(result["analyzer_version"], ANALYZER_VERSION)

    def test_codex_sqlite_path_is_honored(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "sessions.db")
        try:
            subprocess.run(
                [
                    sys.executable,
                    os.path.join(os.path.dirname(__file__), "..", "scripts", "parse_codex_session.py"),
                    "--input",
                    CODEX_SAMPLE,
                    "--sqlite-db",
                    db_path,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            conn = sqlite3.connect(db_path)
            version = conn.execute(
                "SELECT analyzer_version FROM sessions WHERE session_id = 'test-codex-001'"
            ).fetchone()[0]
            conn.close()
            self.assertEqual(version, ANALYZER_VERSION)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
