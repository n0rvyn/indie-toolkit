#!/usr/bin/env python3
"""
Personal baseline computation using MongoDB aggregation.
Computes rolling statistics per metric using $stdDevPop and $percentile.

Usage:
    python baseline.py [--mongo-uri <uri>] [--database health] [--metric <type>] [--window-days 90]
    python baseline.py --mongo-uri <uri> --database health --metric heart_rate --window-days 90
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import pymongo


def _infer_unit(metric: str) -> str:
    """Infer unit from metric name."""
    unit_map = {
        "heart_rate": "bpm",
        "hrv_sdnn": "ms",
        "vo2max": "mL/kg/min",
        "step_count": "count",
        "distance": "km",
        "distance_cycling": "km",
        "active_energy": "kcal",
        "basal_energy": "kcal",
        "flights_climbed": "count",
        "sleep": "hours",
        "blood_glucose": "mmol/L",
        "bp_sys": "mmHg",
        "bp_dia": "mmHg",
        "spo2": "%",
        "resp_rate": "/min",
        "body_mass": "kg",
        "bmi": "kg/m²",
        "body_fat_pct": "%",
        "water": "L",
        "resting_heart_rate": "bpm",
        "walking_heart_rate_avg": "bpm",
        "exercise_time": "min",
        "stand_time": "min",
        "body_temp": "°C",
        "lean_mass": "kg",
        "calories_consumed": "kcal",
        "protein": "g",
        "carbs": "g",
        "fat_total": "g",
        "fiber": "g",
        "sugar": "g",
        "sodium": "mg",
        "cholesterol": "mg",
    }
    return unit_map.get(metric, "unknown")


def compute_baseline(db, metric: str, window_days: int = 90) -> Optional[dict]:
    """
    Compute baseline statistics for a metric over the rolling window.
    Returns None if fewer than 30 data points are available.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    pipeline = [
        {"$match": {
            "metadata.metric": metric,
            "timestamp": {"$gte": cutoff},
        }},
        {"$group": {
            "_id": None,
            "mean": {"$avg": "$value"},
            "std": {"$stdDevPop": "$value"},
            "min": {"$min": "$value"},
            "max": {"$max": "$value"},
            "count": {"$sum": 1},
            "p25": {"$percentile": {"input": "$value", "p": [0.25], "method": "approximate"}},
            "p75": {"$percentile": {"input": "$value", "p": [0.75], "method": "approximate"}},
        }},
    ]

    results = list(db.metrics.aggregate(pipeline))
    if not results:
        return None

    row = results[0]
    count = row.get("count", 0)
    if count < 30:
        return None

    # Two-phase trend detection: first half vs second half of window
    trend_pipeline = [
        {"$match": {
            "metadata.metric": metric,
            "timestamp": {"$gte": cutoff},
        }},
        {"$sort": {"timestamp": 1}},
        {"$group": {
            "_id": None,
            "values": {"$push": "$value"},
        }},
    ]

    trend_results = list(db.metrics.aggregate(trend_pipeline))
    trend = "stable"
    if trend_results:
        values = trend_results[0].get("values", [])
        n = len(values)
        if n >= 10:
            mid = n // 2
            first_half = values[:mid]
            second_half = values[mid:]
            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)
            if first_avg != 0:
                pct_change = (second_avg - first_avg) / first_avg * 100
                if pct_change > 5:
                    trend = "increasing"
                elif pct_change < -5:
                    trend = "decreasing"

    return {
        "metric": metric,
        "window_days": window_days,
        "data_points": count,
        "mean": round(row["mean"], 4),
        "std": round(row["std"], 4),
        "min": round(row["min"], 4),
        "max": round(row["max"], 4),
        "p25": round(row["p25"][0], 4) if row.get("p25") else None,
        "p75": round(row["p75"][0], 4) if row.get("p75") else None,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "unit": _infer_unit(metric),
        "trend": trend,
    }


def save_baseline(db, baseline_dict: dict) -> None:
    """Insert a baseline document into the baselines collection."""
    doc = dict(baseline_dict)  # copy to avoid _id mutation on original
    db.baselines.insert_one(doc)


def compute_all_baselines(db, window_days: int = 90) -> list[dict]:
    """Discover all distinct metrics and compute a baseline for each."""
    metrics = db.metrics.distinct("metadata.metric")
    results = []
    for metric in sorted(metrics):
        baseline = compute_baseline(db, metric, window_days)
        if baseline:
            results.append(baseline)
    return results


def detect_drift(db, metric: str, new_baseline: dict) -> dict:
    """
    Compare a new baseline against the previous one (if any).
    Flags drift when mean deviation exceeds 10%.
    """
    # Previous baseline: second-most-recent (skip most recent)
    prev = db.baselines.find_one(
        {"metric": metric},
        sort=[("computed_at", pymongo.DESCENDING)],
        skip=1,
    )

    if not prev:
        return {"drift_detected": False, "drift_pct": 0.0, "previous_baseline": None}

    prev_mean = prev.get("mean", 0)
    new_mean = new_baseline.get("mean", 0)
    if prev_mean == 0:
        return {"drift_detected": False, "drift_pct": 0.0, "previous_baseline": prev}

    drift_pct = abs(new_mean - prev_mean) / prev_mean * 100
    return {
        "drift_detected": drift_pct > 10.0,
        "drift_pct": round(drift_pct, 2),
        "previous_baseline": prev,
    }


def main():
    default_uri = os.environ.get("MDB_MCP_CONNECTION_STRING", "")

    parser = argparse.ArgumentParser(description="Baseline computation for health metrics (MongoDB)")
    parser.add_argument("--mongo-uri", default=default_uri, help="MongoDB connection string (default: $MDB_MCP_CONNECTION_STRING)")
    parser.add_argument("--database", default="health", help="MongoDB database name (default: health)")
    parser.add_argument("--metric", help="Compute baseline for a specific metric (default: all metrics)")
    parser.add_argument("--window-days", type=int, default=90, help="Rolling window in days (default: 90)")
    args = parser.parse_args()

    if not args.mongo_uri:
        print("Error: --mongo-uri required or MDB_MCP_CONNECTION_STRING env var must be set", file=sys.stderr)
        sys.exit(1)

    client = pymongo.MongoClient(args.mongo_uri)
    db = client[args.database]

    try:
        if args.metric:
            baseline = compute_baseline(db, args.metric, args.window_days)
            if baseline is None:
                print(json.dumps({"error": f"insufficient data for {args.metric}"}, ensure_ascii=False))
                sys.exit(1)

            # Check for drift
            drift_info = detect_drift(db, args.metric, baseline)
            output = {"baseline": baseline, "drift": drift_info}
            save_baseline(db, baseline)
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            baselines = compute_all_baselines(db, args.window_days)
            for b in baselines:
                save_baseline(db, b)
            print(json.dumps({"baselines_computed": len(baselines), "baselines": baselines}, ensure_ascii=False, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
