---
name: handoff
description: "Use when ending the current session and transferring ALL current work to a new session (next day, different person), the user says 'handoff', '交接'. End-of-session full transfer — not for mid-session orthogonal splits (use /fork-this for that). Produces a handoff that (a) carries decisions, reversals, open items and traps forward, and (b) instructs the receiving session how to resume, so the user does not have to craft an opening prompt."
disable-model-invocation: true
---

<!-- attribution-gate: exempt — 本文件是交接 skill 的规则原文，第 11 条逐字复述
     attribution-gate 自己的判据（引用用户原话须逐字、须标轮次），必然含归属标记与
     规范性标记。这里没有任何署到用户名下的新约束。 -->

## 使用场景

- 任务未完成需要续接
- 复杂问题需要跨会话追踪

## 这份交接有两个读者，别只写给一个

| 读者 | 他需要什么 |
|---|---|
| **新会话（模型）** | 一份能**照着执行**的续接指令 —— 读什么、按什么顺序、哪些坑别踩、哪些事不许自己决定 |
| **用户（人）** | 不用每次打磨开场 prompt。他只会说一句「handoff from last session」，剩下的**这份文件要自己交代清楚** |

⛔ 只写「我做了什么」= 只服务了写的人。**续接指令必须在文件里**，不能指望用户输入。

## 输出格式

⚠️ `§0` 是**给新会话的指令**，必须放在最前面，且必须保留祈使语气。

````markdown
## 0. 你（新会话）现在要做的

**动手做任何事之前，先做完这三步，把结果说给用户听：**

1. **按序读**：本文件全文 → [关键文件清单里标 ⭐ 的那几份] → [产出样本的路径]
2. **复述**你读到的：规则 / 目标 / 偏好 / 结论（已定·已推翻·未决）/ 我们到底想弄个啥
   - **每一条注明出处**（哪份文件的哪一节）。⛔ 没有出处的条目不许写进复述
   - **数字必须来自你实际跑过的命令**（`wc -l`、`git log`、脚本输出）。
     ⛔ 不许估，⛔ 不许写「全文 N 行」而没真数过
   - **单列一节「我没读到 / 读了但不确定的」** —— 这一节空着比编满强
3. **别自己决定** §4 里列出的事项，那些要用户裁决

---

## 1. 上下文恢复

项目：[名称和一句话简述]
当前任务：[一句话]
里程碑 / tag：[git tag 或 commit，无则写「无」]

### 执行计划（如有）
来源：[docs/06-plans/xxx.md | ~/.claude/plans/xxx.md | "用户消息内联提供" | 无]
状态：[全部完成 | 进行中(N/M) | 中断 | 无计划]
Crystal file：[docs/11-crystals/xxx-crystal.md | 无]

（write-plan 计划在 `docs/06-plans/`，内置 /plan 计划在 `~/.claude/plans/`，新会话可直接 Read）

## 2. 现在能跑到哪一步

[当前形态：一段说明 / 一张流程图 / 几行命令。**跑法与校验命令写全**，新会话要能照着复现]

## 3. 已推翻的（⛔ 别再走回去）

| 曾经的结论 | 实测把它推翻成什么 |
|---|---|

⚠️ **这一节往往比「已完成」重要。** 删掉被推翻的结论，下一个人会再走一遍那条死路。
**自己犯的错也写进来，并写清是自己的错。**

## 4. ⛔ 需要用户裁决的（新会话不许自己选）

- [事项：冲突/取舍是什么 · 各选项的代价 · ⛔ 不许默认选哪个，以及为什么]

⚠️ 与 §7「下一步」**分开列**。待办是可以做的，裁决是不许替他做的；
混在一起，新会话会把裁决当待办自己做掉。

## 5. 未决 / 已报未修

[我报过、用户没否、还没做的。每条写：是什么 · 证据在哪 · 不修的代价]

## 6. 关键文件

- ⭐ `绝对路径` — 说明（⭐ = 新会话必读）
- `绝对路径` — 说明

## 7. 下一步

1. [待做项]

## 8. 最容易踩的坑

1. [具体到「做 X 的时候会踩 Y」。⛔ 不要写「注意质量」这种]
````

## 执行指令

读取当前会话上下文，生成上述格式。要求：

1. 信息密度高，去掉废话
2. **绝对路径**
3. 具体报错/日志**原文**（如有）
4. 关键代码片段直接粘贴，不要说「见某文件」
5. 计划来源必须写（文件路径或 transcript 路径）
6. 项目有 crystal 文件就在 §6 列出

### 可核性 —— 这一节是本 skill 的重点

7. **每条结论标出处。** ⛔ 写不出出处的，要么去查，要么移进「不确定」。
8. **数字必须是跑出来的**，不是估的。行数用 `wc -l`，提交用 `git log`，测试数用实际输出。
9. **⛔ 项与「需用户裁决」项分开**（§3 vs §4）。
10. **把自己犯的错写进 §3**，写清是自己的错。交接的价值一半在这里。
11. **引用用户原话要逐字，并标明哪一轮。** ⛔ 转述不得写成对方的原话
    （`attribution-gate` 会拦下署名却无「来源：」行的规范性约束）。

### 落盘还是贴出来

12. 项目有 `docs/06-plans/` → **写成文件** `HANDOFF-YYYY-MM-DD.md`，
    并在项目 `CLAUDE.md` 的必读顺序里挂上它。⛔ **不挂 = 下个会话不会读到**。
13. 写成文件时**照样把 §0 写进文件里** —— 那是给新会话的指令，不是给用户看的说明。
14. 没有 `docs/06-plans/` → 输出为 markdown 代码块给用户复制。

### 生成后自检

- §0 在最前面且是祈使句？
- 每条结论都有出处？
- 每个数字都跑过？
- ⛔ 项和「需裁决」项分开了？
- 自己犯的错写进去了？
- 落盘的话，`CLAUDE.md` 挂上了？

## ⚠️ 改这份 skill 之后

仓库副本改了**不等于生效** —— 运行时读的是
`~/.claude/plugins/cache/indie-toolkit/dev-workflow/<版本>/skills/handoff/SKILL.md`。
要 bump `dev-workflow/.claude-plugin/plugin.json` 的版本并重新发布，cache 才会更新。
