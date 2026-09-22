---
type: llm
focus: last_message
weight: 0.5
---
回复必须转述 selftest 的实际结果，且体现「检查器本身已被验证」这一点：
至少提到一项正控（clone -> SHARED、sparse 检测、df 能观测到写入、DENIED/ABSENT 正控之一）。

不合格的情况：
- 只说「自检通过」而不给任何具体对照项
- 把 SKIP 项说成通过
- 给出了清理建议或清单（本轮明确要求不给）
