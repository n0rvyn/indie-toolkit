#!/usr/bin/env python3
"""Generic MongoDB query CLI used by indie-toolkit plugins.

Returns JSON array of matching documents on stdout. Non-zero exit on
connection or parse failure. Designed to be shelled out to from agents;
no state, no stdin.

Usage:
    python3 mongo_query.py \\
        --uri "$MONGO_URI" \\
        --db health \\
        --collection metrics \\
        --filter '{"date": {"$gte": "2026-01-01"}}' \\
        --projection '{"_id": 0, "date": 1, "steps": 1}' \\
        --sort '[["date", -1]]' \\
        --limit 100
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any


def _json_default(obj: Any) -> Any:
    """Coerce non-JSON-native types (ObjectId, datetime) to strings."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    # ObjectId et al.
    return str(obj)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a read-only find() on a MongoDB collection and print JSON."
    )
    parser.add_argument("--uri", required=True, help="MongoDB connection string")
    parser.add_argument("--db", required=True, help="Database name")
    parser.add_argument("--collection", required=True, help="Collection name")
    parser.add_argument(
        "--filter", default="{}",
        help="JSON filter document (default: {})",
    )
    parser.add_argument(
        "--projection", default=None,
        help="JSON projection document (default: none)",
    )
    parser.add_argument(
        "--sort", default=None,
        help='JSON sort spec as a list of [field, direction] pairs, e.g. [["date", -1]]',
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Max documents to return (default: 100)",
    )
    args = parser.parse_args()

    try:
        filter_doc = json.loads(args.filter)
    except json.JSONDecodeError as exc:
        print(f"Invalid --filter JSON: {exc}", file=sys.stderr)
        return 2

    projection = None
    if args.projection:
        try:
            projection = json.loads(args.projection)
        except json.JSONDecodeError as exc:
            print(f"Invalid --projection JSON: {exc}", file=sys.stderr)
            return 2

    sort_spec = None
    if args.sort:
        try:
            sort_spec = json.loads(args.sort)
        except json.JSONDecodeError as exc:
            print(f"Invalid --sort JSON: {exc}", file=sys.stderr)
            return 2

    try:
        from pymongo import MongoClient
    except ImportError:
        print(
            "pymongo not installed. Run: pip3 install pymongo[srv]",
            file=sys.stderr,
        )
        return 3

    try:
        client = MongoClient(args.uri, serverSelectionTimeoutMS=5000)
        coll = client[args.db][args.collection]
        cursor = coll.find(filter_doc, projection)
        if sort_spec:
            cursor = cursor.sort([(f, int(d)) for f, d in sort_spec])
        if args.limit:
            cursor = cursor.limit(args.limit)
        results = list(cursor)
    except Exception as exc:
        print(f"MongoDB query failed: {exc}", file=sys.stderr)
        return 4
    finally:
        try:
            client.close()
        except Exception:
            pass

    json.dump(results, sys.stdout, default=_json_default, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
