#!/usr/bin/env bash
# Test harness for user-prompt-submit hook (schema v3: ambiguity-gated, non-blocking).
#
# v3 asserts a different contract than v2 did. v2 fired on action-verb presence and
# emitted `[readback-mandate]`; v3 fires only on an ambiguous referent and emits
# `[readback-hint]`. Cases that used to expect a mandate on "fix the bug" now expect
# silence — that is the intended behavior change, not a regression.
set -e

HOOK="$(cd "$(dirname "$0")" && pwd)/../hooks/user-prompt-submit.sh"
PASS=0; FAIL=0

# Every case runs in a fresh tmpdir cwd. Without this, the hook reads whatever
# .claude/readback-state.json happens to sit in the repo root, and a leftover
# `user_confirmed: true` silently suppresses every expected-fire case.
run_case() {
  local desc="$1" prompt="$2" expect_hint="$3" state_fixture="${4:-}"
  local input out has_hint td
  td=$(mktemp -d)
  if [ -n "$state_fixture" ]; then
    mkdir -p "$td/.claude"
    echo "$state_fixture" > "$td/.claude/readback-state.json"
  fi
  input=$(jq -n --arg p "$prompt" '{prompt: $p, session_id: "test-current-session"}')
  out=$(cd "$td" && echo "$input" | bash "$HOOK")
  rm -rf "$td"
  has_hint=$(echo "$out" | jq -r '.hookSpecificOutput.additionalContext // empty' | grep -c "readback-hint" || true)
  if [ "$has_hint" -eq "$expect_hint" ]; then
    echo "  ✓ $desc"; PASS=$((PASS+1))
  else
    echo "  ✗ $desc — expected hint=$expect_hint, got=$has_hint"; FAIL=$((FAIL+1))
  fi
}

echo "Test: user-prompt-submit hook (v3)"

echo "-- fires: genuine ambiguous referent"
run_case "A2 demonstrative + attribute (字号)" "把这个字号改小" 1
run_case "A2 demonstrative + attribute (风格)" "那种风格我不喜欢，换一下" 1
run_case "A2 demonstrative + attribute (颜色)" "这个颜色太浅了" 1
run_case "A2b bare demonstrative as target state" "改成那样" 1
run_case "A1 screenshot with no locator" "[Image #1] 改成图里那样" 1
run_case "A3 broad scope, no boundary (重构)" "重构一下这块" 1
run_case "A3 broad scope, no boundary (统一)" "统一一下间距" 1

echo "-- quiet: concrete target named (Skip 4)"
run_case "backticked identifier pins the referent" "修一下 \`CardView\` 的这个字号" 0
run_case "file path pins the referent" "修 src/foo.swift 的 bug" 0
run_case "line reference pins the referent" "第 3 行那个颜色改深一点" 0
run_case "CamelCase symbol pins the referent" "把 BillImportView 的这个间距调大" 0

echo "-- quiet: locator present, so referent is not in doubt"
run_case "screenshot WITH locator" "[Image #1] 把顶部那个间距改小" 0
run_case "locator suppresses A2 too" "左上那个圆角改大" 0

echo "-- quiet: discussion / question (Skip 3)"
run_case "你没有说X？ — the v2 leak this replaces" "你没有说修复建议？" 0
run_case "如何界定" "readback 如何界定这个边界？" 0
run_case "你觉得…行不行" "你觉得这个配色行不行" 0
run_case "你同意吗" "我们应该重构 auth 模块，你同意吗？" 0
run_case "我在想该不该" "我在想该不该实现这个新功能" 0
run_case "English discussion" "What do you think about this spacing" 0

echo "-- quiet: unambiguous action (v2 would have fired on all of these)"
run_case "plain fix request" "fix the crash on launch" 0
run_case "plain 修 request" "修一下账单导入的报错" 0
run_case "plain feature request" "实现一个登录功能" 0
run_case "object noun, not attribute" "把这个按钮挪到右边" 0
run_case "scoped refactor (只)" "只重构这个按钮的样式" 0
run_case "idiom, not an action" "这种修修补补的方式不好" 0

echo "-- quiet: v2 field regressions (real prompts observed misfiring, 2026-07-30)"
# Both of these fired the v2 mandate during the session that produced v3. They are the
# only prompts with direct evidence of a false positive, so they are pinned here.
run_case "R1: long multi-clause approval message" \
  "(b)可接受。如果明显理解不对，用户可以手动ESC强制停下来，但大多数时候，只是想确认下彼此（人VS AI）理解在一条线上。同意你对 ReadBack 的三处改法。3 里面2个，同意你的修法。" 0
# R1 minus the CamelCase token, to prove R1 is not passing merely via the Skip-4
# CamelCase suppressor.
run_case "R1b: same message without any CamelCase token" \
  "(b)可接受。如果明显理解不对，用户可以手动ESC强制停下来，但大多数时候，只是想确认下彼此理解在一条线上。同意你对回读的三处改法。" 0
run_case "R2: pasting a tool report back for review" \
  "4. doctor result： 「All checks done, read-only. What I found is clutter — 4 skills in ~/.claude/skills/ that your own files mark as retired duplicates.」, already do the cleanup in another session." 0

echo "-- quiet: structural skips"
run_case "slash command" "/run-phase" 0
run_case "explicit bypass" "直接做" 0
run_case "empty prompt — fail-open" "" 0

echo "-- quiet: an explicitly confirmed readback already owns the turn"
run_case "user_confirmed=true suppresses the hint" "把这个字号改小" 0 \
  '{"user_confirmed": true, "skill": "fix-bug"}'
run_case "user_confirmed=false does not suppress" "把这个字号改小" 1 \
  '{"user_confirmed": false, "skill": "fix-bug"}'

echo
echo "Passed: $PASS, Failed: $FAIL"
[ "$FAIL" -eq 0 ]
