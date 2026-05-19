---
name: audit-finishing-touches
description: "Mechanical §17–§20 polish-gap scan over SwiftUI files. Runs 5 grep-based checks (border overuse, default-style controls, undecorated card backgrounds, empty-state pointer, undecorated hero areas) and outputs a 必修/建议/灵感 report — does NOT make subjective design judgments. Use when a module is feature-complete and the UI 'feels generic' / 'has AI-feel' / 缺少性格, or the user says 打磨 / polish / finishing touches. Not when: feature is incomplete (use feature-review first); or you want subjective hierarchy/color/spacing review (use design-review — that one judges visual quality, this one only flags mechanical gaps)."
compatibility: Requires macOS and Xcode (greps Swift files).
user-invocable: false
model: sonnet
paths: ["**/*.swift", "**/Package.swift", "**/*.xcodeproj/**", "**/*.xcworkspace/**"]
---

# Audit: Finishing Touches

针对已功能完成的模块，扫描"打磨感"缺口。与 `design-review` skill（合规审查）和 `feature-review` skill（用户旅程完整性审查）形成互补。

## 触发时机

- 模块功能完成后，界面"感觉平淡"或"有 AI 感"
- 用户说"polish"、"打磨一下"、"加细节"
- 设计稿感觉对，但实现出来缺少"性格"
- 希望在提交前做最后一轮视觉质量把关

## 流程

### 1. 确定范围

询问用户或自动识别：
- 指定文件：检查指定的 View 文件
- 指定目录：检查目录下所有 `*View.swift`、`*Screen.swift`、`*Card.swift`、`*Section.swift`、`*Row.swift`、`*Header.swift`
- 无指定：检查本次变更涉及的 UI 文件

排除：`Pods/`、`.build/`、`DerivedData/`、`*.generated.swift`、测试 target。

### 2. 加载参考

读取 `apple-dev/references/ui-design-principles.md`，重点关注：
- §17 — Depth & Elevation（阴影与层级）
- §18 — Images & Photography（图片与摄影）
- §19 — Finishing Touches（收尾打磨手段）
- §19.5 — 替代清单（border / shadow / background / accent border）
- §20 — Hierarchy Tactics（层级战术，labels/baseline/weight-contrast）

### 3. 运行 5 项机械检查

对范围内每个 Swift 文件逐一执行以下检查。

---

### Check 1 — Border Usage

**原则：** 1pt 边框是最弱的容器暗示，过度使用 = 视觉拥挤 (§19.5)。

**机械规则：**
```bash
# Single-line forms: .border(...), .overlay(RoundedRectangle... .strokeBorder...)
grep -cE '\.border\(|\.overlay.*RoundedRectangle.*stroke' <file>

# Leaf form: RoundedRectangle as the view itself (no overlay wrapper)
# Example: RoundedRectangle(cornerRadius: 8).strokeBorder(...)
grep -cE 'RoundedRectangle\(.*\)\s*\.strokeBorder|^\s*\.strokeBorder' <file>
```
对每个文件执行两个 grep，将命中数相加得到该文件的 border 总数。阈值：单文件总命中 ≥ 3 次 → 标记。

**已知盲点：** 多行 `.overlay(\n RoundedRectangle(...)\n .strokeBorder(...)\n)` 写法本 grep 不会匹配（除非以 `pcre2grep -M` 多行模式扫描）。命中数偏低视为可接受的 false negative。

**建议：** §19.5 替代清单（阴影 / 背景色阶 / 留白 / Section / accent border）

**层级映射：**
- ≥ 5 次命中 → 必修（极端过度边框，几乎不会是无意；剥离 1–2 个边框替换为阴影/背景色阶通常即可消除拥挤）
- 4 次命中 → 建议
- 3 次命中 → 灵感

**注意：** 此 grep 同时会命中 §19.2 中 intentional 的 1pt 强调色边框（accent border）。计数为 raw 值，读者需查看上下文后再决定是否替换。

---

### Check 2 — Default-style Controls

**原则：** 核心交互的 Toggle / Picker / DatePicker 值得定制以体现品牌 (§19.1)。

**机械规则：**
```bash
# Match Toggle(/Picker(/DatePicker( anywhere — line-start anchor misses
# `private var foo: some View { Toggle(...) }` and similar wrapped forms.
grep -nE '\bToggle\(|\bPicker\(|\bDatePicker\(' <file>
```
对每个命中行 M，先检查 M 后 3 行内是否含有 `.toggleStyle` / `.pickerStyle` / `.datePickerStyle`。有 → 跳过该命中。无 → 进入下一步父容器扫描。

**父容器扫描（确定性规则）：**

1. 从命中行 M 向**上**扫描，记录每行未配对的 `{` 与 `}`。
2. 遇到第一行其 `{` 数 > `}` 数（= 进入了一个外层 scope） → 记此行为 P。
3. 从 P 向**下**扫描，跟踪 `{`/`}` 计数；当计数回到 P 行的初始余量时，记此行为 Q（= P 对应的闭合 `}`）。
4. 在区间 [P, Q] 内 grep `\.toggleStyle\b|\.pickerStyle\b|\.datePickerStyle\b`：
   - 命中 → 父容器统一定制了，**不标记**。
   - 无命中 → 标记原始命中行 M。
5. 若 P 找不到（M 已在文件最外层）或 Q 触达文件结尾 → 视为无父容器定制，标记 M。

**建议：** §19.1 超充默认值（`BrandToggleStyle` / `BrandSegmentedPickerStyle` / `BrandDatePickerTrigger` 代码片段）

