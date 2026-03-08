# generate-vf-prompt Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Generate a verification prompt for this plan"
- "Create a VF prompt with falsifiable assertions"
- "Generate a design faithfulness check prompt"
- "为这个代码变更生成验证提示词"
- "Create a prompt to verify this implementation"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Execute verification on this plan"
- "Fix the bugs in this plan"
- "Review my code"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output auto-detects content type (plan/code change/UI/architecture/multi-step)
- [ ] Output selects appropriate VF/DF strategies based on content analysis
- [ ] Output generates 3-5 concrete, falsifiable assertions per strategy
- [ ] Output assertions reference actual file paths, function names, and line numbers (no generic placeholders)
- [ ] Output is formatted as a copy-paste prompt (does not execute verification)
- [ ] Output merges multiple strategies into one unified prompt

## Redundancy Risk
Baseline comparison: Base model can generate generic checks but lacks systematic VF/DF strategy selection and egocentric bias override through role separation
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
