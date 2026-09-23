# design-drift + design-drift-auditor — 退役于 2026-09-23

**当初要解决什么**
项目文档（project-brief、AI-CONTEXT、architecture、ADR、feature spec、dev-guide）写了一套，代码又长成了另一套，两边对不上。design-drift 按已知的文档模板机械地抽出断言，交给 design-drift-auditor 代理逐条对照代码核对，最后出一份漂移报告。

**为什么退役** —— 接线断了，也没人用
- 技能设成了 `user-invocable: false`，而全仓库没有任何技能派发它。call graph 从 09-23 之前起就一直标它是「dispatch-only, but NOTHING dispatches it」。
- 自 2026-08-05 以来调用 0 次。
- 它要解决的问题有现成的去处：计划对设计的忠实度由 plan-verifier 的 DF 策略管，实现对计划的一致性由 implementation-reviewer 管，View 的设计规则由 ui-reviewer 管。剩下「跨多份文档的整体漂移」这一块，在真实项目里从没被要过。

**当时怎么做的**
`git show b30b044:dev-workflow/skills/design-drift/SKILL.md` 与 `git show b30b044:dev-workflow/agents/design-drift-auditor.md`（按模板抽断言的规则都写在代理里）。flow-tracer 代理原本由它派发；这次保留，理由见下。

**再做的话要不同在哪**
先定谁来调用它。一个技能如果对用户隐藏、又没有调用方，写得再好也不会被执行。

**如果要重做，形态应该是**
挂在 review-execution 下的一个只读 lens，触发条件是 diff 同时碰到了 `docs/` 和代码，而不是一个独立的技能加一个代理。

来源：session_013jH44W8QaXm2UExGPkHABs 用户原话「How about retire design-drift too?」
