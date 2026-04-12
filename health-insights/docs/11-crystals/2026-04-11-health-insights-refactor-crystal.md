---
type: crystal
status: active
tags: [health-insights, plugin-architecture, mongodb, visualization]
refs: []
---

# Decision Crystal: health-insights plugin refactor

Date: 2026-04-11

## Initial Idea

用户要求评估 health-insights plugin 的完整链路（入口、处理、存储、断点、基线、查询、趋势可视化、报告存储），同时考虑 skill 间的数据联动。评估后发现 3 个根本性架构缺陷，用户要求在不考虑实现复杂度的前提下重新设计，允许引入 cloud 数据库（MongoDB Atlas 免费层）和更好地搭配 Notion/Obsidian/Get笔记。

用户纠正了 3 个关键假设：
1. 「原始心率不存储逐条，ingest 时聚合」— 用户说「我想存原始值」
2. 「外部工具依赖 pdftotext/tesseract」— 用户说「可以让 Claude Code 直接读 PDF，不需要 API」
3. 「LLM API (MiniMax) 做 narrate/summarize」— 用户说「原始设计中让 LLM 做的事情完全是扯蛋，这本来就是 Claude Code 的 skill，不考虑再套一层 API。你需要比原始作者更聪明。记得这些都是 Claude Code 的 plugin（plugin 有自己的规范）」

## Discussion Points

### Phase A: 现状审计（crash 诊断 → 全链路评估）

1. **Server crash 根因**: ENOSPC (disk full)。`~/.adam/roles/钟南山/HealthVault/.ingest_buffer/` 积累 20GB（3902 日期目录，61435 个 .tmp，0 个 .yaml），finalize 从未执行，路径写入 Role workspace 而非 Obsidian vault
2. **Pipeline 完全断路**: ingest 写了原始数据但从未 finalize，下游 baseline/analyze/predict/report 全部无数据可用
3. **架构错误 — LLM API 套娃**: summarize.py/narrate.py 构建 prompt 调用外部 LLM API (Haiku/Sonnet)，但 plugin 运行在 Claude Code session 中，host session 本身就是 LLM

### Phase B: 放开约束后的重新设计

4. **存储层转移**: 文件系统 → MongoDB Atlas Time-Series Collection。Obsidian vault 从「存储+查询层」降级为「下游消费者」（接收 daily markdown 归档）
5. **原始数据保留**: 用户明确要求存储原始心率等逐条数据，不只是聚合值。MongoDB Time-Series Collection 适合这个场景
6. **可视化双平台**: Notion Dashboard（叙事报告 + 结构化数据 + 手机阅读）+ Grafana Cloud（实时监控 + 专业时间序列图表）
7. **跨 Plugin 联动**: health-insights 产出 → Get笔记 weekly digest（聚合摘要，非原始数据）→ ripple-compiler 语义搜索交叉引用；mactools calendar → MongoDB metadata enrichment；Adam delivery rule → WeChat 推送
8. **MCP 为主的技术栈**: scripts/ 用 pymongo 直连写入，agents/ 用 MongoDB MCP 查询 + Notion MCP 写入/可视化。Claude Code Read tool 替代 pdftotext/tesseract 读 PDF

## Rejected Alternatives

- **Wordbase 自建网站做可视化**: Rejected because — 需要新建完整模块（数据模型、API、图表库、页面），工作量大且和现有 Notion/Grafana 能力重复。Rejection scope: Wordbase 作为 health 可视化平台；does NOT reject Wordbase 用于其他用途
- **文件系统作为主存储**: Rejected because — 无法控制存储膨胀（20GB .tmp 证明）、无时间范围查询能力、无聚合 pipeline。Rejection scope: 文件系统作为 primary storage 和 query layer；does NOT reject 文件系统作为下游归档（Obsidian vault daily markdown）
- **外部 LLM API 调用做文本生成**: Rejected because — plugin 运行在 Claude Code session 中，host session 就是 LLM，套一层 API 是多余的网络往返 + token 消耗 + 脱离上下文管理。Rejection scope: scripts/ 中构建 prompt 调用 LLM API 的模式；does NOT reject scripts/ 做纯数据处理（parse, aggregate, transform）
- **只存聚合值不存原始数据**: Rejected because — 用户明确要求保留原始值。Rejection scope: ingest 时丢弃原始记录只保留 avg/min/max 的方案

