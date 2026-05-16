"""
state.py — Cooldown state for /master insights.

State file: ~/.claude/skill-master-insights-state.json (not committed).
"""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_PATH = Path("~/.claude/skill-master-insights-state.json").expanduser()


def load(state_path: str | Path | None = None) -> dict:
    """Load state from file; return {"proposals": []} if missing or invalid."""
    p = Path(state_path) if state_path else STATE_PATH
    if not p.exists():
        return {"proposals": []}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {"proposals": []}


def compute_hash(
    plugin: str,
    component: str,
    change_type: str,
    evidence_keys: list[str],
) -> str:
    """
    SHA-256 of 'plugin|component|change_type|sorted_evidence_keys'.
    Evidence key order does not affect the hash.
    """
    parts = [plugin, component, change_type] + sorted(evidence_keys)
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def is_in_cooldown(
    proposal_hash: str,
    window_days: int = 14,
    state_path: str | Path | None = None,
) -> bool:
    """Return True if the hash was recorded within the last window_days."""
    data = load(state_path)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    for entry in data.get("proposals", []):
        if entry.get("hash") == proposal_hash:
            ts_str = entry.get("ts", "")
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    return True
            except ValueError:
                pass
    return False


def record_proposal(
    proposal_hash: str,
    ts: str | None = None,
    state_path: str | Path | None = None,
) -> None:
    """Append a proposal record and atomically write back to state file."""
    p = Path(state_path) if state_path else STATE_PATH
    data = load(state_path)
    recorded_ts = ts or datetime.now(timezone.utc).isoformat()
    data["proposals"].append({"hash": proposal_hash, "ts": recorded_ts})

    # Atomic write via temp file + os.replace
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=p.parent, prefix=".state_tmp_", suffix=".json"
    )
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, str(p))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
