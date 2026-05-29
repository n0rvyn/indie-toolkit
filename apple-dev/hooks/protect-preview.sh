#!/bin/bash
# Protect #Preview blocks from silent deletion.
# Used as a PreToolUse hook for Edit/Write/MultiEdit tools.
# Reads tool input JSON from stdin, asks for confirmation if a Swift file's
# #Preview count decreases (deleting a #Preview as if it were unused code).
# Fail-open: any parse error -> exit 0 (never hard-blocks on a script bug).

input=$(cat)

tool_name=$(echo "$input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_name', ''))
except:
    print('')
" 2>/dev/null)

ask_msg='{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"#Preview is protected visual-feedback infrastructure (render-preview / run-phase visual loop depends on it). When modifying a View, maintain its #Preview — do not delete it as if it were unused code. If you are deleting the entire View, confirm that explicitly."}}'

# Count #Preview + PreviewProvider occurrences in a string. Fail-open to 0.
count_previews() {
    echo "$1" | python3 -c "
import sys
try:
    content = sys.stdin.read()
    print(content.count('#Preview') + content.count('PreviewProvider'))
except:
    print(0)
" 2>/dev/null
}

if [ "$tool_name" = "Edit" ]; then
    file_path=$(echo "$input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('file_path', ''))
except:
    print('')
" 2>/dev/null)

    # Only process Swift files
    if ! echo "$file_path" | grep -qE '\.swift$'; then
        exit 0
    fi

    old_string=$(echo "$input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('old_string', ''))
except:
    print('')
" 2>/dev/null)

    new_string=$(echo "$input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('new_string', ''))
except:
    print('')
" 2>/dev/null)

    old_count=$(count_previews "$old_string")
    new_count=$(count_previews "$new_string")

    # Trigger if #Preview count decreases (includes new_string empty = deleting
    # the matched #Preview fragment while the View elsewhere is retained).
    # Whole-View deletion also asks — confirmation is cheap and the reason explains it.
    # Scope limit: this protects against removal of the #Preview *token* only. Edits
    # inside a #Preview body that keep the token (old_count == new_count) are not gated;
    # body correctness is caught downstream by render-preview, not here.
    if [ "$old_count" -gt 0 ] 2>/dev/null && [ "$new_count" -lt "$old_count" ] 2>/dev/null; then
        echo "$ask_msg"
        exit 0
    fi

elif [ "$tool_name" = "MultiEdit" ]; then
    file_path=$(echo "$input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('file_path', ''))
except:
    print('')
" 2>/dev/null)

    # Only process Swift files
    if ! echo "$file_path" | grep -qE '\.swift$'; then
        exit 0
    fi

    # Sum #Preview across all edits' old vs new strings; ask if the total decreases.
    decision=$(echo "$input" | python3 -c "
import sys, json
def c(s): return s.count('#Preview') + s.count('PreviewProvider')
try:
    data = json.load(sys.stdin)
    edits = data.get('tool_input', {}).get('edits', [])
    old_total = sum(c(e.get('old_string', '')) for e in edits)
    new_total = sum(c(e.get('new_string', '')) for e in edits)
    print('ask' if (old_total > 0 and new_total < old_total) else 'ok')
except:
    print('ok')
" 2>/dev/null)

    if [ "$decision" = "ask" ]; then
        echo "$ask_msg"
        exit 0
    fi

elif [ "$tool_name" = "Write" ]; then
    file_path=$(echo "$input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('file_path', ''))
except:
    print('')
" 2>/dev/null)

    # Only process Swift files
    if ! echo "$file_path" | grep -qE '\.swift$'; then
        exit 0
    fi

    # New file (no existing content to lose) -> allow
    if [ ! -f "$file_path" ]; then
        exit 0
    fi

    content=$(echo "$input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('content', ''))
except:
    print('')
" 2>/dev/null)

    existing_content=$(cat "$file_path" 2>/dev/null)
    existing_count=$(count_previews "$existing_content")
    new_count=$(count_previews "$content")

    # Trigger if #Preview count decreases (includes overwriting a preview-bearing
    # file with content that drops it, or emptying it).
    if [ "$existing_count" -gt 0 ] 2>/dev/null && [ "$new_count" -lt "$existing_count" ] 2>/dev/null; then
        echo "$ask_msg"
        exit 0
    fi
fi

exit 0
