# testing-guide — 退役于 2026-09-04

**当初要解决什么**（创建于 2026-03-10，`053793f`）
写单测 / mock / TDD 任务时，把 `references/testing-guide.md` 那 553 行（UT/UI 测试模式、Page Object、等待策略、mock、覆盖率）送到模型面前。

**为什么退役** — 形态选错了 + 接线本来就是断的
两件事叠在一起：

1. **形态**：它是 `context: fork` + `agent: Explore` 的参考加载器壳，只干一件事——读一个 markdown 再复述。同一份文件从 `apple-swift-context` 的 Topic Router 一行可达，主线一次 Read，不用起子代理。（这一档共五个，理由相同，见 [README 的形态判据](README.md)。）

2. **接线**：它 description 里写的调用方是 *"dev-workflow:write-plan routes UT/Mock/TDD tasks here"*，而 `write-plan` 的路由表是**结构性死亡**的 —— 写进计划的 `UT/Mock/TDD → apple-dev:testing-guide` 由 `execute-plan` 的执行 agent 来消费，那个 agent 的工具是 `Glob, Grep, Read, Write, Edit, Bash, LSP`，**没有 `Skill`**。它读到一个 skill 名，却没有调用 skill 的能力。这张表从写下那天起就没有能生效过。

**当时怎么做的**
`git show f4ddd65:apple-dev/skills/testing-guide/SKILL.md`（116 行 + eval.md）。思路是「计划里写 skill 名，执行时自动加载对应知识」。

**再做的话要不同在哪**
两条，第二条更贵：

- 计划里给下游 agent 的**永远写路径，不写 skill 名**。agent 能不能调 skill 取决于它的 `tools:` 列表，而写计划的人看不见那个列表。写 `apple-dev/references/testing-guide.md` 一定能读到，写 `apple-dev:testing-guide` 要赌。
- **「A 路由到 B」这句话要能被机械验证**。这条边只存在于两份 SKILL.md 的散文里，两年都没人发现它是断的。`.claude/skills/call-graph/` 就是为这个做的：它区分「真调用」和「只是提到」，跑一次就知道哪条边是想象的。

**如果要重做，形态应该是**
reference。`apple-dev/references/testing-guide.md`（553 行）一行不动，退役同时挂进 Topic Router 的 Testing 行。
