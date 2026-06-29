# project-kickoff Eval

## Trigger Tests
<!-- Skill has disable-model-invocation: true — ONLY slash invocations should trigger (auto-routing + instructed dispatch are both off) -->
- "/project-kickoff"
- "/project-kickoff 做一个记账 App"
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
- [ ] Output presents project concept confirmation table within 20 lines
- [ ] Output uses AskUserQuestion with Continue / Customized / Adjust options
- [ ] Output skips market research for customized projects where client confirmed requirements
- [ ] All 5 checkpoints (CP1, CP2, CP3, CP4, CP5) must contain an [Expectation Recap] block immediately before AskUserQuestion.

## Redundancy Risk
Baseline comparison: Base model can discuss ideas but lacks structured AI-era feasibility validation and iterative clarification flow
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
