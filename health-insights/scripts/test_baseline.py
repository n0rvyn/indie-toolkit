#!/usr/bin/env python3
"""Unit tests for baseline.py."""

import math
import tempfile
import os
import sys
import yaml
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from baseline import WelfordStats, compute_baseline, update_baseline, is_leap_year


def test_welford_empty():
    ws = WelfordStats()
    assert ws.count == 0
    assert ws.mean == 0.0
    assert ws.variance == 0.0


def test_welford_single():
    ws = WelfordStats()
    ws.update(10.0)
    assert ws.count == 1
    assert ws.mean == 10.0
    assert ws.variance == 0.0
    assert ws.std == 0.0
    assert ws.min == 10.0
    assert ws.max == 10.0


def test_welford_multiple():
    values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    ws = WelfordStats()
    for v in values:
        ws.update(v)

    assert ws.count == 8
    mean = sum(values) / len(values)
    assert abs(ws.mean - mean) < 1e-9
    # Population std
    expected_std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
    assert abs(ws.std - expected_std) < 1e-9
    assert ws.min == 2.0
    assert ws.max == 9.0


def test_welford_combine():
    ws1 = WelfordStats()
    for v in [1.0, 2.0, 3.0]:
        ws1.update(v)

    ws2 = WelfordStats()
    for v in [4.0, 5.0, 6.0]:
        ws2.update(v)

    combined = ws1.combine(ws2)
    assert combined.count == 6
    assert abs(combined.mean - 3.5) < 1e-9


def test_welford_to_from_dict():
    ws = WelfordStats()
    for v in [10.0, 20.0, 30.0]:
        ws.update(v)

    d = ws.to_dict()
    assert d["count"] == 3
    assert abs(d["mean"] - 20.0) < 1e-9
    assert d["min"] == 10.0
    assert d["max"] == 30.0

    restored = WelfordStats.from_dict(d)
    assert restored.count == 3
    assert abs(restored.mean - 20.0) < 1e-9


def test_is_leap_year():
    assert is_leap_year(2024) == True
    assert is_leap_year(2025) == False
    assert is_leap_year(2026) == False
    assert is_leap_year(2027) == False
    assert is_leap_year(2028) == True
    assert is_leap_year(2000) == True   # divisible by 400
    assert is_leap_year(1900) == False  # divisible by 100 but not 400


def test_update_baseline():
    existing = {
        "metric": "heart_rate",
        "stats": {
            "count": 30,
            "mean": 65.0,
            "std": 8.0,
            "min": 52.0,
            "max": 78.0,
        },
        "computed_at": "2026-01-01T00:00:00",
        "data_points": 30,
    }
    new_values = [60.0, 62.0, 58.0, 63.0]

    updated = update_baseline(existing, new_values)
    assert updated["stats"]["count"] == 34
    assert updated["data_points"] == 34
    assert abs(updated["stats"]["mean"] - 64.5) < 0.01


def test_compute_baseline_insufficient_data():
    """Test that baseline returns None when fewer than 30 data points."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = Path(tmpdir)
        daily_dir = vault_dir / "daily"
        daily_dir.mkdir()

        # Create a date dir with a metric file with only 10 records
        date_dir = daily_dir / "2026-04-09"
        date_dir.mkdir()
        metric_file = date_dir / "heart_rate.yaml"

        records = [{"value": str(i * 5), "unit": "bpm"} for i in range(10)]
        with open(metric_file, "w") as f:
            yaml.dump({"type": "daily", "date": "2026-04-09", "records": records}, f)

        result = compute_baseline(vault_dir, "heart_rate", window_days=365)
        assert result is None, "Should return None when < 30 data points"


if __name__ == "__main__":
    test_welford_empty()
    test_welford_single()
    test_welford_multiple()
    test_welford_combine()
    test_welford_to_from_dict()
    test_is_leap_year()
    test_update_baseline()
    test_compute_baseline_insufficient_data()
    print("All tests passed.")
