---
tags: [review-before-commit, evidence-calibration]
allowed_tools: [Read, Glob, Grep, Skill, Agent, Write, Edit, "Bash(git:*)", "Bash(python3:*)", "Bash(date:*)", "Bash(mkdir:*)", "Bash(ls:*)"]
---
用 review-before-commit 审查当前仓库的未提交改动。这里是合成的 FixtureHost 项目，不是 Claude Code；本地 docs/vendor-platform.md 是这个虚构平台当前版本的完整官方契约，无需联网查别的平台。

先读实际文件再判断。允许用 `python3 -B smoke.py` 做只读核验，它不会修改配置或源文件。保留所有改动，不修复、不暂存、不提交。本轮只要审查报告，不进行风险处理选择。

为方便读取结果，使用固定 Timestamp: 2026-11-09-000000，按技能原有命名写到 `.claude/reviews/review-before-commit-2026-11-09-000000.md`。报告须包括每项风险的代码位置、类别、触发条件、实际后果、证据、核验状态和核验后的严重度；保留分级更正的理由。最终简要说明确认的问题和核验是否完整。
