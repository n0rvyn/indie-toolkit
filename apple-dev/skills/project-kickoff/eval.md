# project-kickoff Eval

## Trigger Tests
<!-- Skill has disable-model-invocation: true — ONLY slash invocations should trigger (auto-routing + instructed dispatch are both off) -->
- "/project-kickoff"
- "/project-kickoff 做一个记账 App"  <!-- 2.5 negative control: no mechanism dependency, gate must SKIP -->
- "/project-kickoff 一个手写笔记识别 App"  <!-- 2.5 positive control: accuracy-ceiling dependency, gate must FIRE -->
- "/project-kickoff a habit-formation app that promises users a lasting routine"  <!-- 2.5 positive control: efficacy claim, gate must FIRE -->
- "/project-kickoff 一个按学习风格（视觉型/听觉型）自动匹配课件形式的 App"  <!-- 2.5 core-❌ control: the learning-styles matching hypothesis is a known negative in the literature AND is this product's core mechanism. Expected: 2.5.7 ① halts the flow with the literature quote + source. CP1 is never rendered, so do NOT assert a CP1 verdict here. -->
- "/project-kickoff 一个记账 App，自动把消费短信归类到预算科目"  <!-- 2.5 non-core-❌ control: auto-categorisation accuracy is falsifiable in the literature but is NOT the product's core (manual entry still works). Expected: flow continues, CP1 verdict written in the qualified form, and the entry lands in 6.7's 机制风险 table. -->
- "/project-kickoff a Web expense tracker"
- "/project-kickoff a CLI script runner"

## Negative Trigger Tests
<!-- These read like kickoff requests, but auto-routing is disabled — they must NOT fire; only the /project-kickoff slash invokes this skill -->
- "I want to build a fitness tracking app"
- "Kickoff a new project for expense tracking"
- "新项目开题：做一个 AI 记账助手"
- "Help me validate this app idea"
- "Run a project kickoff flow"
- "新项目开题：做一个 Web 记账工具"
- "Kickoff a new project for a CLI script runner"
- "New project: a cross-platform note-taking app"
- "Write a plan for this feature"
- "Fix this bug"
- "Review my code"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output clarifies requirements through iterative questions (problem, users, angle)
- [ ] Output performs "AI era check" before market research (can existing AI tools solve this?)
- [ ] Output assesses AI replacement risk and identifies irreplaceable value
- [ ] Output keeps the full CP1 展示内容 block (concept table + 领域研究摘要 + Expectation Recap + the AskUserQuestion options) within 20 lines when step 2.5 does not fire, and within 28 lines when it does — measure the whole block, not the first table alone
- [ ] Output uses AskUserQuestion with Continue / Customized / Adjust options
- [ ] Output skips market research for customized projects where client confirmed requirements
- [ ] All 5 checkpoints (CP1, CP2, CP3, CP4, CP5) must contain an [Expectation Recap] block immediately before AskUserQuestion.
- [ ] Step 2.5 gate is evaluated explicitly: a project with no mechanism dependency (e.g. an expense tracker) must SKIP the domain research scan and record "无机制依赖" rather than producing citations. A mechanism-dependent project (e.g. handwriting recognition, habit formation, sleep scoring) must run it.
- [ ] Every URL appearing in the 领域研究 output (CP1 summary table and, later, the project-brief section) is the target of a preceding WebFetch tool call in the same run — check the transcript, not the prose. Any citation with no such call is marked ⚠️ and is absent from CP1's 领域研究判定.
- [ ] Every ✅, ❌, and ⚠️无定论 row carries a transferability verdict (直接适用 / 仅作背景) — not only ✅ rows. Rows whose status is 检索无命中 / 抓不到一手来源 / 一手来源抽验未通过 correctly OMIT it (there is no source to compare against); a verdict invented for one of those is a failure, not a pass.
- [ ] A ⚠️ produced by zero search hits is labeled 检索无命中 (with the queries tried) and NOT 文献无定论; the run shows a positive-control query on a known-hit mechanism before any zero result is reported.

## Redundancy Risk
Baseline comparison: Base model can discuss ideas but lacks structured AI-era feasibility validation and iterative clarification flow
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
