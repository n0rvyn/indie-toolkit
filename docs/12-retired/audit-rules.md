# audit-rules（连同 rules-auditor 代理）— 退役于 2026-09-24

**当初要解决什么**：从 AI 执行者的视角审计 CLAUDE.md 规则的冲突、漏洞、缺口和冗余；skill 负责收集上下文，再派 `dev-workflow:rules-auditor` 代理去读。

**为什么退役**：效果不好；而且全局 CLAUDE.md 的审计已定为一个独立会话、按「先建 eval 基线 → 逐条判定 Delete / Shrink / Move / Keep → 分批精简并重跑 eval」的完整闭环来做（种子：`docs/06-plans/2026-09-24-claude-md-eval-audit-trim-seed.md`）。一个 skill 加一次代理阅读给不出这种有对照的结论。60 天记录内调用 0 次；`rules-auditor` 只被本 skill 派发，一起退。

- 来源：session_01WHz4QdvADFm4LqjfETYqn5 用户原话「audit-ruies，应该是为了audit CLAUDE.md 的，但它其它是坏的，效果不咋好，既然定了单独一个session来audit 那个文件，进行规范操作，它的作用没有了，况且，用一个skill来audit CLAUDE.md 也不现实。」

**当时怎么做的**：收集 CLAUDE.md 与相关规则文件 → 派 rules-auditor（只读）→ 按冲突 / 漏洞 / 缺口 / 冗余汇报。`git show 4583a9f:dev-workflow/skills/audit-rules/SKILL.md`、`git show 4583a9f:dev-workflow/agents/rules-auditor.md`

**再做的话要不同在哪**：规则审计的结论要能被证伪——必须有一套改前 / 改后都跑的场景集（并先做 A/A 测噪声），否则「这条冗余」「那条冲突」只是阅读印象。

**如果要重做，形态应该是**：不是 skill，是一次带 eval 的专项工作；需要反复做时再考虑 Workflow 脚本。
