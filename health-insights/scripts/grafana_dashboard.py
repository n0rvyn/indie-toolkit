#!/usr/bin/env python3
"""
Grafana dashboard management for Health Insights.
Auto-discovers all metrics from MongoDB and creates panels for every one.

Usage:
    python grafana_dashboard.py --deploy    # Discover all metrics, deploy full dashboard
    python grafana_dashboard.py --list      # List available metrics (no Grafana needed)
    python grafana_dashboard.py --dry-run   # Show what would be deployed without deploying

Environment variables:
    GRAFANA_URL                 — Grafana instance URL (e.g. https://norvyn.grafana.net)
    GRAFANA_API_KEY             — Grafana service account token
    GRAFANA_DS_UID              — MongoDB datasource UID in Grafana
    MDB_MCP_CONNECTION_STRING   — MongoDB connection string (pymongo direct, not MCP)
"""

import argparse
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pymongo


# --- Metric metadata: display name, unit, color, chart type, category ---

METRIC_META = {
    # Cardiac
    "heart_rate":             {"name": "Heart Rate",             "unit": "bpm",       "color": "red",       "type": "daily_avg", "category": "Cardiac"},
    "resting_heart_rate":     {"name": "Resting Heart Rate",     "unit": "bpm",       "color": "red",       "type": "find",      "category": "Cardiac"},
    "hrv_sdnn":               {"name": "HRV (SDNN)",             "unit": "ms",        "color": "blue",      "type": "find",      "category": "Cardiac"},
    "walking_heart_rate_avg": {"name": "Walking HR Average",     "unit": "bpm",       "color": "orange",    "type": "find",      "category": "Cardiac"},
    "hr_recovery_1min":       {"name": "HR Recovery (1 min)",    "unit": "bpm",       "color": "green",     "type": "find",      "category": "Cardiac"},
    "vo2max":                 {"name": "VO2Max",                 "unit": "mL/kg/min", "color": "dark-green", "type": "find",     "category": "Cardiac"},
    # Activity
    "step_count":             {"name": "Daily Steps",            "unit": "short",     "color": "green",     "type": "daily_sum", "category": "Activity"},
    "active_energy":          {"name": "Active Energy",          "unit": "kcal",      "color": "orange",    "type": "daily_sum", "category": "Activity"},
    "basal_energy":           {"name": "Basal Energy",           "unit": "kcal",      "color": "yellow",    "type": "daily_sum", "category": "Activity"},
    "distance":               {"name": "Distance",              "unit": "km",        "color": "blue",      "type": "daily_sum", "category": "Activity"},
    "flights_climbed":        {"name": "Flights Climbed",        "unit": "short",     "color": "purple",    "type": "daily_sum", "category": "Activity"},
    "exercise_time":          {"name": "Exercise Time",          "unit": "min",       "color": "green",     "type": "daily_sum", "category": "Activity"},
    "stand_time":             {"name": "Stand Time",             "unit": "min",       "color": "cyan",      "type": "daily_sum", "category": "Activity"},
    "physical_effort":        {"name": "Physical Effort",        "unit": "short",     "color": "orange",    "type": "daily_avg", "category": "Activity"},
    "daylight_time":          {"name": "Daylight Time",          "unit": "min",       "color": "yellow",    "type": "daily_sum", "category": "Activity"},
    # Running
    "running_speed":          {"name": "Running Speed",          "unit": "m/s",       "color": "yellow",    "type": "daily_avg", "category": "Running"},
    "running_power":          {"name": "Running Power",          "unit": "W",         "color": "orange",    "type": "daily_avg", "category": "Running"},
    "running_stride_length":  {"name": "Running Stride Length",  "unit": "m",         "color": "green",     "type": "daily_avg", "category": "Running"},
    "running_gct":            {"name": "Ground Contact Time",    "unit": "ms",        "color": "blue",      "type": "daily_avg", "category": "Running"},
    "running_vertical_osc":   {"name": "Vertical Oscillation",   "unit": "cm",        "color": "purple",    "type": "daily_avg", "category": "Running"},
    # Walking
    "walking_speed":          {"name": "Walking Speed",          "unit": "m/s",       "color": "green",     "type": "daily_avg", "category": "Walking"},
    "walking_step_length":    {"name": "Walking Step Length",    "unit": "m",         "color": "blue",      "type": "daily_avg", "category": "Walking"},
    "walking_asymmetry":      {"name": "Walking Asymmetry",      "unit": "percent",   "color": "orange",    "type": "daily_avg", "category": "Walking"},
    "walking_dbl_support":    {"name": "Double Support %",       "unit": "percent",   "color": "yellow",    "type": "daily_avg", "category": "Walking"},
    "walking_steadiness":     {"name": "Walking Steadiness",     "unit": "short",     "color": "green",     "type": "find",      "category": "Walking"},
    "stair_up_speed":         {"name": "Stair Ascent Speed",     "unit": "m/s",       "color": "green",     "type": "daily_avg", "category": "Walking"},
    "stair_down_speed":       {"name": "Stair Descent Speed",    "unit": "m/s",       "color": "blue",      "type": "daily_avg", "category": "Walking"},
    "6min_walk_distance":     {"name": "6-Min Walk Distance",    "unit": "m",         "color": "green",     "type": "find",      "category": "Walking"},
    # Respiratory & Blood
    "resp_rate":              {"name": "Respiratory Rate",        "unit": "/min",      "color": "cyan",      "type": "find",      "category": "Respiratory"},
    "spo2":                   {"name": "SpO2",                   "unit": "percentunit","color": "purple",    "type": "find",      "category": "Respiratory"},
    "bp_sys":                 {"name": "Blood Pressure (Sys)",   "unit": "mmHg",      "color": "red",       "type": "find",      "category": "Respiratory"},
    "bp_dia":                 {"name": "Blood Pressure (Dia)",   "unit": "mmHg",      "color": "blue",      "type": "find",      "category": "Respiratory"},
    "blood_glucose":          {"name": "Blood Glucose",          "unit": "mmol/L",    "color": "orange",    "type": "find",      "category": "Respiratory"},
    # Body
    "body_mass":              {"name": "Body Mass",              "unit": "kg",        "color": "purple",    "type": "find",      "category": "Body"},
    "bmi":                    {"name": "BMI",                    "unit": "short",     "color": "orange",    "type": "find",      "category": "Body"},
    "body_fat_pct":           {"name": "Body Fat %",             "unit": "percent",   "color": "red",       "type": "find",      "category": "Body"},
    "lean_mass":              {"name": "Lean Mass",              "unit": "kg",        "color": "green",     "type": "find",      "category": "Body"},
    "body_temp":              {"name": "Body Temperature",       "unit": "celsius",   "color": "red",       "type": "find",      "category": "Body"},
    "sleep_wrist_temp":       {"name": "Sleep Wrist Temp",       "unit": "celsius",   "color": "orange",    "type": "find",      "category": "Body"},
    # Nutrition
    "water":                  {"name": "Water Intake",           "unit": "mL",        "color": "blue",      "type": "daily_sum", "category": "Nutrition"},
    "calories_consumed":      {"name": "Calories Consumed",      "unit": "kcal",      "color": "red",       "type": "daily_sum", "category": "Nutrition"},
    "protein":                {"name": "Protein",                "unit": "g",         "color": "green",     "type": "daily_sum", "category": "Nutrition"},
    "carbs":                  {"name": "Carbohydrates",          "unit": "g",         "color": "yellow",    "type": "daily_sum", "category": "Nutrition"},
    "fat_total":              {"name": "Total Fat",              "unit": "g",         "color": "orange",    "type": "daily_sum", "category": "Nutrition"},
    "fiber":                  {"name": "Fiber",                  "unit": "g",         "color": "green",     "type": "daily_sum", "category": "Nutrition"},
    "sugar":                  {"name": "Sugar",                  "unit": "g",         "color": "red",       "type": "daily_sum", "category": "Nutrition"},
    "sodium":                 {"name": "Sodium",                 "unit": "mg",        "color": "yellow",    "type": "daily_sum", "category": "Nutrition"},
    "cholesterol":            {"name": "Cholesterol",            "unit": "mg",        "color": "orange",    "type": "daily_sum", "category": "Nutrition"},
    # Environment
    "env_audio_exposure":     {"name": "Env Audio Exposure",     "unit": "dB",        "color": "yellow",    "type": "daily_avg", "category": "Environment"},
    "headphone_exposure":     {"name": "Headphone Exposure",     "unit": "dB",        "color": "orange",    "type": "daily_avg", "category": "Environment"},
    "env_sound_reduction":    {"name": "Sound Reduction",        "unit": "dB",        "color": "green",     "type": "daily_avg", "category": "Environment"},
    # Sleep
    "sleep":                  {"name": "Sleep",                  "unit": "short",     "color": "purple",    "type": "find",      "category": "Sleep"},
    "sleep_goal":             {"name": "Sleep Goal",             "unit": "short",     "color": "blue",      "type": "find",      "category": "Sleep"},
}

