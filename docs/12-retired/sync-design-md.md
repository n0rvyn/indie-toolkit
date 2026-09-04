# sync-design-md — 退役于 2026-09-04

**当初要解决什么**（创建于 2026-04-27，`63fa065`）
Google Stitch 导出的 `DESIGN.md`（9 段格式）和项目里的 `DesignSystem.swift` 是同一套设计 token 的两份副本，会漂移。这个 skill 做双向同步：`to-swift` 把文档写进 Swift，`from-swift` 反向回写，`check` 只报漂移不改文件。它是这一族里**唯一会写文件**的那个。

**为什么退役** — 前提不成立
一个双向同步工具，要同步的两个文件必须同时存在。实测（2026-09-04 全量扫 `~/Code/Projects`，26 个项目）：

| | 数量 | 是哪些 |
|---|---|---|
| 有 `DesignSystem.swift` | 20 | 大多数 iOS 项目 |
| 有 `DESIGN.md` | 7 | 其中 6 份躺在设计导出目录里（`stitch_design_*/`、`design/`、`design-contract/`、`contract/`） |
| **两者都有** | **2** | `claude-design-fidelity`、`Pantrix` |

那 2 个里：
- `claude-design-fidelity` 是**这条管线自己的保真度测试仓**，不是真实项目；
- `Pantrix` 的 `stitch_design_pantrix/pantrix_orchard/DESIGN.md` 是 Stitch 导出件，96 行 6 段，git 记录里最后一次改动是 `2026-03-22 Initial project setup` —— **导入那天写进去，之后再没动过**。没动过就没有漂移，没有漂移就没有可同步的东西。

也就是说：这个工具服务的场景，在真实项目里从来没有真正发生过。它不是被谁取代了，是它等的那个前提没来。

**留着比删掉更糟**：下次有人想做设计同步，会看到有个现成工具，然后花时间去满足它那个不会成立的前提。

**当时怎么做的**
`git show f4ddd65:apple-dev/skills/sync-design-md/SKILL.md`（212 行）。Step 2 先按 `project-kickoff` 的 doc-templates 识别规则验 DESIGN.md 是不是 Stitch 格式（≥6 段），不是就停；Step 4 逐 token 比对（颜色按通道 max-delta ≤ 4，间距要求完全相等，阴影透明度 ±0.01）；Step 5 才落笔改文件并编译验证。

**再做的话要不同在哪**
**先数一遍前提出现过几次，再决定做不做。** 这一条花掉的是 212 行 + 一份 eval + 四个月，而验证它的命令是一行 `find`：两个文件在真实项目里共存过几次？答案是「一次，还是我自己的测试仓」。

这比「功能做得对不对」更靠前：Step 4 的比对规则是对的（对到 `design-parity-build:89` 直接把那几个阈值抄了过去），但**一个正确的答案回答的是一个没人问的问题**。

顺带一条：**用自己的测试仓当「有人在用」的证据，等于没有证据。** 这个仓两个文件都有，恰恰因为它是为了测这条管线才建的。

**如果要重做，形态应该是**
先别做 skill。真的遇到「设计文档和 Swift token 两头维护」的项目时，第一步是问**为什么要两头维护** —— `design-handoff/` 那条链（`design-spec-contract` 产出 DESIGN.md + tokens.css + 镜像的 `Tokens.swift`）已经是单一来源生成两份，源头就不产生漂移，比事后同步更根本。

Step 4 的数值阈值已经内联在 `apple-dev/skills/design-parity-build/SKILL.md` 的 Reuse rules 里（颜色按通道 ≤ 4 / 间距精确 / 阴影 ±0.01），不随本 skill 消失。