## Decisions (machine-readable)

- [D-001] MongoDB Atlas 作为主存储和查询层，使用 Time-Series Collection 存储健康指标（含原始逐条数据）
- [D-002] Obsidian HealthVault 降级为下游消费者，接收 analyze agent 生成的 daily markdown 归档，不再承担 primary storage 角色
- [D-003] 消除 scripts/ 中所有 LLM API 调用（summarize.py build_haiku_prompt, narrate.py build_daily_context 等），scripts/ 只做数据处理输出结构化数据，所有推理由 agent 在 host Claude Code session 中执行 (linked: D-009 — plugin 规范决定了 script/agent 职责边界)
- [D-004] 存储原始健康数据（心率等逐条记录），不只是日聚合值
- [D-005] 可视化双平台：Notion Dashboard（叙事报告 + chart views）+ Grafana Cloud（时间序列监控 + 专业图表）
- [D-006] Claude Code Read tool 直接读 PDF 替代 pdftotext/tesseract 外部依赖；Read 失败时 fallback 到 pdftotext
- [D-007] scripts/ 用 pymongo 直连 MongoDB 写入数据；agents/ 用 MongoDB MCP tools 做查询；agents/ 用 Notion MCP tools 做写入和可视化
- [D-008] 跨 Plugin 联动：health → Get笔记（周度聚合摘要，非原始数据）；health → pkos IEF 产出；mactools calendar → MongoDB metadata enrichment；health alerts/summary → Adam delivery rule → WeChat
- [D-009] 遵循 Claude Code plugin 规范：scripts/ 输出结构化数据，agents/ 做推理，skills/ 做路由编排 (linked: D-003 — 直接推论)

### AI-supplemented

- [D-S01] ⚠️ AI 补充 Checkpoint 存 MongoDB singleton document 而非文件系统 — Reasoning: 当前 checkpoint 写文件导致路径错位 + 未持久化；既然主存储已迁移 MongoDB，checkpoint 也应在同一层，保证原子性
- [D-S02] ⚠️ AI 补充 Get笔记只接收聚合摘要，不接收原始健康数据或体检报告 — Reasoning: Get笔记是第三方服务，隐私边界需要控制数据出域范围
- [D-S03] ⚠️ AI 补充 清理现有 20GB .ingest_buffer 作为 P0 任务 — Reasoning: 磁盘空间已恢复但 buffer 仍占 20GB，且全部是未 finalize 的 .tmp 文件

## Constraints

- 这些是 Claude Code plugin，必须遵循 plugin 规范（scripts 做数据处理，agents 做推理，不套外部 LLM API）
- MongoDB Atlas Free Tier（512MB 存储限制）— 原始心率数据量需要验证是否超限
- 健康数据隐私：原始数据和体检报告不发送到第三方服务（Get笔记只接收聚合摘要）
- 本次重构的 lesson 和架构模式适用于后续其他 plugin 重构（session-reflect, domain-intel 等）

## Scope Boundaries

- IN: health-insights plugin 全链路重构（ingest → storage → baseline → analyze → predict → report → visualize）
- IN: MongoDB Atlas 集成（已创建集群 HealthMetrics，MCP 已连接）
- IN: Notion Dashboard 可视化（4 DB schema + chart/dashboard views）
- IN: 跨 Plugin 数据联动（Get笔记、pkos IEF、mactools calendar、Adam delivery）
- IN: Grafana Cloud 时间序列可视化
- OUT: 其他 plugin 重构（session-reflect, domain-intel — 用户明确说「之后接下来想重构」，不在本次 scope）
- OUT: Wordbase 网站开发
- OUT: iOS 端自动导出机制（需要 Shortcut 或 App，不在 plugin 重构范围）
