#!/usr/bin/env python3
"""PostToolUse(Edit|Write) hook: detect repeated edits to the same file.

When the same file is edited 3+ times within a 10-minute window, inject a
system-reminder asking the assistant to state an explicit hypothesis and
evidence before the next edit. Targets the "patch on top of patch" pattern
identified in the 2026-04 — 2026-05 Claude Code Insights review.

Silent on success. State persisted to .claude/edit-history.json (per project).

Window: 10 minutes (600 seconds). Threshold: 3rd edit (so first 2 pass silently).
Cap: keep at most 100 entries (FIFO eviction); per-file lists keep last 10 timestamps.

Sentinel guard: only persist when CWD looks like a project (has .claude/,
CLAUDE.md, or .git/). Prevents scattering .claude/ directories in scratch /
temp directories where the discipline signal is not useful.
"""

import json
import os
import sys
import time
import tempfile

HISTORY_FILE = ".claude/edit-history.json"
WINDOW_SECONDS = 600  # 10 minutes
THRESHOLD = 3  # 3rd edit fires
MAX_FILES = 100
MAX_TIMESTAMPS_PER_FILE = 10


def read_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def write_history(history):
    """Atomic file-replacement via tempfile + os.replace.

    Single-writer assumption (one Claude Code session); cross-session races
    at worst lose one timestamp. Not a true multi-writer atomic write.
    SIGKILL during the tempfile-write window can leak a .tmp file
    (cleanup on next session's prune cycle is not implemented — accepted
    low-impact leak, see pre-flight risks).
    """
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(HISTORY_FILE) or ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(history, f)
            os.replace(tmp, HISTORY_FILE)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
    except OSError:
        # Silent failure — history persistence is best-effort.
        pass


def is_project_cwd():
    """Return True if CWD looks like a project directory.

    Project sentinels (any one match → True):
    - .claude/ directory already exists (any prior Claude Code activity)
    - CLAUDE.md file present (explicit project memory file)
    - .git/ directory present (git repository)

    Used to gate persistence: edits in scratch/temp dirs without sentinels
    do not create a .claude/edit-history.json. Trade-off: in a fresh project
    init where none of these exist yet, the first edits will not be tracked
    until one of these markers appears.
    """
    return (
        os.path.isdir(".claude")
        or os.path.isfile("CLAUDE.md")
        or os.path.isdir(".git")
    )


def extract_file_path(payload):
    """Pull the file path from tool_input. Returns None if unavailable."""
    try:
        tool_input = payload.get("tool_input", {})
        # Edit and Write both use 'file_path' key.
        path = tool_input.get("file_path")
        if isinstance(path, str) and path:
            return path
    except (AttributeError, TypeError):
        pass
    return None


def prune(history, now):
    """Drop timestamps older than the window and files with empty lists."""
    cutoff = now - WINDOW_SECONDS
    pruned = {}
    for path, timestamps in history.items():
        kept = [t for t in timestamps if t >= cutoff]
        if kept:
            pruned[path] = kept[-MAX_TIMESTAMPS_PER_FILE:]
    # FIFO cap on total files tracked.
    if len(pruned) > MAX_FILES:
        # Sort by most-recent timestamp ascending, drop oldest.
        sorted_paths = sorted(pruned.items(), key=lambda kv: kv[1][-1])
        pruned = dict(sorted_paths[-MAX_FILES:])
    return pruned


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)  # Silent on malformed input.

    path = extract_file_path(payload)
    if not path:
        sys.exit(0)

    # Sentinel guard: only track edits in project directories.
    # Skips scratch/temp CWDs without project markers to avoid scattering
    # .claude/ directories across the filesystem.
    if not is_project_cwd():
        sys.exit(0)

    now = time.time()
    history = read_history()
    history = prune(history, now)

    timestamps = history.get(path, [])
    timestamps.append(now)
    history[path] = timestamps[-MAX_TIMESTAMPS_PER_FILE:]

    write_history(history)

    # Count edits in the window for this file.
    count_in_window = sum(1 for t in timestamps if t >= now - WINDOW_SECONDS)

    if count_in_window >= THRESHOLD:
        # Emit JSON envelope so the runtime injects additionalContext back into
        # the model's view. Plain stdout from PostToolUse hooks surfaces only
        # to the human in transcript mode and would not reach the assistant
        # about to make the next edit.
        message = (
            f"[check-repeated-edit] ⚠️ `{path}` 在 10 分钟内被编辑了 "
            f"{count_in_window} 次。下一次 Edit 之前，先一句话陈述：当前假说 / "
            f"上一次为何失败 / 这次基于什么新证据。"
        )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": message,
                    }
                }
            )
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
