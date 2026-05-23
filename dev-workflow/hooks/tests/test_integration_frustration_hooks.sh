#!/bin/bash
set -u

# Trap cleanup: remove integration-test fixture.
cleanup() {
    rm -f /tmp/integration-test-log.log 2>/dev/null || true
}
trap cleanup EXIT INT TERM

HOOK_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_SRC="${HOOK_DIR}/nudge-named-source.py"
HOOK_BFG="${HOOK_DIR}/bug-fix-gate.py"
FIXTURES="$(dirname "$0")/fixtures"

touch /tmp/integration-test-log.log

INPUT=$(python3 -c "
import json
print(json.dumps({
    'transcript_path': '${FIXTURES}/transcript_combined.jsonl',
    'tool_name': 'Edit',
    'tool_input': {'file_path': '/tmp/unrelated.swift'},
    'isSidechain': False,
    'hook_event_name': 'PreToolUse'
}))
")

OUT_SRC=$(echo "$INPUT" | python3 "$HOOK_SRC" 2>&1 >/dev/null)
RC_SRC=$?
OUT_BFG=$(echo "$INPUT" | python3 "$HOOK_BFG" 2>&1 >/dev/null)
RC_BFG=$?

PASS=0; FAIL=0

if [ "$RC_SRC" -eq 0 ] && echo "$OUT_SRC" | grep -q "source-hint"; then
    echo "PASS: nudge-named-source emits source-hint, exit 0"
    PASS=$((PASS+1))
else
    echo "FAIL: nudge-named-source (rc=$RC_SRC, out=$OUT_SRC)"
    FAIL=$((FAIL+1))
fi

if [ "$RC_BFG" -eq 0 ] && echo "$OUT_BFG" | grep -q "fix-suggest"; then
    echo "PASS: bug-fix-gate emits fix-suggest (soft mode), exit 0"
    PASS=$((PASS+1))
else
    echo "FAIL: bug-fix-gate (rc=$RC_BFG, out=$OUT_BFG)"
    FAIL=$((FAIL+1))
fi

# Additional: existing hooks shouldn't be triggered by this Edit call structure
# (suggest-agent-dispatch matches Bash, suggest-read-routing matches Read)
# We don't need to invoke them — confirming they don't share the matcher.

# Verify hooks.json has both new entries
if grep -q "nudge-named-source.py" "${HOOK_DIR}/hooks.json" && \
   grep -q "bug-fix-gate.py" "${HOOK_DIR}/hooks.json"; then
    echo "PASS: hooks.json registers both new hooks"
    PASS=$((PASS+1))
else
    echo "FAIL: hooks.json missing one or both registrations"
    FAIL=$((FAIL+1))
fi

echo ""
echo "Total: $((PASS+FAIL)), Pass: $PASS, Fail: $FAIL"
[ "$FAIL" -gt 0 ] && exit 1 || exit 0