# Fallback for metrics not in METRIC_META
DEFAULT_META = {"unit": "short", "color": "gray", "type": "find", "category": "Other"}


def _build_find_query(metric, limit=500):
    return f'health.metrics.find({{"metadata.metric": "{metric}"}}).sort({{"timestamp": 1}}).limit({limit})'


def _build_daily_sum_query(metric, limit=365):
    return (
        f'health.metrics.aggregate(['
        f'{{"$match": {{"metadata.metric": "{metric}"}}}},'
        f'{{"$group": {{"_id": {{"$dateToString": {{"format": "%Y-%m-%d", "date": "$timestamp"}}}}, "total": {{"$sum": "$value"}}}}}},'
        f'{{"$project": {{"_id": 0, "time": {{"$dateFromString": {{"dateString": "$_id"}}}}, "value": "$total"}}}},'
        f'{{"$sort": {{"time": 1}}}},'
        f'{{"$limit": {limit}}}'
        f'])'
    )


def _build_daily_avg_query(metric, limit=365):
    return (
        f'health.metrics.aggregate(['
        f'{{"$match": {{"metadata.metric": "{metric}"}}}},'
        f'{{"$group": {{"_id": {{"$dateToString": {{"format": "%Y-%m-%d", "date": "$timestamp"}}}}, '
        f'"avg": {{"$avg": "$value"}}, "min": {{"$min": "$value"}}, "max": {{"$max": "$value"}}}}}},'
        f'{{"$project": {{"_id": 0, "time": {{"$dateFromString": {{"dateString": "$_id"}}}}, "avg": 1, "min": 1, "max": 1}}}},'
        f'{{"$sort": {{"time": 1}}}},'
        f'{{"$limit": {limit}}}'
        f'])'
    )


