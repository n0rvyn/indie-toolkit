#!/usr/bin/env python3
"""
Rule-based early warning engine for health alerts.
Evaluates recent data against personal baselines and generates alerts.

Usage:
    python predict.py --evaluate --vault-dir <dir> [--rules <rule_ids>]
    python predict.py --acknowledge --alert-id <id>
"""

import argparse
import sys
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


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


def load_baseline(metric: str, vault_dir: Path) -> Optional[dict]:
    """Load baseline for a metric."""
    baseline_file = vault_dir / "baselines" / f"{metric}.yaml"
    if not baseline_file.exists():
        return None
    with open(baseline_file, "r") as f:
        content = f.read()
    parts = content.split("---\n")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            return yaml.safe_load(part)
        except yaml.YAMLError:
            continue
    return None


def load_recent_values(metric: str, vault_dir: Path, days: int = 14) -> list:
    """Load recent values for a metric over N days."""
    daily_dir = vault_dir / "daily"
    if not daily_dir.exists():
        return []

    cutoff = datetime.now() - timedelta(days=days)
    values_by_date = {}

    for date_dir in sorted(daily_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        try:
            dt = datetime.strptime(date_dir.name, "%Y-%m-%d")
        except ValueError:
            continue
        if dt < cutoff:
            continue

        metric_file = date_dir / f"{metric}.yaml"
        if not metric_file.exists():
            continue

        try:
            with open(metric_file, "r") as f:
                content = f.read()
            parts = content.split("---\n")
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                data = yaml.safe_load(part)
                if not data or not isinstance(data, dict):
                    continue
                records = data.get("records", [])
                if not isinstance(records, list):
                    continue
                # Average all values for the day
                day_values = []
                for rec in records:
                    try:
                        day_values.append(float(rec.get("value", 0)))
                    except (ValueError, TypeError):
                        continue
                if day_values:
                    values_by_date[date_dir.name] = sum(day_values) / len(day_values)
        except Exception:
            continue

    return [(d, v) for d, v in sorted(values_by_date.items())]


def evaluate_rule(rule_id: str, rule: dict, vault_dir: Path) -> Optional[dict]:
    """Evaluate a single rule. Returns alert dict if triggered, else None."""
    metric = rule["metric"]
    baseline = load_baseline(metric, vault_dir)
    if not baseline:
        return None

    recent = load_recent_values(metric, vault_dir, days=14)
    if not recent:
        return None

    consecutive = 0
    trigger_values = []
    baseline_mean = baseline.get("stats", {}).get("mean", 0)

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
            # Unknown condition — reset to avoid stale state
            consecutive = 0
            trigger_values = []

        if consecutive >= rule["consecutive_days"]:
            deviation = ((value - baseline_mean) / baseline_mean * 100) if baseline_mean else 0
            return {
                "id": f"{rule_id}_{datetime.now().strftime('%Y%m%d')}",
                "rule_id": rule_id,
                "severity": rule["severity"],
                "message": rule["message"],
                "metric": metric,
                "current": round(value, 2),
                "baseline": round(baseline_mean, 2),
                "deviation_pct": round(deviation, 1),
                "days_above_threshold": consecutive,
                "trigger_dates": [d for d, _ in trigger_values[-consecutive:]],
                "date": datetime.now().date().isoformat(),
                "status": "active",
            }

    return None


def evaluate_all_rules(vault_dir: Path, rule_ids: Optional[list] = None) -> list:
    """Evaluate all (or selected) rules against recent data."""
    rules_to_eval = {k: v for k, v in ALERT_RULES.items()
                     if rule_ids is None or k in rule_ids}

    alerts = []
    for rule_id, rule in rules_to_eval.items():
        alert = evaluate_rule(rule_id, rule, vault_dir)
        if alert:
            alerts.append(alert)

    return alerts


def save_alert(alert: dict, vault_dir: Path) -> None:
    """Save an alert to alerts/YYYY-MM-DD-{rule_id}.md and .yaml."""
    date_str = alert["date"]
    rule_id = alert["rule_id"]
    alert_id = alert["id"]

    alerts_dir = vault_dir / "alerts"
    alerts_dir.mkdir(exist_ok=True)

    # YAML version
    yaml_file = alerts_dir / f"{date_str}-{rule_id}.yaml"
    with open(yaml_file, "w") as f:
        f.write("---\n")
        f.write(yaml.dump(alert, allow_unicode=True, sort_keys=False))

    # Markdown version
    md_file = alerts_dir / f"{date_str}-{rule_id}.md"
    with open(md_file, "w") as f:
        f.write(f"# Alert: {rule_id}\n\n")
        f.write(f"**Date:** {alert['date']}\n")
        f.write(f"**Severity:** {alert['severity']}\n")
        f.write(f"**Status:** {alert['status']}\n\n")
        f.write(f"## Message\n\n{alert['message']}\n\n")
        f.write(f"## Triggered By\n\n")
        f.write(f"- Metric: {alert['metric']}\n")
        f.write(f"- Current: {alert['current']}\n")
        f.write(f"- Baseline: {alert['baseline']}\n")
        f.write(f"- Deviation: {alert['deviation_pct']}%\n")
        f.write(f"- Days above threshold: {alert['days_above_threshold']}\n")
        f.write(f"- Trigger dates: {', '.join(alert['trigger_dates'])}\n")

    print(f"Alert saved: {alerts_dir.relative_to(vault_dir)}/{yaml_file.name}")


def main():
    parser = argparse.ArgumentParser(description="Health early warning engine")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate all rules")
    parser.add_argument("--acknowledge", action="store_true", help="Acknowledge an alert")
    parser.add_argument("--vault-dir", required=True, help="HealthVault directory")
    parser.add_argument("--rules", nargs="+", help="Specific rule IDs to evaluate")
    parser.add_argument("--alert-id", help="Alert ID for acknowledgement")
    args = parser.parse_args()

    vault_dir = Path(args.vault_dir).expanduser()

    if args.evaluate:
        alerts = evaluate_all_rules(vault_dir, args.rules)
        if not alerts:
            print("No alerts triggered.")
            return
        for alert in alerts:
            save_alert(alert, vault_dir)
        print(f"\n{len(alerts)} alert(s) triggered.")
    elif args.acknowledge:
        # Mark alert as acknowledged in Notion (stub)
        print(f"Alert {args.alert_id} acknowledged (Notion update not yet implemented)")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
