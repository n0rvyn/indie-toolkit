# product-lens — 退役于 2026-09-23

**当初要解决什么**
独立开发者的产品决策问题：这个想法值不值得做、要不要加这个功能、几个项目先做哪个。插件有 6 个技能（product-lens、evaluate、compare、demand-check、teardown、feature-assess）和 6 个代理，按需求真伪、市场、护城河等维度打分，再给出结论。

**为什么退役**
- 自 2026-08-05 以来调用 0 次，最后一次修改是 2026-04-17。
- 唯一的外部数据来源是 `market-scanner` 代理，它只有 WebSearch / WebFetch。所以各维度的分数，实际上是模型对网页片段的看法。
- 用户的判断：产品需求是个大课题，凭几个维度（Lens）解决不了。
- 对照：同一个仓库里的 `aso-research` 直接从 Apple 的接口拉真实数据（排名、联想词、竞品名称），它有人在用。

**当时怎么做的**
`git show d5e2e95:product-lens/`。评分口径在 `references/_scoring.md`、`_calibration.md`；Obsidian 笔记与 Notion 摘要的契约在 `references/pkos/`。

**再做的话要不同在哪**
先定数据来源，再定框架。维度框架本身不产生信息，信息得来自真实数据：商店排名、搜索联想、自己 app 的留存和付费。

**如果要重做，形态应该是**
挂在真实数据源上的技能，照 `aso-research` 那样做，而不是一套纯推理的打分框架。

来源：session_013jH44W8QaXm2UExGPkHABs 用户原话「‘product-lens’ 感觉没啥用，产品需求这是个大课题，凭几个Lens，我觉得做不到（仅仅是我的想法）」；随后在同一会话里说「go ahead」
