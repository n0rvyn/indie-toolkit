# project-kickoff Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "I want to build a fitness tracking app"
- "Kickoff a new project for expense tracking"
- "新项目开题：做一个 AI 记账助手"
- "Help me validate this app idea"
- "Run a project kickoff flow"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
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

## Redundancy Risk
Baseline comparison: Base model can discuss ideas but lacks structured AI-era feasibility validation and iterative clarification flow
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
