---
name: handoff
description: "Use when ending the current session and transferring ALL current work to a new session (next day, different person), the user says 'handoff', '交接'. Also invoked by dev-workflow:self-pacing at a terminal STOP, where it reads the run's disk artifacts instead of the conversation. End-of-session full transfer — not for mid-session orthogonal splits (use /fork-this for that), and not for the thin locator card a self-pacing stop writes (self-pacing writes that itself)."
disable-model-invocation: false
---

<!-- cost-posture: inherit — this is synthesis, not transcription: deciding what was reversed,
     what only the user can decide, and what the next session will trip on. Downgrading it
     produces a summary, which is the failure mode eval.md's Redundancy Risk section names. -->

<!-- ⚠️ model-invocation is deliberately ON. It is load-bearing for the AFK path where the user
     says "keep going, handoff if you hit a real block" WITHOUT typing /self-pacing — nothing is
     governing there, so without description-match routing nothing fires at the block.
     When /self-pacing IS governing, its Two-tier handoff table decides; this skill is the callee. -->


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

## self-pacing 模式（来源是磁盘，不是聊天）

**触发条件是产物在不在，不是谁调起的**：手上这摊活对应的 `.claude/self-pacing/<slug>.md` 存在 → **先读产物，不要从会话叙述里重建**。self-pacing 明文禁止 narrative reconstruction from chat（其 Step 4：run log + crystal 才是 source of truth），这一条在这里同样成立。

⛔ **不要写成「由 self-pacing 调起时才适用」**。用户「自主推进，遇到重大 block 就 handoff」而**没有**敲 `/self-pacing` 时，没有任何 skill 在管，本 skill 是按 description 匹配直接触发的 —— 那正是最需要读产物的场合（它连自己在一次被跟踪的 run 里都不知道）。按调用方设条件会让这一节在唯一真正需要它的路径上失效。

产物不存在 → 本节不适用，按正常流程从会话上下文写。产物存在但明显属于更早的一摊活 → 照读，但在 §6 注明它是哪一轮的，⛔ 不要把旧 run 的结论当本轮的。

按序读，读完再动笔：

| 读什么 | 它是什么的权威 |
|---|---|
| `.claude/self-pacing/<slug>-handoff.md` | 停在哪、为什么停（本次 STOP 的 delta） |
| `.claude/self-pacing/<slug>.md`（run log） | **发生了什么**——自动裁决、被延后的 nice-to-have、跨过的 seam、flake、截图路径 |
| `docs/11-crystals/*-crystal.md` | **该做什么**——用户锁定的决策 |
| `.claude/execute-plan-checkpoint.json` | 任务级完成映射 |
| `.claude/dev-workflow-state.json` | guide 模式的相位指针 |

映射关系（不是巧合，是同一批事实的两种写法）：

- run log 里被延后的 `nice-to-have` **就是** §5「未决 / 已报未修」——照抄，别重新判定
- checkpoint 的 `completed` map **就是** §可核性第 8 条要的那些数字——从它数，⛔ 不许从聊天里数
- 自动裁决（`recommended` DP 采纳了哪个）进 §1；用户裁决在 crystal 里，进 §6 指针，不重抄
- run log 里同一条判据红了两次、或修了又红——那是 §3「已推翻的」的原料

⛔ **doc 必须带反向指针**：§6 至少列 run-log、checkpoint、stop card 三条绝对路径。实测过一次反面例：`ArtLens/docs/06-plans/HANDOFF-2026-08-18.md` 里 `grep "self-pacing\|run-log\|checkpoint"` 零命中，冷会话只读到 doc 就丢了权威产物。

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

（self-pacing 模式下，这一节**必须**含 run-log / checkpoint / stop card 三条绝对路径）

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

12. 项目有 `docs/06-plans/` → **写成文件** `HANDOFF-YYYY-MM-DD-HHMM.md`（本地 24 小时制，
    时间取生成时刻）。⛔ **不要用 `HANDOFF-YYYY-MM-DD.md`，也不要用 `-EVENING` / `-NIGHT`
    这类要靠判断的后缀** —— 一天停多次是常态（实测：ArtLens 2026-08-18 一天三份，
    裸名 16:38 / `-EVENING` 19:37 / `-NIGHT` 21:07），日期粒度会覆盖，语义后缀会撞。
    时间戳单调，不需要判断「现在算不算晚上」。
13. 写成文件时**照样把 §0 写进文件里** —— 那是给新会话的指令，不是给用户看的说明。
14. 没有 `docs/06-plans/` → 输出为 markdown 代码块给用户复制。

### 挂进项目 CLAUDE.md —— 挂新的，同时摘旧的

⛔ **不挂 = 下个会话不会读到**；但**只挂不摘 = CLAUDE.md 变成交接堆场**。实测反面例：
ArtLens 的 `CLAUDE.md` 里 `HANDOFF` 出现 **22 次**，从第 70 行铺到第 229 行，新会话开场
先吃一个 160 行的交接前言。

动作是两步，一起做：

1. **挂最新**：把本份写进必读顺序的第一条（`**新会话第一件事：读 <路径>**`）。
2. **摘上一条**：把它从必读顺序里降成一行归档指针
   （`历史交接见 docs/06-plans/HANDOFF-*.md`；这一行已存在就不用重复加）。
   ⚠️ 只有 `-HHMM` 命名的文件名倒序等于时间倒序。此前留下的裸日期名与 `-EVENING` / `-NIGHT`
   后缀**不可靠**（实测 ArtLens：`-EVENING` 19:37 早于 `-NIGHT` 21:07 纯属巧合，不是规则），
   要按时间排就看 mtime，别信文件名。
   ⛔ 降级之前，把上一份里**仍然有效**的东西搬进本份 —— 尤其是
   「这条已完成，别再验一遍」这类**防重复劳动**的信息。它不会自己搬家，
   而摘掉挂载之后下个会话就看不见它了。

自检：改完 `CLAUDE.md`，必读顺序里的 `HANDOFF-` 条目是不是**恰好一条**？多于一条 = 第 2 步没做。

### 生成后自检

- §0 在最前面且是祈使句？
- 每条结论都有出处？
- 每个数字都跑过？
- ⛔ 项和「需裁决」项分开了？
- 自己犯的错写进去了？
- 落盘的话，文件名带 `-HHMM` 了？`CLAUDE.md` 必读顺序里的 `HANDOFF-` 条目**恰好一条**？
- self-pacing 模式下：§6 有没有 run-log / checkpoint / stop card 三条路径？§5 是不是照抄了
  run log 里被延后的 `nice-to-have`，而不是自己重判的？

## ⚠️ 改这份 skill 之后

仓库副本改了**不等于生效** —— 运行时读的是
`~/.claude/plugins/cache/indie-toolkit/dev-workflow/<版本>/skills/handoff/SKILL.md`。
要 bump `dev-workflow/.claude-plugin/plugin.json` 的版本并重新发布，cache 才会更新。
