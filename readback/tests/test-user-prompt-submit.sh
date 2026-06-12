#!/usr/bin/env bash
# Test harness for user-prompt-submit hook
set -e

HOOK="$(cd "$(dirname "$0")" && pwd)/../hooks/user-prompt-submit.sh"
PASS=0; FAIL=0

# NOTE: fixture builds {prompt: $p, session_id: ...} to match real Claude Code
# UserPromptSubmit stdin schema (the prompt field name; verified earlier).
run_case() {
  local desc="$1" prompt="$2" expect_mandate="$3" state_fixture="${4:-}"
  local input out has_mandate
  if [ -n "$state_fixture" ]; then
    # Write state fixture to a tmpdir cwd so the hook reads it as project state
    local td
    td=$(mktemp -d)
    mkdir -p "$td/.claude"
    echo "$state_fixture" > "$td/.claude/readback-state.json"
    input=$(jq -n --arg p "$prompt" '{prompt: $p, session_id: "test-current-session"}')
    out=$(cd "$td" && echo "$input" | bash "$HOOK")
    rm -rf "$td"
  else
    input=$(jq -n --arg p "$prompt" '{prompt: $p, session_id: "test-current-session"}')
    out=$(echo "$input" | bash "$HOOK")
  fi
  has_mandate=$(echo "$out" | jq -r '.hookSpecificOutput.additionalContext // empty' | grep -c "readback-mandate" || true)
  if [ "$has_mandate" -eq "$expect_mandate" ]; then
    echo "  ✓ $desc"; PASS=$((PASS+1))
  else
    echo "  ✗ $desc — expected mandate=$expect_mandate, got=$has_mandate"; FAIL=$((FAIL+1))
  fi
}

FRESH_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
# Stale timestamp for TTL boundary tests (40 min old; >30 min TTL).
# BSD date `-v` syntax; GNU date `-d` fallback for portability.
STALE_TS=$(date -u -v-40M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
           || date -u -d "40 minutes ago" +%Y-%m-%dT%H:%M:%SZ)

echo "Test: user-prompt-submit hook"
run_case "action verb 'fix' triggers mandate" "fix the bug in BillImportView import flow" 1
run_case "question without action — no mandate" "how does the import flow work?" 0
run_case "orchestration command — no mandate" "/run-phase" 0
run_case "trivial verb 'rename' — no mandate" "rename BillService to ImportService" 0
run_case "explicit bypass 'go' — no mandate" "go" 0
run_case "Chinese '修' triggers mandate" "修一下账单导入的报错" 1
run_case "malformed json input — fail-open (no mandate, no error)" "" 0
# Skip 5: discussion / opinion / brainstorm prompts should not fire mandate
run_case "Skip 5: 你同意吗 — no mandate" "我们应该重构 auth 模块，你同意吗？" 0
run_case "Skip 5: 如何更好地 — no mandate" "如何更好地处理这个问题？" 0
run_case "Skip 5: 我在想 + action — no mandate" "我在想该不该实现这个新功能" 0
run_case "Skip 5: Think carefully (English) — no mandate" "Think carefully about this problem" 0
# Idiom-strip: 修修补补 metaphor should not match action-verb regex
run_case "Idiom-strip: 修修补补 metaphor — no mandate" "这种修修补补的方式不好" 0
run_case "Idiom-strip: 这个实现 noun — no mandate" "这个实现看起来怪怪的" 0
# L1 regression guard: correction phrase '你理解错了' + action verb should fire mandate
# (Skip 5 must NOT catch 你理解 substring — only the question form 你理解了吗 is a readback signal,
# which is now removed from triggers; 你理解错了 is a correction signal that needs re-readback.)
run_case "L1 regression: 你理解错了 + 修 — mandate (correction loop must re-readback)" \
  "你理解错了，修一下登录页 bug" 1
# Schema v2: state-aware short-circuit cases
# NOTE: 'pre-stamp window' requires confirmed_at field (set by SKILL.md Step 5 on 'go'
# confirmation). Empty stored_sid alone is no longer trusted unconditionally — must be
# paired with fresh confirmed_at (< 30 min) per the TTL fix.
run_case "action verb 'fix' with confirmed-state matching session — no mandate (L1: post-stamp window)" \
  "fix the bug in BillImportView" 0 \
  "$(jq -n --arg ts "$FRESH_TS" '{session_id: "test-current-session", created_at: $ts, confirmed_at: $ts, skill: "fix-bug", user_confirmed: true}')"
# Task-level re-arm: post-stamp matching sid but STALE confirmed_at (>30 min) must
# RE-FIRE the mandate. Under the old code this suppressed eternally (sid match, no
# TTL); the re-arm fix gates the post-stamp branch on the same 30-min freshness as
# the pre-stamp branch, so a new task later in the same session gets readback again.
run_case "task-level re-arm: post-stamp matching sid + stale confirmed_at (40min) — mandate (re-arm, not eternal suppression)" \
  "fix another bug in PaymentView" 1 \
  "$(jq -n --arg stale "$STALE_TS" '{session_id: "test-current-session", created_at: $stale, confirmed_at: $stale, skill: "fix-bug", user_confirmed: true}')"
run_case "action verb 'fix' with confirmed-state and null stored sid + fresh confirmed_at — no mandate (L1: pre-stamp window)" \
  "fix the bug" 0 \
  "$(jq -n --arg ts "$FRESH_TS" '{session_id: null, created_at: $ts, confirmed_at: $ts, skill: "fix-bug", user_confirmed: true}')"
run_case "action verb 'fix' with confirmed-state but different stored sid — mandate (cross-session)" \
  "fix the bug" 1 \
  "$(jq -n --arg ts "$FRESH_TS" '{session_id: "different-old-session", created_at: $ts, confirmed_at: $ts, skill: "fix-bug", user_confirmed: true}')"
# TTL guard: empty stored sid + stale confirmed_at (>30 min) — mandate fires (state leaked across sessions)
run_case "TTL guard: empty stored sid + stale confirmed_at (40min) — mandate (state leak prevention)" \
  "fix the bug" 1 \
  "$(jq -n --arg fresh "$FRESH_TS" --arg stale "$STALE_TS" '{session_id: null, created_at: $stale, confirmed_at: $stale, skill: "fix-bug", user_confirmed: true}')"

echo
echo "Passed: $PASS, Failed: $FAIL"
[ "$FAIL" -eq 0 ]
