---
type: crystal
status: active
tags: [session-reflect, feedback-loop, cross-marketplace]
refs:
  - docs/06-plans/2026-05-16-skill-usage-insights-design.md
---

# Decision Crystal: Skill Usage Insights — Closed-Loop Plugin Improvement

Date: 2026-05-16

## Initial Idea

> 我的项目都在 ~/Code/Projects/ 中，而这个 Claude Code plugin marketplace 是我用的主力 skills 集，我有个想法，能否用 ~/.claude/projects/ 中的 session 记录，结合本项目的提交记录，在上一次提交到运行时间（如果有个定时任务的话）之间，跑类似 /insights 的 skill 来分析这些会话，分析它们用 skill 的频率，用 skill 的问题，然后结合这些真实数据，来 improvement 本 plugin marketplace，然后自动提 PR（有 /loop 可以定时比如按天，或者 3/5 天一次）。

## Discussion Points

### Phase A — 数据基础盘点

1. **现有基础设施盘点**：Claude Code 内置 `/insights` 只按 session 维度归并，不按 skill/plugin 维度。`personal-os/session-reflect` 已有 17 张 SQLite 表覆盖所需维度。
2. **Bug 实测定位**：`personal-os/session-reflect/scripts/parse_claude_session.py:393-412` 的 `_extract_plugin_component` candidates 列表只查 `command/skill_name/agent_type/name`，但当前 Claude Code 2.1.143 实际用 `skill` 和 `subagent_type` 两个字段——导致 1013/1013 `plugin_events.component` 全部 fallback 成字面 "skill"/"agent"。

### Phase B — 路线 pivot

3. **DP-001 推荐被推翻**：AI 初始推荐"在 indie-toolkit 仓内自建轻量 parser"，理由是"跨仓 PR 链长"。用户澄清 personal-os 也是自有 marketplace，跨仓不是组织边界——决议翻转为复用 session-reflect SQLite，把 bug 修复 + schema 扩展并入本计划。

## Rejected Alternatives

- **在 indie-toolkit 仓内自建 JSONL parser + 本地 rollup SQLite**：Rejected because — personal-os 也是用户自有仓，跨仓修复成本不再高；自建会重复造轮子并永远落后于 session-reflect 已有 17 张表（corrections / ai_behavior_audit / pre_brief_hints / ...）的覆盖。Rejection scope: 仅拒绝"在 indie-toolkit 仓内重新解析 JSONL 并维护本地 SQLite"这条路径；does NOT reject 后续如有 indie-toolkit 独有维度需求时再补充小工具。

## Decisions (machine-readable)

- [D-001] `/master insights` 复用 `personal-os/session-reflect` 的 SQLite (`~/.claude/session-reflect/sessions.db`) 作为唯一数据源，不在 indie-toolkit 仓内自建 JSONL parser 或本地 rollup SQLite。
- [D-002] `personal-os/session-reflect` 的 enhance 工作纳入本计划工作范围（不再视为外部依赖）；具体 enhance 项目（bug 修复、backfill、schema 扩展具体字段）在 `/write-plan` 阶段拆解。

## Scope Boundaries

- IN: 用 `~/.claude/projects/` 的 session 记录分析各 skill 使用频率
- IN: 用 session 记录分析 skill 使用中暴露的问题
- IN: 结合本项目（indie-toolkit）的提交记录关联使用变化
- IN: 定时跑分析（具体周期与机制由 plan 决定）
- IN: 自动提 PR（PR 作用范围与机械边界由 plan 决定，编入 skill 自身配置）
- IN: `personal-os/session-reflect` 的 enhance 工作

## Source Context

- Design doc: `docs/06-plans/2026-05-16-skill-usage-insights-design.md`
- Design analysis: none
- Key files discussed:
  - `~/.claude/projects/-Users-norvyn-Code-Skills-indie-toolkit/*.jsonl`（数据样本，58 个）
  - `~/.claude/usage-data/{facets,session-meta}/*.json`（原生 /insights 输出）
  - `~/.claude/session-reflect/sessions.db`（复用目标 SQLite）
  - `/Users/norvyn/Code/Skills/personal-os/session-reflect/scripts/parse_claude_session.py:393-412`（Bug 根因位置）
  - `/Users/norvyn/Code/Skills/personal-os/session-reflect/scripts/sessions-schema.sql`（schema 扩展位置）
  - `/Users/norvyn/Code/Skills/indie-toolkit/.claude-plugin/marketplace.json`（数据过滤白名单源）
  - `/Users/norvyn/Code/Skills/indie-toolkit/skill-master/`（新能力候选归宿，最终由 plan 决定）

## Plan-Stage Topics (to discuss in /write-plan)

以下题目本会话讨论过但属于 plan 阶段范畴，不作为 Crystal 决议：

- 新能力归宿：扩展 `skill-master` vs 新建独立插件
- session-reflect schema 扩展具体字段清单：`invocation_trigger` / `duration_ms` / `parent_tool_use_id` / `cwd` / `skill_proactive_triggers` 表 / `effort_level`
- 调度机制：`/loop` / `launchd` / `/schedule` Claude routine / 混合
- 数据扫描范围：跨项目全扫 vs 限定项目 + 过滤逻辑放在 SQL 还是 reader
- 隐私 SOP：脱敏规则、截断长度、什么落 committed 文件
- 自动 PR 行为边界：能改哪些文件、不能改哪些（**应编入 skill 自身 `allowed-tools` + SKILL.md + 可选 hooks，不进 Crystal**）
- 跨次运行去重机制（dismissed proposals 持久化）
- 实施节奏：personal-os 与 indie-toolkit 两侧的先后顺序
