#!/usr/bin/env bash
set -e
HOOK="$(cd "$(dirname "$0")" && pwd)/../hooks/post-tool-use.sh"
PASS=0; FAIL=0

run_case() {
  local desc="$1" input="$2" expect="$3"
  local out got
  out=$(echo "$input" | bash "$HOOK")
  if [ "$expect" = "reminder" ]; then
    got=$(echo "$out" | jq -r '.hookSpecificOutput.additionalContext // empty' | grep -c "readback-paste-reminder" || true)
    if [ "$got" -ge 1 ]; then
      echo "  ✓ $desc"; PASS=$((PASS+1))
    else
      echo "  ✗ $desc — expected reminder, got: $out"; FAIL=$((FAIL+1))
    fi
  else
    got=$(echo "$out" | jq -c '.')
    if [ "$got" = "{}" ]; then
      echo "  ✓ $desc"; PASS=$((PASS+1))
    else
      echo "  ✗ $desc — expected {}, got: $out"; FAIL=$((FAIL+1))
    fi
  fi
}

echo "== post-tool-use.sh =="
run_case "fires for intent-echoer" \
  '{"tool_name":"Agent","tool_input":{"subagent_type":"intent-echoer"}}' \
  "reminder"
run_case "fires for plugin-qualified readback:intent-echoer" \
  '{"tool_name":"Agent","tool_input":{"subagent_type":"readback:intent-echoer"}}' \
  "reminder"
run_case "fires for Task tool name variant" \
  '{"tool_name":"Task","tool_input":{"subagent_type":"intent-echoer"}}' \
  "reminder"
run_case "skips other agent type" \
  '{"tool_name":"Agent","tool_input":{"subagent_type":"Explore"}}' \
  "pass"
run_case "skips when subagent_type absent" \
  '{"tool_name":"Agent","tool_input":{}}' \
  "pass"
run_case "skips non-Agent tool" \
  '{"tool_name":"Edit","tool_input":{"subagent_type":"intent-echoer"}}' \
  "pass"
run_case "skips empty input" \
  '{}' \
  "pass"

echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
