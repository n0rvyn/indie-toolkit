---
name: asc-listing
description: "Use when preparing ASC store listing materials, or the user says 'ASC listing', 'asc 上架材料', 'ASC 填写', 'app store listing', 'privacy labels'. Performs item-by-item App Store Connect submission material check and guidance. Keywords: ASC, App Store Connect, submission, privacy labels, screenshots, review. Not for 代码合规检查 — use /asc-submit-preview."
---

# App Store Connect 上架审查

逐项指导 App Store Connect 中 iOS/macOS App 上架需要填写的内容，或执行提交前审计。

参考资料在 `asc-listing/references/` 目录中（相对于 skills 目录），按需加载。

## Process

### Step 1: 确定审查模式

从用户消息判断：

**模式 A — 全量填写指导**：用户首次上架或说"帮我填 ASC"。按顺序引导所有字段。

**模式 B — 隐私标签**：用户专门问隐私标签。聚焦 App Privacy 部分。

**模式 C — 特定部分**：用户问某个具体字段或部分。加载对应 reference 段落回答。

> 历史说明：早期版本含"代码合规审计"模式，已迁移到 `/asc-submit-preview`。本 skill 不再处理代码合规，专注 ASC 后台材料（隐私标签 / 截图 / 描述 / 价格 / 关键词）。

### Step 2: 加载参考资料

根据模式加载对应 reference：

| 模式 | 加载文件 |
|------|---------|
| A | `references/asc-fields-guide.md` → `references/asc-version-and-review.md` → `references/asc-audit-checklist.md`（准备清单部分） |
| B | `references/asc-fields-guide.md`（第二部分：App Privacy） |
| C | 根据用户问题定位对应 reference 的具体段落 |

### Step 3: 执行审查

**模式 A**：按 reference 中的字段顺序，逐项向用户解释并确认填写内容。每完成一个大部分（App Information / Privacy / Version），确认再进入下一部分。

**模式 B**：读取项目代码（import 语句、网络请求、数据存储），帮用户判断每个数据类型是否需要声明。输出格式：

```
[隐私标签审查]
| 数据类型 | 是否收集 | 证据 | 建议 |
|---------|---------|------|------|
| Health | ✅ | import HealthKit in ... | 声明，关联用户，App Functionality |
| Location | ❌ | 无相关 import/API | 不声明 |
```

**模式 C**：直接回答用户问题，引用 reference 中的具体指引。

### Step 4: 输出报告

**模式 A/B**：输出已确认的字段值汇总，标注待用户补充的项。

## Completion Criteria

- 用户确认的模式已完成
- 所有检查项有明确结果（通过/不通过/待确认）
- 不通过的项有具体修复建议

## 串联提示

✅ ASC 上架审查完成。

**ASO 优化**（与 ASC 合规审查互补，关注 metadata discoverability）：
- App Store 关键词 / 标题 / 副标题 / description 优化与本地化策略 → grep `apple-dev/references/aso-guide.md`
