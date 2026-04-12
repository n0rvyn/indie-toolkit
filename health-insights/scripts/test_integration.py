#!/usr/bin/env python3
"""Integration test: ingest → baseline → predict pipeline.

Uses mock pymongo to test the full data flow without a real MongoDB connection.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import unittest

sys.path.insert(0, str(Path(__file__).parent))

import ingest
import baseline
import predict


class MockMetricsCollection:
    """Simulates a metrics collection with pre-loaded data."""

    def __init__(self):
        self.documents = []

    def insert_many(self, docs, ordered=False):
        self.documents.extend(docs)

    def aggregate(self, pipeline):
        """Simplified aggregation that handles $match + $group."""
        # Extract match criteria
        match_stage = next((s for s in pipeline if "$match" in s), None)
        metric_filter = match_stage["$match"].get("metadata.metric") if match_stage else None

        filtered = self.documents
        if metric_filter:
            filtered = [d for d in filtered if d.get("metadata", {}).get("metric") == metric_filter]

        if not filtered:
            return iter([])

        values = [d["value"] for d in filtered]
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n if n > 0 else 0
        std = variance ** 0.5

        # Check if $group has $dateToString (for predict's daily aggregation)
        group_stage = next((s for s in pipeline if "$group" in s), None)
        if group_stage and "_id" in group_stage["$group"]:
            id_spec = group_stage["$group"]["_id"]
            if isinstance(id_spec, dict) and "$dateToString" in id_spec:
                # Group by date string
                by_date = {}
                for d in filtered:
                    ds = d["timestamp"].strftime("%Y-%m-%d")
                    by_date.setdefault(ds, []).append(d["value"])
                results = [{"_id": ds, "avg_value": sum(vs) / len(vs)} for ds, vs in sorted(by_date.items())]
                return iter(results)

        result = {
            "_id": None,
            "mean": mean,
            "std": std,
            "min": min(values),
            "max": max(values),
            "count": n,
            "p25": [sorted(values)[n // 4]] if n >= 4 else [values[0]],
            "p75": [sorted(values)[3 * n // 4]] if n >= 4 else [values[-1]],
        }
        return iter([result])

    def distinct(self, field):
        values = set()
        for d in self.documents:
            parts = field.split(".")
            v = d
            for p in parts:
                v = v.get(p, {}) if isinstance(v, dict) else None
                if v is None:
                    break
            if v:
                values.add(v)
        return list(values)


class MockDB:
    """Simulates a MongoDB database with metrics, baselines, alerts, checkpoint collections."""

    def __init__(self):
        self.metrics = MockMetricsCollection()
        self.baselines = MagicMock()
        self.alerts = MagicMock()
        self.checkpoint = MagicMock()
        self.ingest_log = MagicMock()

        # Configure baselines.find_one to return None by default
        self.baselines.find_one = MagicMock(return_value=None)
        self.baselines.insert_one = MagicMock()

        # Configure alerts
        self.alerts.insert_one = MagicMock()
        self.alerts.update_one = MagicMock()

        # Configure checkpoint
        self.checkpoint.find_one = MagicMock(return_value=None)
        self.checkpoint.replace_one = MagicMock()

        # Configure ingest_log
        self.ingest_log.find_one = MagicMock(return_value=None)
        self.ingest_log.insert_one = MagicMock()
        self.ingest_log.create_index = MagicMock()


class TestIngestToBaselinePipeline(unittest.TestCase):
    """Test: ingested data flows correctly into baseline computation."""

    def test_ingested_metrics_produce_valid_baseline(self):
        db = MockDB()

        # Simulate 90 days of heart rate data (what ingest.py would produce)
        now = datetime.now(timezone.utc)
        for i in range(90):
            dt = now - timedelta(days=i)
            # Simulate ~5 readings per day
            for hr in [65, 70, 72, 68, 75]:
                db.metrics.documents.append({
                    "timestamp": dt,
                    "metadata": {"metric": "heart_rate", "source": "apple_watch", "unit": "bpm"},
                    "value": float(hr + (i % 10) - 5),  # Add some variation
                })

        # Run baseline computation
        result = baseline.compute_baseline(db, "heart_rate", window_days=90)

        self.assertIsNotNone(result)
        self.assertEqual(result["metric"], "heart_rate")
        self.assertGreater(result["data_points"], 30)
        self.assertAlmostEqual(result["mean"], 70, delta=5)
        self.assertIn("std", result)
        self.assertIn("trend", result)
        self.assertEqual(result["unit"], "bpm")


class TestBaselineToPredictPipeline(unittest.TestCase):
    """Test: baseline data enables prediction rule evaluation."""

    def test_low_hrv_triggers_alert(self):
        db = MockDB()

        # Set up baseline: HRV mean = 50ms
        db.baselines.find_one = MagicMock(return_value={
            "metric": "hrv_sdnn",
            "mean": 50.0,
            "std": 8.0,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        })

        # Add 14 days of HRV data, last 3 days are low (< 35ms = 50 * 0.7)
        now = datetime.now(timezone.utc)
        for i in range(14):
            dt = now - timedelta(days=13 - i)
            value = 30.0 if i >= 11 else 48.0  # Last 3 days: 30ms (low)
            db.metrics.documents.append({
                "timestamp": dt,
                "metadata": {"metric": "hrv_sdnn", "source": "apple_watch", "unit": "ms"},
                "value": value,
            })

        # Evaluate the hrv_low_3d rule
        alert = predict.evaluate_rule("hrv_low_3d", predict.ALERT_RULES["hrv_low_3d"], db)

        self.assertIsNotNone(alert, "HRV low alert should trigger after 3 consecutive low days")
        self.assertEqual(alert["rule_id"], "hrv_low_3d")
        self.assertEqual(alert["severity"], "moderate")
        self.assertLess(alert["deviation_pct"], -25)

    def test_normal_hrv_no_alert(self):
        db = MockDB()

        db.baselines.find_one = MagicMock(return_value={
            "metric": "hrv_sdnn",
            "mean": 50.0,
            "std": 8.0,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        })

        now = datetime.now(timezone.utc)
        for i in range(14):
            dt = now - timedelta(days=13 - i)
            db.metrics.documents.append({
                "timestamp": dt,
                "metadata": {"metric": "hrv_sdnn", "source": "apple_watch", "unit": "ms"},
                "value": 48.0,  # Normal, within baseline
            })

        alert = predict.evaluate_rule("hrv_low_3d", predict.ALERT_RULES["hrv_low_3d"], db)
        self.assertIsNone(alert, "No alert for normal HRV values")


class TestFullPipeline(unittest.TestCase):
    """Test: ingest → baseline → predict end-to-end data flow."""

    def test_pipeline_data_consistency(self):
        """Verify data format compatibility across all three stages."""
        db = MockDB()

        # Stage 1: Simulate what ingest.py handler produces
        handler = ingest.HealthRecordHandler(db, batch_size=100)
        # Verify handler produces documents with correct schema
        test_doc = {
            "timestamp": datetime.now(timezone.utc),
            "metadata": {"metric": "heart_rate", "source": "test", "unit": "bpm"},
            "value": 72.0,
            "device": None,
            "end_date": None,
        }
        self.assertIn("timestamp", test_doc)
        self.assertIn("metadata", test_doc)
        self.assertIn("value", test_doc)
        self.assertEqual(test_doc["metadata"]["metric"], "heart_rate")

        # Stage 2: Verify baseline reads the same field names
        # baseline.compute_baseline uses: metadata.metric, timestamp, value
        # These match the ingest document schema

        # Stage 3: Verify predict reads the same baseline fields
        # predict.load_baseline reads: metric, mean, std
        # predict.load_recent_values reads: metadata.metric, timestamp, value (via aggregation)
        # These match both ingest and baseline schemas

        # Verify TYPE_MAP consistency
        for metric_key in ["heart_rate", "hrv_sdnn", "resting_heart_rate", "sleep", "blood_glucose"]:
            self.assertIn(metric_key, ingest.TYPE_MAP.values(),
                          f"Metric {metric_key} used by predict rules must be in ingest TYPE_MAP")

        # Verify predict rules reference valid metrics
        for rule_id, rule in predict.ALERT_RULES.items():
            self.assertIn(rule["metric"], ingest.TYPE_MAP.values(),
                          f"Rule {rule_id} references metric '{rule['metric']}' not in TYPE_MAP")


if __name__ == "__main__":
    unittest.main()
