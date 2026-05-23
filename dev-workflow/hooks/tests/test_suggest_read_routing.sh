#!/usr/bin/env bash
# test_suggest_read_routing.sh — test driver for suggest-read-routing.sh hook
# Exits non-zero if any TC fails.
# Verifies: triage on large Read, repeat-file detection, sidechain skip, exit-0 always.

set -u

HOOK="$(cd "$(dirname "$0")/.." && pwd)/suggest-read-routing.sh"
if [ ! -x "$HOOK" ]; then
  echo "FAIL: hook not found at $HOOK"
  exit 1
fi

PASS_COUNT=0
FAIL_COUNT=0
FAILS=()

pass() { PASS_COUNT=$((PASS_COUNT+1)); echo "PASS: $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT+1)); FAILS+=("$1"); echo "FAIL: $1"; }

# Per-TC isolation: each gets its own tmpdir as CLAUDE_PROJECT_DIR
setup_tc() {
  TC_DIR=$(mktemp -d)
  export CLAUDE_PROJECT_DIR="$TC_DIR"
}
cleanup_tc() {
  rm -rf "$TC_DIR" 2>/dev/null || true
}

# Create a "large" test file (>300 lines) and a "small" one (<300 lines)
make_large() {
  local f="$TC_DIR/large.txt"
  yes "line content" 2>/dev/null | head -400 > "$f"
  echo "$f"
}
make_small() {
  local f="$TC_DIR/small.txt"
  yes "line content" 2>/dev/null | head -50 > "$f"
  echo "$f"
}

# Invoke hook with stdin JSON; returns exit code via global, stderr via STDERR_CAPTURE
invoke_hook() {
  local file_path="$1"
  local is_side="${2:-false}"
  STDERR_CAPTURE=$(echo "{\"tool_input\":{\"file_path\":\"$file_path\"},\"isSidechain\":$is_side}" \
    | bash "$HOOK" 2>&1 >/dev/null)
  EXIT_CODE=$?
}

# ── TC1: small file → no hint ──────────────────────────────────────────────────
setup_tc
SMALL=$(make_small)
invoke_hook "$SMALL"
if [ "$EXIT_CODE" -eq 0 ] && ! echo "$STDERR_CAPTURE" | grep -q "cost-hint"; then
  pass "TC1 (small file <300 lines → no hint)"
else
  fail "TC1 (small file): exit=$EXIT_CODE, stderr=[$STDERR_CAPTURE]"
fi
cleanup_tc

# ── TC2: first large file → no hint (only 1 in window) ────────────────────────
setup_tc
LARGE=$(make_large)
invoke_hook "$LARGE"
if [ "$EXIT_CODE" -eq 0 ] && ! echo "$STDERR_CAPTURE" | grep -q "cost-hint"; then
  pass "TC2 (first large file → no hint yet)"
else
  fail "TC2 (first large): exit=$EXIT_CODE, stderr=[$STDERR_CAPTURE]"
fi
cleanup_tc

# ── TC3: 2 large files → hint on 2nd ──────────────────────────────────────────
setup_tc
LARGE1=$(make_large)
LARGE2="$TC_DIR/large2.txt"
yes "another file" 2>/dev/null | head -500 > "$LARGE2"
invoke_hook "$LARGE1"
invoke_hook "$LARGE2"
if [ "$EXIT_CODE" -eq 0 ] && echo "$STDERR_CAPTURE" | grep -q "cost-hint"; then
  pass "TC3 (2 distinct large files → hint emitted)"
else
  fail "TC3 (2 large files): exit=$EXIT_CODE, stderr=[$STDERR_CAPTURE]"
fi
cleanup_tc

# ── TC4: same large file repeated → repeat-style hint ─────────────────────────
setup_tc
LARGE=$(make_large)
invoke_hook "$LARGE"
invoke_hook "$LARGE"
if [ "$EXIT_CODE" -eq 0 ] && echo "$STDERR_CAPTURE" | grep -qE "(Read pollution|2× in this session)"; then
  pass "TC4 (same file Read 2× → repeat-style hint)"
else
  fail "TC4 (repeat file): exit=$EXIT_CODE, stderr=[$STDERR_CAPTURE]"
fi
cleanup_tc

# ── TC5: cooldown — 3rd invocation after hint → no new hint ──────────────────
setup_tc
LARGE=$(make_large)
invoke_hook "$LARGE"
invoke_hook "$LARGE"   # triggers hint
invoke_hook "$LARGE"   # should be silent (cooldown)
if [ "$EXIT_CODE" -eq 0 ] && ! echo "$STDERR_CAPTURE" | grep -q "cost-hint"; then
  pass "TC5 (cooldown active → 3rd invocation silent)"
else
  fail "TC5 (cooldown): exit=$EXIT_CODE, stderr=[$STDERR_CAPTURE]"
fi
cleanup_tc

# ── TC6: sidechain → exit 0, no state mutation ───────────────────────────────
setup_tc
LARGE=$(make_large)
invoke_hook "$LARGE" "true"   # sidechain=true
if [ "$EXIT_CODE" -eq 0 ] && ! echo "$STDERR_CAPTURE" | grep -q "cost-hint"; then
  # Also verify state file wasn't created
  if [ ! -f "$CLAUDE_PROJECT_DIR/.claude/cost-hint-state.json" ]; then
    pass "TC6 (sidechain → no hint, no state file created)"
  else
    # State file shouldn't have been touched for sidechain
    READS=$(python3 -c "import json; print(len(json.load(open('$CLAUDE_PROJECT_DIR/.claude/cost-hint-state.json')).get('recent_reads', [])))" 2>/dev/null || echo 0)
    if [ "$READS" -eq 0 ]; then
      pass "TC6 (sidechain → no hint, recent_reads empty)"
    else
      fail "TC6 (sidechain leaked into state): reads=$READS"
    fi
  fi
else
  fail "TC6 (sidechain): exit=$EXIT_CODE, stderr=[$STDERR_CAPTURE]"
fi
cleanup_tc

# ── TC7: always exit 0 even on malformed JSON ────────────────────────────────
setup_tc
STDERR_CAPTURE=$(echo "not json at all" | bash "$HOOK" 2>&1 >/dev/null)
EXIT_CODE=$?
if [ "$EXIT_CODE" -eq 0 ]; then
  pass "TC7 (malformed JSON → exit 0)"
else
  fail "TC7 (malformed): exit=$EXIT_CODE"
fi
cleanup_tc

# ── TC8: file_path doesn't exist → exit 0, no hint ───────────────────────────
setup_tc
invoke_hook "/nonexistent/path/that/should/not/exist.txt"
if [ "$EXIT_CODE" -eq 0 ] && ! echo "$STDERR_CAPTURE" | grep -q "cost-hint"; then
  pass "TC8 (nonexistent file_path → exit 0, no hint)"
else
  fail "TC8 (nonexistent): exit=$EXIT_CODE, stderr=[$STDERR_CAPTURE]"
fi
cleanup_tc

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "Results: $PASS_COUNT passed, $FAIL_COUNT failed"

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
exit 0
