# Apple Platform Swift Development Rules
<!-- SECTION MARKERS: Each "section" comment line immediately precedes the ##
     heading it labels. Use Grep("<!-- section:", file) to find sections, then
     Read(file, offset, limit) to fetch only the relevant lines. -->

> Extracted from global CLAUDE.md for plugin-based delivery. These rules are automatically loaded in iOS projects via the apple-dev plugin.

<!-- section: Build-Check-Fix Cycle keywords: build, xcodebuild, check, fix, compile cycle, timing -->
## Build-Check-Fix Cycle

**编译验证**：优先 Apple Xcode MCP `BuildProject`（需 Xcode 开着项目，返回结构化错误数组，不用啃日志）；MCP 不可用时 fallback 到 CLI 编译验证 —— ⚠️ **不可用的原因有两个，先分清**：① 工具压根不在盘（2026-08-20 实测本机就是这样，工具列表里查不到任何 Xcode MCP；`claude mcp list` 看不见插件侧 MCP，不能用它判定）② Xcode 未开。①**开 Xcode 也没用**，直接走 CLI；（SPM 项目 `swift build`、Xcode 工程 `xcodebuild build`）。

```
Write Code -> Apple MCP BuildProject（主）/ swift build·xcodebuild build（fallback）-> Check（MCP 结构化错误 / CLI 日志）-> Fix -> Repeat
```

**运行编译验证（BuildProject/xcodebuild）的时机**：
- 完成完整文件后
- 完成相关文件组后
- 修复错误后验证
- 提交代码前

**不要**：每几行代码就跑、只改注释/文档时跑

<!-- section: 通用约束 keywords: constraints, forbidden, required, main thread, API key, hardcoded -->
## 通用约束

```
禁止：在主线程执行耗时操作
禁止：硬编码 API Key 或敏感信息
禁止：硬编码 UI 文本（必须使用 LocalizedString）
禁止：硬编码 UI 尺寸/间距/颜色/字号（必须使用设计系统变量或系统语义值）
禁止：直接编辑 *.xcodeproj/project.pbxproj 或 *.xcworkspace（易损坏项目）

必须：所有 Service 使用 Protocol 抽象
必须：所有异步操作使用 async/await
必须：所有错误妥善处理
必须：所有 UI 文本使用本地化
必须：引用文件路径前用 Glob/Read 验证存在（不要照抄未验证的引用）
必须：使用系统 API 返回值做条件判断前，确认该值在目标场景的实际值域（Apple 文档或代码打印实际值）。禁止凭训练数据假设值域
必须：写自定义状态管理/手势检测/布局逻辑前，先搜索平台是否提供声明式 API 解决同一问题（Apple 文档 / SwiftUI API 列表）。未搜索就写状态机或手工计算 = 违反本规则
```

<!-- section: Swift 6 并发原则 keywords: Swift 6, concurrency, MainActor, Sendable, @Model, actor -->
## Swift 6 并发原则

> 详细规范由 `references/swift-coding-standards.md` 提供。以下为关键要点。

- 所有 `@Model` 类型隐式 `@MainActor`，不可跨 actor 传递
- Service 单例统一 `@MainActor final class`
- 跨 actor 边界传递数据时，提取为 `Sendable` 值类型（struct/enum）
- `nonisolated` 用于不访问 actor 状态的纯计算方法
- 闭包捕获 `@MainActor` 属性时，用 `MainActor.run { ... }` 包裹

<!-- section: .foregroundColor 迁移策略 keywords: foregroundColor, foregroundStyle, migration, deprecation -->
## .foregroundColor 迁移策略

项目中 `.foregroundColor()` 存在大量调用（验证命令：`rg -c '\.foregroundColor\(' --type swift | awk -F: '{s+=$2}END{print s}'`）。无法一次性替换。
- 新代码：一律使用 `.foregroundStyle()`
- 改现有文件时：顺带替换该文件中的 `.foregroundColor()`
- 不做：专门发起批量替换（风险高、收益低）

<!-- section: iOS UI 规则（分层生效） keywords: UI rules, layers, design system, hardcoded values -->
## iOS UI 规则（分层生效）

**Layer 1 - 硬性禁令**（无条件生效，见上方「通用约束」）：
- 禁止硬编码 UI 尺寸/间距/颜色/字号

**Layer 2 - 计划阶段检查**（条件触发）：