def build_panel(metric, meta, grid_pos, ds_uid):
    """Build a Grafana panel for a metric."""
    query_type = meta.get("type", "find")
    if query_type == "daily_sum":
        query = _build_daily_sum_query(metric)
        draw_style = "bars"
        fill_opacity = 60
    elif query_type == "daily_avg":
        query = _build_daily_avg_query(metric)
        draw_style = "line"
        fill_opacity = 5
    else:
        query = _build_find_query(metric)
        draw_style = "line"
        fill_opacity = 10

    return {
        "title": meta.get("name", metric),
        "type": "timeseries",
        "gridPos": grid_pos,
        "datasource": {"type": "grafana-mongodb-datasource", "uid": ds_uid},
        "targets": [{"refId": "A",
            "datasource": {"type": "grafana-mongodb-datasource", "uid": ds_uid},
            "query": query, "queryType": "query"}],
        "fieldConfig": {"defaults": {
            "unit": meta.get("unit", "short"),
            "color": {"mode": "fixed", "fixedColor": meta.get("color", "gray")},
            "custom": {"drawStyle": draw_style, "lineWidth": 2 if draw_style == "line" else 1,
                       "fillOpacity": fill_opacity, "spanNulls": True},
        }},
    }


def discover_and_build(mongo_uri, ds_uid):
    """Discover all metrics from MongoDB, build panels grouped by category."""
    client = pymongo.MongoClient(mongo_uri)
    db = client["health"]

    # Get all metrics with counts
    pipeline = [
        {"$group": {"_id": "$metadata.metric", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    metrics = [(r["_id"], r["count"]) for r in db.metrics.aggregate(pipeline)]
    client.close()

    # Group by category
    categories = {}
    for metric, count in metrics:
        meta = METRIC_META.get(metric, {**DEFAULT_META, "name": metric})
        cat = meta.get("category", "Other")
        categories.setdefault(cat, []).append((metric, meta, count))

    # Category display order
    cat_order = ["Cardiac", "Activity", "Running", "Walking", "Respiratory", "Body", "Nutrition", "Environment", "Sleep", "Other"]

    panels = []
    y = 0
    panel_id = 1

    for cat in cat_order:
        if cat not in categories:
            continue
        items = categories[cat]

        # Row header
        panels.append({
            "id": panel_id, "type": "row", "title": f"📊 {cat}",
            "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "collapsed": False,
        })
        panel_id += 1
        y += 1

        # 2 panels per row (12 cols each)
        for i, (metric, meta, count) in enumerate(items):
            x = (i % 2) * 12
            if i > 0 and i % 2 == 0:
                y += 8
            grid_pos = {"h": 8, "w": 12, "x": x, "y": y}
            panel = build_panel(metric, meta, grid_pos, ds_uid)
            panel["id"] = panel_id
            panel["description"] = f"{count:,} records"
            panels.append(panel)
            panel_id += 1

        # Move to next row after category
        y += 8

    # Stat row at bottom
    panels.append({
        "id": panel_id, "type": "row", "title": "📈 Summary",
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "collapsed": False,
    })
    panel_id += 1
    y += 1

    # Active Alerts stat
    panels.append({
        "id": panel_id, "title": "Active Alerts", "type": "stat",
        "gridPos": {"h": 4, "w": 6, "x": 0, "y": y},
        "datasource": {"type": "grafana-mongodb-datasource", "uid": ds_uid},
        "targets": [{"refId": "A",
            "datasource": {"type": "grafana-mongodb-datasource", "uid": ds_uid},
            "query": 'health.alerts.aggregate([{"$match": {"status": "active"}}, {"$count": "count"}])',
            "queryType": "query"}],
        "fieldConfig": {"defaults": {
            "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "red", "value": 1}]}}},
        "options": {"colorMode": "background", "graphMode": "none", "textMode": "value"},
    })

    return panels, len(metrics)


def _grafana_api(url, api_key, method="GET", data=None):
    req = Request(url, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    if data:
        req.data = json.dumps(data).encode()
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"Grafana API error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


def deploy(grafana_url, api_key, ds_uid, mongo_uri, dashboard_uid="no59jnc"):
    panels, metric_count = discover_and_build(mongo_uri, ds_uid)
    dashboard = {
        "uid": dashboard_uid,
        "title": "Health Insights",
        "description": f"Auto-generated: {metric_count} metrics from MongoDB Atlas",
        "timezone": "browser",
        "schemaVersion": 42,
        "editable": True,
        "time": {"from": "now-90d", "to": "now"},
        "panels": panels,
    }
    result = _grafana_api(f"{grafana_url}/api/dashboards/db", api_key, "POST",
                          {"dashboard": dashboard, "overwrite": True})
    print(f"Dashboard deployed: {grafana_url}{result['url']}")
    print(f"Metrics: {metric_count}, Panels: {len(panels)}")


def list_metrics(mongo_uri):
    client = pymongo.MongoClient(mongo_uri)
    db = client["health"]
    pipeline = [
        {"$group": {"_id": "$metadata.metric", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    print(f"{'Metric':<30} {'Records':>10}  {'Category':<15} {'Chart Type'}")
    print("-" * 75)
    for r in db.metrics.aggregate(pipeline):
        metric = r["_id"]
        meta = METRIC_META.get(metric, DEFAULT_META)
        print(f"  {metric:<28} {r['count']:>10,}  {meta.get('category', 'Other'):<15} {meta.get('type', 'find')}")
    client.close()


def main():
    parser = argparse.ArgumentParser(description="Grafana Health Insights dashboard (auto-discovers all metrics)")
    parser.add_argument("--deploy", action="store_true", help="Discover metrics from MongoDB and deploy full dashboard")
    parser.add_argument("--list", action="store_true", help="List available metrics")
    parser.add_argument("--dry-run", action="store_true", help="Show panel count without deploying")
    parser.add_argument("--grafana-url", default=os.environ.get("GRAFANA_URL", ""))
    parser.add_argument("--api-key", default=os.environ.get("GRAFANA_API_KEY", ""))
    parser.add_argument("--ds-uid", default=os.environ.get("GRAFANA_DS_UID", ""))
    parser.add_argument("--dashboard-uid", default="no59jnc")
    args = parser.parse_args()

    mongo_uri = os.environ.get("MDB_MCP_CONNECTION_STRING", "")
    if not mongo_uri:
        print("Error: MDB_MCP_CONNECTION_STRING required", file=sys.stderr)
        sys.exit(1)

    if args.list:
        list_metrics(mongo_uri)
    elif args.deploy or args.dry_run:
        if not args.grafana_url or not args.api_key or not args.ds_uid:
            print("Error: --grafana-url, --api-key, --ds-uid required (or GRAFANA_URL, GRAFANA_API_KEY, GRAFANA_DS_UID)", file=sys.stderr)
            sys.exit(1)
        if args.dry_run:
            panels, count = discover_and_build(mongo_uri, args.ds_uid)
            print(f"Would deploy: {count} metrics, {len(panels)} panels")
        else:
            deploy(args.grafana_url, args.api_key, args.ds_uid, mongo_uri, args.dashboard_uid)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
