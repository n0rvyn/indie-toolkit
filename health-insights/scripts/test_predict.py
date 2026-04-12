#!/usr/bin/env python3
"""Unit tests for predict.py."""

import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import pymongo
import predict


class MockCollection:
    """In-memory mock of pymongo.collection.Collection."""

    def __init__(self, docs=None):
        self._docs = docs if docs is not None else []

    def find_one(self, filter_dict, sort=None, skip=None):
        docs = list(self._docs)
        if sort:
            # Simple mock: sort by the sort key (direction ignored for single-key)
            key, direction = sort[0]
            docs.sort(key=lambda d: d.get(key) or "", reverse=(direction == pymongo.DESCENDING))
        if skip:
            docs = docs[skip:]
        for doc in docs:
            if all(doc.get(k) == v for k, v in filter_dict.items()):
                return doc
        return None

    def insert_one(self, doc):
        self._docs.append(doc)
        return MagicMock(inserted_id=len(self._docs) - 1)

    def update_one(self, filter_dict, update):
        for doc in self._docs:
            if all(doc.get(k) == v for k, v in filter_dict.items()):
                if "$set" in update:
                    doc.update(update["$set"])
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)

    def aggregate(self, pipeline):
        """Simple mock of aggregation for load_recent_values pattern."""
        # Find the $match stage
        match_stage = next((s for s in pipeline if "$match" in s), None)
        filter_docs = self._docs
        if match_stage:
            for doc in self._docs:
                for field, condition in match_stage["$match"].items():
                    if field == "metadata.metric" and isinstance(condition, dict) and "$gte" in condition:
                        filter_docs = self._docs  # simplified: return all
        # Find $group stage
        group_stage = next((s for s in pipeline if "$group" in s), None)
        if group_stage:
            group_def = group_stage["$group"]
            if "_id" in group_def and "$dateToString" in group_def["_id"]:
                # Daily grouping: group by date string
                date_format = group_def["_id"]["$dateToString"]["format"]
                buckets = {}
                for doc in self._docs:
                    ts = doc.get("timestamp")
                    if ts:
                        if date_format == "%Y-%m-%d":
                            key = ts.strftime("%Y-%m-%d")
                        else:
                            key = str(ts)
                        if key not in buckets:
                            buckets[key] = []
                        buckets[key].append(doc.get("value", 0))
                result = [{"_id": k, "avg_value": sum(v) / len(v)} for k, v in sorted(buckets.items())]
                return result
        return []


class MockDb:
    """In-memory mock of pymongo database."""

    def __init__(self):
        self._collections: dict[str, MockCollection] = {}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = MockCollection()
        return self._collections[name]

    def __getattr__(self, name):
        return self[name]


class TestEvaluateRuleDeviationBelowPct(unittest.TestCase):
    """Tests for deviation_below_pct condition."""

    def _make_baseline(self, mean=60.0):
        return {"metric": "hrv_sdnn", "mean": mean}

    def _make_values(self, days_and_vals):
        """days_and_vals: list of (date_str, avg_value)."""
        return days_and_vals

    def test_triggers_when_3_consecutive_days_below(self):
        """3 consecutive days below threshold → alert triggered."""
        mock_db = MockDb()
        mock_db.baselines._docs = [self._make_baseline(mean=60.0)]
        # 3 days below 42 (30% below 60), then above
        mock_db.metrics._docs = [
            {"metadata": {"metric": "hrv_sdnn"}, "timestamp": datetime(2026, 4, 7, tzinfo=timezone.utc), "value": 35.0},
            {"metadata": {"metric": "hrv_sdnn"}, "timestamp": datetime(2026, 4, 8, tzinfo=timezone.utc), "value": 38.0},
            {"metadata": {"metric": "hrv_sdnn"}, "timestamp": datetime(2026, 4, 9, tzinfo=timezone.utc), "value": 40.0},
            {"metadata": {"metric": "hrv_sdnn"}, "timestamp": datetime(2026, 4, 10, tzinfo=timezone.utc), "value": 55.0},  # above threshold
        ]

        rule = predict.ALERT_RULES["hrv_low_3d"]
        alert = predict.evaluate_rule("hrv_low_3d", rule, mock_db)

        self.assertIsNotNone(alert)
        self.assertEqual(alert["rule_id"], "hrv_low_3d")
        self.assertEqual(alert["severity"], "moderate")
        self.assertGreaterEqual(alert["days_above_threshold"], 3)

    def test_no_alert_when_only_2_consecutive_days_below(self):
        """2 consecutive days below, then 1 above → reset, no alert."""
        mock_db = MockDb()
        mock_db.baselines._docs = [self._make_baseline(mean=60.0)]
        mock_db.metrics._docs = [
            {"metadata": {"metric": "hrv_sdnn"}, "timestamp": datetime(2026, 4, 7, tzinfo=timezone.utc), "value": 35.0},
            {"metadata": {"metric": "hrv_sdnn"}, "timestamp": datetime(2026, 4, 8, tzinfo=timezone.utc), "value": 38.0},
            {"metadata": {"metric": "hrv_sdnn"}, "timestamp": datetime(2026, 4, 9, tzinfo=timezone.utc), "value": 55.0},  # above threshold → reset
            {"metadata": {"metric": "hrv_sdnn"}, "timestamp": datetime(2026, 4, 10, tzinfo=timezone.utc), "value": 36.0},  # new sequence: only 1 day
            {"metadata": {"metric": "hrv_sdnn"}, "timestamp": datetime(2026, 4, 11, tzinfo=timezone.utc), "value": 37.0},  # 2nd day
        ]

        rule = predict.ALERT_RULES["hrv_low_3d"]
        alert = predict.evaluate_rule("hrv_low_3d", rule, mock_db)

        self.assertIsNone(alert)