触发条件：计划的主要目的是创建新 UI 页面/组件，或对现有 UI 做视觉重构。
不触发：修改业务逻辑顺带改一行 View 代码、添加调试 UI、纯文档修改。
示例：
  ✅ 触发：新建 SettingsTab、重构 InsightCard 布局
  ❌ 不触发：修改 SettingsTab 中一个按钮的 action closure

触发后执行：
1. 计划中所有 UI 尺寸必须标注对应设计系统变量
2. 无对应变量的值 → 标注 `⚠️ 待定` 并询问用户

**Layer 3 - 同类组件一致性**（条件触发）：

触发条件：创建新 UI 组件（View struct），且组件名包含常见类型后缀（Card、Row、Cell、Badge、Chip、Tile、Banner）。
不触发：创建唯一类型的组件（项目中无同后缀组件）、修改已有组件内部逻辑。
示例：
  ✅ 触发：新建 ExpenseCard（项目已有 InsightCard）
  ✅ 触发：新建 SettingsRow（项目已有 ProfileRow）
  ❌ 不触发：新建 OnboardingView（唯一类型）
  ❌ 不触发：修改 InsightCard 的数据绑定

触发后执行：
1. 搜索已有同类组件：
   ```
   Grep("struct \\w+Card", glob: "*.swift")  // 替换 Card 为实际后缀
   Glob("**/*Card.swift")
   ```
2. 读取每个已有同类组件，提取以下属性的具体值：
   - 宽度行为：`.frame(maxWidth:)` / `.frame(width:)` / 无 frame（内容自适应）
   - 内边距：`.padding()` 值
   - 背景：`.background()` 的颜色或材质
   - 圆角：`.clipShape()` / `.cornerRadius()` 值
   - 阴影：`.shadow()` 参数
3. 新组件必须匹配已有同类组件的上述属性值。差异项标注 `⚠️ 不一致` 并在计划中说明理由或改为一致。

<!-- section: 同一动作的控件形制一致（条件触发） keywords: back button, close button, navigation bar, system control, consistency, chevron, xmark, dismiss -->
## 同一动作的控件形制一致（条件触发）

触发条件：新增或修改**在多个页面重复出现的同一动作**的控件 —— 返回、关闭、取消、完成、主行动 CTA。
不触发：只在一处出现、且全 App 无同一动作的一次性控件。

Layer 3「同类组件一致性」按**组件类型后缀**（Card/Row/Badge…）触发，管的是同类组件之间；
「按钮组同宽」管的是**同屏并列**。本节管的是第三件事：**同一个动作跨页面的长相**。三者不互相覆盖。

触发后执行（三步，缺一步等于没做）：

1. **数清楚这个动作全 App 有几处呈现，把系统控件也数进去。**
   ```
   grep -rn "navigationBarLeading\|navigationBarBackButtonHidden\|chevron.left\|xmark\|dismiss()" --include="*.swift"
   grep -rn "NavigationLink\|\.sheet\|fullScreenCover" --include="*.swift"   # push/present = 系统控件出现的地方
   ```
   ⛔ **系统控件不在代码里出现**（`NavigationLink` push 自带的返回键、`List` 自带的 disclosure chevron），
   只 grep 自绘代码必然漏掉它们 —— 而它们往往是多数派。

2. **定基准形制**：只要有 ≥1 处用的是系统控件，基准就是系统那一套，自绘的向它看齐。
   ⛔ **不得反过来** `navigationBarBackButtonHidden(true)` 掉系统控件去迁就自绘的 ——
   那会**连带掐掉系统的边缘返回手势**，为了统一长相把滑动返回弄坏（2026-08-09 CleanLabel 实证）。
   全 App 都没有系统控件时，才由设计源定基准。

3. **形制定义写进 DesignSystem 的一个 struct/enum**，调用点只引用不复制。

⛔ 反面（2026-08-09 CleanLabel 实证）：结果页自绘 `‹ 返回`（chevron + 文字），历史页与回看页用系统返回键 ——
iOS 26+ 把它渲染成玻璃圆底 + 光秃秃的 `‹`。同一个动作两种长相，用户一眼看出来，
而 **build 绿 / 单测绿 / 纯代码审计三者都不报警**：自绘那处单看完全正确，系统那处代码里根本不存在。

自检：即将写下 `chevron.left` / `xmark` / 任何「离开本页」按钮时问一句 ——
**这个动作在别的页面长什么样？我看过那一页的渲染吗？**

