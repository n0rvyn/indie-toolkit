#!/usr/bin/env python3
"""Generic MongoDB insert CLI used by indie-toolkit plugins.

Reads a JSON array of documents from --file or stdin, inserts into the given
collection, prints the inserted _id strings as a JSON array on stdout.

Usage (from a file):
    python3 mongo_insert.py \\
        --uri "$MONGO_URI" \\
        --db health \\
        --collection lab_reports \\
        --file docs.json

Usage (from stdin):
    jq -c '[.item1, .item2]' | python3 mongo_insert.py \\
        --uri "$MONGO_URI" --db health --collection alerts --stdin
"""

from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Insert a JSON array of documents into a MongoDB collection."
    )
    parser.add_argument("--uri", required=True, help="MongoDB connection string")
    parser.add_argument("--db", required=True, help="Database name")
    parser.add_argument("--collection", required=True, help="Collection name")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="Path to a JSON file containing an array of documents")
    src.add_argument("--stdin", action="store_true", help="Read JSON array from stdin")
    args = parser.parse_args()

    if args.stdin:
        raw = sys.stdin.read()
    else:
        with open(args.file) as f:
            raw = f.read()

    try:
        documents = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Invalid input JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(documents, list):
        print("Input must be a JSON array of documents", file=sys.stderr)
        return 2

    if not documents:
        json.dump([], sys.stdout)
        sys.stdout.write("\n")
        return 0

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
        result = coll.insert_many(documents)
        inserted_ids = [str(_id) for _id in result.inserted_ids]
    except Exception as exc:
        print(f"MongoDB insert failed: {exc}", file=sys.stderr)
        return 4
    finally:
        try:
            client.close()
        except Exception:
            pass

    json.dump(inserted_ids, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
