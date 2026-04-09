#!/usr/bin/env python3
"""
Personal baseline computation using Welford's online algorithm.
Computes rolling statistics per metric without storing all raw values.

Usage:
    python baseline.py --vault-dir <dir> [--metric <type>] [--window-days 90]
    python baseline.py --update --vault-dir <dir> --metric <type> --baseline <file>
"""

import argparse
import math
import sys
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class WelfordStats:
    """Online Welford algorithm for computing running statistics."""

    def __init__(self):
        self.count = 0
        self.mean = 0.0
        self.M2 = 0.0
        self.min = float('inf')
        self.max = float('-inf')

    def update(self, value: float) -> None:
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.M2 += delta * delta2
        self.min = min(self.min, value)
        self.max = max(self.max, value)

    @property
    def variance(self) -> float:
        return self.M2 / self.count if self.count > 1 else 0.0

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)

    def combine(self, other: 'WelfordStats') -> 'WelfordStats':
        """Merge two WelfordStats (for parallel reduction)."""
        result = WelfordStats()
        result.count = self.count + other.count
        if result.count == 0:
            return result
        delta = other.mean - self.mean
        result.mean = (self.mean * self.count + other.mean * other.count) / result.count
        result.M2 = self.M2 + other.M2 + delta * delta * self.count * other.count / result.count
        result.min = min(self.min, other.min)
        result.max = max(self.max, other.max)
        return result

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "mean": self.mean,
            "std": self.std,
            "min": self.min if self.count > 0 else None,
            "max": self.max if self.count > 0 else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'WelfordStats':
        ws = cls()
        ws.count = d.get("count", 0)
        ws.mean = d.get("mean", 0.0)
        ws.M2 = d.get("std", 0.0) ** 2 * ws.count if ws.count > 1 else 0.0
        ws.min = d.get("min", float('inf'))
        ws.max = d.get("max", float('-inf'))
        return ws


def compute_baseline(vault_dir: Path, metric: str, window_days: int = 90) -> Optional[dict]:
    """
    Compute baseline statistics for a metric over the rolling window.
    Returns None if fewer than 30 data points are available.
    """
    daily_dir = vault_dir / "daily"

    if not daily_dir.exists():
        print(f"No daily directory found in {vault_dir}", file=sys.stderr)
        return None

    cutoff = datetime.now() - timedelta(days=window_days)
    stats = WelfordStats()
    values_by_date = {}

    # Collect all values within window
    for date_dir in sorted(daily_dir.iterdir()):
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
                if not part or part.startswith("#"):
                    continue
                data = yaml.safe_load(part)
                if not data or not isinstance(data, dict):
                    continue
                records = data.get("records", [])
                if not isinstance(records, list):
                    continue
                date_values = []
                for rec in records:
                    try:
                        v = float(rec.get("value", 0))
                        date_values.append(v)
                    except (ValueError, TypeError):
                        continue
                if date_values:
                    values_by_date[date_dir.name] = date_values

        except Exception as e:
            print(f"Error reading {metric_file}: {e}", file=sys.stderr)
            continue

    # Flatten values
    all_values = [v for vals in values_by_date.values() for v in vals]
    if len(all_values) < 30:
        print(f"Only {len(all_values)} data points for {metric}, need 30 minimum. Skipping.")
        return None

    # Compute stats from flat list
    for v in all_values:
        stats.update(v)

    # Per-day means for trend detection
    daily_means = []
    for date_str in sorted(values_by_date.keys()):
        day_vals = values_by_date[date_str]
        daily_means.append(sum(day_vals) / len(day_vals))

    # Trend: compare first half vs second half
    trend = "stable"
    if len(daily_means) >= 10:
        mid = len(daily_means) // 2
        first_half = sum(daily_means[:mid]) / mid
        second_half = sum(daily_means[mid:]) / (len(daily_means) - mid)
        pct_change = (second_half - first_half) / first_half * 100 if first_half != 0 else 0
        if pct_change > 5:
            trend = "increasing"
        elif pct_change < -5:
            trend = "decreasing"

    return {
        "metric": metric,
        "window_days": window_days,
        "data_points": len(all_values),
        "days_with_data": len(values_by_date),
        "computed_at": datetime.now().isoformat(),
        "stats": stats.to_dict(),
        "trend": trend,
        "unit": _infer_unit(all_values, metric),
    }


