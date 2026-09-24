#!/usr/bin/env python3
"""Count how often a skill was invoked, in every form that reaches it.

Three invocation channels are counted, each in both the bare and the
`plugin:name`-namespaced form:

- typed commands: ``<command-name>/name</command-name>`` or
  ``<command-name>/plugin:name</command-name>`` in a genuine user message —
  a ``type:"user"`` line, not ``isMeta``, whose ``message.content`` is a
  string that starts with ``<command-message>`` or ``<command-name>``. A
  ``tool_result`` that echoes that markup (a grep over transcripts, say), an
  ``isMeta`` skill-load or peer message, and a paste that merely contains it
  do not count.
- Skill-tool calls: ``"name":"Skill","input":{"skill":"name"`` or
  ``"input":{"skill":"plugin:name"`` on a ``type:"assistant"`` line
- fork-skill launches (``context: fork`` skills): these never write
  ``<command-name>`` for the typed command. The user line is the plain text
  ``/plugin:name``, followed by a ``type:"system"``, ``subtype:"local_command"``
  record carrying ``<forked-skill-launch>{"skillName":"plugin:name",…}``.
  Only the launch record is counted, so one launch counts once. (Shape
  confirmed on CC 2.1.243–2.1.281 transcripts, 2026-09-24.)

A prose mention of the name (in a sentence, not inside those shapes) never
counts. Sessions are deduped by ``sessionId`` (file stem when absent). With
``--days``, a record whose timestamp is missing or unparseable is excluded —
its age is unknown, so it cannot be shown to fall inside the window.

Usage:
    python3 skill_usage.py --days 60 --control kb self-pacing afk
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


FORK_LAUNCH_RE = re.compile(r"<forked-skill-launch>(.*?)</forked-skill-launch>", re.DOTALL)
TYPED_START_RE = re.compile(r"^\s*<command-(?:message|name)>")


def build_patterns(name: str) -> tuple[re.Pattern, re.Pattern]:
    esc = re.escape(name)
    typed = re.compile(r"<command-name>/?([\w-]+:)?" + esc + r"</command-name>")
    skill_tool = re.compile(r'"name":"Skill","input":\{"skill":"([\w-]+:)?' + esc + r'"')
    return typed, skill_tool


def _fork_name_matches(skill_name: str, name: str) -> bool:
    return skill_name == name or skill_name.endswith(":" + name)


def typed_content(record: dict) -> str | None:
    """The message text when this record is a genuine user-typed message, else None."""
    if record.get("type") != "user" or record.get("isMeta"):
        return None
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not TYPED_START_RE.match(content):
        return None
    return content


def fork_launches(record: dict) -> list[str]:
    """skillName of every fork-skill launch carried by a local_command record."""
    if record.get("type") != "system" or record.get("subtype") != "local_command":
        return []
    content = record.get("content")
    if not isinstance(content, str):
        return []
    names = []
    for m in FORK_LAUNCH_RE.finditer(content):
        try:
            payload = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("skillName"), str):
            names.append(payload["skillName"])
    return names


def iter_jsonl_files(projects_root: Path):
    if not projects_root.exists():
        return
    for path in sorted(projects_root.glob("*/*.jsonl")):
        yield path


def parse_timestamp(ts) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _update_last_use(bucket: dict, ts: datetime | None) -> None:
    if ts is None:
        return
    date_str = ts.date().isoformat()
    if bucket["last_use"] is None or date_str > bucket["last_use"]:
        bucket["last_use"] = date_str


def scan(names: list[str], days: int | None, projects_root: Path) -> dict:
    cutoff = None
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    patterns = {name: build_patterns(name) for name in names}
    buckets = {
        name: {
            "sessions": set(),
            "invocations_typed": 0,
            "invocations_skill_tool": 0,
            "invocations_fork": 0,
            "last_use": None,
        }
        for name in names
    }

    for path in iter_jsonl_files(projects_root):
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue

                ts = parse_timestamp(record.get("timestamp"))
                if cutoff is not None and (ts is None or ts < cutoff):
                    continue

                record_type = record.get("type")
                session_id = record.get("sessionId") or path.stem
                typed_text = typed_content(record)
                launched = fork_launches(record)

                for name in names:
                    typed_pat, skill_pat = patterns[name]
                    bucket = buckets[name]
                    if typed_text is not None and typed_pat.search(typed_text):
                        bucket["invocations_typed"] += 1
                        bucket["sessions"].add(session_id)
                        _update_last_use(bucket, ts)
                    if record_type == "assistant" and skill_pat.search(line):
                        bucket["invocations_skill_tool"] += 1
                        bucket["sessions"].add(session_id)
                        _update_last_use(bucket, ts)
                    forks = sum(1 for n in launched if _fork_name_matches(n, name))
                    if forks:
                        bucket["invocations_fork"] += forks
                        bucket["sessions"].add(session_id)
                        _update_last_use(bucket, ts)

    return {
        name: {
            "sessions": len(bucket["sessions"]),
            "invocations_typed": bucket["invocations_typed"],
            "invocations_skill_tool": bucket["invocations_skill_tool"],
            "invocations_fork": bucket["invocations_fork"],
            "last_use": bucket["last_use"],
        }
        for name, bucket in buckets.items()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("names", nargs="+", help="bare skill names to count, e.g. self-pacing afk")
    parser.add_argument("--days", type=int, default=None, help="only count invocations within the last N days")
    parser.add_argument(
        "--control",
        help="a skill name known to be used, reported separately as a positive control",
    )
    parser.add_argument(
        "--projects",
        default=str(Path.home() / ".claude" / "projects"),
        help="root directory of session jsonl files (override for tests)",
    )
    args = parser.parse_args(argv)

    names = list(dict.fromkeys(args.names))
    all_names = list(names)
    if args.control and args.control not in all_names:
        all_names.append(args.control)

    scanned = scan(all_names, args.days, Path(args.projects))

    result: dict = {"skills": {name: scanned[name] for name in names}}
    if args.control:
        result["control"] = {args.control: scanned[args.control]}

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
