#!/bin/bash
# Protect .pbxproj and .xcworkspace files from direct editing.
# Used as a PreToolUse hook for Edit/Write/Bash tools.
# Reads tool input JSON from stdin, checks file_path or command.

input=$(cat)

tool_name=$(echo "$input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_name', ''))
except:
    print('')
" 2>/dev/null)

deny_msg='{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Direct editing of .pbxproj/.xcworkspace files is prohibited. Use Xcode or xcodebuild to manage project structure."}}'

if [ "$tool_name" = "Edit" ] || [ "$tool_name" = "Write" ]; then
    file_path=$(echo "$input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('file_path', ''))
except:
    print('')
" 2>/dev/null)

    if echo "$file_path" | grep -qE '\.(pbxproj|xcworkspace)'; then
        echo "$deny_msg"
        exit 0
    fi

elif [ "$tool_name" = "Bash" ]; then
    command=$(echo "$input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('command', ''))
except:
    print('')
" 2>/dev/null)

    # Deny only when a modification verb and the protected extension appear in
    # the SAME statement segment, after heredoc bodies are stripped.
    #
    # 2026-08-16: two reproduced false positives, each with a different cause.
    #   (a) find ... \( -name "*.xcodeproj" -o -name "*.xcworkspace" \) 2>/dev/null
    #       -> read-only. The old redirect pattern `>\s*[^&]` matched the `2>` in
    #          `2>/dev/null`, reading an fd redirect as "writes a file". Fixed by
    #          the (?<![0-9]) lookbehind plus an explicit /dev/null exclusion.
    #   (b) python3 - <<EOF ... paths: - "**/*.xcworkspace/**" ... EOF
    #       -> authoring a rules file. The extension sat in the heredoc body while
    #          `python` sat on the opening line, and the two were tested over the
    #          whole command independently. Fixed by stripping heredoc bodies and
    #          by requiring extension + verb in the same statement segment.
    # True positives (sed -i on a pbxproj, `> project.pbxproj`, `cat <<EOF >
    # project.pbxproj`, tee, a pbxproj passed to python) keep the extension and a
    # real write verb together in one segment, so they still deny.
    # 12 cases pinned in tests/test_protect_pbxproj.sh.
    decision=$(printf '%s' "$command" | python3 -c "
import re, sys

cmd = sys.stdin.read()

# 1. Strip heredoc bodies: content quoted into a program is data, not a target.
#    The opening line (which may carry '> file.pbxproj') is preserved.
cmd = re.sub(r'<<-?\s*[\"\']?(\w+)[\"\']?\n.*?\n\s*\1\b', ' <<HEREDOC ', cmd, flags=re.S)

EXT = re.compile(r'\.(pbxproj|xcworkspace)')
# A redirect counts as a write only when it is not an fd redirect (2>, 1>) and
# not aimed at /dev/null. Without this, every '2>/dev/null' on a read-only
# command looked like 'writes a file'.
REDIR = r'(?<![0-9])>{1,2}\s*(?!/dev/null)[^\s&|>]'
VERB = re.compile(r'(sed|awk|perl|ruby|python|echo|printf|cat\s*<<|tee|' + REDIR + ')')
GIT = re.compile(r'^\s*git\s')

# 2. Split into statement segments; a verb in one segment says nothing about a
#    path mentioned in another.
for seg in re.split(r'[;\n]|&&|\|\|', cmd):
    if not EXT.search(seg) or GIT.search(seg):
        continue
    if VERB.search(seg):
        print('deny')
        break
else:
    print('allow')
" 2>/dev/null)

    if [ "$decision" = "deny" ]; then
        echo "$deny_msg"
        exit 0
    fi
fi

exit 0
