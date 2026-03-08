# finish-branch Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "I'm done with this feature, what's next?"
- "Finish this branch and merge it"
- "Implementation complete, help me integrate the work"
- "这个分支写好了，怎么合并？"
- "Should I create a PR or merge locally?"
- "Clean up this worktree after finishing"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Start a new feature"
- "Write a plan for this task"
- "Fix this bug in the current branch"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output runs test suite and stops if tests fail
- [ ] Output checks for documentation updates needed (feature specs, ADRs, changelog)
- [ ] Output presents exactly 4 options: Merge locally / Create PR / Keep as-is / Discard
- [ ] Output executes the chosen option with correct git commands
- [ ] Output cleans up worktree if applicable
- [ ] Output requires "discard" confirmation before destructive Option 4

## Redundancy Risk
Baseline comparison: Base model can run git commands but lacks structured workflow with test gates and documentation reminders
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
