# handoff Eval

Cases: `evals/handoff/` — run with `claude plugin eval ./dev-workflow --tag handoff --scaffold --allow-tools "Write,Edit,Bash(git:*),Bash(date:*),Bash(ls:*),Bash(wc:*),Bash(mkdir:*),Bash(cat:*)" --trust-plugin --no-publish`. The behavior cases build a git repo in the workspace with `scaffold_script`; without `--scaffold` they run in an empty directory and fail, and without `--allow-tools` every Write-based grader scores 0.

⚠️ 状态（2026-09-27）：15 个用例只过了 $0 加载校验，**从未真跑**（用户决定先不跑）。在第一次真跑之前，别把它们当作已通过的回归门。真跑前先试跑 `--case 'done-*' --ablation none --runs 1` 量成本；`done-with-lesson` / `done-two-candidates` 靠判断，同一配置先跑两次看稳不稳。

## Trigger Tests
Not observable: host-env
- "上下文到 82% 了，交接一下吧" —— **必须带实测 `[ctx]` 数字**才算合法触发。`[ctx]` 行由用户的 `context-budget` hook 注入，eval 运行不加载用户 hook

## Negative Trigger Tests
Not observable: host-env
- "这轮上下文感觉挺满的，先交接吧" —— **裸的感觉，无实测数字 → 不该触发**。
  被禁的是「感觉满了」，不是「高占用时交接」（全局 CLAUDE.md 禁止行为 →
  「断言上下文余量而不引本轮 `[ctx]` 行原文」）。依赖全局 CLAUDE.md，eval 运行不加载它

## Output Assertions
Not observable: 不在封闭清单上的原因 —— 交接文档文件名带时间戳，`{source: file}` 只接受确定路径、不接受通配（官方文档 plugin-evals「What a grader can look at」），`llm` 读不到它的正文；`focus: trace` 又把中段的 Write 省略掉。能用 `tool_used: Write` 的正则核的结构项（§0 在最前、§3 / §4 分节、run-log / checkpoint 反向指针、§5 照抄 run log）已进用例，下面是只有读正文才能判的。
- [ ] 每条结论带出处（哪份文件的哪一节）
- [ ] 复述要求里写明「数字必须跑过」与「单列没读到/不确定的」
- [ ] Key code snippets pasted for context
- [ ] **自主运行模式**：§可核性的数字来自 checkpoint `completed` map，不是从会话叙述里重建的（§5 照抄 run log `nice-to-have` 已进用例 `afk-stop-skips-screen`）
- [ ] **afk dev-guide mode 的一次 stop**：doc 的 §7 写的续跑方式是「敲 `/afk`，再粘它交回的新 `/goal` 行」，⛔ 不是「粘 stop card 上那行」

已删除（2026-09-27）：`Output is model-agnostic (haiku can generate)` —— 与 SKILL.md 顶部 cost-posture 注释矛盾（降级产出的是摘要，正是 Redundancy Risk 点名的失败形态）。

## Regression Cases（2026-08-25 实测，改这份 skill 就是为了修它们）
Not observable: 不在封闭清单上的原因 —— 同上，要读交接文档正文。
- 新会话复述时写「HANDOFF 全文 289 行」，实际 336 行 —— 数字没跑过却写了「全文」
- 新会话整篇没有一处标注「这条我没核实」—— 没有诚实出口，读了个大概只好写成读全了
- 旧模板把「下一步」和「需用户裁决」混在一起，新会话会把裁决当待办自己做掉

## Redundancy Risk
Not observable: 待重测 —— 用 `--ablation with-without` 跑 `evals/handoff/` 的行为用例即可测，本次未跑
Baseline comparison: Base model can summarize context but lacks structured cold-start prompt format for session continuity
Last tested model: haiku 4.5
Last tested date: 2026-03-08
Verdict: likely-redundant
⚠️ 2026-08-25 重估：那次 redundancy 判定只看了「能不能总结上下文」。新增的 §0 续接指令与可核性要求，base model 不会自发产出 —— 结论待重测。
