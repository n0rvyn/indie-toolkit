# code-audit — 退役于 2026-09-04（能力搬进 review-execution Lens F）

**当初要解决什么**
Swift 项目的综合代码审计，五类：安全（Step 2）、并发安全（Step 3）、无障碍（Step 4）、性能反模式（Step 5）、SwiftUI 反模式（Step 6），输出 🔴/🟡/🟢 报告 + 审计标记。

**为什么退役** — 四类重复，第五类形态选错了
拆开看，五类各自的处境不同：

| 类别 | 谁已经在做 |
|---|---|
| 并发安全 | `apple-dev:apple-reviewer` |
| 无障碍 | `apple-dev:ui-reviewer` |
| 性能反模式 | `apple-reviewer` + `references/external/swiftui-performance-audit.md` |
| SwiftUI 反模式 | `ui-reviewer`（判据同源 `design-contract-schema.md`） |
| **安全（Step 2）** | **没有人** |

那两个 reviewer 由 `review-execution` 按 diff 形状自动派发；这个 skill 是 `user-invocable: false` 而**没有任何调用方** —— `apple-dev/README.md` 写着 caller 是 "run-phase / implementation-reviewer"，实际 `grep -c "code-audit" dev-workflow/skills/run-phase/SKILL.md` = 0。所以：重复的四类跑得比它勤，独有的一类根本没跑过。

**去向**：Step 2 的四个子检查（硬编码密钥 / 不安全传输 / 注入形状的输入处理 / 敏感数据落 UserDefaults）搬成 `review-execution` 的 **Lens F — Secrets & Transport**，**始终派发，不按路径路由**。

**为什么 Lens F 不路由**：其它条件 lens 都按路径 pattern 判（`*View.swift`、`.plist`……），而**密钥不长在固定路径上** —— 泄露的 key 落在作者当时正在编辑的那个文件里。给它一个路径形状的路由，等于让它恰好错过自己存在的理由。代价可控：sonnet 只扫 diff。

**当时怎么做的**
`git show f4ddd65:apple-dev/skills/code-audit/SKILL.md`（约 300 行，8 个 Step）。

**再做的话要不同在哪**
**"综合审计"是个坏的封装边界。** 把五类不相干的检查捆成一个 skill，结果是它整体的死活由最弱的那条接线决定 —— 四类有人做的被重复，唯一没人做的跟着一起沉。

判据：**一个组件里的各部分，如果各自的调用方不同，它就不该是一个组件。** 拆开之后，每一类去找自己真正的宿主：已有 reviewer 覆盖的就删，没覆盖的做成一个 lens。

**如果要重做，形态应该是**
不重做整体。安全那一类已在 `review-execution` Lens F，判据写在那里。新增一类安全检查时加进 Lens F 的 prompt，不要新起一个 skill。
