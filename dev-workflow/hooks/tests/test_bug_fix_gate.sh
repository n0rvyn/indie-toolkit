#!/bin/bash
set -u

# Trap cleanup: remove fixture files this test may have touched on /tmp.
# Idempotent — also runs at script start to clear stale state from prior runs.
cleanup() {
    rm -f /tmp/test-fixture-bug-fix-gate-*.log 2>/dev/null || true
}
trap cleanup EXIT INT TERM
cleanup

HOOK_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_SCRIPT="${HOOK_DIR}/bug-fix-gate.py"
FIXTURES="$(dirname "$0")/fixtures"

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
        echo "FAIL: $name (exit=$exit_code, stderr=$stderr_output, expected=$expect_exit/$expect_stderr_contains)"
        FAIL=$((FAIL+1))
    fi
}

# Case 1: pure-CJK bug + no block + /fix-bug NOT active → soft (validates CJK-safe BUG_PATTERN)
run_case "soft-pure-cjk-bug-no-block" \
    "${FIXTURES}/transcript_bug_no_block.jsonl" \
    "Edit" '{"file_path": "/tmp/some.swift"}' \
    "fix-suggest" 0

# Case 2: bug + half-width-colon block → no fire
run_case "no-fire-half-width-colon-block" \
    "${FIXTURES}/transcript_bug_with_block.jsonl" \
    "Edit" '{"file_path": "/tmp/some.swift"}' \
    "^$" 0

# Case 3: bug + /fix-bug active + no block → hard
run_case "hard-when-fixbug-active-no-block" \
    "${FIXTURES}/transcript_bug_fix_bug_active.jsonl" \
    "Edit" '{"file_path": "/tmp/some.swift"}' \
    "fix-gate" 2

# Case 3b: same, but recorded the way Claude Code actually records a plugin skill —
# `/dev-workflow:fix-bug`, not the bare name. This is the real invocation form.
run_case "hard-when-fixbug-active-namespaced" \
    "${FIXTURES}/transcript_bug_fix_bug_active_namespaced.jsonl" \
    "Edit" '{"file_path": "/tmp/some.swift"}' \
    "fix-gate" 2

# Case 4: non-bug user message → no fire
run_case "no-fire-on-non-bug-message" \
    "${FIXTURES}/transcript_non_bug.jsonl" \
    "Edit" '{"file_path": "/tmp/some.swift"}' \
    "^$" 0

# Case 5: bug reported but Edit already happened → skip rule
run_case "no-fire-after-first-edit" \
    "${FIXTURES}/transcript_bug_already_edited.jsonl" \
    "Edit" '{"file_path": "/tmp/other.swift"}' \
    "^$" 0

# Case 6: bug + full-width-colon block → no fire (validates BLOCK_PATTERN colon flexibility)
run_case "no-fire-full-width-colon-block" \
    "${FIXTURES}/transcript_bug_with_block_fullwidth_colon.jsonl" \
    "Edit" '{"file_path": "/tmp/some.swift"}' \
    "^$" 0

# Case 7: casual meta-mention of /fix-bug → must NOT trigger HARD (regression test for false-positive).
# SOFT mode IS allowed to fire here — the fixture contains "/fix-bug" which BUG_PATTERNS[6]'s \bfix\b
# matches (word boundaries at / and -), and this SOFT false-positive is an accepted cost of the
# broader repair-verb regex per must-revise #2. The critical assertion is the HARD non-fire (exit 0).
run_case "no-hard-on-fixbug-meta-mention" \
    "${FIXTURES}/transcript_fixbug_meta_mention.jsonl" \
    "Edit" '{"file_path": "dev-workflow/skills/fix-bug/SKILL.md"}' \
    "fix-suggest" 0

echo ""
echo "Total: $((PASS+FAIL)), Pass: $PASS, Fail: $FAIL"
[ "$FAIL" -gt 0 ] && exit 1 || exit 0
