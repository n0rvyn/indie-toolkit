---
type: crystal
status: active
tags: [ios-ui-visual-feedback, mcp-first, run-phase, swiftui-preview, apple-dev]
refs: []
---

# Decision Crystal: iOS UI 视觉反馈环 + MCP-First 工具姿态

Date: 2026-05-29

## Initial Idea
UI/UX 实现和其它代码实现是不是需要不太一样的流程？现在用 dev-workflow 推进开发，
但做 iOS UI 时发现一套流程跑下来（run-phase 推 dev-guide 或 write-plan 推 plan）
都会做得面目全非。是不是单独做一套 UI/UX 的 workflow 来独立推进？先调研现在用最新
ClaudeCode 等 AI 工具做设计/实现推荐的成熟流程，再一起 brainstorm。

## Discussion Points
1. **要不要单独做 UI/UX workflow**：初始假设"另起一套独立 workflow"。盘点后发现用户已拥有
   5 个成熟 AI-UI 原语里的 4 个（token 契约、设计前置锁定且 understand-design 已接 Stitch MCP、
   fresh-context 审查）。结论改为：不另起，只补缺失原语。
2. **"面目全非"根因**：整条 spec-driven 流程没有一步让模型 SEE 渲染输出——verify-plan 查逻辑、
   test-changes 跑 build/test、design-reviewer/ui-reviewer 读源码，全是文本/代码层。对照 Anthropic
   官方 best-practices，截图→实现→对比→修是排第一的验证手段。缺的就是这个环。
3. **开发节奏=(a)**：跟着 run-phase 逐 phase 推，UI 是 phase 的一部分，有时连做多个 phase 最后才
   真机验证——漂移跨 phase 复利累积。决定：视觉环必须在每个 phase 内闭合。
4. **#Preview 作为 agent 的眼睛**：用户提出 Xcode 实时渲染（#Preview），观察到 AI 干活时会清掉它。
   查实 Xcode 26.3 原生 MCP 的 RenderPreview 能把 #Preview 渲染图返回给 agent（推翻早期"agent 无法
   消费 Preview"的说法）。决定：用 #Preview 渲染当视觉环通道，并保护它不被删。
5. **设计源=diff 目标**：用户先做 Claude Design 设计稿，次选 Google Stitch；格式 HTML+图片，
   本地或 URL。视觉环的"对的样子"= 这些设计图。
6. **MCP 能力分工（校正）**：初始设想"iOS 全面 MCP-first"。查实 Apple 原生 MCP（xcrun mcpbridge，
   遥控开着的 Xcode）只能 build/诊断/查 API(ExecuteSnippet)/渲染 Preview；做不了 UDID 定向测试、
   运行态截图、模拟器生命周期。决定分工，SOP 大部分保留。
7. **三条工作线+顺序**：WS3 治理 → WS1 渲染环 → WS2 apple-dev MCP 化，依赖驱动。
8. **WS3 走 (b)**：WS3 较轻且伸到仓库外，用 write-plan 或直接改，不进 dev-guide；dev-guide 只管 WS1+WS2。

## Rejected Alternatives
- **单独做一套独立 UI/UX workflow/plugin**：否决——用户已有 4/5 原语只缺渲染环；独立轨会造成两条
  流水线 + token 契约漂移。
- **把整个 xcodebuild-simulator-testing SOP 改成 MCP-first**：否决——Apple 原生 MCP 做不了 UDID
  定向测试和运行态截图，SOP 必须保留。
- **WS3 折进 dev-guide（route a）**：否决，选 route (b) 轻量单独做。否决范围仅指 WS3 承载方式；
  不否决"三条线统一依赖图"概念本身。
- **UI 视觉环做成全自动像素级保真**：否决——模型对间距细微差不敏感、会早停，最后一公里保留人工。

## Decisions (machine-readable)
- [D-001] 不另起独立 UI/UX workflow；在现有 run-phase 流程里补"渲染-diff-修"视觉环这一个缺失原语
- [D-002] 视觉环插在 run-phase 的 execute 与 review 之间，每个 phase 内闭合（linked: D-001）
- [D-003] 视觉环通道 = 渲染 SwiftUI #Preview；主路 Apple MCP RenderPreview，无头 fallback
  axe / swiftui-render（让 run-phase 可无人值守，因 RenderPreview 需 Xcode 开着）
- [D-004] #Preview 块受保护，禁止被当 unused code 删除（hook/规则）
- [D-005] 视觉环 diff 目标 = Claude Design / Google Stitch 设计图（HTML+图片，本地或 URL）
- [D-006] iOS 工具姿态改为 MCP-first / CLI-fallback；保留而非删除 CLI 指引
- [D-007] MCP 能力分工：Apple MCP 主管 build/诊断/ExecuteSnippet 查 API/RenderPreview；
  测试(UDID)/运行态截图/模拟器生命周期/真机/crash log 由 CLI 或 XcodeBuildMCP 兜底（linked: D-006）
- [D-008] 工作线顺序 WS3（治理）→ WS1（渲染环）→ WS2（apple-dev MCP 化），依赖驱动
- [D-009] WS3 走 route (b)：轻量单独做，不进 dev-guide；dev-guide 只覆盖 WS1+WS2
- [D-010] 渲染环定位为"把面目全非拉到八九不离十，最后一公里人工收"，非全自动像素级保真

## Constraints
- Apple 原生 MCP 需 Xcode 开着（XPC 遥控）→ 无人值守路径必须有无头渲染 fallback
- xcodebuild-simulator-testing SOP（单 test 实例、UDID 不用 name、0x8BADF00D 恢复）保留有效
- apple-dev 源码在本仓 /Users/norvyn/Code/Skills/indie-toolkit/apple-dev/
- WS3 触及仓库外全局文件（~/.claude/CLAUDE.md、~/.claude/references/、memory）
- RenderPreview 渲染孤立单 view，非 app 导航态；跨页面/动画验证另需 XcodeBuildMCP/simctl，
  且动画/视频模型看不了

## Scope Boundaries
- IN: 在 run-phase 加渲染-diff 视觉环（WS1）
- IN: #Preview 保护机制（WS1）
- IN: apple-dev 的 build/诊断迁到 Apple MCP（WS2）
- IN: CLAUDE.md（全局+项目）/memory/references 改 MCP-first/CLI-fallback（WS3）
- OUT: 新建独立 UI/UX workflow 或 plugin
- OUT: 用 MCP 替代 xcodebuild 测试 SOP
- OUT: 全自动像素级 UI 保真（人留在环内）
- OUT: 动画/视频视觉审查（模型能力外）

## Source Context
- Design doc: none
- Design analysis: none
- Key files: dev-workflow/skills/understand-design/SKILL.md; dev-workflow/skills/run-phase/SKILL.md;
  apple-dev/（skills/agents/hooks/references）; ~/.claude/CLAUDE.md;
  ~/.claude/references/xcodebuild-simulator-testing.md; 项目 memory
- 研究简报: UI/UX workflow 调研 + 4 份 agent 报告（apple-dev 盘点 / CLAUDE.md+memory 治理 /
  Xcode 26.3 MCP 深挖 / Claude Design+Stitch→SwiftUI）
- 校验来源: code.claude.com/docs/en/best-practices（截图验证）;
  samwize.com（Apple MCP vs XcodeBuildMCP 能力边界）;
  ethanhuang13 gist（mcpbridge tools/list 实测）; anthropic.com/news/claude-design-anthropic-labs;
  stitch.withgoogle.com/docs/mcp
