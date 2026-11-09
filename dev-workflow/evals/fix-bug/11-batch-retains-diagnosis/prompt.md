---
tags: [fix-bug, diagnosis-contract]
allowed_tools: [Read, Glob, Grep, Skill, Agent, Write, Edit, "Bash(python3:*)", "Bash(git:*)", "Bash(ls:*)", "Bash(mkdir:*)"]
---
Continue the multi-issue fix-bug workflow from the local state and evidence. These are synthetic local issue records, not GitHub issues. Reproduce and diagnose both reported defects through the supplied CLI, then prepare their repair plan. Stop after writing and linting the plan so I can review it; do not execute the repair plan yet. Record the exact write-plan invocation prompt in plan-request.md and use it when following write-plan. Record the outcome, remaining issue IDs and plan path in result.md. Keep work local.
