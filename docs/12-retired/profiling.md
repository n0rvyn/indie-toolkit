# profiling — 退役于 2026-09-04

**当初要解决什么**（创建于 2026-03-16，`e8c2bce`）
性能任务上场时，把 `references/profiling-guide.md` 那 715 行（os_signpost / OSSignposter / MetricKit / Instruments / XCTMetric）送到模型面前。

**为什么退役** — 形态选错了 + 接线断了
与 [testing-guide](testing-guide.md) 同因同源，一起退：`context: fork` 的参考加载器壳，声明的调用方是 `write-plan` 的路由表，而那张表的消费者（`execute-plan` 执行 agent）没有 `Skill` 工具。

**多一条它自己的问题**：Topic Router 的 Performance 行指向的是 `external/swiftui-performance-audit.md`，**不是** `profiling-guide.md`。也就是说这 715 行在退役前**两条路都不通** —— skill 壳没人调，Router 也没指向它。它是这批里唯一一个真正处于「内容在盘上、任何路径都到不了」状态的。

**当时怎么做的**
`git show f4ddd65:apple-dev/skills/profiling/SKILL.md`（128 行 + eval.md）。

**再做的话要不同在哪**
新增一份 reference 时，**当场把它挂进 Topic Router，跟写文件是同一个动作**，不是「之后补」。这 715 行在盘上躺了近半年、任何入口都到不了，就是因为「写内容」和「接入口」被拆成了两步，而第二步没人做。

这跟本仓 CLAUDE.md 的 *「改完了」是 grep 出来的，不是想出来的* 是同一条：新增的东西要在**消费者闭包内连通**才算做完，加一个文件不算。

**如果要重做，形态应该是**
reference。`apple-dev/references/profiling-guide.md`（715 行）一行不动，退役同时**新增** Topic Router 的 Performance 行指向它（原来那行指向别的文件，保留）。
