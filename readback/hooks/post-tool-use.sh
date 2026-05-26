#!/usr/bin/env bash
# readback: post-tool-use — when intent-echoer agent returns, re-inject paste-verbatim mandate
# Background: UserPromptSubmit-injected mandate gets distance-decayed across long agent
# dispatch turns. By PostToolUse time the main model often acknowledges dispatch
# ("回读已发出") without pasting the agent's 3-paragraph output into its reply body,
# leaving the user staring at a collapsed tool-result panel. This hook fires right
# after intent-echoer returns, when the agent output is in the immediate prior turn.
set -e
trap 'echo "{}"; exit 0' ERR

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')

# CC's PostToolUse for Task tool uses matcher "Agent" (verified against
# dev-workflow/hooks/hooks.json and verify-agent-output.py in this repo).
case "$TOOL" in
  Agent|Task) ;;
  *) echo "{}"; exit 0 ;;
esac

# Identify intent-echoer dispatches only (skip every other agent type)
SUBAGENT=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty')
case "$SUBAGENT" in
  intent-echoer|readback:intent-echoer) ;;
  *) echo "{}"; exit 0 ;;
esac

REMINDER=$(cat <<'REMINDER_EOF'
[readback-paste-reminder] The `intent-echoer` agent just returned. Its 3-paragraph output is the user-facing readback. You MUST paste it verbatim into your next reply message body (NOT only via the collapsed tool-result panel — users cannot see tool results without manually expanding them).

Required format for your next message:

```
{verbatim 3-paragraph agent output, unmodified, no preamble}

按 mandate 等你确认。回「go」/「直接做」我就展开；理解偏了告诉我哪里偏。
```

Do NOT send any of these:
- "回读已发出，等你确认或修正。"
- "已 dispatch readback agent，请查看结果。"
- "Intent echoer 完成，请确认。"

These hide the readback in a collapsed panel and the user sees nothing. The agent output IS your message text.
REMINDER_EOF
)

jq -n --arg ctx "$REMINDER" '{
  hookSpecificOutput: {
    hookEventName: "PostToolUse",
    additionalContext: $ctx
  }
}'
