#!/usr/bin/env python3
"""PostToolUse(Edit|Write) hook: detect repeated edits to the same file.

Fires in two situations:
1. The same file receives edits in 3+ separate BURSTS within a 10-minute
   window — a burst is a run of edits whose inter-edit gap is <= 30 s.
   Batched multi-location edits landed in one assistant turn collapse into
   a single burst and stay silent; a debug loop (edit -> build/test ->
   edit again) produces one burst per round and trips the threshold.
   Targets the "patch on top of patch" pattern identified in the
   2026-04 — 2026-05 Claude Code Insights review.
2. The same Edit old_string reappears for the same file within the window —
   a deterministic retry signal, fires immediately regardless of bursts.

(2026-07-11 noise fix: the previous per-edit counter fired ~50 times on a
single approved batch of distinct-location edits. Burst grouping keeps the
original target — separated edit rounds — while ignoring planned batches.)

Silent on success. State persisted to .claude/edit-history.json (per project).

Window: 10 minutes (600 s). Burst gap: 30 s. Threshold: 3rd burst fires.
Cap: keep at most 100 files (FIFO eviction); per-file lists keep last 20 entries.

Sentinel guard: only persist when CWD looks like a project (has .claude/,
CLAUDE.md, or .git/). Prevents scattering .claude/ directories in scratch /
temp directories where the discipline signal is not useful.
"""

import hashlib
import json
import os
import sys
import time
import tempfile

HISTORY_FILE = ".claude/edit-history.json"
WINDOW_SECONDS = 600  # 10 minutes
BURST_GAP_SECONDS = 30  # edits closer than this belong to the same burst
BURST_THRESHOLD = 3  # 3rd burst fires
MAX_FILES = 100
MAX_ENTRIES_PER_FILE = 20


def read_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Valid JSON that is not a dict (null / list / scalar) would crash
        # prune() and never self-heal — treat as empty.
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def write_history(history):
    """Atomic file-replacement via tempfile + os.replace.

    Single-writer assumption (one Claude Code session); cross-session races
    at worst lose one entry. Not a true multi-writer atomic write.
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
    """Return True if CWD looks like a project directory."""
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


def extract_fingerprint(payload):
    """Short hash of Edit's old_string; empty for Write / missing input."""
    try:
        old = payload.get("tool_input", {}).get("old_string")
        if isinstance(old, str) and old:
            return hashlib.sha1(old.encode("utf-8")).hexdigest()[:10]
    except (AttributeError, TypeError):
        pass
    return ""


def normalize_entry(entry):
    """Accept both legacy bare-float entries and [ts, fp] pairs."""
    if isinstance(entry, (int, float)):
        return [float(entry), ""]
    if (
        isinstance(entry, list)
        and len(entry) == 2
        and isinstance(entry[0], (int, float))
        and isinstance(entry[1], str)
    ):
        return [float(entry[0]), entry[1]]
    return None


def prune(history, now):
    """Drop entries older than the window and files with empty lists."""
    cutoff = now - WINDOW_SECONDS
    pruned = {}
    for path, entries in history.items():
        kept = []
        for e in entries if isinstance(entries, list) else []:
            norm = normalize_entry(e)
            if norm and norm[0] >= cutoff:
                kept.append(norm)
        if kept:
            pruned[path] = kept[-MAX_ENTRIES_PER_FILE:]
    # FIFO cap on total files tracked.
    if len(pruned) > MAX_FILES:
        sorted_paths = sorted(pruned.items(), key=lambda kv: kv[1][-1][0])
        pruned = dict(sorted_paths[-MAX_FILES:])
    return pruned


def count_bursts(entries):
    """Group timestamps into bursts separated by > BURST_GAP_SECONDS."""
    timestamps = sorted(e[0] for e in entries)
    if not timestamps:
        return 0
    bursts = 1
    for prev, cur in zip(timestamps, timestamps[1:]):
        if cur - prev > BURST_GAP_SECONDS:
            bursts += 1
    return bursts


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)  # Silent on malformed input.

    path = extract_file_path(payload)
    if not path:
        sys.exit(0)

    # Sentinel guard: only track edits in project directories.
    if not is_project_cwd():
        sys.exit(0)

    now = time.time()
    fp = extract_fingerprint(payload)

    history = prune(read_history(), now)
    entries = history.get(path, [])

    # Deterministic retry signal: same old_string seen before in the window.
    same_fp_count = sum(1 for e in entries if e[1] == fp) if fp else 0
    same_fp_repeat = same_fp_count > 0

    entries.append([now, fp])
    history[path] = entries[-MAX_ENTRIES_PER_FILE:]
    write_history(history)

    message = None
    if same_fp_repeat:
        message = (
            f"[check-repeated-edit] ⚠️ `{path}` 的同一处 old_string 在 10 分钟内"
            f"被第 {same_fp_count + 1} 次编辑——这是在重试同一个补丁。下一次 Edit 之前，先一句话陈述："
            f"当前假说 / 上一次为何失败 / 这次基于什么新证据。"
        )
    else:
        bursts = count_bursts(entries)
        if bursts >= BURST_THRESHOLD:
            message = (
                f"[check-repeated-edit] ⚠️ `{path}` 在 10 分钟内经历了第 {bursts} 轮"
                f"修改（同轮内的批量编辑只算一轮）。下一次 Edit 之前，先一句话陈述："
                f"当前假说 / 上一次为何失败 / 这次基于什么新证据。"
            )

    if message:
        # JSON envelope so the runtime injects additionalContext back into
        # the model's view; plain stdout would only reach the human transcript.
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
