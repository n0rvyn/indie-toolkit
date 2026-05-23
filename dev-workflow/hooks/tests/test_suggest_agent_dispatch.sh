#!/usr/bin/env bash
# Test driver for dev-workflow/hooks/suggest-agent-dispatch.sh
# Run from any directory; uses absolute paths internally.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SCRIPT="$SCRIPT_DIR/../suggest-agent-dispatch.sh"

PASS=0
FAIL=0

pass() { echo "PASS: $1"; ((PASS++)); }
fail() { echo "FAIL: $1 — $2"; ((FAIL++)); }

# Check hook script exists before running any TCs
if [ ! -f "$HOOK_SCRIPT" ]; then
  echo "FAIL: hook script not found at $HOOK_SCRIPT"
  echo "FAIL: TC1 — hook script not found"
  echo "FAIL: TC2 — hook script not found"
  echo "FAIL: TC3 — hook script not found"
  echo "FAIL: TC4 — hook script not found"
  echo "FAIL: TC5 — hook script not found"
  echo "FAIL: TC6 — hook script not found"
  echo "FAIL: TC7 — hook script not found"
  exit 1
fi

# ── TC1: single mechanical Bash → no hint ─────────────────────────────────────
TC1_DIR=$(mktemp -d)
trap 'rm -rf "$TC1_DIR"' EXIT

STDERR_TC1=$(echo '{"tool_input":{"command":"sqlite3 db.db \"SELECT * FROM t\""},"session_id":"main","isSidechain":false}' \
  | CLAUDE_PROJECT_DIR="$TC1_DIR" bash "$HOOK_SCRIPT" 2>&1 1>/dev/null)
EXIT_TC1=$?

if [ $EXIT_TC1 -ne 0 ]; then
  fail "TC1" "hook exited $EXIT_TC1, expected 0"
elif echo "$STDERR_TC1" | grep -q "\[cost-hint\]"; then
  fail "TC1" "unexpected [cost-hint] in stderr after single invocation: $STDERR_TC1"
else
  pass "TC1"
fi

# ── TC2: 2 mechanical Bash → hint emitted on second ──────────────────────────
TC2_DIR=$(mktemp -d)
# First invocation
echo '{"tool_input":{"command":"sqlite3 db.db \"SELECT * FROM t\""},"session_id":"main","isSidechain":false}' \
  | CLAUDE_PROJECT_DIR="$TC2_DIR" bash "$HOOK_SCRIPT" > /dev/null 2>&1
EXIT_FIRST=$?
# Second invocation — should emit hint
STDERR_TC2=$(echo '{"tool_input":{"command":"sqlite3 db.db \"SELECT * FROM t\""},"session_id":"main","isSidechain":false}' \
  | CLAUDE_PROJECT_DIR="$TC2_DIR" bash "$HOOK_SCRIPT" 2>&1 1>/dev/null)
EXIT_SECOND=$?

if [ $EXIT_FIRST -ne 0 ] || [ $EXIT_SECOND -ne 0 ]; then
  fail "TC2" "hook exited non-zero: first=$EXIT_FIRST second=$EXIT_SECOND"
elif ! echo "$STDERR_TC2" | grep -q "\[cost-hint\]"; then
  fail "TC2" "expected [cost-hint] in stderr on second invocation; got: $STDERR_TC2"
else
  pass "TC2"
fi
rm -rf "$TC2_DIR"

# ── TC3: cooldown suppresses duplicate hint ───────────────────────────────────
TC3_DIR=$(mktemp -d)
# Seed: 2 invocations to trigger hint + set cooldown
echo '{"tool_input":{"command":"sqlite3 db.db \"SELECT * FROM t\""},"session_id":"main","isSidechain":false}' \
  | CLAUDE_PROJECT_DIR="$TC3_DIR" bash "$HOOK_SCRIPT" > /dev/null 2>&1
echo '{"tool_input":{"command":"sqlite3 db.db \"SELECT * FROM t\""},"session_id":"main","isSidechain":false}' \
  | CLAUDE_PROJECT_DIR="$TC3_DIR" bash "$HOOK_SCRIPT" > /dev/null 2>&1
