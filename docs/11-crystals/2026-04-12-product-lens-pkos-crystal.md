---
type: crystal
status: active
tags: [product-lens, pkos, obsidian, notion]
refs: []
---

# Decision Crystal: Product Lens PKOS Integration

Date: 2026-04-12

## Initial Idea

我想把 `product-lens` 往 AI 定时运行的方向扩展。我的项目都在 `~/Code` 下面，希望 AI 定时去跑这个插件，回答这些问题：这些项目进度都咋样了，哪些适合接着搞，哪些有问题，应该如何调整，最近提交的这些 feature 到底怎么样。

同时，我希望采用双枢纽：本地 Markdown 为事实源，Notion 为管理视图。也就是 AI 先把结论写到本地 vault，再把摘要同步到 Notion database。

接下来要决定：是先设计、先写计划，还是先把决策沉淀下来。

## Discussion Points

1. **入口分层**: 先区分人的入口和 AI 的入口。人的入口走自然语言问题；AI 的入口不能靠模糊描述，而要走稳定的意图分类 + 结构化输入输出。
2. **产品定位变化**: 重新梳理后，确认 `product-lens` 当前更像单次分析工具；而用户真正需要的是定时运行的项目组合管家，持续判断哪些项目继续、哪些调整、哪些停止。
3. **AI 定时意图方向**: 讨论从"定时跑现有 evaluate/compare"转向更贴近组合管理的方向，例如项目组合扫描、项目进度脉冲、优先级重排、最近 feature 回顾、结论刷新。
4. **沉淀层选择**: 对比 `write-dev-guide`、`write-plan`、`crystallize` 三个 dev-workflow skill 后，确认：
   - `write-dev-guide` 过重，不适合这次任务
   - `write-plan` 是执行计划层，消费已定决策
   - `crystallize` 最适合先固化这轮架构决策，再让后续计划遵守
5. **双枢纽落地方式**: 确认最优解不是"只写 Notion"或"只写 Obsidian"，而是：
   - 本地 Markdown 为事实源
   - Notion 为管理视图
   - 自动运行时先写本地，再同步摘要到 Notion
6. **知识分层**: 进一步明确，自动运行结果不能直接全进 crystal。应分三层：
   - signal / scan：定时扫描看到的事实
   - verdict：本轮收敛出的判断
   - crystal：经过确认的稳定决策
   `write-plan` 只消费 crystal，不消费每天都在变化的 signal。
7. **与现有 PKOS 一致性**: 这次方案与已有 PKOS crystal 中的双枢纽方向一致：Obsidian 管知识本体，Notion 管状态与看板；本次是在 `product-lens` 层补出"项目组合判断与结论沉淀"的能力。

## Rejected Alternatives

- **直接把 `write-dev-guide` 当沉淀层**: Rejected because -- 它是项目级 phased development guide，不是决策或事实沉淀层。 Rejection scope: 本次 `product-lens + PKOS` 集成设计； does NOT reject `write-dev-guide` 用于未来更大范围的新项目规划。
- **直接用 `write-plan` 承接当前讨论**: Rejected because -- 计划会消费决策，但不会沉淀决策；若不先固化边界，后续计划容易漂移。 Rejection scope: 作为第一步； does NOT reject `write-plan` 作为 crystal 之后的第二步。
- **让 AI 定时直接跑完整 `/evaluate` 或 `/compare` 到所有项目**: Rejected because -- 成本高、噪音大，而且容易把"报告生成"误当"组合管理"。 Rejection scope: 作为默认定时策略； does NOT reject 对重点项目按需运行完整评估。
- **所有自动输出直接写成 crystal**: Rejected because -- crystal 应只承载稳定决策，不适合承接高频变化的扫描结果。 Rejection scope: 自动运行层； does NOT reject 将稳定结论升级为 crystal。
- **只存 Notion，不保留本地 Markdown**: Rejected because -- Notion 适合管理视图，不适合作为原始事实与长期知识的唯一来源。 Rejection scope: 单一 Notion 中心； does NOT reject Notion 作为摘要同步目标。

