#!/usr/bin/env python3
"""Render all trend charts from daily aggregate data in one call."""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from chart_utils import render_bar_chart, format_number, format_percent, format_duration


def render_trends(daily_aggregates, metric="all"):
    """Render trend charts from daily aggregates.

    Args:
        daily_aggregates: list of daily metric dicts (sorted by date)
        metric: efficiency | quality | collaboration | all

    Returns:
        rendered charts as string
    """
    if not daily_aggregates:
        return "No data to chart."

    sections = []

    if metric in ("efficiency", "all"):
        sections.append(render_bar_chart(
            [{"label": d["date"][5:], "value": d.get("sessions_count", 0)} for d in daily_aggregates],
            "Sessions per Day", format_number
        ))
        sections.append("")
        sections.append(render_bar_chart(
            [{"label": d["date"][5:], "value": d.get("avg_duration_min") or 0} for d in daily_aggregates],
            "Avg Session Duration", format_duration
        ))
        sections.append("")
        sections.append(render_bar_chart(
            [{"label": d["date"][5:], "value": d.get("avg_cache_hit_rate") or 0} for d in daily_aggregates],
            "Cache Hit Rate", format_percent
        ))

    if metric in ("quality", "all"):
        sections.append("")
        sections.append(render_bar_chart(
            [{"label": d["date"][5:], "value": d.get("build_first_pass_rate") or 0} for d in daily_aggregates],
            "Build First-Pass Rate", format_percent
        ))
        sections.append("")
        sections.append(render_bar_chart(
            [{"label": d["date"][5:], "value": d.get("bash_error_rate", 0)} for d in daily_aggregates],
            "Bash Error Rate", format_percent
        ))

    if metric in ("collaboration", "all"):
        sections.append("")
        sections.append(render_bar_chart(
            [{"label": d["date"][5:], "value": d.get("corrections_count", 0)} for d in daily_aggregates],
            "User Corrections", format_number
        ))
        sections.append("")
        # DNA distribution table
        lines = ["Session DNA Distribution"]
        lines.append("| Date | explore | build | fix | chat | mixed |")
        lines.append("|------|---------|-------|-----|------|-------|")
        for d in daily_aggregates:
            dna = d.get("dna_distribution", {})
            date = d["date"][5:]
            lines.append(f"| {date} | {dna.get('explore',0)} | {dna.get('build',0)} | {dna.get('fix',0)} | {dna.get('chat',0)} | {dna.get('mixed',0)} |")
        sections.append("\n".join(lines))

    return "\n".join(sections)


def main():
    parser = argparse.ArgumentParser(description="Render all trend charts")
    parser.add_argument("--input", required=True, help="JSON file with daily aggregates")
    parser.add_argument("--metric", choices=["efficiency", "quality", "collaboration", "all"],
                       default="all", help="Metric category")
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    if isinstance(data, dict):
        data = list(data.values())

    print(render_trends(data, args.metric))


if __name__ == "__main__":
    main()
