---
type: crystal
status: active
tags: [pkos, knowledge-management, obsidian, notion, adam]
refs:
  - docs/06-plans/2026-03-21-pkos-design.md
---

# Decision Crystal: PKOS

Date: 2026-03-21

## Initial Idea

如何利用 Claude Code 及周边软件（Notion/Obsidian/...）把整个信息的输入-处理-输出整合成一个有机的生态链。环境：macOS + iOS + cloud host + Claude subscription + coding plan。放开想象，大胆一点。

iOS 相当于一个采集终端，通过 iCloud 发到 macOS，macOS 上 Claude 定时任务处理信息，存到 Obsidian/Notion，定时跑分析做反馈闭环。iOS 上随时语音记录 + 多入口（Reminders、Notes 等）是好的信息入口。没有全周期流程做可视化管理，不知道有哪些信息。

## Discussion Points

1. **架构模式**: 提出三方案（Obsidian 中心 / Notion 中心 / 双枢纽），对比分析后用户选择双枢纽 — Obsidian 管知识关联，Notion 管运营状态，各做最擅长的事
2. **处理引擎**: 初始方案是 Claude Code CLI + cron。发现用户有两个半成品项目 Adam（Agent 编排服务器）和 Archon（AI 终端复用器）。验证 Agent SDK 可加载 CLI 插件后，确认用 Adam 替代 cron — 获得调度/并行/持久化/远程审批能力
3. **代码组织**: 四方案（纯插件 / 纯 Adam / Adam + 插件 / 新项目），选择 Adam + 新 pkos 插件 — Adam 管调度，插件管智能逻辑，普通 CLI 会话也能手动调用
4. **iOS 采集**: Reminders tags 在 macOS API 层面不可读（EventKit、AppleScript、SQLite 全验证），改用专用列表 "PKOS Inbox"
5. **语音转写**: Apple SFSpeechRecognizer 中文不支持离线，确定双引擎策略 — 英文走 Apple Speech，中文走 Whisper
6. **Notion 能力**: 属性更新和过滤查询是 notion_api.py 的代码缺口，非 API 限制，需增强
7. **Obsidian vs Notion 分工**: 同一条信息在 Obsidian 中是有深度有关联的知识笔记，在 Notion 中是一行有状态可统计的管道记录，通过 Obsidian Link 字段连通
8. **反馈环**: 确定三节拍模型 — 心跳（每日自动 signal 采集）、呼吸（每周 review + profile 建议）、脉搏（实时语音/flag 反馈）

## Rejected Alternatives

- **Obsidian 中心架构**: Rejected because — Obsidian 不擅长 Kanban/状态追踪/聚合统计，运营管理能力弱
- **Notion 中心架构**: Rejected because — Notion 无图谱视图/双向链接，知识关联能力弱；API 限流 + vendor lock-in
- **Claude Code CLI + crontab**: Rejected because — 无并行、无状态持久化、无容错、无远程审批；Adam 已有这些能力
- **纯 Adam 扩展（不建新插件）**: Rejected because — PKOS 逻辑耦合在 Adam 中，普通 Claude Code 会话无法访问这些能力
- **新独立项目**: Rejected because — 重复造轮子（调度/状态 Adam 已有；插件生态不可用）
- **Claude API 直接调用**: Rejected because — 完全丧失 Claude Code 插件生态，得不偿失
- **Reminders tags 作为分类标记**: Rejected because — macOS 上 EventKit/AppleScript/SQLite 均无法读取 tags（编译验证）
- **纯 Apple Speech 做语音转写**: Rejected because — 中文不支持离线，必须联网走 Apple 服务器

## Decisions (machine-readable)

- [D-001] 采用双枢纽架构：Obsidian 存储知识本体（内容、关联、图谱），Notion 存储运营状态（管道、指标、看板）
- [D-002] iOS 采集层使用 Apple 原生应用（Reminders、Notes、Voice Memo、Safari Share Sheet），不引入第三方 App
- [D-003] iCloud 作为 iOS → Mac 的传输层
- [D-004] Adam 作为 Mac mini 处理引擎，通过 settingSources 或 plugins 选项加载 indie-toolkit 插件
- [D-005] 新建 pkos 插件于 indie-toolkit，提供 /inbox、/signal、/digest、/vault、/evolve、/serendipity 等 skill
- [D-006] Adam 管"何时跑"（调度），pkos 插件管"跑什么"（智能逻辑）
- [D-007] iOS Reminders 使用专用列表 "PKOS Inbox" 替代 tag 过滤
- [D-008] 语音转写采用双引擎：英文用 Apple SFSpeechRecognizer，中文用 Whisper
- [D-009] 文件系统监测使用 launchd WatchPaths（原生），不安装 fswatch
- [D-010] 反馈环三节拍：心跳（每日自动 signal 采集）、呼吸（每周 review + profile 建议）、脉搏（实时反馈）
- [D-011] Notion notion_api.py 需增强：添加 update-db-item-properties 命令 + query-db 过滤参数支持
- [D-012] Adam 需添加 plugins 选项到 query() 调用、完整 cron 解析器、settingSources 默认改为 ["user", "project"]

## Constraints

- macOS Reminders tags 不可通过 API 读取（EventKit、AppleScript、SQLite 均验证失败）
- Apple SFSpeechRecognizer 中文转写必须联网
- Notion API 支持属性更新和过滤查询，但当前 Python 实现未暴露这些能力
- Adam 当前 settingSources 默认为 ["project"]，不加载用户级插件配置
- Adam 的 cron 解析器只支持简单 */N 模式，不支持完整 5 字段 cron 表达式
- Adam Issue #20 已记录 settingSources 增强需求

## Source Context

- Design doc: docs/06-plans/2026-03-21-pkos-design.md
- Design analysis: none
- Key files discussed:
  - /Users/norvyn/Code/Projects/Adam/src/worker/worker-entry.ts
  - /Users/norvyn/Code/Projects/Adam/src/scheduler/bree-engine.ts
  - /Users/norvyn/Code/Projects/Adam/adam.config.yaml
  - /Users/norvyn/.claude/skills/notion-with-api/scripts/notion_api.py
  - /Users/norvyn/Code/Skills/indie-toolkit/mactools/skills/reminders/scripts/reminders.swift
