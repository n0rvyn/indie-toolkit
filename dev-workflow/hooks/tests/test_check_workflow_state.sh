#!/bin/bash
# Tests for check-workflow-state.sh: the SessionStart hook must surface a
# named error for a broken or off-enum state file instead of printing
# nothing (the old hand-parsed hook silently swallowed both). Fixtures are
# shared with run-phase/scripts/fixtures/ so the hook and phase.py's own
# tests read the exact same broken/off-enum/legacy files.
set -u

HOOK_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# CHECK_HOOK may point at another copy of the hook (a copy whose ../skills tree
# holds the pre-fix phase.py) — used to prove these cases can fail.
HOOK_SCRIPT="${CHECK_HOOK:-${HOOK_DIR}/check-workflow-state.sh}"
FIXTURES="${HOOK_DIR}/../skills/run-phase/scripts/fixtures"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT INT TERM

PASS=0
FAIL=0

run_case() {  # run_case <name> <project dir> <expected exit> <expected grep|"" for no output>
    local name="$1" dir="$2" expect_exit="$3" expect_grep="$4" output code
    output=$(cd "$dir" && bash "$HOOK_SCRIPT" 2>&1)
    code=$?
    if [ "$code" -ne "$expect_exit" ]; then
        echo "FAIL: $name (exit=$code, expected=$expect_exit, output=$output)"
        FAIL=$((FAIL+1))
        return
    fi
    if [ -z "$expect_grep" ]; then
        if [ -z "$output" ]; then
            echo "PASS: $name"
            PASS=$((PASS+1))
        else
            echo "FAIL: $name (expected no output, got: $output)"
            FAIL=$((FAIL+1))
        fi
        return
    fi
    if echo "$output" | grep -qF "$expect_grep"; then
        echo "PASS: $name"
        PASS=$((PASS+1))
    else
        echo "FAIL: $name (expected to contain '$expect_grep', got: $output)"
        FAIL=$((FAIL+1))
    fi
}

run_exact() {  # run_exact <name> <project dir> <expected full output>
    local name="$1" dir="$2" expect="$3" output code
    output=$(cd "$dir" && bash "$HOOK_SCRIPT" 2>&1)
    code=$?
    if [ "$code" -eq 0 ] && [ "$output" = "$expect" ]; then
        echo "PASS: $name"
        PASS=$((PASS+1))
    else
        echo "FAIL: $name (exit=$code)"
        echo "   expected: $expect"
        echo "   got:      $output"
        FAIL=$((FAIL+1))
    fi
}

# --- case: valid in-progress state ---
VALID="$WORK/valid"
mkdir -p "$VALID/.claude"
cp "$FIXTURES/valid.json" "$VALID/.claude/dev-workflow-state.json"
run_exact "valid-in-progress-exact-wording" "$VALID" \
    "[dev-workflow] Phase 2 (Phase Two) in progress — step: review, last updated: 2026-09-20T10:00:00. Run /run-phase to resume."

# --- case: done step prints nothing ---
DONE="$WORK/done"
mkdir -p "$DONE/.claude"
python3 -c "
import json
with open('$FIXTURES/valid.json') as f:
    d = json.load(f)
d['phase_step'] = 'done'
with open('$DONE/.claude/dev-workflow-state.json', 'w') as f:
    json.dump(d, f)
"
run_case "done-step-silent" "$DONE" 0 ""

# --- case: broken (unparseable) JSON ---
BROKEN="$WORK/broken"
mkdir -p "$BROKEN/.claude"
cp "$FIXTURES/broken.json" "$BROKEN/.claude/dev-workflow-state.json"
run_case "broken-json" "$BROKEN" 0 "state file unreadable"
run_case "broken-json-names-quarantine" "$BROKEN" 0 "phase.py quarantine"

# --- case: off-enum phase_step ---
OFFENUM="$WORK/offenum"
mkdir -p "$OFFENUM/.claude"
cp "$FIXTURES/offenum.json" "$OFFENUM/.claude/dev-workflow-state.json"
run_case "off-enum-step" "$OFFENUM" 0 "unknown step 'verified-iphone'"

