#!/usr/bin/env python3
"""Phase 3 tests for cross-session linking."""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import backfill
import sessions_db
from link_sessions import build_links, recompute_session_links

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "linking-chains.yaml"


def _insert_session(conn, row):
    conn.execute("""
        INSERT INTO sessions (
            session_id, source, project, project_path, branch, model,
            time_start, time_end, duration_min, turns_user, turns_asst,
            tokens_in, tokens_out, cache_read, cache_create, cache_hit_rate,
            analyzer_version, session_dna, task_summary, analyzed_at, outcome
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        row["session_id"],
        "claude-code",
        row["project"],
        f"/tmp/{row['project']}",
        row["branch"],
        "claude-opus-4-6",
        row["time_start"],
        row["time_end"],
        30.0,
        1,
        1,
        100,
        50,
        0,
        0,
        0.0,
        "2026-04-12-phase2",
        "build",
        row["task_summary"],
        row["time_end"],
        row["outcome"],
    ))
    for idx, tool_name in enumerate(row["tools"]):
        conn.execute("""
            INSERT INTO tool_calls (session_id, seq_idx, tool_name, file_path, is_error)
            VALUES (?, ?, ?, ?, 0)
        """, (row["session_id"], idx, tool_name, None))


class TestPhase3SessionLinks(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "sessions.db")
        self.original_db_path = sessions_db.DB_PATH
        sessions_db.set_db_path(self.db_path)
        sessions_db.init_db()
        with open(FIXTURE_PATH, "r", encoding="utf-8") as handle:
            self.fixture = json.load(handle)
        conn = sqlite3.connect(self.db_path)
        for row in self.fixture["sessions"]:
            _insert_session(conn, row)
        conn.commit()
        conn.close()

    def tearDown(self):
        sessions_db.set_db_path(self.original_db_path)
        self.tmpdir.cleanup()

    def test_bm25_builds_expected_links_without_false_links(self):
        rows = sessions_db.get_sessions_for_linking()
        tool_sequences = sessions_db.get_tool_sequences([row["session_id"] for row in rows])
        links = build_links(rows, tool_sequences)
        source_targets = {(link["source_session_id"], link["target_session_id"]) for link in links}

        self.assertIn(("fixture-chain-001", "fixture-chain-002"), source_targets)
        self.assertIn(("fixture-chain-002", "fixture-chain-003"), source_targets)
        self.assertNotIn(("fixture-chain-001", "fixture-noise-001"), source_targets)
        self.assertNotIn(("fixture-chain-101", "fixture-gap-001"), source_targets)

    def test_recompute_session_links_meets_fixture_chain_coverage(self):
        recompute_session_links(db_path=self.db_path)
        for chain in self.fixture["chains"]:
            trace_rows = sessions_db.get_task_trace(chain["anchor"])
            predicted = {row["session_id"] for row in trace_rows}
            expected = set(chain["expected"])
            coverage = len(predicted & expected) / len(expected)
            self.assertGreaterEqual(coverage, 0.8)
            self.assertTrue(predicted.issubset(expected))

    def test_incremental_recompute_reloads_neighbor_sources(self):
        summary = recompute_session_links(
            target_session_ids=["fixture-chain-003"],
            db_path=self.db_path,
        )
        self.assertGreaterEqual(summary["source_sessions"], 4)

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT source_session_id, target_session_id
            FROM session_links
            WHERE source_session_id IN ('fixture-chain-001', 'fixture-chain-002')
            ORDER BY source_session_id
        """).fetchall()
        conn.close()

        self.assertEqual(
            rows,
            [
                ("fixture-chain-001", "fixture-chain-002"),
                ("fixture-chain-002", "fixture-chain-003"),
            ],
        )

    def test_backfill_main_populates_session_links(self):
        fixture_map = {row["session_id"]: row for row in self.fixture["sessions"]}
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM session_links")
        conn.execute("DELETE FROM tool_calls")
        conn.execute("DELETE FROM sessions")
        conn.commit()
        conn.close()

        def fake_parse_one(session_meta):
            conn = sqlite3.connect(self.db_path)
            _insert_session(conn, fixture_map[session_meta["session_id"]])
            conn.commit()
            conn.close()
            return True, None

        session_metas = [
            {"session_id": row["session_id"], "source": "claude-code", "file_path": f"/tmp/{row['session_id']}.jsonl"}
            for row in self.fixture["sessions"]
        ]

        with mock.patch.object(backfill, "discover_all", return_value=session_metas), \
             mock.patch.object(backfill, "filter_to_pending", return_value=session_metas), \
             mock.patch.object(backfill, "parse_one", side_effect=fake_parse_one):
            backfill.sessions_db.set_db_path(self.db_path)
            argv = ["backfill.py", "--days", "365"]
            with mock.patch.object(sys, "argv", argv):
                backfill.main()

        trace_rows = sessions_db.get_task_trace("fixture-chain-002")
        self.assertEqual(
            [row["session_id"] for row in trace_rows],
            ["fixture-chain-001", "fixture-chain-002", "fixture-chain-003"],
        )


if __name__ == "__main__":
    unittest.main()
