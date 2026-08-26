# handoff Eval

## Trigger Tests
- "handoff"
- "Continue this in a new session"
- "跑到重大 block 就 handoff" —— AFK 场景，**没有** `/self-pacing` 在管，靠 description 匹配路由。
  这条是 `disable-model-invocation: false` 的存在理由（`1c70b5b`），改回 `true` 会让它静默失效
- "上下文到 82% 了，交接一下吧" —— **必须带实测 `[ctx]` 数字**才算合法触发

## Negative Trigger Tests
- "Commit my changes"
- "Write a summary"
- "Fork this topic to a separate session" (should route to /fork-this — mid-session orthogonal split, not end-of-session full transfer)
- "Park this for later" (should route to /fork-this)
- "这轮上下文感觉挺满的，先交接吧" —— **裸的感觉，无实测数字 → 不该触发**。
  被禁的是「感觉满了」，不是「高占用时交接」（全局 CLAUDE.md 禁止行为 →
  「断言上下文余量而不引本轮 `[ctx]` 行原文」；self-pacing SKILL.md
  「Context occupancy is not a terminal」）
- self-pacing `phase` 模式停在一个 blocking DP 上 —— 该只写 stop card，**不该**产出 doc
  （self-pacing `## Two-tier handoff` 模式表）

## Output Assertions
- [ ] Output generates cold-start prompt for session transfer
- [ ] Output includes decision history and pending tasks
- [ ] Output is model-agnostic (haiku can generate)
- [ ] Absolute file paths included for key files
- [ ] Key code snippets pasted for context
- [ ] **§0「你（新会话）现在要做的」在最前面，且是祈使句** —— 用户只说
      「handoff from last session」时，续接指令要来自文件而不是他的 prompt
- [ ] **§3 已推翻的** 与 **§4 需用户裁决的** 分成两节，没有混进「下一步」
- [ ] 每条结论带出处（哪份文件的哪一节）
- [ ] 复述要求里写明「数字必须跑过」与「单列没读到/不确定的」
- [ ] 项目有 docs/06-plans/ 时落盘为文件，文件名为 `HANDOFF-YYYY-MM-DD-HHMM.md`（⛔ 不是日期粒度，
      ⛔ 不是 `-EVENING` / `-NIGHT` 这类判断型后缀）
- [ ] 挂进项目 CLAUDE.md 必读顺序，**且把上一条降成一行归档指针** —— 改完必读顺序里
      `HANDOFF-` 恰好一条
- [ ] **self-pacing 模式**：§6 含 run-log / checkpoint / stop card 三条绝对路径（反向指针）
- [ ] **self-pacing 模式**：§5 来自 run log 里被延后的 `nice-to-have`，§可核性的数字来自
      checkpoint `completed` map —— 不是从会话叙述里重建的

## Regression Cases（2026-08-25 实测，改这份 skill 就是为了修它们）
- 新会话复述时写「HANDOFF 全文 289 行」，实际 336 行 —— 数字没跑过却写了「全文」
- 新会话整篇没有一处标注「这条我没核实」—— 没有诚实出口，读了个大概只好写成读全了
- 旧模板把「下一步」和「需用户裁决」混在一起，新会话会把裁决当待办自己做掉

## Redundancy Risk
Baseline comparison: Base model can summarize context but lacks structured cold-start prompt format for session continuity
Last tested model: haiku 4.5
Last tested date: 2026-03-08
Verdict: likely-redundant
⚠️ 2026-08-25 重估：那次 redundancy 判定只看了「能不能总结上下文」。新增的 §0 续接指令与可核性要求，base model 不会自发产出 —— 结论待重测。
