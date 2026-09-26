---
tags: [collect-lesson]
max_turns: 20
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, "Bash(mkdir:*)", "Bash(date:*)", "Bash(claude --version)", "Bash(ls:*)"]
runs: 1
---
We just hit an API quirk worth keeping. Facts from this session:
- `Decimal(string: "1,5")` returns 1, not nil; `Decimal(string: "35块")` returns 35. It stops at the first invalid character and returns the prefix value. Only an invalid first character gives nil.
- Our amount parser trusted "nil means invalid" and wrote wrong amounts into the ledger.
- Fix: validate the whole string with a regex before calling `Decimal(string:)`.

Save this as an API note in my global knowledge base.
