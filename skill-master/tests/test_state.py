"""
Tests for state.py — cooldown hash + state file logic.

Run with:
    cd skill-master && python3 -m unittest tests.test_state -v
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


class TestHashCanonical(unittest.TestCase):
    def test_same_inputs_produce_same_hash(self):
        from scripts.state import compute_hash
        h1 = compute_hash("dev-workflow", "verify-plan", "description_update",
                           ["correction_rate", "pattern_summary"])
        h2 = compute_hash("dev-workflow", "verify-plan", "description_update",
                           ["correction_rate", "pattern_summary"])
        self.assertEqual(h1, h2)

    def test_evidence_key_order_does_not_matter(self):
        from scripts.state import compute_hash
        h1 = compute_hash("dev-workflow", "verify-plan", "description_update",
                           ["correction_rate", "pattern_summary"])
        h2 = compute_hash("dev-workflow", "verify-plan", "description_update",
                           ["pattern_summary", "correction_rate"])
        self.assertEqual(h1, h2)

    def test_different_components_produce_different_hash(self):
        from scripts.state import compute_hash
        h1 = compute_hash("dev-workflow", "verify-plan", "description_update", [])
        h2 = compute_hash("dev-workflow", "write-plan", "description_update", [])
        self.assertNotEqual(h1, h2)

    def test_hash_is_hex_string(self):
        from scripts.state import compute_hash
        h = compute_hash("plugin", "comp", "type", ["k1"])
        int(h, 16)  # must parse as hex; raises ValueError otherwise
        self.assertEqual(len(h), 64)  # SHA-256 = 64 hex chars


class TestCooldownSkipsWithinWindow(unittest.TestCase):
    def _make_state_file(self, proposal_hash: str, days_ago: int) -> str:
        ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        data = {"proposals": [{"hash": proposal_hash, "ts": ts}]}
        tmp = tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False
        )
        json.dump(data, tmp)
        tmp.close()
        return tmp.name

    def test_within_window_should_skip(self):
        from scripts.state import is_in_cooldown, compute_hash
        h = compute_hash("dev-workflow", "verify-plan", "description_update", [])
        state_path = self._make_state_file(h, days_ago=7)
        try:
            self.assertTrue(is_in_cooldown(h, window_days=14, state_path=state_path))
        finally:
            os.unlink(state_path)

    def test_day_13_should_skip(self):
        from scripts.state import is_in_cooldown, compute_hash
        h = compute_hash("dev-workflow", "verify-plan", "description_update", [])
        state_path = self._make_state_file(h, days_ago=13)
        try:
            self.assertTrue(is_in_cooldown(h, window_days=14, state_path=state_path))
        finally:
            os.unlink(state_path)

    def test_day_15_should_not_skip(self):
        from scripts.state import is_in_cooldown, compute_hash
        h = compute_hash("dev-workflow", "verify-plan", "description_update", [])
        state_path = self._make_state_file(h, days_ago=15)
        try:
            self.assertFalse(is_in_cooldown(h, window_days=14, state_path=state_path))
        finally:
            os.unlink(state_path)

    def test_unknown_hash_not_in_cooldown(self):
        from scripts.state import is_in_cooldown
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"proposals": []}, f)
            state_path = f.name
        try:
            self.assertFalse(is_in_cooldown("nonexistent_hash", state_path=state_path))
        finally:
            os.unlink(state_path)


class TestStateAtomicWrite(unittest.TestCase):
    def test_record_proposal_writes_correctly(self):
        from scripts.state import record_proposal, load
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            state_path = f.name
        os.unlink(state_path)  # start fresh (no file)
        try:
            record_proposal("abc123", state_path=state_path)
            data = load(state_path)
            self.assertEqual(len(data["proposals"]), 1)
            self.assertEqual(data["proposals"][0]["hash"], "abc123")
        finally:
            if os.path.exists(state_path):
                os.unlink(state_path)

    def test_state_file_not_corrupt_if_no_existing_file(self):
        from scripts.state import load
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = os.path.join(tmpdir, "nonexistent.json")
            data = load(state_path)
            self.assertEqual(data, {"proposals": []})


if __name__ == "__main__":
    unittest.main()
