#!/usr/bin/env bash
set -e
HOOK="$(cd "$(dirname "$0")" && pwd)/../hooks/pre-tool-use.sh"
TMPDIR=$(mktemp -d); trap "rm -rf $TMPDIR" EXIT
STATE="$TMPDIR/.claude/readback-state.json"
mkdir -p "$(dirname "$STATE")"
PASS=0; FAIL=0

# fresh / old timestamp helpers (BSD vs GNU date)
FRESH_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
OLD_TS=$( (date -u -v-35M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null) \
         || (date -u -d "35 minutes ago" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null) )

run_case() {
  local desc="$1" tool="$2" skill_val="$3" confirmed="$4" expect_decision="$5" \
        stored_sid="${6:-test}" created_at="${7:-$FRESH_TS}"
  local state_content="{}"
  if [ -n "$skill_val" ]; then
    state_content=$(jq -n --arg s "$skill_val" --argjson c "$confirmed" \
                       --arg sid "$stored_sid" --arg ts "$created_at" \
      '{session_id: $sid, created_at: $ts, skill: $s, readback_done: true, user_confirmed: $c}')
  fi
  echo "$state_content" > "$STATE"

  local input out got
  # session_id arrives via stdin (Claude Code hook contract), matches stored_sid="test"
  input=$(jq -n --arg t "$tool" '{tool_name: $t, tool_input: {}, session_id: "test"}')
  out=$(cd "$TMPDIR" && echo "$input" | bash "$HOOK")
  got=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecision // "pass"')

  if [ "$got" = "$expect_decision" ]; then
    echo "  ✓ $desc"; PASS=$((PASS+1))
  else
    echo "  ✗ $desc — expected $expect_decision, got $got"; FAIL=$((FAIL+1))
  fi
}

# Specialized case for stamping verification (checks state file mutation post-hook)
run_stamp_case() {
  local desc="$1"
  # State: confirmed=true, session_id=null → first read should stamp "test"
  jq -n --arg ts "$FRESH_TS" \
    '{session_id: null, created_at: $ts, skill: "fix-bug", readback_done: true, user_confirmed: true}' \
    > "$STATE"
  local input out got stamped
  input=$(jq -n '{tool_name: "Write", tool_input: {}, session_id: "test"}')
  out=$(cd "$TMPDIR" && echo "$input" | bash "$HOOK")
  got=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecision // "pass"')
  stamped=$(jq -r '.session_id // empty' "$STATE" 2>/dev/null)
  if [ "$got" = "pass" ] && [ "$stamped" = "test" ]; then
    echo "  ✓ $desc"; PASS=$((PASS+1))
  else
    echo "  ✗ $desc — expected pass+stamped=test, got=$got, stamped=$stamped"; FAIL=$((FAIL+1))
  fi
}

echo "Test: pre-tool-use hook"
# State file is reset per case (rm before each)
rm -f "$STATE"; run_case "state missing — allow (pass)" "Write" "" "false" "pass"
run_case "state present, skill=write-plan — allow" "Write" "write-plan" "false" "pass"
run_case "state present, skill=fix-bug, confirmed=true — allow" "Write" "fix-bug" "true" "pass"
run_case "state present, skill=fix-bug, confirmed=false (fresh) — deny" "Write" "fix-bug" "false" "deny"
run_case "non-Write tool (Read) — allow" "Read" "fix-bug" "false" "pass"
# Session-id mismatch — confirmed state from prior session → treat as fresh (allow)
run_case "confirmed + stale session_id — allow (different session)" "Write" "fix-bug" "true" "pass" "different-old-session"
# Schema v2: new cases
run_case "pending state past TTL (35 min old) — allow" "Write" "fix-bug" "false" "pass" "" "$OLD_TS"
run_case "NotebookEdit triggers matcher — deny when unconfirmed fix-bug" "NotebookEdit" "fix-bug" "false" "deny"
run_case "residual unknown sid (v1 schema) — allow (confirmed treated as same-session)" "Write" "fix-bug" "true" "pass" "unknown"
run_stamp_case "confirmed state, first stamp of null sid — allow + mutate state"

echo
echo "Passed: $PASS, Failed: $FAIL"
[ "$FAIL" -eq 0 ]
