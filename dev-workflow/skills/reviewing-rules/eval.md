# reviewing-rules Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Review the CLAUDE.md rules for conflicts"
- "Claude didn't follow the rules, check what's wrong"
- "Audit the rules for loopholes and gaps"
- "检查规则是否有冲突或漏洞"
- "Do a periodic health check on the rules"
- "Claude added animations without asking — check the rules"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Add a new rule to CLAUDE.md"
- "Write a plan"
- "Review my code quality"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output dispatches to dev-workflow:rules-auditor agent in a separate context
- [ ] Output passes deviation description (or "periodic check") and CLAUDE.md paths to agent
- [ ] Output presents Rules Review Report when agent completes
- [ ] Output presents Decision Points via AskUserQuestion if any blocking decisions exist
- [ ] Output asks user to approve or decline fix recommendations before applying

## Redundancy Risk
Baseline comparison: Base model can read rules but lacks systematic conflict/loophole/gap analysis from AI executor perspective
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
