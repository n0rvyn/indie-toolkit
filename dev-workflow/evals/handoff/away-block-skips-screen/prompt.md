---
tags: [handoff]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, "Bash(git:*)", "Bash(date:*)", "Bash(ls:*)", "Bash(wc:*)", "Bash(mkdir:*)", "Bash(cat:*)"]
runs: 1
---
我走开了，你自主推进，跑到重大 block 就 handoff。

现在的情况：`src/dates.py` 的时区修复改了两次，`tests/test_dates.py` 两次都红，而且红在同一条断言上。这就是重大 block。
