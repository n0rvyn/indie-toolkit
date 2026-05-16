#!/usr/bin/env bash
# Test harness for user-prompt-submit hook
set -e

HOOK="$(cd "$(dirname "$0")" && pwd)/../hooks/user-prompt-submit.sh"
PASS=0; FAIL=0

# NOTE: fixture builds {prompt: $p, session_id: ...} to match real Claude Code
# UserPromptSubmit stdin schema (the prompt field name; verified earlier).
run_case() {
  local desc="$1" prompt="$2" expect_mandate="$3" state_fixture="${4:-}"
  local input out has_mandate
  if [ -n "$state_fixture" ]; then
    # Write state fixture to a tmpdir cwd so the hook reads it as project state
    local td
    td=$(mktemp -d)
    mkdir -p "$td/.claude"
    echo "$state_fixture" > "$td/.claude/readback-state.json"
    input=$(jq -n --arg p "$prompt" '{prompt: $p, session_id: "test-current-session"}')
    out=$(cd "$td" && echo "$input" | bash "$HOOK")
    rm -rf "$td"
  else
    input=$(jq -n --arg p "$prompt" '{prompt: $p, session_id: "test-current-session"}')
    out=$(echo "$input" | bash "$HOOK")
  fi
  has_mandate=$(echo "$out" | jq -r '.hookSpecificOutput.additionalContext // empty' | grep -c "readback-mandate" || true)
  if [ "$has_mandate" -eq "$expect_mandate" ]; then
    echo "  ✓ $desc"; PASS=$((PASS+1))
  else
    echo "  ✗ $desc — expected mandate=$expect_mandate, got=$has_mandate"; FAIL=$((FAIL+1))
  fi
}

FRESH_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo "Test: user-prompt-submit hook"
run_case "action verb 'fix' triggers mandate" "fix the bug in BillImportView import flow" 1
run_case "question without action — no mandate" "how does the import flow work?" 0
run_case "orchestration command — no mandate" "/run-phase" 0
run_case "trivial verb 'rename' — no mandate" "rename BillService to ImportService" 0
run_case "explicit bypass 'go' — no mandate" "go" 0
run_case "Chinese '修' triggers mandate" "修一下账单导入的报错" 1
run_case "malformed json input — fail-open (no mandate, no error)" "" 0
# Schema v2: state-aware short-circuit cases
run_case "action verb 'fix' with confirmed-state matching session — no mandate (L1: post-stamp window)" \
  "fix the bug in BillImportView" 0 \
  "$(jq -n --arg ts "$FRESH_TS" '{session_id: "test-current-session", created_at: $ts, skill: "fix-bug", user_confirmed: true}')"
run_case "action verb 'fix' with confirmed-state and null stored sid — no mandate (L1: pre-stamp window)" \
  "fix the bug" 0 \
  "$(jq -n --arg ts "$FRESH_TS" '{session_id: null, created_at: $ts, skill: "fix-bug", user_confirmed: true}')"
run_case "action verb 'fix' with confirmed-state but different stored sid — mandate (cross-session)" \
  "fix the bug" 1 \
  "$(jq -n --arg ts "$FRESH_TS" '{session_id: "different-old-session", created_at: $ts, skill: "fix-bug", user_confirmed: true}')"

echo
echo "Passed: $PASS, Failed: $FAIL"
[ "$FAIL" -eq 0 ]
