---
name: reviewing-rules
description: "Use when Claude exhibited unexpected behavior, for periodic rule health checks, or after adding new rules. Audits CLAUDE.md rules from the AI execution perspective for conflicts, loopholes, gaps, and redundancies."
disable-model-invocation: true
---

## 触发场景

- 会话中 Claude 出现预期外偏差
- 定期规则健康检查
- 新增规则后检查一致性

## 输入

可选：用户描述本次偏差现象（如"Claude 自作主张加了动画"）

## 执行流程

1. 读取 `~/.claude/CLAUDE.md` 和项目 `CLAUDE.md`
2. 以 AI 执行视角分析：

### 2.1 冲突检测
找出可能被我利用来选择性遵守的规则对：
- 规则 A 说 X，规则 B 说 Y，X 和 Y 可能矛盾
- 输出格式：`| 位置 | 冲突 | 我可能的解释 |`

### 2.2 漏洞检测
找出规则表述中我可能钻的空子：
- "优先"、"尽量"、"一般" → 无强制力
- 条件触发不明确 → 我可声称条件不满足
- 输出格式：`| 位置 | 漏洞 | 我可能的绕法 |`

### 2.3 缺失检测
基于近期偏差或常见问题，找出缺失的规则：
- 输出格式：`| 缺失规则 | 会导致的问题 |`

### 2.4 冗余检测
找出重复表述（不一定要删，但需知晓）

3. 针对发现的问题，提出具体修复建议
4. 用户确认后执行修复

## 输出格式

```
## Rules Review Report

### 输入的偏差现象
[用户描述，或"定期检查"]

### 冲突
| 位置 | 冲突 | 我可能的解释 |
|------|------|--------------|

### 漏洞
| 位置 | 漏洞 | 我可能的绕法 |
|------|------|--------------|

### 缺失
| 缺失规则 | 会导致的问题 |
|---------|--------------|

### 修复建议
1. [具体修改内容]
2. ...

是否执行修复？
```

## 原则

- 以 AI 执行视角审视，不考虑人类可读性
- 假设我会寻找规则漏洞，主动暴露这些漏洞
- 修复建议要具体可执行，不要泛泛而谈
