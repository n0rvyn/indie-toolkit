#!/bin/bash
set -u

# Regression for bug-fix-gate against the "combined" transcript fixture — a
# transcript that carries BOTH a bug-shaped user message and a named source path.
#
# History: this file used to assert on nudge-named-source.py as well. That hook's
# rule source is the global CLAUDE.md (「用户原文指定的信息源 = 第一优先级」), not
# any dev-workflow skill, so on 2026-09-05 it moved to ~/.claude/hooks/ and its
# half of this file moved with it (~/.claude/hooks/tests/test-nudge-named-source-combined.sh).
# The two hooks no longer share a registration file, so the old
# "hooks.json registers both" assertion was replaced by a single-hook check.

cleanup() {
    rm -f /tmp/integration-test-log.log 2>/dev/null || true
}
trap cleanup EXIT INT TERM

HOOK_DIR="$(cd "$(dirname "$0")/.." && pwd)"
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

OUT_BFG=$(echo "$INPUT" | python3 "$HOOK_BFG" 2>&1 >/dev/null)
RC_BFG=$?

PASS=0; FAIL=0

if [ "$RC_BFG" -eq 0 ] && echo "$OUT_BFG" | grep -q "fix-suggest"; then
    echo "PASS: bug-fix-gate emits fix-suggest (soft mode), exit 0"
    PASS=$((PASS+1))
else
    echo "FAIL: bug-fix-gate (rc=$RC_BFG, out=$OUT_BFG)"
    FAIL=$((FAIL+1))
fi

if grep -q "bug-fix-gate.py" "${HOOK_DIR}/hooks.json"; then
    echo "PASS: hooks.json registers bug-fix-gate"
    PASS=$((PASS+1))
else
    echo "FAIL: hooks.json missing bug-fix-gate registration"
    FAIL=$((FAIL+1))
fi

echo ""
echo "Total: $((PASS+FAIL)), Pass: $PASS, Fail: $FAIL"
[ "$FAIL" -gt 0 ] && exit 1 || exit 0