def is_leap_year(year: int) -> bool:
    """Check if a year is a leap year."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _infer_unit(values: list, metric: str) -> str:
    """Infer unit from metric name."""
    unit_map = {
        "heart_rate": "bpm",
        "hrv_sdnn": "ms",
        "vo2max": "mL/kg/min",
        "step_count": "count",
        "distance": "km",
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
    }
    return unit_map.get(metric, "unknown")


def update_baseline(existing_baseline: dict, new_values: list) -> dict:
    """
    Update an existing baseline with new observations.
    Uses Welford's algorithm to combine statistics.
    """
    existing = WelfordStats.from_dict({
        "count": existing_baseline.get("stats", {}).get("count", 0),
        "mean": existing_baseline.get("stats", {}).get("mean", 0.0),
        "std": existing_baseline.get("stats", {}).get("std", 0.0),
        "min": existing_baseline.get("stats", {}).get("min"),
        "max": existing_baseline.get("stats", {}).get("max"),
    })

    for v in new_values:
        existing.update(v)

    updated = dict(existing_baseline)
    updated["stats"] = existing.to_dict()
    updated["data_points"] = existing.count
    updated["updated_at"] = datetime.now().isoformat()
    return updated


def compute_all_baselines(vault_dir: Path, window_days: int = 90) -> dict:
    """Discover all metrics and compute baselines for each."""
    daily_dir = vault_dir / "daily"
    if not daily_dir.exists():
        return {}

    # Discover all metric types
    metrics = set()
    for date_dir in daily_dir.iterdir():
        if not date_dir.is_dir():
            continue
        for f in date_dir.glob("*.yaml"):
            metrics.add(f.stem)

    baselines = {}
    for metric in sorted(metrics):
        result = compute_baseline(vault_dir, metric, window_days)
        if result:
            baselines[metric] = result

    return baselines


def save_baseline(baseline: dict, vault_dir: Path) -> None:
    """Save a single baseline to baselines/{metric}.yaml."""
    metric = baseline["metric"]
    baselines_dir = vault_dir / "baselines"
    baselines_dir.mkdir(exist_ok=True)
    out_file = baselines_dir / f"{metric}.yaml"

    with open(out_file, "w") as f:
        f.write("---\n")
        f.write(yaml.safe_dump(baseline, allow_unicode=True, sort_keys=False))

    print(f"Saved: {out_file.relative_to(vault_dir)}")


def load_baseline(metric: str, vault_dir: Path) -> Optional[dict]:
    """Load an existing baseline."""
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


def main():
    parser = argparse.ArgumentParser(description="Baseline computation for health metrics")
    parser.add_argument("--vault-dir", required=True, help="HealthVault directory")
    parser.add_argument("--metric", help="Compute baseline for a specific metric")
    parser.add_argument("--window-days", type=int, default=90, help="Rolling window in days")
    parser.add_argument("--update", action="store_true", help="Update an existing baseline")
    parser.add_argument("--baseline", help="Path to existing baseline YAML (for --update)")
    parser.add_argument("--save", action="store_true", default=True, help="Save baseline to vault")
    args = parser.parse_args()

    vault_dir = Path(args.vault_dir).expanduser()

    if args.update and args.baseline:
        # Update mode
        with open(args.baseline, "r") as f:
            existing = yaml.safe_load(f)
        metric = existing.get("metric", args.metric or "unknown")
        # Collect new values since last update
        cutoff = datetime.fromisoformat(existing.get("computed_at", "2000-01-01"))
        new_values = []
        daily_dir = vault_dir / "daily"
        for date_dir in sorted(daily_dir.iterdir()):
            try:
                dt = datetime.strptime(date_dir.name, "%Y-%m-%d")
            except ValueError:
                continue
            if dt <= cutoff.replace(tzinfo=None):
                continue
            metric_file = date_dir / f"{metric}.yaml"
            if metric_file.exists():
                with open(metric_file, "r") as f:
                    content = f.read()
                parts = content.split("---\n")
                for part in parts:
                    data = yaml.safe_load(part.strip())
                    if not data:
                        continue
                    for rec in data.get("records", []):
                        try:
                            new_values.append(float(rec.get("value", 0)))
                        except (ValueError, TypeError):
                            continue
        updated = update_baseline(existing, new_values)
        if args.save:
            save_baseline(updated, vault_dir)
        print(f"Updated {metric}: {existing.get('stats', {}).get('count')} → {updated['stats']['count']} points")
    elif args.metric:
        # Single metric compute
        result = compute_baseline(vault_dir, args.metric, args.window_days)
        if result:
            if args.save:
                save_baseline(result, vault_dir)
            else:
                print(yaml.dump(result, allow_unicode=True, sort_keys=False))
        else:
            print(f"No baseline computed for {args.metric}", file=sys.stderr)
            sys.exit(1)
    else:
        # Compute all baselines
        baselines = compute_all_baselines(vault_dir, args.window_days)
        for metric, baseline in baselines.items():
            save_baseline(baseline, vault_dir)
        print(f"\nComputed {len(baselines)} baselines")


if __name__ == "__main__":
    main()
