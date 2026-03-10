# appstoreconnect-review Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Review my App Store Connect submission materials"
- "Help me fill out the ASC fields for submission"
- "检查隐私标签应该怎么填"
- "Pre-submit audit for my app"
- "What data types do I need to declare in App Privacy?"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Review my code quality"
- "Write a plan for this feature"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output correctly identifies review mode (full fill / privacy labels / pre-submit audit / specific section)
- [ ] Output loads appropriate reference files based on mode
- [ ] Mode A: Output walks through fields in order, confirming each major section before proceeding
- [ ] Mode B: Output analyzes code imports/APIs and produces privacy label recommendation table with evidence
- [ ] Mode C: Output runs code audit commands and produces compliance report
- [ ] Mode D: Output answers specific questions with reference citations

## Redundancy Risk
Baseline comparison: Base model cannot access Apple's submission requirements without reference documents; this skill provides structured guidance
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
