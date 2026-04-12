#!/usr/bin/env python3
"""Scan repo git history into session-reflect.plugin_changes."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import sessions_db  # noqa: E402

SUBJECT_PATTERN = re.compile(r"^(feat|fix|refactor|perf|docs|chore)\(([^)]+)\):\s+(.+)$")


def parse_commit_subject(subject):
    """Parse a conventional commit subject into plugin/component fields."""
    match = SUBJECT_PATTERN.match(subject or "")
    if not match:
        return None
    change_type, scope, summary = match.groups()
    plugin = scope
    component = None
    if "/" in scope:
        plugin, component = scope.split("/", 1)
    return {
        "plugin": plugin,
        "component": component,
        "change_type": change_type,
        "summary": summary,
    }


def load_git_history(since):
    """Return commit rows from git log."""
    cmd = [
        "git",
        "log",
        f"--since={since}",
        "--format=%H\t%aI\t%s",
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git log failed")
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        rows.append({
            "commit_hash": parts[0],
            "commit_date": parts[1],
            "subject": parts[2],
        })
    return rows


def scan_plugin_changes(since):
    """Parse repo history into plugin_changes rows."""
    parsed = []
    skipped = 0
    for row in load_git_history(since):
        subject = parse_commit_subject(row["subject"])
        if not subject:
            skipped += 1
            continue
        parsed.append({
            "plugin": subject["plugin"],
            "component": subject["component"],
            "commit_hash": row["commit_hash"],
            "commit_date": row["commit_date"],
            "change_type": subject["change_type"],
            "summary": subject["summary"],
        })
    return parsed, skipped


def main():
    parser = argparse.ArgumentParser(description="Scan repo git history into plugin_changes")
    parser.add_argument("--since", default="2026-01-01", help="Git history lower bound")
    parser.add_argument("--sqlite-db", default=None, help="Target sessions.db path")
    args = parser.parse_args()

    if args.sqlite_db:
        sessions_db.set_db_path(args.sqlite_db)
    sessions_db.init_db()

    parsed, skipped = scan_plugin_changes(args.since)
    for row in parsed:
        sessions_db.upsert_plugin_change(row)

    print(f"[plugin-changes] scanned={len(parsed) + skipped}")
    print(f"[plugin-changes] inserted={len(parsed)}")
    print(f"[plugin-changes] skipped={skipped}")


if __name__ == "__main__":
    main()
