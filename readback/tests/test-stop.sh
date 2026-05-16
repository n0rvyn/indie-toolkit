#!/usr/bin/env bash
set -e
HOOK="$(cd "$(dirname "$0")" && pwd)/../hooks/stop.sh"
TMPDIR=$(mktemp -d); trap "rm -rf $TMPDIR" EXIT
TRANS="$TMPDIR/transcript.jsonl"
STATE="$TMPDIR/.claude/readback-state.json"
mkdir -p "$(dirname "$STATE")"
PASS=0; FAIL=0

# fresh / old timestamp helpers (BSD vs GNU date)
FRESH_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
OLD_TS=$( (date -u -v-35M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null) \
         || (date -u -d "35 minutes ago" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null) )

# Build a jsonl fixture with N user/assistant turns; last assistant turn has
# `last_turn_writes` Write tool_use blocks. Earlier turns add noise tool_use
# blocks to verify the hook does NOT count them.
build_transcript() {
  local last_turn_writes="$1" earlier_writes="${2:-0}"
  : > "$TRANS"
  # First turn: user + assistant with $earlier_writes Write blocks (noise)
  echo '{"type":"user","message":{"content":"earlier"}}' >> "$TRANS"
  local earlier_content="[]"
  if [ "$earlier_writes" -gt 0 ]; then
    earlier_content=$(jq -n --argjson n "$earlier_writes" \
      '[range(0; $n) | {type: "tool_use", name: "Write", input: {}}]')
  fi
  jq -nc --argjson c "$earlier_content" \
    '{type: "assistant", message: {content: $c}}' >> "$TRANS"
  # Second turn: user + LAST assistant with $last_turn_writes Write blocks
  echo '{"type":"user","message":{"content":"later"}}' >> "$TRANS"
  local last_content="[]"
  if [ "$last_turn_writes" -gt 0 ]; then
    last_content=$(jq -n --argjson n "$last_turn_writes" \
      '[range(0; $n) | {type: "tool_use", name: "Write", input: {}}]')
  fi
  jq -nc --argjson c "$last_content" \
    '{type: "assistant", message: {content: $c}}' >> "$TRANS"
}

run_case() {
  local desc="$1" last_writes="$2" earlier_writes="$3" skill_val="$4" confirmed="$5" \
        expect_warn="$6" stored_sid="${7:-test}" created_at="${8:-$FRESH_TS}"
  build_transcript "$last_writes" "$earlier_writes"
  if [ -n "$skill_val" ]; then
    jq -n --arg s "$skill_val" --argjson c "$confirmed" --arg sid "$stored_sid" --arg ts "$created_at" \
      '{session_id: $sid, created_at: $ts, skill: $s, user_confirmed: $c}' > "$STATE"
  else
    rm -f "$STATE"
  fi
  local input out has_warn
  # session_id arrives via stdin (Claude Code hook contract)
  input=$(jq -n --arg p "$TRANS" '{transcript_path: $p, session_id: "test"}')
  out=$(cd "$TMPDIR" && echo "$input" | bash "$HOOK")
  has_warn=$(echo "$out" | jq -r '.hookSpecificOutput.additionalContext // empty' | grep -c "readback-warning" || true)
  if [ "$has_warn" -eq "$expect_warn" ]; then
    echo "  ✓ $desc"; PASS=$((PASS+1))
  else
    echo "  ✗ $desc — expected warn=$expect_warn, got=$has_warn"; FAIL=$((FAIL+1))
  fi
}

echo "Test: stop hook"
run_case "1 write last turn — no warn" 1 0 "" false 0
run_case "5 writes last turn, no state — warn" 5 0 "" false 1
run_case "5 writes last turn, fix-bug confirmed (matching sid) — no warn" 5 0 "fix-bug" true 0
run_case "5 writes last turn, run-phase — no warn" 5 0 "run-phase" false 0
# Critical: earlier turns had many writes; this turn has only 1 → no warn
run_case "1 write last + 10 earlier (cumulative) — no warn (turn-aware)" 1 10 "" false 0
# Stale session: state from prior session ignored → treat as fresh → warn
run_case "stale session_id + 5 writes — warn (state ignored)" 5 0 "fix-bug" true 1 "different-old-session"
# Schema v2: new cases
run_case "pending state past TTL + 5 writes — warn (treated as no-readback)" 5 0 "fix-bug" false 1 "test" "$OLD_TS"
run_case "residual unknown sid + 5 writes confirmed — no warn (v1 backward compat)" 5 0 "fix-bug" true 0 "unknown"

echo
echo "Passed: $PASS, Failed: $FAIL"
[ "$FAIL" -eq 0 ]
