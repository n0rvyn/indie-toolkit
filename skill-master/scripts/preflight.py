"""
preflight.py — Dependency checks for /master insights.

All checks raise on failure with actionable error messages.
"""

import json
import sqlite3
import subprocess
from pathlib import Path


def check_db(path: str | Path) -> None:
    """Raise FileNotFoundError if the sessions.db does not exist."""
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(
            f"Database not found: {p}\n"
            "Install personal-os/session-reflect first: "
            "https://github.com/your-org/personal-os"
        )


def check_schema(path: str | Path) -> None:
    """Raise RuntimeError if plugin_events is missing the invocation_trigger column."""
    p = Path(path).expanduser()
    conn = sqlite3.connect(str(p))
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(plugin_events)")}
        if "invocation_trigger" not in cols:
            raise RuntimeError(
                "session-reflect schema outdated.\n"
                "Run migrate_schema in personal-os Phase 1 to update the schema:\n"
                "  cd personal-os && python3 -m session_reflect.scripts.sessions_db migrate"
            )
    finally:
        conn.close()


def check_marketplace(repo_root: str | Path) -> None:
    """Raise if .claude-plugin/marketplace.json is missing or has empty plugins list."""
    mp = Path(repo_root) / ".claude-plugin" / "marketplace.json"
    if not mp.exists():
        raise FileNotFoundError(
            f"marketplace.json not found: {mp}\n"
            "Ensure you are running /master insights from the indie-toolkit repo root."
        )
    data = json.loads(mp.read_text())
    plugins = data.get("plugins", [])
    if not plugins:
        raise RuntimeError(
            f"marketplace.json has no plugins defined: {mp}"
        )


def check_gh() -> None:
    """Raise RuntimeError if gh CLI is not available or returns non-zero."""
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "gh CLI required but returned non-zero.\n"
                "Install gh CLI: https://cli.github.com/"
            )
    except FileNotFoundError:
        raise RuntimeError(
            "gh CLI required but not found in PATH.\n"
            "Install gh CLI: https://cli.github.com/"
        )


def run_all(repo_root: str | Path, db_path: str | Path | None = None) -> None:
    """Run all preflight checks. Any failure raises immediately."""
    db = db_path or Path("~/.claude/session-reflect/sessions.db").expanduser()
    check_db(db)
    check_schema(db)
    check_marketplace(repo_root)
    check_gh()
