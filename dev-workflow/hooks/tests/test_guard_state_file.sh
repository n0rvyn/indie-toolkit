#!/bin/bash
# Tests for guard-state-file.py: a PreToolUse Edit/Write/MultiEdit/NotebookEdit
# targeting the run-phase state file (JSON or legacy YAML), or a Bash command that
# writes onto it, must be denied; every other path, read-only commands, phase.py
# invocations, and malformed / non-object hook input must pass through silently.
#
# The hook's stdout is parsed as JSON (not substring-matched): a deny case passes
# only when hookSpecificOutput.permissionDecision == "deny"; a pass case only when
# stdout is empty. GUARD_HOOK may point at another copy of the hook (used to prove
# these cases can fail against the pre-fix version).
set -u

HOOK_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_SCRIPT="${GUARD_HOOK:-${HOOK_DIR}/guard-state-file.py}"

PASS=0
FAIL=0

# run_case <name> <stdin json> <expect deny 0|1>   (exit code must always be 0)
run_case() {
    local name="$1" input="$2" expect_deny="$3" output code verdict
    output=$(printf '%s' "$input" | python3 "$HOOK_SCRIPT" 2>&1)
    code=$?
    if [ "$code" -ne 0 ]; then
        echo "FAIL: $name (exit=$code, expected=0, output=$output)"
        FAIL=$((FAIL+1))
        return
    fi
    verdict=$(printf '%s' "$output" | python3 -c "
import json, sys
raw = sys.stdin.read()
if raw.strip() == '':
    print('silent')
    sys.exit(0)
try:
    d = json.loads(raw)
except Exception:
    print('not-json')
    sys.exit(0)
hso = d.get('hookSpecificOutput', {}) if isinstance(d, dict) else {}
ok = (hso.get('hookEventName') == 'PreToolUse'
      and hso.get('permissionDecision') == 'deny'
      and 'phase.py' in hso.get('permissionDecisionReason', ''))
print('deny' if ok else 'other')
")
    if [ "$expect_deny" -eq 1 ] && [ "$verdict" = "deny" ]; then
        echo "PASS: $name"; PASS=$((PASS+1))
    elif [ "$expect_deny" -eq 0 ] && [ "$verdict" = "silent" ]; then
        echo "PASS: $name"; PASS=$((PASS+1))
    else
        echo "FAIL: $name (expected $([ "$expect_deny" -eq 1 ] && echo deny || echo silent), got $verdict: $output)"
        FAIL=$((FAIL+1))
    fi
}

# bash_case <name> <command> <expect deny 0|1> — wraps a Bash tool call.
bash_case() {
    local input
    input=$(python3 -c 'import json,sys; print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.argv[1]}}))' "$2")
    run_case "$1" "$input" "$3"
}

S=/tmp/proj/.claude/dev-workflow-state.json

# --- file tools ---
run_case "write-state-json-denied" \
    '{"tool_name":"Write","tool_input":{"file_path":"/tmp/proj/.claude/dev-workflow-state.json","content":"{}"}}' 1
run_case "write-state-yml-denied" \
    '{"tool_name":"Write","tool_input":{"file_path":"/tmp/proj/.claude/dev-workflow-state.yml","content":""}}' 1
run_case "multiedit-state-json-denied" \
    '{"tool_name":"MultiEdit","tool_input":{"file_path":"/tmp/proj/.claude/dev-workflow-state.json","edits":[{"old_string":"a","new_string":"b"}]}}' 1
run_case "notebookedit-notebook-path-denied" \
    '{"tool_name":"NotebookEdit","tool_input":{"notebook_path":"/tmp/proj/.claude/dev-workflow-state.json","new_source":"x"}}' 1
run_case "edit-unrelated-file-passes" \
    '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/proj/src/a.py","old_string":"a","new_string":"b"}}' 0
run_case "edit-state-backup-name-passes" \
    '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/proj/.claude/dev-workflow-state.json.bak","old_string":"a","new_string":"b"}}' 0

# --- malformed / non-object input ---
run_case "malformed-stdin-passes" 'not json at all' 0
run_case "non-object-list-passes" '[]' 0
run_case "non-object-string-passes" '"x"' 0
run_case "non-object-null-passes" 'null' 0
run_case "tool-input-not-object-passes" '{"tool_name":"Bash","tool_input":"echo hi"}' 0

# --- Bash writes: denied ---
bash_case "bash-redirect-denied" "echo '{}' > $S" 1
bash_case "bash-append-denied" "echo x >> .claude/dev-workflow-state.json" 1
bash_case "bash-redirect-quoted-denied" "printf '%s' '{}' >\"$S\"" 1
bash_case "bash-tee-denied" "echo '{}' | tee .claude/dev-workflow-state.json" 1
bash_case "bash-sed-i-denied" "sed -i '' 's/review/done/' .claude/dev-workflow-state.json" 1
bash_case "bash-cp-onto-denied" "cp /tmp/good.json .claude/dev-workflow-state.json" 1
bash_case "bash-mv-onto-denied" "jq '.phase_step=\"done\"' $S > /tmp/x && mv /tmp/x $S" 1
bash_case "bash-yml-redirect-denied" "echo 'phase_step: done' > .claude/dev-workflow-state.yml" 1
bash_case "bash-python-oneliner-denied" "python3 -c \"import json; json.dump({}, open('.claude/dev-workflow-state.json','w'))\"" 1
bash_case "bash-python-heredoc-denied" "python3 - <<'EOF'
import json
p = '.claude/dev-workflow-state.json'
d = json.load(open(p))
d['phase_step'] = 'done'
open(p, 'w').write(json.dumps(d))
EOF" 1
bash_case "bash-perl-i-denied" "perl -pi -e 's/review/done/' .claude/dev-workflow-state.json" 1

# --- Bash reads / phase.py: allowed ---
bash_case "bash-cat-passes" "cat .claude/dev-workflow-state.json" 0
bash_case "bash-grep-passes" "grep phase_step .claude/dev-workflow-state.json" 0
bash_case "bash-jq-read-passes" "jq .phase_step $S" 0
bash_case "bash-cat-redirect-elsewhere-passes" "cat $S > /tmp/state-backup.json" 0
bash_case "bash-cp-from-state-passes" "cp .claude/dev-workflow-state.json /tmp/bak.json" 0
bash_case "bash-python-read-passes" "python3 -c \"import json; print(json.load(open('.claude/dev-workflow-state.json'))['phase_step'])\"" 0
bash_case "bash-phase-py-passes" "python3 dev-workflow/skills/run-phase/scripts/phase.py set plan_file=null --root /tmp/proj  # .claude/dev-workflow-state.json" 0
bash_case "bash-phase-py-status-passes" "python3 \${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py status > /tmp/s.json; cat .claude/dev-workflow-state.json" 0
bash_case "bash-unrelated-passes" "git status && ls -la" 0

TOTAL=$((PASS+FAIL))
echo "---"
echo "PASS: $PASS  FAIL: $FAIL  ($PASS/$TOTAL passed)"
[ "$FAIL" -eq 0 ]
