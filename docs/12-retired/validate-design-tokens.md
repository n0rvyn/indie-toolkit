# validate-design-tokens — 退役于 2026-09-04

**当初要解决什么**（创建于 2026-03-10，`053793f`）
扫 SwiftUI View 文件，找写死的值（`.padding(15)`、`Color(hex:)`、`.font(.system(size:14))`、圆角、阴影、`frame` 宽度），报出来但不改。九个检查段（§0 废弃 API、§1/1a/1b 间距、§2 颜色、§3 字体、§4 圆角、§5 阴影、§6 布局宽度、§7 DESIGN.md 交叉核对）。

**为什么退役** — 形态选错了（只读检查 ≠ skill），且唯一独有的一段死在别人的前提上
两半：

**§0–§6 是重复的，而且是**明知故犯**的重复。** 2026-06-28 那份 reviewer-slimdown 计划把 `ui-reviewer` / `design-reviewer` / 本 skill 三方**统一指向同一份权威** `apple-dev/references/design-contract-schema.md`（§1 间距集合 `{2,4,8,12,16,24,32,48,64}`、§2 颜色、§3 同后缀布局一致性算法）。统一判据是对的，但它同时把三者变成了同一个检查的三个副本 —— 而其中两个是 agent、由 `review-execution` 在 `HAS_VIEW_MODIFIED` 时自动派发，第三个是个 `user-invocable: false` 的 skill，**没有任何自动通道会调它**。

**§7（DESIGN.md ↔ Swift 漂移）是它唯一独有的一段**，而它死在 [sync-design-md](sync-design-md.md) 那同一个前提上：真实项目里 `DESIGN.md` 和 `DesignSystem.swift` 共存的只有 2 个，一个是管线自己的测试仓，另一个的 DESIGN.md 自导入日起没改过。

**形态判据**：它看代码、报发现、**明写「Do not auto-fix. This skill reports only.」** —— 这是 reviewer 的定义，不是 skill 的。只读检查的归宿是 `review-execution` 下的一个 lens，那里有自动路由；做成 skill 就只能等人来敲，而它连敲都不允许（`user-invocable: false`）。

**当时怎么做的**
`git show f4ddd65:apple-dev/skills/validate-design-tokens/SKILL.md`（270 行）。

**再做的话要不同在哪**
两条：

1. **判据统一之后，要接着问「那这三个还都需要吗」。** 那份 slimdown 计划做对了一半 —— 消除了判据分歧（同一个间距值不再被两个 reviewer 判出两种结果），但没有处理「同一份判据现在有三个执行者」。**统一判据的下一步必然是收敛执行者**，停在第一步就把重复固化下来了。
2. **`user-invocable: false` + 没有自动调用方 = 这个组件是死的**，写下这两个属性的时候就能算出来，不用等半年。这是可机械检测的：`.claude/skills/call-graph/scripts/call_graph.py --orphans` 一行就报。

**如果要重做，形态应该是**
不重做。能力去向：
- §0–§6 → `review-execution` 在 `HAS_VIEW_MODIFIED` 时派发的 `apple-dev:ui-reviewer`，判据同源（`design-contract-schema.md`）；
- §7 → 随 DESIGN.md 前提一起放弃。

判据文件 `apple-dev/references/design-contract-schema.md` 不动，它现在的消费者是那两个 reviewer。
