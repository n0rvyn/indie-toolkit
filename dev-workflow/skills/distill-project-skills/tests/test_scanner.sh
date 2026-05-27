#!/usr/bin/env bash
# test_scanner.sh — test driver for distill-project-skills/scripts/scan.py
# Exits non-zero if any TC fails.
# Before Task 7-impl: all TCs fail (scan.py not found).
# After Task 7-impl: all TCs pass.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES_DIR="$SCRIPT_DIR/fixtures"
SCAN_PY="$SCRIPT_DIR/../scripts/scan.py"
PASS=0
FAIL=0

pass() { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1 — $2"; FAIL=$((FAIL+1)); }

# TC1: empty jsonl dir → empty candidate list (no crash)
TC1() {
  local tmpdir
  tmpdir=$(mktemp -d)
  local out
  out=$(python3 "$SCAN_PY" --jsonl-dir "$tmpdir" --output /dev/stdout 2>&1)
  local ec=$?
  rm -rf "$tmpdir"
  if [ $ec -ne 0 ]; then
    fail "TC1" "scan.py exited $ec on empty dir; output: $out"
    return
  fi
  # output must be valid JSON with candidates key
  if ! echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'candidates' in d" 2>/dev/null; then
    fail "TC1" "output not valid JSON with 'candidates' key; got: $out"
    return
  fi
  # candidates must be empty
  local count
  count=$(echo "$out" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['candidates']))" 2>/dev/null)
  if [ "$count" != "0" ]; then
    fail "TC1" "expected 0 candidates for empty dir, got $count"
    return
  fi
  pass "TC1 (empty dir → empty candidates)"
}

