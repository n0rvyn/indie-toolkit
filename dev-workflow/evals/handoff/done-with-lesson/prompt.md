---
tags: [handoff]
max_turns: 20
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, "Bash(git:*)", "Bash(date:*)", "Bash(ls:*)", "Bash(wc:*)", "Bash(mkdir:*)", "Bash(cat:*)"]
runs: 1
---
What happened this session, all verified:
- The ledger showed wrong amounts. We first assumed Swift's `Decimal(string: "1,5")` returns nil for bad input, so the parser treated nil as the only failure. That was wrong: a failing test showed it returns 1. It parses the valid prefix and stops; only an invalid first character gives nil. Two fixes that relied on the nil check failed before we found this.
- Fixed by validating the whole string with a regex before calling `Decimal(string:)`. Tests green, committed, working tree clean, nothing left to do.

handoff or done