<!-- section: UI 改动交付前必须先看渲染（强制） keywords: self check, render, screenshot, preview, before handoff, verification -->
## UI 改动交付前必须先看渲染（强制）

规则：任何用户可见的 UI 改动，在对用户说「做完了 / 你试一下 / 需你验证」之前，**我必须先看过它的渲染**。
`BUILD SUCCEEDED`、单测全绿、代码读着对，三者**都不构成「看过」** —— 形制不一致、控件被系统换了样式、
布局塌陷这三类缺陷，恰恰是这三者结构性看不见的。

渲染通道按可用性降级，用到第一条能通的为止：
1. `apple-dev:render-preview`（#Preview → PNG，最轻，不需要设备）
2. XCUITest 截图（`app.screenshot()` + XCTAttachment）
3. 真机截图

三条**全部**不可用时，必须在交付消息里显式写出「⚠️ 我没能看到渲染」+ 卡在哪个通道 + 具体让用户看哪几处。
⛔ 不得把「没看过」包装成「已完成，请验收」——那是把自检成本转嫁给用户
（2026-08-09 CleanLabel：改完返回按钮直接交付，用户截图一看，漏掉的两个 push 页面还是系统旧样式）。

<!-- section: 设计稿没有横屏 ≠ 锁方向（强制） keywords: orientation, portrait, landscape, supportedInterfaceOrientations, UIRequiresFullScreen, window size -->
## 设计稿没有横屏 ≠ 锁方向（强制）

触发条件：即将写或改 `supportedInterfaceOrientationsFor`、`UISupportedInterfaceOrientations*`、
`UIRequiresFullScreen`，或以任何方式限制方向 / 窗口尺寸。

⛔ **设计稿只有竖屏版面不构成锁方向的理由** —— 那描述的是画布，不是产品要求；版面在横屏下不好看是
**版面要适配**。这一整类错误的形状是「原型画布参数被一级级硬化进运行时」（`393 × 852` /
`portrait only` / 假状态栏同源同类）。

自检一句：**是产品要求它只能竖着用，还是我只是没有横版设计图？**

<!-- 2026-08-16 回写：本判据此前只存在于 ~/.claude/CLAUDE.md 的探测器行里，而那一行指向本文件的
     「设计稿没有横屏 ≠ 锁方向（强制）」节——该节当时并不存在。CLAUDE.md 自己写着「plugin 侧为
     iOS 规则权威源，本节新增判据须同步回写」，这次补上。 -->

<!-- section: 容器宽度意图（条件触发） keywords: container width, maxWidth, infinity, frame, adaptive layout -->
## 容器宽度意图（条件触发）

触发条件：创建或修改的 View 渲染为视觉容器 —— 有 `.background()` / `.clipShape()` / `.shadow()` / `.border()` / `.overlay(strokeBorder)` 中任一。（后两个来自 2026-08-07 前全局 CLAUDE.md 的同名规则：两份长期并存、触发条件已分叉，合并时以本节为准并补上它独有的这两个 token —— 一个只有描边、没有背景色的卡片同样是视觉容器。）
不触发：List/Form 内的 View（系统管理宽度）。有意 content-hugging 的小组件（Badge、Chip、Tag、inline label）。

规则：写 frame modifier 前先判断宽度意图。

| 意图 | Modifier | 适用场景 |
|------|----------|---------|
| 撑满（Full-width） | `.frame(maxWidth: .infinity)` | ScrollView > VStack/LazyVStack 内的卡片、区块、操作按钮、Banner |
| 抱住内容（Content-hugging） | 无 frame 或 `.fixedSize()` | Badge、Tag、inline chip、图标按钮（均限不与全宽按钮并列的场景） |
| 约束最大宽（Constrained） | `.frame(maxWidth: 400)` | iPad 上不需要撑满的内容卡片 |
| 自适应（Adaptive） | `.frame(idealWidth: 300, maxWidth: .infinity)` | 有理想宽度但需要自适应增长的卡片 |

常见错误：ScrollView > VStack 内的卡片/区块忘了 `.frame(maxWidth: .infinity)`，导致容器抱住内容宽度，在宽屏上显示为半宽。

