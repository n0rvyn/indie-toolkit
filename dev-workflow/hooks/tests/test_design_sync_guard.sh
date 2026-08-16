#!/bin/bash
# Test harness for design-sync-guard.py (UserPromptSubmit + PreToolUse WebFetch).
#
# URLs here reproduce the real shape (claude.ai/design/p/<uuid>?file=...), not a
# paraphrase — a case that omits the trigger substring passes no matter what the
# hook does.
set -u

HOOK="$(cd "$(dirname "$0")/.." && pwd)/design-sync-guard.py"
PASS=0
FAIL=0

# run <name> <json> <expect substring|NONE>
#
# A crashed hook prints nothing on stdout, so every "expect silence" case would
# pass against a hook that does not run at all. Capture stderr separately and
# fail on a traceback, so correct silence is distinguishable from a dead script.
run() {
    local name="$1" input="$2" expect="$3" out err
    err=$(mktemp)
    out=$(printf '%s' "$input" | python3 "$HOOK" 2>"$err")
    if grep -q 'Traceback\|SyntaxError\|IndentationError' "$err" 2>/dev/null; then
        echo "  FAIL: $name — hook crashed: $(head -1 "$err")"; FAIL=$((FAIL+1)); rm -f "$err"; return
    fi
    rm -f "$err"
    if [ "$expect" = "NONE" ]; then
        if [ -z "$out" ]; then echo "  PASS: $name (silent)"; PASS=$((PASS+1))
        else echo "  FAIL: $name — expected silence, got: ${out:0:80}"; FAIL=$((FAIL+1)); fi
    else
        if printf '%s' "$out" | grep -q "$expect"; then echo "  PASS: $name"; PASS=$((PASS+1))
        else echo "  FAIL: $name — expected '$expect', got: ${out:-<empty>}"; FAIL=$((FAIL+1)); fi
    fi
}

mk() { python3 -c "
import json,sys
print(json.dumps(json.loads(sys.argv[1])))
" "$1"; }

echo "=== design-sync-guard.py ==="

# --- PreToolUse(WebFetch): the documented failure must be blocked -------------
run "WebFetch on a private design project URL is denied" \
    "$(mk '{"hook_event_name":"PreToolUse","tool_name":"WebFetch","tool_input":{"url":"https://claude.ai/design/p/1c9b0a2e-4f11-4a5d-9b2e-8f0c1d2e3a4b?file=src/App.jsx"}}')" \
    '"permissionDecision": "deny"'
run "deny message points at DesignSync" \
    "$(mk '{"hook_event_name":"PreToolUse","tool_name":"WebFetch","tool_input":{"url":"https://claude.ai/design/p/abc"}}')" \
    'DesignSync'
run "WebFetch on an unrelated URL passes" \
    "$(mk '{"hook_event_name":"PreToolUse","tool_name":"WebFetch","tool_input":{"url":"https://code.claude.com/docs/en/memory"}}')" \
    NONE
run "WebFetch on claude.ai but not /design passes" \
    "$(mk '{"hook_event_name":"PreToolUse","tool_name":"WebFetch","tool_input":{"url":"https://claude.ai/code/artifact/xyz"}}')" \
    NONE
run "a non-WebFetch tool is ignored" \
    "$(mk '{"hook_event_name":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"/p/claude.ai/design/x.md"}}')" \
    NONE

# --- UserPromptSubmit: convention delivered on demand ------------------------
run "prompt containing a design URL gets the convention" \
    "$(mk '{"hook_event_name":"UserPromptSubmit","prompt":"看一下 https://claude.ai/design/p/abc?file=src/App.jsx 这个稿"}')" \
    'DesignSync'
run "convention carries the sub-agent availability caveat" \
    "$(mk '{"hook_event_name":"UserPromptSubmit","prompt":"https://claude.ai/design/p/abc"}')" \
    '不是环境不变量'
run "convention warns that design-login/design-sync are not on disk" \
    "$(mk '{"hook_event_name":"UserPromptSubmit","prompt":"claude.ai/design/p/abc"}')" \
    'grep 不到不等于 phantom'
run "an unrelated prompt stays silent" \
    "$(mk '{"hook_event_name":"UserPromptSubmit","prompt":"帮我改一下这个函数"}')" \
    NONE

# --- robustness ---------------------------------------------------------------
run "malformed json does not crash" "not json at all" NONE
run "unknown event is ignored" \
    "$(mk '{"hook_event_name":"Stop","prompt":"claude.ai/design"}')" \
    NONE

echo ""
echo "PASS: $PASS  FAIL: $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
