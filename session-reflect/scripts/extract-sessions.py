#!/usr/bin/env python3
"""Discover and list Claude Code and Codex session files with metadata."""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


def get_session_ids_from_db(db_path):
    """Return set of session_ids already in sessions.db."""
    import sqlite3
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = conn.execute("SELECT session_id FROM sessions").fetchall()
        conn.close()
        return {r[0] for r in rows}
    except Exception:
        return set()


def _path_matches_prefix(project_path, prefixes):
    """Match path prefixes against project_path components without substring overreach.

    Examples:
    - prefix '/Users/alice/Code/' matches '/Users/alice/Code/app'
    - prefix '.adam' matches '/Users/alice/Code/.adam/tasks'
    - prefix 'adam' does NOT match '/Users/alice/Code/my-adam-tool'
    """
    if not project_path:
        return False
    normalized = str(project_path).strip()
    if not normalized:
        return False
    parts = [part for part in Path(normalized).parts if part not in ("/", "")]
    for raw_prefix in prefixes:
        prefix = str(raw_prefix).strip()
        if not prefix:
            continue
        if normalized.startswith(prefix):
            return True
        if any(part.startswith(prefix) for part in parts):
            return True
    return False


def discover_claude_sessions(projects_dir, cutoff_ts, excluded_projects=None, ignore_patterns=None):
    """Discover Claude Code session JSONL files newer than cutoff.

    Filtering:
    - excluded_projects: path-prefix list, matched against project_path components (preferred, new)
    - ignore_patterns: substring on project_dir.name (DEPRECATED, back-compat only)
    """
    sessions = []
    projects_path = Path(projects_dir).expanduser()
    if not projects_path.is_dir():
        return sessions

    excluded_projects = excluded_projects or []
    ignore_patterns = ignore_patterns or []

    # Emit deprecation warning if old field is in use
    if ignore_patterns:
        print(
            "[session-reflect] DEPRECATION WARNING: 'ignore_patterns' is deprecated. "
            "Migrate to 'excluded_projects' in config.yaml (path-prefix matching). "
            "ignore_patterns will be removed in a future release.",
            file=sys.stderr,
        )

    for project_dir in projects_path.iterdir():
        if not project_dir.is_dir():
            continue

        # Back-compat substring filter (deprecated)
        if any(pat in project_dir.name for pat in ignore_patterns):
            continue

        for jsonl_file in project_dir.glob("*.jsonl"):
            mtime = jsonl_file.stat().st_mtime
            if mtime < cutoff_ts:
                continue
            session_id = jsonl_file.stem
            meta = extract_claude_metadata(jsonl_file, session_id, project_dir.name)
            if meta:
                if _path_matches_prefix(meta.get("project_path"), excluded_projects):
                    continue
                sessions.append(meta)
    return sessions


def extract_claude_metadata(filepath, session_id, project_dir_name):
    """Extract lightweight metadata from first few lines of a Claude Code session."""
    meta = {
        "session_id": session_id,
        "source": "claude-code",
        "file_path": str(filepath),
        "file_size_kb": filepath.stat().st_size // 1024,
        "project_dir": project_dir_name,
        "project_path": None,
        "branch": None,
        "timestamp": None,
    }
    try:
        with open(filepath, "r") as f:
            for i, line in enumerate(f):
                if i > 20:
                    break
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("cwd") and not meta["project_path"]:
                    meta["project_path"] = record["cwd"]
                if record.get("gitBranch") and not meta["branch"]:
                    meta["branch"] = record["gitBranch"]
                if record.get("timestamp") and not meta["timestamp"]:
                    meta["timestamp"] = record["timestamp"]
                if record.get("sessionId"):
                    meta["session_id"] = record["sessionId"]
    except (OSError, PermissionError):
        pass

    if not meta["timestamp"]:
        meta["timestamp"] = datetime.fromtimestamp(
            filepath.stat().st_mtime
        ).isoformat() + "Z"

    return meta


def discover_codex_sessions(sessions_dir, cutoff_ts):
    """Discover Codex session JSONL files newer than cutoff."""
    sessions = []
    sessions_path = Path(sessions_dir).expanduser()
    if not sessions_path.is_dir():
        return sessions

    cutoff_date = datetime.fromtimestamp(cutoff_ts)
    for year_dir in sessions_path.iterdir():
        if not year_dir.is_dir():
            continue
        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir():
                continue
            for day_dir in month_dir.iterdir():
                if not day_dir.is_dir():
                    continue
                try:
                    dir_date = datetime(
                        int(year_dir.name), int(month_dir.name), int(day_dir.name)
                    )
                    if dir_date < cutoff_date.replace(hour=0, minute=0, second=0):
                        continue
                except (ValueError, TypeError):
                    continue
                for jsonl_file in day_dir.glob("*.jsonl"):
                    meta = extract_codex_metadata(jsonl_file)
                    if meta:
                        sessions.append(meta)
    return sessions


