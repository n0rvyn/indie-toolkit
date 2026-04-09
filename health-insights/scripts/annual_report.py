#!/usr/bin/env python3
"""
Annual health report context builder.
Aggregates full year data and outputs structured context for LLM narrative generation.

Usage:
    python annual_report.py --year 2025 --vault-dir <dir> [--output <dir>]
"""

import argparse
import json
import math
import sys
import yaml
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def load_year_data(year: int, vault_dir: Path) -> dict:
    """Load all daily data for a given year."""
    daily_dir = vault_dir / "daily"
    if not daily_dir.exists():
        return {}

    year_data = defaultdict(list)
    for date_dir in sorted(daily_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        try:
            dt = datetime.strptime(date_dir.name, "%Y-%m-%d")
        except ValueError:
            continue
        if dt.year != year:
            continue

        for f in date_dir.glob("*.yaml"):
            metric = f.stem
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
                        if data and isinstance(data, dict):
                            year_data[metric].extend(data.get("records", []))
                    except yaml.YAMLError:
                        continue
            except Exception:
                continue

    return dict(year_data)


def compute_yearly_stats(year_data: dict) -> dict:
    """Compute yearly aggregated statistics per metric."""
    stats = {}
    for metric, records in year_data.items():
        if not records:
            continue
        values = []
        for rec in records:
            try:
                values.append(float(rec.get("value", 0)))
            except (ValueError, TypeError):
                continue

        if len(values) < 5:
            continue

        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = math.sqrt(variance)

        # Monthly breakdown
        monthly = defaultdict(list)
        for rec in records:
            try:
                start = rec.get("start_date", "")
                if start:
                    dt = datetime.fromisoformat(start.replace("Z", "+00:00").replace("+08:00", ""))
                    month_key = f"{dt.year}-{dt.month:02d}"
                    monthly[month_key].append(float(rec.get("value", 0)))
            except (ValueError, TypeError):
                continue

        monthly_avgs = {
            m: round(sum(vals) / len(vals), 2)
            for m, vals in sorted(monthly.items())
        }

        # Days with data
        days_with_data = len(set(
            rec.get("start_date", "")[:10]
            for rec in records
            if rec.get("start_date")
        ))

        stats[metric] = {
            "n": n,
            "mean": round(mean, 2),
            "std": round(std, 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "days_with_data": days_with_data,
            "monthly_avg": monthly_avgs,
        }

    return stats


def is_leap_year(year: int) -> bool:
    """Check if year is a leap year."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def build_annual_context(year: int, vault_dir: Path) -> dict:
    """Build structured context for LLM annual narrative."""
    year_data = load_year_data(year, vault_dir)
    if not year_data:
        return {"error": f"No data found for year {year}"}

    stats = compute_yearly_stats(year_data)
    days_in_year = 366 if is_leap_year(year) else 365

    stats_lines = []
    for metric, s in sorted(stats.items()):
        monthly_str = ", ".join(f"{m}:{v}" for m, v in s.get("monthly_avg", {}).items())
        stats_lines.append(
            f"- **{metric}**: mean={s['mean']}, std={s['std']}, "
            f"range=[{s['min']}, {s['max']}], days={s['days_with_data']}/{days_in_year}, monthly={monthly_str}"
        )

    prompt = f"""为 {year} 写一份全面的年度健康报告。这是一份个人健康回顾 — 温暖、有洞察力、鼓励人心。

## 年度统计
{chr(10).join(stats_lines) if stats_lines else "数据有限。"}

## 报告结构
1. **数字之年** — 关键总数和均值
2. **亮点** — 最佳成就（个人记录、积极趋势）
3. **关注领域** — 显著偏离的指标
4. **每月旅程** — 值得注意的月度模式
5. **展望未来** — 明年2-3个具体健康目标

保持个人化和温暖的语气，像健身教练回顾你的一年。
格式：带标题的 markdown，用中文。"""

    return {
        "year": year,
        "generated_at": datetime.now().isoformat(),
        "metrics_count": len(stats),
        "days_in_year": days_in_year,
        "stats": stats,
        "stats_text": "\n".join(stats_lines) if stats_lines else "数据有限",
        "prompt": prompt,
    }


def main():
    parser = argparse.ArgumentParser(description="Build annual report context for LLM analysis")
    parser.add_argument("--year", type=int, required=True, help="Year to report on")
    parser.add_argument("--vault-dir", required=True, help="HealthVault directory")
    parser.add_argument("--output", help="Output directory (default: vault/annual/)")
    args = parser.parse_args()

    vault_dir = Path(args.vault_dir).expanduser()
    year = args.year

    context = build_annual_context(year, vault_dir)
    if "error" in context:
        print(context["error"], file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output) if args.output else vault_dir / "annual"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write context YAML
    context_file = output_dir / f"{year}-context.yaml"
    with open(context_file, "w") as f:
        f.write("---\n")
        yaml.dump(context, f, allow_unicode=True, sort_keys=False)
    print(f"Context written: {context_file}")

    # Write heatmap JSON (monthly averages per metric)
    heatmap_data = {
        metric: s.get("monthly_avg", {})
        for metric, s in context.get("stats", {}).items()
    }
    heatmap_file = output_dir / f"{year}-heatmap.json"
    with open(heatmap_file, "w") as f:
        json.dump(heatmap_data, f, indent=2)
    print(f"Heatmap data written: {heatmap_file}")


if __name__ == "__main__":
    main()