# Third invocation — should be suppressed by cooldown
STDERR_TC3=$(echo '{"tool_input":{"command":"sqlite3 db.db \"SELECT * FROM t\""},"session_id":"main","isSidechain":false}' \
  | CLAUDE_PROJECT_DIR="$TC3_DIR" bash "$HOOK_SCRIPT" 2>&1 1>/dev/null)
EXIT_TC3=$?

if [ $EXIT_TC3 -ne 0 ]; then
  fail "TC3" "hook exited $EXIT_TC3, expected 0"
elif echo "$STDERR_TC3" | grep -q "\[cost-hint\]"; then
  fail "TC3" "cooldown should suppress hint; got: $STDERR_TC3"
else
  pass "TC3"
fi
rm -rf "$TC3_DIR"

# ── TC4: state file pruned when >10 entries ───────────────────────────────────
TC4_DIR=$(mktemp -d)
mkdir -p "$TC4_DIR/.claude" 2>/dev/null || true
NOW=$(date +%s)
# Generate 12 recent_bash entries (within last 30 min)
ENTRIES=""
for i in $(seq 1 12); do
  TS=$((NOW - 60 * i))
  ENTRIES="${ENTRIES}{\"ts\":$TS,\"pattern\":\"sqlite3-select\",\"cmd_head\":\"sqlite3 db.db SELECT\"},"
done
ENTRIES="${ENTRIES%,}"  # remove trailing comma
STATE_FILE="$TC4_DIR/.claude/cost-hint-state.json"
cat > "$STATE_FILE" <<EOF
{"version":1,"recent_bash":[$ENTRIES],"last_hint_ts":0,"hint_cooldown_until":0}
EOF

echo '{"tool_input":{"command":"sqlite3 db.db \"SELECT * FROM t\""},"session_id":"main","isSidechain":false}' \
  | CLAUDE_PROJECT_DIR="$TC4_DIR" bash "$HOOK_SCRIPT" > /dev/null 2>&1
EXIT_TC4=$?

