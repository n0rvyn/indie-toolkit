---
name: handoff
description: "Use when ending the current session and transferring ALL current work to a new session (next day, different person), the user says 'handoff', '交接'. End-of-session full transfer — not for mid-session orthogonal splits (use /fork-this for that). Generates a cold-start prompt covering: current plan, completed items, open items, key files, next steps."
disable-model-invocation: true
context: fork
model: sonnet
---

## 使用场景

- 任务未完成需要续接
- 复杂问题需要跨会话追踪

## 输出格式

```markdown
## 上下文恢复

项目：[项目名称和简述]
当前任务：[一句话描述]

### 执行计划（如有）
来源：[docs/06-plans/xxx.md | ~/.claude/plans/xxx.md | "用户消息内联提供" | 无]
状态：[全部完成 | 进行中(N/M) | 中断 | 无计划]
Crystal file：[docs/11-crystals/xxx-crystal.md | 无]

（dev-workflow:write-plan 计划文件在 docs/06-plans/，内置 /plan 计划文件在 ~/.claude/plans/，新会话可直接 Read）

### 问题
[遇到的核心问题，包含具体报错/现象]

### 已完成
1. [已完成项 1]
2. [已完成项 2]
...

### 当前状态
[刚做完什么，卡在哪里]

### 关键文件
- `path/to/file1` - 说明
- `path/to/file2` - 说明

### 下一步
1. [待做项 1]
2. [待做项 2]

### 关键代码/配置（如有）
[粘贴关键代码片段或配置，避免新会话重新查找]
```

## 执行指令

读取当前会话上下文，生成上述格式的 markdown。要求：
1. 信息密度高，去掉废话
2. 包含具体文件路径（绝对路径）
3. 包含具体错误信息/日志（如有）
4. 关键代码片段直接粘贴，不要说"见某文件"
5. 输出为 markdown 代码块，方便用户复制
6. 如果当前会话是按计划执行的，必须包含计划来源（文件路径或 transcript 路径）
7. 如果项目有 crystal 文件（`docs/11-crystals/*-crystal.md`），在关键文件中列出路径

## Fork-Context Failure Fallback

This skill runs in a forked context (`context: fork` in frontmatter). If the fork fails (rare but possible — OOM, transient platform error), the user may see no output in the main session.

**What the user should see on success:** a markdown block starting with `## 上下文恢复` containing the structured handoff sections.

**If no output appears within ~30 seconds of invoking `/handoff`:** the fork likely failed. User remediation:

1. Retry: `/handoff` (often transient).
2. If retry also produces no output: manually export by quoting key files in the chat:
   - Current plan file (if any): `docs/06-plans/*-plan.md` (most recent)
   - Crystal file (if any): `docs/11-crystals/*-crystal.md` (most recent)
   - Current state file (if any): `.claude/dev-workflow-state.yml`
   - One-line task summary
3. Paste these into the new session as the cold-start prompt.

The fallback exists because forked contexts have no main-session error channel — silent fork failure is the only failure mode that doesn't surface naturally.
