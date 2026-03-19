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

    # Check if command targets .pbxproj/.xcworkspace with modification intent
    # Allow git commands (add, commit, diff, log, status, etc.) to pass through
    if echo "$command" | grep -qE '\.(pbxproj|xcworkspace)'; then
        if ! echo "$command" | grep -qE '^\s*git\s'; then
            if echo "$command" | grep -qE '(sed|awk|perl|ruby|python|echo|printf|cat\s*<<|tee|>\s*[^&]|>>)'; then
                echo "$deny_msg"
                exit 0
            fi
        fi
    fi
fi

exit 0