**层级映射：**
- 主屏控件（设置页、引导页、支付页）→ 建议
- 罕见工具页面 → 灵感

**已知限制：** 间接声明（`private var toggle: some View { Toggle(...) }` 然后在另一处使用 `Self.toggle.toggleStyle(...)`）本检查仍会标记。这是可接受的 false positive — 让读者人工确认即可。一次性提示用途（如系统弹窗中的 picker）无需定制，读者上下文判断后归类为灵感。

---

### Check 3 — Undecorated Card Backgrounds

**原则：** 纯 `.background(.regularMaterial)` 无 accent border / gradient / pattern → 工程师感强 (§19.2 / §19.3)。

**机械规则：**
```bash
# Both shorthand (.regularMaterial) and qualified (Material.regular) forms
grep -nE '\.background\(\.(regular|thick|thin|ultraThin|ultraThick)Material\)|\.background\(Material\.(regular|thick|thin|ultraThin|ultraThick)\)' <file>
```
对每个命中行，检查其周围 5 行内是否含有：`.overlay(alignment:` 配合 `.fill(.*accent` / `Rectangle().fill(Color.accent` / `RadialGradient` / `LinearGradient` / `Canvas` / `Image(`。均无 → 标记。

**建议：** §19.2（1pt 左/顶 accent border）或 §19.3（radial gradient / pattern / illustration）

**层级映射：**
- Hero / dashboard / login 容器 → 建议
- 普通列表 cell → 灵感

**注意：** 工具型卡片（如设置 row）刻意保持朴素 — 默认映射为灵感，由读者判断是否升级。

---

### Check 4 — Empty-state Coverage

**原则：** 列表 / 搜索 / 异步加载结果为空时需引导 (§19.4)。

**机械规则：** 本 skill **不重复扫描**。改为输出以下指针：

> 空状态完整规范见 `apple-dev:feature-review` B3 检查项与 `apple-dev:ui-review`。本 skill 不重复列表扫描；仅在 audit 结尾以 hint 形式提醒：「如尚未跑过 feature-review，建议补一次空状态扫描。」

**建议：** 跨引用，无重复检测逻辑。

**层级映射：** N/A — 仅作指针。

**注意：** 根据 Phase 1 §19.4 dev-guide AC，本节设计为引用式，不执行独立扫描。

---

### Check 5 — Hero / Title Decoration

**原则：** 顶部 Section / 大标题区域裸 `Text(...).font(.largeTitle)` 而无背景装饰 → 错失"性格"机会 (§19.3)。

**机械规则：**
```bash
# Match .largeTitle, .title, and .system(size: N[.M]) where N is any integer
grep -nE '\.font\(\.largeTitle\)|\.font\(\.title\)|\.font\(\.system\(size:\s*[0-9]+(\.[0-9]+)?' <file>
```
对 `.system(size: ...)` 命中，post-filter 出 size ≥ 28 的行（解析捕获的数字，包括 `28.0` 这类小数）。

`.largeTitle` / `.title` 无需 size 过滤 — 直接覆盖三类大字号 hero 候选。对每个保留下来的命中行，检查其上下 10 行内是否含有：`RadialGradient` / `LinearGradient` / `Canvas` / `Image(` / `.background(` 配合非系统颜色。均无 → 标记。

**建议：** §19.3 装饰背景（radial gradient / Canvas pattern / illustration）

**层级映射：**
- 文件名含 `Dashboard` / `Home` / `Hero` / `Landing` / `Welcome` **且**整个文件无任何 §19 装饰元素（gradient / Canvas / Image / accent border）→ 必修（hero 区域无性格 = 错失关键品牌时刻）
- Dashboard / landing / hero 页面（命名匹配但文件中其他位置有 §19 元素）→ 建议
- 深层导航内部页面 → 灵感

**注意：** 工具型 / 设置页有正当理由保持简洁标题 — 默认映射为灵感。文件名 escalation 是为了防止 hero 区"全裸"出货。

---

### 4. 输出报告

```
## Audit: Finishing Touches Report

> Note: Check 4 (空状态) is a cross-reference pointer — it produces no entries
> in 必修/建议/灵感 below. See the Hint section.

### 检查范围
- [file list with line counts]

### 必修 (must-fix polish gaps)
- [Check N · file:line] {one-line description}
  §X.Y reference: {section title}
  Before / After SwiftUI snippet:
  ```swift
  // before (current code)
  ...
  // after (suggested replacement)
  ...
  ```

### 建议 (recommended polish improvements)
- [Check N · file:line] {one-line description}
  §X.Y reference: {section title}
  Suggestion: {short prose; snippet optional}

### 灵感 (inspiration — context-dependent)
- [Check N · file:line] {one-line description}
  §X.Y reference: {section title}
  Note: this may be intentional in your context — review and decide.

### Hint
- 如果尚未跑过 `apple-dev:feature-review`，建议补一次空状态扫描（Check 4 在本 skill 中仅作为 pointer，未执行扫描）。

### 总结
- 检查文件数: N
- 必修: X · 建议: Y · 灵感: Z
```

---

### 5. 用户确认

报告输出后，**禁止自行修改被审查文件**。必须使用 `AskUserQuestion` 让用户选择：

- 选项从报告的 必修 / 建议 发现中生成
- 用户确认后，仅修复用户选中的项目
- 用户未确认 = 不动代码

---

## Completion Criteria

- 报告包含 必修 / 建议 / 灵感 三层
- 每个发现附 `file:line` 引用和 §X.Y 引用
- Check 4 仅发出跨引用指针，无独立列表扫描
- 修复动作经过 `AskUserQuestion` 确认
