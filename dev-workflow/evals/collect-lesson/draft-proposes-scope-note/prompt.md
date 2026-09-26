---
tags: [collect-lesson]
max_turns: 20
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, "Bash(mkdir:*)", "Bash(date:*)", "Bash(claude --version)", "Bash(ls:*)"]
runs: 1
---
We just finished a resume bug in our app. Facts from this session, all on claude-agent-sdk 0.2.141:
- A streaming-input session, `query({prompt: <AsyncIterable>})` with `persistSession: true`, writes no resumable transcript: after the app restarts, `--resume <id>` finds nothing.
- Single-prompt `query({prompt: "..."})` still writes one on clean exit; we re-checked it in the same session.
- Fix: the app persists its own messages and replays them into the first streaming turn after a cold start.

Save this as a lesson in my global knowledge base.
