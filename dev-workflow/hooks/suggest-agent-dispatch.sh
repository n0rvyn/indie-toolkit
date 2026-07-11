#!/usr/bin/env bash
# PreToolUse hook: suggest Agent dispatch for repeated mechanical Bash exploration.
# Emits hints to stderr only. NEVER exits non-zero (enhance, not break).
#
# Reads stdin: Claude Code PreToolUse JSON
# State: ${CLAUDE_PROJECT_DIR}/.claude/cost-hint-state.json
# Log:   ${CLAUDE_PROJECT_DIR}/.claude/cost-hint.log

set -euo pipefail

# Always exit 0 — wrap everything in a trap so any unhandled error still exits 0
cleanup_exit() { exit 0; }
trap cleanup_exit EXIT ERR

# ── Read stdin ────────────────────────────────────────────────────────────────
INPUT=$(cat)

# ── Sidechain guard (DP-004): sub-agent activity does not count ───────────────
IS_SIDECHAIN=$(echo "$INPUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('true' if d.get('isSidechain', False) else 'false')
" 2>/dev/null || echo "false")

if [ "$IS_SIDECHAIN" = "true" ]; then
  exit 0
fi

# ── Extract command ───────────────────────────────────────────────────────────
CMD=$(echo "$INPUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(d.get('tool_input', {}).get('command', ''))
" 2>/dev/null || echo "")

if [ -z "$CMD" ]; then
  exit 0
fi

# ── Pattern matching ──────────────────────────────────────────────────────────
MATCHED_PATTERN=""
if echo "$CMD" | grep -qE '^sqlite3 .+SELECT'; then
  MATCHED_PATTERN="sqlite3-select"
elif echo "$CMD" | grep -qE '^curl -s .+https?://'; then
  MATCHED_PATTERN="curl-get"
elif echo "$CMD" | grep -qE '^grep -r'; then
  MATCHED_PATTERN="grep-r"
elif echo "$CMD" | grep -qE '^find\s+'; then
  MATCHED_PATTERN="find-scan"
fi

if [ -z "$MATCHED_PATTERN" ]; then
  exit 0
fi

# ── State dir + file paths (DP-005: project-scoped) ──────────────────────────
STATE_DIR="${CLAUDE_PROJECT_DIR:-.}/.claude"
STATE_FILE="${STATE_DIR}/cost-hint-state.json"
LOG_FILE="${STATE_DIR}/cost-hint.log"

mkdir -p "$STATE_DIR" 2>/dev/null || true

# ── Read + parse state (fail-open on corrupt) ─────────────────────────────────
NOW=$(date +%s)
WINDOW=$((NOW - 1800))  # 30 min

STATE=$(python3 - "$STATE_FILE" "$NOW" "$WINDOW" "$MATCHED_PATTERN" "$CMD" <<'PYEOF'
import json, sys, os, time

state_file = sys.argv[1]
now = int(sys.argv[2])
window = int(sys.argv[3])
pattern = sys.argv[4]
cmd = sys.argv[5]
cmd_head = cmd[:40]

# Load state
state = None
if os.path.exists(state_file):
    try:
        with open(state_file) as f:
            state = json.load(f)
        if not isinstance(state, dict):
            state = None
    except Exception:
        state = None
        # Delete corrupt file
        try:
            os.remove(state_file)
        except Exception:
            pass

if state is None:
    state = {"version": 1, "recent_bash": [], "last_hint_ts": 0, "hint_cooldown_until": 0}

# Prune stale entries (>30 min old)
state["recent_bash"] = [e for e in state.get("recent_bash", []) if e.get("ts", 0) >= window]

# Append new entry
state["recent_bash"].append({"ts": now, "pattern": pattern, "cmd_head": cmd_head})

# Cap at 10
state["recent_bash"] = state["recent_bash"][-10:]

# File-size sanity: if state file >4KB, keep last 5
try:
    if os.path.exists(state_file) and os.path.getsize(state_file) > 4096:
        state["recent_bash"] = state["recent_bash"][-5:]
except Exception:
    pass

# Check if hint should fire.
# Note: count is pattern-blind by design — a single Agent dispatch can batch
# heterogeneous mechanical探查 (sqlite + curl + grep in one prompt), so the
# trigger is "≥2 mechanical Bash in window" regardless of which patterns mix.
count = len(state["recent_bash"])
cooldown_until = state.get("hint_cooldown_until", 0)
should_hint = count >= 2 and now > cooldown_until

if should_hint:
    state["hint_cooldown_until"] = now + 300
    state["last_hint_ts"] = now

# Write state
try:
    with open(state_file, "w") as f:
        json.dump(state, f)
except Exception:
    pass

# Output: count and whether to hint
print(f"{count}:{1 if should_hint else 0}")
PYEOF
) 2>/dev/null || echo "0:0"

COUNT=$(echo "$STATE" | cut -d: -f1)
SHOULD_HINT=$(echo "$STATE" | cut -d: -f2)

# ── Emit hint if warranted ────────────────────────────────────────────────────
if [ "$SHOULD_HINT" = "1" ]; then
  echo "[cost-hint] ${COUNT} mechanical探查 detected; consider Agent(subagent_type=Explore) for batching — use general-purpose only if you will act on the results (see CLAUDE.md Bash 路由)" >&2

  # Append to log
  ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
  CMD_HEAD="${CMD:0:40}"
  echo "${ISO} mechanical-bash-cluster pattern=${MATCHED_PATTERN} count=${COUNT} cmd_heads=${CMD_HEAD}" >> "$LOG_FILE" 2>/dev/null || true

  # Cap log file at ~200KB (keep last 1000 lines)
  if [ -f "$LOG_FILE" ]; then
    LOGSIZE=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$LOGSIZE" -gt 204800 ]; then
      TMPLOG=$(mktemp)
      tail -n 1000 "$LOG_FILE" > "$TMPLOG" && mv "$TMPLOG" "$LOG_FILE" || rm -f "$TMPLOG"
    fi
  fi
fi

exit 0