按钮组同宽（强制）：同一组并列的行动按钮必须同宽。判据不是「它是不是 button」（button 单独看可以 hug），而是「它和谁并排」——一个 VStack 里主行动全宽、次级 hug content = 一组两种宽度，用户会看见。机制：`.frame(maxWidth: .infinity)` 必须贴在 **Button 的 label** 上，贴在 Button 外面撑开的是布局槽位，不是按钮本体。⛔ `Button("标题") { }` 字符串 title 构造器没有暴露 label，无处贴 frame，必然抱住内容——一组按钮统一写 `Button { } label: { Text(...).frame(maxWidth: .infinity) }`。例外：设计源本身就是 hug 的药丸/胶囊按钮——1:1 复刻，不得为「统一」而改（未授权 UX 变更）。这类不一致纯代码审计抓不到（每一处单看都没错），必须并排看多屏渲染。详见 `~/.claude/knowledge/api-misuse/2026-07-10-swiftui-button-string-init-cannot-fill-width.md`。

自检：写完容器 View 后问自己："这个容器在宽屏（iPad / 大 iPhone）上是正确撑满还是尴尬地抱住内容？"

<!-- section: 计划阶段架构审查（条件触发） keywords: architecture review, plan, triggers, parallel paths -->
## 计划阶段架构审查（条件触发）

触发条件：计划涉及新增触发/调度入口、新增数据处理路径、或重构已有机制的核心路径。
不触发：修复单个 bug（未涉及路径变更）、UI 显示修复、文档修改。
示例：
  ✅ 触发：新增定时任务调度器（新入口）
  ✅ 触发：重构 InspirationService 的事件分发机制（核心路径变更）
  ❌ 不触发：修复 InsightCard 的日期格式显示错误（单点 bug）
  ❌ 不触发：调整 SettingsTab 的布局间距（UI 显示）

触发后执行：
1. 追溯相关数据的完整路径（触发源 → 处理 → 持久化 → 展示），在计划中标注路径上每个节点的文件:行号
2. 在路径的每个处理节点，搜索是否有其他上游入口调用同一节点（= 并行路径）
3. 如发现并行路径，在计划中标注：
   ```
   ⚠️ 并行路径：{核心函数} 被 {路径A 文件:行号} 和 {路径B 文件:行号} 独立调用
   协调机制：{有/无}
   计划处理：{合并到路径A / 保留并新增协调 / 问用户}
   ```
4. 标注了"问用户"的架构冲突，禁止在未得到用户回复前继续编写计划的该部分

<!-- section: 计划编写原则 keywords: plan writing, plan draft, requirements -->
## 计划编写原则

- **约束前置** 计划开头列出：用户明确要求、技术约束、禁止事项
- **UX 决策显式化** 全局 CLAUDE.md「决策权归属」列出的 UX 决策类别必须在计划中列出，不留给实现时判断（全局清单为权威源；不可见时最小集 = 导航方式、过渡动画、交互反馈）

<!-- section: 计划自检（M&M 测试） keywords: plan self-check, M&M test, surface, hidden, reinventing -->
## 计划自检（M&M 测试）

> 触发条件：计划涉及 ≥ 3 个文件变更，或涉及架构/数据流变更。
> 跳过：单文件修改、文档更新、简单 bug 修复。
> 示例：
>   ✅ 触发：重构洞察系统（涉及 Service + ViewModel + View）
>   ✅ 触发：新增数据同步路径
>   ❌ 跳过：修复 SettingsTab 中一个显示 bug（单文件）
>   ❌ 跳过：更新 CHANGELOG.md

计划末尾必须包含：

```
[自检-表面] 本次任务最容易违反哪条规则？
答：{规则名称} — {为什么这个任务容易踩这条规则}

[自检-隐蔽] 本次任务中，哪个"看起来已完成"的步骤最可能实际未生效？
答：{步骤} — {为什么它可能未生效（运行时条件、数据依赖、环境差异）}

[自检-造轮子] 本次方案中是否有手写逻辑在解决平台 API 已覆盖的问题？
答：{具体逻辑} — {已查 / 未查对应平台 API}（未查 = 必须先查再继续）
```

<!-- section: 计划执行原则 keywords: execution, ambiguity, interruption, clarification -->
## 计划执行原则

**歧义词检查**（执行前必做）：

> 触发条件：歧义词指向用户可见的 UI/UX 决策。
> 不触发：纯内部实现（"自定义 struct"、"新建 helper 函数"）。
> 示例：
>   ✅ 触发：计划说"自定义导航栏"（用户可见，需确认自定义程度）
>   ✅ 触发：计划说"新建一个卡片组件"（用户可见 View）
>   ❌ 不触发：计划说"自定义 Codable 解码逻辑"（纯内部）
>   ❌ 不触发：计划说"新建 helper extension"（纯内部）

