---
name: fork-this
description: "Use when discussing topic A and an orthogonal problem B surfaces mid-session, OR the user says 'fork this', 'park this', '先记下来', '先放着', 'fork-this', '分叉', '现场分叉', '另起一个'. Generates a minimal seed prompt for B in a clean fork context, writes to docs/06-plans/ (or .claude/parked/ for non-dev-workflow projects), and returns a one-line receipt so the main session can continue with A uninterrupted. Not when: ending session and transferring all current work — use handoff instead. Not when: B is already well-scoped and the user wants to switch immediately (just /clear)."
user-invocable: true
context: fork
model: sonnet
argument-hint: "<one-line description of topic B>"
allowed-tools: Read, Write
---

# Fork This Topic

Mid-session orthogonal split. Used when topic A is the active discussion but B has just surfaced and would derail A if developed inline.

## Process

### Step 1: Capture B's minimal context

Based on the user's argument (B's description) AND the recent main-session context visible in this fork's parent:
- Identify B's symptom (1-2 sentences)
- Identify the file(s) where B was observed (if mentioned in main context)
- Identify what the user was doing on A when B surfaced (1 sentence, for context only)

Do NOT include main session's full history. The whole point is a clean seed.

### Step 2: Write seed file

Path resolution:
- If `docs/06-plans/` exists under project root → write to `docs/06-plans/YYYY-MM-DD-<slug>-seed.md`
- Else → write to `.claude/parked/YYYY-MM-DD-<slug>-seed.md` (creating `.claude/parked/` if absent)

Slug is kebab-case of B's description (max 40 chars).

Format:
```markdown
---
type: topic-seed
status: parked
parked_from: <main session date + brief A-topic>
tags: [seed]
---

# B 主题种子

## 现象
{1-2 句症状描述}

## 相关文件
- {path}
{或 "尚未定位"}

## 上下文起源
在 {date} 的 {A-topic} 讨论中浮现。本种子是为了让 B 在干净 session 中独立推进。

## 建议的开场指令
"Read docs/06-plans/{seed-file}; 然后开始诊断 B。"
```

### Step 3: Return receipt to main session

Output to main session (single line, use actual chosen path):

`B parked at <full-path>; copy as cold-start prompt for new session. Main can continue A.`

## Completion criteria

- Seed file written (under `docs/06-plans/` or `.claude/parked/` per resolution above)
- Receipt line returned to main session

## Why this skill (vs handoff)

- **handoff**: end-of-session, transfer everything to a follow-up session
- **fork-this**: mid-session, park ONE orthogonal problem, current session keeps going on the original topic
