#!/usr/bin/env bash
# test_diagnose.sh — test driver for diagnose-cost-drivers/scripts/diagnose.py
# Exits non-zero if any TC fails.
# Before Task 8-impl: all TCs fail (diagnose.py not found).
# After Task 8-impl: all TCs pass.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES_DIR="$SCRIPT_DIR/fixtures"
DIAGNOSE_PY="$SCRIPT_DIR/../scripts/diagnose.py"
PASS=0
FAIL=0

pass() { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1 — $2"; FAIL=$((FAIL+1)); }

# TC1: empty TSV → output HTML fragment containing "No diagnosis data"
TC1() {
  local tmptsv
  tmptsv=$(mktemp /tmp/diagnose-test-XXXXXX.tsv)
  # Write empty TSV (header line only, or truly empty)
  printf "" > "$tmptsv"
  local out
  out=$(python3 "$DIAGNOSE_PY" "$tmptsv" 2>&1)
  local ec=$?
  rm -f "$tmptsv"
  if [ $ec -ne 0 ]; then
    fail "TC1" "diagnose.py exited $ec on empty TSV; output: $out"
    return
  fi
  if ! echo "$out" | grep -qi "no diagnosis data"; then
    fail "TC1" "output does not contain 'No diagnosis data'; got: $out"
    return
  fi
  pass "TC1 (empty TSV → 'No diagnosis data' in output)"
}

# TC2: sample TSV → fragment contains root-cause categories + specific session ID
TC2() {
  local out
  out=$(python3 "$DIAGNOSE_PY" "$FIXTURES_DIR/sample-tsv.tsv" 2>&1)
  local ec=$?
  if [ $ec -ne 0 ]; then
    fail "TC2" "diagnose.py exited $ec; output: $out"
    return
  fi
  # Must contain at least one root-cause category
  local has_category=0
  for cat in "Sub-agent miss" "Cache bloat" "Read pollution" "Skill gap"; do
    if echo "$out" | grep -qi "$cat"; then
      has_category=1
      break
    fi
  done
  if [ $has_category -eq 0 ]; then
    fail "TC2" "output contains no root-cause categories (Sub-agent miss/Cache bloat/Read pollution/Skill gap); got: $out"
    return
  fi
  # Must reference at least one specific session ID from the fixture
  local has_session=0
  for sid in "sess-aaa-001" "sess-bbb-001" "sess-ccc-001"; do
    if echo "$out" | grep -q "$sid"; then
      has_session=1
      break
    fi
  done
  if [ $has_session -eq 0 ]; then
    fail "TC2" "output does not reference any specific session ID; got: $out"
    return
  fi
  pass "TC2 (sample TSV → root-cause categories + session ID present)"
}

# TC3: output is a valid HTML fragment (parseable by HTMLParser)
TC3() {
  local out
  out=$(python3 "$DIAGNOSE_PY" "$FIXTURES_DIR/sample-tsv.tsv" 2>&1)
  local ec=$?
  if [ $ec -ne 0 ]; then
    fail "TC3" "diagnose.py exited $ec; output: $out"
    return
  fi
  local parse_result
  parse_result=$(echo "$out" | python3 -c "
from html.parser import HTMLParser
import sys

class CheckParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.error = None
    def handle_error(self, message):
        self.error = message

p = CheckParser()
try:
    p.feed(sys.stdin.read())
    print('OK')
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1)
  if [ "$parse_result" != "OK" ]; then
    fail "TC3" "HTML fragment is not parseable: $parse_result; output head: $(echo "$out" | head -5)"
    return
  fi
  pass "TC3 (output is valid HTML fragment)"
}

# Check diagnose.py exists before running TCs
if [ ! -f "$DIAGNOSE_PY" ]; then
  echo "FAIL: TC1 — diagnose.py not found at $DIAGNOSE_PY"
  echo "FAIL: TC2 — diagnose.py not found at $DIAGNOSE_PY"
  echo "FAIL: TC3 — diagnose.py not found at $DIAGNOSE_PY"
  exit 1
fi

TC1
TC2
TC3

# TC4: HTML escaping — session ID containing '<' / '&' must be escaped in output
TC4() {
  local tmptsv
  tmptsv=$(mktemp /tmp/diagnose-test-XXXXXX.tsv)
  # One row with a session ID containing HTML-special chars
  printf "sess<script>&amp;\treq1\t_none_\t_none_\tclaude-opus-4-7\t100000\t50000\t300000\t1000\t0\t0\tfalse\t/tmp/x\t2026-05-23T00:00:00Z\n" > "$tmptsv"
  local out
  out=$(python3 "$DIAGNOSE_PY" "$tmptsv" 2>&1)
  local ec=$?
  rm -f "$tmptsv"
  if [ $ec -ne 0 ]; then
    fail "TC4" "diagnose.py exited $ec on escape-test TSV; output: $out"
    return
  fi
  # Raw '<script>' MUST NOT appear unescaped in output
  if echo "$out" | grep -q "<script>"; then
    fail "TC4" "session ID '<script>' leaked unescaped into HTML output"
    return
  fi
  # The escaped form should be present
  if ! echo "$out" | grep -qE "&lt;script&gt;|sess&lt;"; then
    fail "TC4" "no evidence of HTML escaping in output; got: $(echo "$out" | head -10)"
    return
  fi
  pass "TC4 (HTML escaping: <script> in session ID is escaped)"
}

# TC5: multi-attribution — one session triggering BOTH Skill gap AND Cache bloat
TC5() {
  local tmptsv
  tmptsv=$(mktemp /tmp/diagnose-test-XXXXXX.tsv)
  # 3 rows for one session: no_skill cost > 50% of total AND cache_read > 250K avg with max > 500K
  {
    printf "sess-multi-001\treq1\t_none_\t_none_\tclaude-opus-4-7\t100000\t100000\t600000\t1000\t0\t0\tfalse\t/tmp/x\t2026-05-23T00:00:00Z\n"
    printf "sess-multi-001\treq2\t_none_\t_none_\tclaude-opus-4-7\t100000\t0\t450000\t1000\t0\t0\tfalse\t/tmp/x\t2026-05-23T00:00:01Z\n"
    printf "sess-multi-001\treq3\t_none_\t_none_\tclaude-opus-4-7\t100000\t0\t400000\t1000\t0\t0\tfalse\t/tmp/x\t2026-05-23T00:00:02Z\n"
  } > "$tmptsv"
  local out
  out=$(python3 "$DIAGNOSE_PY" "$tmptsv" 2>&1)
  local ec=$?
  rm -f "$tmptsv"
  if [ $ec -ne 0 ]; then
    fail "TC5" "diagnose.py exited $ec on multi-attribution TSV; output: $out"
    return
  fi
  # Output must contain BOTH categories for the same session row
  if ! echo "$out" | grep -q "Skill gap"; then
    fail "TC5" "expected 'Skill gap' attribution missing; got: $(echo "$out" | head -20)"
    return
  fi
  if ! echo "$out" | grep -q "Cache bloat"; then
    fail "TC5" "expected 'Cache bloat' attribution missing; got: $(echo "$out" | head -20)"
    return
  fi
  pass "TC5 (multi-attribution: one session triggers Skill gap + Cache bloat)"
}

TC4
TC5

echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ $FAIL -gt 0 ]; then
  exit 1
fi
exit 0
