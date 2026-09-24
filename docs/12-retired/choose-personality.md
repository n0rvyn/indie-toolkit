# choose-personality — 退役于 2026-09-24

**当初要解决什么**：新项目还没有设计系统时，先用 6 个问题把「设计性格」（严肃 / 活泼、密 / 疏……）问清楚，推导出配色、字体、圆角和语气，写成 `docs/02-architecture/design-personality.md`，给 `generate-design-system` 和 `brainstorm` 当输入。

**为什么退役**：需求被别处覆盖了。设计现在从 Claude Design 的 Design / Design System 交接过来，性格和 token 在那边就定了，不再需要在代码仓里靠问答推一份。60 天会话记录里调用 0 次（本机记录最早到 2026-08-05），用户已经不记得它是做什么的。而且它不是 `disable-model-invocation`，描述每轮都占上下文。

- 来源：session_01WHz4QdvADFm4LqjfETYqn5 用户原话「retire， now we have Design and Design System, no long need it」

**当时怎么做的**：6 问逐个 AskUserQuestion → 配色 / 字体候选 → 圆角刻度和语气 → 写 `design-personality.md`。`git show 4583a9f:dev-workflow/skills/choose-personality/SKILL.md`

**再做的话要不同在哪**：先确认设计是否已经来自外部设计工具。设计源在外部时，代码仓侧只该消费 token，不该再推导一遍性格。

**如果要重做，形态应该是**：不做。设计性格属于 Claude Design 的 Design System 类型。
