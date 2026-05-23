#!/usr/bin/env bash
# PreToolUse hook (Read): nudge toward Read 路由 triage for large files / repeated Reads.
# Symmetric to suggest-agent-dispatch.sh (Bash routing).
# Emits hints to stderr only. NEVER exits non-zero (enhance, not break).
#
# Reads stdin: Claude Code PreToolUse JSON for Read tool
# State: ${CLAUDE_PROJECT_DIR:-.}/.claude/cost-hint-state.json (shared file, distinct keys)
# Log:   ${CLAUDE_PROJECT_DIR:-.}/.claude/cost-hint.log

set -euo pipefail

cleanup_exit() { exit 0; }
trap cleanup_exit EXIT ERR

# ── Read stdin ────────────────────────────────────────────────────────────────
INPUT=$(cat)

# ── Sidechain guard ───────────────────────────────────────────────────────────
IS_SIDECHAIN=$(echo "$INPUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('true' if d.get('isSidechain', False) else 'false')
" 2>/dev/null || echo "false")

if [ "$IS_SIDECHAIN" = "true" ]; then
  exit 0
fi

# ── Extract file_path ─────────────────────────────────────────────────────────
FILE_PATH=$(echo "$INPUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(d.get('tool_input', {}).get('file_path', ''))
" 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

# ── Get line count (fast, fail-open) ──────────────────────────────────────────
LINE_COUNT=$(wc -l < "$FILE_PATH" 2>/dev/null || echo 0)
LINE_COUNT=${LINE_COUNT// /}  # strip whitespace

# Threshold: 300 lines. Smaller files are not a cache concern.
if [ -z "$LINE_COUNT" ] || [ "$LINE_COUNT" -le 300 ]; then
  exit 0
fi

# ── State dir + file paths (DP-005) ──────────────────────────────────────────
STATE_DIR="${CLAUDE_PROJECT_DIR:-.}/.claude"
STATE_FILE="${STATE_DIR}/cost-hint-state.json"
LOG_FILE="${STATE_DIR}/cost-hint.log"

mkdir -p "$STATE_DIR" 2>/dev/null || true

NOW=$(date +%s)
WINDOW=$((NOW - 1800))  # 30 min

# ── Update state, decide hint via python ──────────────────────────────────────
STATE=$(python3 - "$STATE_FILE" "$NOW" "$WINDOW" "$FILE_PATH" "$LINE_COUNT" <<'PYEOF'
import json, sys, os

state_file = sys.argv[1]
now = int(sys.argv[2])
window = int(sys.argv[3])
file_path = sys.argv[4]
line_count = int(sys.argv[5])

# Load state (fail-open on corrupt)
state = None
if os.path.exists(state_file):
    try:
        with open(state_file) as f:
            state = json.load(f)
        if not isinstance(state, dict):
            state = None
    except Exception:
        state = None
        try:
            os.remove(state_file)
        except Exception:
            pass

if state is None:
    state = {"version": 1}

# Read-specific keys (distinct from Bash keys to keep concerns isolated)
state.setdefault("recent_reads", [])
state.setdefault("read_hint_cooldown_until", 0)

# Prune entries older than window
state["recent_reads"] = [e for e in state["recent_reads"] if e.get("ts", 0) >= window]

# Append new entry
state["recent_reads"].append({"ts": now, "path": file_path, "lines": line_count})

# Cap at 20 to avoid unbounded growth (Reads can be more frequent than Bash探查)
state["recent_reads"] = state["recent_reads"][-20:]

# Decide hint type
same_file_count = sum(1 for e in state["recent_reads"] if e.get("path") == file_path)
large_read_count = sum(1 for e in state["recent_reads"] if e.get("lines", 0) > 300)
cooldown_until = state.get("read_hint_cooldown_until", 0)

hint_type = "none"
if now > cooldown_until:
    if same_file_count >= 2:
        hint_type = "repeat"
    elif large_read_count >= 2:
        hint_type = "large"

if hint_type != "none":
    state["read_hint_cooldown_until"] = now + 300

# Write state
try:
    with open(state_file, "w") as f:
        json.dump(state, f)
except Exception:
    pass

# Sanity: shrink if file blew up (defensive)
try:
    if os.path.exists(state_file) and os.path.getsize(state_file) > 8192:
        state["recent_reads"] = state["recent_reads"][-10:]
        with open(state_file, "w") as f:
            json.dump(state, f)
except Exception:
    pass

print(f"{hint_type}:{same_file_count}:{large_read_count}")
PYEOF
) 2>/dev/null || echo "none:0:0"

HINT_TYPE=$(echo "$STATE" | cut -d: -f1)
SAME_COUNT=$(echo "$STATE" | cut -d: -f2)
LARGE_COUNT=$(echo "$STATE" | cut -d: -f3)

# ── Emit hint ─────────────────────────────────────────────────────────────────
BASENAME=$(basename "$FILE_PATH" 2>/dev/null || echo "$FILE_PATH")

case "$HINT_TYPE" in
  repeat)
    echo "[cost-hint] Read on ${BASENAME} is the ${SAME_COUNT}× in this session — Read pollution risk. If intent is Verify, use Grep; if Extract, dispatch Agent. (See CLAUDE.md 'Read 路由')" >&2
    ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
    echo "${ISO} same-file-read-${SAME_COUNT}x file=${FILE_PATH}" >> "$LOG_FILE" 2>/dev/null || true
    ;;
  large)
    echo "[cost-hint] Large Read on ${BASENAME} (${LINE_COUNT} lines); ${LARGE_COUNT} large Reads in window. Triage intent before reading: Verify→Grep / Extract→Agent / Skim→ls / Understand-context→Read (the only legitimate main-line Read). See CLAUDE.md 'Read 路由'." >&2
    ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
    echo "${ISO} large-read-cluster count=${LARGE_COUNT} latest_file=${FILE_PATH} lines=${LINE_COUNT}" >> "$LOG_FILE" 2>/dev/null || true
    ;;
esac

# Cap log file at ~200KB (last 1000 lines)
if [ -f "$LOG_FILE" ]; then
  LOGSIZE=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)
  if [ "$LOGSIZE" -gt 204800 ]; then
    TMPLOG=$(mktemp)
    tail -n 1000 "$LOG_FILE" > "$TMPLOG" && mv "$TMPLOG" "$LOG_FILE" || rm -f "$TMPLOG"
  fi
fi

exit 0
