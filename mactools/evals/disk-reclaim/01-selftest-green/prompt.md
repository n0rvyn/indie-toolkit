---
tags: [disk-reclaim, mactools]
max_turns: 12
timeout_seconds: 900
allowed_tools: [Skill, Read, "Bash(bash:*)", "Bash(python3:*)", "Bash(ls:*)", "Bash(chmod:*)"]
runs: 1
---
用 disk-reclaim 技能先自检一遍它的检查器，把结果原样报给我。

不要清理任何东西，也不要给我清理建议 —— 这一轮只要知道那些检查器自己是不是好的。
