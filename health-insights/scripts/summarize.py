#!/usr/bin/env python3
"""
Daily health data extractor for Haiku/LLM analysis.
Loads daily metrics and outputs structured context for AI summarization.

Usage:
    python summarize.py --date 2026-04-09 --vault-dir <dir> [--output <file>]
    python summarize.py --date 2026-04-09 --vault-dir <dir> --prompt  # print prompt to stdout
"""

import argparse
import json
import sys
import yaml
from datetime import datetime
from pathlib import Path


def load_daily_metrics(date: str, vault_dir: Path) -> dict:
    """Load all metric YAML files for a given date."""
    daily_date_dir = vault_dir / "daily" / date
    if not daily_date_dir.exists():
        return {}

    metrics = {}
    for f in daily_date_dir.glob("*.yaml"):
        metric_name = f.stem
        try:
            with open(f, "r") as fh:
                content = fh.read()
            parts = content.split("---\n")
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                try:
                    data = yaml.safe_load(part)
                    if data and isinstance(data, dict) and data.get("type") == "daily":
                        records = data.get("records", [])
                        values = []
                        for rec in records:
                            try:
                                values.append({
                                    "value": float(rec.get("value", 0)),
                                    "unit": rec.get("unit", ""),
                                    "source": rec.get("source", ""),
                                })
                            except (ValueError, TypeError):
                                continue
                        if values:
                            metrics[metric_name] = {
                                "count": len(values),
                                "values": values,
                                "avg": sum(v["value"] for v in values) / len(values),
                                "min": min(v["value"] for v in values),
                                "max": max(v["value"] for v in values),
                            }
                except yaml.YAMLError:
                    continue
        except Exception as e:
            print(f"Error reading {f}: {e}", file=sys.stderr)

    return metrics


def build_context(date: str, metrics: dict, baselines: dict) -> dict:
    """Build structured context for LLM summarization."""
    metrics_summary = []
    for name, data in sorted(metrics.items()):
        bl = baselines.get(name)
        bl_mean = bl.get("stats", {}).get("mean") if bl else None
        deviation = ""
        if bl_mean and data["avg"] > 0:
            pct = (data["avg"] - bl_mean) / bl_mean * 100
            deviation = f" (baseline: {bl_mean:.1f}, deviation: {pct:+.1f}%)"
        unit = data["values"][0]["unit"] if data["values"] else ""
        metrics_summary.append(
            f"- {name}: avg={data['avg']:.1f}{unit} (n={data['count']}, "
            f"range=[{data['min']:.1f}, {data['max']:.1f}]){deviation}"
        )

    return {
        "date": date,
        "generated_at": datetime.now().isoformat(),
        "metrics_count": len(metrics),
        "metrics": {
            name: {
                "avg": round(data["avg"], 2),
                "min": round(data["min"], 2),
                "max": round(data["max"], 2),
                "count": data["count"],
                "unit": data["values"][0]["unit"] if data["values"] else "",
            }
            for name, data in metrics.items()
        },
        "metrics_text": "\n".join(metrics_summary) if metrics_summary else "(No structured metrics for this date)",
    }


def build_haiku_prompt(date: str, context: dict) -> str:
    """Build Haiku extraction prompt."""
    return f"""You are a health data analyst. Extract key health insights from the following daily metrics for {date}.

Daily Metrics:
{context['metrics_text']}

Respond with a JSON object:
{{
  "recovery_score": 0-100,
  "highlight": "one sentence about the most notable health event",
  "concerns": ["list of any concerning values or trends"],
  "positive_signals": ["list of positive health indicators"],
  "sleep_quality": "good|moderate|poor|unknown",
  "activity_level": "high|moderate|low|unknown",
  "notes": "any additional observations"
}}"""


def main():
    parser = argparse.ArgumentParser(description="Generate daily health summary context for LLM analysis")
    parser.add_argument("--date", required=True, help="Date in YYYY-MM-DD format")
    parser.add_argument("--vault-dir", required=True, help="HealthVault directory")
    parser.add_argument("--output", help="Output YAML file (default: stdout)")
    parser.add_argument("--prompt", action="store_true", help="Print Haiku prompt instead of structured context")
    args = parser.parse_args()

    vault_dir = Path(args.vault_dir).expanduser()

    # Load baselines for deviation context
    baselines = {}
    baselines_dir = vault_dir / "baselines"
    if baselines_dir.exists():
        for bl_file in baselines_dir.glob("*.yaml"):
            try:
                content = bl_file.read_text()
                parts = content.split("---\n")
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    data = yaml.safe_load(part)
                    if data and isinstance(data, dict):
                        baselines[bl_file.stem] = data
            except:
                continue

    metrics = load_daily_metrics(args.date, vault_dir)
    context = build_context(args.date, metrics, baselines)

    if args.prompt:
        print(build_haiku_prompt(args.date, context))
    elif args.output:
        with open(args.output, "w") as f:
            f.write("---\n")
            f.write(yaml.dump(context, allow_unicode=True, sort_keys=False))
        print(f"Context written to {args.output}")
    else:
        print(yaml.dump(context, allow_unicode=True, sort_keys=False))


if __name__ == "__main__":
    main()
