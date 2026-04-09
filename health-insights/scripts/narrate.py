#!/usr/bin/env python3
"""
Health narrative context builder.
Loads daily/weekly data and outputs structured context for LLM narrative generation.

Usage:
    python narrate.py --date 2026-04-09 --vault-dir <dir> [--output <file>]
    python narrate.py --date 2026-04-09 --vault-dir <dir> --weekly [--output <file>]
    python narrate.py --trend heart_rate --vault-dir <dir> [--output <file>]
"""

import argparse
import sys
import yaml
from datetime import datetime, timedelta
from pathlib import Path


def load_daily_data(date: str, vault_dir: Path) -> dict:
    """Load all metrics for a date."""
    daily_date_dir = vault_dir / "daily" / date
    if not daily_date_dir.exists():
        return {}

    all_data = {}
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
                    if data and isinstance(data, dict):
                        all_data[metric_name] = data
                except yaml.YAMLError:
                    continue
        except Exception:
            continue
    return all_data


def load_weekly_data(vault_dir: Path, end_date: str, weeks: int = 1) -> dict:
    """Load daily data for past N weeks."""
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(weeks=weeks)
    days = {}
    current = start_dt
    while current <= end_dt:
        date_str = current.strftime("%Y-%m-%d")
        days[date_str] = load_daily_data(date_str, vault_dir)
        current += timedelta(days=1)
    return days


def load_baseline(metric: str, vault_dir: Path) -> dict | None:
    """Load baseline for a metric."""
    baseline_file = vault_dir / "baselines" / f"{metric}.yaml"
    if not baseline_file.exists():
        return None
    try:
        with open(baseline_file, "r") as f:
            content = f.read()
        parts = content.split("---\n")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            return yaml.safe_load(part)
    except:
        return None


def build_daily_context(date: str, vault_dir: Path) -> dict:
    """Build structured context for daily narrative."""
    metrics = load_daily_data(date, vault_dir)
    baselines = {m: load_baseline(m, vault_dir) for m in metrics}

    metrics_lines = []
    for name, data in sorted(metrics.items()):
        records = data.get("records", [])
        if not records:
            continue
        values = []
        for rec in records:
            try:
                values.append(float(rec.get("value", 0)))
            except (ValueError, TypeError):
                continue
        if values:
            avg = sum(values) / len(values)
            bl = baselines.get(name, {})
            bl_mean = bl.get("stats", {}).get("mean")
            deviation = f" (baseline: {bl_mean:.1f})" if bl_mean else ""
            unit = records[0].get("unit", "") if records else ""
            metrics_lines.append(f"- **{name}**: avg={avg:.1f}{unit}, n={len(values)}{deviation}")

    prompt = f"""你是一个个人健康叙事作者。为 {date} 写一段简洁、鼓励人心的每日健康叙事。

## 今日指标
{chr(10).join(metrics_lines) if metrics_lines else "无结构化数据。"}

## 要求
- 3-5句，温暖鼓励的语气
- 突出积极趋势，承认挑战
- 与个人基线对比（如果有）
- 提及特别突出的指标
- 用中文结尾一个可行的建议

格式：纯文本 markdown。"""

    return {
        "date": date,
        "type": "daily",
        "metrics_count": len(metrics),
        "metrics_text": "\n".join(metrics_lines) if metrics_lines else "无数据",
        "prompt": prompt,
    }


def build_weekly_context(vault_dir: Path, end_date: str) -> dict:
    """Build structured context for weekly correlation analysis."""
    week_data = load_weekly_data(vault_dir, end_date, weeks=1)

    daily_summaries = []
    for date_str in sorted(week_data.keys()):
        metrics = week_data[date_str]
        if not metrics:
            daily_summaries.append(f"- {date_str}: 无数据")
            continue
        lines = []
        for name, data in sorted(metrics.items()):
            records = data.get("records", [])
            if not records:
                continue
            try:
                avg = sum(float(r.get("value", 0)) for r in records) / len(records)
                lines.append(f"{name}={avg:.1f}")
            except (ValueError, TypeError, ZeroDivisionError):
                continue
        daily_summaries.append(f"- {date_str}: {', '.join(lines) if lines else '无数据'}")

    prompt = f"""分析过去一周的健康关联。识别以下模式：
- 睡眠质量 vs HRV恢复
- 训练强度（active energy, exercise time）vs HRV
- 压力指标（静息心率升高）
- 血糖控制

## 周数据
{chr(10).join(daily_summaries)}

## 任务
1. 识别最强的正相关和负相关
2. 标注任何异常趋势（3天以上偏离）
3. 提供2-3个下周具体建议

格式：带章节的 markdown，用中文。"""

    return {
        "date": end_date,
        "type": "weekly",
        "days_with_data": sum(1 for d in week_data.values() if d),
        "week_data_text": "\n".join(daily_summaries),
        "prompt": prompt,
    }


def build_trend_context(metric: str, vault_dir: Path) -> dict:
    """Build structured context for trend narrative."""
    bl = load_baseline(metric, vault_dir)
    bl_text = f"(基线均值: {bl['stats']['mean']:.1f})" if bl else "(无基线数据)"

    prompt = f"""描述 {metric} {bl_text} 过去90天的趋势。
重点：方向、变化程度、值得注意的事件。
用2-3句中文回复。"""

    return {
        "metric": metric,
        "type": "trend",
        "has_baseline": bl is not None,
        "baseline_mean": bl.get("stats", {}).get("mean") if bl else None,
        "prompt": prompt,
    }


def main():
    parser = argparse.ArgumentParser(description="Build narrative context for LLM analysis")
    parser.add_argument("--date", help="Date in YYYY-MM-DD format")
    parser.add_argument("--weekly", action="store_true", help="Weekly correlation mode")
    parser.add_argument("--vault-dir", required=True, help="HealthVault directory")
    parser.add_argument("--output", help="Output YAML file")
    parser.add_argument("--trend", help="Generate trend context for a specific metric")
    args = parser.parse_args()

    vault_dir = Path(args.vault_dir).expanduser()

    if args.weekly:
        if not args.date:
            args.date = datetime.now().strftime("%Y-%m-%d")
        context = build_weekly_context(vault_dir, args.date)
    elif args.trend:
        context = build_trend_context(args.trend, vault_dir)
    else:
        if not args.date:
            print("--date required for daily narrative", file=sys.stderr)
            sys.exit(1)
        context = build_daily_context(args.date, vault_dir)

    output = {
        "generated_at": datetime.now().isoformat(),
        **context,
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write("---\n")
            f.write(yaml.dump(output, allow_unicode=True, sort_keys=False))
        print(f"Context written to {output_path}")
    else:
        print(yaml.dump(output, allow_unicode=True, sort_keys=False))


if __name__ == "__main__":
    main()
