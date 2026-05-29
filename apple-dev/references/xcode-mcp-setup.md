# Xcode MCP Setup（RenderPreview + 无头 fallback）

本文档说明如何配置 Apple Xcode MCP 以及无头 fallback 工具，供 `render-preview` skill 使用。

---

## 1. 启用 Xcode MCP

### 1.1 Xcode 端设置

```
Xcode → Settings (⌘,) → Intelligence → Model Context Protocol → Xcode Tools = ON
```

### 1.2 注册 MCP server

```bash
# 项目级（当前目录生效）
claude mcp add --transport stdio xcode -- xcrun mcpbridge

# 用户级（所有项目生效，加 -s user）
claude mcp add -s user --transport stdio xcode -- xcrun mcpbridge
```

### 1.3 验证注册

```bash
claude mcp list
# 预期输出中含 xcode (stdio)
```

---

## 2. 硬约束

- **Xcode 必须开着**：`xcrun mcpbridge` 是 XPC 遥控 **开着的 Xcode**。Xcode 崩溃或关闭后，所有 MCP 调用立即断开，直到 Xcode 重新打开且项目已加载。
- **项目必须已打开**：目标 Swift 文件所属的 Xcode 项目必须在 Xcode 中处于打开状态。
- **授权弹窗**：首次连接及每次重启 Xcode 后，可能出现多次 "Allow Connection?" 授权弹窗，需手动点击 Allow。

---

## 3. RenderPreview 用法

`RenderPreview` 是 Xcode MCP 提供的工具，用于渲染 SwiftUI `#Preview` 块并返回 PNG 截图。

**调用方式**（通过 MCP tool call，由 skill 自动调用）：

- 传入目标 Swift 文件路径和（可选）`#Preview` 标识符
- 返回结果含 `previewSnapshotPath`（PNG 文件绝对路径）

**重要说明**：

- RenderPreview 渲染**孤立单 view**（与 `#Preview` 块隔离），**不是**运行态 app 的截图
- 不支持跨页面导航状态、动画或依赖运行态 app 环境的 view
- 需 Xcode 26.3+（`xcrun mcpbridge` 需要该版本起支持）

---

## 4. 无头 fallback（无需 Xcode 开）

当 Xcode MCP 不可用时，可使用以下工具渲染 `#Preview`。**精确命令行 flag 以各自 README / `--help` 为准，执行前务必核对。**

### 4.1 axe（k-kohey）

- 读取 Swift 文件中的 `#Preview` 块，oneshot 截图输出至 stdout
- 安装：参见 [https://github.com/k-kohey/axe](https://github.com/k-kohey/axe) 的 README
- 基本形态（执行前核对 --help 确认精确 flag）：
  ```bash
  axe preview <SwiftFile.swift>
  # 输出 PNG 至 stdout；重定向到文件：
  axe preview <SwiftFile.swift> > output.png
  ```

### 4.2 swiftui-render（olliewagner）

- Catalyst backend，iOS 渲染精确
- 安装：参见 [https://github.com/olliewagner/swiftui-render](https://github.com/olliewagner/swiftui-render) 的 README
- 基本形态（执行前核对 --help 确认精确 flag）：
  ```bash
  swiftui-render <SwiftFile.swift> --output <output.png>
  ```

---

## 5. 3x → 1x 降采样（省 image token）

Retina 截图为 3x 分辨率，传给 LLM 前降采样到 1x 可节省约 89% image token：

```bash
magick <input>.png -resize 33.333% <output>_1x.png
```

需要安装 [ImageMagick](https://imagemagick.org/)：

```bash
brew install imagemagick
```

---

## 6. 能力分工总览

本文档只覆盖 Preview 渲染（孤立 view → PNG）。运行态 app 截图、simulator 控制、xctest 等能力分工见：

```
~/.claude/references/xcodebuild-simulator-testing.md
```
