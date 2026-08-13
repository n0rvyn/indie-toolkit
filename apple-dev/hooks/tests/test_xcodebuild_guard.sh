#!/bin/bash
set -u

# Tests for xcodebuild-guard.py's two false-positive control layers.
#
# The regression that motivated this file (2026-08-10, CleanLabel): the guard
# split the command on newlines, so every line of a `python3 - <<'EOF'` heredoc
# body became a "shell segment". Writing a doc/plan/knowledge entry that quoted
# `xcodebuild test …` was denied twice as if it were a real invocation.
#
# Deterministic cases only: the concurrent-run rule reads live `ps`, so it is
# deliberately NOT asserted here (it would pass or fail depending on what else
# is running on the machine).

HOOK_SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/xcodebuild-guard.py"

PASS=0
FAIL=0

# run_case <name> <command> <expect: deny|ask|none>
run_case() {
    local name="$1" command="$2" expect="$3"

    local input_json
    input_json=$(COMMAND="$command" python3 -c "
import json, os
print(json.dumps({
    'tool_name': 'Bash',
    'tool_input': {'command': os.environ['COMMAND']},
    'hook_event_name': 'PreToolUse',
}))
")

    local stdout_output actual
    stdout_output=$(printf '%s' "$input_json" | python3 "$HOOK_SCRIPT" 2>/dev/null)

    if [ -z "$stdout_output" ]; then
        actual="none"
    else
        actual=$(OUT="$stdout_output" python3 -c "
import json, os
try:
    d = json.loads(os.environ['OUT'])
    print(d['hookSpecificOutput']['permissionDecision'])
except Exception:
    print('unparseable')
")
    fi

    if [ "$actual" = "$expect" ]; then
        echo "  ✅ $name (expect=$expect)"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $name — expected '$expect', got '$actual'"
        FAIL=$((FAIL + 1))
    fi
}

echo "== layer a: heredoc bodies are not shell =="

# The exact shape that was denied twice on 2026-08-10.
run_case "heredoc body quoting the command is not an invocation" \
"python3 - <<'PYEOF'
import pathlib
body = '''
xcodebuild test -scheme CleanLabel -destination \"platform=iOS,id=00008140\"
'''
pathlib.Path('doc.md').write_text(body)
PYEOF" \
"none"

run_case "unquoted heredoc delimiter also strips" \
"cat > notes.md <<EOF
xcodebuild test -destination 'platform=iOS Simulator,name=iPhone 16'
EOF" \
"none"

run_case "<<- (tab-indented) heredoc strips" \
"cat > notes.md <<-EOF
	xcodebuild test -scheme X
	EOF" \
"none"

run_case "real invocation AFTER a heredoc still evaluated" \
"cat > notes.md <<'EOF'
just prose
EOF
xcodebuild test -scheme X -destination 'platform=iOS Simulator,name=iPhone 16'" \
"deny"

echo "== layer b: first-token control (pre-existing) =="

run_case "echo mentioning the command" \
'echo "xcodebuild test -destination name=iPhone 16"' \
"none"

run_case "grep for a name= destination" \
"grep -rn 'destination.*name=' ." \
"none"

echo "== rules still fire on genuine invocations =="

run_case "name= destination is denied" \
"xcodebuild test -scheme CleanLabel -destination 'platform=iOS Simulator,name=iPhone 16'" \
"deny"

run_case "name= denied even behind cd &&" \
"cd /tmp && xcodebuild test -scheme X -destination \"platform=iOS Simulator,name=iPhone 16\"" \
"deny"

run_case "simctl boot asks for approval" \
"xcrun simctl boot ABC-123" \
"ask"

run_case "build-for-testing is not a test run" \
"xcodebuild build-for-testing -scheme X -destination 'platform=iOS Simulator,name=iPhone 16'" \
"none"

echo
echo "Passed: $PASS   Failed: $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
