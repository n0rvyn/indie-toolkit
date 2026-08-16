#!/bin/bash
# Test harness for protect-pbxproj.sh PreToolUse hook.
#
# The Bash branch must deny real modification of .pbxproj/.xcworkspace while
# leaving read-only inspection and unrelated authoring alone. Before 2026-08-16
# it tested "extension anywhere" AND "verb anywhere" independently and denied
# both of the read-only cases below.
set -u

HOOK="$(cd "$(dirname "$0")/.." && pwd)/protect-pbxproj.sh"
PASS=0
FAIL=0

# run <name> <tool_name> <json-field-value> <expect: DENY|ALLOW> [field]
run() {
    local name="$1" tool="$2" value="$3" expect="$4" field="${5:-command}"
    local input out got
    input=$(python3 -c "
import json,sys
tool, field, value = sys.argv[1], sys.argv[2], sys.argv[3]
print(json.dumps({'tool_name': tool, 'tool_input': {field: value}}))
" "$tool" "$field" "$value")
    local __err
    __err=$(mktemp)
    out=$(printf '%s' "$input" | bash "$HOOK" 2>"$__err")
    if grep -q 'Traceback\|SyntaxError\|IndentationError' "$__err" 2>/dev/null; then
        echo "  FAIL: $name — hook crashed: $(head -1 "$__err")"; FAIL=$((FAIL+1)); rm -f "$__err"; return
    fi
    rm -f "$__err"
    if printf '%s' "$out" | grep -q '"permissionDecision":"deny"'; then got=DENY; else got=ALLOW; fi
    if [ "$got" = "$expect" ]; then
        echo "  PASS: $name ($got)"; PASS=$((PASS+1))
    else
        echo "  FAIL: $name — expected $expect, got $got"; FAIL=$((FAIL+1))
    fi
}

echo "=== protect-pbxproj.sh ==="

# --- Edit/Write branch: path-based, unchanged behavior ------------------------
run "Write to project.pbxproj is denied" Write "/a/App.xcodeproj/project.pbxproj" DENY file_path
run "Write to a normal file is allowed"  Write "/a/CLAUDE.md"                     ALLOW file_path
run "Edit of xcworkspace is denied"      Edit  "/a/App.xcworkspace/contents.xcworkspacedata" DENY file_path

# --- Bash branch: true positives must keep denying ---------------------------
run "sed -i on a pbxproj" Bash \
    "sed -i '' 's/OLD/NEW/' App.xcodeproj/project.pbxproj" DENY
run "redirect into a pbxproj" Bash \
    "echo 'x' > App.xcodeproj/project.pbxproj" DENY
run "append into a pbxproj" Bash \
    "printf 'x' >> App.xcodeproj/project.pbxproj" DENY
run "heredoc redirected into a pbxproj" Bash \
    "cat <<EOF > App.xcodeproj/project.pbxproj
stuff
EOF" DENY
run "tee into an xcworkspace file" Bash \
    "tee App.xcworkspace/contents.xcworkspacedata < /tmp/x" DENY
run "python writing a pbxproj argument" Bash \
    "python3 patch.py App.xcodeproj/project.pbxproj" DENY

# --- Bash branch: reproduced false positives must now pass -------------------
# NOTE: a case must contain .pbxproj or .xcworkspace to exercise the guard at
# all. An earlier version of this file used a find over "*.xcodeproj" only —
# that extension is not protected, so the case passed no matter what the hook
# did. Reproduce the command that was actually denied, do not paraphrase it.
run "read-only find (2>/dev/null) + unrelated echo" Bash \
    'xc=$(find "$d" -maxdepth 2 \( -name "*.xcodeproj" -o -name "*.xcworkspace" \) 2>/dev/null | head -1)
if [ -n "$xc" ]; then echo "  APPLE  $d"; fi' ALLOW
run "extension only inside a heredoc body" Bash \
    "python3 - <<EOF
paths:
  - \"**/*.xcworkspace/**\"
EOF" ALLOW
run "ls of an xcodeproj directory with 2>/dev/null" Bash \
    "ls -la App.xcworkspace/ 2>/dev/null" ALLOW
run "grep inside a pbxproj (read-only)" Bash \
    "grep -n DEVELOPMENT_TEAM App.xcodeproj/project.pbxproj" ALLOW
run "write still denied even when stderr is discarded" Bash \
    "echo x > App.xcodeproj/project.pbxproj 2>/dev/null" DENY

# --- git allowlist stays -----------------------------------------------------
run "git diff on a pbxproj" Bash \
    "git diff App.xcodeproj/project.pbxproj" ALLOW
run "git add a pbxproj" Bash \
    "git add App.xcodeproj/project.pbxproj" ALLOW

# --- unrelated commands ------------------------------------------------------
run "unrelated write" Bash "echo hi > /tmp/x.txt" ALLOW

echo ""
echo "PASS: $PASS  FAIL: $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
