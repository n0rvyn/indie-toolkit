#!/usr/bin/env python3
"""
Generate annual health heatmap JSON from MongoDB daily aggregates.

Outputs one entry per day of the target year with a composite health score
(0-100) and per-metric sub-scores, suitable for Obsidian or web rendering.

Usage:
    python3 heatmap.py --year 2026 [--mongo-uri <uri>] [--database health] [--output <path>]
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import pymongo


METRICS_TO_SCORE = (
    "heart_rate",
    "hrv_sdnn",
    "sleep",
    "step_count",
    "resting_heart_rate",
)

SCORE_WEIGHTS = {
    "heart_rate": 0.15,
    "hrv_sdnn": 0.25,
    "sleep": 0.30,
    "step_count": 0.15,
    "resting_heart_rate": 0.15,
}


def is_leap_year(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def day_range(year):
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def metric_score(metric, value, baseline):
    """Map metric value to a 0-100 score using baseline deviation.

    Higher-is-better metrics (hrv_sdnn, sleep, step_count): >= baseline -> 100,
    degrade linearly down to 0 at 50% below baseline.
    Lower-is-better metrics (heart_rate, resting_heart_rate): <= baseline -> 100,
    degrade linearly up to 0 at 150% above baseline.
    """
    if value is None or baseline is None or baseline == 0:
        return None
    ratio = value / baseline
    higher_better = metric in ("hrv_sdnn", "sleep", "step_count")
    if higher_better:
        if ratio >= 1.0:
            return 100
        return max(0, int(round((ratio - 0.5) / 0.5 * 100)))
    else:
        if ratio <= 1.0:
            return 100
        return max(0, int(round((1.5 - ratio) / 0.5 * 100)))


def composite_score(per_metric):
    """Weighted average of available metric sub-scores, rescaled by present weight."""
    total_weight = 0.0
    weighted_sum = 0.0
    for metric, sub in per_metric.items():
        if sub is None:
            continue
        w = SCORE_WEIGHTS.get(metric, 0.0)
        if w == 0:
            continue
        total_weight += w
        weighted_sum += w * sub
    if total_weight == 0:
        return None
    return int(round(weighted_sum / total_weight))


def load_baselines(db):
    """Return {metric: mean} map from the latest baseline row per metric."""
    pipeline = [
        {"$sort": {"computed_at": -1}},
        {
            "$group": {
                "_id": "$metric",
                "mean": {"$first": "$stats.mean"},
            }
        },
    ]
    out = {}
    for row in db.baselines.aggregate(pipeline):
        metric = row.get("_id")
        mean = row.get("mean")
        if metric and mean is not None:
            out[metric] = mean
    return out


def load_daily_averages(db, year):
    """Return {iso_date: {metric: avg_value}} for the target year."""
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    pipeline = [
        {"$match": {"timestamp": {"$gte": start, "$lt": end}}},
        {
            "$group": {
                "_id": {
                    "date": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}
                    },
                    "metric": "$metadata.metric",
                },
                "avg": {"$avg": "$value"},
            }
        },
    ]
    out = {}
    for row in db.metrics.aggregate(pipeline):
        d = row["_id"]["date"]
        m = row["_id"]["metric"]
        avg = row["avg"]
        out.setdefault(d, {})[m] = avg
    return out


def build_heatmap(year, daily_avgs, baselines):
    days = []
    scored_days = []
    for day in day_range(year):
        iso = day.isoformat()
        metrics = daily_avgs.get(iso, {})
        per_metric_scores = {}
        for metric in METRICS_TO_SCORE:
            value = metrics.get(metric)
            baseline = baselines.get(metric)
            per_metric_scores[metric] = metric_score(metric, value, baseline)
        score = composite_score(per_metric_scores)
        entry = {"date": iso, "score": score}
        for metric, sub in per_metric_scores.items():
            entry[metric] = sub
        days.append(entry)
        if score is not None:
            scored_days.append(score)

    overall = int(round(sum(scored_days) / len(scored_days))) if scored_days else None
    return {
        "year": year,
        "generated": datetime.now(timezone.utc).date().isoformat(),
        "overall_score": overall,
        "covered_days": len(scored_days),
        "total_days": 366 if is_leap_year(year) else 365,
        "days": days,
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--mongo-uri",
        default=os.environ.get("MDB_MCP_CONNECTION_STRING"),
        help="MongoDB connection string (default: $MDB_MCP_CONNECTION_STRING)",
    )
    parser.add_argument("--database", default="health")
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path (default: stdout)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.mongo_uri:
        print("error: --mongo-uri or $MDB_MCP_CONNECTION_STRING is required", file=sys.stderr)
        return 2

    client = pymongo.MongoClient(args.mongo_uri)
    try:
        db = client[args.database]
        baselines = load_baselines(db)
        daily_avgs = load_daily_averages(db, args.year)
        heatmap = build_heatmap(args.year, daily_avgs, baselines)
    finally:
        client.close()

    payload = json.dumps(heatmap, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(payload)
        print(f"wrote {args.output} ({len(heatmap['days'])} days, {heatmap['covered_days']} scored)")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
