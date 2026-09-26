---
tags: [collect-lesson]
max_turns: 20
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, "Bash(mkdir:*)", "Bash(date:*)", "Bash(claude --version)", "Bash(ls:*)"]
runs: 1
---
We just finished debugging why a hook's guidance never reached Claude.

Facts from this session:
- On Claude Code 2.1.283 (`claude --version` printed `2.1.283`), a PreToolUse hook that prints guidance to stderr and exits 0: the model never sees the text. Measured: the hook logged 23 nudges over 60 days and none reached the model.
- Printing `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "..."}}` to stdout with exit 0 does reach the model; verified in the same session.
- The hook now uses additionalContext.

Save this as a lesson in my global knowledge base.