# TC2: fixtures dir with 3 sessions → ≥1 candidate with pattern sqlite3-select, frequency ≥ 3
TC2() {
  local out
  out=$(python3 "$SCAN_PY" --jsonl-dir "$FIXTURES_DIR" --output /dev/stdout 2>&1)
  local ec=$?
  if [ $ec -ne 0 ]; then
    fail "TC2" "scan.py exited $ec; output: $out"
    return
  fi
  if ! echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'candidates' in d" 2>/dev/null; then
    fail "TC2" "output not valid JSON with 'candidates' key; got: $out"
    return
  fi
  # check for sqlite3-select candidate with frequency >= 3
  local found
  found=$(echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
matches = [c for c in d['candidates'] if 'sqlite3' in c.get('pattern','').lower() and c.get('frequency',0) >= 3]
print(len(matches))
" 2>/dev/null)
  if [ "$found" = "" ] || [ "$found" -lt 1 ]; then
    fail "TC2" "no sqlite3-select candidate with frequency>=3; output: $out"
    return
  fi
  pass "TC2 (fixtures → sqlite3-select candidate with freq>=3)"
}

# TC3: --include-hint-log → candidates include same-file-read pattern
TC3() {
  local out
  out=$(python3 "$SCAN_PY" --jsonl-dir "$FIXTURES_DIR" --include-hint-log "$FIXTURES_DIR/cost-hint.log" --output /dev/stdout 2>&1)
  local ec=$?
  if [ $ec -ne 0 ]; then
    fail "TC3" "scan.py exited $ec; output: $out"
    return
  fi
  if ! echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'candidates' in d" 2>/dev/null; then
    fail "TC3" "output not valid JSON with 'candidates' key; got: $out"
    return
  fi
  # check for same-file-read candidate
  local found
  found=$(echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
matches = [c for c in d['candidates'] if 'read' in c.get('pattern','').lower() or 'file' in c.get('pattern','').lower()]
print(len(matches))
" 2>/dev/null)
  if [ "$found" = "" ] || [ "$found" -lt 1 ]; then
    fail "TC3" "no same-file-read candidate from hint log; output: $out"
    return
  fi
  pass "TC3 (hint-log → same-file-read candidate present)"
}

# TC4: each candidate has all required fields (now including status)
TC4() {
  local out
  out=$(python3 "$SCAN_PY" --jsonl-dir "$FIXTURES_DIR" --include-hint-log "$FIXTURES_DIR/cost-hint.log" --no-history --no-existing-skills --output /dev/stdout 2>&1)
  local ec=$?
  if [ $ec -ne 0 ]; then
    fail "TC4" "scan.py exited $ec; output: $out"
    return
  fi
  local result
  result=$(echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
required = {'pattern', 'frequency', 'est_cost_usd', 'suggested_name', 'suggested_frontmatter', 'status'}
missing = []
for i, c in enumerate(d['candidates']):
    for f in required:
        if f not in c:
            missing.append(f'candidate[{i}] missing {f}')
if missing:
    print('MISSING: ' + '; '.join(missing))
else:
    print('OK')
" 2>/dev/null)
  if [ "$result" != "OK" ]; then
    fail "TC4" "schema validation failed: $result; output: $out"
    return
  fi
  pass "TC4 (all candidates have required schema fields)"
}

# TC5: existing skill with matching suggested_name → candidate.status == 'name-exists'
TC5() {
  local tmpdir
  tmpdir=$(mktemp -d)
  # Create a fake existing skill named 'query-adam-db' (matches sqlite3-select's suggested_name)
  mkdir -p "$tmpdir/fake-plugin/skills/query-adam-db"
  cat > "$tmpdir/fake-plugin/skills/query-adam-db/SKILL.md" <<'EOF'
---
name: query-adam-db
description: "Query the adam database via sqlite3"
model: haiku
context: fork
---
EOF
  local out
  out=$(python3 "$SCAN_PY" --jsonl-dir "$FIXTURES_DIR" \
        --skill-roots "$tmpdir/*/skills/*/SKILL.md" \
        --no-history \
        --output /dev/stdout 2>&1)
  local ec=$?
  rm -rf "$tmpdir"
  if [ $ec -ne 0 ]; then
    fail "TC5" "scan.py exited $ec; output: $out"
    return
  fi
  local status_check
  status_check=$(echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for c in d['candidates']:
    if c.get('pattern') == 'sqlite3-select':
        print(c.get('status', 'MISSING'))
        sys.exit(0)
print('NO_SQLITE_CANDIDATE')
" 2>/dev/null)
  if [ "$status_check" != "name-exists" ]; then
    fail "TC5" "expected status=name-exists for sqlite3-select, got: $status_check; output: $out"
    return
  fi
  pass "TC5 (existing skill name → status=name-exists)"
}

# TC6: pattern declined recently in history → candidate omitted from output
TC6() {
  local tmpdir
  tmpdir=$(mktemp -d)
  local hist="$tmpdir/distill-history.jsonl"
  # Recent declined entry (today) for sqlite3-select
  local now
  now=$(python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())")
  cat > "$hist" <<EOF
{"ts":"$now","pattern":"sqlite3-select","suggested_name":"query-adam-db","outcome":"declined"}
EOF
  local out
  out=$(python3 "$SCAN_PY" --jsonl-dir "$FIXTURES_DIR" \
        --history-file "$hist" \
        --no-existing-skills \
        --output /dev/stdout 2>&1)
  local ec=$?
  rm -rf "$tmpdir"
  if [ $ec -ne 0 ]; then
    fail "TC6" "scan.py exited $ec; output: $out"
    return
  fi
  local has_sqlite
  has_sqlite=$(echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
matches = [c for c in d['candidates'] if c.get('pattern') == 'sqlite3-select']
print(len(matches))
" 2>/dev/null)
  if [ "$has_sqlite" != "0" ]; then
    fail "TC6" "sqlite3-select declined-recently should have been omitted, got $has_sqlite candidate(s); output: $out"
    return
  fi
  pass "TC6 (declined-recently → candidate omitted)"
}

# TC7: status field is always one of {new, name-exists, possibly-covered, already-built}
TC7() {
  local out
  out=$(python3 "$SCAN_PY" --jsonl-dir "$FIXTURES_DIR" --include-hint-log "$FIXTURES_DIR/cost-hint.log" --no-history --no-existing-skills --output /dev/stdout 2>&1)
  local ec=$?
  if [ $ec -ne 0 ]; then
    fail "TC7" "scan.py exited $ec; output: $out"
    return
  fi
  local result
  result=$(echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
valid = {'new', 'name-exists', 'possibly-covered', 'already-built'}
bad = []
for i, c in enumerate(d['candidates']):
    s = c.get('status')
    if s not in valid:
        bad.append(f'candidate[{i}] status={s!r}')
if bad:
    print('INVALID: ' + '; '.join(bad))
else:
    print('OK')
" 2>/dev/null)
  if [ "$result" != "OK" ]; then
    fail "TC7" "invalid status values: $result; output: $out"
    return
  fi
  pass "TC7 (status field always in valid enum)"
}

# Check scan.py exists before running TCs
if [ ! -f "$SCAN_PY" ]; then
  for tc in TC1 TC2 TC3 TC4 TC5 TC6 TC7; do
    echo "FAIL: $tc — scan.py not found at $SCAN_PY"
  done
  exit 1
fi

TC1
TC2
TC3
TC4
TC5
TC6
TC7

echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ $FAIL -gt 0 ]; then
  exit 1
fi
exit 0