# --- case: legacy .yml resumes ---
LEGACY="$WORK/legacy"
mkdir -p "$LEGACY/.claude"
cp "$FIXTURES/legacy.yml" "$LEGACY/.claude/dev-workflow-state.yml"
run_exact "legacy-yaml-resume" "$LEGACY" \
    "[dev-workflow] Phase 1 (Phase One) in progress — step: test, last updated: 2026-09-18T09:00:00. Run /run-phase to resume."

# --- case: legacy_leftover (both .json and .yml) — the .json wins ---
LEFTOVER="$WORK/leftover"
mkdir -p "$LEFTOVER/.claude"
cp "$FIXTURES/valid.json" "$LEFTOVER/.claude/dev-workflow-state.json"
cp "$FIXTURES/legacy.yml" "$LEFTOVER/.claude/dev-workflow-state.yml"
run_exact "legacy-leftover-json-wins" "$LEFTOVER" \
    "[dev-workflow] Phase 2 (Phase Two) in progress — step: review, last updated: 2026-09-20T10:00:00. Run /run-phase to resume."

# --- case: finished .yml with a letter phase (Socratic shape) stays silent ---
FINISHED_YML="$WORK/finished-yml"
mkdir -p "$FINISHED_YML/.claude"
printf 'project: X\ncurrent_phase: D\nphase_name: "P"\nphase_step: done\nlast_updated: "2026-03-13T00:10:00"\n' \
    > "$FINISHED_YML/.claude/dev-workflow-state.yml"
run_case "finished-letter-phase-silent" "$FINISHED_YML" 0 ""

# --- case: duplicate keys, last-wins phase_step finalized (Delphi shape) stays silent ---
DUP_DONE="$WORK/dup-done"
mkdir -p "$DUP_DONE/.claude"
printf '{"phase_step": "finalized", "current_phase": 4, "test_report": null, "test_report": "x"}' \
    > "$DUP_DONE/.claude/dev-workflow-state.json"
run_case "dup-keys-finalized-silent" "$DUP_DONE" 0 ""

# --- case: duplicate keys, in progress — named error ---
DUP_OPEN="$WORK/dup-open"
mkdir -p "$DUP_OPEN/.claude"
printf '{"phase_step": "review", "current_phase": 4, "test_report": null, "test_report": "x"}' \
    > "$DUP_OPEN/.claude/dev-workflow-state.json"
run_case "dup-keys-in-progress-named" "$DUP_OPEN" 0 "duplicate keys: test_report"

# --- case: phase.py missing — a visible line, not silence ---
# A copy of the hook in a dir whose ../skills tree does not exist.
NOPHASE="$WORK/nophase"
mkdir -p "$NOPHASE/hooks" "$NOPHASE/proj/.claude"
cp "$HOOK_SCRIPT" "$NOPHASE/hooks/check-workflow-state.sh"
cp "$FIXTURES/valid.json" "$NOPHASE/proj/.claude/dev-workflow-state.json"
output=$(cd "$NOPHASE/proj" && bash "$NOPHASE/hooks/check-workflow-state.sh" 2>&1)
code=$?
if [ "$code" -eq 0 ] && [ "$output" = "[dev-workflow] phase.py not found — plugin install incomplete" ]; then
    echo "PASS: phase-py-not-found"
    PASS=$((PASS+1))
else
    echo "FAIL: phase-py-not-found (exit=$code, got: $output)"
    FAIL=$((FAIL+1))
fi

# --- case: no state file at all ---
NOSTATE="$WORK/nostate"
mkdir -p "$NOSTATE"
run_case "no-state-file" "$NOSTATE" 0 ""

echo "---"
echo "PASS: $PASS  FAIL: $FAIL  ($PASS/$((PASS+FAIL)) passed)"
[ "$FAIL" -eq 0 ]
