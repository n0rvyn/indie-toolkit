#!/usr/bin/env python3
"""
Notion sync for Health Insights alerts and trends.
Writes to the Health workspace — Trends, Alerts, and Reports databases.

Usage:
    python notion_sync.py --action sync-alerts --alerts <file> [--dry-run]
    python notion_sync.py --action sync-trends --trends <file> [--dry-run]
"""

import argparse
import asyncio
import json
import sys
import yaml
from datetime import datetime, date
from pathlib import Path
from typing import Optional

try:
    from notion_client import AsyncNotion
    HAS_NOTION = True
except ImportError:
    HAS_NOTION = False


def get_notion_token() -> Optional[str]:
    import os
    return os.environ.get("NOTION_API_KEY") or os.environ.get("NOTION_TOKEN")


def notion_timestamp(dt: datetime | date | str) -> str:
    """Convert datetime/date/ISO-str to Notion date format."""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt.isoformat()
    return dt.isoformat()


async def _create_pages(client: AsyncNotion, db_id: str, items: list, properties_fn, dry_run: bool) -> list:
    """Create Notion pages for all items. Returns list of results."""
    if dry_run:
        return [{"dry_run": True, "item": properties_fn(item)} for item in items]

    async def create_one(item):
        props = properties_fn(item)
        try:
            result = await client.pages.create(
                parent={"database_id": db_id},
                properties=props,
            )
            return {"success": True, "id": result.get("id")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    results = await asyncio.gather(*[create_one(item) for item in items], return_exceptions=True)
    return results


def _load_yaml_file(filepath: str) -> list:
    """Load list of records from a YAML file with document separators."""
    with open(filepath, "r") as f:
        content = f.read()
    parts = content.split("---\n")
    records = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            records.append(yaml.safe_load(part))
        except yaml.YAMLError:
            continue
    return records


def sync_alerts(alerts_file: str, dry_run: bool = False) -> dict:
    """Sync alerts to Notion Alerts DB."""
    token = get_notion_token()
    if not token:
        return {"synced": 0, "skipped": "no_token"}

    if not HAS_NOTION:
        return {"synced": 0, "skipped": "no_client"}

    alerts = _load_yaml_file(alerts_file)
    if not alerts:
        return {"synced": 0, "total": 0}

    import os
    alerts_db = os.environ.get("NOTION_ALERTS_DB_ID", "")

    def alert_properties(alert):
        return {
            "Date": {"date": {"start": notion_timestamp(alert.get("date", ""))}},
            "Alert Type": {"select": {"name": alert.get("type", "unknown")}},
            "Severity": {"select": {"name": alert.get("severity", "mild")}},
            "Triggered By": {"text": [{"text": {"content": alert.get("trigger", "")}}]},
            "Status": {"select": {"name": alert.get("status", "active")}},
            "Action Taken": {"text": [{"text": {"content": alert.get("action_taken", "")}}]},
            "Vault Link": {"url": alert.get("vault_link", "")},
        }

    client = AsyncNotion(auth=token)

    if dry_run:
        for alert in alerts:
            print(f"[dry-run] Would create alert: {alert.get('type')} on {alert.get('date')}")
        return {"synced": len(alerts), "dry_run": True}

    results = asyncio.run(_create_pages(client, alerts_db, alerts, alert_properties, False))
    synced = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
    errors = [r for r in results if isinstance(r, dict) and not r.get("success")]

    for err in errors:
        print(f"Error creating alert page: {err.get('error')}", file=sys.stderr)

    return {"synced": synced, "total": len(alerts), "errors": len(errors)}


def sync_trends(trends_file: str, dry_run: bool = False) -> dict:
    """Sync trend records to Notion Trends DB."""
    token = get_notion_token()
    if not token:
        return {"synced": 0, "skipped": "no_token"}

    if not HAS_NOTION:
        return {"synced": 0, "skipped": "no_client"}

    records = _load_yaml_file(trends_file)
    if not records:
        return {"synced": 0, "total": 0}

    import os
    client = AsyncNotion(auth=token)
    trends_db = os.environ.get("NOTION_TRENDS_DB_ID", "")

    def trend_properties(rec):
        return {
            "Date": {"date": {"start": notion_timestamp(rec.get("date", ""))}},
            "Metric Type": {"select": {"name": rec.get("metric", "unknown")}},
            "Value": {"number": float(rec.get("value", 0))},
            "Unit": {"text": [{"text": {"content": rec.get("unit", "")}}]},
            "Source": {"select": {"name": rec.get("source", "apple_health_export")}},
            "Notes": {"text": [{"text": {"content": rec.get("notes", "")}}]},
            "Is Baseline Update": {"checkbox": rec.get("is_baseline_update", False)},
        }

    if dry_run:
        for rec in records:
            print(f"[dry-run] Would create trend: {rec.get('metric')} = {rec.get('value')} on {rec.get('date')}")
        return {"synced": len(records), "dry_run": True}

    results = asyncio.run(_create_pages(client, trends_db, records, trend_properties, False))
    synced = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
    errors = [r for r in results if isinstance(r, dict) and not r.get("success")]

    for err in errors:
        print(f"Error creating trend page: {err.get('error')}", file=sys.stderr)

    return {"synced": synced, "total": len(records), "errors": len(errors)}


def main():
    parser = argparse.ArgumentParser(description="Notion sync for Health Insights")
    parser.add_argument("--action", required=True, choices=["sync-alerts", "sync-trends", "sync-reports"])
    parser.add_argument("--alerts", help="Alerts YAML file to sync")
    parser.add_argument("--trends", help="Trends YAML file to sync")
    parser.add_argument("--reports", help="Reports YAML file to sync")
    parser.add_argument("--dry-run", action="store_true", help="Print without creating pages")
    args = parser.parse_args()

    if args.action == "sync-alerts" and args.alerts:
        result = sync_alerts(args.alerts, args.dry_run)
    elif args.action == "sync-trends" and args.trends:
        result = sync_trends(args.trends, args.dry_run)
    else:
        parser.print_help()
        sys.exit(1)

    print(f"Result: {json.dumps(result)}")


if __name__ == "__main__":
    main()
