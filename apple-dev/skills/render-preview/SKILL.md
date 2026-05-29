---
name: render-preview
description: "Internal tool-wrapper that renders a SwiftUI #Preview to a downsampled PNG and returns a structured { channel, pngPath, downsampled, error } result. Internal callee for run-phase's visual feedback step (hidden from the / menu); not for ad-hoc user requests. Primary path: Apple Xcode MCP RenderPreview; headless fallback: axe / swiftui-render. Not for: running-app / navigation / animation screenshots or XCUITest visual regression (use apple-dev:xc-ui-test, simctl io, or XcodeBuildMCP), UDID-targeted tests, or design-vs-render diffing (that's the caller's job)."
user-invocable: false
model: haiku
context: fork
---

<!-- cost-posture rationale:
  This skill is a tool-wrapper: input = Swift view path, output = PNG path, no judgment.
  model: haiku (tool-wrapper standard) + context: fork (structured { channel, pngPath } return to caller).
  Diff/iteration judgment lives in the calling run-phase main context.
  model: haiku kept intentionally — billing gate issue #24: sonnet child skills fail in
  opus-[1m] parent sessions (CC auto-appends [1m] via modelSupports1M() without checking
  Sonnet-1M entitlement). Do NOT upgrade to sonnet without resolving issue #24.
-->

# render-preview

渲染 SwiftUI `#Preview` 块为 PNG 图片，返回结构化结果 `{ channel, pngPath, downsampled, error }`，供调用方（如 run-phase visual feedback step）进行视觉比对。

本 skill 不做 diff、不做迭代判断；这些归调用方负责。

**Requires**：macOS。RenderPreview 主路需 Xcode 26.3+ 开着项目；无头 fallback（axe / swiftui-render）不需要。

---

## Input

| 字段 | 必选 | 说明 |
|------|------|------|
| `swiftFile` | 必选 | 目标 Swift 文件路径（含 `#Preview` 块） |
| `previewId` | 可选 | `#Preview` 标识符（文件含多个 Preview 时区分）；省略则渲染默认/第一个 |
| `outputDir` | 可选 | PNG 输出目录；省略则使用系统临时目录 |

**输出文件名 `<name>`** = `swiftFile` 基名（去 `.swift`）+（`previewId` 非空时）`-{previewId}` —— 避免同文件不同 preview 撞名。

---

## Process（通道选择，对齐 D-003/D-007）

精确命令参数参见 `apple-dev/references/xcode-mcp-setup.md`，并在执行前核对各工具 `--help`/README。

### Step 1：RenderPreview（主路，需 Xcode MCP）

探测 `RenderPreview` MCP 工具是否可用（即 Xcode MCP 已连接、Xcode 开着且项目已打开）。

可用时：调用 `RenderPreview` MCP 工具，**传入 `swiftFile`；`previewId` 非空时一并传入以选定具体 `#Preview`**（省略则渲染默认/第一个）。读取返回结果中的 `previewSnapshotPath`（PNG 文件绝对路径）。

```
channel: xcode-mcp
pngPath: <previewSnapshotPath 值>
```

成功 → 跳至 [降采样步骤](#step-4降采样-3x-→-1x)。

### Step 2：无头 fallback — axe（k-kohey）

RenderPreview 不可用时，尝试 `axe`（读取 `#Preview` 块，oneshot 截图）：

```bash
# 基本形态；执行前核对 axe --help/README 确认精确 flag
# previewId 非空时，按 axe 的 preview 选择 flag 传入（精确 flag 核对 --help）
axe preview <SwiftFile.swift> > <outputDir>/<name>.png
```

```
channel: axe
pngPath: <outputDir>/<name>.png
```

成功 → 跳至 [降采样步骤](#step-4降采样-3x-→-1x)。

### Step 3：无头 fallback — swiftui-render（olliewagner）

axe 不可用或失败时，尝试 `swiftui-render`（Catalyst backend，iOS 渲染精确）：

```bash
# 基本形态；执行前核对 swiftui-render --help/README 确认精确 flag
# previewId 非空时，按 swiftui-render 的 preview 选择 flag 传入（精确 flag 核对 --help）
swiftui-render <SwiftFile.swift> --output <outputDir>/<name>.png
```

```
channel: swiftui-render
pngPath: <outputDir>/<name>.png
```

三条通道均失败 → 返回 Output 的**失败 JSON**（`channel: null, pngPath: null, error: <原因+指引>`），不要返回散文。

### Step 4：降采样 3x → 1x

得到 PNG 后执行降采样（省约 89% image token）：

```bash
magick <pngPath> -resize 33.333% <outputDir>/<name>_1x.png
```

降采样成功 → `pngPath` 指向 `_1x.png`、`downsampled: true`。若 ImageMagick 未安装 → 跳过此步、`pngPath` 保持原图、`downsampled: false`。

---

## Output

**返回通道（重要）**：`context: fork` 下，forked subagent 的最终消息会被**摘要**后回传（官方文档：results are summarized），逐字节的路径串不保证原样到达调用方。因此结果以**文件**为权威通道，最终消息仅供人读：

1. **结果文件（权威）**：用 Write/Bash 将结果 JSON（成功或失败，见下）写入 `<outputDir>/<name>.result.json`（`<name>` 见 Input 节命名规则）。调用方据此确定性路径 `Read` 该文件解析结果，**不依赖**最终消息回传。
   - ⚠️ 作为 run-phase 视觉环被调用时，调用方**必须传入显式 `outputDir`**；否则结果文件落在系统临时目录、调用方无法确定其路径。
2. **最终消息（便于人读）**：最终消息同时输出同一 JSON 对象本身（不附带其它散文）。

成功：
```json
{
  "channel": "xcode-mcp | axe | swiftui-render",
  "pngPath": "/absolute/path/to/preview.png",
  "downsampled": true,
  "error": null
}
```

失败（三通道全败 / 无 #Preview / 工具缺失）：
```json
{
  "channel": null,
  "pngPath": null,
  "downsampled": false,
  "error": "<失败原因 + 安装/修复指引，如 'Xcode 未开且 axe/swiftui-render 未安装'>"
}
```

- `downsampled`：`true` = 已降采样到 1x；`false` = 跳过（ImageMagick 缺失或 channel 已返回 1x），`pngPath` 为原始分辨率，调用方据此估算 image token。

---

## Guardrails

- 本 skill 渲染**孤立单 view**（`#Preview` 块隔离态），**不支持**：运行态 app 截图、跨页面导航状态、动画、依赖 app 环境的 view（用 `simctl io` 或 `XcodeBuildMCP` 代替）
- diff 和迭代判断**不在本 skill 范围** —— 归调用方（run-phase 等）负责
- 本仓无 iOS Xcode 项目，端到端渲染无法烟测：⚠️需项目验证 —— 在真实 iOS 项目中对一个 `#Preview` 跑通「渲染 → PNG」（RenderPreview 主路 + 至少一条无头 fallback）

---

## 参考文档

- 工具安装 + 命令细节：`apple-dev/references/xcode-mcp-setup.md`
- Simulator / xctest 能力分工：`~/.claude/references/xcodebuild-simulator-testing.md`
