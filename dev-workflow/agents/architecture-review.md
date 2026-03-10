#### AR. 架构审查（架构变更时）

**目的**：检测并行路径、不完整替代、死保底。从 `reviewing-architecture` skill 吸收。

**AR.1 入口唯一性检查**

对计划中每个新增的入口（trigger、scheduler、observer、event handler）：
- 找出该入口最终调用的核心函数
- Grep 该核心函数及其关键子函数的所有现有调用者

```
[入口检查] 计划新增入口: {new entry point}
目标核心函数: {function name}
现有调用者:
- {file:line} — {caller description}
- {file:line} — {caller description}
结论: ✅ 无并行路径 / ⚠️ 已存在 {N} 条路径，需合并或说明共存理由
```

现有调用者走不同上游路径且计划未说明 → 停止，报告冲突。

**AR.2 替代完整性检查**

对计划或相关 ADR 中每个"替代/淘汰/取代"：
- 列出需要删除/修改的具体项：

```
[替代清单] {old component} → {new component}
需删除:
- [ ] {file}: {method/config} — {用途}
- [ ] {file}: {registration/import} — {用途}
需修改:
- [ ] {file:line}: {old reference} → {new reference}
```

计划或 ADR 缺少此清单 → 标记为不完整，通过 Grep 构建清单。

**AR.3 数据流追踪**

对计划修改的主要数据：
- 从源头到终点追踪：

```
[数据流] {data name}
生产: {file:line} ({how it's created})
处理: {file:line} → {file:line} ({transformations})
持久化: {file:line} ({storage})
展示: {file:line} ({UI display})
```

每个处理节点搜索其他上游调用者（= 并行路径）。并行路径无协调机制 = 架构冲突。

**AR.4 保底验证**

对计划或现有代码中任何"保留作为保底/fallback"：

```
[保底三问] {component kept as fallback}
1. 协调机制: {谁决定走哪条路径? — 具体代码位置 / "无"}
2. 触发条件: {什么条件走旧路径? — 可求值的布尔表达式 / "无"}
3. 移除条件: {何时删除? — 可验证的里程碑 / "无"}
结论: ✅ 三问均有具体答案 / ❌ {N}问无答案 → 建议用户决定是否删除旧实现
```

"运行时决定" / "新路径失败时" / "测试通过后" = 描述性回答 = 无答案。
