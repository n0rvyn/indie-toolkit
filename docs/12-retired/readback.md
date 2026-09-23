# readback — 退役于 2026-09-23

**当初要解决什么**
模型在开始写代码前误解了用户要什么，结果修错了 bug，或者只撤回了一半。`.claude/research/frustration-audit-2026-05-23.md` 里记了好几次。当时的办法是动手前先用大白话把用户的意思复述一遍，让用户确认。

**为什么退役**
想法本身没问题，退役是因为形态选错了：一套机械的机制，替代不了「该复述的时候才复述」这个判断。

- **该复述的时候没复述。** UserPromptSubmit hook 触发时，模型还什么都没读，只能从表面措辞猜有没有歧义。v3 的 hook 头注释自己也承认，v2 为此攒了五组跳过规则、九条中文习语剥离规则，照样会在讨论型的消息上误触发。
- **不该停的时候硬停。** fix-bug 第一步必然派一个 intent-echoer 代理，写状态文件，等用户回「go」。PreToolUse hook 在确认之前拦住所有编辑。token 浪费倒是次要的，主要是每次都要被打断，用户心里不痛快（用户原话见本条末尾）。
- **机制本身的成本很重。** 4 个 hook、v3 状态 schema（带 TTL、会话身份两阶段戳记）、一个代理、一个技能、3 份 reference，另外 write-plan 里还有一整套 echo-only 前置条件。
- **能证明有用的部分，不需要这套机制。** fix-bug 的受控 A/B（`dev-workflow/evals/fix-bug/FINDINGS.md`）里，唯一站得住的差距就是用大白话说出「现在什么样 / 修完什么样」。而那次测试环境里根本没装 readback，是模型自己在回复里复述的。
- 30 天内，`[readback-hint]` 注入了 27 次，intent-echoer 被派了 10 次。

**当时怎么做的**
- `git show b2f8b39:readback/` 看目录。`hooks/`：user-prompt-submit、pre-tool-use、post-tool-use、stop。`agents/intent-echoer.md`。`skills/readback/SKILL.md`。`references/`：speak-rules、state-schema、trigger-detection。
- dev-workflow 那边接的地方：fix-bug 的 Step pre-0，以及 write-plan 的 Step 2.5（含 echo-only 模式）。改动前的版本在 `git show b2f8b39:dev-workflow/skills/fix-bug/SKILL.md`。

**留下了什么**
`dev-workflow/references/readback.md`：什么时候复述、什么时候不复述、复述长什么样（三段式；技术名不做主语；自己加的范围标 `⚠️ AI 补充`）。fix-bug 的「现状 / 预期」块本身就是复述，write-plan Step 2.5 改为按需复述，两处都不停下等确认。

**再做的话要不同在哪**
1. 「什么时候该做」是判断，不是触发条件。hook 触发时模型还没看任何东西，判断不了有没有歧义。
2. 对齐用的步骤默认不停。只有几种读法真的会导向不同的活、猜错会白干时才停。
3. 先确认能测出来的价值在哪一层。这次是大白话复述这一步，不是代理、状态文件和拦截。

**如果要重做，形态应该是**
reference 加上调用方技能里的一两句话，不要 hook，不要代理，不要状态文件。

来源：session_013jH44W8QaXm2UExGPkHABs 用户原话「这种read back的思路，能够在合适的时候用起来就行，现在的方式太机械，该回读的时候它不读人机形成了误解，不该的时候它硬停，浪费token倒事小，主要是造成中断心里不痛快」
