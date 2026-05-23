#!/bin/bash
# Test harness for nudge-named-source.py PreToolUse hook
set -u

# Trap cleanup: remove /tmp fixtures this test created. Idempotent.
cleanup() {
    rm -f /tmp/test-fixture-existing-file.log /tmp/test-fixture-already-read.log 2>/dev/null || true
}
trap cleanup EXIT INT TERM

HOOK_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_SCRIPT="${HOOK_DIR}/nudge-named-source.py"
FIXTURES="$(dirname "$0")/fixtures"

# Setup: create the "existing" path fixture
touch /tmp/test-fixture-existing-file.log
touch /tmp/test-fixture-already-read.log

PASS=0
FAIL=0

run_case() {
    local name="$1"
    local transcript="$2"
    local tool_name="$3"
    local tool_input_json="$4"
    local expect_stderr_contains="$5"
    local expect_exit="$6"

    local input_json=$(python3 -c "
import json
print(json.dumps({
    'transcript_path': '${transcript}',
    'tool_name': '${tool_name}',
    'tool_input': ${tool_input_json},
    'isSidechain': False,
    'hook_event_name': 'PreToolUse'
}))
")
    local stderr_output
    local exit_code
    stderr_output=$(echo "$input_json" | python3 "$HOOK_SCRIPT" 2>&1 >/dev/null)
    exit_code=$?

    if [ "$exit_code" -eq "$expect_exit" ] && echo "$stderr_output" | grep -q "$expect_stderr_contains"; then
        echo "PASS: $name"
        PASS=$((PASS+1))
    else
        echo "FAIL: $name (exit=$exit_code, stderr=$stderr_output, expected_exit=$expect_exit, expected_stderr~$expect_stderr_contains)"
        FAIL=$((FAIL+1))
    fi
}

# Case 1: user mentioned path, model going to Edit something else → nudge expected
run_case "nudge-when-path-unread-and-edit-other" \
    "${FIXTURES}/transcript_user_with_path.jsonl" \
    "Edit" \
    '{"file_path": "/tmp/unrelated.txt"}' \
    "source-hint" \
    0

# Case 2: user didn't mention path → no nudge
run_case "no-nudge-when-no-path-in-message" \
    "${FIXTURES}/transcript_user_no_path.jsonl" \
    "Edit" \
    '{"file_path": "/tmp/anything.txt"}' \
    "^$" \
    0

# Case 3: user mentioned path, model already read it → no nudge
run_case "no-nudge-when-path-already-read" \
    "${FIXTURES}/transcript_user_path_already_read.jsonl" \
    "Edit" \
    '{"file_path": "/tmp/unrelated.txt"}' \
    "^$" \
    0

# Case 4: user mentioned path, current tool call IS reading it → no nudge
run_case "no-nudge-when-current-call-reads-it" \
    "${FIXTURES}/transcript_user_with_path.jsonl" \
    "Bash" \
    '{"command": "cat /tmp/test-fixture-existing-file.log"}' \
    "^$" \
    0

echo ""
echo "Total: $((PASS+FAIL)), Pass: $PASS, Fail: $FAIL"
if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