计划中出现以下词汇时，禁止直接执行，必须先问用户确认具体含义：
- "自定义"：是完全重写，还是在原生基础上添加元素？
- "新建"：是新建独立组件，还是在现有结构中添加？
- "改造"：改多少？哪些保留哪些替换？

格式：
```
计划说「{原文}」，我的理解是：{具体实现方式}。是否正确？
```

<!-- section: 计划执行中断处理（必须遵守） keywords: interruption, pause, resume, mid-execution -->
## 计划执行中断处理（必须遵守）

**触发条件**：执行计划时遇到以下情况之一：
- API/框架 bug 或不兼容
- 依赖缺失或版本冲突
- 技术方案不可行
- 任何导致"原计划无法继续"的障碍

**强制动作**：
1. 立即停止执行
2. 输出格式：
   ```
   [计划中断]
   原计划：{计划内容}
   阻断原因：{具体问题 + 证据}
   可选方案：
   A. {方案A}
   B. {方案B}
   请选择。
   ```
3. 等待用户决定后再继续

**禁止**：以任何技术理由自行选择方案

<!-- section: 错误修复原则 keywords: error fix, bug fix, reproduce, confirm -->
## 错误修复原则

> 触发条件：用户指出实现逻辑或行为错误。
> 不触发：拼写错误、格式错误等显而易见的修正，直接执行。
> 示例：
>   ✅ 触发：用户说"这个按钮应该触发保存而不是删除"（行为错误）
>   ✅ 触发：用户说"排序逻辑反了"（逻辑错误）
>   ❌ 不触发：用户说"这里少了个右括号"
>   ❌ 不触发：用户说"变量名拼错了"

用户指出实现错误时，**禁止立即修改代码**。必须先执行：

1. 复述用户指出的问题
2. 陈述我理解的期望效果
3. **等待用户确认后再改**


<!-- section: #Preview Protection keywords: preview, PreviewProvider, visual feedback, unused code, delete -->
## #Preview Protection

`#Preview` 块（及 `PreviewProvider`）是**受保护的视觉反馈基础设施**。`render-preview` 和 `run-phase` 视觉环依赖它们生成截图以完成视觉验收闭环。

**规则：改 View 时必须维护其 `#Preview`。** 不得以"未使用代码"为由删除 `#Preview`。

**与全局 CLAUDE.md 的切割**：全局 CLAUDE.md「删除未使用的代码（编译器/linter 已标记 unused）免陈述预期」例外条款**不适用于 `#Preview`**。`#Preview` 即使看似 unused（编译器不报错不代表它无用），也不在该例外范围内。删除 `#Preview` 必须陈述预期。

**合法删除出口**：删除整个 View 时，可连同删除其 `#Preview`，但需在改动说明中点明（例：「删除 FooView 及其 #Preview」）。

<!-- section: 删除代码原则 keywords: delete code, search references, dead code -->
## 删除代码原则

删除任何状态变量、函数、文件前，必须：

1. **搜索引用**：`Grep` 该变量/函数名，列出所有引用位置
2. **检查用途**：每个引用位置的功能是什么？删除后功能是否受影响？
3. **关联处理**：功能需要保留则保留代码或用替代方案实现

<!-- section: 死代码/未接入代码处置原则 keywords: dead code, unused code, unreferenced, disposal -->
## 死代码/未接入代码处置原则

触发条件：发现代码存在但未被调用、功能写好但未接入主路径、或代码路径不可达

强制流程：
(1) **识别目标**：这段代码原本要解决什么问题？（读注释、git blame、周边调用关系）
(2) **验证问题**：这个问题在当前代码中还存在吗？（必须用 Grep/Read 验证，不凭推测回答"不存在"）
    - "不存在"的证据：当前代码已有其他机制解决同一问题，且该机制已接入并生效
    - "存在"的证据：问题场景可构造（例：对话超过 N 条消息时无截断），且无其他机制覆盖
(3) **决定处置**（必须输出下表，不可省略）：

    | 死代码 | 原本解决的问题 | 问题是否仍存在（附证据） | 处置 |
    |--------|-------------|---------------------|------|

    处置选项：
    - 问题存在 + 实现方式匹配当前架构 → 接入（重新连通到主路径）
    - 问题存在 + 实现方式不匹配 → 在当前架构中重新解决该问题，删除旧代码
    - 问题不存在（附证据） → 删除

