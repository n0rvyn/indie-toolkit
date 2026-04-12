#!/usr/bin/env python3
"""Unit tests for baseline.py (MongoDB-backed)."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from baseline import _infer_unit, compute_baseline, detect_drift


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def make_mock_cursor(rows):
    """Wrap a list of dicts as a mock pymongo cursor that iterates."""
    cursor = MagicMock()
    cursor.__iter__ = lambda self: iter(rows)
    return cursor


def mock_db(agg_results_by_pipeline):
    """
    Build a mock db whose aggregate() returns canned results per pipeline.

    agg_results_by_pipeline: list of (pipeline_template, result_rows)
    For simplicity, we match on the first pipeline command's collection
    and return the associated rows.
    """
    db = MagicMock()

    def aggregate_side_effect(pipeline):
        # Return canned results based on pipeline structure
        # We look for the $match stage to determine which result set
        for stage in pipeline:
            if "$match" in stage:
                match = stage["$match"]
                # Determine metric from match filter
                metric_filter = match.get("metadata.metric")
                if metric_filter == "heart_rate":
                    return make_mock_cursor(agg_results_by_pipeline.get("heart_rate", []))
                elif metric_filter == "hrv_sdnn":
                    return make_mock_cursor(agg_results_by_pipeline.get("hrv_sdnn", []))
                elif metric_filter == "empty_metric":
                    return make_mock_cursor([])
        # Default: return empty
        return make_mock_cursor([])

    metrics_col = MagicMock()
    metrics_col.aggregate = aggregate_side_effect
    metrics_col.distinct = MagicMock(return_value=["heart_rate", "hrv_sdnn", "blood_glucose"])

    baselines_col = MagicMock()
    baselines_col.find_one = MagicMock(return_value=None)

    db.metrics = metrics_col
    db.baselines = baselines_col
    return db


# -------------------------------------------------------------------
# Tests for _infer_unit
# -------------------------------------------------------------------

def test_infer_unit_known_metrics():
    assert _infer_unit("heart_rate") == "bpm"
    assert _infer_unit("hrv_sdnn") == "ms"
    assert _infer_unit("vo2max") == "mL/kg/min"
    assert _infer_unit("step_count") == "count"
    assert _infer_unit("distance") == "km"
    assert _infer_unit("active_energy") == "kcal"
    assert _infer_unit("sleep") == "hours"
    assert _infer_unit("blood_glucose") == "mmol/L"
    assert _infer_unit("bp_sys") == "mmHg"
    assert _infer_unit("spo2") == "%"
    assert _infer_unit("body_mass") == "kg"
    assert _infer_unit("bmi") == "kg/m²"
    assert _infer_unit("resting_heart_rate") == "bpm"
    assert _infer_unit("exercise_time") == "min"
    assert _infer_unit("body_temp") == "°C"


def test_infer_unit_unknown_metric():
    assert _infer_unit("unknown_metric") == "unknown"
    assert _infer_unit("") == "unknown"


# -------------------------------------------------------------------
# Tests for compute_baseline
# -------------------------------------------------------------------

def test_compute_baseline_returns_correct_stats():
    """Aggregation returns stats -> correct baseline dict."""
    agg_results = {
        "heart_rate": [
            {"_id": None, "mean": 63.5, "std": 8.2, "min": 48.0, "max": 85.0, "count": 90},
        ],
        # Trend detection needs a second aggregate call
    }
    db = mock_db(agg_results)

    # Patch trend detection to avoid second aggregate complexity
    with patch.object(db.metrics, "aggregate") as mock_agg:
        # First call = stats pipeline, second = trend pipeline
        stats_row = {"_id": None, "mean": 63.5, "std": 8.2, "min": 48.0, "max": 85.0, "count": 90}
        # Return same for both calls (trend will detect stable with identical means)
        mock_agg.side_effect = [
            make_mock_cursor([stats_row]),
            make_mock_cursor([{"_id": None, "values": [60.0] * 50 + [60.0] * 50}]),
        ]

        result = compute_baseline(db, "heart_rate", window_days=90)

        assert result is not None
        assert result["metric"] == "heart_rate"
        assert result["mean"] == 63.5
        assert result["std"] == 8.2
        assert result["min"] == 48.0
        assert result["max"] == 85.0
        assert result["data_points"] == 90
        assert result["unit"] == "bpm"
        assert result["window_days"] == 90
        assert "computed_at" in result


def test_compute_baseline_insufficient_data():
    """Fewer than 30 records -> returns None."""
    agg_results = {
        "heart_rate": [
            {"_id": None, "mean": 63.5, "std": 8.2, "min": 48.0, "max": 85.0, "count": 20},
        ],
    }
    db = mock_db(agg_results)

    result = compute_baseline(db, "heart_rate")
    assert result is None


def test_compute_baseline_no_data():
    """No aggregation results -> returns None."""
    agg_results = {"heart_rate": []}
    db = mock_db(agg_results)

    result = compute_baseline(db, "heart_rate")
    assert result is None


def test_compute_baseline_trend_increasing():
    """First half mean < second half -> trend = increasing."""
    agg_results = {"hrv_sdnn": []}
    db = mock_db(agg_results)

    with patch.object(db.metrics, "aggregate") as mock_agg:
        stats_row = {"_id": None, "mean": 50.0, "std": 5.0, "min": 35.0, "max": 70.0, "count": 90}
        # First half: mean=40, second half: mean=60 -> increasing
        values = [40.0] * 50 + [60.0] * 50
        mock_agg.side_effect = [
            make_mock_cursor([stats_row]),
            make_mock_cursor([{"_id": None, "values": values}]),
        ]

        result = compute_baseline(db, "hrv_sdnn", window_days=90)
        assert result is not None
        assert result["trend"] == "increasing"


def test_compute_baseline_trend_decreasing():
    """First half mean > second half -> trend = decreasing."""
    agg_results = {"hrv_sdnn": []}
    db = mock_db(agg_results)

    with patch.object(db.metrics, "aggregate") as mock_agg:
        stats_row = {"_id": None, "mean": 50.0, "std": 5.0, "min": 35.0, "max": 70.0, "count": 90}
        values = [60.0] * 50 + [40.0] * 50
        mock_agg.side_effect = [
            make_mock_cursor([stats_row]),
            make_mock_cursor([{"_id": None, "values": values}]),
        ]

        result = compute_baseline(db, "hrv_sdnn", window_days=90)
        assert result is not None
        assert result["trend"] == "decreasing"


def test_compute_baseline_trend_stable():
    """No significant change -> trend = stable."""
    agg_results = {"hrv_sdnn": []}
    db = mock_db(agg_results)

    with patch.object(db.metrics, "aggregate") as mock_agg:
        stats_row = {"_id": None, "mean": 50.0, "std": 5.0, "min": 35.0, "max": 70.0, "count": 90}
        values = [50.0] * 100
        mock_agg.side_effect = [
            make_mock_cursor([stats_row]),
            make_mock_cursor([{"_id": None, "values": values}]),
        ]

        result = compute_baseline(db, "hrv_sdnn", window_days=90)
        assert result is not None
        assert result["trend"] == "stable"


def test_compute_all_baselines():
    """Discovers 3 metrics -> computes 3 baselines."""
    db = mock_db({})

    with patch.object(db.metrics, "aggregate") as mock_agg:
        mock_agg.side_effect = [
            make_mock_cursor([{"_id": None, "mean": 63.0, "std": 8.0, "min": 48.0, "max": 85.0, "count": 90}]),
            make_mock_cursor([{"_id": None, "values": [60.0] * 100}]),
            make_mock_cursor([{"_id": None, "mean": 50.0, "std": 5.0, "min": 35.0, "max": 70.0, "count": 90}]),
            make_mock_cursor([{"_id": None, "values": [50.0] * 100}]),
            make_mock_cursor([{"_id": None, "mean": 5.5, "std": 0.5, "min": 4.0, "max": 7.0, "count": 90}]),
            make_mock_cursor([{"_id": None, "values": [5.5] * 100}]),
        ]

        from baseline import compute_all_baselines
        results = compute_all_baselines(db, window_days=90)

        assert len(results) == 3
        metrics_found = {r["metric"] for r in results}
        assert metrics_found == {"heart_rate", "hrv_sdnn", "blood_glucose"}


# -------------------------------------------------------------------
# Tests for detect_drift
# -------------------------------------------------------------------

def test_detect_drift_no_previous():
    """No previous baseline -> no drift."""
    db = mock_db({})
    db.baselines.find_one = MagicMock(return_value=None)

    new_baseline = {"metric": "heart_rate", "mean": 63.0}
    result = detect_drift(db, "heart_rate", new_baseline)

    assert result["drift_detected"] is False
    assert result["drift_pct"] == 0.0
    assert result["previous_baseline"] is None


def test_detect_drift_small_change():
    """Mean shift < 10% -> no drift."""
    prev = {"metric": "heart_rate", "mean": 60.0, "computed_at": "2026-01-01T00:00:00+00:00"}
    db = mock_db({})
    db.baselines.find_one = MagicMock(return_value=prev)

    new_baseline = {"metric": "heart_rate", "mean": 63.0}  # +5%
    result = detect_drift(db, "heart_rate", new_baseline)

    assert result["drift_detected"] is False
    assert result["drift_pct"] == 5.0


def test_detect_drift_large_change():
    """Mean shift > 10% -> drift detected."""
    prev = {"metric": "heart_rate", "mean": 60.0, "computed_at": "2026-01-01T00:00:00+00:00"}
    db = mock_db({})
    db.baselines.find_one = MagicMock(return_value=prev)

    new_baseline = {"metric": "heart_rate", "mean": 72.0}  # +20%
    result = detect_drift(db, "heart_rate", new_baseline)

    assert result["drift_detected"] is True
    assert result["drift_pct"] == 20.0
    assert result["previous_baseline"] == prev


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

if __name__ == "__main__":
    test_infer_unit_known_metrics()
    test_infer_unit_unknown_metric()
    test_compute_baseline_returns_correct_stats()
    test_compute_baseline_insufficient_data()
    test_compute_baseline_no_data()
    test_compute_baseline_trend_increasing()
    test_compute_baseline_trend_decreasing()
    test_compute_baseline_trend_stable()
    test_compute_all_baselines()
    test_detect_drift_no_previous()
    test_detect_drift_small_change()
    test_detect_drift_large_change()
    print("All baseline tests passed.")
