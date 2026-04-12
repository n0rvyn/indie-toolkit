#!/usr/bin/env python3
"""
Rule-based early warning engine for health alerts.
Evaluates recent data against personal baselines and writes alerts to MongoDB.

Usage:
    python predict.py --evaluate [--mongo-uri <uri>] [--database health] [--rules <rule_ids>]
    python predict.py --acknowledge [--mongo-uri <uri>] [--database health] --alert-id <id>
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import pymongo


ALERT_RULES = {
    "hrv_low_3d": {
        "metric": "hrv_sdnn",
        "condition": "deviation_below_pct",
        "threshold_pct": 30,
        "consecutive_days": 3,
        "severity": "moderate",
        "message": "心血管恢复压力持续偏高，建议减少训练强度或休息",
    },
    "resting_hr_high": {
        "metric": "resting_heart_rate",
        "condition": "deviation_above_pct",
        "threshold_pct": 15,
        "consecutive_days": 1,
        "severity": "moderate",
        "message": "静息心率异常升高，排除睡眠债因素后建议就医",
    },
    "sleep_debt_5d": {
        "metric": "sleep",
        "condition": "below_value",
        "threshold_value": 6.0,
        "consecutive_days": 5,
        "severity": "mild",
        "message": "持续睡眠债累积，认知表现和免疫功能可能受影响",
    },
    "blood_glucose_high": {
        "metric": "blood_glucose",
        "condition": "above_value",
        "threshold_value": 11.0,
        "consecutive_days": 3,
        "severity": "severe",
        "message": "血糖控制需关注，建议复查并调整饮食",
    },
}


def load_baseline(db, metric: str) -> Optional[dict]:
    """Load the most recent baseline for a metric from MongoDB."""
    return db.baselines.find_one(
        {"metric": metric},
        sort=[("computed_at", pymongo.DESCENDING)],
    )


def load_recent_values(db, metric: str, days: int = 14) -> list[tuple[str, float]]:
    """
    Load daily average values for a metric over the past N days from MongoDB.
    Returns a sorted list of (date_str, avg_value) tuples.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {
            "metadata.metric": metric,
            "timestamp": {"$gte": cutoff},
        }},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
            "avg_value": {"$avg": "$value"},
        }},
        {"$sort": {"_id": 1}},
    ]

    results = list(db.metrics.aggregate(pipeline))
    return [(r["_id"], r["avg_value"]) for r in results]


def evaluate_rule(rule_id: str, rule: dict, db) -> Optional[dict]:
    """Evaluate a single rule. Returns alert dict if triggered, else None."""
    metric = rule["metric"]
    baseline = load_baseline(db, metric)
    if not baseline:
        return None

    recent = load_recent_values(db, metric, days=14)
    if not recent:
        return None

    consecutive = 0
    trigger_values: list[tuple[str, float]] = []
    baseline_mean = baseline.get("mean", 0)
    if baseline_mean == 0:
        return None

    # Iterate in reverse-chronological order (most recent last)
    for date_str, value in reversed(recent):
        condition = rule["condition"]

        if condition == "deviation_below_pct":
            threshold_pct = rule["threshold_pct"]
            lower_bound = baseline_mean * (1 - threshold_pct / 100)
            if value < lower_bound:
                consecutive += 1
                trigger_values.append((date_str, value))
            else:
                consecutive = 0
                trigger_values = []

        elif condition == "deviation_above_pct":
            threshold_pct = rule["threshold_pct"]
            upper_bound = baseline_mean * (1 + threshold_pct / 100)
            if value > upper_bound:
                consecutive += 1
                trigger_values.append((date_str, value))
            else:
                consecutive = 0
                trigger_values = []

        elif condition == "below_value":
            if value < rule["threshold_value"]:
                consecutive += 1
                trigger_values.append((date_str, value))
            else:
                consecutive = 0
                trigger_values = []

        elif condition == "above_value":
            if value > rule["threshold_value"]:
                consecutive += 1
                trigger_values.append((date_str, value))
            else:
                consecutive = 0
                trigger_values = []

        else:
            consecutive = 0
            trigger_values = []

        if consecutive >= rule["consecutive_days"]:
            deviation = ((value - baseline_mean) / baseline_mean * 100)
            alert_id = f"{rule_id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
            return {
                "_id": alert_id,
                "rule_id": rule_id,
                "severity": rule["severity"],
                "message": rule["message"],
                "metric": metric,
                "current": round(value, 2),
                "baseline": round(baseline_mean, 2),
                "deviation_pct": round(deviation, 1),
                "days_above_threshold": consecutive,
                "trigger_dates": [d for d, _ in trigger_values[-consecutive:]],
                "date": datetime.now(timezone.utc).date().isoformat(),
                "status": "active",
            }

    return None


def evaluate_all_rules(db, rule_ids: Optional[list[str]] = None) -> list[dict]:
    """Evaluate all (or selected) rules against recent data."""
    rules_to_eval = {k: v for k, v in ALERT_RULES.items()
                     if rule_ids is None or k in rule_ids}

    alerts = []
    for rule_id, rule in rules_to_eval.items():
        alert = evaluate_rule(rule_id, rule, db)
        if alert:
            alerts.append(alert)

    return alerts


def save_alert(db, alert: dict) -> None:
    """Insert an alert document into the alerts collection."""
    db.alerts.insert_one(alert)


def acknowledge_alert(db, alert_id: str) -> None:
    """Update alert status to acknowledged."""
    now = datetime.now(timezone.utc)
    db.alerts.update_one(
        {"_id": alert_id},
        {"$set": {"status": "acknowledged", "acknowledged_at": now}},
    )


def main():
    default_uri = os.environ.get("MDB_MCP_CONNECTION_STRING", "")

    parser = argparse.ArgumentParser(description="Health early warning engine")
    parser.add_argument("--mongo-uri", default=default_uri, help="MongoDB connection string (default: $MDB_MCP_CONNECTION_STRING)")
    parser.add_argument("--database", default="health", help="MongoDB database name (default: health)")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate all rules")
    parser.add_argument("--acknowledge", action="store_true", help="Acknowledge an alert")
    parser.add_argument("--rules", nargs="+", help="Specific rule IDs to evaluate")
    parser.add_argument("--alert-id", help="Alert ID for acknowledgement")
    args = parser.parse_args()

    if not args.mongo_uri:
        print("Error: --mongo-uri required or MDB_MCP_CONNECTION_STRING env var must be set", file=sys.stderr)
        sys.exit(1)

    client = pymongo.MongoClient(args.mongo_uri)
    db = client[args.database]

    try:
        if args.evaluate:
            alerts = evaluate_all_rules(db, args.rules)
            for alert in alerts:
                save_alert(db, alert)
            output = {"alerts_triggered": len(alerts), "alerts": alerts}
            print(json.dumps(output, ensure_ascii=False, indent=2))

        elif args.acknowledge:
            if not args.alert_id:
                print("Error: --alert-id required for --acknowledge", file=sys.stderr)
                sys.exit(1)
            acknowledge_alert(db, args.alert_id)
            print(json.dumps({"alert_id": args.alert_id, "status": "acknowledged"}, ensure_ascii=False))

        else:
            parser.print_help()
    finally:
        client.close()


if __name__ == "__main__":
    main()