class TestEvaluateRuleBelowValue(unittest.TestCase):
    """Tests for below_value condition (sleep debt rule)."""

    def test_triggers_when_sleep_below_6h_for_5_days(self):
        mock_db = MockDb()
        mock_db.baselines._docs = [{"metric": "sleep", "mean": 7.5}]
        # 5 days of low sleep
        mock_db.metrics._docs = [
            {"metadata": {"metric": "sleep"}, "timestamp": datetime(2026, 4, 5, tzinfo=timezone.utc), "value": 5.5},
            {"metadata": {"metric": "sleep"}, "timestamp": datetime(2026, 4, 6, tzinfo=timezone.utc), "value": 5.2},
            {"metadata": {"metric": "sleep"}, "timestamp": datetime(2026, 4, 7, tzinfo=timezone.utc), "value": 5.8},
            {"metadata": {"metric": "sleep"}, "timestamp": datetime(2026, 4, 8, tzinfo=timezone.utc), "value": 5.0},
            {"metadata": {"metric": "sleep"}, "timestamp": datetime(2026, 4, 9, tzinfo=timezone.utc), "value": 4.9},
        ]

        rule = predict.ALERT_RULES["sleep_debt_5d"]
        alert = predict.evaluate_rule("sleep_debt_5d", rule, mock_db)

        self.assertIsNotNone(alert)
        self.assertEqual(alert["rule_id"], "sleep_debt_5d")
        self.assertEqual(alert["severity"], "mild")
        self.assertGreaterEqual(alert["days_above_threshold"], 5)


class TestEvaluateRuleAboveValue(unittest.TestCase):
    """Tests for above_value condition (blood glucose rule)."""

    def test_triggers_when_glucose_above_11_for_3_days(self):
        mock_db = MockDb()
        mock_db.baselines._docs = [{"metric": "blood_glucose", "mean": 5.5}]
        mock_db.metrics._docs = [
            {"metadata": {"metric": "blood_glucose"}, "timestamp": datetime(2026, 4, 7, tzinfo=timezone.utc), "value": 11.5},
            {"metadata": {"metric": "blood_glucose"}, "timestamp": datetime(2026, 4, 8, tzinfo=timezone.utc), "value": 12.1},
            {"metadata": {"metric": "blood_glucose"}, "timestamp": datetime(2026, 4, 9, tzinfo=timezone.utc), "value": 11.8},
            {"metadata": {"metric": "blood_glucose"}, "timestamp": datetime(2026, 4, 10, tzinfo=timezone.utc), "value": 9.0},  # reset
        ]

        rule = predict.ALERT_RULES["blood_glucose_high"]
        alert = predict.evaluate_rule("blood_glucose_high", rule, mock_db)

        self.assertIsNotNone(alert)
        self.assertEqual(alert["rule_id"], "blood_glucose_high")
        self.assertEqual(alert["severity"], "severe")


class TestEvaluateAllRules(unittest.TestCase):
    """Tests for evaluate_all_rules()."""

    def test_4_rules_1_triggers_returns_1_alert(self):
        mock_db = MockDb()
        # Only baseline for hrv_sdnn (others missing → skipped)
        mock_db.baselines._docs = [{"metric": "hrv_sdnn", "mean": 60.0}]
        # 3 days below threshold for hrv
        mock_db.metrics._docs = [
            {"metadata": {"metric": "hrv_sdnn"}, "timestamp": datetime(2026, 4, 7, tzinfo=timezone.utc), "value": 35.0},
            {"metadata": {"metric": "hrv_sdnn"}, "timestamp": datetime(2026, 4, 8, tzinfo=timezone.utc), "value": 38.0},
            {"metadata": {"metric": "hrv_sdnn"}, "timestamp": datetime(2026, 4, 9, tzinfo=timezone.utc), "value": 40.0},
        ]

        alerts = predict.evaluate_all_rules(mock_db)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["rule_id"], "hrv_low_3d")


class TestSaveAlert(unittest.TestCase):
    """Tests for save_alert()."""

    def test_inserts_document_with_correct_fields(self):
        mock_db = MockDb()
        alert = {
            "id": "hrv_low_3d_20260409",
            "rule_id": "hrv_low_3d",
            "severity": "moderate",
            "metric": "hrv_sdnn",
            "current": 38.0,
            "baseline": 60.0,
            "status": "active",
        }

        predict.save_alert(mock_db, alert)

        self.assertEqual(len(mock_db.alerts._docs), 1)
        saved = mock_db.alerts._docs[0]
        self.assertEqual(saved["id"], "hrv_low_3d_20260409")
        self.assertEqual(saved["status"], "active")


class TestAcknowledgeAlert(unittest.TestCase):
    """Tests for acknowledge_alert()."""

    def test_updates_status_to_acknowledged(self):
        mock_db = MockDb()
        # Pre-populate an alert
        mock_db.alerts._docs = [
            {"_id": 0, "id": "hrv_low_3d_20260409", "status": "active"},
            {"_id": 1, "id": "sleep_debt_5d_20260409", "status": "active"},
        ]

        predict.acknowledge_alert(mock_db, 0)

        self.assertEqual(mock_db.alerts._docs[0]["status"], "acknowledged")
        self.assertIn("acknowledged_at", mock_db.alerts._docs[0])
        # Second alert unchanged
        self.assertEqual(mock_db.alerts._docs[1]["status"], "active")


if __name__ == "__main__":
    unittest.main()