## Decisions (machine-readable)

- [D-001] `product-lens` 的入口分为两类：人入口与 AI 入口，分别设计
- [D-002] 人入口继续采用自然语言问题入口，不要求用户先理解 skill 名称
- [D-003] AI 入口采用稳定意图 + 结构化输入输出，不依赖自然语言营销式触发
- [D-004] AI 定时运行的核心目标是项目组合管理，而不是单次产品评估
- [D-005] 本地 Markdown 作为事实源，Notion 作为管理视图
- [D-006] 自动运行时，`product-lens` 先把结构化结果写入统一的 PKOS ingress / exchange 层，再由 PKOS 按自身标签与入库规则写入本地 vault，最后把摘要同步到 Notion database
- [D-007] 自动运行结果分层存储：signal / verdict / crystal
- [D-008] crystal 只用于沉淀稳定决策，不直接承接高频自动扫描结果
- [D-009] 本轮工作流程采用 `crystallize -> write-plan`
- [D-010] `write-dev-guide` 不作为本轮工作的入口技能
- [D-011] 后续 `write-plan` 应围绕 `product-lens + PKOS` 的 AI 意图、Markdown 信息模型、Obsidian/Notion 同步边界来展开

### AI-supplemented

- [D-S01] ⚠️ AI 补充：本地事实源建议落在 PKOS vault 中，而不是散落在各 repo 自己的 docs 目录。 Reasoning: 这样更符合"统一知识本体 + 跨项目查询"的双枢纽架构，也便于 Obsidian Bases 统一建视图。
- [D-S02] ⚠️ AI 补充：Notion 只同步摘要字段，不同步全文报告。 Reasoning: Notion 的价值在状态、排序、看板，不在承载长文知识。
- [D-S03] ⚠️ AI 补充：第一版 AI 意图可先围绕项目组合扫描、项目进度脉冲、优先级重排、最近 feature 回顾、结论刷新来命名与分工。 Reasoning: 这些方向最贴近用户明确提出的定时问题，但命名与边界仍应在计划阶段细化。

## Constraints

- 用户的项目集中在 `~/Code` 目录下，AI 定时任务需要以根目录扫描为基础
- 自动运行的目标是"知道哪些项目该继续、哪些有问题、最近 feature 怎么样"，不是生成高密度长报告
- 现有 `product-lens` 偏单次分析，需要新增 portfolio / refresh 这类长期能力
- 现有 PKOS 已确定双枢纽架构，本次方案必须与其保持一致
- Notion 写入能力当前存在实现缺口，尤其是属性更新与过滤查询能力仍需增强
- `write-plan` 会读取 crystal 作为后续计划约束，因此 crystal 中的决策必须尽量稳定、可检查
- 现有 `product-lens` 只有 `demand-check` 明确标为 auto-trigger，其它核心 skill 默认不是自动触发入口

## Scope Boundaries

- IN: 为 `product-lens` 设计 AI 定时运行的入口与意图
- IN: 设计本地 Markdown 事实源 + Notion 管理视图的沉淀架构
- IN: 明确 dev-workflow 各技能在本轮工作的使用顺序

## Source Context

- Design doc: none
- Design analysis: none
- Key files discussed:
  - docs/11-crystals/2026-03-21-pkos-crystal.md
  - docs/11-crystals/2026-04-08-cross-project-harvester-crystal.md
  - dev-workflow/skills/crystallize/SKILL.md
  - dev-workflow/skills/write-plan/SKILL.md
  - dev-workflow/skills/write-dev-guide/SKILL.md
  - product-lens/README.md
  - product-lens/skills/evaluate/SKILL.md
  - product-lens/skills/compare/SKILL.md
  - product-lens/skills/feature-assess/SKILL.md
  - product-lens/skills/demand-check/SKILL.md
