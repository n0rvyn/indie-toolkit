# localization-setup — 退役于 2026-09-04

**当初要解决什么**（创建于 2026-03-10，`053793f`）
做本地化时，把 `references/localization-guide.md` 那 463 行（String Catalogs / 复数规则 / 变量处理）送到模型面前。

**为什么退役** — 形态选错了，而且从来没有过调用方
与同批四个参考加载器壳同因（见 [README 的形态判据](README.md)），但它是最彻底的一个：**从未接线**。

它自己的 description 写着：*"no skill currently calls it — reach it by reading references/localization-guide.md directly until a caller is wired up"*。

「until a caller is wired up」—— 从 2026-03-10 到退役，**近半年，那个 caller 没有出现**。同时 Topic Router 里**也没有 Localization 行**。这份 463 行的参考，两条路都不通，唯一的到达方式就是 description 里那句「直接去读文件」，而那句话本身只有加载了这个永不加载的 skill 才看得见。

**当时怎么做的**
`git show f4ddd65:apple-dev/skills/localization-setup/SKILL.md`（109 行 + eval.md）。

**再做的话要不同在哪**
**「等以后接上」= 永远接不上。** 一个组件在创建时就没有消费者，它不会自己长出来一个。写下 *"until a caller is wired up"* 的那一刻，正确动作是二选一：当场把 caller 接上，或者根本不建这个壳、直接把文件挂进 Router。

这跟本仓 CLAUDE.md 里那条 *「工作量大所以先标记后续」= 永远不清理* 是同一个形状 —— 都是把一个已经看见的缺口写成 TODO 就走了。**description 里出现「暂无 / 尚未 / until」这类词，就是这个组件当场不成立的自述证据。**

**如果要重做，形态应该是**
reference。`apple-dev/references/localization-guide.md`（463 行）一行不动，退役同时**新建** Topic Router 的 Localization 行 —— 这是它半年来第一条真正可达的路径。
