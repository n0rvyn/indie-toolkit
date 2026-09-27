---
tags: [handoff]
max_turns: 20
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, "Bash(git:*)", "Bash(date:*)", "Bash(ls:*)", "Bash(wc:*)", "Bash(mkdir:*)", "Bash(cat:*)"]
runs: 1
---
What happened this session, all verified:
- We assumed Swift's `Decimal(string: "1,5")` returns nil for bad input. A failing test showed it returns 1: it parses the valid prefix and stops. Two fixes that relied on the nil check failed before we found it. Fixed with a regex check first.
- Separately, we assumed `git stash` saves untracked files. It does not without `-u`; a new file was lost once and had to be rewritten.
- Tests green, committed, working tree clean, nothing left to do.

handoff or done
