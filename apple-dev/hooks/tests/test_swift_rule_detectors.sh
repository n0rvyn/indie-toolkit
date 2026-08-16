#!/bin/bash
# Test harness for swift-rule-detectors.py PreToolUse hook.
#
# Each case reproduces the shape of real Swift source, not a paraphrase: a case
# that does not actually contain the trigger token tests nothing and passes no
# matter what the hook does (see
# ~/.claude/knowledge/workflow/2026-08-16-paraphrased-failing-input-makes-test-vacuous.md).
set -u

HOOK="$(cd "$(dirname "$0")/.." && pwd)/swift-rule-detectors.py"
PASS=0
FAIL=0
SID=0

# run <name> <tool> <file_path> <content> <expect substring|NONE>
run() {
    local name="$1" tool="$2" fpath="$3" content="$4" expect="$5"
    SID=$((SID+1))
    local input out
    input=$(python3 -c "
import json,sys
tool, fpath, content, sid = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
key = 'content' if tool == 'Write' else 'new_string'
print(json.dumps({'tool_name': tool, 'session_id': sid,
                  'tool_input': {'file_path': fpath, key: content}}))
" "$tool" "$fpath" "$content" "test-$SID-$RANDOM")
    local __err
    __err=$(mktemp)
    out=$(printf '%s' "$input" | python3 "$HOOK" 2>"$__err" >/dev/null)
    if grep -q 'Traceback\|SyntaxError\|IndentationError' "$__err" 2>/dev/null; then
        echo "  FAIL: $name — hook crashed: $(head -1 "$__err")"; FAIL=$((FAIL+1)); rm -f "$__err"; return
    fi
    # the hook nudges on stderr, so stderr IS the output under test
    out=$(cat "$__err" 2>/dev/null)
    rm -f "$__err"
    if [ "$expect" = "NONE" ]; then
        if [ -z "$out" ]; then echo "  PASS: $name (silent)"; PASS=$((PASS+1))
        else echo "  FAIL: $name — expected silence, got: $out"; FAIL=$((FAIL+1)); fi
    else
        if printf '%s' "$out" | grep -q "$expect"; then echo "  PASS: $name"; PASS=$((PASS+1))
        else echo "  FAIL: $name — expected '$expect', got: ${out:-<empty>}"; FAIL=$((FAIL+1)); fi
    fi
}

echo "=== swift-rule-detectors.py ==="

# --- scope -------------------------------------------------------------------
run "non-swift file is ignored" Write "/p/README.md" \
    'struct X { var body: some View { Text("x").background(.red) } }' NONE
run "empty content is ignored" Write "/p/A.swift" "" NONE

# --- 容器宽度意图: trigger is the reference's own container tokens -------------
run "background() marks a visual container" Write "/p/Card.swift" \
    'struct Card: View { var body: some View { VStack { Text("hi") }.background(Color.gray) } }' \
    "容器宽度意图"
run "strokeBorder-only card also counts" Edit "/p/Card.swift" \
    '.overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Color.gray))' \
    "容器宽度意图"
run "plain view without container tokens stays silent" Write "/p/Plain.swift" \
    'struct Plain: View { var body: some View { Text("just text") } }' NONE

# --- 按钮组同宽: two Buttons in one row --------------------------------------
run "two Buttons in an HStack trigger the width section" Write "/p/Bar.swift" \
    'HStack { Button("取消") { }; Button("确定") { } }' \
    "容器宽度意图"

# --- 测试框架 -----------------------------------------------------------------
run "@Test attribute triggers testing section" Write "/p/FooTests.swift" \
    'import Testing
@Test func works() { #expect(1 == 1) }' \
    "测试框架与文件放置"
run "XCTestCase triggers testing section" Write "/p/Legacy.swift" \
    'import XCTest
final class LegacyTests: XCTestCase { }' \
    "测试框架与文件放置"
run "a *Tests.swift path triggers even without a framework token" Write "/p/EmptyTests.swift" \
    'struct Placeholder { }' \
    "测试框架与文件放置"

# --- 同一动作控件 --------------------------------------------------------------
run "dismiss() triggers the control-consistency section" Write "/p/Sheet.swift" \
    '@Environment(\.dismiss) private var dismiss
Button("x") { dismiss() }' \
    "同一动作的控件形制一致"
run "a 返回 label triggers it" Write "/p/Nav.swift" \
    'Button("返回") { go() }' \
    "同一动作的控件形制一致"
run "navigationBarBackButtonHidden triggers it" Edit "/p/Nav.swift" \
    '.navigationBarBackButtonHidden(true)' \
    "同一动作的控件形制一致"

# --- 锁方向 -------------------------------------------------------------------
run "supportedInterfaceOrientations triggers the orientation section" Edit "/p/AppDelegate.swift" \
    'func application(_ a: UIApplication, supportedInterfaceOrientationsFor w: UIWindow?) -> UIInterfaceOrientationMask { .portrait }' \
    "锁方向"
run "UIRequiresFullScreen triggers it" Edit "/p/Config.swift" \
    'let UIRequiresFullScreen = true' \
    "锁方向"

# --- once per session ---------------------------------------------------------
echo "  -- once-per-session guard"
SESSION="dedup-$RANDOM"
mk() { python3 -c "
import json,sys
print(json.dumps({'tool_name':'Write','session_id':sys.argv[1],
                  'tool_input':{'file_path':'/p/A.swift','content':sys.argv[2]}}))
" "$SESSION" "$1"; }
first=$(mk 'VStack { }.background(Color.red)' | python3 "$HOOK" 2>&1 >/dev/null)
second=$(mk 'HStack { }.background(Color.blue)' | python3 "$HOOK" 2>&1 >/dev/null)
if [ -n "$first" ] && [ -z "$second" ]; then
    echo "  PASS: fires once, then stays silent in the same session"; PASS=$((PASS+1))
else
    echo "  FAIL: dedup — first='${first:0:40}' second='${second:0:40}'"; FAIL=$((FAIL+1))
fi

# --- the referenced sections must exist --------------------------------------
echo "  -- referenced sections exist in the reference file"
REF="$(cd "$(dirname "$0")/../.." && pwd)/references/apple-swift-rules.md"
for s in "容器宽度意图" "测试框架与文件放置" "同一动作的控件形制一致" "设计稿没有横屏"; do
    if grep -qE "^## .*$s" "$REF"; then
        echo "  PASS: section exists — $s"; PASS=$((PASS+1))
    else
        echo "  FAIL: section missing — $s"; FAIL=$((FAIL+1))
    fi
done

echo ""
echo "PASS: $PASS  FAIL: $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
