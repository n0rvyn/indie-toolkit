# audit-finishing-touches — 退役于 2026-09-04（4 项检查搬进 design-reviewer）

**当初要解决什么**
模块功能做完了但 UI「一股 AI 味」/「缺少性格」时，跑一遍 §17–§20 的机械打磨扫描：边框过度、控件用系统默认样式、卡片背景无装饰、空状态缺失、大标题区无装饰。明确**不做主观设计判断**，只报机械缺口，输出必修/建议/灵感三档。

**为什么退役** — 只读检查，且没有调用方
形态判据（见 [README](README.md)）：它**看代码、报发现、不改文件** —— 这是 reviewer，不是 skill。而它是 `user-invocable: false` 且全仓无人 dispatch，等于一个不能被人敲、也不会被机器调的检查。

**去向**：5 项检查里有 4 项 `design-reviewer` 没有覆盖，全部搬过去，成为 A13–A16：

| 原检查 | 去向 | 为什么不是重复 |
|---|---|---|
| Check 1 边框过度 | A13 | design-reviewer 全文不含 border 计数 |
| Check 2 控件默认样式 | A14 | 同上，含那套花括号配对的父容器扫描 |
| Check 5 Hero 无装饰 | A15 | 含文件名 escalation（`Dashboard`/`Home`/`Hero`/…）|
| Check 3 材质卡片无装饰 | A16 | **差点被误判为重复** —— 见下 |
| Check 4 空状态 | 不搬 | 它本来就不扫描，只是一句指针 |

**Check 3 那次误判值得记**：初判把它归为「A5 卡片与容器已覆盖」。读原文才看清 A5 问的是**同类卡片彼此一致吗**，Check 3 问的是**这张卡有没有装饰** —— 两张一样朴素的卡片能一起通过 A5。**"都跟卡片有关"不等于"是同一个检查"**，判重复要读两边的原文，不能靠标题相似度。

Check 4 的处境不一样：它自己写明「本 skill **不重复扫描**」，只输出一句指向 `feature-reviewer` B3 和 `ui-reviewer` 的提示。而 `/review-execution` 已经按 diff 形状派发那两个 agent，这句指针没有对象了。

**当时怎么做的**
`git show f4ddd65:apple-dev/skills/audit-finishing-touches/SKILL.md`（约 225 行）。每项检查都写清了机械规则、已知盲点、已知误报、分级映射 —— 这份质量是它内容能整体搬走的原因。

**再做的话要不同在哪**
**一组机械检查的归宿是某个 reviewer 的一节，不是一个新 skill。** 判据：它改不改文件？不改 → 它是 lens 或 agent 的一节。做成 skill 就要有人敲，而 `user-invocable: false` 的 skill 连敲都不允许 —— 这两个属性一起出现就是自相矛盾，写下的当时就能看出来。

它写得最好的那部分反而最容易随退役一起丢：**每项检查都注明了已知盲点与已知误报**（多行 `.overlay` 那个 grep 匹配不到、间接声明的 Toggle 会误报）。搬运时这些必须一起搬 —— 少了它们，读者会把漏报当成"检查过了没问题"，正是 GATE「零结果 → 禁止下结论」那条。

**如果要重做，形态应该是**
不重做。新的机械打磨检查直接加进 `apple-dev/agents/design-reviewer.md` 的 Part A，由 `/review-execution` 在 `HAS_NEW_VIEW` 时派发。