COUNT=$(python3 -c "
import json, sys
with open('$STATE_FILE') as f:
    d = json.load(f)
print(len(d.get('recent_bash', [])))
" 2>/dev/null)

if [ $EXIT_TC4 -ne 0 ]; then
  fail "TC4" "hook exited $EXIT_TC4"
elif [ -z "$COUNT" ] || [ "$COUNT" -gt 10 ]; then
  fail "TC4" "expected ≤10 recent_bash entries after prune; got $COUNT"
else
  pass "TC4"
fi
rm -rf "$TC4_DIR"

# ── TC5: corrupt state file → deleted and recreated, fail-open ───────────────
TC5_DIR=$(mktemp -d)
mkdir -p "$TC5_DIR/.claude"
echo '{not valid json' > "$TC5_DIR/.claude/cost-hint-state.json"

STDERR_TC5=$(echo '{"tool_input":{"command":"sqlite3 db.db \"SELECT * FROM t\""},"session_id":"main","isSidechain":false}' \
  | CLAUDE_PROJECT_DIR="$TC5_DIR" bash "$HOOK_SCRIPT" 2>&1 1>/dev/null)
EXIT_TC5=$?

VALID=$(python3 -c "
import json, sys
try:
    with open('$TC5_DIR/.claude/cost-hint-state.json') as f:
        json.load(f)
    print('valid')
except:
    print('invalid')
" 2>/dev/null)

if [ $EXIT_TC5 -ne 0 ]; then
  fail "TC5" "hook exited $EXIT_TC5 on corrupt state; expected 0 (fail-open)"
elif [ "$VALID" != "valid" ]; then
  fail "TC5" "state file not recreated as valid JSON after corruption"
else
  pass "TC5"
fi
rm -rf "$TC5_DIR"

# ── TC6: always exit 0 ────────────────────────────────────────────────────────
TC6_DIR=$(mktemp -d)
ALL_ZERO=true
for cmd in \
  'sqlite3 db.db "SELECT * FROM t"' \
  'curl -s https://example.com/api' \
  'grep -r foo .' \
  'find . -name "*.sh"'; do
  JSON="{\"tool_input\":{\"command\":\"$(echo "$cmd" | sed 's/"/\\"/g')\"},\"session_id\":\"main\",\"isSidechain\":false}"
  EXIT_CODE=$(echo "$JSON" | CLAUDE_PROJECT_DIR="$TC6_DIR" bash "$HOOK_SCRIPT" > /dev/null 2>&1; echo $?)
  if [ "$EXIT_CODE" -ne 0 ]; then
    ALL_ZERO=false
    fail "TC6" "hook exited $EXIT_CODE for command: $cmd"
    break
  fi
done
if $ALL_ZERO; then
  pass "TC6"
fi
rm -rf "$TC6_DIR"

# ── TC7: sidechain ignored ────────────────────────────────────────────────────
TC7_DIR=$(mktemp -d)
echo '{"tool_input":{"command":"sqlite3 db.db \"SELECT * FROM t\""},"session_id":"sub","isSidechain":true}' \
  | CLAUDE_PROJECT_DIR="$TC7_DIR" bash "$HOOK_SCRIPT" > /dev/null 2>&1
echo '{"tool_input":{"command":"sqlite3 db.db \"SELECT * FROM t\""},"session_id":"sub","isSidechain":true}' \
  | CLAUDE_PROJECT_DIR="$TC7_DIR" bash "$HOOK_SCRIPT" > /dev/null 2>&1

STATE_TC7="$TC7_DIR/.claude/cost-hint-state.json"
if [ -f "$STATE_TC7" ]; then
  COUNT_TC7=$(python3 -c "
import json
with open('$STATE_TC7') as f:
    d = json.load(f)
print(len(d.get('recent_bash', [])))
" 2>/dev/null)
  if [ -n "$COUNT_TC7" ] && [ "$COUNT_TC7" -gt 0 ]; then
    fail "TC7" "sidechain activity counted in recent_bash (expected 0); got $COUNT_TC7"
  else
    pass "TC7"
  fi
else
  # No state file at all is also acceptable (sidechain exited early, never wrote)
  pass "TC7"
fi
rm -rf "$TC7_DIR"

# ── TC8: malformed JSON input → exit 0, no crash ─────────────────────────────
TC8_DIR=$(mktemp -d)
STDERR_TC8=$(echo "not valid json at all" \
  | CLAUDE_PROJECT_DIR="$TC8_DIR" bash "$HOOK_SCRIPT" 2>&1 1>/dev/null)
EXIT_TC8=$?
if [ $EXIT_TC8 -ne 0 ]; then
  fail "TC8" "malformed JSON crashed hook (exit $EXIT_TC8)"
else
  pass "TC8"
fi
rm -rf "$TC8_DIR"

# ── TC9: command with embedded newlines → safe handling, exit 0 ──────────────
TC9_DIR=$(mktemp -d)
# Multi-line command via Python heredoc-ish injection
NEWLINE_CMD='echo "line1\nline2\nline3" && sqlite3 db.db "SELECT 1"'
STDERR_TC9=$(python3 -c "
import json, subprocess, sys, os
payload = {'tool_input': {'command': '$NEWLINE_CMD'}, 'session_id': 'main', 'isSidechain': False}
env = os.environ.copy()
env['CLAUDE_PROJECT_DIR'] = '$TC9_DIR'
r = subprocess.run(['bash', '$HOOK_SCRIPT'], input=json.dumps(payload), capture_output=True, text=True, env=env)
sys.stderr.write(r.stderr)
sys.exit(r.returncode)
" 2>&1)
EXIT_TC9=$?
if [ $EXIT_TC9 -ne 0 ]; then
  fail "TC9" "embedded-newline command crashed hook (exit $EXIT_TC9)"
else
  pass "TC9"
fi
rm -rf "$TC9_DIR"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ $FAIL -gt 0 ]; then
  exit 1
fi
exit 0
