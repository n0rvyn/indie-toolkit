# fetch-swift-api-updates — 迁出于 2026-09-04（不是退役）

**去向**：`.claude/skills/fetch-swift-api-updates/`（本仓本地 skill，不随 marketplace 发布）

**当初要解决什么**（创建于 2026-03-10，`053793f`）
WWDC 之后 Swift / SwiftUI API 会变，`apple-dev/references/swift-api-changes-ios18.md`（311 行）和 `swift-api-changes-ios26.md`（256 行）需要有人更新。这个 skill 去抓 WWDC session notes，把新 API 追加进那两份参考。

**为什么迁出** — 它在错误的仓库范围里
它维护的目标是 **`apple-dev/references/swift-api-changes-*.md`，也就是这个仓库自己的文件**。但它被打包进 `apple-dev` plugin 发给了下游用户 —— 而下游用户的机器上没有这个仓库，他们装到的是 plugin 的 cache 副本，跑这个 skill 只会去改一份用完即弃的 cache，或者干脆找不到目标文件。

**这解释了它为什么零调用**：`grep -rn "apple-dev:fetch-swift-api-updates"` 全仓 0 命中（唯一提到它的是 `apple-dev/README.md` 的表格）。它对下游没用，对上游（这个仓库的维护者）又因为被封装成 plugin skill 而不在手边。

**⚠️ 它维护的参考还活着，别一起删**：`swift-api-changes-ios26.md` 有真实消费者 —— `apple-dev/skills/generate-design-system/SKILL.md:79` 把它列为 Liquid Glass / glassEffect 的补充来源。两份参考原地不动。

**当时怎么做的**
`git show f4ddd65:apple-dev/skills/fetch-swift-api-updates/SKILL.md`（138 行 + eval.md）。

**再做的话要不同在哪**
**先问「这个 skill 改的文件，属于谁的仓库」。**

- 改**用户项目**里的文件 → 它是 plugin skill，发出去；
- 改 **plugin 自己**的文件 → 它是这个 marketplace 的维护工具，属于 `.claude/skills/`，**不发布**。

这一条判据在本仓还能筛出别的：任何写 `apple-dev/references/**` 或 `*/skills/**` 的 skill，都不该在发布物里。

**形态**：仍然是 skill（它抓取 + 写文件，不是只读检查也不是知识），只是换了归属地 —— 从发布物挪到本地维护工具，和 `.claude/skills/call-graph/` 并列。