禁止：
- 未填写上表就删除或保留任何死代码
- "问题是否存在"列填写"可能"/"不确定" — 不确定就去验证
- 以"死代码"为由跳过问题分析，直接执行删除
- 以"先保留以后可能用到"为由跳过问题分析，直接保留

<!-- section: macOS Window Management keywords: WindowGroup, Window, Settings, MenuBarExtra, window, macOS, openWindow platform: macOS -->
## macOS Window Management

- `WindowGroup`：多实例文档窗口（每次打开创建新窗口）
- `Window`：单实例工具窗口（如 About 面板），重复打开仅聚焦已有窗口
- `Settings`：偏好设置窗口，自动获得 Cmd+, 快捷键，不要用自定义 Window 替代
- `MenuBarExtra`：菜单栏常驻图标 + 弹出面板

窗口尺寸：
- `.defaultSize(width: 800, height: 600)` 设置默认尺寸
- `.frame(minWidth: 400, minHeight: 300)` 设置最小尺寸（在内容 View 上）
- 不要锁死固定尺寸，macOS 用户期望窗口可自由调整

编程式窗口操作：
- `@Environment(\.openWindow) var openWindow` → `openWindow(id: "detail")`
- `@Environment(\.dismissWindow) var dismissWindow` → `dismissWindow(id: "detail")`
- Window ID 必须与 `WindowGroup(id:)` 或 `Window(id:)` 声明的 ID 匹配

<!-- section: macOS Menu & Toolbar keywords: commands, CommandMenu, CommandGroup, toolbar, macOS menu platform: macOS -->
## macOS Menu & Toolbar

菜单栏：
- `CommandMenu("MyMenu") { ... }` 添加自定义菜单
- `CommandGroup(before: .newItem) { ... }` 在系统菜单中插入条目
- `CommandGroup(replacing: .appInfo) { ... }` 替换系统菜单条目
- 菜单内的 Button 自动显示 `.keyboardShortcut()` 绑定

Toolbar：
- `.toolbar { ToolbarItem(placement: .automatic) { ... } }` 添加工具栏按钮
- macOS 的 toolbar 位于窗口标题栏区域
- 高频操作同时放在 toolbar 和菜单中（toolbar 是快捷入口，菜单是可发现性保障）

导航结构：
- macOS 不使用 TabBar，用 `NavigationSplitView` 的 Sidebar 做一级导航
- Sidebar 使用 `List(selection:)` 实现选中状态
- `.listStyle(.sidebar)` 获得系统 sidebar 外观

<!-- section: macOS Keyboard Shortcuts keywords: keyboardShortcut, keyboard, shortcut, macOS, focusedSceneValue platform: macOS -->
## macOS Keyboard Shortcuts

标准快捷键惯例（必须遵循）：
- Cmd+N：新建
- Cmd+W：关闭窗口
- Cmd+,：偏好设置（Settings scene 自动处理）
- Cmd+Q：退出（系统自动处理）
- Cmd+Z/Shift+Cmd+Z：撤销/重做

自定义快捷键：
- `.keyboardShortcut("n", modifiers: .command)` 绑定到 Button
- 所有主要操作都应有键盘快捷键
- 菜单中的快捷键自动显示在右侧

跨窗口路由：
- `@FocusedValue` / `.focusedSceneValue()` 在多窗口间路由键盘事件
- 当前活跃窗口的 focused value 优先响应 Command 中的 action

<!-- section: macOS SwiftUI Patterns keywords: NSViewRepresentable, pasteboard, drag drop, macOS SwiftUI, onHover platform: macOS -->
## macOS-specific SwiftUI Patterns

平台桥接：
- `NSViewRepresentable`（不是 `UIViewRepresentable`）包裹 AppKit 视图
- 实现 `makeNSView(context:)` / `updateNSView(_:context:)` / `dismantleNSView(_:coordinator:)`
- `NSPasteboard`（不是 `UIPasteboard`）操作剪贴板

条件编译：
```swift
#if os(macOS)
// macOS-only code
#elseif os(iOS)
// iOS-only code
#endif
```

macOS 特有交互：
- `.onHover { isHovered in ... }` 鼠标悬停（iOS 上无意义）
- `.contextMenu { ... }` 右键菜单在 macOS 上比 iOS 更常用
- 拖放：`.draggable()` / `.dropDestination()` 修饰符通用，但 macOS 支持文件 promise
- `.help("tooltip text")` 添加鼠标悬停提示（macOS only）

