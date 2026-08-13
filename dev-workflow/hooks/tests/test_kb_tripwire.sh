#!/bin/bash
set -u

# Tests for kb-tripwire.py.
#
# The wire only earns its place if it fires on the real 2026-08-10 regressions and
# stays silent on everything adjacent. Both directions are asserted here; the
# silent-direction cases are the ones that keep the nudge from becoming noise.

HOOK_SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/kb-tripwire.py"
TMP=$(mktemp -d)
STATE="$HOME/.claude/.kb-tripwire"

cleanup() { rm -rf "$TMP"; rm -f "$STATE"/test-session-*.* 2>/dev/null || true; }
trap cleanup EXIT INT TERM
cleanup_state() { rm -f "$STATE"/test-session-*.* 2>/dev/null || true; }

PASS=0
FAIL=0

# run_case <name> <session> <tool> <file_path> <payload> <expect_substring|"">
run_case() {
    local name="$1" session="$2" tool="$3" fpath="$4" payload="$5" expect="$6"

    local input_json
    input_json=$(SESSION="$session" TOOL="$tool" FPATH="$fpath" PAYLOAD="$payload" python3 -c "
import json, os
tool = os.environ['TOOL']
key = 'content' if tool == 'Write' else 'new_string'
print(json.dumps({
    'session_id': os.environ['SESSION'],
    'tool_name': tool,
    'tool_input': {'file_path': os.environ['FPATH'], key: os.environ['PAYLOAD']},
    'hook_event_name': 'PreToolUse',
}))
")
    local err
    err=$(printf '%s' "$input_json" | python3 "$HOOK_SCRIPT" 2>&1 >/dev/null)

    if [ -z "$expect" ]; then
        if [ -z "$err" ]; then
            echo "  ✅ $name (silent)"; PASS=$((PASS + 1))
        else
            echo "  ❌ $name — expected silence, got: ${err:0:80}"; FAIL=$((FAIL + 1))
        fi
    else
        if printf '%s' "$err" | grep -q "$expect"; then
            echo "  ✅ $name (fired)"; PASS=$((PASS + 1))
        else
            echo "  ❌ $name — expected nudge containing '$expect', got: ${err:0:80}"; FAIL=$((FAIL + 1))
        fi
    fi
}

echo "== fires on the real 2026-08-10 regressions =="
cleanup_state

run_case "let + default value (memberwise init)" test-session-a Edit "$TMP/ScanFlowView.swift" \
'    let onResultForComparison: ((ParseResult) -> Void)? = nil' \
"memberwise"

cleanup_state
run_case "@Test with no enclosing suite" test-session-b Write "$TMP/FooTests.swift" \
'import Testing

@Test func 添加剂计数() {
    #expect(1 == 1)
}' \
"totalTestCount"

cleanup_state
run_case "import Testing inside a UITests path" test-session-c Write "$TMP/CleanLabelUITests/BarUITests.swift" \
'import Testing' \
"XCUITest"

cleanup_state
run_case "LazyVStack a11y hole" test-session-d Edit "$TMP/View.swift" \
'        LazyVStack(spacing: 0) {' \
"可访问性"

echo "== stays silent where it must =="
cleanup_state

run_case "var + default value is the correct form" test-session-e Edit "$TMP/View.swift" \
'    var onResult: ((Int) -> Void)? = nil' \
""

cleanup_state
run_case "@Test already inside a suite" test-session-f Write "$TMP/BarTests.swift" \
'import Testing

struct BarTests {
    @Test func ok() { #expect(true) }
}' \
""

cleanup_state
run_case "prose file quoting the pattern (markdown)" test-session-g Write "$TMP/notes.md" \
'    let onTap: (() -> Void)? = nil   // 这段是文档在讲这个坑' \
""

cleanup_state
run_case "knowledge base entry itself" test-session-h Write "$HOME/.claude/knowledge/x/y.md" \
'LazyVStack 会漏 a11y' \
""

cleanup_state
run_case "import Testing in a normal unit-test path" test-session-i Write "$TMP/CleanLabelTests/BarTests.swift" \
'import Testing

struct BarTests { @Test func ok() {} }' \
""

cleanup_state
run_case "non-Swift file with a similar-looking line" test-session-j Write "$TMP/config.ts" \
'const onTap: (() => void) | null = null' \
""

echo "== one nudge per wire per session =="
cleanup_state
run_case "first edit fires" test-session-k Edit "$TMP/A.swift" \
'    let cb: (() -> Void)? = nil' \
"memberwise"
run_case "second edit, same session, stays quiet" test-session-k Edit "$TMP/B.swift" \
'    let cb2: (() -> Void)? = nil' \
""
run_case "different session fires again" test-session-l Edit "$TMP/C.swift" \
'    let cb3: (() -> Void)? = nil' \
"memberwise"

echo
echo "Passed: $PASS   Failed: $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
