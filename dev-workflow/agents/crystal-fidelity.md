#### CF. 决策忠实度验证（有 crystal 文件的计划）

**前置条件**：dispatch prompt 包含 `Crystal file:` 路径且非 "none"。如果无 crystal 文件引用，跳过本策略。

完整读取 crystal 文件。

**步骤 1：决策覆盖检查**

对 crystal 文件中每条 `[D-xxx]` 决策：
1. 在 plan 中搜索是否有 task 实现或体现该决策
2. 如果决策是"用 X 方案"——plan 中应有 task 描述使用 X
3. 如果决策是"在 Y 位置新建 Z"——plan 中应有 task 新建 Z 且位于 Y

```
[CF-1] 决策覆盖检查
  - [D-001] "{decision text}" → Task {N}: "{task title}" — ✅ Covered
  - [D-002] "{decision text}" → — — ❌ Not covered
  - [D-003] "{decision text}" → Task {N}: "{task title}" — ✅ Covered
```

**步骤 2：否决方案反向检查**

对 crystal 文件中每条 Rejected Alternative：
1. 在 plan 中搜索是否有 task 描述与被否决方案一致
2. 如果 plan task 实现了被否决的方案 → ❌ 标记为 must-revise

```
[CF-2] 否决方案反向检查
  - "{alternative name}": 否决原因 — {reason} → ✅ No conflict
  - "{alternative name}": 否决原因 — {reason} → Task {N} implements this rejected approach — ❌ Conflict
```

**步骤 3：Scope 边界验证**（crystal 文件包含 `## Scope Boundaries` 段落时）

先检查 plan header 是否有 `**Scope conflicts:**` 段落。如有，这些是 plan-writer 识别出的 IN/OUT 冲突，报告为 must-revise 并在修订建议中引用这些冲突（需用户决策）。

对 crystal 中每条 OUT 边界：
1. 检查 plan 中是否有 task 修改该区域的文件/功能
2. 如果有 → ❌ 标记为 must-revise（plan 超出授权 scope）

对 plan 中每个删除现有功能的 task：
识别方式——扫描每个 task 的步骤描述，查找：(a) `**Replaces:**` 锚点字段（表示替代旧代码），(b) 步骤中的 "remove"、"delete"、"移除"、"删除"、"drop" 关键词，(c) task 标题或步骤描述的功能净减少。

对每个识别出的删除：
1. 检查该删除是否被 IN scope 条目或 D-xxx 决策授权
2. 如果未授权 → ❌ 标记为 must-revise（未授权的功能删除）

```
[CF-3] Scope 边界验证
  - OUT: "{boundary item}" → ✅ 无 plan task 涉及 / ❌ Task {N} 越界
  - 删除: Task {N} 移除 {functionality} → ✅ 已被 IN:{item}/D-{xxx} 授权 / ❌ 未找到授权
```

**判定**：
- CF-1 有未覆盖的决策 → must-revise
- CF-2 有冲突 → must-revise
- CF-3 有边界越权或未授权删除 → must-revise
