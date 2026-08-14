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

# ---------------------------------------------------------------------------
# 并发规则的判据（2026-08-14）：从「看见任何 test 就拦」改成「只拦真抢同一样东西的」
#
# 这几条测的是纯函数 `_conflict_reason` / `_contention_key`，不读 live `ps`，
# 所以是确定性的 —— 上面那条「并发规则不在这里断言」的说明只对读 ps 的那部分成立。
echo
echo "── 并发冲突判据"
python3 - "$HOOK_SCRIPT" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("guard", sys.argv[1])
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

IPHONE = "00008140-0001546401FB001C"
IPAD   = "00008027-000165A00A39002E"

def cmd(proj, dev, sim=False):
    plat = "iOS Simulator" if sim else "iOS"
    return f'xcodebuild test -project {proj}.xcodeproj -scheme {proj} -destination "platform={plat},id={dev}"'

cases = [
    # (说明, 新的, 在跑的, 期望拦不拦)
    ("同一个项目 → 拦（build.db 锁共享）",
     cmd("ArtLens", IPHONE), cmd("ArtLens", IPAD), True),
    ("同一台设备 → 拦（一台设备装不下两个 session）",
     cmd("ArtLens", IPHONE), cmd("Lucent", IPHONE), True),
    ("两边都在模拟器 → 拦（CoreSimulator daemon 是全局的）",
     cmd("ArtLens", "AAA", sim=True), cmd("Lucent", "BBB", sim=True), True),
    ("不同项目 + 不同真机 → 放行（三条理由一条都不成立）",
     cmd("ArtLens", IPHONE), cmd("Lucent", IPAD), False),
    ("认不出项目（没写 -project） → 保守拦",
     'xcodebuild test -scheme ArtLens -destination "platform=iOS,id=%s"' % IPHONE,
     cmd("Lucent", IPAD), True),
    ("一边真机一边模拟器、不同项目 → 放行",
     cmd("ArtLens", IPHONE), cmd("Lucent", "BBB", sim=True), False),
]

bad = 0
for name, new, old, want_block in cases:
    why = g._conflict_reason(g._contention_key(new), g._contention_key(old))
    got = why is not None
    ok = got == want_block
    bad += 0 if ok else 1
    print(f"  {'✅' if ok else '❌'} {name}" + (f"　→ {why}" if why else "　→ 放行"))
sys.exit(1 if bad else 0)
PY
if [ $? -eq 0 ]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); fi
