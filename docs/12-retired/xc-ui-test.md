# xc-ui-test — 退役于 2026-09-04

**当初要解决什么**（创建于 2026-03-16，`e8c2bce`）
E2E / 快照 / 无障碍审计类任务上场时，把 `references/xc-ui-test-guide.md` 那 **1513 行**（多屏 journey 测试、网络打桩、视觉回归、`performAccessibilityAudit`、CI 接入）送到模型面前。这是本仓最大的一份参考。

**为什么退役** — 只退壳，内容一行不动
与 [testing-guide](testing-guide.md) 同因：`context: fork` 参考加载器壳，声明的调用方是 `write-plan` 那张对执行 agent 无效的路由表。

**它比同批那几个更早就该退**：Topic Router 的 Testing 行**已经**把 `xc-ui-test-guide.md` 列在 API Reference 列里了 —— 也就是说这 1513 行一直是可达的，skill 壳从来没有提供过任何额外可达性，只是多了一层子代理。

**当时怎么做的**
`git show f4ddd65:apple-dev/skills/xc-ui-test/SKILL.md`（131 行 + eval.md）。131 行的壳包 1513 行的内容，比例上就能看出它是个包装。

**再做的话要不同在哪**
**退役前先查 Router 里有没有它。** 这个壳和 Router 行长期并存，谁也不知道对方在，因为「skill 名」和「文件路径」是两套命名，grep 一个搜不到另一个。做形态判断时要用**文件路径**做 key 去搜全仓，不是用 skill 名。

**如果要重做，形态应该是**
reference —— 已经是了，且已在 Topic Router 的 Testing 行。这个 skill 从头到尾没有存在的必要。