<!-- section: 测试框架与文件放置 keywords: Swift Testing, XCTest, @Test, #expect, XCUITest, synchronized folders, pbxproj -->
## 测试框架与文件放置

- 测试一律用 Swift Testing（`@Test`、`#expect`、`#require`），不使用 XCTest。例外：项目已有 XCTest 且不在本次重构范围；XCUITest（UI 自动化）没有 Swift Testing 等价物，仍用 `XCTestCase`
- Xcode 16+ 项目默认自动同步文件夹内的 Swift 文件：新文件放到对应目录即可生效。禁止写「需要手动编辑 pbxproj」或「需要拖进 Xcode」

### 两个会把整轮测试挂死、而且长得完全不像测试问题的坑

**① Swift Testing 默认并行，多个 Vision 请求同时压进去会把整个进程卡住。**
实证 2026-08-12（iPhone 16 Pro / iOS 27 / Xcode 26.3）：加了 2 条跑
`VNRecognizeTextRequest(.accurate)` 的测试之后，整套 65 条**十分钟不返回**；
而这两条单独跑 0.565 秒、其余 58 条单独跑 0.802 秒。日志里 62 条 started、
只有 9 条完成，**完成的全是不碰图像的纯几何测试**——凡是走 Vision 的全堵住。
- 判据：`started` 远多于 `passed/failed`，且完成的那几条有共同点（都不碰某个共享子系统）
  → 是并行争用，不是某条测试写错。别去逐条改测试。
- 定位：`-only-testing:` 单跑各套件（都秒过）→ `-skip-testing:<嫌疑套件>`（秒过）
  → `-parallel-testing-enabled NO`（秒过）。三步坐实，不用猜。
- 修法：给那个套件加 `.serialized`（`@Suite("…", .serialized)`）。实测加完并行照开、
  三轮连过 1.27/1.00/0.94 秒。比让所有人记住命令行参数可靠。

**② 同一种并行，另一种形态：进程级全局注册的桩会互相拦到对方的请求。**
实证 2026-08-14（iPhone 真机）：新加一个 `URLProtocol` 桩之后，**另一个套件**
里一条早就绿着的负控（「未同意 → 一次 `/v1/vision` 都不打」）从 0 变成 1。
两个桩都 `URLProtocol.registerClass`，而那是**进程级**的；Swift Testing 并行跑
不同套件，于是 A 套件的请求被 B 套件的桩拦下并计了数。

- 判据：**加了新测试之后，别处一条没动过的断言开始红**。不要去改那条断言 ——
  它没错，是被污染了。
- ⚠️ 它比 ① 更阴：① 会卡死，一眼看得出；这个只让数字偏一点，
  而且偏的方向取决于调度，重跑还可能变绿。
- 修法两条一起上：
  · 桩**按宿主分流**（`request.url?.host == 自己那个 host`，两边各用各的
    `https://<套件名>.invalid`），别只按 path 判；
  · 共享静态计数器的那个套件加 `.serialized`（同套件内的两条用例照样会互相加数）。
- 同族的还有：`UserDefaults.standard`、`FileManager` 的固定路径、单例缓存。
  凡是**进程级**的东西，并行测试里都要按套件分流，不是靠「跑之前 reset 一下」。

**⛔ 最贵的一条：截图/UI 工装为了「状态干净」而清库，清的是用户的真实数据。**
实证 2026-08-12（真机）：截图套件启动时调 `wipeSeenForScreenshots()`，
而 App 只有一个磁盘 `ModelContainer` —— 跑一次截图套件就把用户自己拍的记录连同
照片文件一起删光。用户第二天问「我之前拍的几个怎么全没了」才发现；那是真机上
唯一一份数据，删了就没了。取证方式：把设备容器拉下来看时间戳，
`xcrun devicectl device copy from --domain-type appDataContainer`。
- **「工装小心点别清库」不是解法。** 只要两边共用一个容器，下一个为了截图方便
  而清库的人会再犯一次。
- 解法是**物理隔离**：工装启动参数在场时用
  `ModelConfiguration(isStoredInMemoryOnly: true)`；工装写的附属文件
  （图片/缓存）也换一个目录，否则真实目录里会攒下没有记录指向的孤儿文件。
- 容器建不起来就让它崩：静默退到内存库，用户以为记录丢了；静默退到磁盘库，
  工装又会去清用户数据。两种兜底都比崩更糟。