def extract_codex_metadata(filepath):
    """Extract lightweight metadata from a Codex session file."""
    meta = {
        "session_id": None,
        "source": "codex",
        "file_path": str(filepath),
        "file_size_kb": filepath.stat().st_size // 1024,
        "project_dir": None,
        "project_path": None,
        "branch": None,
        "timestamp": None,
    }
    try:
        with open(filepath, "r") as f:
            for i, line in enumerate(f):
                if i > 10:
                    break
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("type") == "session_meta":
                    payload = record.get("payload", {})
                    meta["session_id"] = payload.get("id")
                    meta["project_path"] = payload.get("cwd")
                    if meta["project_path"]:
                        meta["project_dir"] = os.path.basename(meta["project_path"])
                    meta["timestamp"] = payload.get("timestamp")
                    git_info = payload.get("git", {})
                    if isinstance(git_info, dict):
                        meta["branch"] = git_info.get("branch")
                    break
    except (OSError, PermissionError):
        pass

    if not meta["session_id"]:
        meta["session_id"] = filepath.stem
    if not meta["timestamp"]:
        meta["timestamp"] = datetime.fromtimestamp(
            filepath.stat().st_mtime
        ).isoformat() + "Z"

    return meta


def _load_config():
    """Read session-reflect/config.yaml for excluded_projects + back-compat ignore_patterns.
    Mirrors backfill.py:_load_config — keep in sync."""
    from pathlib import Path
    cfg_path = Path(__file__).resolve().parent.parent / "config.yaml"
    excluded = []
    legacy = []
    if not cfg_path.exists():
        return excluded, legacy
    in_excluded = False
    in_legacy = False
    for line in cfg_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped.startswith("excluded_projects:"):
            in_excluded = True
            in_legacy = False
            continue
        if stripped.startswith("ignore_patterns:"):
            in_legacy = True
            in_excluded = False
            continue
        if line.startswith("  - ") or line.startswith("- "):
            value = stripped.lstrip("- ").strip()
            if in_excluded:
                excluded.append(value)
            elif in_legacy:
                legacy.append(value)
        else:
            in_excluded = False
            in_legacy = False
    return excluded, legacy


def main():
    parser = argparse.ArgumentParser(
        description="Discover Claude Code and Codex session files"
    )
    parser.add_argument(
        "--claude-projects",
        default="~/.claude/projects/",
        help="Path to Claude projects directory (default: ~/.claude/projects/)",
    )
    parser.add_argument(
        "--codex-sessions",
        default="~/.codex/sessions/",
        help="Path to Codex sessions directory (default: ~/.codex/sessions/)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Lookback days. 0 = no time filter (used by backfill --days None). Default: 7.",
    )
    parser.add_argument(
        "--excluded-projects",
        nargs="*",
        default=None,
        help="Project path prefixes to exclude (e.g. .adam). Replaces --ignore-patterns.",
    )
    parser.add_argument(
        "--ignore-patterns",
        nargs="*",
        default=None,
        help="DEPRECATED: substring match on project dirname. Use --excluded-projects instead.",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Filter by project name (substring match)",
    )
    parser.add_argument(
        "--source",
        choices=["claude-code", "codex", "all"],
        default="all",
        help="Filter by source (default: all)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file (default: stdout)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--sqlite-db",
        default=None,
        help="Path to sessions.db for deduplication (skip already-analyzed sessions)",
    )
    args = parser.parse_args()

    # --days 0 sentinel = no time filter (used by backfill orchestrator)
    if args.days == 0:
        cutoff_ts = 0
    else:
        cutoff_ts = (datetime.now() - timedelta(days=args.days)).timestamp()

    # Merge CLI args with config.yaml defaults
    config_excluded, config_legacy = _load_config()
    effective_excluded = args.excluded_projects if args.excluded_projects is not None else config_excluded
    effective_legacy = args.ignore_patterns if args.ignore_patterns is not None else config_legacy

    sessions = []
    if args.source in ("claude-code", "all"):
        sessions.extend(discover_claude_sessions(
            args.claude_projects,
            cutoff_ts,
            excluded_projects=effective_excluded,
            ignore_patterns=effective_legacy,
        ))
    if args.source in ("codex", "all"):
        sessions.extend(discover_codex_sessions(args.codex_sessions, cutoff_ts))

    if args.sqlite_db:
        existing = get_session_ids_from_db(args.sqlite_db)
        sessions = [s for s in sessions if s["session_id"] not in existing]

    if args.project:
        sessions = [
            s for s in sessions
            if args.project.lower() in (s.get("project_dir") or "").lower()
            or args.project.lower() in (s.get("project_path") or "").lower()
        ]

    sessions.sort(key=lambda s: s.get("timestamp") or "", reverse=True)

    if args.format == "text":
        output_lines = []
        for s in sessions:
            ts = (s.get("timestamp") or "")[:19]
            src = s["source"][:6]
            proj = (s.get("project_dir") or "?")[:25]
            size = s.get("file_size_kb", 0)
            output_lines.append(f"{ts}  {src:6s}  {proj:25s}  {size:>6d}KB  {s['session_id']}")
        output = "\n".join(output_lines)
    else:
        output = json.dumps(sessions, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
