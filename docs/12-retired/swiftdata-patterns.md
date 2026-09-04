# swiftdata-patterns — 退役于 2026-09-04

**当初要解决什么**（创建于 2026-03-10，`053793f`）
写 SwiftData 代码时，希望模型手上有 `references/swiftdata-guide.md` 那 673 行的建模 / 关系 / 查询 / 迁移 / 并发规则，而不是靠训练数据编。

**为什么退役** — 形态选错了，能力被 Topic Router 覆盖
它是一个 `user-invocable: false` + `context: fork` + `agent: Explore` 的**参考加载器壳**：派一个子代理去读一个 markdown 文件，再把内容复述回来。而 `apple-swift-context` 的 Topic Router 里 `| Data persistence | swiftdata-guide.md | external/swiftdata-api/ |` 这一行指向的是**同一个文件**，主线一次 Read 就到，不用起子代理。

它自己的 description 在退役前就写着实话：*"no skill currently calls it by name — dev-workflow:fix-bug reaches SwiftData rules through apple-swift-context instead"*。写下这句的人已经看见了结论，只是没做处置。

`paths:` 帮不上忙 —— 2026-08-16 实测：`paths:` 是**限制器不是触发器**，它只收窄「允许自动加载的范围」，不制造加载。没有调用方 = 永不运行。

**当时怎么做的**
`git show f4ddd65:apple-dev/skills/swiftdata-patterns/SKILL.md`（115 行 + eval.md）。思路是「每个知识域一个 skill 壳，靠 `paths:` 自动上场」。

**再做的话要不同在哪**
不要为「让模型读到某份参考」单独做一个 skill。这件事的代价不是零：一个 fork 壳 = 一份 system prompt + 一套工具 schema + 一轮工具循环，换来的是主线一次 Read 就能拿到的同一段文本。**判据：这个 skill 除了 Read 一个文件还干别的吗？不干 → 它应该是 Topic Router 里的一行。**

**如果要重做，形态应该是**
reference（已经是了 —— `apple-dev/references/swiftdata-guide.md` 一行不动，仍挂在 Topic Router 的 Data persistence 行）。
