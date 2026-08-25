# handoff Eval

## Trigger Tests
- "handoff"
- "Session is running low on context"
- "Continue this in a new session"

## Negative Trigger Tests
- "Commit my changes"
- "Write a summary"
- "Fork this topic to a separate session" (should route to /fork-this — mid-session orthogonal split, not end-of-session full transfer)
- "Park this for later" (should route to /fork-this)

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
- [ ] 项目有 docs/06-plans/ 时落盘为文件，并挂进项目 CLAUDE.md 必读顺序

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