- 验法用**已知正例**：跑工装前后各把库拉下来比对主键与时间戳，
  一致才算隔离住了——「我看了代码觉得不会碰」不算。

**② 单元测试的宿主 App 会真的申请系统权限，而没有任何人去点那个弹窗。**
单测跑在宿主 App 进程里；只要根视图 `.task` 里起了相机/定位/麦克风，
真机上就会弹系统授权框，测试挂在那里。
- 特别阴的地方：如果同项目的 XCUITest 里有 `dismissSystemAlerts()` 之类的助手，
  它早就替你点过「允许」，于是单测**看起来**一直是好的——**直到 App 被卸载重装一次**。
- 修法：权限/硬件会话的入口加一道「在测试进程里一律不启动」，判据用
  `ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil`
  （比只判自家的 `-uiScreenshots` 之类启动参数覆盖得全）。

## SwiftUI Correctness Checklist (vendored from vabole/apple-skills:ios-dev)

_Inline attribution: vendor 自 vabole/apple-skills v1.0.10 `skills/ios-dev/SKILL.md` (MIT, (c) 2026 Ilia Abolhasani, vendored 2026-05-14). 违反任一条即 bug，code-review 和 `apple-dev:ui-reviewer` agent（通过 /review-execution 派发）直接引用。_

- [ ] `@State` properties are `private`
- [ ] `@Binding` only where a child needs to mutate parent state
- [ ] Values passed in are never declared as `@State` — they silently ignore updates
- [ ] Use `@State` with `@Observable` classes — not `@StateObject` or `ObservableObject`
- [ ] Use `@Bindable` for injected observables that need bindings
- [ ] `ForEach` uses stable identity — never `.indices` on dynamic content
- [ ] Each `ForEach` element produces a constant number of views
- [ ] `.animation(_:value:)` always includes the `value:` parameter
- [ ] `@FocusState` properties are `private`
- [ ] `@Observable` classes are `@MainActor` — Swift 6 strict concurrency requires it
- [ ] Property wrappers (`@AppStorage`, `@SceneStorage`, `@Query`) inside `@Observable` classes are marked `@ObservationIgnored` — they conflict with the macro and cause compiler errors
- [ ] No business logic in `body` — use `.task`, `.onChange`, or methods
- [ ] No `AnyView` unless truly unavoidable — fix with better composition

## Topic Router (Local References)

_Inline attribution: 改编自 vabole/apple-skills:ios-dev Topic Router，全部路由指向本仓 `apple-dev/references/`。_

| Topic | Guide | API Reference |
|-------|-------|---------------|
| State management | `external/swiftui-ui-patterns/` | `external/swiftui-api/state.md`, `binding.md`, `observation.md`, `environment.md` |
| View composition | `external/swiftui-view-refactor.md` | — |
| Performance | `external/swiftui-performance-audit.md` | — |
| Navigation | `external/swiftui-ui-patterns/` | `external/swiftui-api/navigationstack.md`, `navigationsplitview.md` |
| Sheets & modals | `external/swiftui-ui-patterns/` | `external/swiftui-api/sheet.md` |
| Lists & ForEach | `external/swiftui-ui-patterns/` | `external/swiftui-api/list.md` |
| ScrollView | `external/swiftui-ui-patterns/` | `external/swiftui-api/scrollview.md` |
| Forms & input | — | `external/swiftui-api/form.md`, `textfield.md`, `picker.md` |
| Charts | `external/swiftui-charts.md` | `external/swiftui-api/chart.md` |
| Animations | `external/swiftui-animations.md` | — |
| Liquid Glass | `external/ios-design-consultant.md` | `external/ios-liquid-glass/` |
| Visual design | `external/ios-design-consultant.md` | `external/hig/` |
| Accessibility | — | `external/hig/accessibility.md` |
| macOS apps | `external/macos-spm-packaging.md` | — |
| Data persistence | `swiftdata-guide.md` (含 Community Patterns 节) | `external/swiftdata-api/` |
| Testing | `external/swift-testing-patterns.md` | `external/swift-testing-api/`, `xc-ui-test-guide.md` |
| Concurrency | `external/swift-concurrency-patterns.md` | `external/swift-concurrency-api/` |
| Widgets | — | `external/widgetkit/` |
| Tips | — | `external/tipkit/` |
| Notifications | — | `external/usernotifications/` |
| Photos | — | `external/photosui/` |
| App Store metadata | `aso-guide.md` | — |
| Simulator commands | `external/simulator-cheatsheet.md` | — |
